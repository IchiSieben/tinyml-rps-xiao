"""Capturas y verificación de la interfaz con Playwright (1366x768).

Uso:
    python tools/capturas.py                  # escribe PNG y demo.gif en resultados/
    python tools/capturas.py --sin-gif        # solo los PNG
    python tools/capturas.py --verificar      # sin tocar resultados/: solo cuenta errores de consola

Arranca dashboard/servidor.py --simular con un guion como subproceso (se mata solo ese PID) y
recorre cinco estados: inicio, jugando, arcade (ROCK ON), FULL AURA y fin de clase. Recoge todos
los mensajes de consola de tipo error y los errores de página. Repite el recorrido con
--autoplay-policy=user-gesture-required (sonidos antes de cualquier clic) y con AudioContext
borrado. Sale con código 1 si hay algún error.
"""
import argparse
import io
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTADOS = ["inicio", "jugando", "arcade", "full_aura", "fin_de_clase"]
ARCHIVOS = {"inicio": "ui_inicio.png", "jugando": "ui_jugando.png", "arcade": "ui_arcade.png",
            "full_aura": "ui_full_aura.png", "fin_de_clase": "ui_fin_de_clase.png"}
GUION = "piedra:16,metal:4,nada:2,papel:2,tijera:2,pulgar:2,lagarto:2"
SIN_AUDIO = ("delete window.AudioContext; delete window.webkitAudioContext;"
             "window.AudioContext=undefined; window.webkitAudioContext=undefined;")
SONIDOS = ["tick", "win", "lose", "draw", "riff", "aprobado"]


def puerto_libre():
    for p in range(5140, 5160):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError("sin puertos libres en 5140-5159")


