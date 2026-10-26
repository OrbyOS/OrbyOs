"""Dirección (Orby): tu único punto de contacto con el equipo.

- El resumen de cada mañana: qué grabar hoy, lo que espera tu aprobación (lo más antiguo primero), los resultados de ayer
  y las alertas. Lo compone el código, sin IA: llega aunque Claude no esté disponible, no cuesta nada y no se inventa nada.
- Telegram: cada aprobación nueva te llega con sus botones; también puedes escribir «aprobar ap-7», «rechazar ap-7
  motivo», «cambios ap-7 lo que quieres», «resumen», «aprobaciones», «silencio 21:30-07:00» o «silencio no». Cualquier
  otra cosa la contesta Orby. Solo se aceptan mensajes de tu chat.
- Horas de silencio: lo normal espera a que acaben; lo urgente (una cuenta desconectada…) sale igual.
- Un mismo aviso no se repite en 3 horas: se cuenta, y el siguiente dice cuántas veces ha pasado.
- Todo pasa por una bandeja de salida: si la app se reinicia o Telegram falla, nada se manda dos veces y nada se pierde.
"""
import json
import re
import secrets
import threading
import time
import traceback
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .. import claves, db, jobs
from ..connectors import telegram
from ..modules import edicion as motor
from . import AGENTES, estado, estratega, publicador
from . import aprobaciones as ap
from . import kit as kit_marca

AGENTE = "jefa"
AGRUPAR_MINUTOS = 180
MAX_INTENTOS = 5
APROBACIONES_EN_RESUMEN = 5
VENTANA_RESUMEN_HORAS = 5  # si la app estaba cerrada a la hora del resumen, sale al abrirla, pero no por la noche
CADA_SEGUNDOS = 15
UNIDADES = {"leads": "leads", "seguidores": "seguidores nuevos", "llamadas": "llamadas", "ventas": "€ en ventas"}
RITMOS = {"cumplido": "¡cumplido!", "en_camino": "vas bien", "en_riesgo": "vas justo", "por_detras": "vas por detrás"}
AYUDA = ("Puedes escribirme:\n• aprobar ap-7\n• rechazar ap-7 motivo\n• cambios ap-7 lo que quieres cambiar\n• resumen\n"
         "• aprobaciones\n• regla: lo que el equipo debe hacer siempre (o no hacer nunca)\n• qué falta (del Kit)\n"
         "• silencio 21:30-07:00 · silencio no\n\nCualquier otra cosa, te la contesto yo.")


def _ahora() -> datetime:
    return datetime.now()


def hora_local(negocio_id: int) -> datetime:
    """La hora del negocio (kit «zona»), sin zona: el resumen, el silencio y el informe van con su reloj, no con el del
    servidor."""
    try:
        return datetime.now(ZoneInfo(kit_marca.leer(negocio_id).get("zona") or "Europe/Madrid")).replace(tzinfo=None)
    except (ZoneInfoNotFoundError, ValueError):
        return _ahora()


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


# ---------------------------------------------------------------- la conexión con Telegram

def conexion(negocio_id: int) -> dict:
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM conexiones WHERE negocio_id = ? AND servicio = 'telegram'", (negocio_id,)).fetchone()
    return json.loads(f["datos"]) if f else {}


def _guardar_conexion(negocio_id: int, datos: dict):
    with db.conexion() as con:
        con.execute("INSERT INTO conexiones (negocio_id, servicio, actualizado, datos) VALUES (?, 'telegram', ?, ?) "
                    "ON CONFLICT(negocio_id, servicio) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
                    (negocio_id, _iso(_ahora()), json.dumps(datos, ensure_ascii=False)))


def conectado(negocio_id: int) -> bool:
    c = conexion(negocio_id)
    return bool(c.get("token") and c.get("chat"))


def conectar(negocio_id: int, token: str) -> dict:
    """Guarda el token del bot y prepara el código con el que se reconoce tu chat."""
    info = telegram.bot(token.strip())
    datos = {"token": token.strip(), "bot": info["usuario"], "codigo": secrets.token_hex(4), "chat": "", "desde": 0}
    _guardar_conexion(negocio_id, datos)
    return datos


def enlace_de_inicio(negocio_id: int) -> str:
    c = conexion(negocio_id)
    return f"https://t.me/{c['bot']}?start={c['codigo']}" if c.get("bot") and c.get("codigo") else ""


def desconectar(negocio_id: int):
    with db.conexion() as con:
        con.execute("DELETE FROM conexiones WHERE negocio_id = ? AND servicio = 'telegram'", (negocio_id,))


# ---------------------------------------------------------------- horas de silencio

def _minutos(hora: str) -> int | None:
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", (hora or "").strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def en_silencio(negocio_id: int, ahora: datetime | None = None) -> bool:
    a = kit_marca.leer(negocio_id)["avisos"]
    inicio, fin = _minutos(a.get("silencio_inicio")), _minutos(a.get("silencio_fin"))
    if inicio is None or fin is None or inicio == fin:
        return False
    ahora = ahora or hora_local(negocio_id)
    m = ahora.hour * 60 + ahora.minute
    return inicio <= m < fin if inicio < fin else (m >= inicio or m < fin)


