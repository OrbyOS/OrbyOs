# Manual de motion graphics

Reglas fijas del motor de `generacion_videos`. Valen para cualquier negocio del SaaS. Lo que cambia de un negocio a otro sale de su Kit, nunca de este manual:
- su **identidad visual**: paleta (el primer color es el principal), tipografías (la de titulares manda), logo y su lista de «nunca hagas», que manda sobre el gusto del editor (nunca sobre este manual);
- su **voz**: si usa emoticonos (por defecto, ninguno) y su ritmo;
- su **inventario de pruebas**: la única fuente de cifras. Una cifra sin fuente no sale en pantalla.

La pregunta de control es siempre la misma: **¿esto lo haría un estudio de motion con criterio (nivel Apple) o parece una plantilla de Canva?**

## 1. Las reglas de la casa

1. **Contención. Texto plano por defecto.** Un texto en pantalla es texto limpio, bien espaciado, con un **filete de acento** (una línea fina en el color principal que se dibuja con él) y, detrás, un **velo difuso** en el color de fondo de la marca (cristal desenfocado que se funde por los bordes). Así se lee sobre cualquier cosa sin que haya caja.
2. **Nada de cajas, píldoras ni baldosas de icono.** Ni rótulos en recuadro, ni etiquetas en píldora, ni iconos dentro de un cuadrado o un círculo relleno, ni sellos de goma. Las marcas (visto, cruz) son de línea. Excepción: lo que **es** un objeto real se dibuja como ese objeto (un chat, un móvil, la página de una web, una grabación de la app).
3. **Un efecto a la vez.** En cada momento pasa una sola cosa: entra un elemento, o cuenta una cifra, o se mueve la cámara. Nada de destellos, sacudidas, brillos que laten ni luces que parpadean encima de una entrada.
4. **Nada fijo en pantalla.** Ni logo en una esquina, ni marco, ni barra de progreso, ni un título que se queda todo el vídeo. Lo que entra, sale cuando deja de hacer falta.
5. **Sin etalonaje** en el vídeo de la persona ni en las grabaciones de pantalla: se ven como son. El único tratamiento de color es el de los vídeos de banco, y es para igualarlos a la marca (sección 4).
6. **Cero emoticonos** salvo que la voz del Kit diga otra cosa. Si hace falta un icono, se dibuja con líneas.
7. **Lo que se nombra se apoya con lo real.** Si se habla de la app, se graba la app (con un negocio de prueba). Si se nombra algo concreto (una web, un sitio, un producto), su imagen real. Nada generado con IA ni de bancos de imágenes de catálogo.
8. **Nada literal.** El gráfico subraya la idea, no repite la frase. Si solo diría lo mismo que el subtítulo, ese momento no lleva gráfico.
9. **Seis palabras como mucho** por rótulo o etiqueta. Un mensaje de chat no es un rótulo.
10. **Zona segura de Instagram** (1080×1920): ningún texto fuera de x 60-850 e y 230-1440. El texto se centra en x 470 y lo dibujado en x 510.

## 2. Tiempos (el movimiento)

| Qué | Cómo y cuánto |
|---|---|
| **Entrada de cualquier cosa** | Muelle muy amortiguado (`pop`): se asienta en unos 8 fotogramas, sin rebote visible. Aparece y se asienta (escala 1,06 → 1 o 14-16 px de recorrido). Nunca cae, gira, se aplasta ni rebota |
| **Cuándo entra** | **2 fotogramas antes de su palabra** (`ANTICIPA`): ni a la vez ni tarde. Cada cosa en su `^palabra`; sin marca, repartidas en la primera parte del plano |
| **Cambio de plano** | 7 fotogramas: el nuevo entra con un fundido y una escala de 1,08 a 1 con un desenfoque que se va (o sube 90 px). El anterior se va en 5 fotogramas a la vez. Nada de barridos sesgados ni giros |
| **Filete** | Se dibuja en 6-8 fotogramas, con el texto |
| **Rótulo** | 6-8 fotogramas para entrar; aguanta lo que dura su frase; sale en 5 |
| **Palabra grande** | 7 fotogramas (escala 1,06 → 1) y después respira muy lento |
| **Cifra que cuenta** | Llega a su valor en el 60 % del plano (entre 12 y 40 fotogramas) con una curva que frena al final, y se queda. Sin golpe al llegar. Números tabulares |
| **Lista** | Cada punto en su palabra; la marca se dibuja en 8 fotogramas; lo tachado se apaga |
| **Cámara** | Solo un acercamiento lento de un 3,5 % a lo largo de cada plano. Sin sacudidas |
| **Subtítulos** | Grupos de hasta 3 palabras; cada palabra aparece en 0,12 s; la de énfasis, en el color de resalte y un 6 % más grande, sin girar ni caja |
| **Duración de un plano** | Entre 0,8 s (menos no se lee) y 7 s (más se queda quieto). Un plano que no tiene nada que enseñar hasta su primera palabra no entra vacío: el anterior aguanta, como mucho 2,5 s |
| **A cámara: capas** | Una capa (pantalla o plano) entra en 5 fotogramas y cubre su frase entera. Entre dos capas, al menos 1 s de cara, o se juntan en una |
| **Pantalla grabada** | El encuadre va de un rectángulo a otro con curva suave de entrada y salida. El cursor llega en 0,6 s; el clic, un anillo de 0,4 s |
| **Sonido** | Un barrido suave en cada cambio de plano y un tic o pop en cada entrada, siempre por debajo de la voz. Vídeo final a -14 LUFS y -1,5 dBTP |

