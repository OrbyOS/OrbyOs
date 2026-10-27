"""Publi: pone cada vídeo aprobado en tus redes, a su hora, sin publicar nunca dos veces.

- Huecos: cada red tiene sus días y horas (Kit de marca). Publi coge el siguiente libre de cada una.
- Antes de llamar a Zernio comprueba cada publicación: que la cuenta esté conectada, que el texto quepa en la red, que el
  título de YouTube tenga menos de 100 caracteres, que el vídeo exista.
- Cada publicación lleva una clave única (vídeo, versión y red): aunque algo se reintente, Zernio la publica una vez.
- Ensayo: `programar(..., ensayo=True)` enseña lo que saldría (red, hora, texto final y fallos) sin mandar nada.
- Enlace de seguimiento en cada post: utm_content = <prefijo del Kit><palabra>_<número de la pieza>. Todas las redes
  de una misma pieza comparten número, así los leads se suman por pieza. Va en el texto donde los enlaces funcionan
  (YouTube y LinkedIn); en TikTok, «enlace en la bio»; en Instagram manda la palabra clave.
- Fuera de Instagram, la palabra clave no sirve (los mensajes automáticos de ManyChat solo van en Instagram): esa línea
  se cambia por la del enlace.
- Hashtags: de 3 a 5 en Instagram y TikTok, los del tema de la pieza primero y luego los de la lista del Kit.
- Colaboradores en Instagram (hasta 3 cuentas): los del vídeo o, si no tiene, los del plan de Instagram. Con Zernio
  se mandan con el post; si lo publicas tú, el recordatorio te dice a quién invitar.
- Horas: `mejores_horas` mira a qué hora rinden más tus propios posts (vistas frente a lo normal de tu cuenta) y
  `proponer_horas` pone una hora a cada día del calendario de Plani. Sin datos suficientes, las horas del plan.
- Reels de prueba (Instagram, solo si el negocio los activa): las variantes que haga Monti salen como «trial reels»,
  que Instagram enseña primero a quien no te sigue y nunca van a tu perfil. Nada sale sin tu OK, y la primera vez
  sale una sola hasta que confirmes que no apareció en tu perfil.
- Instagram, por defecto, lo publicas tú (para poder poner audio en tendencia): a su hora te aparece el vídeo con su
  texto listo para copiar.
- La hora es siempre la de España (RADAR_ZONA), aunque el servidor vaya con otra: las 19:00 del plan salen a las 19:00.
- Textos: de cada grabación salen 3-4 reels. Cada uno lleva su texto, escrito a partir de lo que se dice en su tramo
  (no de la idea general de la estructura); se preparan al aprobar el vídeo y se guardan junto a él.
- Portada: el primer plano del reel lleva el titular (así lo monta Monti). Se manda como portada a Instagram y LinkedIn;
  en TikTok, ese mismo instante del vídeo. Los Shorts de YouTube no dejan poner una propia.
"""
import json
import os
import re
import statistics
import subprocess
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .. import config, db, gasto, jobs, llm
from ..connectors import zernio
from ..modules import edicion as motor
from . import aprobaciones as ap
from . import guionista, produccion
from . import kit as kit_marca

AGENTE = "publicador"
REDES = {"instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube", "linkedin": "LinkedIn"}
LIMITE_TEXTO = {"instagram": 2200, "tiktok": 2200, "youtube": 5000, "linkedin": 3000}
MAX_HASHTAGS_IG = 30
MARGEN_MINUTOS = 30          # el primer hueco posible, contando desde ahora
DURACION_MAX = {"instagram": 900, "tiktok": 600, "youtube": 180, "linkedin": 600}  # en segundos (YouTube: un Short)
ENLACE_EN_TEXTO = ("youtube", "linkedin")          # donde un enlace en el texto se puede pulsar
CON_HASHTAGS = ("instagram", "tiktok")
HASHTAGS_MIN, HASHTAGS_MAX = 3, 5
ESTADOS = {"programada": "Programada", "tu_publicas": "Te toca publicarlo", "publicada": "Publicada",
           "fallida": "Ha fallado", "cancelada": "Cancelada"}
VIVAS = ("programada", "tu_publicas", "publicada")
ZONA = ZoneInfo(os.getenv("RADAR_ZONA") or "Europe/Madrid")
PORTADA_SEGUNDO = 0.5        # el fotograma de la portada: el titular ya está en pantalla


def _ahora() -> datetime:
    """La hora de España, sin zona (como se guarda en la base de datos)."""
    return datetime.now(ZONA).replace(second=0, microsecond=0, tzinfo=None)


# ---------------------------------------------------------------- la conexión con Zernio

def conexion(negocio_id: int) -> dict:
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM conexiones WHERE negocio_id = ? AND servicio = 'zernio'", (negocio_id,)).fetchone()
    return json.loads(f["datos"]) if f else {}


def _guardar_conexion(negocio_id: int, datos: dict):
    with db.conexion() as con:
        con.execute("INSERT INTO conexiones (negocio_id, servicio, actualizado, datos) VALUES (?, 'zernio', ?, ?) "
                    "ON CONFLICT(negocio_id, servicio) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
                    (negocio_id, _ahora().isoformat(), json.dumps(datos, ensure_ascii=False)))


def clave(negocio_id: int) -> str:
    """La clave del negocio o, si no tiene, la del proyecto (ZERNIO_API_KEY)."""
    return conexion(negocio_id).get("clave") or zernio.clave_por_defecto()


def conectado(negocio_id: int) -> bool:
    return bool(clave(negocio_id))


def conectar(negocio_id: int, clave_nueva: str = "", perfil: str = "") -> dict:
    """Guarda la clave (si llega) y comprueba qué cuentas ve Zernio. La clave no se vuelve a enseñar."""
    actual = conexion(negocio_id)
    datos = {**actual, **({"clave": clave_nueva.strip()} if clave_nueva.strip() else {}), "perfil": perfil.strip()
             if perfil.strip() or clave_nueva.strip() else actual.get("perfil", "")}
    lista = zernio.cuentas(datos.get("clave") or zernio.clave_por_defecto(), datos.get("perfil", ""))
    datos.update(cuentas=lista, comprobado=_ahora().isoformat())
    _guardar_conexion(negocio_id, datos)
    return datos


def cuenta_de(negocio_id: int, red: str) -> dict | None:
    """La cuenta conectada para esa red. Si hay varias, la que coincide con tu usuario de la ficha."""
    candidatas = [c for c in conexion(negocio_id).get("cuentas") or [] if c["plataforma"] == red]
    if not candidatas:
        return None
    neg = db.negocio(negocio_id) or {"ficha": {}}
    mio = re.sub(r"^@|.*\.com/@?", "", str(neg["ficha"].get(red) or "")).strip("/").lower()
    return next((c for c in candidatas if mio and c["usuario"].lower() == mio), candidatas[0])


