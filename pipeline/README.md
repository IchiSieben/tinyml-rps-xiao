# Pipeline: de las fotos a la biblioteca Arduino

Entrena el clasificador piedra / papel / tijera / nada en Edge Impulse **solo por API** (sin hacer clic
en Studio) y lo prueba en la PC antes de grabarlo en la XIAO ESP32S3 Sense.

Requisitos: `pip install -r requirements.txt`, y copiar `.env.example` a `.env` con `EI_API_KEY`
(y `EI_PROJECT_ID`, opcional: si falta, se usa el proyecto visible con la clave). La clave nunca se imprime
completa (sale como `ei_****abcd`). Todos los scripts de API aceptan `--dry-run`: muestran las peticiones y no
necesitan clave ni red.

## Orden de comandos

```bash
# 1. Fotos crudas -> dataset validado, sin duplicados, 96x96, 80/20 estratificado
python pipeline/preparar_dataset.py --entrada datos/crudas
#    o con los ZIPs de la pagina de captura (la clase sale del nombre del archivo)
python pipeline/preparar_dataset.py --zips piedra.zip papel.zip tijera.zip nada.zip

# 2. Subir a Edge Impulse (Ingestion API)
python pipeline/subir_edge_impulse.py

# 3. Impulso + features + transfer learning + metricas (guarda resultados/entrenamiento_<fecha>.json)
python pipeline/entrenar.py --probar

# 4. Biblioteca Arduino int8 (+ .tflite) en modelos/
python pipeline/descargar_libreria.py --tflite

# 5. Probar en la PC con la webcam (emite el contrato JSON de docs/CONTRATO.md)
python pipeline/inferencia_local.py --modelo modelos/rps_int8.tflite --etiquetas nada,papel,piedra,tijera --mostrar --enviar http://127.0.0.1:5000

# 6. Parchear la biblioteca para el firmware
python firmware/parchear_libreria.py modelos/rps_arduino.zip --led-clase tijera --umbral 0.60
```

Edge Impulse ordena las etiquetas alfabeticamente (`nada, papel, piedra, tijera`); ese es el orden de salida del
modelo. `inferencia_local.py` traduce por nombre y emite siempre `piedra, papel, tijera, nada`.

## Banderas principales

| Script | Bandera | Para que |
|---|---|---|
| `preparar_dataset.py` | `--entrada`, `--zips` | Carpeta por clase, o un ZIP por clase |
| | `--tam 96` (0 = original) | Lado del recorte cuadrado centrado |
| | `--prueba 0.2`, `--semilla 42` | Reparto estratificado reproducible |
| | `--hash-umbral 2` | Distancia (hash promedio de 64 bits) para descartar duplicados |
| | `--dry-run` | Muestra conteos y avisos sin escribir. Avisa si hay menos de 30 por clase |
| `subir_edge_impulse.py` | `--datos`, `--lote 20` | Origen y archivos por peticion |
| `entrenar.py` | `--ciclos 20`, `--tasa 0.0005`, `--tam 96` | Entrenamiento (MobileNetV2 0.35, 96x96) |
| | `--capa` | Otra base de transfer learning |
| | `--probar` | Clasifica el conjunto testing al final |
| `descargar_libreria.py` | `--eon`, `--tflite`, `--nombre` | Motor EON, bajar el .tflite, prefijo de archivos |
| `inferencia_local.py` | `--modelo`, `--etiquetas` | `.tflite` y etiquetas (lista, archivo, `model_metadata.h` o `labels.txt` junto al modelo) |
| | `--camara 0`, `--umbral 0.6`, `--mostrar`, `--enviar URL` | Webcam, LED logico, ventana, POST a `/api/inferencia` |
| | `--evaluar CARPETA_O_ZIP --salida DIR` | Exactitud, matriz de confusion, CSV y PNG |
| | `--rango 01\|0255` | Forzar el rango de pixeles de entrada |

### Rango de entrada

La forma, el tipo, `scale` y `zero_point` se leen del interprete, nunca van fijos. Heuristica: el techo del valor
cuantizado es `(qmax - zero_point) * scale`; si es cercano a 1 el modelo espera pixeles en [0, 1] (caso de Edge Impulse
y SenseCraft), si es cercano a 255 espera [0, 255]. `--rango` fuerza el valor.

## Validacion con un modelo de referencia

Modelo SenseCraft MobileNet int8 (224x224, 2 clases) y sus 162 fotos de entrenamiento:

| Orden de etiquetas | Exactitud |
|---|---|
| `Celular,Lentes` | 0.0000 (0/162) |
| `Lentes,Celular` | 1.0000 (162/162) |

Orden consistente: `Lentes,Celular`. Rango usado: [0, 1] (con [0, 255] la exactitud cae a 0.5).
Detalle y matrices en [`../resultados/validacion_modelo_referencia/resumen.md`](../resultados/validacion_modelo_referencia/resumen.md).
Son las fotos de entrenamiento: valida el preprocesado, no la generalizacion.

## Endpoints de la Studio API usados

`POST /{projectId}/impulse`, `POST /{projectId}/dsp/{dspId}`, `POST /{projectId}/jobs/generate-features`,
`POST /{projectId}/training/keras/{learnId}`, `POST /{projectId}/jobs/train/keras/{learnId}`,
`GET /{projectId}/jobs/{jobId}/status`, `GET /{projectId}/training/keras/{learnId}/metadata`,
`POST /{projectId}/jobs/classify`, `GET /{projectId}/classify/all/result`,
`POST /{projectId}/jobs/build-ondevice-model?type=arduino`, `GET /{projectId}/deployment/download`.
Comprobados contra el OpenAPI (https://studio.edgeimpulse.com/openapi.yml). Sin comprobar contra una cuenta real: la clave
`channels` del bloque DSP image y el `modelDownloadId` `tflite-int8` del `.tflite`.
