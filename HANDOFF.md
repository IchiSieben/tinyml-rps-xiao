# HANDOFF: tinyml-rps-xiao  (updated: 2026-10-15)

## Goal
Demo TinyML piedra/papel/tijera/nada en XIAO ESP32S3 Sense, entrenada en Edge Impulse por API,
con dashboard local en vivo. Todo lo que no depende de placa, fotos o API key queda hecho.

## Current state
- DONE (segunda hora): inicio con Jugar, capó (D), arcade (A), sonidos WebAudio, juego con marcador,
  aura, easter eggs (metal, pulgar, Konami, consuelo), Fin de clase (F) con QR propio; clases abiertas
  en el contrato; `--guion` en el simulador; `--led-clases` en firmware y webcam. Revisión adversarial
  de 4 lentes: 6 defectos medios confirmados y arreglados; capturas estables 6/6. Último commit: 227dc08.
- DONE: dashboard Flask + SSE con simulador, serie y POST; capturas en `resultados/ui_*.png` y `demo.gif` (`python tools/capturas.py`).
- DONE: `firmware/parchear_libreria.py` con pruebas, y el sketch parcheado compila contra una librería
  pública real de Edge Impulse (`resultados/compilacion_libreria_ei_real.log`, 13 % de flash).
- DONE: `pipeline/inferencia_local.py` validado con el modelo SenseCraft del equipo
  (`resultados/validacion_modelo_referencia/resumen.md`).
- DONE: scripts de la API de Edge Impulse con `--dry-run` (nunca probados contra la API real: no hay clave).
- DONE: revisión independiente; arreglos en `3cc9433` y tildes en `c337cf3`.
- DONE: entorno arduino-cli + core esp32 3.3.12; `CameraWebServer` compila
  (`resultados/compilacion_camerawebserver.log`).
- DONE (segunda hora, 2026-10-15): interfaz nueva `18f80d0` (UX), juego y easter eggs `7b2cc63`,
  clases abiertas y `--guion`/`--led-clases` `5263ff8`..`f9cba5c`, capturas y prueba de consola `2e5bedc`,
  capturas y GIF `465318e`, documentación y `docs/SECRETOS.md` `eeac249`. `pytest -q`: 47 pasan (incluye `tests/test_ui.py`).
- BLOCKED (hardware/credenciales): fotos, API key, flasheo. Ver `docs/PENDIENTES.md`.

## Decisions
Ver `docs/DECISIONES.md` (la especificación `CLAUDE_TINYML_DEMO.md` no estaba en disco;
contrato JSON propio en `docs/CONTRATO.md`).

## Next steps
Seguir `docs/PENDIENTES.md` en orden, del paso 0 al 8.

## Commands that matter
- pruebas: `python -m pytest -q`
- demo sin placa: `python dashboard/servidor.py --simular`
- capturas y verificación de consola: `python tools/capturas.py` (necesita playwright y chromium)
- entorno: `bash firmware/compilar.sh --prueba-entorno`