# ---------------------------------------------------------------- colaboradores (Instagram)

MAX_COLABORADORES = 3     # lo que admite Instagram
AJUSTES_VIDEO = "publi.json"


def limpiar_colaboradores(lista) -> list[str]:
    """Usuarios de Instagram válidos, sin @ ni repetidos, como mucho 3."""
    if isinstance(lista, str):
        lista = re.split(r"[\s,;]+", lista)
    salida = []
    for u in lista or []:
        u = re.sub(r"^.*instagram\.com/|^@|/.*$", "", str(u).strip()).lower()
        if re.fullmatch(r"[a-z0-9._]{1,30}", u) and u not in salida:
            salida.append(u)
    return salida[:MAX_COLABORADORES]


def _ajustes_video(edicion_id: int) -> dict:
    ruta = motor.carpeta(edicion_id) / AJUSTES_VIDEO
    try:
        return json.loads(ruta.read_text()) if ruta.exists() else {}
    except ValueError:
        return {}


def poner_colaboradores(negocio_id: int, edicion_id: int, lista) -> list[str]:
    """Los colaboradores de este vídeo (sustituyen a los del plan). Una lista vacía vuelve a los del plan."""
    ed = db.edicion(edicion_id)
    if not ed or ed["negocio_id"] != negocio_id:
        return []
    datos = {**_ajustes_video(edicion_id), "colaboradores": limpiar_colaboradores(lista)}
    if not datos["colaboradores"]:
        datos.pop("colaboradores")
    (motor.carpeta(edicion_id) / AJUSTES_VIDEO).write_text(json.dumps(datos, ensure_ascii=False))
    return datos.get("colaboradores", [])


def colaboradores(negocio_id: int, edicion_id: int | None, kit: dict | None = None) -> list[str]:
    """Los del vídeo o, si no tiene, los del plan de Instagram. Nunca la propia cuenta."""
    propios = _ajustes_video(edicion_id).get("colaboradores") if edicion_id else None
    lista = limpiar_colaboradores(propios if propios is not None else
                                  (kit or kit_marca.leer(negocio_id))["publicacion"]["instagram"].get("colaboradores"))
    mia = (cuenta_de(negocio_id, "instagram") or {}).get("usuario", "").lower()
    return [u for u in lista if u != mia]


def estado_cuentas(negocio_id: int) -> list[dict]:
    """Cada red del plan con su cuenta: conectada, a reconectar o sin conectar."""
    plan = kit_marca.leer(negocio_id)["publicacion"]
    salida = []
    for red, nombre in REDES.items():
        c = cuenta_de(negocio_id, red)
        estado = "sin_conectar" if not c else ("reconectar" if c["reconectar"] or not c["activa"] else "conectada")
        salida.append({"red": red, "nombre": nombre, "cuenta": c, "estado": estado, "activa": plan[red]["activa"]})
    return salida


# ---------------------------------------------------------------- huecos

def ocupados(negocio_id: int, red: str) -> set[str]:
    with db.conexion() as con:
        return {f["programado"][:16] for f in con.execute(
            f"SELECT programado FROM publicaciones WHERE negocio_id = ? AND plataforma = ? AND modo != 'prueba' AND "
            f"estado IN ({','.join('?' * len(VIVAS))})", (negocio_id, red, *VIVAS))}


def proximo_hueco(negocio_id: int, red: str, *, despues: datetime | None = None, tomados: set[str] | None = None) -> datetime | None:
    plan = kit_marca.leer(negocio_id)["publicacion"].get(red) or {}
    horas = sorted(h for h in plan.get("horas") or [] if re.fullmatch(r"\d{2}:\d{2}", h))
    if not plan.get("dias") or not horas:
        return None
    desde = despues or (_ahora() + timedelta(minutes=MARGEN_MINUTOS))
    usados = ocupados(negocio_id, red) | (tomados or set())
    dia = desde.date()
    for _ in range(60):
        if dia.weekday() in plan["dias"]:
            for h in horas:
                momento = datetime.fromisoformat(f"{dia.isoformat()}T{h}")
                if momento >= desde and momento.isoformat()[:16] not in usados:
                    return momento
        dia += timedelta(days=1)
    return None


# ---------------------------------------------------------------- lo que se publica

def videos_aprobados(negocio_id: int) -> list[dict]:
    """Vídeos aprobados en Producción, con sus publicaciones."""
    salida = []
    for ed in db.ediciones_de(negocio_id):
        p = (ed.get("datos") or {}).get("produccion") or {}
        if not p.get("aprobado"):
            continue
        ed["publicaciones"] = publicaciones(negocio_id, edicion_id=ed["id"])
        ed["guion"] = guionista.guion(negocio_id, p["guion_id"]) if p.get("guion_id") else None
        ed["toma"] = p
        salida.append(ed)
    return salida


