"""Piloto automático: el equipo trabaja con horario, dentro de la autonomía que le das a cada agente.

Con el piloto encendido, mientras Radar esté abierto (en tu ordenador o en un servidor):
- 06:00 · Lupi escanea tus cuentas y las de tu competencia (por rotación, con el presupuesto de Apify).
- 07:00 de lunes a viernes · Plani prepara el «Graba hoy» (y el día de grabación, la semana entera).
- Cada 2 horas, de 8 a 22 · Chati clasifica los DMs que no se hayan clasificado ya y prepara las respuestas.
- Cada hora · se preparan las guías de las palabras clave nuevas, se comprueba ManyChat y se hacen las fotos de las métricas y los post-mortems.
- Cada 10 minutos · Publi comprueba qué se ha publicado.
- Lunes 08:00 · el informe semanal, que también te llega a Telegram.
- Cada 6 horas, de 8 a 22 · Lupi mira las noticias de tu nicho; si hay una para grabar, te avisa.
- Una vez al mes · Lupi puntúa tu perfil.
Si una tarea del día falla (o la app se cerró mientras Lupi escaneaba o Plani planificaba), se vuelve a intentar una
vez, media hora después, y Orby te avisa.
Lo que cuesta dinero respeta los presupuestos del mes (Apify y Claude). Lo que sale en público sigue pasando por tus
aprobaciones salvo que pongas a ese agente en piloto automático.
"""
import os
import traceback
from datetime import datetime, timedelta

from .. import db, jobs, llm
from . import aprendizaje, analista, comunidad, estado, estratega, jefa, publicador
from . import kit as kit_marca

AGENTE = "piloto"
PRESUPUESTO_CLAUDE_MES = float(os.getenv("RADAR_PRESUPUESTO_CLAUDE", "40"))  # $ al mes por negocio

AJUSTES = {"activo": False, "hora_escaneo": "06:00", "hora_plan": "07:00", "dia_grabacion": 6,  # 6 = domingo; -1 = ninguno
           "tareas": {}}

# clave: (nombre, cuándo, usa Claude)
TAREAS = {
    "escaneo": ("Escanear cuentas", "Cada día a la hora del escaneo", True),
    "plan": ("Preparar «Graba hoy»", "De lunes a viernes a la hora del plan; el día de grabación, la semana", True),
    "bandeja": ("Leer los DMs", "Cada 2 horas, de 8 a 22", True),
    "descubrir": ("Buscar cuentas nuevas", "Los lunes a las 9:00, con las búsquedas de su cliente", True),
    "seguimiento": ("Seguir lo que despega", "Cada 6 horas, de 8 a 23, solo las cuentas con posts recientes", True),
    "dm_auto": ("Preparar las guías y comprobar ManyChat", "Cada hora", False),
    "publicaciones": ("Comprobar publicaciones", "Cada 10 minutos", False),
    "metricas": ("Métricas y post-mortems", "Cada hora", True),
    "informe": ("Informe semanal", "Los lunes a las 8:00", True),
    "noticias": ("Noticias del nicho", "Cada 6 horas, de 8 a 22 (unas 3 veces al día)", True),
    "perfil": ("Nota de tu perfil", "Una vez al mes", True),
}
REINTENTO = timedelta(minutes=30)
EN_SEGUNDO_PLANO = {"escaneo": analista.AGENTE, "plan": estratega.AGENTE}  # su fallo se ve en el estado del agente
CADA = {"noticias": timedelta(hours=6), "perfil": timedelta(days=30), "bandeja": timedelta(hours=2), "seguimiento": timedelta(hours=6), "dm_auto": timedelta(hours=1), "publicaciones": timedelta(minutes=10),
        "metricas": timedelta(hours=1)}


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _dia_del_kit(texto: str) -> int | None:
    """El día de grabación que se dijo en el onboarding («el domingo», «Lunes») como número (0 = lunes)."""
    t = (texto or "").lower().replace("miercoles", "miércoles").replace("sabado", "sábado")
    return next((i for i, d in enumerate(DIAS) if d in t), None)


def ajustes(negocio_id: int) -> dict:
    kit = kit_marca.leer(negocio_id)
    guardados = kit.get("piloto") or {}
    a = {**AJUSTES, **guardados}
    if "dia_grabacion" not in guardados and _dia_del_kit(kit.get("dia_grabacion")) is not None:
        a["dia_grabacion"] = _dia_del_kit(kit["dia_grabacion"])  # mientras no lo cambies en el piloto, el del Kit
    a["tareas"] = {t: (guardados.get("tareas") or {}).get(t, True) for t in TAREAS}
    return a


def activo(negocio_id: int) -> bool:
    return bool(ajustes(negocio_id)["activo"])


