"""La palabra clave de Instagram sin ManyChat: alguien comenta la palabra de un reel y le llega el enlace por privado.

- Conectores → Instagram: el token de la cuenta y la clave secreta de la app de Instagram (la de Meta del negocio).
  Se guardan con el negocio y no se vuelven a enseñar.
- Meta avisa de cada comentario en /ig/<token> (la dirección que se pega en el panel de Meta, con su «verify token»).
- Las palabras: las de este conector (globales o de un reel concreto, con su enlace y, si se quiere, su mensaje y una
  respuesta pública) y, si no hay ninguna, las guías de Comunidad (Chati) con su palabra.
- Nunca dos veces a la misma persona por la misma palabra en el mismo reel, y un tope de envíos al día.
- Modo «conversación» (por defecto): Meta solo deja mandar un mensaje por comentario hasta que la persona conteste. Así
  que el primero pregunta si se lo mandamos, con un botón; al pulsarlo (o al contestar cualquier cosa) le llega el
  enlace, y una hora después una pregunta sobre el regalo (dentro de las 24 h que da su respuesta). Modo «directo»: el
  enlace en el primer mensaje y nada más.
- La cuenta de la propia instalación (la de Orby, que no es un negocio de la app) va con el número 0. Se conecta y
  se maneja solo desde el servidor, sin pantalla:  python -m radar.agentes.instagram_dm --ayuda
"""
import json
import re
import secrets
import sys
import threading
import traceback
import unicodedata
from datetime import datetime, timedelta

from .. import config, db
from ..connectors import instagram

TOPE_DIARIO = 100
INSTALACION = 0  # la cuenta de la instalación: no es un negocio de la app
RENOVAR_CADA_DIAS = 20
# La respuesta pública «*»: una distinta cada vez (y nunca la misma dos veces seguidas), para que no parezca un robot.
# También vale una lista propia separada por «|». «{nombre}» pone @usuario de quien comenta.
APERTURAS = (
    "Lo tengo preparado. ¿Te lo mando?",
    "Aquí estoy. Pulsa el botón y te lo paso ahora mismo.",
    "Listo para enviártelo. Dale al botón y es tuyo.",
    "Me ha llegado tu comentario. ¿Te lo paso por aquí?",
    "Ya lo tengo a mano. Dime y te lo envío.",
)
BOTON = "Mándamelo"
ENTREGAS = (
    "Aquí lo tienes: {enlace}\n\nEmpieza por lo primero que veas: en diez minutos ya lo estás usando.",
    "Todo tuyo: {enlace}\n\nGuárdalo, que luego no se encuentra.",
    "Hecho. Aquí está: {enlace}\n\nSi te atascas en algo, escríbeme por aquí.",
    "Te lo dejo aquí: {enlace}\n\nNo hace falta saber programar para usarlo.",
    "Ahí va: {enlace}\n\nCuando lo pruebes, cuéntame qué tal.",
)
PREGUNTAS = (
    "¿Qué tal? ¿Le has podido echar un ojo?",
    "Oye, ¿te ha servido? Me interesa saber qué parte te ha resultado más útil.",
    "¿Has llegado a probarlo? Si algo no te ha quedado claro, pregúntame.",
    "Una pregunta rápida: ¿para qué lo vas a usar primero?",
    "¿Cómo te ha ido? Si te ha servido, dime en qué y te paso algo más que te puede venir bien.",
)
UNA_HORA = timedelta(hours=1)
VENTANA = timedelta(hours=23)  # Meta da 24 h desde su respuesta: un margen
VARIADAS = (  # la cuenta de la instalación habla como Orby
    "Te lo acabo de mandar por privado. Orby.",
    "Hecho. Uno de mis siete agentes ya te lo ha enviado.",
    "Enviado. Aquí no dormimos.",
    "Ya lo tienes en tus mensajes. Luego me cuentas. Orby.",
    "Mandado. Si no lo ves, mira en solicitudes de mensajes.",
    "Listo, te espera en privado.",
    "Te ha llegado por privado. Y si lo pierdes, está en el perfil.",
    "Dentro. Avísame cuando lo pruebes. Orby.",
)
# La misma idea para la cuenta de una persona (los regalos de un negocio), en primera persona.
VARIADAS_PERSONA = (
    "Te lo acabo de mandar por privado.",
    "Hecho, revisa tus mensajes.",
    "Enviado. Si no lo ves, mira en solicitudes de mensajes.",
    "Ya lo tienes en privado. Luego me cuentas.",
    "Mira tus mensajes, te lo he dejado ahí.",
    "Mandado. Cuando lo pruebes, cuéntame qué tal.",
    "Te he escrito por privado.",
    "Dentro. Avísame cuando lo pruebes.",
)
_cerrojo = threading.Lock()


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- la conexión

