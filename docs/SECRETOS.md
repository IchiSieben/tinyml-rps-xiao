# Secretos del dashboard

**Aviso de spoiler.** Este archivo cuenta todo lo escondido en el juego. Si quieres descubrirlo
jugando, cierra esta página.

| Secreto | Cómo se activa | Qué pasa |
|---|---|---|
| AURA | Ganar sube el medidor (+15, y +5 más con confianza de 85 % o más); empatar da +2; perder resta 10 | Al llegar a 100: pantalla "FULL AURA" con destello y confeti; luego el medidor baja a 50. |
| Racha de 3 | Ganar tres partidas seguidas | Tema arcade (negro y neón). También se alterna a mano con la tecla A. |
| Metal | La clase `metal` (🤘) sostenida 1 segundo, si el modelo la tiene | Mensaje gigante "ROCK ON 🤘", tema arcade durante 5 s y un riff de tres notas. |
| Pulgar | La clase `pulgar` (👍) sostenida 1 segundo | Sello "APROBADO ✅" con animación. |
| Clase desconocida | Cualquier otra etiqueta que traiga el modelo | Se muestra con su nombre y un emoji genérico (❔); no rompe nada. |
| Konami | Teclado: arriba, arriba, abajo, abajo, izquierda, derecha, izquierda, derecha, B, A | "Placa invencible": la placa siempre gana durante 3 partidas, con un aviso cómico. |
| Consuelo | 5 derrotas seguidas | Un mensaje de ánimo al azar, en español peruano. |

## Cómo probarlos sin placa

El simulador acepta un guion con la secuencia de clases:

```bash
python dashboard/servidor.py --simular --guion "piedra:3,metal:3,pulgar:3,lagarto:3" --guion-bucle
```

Abre `http://127.0.0.1:5000/?rapido=1` para pausas cortas. En la consola del navegador,
`RPS.debug.fijarAura(95)` y `RPS.debug.jugar("piedra", "tijera")` fuerzan un FULL AURA al instante.
`metal` y `pulgar` solo se reconocen con una placa cuyo modelo las tenga; cómo conseguirlas está en
la sección "Gestos extra" de [PENDIENTES.md](PENDIENTES.md).