class Servidor:
    """Servidor del dashboard en subproceso; al salir se detiene solo ese PID."""

    def __enter__(self):
        self.puerto = puerto_libre()
        cmd = [sys.executable, str(RAIZ / "dashboard" / "servidor.py"), "--simular", "--guion", GUION,
               "--guion-bucle", "--puerto-http", str(self.puerto)]
        self.proc = subprocess.Popen(cmd, cwd=str(RAIZ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.puerto}/api/estado", timeout=1).read()
                return self
            except Exception:
                time.sleep(0.5)
        self.__exit__()
        raise RuntimeError("el servidor no arrancó")

    def __exit__(self, *a):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        return False


def recorrido(pw, url, args_nav, init_js, destino, fotogramas):
    """Un recorrido completo. Devuelve {estado: [errores]}. Escribe PNG si destino no es None."""
    print("pasada", args_nav, bool(init_js), flush=True)
    errores = {e: [] for e in ESTADOS}
    estado = {"actual": "inicio"}
    nav = pw.chromium.launch(args=args_nav)
    ctx = nav.new_context(viewport={"width": 1366, "height": 768})
    if init_js:
        ctx.add_init_script(init_js)
    pag = ctx.new_page()
    pag.on("console", lambda m: errores[estado["actual"]].append("console: " + m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores[estado["actual"]].append("pageerror: " + str(e)))
    pag.on("request", lambda r: errores[estado["actual"]].append("peticion externa: " + r.url)
           if not r.url.startswith(("http://127.0.0.1", "data:", "blob:")) else None)

    def foto(nombre=None, gif=False):
        png = pag.screenshot()
        if destino is not None and nombre:
            (destino / ARCHIVOS[nombre]).write_bytes(png)
        if gif and fotogramas is not None:
            fotogramas.append(png)

    def esperar_texto(txt, ms=25000):
        pag.wait_for_function("t => document.body.innerText.includes(t)", arg=txt, timeout=ms, polling=100)

    try:
        pag.goto(url + "/?semilla=7")
        # Sonidos antes de cualquier clic: no deben lanzar nada
        pag.evaluate("(s) => s.forEach(n => window.RPS.sonido(n))", SONIDOS)
        pag.wait_for_function("window.RPS && window.RPS.conectado === true", timeout=10000)
        pag.wait_for_timeout(1200)
        estado["actual"] = "inicio"
        foto("inicio", gif=True)

        estado["actual"] = "jugando"
        pag.click("#btn-jugar")
        pag.wait_for_timeout(500)
        foto(gif=True)
        pag.wait_for_timeout(900)
        foto(gif=True)
        esperar_texto("Tú vs Placa")
        pag.wait_for_timeout(500)
        foto("jugando", gif=True)

        estado["actual"] = "arcade"
        esperar_texto("ROCK ON")
        pag.wait_for_timeout(700)
        foto("arcade", gif=True)

        estado["actual"] = "full_aura"
        pag.wait_for_function("document.body.innerText.includes('ROCK ON') === false", timeout=8000)
        pag.wait_for_timeout(600)
        pag.evaluate("window.RPS.debug.fijarAura(95)")
        pag.evaluate("setTimeout(() => window.RPS.debug.jugar('piedra','tijera',0.95), 0)")
        esperar_texto("FULL AURA")
        pag.wait_for_timeout(700)
        foto("full_aura", gif=True)
        pag.wait_for_timeout(700)
        foto(gif=True)
        pag.wait_for_function("window.RPS.debug.estado().aura === 50", timeout=10000)
        pag.wait_for_timeout(800)

        estado["actual"] = "fin_de_clase"
        pag.evaluate("document.activeElement && document.activeElement.blur()")
        pag.keyboard.press("f")
        pag.wait_for_selector("#fin:not([hidden]) canvas", timeout=5000)
        pag.wait_for_timeout(500)
        foto("fin_de_clase", gif=True)
        pag.keyboard.press("Escape")
        pag.wait_for_timeout(300)
    finally:
        nav.close()
    return errores


def crear_gif(png_lista, ruta):
    from PIL import Image
    imgs = []
    for b in png_lista:
        im = Image.open(io.BytesIO(b)).convert("RGB")
        im = im.resize((960, round(768 * 960 / 1366)), Image.LANCZOS)
        imgs.append(im.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    imgs[0].save(ruta, save_all=True, append_images=imgs[1:], duration=1000, loop=0, optimize=True)
    return ruta.stat().st_size


def principal(verificar=False, sin_gif=False, salida=None):
    from playwright.sync_api import sync_playwright
    destino = None if verificar else (Path(salida) if salida else RAIZ / "resultados")
    fotogramas = [] if (not verificar and not sin_gif) else None
    pasadas = [("normal", [], None),
               ("autoplay-bloqueado", ["--autoplay-policy=user-gesture-required"], None),
               ("sin-AudioContext", [], SIN_AUDIO)]
    total = {}
    with sync_playwright() as pw, Servidor() as srv:
        url = f"http://127.0.0.1:{srv.puerto}"
        for i, (nombre, args_nav, init) in enumerate(pasadas):
            total[nombre] = recorrido(pw, url, args_nav, init, destino if i == 0 else None,
                                      fotogramas if i == 0 else None)
            time.sleep(0.5)
    malos = 0
    for nombre, err in total.items():
        for est in ESTADOS:
            n = len(err[est])
            malos += n
            print(f"[{nombre}] {est}: {n} errores de consola")
            for m in err[est]:
                print("    ", m)
    if fotogramas:
        tam = crear_gif(fotogramas, destino / "demo.gif")
        print(f"demo.gif: {tam / 1024:.0f} KB, {len(fotogramas)} fotogramas")
    return 1 if malos else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-gif", action="store_true", help="no genera demo.gif")
    ap.add_argument("--verificar", action="store_true", help="no escribe nada en resultados/, solo verifica errores")
    ap.add_argument("--salida", default=None, help="directorio de salida (por defecto resultados/)")
    a = ap.parse_args()
    sys.exit(principal(a.verificar, a.sin_gif, a.salida))