def conexion(negocio_id: int) -> dict:
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM conexiones WHERE negocio_id = ? AND servicio = 'instagram'",
                        (negocio_id,)).fetchone()
    return json.loads(f["datos"]) if f else {}


def _guardar(negocio_id: int, datos: dict):
    with db.conexion() as con:
        con.execute("INSERT INTO conexiones (negocio_id, servicio, actualizado, datos) VALUES (?, 'instagram', ?, ?) "
                    "ON CONFLICT(negocio_id, servicio) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
                    (negocio_id, _ahora(), json.dumps(datos, ensure_ascii=False)))


def _todas() -> list[tuple[int, dict]]:
    with db.conexion() as con:
        return [(f["negocio_id"], json.loads(f["datos"]))
                for f in con.execute("SELECT negocio_id, datos FROM conexiones WHERE servicio = 'instagram'")]


def token_aviso(negocio_id: int) -> str:
    """El secreto de la dirección de avisos (y su «verify token»). Se crea la primera vez que hace falta."""
    datos = conexion(negocio_id)
    if not datos.get("aviso"):
        datos["aviso"] = secrets.token_urlsafe(18)
        _guardar(negocio_id, datos)
    return datos["aviso"]


def direccion(negocio_id: int) -> str:
    """La «Callback URL» que se pega en el panel de Meta."""
    return f"{config.URL_PUBLICA}/ig/{token_aviso(negocio_id)}" if config.URL_PUBLICA else ""


def negocio_de(negocio_id: int) -> dict | None:
    if negocio_id == INSTALACION:
        return {"id": INSTALACION, "nombre": config.APP_NOMBRE}
    return db.negocio(negocio_id)


def negocio_por_token(valor: str) -> int | None:
    if not valor:
        return None
    for nid, datos in _todas():
        if secrets.compare_digest(datos.get("aviso") or "", valor):
            return nid
    return None


def conectar(negocio_id: int, token: str = "", secreto: str = "") -> dict:
    """Guarda lo que llegue (lo vacío no toca lo que había), comprueba el token y suscribe la cuenta a los comentarios.
    Lanza ErrorInstagram si el token no vale."""
    datos = conexion(negocio_id)
    if token.strip():
        datos.update(token=token.strip(), renovado=_ahora())
    if secreto.strip():
        datos["secreto"] = secreto.strip()
    if not datos.get("token"):
        raise instagram.ErrorInstagram("Pega el token de la cuenta de Instagram.")
    datos.update(instagram.cuenta(datos["token"]))
    datos.update(suscrito=instagram.suscribir(datos["token"]), campos=instagram.CAMPOS)
    datos.update(comprobado=_ahora(), aviso=datos.get("aviso") or secrets.token_urlsafe(18))
    datos.setdefault("activa", True)
    _guardar(negocio_id, datos)
    return estado(negocio_id)


# ---------------------------------------------------------------- conectar con un botón (inicio de sesión de Instagram)

def app_de_instagram() -> tuple[str, str]:
    """(identificador, clave secreta) de la app de Meta de la instalación. Sin ellos, solo se conecta pegando el token."""
    import os
    return os.getenv("RADAR_IG_APP_ID", "").strip(), os.getenv("RADAR_IG_APP_SECRETO", "").strip()


def volver_oauth() -> str:
    return f"{config.URL_PUBLICA}/instagram/volver" if config.URL_PUBLICA else ""


def boton_disponible() -> bool:
    return all(app_de_instagram()) and bool(volver_oauth())


def enlace_conectar(negocio_id: int) -> str:
    """Adónde lleva el botón «Conectar Instagram». Guarda un «state» de un solo uso para saber de qué negocio vuelve."""
    app_id, _ = app_de_instagram()
    if not boton_disponible():
        raise instagram.ErrorInstagram("Falta la app de Instagram de la instalación (identificador y clave secreta).")
    datos = conexion(negocio_id)
    datos["oauth"] = {"estado": secrets.token_urlsafe(18), "creado": _ahora()}
    _guardar(negocio_id, datos)
    return instagram.enlace_autorizar(app_id, volver_oauth(), f"{negocio_id}.{datos['oauth']['estado']}")


