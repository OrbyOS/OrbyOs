"""La sala de control de «Hoy»: qué hace cada agente ahora mismo, lo que tiene en su pantalla y lo último que ha
pasado. La página la pide cada pocos segundos y anima los cambios."""
from datetime import datetime, timedelta

from .. import db
from ..modules import edicion as motor
from . import (AGENTES, analista, aprendizaje, comunidad, estado, estratega, guionista, jefa, piloto, produccion,
               publicador)
from . import aprobaciones as ap

COLORES = {"jefa": "#3D7BFF", "analista": "#22D3EE", "estratega": "#FBBF24", "guionista": "#F472B6",
           "editor": "#34D399", "publicador": "#A78BFA", "comunidad": "#FB7185"}
# El camino del trabajo: de la investigación a la comunidad (y de vuelta, con lo aprendido).
CADENA = ["analista", "estratega", "guionista", "editor", "publicador", "comunidad"]
TAREA_AGENTE = {"Escanear cuentas": "analista", "Preparar «Graba hoy»": "estratega", "Leer los DMs": "comunidad",
                "Crear los DMs automáticos": "comunidad", "Comprobar publicaciones": "publicador",
                "Métricas y post-mortems": "analista", "Informe semanal": "jefa"}


def _agente(clave: str, estado_: str, texto: str, cifra: int | float | str, etiqueta: str, pantalla: list | None = None,
            enlace: str = "", accion: dict | None = None) -> dict:
    a = AGENTES[clave]
    return {"clave": clave, "nombre": a["nombre"], "rol": a["rol"], "color": COLORES[clave], "estado": estado_,
            "texto": texto, "cifra": cifra, "etiqueta": etiqueta, "pantalla": pantalla or [], "enlace": enlace,
            "accion": accion, "hace": a["texto"]}


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def estado_sala(negocio: dict) -> dict:
    nid, base = negocio["id"], f"/negocios/{negocio['id']}"
    ahora = datetime.now()
    agentes = []

    # Orby · coordinación
    pendientes = ap.pendientes(nid)
    alertas = jefa.alertas(nid)
    agentes.append(_agente(
        "jefa", "atencion" if pendientes or alertas else "listo",
        (f"{_plural(len(pendientes), 'cosa espera', 'cosas esperan')} tu aprobación" if pendientes else "Todo al día")
        + (f" · {_plural(len(alertas), 'alerta', 'alertas')}" if alertas else ""),
        len(pendientes), "por aprobar", [{"texto": a["resumen"], "ref": a["ref"]} for a in pendientes[:4]],
        f"{base}/aprobaciones", {"texto": "Mandarme el resumen", "url": f"{base}/hoy/resumen"} if jefa.conectado(nid) else None))

    # Lupi · investigación
    e = estado.leer(nid, analista.AGENTE)
    destacados = analista.destacados(nid, limite=8)
    ultimo = e.get("ultimo")
    agentes.append(_agente(
        "analista", "trabajando" if e.get("trabajando") else ("listo" if destacados else "esperando"),
        "Escaneando tu nicho…" if e.get("trabajando") else (
            f"{_plural(len(destacados), 'post destaca', 'posts destacan')} en tu nicho" if destacados else
            "Aún no ha escaneado tu nicho"),
        len(destacados), "destacan",
        [{"imagen": p["imagen"], "cuenta": p["cuenta"], "x": p["x"], "url": p["url"]} for p in destacados[:6]],
        f"{base}/investigacion",
        None if e.get("trabajando") else {"texto": "Escanear ahora", "url": f"{base}/investigacion/escanear"}))

    # Plani · estrategia
    e = estado.leer(nid, estratega.AGENTE)
    hoy = [p for p in estratega.piezas(nid, dia=ahora.date().isoformat()) if p["estado"] != "rechazada"]
    agentes.append(_agente(
        "estratega", "trabajando" if e.get("trabajando") else ("listo" if hoy else "esperando"),
        "Preparando el «Graba hoy»…" if e.get("trabajando") else (
            f"{_plural(len(hoy), 'pieza', 'piezas')} para grabar hoy" if hoy else "Sin plan para hoy"),
        len(hoy), "para hoy", [{"texto": p["titulo"], "tipo": p["tipo_nombre"]} for p in hoy[:4]],
        f"{base}/estrategia",
        None if e.get("trabajando") or hoy else {"texto": "Planificar hoy", "url": f"{base}/estrategia/planificar"}))

    # Escri · guiones
    e = estado.leer(nid, guionista.AGENTE)
    gs = guionista.guiones(nid, estados=("pendiente", "aprobado", "bloqueado"))
    listos = [g for g in gs if g["estado"] == "aprobado"]
    bloqueados = [g for g in gs if g["estado"] == "bloqueado"]
    agentes.append(_agente(
        "guionista", "trabajando" if e.get("trabajando") else ("atencion" if bloqueados else ("listo" if gs else "esperando")),
        "Escribiendo guiones…" if e.get("trabajando") else (
            f"{_plural(len(listos), 'guion listo', 'guiones listos')} para grabar" if gs else "Esperando un plan aprobado"),
        len(listos), "para grabar", [{"texto": (g["texto"] or "")[:70], "clave": g["palabra_clave"]} for g in gs[:4]],
        f"{base}/guiones"))

    # Monti · edición
    tomas = produccion.tomas(nid)
    en_marcha = [t for t in tomas if t["etapa"] in ("en_cola", "cortando", "plan", "montando")]
    para_ti = [t for t in tomas if t["etapa"] == "revisar"]
    agentes.append(_agente(
        "editor", "trabajando" if en_marcha else ("atencion" if para_ti else ("listo" if tomas else "esperando")),
        (f"Editando «{en_marcha[0]['titulo'][:40]}»" if en_marcha else (
            f"{_plural(len(para_ti), 'vídeo listo', 'vídeos listos')} para revisar" if para_ti else
            ("Sin tomas por editar" if tomas else "Esperando tus tomas"))),
        len(tomas), "reels",
        [{"titulo": t["titulo"], "etapa": t["etapa_nombre"],
          "portada": f"/ediciones/{t['id']}/portada" if (motor.carpeta(t["id"]) / "portada.jpg").exists() else "",
          "video": f"/ediciones/{t['id']}/video" if (motor.carpeta(t["id"]) / "final.mp4").exists() else ""}
         for t in tomas[:6]],
        f"{base}/produccion"))

    # Publi · publicación
    proximas = [p for p in publicador.publicaciones(nid, desde=ahora.isoformat(timespec="minutes"))
                if p["estado"] in ("programada", "tu_publicas")]
    semana = [p for p in publicador.publicaciones(nid, desde=(ahora - timedelta(days=7)).isoformat(timespec="minutes"))
              if p["estado"] == "publicada"]
    te_toca = publicador.te_toca(nid)
    agentes.append(_agente(
        "publicador", "atencion" if te_toca else ("listo" if proximas or semana else "esperando"),
        ("Te toca publicar en Instagram" if te_toca else (
            f"Próxima: {proximas[0]['red_nombre']} a las {proximas[0]['programado'][11:16]}" if proximas else
            "Nada programado")),
        len(semana), "esta semana", [{"red": p["red_nombre"], "hora": p["programado"][5:16].replace("T", " ")}
                                     for p in proximas[:4]],
        f"{base}/publicacion"))

    # Chati · comunidad
    e = estado.leer(nid, comunidad.AGENTE)
    convs = comunidad.bandeja(nid)
    calientes = [c for c in convs if c["temperatura"] == "caliente"]
    contactos_semana = [c for c in comunidad.contactos(nid, 200) if c["creado"] >= (ahora - timedelta(days=7)).isoformat()]
    agentes.append(_agente(
        "comunidad", "trabajando" if e.get("trabajando") else ("atencion" if calientes else ("listo" if convs else "esperando")),
        "Leyendo tus DMs…" if e.get("trabajando") else (
            f"{_plural(len(calientes), 'conversación caliente', 'conversaciones calientes')}" if calientes else
            f"{_plural(len(contactos_semana), 'lead', 'leads')} esta semana"),
        len(contactos_semana), "leads", [{"texto": c["participante"] or "Sin nombre", "temp": c["temperatura"]}
                                        for c in convs[:4]],
        f"{base}/comunidad",
        {"texto": "Leer DMs", "url": f"{base}/comunidad/leer"} if publicador.conectado(nid) and not e.get("trabajando") else None))

    # Quien tiene un primer paso pendiente está «en reposo» hasta que lo hagas.
    pasos = jefa.primeros_pasos(negocio)
    for a in agentes:
        falta = next((p for p in pasos if not p["hecho"] and a["clave"] in p["agentes"]), None)
        a["dormido"] = {"texto": falta["texto"], "enlace": falta["enlace"]} if falta else None

    return {"agentes": agentes, "cadena": CADENA, "metricas": metricas(nid), "eventos": eventos(negocio),
            "pasos": pasos, "muros": muros(nid, analista.destacados(nid, limite=20), tomas),
            "panel": panel_mando(nid, len(pendientes)),
            "piloto": piloto.activo(nid), "generado": ahora.isoformat(timespec="seconds")}


