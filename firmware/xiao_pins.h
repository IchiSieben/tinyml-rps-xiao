#ifndef XIAO_PINS_H
#define XIAO_PINS_H

// Pines de camara de la XIAO ESP32S3 Sense (OV2640/OV5640), con los nombres del ejemplo
// esp32_camera de Edge Impulse. Fuente: wiki de Seeed
// https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39

#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

// LED de usuario (naranja) en GPIO21. La wiki de Seeed indica que se apaga con nivel alto y se
// enciende con nivel bajo, es decir, es activo en bajo.
#define LED_GPIO          21
#define LED_ACTIVO_BAJO   1

#endif