## 3. Catálogo de piezas

Cada pieza es un `ve` del guion (explicativo) o de una frase del montaje (a cámara). Campos entre paréntesis.

**Texto**
- **Titular de portada** (`titulo`: texto, resalte, insignia): visible desde el fotograma 0, texto plano grande con la parte resaltada en el color de resalte y la insignia como filete debajo.
- **Rótulo de bloque** (`rotulo` de la escena, o de la frase a cámara): «1 · El equipo», «Trampa 2», «Comenta IDEAS». Arriba (y 250-262) o encima de los subtítulos.
- **Palabra** (`palabra`: texto, sub, malo): una idea en una palabra («NO.») con una línea debajo.
- **Frase** (`frase`: texto, autor, tachar): una cita; tachada en su palabra si es lo que se desmonta.
- **Sello** (campo `sello` de cualquier plano): ya no es un sello de goma; es la palabra en el color de «malo» con su filete, a mitad del plano o en su golpe.

**Cifras**
- **Cifra** (`cifra`: valor, desde, prefijo, sufijo, etiqueta, tope, malo, decimales): cuenta dentro de un anillo que se llena.
- **Suma** (`suma`: items [{texto, valor}], desde, sufijo, tope): cada partida entra en su palabra y el total sube con ella.
- **Gráfica** (`grafica`: modo linea|barras, valores, etiquetas, titulo, resalte, malo): sin tarjeta, sobre el velo.
- **Reloj** (`reloj`: vueltas, texto) y **calendario** (`calendario`: dias, marcados, marca check|cruz, notas).

**Listas y comparaciones**
- **Lista** (`lista`: items, marca check|cruz|num): texto plano con marca de línea o número en el color de acento.
- **Versus** (`versus`: izq y der {titulo, items, robot|objeto, nota}, ganador): dos columnas; la que pierde se apaga.
- **Flujo** (`flujo`: pasos [{quien, texto}]): quién hace qué, con un filete a la izquierda del paso activo.

**Objetos reales** (los únicos que llevan su forma: son lo que se enseña)
- **Chat** (`chat`: mensajes [{de tu|ellos, texto, hora}]), **móvil** (`movil`: modo vistas|mensajes|perfil|comentarios…), **página de venta** (`venta`: modo precio|cuenta|bonos…).
- **Objetos** (`objetos`: objetos [nombres de `ilustraciones.tsx`], textos): ilustraciones de línea con su etiqueta en texto plano.
- **Robot / equipo** (`robot`, `equipo`): los muñecos de los agentes de Orby. Solo para la cuenta de Orby: en un negocio cualquiera, su logo o su material.

**Material real**
- **Pantalla** (`pantalla`: fuente, medidas, ancho, alto, desde, encuadres [{t, caja, aire} | {t, x, y, w}], cursor [{t, x, y, clic}]): una grabación de la app con zoom a la caja medida al grabar. Se graba con `grabar_pantalla.mjs` en modo `virtual` (reloj falso: sale fluida aunque la página sea pesada) a 540×960 CSS con escala 4 (2160×3840); en el montaje, `ancho` 540 y `alto` 960 para que cuadren las cajas.
- **Recurso** (`recurso`: pixabay id, desde, segundos, oscurecer, texto): un vídeo de banco a pantalla completa con acercamiento lento. Solo como ambiente, 1,5-3 s, y tras revisar la hoja de candidatos de `generacion_banco.hoja` (fuera lo de catálogo: sonrisas a cámara, apretones de manos, hologramas). Se trata con el color de la marca (apagado, grano y viñeta suaves) para que parezca del mismo vídeo.
- **Imagen real**: la captura o la foto exacta de lo que se nombra. Primero, el material del propio negocio; después, la web que se nombra. Nunca de Google Imágenes.

