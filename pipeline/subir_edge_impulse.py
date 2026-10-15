"""Sube datos/listo/{training,testing}/<clase>/ a Edge Impulse con la Ingestion API.

POST https://ingestion.edgeimpulse.com/api/{training|testing}/files
  cabeceras: x-api-key, x-label (clase); campo multipart `data` (varios archivos por peticion)
Doc: https://docs.edgeimpulse.com/reference/ingestion-api/ingestion-api

  python pipeline/subir_edge_impulse.py --dry-run
  python pipeline/subir_edge_impulse.py
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ei_api import INGESTION, ClienteEI, agregar_args_comunes, enmascarar, salida_utf8  # noqa: E402

EXT = {".jpg", ".jpeg", ".png"}


def lotes(lista, n):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]


def main(argv=None):
    salida_utf8()
    ap = argparse.ArgumentParser(description="Sube el dataset preparado a Edge Impulse (Ingestion API).")
    ap.add_argument("--datos", default="datos/listo", help="Carpeta con training/ y testing/ (defecto datos/listo)")
    ap.add_argument("--lote", type=int, default=20, help="Archivos por peticion (defecto 20)")
    agregar_args_comunes(ap)
    args = ap.parse_args(argv)

    cli = ClienteEI(dry_run=args.dry_run)
    base = Path(args.datos)
    total = 0
    peticiones = []
    for split in ("training", "testing"):
        raiz = base / split
        if not raiz.is_dir():
            print(f"Aviso: no existe {raiz} (corre primero preparar_dataset.py)")
            continue
        for carpeta in sorted(p for p in raiz.iterdir() if p.is_dir()):
            archivos = sorted(f for f in carpeta.iterdir() if f.suffix.lower() in EXT)
            for lote in lotes(archivos, args.lote):
                peticiones.append((split, carpeta.name, lote))
            print(f"{split:<9}{carpeta.name:<12}{len(archivos):>5} archivos")
            total += len(archivos)
    print(f"Total: {total} archivos en {len(peticiones)} peticiones de hasta {args.lote}")

    if args.dry_run:
        vistos = set()
        for split, clase, lote in peticiones:
            if (split, clase) in vistos:
                continue
            vistos.add((split, clase))
            cli.mostrar("POST", f"{INGESTION}/{split}/files", extra_cab={"x-label": clase},
                        nota=f"multipart campo 'data', hasta {args.lote} archivos por peticion (ej. {len(lote)} en el primer lote de {clase}); clave {enmascarar(cli.clave)}")
        print("[dry-run] No se envio nada.")
        return

    subidos = fallidos = 0
    for split, clase, lote in peticiones:
        manejadores = [open(f, "rb") for f in lote]
        try:
            files = [("data", (f.name, fh, "image/jpeg" if f.suffix.lower() != ".png" else "image/png"))
                     for f, fh in zip(lote, manejadores)]
            ultimo = None
            for intento in range(4):
                for fh in manejadores:
                    fh.seek(0)
                r = cli.sesion.post(f"{INGESTION}/{split}/files", headers={"x-label": clase}, files=files, timeout=120)
                if r.status_code == 200:
                    for item in r.json().get("files", []):
                        if item.get("success"):
                            subidos += 1
                        else:
                            fallidos += 1
                            print(f"  fallo {item.get('fileName')}: {item.get('error')}")
                    break
                ultimo = f"HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(2 ** (intento + 1))
            else:
                fallidos += len(lote)
                print(f"Lote {split}/{clase} fallo: {ultimo}")
        finally:
            for fh in manejadores:
                fh.close()
        print(f"  {split}/{clase}: {subidos} subidos, {fallidos} fallidos", flush=True)
    print(f"Listo: {subidos} subidos, {fallidos} fallidos")
    if fallidos:
        sys.exit(1)


if __name__ == "__main__":
    main()
