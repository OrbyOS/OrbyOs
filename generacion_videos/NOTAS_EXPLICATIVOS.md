# Explicativos de @orbyos: reglas fijas del motor

Lo que hace siempre `radar/agentes/generacion.py`, sin opción para quitarlo. Cada regla lleva el commit que la puso.

## Voz
- El clon profesional de voz del cliente (su nombre en `ELEVENLABS_VOZ_NOMBRE`) con el modelo `eleven_v4_exp`, a velocidad 1.0. Se busca por nombre en la cuenta. Cada escena se genera con el texto de la anterior y de la siguiente, para que la entonación no se reinicie. (cedab37, 7cacdbf)
- Ritmo de 182-192 palabras por minuto. Primero se estiran o encogen las pausas, de ×0,7 a ×1,3. Si no basta, la voz se acelera como mucho un 6 % (un guion puede permitir más con `"acelerar_max"`) o se frena como mucho un 5 %. Ninguna pausa insertada pasa de 0,55 s. (402f2e3, d961ef2, b1c7c24)
- **Sin cortes secos** (el cliente, 29/10/2026), en 2945d20:
  - Las pausas no se cortan en la marca de tiempo de cada palabra, que a veces llega tarde y se come el principio de la palabra. Se cortan en el punto más callado de la onda entre 250 ms antes y 50 ms después de la marca.
  - Cada trozo de voz lleva un fundido de entrada de 25 ms y uno de salida de 12 ms.
  - Debajo de la voz no va nada (silencio digital): el ruido de sala de -50 dB se oía y el cliente lo quitó (29/10). En su lugar, cada arranque de golpe de la voz (de menos de -58 dB a más de -42 dB en 5 ms) recibe un ataque de 35 ms, y el corte de cada pausa va 20 ms más dentro del silencio, para no comerse una consonante fuerte. (06174b0)
  - Puerta de ruido a -62 dB (ventanas de 10 ms, se abre 10 ms antes y se cierra 10 ms después, con 5 ms de suavizado): quita el siseo que deja el cambio de tempo en las pausas, que quedan por debajo de -75 dB. Los primeros 60 ms de la voz entran con un fundido, para que el vídeo no arranque de golpe. (commit de esta nota)
- **Control de calidad del sonido** (29/10/2026), en el commit de estas notas: después de cada render se buscan arranques secos, es decir, pasos de menos de -55 dB a más de -28 dB en 5 ms. Con uno solo, el vídeo se renombra a `_FALLIDO` y el montaje da error: no se entrega. El mismo detector suelto: `.venv/bin/python generacion_videos/herramientas/rehacer_audio.py --comprobar vídeo.mp4`.
- Para arreglar solo el sonido de un vídeo ya montado, sin render (la imagen se copia tal cual): `generacion_videos/herramientas/rehacer_audio.py guion.json origen.mp4 salida.mp4`.

## Imagen (diseño `"estilo": {"diseno": "cazzap"}`)
- Todo centrado en x=540: texto, planos y cámara. (15a07db)
- El subtítulo de arriba va en dos líneas y sale entero desde el principio, con lo que aún no se ha dicho al 35 %. La palabra clave va seleccionada. Ninguna línea acaba en artículo, preposición o conjunción. (b52b68a, 729cf41)
- Sin fundidos entre planos: el que sale desaparece en el fotograma en que entra el siguiente. El cierre entra en seco. (e675c34, 3b1f558)
- Las webs grabadas van en una tarjeta debajo del subtítulo (`"marco": true`), enteras. Nada por debajo de la caja del subtítulo. (7254e8a)
- Una visual por frase: grabaciones reales de la app y de webs, clips de Pixabay (con el OK del cliente, sin caras ni logos) y las escenas papel, moneda, multiplica, cadena, oficina y mapa. Nada de logos de marcas ni pantallas que imiten apps.

## Montaje
- Siempre con `generacion_videos/herramientas/montar.sh <números>`, que pasa por el turno pesado único del equipo (`Edicion/herramientas/turno_pesado.sh`), y solo cuando la dirección general da turno. (13ea871)
