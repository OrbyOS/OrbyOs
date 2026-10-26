# Instalar Radar

Radar es tu equipo de contenido: investiga tu nicho, te dice qué grabar, escribe los guiones, edita los vídeos, los publica, atiende los DMs y aprende de los resultados. Se instala en tu ordenador o en un servidor tuyo, y tus datos se quedan ahí.

## Lo que necesitas

| | Para qué | Coste |
|---|---|---|
| Un Mac o un ordenador con Linux (en Windows, dentro de WSL) | Donde corre Radar | — |
| **Claude**: tu plan Pro o Max, o una clave de la API | Que el equipo piense y escriba | Tu plan, o pago por uso |
| Apify | Leer los posts de tu cuenta y de tu competencia | Tiene saldo gratis para empezar |
| Zernio | Publicar y métricas | Gratis para las 2 primeras cuentas |
| ManyChat (plan Pro) | DMs y palabras clave de Instagram | El plan Pro de ManyChat |
| Telegram (opcional) | El resumen de cada mañana y aprobar desde el móvil | Gratis |

## En tu ordenador (unos 10 minutos)

1. Si no los tienes, instala **Python 3.12** y **ffmpeg**. En un Mac, con [Homebrew](https://brew.sh):
   ```bash
   brew install python@3.12 ffmpeg
   ```
2. Abre la carpeta de Radar en una terminal y ejecuta:
   ```bash
   bash instalar.sh
   ```
   Instala lo necesario, crea un acceso directo («Abrir Radar.command») y abre Radar en el navegador.
3. **Crea tu cuenta**: la primera que se crea es la de administración.
4. Ve a **Administración → Claves y ajustes** y pega tus claves. No hace falta tocar ningún archivo.

Para abrirlo otro día: doble clic en **«Abrir Radar.command»**. Radar trabaja mientras esté abierto. Si quieres que trabaje aunque apagues el ordenador, instálalo en un servidor.

## Claude: con tu plan o con una clave

En **Claves y ajustes → Cómo usa Claude la app**:

- **Mi plan de Claude (Claude Code)**: usa tu suscripción Pro o Max.
  1. Instala Claude Code: [code.claude.com](https://code.claude.com).
  2. En una terminal, ejecuta `claude setup-token` e inicia sesión.
  3. Pega el token en «Token de tu plan de Claude».
  Úsalo solo para tu propio negocio. Revisa las condiciones de Anthropic si vas a dar servicio a otras personas.
- **Clave de la API**: crea una en [console.anthropic.com](https://console.anthropic.com) y pégala. Pagas por uso. Es la opción para un servidor o para gestionar varios clientes.

Hay una cosa que solo funciona con la clave de la API: sacar el estilo de edición mirando los fotogramas de los vídeos de tu competencia.

## En un servidor (para que trabaje 24/7)

Un servidor pequeño cuesta unos 10-20 $ al mes. Con Docker:

```bash
cp .env.example .env
docker compose up -d
```

Ponle delante una dirección con https (Caddy, Nginx o un túnel de Cloudflare) y escríbela en **Claves y ajustes → Dirección pública**. Así, las guías de tus palabras clave se abren desde un DM y ManyChat puede pasarle los mensajes a Radar. Lo que pegues en Claves y ajustes se guarda en la carpeta `datos/`, junto a tu base de datos.

## Primeros pasos, en este orden

1. **Ficha del negocio**: lo que vendes, a quién, tus redes y tu competencia (desde «Nuevo onboarding» en Administración).
2. **Kit de marca → Redactar borrador**: tu voz, tus carriles y tus pruebas. Apruébalo en Aprobaciones.
3. **Investigación → Escanear ahora**: lo que destaca en tu nicho.
4. **Graba hoy → Planificar hoy**: apruébalo y el guionista escribe los guiones.
5. **Graba** con el teleprompter de cada guion y **sube las tomas** en Producción.
6. **Publicación**: conecta Zernio y programa lo aprobado.
7. **Comunidad**: conecta ManyChat en **Conectores**, monta la automatización maestra (pasos en `INSTALAR_MANYCHAT.md`), activa los DMs automáticos y pon un enlace en cada guía.
8. **Hoy**: conecta Telegram y enciende el **piloto automático**.

## Si algo no va

| Ves | Haz |
|---|---|
| «Falta la clave de Claude» | Claves y ajustes → elige cómo usa Claude la app y pega la clave o el token |
| «No encuentro Claude Code» | Instala Claude Code o cambia a la clave de la API |
| Una cuenta «hay que reconectarla» | Reconéctala dentro de Zernio y pulsa «Guardar y comprobar» en Publicación |
| Las tomas salen «Se ha parado» después de cerrar la app | Pulsa «Reintentar» en Producción |
| El piloto se ha parado | Mira el registro en Hoy: suele ser el presupuesto del mes de Claude o de Apify |
