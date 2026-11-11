# Instalar Orby

Orby es tu equipo de contenido: investiga tu nicho, te dice qué grabar, prepara los guiones o las estructuras, edita
los vídeos, los publica, atiende los DMs y aprende de los resultados. Se instala en tu ordenador o en un servidor
tuyo, y tus datos se quedan ahí.

## Lo que necesitas

| | Para qué | Coste |
|---|---|---|
| Un Mac o un ordenador con Linux (en Windows, dentro de WSL) | Donde corre Orby | — |
| **Claude**: una clave de la API o, en tu ordenador, tu plan Pro o Max | Que el equipo piense y escriba | Pago por uso, o tu plan |
| Apify | Leer los posts de tu cuenta y de tu competencia | Tiene saldo gratis para empezar |
| Zernio | Publicar y métricas | Gratis para las 2 primeras cuentas |
| ManyChat (plan Pro) | DMs y palabras clave de Instagram | El plan Pro de ManyChat |
| Telegram (opcional) | El resumen de cada mañana y aprobar desde el móvil | Gratis |

Cada negocio conecta **sus propias claves** y paga su propio uso. Orby no cobra nada.

## En tu ordenador (unos 10 minutos)

1. Si no los tienes, instala **Python 3.12** y **ffmpeg**. En un Mac, con [Homebrew](https://brew.sh):
   ```bash
   brew install python@3.12 ffmpeg
   ```
2. Abre la carpeta de Orby en una terminal y ejecuta:
   ```bash
   bash instalar.sh
   ```
   Instala lo necesario, crea un acceso directo («Abrir Orby.command») y abre Orby en el navegador.
3. **Crea tu cuenta**: la primera que se crea es la de administración.
4. **Crea tu negocio** y ve a **Conectores**: ahí se pegan las claves de ese negocio (Claude, Apify, YouTube,
   Zernio, ManyChat y Telegram). Cada una se comprueba al guardarla. No hace falta tocar ningún archivo.

Para abrirlo otro día: doble clic en **«Abrir Orby.command»**. Orby trabaja mientras esté abierto. Si quieres que
trabaje aunque apagues el ordenador, instálalo en un servidor.

## Claude: con una clave o con tu plan

Se elige en **Administración → Ajustes de la instalación → Cómo usa Claude la app**:

- **Clave de la API** (por defecto): crea una en [console.anthropic.com](https://console.anthropic.com) y pégala en
  los Conectores de tu negocio. Pagas por uso. Es la opción para un servidor o para gestionar varios negocios.
- **Mi plan de Claude (Claude Code)**: solo en tu ordenador y para tu propio negocio.
  1. Instala Claude Code: [code.claude.com](https://code.claude.com).
  2. En una terminal, ejecuta `claude setup-token` e inicia sesión.
  3. Pega el token en «Token de tu plan de Claude».
  Revisa las condiciones de Anthropic si vas a dar servicio a otras personas.

Hay una cosa que solo funciona con la clave de la API: sacar el estilo de edición mirando los fotogramas de los
vídeos de tu competencia.

## En un servidor (para que trabaje 24/7)

Un servidor pequeño con Ubuntu (por ejemplo, de Hetzner) cuesta unos 5-20 € al mes. Si quieres dominio propio,
apúntalo a la IP del servidor con un registro A. Desde tu ordenador:

```bash
./desplegar.sh <IP del servidor> [tu-dominio.com]
```

Instala Docker si falta, copia la app (sin tus datos locales ni tu `.env`), pone https automático con Caddy y la
arranca. Sin dominio, la dirección es `<ip-con-guiones>.sslip.io`. Volver a lanzarlo actualiza la app sin tocar los
datos del servidor, y si cambias de dirección, la antigua sigue funcionando y lleva a la nueva.

La dirección pública (para que las guías se abran desde un DM y ManyChat le pase los mensajes a Orby) la pone
`desplegar.sh` solo. Lo que pegues en Conectores y en los ajustes se guarda en la carpeta `datos/` del servidor,
junto a la base de datos.

## Primeros pasos, en este orden

1. **Onboarding**: tus datos y tus redes, tu tipo de negocio y cómo grabas. Después sube de 1 a 3 llamadas (texto,
   audio o vídeo) y pulsa «Preparar la ficha y el Kit». Te llega a Aprobaciones.
2. **Kit de marca**: revisa la voz, los temas, los límites y la identidad visual (colores, tipografías y movimiento).
3. **Investigación → Escanear ahora**: lo que destaca en tu nicho.
4. **Graba hoy → Planificar hoy**: apruébalo y Escri prepara lo que hay que grabar.
5. **Graba** y **sube las tomas** en Producción. Monti las edita; de una grabación larga saca varios reels.
6. **Publicación**: con Zernio conectado, programa lo aprobado.
7. **Comunidad**: con ManyChat conectado, monta la automatización maestra (pasos en `INSTALAR_MANYCHAT.md`), activa los
   DMs automáticos y pon un enlace en cada guía.
8. **Hoy**: conecta Telegram y enciende el **piloto automático**.

## Si algo no va

| Ves | Haz |
|---|---|
| «Falta la clave de Claude» | Conectores de tu negocio → pega la clave de la API (o elige tu plan en Ajustes de la instalación) |
| «No encuentro Claude Code» | Instala Claude Code o cambia a la clave de la API |
| Una cuenta «hay que reconectarla» | Reconéctala dentro de Zernio y pulsa «Guardar y comprobar» en Conectores |
| Las tomas salen «Se ha parado» después de cerrar la app | Pulsa «Reintentar» en Producción |
| El piloto se ha parado | Mira el registro en Hoy: suele ser el presupuesto del mes de Claude o de Apify |
