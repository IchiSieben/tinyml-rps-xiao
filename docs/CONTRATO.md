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
| `clase` | string | sí | Clase ganadora. Debe ser una clave de `probs`. |
| `confianza` | float | sí | Probabilidad de la clase ganadora. |
| `probs` | objeto | sí | Probabilidad por clase: de 2 a 16 claves (ver "Clases abiertas"). |
| `lat_ms` | objeto | sí | `{"dsp": int, "inf": int}`: preprocesado e inferencia en ms. |
| `led` | bool | sí | Estado lógico del LED (true = encendido), sin importar que sea activo en bajo. Regla única en placa, webcam y simulador: `clase in clases_led` y `confianza >= umbral` (por defecto `clases_led = [tijera]` y 0.6; ver "Regla del LED"). |
| `umbral` | float | sí | Umbral de confianza usado para encender el LED. |

## Clases abiertas

Las clases **no están fijas**. `probs` puede traer cualquier conjunto de etiquetas y el dashboard
no asume cuatro:

- De 2 a 16 claves; cada etiqueta cumple `^[a-z0-9_]{1,24}$` (minúsculas ASCII, dígitos y guion bajo;
  sin tildes, mayúsculas ni espacios). Cada valor está en `[0, 1]`.
- `clase` es una de las claves de `probs`; si no lo es, la línea se rechaza.
- El orden de las claves **no es significativo**. El validador las normaliza para mostrar: primero
  `piedra`, `papel`, `tijera`, `nada` (las que existan, en ese orden) y luego el resto en el orden
  recibido.
- Un modelo puede no tener `nada` (por ejemplo `piedra`, `papel`, `tijera`, `metal`).
- El emisor traduce por nombre, nunca por posición. El orden de salida real del modelo lo define
  Edge Impulse (alfabético). Edge Impulse acepta etiquetas con otros caracteres, pero para este
  contrato hay que nombrarlas en minúsculas ASCII desde el principio (el nombre de la carpeta o ZIP
  de cada clase es la etiqueta).
- Gestos extra previstos: `metal` y `pulgar`. Cualquier otra clase se acepta igual.

## Regla del LED

El LED se enciende si la clase ganadora está en la **lista de clases del LED** y
`confianza >= umbral`. La lista por defecto es `tijera`. Se configura con banderas, sin tocar código:
`--led-clase tijera` (una clase) y/o `--led-clases "tijera,metal"` (varias, se unen) en
`dashboard/servidor.py`, `pipeline/inferencia_local.py` y `firmware/parchear_libreria.py`.

## Ejemplo

Con clases nuevas (aquí `metal` y `pulgar`), en una sola línea:

```json
{"v":1,"fuente":"xiao","n":43,"t_ms":183420,"clase":"metal","confianza":0.8828,"probs":{"piedra":0.0117,"papel":0.0156,"tijera":0.0273,"nada":0.0078,"metal":0.8828,"pulgar":0.0547},"lat_ms":{"dsp":4,"inf":191},"led":true,"umbral":0.6}
```

Con cuatro clases:

```json
{"v":1,"fuente":"xiao","n":42,"t_ms":183220,"clase":"tijera","confianza":0.9141,"probs":{"piedra":0.0234,"papel":0.0469,"tijera":0.9141,"nada":0.0156},"lat_ms":{"dsp":4,"inf":187},"led":true,"umbral":0.6}
```

## Transporte

| Emisor | Canal | Cómo llega al dashboard |
|---|---|---|
| XIAO ESP32S3 Sense | Serie USB a 115200 baudios | `servidor.py --serial COM5` |
| Webcam en la PC | stdout o `POST /api/inferencia` | `inferencia_local.py --enviar http://127.0.0.1:5000` |
| Simulador | interno | `servidor.py --simular` (con `--guion "piedra,papel,metal"` fuerza la secuencia) |

El dashboard reenvía cada línea válida tal cual como evento SSE `inferencia` en `GET /api/stream`.

`GET /api/estado` devuelve, además de los conteos por clase, `puerto` (puerto serie o cadena vacía) y
`clases` (las clases vistas, en orden de visualización).
