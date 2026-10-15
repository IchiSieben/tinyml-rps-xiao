# Dashboard en vivo

Panel web para ver las inferencias del clasificador piedra, papel o tijera (XIAO ESP32S3 Sense). Un solo archivo HTML sin CDN ni fuentes externas, claro y oscuro, adaptado a celular.

![Dashboard](../resultados/dashboard_claro.png)

## Ejecutar

Desde la raiz del repo (necesita `flask`; `pyserial` solo para el modo serie):

| Modo | Comando |
|---|---|
| Simulacion (sin hardware) | `python dashboard/servidor.py --simular` |
| XIAO por USB | `python dashboard/servidor.py --serial COM5` (o define `XIAO_PUERTO` en `.env` y usa `--serial`) |
| Webcam | `python dashboard/servidor.py` y en otra terminal `python pipeline/inferencia_local.py --enviar http://127.0.0.1:5000` |

Opciones: `--puerto-http 5000`, `--host 127.0.0.1`, `--baudios 115200`. Abre `http://127.0.0.1:5000`.

## Endpoints

- `GET /` : la pagina.
- `GET /api/stream` : SSE, evento `inferencia` y un latido cada 15 s.
- `GET /api/estado` : fuente, conexion, conteos por clase, ultima inferencia, latencia media y tiempo activo.
- `POST /api/inferencia` : una inferencia en JSON o una linea cruda; 400 si no cumple `docs/CONTRATO.md`.

## Pruebas

`python -m pytest tests/test_dashboard.py -q`

Capturas: `resultados/dashboard_claro.png`, `dashboard_oscuro.png`, `dashboard_movil.png`.
