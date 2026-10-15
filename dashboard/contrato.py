"""Validacion estricta del contrato de datos (docs/CONTRATO.md)."""
import json

CLASES = ("piedra", "papel", "tijera", "nada")
FUENTES = ("xiao", "webcam", "simulacion")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validar(linea_o_dict):
    """Devuelve el dict normalizado o None si no cumple el contrato."""
    d = linea_o_dict
    if isinstance(d, (bytes, bytearray)):
        d = d.decode("utf-8", "ignore")
    if isinstance(d, str):
        s = d.strip()
        if not s.startswith("{"):
            return None
        try:
            d = json.loads(s)
        except ValueError:
            return None
    if not isinstance(d, dict) or d.get("v") != 1 or isinstance(d.get("v"), bool):
        return None
    clase = d.get("clase")
    conf = d.get("confianza")
    probs = d.get("probs")
    lat = d.get("lat_ms")
    if clase not in CLASES or not _num(conf) or not 0 <= conf <= 1:
        return None
    if not isinstance(probs, dict) or any(
        k not in probs or not _num(probs[k]) or not 0 <= probs[k] <= 1 for k in CLASES
    ):
        return None
    if not isinstance(lat, dict) or not _num(lat.get("dsp")) or not _num(lat.get("inf")):
        return None
    if not isinstance(d.get("n"), int) or not isinstance(d.get("t_ms"), int):
        return None
    if d.get("fuente") not in FUENTES or not isinstance(d.get("led"), bool) or not _num(d.get("umbral")):
        return None
    return {
        "v": 1,
        "fuente": d["fuente"],
        "n": d["n"],
        "t_ms": d["t_ms"],
        "clase": clase,
        "confianza": float(conf),
        "probs": {k: float(probs[k]) for k in CLASES},
        "lat_ms": {"dsp": lat["dsp"], "inf": lat["inf"]},
        "led": d["led"],
        "umbral": float(d["umbral"]),
    }
