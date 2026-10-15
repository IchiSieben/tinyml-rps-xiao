"""Cliente minimo de la Studio API de Edge Impulse compartido por los scripts del pipeline.

Docs: https://docs.edgeimpulse.com/reference (OpenAPI: https://studio.edgeimpulse.com/openapi.yml)
La clave sale solo de .env (EI_API_KEY) y nunca se imprime completa.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
STUDIO = "https://studio.edgeimpulse.com/v1/api"
INGESTION = "https://ingestion.edgeimpulse.com/api"


def enmascarar(clave):
    if not clave:
        return "<EI_API_KEY>"
    return f"{clave[:3]}****{clave[-4:]}" if len(clave) >= 12 else "****"


def cargar_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for p in (RAIZ / ".env", Path.cwd() / ".env"):
        if p.is_file():
            load_dotenv(p, override=False)


def agregar_args_comunes(ap):
    ap.add_argument("--dry-run", action="store_true",
                    help="Solo muestra las peticiones (metodo, URL, cuerpo); no envia nada y no necesita clave")
    return ap


class ClienteEI:
    def __init__(self, dry_run=False, proyecto=""):
        cargar_env()
        self.dry_run = dry_run
        self.clave = os.environ.get("EI_API_KEY", "").strip()
        self.proyecto = (proyecto or os.environ.get("EI_PROJECT_ID", "")).strip()
        self.registro = []
        if not dry_run:
            if not self.clave or self.clave.startswith("ei_xxxx"):
                raise SystemExit("Falta EI_API_KEY en .env (copia .env.example a .env y completa la clave). Usa --dry-run para ver el plan.")
            import requests
            self.sesion = requests.Session()
            self.sesion.headers["x-api-key"] = self.clave

    @property
    def pid(self):
        return self.proyecto or "<PROJECT_ID>"

    def url(self, ruta):
        return f"{STUDIO}/{ruta.lstrip('/')}"

    def cabeceras_visibles(self, extra=None):
        h = {"x-api-key": enmascarar(self.clave)}
        h.update(extra or {})
        return h

    def mostrar(self, metodo, url, cuerpo=None, extra_cab=None, nota=""):
        print(f"{metodo} {url}")
        print(f"  cabeceras: {json.dumps(self.cabeceras_visibles(extra_cab))}")
        if cuerpo is not None:
            print("  cuerpo: " + json.dumps(cuerpo, ensure_ascii=False))
        if nota:
            print(f"  nota: {nota}")
        self.registro.append((metodo, url, cuerpo))

    def peticion(self, metodo, url, json_cuerpo=None, params=None, simulado=None, nota="", **kw):
        """Devuelve el JSON de respuesta. En --dry-run imprime y devuelve `simulado`."""
        if self.dry_run:
            u = url
            if params:
                u += "?" + "&".join(f"{k}={v}" for k, v in params.items())
            self.mostrar(metodo, u, json_cuerpo, nota=nota)
            return simulado if simulado is not None else {"success": True}
        import requests
        ultimo = None
        for intento in range(5):
            try:
                r = self.sesion.request(metodo, url, json=json_cuerpo, params=params, timeout=60, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    ultimo = f"HTTP {r.status_code}"
                else:
                    break
            except requests.RequestException as e:
                ultimo = type(e).__name__
            time.sleep(2 ** intento)
        else:
            raise SystemExit(f"{metodo} {url} falló tras 5 intentos ({ultimo})")
        if r.status_code >= 400:
            raise SystemExit(f"{metodo} {url} -> HTTP {r.status_code}: {r.text[:300]}")
        if "json" in r.headers.get("content-type", ""):
            d = r.json()
            if isinstance(d, dict) and d.get("success") is False:
                raise SystemExit(f"{metodo} {url} -> error de la API: {d.get('error')}")
            return d
        return r

    def descargar(self, url, destino, params=None, nota=""):
        destino = Path(destino)
        if self.dry_run:
            u = url + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")
            self.mostrar("GET", u, nota=f"guarda en {destino}" + (f". {nota}" if nota else ""))
            return destino
        r = self.peticion("GET", url, params=params, stream=True)
        if not hasattr(r, "iter_content"):
            raise SystemExit(f"Respuesta inesperada al descargar {url}: {r}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as fh:
            for trozo in r.iter_content(65536):
                fh.write(trozo)
        return destino

    def esperar_trabajo(self, id_trabajo, etiqueta, intervalo=5, limite_s=3600):
        if self.dry_run:
            self.mostrar("GET", self.url(f"{self.pid}/jobs/<ID_TRABAJO>/status"),
                         nota=f"se repite cada {intervalo} s hasta que '{etiqueta}' termine")
            return {"finishedSuccessful": True}
        t0 = time.time()
        while time.time() - t0 < limite_s:
            d = self.peticion("GET", self.url(f"{self.pid}/jobs/{id_trabajo}/status"))
            job = d["job"]
            if job.get("finished"):
                if not job.get("finishedSuccessful"):
                    raise SystemExit(f"El trabajo '{etiqueta}' (id {id_trabajo}) falló. Revisa los logs en Studio.")
                print(f"  {etiqueta}: terminado en {int(time.time() - t0)} s")
                return job
            print(f"  {etiqueta}: en curso ({int(time.time() - t0)} s)", flush=True)
            time.sleep(intervalo)
        raise SystemExit(f"El trabajo '{etiqueta}' supero {limite_s} s")

    def resolver_proyecto(self):
        """Si EI_PROJECT_ID esta vacio, usa el proyecto accesible con la clave."""
        if self.proyecto:
            return self.proyecto
        # https://docs.edgeimpulse.com/reference/listprojects  (GET /v1/api/projects)
        d = self.peticion("GET", self.url("projects"),
                          simulado={"success": True, "projects": [{"id": "<PROJECT_ID>", "name": "<proyecto>"}]},
                          nota="se elige el proyecto accesible con la clave")
        proyectos = d.get("projects", [])
        if not proyectos:
            raise SystemExit("La clave no ve ningun proyecto")
        if len(proyectos) > 1 and not self.dry_run:
            print("Aviso: la clave ve varios proyectos; se usa el primero. Fija EI_PROJECT_ID en .env para elegir.")
        self.proyecto = str(proyectos[0]["id"])
        print(f"Proyecto: {proyectos[0].get('name')} (id {self.proyecto})")
        return self.proyecto


def salida_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
