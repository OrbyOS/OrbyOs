# Cambios del estilo

Cada corrección del cliente con el que se afina el estilo, convertida en regla. Lo más nuevo, arriba.

## 29/10/2026
- **Formato raw para el cliente.** Dijo: «no me gustan… vamos a tirar por un formato más raw», «cortes y letras sencillas. Alguna animación por detrás y ya». Regla: el kit del cliente con máximos a 0 para pantallas partidas, tarjetas, mosaicos, portadas, rótulos, prompt, editor y CTA en tarjeta. `validar` cuenta ahora `partida`, `mosaico`, `esquinas`, `rotulo`, `prompt`, `terminal` y `cta`, así que cualquier kit los puede bajar a 0. El estilo de rótulos queda en un kit archivado.

## 28/10/2026
- **Edición en directo en Montaje** (`/panel/<bruto>/<reel>`): el Reel del motor en el Player de Remotion, con la voz y los efectos, y las variables que elige el cliente (música, volumen, gancho de los 2 primeros segundos, ritmo de cortes, reencuadres, pantallas, subtítulos, logos y efectos de sonido) aplicadas al momento sobre las props, sin volver a montar. Nota, veredicto y qué cambiaría se guardan en `trabajo/<bruto>/elecciones.json`; «Renderizar final» deja un pedido en `Edicion/reels/pedidos/` con la orden (`motor_reels final`), que se lanza con turno. En el motor: `preparar_vista` (todo menos el render), `renderizar_props` (render de unas props dadas), `sonidos_de_props`, subtítulos medianos abajo y captura flotante sobre el vídeo.
- **Estilo propio del cliente (kit «estilo»).** Una cuenta puede copiar la edición de otra. Para el primer caso se ha añadido al motor: subtítulos limpios (blancos, sin caja), pantalla partida sobre lienzo liso con la captura como tarjeta, efectos en tinta oscura sobre el lienzo, logos de apps que saltan alrededor de la cabeza, sello de serie con cinta, música continua a -30 LUFS, gancho sin titular obligatorio y máximos por minuto propios. Sin bloque `estilo`, todo sale como antes.

## 26/10/2026
- **Cierre de las skills de Monti (encargo de «Skill dirección»).** Zona segura de Instagram (ningún texto fuera de x 60-850 e y 230-1440; `zona_segura.json`, la usan el render y el validador), seis palabras como mucho por rótulo (sanear recorta) y el gancho entero desde el fotograma 0 (si el primer plano no trae titular, el conversor pone uno). El gancho de cada reel de una serie sale puntuado con el catálogo de Escri (`agentes/ganchos.py`) entre la propuesta de Claude, sus candidatos y las frases del tramo, y guarda su fórmula. Manual genérico: el color de fondo del kit en vez de uno fijo, la tipografía de titular del kit y los emoticonos según `voz.emojis` del Kit (nunca, pocos o libre; sin dato, ninguno).
- **Preferencias de edición de cada cliente en su identidad visual** (plan de skills de Orby, 2.11): estilo de subtítulos (`resaltado`, `simple` o `sin`), música y efectos de sonido (sí o no) y una lista de «nunca hagas». El motor las lee de `kit["reglas"]`: sin subtítulos no pinta ninguno, «simple» no resalta la palabra y sin efectos de sonido la pista va en silencio. La lista «nunca» llega a Monti cuando planifica: manda sobre su gusto, nunca sobre este manual. La música queda guardada para cuando haya biblioteca con licencia.

