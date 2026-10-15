"""Inferencia local con un .tflite: webcam (contrato JSON por linea) o evaluacion de carpeta/ZIP.

Ejemplos:
  python pipeline/inferencia_local.py --modelo modelos/rps_int8.tflite --etiquetas piedra,papel,tijera,nada --mostrar
  python pipeline/inferencia_local.py --modelo m.tflite --etiquetas a,b --evaluar datos/listo/testing --salida resultados/eval
"""
import argparse
import csv
import json
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
from contrato import orden_clases  # noqa: E402  (una sola regla de orden para todo el repo)
from tflite_util import (cargar_interprete, cuantizar, detectar_rango,  # noqa: E402
                         info_entrada, info_salida, predecir)

EXT_IMG = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def leer_etiquetas(valor, ruta_modelo):
    """--etiquetas: lista 'a,b,c', ruta a un .txt / model_metadata.h, o (vacio) archivos junto al modelo."""
    candidatos = []
    if valor:
        p = Path(valor)
        if p.is_file():
            candidatos.append(p)
        else:
            return [e.strip() for e in valor.split(",") if e.strip()]
    base = Path(ruta_modelo).resolve().parent
    candidatos += [base / "labels.txt", base / "model_metadata.h"]
    for p in candidatos:
        if not p.is_file():
            continue
        texto = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix == ".h":
            m = re.search(r"ei_classifier_inferencing_categories\s*\[[^\]]*\]\s*=\s*\{([^}]*)\}", texto)
            if m:
                return re.findall(r'"([^"]+)"', m.group(1))
            continue
        etq = [l.strip() for l in texto.splitlines() if l.strip()]
        if len(etq) == 1 and "," in etq[0]:
            etq = [e.strip() for e in etq[0].split(",")]
        if etq:
            return etq
    raise SystemExit("No se encontraron etiquetas: usa --etiquetas piedra,papel,tijera,nada")


class Clasificador:
    def __init__(self, ruta_modelo, etiquetas, rango=None):
        self.interprete = cargar_interprete(ruta_modelo)
        self.ent = info_entrada(self.interprete)
        self.sal = info_salida(self.interprete)
        self.etiquetas = etiquetas
        self.rango = rango or detectar_rango(self.ent)
        _, self.alto, self.ancho, self.canales = self.ent["forma"]
        n = int(self.interprete.get_output_details()[0]["shape"][-1])
        if n != len(etiquetas):
            raise SystemExit(f"El modelo tiene {n} salidas y se dieron {len(etiquetas)} etiquetas")

    def preparar(self, rgb):
        """rgb: uint8 HxWx3. Recorte cuadrado centrado y resize a la entrada del modelo."""
        h, w = rgb.shape[:2]
        lado = min(h, w)
        y0, x0 = (h - lado) // 2, (w - lado) // 2
        img = Image.fromarray(rgb[y0:y0 + lado, x0:x0 + lado]).resize((self.ancho, self.alto), Image.BILINEAR)
        a = np.asarray(img, dtype=np.float32)
        if self.canales == 1:
            a = a.mean(axis=2, keepdims=True)
        return a

    def probs(self, rgb):
        t0 = time.perf_counter()
        x = cuantizar(self.preparar(rgb), self.ent, self.rango)
        t1 = time.perf_counter()
        p = predecir(self.interprete, x, self.ent, self.sal)
        t2 = time.perf_counter()
        if p.min() < 0 or p.sum() > 1.5:
            e = np.exp(p - p.max())
            p = e / e.sum()
        return p, int((t1 - t0) * 1000), int((t2 - t1) * 1000)


def unir_clases_led(una, varias):
    """--led-clase y --led-clases ("a,b") se unen sin repetir; vacio = ninguna."""
    res = []
    for c in ([una] if una else []) + (varias or "").split(","):
        c = c.strip()
        if c and c not in res:
            res.append(c)
    return res


def linea_contrato(fuente, n, t_ms, etiquetas, p, dsp, inf, umbral, clase_led="tijera", clases_led=None):
    """Registro del contrato con TODAS las etiquetas del modelo, en orden de visualizacion.
    El LED se enciende si la clase ganadora esta en clase_led / clases_led y conf >= umbral."""
    d = {e: float(v) for e, v in zip(etiquetas, p)}
    probs = {e: round(d[e], 4) for e in orden_clases(d)}
    clase = max(d, key=d.get)
    conf = round(d[clase], 4)
    leds = set(unir_clases_led(clase_led, ",".join(clases_led) if clases_led else ""))
    return {"v": 1, "fuente": fuente, "n": n, "t_ms": t_ms, "clase": clase, "confianza": conf,
            "probs": probs, "lat_ms": {"dsp": dsp, "inf": inf}, "led": bool(clase in leds and conf >= umbral),
            "umbral": umbral}