# ---------------------------------------------------------------- la bandeja de salida

def encolar(negocio_id: int, texto: str, *, botones: list | None = None, prioridad: str = "normal", clave: str = "",
            video: str = "", contar: bool = True, cada_minutos: int = AGRUPAR_MINUTOS) -> int | None:
    """Deja el mensaje en la bandeja de salida. Un aviso con la misma clave en las últimas 3 horas no se repite: se
    cuenta, y el siguiente dice cuántas veces ha pasado. Con contar=False (algo que sigue roto, no algo que vuelve a
    pasar) no se cuenta: pasado el plazo, se recuerda que sigue igual."""
    ahora = _ahora()
    if not conectado(negocio_id):
        return None
    with db.conexion() as con:
        if clave:
            reciente = con.execute("SELECT id FROM mensajes_salida WHERE negocio_id = ? AND clave = ? AND creado >= ? "
                                   "ORDER BY id DESC LIMIT 1",
                                   (negocio_id, clave, _iso(ahora - timedelta(minutes=cada_minutos)))).fetchone()
            if reciente:
                if contar:
                    con.execute("UPDATE mensajes_salida SET repeticiones = repeticiones + 1 WHERE id = ?", (reciente["id"],))
                return None
            anterior = con.execute("SELECT creado, repeticiones FROM mensajes_salida WHERE negocio_id = ? AND clave = ? "
                                   "ORDER BY id DESC LIMIT 1", (negocio_id, clave)).fetchone()
            if anterior and contar and anterior["repeticiones"]:
                texto += f"\n\n(Ha vuelto a pasar {anterior['repeticiones']} vez{'es' if anterior['repeticiones'] != 1 else ''} desde el último aviso.)"
            elif anterior and not contar and anterior["creado"] >= _iso(ahora - timedelta(minutes=2 * cada_minutos)):
                texto += f"\n\n(Sigue igual desde el aviso de las {anterior['creado'][11:16]}.)"
        cur = con.execute("INSERT INTO mensajes_salida (negocio_id, creado, texto, botones, video, prioridad, clave) VALUES "
                          "(?, ?, ?, ?, ?, ?, ?)", (negocio_id, _iso(ahora), texto, json.dumps(botones or []), video,
                                                    prioridad, clave))
        return cur.lastrowid


def despachar(negocio_id: int) -> int:
    """Manda lo pendiente, en orden, respetando las horas de silencio (salvo lo urgente)."""
    c = conexion(negocio_id)
    if not (c.get("token") and c.get("chat")):
        return 0
    silencio = en_silencio(negocio_id)
    with db.conexion() as con:
        pendientes = [dict(f) for f in con.execute(
            "SELECT * FROM mensajes_salida WHERE negocio_id = ? AND estado = 'pendiente' ORDER BY id", (negocio_id,))]
    enviados = 0
    for m in pendientes:
        if silencio and m["prioridad"] != "alta":
            continue
        try:
            if m["video"] and Path(m["video"]).exists():
                mid = telegram.enviar_video(c["token"], c["chat"], Path(m["video"]), m["texto"])
            else:
                mid = telegram.enviar(c["token"], c["chat"], m["texto"], json.loads(m["botones"]) or None)
            nuevo, extra = "enviado", {"enviado": _iso(_ahora()), "mensaje_id": mid}
        except telegram.ErrorTelegram:
            nuevo = "fallido" if m["intentos"] + 1 >= MAX_INTENTOS else "pendiente"
            extra = {}
        with db.conexion() as con:
            con.execute("UPDATE mensajes_salida SET estado = ?, intentos = intentos + 1, enviado = ?, mensaje_id = ? "
                        "WHERE id = ?", (nuevo, extra.get("enviado"), extra.get("mensaje_id"), m["id"]))
        enviados += nuevo == "enviado"
    return enviados


# ---------------------------------------------------------------- las alertas