def _hora(texto: str, defecto: str) -> tuple[int, int]:
    try:
        h, m = (texto or defecto).split(":")
        return int(h), int(m)
    except ValueError:
        h, m = defecto.split(":")
        return int(h), int(m)


def gasto_claude_del_mes(negocio_id: int) -> float:
    inicio = datetime.now().strftime("%Y-%m-01T00:00:00")
    with db.conexion() as con:
        return float(con.execute("SELECT COALESCE(SUM(coste_claude), 0) FROM gastos WHERE negocio_id = ? AND creado >= ?",
                                 (negocio_id, inicio)).fetchone()[0])


def toca(tarea: str, a: dict, ultimo: str | None, ahora: datetime) -> bool:
    """¿Le toca a esta tarea ahora? Las diarias, una vez al día a partir de su hora; las periódicas, cada X."""
    previo = datetime.fromisoformat(ultimo) if ultimo else None
    if tarea in CADA:
        if tarea in ("bandeja", "noticias") and not 8 <= ahora.hour < 22 or \
                tarea == "seguimiento" and not 8 <= ahora.hour < 23 or tarea == "perfil" and ahora.hour < 9:
            return False
        return previo is None or ahora - previo >= CADA[tarea]
    if tarea == "escaneo":
        h, m = _hora(a["hora_escaneo"], "06:00")
        return (ahora.hour, ahora.minute) >= (h, m) and (previo is None or previo.date() < ahora.date())
    if tarea == "plan":
        h, m = _hora(a["hora_plan"], "07:00")
        dia_lote = ahora.weekday() == a.get("dia_grabacion", -1)
        if ahora.weekday() >= 5 and not dia_lote:
            return False
        return (ahora.hour, ahora.minute) >= (h, m) and (previo is None or previo.date() < ahora.date())
    if tarea == "descubrir":
        return ahora.weekday() == 0 and ahora.hour >= 9 and (previo is None or previo.date() < ahora.date())
    if tarea == "informe":
        return ahora.weekday() == 0 and ahora.hour >= 8 and (previo is None or previo.date() < ahora.date())
    return False


def _hacer(negocio: dict, tarea: str, a: dict, ahora: datetime) -> str:
    """Hace la tarea (lo que tarda, en un hilo aparte). Devuelve una línea para el registro."""
    nid = negocio["id"]
    if tarea == "escaneo":
        if not analista.cuentas(nid):
            return "Sin cuentas que escanear."
        if estado.leer(nid, analista.AGENTE).get("trabajando"):
            return "Ya estaba escaneando."
        toca_hoy, motivo = analista.toca_escanear_hoy(nid, ahora)
        if not toca_hoy:
            return motivo
        estado.cambiar(nid, analista.AGENTE, trabajando=True, avisos=[])
        jobs.en_segundo_plano(analista.trabajo_escaneo, nid, None)
        return "Escaneo lanzado."
    if tarea == "plan":
        if any(p["estado"] != "rechazada" for p in estratega.piezas(nid, dia=ahora.date().isoformat())):
            return "Ya había plan para hoy."
        if estado.leer(nid, estratega.AGENTE).get("trabajando"):
            return "Plani ya estaba trabajando."
        lote = ahora.weekday() == a.get("dia_grabacion", -1)
        if not lote and not estratega.faltan_semana(nid):
            return "La semana ya tiene todas sus piezas: hoy no hace falta plan."
        estado.cambiar(nid, estratega.AGENTE, trabajando=True, avisos=[])
        jobs.en_segundo_plano(estratega.trabajo_planificar, negocio, lote, "", None)
        return "Plan de la semana lanzado." if lote else "«Graba hoy» lanzado."
    if tarea == "descubrir":
        jobs.en_segundo_plano(analista.trabajo_descubrir, negocio)
        return "Buscando cuentas nuevas en tu nicho."
    if tarea == "seguimiento":
        if estado.leer(nid, analista.AGENTE).get("trabajando"):
            return "Lupi estaba escaneando."
        jobs.en_segundo_plano(analista.trabajo_seguimiento, nid)
        return "Mirando lo que despega."
    if tarea == "bandeja":
        if not comunidad.conectado(nid):
            return "Sin ManyChat: no hay DMs que clasificar."
        jobs.en_segundo_plano(comunidad.sincronizar_bandeja, negocio)
        return "Clasificando DMs."
    if tarea == "dm_auto":
        avisos = comunidad.sincronizar_automatizaciones(negocio) if comunidad.conectado(nid) else []
        return " ".join(avisos) or "Palabras clave al día."
    if tarea == "publicaciones":
        return f"{publicador.actualizar_estados(nid)} publicaciones actualizadas."
    if tarea == "metricas":  # los post-mortems usan Claude: en un hilo aparte, para no frenar a los demás
        jobs.en_segundo_plano(aprendizaje.actualizar, negocio)
        return "Haciendo las fotos de las métricas y los post-mortems."
    if tarea == "noticias":  # si hay una noticia caliente y lista, Lupi avisa por Orby
        from . import noticias
        jobs.en_segundo_plano(noticias.trabajo_noticias, nid)
        return "Mirando las noticias de tu nicho."
    if tarea == "perfil":
        from . import analista_web
        jobs.en_segundo_plano(analista_web.trabajo_perfil, nid)
        return "Puntuando tu perfil."
    if tarea == "informe":
        return "Preparando el informe semanal." if jefa.lanzar_informe(negocio) else "El informe ya se había mandado."
    return ""


