# Conectar Chati con el ManyChat del negocio

Chati (Comunidad) responde a la palabra clave y lleva la bandeja de DMs de Instagram a través del ManyChat del propio negocio. En Radar se configura cada palabra clave, su guía y su mensaje. En ManyChat se montan unas automatizaciones sencillas que le pasan a Radar lo que llega y mandan lo que Radar contesta.

La API de ManyChat no deja crear automatizaciones, y ManyChat **no le pasa a Radar el texto de un comentario** (lo confirman sus moderadores en agosto de 2026). Por eso hay dos tipos:

- **Equipo · DMs**: una sola, para todos los mensajes directos. Se monta una vez.
- **Equipo · PALABRA**: una por palabra clave (por ejemplo «Equipo · CIERRE»), para los comentarios. Se monta cada vez que sale un vídeo con una palabra nueva. Radar avisa de las que faltan.

## Lo que hace falta

- **ManyChat Pro** en la cuenta del negocio, con su Instagram conectado. La API y la petición externa lo necesitan.
- **Radar abierto por una dirección https**, para que ManyChat pueda llamarle:
  - En un servidor, la del servidor. La primera vez que se entra por https, Radar la guarda sola. También se puede pegar en Administración → Ajustes de la instalación → «Dirección pública de la app».
  - Para probar en tu ordenador, un túnel: `cloudflared tunnel --url http://localhost:8000`. Abre una vez la dirección `https://….trycloudflare.com` que te da. Ojo: esa dirección cambia cada vez que lanzas el túnel, y entonces hay que cambiarla también en ManyChat.

## 1. La clave

1. En ManyChat: Settings → API → Generate your API Key.
2. Pégala en Radar, en Conectores → ManyChat. Radar comprueba la clave y crea en ManyChat:
   - las etiquetas `equipo-caliente`, `equipo-templado` y `equipo-frio`;
   - los campos `equipo_respuesta`, `equipo_responder`, `equipo_palabra`, `equipo_temperatura` y `equipo_origen`.

   La **dirección para la petición externa** (`https://<tu dirección>/m/<código>`) está en Conectores → ManyChat, con un botón para copiarla.

## 2. Las automatizaciones

Los nombres tienen que empezar por «Equipo», porque así comprueba Radar que existen. Los nombres de los menús pueden cambiar un poco según la versión de ManyChat.

**Equipo · DMs** (una vez)
1. Disparador: la respuesta por defecto de Instagram («Default Reply»: salta cuando no salta ninguna otra automatización). Si tiene opción de frecuencia, ponla en **cada vez** (no «una vez cada 24 h»): si no, Radar solo vería el primer mensaje de cada día.
2. Acción «External Request»:
   - método **POST**;
   - dirección: la del paso 1;
   - Body en JSON (cada `{{…}}` se mete con el botón de campos de ManyChat):
     ```json
     {"suscriptor": "{{user_id}}", "usuario": "{{ig_username}}", "nombre": "{{full_name}}", "texto": "{{last_input_text}}", "origen": "dm"}
     ```
   - Response mapping: `$.responder` → `equipo_responder`, y `$.respuesta` → `equipo_respuesta`.
3. Condición: `equipo_responder` es `si` → mensaje de Instagram con el texto `{{equipo_respuesta}}`.

**Equipo · PALABRA** (una por palabra clave; Radar te da el texto exacto en Conectores → ManyChat)
1. Disparador: «User comments on your Post or Reel» → **todos los posts** (y los futuros) → **contiene la palabra** (por ejemplo `CIERRE`).
2. La misma petición externa, con la palabra escrita a mano en `texto` y `"origen": "comentario"`:
   ```json
   {"suscriptor": "{{user_id}}", "usuario": "{{ig_username}}", "nombre": "{{full_name}}", "texto": "CIERRE", "origen": "comentario"}
   ```
3. La misma condición y el mismo mensaje.

Ojo: Instagram solo deja que una automatización de comentarios responda una vez por persona y post.

## 3. Comprobarlo

1. En Comunidad, marca «Activar los DMs automáticos» y guarda. Si está apagado, Radar apunta todo pero no manda nada solo.
2. En Comunidad, pulsa «Comprobar ahora» (en «DMs automáticos»): si no sale ningún aviso, está listo.

## 4. Primera prueba de verdad (lista de comprobación)

Hazla con una cuenta de Instagram de pruebas que escriba a la del negocio. Apunta qué falla en cada paso.

1. **Clave**: al pegarla, Radar dice «ManyChat conectado con …» y en ManyChat aparecen las etiquetas `equipo-…` y los campos `equipo_…`.
2. **DM normal**: desde la cuenta de pruebas escribe «Hola, ¿cuánto cuesta?». En ManyChat, en el historial de la petición externa, la respuesta tiene que ser 200. Al minuto, en Radar → Comunidad aparece la conversación como caliente y en Aprobaciones hay un borrador.
3. **El texto llega bien**: en esa conversación de Radar se lee lo que escribiste. Si sale vacío o `{{last_input_text}}` tal cual, el campo no es ese: busca en el botón de campos de ManyChat el que traiga el último mensaje.
4. **El contacto llega bien**: en Radar sale el usuario de Instagram. Si sale vacío, revisa `{{user_id}}` y `{{ig_username}}`.
5. **Segundo DM**: escribe otro mensaje. Tiene que llegar también (si no, la respuesta por defecto está en «una vez cada 24 h»). En Aprobaciones solo queda el borrador nuevo.
6. **Aprobar**: aprueba el borrador. El mensaje llega a la cuenta de pruebas.
7. **Palabra clave por comentario**: comenta la palabra en un post. Llega el DM con el enlace a la guía. En ManyChat, el contacto tiene la etiqueta `equipo-templado` y el campo `equipo_palabra`.
8. **Guía y correo**: abre el enlace del DM y deja un correo. En Radar → Contactos sale una sola persona con su usuario y su correo, y en ManyChat el campo `equipo_email`.
9. **Palabra repetida**: vuelve a comentar la palabra. No llega otro DM.

## Cómo se comporta

- **Palabra clave:** se manda una vez por persona y palabra, con el enlace de seguimiento del post (`utm_content`). En un DM, la palabra tiene que ser casi todo el mensaje.
- **Guía:** el enlace del DM reconoce a quien lo recibió. Si deja su correo, se añade a su contacto (y a ManyChat, en `equipo_email`) en vez de crear otro.
- **Lo demás que llega por DM:** se guarda y, al minuto, Claude lo clasifica en lote (caliente, templado, frío o spam). Deja un borrador de respuesta en Aprobaciones, con la hora a la que caduca. Si la persona escribe otra vez, el borrador anterior se retira y queda solo el nuevo. Al aprobarlo sale por ManyChat, siempre que no hayan pasado 24 h desde el último mensaje de esa persona (norma de Instagram); si han pasado, Radar avisa.
- **En ManyChat** quedan la etiqueta de temperatura y la palabra en cada contacto, para usarlas en tus propias automatizaciones.
- **Una sola herramienta en los DMs:** apaga en ManyChat otras automatizaciones que respondan a las mismas palabras. Zernio ya no toca los DMs, solo publica.