def completar_conexion(estado: str, codigo: str) -> int:
    """La vuelta de Instagram: comprueba el «state», cambia el código por un token y conecta la cuenta. Devuelve el
    negocio. Lanza ErrorInstagram (o ValueError si el «state» no vale)."""
    nid_txt, _, valor = (estado or "").partition(".")
    if not nid_txt.isdigit():
        raise ValueError("estado")
    nid = int(nid_txt)
    datos = conexion(nid)
    pendiente = datos.pop("oauth", None) or {}
    _guardar(nid, datos)  # de un solo uso
    caduca = datetime.fromisoformat(pendiente.get("creado", "2000-01-01")) + timedelta(minutes=30)
    if not pendiente or not secrets.compare_digest(pendiente.get("estado", ""), valor) or datetime.now() > caduca:
        raise ValueError("estado")
    app_id, secreto = app_de_instagram()
    token = instagram.token_desde_codigo(app_id, secreto, volver_oauth(), codigo)
    conectar(nid, token, secreto)
    return nid


def desconectar(negocio_id: int):
    datos = conexion(negocio_id)
    for k in ("token", "secreto", "id", "usuario", "suscrito", "comprobado", "renovado"):
        datos.pop(k, None)
    _guardar(negocio_id, datos)


def ajustar(negocio_id: int, *, activa: bool | None = None, tope: int | None = None, publica: str | None = None,
            modo_: str | None = None):
    datos = conexion(negocio_id)
    if modo_ in ("conversacion", "directo"):
        datos["modo"] = modo_
    if activa is not None:
        datos["activa"] = activa
    if tope is not None:
        datos["tope"] = max(1, min(int(tope), 500))
    if publica is not None:
        datos["publica"] = publica.strip()[:600]  # la respuesta pública por defecto («» = ninguna, «*» = variada)
    _guardar(negocio_id, datos)


def estado(negocio_id: int) -> dict:
    """Para Conectores y Comunidad. Sin el token ni la clave secreta."""
    d = conexion(negocio_id)
    return {"conectado": bool(d.get("token")), "secreto": bool(d.get("secreto")), "usuario": d.get("usuario", ""),
            "cuenta_id": d.get("id", ""), "suscrito": bool(d.get("suscrito")), "comprobado": d.get("comprobado", ""),
            "activa": d.get("activa", True), "modo": d.get("modo") or "conversacion", "tope": d.get("tope", TOPE_DIARIO), "publica": d.get("publica", ""),
            "direccion": direccion(negocio_id) if d else "", "verify_token": d.get("aviso", ""),
            "boton": boton_disponible(), "conectar": f"/negocios/{negocio_id}/conectores/instagram/conectar",
            "palabras": palabras(negocio_id), "hoy": enviados_hoy(negocio_id), "ultimos": envios(negocio_id, 20)}


# ---------------------------------------------------------------- las palabras

def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sin_tildes.upper()


def palabras(negocio_id: int) -> list[dict]:
    """Las de este conector (las de la cuenta de la instalación se ponen desde el servidor) y los regalos activos."""
    from . import regalos
    propias = conexion(negocio_id).get("palabras", [])
    return propias + (regalos.para_instagram(negocio_id) if negocio_id != INSTALACION else [])


