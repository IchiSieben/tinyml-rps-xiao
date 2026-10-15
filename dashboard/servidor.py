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
    from .contrato import CLASES, validar
except ImportError:
    from contrato import CLASES, validar

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
        self.conteos = {c: 0 for c in CLASES}
        self.ultima = None

    def publicar(self, d):
        with self.lock:
            self.ultimas.append(d)
            self.conteos[d["clase"]] += 1
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


def simulador(estado, hz=3.0, parar=None, clase_led="tijera"):
    n = 0
    t0 = time.time()
    clase = "nada"
    cambia = 0.0
    umbral = 0.6
    estado.conectado = True
    while not (parar and parar.is_set()):
        ahora = time.time()
        if ahora >= cambia:
            clase = random.choices(CLASES, weights=(3, 3, 3, 1.2))[0]
            cambia = ahora + random.uniform(2.5, 6)
        c = clase
        if random.random() < 0.04:
            c = "nada"
        conf = round(random.uniform(0.55, 0.98), 4)
        resto = [random.random() + 0.05 for _ in range(3)]
        s = sum(resto)
        otras = [x for x in CLASES if x != c]
        probs = {c: conf}
        for k, r in zip(otras, resto):
            probs[k] = round((1 - conf) * r / s, 4)
        d = {
            "v": 1, "fuente": "simulacion", "n": n, "t_ms": int((ahora - t0) * 1000),
            "clase": c, "confianza": conf, "probs": {k: probs[k] for k in CLASES},
            "lat_ms": {"dsp": random.randint(3, 6), "inf": random.randint(150, 220)},
            "led": c == clase_led and conf >= umbral, "umbral": umbral,
        }
        estado.publicar(validar(d))
        n += 1
        time.sleep(1 / hz * random.uniform(0.9, 1.1))


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
    p.add_argument("--led-clase", default="tijera", help="clase que enciende el LED en la simulacion (defecto tijera)")
    p.add_argument("--baudios", type=int, default=115200, help="velocidad del puerto serie")
    p.add_argument("--puerto-http", type=int, default=5000, help="puerto HTTP del dashboard")
    p.add_argument("--host", default="127.0.0.1", help="direccion donde escucha el servidor")
    a = p.parse_args()
    if a.simular:
        E.fuente = "simulacion"
        threading.Thread(target=simulador, args=(E,), kwargs={"clase_led": a.led_clase}, daemon=True).start()
    elif a.serial is not None:
        if not a.serial:
            p.error("falta el puerto: usa --serial COM5 o define XIAO_PUERTO en .env")
        E.fuente = "xiao"
        threading.Thread(target=lector_serie, args=(E, a.serial, a.baudios), daemon=True).start()
    app.run(host=a.host, port=a.puerto_http, threaded=True, debug=False)


if __name__ == "__main__":
    main()
