# Manual de editor: reels

Reglas fijas del motor de reels. Valen para cualquier cliente del SaaS. Lo que cambia de un cliente a otro sale de su Kit, nunca de este manual:
- su **kit visual** (identidad visual): colores por uso (fondo, luz, panel, texto, acento), tipografías y su propio material;
- sus **preferencias de edición** (identidad visual): estilo de subtítulos, música y efectos de sonido sí o no, y su lista de «nunca hagas», que manda sobre el gusto del editor (nunca sobre este manual);
- su **voz** (Kit): si usa emoticonos (nunca, pocos o libre) y a qué ritmo habla.

El motor no sabe hacer nada que este manual no permita.

La pregunta de control es siempre la misma: **¿esto lo haría un editor profesional con criterio o parece una plantilla?**

## 0. Del bruto al reel

- **Lo pesado, por turno (obligatorio en el Mac del equipo).** Toda orden pesada (extraer fotogramas, Whisper, render de Remotion, ffmpeg) se lanza con `bash "$TURNO_PESADO" <orden…> (la ruta del script de turno del equipo, en la variable TURNO_PESADO)`: un solo turno en todo el equipo, espera a que el Mac esté tranquilo (carga < 4 y memoria libre ≥ 25 %) y lo lanza con nice 15 y QoS de segundo plano. Además, `MOTOR_REELS_HILOS=2` (ffmpeg -threads 2) y `MOTOR_REELS_CONCURRENCIA=2` (o 1). Un paso pesado a la vez y temporales borrados al acabar cada uno. La limpieza nocturna (23:45) borra fotogramas y temporales de más de un día y las versiones superadas de ENTREGA.

- El bruto puede durar 4-5 minutos, con repeticiones, pruebas y tomas falsas. El editor se queda con **la mejor toma de cada parte** y monta el reel entero.
- **El gancho**: normalmente es lo primero que se dice. Si en el bruto hay una frase mejor para abrir (más concreta, más sorprendente, con una cifra), se usa esa como gancho, aunque esté más adelante. Es la única parte que puede cambiar de sitio, y no se repite después.
- **Duración**: la que pida la idea bien contada. Son reels de valor: no tienen por qué ser cortos, pero cada segundo tiene que aportar. Se corta lo que se repite, lo que se va por las ramas y lo que no suma.

## 0 bis. Más de un reel de un bruto

Un bruto de 3-5 minutos suele tener más de un reel dentro. Hay que sacar todos los que se sostengan, para publicar más sin grabar más, pero **ninguno flojo ni repetido**:
- **Cada reel vale por sí solo**: su propio gancho (sacado de su tramo o de otra parte del bruto), una idea completa con su cierre y nada que dependa de otro reel («como os decía antes», «el segundo error es…» sin que se haya dicho el primero).
- **Formas típicas**:
  - el reel completo, más un reel por cada punto que se sostenga solo (3 consejos → 3 reels de un consejo);
  - dos ideas distintas dentro del mismo bruto.
- **Duración**: mínimo 25 s, con 30 o más como objetivo. Un trozo que no llega no es un reel.
- **Sin repetirse**: dos reels del mismo bruto no comparten más del 30 % de lo que se dice. El reel completo y los de un solo punto son la excepción, porque es la misma idea contada a dos escalas; aun así, el gancho de cada uno es distinto.
- Si el bruto solo da para uno, sale uno: calidad antes que cantidad.
- Antes de montar, el editor escribe el **mapa de reels**: cuántos salen, el gancho de cada uno, de qué parte del bruto sale y por qué se sostiene solo.

## 1. Vocabulario: efectos que explican, con ritmo

Un editor tiene una firma y la repite; la IA enseña todo su catálogo en cada vídeo. Los máximos son **por minuto de reel**.

| Recurso | Para qué | Máximo por minuto |
|---|---|---|
| **Efecto explicativo** (lista, cifra, comparación, proceso, gráfica; tipo After Effects) | Respaldar lo que se dice cuando hay pasos, números, un antes y un después, un proceso o una tendencia. Es el recurso de apoyo principal | 4 |
| **Titular detrás** (la tipografía de titular del kit, gigante, con la cabeza delante) | La idea central del gancho y, como mucho, otra más | 2 |
| **Tarjeta** (chat, ficha) | Cuando lo que se dice es un objeto: un mensaje, un nombre, un dato | 2 |
| **Imagen real** (foto o captura de lo que se nombra) | Solo en momentos puntuales en que enseñar la cosa convence más que cualquier efecto. Primero, el material del propio cliente | 2 |
| **Punch-in** (cambio de encuadre seco sobre la palabra fuerte) | El ritmo | cada 1,5-3 s |
| **Golpe de zoom** (acercamiento rápido dentro del plano, con un sonido sutil) | Remarcar la palabra más fuerte de una frase | 6 |
| **Icono de línea** (junto a la cabeza, con su palabra si la lleva) | Acompañar una idea concreta sin tapar nada: un plazo, una herramienta, un resultado | 4 |
| **Transición** (látigo, tiras) | Solo para cambiar de bloque, nunca dentro de una frase | 2 |
| **Quitar el fondo** | Gancho o momento clave | 2 |