def alertas(negocio_id: int) -> list[dict]:
    """Lo que hay que arreglar, en lenguaje claro. Cada alerta lleva su clave para no repetirse."""
    salida = []
    for c in publicador.estado_cuentas(negocio_id):
        if c["activa"] and c["estado"] == "reconectar":
            salida.append({"texto": f"Tu cuenta de {c['nombre']} @{c['cuenta']['usuario']} se ha desconectado de Zernio: "
                                    "reconéctala allí. Sus publicaciones están en pausa.",
                           "clave": f"reconectar-{c['red']}", "prioridad": "alta"})
    desde = _iso(_ahora() - timedelta(days=2))
    with db.conexion() as con:
        for p in con.execute("SELECT id, plataforma, error FROM publicaciones WHERE negocio_id = ? AND estado = 'fallida' "
                             "AND creado >= ?", (negocio_id, desde)):
            salida.append({"texto": f"No se ha podido publicar en {publicador.REDES.get(p['plataforma'])}: "
                                    f"{p['error'] or 'sin motivo'}. Está en Publicación para volver a intentarlo.",
                           "clave": f"publicacion-{p['id']}", "prioridad": "normal"})
        for e in con.execute("SELECT id, titulo, paso FROM ediciones WHERE negocio_id = ? AND estado = 'error' AND creado >= ? "
                             "AND datos LIKE '%\"produccion\"%'", (negocio_id, desde)):
            salida.append({"texto": f"La edición de «{e['titulo']}» se ha parado: {e['paso']}",
                           "clave": f"edicion-{e['id']}", "prioridad": "normal"})
        bloqueados = con.execute("SELECT COUNT(*) FROM guiones WHERE negocio_id = ? AND estado = 'bloqueado'",
                                 (negocio_id,)).fetchone()[0]
    if bloqueados:
        salida.append({"texto": f"{bloqueados} guion{'es' if bloqueados != 1 else ''} no pasa{'n' if bloqueados != 1 else ''} "
                                "el validador: están en Guiones.", "clave": "guiones-bloqueados", "prioridad": "normal"})
    from . import analista
    gastado, tope = analista.gasto_apify_del_mes(negocio_id), analista.PRESUPUESTO_APIFY_MES
    if tope and gastado >= 0.8 * tope:
        salida.append({"texto": f"Llevas {gastado:.2f} $ de Apify este mes, de {tope:.0f} $ de presupuesto.",
                       "clave": f"apify-{date.today():%Y-%m}", "prioridad": "normal"})
    # Un agente que se ha parado a medias (un error o la app cerrada mientras trabajaba): te llega una vez al día.
    for agente, info in AGENTES.items():
        for aviso in paradas(negocio_id, agente):
            salida.append({"texto": f"{info['nombre']} ({info['rol'].lower()}): {aviso}", "prioridad": "normal",
                           "clave": f"parado-{agente}-{zlib.crc32(aviso.encode())}", "avisar": True, "cada": 24 * 60})
    return salida


def paradas(negocio_id: int, agente: str) -> list[str]:
    """Los avisos de un agente que dicen que su último trabajo no terminó."""
    return [a for a in estado.leer(negocio_id, agente).get("avisos") or []
            if "se ha parado" in a.lower() or a.startswith("Se cortó")]


# ---------------------------------------------------------------- el resumen de la mañana

def resumen(negocio: dict) -> dict:
    """El resumen del día, compuesto sin IA."""
    nid, hoy = negocio["id"], _ahora().date()
    ayer = hoy - timedelta(days=1)
    piezas = [p for p in estratega.piezas(nid, dia=hoy.isoformat()) if p["estado"] != "rechazada"]
    por_grabar = [p for p in estratega.piezas(nid, estados=("aprobada", "guion"))]
    pendientes = ap.pendientes(nid)
    with db.conexion() as con:
        publicadas = [dict(f) for f in con.execute(
            "SELECT * FROM publicaciones WHERE negocio_id = ? AND estado = 'publicada' AND programado >= ? AND programado < ?",
            (nid, ayer.isoformat(), hoy.isoformat()))]
        leads = con.execute("SELECT COUNT(*) FROM contactos WHERE negocio_id = ? AND creado >= ? AND creado < ?",
                            (nid, ayer.isoformat(), hoy.isoformat())).fetchone()[0]
        calientes = con.execute("SELECT COUNT(*) FROM conversaciones WHERE negocio_id = ? AND temperatura = 'caliente'",
                                (nid,)).fetchone()[0]
    from . import analista, aprendizaje
    despega = analista.despegando(nid, 3)
    r = {"fecha": hoy.isoformat(), "piezas": piezas, "por_grabar": por_grabar, "pendientes": pendientes,
         "despegando": despega,
         "publicadas": publicadas, "leads_ayer": leads, "calientes": calientes, "alertas": alertas(nid),
         "te_toca": publicador.te_toca(nid, antes_minutos=24 * 60), "ritmo": aprendizaje.ritmo(nid)}
    r["primero"] = lo_primero(r)
    return r


def lo_primero(r: dict) -> str:
    """Lo único que harías hoy si solo pudieras hacer una cosa: lo que tiene parado al equipo va antes que lo demás."""
    if any(a["prioridad"] == "alta" for a in r["alertas"]):
        return "arreglar lo que tiene publicaciones en pausa (mira las alertas)."
    if r["te_toca"]:
        p = r["te_toca"][0]
        return f"publicar en Instagram a las {p['programado'][11:16]}: «{p['texto'][:50]}»."
    if r["pendientes"]:
        a = r["pendientes"][0]
        return f"decidir {a['ref']} ({a['resumen']}): el equipo espera tu respuesta para seguir."
    por_grabar = [p for p in r["piezas"] if p["estado"] in ("aprobada", "guion")]
    if por_grabar:
        return f"grabar «{por_grabar[0]['titulo']}»."
    return ""