def poner_palabra(negocio_id: int, palabra: str, enlace: str, *, mensaje: str = "", media_id: str = "",
                  publica: str | None = None, apertura: str = "", pregunta: str = "", exacta: bool = False) -> dict:
    """Una palabra con su enlace. Con `media_id`, solo en ese reel; sin él, en todos. Si ya estaba, se cambia."""
    palabra = re.sub(r"[^A-Z0-9]", "", _normalizar(palabra))
    enlace = enlace.strip()
    mensaje, apertura, pregunta = (t.replace("\\n", "\n") for t in (mensaje, apertura, pregunta))  # «\n» desde el servidor
    if not palabra or not enlace.startswith(("https://", "http://")):
        raise ValueError("Hace falta la palabra (letras o números) y un enlace que empiece por https://.")
    if mensaje:  # cada variante («a | b») lleva el enlace
        mensaje = " | ".join(m if "{enlace}" in m or enlace in m else f"{m.rstrip()} {{enlace}}"
                             for m in (x.strip() for x in mensaje.split("|")) if m)
    nueva = {"palabra": palabra, "enlace": enlace, "mensaje": mensaje.strip()[:900], "media_id": media_id.strip()}
    if exacta:  # palabras corrientes («estilo», «manual»): solo cuentan escritas en mayúsculas o solas en el comentario
        nueva["exacta"] = True
    if publica is not None:
        nueva["publica"] = publica.strip()[:600]
    if apertura.strip():
        nueva["apertura"] = apertura.strip()[:600]  # el primer mensaje, con el botón (modo conversación)
    if pregunta.strip():
        nueva["pregunta"] = pregunta.strip()[:600]  # la pregunta de una hora después
    datos = conexion(negocio_id)
    datos["palabras"] = [p for p in datos.get("palabras", [])
                         if (p["palabra"], p.get("media_id", "")) != (palabra, nueva["media_id"])] + [nueva]
    _guardar(negocio_id, datos)
    return nueva


def quitar_palabra(negocio_id: int, palabra: str, media_id: str = "") -> bool:
    palabra = re.sub(r"[^A-Z0-9]", "", _normalizar(palabra))
    datos = conexion(negocio_id)
    antes = datos.get("palabras", [])
    datos["palabras"] = [p for p in antes if (p["palabra"], p.get("media_id", "")) != (palabra, media_id.strip())]
    _guardar(negocio_id, datos)
    return len(datos["palabras"]) < len(antes)


def _de_chati(negocio_id: int) -> list[dict]:
    """Las guías de Comunidad, como palabras globales (su enlace es el de la guía)."""
    from . import comunidad
    salida = []
    for g in comunidad.guias(negocio_id):
        if g.get("palabra"):
            salida.append({"palabra": re.sub(r"[^A-Z0-9]", "", _normalizar(g["palabra"])), "media_id": "",
                           "guia": g, "enlace": "", "mensaje": ""})
    return salida


def regla_para(negocio_id: int, texto: str, media_id: str) -> dict | None:
    """La palabra que lleva el comentario: primero la de ese reel, luego las globales y luego las guías de Chati."""
    palabras_ = set(re.findall(r"[A-Z0-9]+", _normalizar(texto)))
    if not palabras_:
        return None
    en_mayusculas = {_normalizar(t) for t in re.findall(r"\w+", texto or "") if len(t) > 1 and t.isupper()}

    def dice(p: dict) -> bool:
        if p["palabra"] not in palabras_:
            return False
        return not p.get("exacta") or palabras_ == {p["palabra"]} or p["palabra"] in en_mayusculas
    propias = palabras(negocio_id)
    for candidatas in ([p for p in propias if p.get("media_id") and p["media_id"] == media_id],
                       [p for p in propias if not p.get("media_id")], _de_chati(negocio_id)):
        for p in candidatas:
            if dice(p):
                return p
    return None


def _nombre_de(token: str, c: dict) -> str:
    """La primera palabra del nombre de su perfil (sin emojis ni símbolos) o, si no lo hay, su @usuario."""
    nombre = instagram.nombre_de(token, c["autor_id"]) if c.get("autor_id") else ""
    primera = next((p for p in re.findall(r"[^\W\d_]+", nombre)), "")
    return primera[:30] if primera else (f"@{c['autor']}" if c.get("autor") else "")


def con_nombre(texto: str, nombre: str) -> str:
    """Pone el nombre en «{nombre}»; sin nombre, deja la frase limpia («Hola, {nombre}.» → «Hola.»)."""
    texto = texto.replace("{nombre}", nombre)
    texto = re.sub(r",\s*([.!?])", r"\1", texto)
    return re.sub(r"[ \t]+([,.!?])", r"\1", texto).replace("  ", " ").strip()


