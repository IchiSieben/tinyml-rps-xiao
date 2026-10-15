"""Prepara el dataset: valida, deduplica, recorta/redimensiona y reparte 80/20 estratificado.

Entrada: datos/crudas/<clase>/*.jpg  o  ZIPs de la pagina de captura (un ZIP por clase, la clase
sale del nombre del archivo: piedra.zip, papel.zip...). Salida: datos/listo/{training,testing}/<clase>/
y datos/listo/manifiesto.csv.

  python pipeline/preparar_dataset.py --entrada datos/crudas
  python pipeline/preparar_dataset.py --zips piedra.zip papel.zip tijera.zip nada.zip --dry-run
"""
import argparse
import csv
import io
import random
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

EXT_IMG = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MIN_POR_CLASE = 30
ETIQUETA = re.compile(r"^[a-z0-9_]{1,24}$")  # regla del contrato (docs/CONTRATO.md)


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def nombre_clase(s):
    return sin_acentos(s).strip().lower().replace(" ", "_")


def recolectar(entrada, zips):
    """Devuelve lista de (clase, origen, bytes_o_ruta)."""
    items = []
    if entrada:
        raiz = Path(entrada)
        if not raiz.is_dir():
            raise SystemExit(f"No existe la carpeta de entrada: {raiz}")
        for carpeta in sorted(p for p in raiz.iterdir() if p.is_dir()):
            for f in sorted(carpeta.rglob("*")):
                if f.suffix.lower() in EXT_IMG:
                    items.append((nombre_clase(carpeta.name), str(f), f))
    for z in zips or []:
        zp = Path(z)
        if not zp.is_file():
            raise SystemExit(f"No existe el ZIP: {zp}")
        clase = nombre_clase(zp.stem)
        with zipfile.ZipFile(zp) as zf:
            for m in sorted(zf.namelist()):
                if m.endswith("/") or Path(m).suffix.lower() not in EXT_IMG:
                    continue
                items.append((clase, f"{zp.name}:{m}", zf.read(m)))
    return items


def abrir(dato):
    img = Image.open(dato if isinstance(dato, Path) else io.BytesIO(dato))
    img.load()
    return img.convert("RGB")


def hash_promedio(img):
    g = img.convert("L").resize((8, 8), Image.BILINEAR)
    px = list(g.tobytes())
    m = sum(px) / 64
    return sum(1 << i for i, v in enumerate(px) if v >= m)


def distancia(a, b):
    return bin(a ^ b).count("1")


def recortar(img, tam):
    w, h = img.size
    lado = min(w, h)
    x0, y0 = (w - lado) // 2, (h - lado) // 2
    img = img.crop((x0, y0, x0 + lado, y0 + lado))
    return img.resize((tam, tam), Image.LANCZOS) if tam else img


