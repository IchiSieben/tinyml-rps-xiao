"""Ayudante compartido: carga del interprete TFLite y cuantizacion.

Cadena de importacion: ai_edge_litert -> tflite_runtime -> tensorflow.lite.
"""
import numpy as np


def cargar_interprete(ruta_modelo):
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            try:
                import tensorflow as tf
                Interpreter = tf.lite.Interpreter
            except ImportError as e:
                raise SystemExit(
                    "No hay interprete TFLite. Instala ai-edge-litert o tensorflow."
                ) from e
    interprete = Interpreter(model_path=str(ruta_modelo))
    interprete.allocate_tensors()
    return interprete


def info_entrada(interprete):
    d = interprete.get_input_details()[0]
    scale, zp = d["quantization"] if d.get("quantization") else (0.0, 0)
    return {
        "indice": d["index"],
        "forma": tuple(int(x) for x in d["shape"]),
        "dtype": np.dtype(d["dtype"]),
        "scale": float(scale),
        "zero_point": int(zp),
    }


def info_salida(interprete):
    d = interprete.get_output_details()[0]
    scale, zp = d["quantization"] if d.get("quantization") else (0.0, 0)
    return {
        "indice": d["index"],
        "dtype": np.dtype(d["dtype"]),
        "scale": float(scale),
        "zero_point": int(zp),
    }


def detectar_rango(info):
    """Heuristica del rango de pixeles de entrada: devuelve '01' o '0255'.

    Un modelo float32 o sin escala se asume en [0,1]. En int8/uint8 el valor
    cuantizado cubre [(qmin-zp)*scale, (qmax-zp)*scale]. Si ese techo es ~1
    (scale ~1/255, caso Edge Impulse) la entrada esperada es [0,1]; si es ~255
    (scale ~1, caso tipico de SenseCraft) es [0,255]. Se puede forzar con --rango.
    """
    if info["dtype"] == np.float32 or info["scale"] <= 0:
        return "01"
    q = np.iinfo(info["dtype"])
    techo = (q.max - info["zero_point"]) * info["scale"]
    return "01" if techo <= 2.0 else "0255"


def cuantizar(x01_255, info, rango):
    """x01_255: float32 en [0,255]. Devuelve el tensor listo para el modelo."""
    x = x01_255.astype(np.float32)
    if rango == "01":
        x = x / 255.0
    if info["dtype"] == np.float32:
        return x
    q = np.iinfo(info["dtype"])
    s = info["scale"] if info["scale"] > 0 else 1.0
    return np.clip(np.round(x / s) + info["zero_point"], q.min, q.max).astype(info["dtype"])


def dequantizar(salida, info):
    s = salida.astype(np.float32)
    if info["dtype"] != np.float32 and info["scale"] > 0:
        s = (s - info["zero_point"]) * info["scale"]
    return s


def predecir(interprete, entrada, info_in, info_out):
    interprete.set_tensor(info_in["indice"], entrada[np.newaxis, ...])
    interprete.invoke()
    out = interprete.get_tensor(info_out["indice"])[0]
    return dequantizar(out, info_out)