def modo_webcam(args, clf):
    import cv2
    cap = cv2.VideoCapture(args.camara)
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir la camara {args.camara}")
    sesion = None
    aviso = False
    url = ""
    if args.enviar:
        import requests
        sesion = requests.Session()
        url = args.enviar.rstrip("/") + "/api/inferencia"
    n, t0 = 0, time.time()
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                print("Camara sin imagen, saliendo", file=sys.stderr)
                break
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            p, dsp, inf = clf.probs(rgb)
            reg = linea_contrato("webcam", n, int((time.time() - t0) * 1000), clf.etiquetas, p, dsp, inf, args.umbral,
                                 clases_led=unir_clases_led(args.led_clase, args.led_clases))
            linea = json.dumps(reg, separators=(",", ":"))
            print(linea, flush=True)
            if sesion:
                try:
                    sesion.post(url, data=linea, headers={"Content-Type": "application/json"}, timeout=0.5)
                except Exception as e:
                    if not aviso:
                        print(f"Aviso: no se pudo enviar a {url}: {e}", file=sys.stderr)
                        aviso = True
            if args.mostrar:
                txt = f"{reg['clase']} {reg['confianza']:.2f}"
                color = (0, 255, 0) if reg["led"] else (0, 0, 255)
                cv2.putText(bgr, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                cv2.imshow("inferencia_local (q para salir)", bgr)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            n += 1
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if args.mostrar:
            cv2.destroyAllWindows()


def listar_imagenes(raiz):
    for carpeta in sorted(p for p in Path(raiz).iterdir() if p.is_dir()):
        for f in sorted(carpeta.rglob("*")):
            if f.suffix.lower() in EXT_IMG:
                yield carpeta.name, f


def extraer_zip_seguro(ruta_zip, destino):
    destino = Path(destino).resolve()
    with zipfile.ZipFile(ruta_zip) as z:
        for m in z.infolist():
            objetivo = (destino / m.filename).resolve()
            if destino not in objetivo.parents and objetivo != destino:
                raise SystemExit(f"ZIP con ruta peligrosa: {m.filename}")
        z.extractall(destino)
    hijos = [p for p in destino.iterdir() if p.is_dir()]
    if len(hijos) == 1 and not any(p.is_file() for p in destino.iterdir()):
        interno = hijos[0]
        if any(p.is_dir() for p in interno.iterdir()) and not any(
                f.suffix.lower() in EXT_IMG for f in interno.iterdir() if f.is_file()):
            return interno
    return destino


def guardar_png_matriz(cm, filas, cols, ruta, titulo):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        from PIL import ImageDraw
        c = 90
        img = Image.new("RGB", (c * (len(cols) + 1), c * (len(filas) + 1)), "white")
        d = ImageDraw.Draw(img)
        for j, nom in enumerate(cols):
            d.text((c * (j + 1) + 5, 10), nom[:12], fill="black")
        for i, nom in enumerate(filas):
            d.text((5, c * (i + 1) + 35), nom[:12], fill="black")
            for j in range(len(cols)):
                v = int(cm[i][j])
                tono = 255 - int(200 * v / max(cm.max(), 1))
                d.rectangle([c * (j + 1), c * (i + 1), c * (j + 2) - 2, c * (i + 2) - 2], fill=(tono, tono, 255), outline="gray")
                d.text((c * (j + 1) + 35, c * (i + 1) + 35), str(v), fill="black")
        img.save(ruta)
        return
    fig, ax = plt.subplots(figsize=(1.2 * len(cols) + 3, 1.0 * len(filas) + 2.5))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(cols)), cols, rotation=30)
    ax.set_yticks(range(len(filas)), filas)
    ax.set_xlabel("Prediccion")
    ax.set_ylabel("Real")
    ax.set_title(titulo)
    for i in range(len(filas)):
        for j in range(len(cols)):
            ax.text(j, i, int(cm[i][j]), ha="center", va="center",
                    color="black" if cm[i][j] < cm.max() / 2 else "white")
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


