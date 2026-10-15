import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
import servidor  # noqa: E402
from contrato import validar  # noqa: E402

EJEMPLO = '{"v":1,"fuente":"xiao","n":42,"t_ms":183220,"clase":"tijera","confianza":0.9141,"probs":{"piedra":0.0234,"papel":0.0469,"tijera":0.9141,"nada":0.0156},"lat_ms":{"dsp":4,"inf":187},"led":true,"umbral":0.6}'


def test_acepta_ejemplo():
    d = validar(EJEMPLO)
    assert d["clase"] == "tijera" and d["lat_ms"]["inf"] == 187


def test_rechaza_malas():
    base = json.loads(EJEMPLO)
    falta = json.loads(EJEMPLO)
    del falta["probs"]["tijera"]  # la clase ganadora ya no esta en probs; borrar 'nada' ahora es valido
    v2 = dict(base, v=2)
    fuera = dict(base, confianza=1.5)
    clase_mala = dict(base, clase="lagarto")
    for malo in (falta, v2, fuera, clase_mala, "I (123) boot: arranque", "{no es json", "", None, 5):
        assert validar(malo) is None


@pytest.fixture
def cliente():
    servidor.E.__init__()
    return servidor.app.test_client()


def test_post_valido_y_estado(cliente):
    r = cliente.post("/api/inferencia", data=EJEMPLO, content_type="text/plain")
    assert r.status_code == 200
    r = cliente.post("/api/inferencia", json=json.loads(EJEMPLO))
    assert r.status_code == 200
    est = cliente.get("/api/estado").get_json()
    assert est["conteos"]["tijera"] == 2 and est["ultima"]["n"] == 42


def test_post_invalido(cliente):
    assert cliente.post("/api/inferencia", data="hola").status_code == 400
    assert cliente.post("/api/inferencia", json={"v": 2}).status_code == 400


def test_indice_sin_cdn(cliente):
    r = cliente.get("/")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "<html" in html
    assert not re.search(r'<(script|link)[^>]+(src|href)=["\']https?://', html)
    assert chr(0x2014) not in html


def linea(clase="tijera", probs=None, **extra):
    d = json.loads(EJEMPLO)
    d["clase"] = clase
    d["probs"] = probs if probs is not None else d["probs"]
    d.update(extra)
    return d


def test_acepta_clases_nuevas():
    probs = {"piedra": 0.05, "papel": 0.05, "tijera": 0.05, "nada": 0.05, "metal": 0.7, "pulgar": 0.1}
    d = validar(linea("metal", probs, confianza=0.7))
    assert d["clase"] == "metal" and list(d["probs"]) == ["piedra", "papel", "tijera", "nada", "metal", "pulgar"]


def test_orden_normalizado():
    from contrato import orden_clases
    assert orden_clases(["pulgar", "nada", "metal", "piedra"]) == ["piedra", "nada", "pulgar", "metal"]
    probs = {"nada": 0.1, "zeta": 0.2, "papel": 0.1, "piedra": 0.6}
    assert list(validar(linea("piedra", probs, confianza=0.6))["probs"]) == ["piedra", "papel", "nada", "zeta"]


def test_acepta_modelo_sin_nada():
    probs = {"piedra": 0.1, "papel": 0.1, "tijera": 0.1, "metal": 0.7}
    assert validar(linea("metal", probs, confianza=0.7)) is not None


def test_rechaza_clase_fuera_de_probs():
    assert validar(linea("lagarto")) is None
    assert validar(linea("nada", {"piedra": 0.5, "papel": 0.5})) is None


@pytest.mark.parametrize("etiqueta", ["Metal", "met al", "metal-2", "métal", "", "x" * 25])
def test_rechaza_etiqueta_mala(etiqueta):
    probs = {"piedra": 0.2, etiqueta: 0.8}
    assert validar(linea(etiqueta, probs, confianza=0.8)) is None


def test_rechaza_pocas_o_muchas_clases():
    assert validar(linea("tijera", {"tijera": 0.9}, confianza=0.9)) is None
    assert validar(linea("c0", {f"c{i}": 0.05 for i in range(17)}, confianza=0.05)) is None
    assert validar(linea("c0", {f"c{i}": 0.05 for i in range(16)}, confianza=0.05)) is not None


def test_parsear_guion():
    assert servidor.parsear_guion("piedra, papel:2,metal") == [("piedra", 1.6), ("papel", 2.0), ("metal", 1.6)]
    for malo in ("", "Piedra", "metal:abc", "metal:0", "me tal", "a:-1"):
        with pytest.raises(ValueError):
            servidor.parsear_guion(malo)


class EstadoGrabado(servidor.Estado):
    """Estado que guarda todo lo publicado (ultimas solo conserva 50)."""
    def __init__(self):
        super().__init__()
        self.todo = []

    def publicar(self, d):
        self.todo.append(d)
        super().publicar(d)


def correr_guion(guion, bucle=False, espera=0.6, **kw):
    est = EstadoGrabado()
    parar = threading.Event()
    h = threading.Thread(target=servidor.simulador, args=(est,), daemon=True,
                         kwargs=dict(hz=3.0, parar=parar, guion=guion, bucle=bucle, velocidad=40.0, **kw))
    h.start()
    time.sleep(espera)
    parar.set()
    h.join(2)
    return est


def test_guion_en_orden_y_clases_nuevas():
    guion = servidor.parsear_guion("piedra,metal,lagarto,pulgar")
    est = correr_guion(guion, espera=0.5)
    vistas = []
    for d in est.todo:
        if not vistas or vistas[-1] != d["clase"]:
            vistas.append(d["clase"])
        if len(vistas) <= 4:
            assert 0.80 <= d["confianza"] <= 0.97
        assert {"metal", "lagarto", "pulgar", "piedra", "nada"} <= set(d["probs"])
    assert vistas[:4] == ["piedra", "metal", "lagarto", "pulgar"]
    assert est.resumen()["clases"][:4] == ["piedra", "papel", "tijera", "nada"]


def test_guion_bucle_repite_y_led_lista():
    est = correr_guion(servidor.parsear_guion("tijera,metal"), bucle=True, espera=0.8, clases_led=["tijera", "metal"])
    cambios = [d["clase"] for d in est.todo]
    assert cambios.count("tijera") and cambios.count("metal")
    secuencia = [c for i, c in enumerate(cambios) if i == 0 or cambios[i - 1] != c]
    assert len(secuencia) >= 3 and secuencia[:3] == ["tijera", "metal", "tijera"]
    assert all(d["led"] for d in est.todo)


def test_estado_trae_puerto_y_clases(cliente):
    servidor.E.puerto = "COM5"
    probs = {"piedra": 0.05, "papel": 0.05, "tijera": 0.1, "nada": 0.0, "metal": 0.8}
    assert cliente.post("/api/inferencia", json=linea("metal", probs, confianza=0.8)).status_code == 200
    est = cliente.get("/api/estado").get_json()
    assert est["puerto"] == "COM5" and est["clases"] == ["piedra", "papel", "tijera", "nada", "metal"]
    assert est["conteos"]["metal"] == 1
