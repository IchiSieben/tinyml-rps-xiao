#!/usr/bin/env bash
# Sube build/ a la XIAO ESP32S3 Sense. Uso: ./flashear.sh [PUERTO] [--monitor]
# El puerto sale del argumento o de XIAO_PUERTO en .env.
set -euo pipefail
PSRAM="${PSRAM:-opi}"
FQBN="esp32:esp32:XIAO_ESP32S3:PSRAM=${PSRAM}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
CLI="${ARDUINO_CLI:-$(command -v arduino-cli || command -v arduino-cli.exe || echo "$HOME/bin/arduino-cli.exe")}"

PUERTO=""; MONITOR=0
for a in "$@"; do
    case "$a" in
        --monitor) MONITOR=1 ;;
        *) PUERTO="$a" ;;
    esac
done
if [ -z "$PUERTO" ] && [ -f "$RAIZ/.env" ]; then
    PUERTO="$(grep -E '^XIAO_PUERTO=' "$RAIZ/.env" | head -1 | cut -d= -f2- | tr -d '\r"' || true)"
fi
if [ -z "$PUERTO" ]; then
    echo "No hay puerto. Pasalo como argumento o define XIAO_PUERTO en .env. Puertos detectados:"
    "$CLI" board list || true
    echo
    echo "Si la placa no aparece: manten pulsado BOOT, pulsa y suelta RESET, suelta BOOT (modo bootloader)"
    echo "y vuelve a listar. Cierra el Monitor Serie antes de subir."
    exit 1
fi
"$CLI" upload -p "$PUERTO" --fqbn "$FQBN" --input-dir "$RAIZ/build"
if [ "$MONITOR" = 1 ]; then
    "$CLI" monitor -p "$PUERTO" -c baudrate=115200
fi
