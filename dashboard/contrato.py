"""Validacion estricta del contrato de datos (docs/CONTRATO.md)."""
import json
import re

BASE = ("piedra", "papel", "tijera", "nada")
CLASES = BASE  # alias historico
ETIQUETA = re.compile(r"^[a-z0-9_]{1,24}$")
MIN_CLASES, MAX_CLASES = 2, 16
FUENTES = ("xiao", "webcam", "simulacion")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def orden_clases(claves):
    """Orden de visualizacion: primero las BASE presentes, luego el resto en el orden recibido."""
    claves = list(claves)
    return [c for c in BASE if c in claves] + [c for c in claves if c not in BASE]


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
    if not isinstance(clase, str) or not _num(conf) or not 0 <= conf <= 1:
        return None
    if not isinstance(probs, dict) or not MIN_CLASES <= len(probs) <= MAX_CLASES:
        return None
    if any(not isinstance(k, str) or not ETIQUETA.match(k) or not _num(v) or not 0 <= v <= 1
           for k, v in probs.items()):
        return None
    if clase not in probs:
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
        "probs": {k: float(probs[k]) for k in orden_clases(probs)},
        "lat_ms": {"dsp": lat["dsp"], "inf": lat["inf"]},
        "led": d["led"],
        "umbral": float(d["umbral"]),
    }