def respuesta_publica(plantilla: str, autor: str = "", anterior: str = "", *, persona: bool = False) -> str:
    """El texto de la respuesta pública: «*» elige una de VARIADAS (o de VARIADAS_PERSONA en la cuenta de una persona);
    «a | b | c», una de esas. Nunca repite la anterior."""
    import random
    casa = VARIADAS_PERSONA if persona else VARIADAS
    opciones = list(casa) if plantilla.strip() == "*" else [o.strip() for o in plantilla.split("|") if o.strip()]
    if not opciones:
        return ""
    elegible = [o for o in opciones if o != anterior] or opciones
    texto = random.choice(elegible)
    texto = texto.replace("{nombre}", f"@{autor}" if autor else "")
    return re.sub(r"\s+([,.])", r"\1", re.sub(r",\s*\.", ".", texto)).replace("  ", " ").strip()


def _una(opciones, propia: str = "") -> str:
    """La propia de la palabra (o una de sus variantes separadas por «|») o una de las de la casa."""
    import random
    lista = [o.strip() for o in propia.split("|") if o.strip()] if propia else list(opciones)
    return random.choice(lista)


def mensaje_de(negocio: dict, regla: dict, autor: str = "") -> str:
    """El mensaje con el enlace."""
    from . import comunidad
    if regla.get("guia"):
        enlace = comunidad.enlace_guia(regla["guia"], comunidad._utm_de(negocio["id"], regla["palabra"]))
        return comunidad.texto_entrega(negocio, regla["palabra"], enlace, autor)
    if regla.get("mensaje"):
        return _una((), regla["mensaje"]).replace("{enlace}", regla["enlace"]).replace("{nombre}", autor or "").strip()
    if negocio["id"] == INSTALACION:  # sin Kit de marca
        return _una(ENTREGAS).replace("{enlace}", regla["enlace"])
    return comunidad.texto_entrega(negocio, regla["palabra"], regla["enlace"], autor)


def modo(negocio_id: int) -> str:
    return conexion(negocio_id).get("modo") or "conversacion"


# ---------------------------------------------------------------- los envíos

def enviados_hoy(negocio_id: int) -> int:
    hoy = datetime.now().date().isoformat()
    with db.conexion() as con:
        return con.execute("SELECT COUNT(*) FROM envios_ig WHERE negocio_id = ? AND estado = 'enviado' AND creado >= ?",
                           (negocio_id, hoy)).fetchone()[0]


def envios(negocio_id: int, limite: int = 50) -> list[dict]:
    with db.conexion() as con:
        return [dict(f) for f in con.execute("SELECT * FROM envios_ig WHERE negocio_id = ? ORDER BY id DESC LIMIT ?",
                                             (negocio_id, limite))]


def _anotar(negocio_id: int, c: dict, palabra: str, estado_: str, error: str = "") -> bool:
    """Apunta el comentario. False si ya estaba (Meta repite los avisos)."""
    with db.conexion() as con:
        cur = con.execute("INSERT OR IGNORE INTO envios_ig (negocio_id, comentario_id, media_id, autor_id, autor, palabra, "
                          "estado, error, creado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (negocio_id, c["id"], c["media_id"], c["autor_id"], c["autor"][:80], palabra, estado_,
                           error[:300], _ahora()))
        return cur.rowcount > 0


def _cambiar(negocio_id: int, comentario_id: str, estado_: str, error: str = "", fase: str = ""):
    with db.conexion() as con:
        con.execute("UPDATE envios_ig SET estado = ?, error = ?, fase = ? WHERE negocio_id = ? AND comentario_id = ?",
                    (estado_, error[:300], fase, negocio_id, comentario_id))


def _ya_recibio(negocio_id: int, c: dict, palabra: str) -> bool:
    with db.conexion() as con:
        return con.execute("SELECT 1 FROM envios_ig WHERE negocio_id = ? AND autor_id = ? AND media_id = ? AND palabra = ? "
                           "AND estado = 'enviado' LIMIT 1", (negocio_id, c["autor_id"], c["media_id"], palabra)
                           ).fetchone() is not None


