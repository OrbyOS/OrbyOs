# Motor de reels

Convierte un reel vertical grabado a cámara en un reel editado con criterio de editor profesional. Mismo código en los dos sitios:

- **La skill `editar-reel`** (Claude Code, con el cliente con el que se afina el estilo): donde se afina el estilo. Cada corrección se convierte en regla (ver `CAMBIOS.md`).
- **El SaaS (Radar)**: donde se aplica a cada cliente con su kit visual.

## Las piezas

| Pieza | Qué es | Quién la toca |
|---|---|---|
| `MANUAL_EDITOR.md` | El criterio: recursos, máximos, movimiento, imagen, corte, subtítulos, sonido y control de calidad | Se afina con la skill |
| `kits/ejemplo.json` | Kit de ejemplo: colores, fuentes (del catálogo de `remotion/src/fuentes.ts`) y preferencias. Los de cada cliente no van en el repositorio: en el SaaS salen de su identidad visual (`identidad.kit_motor`) y, con la skill, de la carpeta de `MOTOR_REELS_KITS` | Uno por cliente, fuera del repo |
| `esquema_montaje.json` | Lo que decide el editor en cada vídeo: tramos, encuadres, gráficos y transiciones | Lo escribe Claude |
| `motor/validar.py` | Las reglas medibles del manual. Un error bloquea el render | Crece con el manual |
| `motor/preparar.py` | Bruto → transcripción con tiempos + fotogramas en SDR + silueta (Vision en Mac o MediaPipe en servidor) | |
| `motor/montar.py` | Montaje + kit → props → render en Remotion → voz y efectos a -14 LUFS | |
| `motor/qa.py` | Hoja de contactos, transiciones fotograma a fotograma y volumen | |
| `remotion/` | Las piezas visuales: plano con cámara en mano, titular detrás de la cabeza, tarjetas, subtítulos, grano y transiciones | Crece con el manual |

```bash
# solo Mac, una vez: compila la silueta con Vision (tools/segmentar)
motor_reels/tools/compilar_segmentar.sh
# desde producto/app (MOTOR_REELS_KITS=<carpeta con los kits de los clientes>)
.venv/bin/python -m motor_reels preparar <bruto> <trabajo>
.venv/bin/python -m motor_reels validar  <trabajo>/montaje.json
.venv/bin/python -m motor_reels montar   <trabajo>/montaje.json <salida.mp4>
.venv/bin/python -m motor_reels qa       <salida.mp4> <trabajo>
```

## Integración en el SaaS

Hecho el 23/10/2026 sobre el editor de Monti (`radar/editor`), como el estilo **«De editor»**. El estilo se elige en el Kit («Estilo de edición»).

| Pieza | Qué hace |
|---|---|
| `editor/modelo.py` | Estilo `editor` (`motor: True`, modos cámara y vídeo largo), `usa_motor(ajustes, modo, datos)` y `ESTILO_SIN_MOTOR = "natural"` |
| `editor/plan_motor.py` | Claude recibe el manual entero y las palabras numeradas, y devuelve los planos **por número de palabra**. `motor/desde_palabras.py` los pasa a segundos (corta los silencios con punch-in y no pisa frases quitadas) y `validar.py` los comprueba. Si hay errores, se le devuelven a Claude una vez; lo que siga mal lo arregla `sanear()`. Sin clave de Claude, `basico()`. `para_ver()` cuenta los planos al cliente («Así queda cada plano») |
| `editor/montaje_motor.py` | Extrae y recorta (MediaPipe) solo los tramos usados, reencuadra a 9:16 los horizontales con `montaje.encuadre` y renderiza con el kit |
| `agentes/identidad.py` → `kit_motor(nid)` | El kit sale de la identidad visual del Kit: cada rol de color (fondo, luz, panel, texto, acento) por las palabras de su «uso»; lo que falte, derivado del color principal. Las tipografías propias del cliente (.ttf/.otf) se usan por su «uso» (titular, subtítulos, golpe, mono); si no hay, las del catálogo |
| `editor/flujo.py` | Plan, cambios (v2, v3…) y montaje por el motor cuando `usa_motor()`. Si no se puede (Monti, o servidor sin Node), `ajustes_de()` cambia «editor» por «natural» y se monta por la vía clásica; la elección de la marca no se pierde |
| `config.motor_reels_activo()` | Node + `motor_reels/remotion/node_modules` |

**Monti no usa el motor todavía** (`modelo.es_de_monti`: ediciones con `datos["produccion"]` o `automatico`). Renderizar con Remotion desde el hilo web ahogaría el servidor (Hetzner CPX22, 2 núcleos, 4 GB). Cuando exista el worker de renders se quita esa condición. Como hoy todas las ediciones del SaaS pasan por Monti, el estilo «De editor» está **dormido en producción**: se trabaja y se afina con la skill `editar-reel`.

El titular se ajusta al ancho real medido con la tipografía del cliente, y la cámara sigue la cabeza (acercando la imagen si hace falta) para que tape solo la base del titular.

Pruebas: `tests/test_motor_reels.py`.

## Pendiente antes de dárselo a clientes

1. **Docker y worker**: el `Dockerfile` de producción no lleva todavía Node ni Chromium (es de Back-end; en la copia antigua quedó un ejemplo). Hay que decidir con Back-end entre un worker aparte en docker-compose o Remotion Lambda. Las fuentes se descargan de Google Fonts al renderizar, así que el servidor necesita salida a internet (o copiarlas en local).
2. **Cola de renders**: renderizar ocupa todos los núcleos ~1,5 min por reel. Ahora va en un hilo del proceso web, como el editor clásico; con varios clientes a la vez, hace falta una cola (o Remotion Lambda).
3. **Licencia de Remotion**: es gratis para personas y empresas de hasta 3 trabajadores. Por encima, y sobre todo si se renderiza como servicio para terceros, hace falta la licencia de empresa. Hay que revisarlo antes de cobrar.
4. **Calidad de la silueta (prioridad)**: probado el 23/10/2026 con IMG_3084. MediaPipe deja un halo claro alrededor del pelo (el borde de la máscara arrastra la pared), muy visible en los recortes sobre el color de fondo; Vision (Mac) sale limpio. En el servidor hará falta un modelo de matting de vídeo (por ejemplo, RobustVideoMatting), o como mínimo erosionar el borde y descontaminar su color.
5. **HDR del iPhone**: casi todos los brutos de iPhone son HLG. En el servidor se convierten con `zscale` (el ffmpeg de Debian lo trae); si no está, el reel sale con un aviso de colores lavados. El editor clásico del SaaS no lo trata: hoy sus reels de iPhone salen lavados.
6. **Kit visual por cliente**: un paso del onboarding (colores de su marca, fuentes del catálogo y referencia de edición) que escriba `data/marcas/<negocio>/kit.json`. Hasta entonces se deriva de su color.
7. **Tarjeta final y logo**: el estilo «De editor» todavía no pone la tarjeta de cierre ni el logo en la esquina de los estilos clásicos.
8. **Música**: hace falta una biblioteca con licencia (API de Epidemic Sound, Artlist o similar).
