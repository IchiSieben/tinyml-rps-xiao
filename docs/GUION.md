# Guion de la demo (4 minutos)

Demo en vivo de clasificación de gestos de piedra, papel o tijera con TinyML (aprendizaje
automático en microcontroladores) sobre una XIAO ESP32S3 Sense. Pensado para presentarlo en el
Proyecto Integrador sin depender de Internet durante la exposición.

## Antes de entrar al aula

- [ ] Placa flasheada con la última librería (`firmware/flashear.ps1`).
- [ ] `python dashboard/servidor.py --serial COM5` corriendo y el navegador en `http://127.0.0.1:5000`.
- [ ] Plan B probado: `python dashboard/servidor.py --simular` (sin placa) y `pipeline/inferencia_local.py` con la webcam.
- [ ] Fondo liso detrás de la mano, buena luz frontal. Es el mismo fondo con el que se tomaron las fotos.
- [ ] Monitor Serie del Arduino IDE **cerrado** (si está abierto, el dashboard no puede leer el puerto).

## 0:00 · El problema (30 s)

"Una red neuronal normalmente corre en la nube o en una computadora. Hoy la vamos a correr dentro
de una placa del tamaño de un pulgar con 8 MB de PSRAM (memoria RAM externa), sin Internet y sin enviar la
imagen a ningún lado."

Mostrar la placa. Señalar la cámara y el LED de usuario.

## 0:30 · Cómo se entrenó (60 s)

Mostrar el README, sección "Flujo".

1. Tomamos fotos con la misma cámara de la placa usando `CameraWebServer` (variedad: ángulos,
   distancias, fondos y luz).
2. `preparar_dataset.py` elimina duplicados y separa 80 % entrenamiento y 20 % prueba. Las fotos de
   prueba **nunca** se usan para entrenar.
3. `subir_edge_impulse.py` y `entrenar.py` hacen todo por la API de Edge Impulse: no hay clics en
   el Studio, así que cualquiera del equipo puede repetirlo con un comando.
4. Modelo: Transfer Learning (MobileNetV2) sobre imágenes de 96x96, cuantizado a int8 (enteros de
   8 bits) para que quepa y sea rápido.

Mostrar la matriz de confusión del conjunto de prueba (`resultados/`).

## 1:30 · Demo en vivo (90 s)

1. Mano fuera de cámara: el dashboard marca `nada`.
2. Piedra, papel, tijera, despacio. Señalar las barras de probabilidad y la latencia de inferencia.
3. Tijera sostenida: el LED de la placa se enciende (umbral 60 %). Explicar que el LED es activo en
   bajo: se enciende escribiendo `LOW` en el GPIO 21 (pin de entrada y salida de propósito general).
4. Modo "Jugar contra la XIAO": dos rondas con alguien del público.

## 3:00 · Qué aprendimos y límites (45 s)

- La precisión medida sobre las fotos de entrenamiento no prueba nada; la que cuenta es la del 20 %
  separado.
- El modelo aprende el fondo y la luz además de la mano: con otro fondo baja la confianza.
- Puente al proyecto: la misma cadena (captura, Edge Impulse, int8, ESP32-S3) sirve para clasificar
  "malla limpia" contra "malla con obstrucción" en el nodo, y enviar foto por LoRa solo cuando haga
  falta. Es una alternativa a evaluar, no un cambio de arquitectura.

## 3:45 · Cierre (15 s)

"Todo está en GitHub y se reproduce con un comando por etapa." Mostrar el QR o la URL del repo.

## Si algo falla

| Síntoma | Qué hacer en el momento |
|---|---|
| El dashboard dice "Sin datos" | Cerrar el Monitor Serie; reiniciar `servidor.py --serial`. |
| La placa no aparece como puerto | Mantener BOOT, pulsar RESET, soltar BOOT; volver a conectar. |
| Predicciones erráticas | Acercar la mano, fondo liso, más luz. |
| Nada funciona | `servidor.py --simular` y explicar con el simulador. |
