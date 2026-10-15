"""Entrena en Edge Impulse solo por API: impulso, features, transfer learning, metricas.

Orden: proyecto -> impulso -> config DSP -> generar features -> config Keras -> entrenar -> metricas
-> (opcional) test del modelo. Guarda resultados/entrenamiento_<fecha>.json.
Docs (OpenAPI https://studio.edgeimpulse.com/openapi.yml, referencia https://docs.edgeimpulse.com/reference):

  python pipeline/entrenar.py --dry-run
  python pipeline/entrenar.py --probar
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ei_api import RAIZ, ClienteEI, agregar_args_comunes, salida_utf8  # noqa: E402

ID_ENTRADA, ID_DSP, ID_APRENDIZAJE = 1, 2, 3


def cuerpo_impulso(tam, nombre):
    return {
        "name": nombre,
        "inputBlocks": [{
            "id": ID_ENTRADA, "type": "image", "name": "image", "title": "Image data",
            "imageWidth": tam, "imageHeight": tam, "resizeMode": "fit-short",
        }],
        "dspBlocks": [{
            "id": ID_DSP, "type": "image", "name": "Image", "title": "Image", "axes": ["image"],
            "input": ID_ENTRADA, "implementationVersion": 1,
        }],
        "learnBlocks": [{
            "id": ID_APRENDIZAJE, "type": "keras-transfer-image", "name": "Transfer learning",
            "title": "Transfer Learning (Images)", "dsp": [ID_DSP],
        }],
    }


def cuerpo_keras(ciclos, tasa, capa):
    return {
        "mode": "visual",
        "visualLayers": [{"type": capa, "neurons": 16, "dropoutRate": 0.1}],
        "trainingCycles": ciclos,
        "learningRate": tasa,
        "trainTestSplit": 0.2,
        "autoClassWeights": True,
        "augmentationPolicyImage": "all",
        "selectedModelType": "int8",
    }


def main(argv=None):
    salida_utf8()
    ap = argparse.ArgumentParser(description="Entrena el clasificador en Edge Impulse por API.")
    ap.add_argument("--tam", type=int, default=96, help="Lado de la imagen de entrada (defecto 96)")
    ap.add_argument("--ciclos", type=int, default=20, help="Ciclos de entrenamiento (defecto 20)")
    ap.add_argument("--tasa", type=float, default=0.0005, help="Learning rate (defecto 0.0005)")
    ap.add_argument("--capa", default="transfer_mobilenetv2_a35",
                    help="Base de transfer learning (defecto transfer_mobilenetv2_a35 = MobileNetV2 0.35 de 96x96)")
    ap.add_argument("--probar", action="store_true", help="Al final clasifica todo el conjunto testing")
    ap.add_argument("--proyecto", default="", help="ID de proyecto (defecto EI_PROJECT_ID o el unico visible con la clave)")
    ap.add_argument("--sondeo", type=int, default=5, help="Segundos entre consultas de estado (defecto 5)")
    agregar_args_comunes(ap)
    args = ap.parse_args(argv)

    cli = ClienteEI(dry_run=args.dry_run, proyecto=args.proyecto)
    print("1. Proyecto")
    pid = cli.resolver_proyecto()
    p = f"{pid}"

    print("2. Impulso (imagen + DSP image + Transfer Learning)")
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): POST /{projectId}/impulse
    cli.peticion("POST", cli.url(f"{p}/impulse"), cuerpo_impulso(args.tam, f"rps-{args.tam}x{args.tam}"))

    print("3. DSP: color RGB")
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): POST /{projectId}/dsp/{dspId}  (la clave 'channels' es la del bloque image)
    cli.peticion("POST", cli.url(f"{p}/dsp/{ID_DSP}"), {"config": {"channels": "RGB"}})

    print("4. Generar features")
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): POST /{projectId}/jobs/generate-features
    r = cli.peticion("POST", cli.url(f"{p}/jobs/generate-features"),
                     {"dspId": ID_DSP, "calculateFeatureImportance": False, "skipFeatureExplorer": True},
                     simulado={"success": True, "id": 0})
    cli.esperar_trabajo(r.get("id"), "generar features", args.sondeo)

    print("5. Configurar Keras (transfer learning visual)")
    cuerpo = cuerpo_keras(args.ciclos, args.tasa, args.capa)
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): POST /{projectId}/training/keras/{learnId}
    cli.peticion("POST", cli.url(f"{p}/training/keras/{ID_APRENDIZAJE}"), cuerpo)

    print("6. Entrenar")
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): POST /{projectId}/jobs/train/keras/{learnId}
    r = cli.peticion("POST", cli.url(f"{p}/jobs/train/keras/{ID_APRENDIZAJE}"), cuerpo,
                     simulado={"success": True, "id": 0})
    cli.esperar_trabajo(r.get("id"), "entrenamiento", args.sondeo)

    print("7. Metricas de validacion")
    # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): GET /{projectId}/training/keras/{learnId}/metadata
    meta = cli.peticion("GET", cli.url(f"{p}/training/keras/{ID_APRENDIZAJE}/metadata"),
                        simulado={"success": True, "classNames": [], "modelValidationMetrics": []})
    metricas = {"fecha": datetime.now().isoformat(timespec="seconds"), "proyecto": pid,
                "clases": meta.get("classNames", []), "validacion": {}}
    for m in meta.get("modelValidationMetrics", []):
        metricas["validacion"][m["type"]] = {"accuracy": m.get("accuracy"), "loss": m.get("loss"),
                                             "matriz_confusion": m.get("confusionMatrix")}
        print(f"  {m['type']}: exactitud {m.get('accuracy')} perdida {m.get('loss')}")

    if args.probar:
        print("8. Probar con el conjunto testing")
        # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): POST /{projectId}/jobs/classify
        r = cli.peticion("POST", cli.url(f"{p}/jobs/classify"), {"modelVariants": ["int8"]}, simulado={"success": True, "id": 0})
        cli.esperar_trabajo(r.get("id"), "clasificar testing", args.sondeo)
        # openapi.yml (https://studio.edgeimpulse.com/openapi.yml): GET /{projectId}/classify/all/result
        res = cli.peticion("GET", cli.url(f"{p}/classify/all/result"), params={"variant": "int8"},
                           simulado={"success": True, "accuracy": {}})
        acc = res.get("accuracy", {})
        metricas["testing_int8"] = {"accuracy": acc.get("accuracyScore"), "balanced": acc.get("balancedAccuracyScore"),
                                    "matriz_confusion": acc.get("confusionMatrixValues"), "clases": acc.get("allLabels")}
        print(f"  testing int8: exactitud {acc.get('accuracyScore')}")

    if args.dry_run:
        print("[dry-run] No se envio nada ni se escribio el JSON de metricas.")
        return
    destino = RAIZ / "resultados" / f"entrenamiento_{datetime.now():%Y%m%d_%H%M}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Metricas guardadas en {destino}")
    print("Siguiente: python pipeline/descargar_libreria.py")


if __name__ == "__main__":
    main()