## 25/10/2026 (correcciones a los reels de IMG_3092)
- **«Que no todos empiecen con el fondo de color, pero con un gancho visual».** El titular del gancho puede ir sobre el vídeo real (en la pared, detrás de la cabeza) o sobre el color de fondo del kit; se alterna.
- **«Baja el grano».** Grano muy fino (opacidad 0,22), apenas perceptible.
- **«Después del gancho metes un corte muy duro; con el fondo de color, una transición».** El color de fondo nunca entra ni sale en seco: se abre desde detrás de la cabeza o se cierra hacia ella (entrada/salida `revela`).
- **«Hay parpadeos».** La silueta a veces no estaba cargada y la persona desaparecía 1-3 fotogramas. El render espera ahora a que cada máscara esté decodificada. QA con detector de parpadeos (A-B-A).
- **«Que no se pierda calidad».** Fotogramas JPEG al 98 % y render CRF 15, preset slow.
- **«Más efectos sin sobre-editar»**: golpes de zoom en la palabra fuerte (6 por minuto) e iconos de línea propios junto a la cabeza (4 por minuto).
- **«Que se vean menos IA: paneles con texto, cómo entran, recorte con fondo de color».** El texto aparece de golpe (palabra entera) y se asienta; fuera las líneas que se dibujan. Partida y completa van sobre el propio vídeo desenfocado y oscurecido, no sobre un panel. Encima: velo difuso en el color de fondo del kit (cristal desenfocado, sin bordes) detrás del texto en crema, más denso si la camisa es clara; sin él, el texto se perdía entre las manos.
- **«Si los reels son lentos, probemos x1,1».** Regla: si la voz, ya sin silencios, va a menos de 3,3 palabras/s, el reel entero va a x1,1 (`velocidad` en el montaje la fija a mano, hasta x1,2). Los de IMG_3092 iban a 3,0.
- Corregido: en la pantalla partida, la mitad de abajo salía vacía (el recorte se aplicaba a la capa que se mueve con la cámara).
- Disco: en brutos largos solo se extraen los tramos que usan los reels (`motor_reels fotogramas`).

## 24/10/2026 (primer bruto real, IMG_3092)
- **Los efectos sobreviven a los cortes.** Una lista o una comparación dicha con tropiezos en medio se mantenía solo hasta el primer corte. Ahora el efecto abarca todos los tramos de su plano y se pinta como una capa encima (`abarca` en el montaje, `superpuestos` en el render).
- **La pantalla partida o completa empieza con su primer elemento.** En el reel «Criterio» el panel estuvo 4 s vacío esperando a «Tecnología». El conversor parte el plano: lo dicho antes va con la cara entera.
- Corregido: tras un primer efecto, los tiempos del segundo caían en la primera palabra (variable reutilizada).

## 24/10/2026
- **«Intentemos sacar más de un definitivo de cada bruto, para subir más volumen».** Sección nueva «0 bis»: de un bruto de 3-5 minutos salen todos los reels que se sostengan solos (el completo, uno por punto o ideas distintas). Mínimo 25 s, sin repetir más del 30 % ni el gancho, y si solo da para uno sale uno. Antes de montar, mapa de reels. Una preparación por bruto y un montaje por reel; `motor_reels serie` valida la serie. En el SaaS, `plan_motor.mapa_de_reels` (Monti, pendiente de Back-end).

## 23/10/2026 (noche)
- **«En vez de tanta imagen, efectos tipo After Effects que respalden lo que digo».** Recurso principal nuevo, el **efecto explicativo**: lista, cifra, comparación, proceso y gráfica (líneas que se dibujan y números que cuentan). Las imágenes reales pasan a ser puntuales (2 por minuto), y primero las suyas.
- **«Alternar: a veces la cara entera con un efecto, a veces partir la pantalla y a veces el efecto a pantalla completa».** Tres composiciones: `encima`, `partida` (la cara centrada en su mitad, sin bajar el vídeo) y `completa`.
- **«Quitar el fondo no para un color liso».** Fondos animados: luz en movimiento, rejilla en perspectiva o una foto suya con un acercamiento lento.
- **«Los brutos serán de 4-5 minutos: sácame tú el clip entero, incluso el gancho».** El editor elige la mejor toma de cada parte (corta frases enteras) y el gancho: el del principio o uno mejor de más adelante (`"gancho": true`, la única excepción al orden, y no se repite). La duración la decide la idea.
- Los máximos pasan a contarse **por minuto de reel**.