def atender(negocio: dict, c: dict) -> str:
    """Un comentario: manda el enlace por privado si toca. Devuelve qué ha pasado (para el registro y las pruebas)."""
    nid, datos = negocio["id"], conexion(negocio["id"])
    if not datos.get("token") or not datos.get("activa", True):
        return "apagado"
    if not c["autor_id"] or c["autor_id"] == datos.get("id"):
        return "propio"  # los comentarios de la propia cuenta (también sus respuestas públicas)
    regla = regla_para(nid, c["texto"], c["media_id"])
    if not regla:
        return "sin_palabra"
    with _cerrojo:
        if _ya_recibio(nid, c, regla["palabra"]):
            return "repetido" if _anotar(nid, c, regla["palabra"], "repetido") else "ya_visto"
        if enviados_hoy(nid) >= int(datos.get("tope") or TOPE_DIARIO):
            return "tope" if _anotar(nid, c, regla["palabra"], "tope") else "ya_visto"
        if not _anotar(nid, c, regla["palabra"], "enviando"):
            return "ya_visto"
    cuenta, conversa = datos.get("id") or c["cuenta_id"], modo(nid) == "conversacion"
    try:
        if conversa:
            apertura = con_nombre(_una(APERTURAS, regla.get("apertura", "")),
                                  _nombre_de(datos["token"], c) if "{nombre}" in regla.get("apertura", "") else "")
            try:
                instagram.responder_en_privado(datos["token"], cuenta, c["id"], apertura, [(BOTON, f"ENLACE:{regla['palabra']}")])
            except instagram.ErrorInstagram:  # si Meta no acepta el botón, que conteste con cualquier cosa
                instagram.responder_en_privado(datos["token"], cuenta, c["id"],
                                               f"{apertura} Contéstame «sí» y te lo paso.")
        else:
            instagram.responder_en_privado(datos["token"], cuenta, c["id"], mensaje_de(negocio, regla, c["autor"]))
    except instagram.ErrorInstagram as e:
        _cambiar(nid, c["id"], "fallido", str(e))
        return "fallido"
    _cambiar(nid, c["id"], "enviado", fase="esperando" if conversa else "")
    # Los regalos contestan en público por defecto, con una frase variada (salvo que la cuenta diga otra cosa).
    plantilla = regla.get("publica") or datos.get("publica") or ("*" if regla.get("regalo_id") else "")
    if plantilla:
        try:
            publica = respuesta_publica(plantilla, c["autor"], datos.get("ultima_publica", ""), persona=nid != INSTALACION)
            instagram.responder_en_publico(datos["token"], c["id"], publica)
            datos = conexion(nid)
            datos["ultima_publica"] = publica.replace(f"@{c['autor']}", "{nombre}") if c["autor"] else publica
            _guardar(nid, datos)
        except instagram.ErrorInstagram:
            traceback.print_exc()  # el privado ya ha llegado: la respuesta pública es un extra
    return "enviado"


def _regla_de(negocio_id: int, palabra: str, media_id: str) -> dict | None:
    propias = palabras(negocio_id)
    for p in ([p for p in propias if p["palabra"] == palabra and p.get("media_id") == media_id] +
              [p for p in propias if p["palabra"] == palabra and not p.get("media_id")] +
              [p for p in _de_chati(negocio_id) if p["palabra"] == palabra]):
        return p
    return None


def contestado(negocio: dict, m: dict) -> str:
    """Un mensaje privado de alguien: si le habíamos ofrecido un regalo (botón o no), ahora le llega el enlace."""
    nid, datos = negocio["id"], conexion(negocio["id"])
    if not datos.get("token") or not datos.get("activa", True):
        return "apagado"
    hace_7_dias = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    with _cerrojo, db.conexion() as con:
        filas = [dict(f) for f in con.execute(
            "SELECT * FROM envios_ig WHERE negocio_id = ? AND autor_id = ? AND fase = 'esperando' AND creado >= ? "
            "ORDER BY id DESC", (nid, m["autor_id"], hace_7_dias))]
        if not filas:
            return "nada"
        pedida = m["payload"].split(":", 1)[1] if m["payload"].startswith("ENLACE:") else ""
        envio = next((f for f in filas if f["palabra"] == pedida), filas[0])
        con.execute("UPDATE envios_ig SET fase = 'enviando' WHERE id = ?", (envio["id"],))
    regla = _regla_de(nid, envio["palabra"], envio["media_id"])
    if not regla:
        _fase(envio["id"], "caducado")
        return "sin_palabra"
    try:
        instagram.enviar_mensaje(datos["token"], datos.get("id") or m["cuenta_id"], m["autor_id"],
                                 mensaje_de(negocio, regla, envio["autor"]))
    except instagram.ErrorInstagram as e:
        _fase(envio["id"], "esperando", str(e))
        return "fallido"
    _fase(envio["id"], "enlace", enlace_en=_ahora())
    return "enlace"


