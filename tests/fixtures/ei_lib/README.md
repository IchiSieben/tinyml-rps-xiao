# Fixture de libreria Edge Impulse

`rps_inferencing/examples/esp32/esp32_camera/esp32_camera.ino` es el ejemplo real de Edge Impulse
(licencia MIT, cabecera original incluida), copiado de una libreria exportada publica. Unico cambio:
el `#include <pico_detect_inferencing.h>` pasa a `<rps_inferencing.h>`.

Origen: https://github.com/dht3218/esp32pico_watch/blob/7581fd1986372106a9e1ad8e42318bfb2a1ed70e/libraries/pico_detect_inferencing/examples/esp32/esp32_camera/esp32_camera.ino

El resto (`library.properties`, `src/`) es un esqueleto minimo; los defines de arena replican el
formato real de `tflite_learn_*.h` (ejemplo: https://github.com/eslamabdelmogood/Green-Box-Model/blob/main/tflite-model/tflite_learn_825137_18.h)
y `model_metadata.h` (`EI_CLASSIFIER_TFLITE_LARGEST_ARENA_SIZE`). El test arma el ZIP en tiempo de ejecucion.