def texto_resumen(negocio: dict, r: dict | None = None) -> str:
    r = r or resumen(negocio)
    lineas = [f"Buenos días. Esto es lo de hoy en {negocio['nombre']}:"]
    if r.get("primero"):
        lineas.append(f"\n👉 Lo primero: {r['primero']}")
    if r["piezas"]:
        lineas.append("\n🎬 Graba hoy:")
        lineas += [f"• {p['titulo']} ({p['tipo_nombre'].lower()}, {p['estado_nombre'].lower()})" for p in r["piezas"]]
    elif r["por_grabar"]:
        lineas.append(f"\n🎬 Tienes {len(r['por_grabar'])} pieza{'s' if len(r['por_grabar']) != 1 else ''} aprobada{'s' if len(r['por_grabar']) != 1 else ''} sin grabar.")
    else:
        lineas.append("\n🎬 Aún no hay plan para hoy: pídelo en «Graba hoy».")
    if r.get("despegando"):
        lineas.append("\n🚀 Despegando ahora en tu nicho:")
        lineas += [f"• @{p['cuenta'].lstrip('@')} · ×{p['ritmo']:g} de lo normal a su edad · {p['texto'][:70]}"
                   for p in r["despegando"]]
    if r["pendientes"]:
        lineas.append(f"\n✅ Esperan tu aprobación ({len(r['pendientes'])}):")
        lineas += [f"• {a['ref']} · {a['resumen']}" for a in r["pendientes"][:APROBACIONES_EN_RESUMEN]]
    if r["te_toca"]:
        lineas.append("\n📲 Te toca publicar hoy en Instagram:")
        lineas += [f"• {p['programado'][11:16]} · {p['texto'][:60]}" for p in r["te_toca"]]
    lineas.append(f"\n📈 Ayer: {len(r['publicadas'])} post{'s' if len(r['publicadas']) != 1 else ''} publicado"
                  f"{'s' if len(r['publicadas']) != 1 else ''} y {r['leads_ayer']} lead{'s' if r['leads_ayer'] != 1 else ''} nuevo"
                  f"{'s' if r['leads_ayer'] != 1 else ''}." + (f" Tienes {r['calientes']} conversación"
                                                              f"{'es' if r['calientes'] != 1 else ''} caliente"
                                                              f"{'s' if r['calientes'] != 1 else ''}." if r["calientes"] else ""))
    ritmo = r.get("ritmo") or {}
    if ritmo.get("meta"):
        lineas.append(f"\n🎯 Objetivo de la semana: {ritmo['hecho']:g} de {ritmo['meta']:g} "
                      f"{UNIDADES.get(ritmo['metrica'], '')}, {RITMOS.get(ritmo['estado'], '')}")
    if r["alertas"]:
        lineas.append("\n⚠️ Alertas:")
        lineas += [f"• {a['texto']}" for a in r["alertas"]]
    return "\n".join(lineas)


def mandar_resumen(negocio: dict) -> bool:
    """Una vez al día: si ya salió hoy, no se repite."""
    nid, hoy = negocio["id"], hora_local(negocio["id"]).date().isoformat()
    if not conectado(nid) or estado.leer(nid, AGENTE).get("ultimo_resumen") == hoy:
        return False
    encolar(nid, texto_resumen(negocio), clave=f"resumen-{hoy}")
    estado.cambiar(nid, AGENTE, ultimo_resumen=hoy)
    return True


def toca_resumen(negocio_id: int, ahora: datetime | None = None) -> bool:
    ahora = ahora or hora_local(negocio_id)
    hora = _minutos(kit_marca.leer(negocio_id)["avisos"].get("hora_resumen") or "07:30")
    return hora is not None and hora <= ahora.hour * 60 + ahora.minute < hora + VENTANA_RESUMEN_HORAS * 60 and \
        estado.leer(negocio_id, AGENTE).get("ultimo_resumen") != ahora.date().isoformat()


# ---------------------------------------------------------------- el informe de la semana

def _semana_pasada(ahora: datetime) -> str:
    return (estratega.inicio_de_semana(ahora) - timedelta(days=7)).date().isoformat()


def toca_informe(negocio_id: int, ahora: datetime | None = None) -> bool:
    """Los lunes desde las 8:00, una vez por semana."""
    ahora = ahora or hora_local(negocio_id)
    return ahora.weekday() == 0 and ahora.hour >= 8 and \
        estado.leer(negocio_id, AGENTE).get("ultimo_informe") != _semana_pasada(ahora)


def lanzar_informe(negocio: dict) -> bool:
    """Prepara el informe de la semana pasada en segundo plano (usa Claude) y te lo manda. Una vez por semana, lleve o
    no el piloto automático."""
    nid, semana = negocio["id"], _semana_pasada(hora_local(negocio["id"]))
    if estado.leer(nid, AGENTE).get("ultimo_informe") == semana:
        return False
    estado.cambiar(nid, AGENTE, ultimo_informe=semana)
    jobs.en_segundo_plano(_mandar_informe, negocio)
    return True


