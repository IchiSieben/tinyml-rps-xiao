# tinyml-rps-xiao

![Placa](https://img.shields.io/badge/placa-XIAO%20ESP32S3%20Sense-1f6feb)
![Core](https://img.shields.io/badge/core%20esp32-3.3.12-2ea44f)
![Edge Impulse](https://img.shields.io/badge/Edge%20Impulse-API-6f42c1)
![Python](https://img.shields.io/badge/Python-3.12-3776ab)
![Flask](https://img.shields.io/badge/Flask-SSE-000000)

Piedra, papel o tijera con TinyML (aprendizaje automático en microcontroladores): una XIAO
ESP32S3 Sense mira la mano, clasifica el gesto en la propia placa y enciende su LED (diodo emisor de luz) cuando ve
`tijera` con más de 60 % de confianza. El modelo se entrena en Edge Impulse **por API** (interfaz de programación), sin clics
en el Studio, y un dashboard local muestra cada inferencia en vivo.

Curso Proyecto Integrador C7328, UPCH (Universidad Peruana Cayetano Heredia) 2026-II.

## Cómo se juega

![Demo: inicio, cuenta regresiva, resultado y fin de clase](resultados/demo.gif)

Abre el dashboard, pulsa **Jugar** (o Enter), muestra la mano a la cámara con la palma hacia ella, a
30 o 40 cm, y espera la cuenta 3, 2, 1. La placa elige su jugada al azar y el marcador guarda partidas,
racha y mejor racha en el navegador. Todo lo técnico (latencia, DSP, LED, sparkline) está en el panel
"Debajo del capó".

| Pantalla | Captura |
|---|---|
| Inicio | ![Inicio](resultados/ui_inicio.png) |
| Jugando | ![Jugando](resultados/ui_jugando.png) |
| Tema arcade | ![Arcade](resultados/ui_arcade.png) |
| Aura al máximo | ![Full aura](resultados/ui_full_aura.png) |
| Fin de clase | ![Fin de clase](resultados/ui_fin_de_clase.png) |

| Tecla | Qué hace |
|---|---|
| Enter o Espacio | Jugar una partida |
| D | Abrir o cerrar "Debajo del capó" |
| A | Alternar el tema arcade |
| M | Silenciar o activar el sonido |
| F | Pantalla de fin de clase con resumen y QR |
| Esc | Cerrar el panel o la pantalla abierta |

Hay cosas escondidas. Si quieres descubrirlas jugando, no abras [docs/SECRETOS.md](docs/SECRETOS.md)
(contiene spoilers).

## Flujo

```
fotos (CameraWebServer)          pipeline/preparar_dataset.py      pipeline/subir_edge_impulse.py
datos/crudas/<clase>/*.jpg  -->  datos/listo/{training,testing}  -->  Edge Impulse (Ingestion API)
                                                                              |
firmware/flashear  <--  firmware/compilar  <--  firmware/parchear_libreria.py  <--  pipeline/entrenar.py
      |                                                                          pipeline/descargar_libreria.py
      v
XIAO: una línea JSON por inferencia (docs/CONTRATO.md)  -->  dashboard/servidor.py --serial  -->  navegador
```

Clases base: `piedra`, `papel`, `tijera`, `nada`; el dashboard acepta además cualquier otra que traiga el modelo (2 a 16 etiquetas). Contrato de datos entre placa, webcam y dashboard:
[docs/CONTRATO.md](docs/CONTRATO.md).

## Probarlo ya, sin placa

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows (Git Bash); en macOS o Linux: source .venv/bin/activate
pip install -r requirements.txt
python dashboard/servidor.py --simular
# abrir http://127.0.0.1:5000
```

Pruebas: `python -m pytest -q`. Para correr también la prueba de cuantización con un modelo TFLite real: `pip install -r requirements-dev.txt`.

## Estructura

| Carpeta | Qué hay |
|---|---|
| [firmware/](firmware/README.md) | Parcheador de la librería de Edge Impulse (pines de la XIAO, LED en GPIO 21 (pin de entrada y salida de propósito general) activo en bajo, salida JSON (JavaScript Object Notation)), compilación y flasheo con `arduino-cli`. |
| [pipeline/](pipeline/README.md) | Preparación del dataset, subida y entrenamiento por API, descarga de la librería, inferencia local con webcam. |
| [dashboard/](dashboard/README.md) | Servidor Flask con SSE (eventos enviados por el servidor) y una página de un solo archivo, sin CDN (red de distribución de contenidos). |
| [tests/](tests/) | Pruebas con `pytest` (`-m "not ui"` omite la prueba del navegador). |
| [tools/](tools/capturas.py) | `capturas.py`: capturas, GIF y verificación de consola con Playwright (requiere `pip install -r requirements-dev.txt` y `python -m playwright install chromium`). |
| [resultados/](resultados/) | Capturas de la interfaz (`python tools/capturas.py`), log de compilación y validación de la inferencia local. |
| [docs/](docs/) | Contrato JSON, guion de la demo, decisiones y lista de pendientes. |

## Lo que falta y depende del hardware

Ver [docs/PENDIENTES.md](docs/PENDIENTES.md): la lista exacta, en orden, de lo que hay que hacer
con la placa, las fotos y la clave de la API de Edge Impulse.

## Secretos

La clave de Edge Impulse va solo en `.env` (copia de `.env.example`), que está en `.gitignore`.
Ningún script la imprime completa.
