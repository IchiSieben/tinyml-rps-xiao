# HANDOFF: tinyml-rps-xiao  (updated: 2026-10-15)

## Goal
Demo TinyML piedra/papel/tijera/nada en XIAO ESP32S3 Sense, entrenada en Edge Impulse por API,
con dashboard local en vivo. Todo lo que no depende de placa, fotos o API key queda hecho.

## Current state
- DONE: dashboard Flask + SSE con simulador, serie y POST; capturas en `resultados/dashboard_*.png`.
- DONE: `firmware/parchear_libreria.py` con pruebas, y el sketch parcheado compila contra una librería
  pública real de Edge Impulse (`resultados/compilacion_libreria_ei_real.log`, 13 % de flash).
- DONE: `pipeline/inferencia_local.py` validado con el modelo SenseCraft del equipo
  (`resultados/validacion_modelo_referencia/resumen.md`).
- DONE: scripts de la API de Edge Impulse con `--dry-run` (nunca probados contra la API real: no hay clave).
- DONE: revisión independiente; arreglos en `3cc9433` y tildes en `c337cf3`.
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