def panel_mando(negocio_id: int, por_aprobar: int = 0) -> dict:
    """El panel de debajo de la oficina: todo el embudo, de lo que se detecta en el nicho a los leads, con lo que
    hay en marcha en cada paso. Ventana: los últimos 14 días."""
    ahora = datetime.now()
    hace14 = (ahora - timedelta(days=14)).isoformat(timespec="minutes")
    with db.conexion() as con:
        leidos = con.execute("SELECT COUNT(*) FROM posts p JOIN cuentas c ON c.id = p.cuenta_id "
                             "WHERE p.negocio_id = ? AND c.propia = 0", (negocio_id,)).fetchone()[0]
    cuentas = [c for c in analista.cuentas(negocio_id) if not c.get("propia")]
    destacan = len(analista.destacados(negocio_id, limite=500))
    piezas = [p for p in estratega.piezas(negocio_id, desde=hace14) if p["estado"] != "rechazada"]
    hoy = [p for p in piezas if p.get("dia") == ahora.date().isoformat()]
    gs = guionista.guiones(negocio_id, estados=("pendiente", "aprobado", "bloqueado", "grabado"))
    listos = [g for g in gs if g["estado"] == "aprobado"]
    bloqueados = [g for g in gs if g["estado"] == "bloqueado"]
    tomas = produccion.tomas(negocio_id)
    editando = [t for t in tomas if t["etapa"] in ("en_cola", "cortando", "plan", "montando")]
    para_ti = [t for t in tomas if t["etapa"] == "revisar"]
    terminados = [t for t in tomas if t["etapa"] in ("revisar", "aprobado")]
    pubs = publicador.publicaciones(negocio_id, desde=hace14)
    publicadas = [p for p in pubs if p["estado"] == "publicada"]
    programadas = [p for p in publicador.publicaciones(negocio_id, desde=ahora.isoformat(timespec="minutes"))
                   if p["estado"] in ("programada", "tu_publicas")]
    leads = [c for c in comunidad.contactos(negocio_id, 500) if (c["creado"] or "") >= hace14]
    calientes = [c for c in comunidad.bandeja(negocio_id) if c["temperatura"] == "caliente"]
    m = metricas(negocio_id)
    embudo = [
        {"clave": "analista", "etapa": "Detectado", "valor": destacan, "unidad": "posts que destacan",
         "detalle": f"{_plural(leidos, 'post leído', 'posts leídos')} de {_plural(len(cuentas), 'cuenta', 'cuentas')}"},
        {"clave": "estratega", "etapa": "Planificado", "valor": len(piezas), "unidad": "piezas",
         "detalle": f"{_plural(len(hoy), 'pieza', 'piezas')} para grabar hoy"},
        {"clave": "guionista", "etapa": "Escrito", "valor": len(gs), "unidad": "guiones",
         "detalle": f"{len(listos)} para grabar" + (f" · {len(bloqueados)} sin pasar el validador" if bloqueados else "")},
        {"clave": "editor", "etapa": "Editado", "valor": len(terminados), "unidad": "vídeos",
         "detalle": f"{len(editando)} en edición · {len(para_ti)} para revisar"},
        {"clave": "publicador", "etapa": "Publicado", "valor": len(publicadas), "unidad": "publicaciones",
         "detalle": f"{_plural(len(programadas), 'programada', 'programadas')}"},
        {"clave": "analista", "etapa": "Visto", "valor": m["vistas_14d"], "unidad": "visualizaciones",
         "detalle": f"×{str(m['x_medio']).replace('.', ',')} sobre tu normal"},
        {"clave": "comunidad", "etapa": "Leads", "valor": len(leads), "unidad": "contactos",
         "detalle": f"{_plural(len(calientes), 'conversación caliente', 'conversaciones calientes')}"},
    ]
    return {"embudo": embudo, "por_aprobar": por_aprobar, "contenido": contenido(negocio_id, hace14), "dias": 14}