**Solo a cámara** (`ConCara.tsx`)
- **Palabra clave junto a la cara** (`clave`, `lugar` izq|der|arriba en la frase) y **reencuadres** (automáticos; `zoom` en la frase para forzar uno).
- **Imagen real** (capa `imagen`: fuente, ancho, alto, encuadres): una captura con acercamiento.
- **Copias** (`copias`: texto, n): la misma respuesta genérica, multiplicada.
- **Transcripción** (`transcripcion`: quien, titulo, texto con *frases buenas*): las frases se iluminan una a una.
- **Partir** (`partir`: titulo, ganchos): una grabación larga que se corta en varios reels con su gancho.
- **Grabando** (capa `{"tipo": "encima", "plano": {"tipo": "grabando", "segundos": 300}}`): REC y contador encima de la persona, sin taparle la cara.

**Cierre** (`cierre`: palabra, enlace, texto, web): el logo de la marca (o el muñeco de Orby en su cuenta) y **una sola** cosa que hacer en texto grande: «Comenta PALABRA» o «Enlace en el perfil».

## 4. Imagen

- Fondo de los planos: degradado del color de fondo de la marca con dos luces suaves que se mueven muy despacio, una rejilla tenue y partículas apenas visibles. Nunca un color liso.
- Vídeos de banco: recorte a vertical y tratamiento de la marca (color apagado y hacia el tono de la marca, grano y viñeta suaves). Es la única corrección de color permitida.
- Calidad: grabaciones de pantalla a 2160×3840 para que el zoom no pixele; render sin compresión visible.

## 5. Vídeo a cámara (lo principal)

Reels de 30-60 s con la persona hablando. Referencias de estilo que marcan el nivel:
- **El reel de Meta Ads** (referencia del cliente): texto **sin borde ni caja**, efectos de sonido **solo en los remates**, imagen **sin etalonar**.
- **El gancho de Rodri Yenom** (referencia del cliente): **reencuadre cada 1,5-2 s** en el gancho, **palabras clave junto a la cara**, **pruebas reales** en pantalla.
- **El reel de ponceeric «editado por Claude»** (instagram.com/reel/De_2u8gjCbw, referencia del cliente): **pantalla dividida** con la visual arriba (interfaces que se animan con lo que dice: los pasos del proceso, etiquetas, un editor, un chat) y la cara abajo, los subtítulos en la costura, alternando con la cara entera. Se toma la estructura, no su aspecto: sus pastillas y cajas no van; todo se pasa al kit de la marca.