- Un solo gráfico a la vez y, como mucho, un gráfico por plano.
- Entre un gráfico y el siguiente debe haber al menos 1 s de cara limpia.
- Cuando hay titular o efecto a pantalla partida o completa, no hay subtítulos: el gráfico ya cuenta lo que se dice.

### Tres composiciones, alternadas

Cada efecto va en una de estas tres composiciones. Se alternan según lo que pida el momento:

1. **Encima** (lo normal): la cara entera, tal cual, y el efecto apoyando en la zona libre (arriba o a la altura del pecho), sin tapar la cara.
2. **Partida**: cuando algo necesita explicación gráfica y el efecto necesita espacio. Arriba, el efecto; abajo, la persona **reencuadrada para que su cara quede centrada en su mitad**. No se baja el vídeo entero sin más.
3. **Completa**: el efecto ocupa toda la pantalla y la cara desaparece unos segundos mientras sigue la voz. Para el momento más gráfico del reel. Como mucho una por minuto.

Partida y completa **empiezan cuando entra su primer elemento**: lo que se dice antes va con la cara entera, nunca con el panel vacío esperando a que se diga.

### Centrado

Todo lo que va centrado (subtítulos, titulares, rótulos, tarjetas, barras de prompt, CTA) tiene el centro en **x=540**, con márgenes simétricos (`LADOS` en `remotion/src/zona.ts`). Con los márgenes de la zona segura (60 y 230) el centro caía en 455 y se veía torcido. Solo lo que va pegado a un lado usa la zona. `qa` lo mide en el render: ±2 px o no se entrega.

### Logos e iconos

Fuera, de momento, en el kit del cliente: los logos de apps (tachados o no) y los iconos «quedan súper cutres» (28/10/2026). El kit los pone a máximo 0 y `validar` da error si aparecen.

### Zona segura

Instagram tapa la cabecera, el pie con el texto y los botones de la derecha. En 1080×1920, **ningún texto** fuera de x 60-850 e y 230-1440 (los 230 px de la derecha, libres). Las cajas de cada pieza están en `zona_segura.json`; el motor las pinta y `validar.py` comprueba que ninguna se salga.

### Estilo propio del cliente (kit «estilo»)

Un cliente puede pedir un estilo de edición distinto del de este manual (por ejemplo, el de una cuenta de referencia). Va en el bloque `estilo` de su kit y manda sobre este manual en lo que diga; en lo demás, el manual sigue valiendo:
- `subtitulos: "limpio"`: blancos, pequeños, sin caja; también sobre pantallas, logos y sello.
- `lienzo` (un color) y `lienzoAcento`: la mitad de arriba de la pantalla partida es un lienzo liso. Las capturas van como tarjeta y los efectos, en tinta oscura con la fila activa en el acento.
- `logos` (una carpeta de PNG): el gráfico `logos` hace saltar los de las apps que se nombran alrededor de la cabeza.
- `sello` ({texto, cinta}): el gráfico `sello` presenta su serie.
- `musica` (un archivo con licencia): continua bajo la voz, a -30 LUFS.
- `montaje`: `gancho: "libre"` (sin titular obligatorio), `corte` (segundos por plano) y `maximos` (sus propios máximos por minuto).
- **Formato raw** (kit del cliente desde el 29/10/2026): cortes limpios, letras sencillas y alguna animación por detrás, y ya. `maximos` a 0 para `efecto`, `tarjeta`, `imagen`, `partida`, `mosaico`, `esquinas` (portada de revista), `rotulo`, `prompt`, `terminal`, `cta`, `logos`, `icono` y `sello`: `validar` los bloquea. Quedan: subtítulos limpios en la sans, el gancho encima de la cabeza en la sans (dos líneas, sin cursiva ni pastilla), 2-3 recortes por minuto con la luz azul moviéndose detrás (2-3 s, nunca en cada frase) y la palabra del CTA como texto sencillo. Siguen las reglas fijas: cero repeticiones, centrado medido, sin logos y música a -38 LUFS.

## 2. Nada literal y nada de plantilla

