import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
PIPE = RAIZ / "pipeline"
sys.path.insert(0, str(PIPE))

CLAVE = "ei_0123456789abcdef0123456789abcdef"


def correr(script, *args, env_extra=None, cwd=None):
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("EI_API_KEY", "EI_PROJECT_ID")}
    env["TF_CPP_MIN_LOG_LEVEL"] = "3"
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(PIPE / script), *args], capture_output=True, text=True,
                          env=env, cwd=cwd or RAIZ, timeout=120)


def test_cuantizacion_ida_y_vuelta():
    tf = pytest.importorskip("tensorflow")
    from tflite_util import cargar_interprete, cuantizar, dequantizar, detectar_rango, info_entrada, info_salida

    rng = np.random.default_rng(0)
    modelo = tf.keras.Sequential([
        tf.keras.layers.Input((8, 8, 3)), tf.keras.layers.Conv2D(2, 3, activation="relu"),
        tf.keras.layers.Flatten(), tf.keras.layers.Dense(3, activation="softmax")])

    def datos():
        for _ in range(20):
            yield [rng.random((1, 8, 8, 3), dtype=np.float32)]

    conv = tf.lite.TFLiteConverter.from_keras_model(modelo)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = datos
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    ruta = RAIZ / "build" / "test_sintetico.tflite"
    ruta.parent.mkdir(exist_ok=True)
    ruta.write_bytes(conv.convert())

    it = cargar_interprete(ruta)
    ent, sal = info_entrada(it), info_salida(it)
    assert ent["dtype"] == np.int8 and ent["scale"] > 0
    assert detectar_rango(ent) == "01"
    x255 = rng.integers(0, 256, (8, 8, 3)).astype(np.float32)
    q = cuantizar(x255, ent, "01")
    assert q.dtype == np.int8
    recon = (q.astype(np.float32) - ent["zero_point"]) * ent["scale"]
    assert np.abs(recon - x255 / 255.0).max() <= ent["scale"] / 2 + 1e-6
    it.set_tensor(ent["indice"], q[None])
    it.invoke()
    p = dequantizar(it.get_tensor(sal["indice"])[0], sal)
    assert p.shape == (3,) and abs(p.sum() - 1) < 0.1


def crear_imagenes(carpeta, n_por_clase, clases=("piedra", "papel")):
    rng = np.random.default_rng(1)
    for c in clases:
        d = carpeta / c
        d.mkdir(parents=True)
        for i in range(n_por_clase):
            Image.fromarray(rng.integers(0, 256, (40, 60, 3), dtype=np.uint8)).save(d / f"{i}.jpg")


def test_preparar_dataset_reparto(tmp_path):
    crudas = tmp_path / "crudas"
    crear_imagenes(crudas, 10)
    (crudas / "piedra" / "mala.jpg").write_bytes(b"no es imagen")
    salida = tmp_path / "listo"
    r = correr("preparar_dataset.py", "--entrada", str(crudas), "--salida", str(salida))
    assert r.returncode == 0, r.stderr
    for c in ("piedra", "papel"):
        assert len(list((salida / "training" / c).glob("*.jpg"))) == 8
        assert len(list((salida / "testing" / c).glob("*.jpg"))) == 2
    assert Image.open(next((salida / "training" / "piedra").glob("*.jpg"))).size == (96, 96)
    filas = list(csv.DictReader(open(salida / "manifiesto.csv", encoding="utf-8")))
    assert len(filas) == 20
    assert "minimo recomendado 30" in r.stdout and "invalida" in r.stdout


def test_preparar_dataset_dry_run_no_escribe(tmp_path):
    crudas = tmp_path / "crudas"
    crear_imagenes(crudas, 5)
    salida = tmp_path / "listo"
    r = correr("preparar_dataset.py", "--entrada", str(crudas), "--salida", str(salida), "--dry-run")
    assert r.returncode == 0 and not salida.exists()


def test_preparar_dataset_deduplica(tmp_path):
    crudas = tmp_path / "crudas" / "papel"
    crudas.mkdir(parents=True)
    img = Image.fromarray(np.random.default_rng(3).integers(0, 256, (30, 30, 3), dtype=np.uint8))
    for i in range(4):
        img.save(crudas / f"{i}.png")
    r = correr("preparar_dataset.py", "--entrada", str(tmp_path / "crudas"), "--dry-run")
    assert "duplicadas descartadas: 3" in r.stdout


