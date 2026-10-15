# Cómo tomar las fotos (20 minutos, con el celular)

Carpetas: `fotos_rps/piedra`, `fotos_rps/papel`, `fotos_rps/tijera`, `fotos_rps/nada`. Entre 60 y 80 fotos por clase. Luego `python pipeline/preparar_dataset.py --origen fotos_rps`.

## Lo que importa

- **Igual a como vas a mostrarlo en clase:** mano a 30-60 cm de la cámara, palma hacia ella, gesto centrado.
- **Variar lo que va a variar en el laboratorio:** 3 fondos distintos (pared, mesa, ropa), luz de ventana y luz de foco, ambas manos, ligera rotación de la muñeca, distancia cerca y lejos.
- **La clase `nada` es la más importante:** escritorio vacío, pared, tu cara sin manos, el brazo sin gesto, objetos sueltos. Sin ella el modelo "ve" tijeras en todo.
- Ráfaga del celular o video y extraer frames: `ffmpeg -i video.mp4 -vf fps=3 piedra/%03d.jpg`.

## Lo que no hace falta

- Resolución alta: todo se reduce a 96x96. Un celular cualquiera sobra.
- Fotos perfectas: un poco de desenfoque y mala luz ayudan a generalizar.

## Regla de oro

Las fotos de prueba (20 %) no se tocan ni se miran: el script las separa solo. Si el modelo acierta en esas, va a acertar en clase. Si solo acierta en las de entrenamiento, no sabemos nada todavía.