def contenido(negocio_id: int, desde: str) -> dict:
    """Lo que dice tu contenido publicado: el mejor post, cuánto se comparte y se comenta, cómo va cada red, qué rasgo
    funciona mejor y a qué hora."""
    todos = aprendizaje.mis_posts(negocio_id)
    recientes = [p for p in todos if (p["programado"] or "") >= desde]
    mejor = max(recientes or todos, key=lambda p: (p.get("x") or 0, p["vistas"]), default=None)
    vistas = sum(p["vistas"] for p in recientes)
    envios = [p["envios"] for p in recientes if p["vistas"]]
    por_red: dict[str, int] = {}
    for p in recientes:
        por_red[p["red"]] = por_red.get(p["red"], 0) + p["vistas"]
    funciona = None
    for dim, filas in aprendizaje.que_funciona(todos).items():
        for f in filas:
            if not f["hueco"] and f["veredicto"] in ("claro_mejor", "mejor") and (not funciona or f["mediana"] > funciona["mediana"]):
                funciona = {"dimension": aprendizaje.DIMENSIONES.get(dim, dim), "valor": f["valor"], "mediana": f["mediana"], "subida": f["subida"], "n": f["n"]}
    return {
        "mejor": {"titulo": mejor["titulo"], "vistas": mejor["vistas"], "x": mejor.get("x"), "red": mejor["red"],
                  "url": mejor["url"]} if mejor else None,
        "envios_mil": round(1000 * sum(envios) / len(envios), 1) if envios else 0,
        "comentarios": sum(p["comentarios"] for p in recientes),
        "por_red": sorted(({"red": r, "vistas": v} for r, v in por_red.items()), key=lambda d: -d["vistas"]),
        "funciona": funciona, "mejor_franja": aprendizaje.mapa_horas(todos)["mejor"] if todos else None,
        "publicados": len(recientes), "vistas_por_post": round(vistas / len(recientes)) if recientes else 0,
    }