- El gráfico subraya **la idea**, no repite la frase. Una palabra o, como mucho, tres por línea.
- Si el gráfico solo diría lo mismo que el subtítulo, ese momento no lleva gráfico; lleva un punch-in.
- **Emoticonos, los que diga la voz del cliente**: «nunca» (ninguno en ningún texto), «pocos» (2 por reel como mucho) o «libre». Sin dato, ninguno. Los iconos, si hacen falta, se dibujan con líneas en el estilo del kit.
- **Seis palabras como mucho por rótulo** (titular con su antetítulo, título y elementos de un efecto, etiquetas). El mensaje de un chat y el pie de una foto no son rótulos.

## 2 bis. Imágenes reales, solo en momentos puntuales

- Una imagen real va cuando enseñar la cosa convence más que cualquier efecto: la captura de un resultado, la web de la que se habla, la foto de una persona o un lugar concretos. **Pocas**: el apoyo normal son los efectos.
- **Solo imágenes reales e identificables**: nada de bancos de imágenes genéricos, nada generado con IA y nada de memes. Si no hay una imagen exacta de lo que se dice, no va ninguna.
- De dónde salen, por este orden:
  1. el material del propio cliente (fotos y capturas de su Kit o las que añade a ese reel);
  2. el artículo exacto de Wikipedia (licencia libre, con el autor y la licencia en el pie);
  3. la captura de la web que se nombra.

  **Nunca de Google Imágenes**: tienen dueño y los reels se usan en anuncios.
- En reels que vayan a anuncios, ninguna foto de personas conocidas: puede parecer que avalan el producto.

- **Cuando nombra mucho contenido** («mil vídeos de YouTube», «todos los reels virales»): capturas reales a pantalla completa por detrás de él, no pantalla partida (cliente, 28/10/2026). Plano `recorte` abierto (zoom 1,0) con `fondo: {"mosaico": [...]}`: un mosaico denso (cinco columnas) con muchas miniaturas distintas, unas 40, sacadas de una búsqueda real. Se tienen que ver muchos ejemplos, no dos o tres. La pantalla partida sigue para enseñar una cosa concreta que hay que leer.

## 3. Movimiento

- **El texto entra como lo pondría un editor**: aparece de golpe al ritmo de la voz y se asienta con un leve ajuste de escala. La palabra entera, nunca letra a letra; nada de subir desde una línea ni de líneas que se dibujan, ni de «desenfoque + subida». Lo demasiado perfecto delata la plantilla.
- Los números **cuentan**; las líneas aparecen con su elemento.
- **Anticipación**: todo entra 2 fotogramas antes de la palabra, nunca en el mismo fotograma.
- **Los gráficos no se despiden**: desaparecen con el corte del plano. Solo hay salida animada si el plano sigue.
- **Cámara viva**: todo plano lleva una deriva de cámara en mano muy leve (±4 px, ±0,15°). Una imagen clavada delata el ordenador.
- El desenfoque solo aparece por velocidad (látigo, tiras) y es direccional, como el de una cámara real.
- La sacudida es un recurso de impacto: como mucho una por minuto.

## 4. Imagen

- Nada de etalonaje: solo la conversión HDR → SDR del iPhone.
- Grano muy fino en todo el reel (apenas perceptible): une la persona recortada, los gráficos y el vídeo, sin que se note como efecto.
- **Calidad máxima**: fotogramas extraídos casi sin pérdida, render sin compresión visible. Nada de parpadeos: el render espera a que la silueta de cada fotograma esté cargada.
- La persona recortada lleva sombra suave sobre el fondo; si no, parece una pegatina.
- **Al quitar el fondo, nunca un color liso**: un fondo animado en los colores del kit (luz que se mueve, rejilla en perspectiva) o una foto del propio cliente con un acercamiento lento.
- **El color de fondo del kit nunca entra ni sale en seco**: se abre desde detrás de la cabeza y se come la habitación, o se cierra hacia la cabeza y la descubre. Úsalo con medida: no todos los reels abren sobre él.
- **Pantalla partida y completa, sobre el propio vídeo desenfocado** y oscurecido, no sobre un panel de color: así no parecen diapositivas. Los efectos encima llevan detrás un velo difuso en el color de fondo del kit (cristal desenfocado que se funde por los bordes, nunca una caja): sin él, el texto se pierde entre las manos y la ropa.

## 5. Corte

