# Firmware para la XIAO ESP32S3 Sense

Convierte la librería Arduino que exporta Edge Impulse en un firmware que imprime, por el puerto
serie, una línea JSON por inferencia (formato en [`../docs/CONTRATO.md`](../docs/CONTRATO.md)).

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `xiao_pins.h` | Pines de la cámara de la XIAO ESP32S3 Sense y del LED de usuario (GPIO21, activo en bajo). |
| `salida_json.h` | Imprime la línea JSON del contrato y maneja el LED. Busca las clases por nombre, nunca por posición. |
| `parchear_libreria.py` | Toma el ZIP de Edge Impulse y genera `<nombre>_xiao.zip` listo para la XIAO. Solo librería estándar de Python 3.10+. |
| `compilar.ps1` / `compilar.sh` | Instalan el core `esp32:esp32@3.3.12` si falta y compilan con `arduino-cli`. |
| `flashear.ps1` / `flashear.sh` | Suben `build/` a la placa y, opcional, abren el monitor serie a 115200. |

## Secuencia de comandos

Exporta en Edge Impulse: Deployment > Arduino library > Build, y guarda el ZIP (por ejemplo
`rps-arduino.zip`).

```powershell
# 1. Parchear (LED opcional: se enciende con "piedra" si la confianza es >= 0.60)
python firmware/parchear_libreria.py rps-arduino.zip --led-clase piedra --umbral 0.60
# Varias clases para el LED (se unen con --led-clase si se pasan las dos):
python firmware/parchear_libreria.py rps-arduino.zip --led-clases "tijera,metal" --umbral 0.60

# 2. Compilar (genera build/)
.\firmware\compilar.ps1 -Zip rps-arduino_xiao.zip

# 3. Subir y ver la salida
.\firmware\flashear.ps1 -Puerto COM5 -Monitor
```

En Linux o macOS: `./firmware/compilar.sh rps-arduino_xiao.zip` y `./firmware/flashear.sh /dev/ttyACM0 --monitor`.

El puerto también se puede guardar como `XIAO_PUERTO=COM5` en `.env`. Para el dashboard:
`python dashboard/servidor.py --serial COM5` (cierra antes el monitor serie).

El parcheado es idempotente: repetirlo sobre un ZIP ya parcheado no cambia nada. Cada cambio se
imprime en pantalla.

## Prueba del entorno sin modelo

Antes de tener el modelo, comprueba que el core y la placa compilan con el ejemplo oficial de cámara:

```powershell
.\firmware\compilar.ps1 -PruebaEntorno
```

No se rellenan credenciales WiFi: solo se compila. El registro de la última prueba esta en
`resultados/compilacion_camerawebserver.log`.

## Solución de problemas

- **El puerto no aparece o no se reconoce:** entra en modo bootloader. Mantén pulsado BOOT, pulsa y
  suelta RESET, suelta BOOT. Luego `arduino-cli board list` debe mostrar un puerto.
- **Falta de memoria (arena o `Failed to allocate tensor arena`):** parchea con `--arena 384605`.
- **Core alpha o RC:** usa una versión estable 3.3.x. Los scripts rechazan versiones con `alpha`, `rc` o `beta`.
- **No sube:** cierra el Monitor Serie del IDE (o cualquier programa que tenga el puerto) antes de subir.
- **Otra opción de PSRAM:** `PSRAM=disabled` (o `-Psram disabled`) cambia el FQBN. Para clasificar con
  esta cámara se necesita `opi`.
- **La placa no arranca con power bank:** el ejemplo de Edge Impulse tiene `while (!Serial);` en `setup`, así que la placa espera una conexión serie con la PC; alimentada desde un power bank no inicia hasta quitar esa línea (el parcheador no la quita).
- **El ZIP no es el esperado:** el parcheador avisa si no encuentra `examples/esp32/esp32_camera/esp32_camera.ino`.

## Clases del modelo

`salida_json.h` imprime en `probs` **todas** las etiquetas del modelo (no hay lista fija de cuatro),
así que agregar `metal` o `pulgar` no exige tocar el firmware. Las etiquetas salen tal cual: deben ser
minúsculas ASCII `[a-z0-9_]` (hasta 24 caracteres, de 2 a 16 clases) para cumplir `docs/CONTRATO.md`.
Edge Impulse permite otras, pero el dashboard rechaza esas líneas, así que hay que nombrar las clases
así desde el principio. El parcheador avisa si una clase del LED no cumple.