def texto_informe(datos: dict) -> str:
    lineas = [f"📊 Tu semana del {datos['semana']}: {datos['posts']} post{'s' if datos['posts'] != 1 else ''}, "
              f"{datos['vistas']} visualizaciones y {datos['embudo']['lead']} lead{'s' if datos['embudo']['lead'] != 1 else ''}."]
    ritmo = datos.get("ritmo") or {}
    if ritmo.get("meta"):
        lineas.insert(0, f"🎯 Objetivo: {ritmo['hecho']:g} de {ritmo['meta']:g} {UNIDADES.get(ritmo['metrica'], '')}, "
                         f"{RITMOS.get(ritmo['estado'], '')}.")
    if datos.get("diagnostico"):
        lineas.append(f"\n🩺 {datos['diagnostico']}")
    if datos.get("titular"):
        lineas.append(f"\n{datos['titular']}")
    mejor, peor = datos.get("mejor"), datos.get("peor")
    if mejor and peor and mejor["id"] != peor["id"]:
        lineas.append(f"\n🏆 El mejor: «{mejor['titulo'][:60]}» (×{mejor['x']:g} de lo normal)."
                      f"\n🔻 El que menos: «{peor['titulo'][:60]}» (×{peor['x']:g}).")
    if datos.get("focos"):
        lineas.append("\nPara esta semana:\n" + "\n".join(f"• {f}" for f in datos["focos"]))
    if datos.get("mejor_hora"):
        lineas.append(f"\n🕒 Tu mejor hora hasta ahora: {datos['mejor_hora']}.")
    return "\n".join(lineas)


def _mandar_informe(negocio: dict):
    from . import aprendizaje
    try:
        datos = aprendizaje.informe_semanal(negocio)
    except Exception as e:  # noqa: BLE001 — el informe no puede tumbar el bucle
        traceback.print_exc()
        encolar(negocio["id"], f"⚠️ No he podido preparar el informe de la semana: {e}. Lo tienes en Resultados.")
        return
    encolar(negocio["id"], texto_informe(datos), clave=f"informe-{datos['semana']}")


# ---------------------------------------------------------------- avisos de aprobaciones y recordatorios

def _vista_previa(a: dict) -> str:
    d = a["datos"]
    texto = d.get("texto") or ""
    if a["tipo"] == "brief":
        texto = "\n".join(f"• {p['titulo']}" for p in d.get("vista") or [])
    elif a["tipo"] == "leccion":
        texto = d.get("regla", "")
    return texto[:1500]


@ap.al_pedir
def _avisar_aprobacion(a: dict):
    nid = a["negocio_id"]
    if not conectado(nid) or not kit_marca.leer(nid)["avisos"].get("avisar_aprobaciones"):
        return
    quien = AGENTES.get(a["agente"], {}).get("nombre", a["agente"])
    texto = f"{a['ref']} · {quien}: {a['resumen']}"
    previa = _vista_previa(a)
    if previa:
        texto += f"\n\n{previa}"
    texto += f"\n\nPara pedir cambios: «cambios {a['ref']} lo que quieres»."
    botones = [[{"text": "✅ Aprobar", "callback_data": f"ap:{a['id']}:aprobar"},
                {"text": "✖️ Rechazar", "callback_data": f"ap:{a['id']}:rechazar"}]]
    video = ""
    if a["tipo"] == "video" and a["datos"].get("edicion_id"):
        ruta = motor.carpeta(a["datos"]["edicion_id"]) / "final.mp4"
        video = str(ruta) if ruta.exists() else ""
    if video:  # el vídeo va primero y los botones en un mensaje aparte
        encolar(nid, f"{a['ref']} · {a['resumen']}", video=video)
    encolar(nid, texto, botones=botones)


def recordatorios(negocio_id: int) -> int:
    """Una hora antes de cada publicación de Instagram que haces tú: el vídeo y su texto, listos para subir."""
    n = 0
    for p in publicador.te_toca(negocio_id, antes_minutos=60):
        ruta = motor.carpeta(p["edicion_id"]) / "final.mp4"
        if encolar(negocio_id, f"📲 A las {p['programado'][11:16]} te toca publicar en Instagram. Este es el texto:\n\n"
                               f"{p['texto']}", video=str(ruta) if ruta.exists() else "", clave=f"tuyo-{p['id']}",
                   prioridad="alta"):
            n += 1
    return n


# ---------------------------------------------------------------- lo que llega de Telegram

def _decidir_por_chat(negocio: dict, ref: str, decision: str, nota: str = "") -> str:
    a = ap.por_ref(negocio["id"], ref)
    if not a:
        return f"No encuentro {ref}."
    if a["estado"] != "pendiente":
        return f"{a['ref']} ya estaba decidida ({ap.ESTADOS[a['estado']].lower()})."
    if decision == "cambios" and not nota:
        return f"Dime qué cambio: «cambios {a['ref']} lo que quieres»."
    ap.decidir(a["id"], decision, nota=nota, por="telegram")
    return {"aprobar": f"Aprobado {a['ref']}.", "rechazar": f"Rechazado {a['ref']}.",
            "cambios": f"Pedidos los cambios de {a['ref']}: el equipo se pone con ello.\n\nSi es algo que quieres "
                       "siempre, escríbeme «regla: …» y lo apunto para todo el equipo."}[decision]


