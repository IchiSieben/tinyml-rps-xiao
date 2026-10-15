"""Servidor del dashboard: recibe inferencias (simulacion, serie o HTTP) y las reenvia por SSE."""
import argparse
import json
import os
import queue
import random
import sys
import threading
import time
from collections import deque

from flask import Flask, Response, jsonify, request, send_from_directory

try:
    from .contrato import BASE, ETIQUETA, orden_clases, validar
except ImportError:
    from contrato import BASE, ETIQUETA, orden_clases, validar

AQUI = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)


class Estado:
    def __init__(self):
        self.lock = threading.Lock()
        self.clientes = []
        self.fuente = "ninguna"
        self.conectado = False
        self.inicio = time.time()
        self.ultimas = deque(maxlen=50)
        self.conteos = {}
        self.vistas = []  # clases vistas, en orden de llegada
        self.puerto = ""
        self.ultima = None

    def publicar(self, d):
        with self.lock:
            self.ultimas.append(d)
            self.conteos[d["clase"]] = self.conteos.get(d["clase"], 0) + 1
            for k in d["probs"]:
                if k not in self.vistas:
                    self.vistas.append(k)
            self.ultima = d
            clientes = list(self.clientes)
        msg = json.dumps(d, separators=(",", ":"))
        for q in clientes:
            try:
                q.put_nowait(msg)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(msg)
                except (queue.Empty, queue.Full):
                    pass

    def resumen(self):
        with self.lock:
            u = list(self.ultimas)
            n = len(u)
            return {
                "fuente": self.fuente,
                "conectado": self.conectado,
                "puerto": self.puerto,
                "clases": orden_clases(self.vistas),
                "conteos": dict(self.conteos),
                "ultima": self.ultima,
                "uptime_s": round(time.time() - self.inicio, 1),
                "ventana": n,
                "lat_media_ms": {
                    "dsp": round(sum(x["lat_ms"]["dsp"] for x in u) / n, 1) if n else 0,
                    "inf": round(sum(x["lat_ms"]["inf"] for x in u) / n, 1) if n else 0,
                },
            }


E = Estado()


SEG_POR_ELEMENTO = 1.6  # un elemento del guion dura esto por defecto (la clase se mantiene > 1 s)


def parsear_guion(texto):
    """'piedra,papel:2,metal' -> [('piedra', 1.6), ('papel', 2.0), ('metal', 1.6)]. ValueError si no cumple."""
    items = []
    for crudo in (texto or "").split(","):
        s = crudo.strip()
        if not s:
            continue
        nombre, _, seg = s.partition(":")
        nombre = nombre.strip()
        if not ETIQUETA.fullmatch(nombre):
            raise ValueError(f"etiqueta de guion no válida: '{nombre}' (usa minúsculas ASCII, dígitos y _, hasta 24)")
        dur = SEG_POR_ELEMENTO
        if seg.strip():
            try:
                dur = float(seg)
            except ValueError:
                raise ValueError(f"duración no válida en '{s}': usa clase:segundos, por ejemplo metal:2.5") from None
            if not 0 < dur <= 3600:
                raise ValueError(f"duración fuera de rango en '{s}': debe estar entre 0 y 3600 segundos")
        items.append((nombre, dur))
    if not items:
        raise ValueError("el guion está vacío")
    return items


def probs_simuladas(clase, conf, clases):
    """Reparte 1 - conf entre las demás clases; devuelve un dict con las claves de `clases`."""
    otras = [x for x in clases if x != clase]
    resto = [random.random() + 0.05 for _ in otras]
    s = sum(resto)
    probs = {clase: conf}
    for k, r in zip(otras, resto):
        probs[k] = round((1 - conf) * r / s, 4)
    return {k: probs[k] for k in clases}


def simulador(estado, hz=3.0, parar=None, clase_led=None, clases_led=None, guion=None,
              bucle=False, velocidad=1.0):
    """Genera inferencias. Con `guion` (lista de (clase, segundos)) fuerza la clase ganadora en ese
    orden; sin `bucle`, al terminar vuelve al modo aleatorio. `velocidad` > 1 acelera (para pruebas)."""
    leds = set(clases_led or []) | ({clase_led} if clase_led else set())
    if not leds:
        leds = {"tijera"}
    extras = []
    for c, _ in guion or []:
        if c not in BASE and c not in extras:
            extras.append(c)
    clases = list(BASE) + extras
    n = 0
    t0 = time.time()
    clase = "nada"
    cambia = 0.0
    umbral = 0.6
    idx = 0
    cambia_guion = 0.0
    estado.conectado = True
    while not (parar and parar.is_set()):
        ahora = time.time()
        if guion:
            if ahora >= cambia_guion:
                if idx >= len(guion):
                    if bucle:
                        idx = 0
                    else:
                        guion = None
                if guion:
                    clase, dur = guion[idx]
                    idx += 1
                    cambia_guion = ahora + dur / velocidad
            c = clase if guion else None
        if not guion:
            if ahora >= cambia:
                clase = random.choices(BASE, weights=(3, 3, 3, 1.2))[0]
                cambia = ahora + random.uniform(2.5, 6) / velocidad
            c = clase
            if random.random() < 0.04:
                c = "nada"
            conf = round(random.uniform(0.55, 0.98), 4)
        else:
            conf = round(random.uniform(0.80, 0.97), 4)
        d = {
            "v": 1, "fuente": "simulacion", "n": n, "t_ms": int((ahora - t0) * 1000),
            "clase": c, "confianza": conf, "probs": probs_simuladas(c, conf, clases),
            "lat_ms": {"dsp": random.randint(3, 6), "inf": random.randint(150, 220)},
            "led": c in leds and conf >= umbral, "umbral": umbral,
        }
        estado.publicar(validar(d))
        n += 1
        time.sleep(1 / hz * random.uniform(0.9, 1.1) / velocidad)


