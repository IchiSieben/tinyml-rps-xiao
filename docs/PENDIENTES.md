# Lo que falta, en orden

Todo lo que no depende de la placa, las fotos o la clave de Edge Impulse ya está hecho y probado.
Esto es lo que queda, con el comando exacto de cada paso. Los comandos son para PowerShell en
Windows desde la raíz del repo; en macOS o Linux cambia `.ps1` por `.sh` y `COM5` por el puerto
que liste `arduino-cli board list`.

## 0. Preparar la máquina (5 min, una sola vez)

```powershell
git clone https://github.com/IchiSieben/tinyml-rps-xiao; cd tinyml-rps-xiao
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
python dashboard/servidor.py --simular     # abrir http://127.0.0.1:5000 y cerrar con Ctrl+C
```

En otra máquina hace falta además `arduino-cli` en el PATH; `firmware/compilar.ps1` instala el
core `esp32:esp32@3.3.12` si no está.

## 1. Conectar la placa (2 min)

1. Conectar la XIAO ESP32S3 Sense por USB-C (cable de datos, no solo de carga).
2. `arduino-cli board list` y anotar el puerto. Si no aparece: mantener BOOT, pulsar RESET, soltar BOOT.
3. `copy .env.example .env` y poner `XIAO_PUERTO=COM5` (el que salió).

## 2. Tomar las fotos (30 a 40 min)

1. En Arduino IDE: Archivo > Ejemplos > ESP32 > Camera > CameraWebServer. Dejar solo
   `#define CAMERA_MODEL_XIAO_ESP32S3`, poner el SSID y la clave del Wi-Fi **solo en tu copia local**,
   placa XIAO_ESP32S3, PSRAM "OPI PSRAM", subir. El Monitor Serie muestra la IP.
2. Abrir `captura_xiao_etiqueta_personalizada.html` (la página de la clase), poner la IP y capturar
   un ZIP por clase con el nombre de la clase: `piedra.zip`, `papel.zip`, `tijera.zip`, `nada.zip`.
3. Al menos 60 fotos por clase, con variedad: dos o tres personas, mano izquierda y derecha,
   distancias de 15 a 40 cm, dos fondos, luz natural y de foco. `nada` = fondo vacío y la mano
   en reposo o fuera de cuadro.
4. Copiar los cuatro ZIP a `datos/zips/` (está en `.gitignore`).

## 3. Preparar el dataset (1 min)

```powershell
python pipeline/preparar_dataset.py --zips datos/zips/piedra.zip datos/zips/papel.zip datos/zips/tijera.zip datos/zips/nada.zip --dry-run
python pipeline/preparar_dataset.py --zips datos/zips/piedra.zip datos/zips/papel.zip datos/zips/tijera.zip datos/zips/nada.zip
```

Revisar las advertencias: menos de 30 fotos por clase o muchos duplicados significa volver al paso 2.

## 4. Crear el proyecto y la clave de Edge Impulse (3 min)

1. https://studio.edgeimpulse.com > Create new project (tipo imagen, clasificación, **no** detección de objetos).
2. Dashboard > Keys > copiar la API key (empieza con `ei_`).
3. En `.env`: `EI_API_KEY=ei_...` y `EI_PROJECT_ID=` con el número que aparece en la URL del proyecto.

## 5. Subir, entrenar y descargar por API (10 a 15 min, casi todo es espera)

```powershell
python pipeline/subir_edge_impulse.py --dry-run
python pipeline/subir_edge_impulse.py
python pipeline/entrenar.py --dry-run
python pipeline/entrenar.py --probar
python pipeline/descargar_libreria.py --tflite
```

Queda `modelos/rps_arduino.zip` y `modelos/rps_int8.tflite`. `entrenar.py --probar` guarda las
métricas del 20 % de prueba en `resultados/entrenamiento_<fecha>.json`.

## 6. Parchear, compilar y flashear (5 a 10 min)

```powershell
python firmware/parchear_libreria.py modelos/rps_arduino.zip --led-clase tijera --umbral 0.60
.\firmware\compilar.ps1 -Zip modelos\rps_arduino_xiao.zip
.\firmware\flashear.ps1 -Puerto COM5 -Monitor
```