def _guardar_regla(negocio: dict, regla: str) -> str:
    """El chat no es memoria: una corrección solo se queda si se apunta. La tuya entra activa, sin pasar por aprobación."""
    if not regla.strip():
        return "Dime la regla: «regla: no abras nunca con una pregunta»."
    leccion = kit_marca.anadir_leccion(negocio["id"], regla, origen="tú", evidencia="Telegram")
    if not leccion:
        return "Ya había una regla igual o muy parecida: no la repito."
    return f"Apuntado: «{leccion['regla']}». Todo el equipo la sigue desde ahora (está en el Kit, en Lecciones)."


def responder_texto(negocio: dict, texto: str) -> str:
    """Los comandos del chat. Lo que no es un comando, lo contesta Orby."""
    respuesta = _comando(negocio, texto)
    return respuesta if respuesta is not None else _preguntar_a_vega(negocio, texto.strip())


def _comando(negocio: dict, texto: str) -> str | None:
    """La respuesta a un comando, al momento y sin IA; None si no es un comando."""
    t = texto.strip()
    bajo = t.lower()
    m = re.match(r"^(aprobar|aprueba|ok|rechazar|rechaza|cambios|cambia)\s+(ap-?\d+)\s*(.*)$", bajo, re.DOTALL)
    if m:
        decision = {"aprobar": "aprobar", "aprueba": "aprobar", "ok": "aprobar", "rechazar": "rechazar",
                    "rechaza": "rechazar", "cambios": "cambios", "cambia": "cambios"}[m.group(1)]
        nota = t[m.start(3):].strip() if m.group(3) else ""
        return _decidir_por_chat(negocio, m.group(2), decision, nota)
    m = re.match(r"^(regla|lecci[oó]n|apunta)\s*:?\s*(.*)$", t, re.IGNORECASE | re.DOTALL)
    if m:
        return _guardar_regla(negocio, m.group(2))
    if bajo in ("resumen", "brief", "/resumen"):
        return texto_resumen(negocio)
    if bajo in ("aprobaciones", "/aprobaciones", "pendientes"):
        p = ap.pendientes(negocio["id"])
        return "\n".join(f"• {a['ref']} · {a['resumen']}" for a in p) if p else "No hay nada esperando tu decisión."
    m = re.match(r"^silencio\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$", bajo)
    if m and _minutos(m.group(1)) is not None and _minutos(m.group(2)) is not None:
        avisos = kit_marca.leer(negocio["id"])["avisos"]
        kit_marca.cambiar(negocio["id"], avisos={**avisos, "silencio_inicio": m.group(1).zfill(5), "silencio_fin": m.group(2).zfill(5)})
        return f"Hecho: de {m.group(1)} a {m.group(2)} solo te escribo si es urgente."
    if bajo in ("silencio no", "silencio off", "sin silencio"):
        avisos = kit_marca.leer(negocio["id"])["avisos"]
        kit_marca.cambiar(negocio["id"], avisos={**avisos, "silencio_inicio": "", "silencio_fin": ""})
        return "Quitadas las horas de silencio."
    if bajo in ("revisión", "revision", "/revision", "qué falta", "que falta", "kit"):
        return texto_revision(negocio)
    if bajo in ("ayuda", "/help", "/ayuda", "help"):
        return AYUDA
    return None


def _contestar_pregunta(negocio: dict, pregunta: str):
    """En segundo plano: mientras Claude piensa, los botones y los avisos siguen saliendo."""
    try:
        respuesta = _preguntar_a_vega(negocio, pregunta)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        respuesta = "Ahora no he podido contestarte. Prueba otra vez en un rato."
    encolar(negocio["id"], respuesta or AYUDA, prioridad="alta")  # sale en la siguiente vuelta del bucle


def _preguntar_a_vega(negocio: dict, pregunta: str) -> str:
    from .. import llm, vega
    if not llm.disponible():
        return "Ahora no puedo contestarte (falta la clave de Claude). " + AYUDA
    dueño = db.usuario(negocio["usuario_id"]) if negocio.get("usuario_id") else None
    if not dueño:
        return AYUDA
    return "".join(vega.responder(negocio, db.ultimo_informe(negocio["id"]), dueño, pregunta[:2000])).strip()