def repartir(n, prueba):
    if n < 2:
        return 0
    return max(1, round(n * prueba))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valida, deduplica, redimensiona y reparte el dataset 80/20 estratificado.")
    ap.add_argument("--entrada", default="", help="Carpeta con una subcarpeta por clase (defecto datos/crudas si existe)")
    ap.add_argument("--zips", nargs="*", default=[], help="ZIPs por clase de la pagina de captura; la clase sale del nombre")
    ap.add_argument("--salida", default="datos/listo", help="Directorio de salida (defecto datos/listo)")
    ap.add_argument("--tam", type=int, default=96, help="Lado en pixeles tras el recorte cuadrado centrado; 0 = conservar (defecto 96)")
    ap.add_argument("--prueba", type=float, default=0.2, help="Fraccion para testing (defecto 0.2)")
    ap.add_argument("--semilla", type=int, default=42, help="Semilla del reparto (defecto 42)")
    ap.add_argument("--hash-umbral", type=int, default=2, help="Distancia Hamming maxima (de 64 bits) para considerar duplicada (defecto 2)")
    ap.add_argument("--dry-run", action="store_true", help="Muestra el plan sin escribir archivos")
    args = ap.parse_args(argv)

    entrada = args.entrada or ("datos/crudas" if not args.zips and Path("datos/crudas").is_dir() else "")
    if not entrada and not args.zips:
        raise SystemExit("Indica --entrada CARPETA o --zips a.zip b.zip ...")

    items = recolectar(entrada, args.zips)
    if not items:
        raise SystemExit("No se encontraron imagenes")

    invalidas, vistos, conservadas = [], defaultdict(list), defaultdict(list)
    duplicadas = 0
    cruzadas = 0
    for clase, origen, dato in items:
        try:
            img = abrir(dato)
        except Exception as e:
            invalidas.append((origen, type(e).__name__))
            continue
        h = hash_promedio(img)
        if any(distancia(h, o) <= args.hash_umbral for o in vistos[clase]):
            duplicadas += 1
            continue
        if any(distancia(h, o) <= args.hash_umbral for c, hs in vistos.items() if c != clase for o in hs):
            cruzadas += 1
        vistos[clase].append(h)
        conservadas[clase].append((origen, img, h))

    rng = random.Random(args.semilla)
    plan = {}
    for clase in sorted(conservadas):
        lista = sorted(conservadas[clase], key=lambda t: t[0])
        rng.shuffle(lista)
        n_test = repartir(len(lista), args.prueba)
        plan[clase] = {"testing": lista[:n_test], "training": lista[n_test:]}

    total_leido = len(items)
    print(f"Imágenes leídas: {total_leido}, inválidas: {len(invalidas)}, duplicadas descartadas: {duplicadas}")
    print(f"{'clase':<12}{'training':>10}{'testing':>10}")
    for c, d in plan.items():
        print(f"{c:<12}{len(d['training']):>10}{len(d['testing']):>10}")
    for origen, motivo in invalidas[:10]:
        print(f"Aviso: imagen inválida ({motivo}): {origen}")
    for c, d in plan.items():
        n = len(d["training"]) + len(d["testing"])
        if n < MIN_POR_CLASE:
            print(f"Aviso: la clase '{c}' tiene {n} imágenes útiles (mínimo recomendado {MIN_POR_CLASE})")
    for c in plan:
        if not ETIQUETA.fullmatch(c):
            print(f"Aviso: el nombre de clase '{c}' no cumple el contrato (minúsculas ASCII, dígitos y _, hasta 24); "
                  "renombra la carpeta o el ZIP antes de subir")
    if len(plan) > 16:
        print(f"Aviso: hay {len(plan)} clases y el contrato admite hasta 16")
    valid = total_leido - len(invalidas)
    if valid and duplicadas / valid > 0.2:
        print(f"Aviso: {duplicadas / valid:.0%} de las imagenes eran casi duplicadas; captura mas variedad (angulos, fondos, luz)")
    if cruzadas:
        print(f"Aviso: {cruzadas} imagenes se parecen a otras de una clase distinta (revisar etiquetas)")

    if args.dry_run:
        print(f"[dry-run] Se escribiria en {args.salida}/{{training,testing}}/<clase>/ (lado {args.tam or 'original'}) y {args.salida}/manifiesto.csv. No se escribio nada.")
        return

    salida = Path(args.salida)
    for sub in ("training", "testing"):
        d = salida / sub
        if d.exists() and any(d.iterdir()):
            raise SystemExit(f"{d} ya tiene archivos. Muevelo o usa otra --salida (el script nunca borra).")
    filas = []
    for clase, d in plan.items():
        for split, lista in d.items():
            carpeta = salida / split / clase
            carpeta.mkdir(parents=True, exist_ok=True)
            for i, (origen, img, h) in enumerate(lista):
                nombre = f"{clase}.{split[:2]}{i:04d}.jpg"
                recortar(img, args.tam).save(carpeta / nombre, quality=95)
                filas.append([f"{split}/{clase}/{nombre}", clase, split, origen, f"{h:016x}"])
    with open(salida / "manifiesto.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["archivo", "clase", "split", "origen", "ahash"])
        w.writerows(sorted(filas))
    print(f"Escrito: {len(filas)} imagenes y manifiesto en {salida}")


if __name__ == "__main__":
    sys.exit(main())
