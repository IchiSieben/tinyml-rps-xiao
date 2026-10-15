#ifndef SALIDA_JSON_H
#define SALIDA_JSON_H

// Emite una linea JSON por inferencia segun docs/CONTRATO.md. Requiere que el sketch ya haya
// incluido la libreria de Edge Impulse (ei_impulse_result_t, ei_classifier_inferencing_categories).
#include <Arduino.h>
#include <string.h>
#include "xiao_pins.h"

static const char *SJ_CLASES[4] = {"piedra", "papel", "tijera", "nada"};

// Probabilidad de la clase `nombre`, buscada por etiqueta y nunca por posicion.
static inline float sj_prob(const ei_impulse_result_t &r, const char *nombre) {
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        if (strcmp(r.classification[i].label, nombre) == 0) return r.classification[i].value;
    }
    return 0.0f;
}

// Clase ganadora (entre las etiquetas del modelo) y su confianza.
static inline void sj_ganadora(const ei_impulse_result_t &r, const char **clase, float *conf) {
    size_t mejor = 0;
    for (size_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        if (r.classification[i].value > r.classification[mejor].value) mejor = i;
    }
    *clase = ei_classifier_inferencing_categories[mejor];
    *conf = r.classification[mejor].value;
}

// Enciende el LED si `clase` == `clase_led` y conf >= umbral. Devuelve el estado logico.
static inline bool actualizar_led(const char *clase, float conf, const char *clase_led, float umbral) {
    static bool iniciado = false;
    if (!iniciado) {
        pinMode(LED_GPIO, OUTPUT);
        iniciado = true;
    }
    bool encendido = clase_led != nullptr && clase_led[0] != '\0' &&
                     strcmp(clase, clase_led) == 0 && conf >= umbral;
#if LED_ACTIVO_BAJO
    digitalWrite(LED_GPIO, encendido ? LOW : HIGH);
#else
    digitalWrite(LED_GPIO, encendido ? HIGH : LOW);
#endif
    return encendido;
}

static inline void emitir_json(const ei_impulse_result_t &r, uint32_t n, float umbral, bool led) {
    const char *clase;
    float conf;
    sj_ganadora(r, &clase, &conf);
    Serial.printf(
        "{\"v\":1,\"fuente\":\"xiao\",\"n\":%lu,\"t_ms\":%lu,\"clase\":\"%s\",\"confianza\":%.4f,"
        "\"probs\":{\"piedra\":%.4f,\"papel\":%.4f,\"tijera\":%.4f,\"nada\":%.4f},"
        "\"lat_ms\":{\"dsp\":%d,\"inf\":%d},\"led\":%s,\"umbral\":%.4f}\n",
        (unsigned long)n, (unsigned long)millis(), clase, conf,
        sj_prob(r, "piedra"), sj_prob(r, "papel"), sj_prob(r, "tijera"), sj_prob(r, "nada"),
        (int)r.timing.dsp, (int)r.timing.classification, led ? "true" : "false", umbral);
}

#endif