def publicaciones(negocio_id: int, *, edicion_id: int | None = None, desde: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM publicaciones WHERE negocio_id = ?", [negocio_id]
    if edicion_id:
        sql += " AND edicion_id = ?"
        args.append(edicion_id)
    if desde:
        sql += " AND programado >= ?"
        args.append(desde)
    with db.conexion() as con:
        filas = [dict(f) for f in con.execute(sql + " ORDER BY programado", args)]
    for f in filas:
        f["red_nombre"] = REDES.get(f["plataforma"], f["plataforma"])
        f["estado_nombre"] = ESTADOS.get(f["estado"], f["estado"])
    return filas


def numero_de_pieza(negocio_id: int, edicion_id: int) -> int:
    """El número de la pieza en los enlaces: el mismo en todas sus redes. Se da al publicarla por primera vez."""
    with db.conexion() as con:
        filas = con.execute("SELECT edicion_id, utm FROM publicaciones WHERE negocio_id = ? AND utm != ''",
                            (negocio_id,)).fetchall()
    numeros = {}
    for f in filas:
        m = re.search(r"utm_content=[^&]*_(\d+)(?:&|$)", f["utm"])
        if m:
            numeros.setdefault(f["edicion_id"], int(m.group(1)))
    return numeros.get(edicion_id) or max(numeros.values(), default=0) + 1


def enlace_seguimiento(web: str, palabra: str, numero: int, red: str, prefijo: str = "") -> str:
    web = (web or "").strip()
    if not web:
        return ""
    if not web.startswith("http"):
        web = "https://" + web
    sep = "&" if "?" in web else "?"
    return web + sep + urlencode({"utm_source": red, "utm_medium": "social",
                                  "utm_content": f"{prefijo}{(palabra or 'post').lower()}_{numero}"})


def _web(negocio_id: int, kit: dict | None = None) -> tuple[str, str]:
    """La web de destino y el prefijo de los enlaces: los del Kit o, si no hay, la web de la ficha."""
    cta = (kit or kit_marca.leer(negocio_id)).get("cta") or {}
    neg = db.negocio(negocio_id) or {"ficha": {}}
    return (cta.get("web") or neg["ficha"].get("web") or "").strip(), cta.get("prefijo_utm") or ""


def hashtags(ed: dict, kit: dict) -> list[str]:
    """De 3 a 5: los del tema de la pieza (los de Escri) y, para completar, los de la lista del Kit. Cada pieza
    empieza la lista del Kit en un sitio distinto para no repetir siempre los mismos."""
    def limpio(h):
        h = re.sub(r"[^\wáéíóúñü]", "", str(h).lstrip("#")).lower()
        return f"#{h}" if h else ""
    propios = [limpio(h) for h in (ed.get("guion") or {}).get("hashtags") or []]
    lista = [limpio(h) for h in kit.get("hashtags") or []]
    if lista:
        giro = (ed.get("id") or 0) % len(lista)
        lista = lista[giro:] + lista[:giro]
    return [h for h in dict.fromkeys(propios + lista) if h][:HASHTAGS_MAX]


def _humanizar(texto: str, palabra: str = "") -> str:
    """El humanizador de Escri: quita caracteres invisibles, rayas y palabrería de IA. La palabra clave no se toca."""
    try:
        from . import humanizador
    except ImportError:
        return texto
    try:
        return humanizador.limpiar(texto, respetar=[palabra] if palabra else [])[0] or texto
    except Exception:  # noqa: BLE001 — si falla, el texto sale como estaba
        return texto


def texto_final(texto: str, red: str, *, palabra: str = "", utm: str = "", etiquetas: list[str] | None = None) -> str:
    """El texto tal como sale en esa red. Se puede pasar dos veces sin que cambie (el del formulario ya viene así).
    - Fuera de Instagram se quitan las líneas que piden la palabra clave y va la del enlace.
    - Los hashtags: si el texto ya trae de 3 a 5, se respetan; si no, van los de la pieza."""
    texto = _humanizar(texto.strip(), palabra)
    lineas = texto.split("\n")
    if red != "instagram" and palabra:
        lineas = [x for x in lineas if not re.search(rf"\b{re.escape(palabra)}\b", x, re.I)]
    actuales = re.findall(r"#\w+", "\n".join(lineas))
    if red in CON_HASHTAGS and HASHTAGS_MIN <= len(actuales) <= HASHTAGS_MAX:
        etiquetas = actuales
    lineas = [re.sub(r"(^|\s)#\w+", "", x).rstrip() for x in lineas]
    cuerpo = re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()
    partes = [cuerpo]
    if red in ENLACE_EN_TEXTO and utm and utm not in cuerpo:
        partes.append(f"Más aquí: {utm}")
    elif red == "tiktok" and utm and "bio" not in cuerpo.lower():
        partes.append("Enlace en la bio.")
    if red in CON_HASHTAGS and etiquetas:
        partes.append(" ".join(etiquetas))
    return "\n\n".join(x for x in partes if x).strip()


# ---------------------------------------------------------------- los textos de cada reel

TEXTOS_REEL = "textos_publi.json"
_PREPARANDO: set[int] = set()

ESQUEMA_TEXTOS = llm.obj(titulo_youtube=llm.S, instagram=llm.S, tiktok=llm.S, youtube=llm.S, linkedin=llm.S)

SISTEMA_TEXTOS = """Eres Publi, quien publica los reels del dueño de una marca personal en español. Escribes el texto
que acompaña a UN reel en cada red. El reel es un trozo de una grabación más larga: escribe sobre lo que se dice en
ESE trozo, no sobre la idea general de la grabación.

Reglas:
- La primera línea engancha con lo que dice el reel (su gancho o su giro), con sus palabras; nada de «En este vídeo…».
- Breve: Instagram y TikTok, de 2 a 5 líneas cortas; YouTube, 1 o 2 frases; LinkedIn, algo más largo (hasta 8
  líneas) y sin hashtags.
- Cierre: en Instagram, si hay palabra clave, pide comentarla («Comenta PALABRA y te lo mando»). Fuera de Instagram
  NO menciones la palabra clave (los mensajes automáticos solo funcionan allí): cierra con una pregunta o invitando a
  seguir la cuenta; el enlace lo añade Publi.
- No pongas hashtags ni enlaces: los añade Publi.
- «titulo_youtube»: el título del Short, de 40 a 70 caracteres, sin hashtags ni comillas; tiene que dar ganas de verlo.
- Cumple la voz y lo que nunca dice el Kit de marca. Sin cifras que no salgan del reel, sin clientes con nombre, sin
  emojis de relleno ni frases hechas («al siguiente nivel», «no es solo…»)."""


def _tramo(ed: dict) -> list[dict]:
    """Las frases que se quedan en este reel."""
    return [f for f in (ed.get("datos") or {}).get("frases") or [] if not f.get("quitada") and f.get("texto")]


def _reel(ed: dict) -> dict:
    return (ed.get("datos") or {}).get("reel") or (ed.get("toma") or {}).get("reel") or {}


def titulo_reel(ed: dict) -> str:
    """El título del reel, sin el «Reel 2 de 4 · » de delante."""
    return (_reel(ed).get("titulo") or re.sub(r"^Reel \d+ de \d+ · ", "", ed.get("titulo") or "")).strip()


def _gancho(ed: dict) -> str:
    tramo = _tramo(ed)
    gancho = next((f for f in tramo if f.get("id") == _reel(ed).get("gancho")), tramo[0] if tramo else None)
    return (gancho or {}).get("texto", "").strip()


def textos_guardados(edicion_id: int) -> dict:
    ruta = motor.carpeta(edicion_id) / TEXTOS_REEL
    try:
        return json.loads(ruta.read_text()) if ruta.exists() else {}
    except ValueError:
        return {}


def _cierre(g: dict, red: str) -> str:
    """La palabra clave solo sirve en Instagram (ManyChat): fuera, el cierre es el enlace, que pone texto_final."""
    palabra = g.get("palabra_clave") or ""
    if red != "instagram" or not palabra or g.get("cta") not in ("comentar", "mensaje"):
        return ""
    return f"Comenta {palabra} y te lo mando." if g.get("cta") == "comentar" else f"Escríbeme {palabra} por privado."


def preparar_textos(negocio_id: int, edicion_id: int, *, rehacer: bool = False) -> dict:
    """Escribe con Claude el texto de cada red para este reel, a partir de lo que dice en su tramo. Se guarda junto al
    vídeo: así se escribe una vez y la página no espera. Sin Claude o sin transcripción, no hace nada."""
    if not rehacer and textos_guardados(edicion_id):
        return textos_guardados(edicion_id)
    ed = next((v for v in videos_aprobados(negocio_id) if v["id"] == edicion_id), None)
    if not ed or not _tramo(ed) or not llm.disponible():
        return {}
    g, neg = ed.get("guion") or {}, db.negocio(negocio_id)
    peticion = "\n\n".join(x for x in (
        kit_marca.contexto(neg),
        f"## El reel\nTítulo: {titulo_reel(ed)}\nGancho: {_gancho(ed)}\nLo que dice:\n"
        + " ".join(f["texto"] for f in _tramo(ed))[:6000],
        f"## La grabación de la que sale\nIdea: {(g.get('texto') or '').splitlines()[0][:300] if g.get('texto') else ''}",
        f"## Cierre\nPalabra clave: {g.get('palabra_clave') or '(ninguna)'}\nLlamada: {g.get('cta') or '(ninguna)'}\n"
        f"Hashtags: {' '.join(g.get('hashtags') or []) or '(ninguno)'}") if x)
    gasto.empezar()
    gasto_id = db.abrir_gasto(usuario_id=None, negocio_id=negocio_id, concepto=AGENTE, referencia=edicion_id)
    try:
        datos = llm.json_con_esquema(SISTEMA_TEXTOS, peticion, ESQUEMA_TEXTOS, effort="low")
    except llm.ErrorIA:
        return {}
    finally:
        db.cerrar_gasto(gasto_id, gasto.uso())
    textos = {}
    for red in REDES:
        t = str(datos.get(red) or "").strip()
        cierre = _cierre(g, red)
        if t and cierre and g["palabra_clave"].upper() not in t.upper():
            t += f"\n\n{cierre}"
        if t and len(t) <= LIMITE_TEXTO[red]:
            textos[red] = t
    if datos.get("titulo_youtube"):
        textos["titulo_youtube"] = str(datos["titulo_youtube"]).strip().strip('"«»')[:99]
    if textos:
        (motor.carpeta(edicion_id) / TEXTOS_REEL).write_text(json.dumps(textos, ensure_ascii=False, indent=1))
    return textos


def _preparar_en_segundo_plano(negocio_id: int, edicion_id: int, despues=None):
    if edicion_id in _PREPARANDO:
        return
    _PREPARANDO.add(edicion_id)

    def trabajo():
        try:
            preparar_textos(negocio_id, edicion_id)
            if despues:
                despues()
        finally:
            _PREPARANDO.discard(edicion_id)
    jobs.en_segundo_plano(trabajo)


def preparar_los_que_falten(negocio_id: int, videos: list[dict] | None = None):
    """Al abrir Publicación: los vídeos aprobados que aún no tienen sus textos, a prepararlos sin esperar."""
    if not llm.disponible():
        return
    for v in videos if videos is not None else videos_aprobados(negocio_id):
        if not textos_guardados(v["id"]) and _tramo(v):
            _preparar_en_segundo_plano(negocio_id, v["id"])


def _texto_base(ed: dict, red: str) -> str:
    """El que Publi escribió para este reel; si el vídeo es la grabación entera, el de Escri; y si no, uno sencillo con
    el gancho del reel y su cierre."""
    propio = textos_guardados(ed["id"]).get(red) if ed.get("id") else ""
    if propio:
        return propio.strip()
    g = ed.get("guion") or {}
    if (_reel(ed).get("de") or 1) <= 1 and (g.get("textos") or {}).get(red):
        return g["textos"][red].strip()
    primera = (_gancho(ed) or titulo_reel(ed))[:300]
    return "\n\n".join(x for x in (primera, _cierre(g, red)) if x).strip()


def texto_para(ed: dict, red: str, *, kit: dict | None = None) -> str:
    """El texto del post en esa red, ya como sale: con su enlace, sus hashtags y sin la palabra clave fuera de
    Instagram."""
    nid = ed["negocio_id"]
    kit = kit or kit_marca.leer(nid)
    g = ed.get("guion") or {}
    web, prefijo = _web(nid, kit)
    utm = enlace_seguimiento(web, g.get("palabra_clave", ""), numero_de_pieza(nid, ed["id"]), red, prefijo)
    return texto_final(_texto_base(ed, red), red, palabra=g.get("palabra_clave", ""), utm=utm,
                       etiquetas=hashtags(ed, kit))


def duracion(ruta: Path) -> float | None:
    """Los segundos del vídeo (None si no se puede medir: entonces no se comprueba)."""
    try:
        r = subprocess.run([config.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(ruta)], capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
        return None


def comprobar(negocio_id: int, red: str, texto: str, ed: dict, *, modo: str, momento: datetime | None = None,
              titulo: str = "") -> list[str]:
    """Lo que se mira antes de mandar nada a Zernio."""
    fallos = []
    video = motor.carpeta(ed["id"]) / "final.mp4"
    if not video.exists():
        fallos.append("No se encuentra el vídeo montado.")
    else:
        segundos = duracion(video)
        if segundos and segundos > DURACION_MAX[red]:
            fallos.append(f"El vídeo dura {segundos:.0f} s y {REDES[red]} admite {DURACION_MAX[red]} s"
                          + (" en un Short." if red == "youtube" else "."))
    if momento and momento < _ahora():
        fallos.append("Esa hora ya ha pasado.")
    if red == "youtube" and modo == "zernio" and not titulo.strip():
        fallos.append("Falta el título de YouTube.")
    if not texto.strip():
        fallos.append("Falta el texto del post.")
    if len(texto) > LIMITE_TEXTO[red]:
        fallos.append(f"El texto pasa de {LIMITE_TEXTO[red]} caracteres.")
    if red == "instagram" and len(re.findall(r"#\w", texto)) > MAX_HASHTAGS_IG:
        fallos.append("Instagram no admite más de 30 hashtags.")
    if modo == "zernio":
        c = cuenta_de(negocio_id, red)
        if not conectado(negocio_id):
            fallos.append("Falta conectar Zernio.")
        elif not c:
            fallos.append(f"No hay ninguna cuenta de {REDES[red]} conectada en Zernio.")
        elif c["reconectar"] or not c["activa"]:
            fallos.append(f"La cuenta de {REDES[red]} @{c['usuario']} hay que reconectarla en Zernio.")
    return fallos


def _clave_unica(negocio_id: int, edicion_id: int, version: int, red: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"radar:{negocio_id}:{edicion_id}:v{version}:{red}"))


def _zona(nombre: str = "") -> ZoneInfo:
    """La zona horaria del negocio (Kit) o, si no hay o no existe, la de la instalación."""
    try:
        return ZoneInfo(nombre) if nombre else ZONA
    except (ValueError, KeyError):
        return ZONA


def portada(edicion_id: int) -> Path | None:
    """La portada a tamaño completo, sacada del vídeo final (la de Monti es pequeña, para la app)."""
    dir_ = motor.carpeta(edicion_id)
    final, salida = dir_ / "final.mp4", dir_ / "portada_redes.jpg"
    if salida.exists() and final.exists() and salida.stat().st_mtime >= final.stat().st_mtime:
        return salida
    try:
        subprocess.run([config.FFMPEG, "-y", "-v", "error", "-ss", str(PORTADA_SEGUNDO), "-i", str(final), "-frames:v", "1",
                        "-q:v", "2", str(salida)], check=True, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    return salida if salida.exists() else None


def _cuerpo(red: str, cuenta: str, texto: str, url_video: str, cuando: datetime, titulo: str, clave_unica: str,
            url_portada: str = "", *, zona: str = "", prueba: bool = False, colaboradores: list[str] | None = None) -> dict:
    especifico, video = {}, {"type": "video", "url": url_video}
    if red == "youtube":
        especifico = {"title": (titulo or texto.split("\n")[0])[:99], "visibility": "public", "madeForKids": False}
    elif red == "tiktok":
        # Lo ha aprobado una persona: se marca el consentimiento que pide TikTok.
        especifico = {"privacyLevel": "PUBLIC_TO_EVERYONE", "allowComment": True, "contentPreviewConfirmed": True,
                      "expressConsentGiven": True, "videoCoverTimestampMs": int(PORTADA_SEGUNDO * 1000)}
    elif red == "instagram" and prueba:
        # Reel de prueba: Instagram lo enseña a quien no te sigue y no va a tu perfil. Pasarlo a normal, a mano.
        especifico = {"trialParams": {"graduationStrategy": "MANUAL"}}
    elif red == "instagram":
        especifico = {"shareToFeed": True, **({"collaborators": colaboradores} if colaboradores else {})}
        if url_portada:
            video["instagramThumbnail"] = url_portada
    elif red == "linkedin" and url_portada:
        video["thumbnail"] = url_portada
    zona_ = _zona(zona)
    return {"content": texto, "mediaItems": [video],
            "platforms": [{"platform": red, "accountId": cuenta, "platformSpecificData": especifico}],
            "scheduledFor": cuando.replace(tzinfo=zona_).isoformat(), "timezone": zona_.key,
            "metadata": {"radarClave": clave_unica}}


def programar(negocio_id: int, edicion_id: int, redes: list[str], *, cuando: datetime | None = None,
              textos: dict[str, str] | None = None, ensayo: bool = False) -> dict:
    """Programa el vídeo en cada red, en su siguiente hueco (o a la hora que digas). Devuelve {programadas, fallos}.
    Con `ensayo`, no manda ni guarda nada: devuelve también `plan`, con lo que saldría en cada red."""
    ed = next((v for v in videos_aprobados(negocio_id) if v["id"] == edicion_id), None)
    if not ed:
        return {"programadas": [], "fallos": ["Ese vídeo no está aprobado."], "plan": []}
    kit = kit_marca.leer(negocio_id)
    plan = kit["publicacion"]
    version = ed["toma"].get("version", 1)
    g = ed.get("guion") or {}
    neg = db.negocio(negocio_id)
    web, prefijo = _web(negocio_id, kit)
    numero, etiquetas = numero_de_pieza(negocio_id, edicion_id), hashtags(ed, kit)
    titulo = textos_guardados(edicion_id).get("titulo_youtube") or titulo_reel(ed)
    colabs = colaboradores(negocio_id, edicion_id, kit)
    programadas, fallos, ensayado, url_video, url_portada = [], [], [], None, None
    for red in [r for r in redes if r in REDES]:
        unica = _clave_unica(negocio_id, edicion_id, version, red)
        with db.conexion() as con:
            ya = con.execute("SELECT estado FROM publicaciones WHERE negocio_id = ? AND clave_unica = ?",
                             (negocio_id, unica)).fetchone()
        if ya and ya["estado"] in VIVAS:
            continue  # nunca dos veces
        modo = "zernio" if (red != "instagram" or plan["instagram"].get("autopublicar")) else "tu"
        utm = enlace_seguimiento(web, g.get("palabra_clave", ""), numero, red, prefijo)
        texto = texto_final((textos or {}).get(red) or _texto_base(ed, red), red, palabra=g.get("palabra_clave", ""),
                            utm=utm, etiquetas=etiquetas)
        momento = cuando or proximo_hueco(negocio_id, red)
        problemas = comprobar(negocio_id, red, texto, ed, modo=modo, momento=momento, titulo=titulo) + (
            [] if momento else [f"No hay huecos de publicación para {REDES[red]}: revisa sus días y horas."])
        if red in CON_HASHTAGS and len(re.findall(r"#\w+", texto)) < HASHTAGS_MIN:
            aviso = f"Lleva menos de {HASHTAGS_MIN} hashtags: añade los de tu nicho en el Kit."
        else:
            aviso = ""
        if ensayo:
            ensayado.append({"red": red, "red_nombre": REDES[red], "cuando": momento, "modo": modo, "texto": texto,
                             "utm": utm, "titulo": titulo if red == "youtube" else "", "problemas": problemas,
                             "colaboradores": colabs if red == "instagram" else [],
                             "aviso": aviso})
            continue
        if problemas:
            fallos.append(f"{REDES[red]}: " + " ".join(problemas))
            continue
        externo, estado = "", "tu_publicas" if modo == "tu" else "programada"
        if modo == "zernio":
            try:
                url_video = url_video or zernio.subir_video(clave(negocio_id), motor.carpeta(edicion_id) / "final.mp4")
                if url_portada is None and red in ("instagram", "linkedin"):
                    url_portada = _subir_portada(negocio_id, edicion_id)
                r = zernio.crear_post(clave(negocio_id), _cuerpo(red, cuenta_de(negocio_id, red)["id"], texto, url_video,
                                                                 momento, titulo, unica, url_portada or "",
                                                                 zona=kit.get("zona", ""), colaboradores=colabs), unica)
                externo = r["id"]
            except zernio.ErrorZernio as e:
                fallos.append(f"{REDES[red]}: {e}")
                continue
        with db.conexion() as con:
            con.execute(
                "INSERT INTO publicaciones (negocio_id, edicion_id, guion_id, creado, plataforma, cuenta, texto, programado, "
                "modo, estado, clave_unica, externo_id, utm) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(negocio_id, clave_unica) DO UPDATE SET estado = excluded.estado, programado = excluded.programado, "
                "texto = excluded.texto, externo_id = excluded.externo_id, utm = excluded.utm, error = ''",
                (negocio_id, edicion_id, g.get("id"), _ahora().isoformat(), red,
                 (cuenta_de(negocio_id, red) or {}).get("id", ""), texto, momento.isoformat(timespec="minutes"), modo, estado,
                 unica, externo, utm))
        programadas.append({"red": red, "cuando": momento, "modo": modo})
    if ensayo:
        return {"programadas": [], "fallos": [], "plan": ensayado}
    if any(p["red"] == "instagram" for p in programadas) and g.get("cta") in ("comentar", "mensaje"):
        # La palabra clave ya tiene vídeo en Instagram: Chati prepara su guía para que ManyChat la mande.
        from . import comunidad
        jobs.en_segundo_plano(comunidad.sincronizar_automatizaciones, neg)
    return {"programadas": programadas, "fallos": fallos, "plan": []}


def _subir_portada(negocio_id: int, edicion_id: int) -> str:
    """Sin portada el post sale igual (con el fotograma que elija la red): un fallo aquí no para nada."""
    ruta = portada(edicion_id)
    if not ruta:
        return ""
    try:
        return zernio.subir_imagen(clave(negocio_id), ruta)
    except zernio.ErrorZernio:
        return ""


def emparejar_instagram(negocio_id: int, ahora: datetime | None = None) -> int:
    """Lo que publicas tú en Instagram, sin pegar el enlace: Lupi escanea tu cuenta y aquí se reconoce cada post por
    la hora (de 12 h antes a 2 días después de su hueco) y por el texto (la palabra clave o las mismas palabras).
    Queda publicada, con su enlace, y Resultados ya puede medirla. Devuelve cuántas ha emparejado."""
    from . import estratega
    ahora = ahora or _ahora()
    with db.conexion() as con:
        pendientes = [dict(f) for f in con.execute(
            "SELECT p.*, g.palabra_clave FROM publicaciones p LEFT JOIN guiones g ON g.id = p.guion_id WHERE "
            "p.negocio_id = ? AND p.plataforma = 'instagram' AND p.estado = 'tu_publicas' AND p.programado <= ?",
            (negocio_id, (ahora + timedelta(hours=2)).isoformat(timespec="minutes")))]
        if not pendientes:
            return 0
        usadas = {f[0] for f in con.execute("SELECT url FROM publicaciones WHERE negocio_id = ? AND url != ''", (negocio_id,))}
        mios = [dict(f) for f in con.execute(
            "SELECT p.url, p.publicado, p.texto FROM posts p JOIN cuentas c ON c.id = p.cuenta_id WHERE p.negocio_id = ? "
            "AND c.propia = 1 AND c.plataforma = 'instagram' AND p.publicado != ''", (negocio_id,))]
    hechas = 0
    for pub in sorted(pendientes, key=lambda x: x["programado"]):
        hueco = datetime.fromisoformat(pub["programado"])
        palabras_pub = estratega.palabras(pub["texto"])
        mejor, nota_mejor = None, 0.0
        for post in mios:
            if post["url"] in usadas:
                continue
            try:
                cuando = datetime.fromisoformat(post["publicado"][:19])
            except ValueError:
                continue
            if not hueco - timedelta(hours=12) <= cuando <= hueco + timedelta(days=2):
                continue
            palabra = (pub.get("palabra_clave") or "").upper()
            nota = 1.0 if palabra and re.search(rf"\b{re.escape(palabra)}\b", post["texto"].upper()) else \
                estratega._parecido(palabras_pub, estratega.palabras(post["texto"]))
            if nota > nota_mejor:
                mejor, nota_mejor = post, nota
        if mejor and nota_mejor >= 0.5:
            with db.conexion() as con:
                con.execute("UPDATE publicaciones SET estado = 'publicada', url = ? WHERE id = ? AND estado = 'tu_publicas'",
                            (mejor["url"], pub["id"]))
            usadas.add(mejor["url"])
            hechas += 1
    return hechas


def marcar_publicada(negocio_id: int, publicacion_id: int, url: str = ""):
    with db.conexion() as con:
        con.execute("UPDATE publicaciones SET estado = 'publicada', url = COALESCE(NULLIF(?, ''), url) "
                    "WHERE negocio_id = ? AND id = ?", (url.strip(), negocio_id, publicacion_id))


def cancelar(negocio_id: int, publicacion_id: int) -> str:
    with db.conexion() as con:
        p = con.execute("SELECT * FROM publicaciones WHERE negocio_id = ? AND id = ?", (negocio_id, publicacion_id)).fetchone()
    if not p or p["estado"] not in ("programada", "tu_publicas", "fallida"):
        return "Esa publicación ya no se puede cancelar."
    if p["externo_id"]:
        try:
            zernio.cancelar(clave(negocio_id), p["externo_id"])
        except zernio.ErrorZernio as e:
            return f"Zernio no la ha cancelado: {e}"
    with db.conexion() as con:
        con.execute("UPDATE publicaciones SET estado = 'cancelada' WHERE id = ?", (publicacion_id,))
    return ""


def actualizar_estados(negocio_id: int, limite: int = 15) -> int:
    """Pregunta a Zernio por las publicaciones cuya hora ya ha pasado: publicada (con su enlace) o fallida."""
    if not conectado(negocio_id):
        return 0
    with db.conexion() as con:
        pendientes = con.execute("SELECT * FROM publicaciones WHERE negocio_id = ? AND estado = 'programada' AND "
                                 "externo_id != '' AND programado <= ? ORDER BY programado LIMIT ?",
                                 (negocio_id, _ahora().isoformat(timespec="minutes"), limite)).fetchall()
    cambiadas = 0
    for p in pendientes:
        try:
            r = zernio.post(clave(negocio_id), p["externo_id"])
        except zernio.ErrorZernio:
            continue
        nuevo = {"published": "publicada", "failed": "fallida", "cancelled": "cancelada"}.get(r["estado"]) or \
            {"published": "publicada", "failed": "fallida"}.get(r["estado_plataforma"])
        if nuevo:
            with db.conexion() as con:
                con.execute("UPDATE publicaciones SET estado = ?, url = ?, error = ? WHERE id = ?",
                            (nuevo, r["url"], r["error"], p["id"]))
            cambiadas += 1
    return cambiadas


def te_toca(negocio_id: int, *, antes_minutos: int = 60) -> list[dict]:
    """Las de Instagram que publicas tú y cuya hora está cerca o ya ha pasado. Cada una lleva `colaboradores` (a
    quién invitar al publicar) y `aviso_colaboradores`, la línea lista para el recordatorio."""
    limite = (_ahora() + timedelta(minutes=antes_minutos)).isoformat(timespec="minutes")
    salida = [p for p in publicaciones(negocio_id) if p["estado"] == "tu_publicas" and p["programado"] <= limite]
    for p in salida:
        p["colaboradores"] = colaboradores(negocio_id, p["edicion_id"])
        p["aviso_colaboradores"] = (
            "Antes de compartir: Etiquetar personas → Invitar colaborador → "
            + ", ".join(f"@{u}" for u in p["colaboradores"]) + "." if p["colaboradores"] else "")
    return salida


# ---------------------------------------------------------------- a qué hora publicar

MIN_POSTS_HORAS = 10      # menos posts propios con fecha y vistas, y no hay datos para fiarse
DIAS_HORAS = 180


def _hora_local(publicado: str, zona: ZoneInfo) -> datetime | None:
    try:
        d = datetime.fromisoformat(publicado.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(zona).replace(tzinfo=None) if d.tzinfo else d


def mejores_horas(negocio_id: int, red: str = "instagram") -> dict:
    """A qué hora rinden más tus posts: la mediana de «veces lo normal de tu cuenta» por hora del día (y por día de
    la semana). Devuelve {fuente, posts, horas: [«HH:00»…] (las mejores primero), por_dia: {0-6: «HH:00»}}."""
    kit = kit_marca.leer(negocio_id)
    zona = _zona(kit.get("zona", ""))
    desde = (_ahora() - timedelta(days=DIAS_HORAS)).isoformat()
    with db.conexion() as con:
        filas = con.execute(
            "SELECT p.publicado, p.vistas, p.x FROM posts p JOIN cuentas c ON c.id = p.cuenta_id WHERE p.negocio_id = ? "
            "AND c.propia = 1 AND c.plataforma = ? AND p.publicado != '' AND p.vistas > 0", (negocio_id, red)).fetchall()
    puntos = []
    mediana = statistics.median([f["vistas"] for f in filas]) if filas else 0
    for f in filas:
        cuando = _hora_local(f["publicado"], zona)
        if cuando and cuando.isoformat() >= desde[:19]:
            puntos.append((cuando, f["x"] or f["vistas"] / max(mediana, 1)))
    plan = sorted((kit["publicacion"].get(red) or {}).get("horas") or [])
    if len(puntos) < MIN_POSTS_HORAS:
        return {"fuente": "plan", "posts": len(puntos), "horas": plan, "por_dia": {}}

    def ranking(grupo):
        por_hora: dict[int, list[float]] = {}
        for cuando, x in grupo:
            por_hora.setdefault(cuando.hour, []).append(x)
        notas = {h: statistics.median(xs) for h, xs in por_hora.items() if len(xs) >= 2}
        return [f"{h:02d}:00" for h, _ in sorted(notas.items(), key=lambda kv: -kv[1])]
    por_dia = {}
    for d in range(7):
        mejor = ranking([p for p in puntos if p[0].weekday() == d])
        if mejor:
            por_dia[d] = mejor[0]
    return {"fuente": "tu cuenta", "posts": len(puntos), "horas": ranking(puntos)[:3] or plan, "por_dia": por_dia}


def proponer_horas(negocio_id: int, dias: list[date], red: str = "instagram") -> dict:
    """Una hora para cada día del calendario de Plani: la mejor de ese día de la semana si hay datos; si no, la mejor
    en general; y si tampoco, la del plan. Devuelve {fuente, posts, horas: {«AAAA-MM-DD»: «HH:MM»}}."""
    m = mejores_horas(negocio_id, red)
    defecto = (m["horas"] or ["13:30"])[0]
    return {"fuente": m["fuente"], "posts": m["posts"],
            "horas": {d.isoformat(): m["por_dia"].get(d.weekday(), defecto) for d in sorted(set(dias))}}


def calendario(negocio_id: int, dias: int = 14) -> list[tuple[str, list[dict]]]:
    desde = (_ahora() - timedelta(days=1)).date().isoformat()
    hasta = (_ahora() + timedelta(days=dias)).date().isoformat()
    por_dia: dict[str, list[dict]] = {}
    for p in publicaciones(negocio_id, desde=desde):
        if p["programado"][:10] <= hasta and p["estado"] != "cancelada":
            por_dia.setdefault(p["programado"][:10], []).append(p)
    return sorted(por_dia.items())


# ---------------------------------------------------------------- reels de prueba (Instagram)

TOPE_DIARIO = 50          # posts en 24 h en la cuenta, contando todo: más, e Instagram lo toma por spam
CARPETA_VARIANTES = "variantes"


def ajustes_prueba(negocio_id: int) -> dict:
    return kit_marca.leer(negocio_id)["reels_prueba"]  # activa, al_dia, desde, hasta y comprobado


def variantes(edicion_id: int) -> list[Path]:
    """Las variantes que ha hecho Monti para este vídeo (mismo vídeo, otra velocidad, color o título)."""
    return sorted((motor.carpeta(edicion_id) / CARPETA_VARIANTES).glob("*.mp4"))


def _posts_del_dia(negocio_id: int, dia: str) -> int:
    with db.conexion() as con:
        return con.execute("SELECT COUNT(*) FROM publicaciones WHERE negocio_id = ? AND plataforma = 'instagram' AND "
                           "substr(programado, 1, 10) = ? AND estado IN ('programada', 'tu_publicas', 'publicada')",
                           (negocio_id, dia)).fetchone()[0]


def _clave_prueba(negocio_id: int, edicion_id: int, archivo: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"radar:{negocio_id}:{edicion_id}:prueba:{archivo}"))


def _ya_programada(negocio_id: int, clave_unica: str) -> bool:
    with db.conexion() as con:
        return bool(con.execute("SELECT 1 FROM publicaciones WHERE negocio_id = ? AND clave_unica = ?",
                                (negocio_id, clave_unica)).fetchone())


def plan_de_prueba(negocio_id: int, edicion_id: int, dia: datetime | None = None) -> dict:
    """Qué reels de prueba saldrían y a qué hora, repartidos en la ventana del día. No manda nada.
    Devuelve {variantes: [{archivo, cuando, hashtags}], fallos}."""
    aj = ajustes_prueba(negocio_id)
    if not aj["activa"]:
        return {"variantes": [], "fallos": ["Los reels de prueba no están activados para este negocio."]}
    ed = next((v for v in videos_aprobados(negocio_id) if v["id"] == edicion_id), None)
    if not ed:
        return {"variantes": [], "fallos": ["Ese vídeo no está aprobado."]}
    archivos = [a for a in variantes(edicion_id) if not _ya_programada(negocio_id, _clave_prueba(negocio_id, edicion_id, a.name))]
    if not archivos:
        return {"variantes": [], "fallos": ["No hay variantes nuevas de este vídeo: Monti tiene que hacerlas."]}
    c = cuenta_de(negocio_id, "instagram")
    if not conectado(negocio_id) or not c or c["reconectar"] or not c["activa"]:
        return {"variantes": [], "fallos": ["Hace falta la cuenta de Instagram conectada en Zernio."]}
    dia = (dia or _ahora() + timedelta(days=1)).date()
    hueco = TOPE_DIARIO - _posts_del_dia(negocio_id, dia.isoformat())
    n = min(len(archivos), int(aj["al_dia"]), max(hueco, 0))
    if not aj["comprobado"]:
        n = min(n, 1)  # la primera, sola: hay que ver que no sale en el perfil
    if n <= 0:
        return {"variantes": [], "fallos": [f"Ese día ya hay {TOPE_DIARIO} posts o más en Instagram."]}
    desde = datetime.fromisoformat(f"{dia.isoformat()}T{aj['desde']}")
    hasta = datetime.fromisoformat(f"{dia.isoformat()}T{aj['hasta']}")
    paso = (hasta - desde) / n
    todos = hashtags(ed, kit_marca.leer(negocio_id)) or []
    salida = []
    for i, archivo in enumerate(archivos[:n]):
        cuando = (desde + paso * i + paso / 2).replace(second=0, microsecond=0)
        giro = i % len(todos) if todos else 0
        salida.append({"archivo": archivo.name, "cuando": cuando, "hashtags": (todos[giro:] + todos[:giro])[:HASHTAGS_MAX]})
    return {"variantes": salida, "fallos": []}


def proponer_reels_prueba(negocio_id: int, edicion_id: int, dia: datetime | None = None) -> dict:
    """Pide tu OK para el lote. Nada sale hasta que lo apruebes (aunque Publi vaya en piloto automático)."""
    plan = plan_de_prueba(negocio_id, edicion_id, dia)
    if plan["fallos"]:
        return {"aprobacion": None, "fallos": plan["fallos"]}
    vs = plan["variantes"]
    resumen = (f"{len(vs)} reel{'es' if len(vs) > 1 else ''} de prueba en Instagram el {vs[0]['cuando']:%d/%m}, "
               f"de {vs[0]['cuando']:%H:%M} a {vs[-1]['cuando']:%H:%M}")
    datos = {"edicion_id": edicion_id, "variantes": [{**v, "cuando": v["cuando"].isoformat(timespec="minutes")}
                                                     for v in vs]}
    return {"aprobacion": ap.pedir(negocio_id, AGENTE, "reels_prueba", resumen, datos, siempre=True), "fallos": []}


@ap.al_aprobar("reels_prueba")
def _programar_reels_prueba(a: dict) -> dict:
    nid, d = a["negocio_id"], a["datos"]
    ed = next((v for v in videos_aprobados(nid) if v["id"] == d.get("edicion_id")), None)
    if not ed or not ajustes_prueba(nid)["activa"]:
        return {"programadas": 0, "fallos": ["Ya no se pueden programar."]}
    g, kit = ed.get("guion") or {}, kit_marca.leer(nid)
    base = texto_final(_texto_base(ed, "instagram"), "instagram", palabra=g.get("palabra_clave", ""))
    base = re.sub(r"\n*(#\w+\s*)+$", "", base).strip()
    cuenta = cuenta_de(nid, "instagram")
    hechas, fallos = 0, []
    for v in d.get("variantes") or []:
        ruta = motor.carpeta(ed["id"]) / CARPETA_VARIANTES / v["archivo"]
        unica = _clave_prueba(nid, ed["id"], v["archivo"])
        if _ya_programada(nid, unica):
            continue  # nunca dos veces
        cuando = datetime.fromisoformat(v["cuando"])
        if not ruta.exists() or cuando < _ahora() or not cuenta:
            fallos.append(f"{v['archivo']}: no se ha podido programar (falta el vídeo, la cuenta o la hora ha pasado).")
            continue
        texto = "\n\n".join(x for x in (base, " ".join(v.get("hashtags") or [])) if x)
        try:
            url = zernio.subir_video(clave(nid), ruta)
            r = zernio.crear_post(clave(nid), _cuerpo("instagram", cuenta["id"], texto, url, cuando, "", unica,
                                                      zona=kit.get("zona", ""), prueba=True), unica)
        except zernio.ErrorZernio as e:
            fallos.append(f"{v['archivo']}: {e}")
            continue
        with db.conexion() as con:
            con.execute("INSERT INTO publicaciones (negocio_id, edicion_id, guion_id, creado, plataforma, cuenta, texto, "
                        "programado, modo, estado, clave_unica, externo_id, utm) VALUES (?, ?, ?, ?, 'instagram', ?, ?, ?, "
                        "'prueba', 'programada', ?, ?, '')",
                        (nid, ed["id"], g.get("id"), _ahora().isoformat(), cuenta["id"], texto,
                         cuando.isoformat(timespec="minutes"), unica, r["id"]))
        hechas += 1
    return {"programadas": hechas, "fallos": fallos}


def confirmar_fuera_del_perfil(negocio_id: int):
    """Solo lo dice el dueño: el primer reel de prueba salió y NO aparece en su perfil. Desde ahí, lotes enteros."""
    kit_marca.cambiar(negocio_id, reels_prueba={**ajustes_prueba(negocio_id), "comprobado": True})


# ---------------------------------------------------------------- en piloto automático

@ap.al_aprobar("video")
def _programar_si_hay_piloto(a: dict):
    """Un vídeo aprobado: Publi escribe sus textos y, en piloto automático, lo programa en todas las redes activas."""
    nid, eid = a["negocio_id"], a["datos"].get("edicion_id")
    if not eid:
        return
    produccion._video_aprobado(a)  # por si este aviso llega antes que el de producción
    despues = None
    if kit_marca.autonomia(nid, AGENTE) == "piloto":
        redes = [r for r, plan in kit_marca.leer(nid)["publicacion"].items() if plan.get("activa")]
        despues = lambda: programar(nid, eid, redes)  # noqa: E731
    if llm.disponible():
        _preparar_en_segundo_plano(nid, eid, despues)
    elif despues:
        despues()
