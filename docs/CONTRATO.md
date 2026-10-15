# Contrato de datos: una inferencia, una línea JSON

Todas las piezas del repo hablan el mismo formato: el firmware de la XIAO lo imprime por el puerto
serie, `pipeline/inferencia_local.py` lo imprime por stdout (o lo envía por HTTP al dashboard) y
`dashboard/servidor.py` lo lee, lo valida y lo reenvía al navegador por SSE (Server-Sent Events,
eventos enviados por el servidor).

## Reglas

1. Una inferencia es **una sola línea** de JSON compacto, terminada en `\n`, sin saltos internos.
2. La línea empieza con `{` y contiene `"v":1`. Cualquier otra línea del puerto serie (logs de
   arranque, mensajes de Edge Impulse) se **ignora** sin error.
3. Codificación ASCII: las etiquetas no llevan tildes ni eñes.
4. Las probabilidades van en `[0, 1]` con 4 decimales como máximo. Su suma puede no ser 1 por
   redondeo y cuantización int8 (entero de 8 bits).

## Campos

| Campo | Tipo | Obligatorio | Significado |
|---|---|---|---|
| `v` | int | sí | Versión del contrato. Hoy `1`. |
| `fuente` | string | sí | `xiao`, `webcam` o `simulacion`. |
| `n` | int | sí | Contador de inferencias desde el arranque (empieza en 0). |
| `t_ms` | int | sí | Milisegundos desde el arranque del emisor (`millis()` en la placa). |
| `clase` | string | sí | Clase ganadora: `piedra`, `papel`, `tijera` o `nada`. |
| `confianza` | float | sí | Probabilidad de la clase ganadora. |
| `probs` | objeto | sí | Probabilidad por clase, las cuatro claves siempre presentes. |
| `lat_ms` | objeto | sí | `{"dsp": int, "inf": int}`: preprocesado e inferencia en ms. |
| `led` | bool | sí | Estado lógico del LED (true = encendido), sin importar que sea activo en bajo. |
| `umbral` | float | sí | Umbral de confianza usado para encender el LED. |

Clases fijas y en este orden: `piedra`, `papel`, `tijera`, `nada`. El orden real de salida del
modelo lo define Edge Impulse (orden alfabético de etiquetas: `nada, papel, piedra, tijera`); el
emisor traduce por nombre, nunca por posición.

## Ejemplo

```json
{"v":1,"fuente":"xiao","n":42,"t_ms":183220,"clase":"tijera","confianza":0.9141,"probs":{"piedra":0.0234,"papel":0.0469,"tijera":0.9141,"nada":0.0156},"lat_ms":{"dsp":4,"inf":187},"led":true,"umbral":0.6}
```

## Transporte

| Emisor | Canal | Cómo llega al dashboard |
|---|---|---|
| XIAO ESP32S3 Sense | Serie USB a 115200 baudios | `servidor.py --serial COM5` |
| Webcam en la PC | stdout o `POST /api/inferencia` | `inferencia_local.py --enviar http://127.0.0.1:5000` |
| Simulador | interno | `servidor.py --simular` |

El dashboard reenvía cada línea válida tal cual como evento SSE `inferencia` en `GET /api/stream`.
