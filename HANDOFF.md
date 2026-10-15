# HANDOFF: tinyml-rps-xiao  (updated: 2026-10-15)

## Goal
Demo TinyML piedra/papel/tijera/nada en XIAO ESP32S3 Sense, entrenada en Edge Impulse por API,
con dashboard local en vivo. Todo lo que no depende de placa, fotos o API key queda hecho.

## Current state
- DONE: dashboard Flask + SSE con simulador, serie y POST; capturas en `resultados/dashboard_*.png`.
- DONE: `firmware/parchear_libreria.py` con pruebas sobre el `esp32_camera.ino` real de Edge Impulse.
- DONE: `pipeline/inferencia_local.py` validado con el modelo SenseCraft del equipo
  (`resultados/validacion_modelo_referencia/resumen.md`).
- DONE: scripts de la API de Edge Impulse con `--dry-run`.
- DONE: entorno arduino-cli + core esp32 3.3.12; `CameraWebServer` compila
  (`resultados/compilacion_camerawebserver.log`).
- BLOCKED (hardware/credenciales): fotos, API key, flasheo. Ver `docs/PENDIENTES.md`.

## Decisions
Ver `docs/DECISIONES.md` (la especificación `CLAUDE_TINYML_DEMO.md` no estaba en disco;
contrato JSON propio en `docs/CONTRATO.md`).

## Next steps
Seguir `docs/PENDIENTES.md` en orden, del paso 0 al 8.

## Commands that matter
- pruebas: `python -m pytest -q`
- demo sin placa: `python dashboard/servidor.py --simular`
- entorno: `bash firmware/compilar.sh --prueba-entorno`
