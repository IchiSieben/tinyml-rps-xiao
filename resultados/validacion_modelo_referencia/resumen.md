# Validacion de `inferencia_local.py` con un modelo de referencia

Modelo: `Xiao_20261013200520.tflite` (SenseCraft, MobileNet int8, entrada 1x224x224x3, 2 clases).
Datos: `classification_dataset.zip`, 162 JPG de 224x224 (81 en `Celular/`, 81 en `Lentes/`).
Comando: `python pipeline/inferencia_local.py --modelo M.tflite --etiquetas <orden> --evaluar <carpeta> --salida <dir>`

Parametros leidos del interprete: entrada `int8`, `scale=0.00738178`, `zero_point=-8`.

## Rango de entrada usado

`[0,1]` (detectado por la heuristica). Con esos parametros el valor cuantizado cubre
`(127-(-8))*0.00738 = 0.996`, es decir [0,1]. Se probo tambien `--rango 0255` con el orden bueno:
exactitud 0.5000 (azar), asi que `[0,1]` es el correcto.

## Orden de etiquetas `Celular,Lentes`

Exactitud: 0.0000 (0/162).

| real \ prediccion | Celular | Lentes |
|---|---|---|
| Celular | 0 | 81 |
| Lentes | 81 | 0 |

## Orden de etiquetas `Lentes,Celular`

Exactitud: 1.0000 (162/162).

| real \ prediccion | Lentes | Celular |
|---|---|---|
| Lentes | 81 | 0 |
| Celular | 0 | 81 |

## Conclusion

El orden consistente es `Lentes,Celular` (salida 0 = Lentes, salida 1 = Celular): es el unico que
da aciertos; el otro invierte todas las predicciones (0/162), lo que confirma que el modelo separa
las clases perfectamente y solo el orden de la lista de etiquetas decide. Esto tambien demuestra que
la cuantizacion, el recorte centrado y la lectura de `scale`/`zero_point` de `inferencia_local.py`
reproducen el preprocesado del modelo.

Evaluar el .tflite sobre las mismas 162 fotos no es medir generalización: son las fotos de entrenamiento.

Archivos por orden: `predicciones.csv`, `matriz_confusion.csv`, `matriz_confusion.png` en
`orden_celular_lentes/` y `orden_lentes_celular/`.