@pytest.mark.parametrize("script", ["subir_edge_impulse.py", "entrenar.py", "descargar_libreria.py"])
def test_dry_run_sin_env_y_clave_enmascarada(script, tmp_path):
    r = correr(script, "--dry-run", cwd=tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "x-api-key" in r.stdout or "subir" in script
    r = correr(script, "--dry-run", env_extra={"EI_API_KEY": CLAVE, "EI_PROJECT_ID": "123"}, cwd=tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    assert CLAVE not in r.stdout + r.stderr
    if script != "subir_edge_impulse.py":
        assert "ei_****cdef" in r.stdout


def test_subir_dry_run_muestra_cabeceras(tmp_path):
    listo = tmp_path / "listo"
    crear_imagenes(listo / "training", 25)
    crear_imagenes(listo / "testing", 3)
    r = correr("subir_edge_impulse.py", "--dry-run", "--datos", str(listo), env_extra={"EI_API_KEY": CLAVE})
    assert r.returncode == 0
    assert "ingestion.edgeimpulse.com/api/training/files" in r.stdout
    assert "x-label" in r.stdout and "ei_****cdef" in r.stdout and CLAVE not in r.stdout
    assert "Total: 56 archivos" in r.stdout


def test_sin_clave_falla_con_mensaje(tmp_path):
    r = correr("entrenar.py", cwd=tmp_path)
    assert r.returncode != 0 and "EI_API_KEY" in (r.stderr + r.stdout)


def test_etiquetas_desde_metadata_h(tmp_path):
    from inferencia_local import leer_etiquetas
    (tmp_path / "model_metadata.h").write_text(
        'const char* ei_classifier_inferencing_categories[] = { "nada", "papel", "piedra", "tijera" };')
    assert leer_etiquetas("", tmp_path / "m.tflite") == ["nada", "papel", "piedra", "tijera"]
    assert leer_etiquetas("a,b", tmp_path / "m.tflite") == ["a", "b"]


def test_linea_contrato_orden_fijo():
    from inferencia_local import linea_contrato
    reg = linea_contrato("webcam", 0, 5, ["nada", "papel", "piedra", "tijera"], [0.1, 0.2, 0.6, 0.1], 1, 2, 0.6)
    assert list(reg["probs"]) == ["piedra", "papel", "tijera", "nada"]
    assert reg["clase"] == "piedra" and reg["v"] == 1
    # LED: misma regla que el firmware (clase_led y umbral)
    assert reg["led"] is False
    assert linea_contrato("webcam", 0, 5, ["nada", "papel", "piedra", "tijera"], [0.1, 0.2, 0.6, 0.1], 1, 2, 0.6,
                          clase_led="piedra")["led"] is True


SEIS = ("piedra", "papel", "tijera", "nada", "metal", "pulgar")


def test_preparar_dataset_seis_clases_con_zips(tmp_path):
    import zipfile
    crudas = tmp_path / "crudas"
    crear_imagenes(crudas, 10, SEIS)
    zips = []
    for c in ("metal", "pulgar"):  # las clases nuevas entran solo como ZIP, sin tocar codigo
        zp = tmp_path / f"{c}.zip"
        with zipfile.ZipFile(zp, "w") as z:
            for f in sorted((crudas / c).glob("*.jpg")):
                z.write(f, f"{c}/{f.name}")
        zips.append(str(zp))
        for f in (crudas / c).glob("*.jpg"):
            f.unlink()
        (crudas / c).rmdir()
    salida = tmp_path / "listo"
    r = correr("preparar_dataset.py", "--entrada", str(crudas), "--zips", *zips, "--salida", str(salida))
    assert r.returncode == 0, r.stderr
    for c in SEIS:
        assert len(list((salida / "training" / c).glob("*.jpg"))) == 8, c
        assert len(list((salida / "testing" / c).glob("*.jpg"))) == 2, c
    assert "Aviso: el nombre de clase" not in r.stdout


def test_preparar_dataset_avisa_nombre_fuera_de_contrato(tmp_path):
    crudas = tmp_path / "crudas"
    crear_imagenes(crudas, 6, ("piedra", "Mano-X"))
    r = correr("preparar_dataset.py", "--entrada", str(crudas), "--dry-run")
    assert r.returncode == 0 and "'mano-x' no cumple el contrato" in r.stdout


def test_linea_contrato_seis_etiquetas():
    from inferencia_local import linea_contrato
    sys.path.insert(0, str(RAIZ / "dashboard"))
    from contrato import validar
    etq = ["metal", "nada", "papel", "piedra", "pulgar", "tijera"]  # orden alfabetico de Edge Impulse
    p = [0.7, 0.02, 0.03, 0.05, 0.1, 0.1]
    reg = linea_contrato("webcam", 1, 10, etq, p, 3, 4, 0.6, clases_led=["tijera", "metal"])
    assert list(reg["probs"]) == ["piedra", "papel", "tijera", "nada", "metal", "pulgar"]
    assert reg["clase"] == "metal" and reg["led"] is True
    assert validar(reg)["clase"] == "metal"
    sin_nada = linea_contrato("webcam", 1, 10, ["metal", "papel"], [0.8, 0.2], 3, 4, 0.6, clase_led="tijera")
    assert list(sin_nada["probs"]) == ["papel", "metal"] and sin_nada["led"] is False and validar(sin_nada)


def test_subir_dry_run_seis_clases(tmp_path):
    listo = tmp_path / "listo"
    crear_imagenes(listo / "training", 25, SEIS)
    crear_imagenes(listo / "testing", 3, SEIS)
    r = correr("subir_edge_impulse.py", "--dry-run", "--datos", str(listo), env_extra={"EI_API_KEY": CLAVE})
    assert r.returncode == 0, r.stderr
    assert "Total: 168 archivos" in r.stdout
    for c in SEIS:
        assert any(l.split()[:2] == ["training", c] and l.split()[2] == "25" for l in r.stdout.splitlines()), c