def evaluar_carpeta(clf, raiz, salida, nombre=""):
    filas_csv, reales, preds = [], [], []
    for real, f in listar_imagenes(raiz):
        rgb = np.asarray(Image.open(f).convert("RGB"))
        p, _, _ = clf.probs(rgb)
        pred = clf.etiquetas[int(np.argmax(p))]
        reales.append(real)
        preds.append(pred)
        filas_csv.append([f"{real}/{f.name}", real, pred, f"{float(p.max()):.4f}", int(real == pred)])
    if not reales:
        raise SystemExit(f"No hay imagenes en subcarpetas de {raiz}")
    cols = list(clf.etiquetas)
    filas = cols + sorted(set(reales) - set(cols))
    cm = np.zeros((len(filas), len(cols)), dtype=int)
    for r, p in zip(reales, preds):
        cm[filas.index(r)][cols.index(p)] += 1
    aciertos = sum(r == p for r, p in zip(reales, preds))
    acc = aciertos / len(reales)
    print(f"Exactitud: {acc:.4f} ({aciertos}/{len(reales)}) rango de entrada: {clf.rango}")
    print("Matriz de confusion (filas = real, columnas = prediccion)")
    print("\t" + "\t".join(cols))
    for i, fila in enumerate(filas):
        print(f"{fila}\t" + "\t".join(str(v) for v in cm[i]))
    if salida:
        salida = Path(salida)
        salida.mkdir(parents=True, exist_ok=True)
        with open(salida / "predicciones.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["archivo", "real", "prediccion", "confianza", "acierto"])
            w.writerows(filas_csv)
        with open(salida / "matriz_confusion.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["real\\prediccion"] + cols)
            for i, fila in enumerate(filas):
                w.writerow([fila] + [int(v) for v in cm[i]])
        guardar_png_matriz(cm, filas, cols, salida / "matriz_confusion.png", f"Exactitud {acc:.3f} {nombre}".strip())
        print(f"Resultados escritos en {salida}")
    return acc, filas, cols, cm


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inferencia local con .tflite: webcam o evaluacion de carpeta/ZIP.")
    ap.add_argument("--modelo", required=True, help="Ruta del .tflite")
    ap.add_argument("--etiquetas", default="", help="Lista 'a,b,c', archivo de texto o model_metadata.h. Orden = orden de salida del modelo")
    ap.add_argument("--camara", type=int, default=0, help="Indice de camara OpenCV (defecto 0)")
    ap.add_argument("--umbral", type=float, default=0.6, help="Confianza minima para el LED logico (defecto 0.6)")
    ap.add_argument("--led-clase", default=None, help="Clase que enciende el LED logico (defecto tijera si no se pasa ninguna bandera de LED)")
    ap.add_argument("--led-clases", default="", help='Lista de clases que encienden el LED logico, ej. "tijera,metal" (se une con --led-clase)')
    ap.add_argument("--enviar", default="", help="URL del dashboard, ej. http://127.0.0.1:5000")
    ap.add_argument("--mostrar", action="store_true", help="Ventana de vista previa con la etiqueta")
    ap.add_argument("--rango", choices=["01", "0255"], help="Forzar rango de pixeles de entrada (defecto: heuristica segun scale/zero_point)")
    ap.add_argument("--evaluar", metavar="CARPETA_O_ZIP", help="Evaluar imagenes en subcarpetas con nombre de clase")
    ap.add_argument("--salida", default="", help="Directorio para CSV y PNG de la evaluacion")
    args = ap.parse_args(argv)

    if not args.led_clase and not args.led_clases:
        args.led_clase = "tijera"
    etiquetas = leer_etiquetas(args.etiquetas, args.modelo)
    clf = Clasificador(args.modelo, etiquetas, args.rango)
    e = clf.ent
    print(f"Entrada {e['forma']} {e['dtype']} scale={e['scale']:.6g} zp={e['zero_point']} rango={clf.rango}", file=sys.stderr)
    if args.evaluar:
        ruta = Path(args.evaluar)
        if ruta.is_file() and ruta.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory() as tmp:
                evaluar_carpeta(clf, extraer_zip_seguro(ruta, tmp), args.salida)
        else:
            evaluar_carpeta(clf, ruta, args.salida)
    else:
        modo_webcam(args, clf)


if __name__ == "__main__":
    main()
