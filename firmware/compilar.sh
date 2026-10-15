#!/usr/bin/env bash
# Compila el firmware para la XIAO ESP32S3 Sense con arduino-cli.
# Uso: ./compilar.sh <libreria_parcheada_xiao.zip>   |   ./compilar.sh --prueba-entorno
# Variables: CORE_ESP32 (por defecto 3.3.12), PSRAM (por defecto opi), ARDUINO_CLI (ruta).
set -euo pipefail

CORE_ESP32="${CORE_ESP32:-3.3.12}"
PSRAM="${PSRAM:-opi}"
FQBN="esp32:esp32:XIAO_ESP32S3:PSRAM=${PSRAM}"
URL_INDICE="https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$RAIZ/build"

CLI="${ARDUINO_CLI:-}"
[ -z "$CLI" ] && CLI="$(command -v arduino-cli || command -v arduino-cli.exe || true)"
[ -z "$CLI" ] && [ -x "$HOME/bin/arduino-cli.exe" ] && CLI="$HOME/bin/arduino-cli.exe"
[ -z "$CLI" ] && [ -x "$HOME/bin/arduino-cli" ] && CLI="$HOME/bin/arduino-cli"
if [ -z "$CLI" ]; then
    echo "No se encontro arduino-cli. Instalalo con: curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh" >&2
    echo "(en Windows: winget install ArduinoSA.CLI) o define ARDUINO_CLI con la ruta." >&2
    exit 1
fi

case "$CORE_ESP32" in
    *alpha*|*rc*|*beta*) echo "Version de core no estable ($CORE_ESP32): usa una 3.3.x estable." >&2; exit 1 ;;
esac

PRUEBA=0; ZIP=""
for a in "$@"; do
    case "$a" in
        --prueba-entorno) PRUEBA=1 ;;
        -h|--help) sed -n 2,5p "$0"; exit 0 ;;
        *) ZIP="$a" ;;
    esac
done
if [ "$PRUEBA" = 0 ] && [ -z "$ZIP" ]; then
    echo "Falta el ZIP parcheado. Uso: ./compilar.sh <libreria_xiao.zip> | --prueba-entorno" >&2
    exit 1
fi

"$CLI" config init --overwrite >/dev/null 2>&1 || true
"$CLI" config add board_manager.additional_urls "$URL_INDICE" >/dev/null 2>&1 || true
"$CLI" core update-index
if ! "$CLI" core list | grep -q "esp32:esp32 *$CORE_ESP32"; then
    "$CLI" core install "esp32:esp32@$CORE_ESP32"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$BUILD"

if [ "$PRUEBA" = 1 ]; then
    DATOS="$("$CLI" config get directories.data)"
    ORIGEN="$DATOS/packages/esp32/hardware/esp32/$CORE_ESP32/libraries/ESP32/examples/Camera/CameraWebServer"
    [ -d "$ORIGEN" ] || { echo "No existe $ORIGEN" >&2; exit 1; }
    mkdir -p "$TMP/CameraWebServer"
    cp "$ORIGEN"/* "$TMP/CameraWebServer/"
    sed -i -E 's|^[[:space:]]*#define[[:space:]]+CAMERA_MODEL_|//#define CAMERA_MODEL_|; s|^//[[:space:]]*#define[[:space:]]+CAMERA_MODEL_XIAO_ESP32S3|#define CAMERA_MODEL_XIAO_ESP32S3|' "$TMP/CameraWebServer/CameraWebServer.ino"
    "$CLI" compile --fqbn "$FQBN" --output-dir "$BUILD/prueba_entorno" "$TMP/CameraWebServer"
    exit 0
fi

mkdir -p "$TMP/lib"
python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$ZIP" "$TMP/lib" 2>/dev/null \
    || python -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$ZIP" "$TMP/lib"
PROPS="$(find "$TMP/lib" -name library.properties | head -1)"
[ -n "$PROPS" ] || { echo "El ZIP no contiene library.properties." >&2; exit 1; }
LIB="$(dirname "$PROPS")"
SKETCH="$LIB/examples/esp32/esp32_camera"
[ -f "$SKETCH/esp32_camera.ino" ] || { echo "Falta esp32_camera.ino en el ZIP." >&2; exit 1; }
grep -q xiao_pins.h "$SKETCH/esp32_camera.ino" || { echo "El ZIP no esta parcheado: corre parchear_libreria.py primero." >&2; exit 1; }
"$CLI" compile --fqbn "$FQBN" --library "$LIB" --output-dir "$BUILD" "$SKETCH"
echo "Binarios en $BUILD"