Si la compilación o el arranque fallan por memoria, repetir el parcheo con `--arena 384605`.
Cerrar el monitor (Ctrl+C) antes del paso 7: dos programas no pueden abrir el mismo puerto.

## 7. Demo en vivo

```powershell
python dashboard/servidor.py --serial COM5
```

Plan B con la webcam de la laptop y el mismo modelo (las etiquetas van en el orden de salida de
Edge Impulse, que es alfabético):

```powershell
python dashboard/servidor.py                  # sin bandera: solo escucha POST /api/inferencia
python pipeline/inferencia_local.py --modelo modelos/rps_int8.tflite --etiquetas nada,papel,piedra,tijera --enviar http://127.0.0.1:5000 --mostrar
```

## 8. Cerrar

1. Pegar en el README la exactitud del conjunto de prueba (del JSON de `resultados/`) y una captura
   del dashboard con la placa real.
2. Opcional, como pide la guía: subir `modelos/rps_int8.tflite` a SenseCraft (Espacio de trabajo > Subir modelo).
3. Ensayar `docs/GUION.md` una vez de punta a punta.

## 9. Gestos extra: cuántas fotos y cómo

Dos gestos opcionales además de las cuatro clases base: `metal` (🤘) y `pulgar` (👍). No hace falta
tocar código: las clases nuevas entran solo como carpeta o ZIP, y el dashboard las muestra solo.

1. **Cuántas fotos.** Las mismas reglas de variedad del paso 2 (dos o tres personas, mano izquierda y
   derecha, 15 a 40 cm, dos fondos, luz natural y de foco) y **al menos 60 por clase**, igual que las
   cuatro base. Con menos de 30 útiles `preparar_dataset.py` avisa.
2. **Nombre del ZIP = nombre de la clase**, en minúsculas y sin tildes: `metal.zip`, `pulgar.zip`
   (solo `a-z`, `0-9` y `_`, hasta 24 caracteres). El script normaliza el nombre (minúsculas, sin tildes, espacios a `_`) y avisa si aun así no cumple el contrato.
   Pon los ZIP en `datos/zips/`.
3. **`nada` tiene que seguir existiendo**: es lo que evita que el LED o el juego reaccionen al fondo.
   Sin mano, `nada` debe ganar; asegúrate de tener fotos de fondo vacío con cada fondo y luz que uses.
4. **Más clases bajan la exactitud.** Seis clases se confunden más que cuatro (`metal` con `tijera`,
   `pulgar` con `piedra`). Tras entrenar, vuelve a revisar la matriz de confusión del 20 % de prueba
   (`entrenar.py --probar` la guarda en `resultados/entrenamiento_<fecha>.json`) y, si una pareja se
   mezcla, agrega fotos de esas dos clases con variedad de ángulos.
5. **Comando exacto de preparar con las seis clases:**

```powershell
python pipeline/preparar_dataset.py --zips datos/zips/piedra.zip datos/zips/papel.zip datos/zips/tijera.zip datos/zips/nada.zip datos/zips/metal.zip datos/zips/pulgar.zip --dry-run
python pipeline/preparar_dataset.py --zips datos/zips/piedra.zip datos/zips/papel.zip datos/zips/tijera.zip datos/zips/nada.zip datos/zips/metal.zip datos/zips/pulgar.zip
```

   Después siguen igual `subir_edge_impulse.py`, `entrenar.py --probar` y `descargar_libreria.py --tflite`
   (los tres leen las clases de las carpetas y del proyecto, no de una lista fija).
6. **Parchear con el LED en dos clases:**

```powershell
python firmware/parchear_libreria.py modelos/rps_arduino.zip --led-clases "tijera,metal" --umbral 0.60
```

   Para la webcam: `python pipeline/inferencia_local.py ... --led-clases "tijera,metal"`. Para ensayar el
   dashboard sin placa: `python dashboard/servidor.py --simular --guion "piedra,papel,metal,pulgar,nada" --led-clases "tijera,metal"`
   (`--guion-bucle` lo repite; cada elemento dura 1.6 s, o `metal:3` para 3 s).