- **«Nada de emoticonos».** Prohibidos en cualquier texto del reel. El validador lo bloquea y `sanear` los quita.
- **«Que refuerce todo con imágenes reales sacadas de Google o donde veas necesario».** Recurso nuevo, la **imagen real**: hasta 4 por reel, en tarjeta (a la altura del pecho) o pantalla partida (arriba). Sale del material propio del cliente, del artículo exacto de Wikipedia (licencia libre, con autor en el pie) o de la captura de su web. **No de Google Imágenes**, porque tienen dueño y los reels se usan en anuncios. Se piden por título exacto, no por nombre (los nombres son ambiguos), y si no aparece la imagen exacta no se pone ninguna. Se descartan las capturas en blanco o de «verificando que no eres un robot».

## 23/10/2026
- **Integrado en el SaaS como estilo «De editor».** Claude decide los planos por número de palabra; el motor los pasa a segundos, corta los silencios con un punch-in (regla nueva) y valida. Si no hay kit, se deriva del color de marca.
- **«Que sea siempre así, con todos los clientes del SaaS».** El estilo pasa a ser datos: manual (`MANUAL_EDITOR.md`) + kit por cliente (`kits/`) + montaje por vídeo (`esquema_montaje.json`). El motor se mueve a `producto/app/motor_reels`.
- **«Parece editado con IA».** Reglas nuevas en el manual: vocabulario corto con máximos por reel; nada literal; prohibido el «desenfoque + subida»; anticipación de 2 fotogramas; cámara en mano; grano; sombra en el recorte; efectos de sonido por prioridad con separación de 3 s. El motor sigue la cabeza para que el titular quede tapado solo por abajo.
- **El primer kit sale de una referencia de edición que elige el cliente** (su tipografía y su color, llevados a su marca).

## 28/10/2026 (IMG_3122, estilo de rótulos en azul)
- **«Quedan súper cutres» (logos tachados).** Sin logos ni iconos en el kit del cliente: máximo 0 en el kit y `validar` lo hace cumplir sobre cualquier montaje.
- **«Se le ha quedado un "es" dicho dos veces… no puede pasar nunca».** `validar` busca con la transcripción palabras repetidas, frases reempezadas y la palabra repetida en la junta de dos tramos; `qa` transcribe el render en literal y no deja entregar si hay alguna.
- **«El texto del gancho va encima de su cabeza».** Titular `encima` (delante y con la persona debajo); el kit del cliente lo aplica solo al gancho con `ganchoEncima`.
- **«No queda exactamente centrado».** Todo lo centrado usa márgenes simétricos (centro en 540, como hizo la dirección Orby en los explicativos) y `qa` mide el centro en el render (±2 px).
- Estilo de rótulos en azul: titular sans sobre color sólido, portada de revista, rótulo sans + cursiva, barra de prompt, pantalla de editor y CTA con comentario. Los titulares sobre vídeo van en claro y se ajustan al ancho medido.
- **«Adapta el visual del principio y que sea más hook… en todos los reels tenemos que generar engagement con ese título».** El gancho pasa a ser un titular en dos líneas: sans gigante que habla al que mira («TU IA») y cursiva serif en una pastilla del acento con el giro («escribe fatal.»). Regla en el manual (sección 5) y pieza `cursiva` del titular.
- Titulares: el canvas medía con la fuente de reserva porque las del catálogo de Google se cargaban solas; ahora `fuentesListas` las espera. Los titulares sobre color llenan el ancho; sobre el vídeo, 560 px, para que la cabeza no tape el centro.
- **«Capturas de los vídeos en pantalla completa, por detrás de mí… y pon más ejemplos, no solo 2».** Fondo `mosaico`: cuadrícula densa de miniaturas reales, un poco girada y subiendo despacio, con él recortado delante. Para cuando nombra mucho contenido; la pantalla partida queda para lo que hay que leer.