def lector_serie(estado, puerto, baudios):
    import serial
    ultimo_error = None
    while True:
        try:
            with serial.Serial(puerto, baudios, timeout=1) as s:
                estado.conectado = True
                while True:
                    raw = s.readline()
                    if not raw:
                        continue
                    d = validar(raw)
                    if d:
                        estado.publicar(d)
        except Exception as e:
            estado.conectado = False
            msg = f"serie {puerto}: {e}"
            if msg != ultimo_error:
                print(msg, file=sys.stderr, flush=True)
                ultimo_error = msg
            time.sleep(2)


@app.get("/")
def indice():
    return send_from_directory(AQUI, "index.html")


@app.post("/api/inferencia")
def api_inferencia():
    cuerpo = request.get_json(silent=True)
    if cuerpo is None:
        cuerpo = request.get_data(as_text=True)
    d = validar(cuerpo)
    if d is None:
        return jsonify(error="linea fuera del contrato"), 400
    if E.fuente == "ninguna":
        E.fuente = d["fuente"]
    E.conectado = True
    E.publicar(d)
    return jsonify(ok=True)


@app.get("/api/estado")
def api_estado():
    return jsonify(E.resumen())


@app.get("/api/stream")
def api_stream():
    q = queue.Queue(maxsize=100)
    with E.lock:
        E.clientes.append(q)

    def gen():
        try:
            yield "retry: 2000\n\n"
            while True:
                try:
                    m = q.get(timeout=15)
                    yield f"event: inferencia\ndata: {m}\n\n"
                except queue.Empty:
                    yield ": latido\n\n"
        finally:
            with E.lock:
                if q in E.clientes:
                    E.clientes.remove(q)

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    p = argparse.ArgumentParser(description="Dashboard TinyML piedra, papel o tijera")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--simular", action="store_true", help="genera inferencias simuladas (~3 Hz)")
    g.add_argument("--serial", metavar="PUERTO", nargs="?", const=os.environ.get("XIAO_PUERTO", ""),
                   help="lee la XIAO por puerto serie (por defecto XIAO_PUERTO del .env)")
    p.add_argument("--led-clase", default=None, help="clase que enciende el LED en la simulación (defecto tijera)")
    p.add_argument("--led-clases", default="", help="lista de clases que encienden el LED, ej. \"tijera,metal\" (se une con --led-clase)")
    p.add_argument("--guion", default="", help="fuerza la secuencia de clases del simulador: \"piedra,papel:2,metal\" (clase o clase:segundos, 1.6 s por defecto)")
    p.add_argument("--guion-bucle", action="store_true", help="repite el guion sin parar (sin esto, al terminar vuelve al modo aleatorio)")
    p.add_argument("--baudios", type=int, default=115200, help="velocidad del puerto serie")
    p.add_argument("--puerto-http", type=int, default=5000, help="puerto HTTP del dashboard")
    p.add_argument("--host", default="127.0.0.1", help="direccion donde escucha el servidor")
    a = p.parse_args()
    leds = []
    for c in ([a.led_clase] if a.led_clase else []) + [x.strip() for x in a.led_clases.split(",") if x.strip()]:
        if not ETIQUETA.fullmatch(c):
            p.error(f"clase de LED no válida: '{c}' (minúsculas ASCII, dígitos y _)")
        if c not in leds:
            leds.append(c)
    leds = leds or ["tijera"]
    guion = None
    if a.guion:
        if not a.simular:
            p.error("--guion solo funciona con --simular")
        try:
            guion = parsear_guion(a.guion)
        except ValueError as e:
            p.error(str(e))
    if a.simular:
        E.fuente = "simulacion"
        threading.Thread(target=simulador, args=(E,), kwargs={
            "clases_led": leds, "guion": guion, "bucle": a.guion_bucle}, daemon=True).start()
    elif a.serial is not None:
        if not a.serial:
            p.error("falta el puerto: usa --serial COM5 o define XIAO_PUERTO en .env")
        E.fuente = "xiao"
        E.puerto = a.serial
        threading.Thread(target=lector_serie, args=(E, a.serial, a.baudios), daemon=True).start()
    app.run(host=a.host, port=a.puerto_http, threaded=True, debug=False)


if __name__ == "__main__":
    main()