**Cómo se combina con la persona**
1. **La cara manda.** Nada la tapa salvo una capa a pantalla completa durante su frase. El título va **centrado encima de la cabeza** (y 250-470); al lado de la cara solo si el montaje lo pide con `"lugar"` y cabe sin tocarla. Nunca sobre la boca ni los ojos.
2. **Reencuadres secos** (punch-ins): en el gancho (los 6 primeros segundos), cada ~1,7 s en el principio de una palabra; después, uno al empezar cada frase. Escalas alternas 1,0 → 1,18 → 1,08, centradas en la cara (`"cara": {"x", "y"}` del montaje). Corte seco, como un editor: sin zoom animado.
3. **Título del reel** (`"clave"` en la frase, 1-3 palabras): aparece 2 fotogramas antes de que la diga, se asienta y se va con su frase (al menos 1,2 s). Con la **tipografía de titular y el color de texto de la marca** (una serif va en caja normal; una de palo, en mayúsculas) y sombra difusa. La **última palabra en cursiva y en el acento** («Negocio de *IA*»; con `*palabra*` se elige otra) y, en el del gancho, un **trazo fino del acento que se dibuja debajo**; `"ante"` añade un antetítulo pequeño. Lo cambia `"titulo"` en el kit o el montaje (`{"cursiva": false, "subraya_gancho": false}`). Mientras está en pantalla, un velo muy leve oscurece en degradado la parte de arriba (o su lado), sin bordes, para que se lea sobre un techo o una pared clara: contraste de 4,5:1 o más con lo que tiene detrás (lo mide la revisión). Como mucho una por frase; no en todas.
4. **Material real cuando nombra algo**: una herramienta o la app → su **pantalla grabada** (`"ve": {"tipo": "pantalla", ...}`); un dato, una web, una noticia → su **captura** (`"ve": {"tipo": "imagen", "fuente", "ancho", "alto", "encuadres"}`) con un acercamiento al trozo que importa. La captura es la prueba: nunca una imagen genérica.
5. **Pantalla dividida** (`"dividida": true` en la capa; lo principal para acompañar lo que dice): la visual arriba (y 0-960) y la cara abajo, recolocada con la cara centrada; los subtítulos suben a la costura; una línea fina del acento marca la costura. Entra y sale con corte seco. Mientras está, no hay título encima de la cabeza (no hay cabeza arriba). Arriba vale cualquier pieza del catálogo, una pantalla grabada o una captura (en pequeño, como un móvil), y las piezas hechas para la mitad:
   - **Tachar** (`tachar`: items, golpes, marca `cruz`, titulo, queda): la lista en la serif de la marca, centrada; cada línea entra en su golpe y el trazo del acento la tacha y la apaga; `queda` es la línea que sobrevive, en cursiva y en el acento; `titulo`, una línea pequeña encima con palabras de la frase, visible desde el primer fotograma.
   - **Pasos** (`"pasos": [...], "paso": n` en la capa): los pasos del proceso que cuenta, arriba del todo, en texto plano y el actual en el acento con su filete. Es el hilo entre varias divididas del mismo reel.
   Reglas: la mitad de arriba **nunca espera vacía** (algo en pantalla en el primer fotograma); la visual **explica** lo que dice, no lo repite; con `"ve": "sigue"` en la frase siguiente, la misma visual continúa (una lista que se completa). Fondo: el de la marca casi plano con rejilla fina; nada de pastillas, cajas ni iconos en baldosa.
   **Lienzo** (`"fondo": "lienzo"` en la dividida, con `"alto": 0.46`): la interfaz limpia sobre blanco, sin línea de costura (estilo de los creadores de IA tipo @aiwithremy). Piezas, todas en `generacion_videos/remotion/src/lienzo.tsx` y con los colores del kit (`lienzo`, `interfaz`, `marcador`, `notas`):
   - **Carpetas** (`carpetas`: titulo, items, marca, etiqueta, golpes, acerca): la ventana de una app con carpetas; en su golpe se marca una fila en el color de la interfaz y, con `acerca`, esa fila se adelanta.
   - **Tarjetas** (`tarjetas`: items, marca, golpes): un mazo que se abanica; la marcada se queda con el borde y la barra de la interfaz.
   - **Captura** (`captura`: fuente, ancho, alto, marcas, circulos, notas): la prueba real con la cifra subrayada con rotulador (se pinta en su golpe), un círculo a mano que se dibuja y notas a mano en rojo. Medidas en píxeles de la imagen. Con `"flota": true` en la capa (sin `dividida`), flota sobre el vídeo en la parte de arriba.
   **Encima de la cara** (capas `"tipo": "encima"`):
   - **Logos** (`logos`: fuentes, golpes): los logos reales de las apps que nombra saltan alrededor de la cabeza, con un poco de rebote. Siempre el logo real (nunca uno inventado).
   - **Sello de serie** (`serie`: palabra, cinta, lazo): el nombre de la sección («SKILL» + «de la semana») con la cinta del color de la marca en letra a mano y un lazo. Entra y se va con su frase.
   **Subtítulos cortos** (`"subtitulos": "cortos"` en las reglas del kit): 1-3 palabras, blancos y pequeños, sin caja, a la altura del pecho, también con la pantalla partida.
   **Ritmo** (`"ritmo": {"reencuadre_cada": 1.3, "escalas": [1.0, 1.08, 1.04]}` en el kit o el montaje): reencuadres leves en todo el vídeo, no solo en el gancho.
6. **Planos animados a pantalla completa** solo cuando la visual necesita todo el cuadro (una comparación grande, el cierre). Ocupan su frase entera y vuelve la cara.
7. **Rótulos** para cambiar de bloque o la llamada final («Comenta IDEAS»).
8. **Sonido**: sin efectos por defecto. Solo un golpe suave en los remates (`"remate": true` en la frase), por debajo de la voz.
9. **Nada fijo y nada se despide con animación larga**: lo que entra se va con el corte de su frase.