- Se quitan silencios, muletillas, repeticiones y tomas falsas. El orden del discurso no se toca, salvo el gancho (sección 0).
- **Cero repeticiones, siempre** (cliente, 28/10/2026: «esto no puede pasar nunca, en ningún vídeo»). Se trabaja con la transcripción palabra a palabra y se corta toda palabra dicha dos veces, arranque en falso, frase reempezada y muletilla, también en la junta entre dos tramos («…es esta. | Es dejar…»: el segundo tramo empieza en «dejar»). Los cortes se ajustan con la energía del audio, no con el tiempo de Whisper (adelanta hasta 0,4 s). `validar` lo comprueba con la transcripción del bruto y da error; `qa` vuelve a transcribir el render, en literal, y sin «Repeticiones: ninguna» no se entrega. Ojo: la transcripción del bruto pega las retomas («es… es dejar de» salió como «es dejar de»). Antes de montar, cada tramo elegido se vuelve a transcribir en literal (Whisper con un ejemplo de muletillas en el prompt) y el corte se pone en el valle de energía entre la retoma y la frase buena.
- El cambio de encuadre va sobre la palabra fuerte o en la respiración, nunca a mitad de palabra.
- Todo silencio de más de 0,3 s se corta, también dentro de un plano, y el corte se tapa cambiando el encuadre (punch-in). Un salto sin cambio de encuadre se nota.
- **Ritmo de la voz**: si, ya sin silencios, va a menos de 3,3 palabras por segundo, todo el reel va a x1,1 (imagen, voz y efectos, sin cambiar el tono). Más de x1,2 nunca: se nota.
- Hay que alternar real ↔ recorte, abierto ↔ cerrado y las tres composiciones: dos planos seguidos iguales no son un corte, son un salto.
- El primer fotograma ya tiene que enseñar el gancho (texto visible): es la portada en el feed. Si el kit lo pide (`estilo.ganchoEncima`, el del cliente), el texto del gancho va **encima de la cabeza**, entero y delante, con la persona bajada hasta quedar justo debajo; nunca detrás.
- **El texto del gancho tiene que enganchar por sí solo** (cliente, 28/10/2026: «no puede ser solo "lo malo"; en todos los reels tenemos que generar engagement con ese título»). Nunca una palabra que resume («TAN MALO»): es un titular con tensión que habla al que mira, en dos líneas con el diseño del reel. Arriba, en sans gruesa y gigante, a quién o a qué afecta (1-2 palabras, mejor con «tu»: «TU IA», «TUS REELS», «TU WEB»). Debajo, en cursiva serif sobre una pastilla del acento, el giro o el problema («escribe fatal.», «no venden.», «huele a IA.»). Sale de lo que dice en el gancho, sin prometer nada que el vídeo no cuente. En el montaje: titular `sans` + `cursiva`. **Mejor aún: que prometa el destino del reel y lo identifique** (lo que se consigue al final, con la herramienta o el tema del vídeo): «CLAUDE / escribiendo contenido de 10.». Corto. Nunca fórmulas genéricas («así lo arreglas», «te lo explico»). El titular del gancho puede ir sobre el vídeo real (en la pared, por detrás de la cabeza) o sobre el color de fondo del kit; hay que alternar. El titular del gancho está entero desde el fotograma 0.

## 6. Subtítulos

- 2-3 palabras; se cambia de grupo en seco, sin animación.
- La palabra que se está diciendo va en el color de texto y las que faltan, apagadas.
- Van a la altura del pecho, nunca encima de la cara ni de un efecto.

## 7. Sonido

- Voz a -14 LUFS con pico máximo de -1,5 dBTP.
- Efectos de sonido solo en los remates: entrada de un efecto, transición y titular. Como máximo, uno cada 3 s y siempre por debajo de la voz.
- Música, cuando haya biblioteca con licencia: por debajo de la voz (-20 dB) y cortada en el último fotograma.

## 8. Control de calidad antes de entregar

1. Hoja de contactos a 2 fps: ¿hay más de un gráfico a la vez? ¿Dos planos seguidos iguales? ¿Se alternan las composiciones?
2. Fotograma a fotograma de cada transición y de cada pantalla partida o completa: sin fotogramas negros, sin saltos de recorte y con la cara centrada en su mitad.
3. Contar recursos frente a los máximos por minuto.
4. Leer los gráficos sin audio: ¿alguno repite la frase literal? ¿Hay emoticonos que su voz no use? ¿Algún texto fuera de la zona segura?
5. Cada imagen real: ¿es exactamente lo que se nombra?
6. **Repeticiones**: la transcripción literal del render (`qa/transcripcion_render.json`) no tiene ninguna palabra repetida seguida ni arranques en falso. Se lee entera además del informe.
7. **Centrado medido**: subtítulos, pastillas, tarjetas y titulares blancos con el centro a ±2 px de x=540 en todos los fotogramas muestreados.
8. Volumen: -14 LUFS y pico por debajo de -1 dB.
Si `qa` dice «Entregable: NO», no se entrega.
6. Volumen: -14 LUFS ±1.