def recibir(negocio: dict) -> int:
    """Lee lo nuevo de Telegram: el código de inicio (para reconocer tu chat), botones y mensajes."""
    nid = negocio["id"]
    c = conexion(nid)
    if not c.get("token"):
        return 0
    try:
        novedades = telegram.novedades(c["token"], c.get("desde", 0))
    except telegram.ErrorTelegram:
        return 0
    atendidas = 0
    for u in novedades:
        c["desde"] = max(c.get("desde", 0), u["update_id"] + 1)
        mensaje = u.get("message") or {}
        pulsacion = u.get("callback_query") or {}
        chat = str((mensaje.get("chat") or (pulsacion.get("message") or {}).get("chat") or {}).get("id") or "")
        texto = mensaje.get("text") or ""
        if not c.get("chat"):
            # Mientras no hay chat, solo vale el /start con tu código: así nadie más puede colarse.
            if texto.strip() == f"/start {c.get('codigo')}":
                c["chat"] = chat
                _guardar_conexion(nid, c)
                telegram.enviar(c["token"], chat, f"¡Hola! Soy Orby, del equipo de {negocio['nombre']}. A partir de ahora te aviso por "
                                                  "aquí.\n\n" + AYUDA)
            continue
        if chat != c["chat"]:
            continue  # solo tu chat
        if pulsacion:
            m = re.fullmatch(r"ap:(\d+):(aprobar|rechazar)", pulsacion.get("data") or "")
            respuesta = _decidir_por_chat(negocio, m.group(1), m.group(2)) if m else "No entiendo ese botón."
            try:
                telegram.contestar_boton(c["token"], pulsacion["id"], respuesta)
                original = pulsacion.get("message") or {}
                if original.get("message_id"):
                    telegram.quitar_botones(c["token"], chat, original["message_id"],
                                            (original.get("text") or "") + f"\n\n→ {respuesta}")
            except telegram.ErrorTelegram:
                pass
        elif texto and not texto.startswith("/start"):
            respuesta = _comando(negocio, texto)
            if respuesta is None:
                jobs.en_segundo_plano(_contestar_pregunta, negocio, texto.strip())
            else:
                encolar(nid, respuesta, prioridad="alta")
        atendidas += 1
    _guardar_conexion(nid, {**conexion(nid), "desde": c.get("desde", 0), "chat": c.get("chat", "")})
    return atendidas


# ---------------------------------------------------------------- el bucle

def ciclo(negocio: dict):
    """Una vuelta para un negocio: leer Telegram, avisos, resumen si toca y mandar lo pendiente."""
    nid = negocio["id"]
    recibir(negocio)
    for a in alertas(nid):
        if a["prioridad"] == "alta" or a.get("avisar"):  # lo demás espera al resumen de la mañana
            encolar(nid, "⚠️ " + a["texto"], clave=a["clave"], prioridad=a["prioridad"], contar=False,
                    cada_minutos=a.get("cada", AGRUPAR_MINUTOS))
    recordatorios(nid)
    if toca_resumen(nid):
        mandar_resumen(negocio)
    from . import piloto
    if toca_informe(nid) and not piloto.activo(nid):  # con el piloto encendido, el informe lo lanza el piloto
        lanzar_informe(negocio)
    despachar(nid)


def negocios_con_telegram() -> list[dict]:
    with db.conexion() as con:
        ids = [f["negocio_id"] for f in con.execute("SELECT negocio_id FROM conexiones WHERE servicio = 'telegram'")]
    return [n for n in (db.negocio(i) for i in ids) if n]


_bucle = threading.Event()


def arrancar_bucle():
    """Un hilo que da una vuelta cada pocos segundos mientras la app está abierta."""
    if _bucle.is_set():
        return
    _bucle.set()

    def vueltas():
        from . import piloto
        while True:
            try:
                from .. import limpieza
                limpieza.si_toca()  # los vídeos que ya no hacen falta, fuera del disco
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            con_telegram = {n["id"]: n for n in negocios_con_telegram()}
            con_piloto = {n["id"]: n for n in piloto.negocios_con_piloto()}
            for nid, negocio in {**con_telegram, **con_piloto}.items():
                try:
                    with claves.en(nid):  # cada negocio, con sus claves
                        if nid in con_piloto:
                            piloto.vuelta(negocio)  # el horario del equipo
                        if nid in con_telegram:
                            ciclo(negocio)  # Telegram, avisos y resumen
                except Exception:  # noqa: BLE001 — un negocio con un problema no para a los demás
                    traceback.print_exc()
            time.sleep(CADA_SEGUNDOS)
    threading.Thread(target=vueltas, daemon=True).start()



# ---------------------------------------------------------------- revisión del Kit

MIN_COMPETIDORES = 6