def metricas(negocio_id: int) -> dict:
    posts = aprendizaje.mis_posts(negocio_id)
    hoy = datetime.now().date()
    dias = [(hoy - timedelta(days=13 - i)).isoformat() for i in range(14)]
    por_dia = {d: 0 for d in dias}
    for p in posts:
        if p["programado"][:10] in por_dia:
            por_dia[p["programado"][:10]] += p["vistas"]
    recientes = posts[:10]
    ritmo = aprendizaje.ritmo(negocio_id)
    return {"vistas_14d": sum(por_dia.values()), "serie": [por_dia[d] for d in dias], "dias": dias,
            "x_medio": round(sum(p["x"] for p in recientes) / len(recientes), 2) if recientes else 0,
            "posts": len(posts), "objetivo": ritmo}


def eventos(negocio: dict, limite: int = 24) -> list[dict]:
    """Lo último que ha pasado, de todos los agentes, del más reciente al más antiguo."""
    nid = negocio["id"]
    salida = []
    for r in estado.leer(nid, piloto.AGENTE).get("registro") or []:
        salida.append({"cuando": r["cuando"], "agente": TAREA_AGENTE.get(r["tarea"], "jefa"),
                       "texto": f"{r['tarea']}: {r['resultado']}"})
    for a in ap.de_negocio(nid, limite=15):
        salida.append({"cuando": a["creado"], "agente": a["agente"], "texto": f"Pide tu OK: {a['resumen']}"})
        if a["estado"] != "pendiente" and a["decidido"]:
            salida.append({"cuando": a["decidido"], "agente": "jefa",
                           "texto": f"{ap.ESTADOS[a['estado']]}: {a['resumen']}"})
    for t in produccion.tomas(nid)[:10]:
        salida.append({"cuando": t["creado"], "agente": "editor", "texto": f"«{t['titulo'][:50]}» · {t['etapa_nombre']}"})
    for p in publicador.publicaciones(nid)[-10:]:
        salida.append({"cuando": p["creado"], "agente": "publicador",
                       "texto": f"{p['red_nombre']} · {p['estado_nombre'].lower()} para el {p['programado'][8:10]}/{p['programado'][5:7]}"})
    for c in comunidad.contactos(nid, 10):
        salida.append({"cuando": c["creado"], "agente": "comunidad",
                       "texto": f"Nuevo lead: {c['nombre'] or c['usuario'] or c['email']}" + (f" ({c['palabra']})" if c["palabra"] else "")})
    for c in analista.cuentas(nid):
        if c["ultimo_escaneo"]:
            salida.append({"cuando": c["ultimo_escaneo"], "agente": "analista",
                           "texto": f"Ha escaneado {c['usuario'] if c['usuario'].startswith('@') else '@' + c['usuario']}"})
    salida = [e for e in salida if e["cuando"]]
    salida.sort(key=lambda e: e["cuando"], reverse=True)
    vistos, unicos = set(), []
    for e in salida:
        clave = (e["agente"], e["texto"])
        if clave not in vistos:
            vistos.add(clave)
            unicos.append({**e, "nombre": AGENTES.get(e["agente"], {}).get("nombre", ""),
                           "color": COLORES.get(e["agente"], "#94A3B8")})
    return unicos[:limite]