def _fase(envio_id: int, fase: str, error: str = "", enlace_en: str | None = None):
    with db.conexion() as con:
        con.execute("UPDATE envios_ig SET fase = ?, error = ?, enlace_en = COALESCE(?, enlace_en) WHERE id = ?",
                    (fase, error[:300], enlace_en, envio_id))


def preguntar_pendientes(ahora: datetime | None = None) -> int:
    """Una hora después del enlace, la pregunta sobre el regalo (si aún estamos en las 24 h de su respuesta)."""
    ahora, hechas = ahora or datetime.now(), 0
    with db.conexion() as con:
        filas = [dict(f) for f in con.execute("SELECT * FROM envios_ig WHERE fase = 'enlace' AND enlace_en != '' "
                                              "AND enlace_en <= ?", ((ahora - UNA_HORA).isoformat(timespec="seconds"),))]
    for f in filas:
        datos = conexion(f["negocio_id"])
        if datetime.fromisoformat(f["enlace_en"]) < ahora - VENTANA or not datos.get("token"):
            _fase(f["id"], "caducado")
            continue
        regla = _regla_de(f["negocio_id"], f["palabra"], f["media_id"]) or {}
        try:
            instagram.enviar_mensaje(datos["token"], datos.get("id", ""), f["autor_id"],
                                     _una(PREGUNTAS, regla.get("pregunta", "")))
        except instagram.ErrorInstagram as e:
            _fase(f["id"], "caducado", str(e))
            continue
        _fase(f["id"], "preguntado")
        hechas += 1
    return hechas


def asegurar_suscripciones() -> int:
    """Las cuentas conectadas antes de escuchar los mensajes se vuelven a suscribir (comentarios y mensajes)."""
    hechas = 0
    for nid, datos in _todas():
        if datos.get("token") and datos.get("campos") != instagram.CAMPOS:
            try:
                instagram.suscribir(datos["token"])
            except instagram.ErrorInstagram as e:
                datos["error_suscribir"] = str(e)
            else:
                datos.update(campos=instagram.CAMPOS, suscrito=True)
                datos.pop("error_suscribir", None)
                hechas += 1
            _guardar(nid, datos)
    return hechas


def _negocio_de_la_cuenta(cuenta_id: str, secreto: str, por_defecto: int) -> int:
    """Varios negocios pueden usar la misma app de Meta: cada comentario va al de su cuenta."""
    for nid, datos in _todas():
        if datos.get("id") == cuenta_id and datos.get("secreto") == secreto:
            return nid
    return por_defecto


def recibir(negocio_id: int, cuerpo: bytes, firma: str) -> list[tuple[dict, dict]] | None:
    """Comprueba la firma del aviso y devuelve [(negocio, comentario o mensaje)] para atender. None si la firma no
    vale."""
    secreto = conexion(negocio_id).get("secreto", "")
    if not instagram.firma_valida(cuerpo, firma, secreto):
        return None
    try:
        aviso = json.loads(cuerpo or b"{}")
    except ValueError:
        return []
    salida = []
    for c in instagram.comentarios(aviso) + instagram.mensajes(aviso):
        neg = negocio_de(_negocio_de_la_cuenta(c["cuenta_id"], secreto, negocio_id))
        if neg:
            salida.append((neg, c))
    return salida


def atender_todos(pendientes: list[tuple[dict, dict]]):
    from .. import claves
    for neg, c in pendientes:
        try:
            with claves.en(neg["id"]):
                atender(neg, c) if "media_id" in c else contestado(neg, c)
        except Exception:  # noqa: BLE001 — un comentario con un problema no para a los demás
            traceback.print_exc()


# ---------------------------------------------------------------- el token dura 60 días: se renueva solo

def renovar_tokens(ahora: datetime | None = None) -> int:
    ahora, hechos = ahora or datetime.now(), 0
    for nid, datos in _todas():
        if not datos.get("token"):
            continue
        try:
            ultima = datetime.fromisoformat(datos.get("renovado") or datos.get("comprobado") or "2000-01-01")
        except ValueError:
            ultima = datetime(2000, 1, 1)
        if ahora - ultima < timedelta(days=RENOVAR_CADA_DIAS):
            continue
        try:
            nuevo = instagram.renovar(datos["token"])
        except instagram.ErrorInstagram as e:
            datos["error_renovar"] = str(e)
            _guardar(nid, datos)
            continue
        if nuevo["token"]:
            datos.update(token=nuevo["token"], renovado=ahora.isoformat(timespec="seconds"))
            datos.pop("error_renovar", None)
            _guardar(nid, datos)
            hechos += 1
    return hechos