def revision(negocio: dict) -> list[dict]:
    """Lo que le falta al Kit para que el equipo trabaje sin suponer nada del negocio, de lo que más pesa a lo que
    menos. Cada falta dice qué agente lo necesita y dónde se completa (casi todo sale de las llamadas del onboarding)."""
    from . import analista
    nid, base = negocio["id"], f"/negocios/{negocio['id']}"
    kit = kit_marca.leer(nid)
    voz, cta = kit["voz"], kit.get("cta") or {}
    onboarding, en_kit = f"{base}/onboarding#llamadas", f"{base}/kit"
    competidores = [c for c in analista.cuentas(nid) if not c.get("propia")]
    fuentes = [f for f in kit.get("fuentes") or [] if not re.search(r"\btu (sector|nicho)\b", f.get("valor", ""))]
    faltas = [
        (not voz.get("resumen"), "Tu voz: sube tus llamadas o vídeos tuyos para que los textos suenen a ti",
         ["guionista"], onboarding),
        (not kit["pruebas"], "Pruebas: casos, resultados y testimonios. Sin ellas no se usa ni una cifra",
         ["guionista"], f"{en_kit}#pruebas"),
        (not (kit.get("contexto") or {}).get("frases_cliente"), "Frases reales de tus clientes (de llamadas o DMs)",
         ["guionista", "estratega"], onboarding),
        (not any(o.get("url") for o in kit.get("ofertas") or []), "Tu oferta con su enlace y cómo se empieza",
         ["guionista", "publicador"], onboarding),
        (not cta.get("web"), "La web a la que llevan los enlaces de tus posts", ["publicador"], onboarding),
        (not (kit.get("angulos") or {}).get("principal"), "Tu ángulo: la idea que atraviesa todo lo que publicas",
         ["estratega"], onboarding),
        (len(voz.get("posiciones") or []) < 3, "De 3 a 5 opiniones tuyas que no todo el mundo comparte",
         ["guionista", "estratega"], onboarding),
        (len(competidores) < MIN_COMPETIDORES, f"Cuentas que seguir: hay {len(competidores)} y hacen falta "
         f"{MIN_COMPETIDORES} o más", ["analista"], f"{base}/investigacion"),
        (not fuentes, "Fuentes de noticias de tu nicho (búsquedas, RSS o Reddit)", ["analista"], onboarding),
        (len(kit.get("hashtags") or []) < 3, "De 10 a 20 hashtags de tu nicho", ["publicador"], onboarding),
    ]
    return [{"texto": texto, "agentes": agentes, "quien": ", ".join(AGENTES[a]["nombre"] for a in agentes),
             "enlace": enlace} for falta, texto, agentes, enlace in faltas if falta]


def texto_revision(negocio: dict) -> str:
    faltas = revision(negocio)
    if not faltas:
        return "El Kit está completo: el equipo tiene todo lo que necesita de tu negocio."
    return (f"Al Kit le faltan {len(faltas)} cosa{'s' if len(faltas) != 1 else ''}, de la más a la menos importante:\n" +
            "\n".join(f"• {f['texto']} ({f['quien']})" for f in faltas) +
            "\n\nCasi todo sale de las llamadas del onboarding.")


# ---------------------------------------------------------------- primeros pasos

def primeros_pasos(negocio: dict) -> list[dict]:
    """Lo que falta para que el equipo trabaje solo, en orden. Cada paso dice si está hecho y dónde se hace."""
    from .. import config, llm
    from . import analista, comunidad, estratega, identidad, llamadas, piloto
    nid, base = negocio["id"], f"/negocios/{negocio['id']}"
    kit = kit_marca.leer(nid)
    ob = llamadas.vista(nid)  # el onboarding es la base de todo: va justo después de conectar Claude
    # «agentes»: a quién despierta cada paso en la sala de «Hoy». Telegram es opcional y no cuenta.
    todos = list(AGENTES)
    return [
        {"texto": "Conectar Claude (tu plan o una clave)", "hecho": llm.disponible(), "enlace": f"{base}/conectores#claude",
         "agentes": todos},
        {"texto": "Onboarding: tus datos y tus redes", "hecho": ob["respondidas"] >= len(llamadas.PREGUNTAS),
         "enlace": f"{base}/onboarding#preguntas", "agentes": ["analista", "estratega"]},
        {"texto": "Onboarding: subir las llamadas y aprobar la ficha y el Kit",
         "hecho": bool(ob["aplicado"]) or bool(kit["voz"]["resumen"] and kit["pruebas"]),
         "enlace": f"{base}/onboarding#llamadas", "agentes": ["analista", "estratega", "guionista", "comunidad"]},
        {"texto": "Completar el Kit (lo que no salió de las llamadas)", "hecho": not revision(negocio),
         "enlace": f"{base}/kit", "agentes": []},  # con huecos, el equipo trabaja con puntos de partida neutros
        {"texto": "Kit visual: tu paleta, tu tipografía y tu movimiento",
         "hecho": bool(identidad.leer(nid)["colores"]),
         "enlace": f"{base}/kit#identidad", "agentes": []},  # Monti edita igual con el estilo de la casa
        {"texto": "Conectar Apify para leer posts", "hecho": config.apify_activo(), "enlace": f"{base}/conectores#apify",
         "agentes": ["analista"]},
        {"texto": "Primer escaneo de tu nicho", "hecho": bool(estado.leer(nid, analista.AGENTE).get("ultimo")),
         "enlace": f"{base}/investigacion", "agentes": ["analista"]},
        {"texto": "Aprobar tu primer «Graba hoy»", "hecho": bool(estratega.piezas(nid, estados=estratega.EN_MARCHA)),
         "enlace": f"{base}/estrategia", "agentes": ["estratega"]},
        {"texto": "Conectar Zernio para publicar", "hecho": publicador.conectado(nid), "enlace": f"{base}/conectores#zernio",
         "agentes": ["publicador"]},
        {"texto": "Conectar ManyChat para los DMs", "hecho": comunidad.conectado(nid), "enlace": f"{base}/conectores#manychat",
         "agentes": ["comunidad"]},
        {"texto": "Encender el piloto automático", "hecho": piloto.activo(nid), "enlace": f"{base}/hoy#piloto",
         "agentes": []},
    ]
