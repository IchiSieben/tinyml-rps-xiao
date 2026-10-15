"""Construye y descarga la biblioteca Arduino (int8) del modelo entrenado, y opcionalmente el .tflite.

  python pipeline/descargar_libreria.py --dry-run
  python pipeline/descargar_libreria.py --tflite
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ei_api import RAIZ, ClienteEI, agregar_args_comunes, salida_utf8  # noqa: E402

ID_APRENDIZAJE = 3


def main(argv=None):
    salida_utf8()
    ap = argparse.ArgumentParser(description="Construye y descarga la biblioteca Arduino de Edge Impulse.")
    ap.add_argument("--nombre", default="rps", help="Prefijo de los archivos en modelos/ (defecto rps)")
    ap.add_argument("--eon", action="store_true", help="Usar EON Compiler (tflite-eon) en lugar de TFLite puro")
    ap.add_argument("--tflite", action="store_true", help="Descargar tambien el .tflite int8 (para inferencia_local.py y SenseCraft)")
    ap.add_argument("--proyecto", default="", help="ID de proyecto (defecto EI_PROJECT_ID o el visible con la clave)")
    ap.add_argument("--led-clase", default="tijera", help="Clase que enciende el LED en el comando sugerido (defecto tijera)")
    ap.add_argument("--umbral", type=float, default=0.60, help="Umbral en el comando sugerido (defecto 0.60)")
    agregar_args_comunes(ap)
    args = ap.parse_args(argv)

    cli = ClienteEI(dry_run=args.dry_run, proyecto=args.proyecto)
    pid = cli.resolver_proyecto()
    modelos = RAIZ / "modelos"
    zip_destino = modelos / f"{args.nombre}_arduino.zip"
    motor = "tflite-eon" if args.eon else "tflite"

    print("1. Construir la biblioteca Arduino (int8)")
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): POST /{projectId}/jobs/build-ondevice-model?type=arduino
    r = cli.peticion("POST", cli.url(f"{pid}/jobs/build-ondevice-model"), {"engine": motor, "modelType": "int8"},
                     params={"type": "arduino"}, simulado={"success": True, "id": 0, "deploymentVersion": 0})
    cli.esperar_trabajo(r.get("id"), "construir biblioteca")

    print("2. Descargar el ZIP")
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): GET /{projectId}/deployment/download (marcado DEPRECATED en el OpenAPI; el
    # reemplazo es GET /{projectId}/deployment/history/{deploymentVersion}/download, que se usa si la API devuelve deploymentVersion)
    version = r.get("deploymentVersion")
    if version and not args.dry_run:
        cli.descargar(cli.url(f"{pid}/deployment/history/{version}/download"), zip_destino)
    else:
        cli.descargar(cli.url(f"{pid}/deployment/download"), zip_destino,
                      params={"type": "arduino", "modelType": "int8", "engine": motor})
    print(f"  {zip_destino}")

    if args.tflite:
        print("3. Descargar el .tflite int8")
        tflite_destino = modelos / f"{args.nombre}_int8.tflite"
        # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): GET /{projectId}/learn-data/{learnId}/model/{modelDownloadId}
        # El modelDownloadId sale de la informacion del proyecto; "tflite-int8" es el valor habitual. NO verificado contra una cuenta real.
        cli.descargar(cli.url(f"{pid}/learn-data/{ID_APRENDIZAJE}/model/tflite-int8"), tflite_destino,
                      nota="si responde 404, descarga el .tflite desde Studio > Dashboard > Download block output")
        print(f"  {tflite_destino}")

    print("Siguiente:")
    print(f"  python firmware/parchear_libreria.py modelos/{zip_destino.name} --led-clase {args.led_clase} --umbral {args.umbral:.2f}")
    if args.dry_run:
        print("[dry-run] No se envio nada.")


if __name__ == "__main__":
    main()
