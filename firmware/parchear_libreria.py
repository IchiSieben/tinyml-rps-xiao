#!/usr/bin/env python3
"""Adapta la libreria Arduino exportada por Edge Impulse a la XIAO ESP32S3 Sense."""
import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
INO_REL = "examples/esp32/esp32_camera/esp32_camera.ino"

RE_PINES = re.compile(
    r"(?:^[ \t]*(?://)?[ \t]*#define[ \t]+CAMERA_MODEL_\w+[^\n]*\n)+"
    r"\s*#if defined\(CAMERA_MODEL_.*?#error[^\n]*\n#endif[^\n]*\n",
    re.DOTALL | re.MULTILINE,
)
RE_ARENA_DEFINE = re.compile(r"(#define[ \t]+EI_CLASSIFIER_\w*ARENA_SIZE[ \t]+)\d+")
RE_ARENA_CONST = re.compile(r"(\b\w*_arena_size[ \t]*=[ \t]*)\d+")


class ErrorParche(Exception):
    pass


def extraer(zip_ruta: Path, destino: Path) -> None:
    try:
        with zipfile.ZipFile(zip_ruta) as z:
            raiz = destino.resolve()
            for nombre in z.namelist():
                if not (raiz / nombre).resolve().is_relative_to(raiz):
                    raise ErrorParche(f"El ZIP contiene una ruta insegura: {nombre}")
            z.extractall(destino)
    except zipfile.BadZipFile:
        raise ErrorParche(f"'{zip_ruta}' no es un ZIP valido.")


def parchear_ino(ino: Path, clase_led, umbral: float) -> list[str]:
    texto = ino.read_text(encoding="utf-8")
    if "xiao_pins.h" in texto:
        return ["esp32_camera.ino ya estaba parcheado, sin cambios"]
    msgs = []
    if not RE_PINES.search(texto):
        raise ErrorParche(
            "No se encontro el bloque de seleccion de camara (CAMERA_MODEL_* ... #error) en "
            "esp32_camera.ino. La plantilla de Edge Impulse cambio o el ZIP no es el esperado."
        )
    inc = '#include "xiao_pins.h"\n#include "salida_json.h"\n'
    texto = RE_PINES.sub(lambda m: inc, texto, count=1)
    msgs.append("bloque de pines ESP_EYE/AI_THINKER reemplazado por xiao_pins.h")

    ini = texto.find("// print the predictions")
    fin = texto.find("free(snapshot_buf);", ini) if ini >= 0 else -1
    if ini < 0 or fin < 0:
        raise ErrorParche("No se encontro el bloque de impresion de resultados en loop().")
    if clase_led:
        led = f'bool led = actualizar_led(clase_ganadora, conf_ganadora, "{clase_led}", {umbral:.2f}f);'
    else:
        led = "bool led = false;"
    bloque = (
        "// salida JSON, una linea por inferencia (docs/CONTRATO.md)\n"
        "    {\n"
        "        static uint32_t n_inferencia = 0;\n"
        "        const char *clase_ganadora;\n"
        "        float conf_ganadora;\n"
        "        sj_ganadora(result, &clase_ganadora, &conf_ganadora);\n"
        f"        {led}\n"
        f"        emitir_json(result, n_inferencia++, {umbral:.2f}f, led);\n"
        "    }\n\n    "
    )
    texto = texto[:ini] + bloque + texto[fin:]
    msgs.append("impresion ei_printf de resultados reemplazada por emitir_json()")
    msgs.append(f"LED: {'clase ' + clase_led if clase_led else 'desactivado'}, umbral {umbral:.2f}")
    ino.write_text(texto, encoding="utf-8", newline="\n")
    return msgs


def parchear_arena(raiz: Path, arena: int) -> list[str]:
    msgs = []
    candidatos = [p for p in (raiz / "src").rglob("*") if p.suffix in (".h", ".cpp")
                  and (p.name.startswith("tflite_learn_") or p.name == "model_metadata.h")]
    for p in sorted(candidatos):
        original = p.read_text(encoding="utf-8", errors="replace")
        nuevo = RE_ARENA_DEFINE.sub(lambda m: f"{m.group(1)}{arena}", original)
        nuevo = RE_ARENA_CONST.sub(lambda m: f"{m.group(1)}{arena}", nuevo)
        if nuevo != original:
            p.write_text(nuevo, encoding="utf-8", newline="\n")
            msgs.append(f"arena = {arena} en {p.relative_to(raiz).as_posix()}")
    if not msgs:
        msgs.append("no se encontro ningun define de arena para cambiar (o ya tenia ese valor)")
    return msgs


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Parchea la libreria Arduino de Edge Impulse (ZIP) para la XIAO ESP32S3 Sense.")
    ap.add_argument("zip", type=Path, help="ZIP de la libreria Arduino exportada desde Edge Impulse")
    ap.add_argument("--salida", type=Path, help="ZIP de salida (por defecto <entrada>_xiao.zip)")
    ap.add_argument("--arena", type=int, help="tamano del tensor arena; usar 384605 si falta memoria")
    ap.add_argument("--led-clase", help="clase que enciende el LED (piedra, papel, tijera, nada)")
    ap.add_argument("--umbral", type=float, default=0.60, help="confianza minima para el LED (0.60)")
    a = ap.parse_args()

    try:
        if not a.zip.is_file():
            raise ErrorParche(f"No existe el archivo '{a.zip}'.")
        salida = a.salida or a.zip.with_name(a.zip.stem + "_xiao.zip")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            extraer(a.zip, tmp)
            inos = sorted(tmp.rglob(INO_REL))
            if not inos:
                raise ErrorParche(
                    f"No se encontro {INO_REL} dentro del ZIP. Exporta la libreria desde Edge "
                    "Impulse con Deployment > Arduino library.")
            ino = inos[0]
            raiz_lib = ino.parents[3]
            msgs = parchear_ino(ino, a.led_clase, a.umbral)
            for h in ("xiao_pins.h", "salida_json.h"):
                shutil.copyfile(AQUI / h, ino.parent / h)
            msgs.append("xiao_pins.h y salida_json.h copiados junto al .ino")
            if a.arena:
                msgs += parchear_arena(raiz_lib, a.arena)
            salida.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
                for p in sorted(tmp.rglob("*")):
                    if p.is_file():
                        z.write(p, p.relative_to(tmp).as_posix())
        for m in msgs:
            print(f"- {m}")
        print(f"Listo: {salida}")
        return 0
    except ErrorParche as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