def arrancar_renovacion():
    """Cada minuto, las preguntas pendientes; cada 6 horas, los tokens."""
    def vueltas():
        import time
        vuelta = 0
        while True:
            try:
                if vuelta % 360 == 0:
                    asegurar_suscripciones()
                    renovar_tokens()
                preguntar_pendientes()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            vuelta += 1
            time.sleep(60)
    threading.Thread(target=vueltas, daemon=True).start()


# ---------------------------------------------------------------- desde el servidor, sin pantalla

AYUDA = """Uso (dentro del contenedor: docker compose exec radar python -m radar.agentes.instagram_dm …):
  conectar <negocio>                                lee el token y la clave secreta (una línea cada uno) de la entrada
  estado <negocio>                                  cuenta, dirección de avisos, palabras y envíos de hoy
  poner <negocio> <PALABRA> <enlace> [--reel <media_id>] [--mensaje "texto con {enlace}"] [--apertura "…"] [--pregunta "…"] [--exacta] [--publica "texto" | "a | b | c" | "*" (variada)]
  quitar <negocio> <PALABRA> [--reel <media_id>]
  activar | apagar <negocio>
  modo <negocio> conversacion|directo           conversación: botón → enlace → pregunta a la hora; directo: el enlace y ya
  tope <negocio> <número al día>
  envios <negocio>                                  los últimos 30
<negocio> es su número en la app, o 0 para la cuenta de la instalación."""


def _opcion(args: list[str], nombre: str) -> str | None:
    if nombre in args:
        i = args.index(nombre)
        valor = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
        return valor
    return None


def main(args: list[str]) -> int:
    db.iniciar()
    if len(args) < 2 or args[0] in ("--ayuda", "-h", "--help"):
        print(AYUDA)
        return 0
    orden, nid = args[0], int(args[1])
    resto = args[2:]
    reel, mensaje, publica = _opcion(resto, "--reel") or "", _opcion(resto, "--mensaje") or "", _opcion(resto, "--publica")
    apertura, pregunta = _opcion(resto, "--apertura") or "", _opcion(resto, "--pregunta") or ""
    exacta = "--exacta" in resto
    resto = [a for a in resto if a != "--exacta"]
    if orden == "conectar":
        token, secreto = (sys.stdin.readline().strip(), sys.stdin.readline().strip())
        try:
            e = conectar(nid, token, secreto)
        except instagram.ErrorInstagram as err:
            print(f"No se ha podido conectar: {err}")
            return 1
        print(f"Conectada @{e['usuario']} (suscrita a comentarios: {'sí' if e['suscrito'] else 'no'}).")
        print(f"Callback URL: {e['direccion']}\nVerify token: {e['verify_token']}")
    elif orden == "estado":
        e = estado(nid)
        e.pop("ultimos")
        print(json.dumps(e, ensure_ascii=False, indent=2))
    elif orden == "poner" and len(resto) >= 2:
        print(json.dumps(poner_palabra(nid, resto[0], resto[1], mensaje=mensaje, media_id=reel, publica=publica,
                                       apertura=apertura, pregunta=pregunta, exacta=exacta), ensure_ascii=False))
    elif orden == "modo" and resto:
        ajustar(nid, modo_=resto[0])
        print(f"modo: {modo(nid)}")
    elif orden == "quitar" and resto:
        print("quitada" if quitar_palabra(nid, resto[0], reel) else "no estaba")
    elif orden in ("activar", "apagar"):
        ajustar(nid, activa=orden == "activar")
        print("activa" if orden == "activar" else "apagada")
    elif orden == "tope" and resto:
        ajustar(nid, tope=int(resto[0]))
        print(f"tope: {conexion(nid)['tope']} al día")
    elif orden == "envios":
        for f in envios(nid, 30):
            print(f"{f['creado']}  {f['estado']:<9} {f['fase']:<10} {f['palabra']:<10} @{f['autor']}  {f['error']}")
    else:
        print(AYUDA)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