**El montaje** (`montaje.json`):
```json
{"bruto": "<vídeo>", "negocio_id": 1, "cara": {"x": 0.49, "y": 0.37},
 "frases": [
  {"di": "En un futuro nadie dirá un negocio de inteligencia artificial.", "gancho": true, "clave": "Negocio de IA", "remate": true},
  {"di": "Lupi mira qué está funcionando en cuentas como la mía.", "ve": {"tipo": "pantalla", "fuente": "...", "medidas": "...", "ancho": 540, "alto": 960, "desde": 0, "encuadres": [{"t": 0, "caja": "#post-31", "aire": 1.1}]}},
  {"di": "Y es que hoy en día nadie dice un negocio de internet", "ve": {"tipo": "plano", "dividida": true, "plano": {"tipo": "tachar", "titulo": "Nadie dice", "marca": "cruz", "items": ["Negocio de internet", "Negocio online"], "golpes": [91, 147]}}},
  {"di": "o un negocio online, ya nadie habla de esto.", "ve": "sigue"},
  {"di": "Si quieres la lista, comenta IDEAS.", "rotulo": "Comenta IDEAS"}]}
```
- Las frases son las del guion, en orden (salvo el gancho). Una frase larga se puede partir en dos para que cada mitad tenga su capa.
- Si se traba, repite la frase: el montaje se queda con **la última toma buena**. **El orden de lo que dice no se cambia.**
- Los subtítulos llevan las palabras del guion (nombres bien escritos) con los tiempos de la transcripción.
- Para encontrar la cara: un fotograma del bruto y su centro en proporción (x, y).
- La marca sale de `"negocio_id"` (el Kit del SaaS) o, mientras se trabaja en la skill, de `"kit": "<ruta del kit visual JSON>"` (el del cliente: `Edicion/kits/<cliente>.json`).
- Los `golpes` de una pieza son fotogramas desde que empieza su capa: el de cada línea, 2 fotogramas antes de la palabra en la transcripción.

## 6. Genérico

- Colores, tipografía y logo salen de la identidad visual del Kit (`estilo_de_marca`). Los neutros de partida solo se usan si el negocio no tiene identidad.
- Los muñecos y la oficina de Orby son de la cuenta de Orby. En un negocio cualquiera, en su lugar van su logo, su material y las grabaciones de su propia app o web.
- Los datos que salen en pantalla son siempre de prueba o del propio negocio con permiso. Nunca datos reales de terceros.

## 7. Control de calidad (antes de entregar)

La nota es la media de dos mitades. **Por debajo de 8 no se entrega.**

**Mitad automática** (`herramientas/revisar.py`): parte de 10; resta 1,5 por cada fallo (volumen fuera de -14 ±1 LUFS, pico por encima de -1 dBTP, rótulo de más de 6 palabras, emoticonos, palabra clave con contraste por debajo de 3:1 con lo que tiene detrás) y 0,5 por cada aviso (contraste por debajo de 4,5:1, plano de menos de 0,8 s o de más de 7 s, dos planos iguales seguidos, menos de 1 s de cara entre capas, voz lenta, mucho rato sin voz).

**Mitad a ojo** (hoja de contactos a 2 fps y cada transición fotograma a fotograma): parte de 10 y resta 1 por cada vez que:
1. pasan dos efectos a la vez;
2. hay una caja, una píldora, una baldosa de icono o un sello;
3. algo entra más de 3 fotogramas antes o después de su palabra;
4. un texto sale de la zona segura o tapa la cara;
5. un gráfico repite literalmente lo que dice el subtítulo;
6. una transición deja un fotograma negro, un salto o un plano vacío;
7. una imagen o grabación no es exactamente lo que se nombra, o enseña datos reales de alguien;
8. hay algo fijo en pantalla todo el vídeo;
9. el conjunto parece una plantilla (mismo recurso repetido, todo rebota, todo brilla).

Se entrega con la nota y lo que se ha restado. Si algo resta por un fallo del motor, se arregla en el motor, no en ese vídeo.

## 8. Pendiente del motor

- Las ilustraciones de `ilustraciones.tsx` tienen sus colores de serie (azules): falta pasarlas a los colores de la marca.
- Página de venta, móvil, calendario y chat siguen siendo objetos con su tarjeta (está permitido), pero se pueden aligerar.