def _vistas_por_edicion(negocio_id: int) -> dict[int, int]:
    """Visualizaciones de cada vídeo editado, sumando sus redes (la última foto de cada publicación)."""
    import json
    vistas: dict[int, int] = {}
    with db.conexion() as con:
        for f in con.execute(
                "SELECT p.edicion_id, m.datos FROM publicaciones p JOIN metricas m ON m.publicacion_id = p.id "
                "WHERE p.negocio_id = ? ORDER BY m.id", (negocio_id,)):
            vistas[f["edicion_id"]] = vistas.get(f["edicion_id"], 0) + int(json.loads(f["datos"]).get("vistas") or 0)
    return vistas


def muros(negocio_id: int, destacados: list[dict], tomas: list[dict]) -> dict:
    """Las dos paredes de la sala. A la izquierda, lo que destaca en tu nicho. A la derecha, tus reels (los vídeos
    editados se reproducen); si aún no hay, más de tu nicho. Los vídeos de fuera pueden caducar: entonces se ve la
    portada."""
    vistas = _vistas_por_edicion(negocio_id)
    tuyos = []
    for t in tomas[:12]:
        carpeta = motor.carpeta(t["id"])
        portada = f"/ediciones/{t['id']}/portada" if (carpeta / "portada.jpg").exists() else ""
        video = f"/ediciones/{t['id']}/video" if (carpeta / "final.mp4").exists() else ""
        if portada or video:
            tuyos.append({"video": video, "imagen": portada, "titulo": t["titulo"], "vistas": vistas.get(t["id"]),
                          "etiqueta": t["etapa_nombre"]})
    for p in analista.tus_posts(negocio_id, limite=12):
        if p["imagen"] or p["video_url"]:
            tuyos.append({"video": p["video_url"], "imagen": p["imagen"], "titulo": (p["texto"] or "")[:60],
                          "vistas": p["vistas"], "x": p["x"], "url": p["url"]})
    nicho = [{"video": p["video_url"], "imagen": p["imagen"], "cuenta": p["cuenta"], "vistas": p["vistas"],
              "x": p["x"], "url": p["url"], "titulo": (p["texto"] or "")[:60]} for p in destacados]
    izq = {"titulo": "Lo que destaca en tu nicho", "items": nicho[:10],
           "vacio": "Cuando Lupi escanee tu nicho, aquí verás lo que mejor funciona"}
    if tuyos:
        der = {"titulo": "Tus reels", "items": tuyos[:10], "tuyos": True}
    else:
        der = {"titulo": "Más de tu nicho", "items": nicho[10:20] or nicho[::-1][:10],
               "vacio": "Tus reels aparecerán aquí en cuanto Monti edite el primero"}
    return {"izq": izq, "der": der}
