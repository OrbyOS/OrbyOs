---
name: motion-graphics
description: Hace los motion graphics de los vídeos verticales (9:16) del SaaS con su motor de Remotion (generacion_videos), para cualquier negocio y con su identidad visual del Kit. Sobre todo, reels a cámara de 30-60 s (la persona hablando o leyendo un guion) con reencuadres secos en el gancho, la palabra clave junto a la cara en el momento en que la dice, pantallas y capturas reales cuando nombra una herramienta o un dato, planos animados y rótulos, sin nada fijo en pantalla; también los explicativos sin cámara (voz clonada y planos animados palabra a palabra). Úsala siempre que pidan motion graphics, gráficos, textos o animaciones encima de un vídeo a cámara, un reel con pantallas de la app o pruebas reales, grabar la pantalla de la app para un vídeo, un vídeo explicativo, una pasada fina de los motion graphics, o revisar uno de estos vídeos antes de entregarlo, aunque no digan «skill». No es para sacar los reels de un bruto largo hablado sin guion ni para quitar el fondo (eso es editar-reel), ni para vídeos largos de YouTube (editar-video-largo), ni para trocear vídeos largos (simplest-clips).
---

# Motion graphics

El motor vive en el SaaS: **`generacion_videos/`**, en la raíz del repositorio de la app, (en adelante `MOTOR`), con la lógica en `radar/agentes/generacion.py` (explicativo), `generacion_cara.py` (a cámara) y `generacion_banco.py` (vídeos de banco). Lo que aquí se decide y se corrige es lo que después hará el SaaS con cada negocio. Por eso **nunca se arregla un vídeo «a mano»**: toda corrección se convierte en una regla del manual o en una pieza del motor.

Antes de empezar, lee:
- **`MANUAL.md`** (en esta carpeta): las reglas, el catálogo de piezas con sus tiempos y el control de calidad. Mandan sobre tu gusto.
- La **identidad visual del negocio** (Kit → identidad: paleta, tipografías, logo, «nunca hagas»). El estilo sale de ahí con `generacion.estilo_de_marca(negocio_id)`; en el guion o el montaje basta con `"negocio_id"`. Sin identidad se usan los neutros de partida (`generacion.ESTILO`, los azules de Orby, la cuenta de la casa). **Nada de un negocio concreto va en el código.**
- Las **reglas del cliente** que estén en su Kit (voz, emoticonos, cifras con fuente). En la marca del cliente cero: el `CLAUDE.md` de su carpeta.

## Qué hace esta skill y qué hace editar-reel

Las dos trabajan reels a cámara; no se pisan si cada una hace lo suyo:

| | **editar-reel** (`motor_reels`) | **motion-graphics** (`generacion_videos`) |
|---|---|---|
| Bruto | Hablado libre, 3-5 min, varias tomas: saca el **mapa de reels** y elige la mejor toma de cada parte | Un **guion** leído frase a frase (si se traba, repite la frase) o frases ya elegidas de una transcripción |
| Cortes | Silencios, muletillas, tomas falsas; el gancho que se adelanta | La última toma buena de cada frase del guion (alineado con Whisper); el gancho que se adelanta (`"gancho": true`) |
| Encima | Titular **detrás** de la cabeza y quitar el fondo (necesitan la silueta), sus efectos y tarjetas | **Todo lo que va encima sin silueta**: palabra clave junto a la cara, reencuadres del gancho, pantallas y capturas reales, planos animados, rótulos, cierre |
| Subtítulos | Los suyos (estilo del kit) | Los suyos, con las palabras del guion |

Regla práctica: **si hay guion o hace falta enseñar la app o pruebas reales, esta skill**. Si es un bruto largo sin guion del que salen varios reels, o el gancho pide la cabeza delante del titular, **editar-reel**. Las reglas de gusto (sin cajas, un efecto a la vez, tiempos, sin etalonaje) son las mismas en las dos: las de este `MANUAL.md` valen también para los gráficos de editar-reel.

## Regla del Mac (obligatoria)

Un solo trabajo pesado a la vez en el Mac (render de Remotion, Whisper, grabación de pantalla a 2160×3840). Remotion siempre con `--concurrency=2` como mucho (ya lo pone el motor). Mientras otra sesión renderiza, solo fotogramas sueltos (`remotion still`). Si hay una sesión que reparte turnos (Dire), pide turno antes de renderizar y avisa al acabar.

## Órdenes (desde `producto/app`, con el Python del SaaS)

```bash
cd <raíz del repositorio de la app>
# Explicativo: guion.json → vídeo. --borrador usa la voz del Mac y no gasta créditos de ElevenLabs.
.venv/bin/python -m radar.agentes.generacion <guion.json> <salida.mp4> [--borrador] [--escala 0.5]
# A cámara: montaje.json → vídeo. --trabajo guarda la transcripción y las props para no repetir Whisper.
.venv/bin/python -m radar.agentes.generacion_cara <montaje.json> <salida.mp4> --trabajo <carpeta>
# Control de calidad: nota automática + hoja de contactos (las props salen en la carpeta de trabajo).
.venv/bin/python generacion_videos/herramientas/revisar.py <video.mp4> <props.json>
# Grabar una pantalla de la app (fluida a 2160×3840, con las cajas medidas para el zoom).
node generacion_videos/herramientas/grabar_pantalla.mjs <config.json>
```

Muestrario de todos los planos (para comparar un antes y un después sin renderizar vídeos): `npx remotion bundle src/index.ts --out-dir <b> --public-dir=../../radar/static/marca` en `MOTOR/remotion`, y un `npx remotion still <b> Explicativo <png> --frame=N` por plano (cada plano dura 72 fotogramas).

## Flujo

1. **Guion o montaje.** Lo que se dice va en `di` y lo que se ve en `ve`. Marca con `^palabra` dónde entra cada cosa (cada punto de una lista, cada mensaje de un chat) y con `*palabra*` el énfasis. Una pieza por frase: elige del catálogo del manual la que **explica** lo que se dice, no la que lo repite.
2. **Material real primero.** Si se nombra la app, graba su pantalla con datos de prueba (nunca datos reales de nadie). Si se nombra algo concreto, busca la imagen real. El vídeo de banco (`recurso`) solo como ambiente, tratado con el color de la marca y nunca para «ilustrar» lo que no se ha podido enseñar.
3. **Borrador barato.** Explicativo con `--borrador` o fotogramas sueltos de las piezas nuevas. Mira los tiempos contra la voz antes de gastar voz pagada o un render largo.
4. **Render** (con turno), una sola vez y a 2 hilos.
5. **Control de calidad** (manual, sección 7): la nota automática más la revisión a ojo de la hoja de contactos y de cada transición fotograma a fotograma. Por debajo de 8, no se entrega: se arregla en el motor o en el guion y se vuelve a montar.
6. **Entrega** en la carpeta de entregas del cliente (`<nombre>_vN.mp4`) con dos o tres líneas: qué es, qué se ha decidido y qué tiene que mirar.

## Cuando te corrijan

Cada corrección es una regla: si es de gusto general, va al `MANUAL.md`; si es de un negocio, a su Kit («nunca hagas» o identidad visual); si es un fallo del motor, al código con un commit pequeño en español. Después, vuelve a montar lo afectado.
