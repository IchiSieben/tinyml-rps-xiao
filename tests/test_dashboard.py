import json
import re
import sys
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
    del falta["probs"]["nada"]
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