def _fallo(nid: int, tarea: str, e: dict, ultimo: str | None) -> bool:
    """¿Falló la última vez que se hizo esta tarea?"""
    if ultimo and (e.get("fallidas") or {}).get(tarea) == ultimo:
        return True
    return tarea in EN_SEGUNDO_PLANO and bool(jefa.paradas(nid, EN_SEGUNDO_PLANO[tarea]))


def reintentar(tarea: str, e: dict, nid: int, ultimo: str | None, ahora: datetime) -> bool:
    """Una tarea del día que falló hoy se vuelve a intentar una vez, media hora después."""
    if tarea in CADA or not ultimo or ultimo[:10] != ahora.date().isoformat():
        return False  # las periódicas ya se repiten solas
    if (e.get("reintentos") or {}).get(tarea) == ahora.date().isoformat():
        return False
    return ahora - datetime.fromisoformat(ultimo) >= REINTENTO and _fallo(nid, tarea, e, ultimo)


def vuelta(negocio: dict, ahora: datetime | None = None) -> list[str]:
    """Una vuelta del piloto para un negocio: hace lo que toca y lo anota."""
    nid = negocio["id"]
    a = ajustes(nid)
    if not a["activo"]:
        return []
    ahora = ahora or jefa.hora_local(nid)
    e = estado.leer(nid, AGENTE)
    ultimos, registro, hechas = dict(e.get("ultimos") or {}), list(e.get("registro") or []), []
    fallidas, reintentos = dict(e.get("fallidas") or {}), dict(e.get("reintentos") or {})
    sin_presupuesto = gasto_claude_del_mes(nid) >= PRESUPUESTO_CLAUDE_MES
    for tarea, (nombre, _cuando, usa_claude) in TAREAS.items():
        if not a["tareas"].get(tarea, True):
            continue
        otra_vez = reintentar(tarea, e, nid, ultimos.get(tarea), ahora)
        if not otra_vez and not toca(tarea, a, ultimos.get(tarea), ahora):
            continue
        if otra_vez:
            reintentos[tarea] = ahora.date().isoformat()
        ultimos[tarea] = ahora.isoformat(timespec="seconds")
        if usa_claude and (sin_presupuesto or not llm.disponible()):
            linea = ("Saltada: se ha llegado al presupuesto de Claude del mes." if sin_presupuesto
                     else "Saltada: falta conectar Claude.")
            if sin_presupuesto:
                jefa.encolar(nid, f"⚠️ El piloto automático se ha parado en lo que usa Claude: llevas "
                                  f"{gasto_claude_del_mes(nid):.2f} $ este mes, de {PRESUPUESTO_CLAUDE_MES:.0f} $.",
                             clave=f"presupuesto-claude-{ahora:%Y-%m}", prioridad="alta")
        else:
            try:
                linea = _hacer(negocio, tarea, a, ahora)
            except Exception as ex:  # noqa: BLE001 — una tarea rota no para las demás
                traceback.print_exc()
                linea = f"Error: {ex}"
                fallidas[tarea] = ultimos[tarea]
                otra = tarea not in CADA and not otra_vez
                jefa.encolar(nid, f"⚠️ El piloto no ha podido «{nombre}»: {ex}." +
                             (" Lo vuelvo a intentar en media hora." if otra else ""),
                             clave=f"piloto-{tarea}-{ahora:%Y-%m-%d}-{'2' if otra_vez else '1'}", contar=False,
                             cada_minutos=24 * 60)
            if otra_vez:
                linea = "Segundo intento: " + linea
        registro.insert(0, {"cuando": ultimos[tarea], "tarea": nombre, "resultado": linea})
        hechas.append(tarea)
    if hechas:
        estado.cambiar(nid, AGENTE, ultimos=ultimos, registro=registro[:40], fallidas=fallidas, reintentos=reintentos)
    return hechas


def negocios_con_piloto() -> list[dict]:
    with db.conexion() as con:
        ids = [f["negocio_id"] for f in con.execute("SELECT negocio_id FROM kits")]
    return [n for n in (db.negocio(i) for i in ids if activo(i)) if n]

