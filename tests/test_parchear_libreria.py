import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / "tests" / "fixtures" / "ei_lib" / "rps_inferencing"
SCRIPT = RAIZ / "firmware" / "parchear_libreria.py"
INO = "rps_inferencing/examples/esp32/esp32_camera/esp32_camera.ino"
CARPETA_INO = "rps_inferencing/examples/esp32/esp32_camera/"


def armar_zip(destino):
    z_ruta = destino / "rps-arduino.zip"
    with zipfile.ZipFile(z_ruta, "w") as z:
        for p in FIXTURE.rglob("*"):
            if p.is_file():
                z.write(p, "rps_inferencing/" + p.relative_to(FIXTURE).as_posix())
    return z_ruta


def correr(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True)


def leer(zip_ruta, nombre):
    with zipfile.ZipFile(zip_ruta) as z:
        return z.read(nombre).decode("utf-8")


def test_pines_xiao(tmp_path):
    z = armar_zip(tmp_path)
    r = correr(z)
    assert r.returncode == 0, r.stderr
    salida = tmp_path / "rps-arduino_xiao.zip"
    ino = leer(salida, INO)
    assert '#include "xiao_pins.h"' in ino
    assert "#define CAMERA_MODEL_ESP_EYE" not in ino
    assert "Camera model not selected" not in ino
    assert "emitir_json(" in ino and 'ei_printf("Predictions' not in ino
    assert "actualizar_led" not in ino
    nombres = zipfile.ZipFile(salida).namelist()
    assert CARPETA_INO + "xiao_pins.h" in nombres
    assert CARPETA_INO + "salida_json.h" in nombres
    assert "XCLK_GPIO_NUM     10" in leer(salida, CARPETA_INO + "xiao_pins.h")


def test_arena(tmp_path):
    z = armar_zip(tmp_path)
    assert correr(z, "--arena", 384605).returncode == 0
    s = tmp_path / "rps-arduino_xiao.zip"
    h = leer(s, "rps_inferencing/src/tflite-model/tflite_learn_825137_18.h")
    assert "ARENA_SIZE     384605" in h and "_arena_size = 384605;" in h
    assert "294912" not in h
    assert "LARGEST_ARENA_SIZE     384605" in leer(s, "rps_inferencing/src/model-parameters/model_metadata.h")


def test_led_solo_con_opcion(tmp_path):
    z = armar_zip(tmp_path)
    r = correr(z, "--led-clase", "piedra", "--umbral", "0.7", "--salida", tmp_path / "led.zip")
    assert r.returncode == 0, r.stderr
    ino = leer(tmp_path / "led.zip", INO)
    assert 'actualizar_led(clase_ganadora, conf_ganadora, "piedra", 0.70f)' in ino


def test_idempotente(tmp_path):
    z = armar_zip(tmp_path)
    assert correr(z, "--salida", tmp_path / "a.zip").returncode == 0
    assert correr(tmp_path / "a.zip", "--salida", tmp_path / "b.zip").returncode == 0
    assert leer(tmp_path / "a.zip", INO) == leer(tmp_path / "b.zip", INO)


def test_zip_invalido(tmp_path):
    malo = tmp_path / "malo.zip"
    malo.write_text("no es un zip")
    r = correr(malo)
    assert r.returncode != 0 and "Error" in r.stderr
    vacio = tmp_path / "vacio.zip"
    with zipfile.ZipFile(vacio, "w") as z:
        z.writestr("x/readme.txt", "hola")
    assert correr(vacio).returncode != 0
