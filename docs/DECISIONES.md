# Decisiones tomadas sin el dueño

Formato: fecha · tarea · qué se eligió · por qué · qué se descartó · cómo revertirlo.

## 2026-10-15 · especificación

- **Qué:** el archivo `CLAUDE_TINYML_DEMO.md` citado en el pedido no existe en la carpeta del
  proyecto ni en Descargas, Escritorio, `docs/`, `guia_IA/` o `parcial/`. Se trabajó con: el texto
  del pedido (clases, LED, pines, estructura), `tiny ml/PROMPT_ClaudeCode_TinyML.md` (flujo de la
  guía de Edge Impulse, pines de la XIAO, `ARENA_SIZE` 384605) y la wiki de Seeed.
- **Por qué:** modo autónomo, no se detiene la sesión.
- **Contrato JSON:** `docs/CONTRATO.md` es una propuesta propia. Si la especificación original
  define otro formato, se cambia en tres sitios: `firmware/salida_json.h`, `dashboard/servidor.py`
  (función de validación) y `pipeline/inferencia_local.py`.
- **Revertir:** reemplazar `docs/CONTRATO.md` y los tres sitios anteriores.

## 2026-10-15 · herramientas

- **arduino-cli:** la URL "latest" entregó `1.5.2-rc.1`. Se dejó así: la regla "nada alpha" del
  pedido es para el core esp32, no para la CLI. Core instalado: `esp32:esp32@3.3.12` (estable,
  índice `package_esp32_index.json`, que no publica versiones alpha ni RC).
- **Revertir:** descargar una CLI estable desde https://github.com/arduino/arduino-cli/releases.

## 2026-10-15 · validación del parcheador con una librería real

- **Qué:** como no hay modelo propio todavía, el parche se probó compilando contra una librería
  pública de Edge Impulse para clasificación de imagen (ver `resultados/compilacion_libreria_ei_real.log`).
  Sus etiquetas son nombres de personas: se omitieron del log. El commit `832ce63` todavía las
  contiene en el historial; no se reescribió el historial porque eso exige force-push.
- **Descartado:** una librería más antigua (SDK viejo) que no compila con gcc 14 del core 3.x por un
  problema del propio SDK. Si Edge Impulse entrega un SDK así, la salida es exportar de nuevo desde
  el Studio (las exportaciones actuales traen el SDK nuevo).
- **Revertir:** borrar `resultados/compilacion_libreria_ei_real.log`.

## 2026-10-15 · LED con una sola regla

- **Qué:** `led = (clase == clase_led) y (confianza >= umbral)` en firmware, webcam y simulador
  (antes cada uno usaba una regla distinta). Por defecto `tijera` y 0.6.
- **Revertir:** `--led-clase` en `servidor.py`, `inferencia_local.py` y `parchear_libreria.py`.

## 2026-10-15 · clases abiertas en el contrato

- **Qué:** `probs` acepta de 2 a 16 etiquetas `[a-z0-9_]` (hasta 24 caracteres); `clase` debe ser una
  clave de `probs`. Ya no hay cuatro clases fijas. El validador ordena `probs` (piedra, papel,
  tijera, nada y luego el resto). Para el LED hay lista de clases (`--led-clases "tijera,metal"`).
- **Prueba existente cambiada:** `tests/test_dashboard.py::test_rechaza_malas` borraba `probs['nada']`
  y esperaba rechazo; con clases abiertas eso es válido. Ahora borra `probs['tijera']` (la clase
  ganadora, que sigue siendo inválido), con un comentario de una línea. Los demás casos no cambian.
- **Por qué:** los gestos extra (`metal`, `pulgar`) se agregan solo con carpetas o ZIP nuevos, y el
  dashboard debe mostrarlos sin tocar código.
- **Descartado:** mantener `nada` obligatoria (obliga a todo modelo a tener esa clase); lista cerrada
  de clases extra (hay que editar código por cada gesto nuevo).
- **Revertir:** volver a la tupla fija de cuatro clases en `dashboard/contrato.py` y restaurar la
  línea `del falta["probs"]["nada"]` en la prueba.
