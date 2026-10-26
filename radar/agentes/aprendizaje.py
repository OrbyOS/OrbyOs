"""Aprendizaje: lo que hace que el equipo mejore cada semana.

- Fotos de cada post a la hora, a las 24 h, 72 h, 7 días y 30 días (de Zernio o, si lo publicaste tú, del escaneo de tu
  cuenta). Cada post se mide contra TU normal: x = visualizaciones ÷ la mediana de tus últimos posts en esa red.
- Además de x: ritmo del primer día, envíos (compartidos + guardados por visualización), seguidores por cada mil
  visualizaciones y la tasa de salto en los 3 primeros segundos cuando la red la da.
- Qué funciona: por gancho, carril, formato, etapa, tipo de pieza, llamada a la acción, duración y hora de publicación,
  la mediana de x, cuánto sube o baja respecto a lo normal, cuántos posts hay y un intervalo. Si no hay datos
  suficientes, lo dice («Faltan datos») en vez de adivinar.
- Cuándo publicar: día × franja horaria, con los huecos con pocos posts acercados a lo normal para que un golpe de suerte
  no corone una hora.
- Post-mortem de cada post que despega (×2 o más), de cada uno que no funciona (menos de ×0,6 o un salto del 70 %) y de
  cada récord: los 3 primeros segundos, las causas por orden, dónde falló y qué hacer después.
- Objetivo de la semana (leads, seguidores, llamadas o ventas) con su ritmo: cumplido, en camino, en riesgo o por detrás.
- De tu web llegan clics, leads, llamadas y ventas con su utm_content: cada uno se atribuye al post que lo trajo.
- El informe semanal reúne todo con una lista de focos, cada uno apoyado en una cifra.
"""
import json
import random
import secrets
from datetime import datetime, timedelta
from statistics import median

from .. import db, llm
from ..connectors import zernio
from ..llm import ErrorIA
from . import aprobaciones as ap
from . import estratega, guionista, publicador, validador
from . import kit as kit_marca

AGENTE = "analista"
MOMENTOS = [("1h", timedelta(hours=1)), ("24h", timedelta(hours=24)), ("72h", timedelta(hours=72)),
            ("7d", timedelta(days=7)), ("30d", timedelta(days=30))]
BASE_POSTS = 30            # tus últimos posts en esa red que forman tu «normal»
MIN_N = 5                  # posts necesarios para opinar de una dimensión
DESPEGUE_X, FLOP_X, FLOP_SALTO = 2.0, 0.6, 0.7
FRANJA_HORAS, MIN_N_FRANJA, PRIOR_N = 3, 3, 3
OBJETIVOS = {"leads": "Leads a la semana", "seguidores": "Seguidores nuevos a la semana",
             "llamadas": "Llamadas a la semana", "ventas": "Ventas a la semana (€)"}
DIMENSIONES = {"gancho": "Gancho", "carril": "Carril", "formato": "Formato", "etapa": "Etapa", "tipo": "Tipo de pieza",
               "cta": "Llamada a la acción", "duracion": "Duración", "franja": "Hora de publicación"}
VEREDICTOS = {"claro_mejor": "Claramente mejor", "mejor": "Tiende a mejor", "igual": "Como siempre",
              "peor": "Tiende a peor", "claro_peor": "Claramente peor"}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _ahora() -> datetime:
    return datetime.now()


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


# ---------------------------------------------------------------- fotos de las métricas

def _de_tu_escaneo(negocio_id: int, url: str) -> dict | None:
    """Si el post lo publicaste tú, sus números salen del escaneo de tu cuenta (Investigación)."""
    if not url:
        return None
    with db.conexion() as con:
        f = con.execute("SELECT vistas, likes, comentarios, compartidos FROM posts WHERE negocio_id = ? AND url = ?",
                        (negocio_id, url.split("?")[0])).fetchone()
    return dict(f) if f else None


def leer_metricas(negocio_id: int, p: dict) -> dict | None:
    if p["externo_id"] and publicador.conectado(negocio_id):
        try:
            return zernio.metricas_post(publicador.clave(negocio_id), p["externo_id"])
        except zernio.ErrorZernio:
            return None
    return _de_tu_escaneo(negocio_id, p["url"])


def capturar(negocio_id: int) -> int:
    """Hace las fotos que tocan (1 h, 24 h, 72 h, 7 días, 30 días) de las publicaciones ya publicadas."""
    ahora, hechas = _ahora(), 0
    with db.conexion() as con:
        pubs = [dict(f) for f in con.execute("SELECT * FROM publicaciones WHERE negocio_id = ? AND estado = 'publicada'",
                                             (negocio_id,))]
        tomadas = {(f["publicacion_id"], f["momento"]) for f in con.execute(
            "SELECT publicacion_id, momento FROM metricas WHERE negocio_id = ?", (negocio_id,))}
    for p in pubs:
        inicio = datetime.fromisoformat(p["programado"])
        orden = [m for m, _ in MOMENTOS]
        ultima = max((orden.index(m) for pid, m in tomadas if pid == p["id"]), default=-1)
        debidas = [m for i, (m, d) in enumerate(MOMENTOS) if i > ultima and ahora >= inicio + d]
        if not debidas:
            continue
        datos = leer_metricas(negocio_id, p)
        if not datos:
            continue
        with db.conexion() as con:
            # Una foto tardía vale para el momento más reciente que toca; las anteriores que se perdieron, no se inventan.
            con.execute("INSERT OR IGNORE INTO metricas (negocio_id, publicacion_id, momento, capturado, datos) VALUES "
                        "(?, ?, ?, ?, ?)", (negocio_id, p["id"], debidas[-1], _iso(ahora), json.dumps(datos)))
        hechas += 1
    return hechas


def _ultima_foto(fotos: list[dict]) -> dict:
    orden = [m for m, _ in MOMENTOS]
    return max(fotos, key=lambda f: orden.index(f["momento"])) if fotos else {}


# ---------------------------------------------------------------- tus posts con su x

def _duracion(s: float) -> str:
    return "menos de 30 s" if s < 30 else ("30-45 s" if s < 45 else ("45-60 s" if s < 60 else "más de 60 s"))


def _segundos(g: dict | None, reel: dict) -> float | None:
    """Lo que dura el reel: la duración real del vídeo montado o, en un guion para leer de los de antes, sus palabras.
    Una estructura (Escri) no dice cuánto dura cada reel: de una salen 3-4."""
    if reel.get("segundos"):
        return reel["segundos"]
    texto = (g or {}).get("texto") or ""
    if not texto or texto.lstrip().lower().startswith("idea:"):
        return None
    return validador.contar_palabras(texto) / validador.PALABRAS_POR_SEGUNDO


def _reels(negocio_id: int) -> dict[int, dict]:
    """De cada edición: su duración final, qué reel es de su estructura (n de m), su título y su primera frase."""
    with db.conexion() as con:
        filas = con.execute(
            "SELECT id, json_extract(resultado, '$.duracion_final') AS segundos, "
            "json_extract(datos, '$.produccion.reel.n') AS n, json_extract(datos, '$.produccion.reel.de') AS de, "
            "json_extract(datos, '$.produccion.reel.titulo') AS titulo, json_extract(datos, '$.frases[0].texto') AS gancho "
            "FROM ediciones WHERE negocio_id = ?", (negocio_id,)).fetchall()
    return {f["id"]: dict(f) for f in filas}


def _franja(momento: str) -> str:
    d = datetime.fromisoformat(momento)
    inicio = d.hour // FRANJA_HORAS * FRANJA_HORAS
    return f"{DIAS[d.weekday()]} {inicio:02d}-{inicio + FRANJA_HORAS:02d} h"


def _patron_gancho(gancho_fuente: str) -> str:
    g = (gancho_fuente or "").lower()
    if "plantilla" in g or "remix" in g:
        return "Remix del original"
    if "banco propio" in g:
        return "De tus ganchos"
    if "competencia" in g:
        return "De la competencia"
    return "Nuevo"


def mis_posts(negocio_id: int) -> list[dict]:
    """Cada publicación publicada con sus números, su x frente a tu normal en esa red y sus características."""
    with db.conexion() as con:
        pubs = [dict(f) for f in con.execute("SELECT * FROM publicaciones WHERE negocio_id = ? AND estado = 'publicada' "
                                             "ORDER BY programado", (negocio_id,))]
        fotos: dict[int, list] = {}
        for f in con.execute("SELECT * FROM metricas WHERE negocio_id = ?", (negocio_id,)):
            fotos.setdefault(f["publicacion_id"], []).append({**dict(f), "datos": json.loads(f["datos"])})
    carriles = {c["id"]: c["nombre"] for c in kit_marca.leer(negocio_id)["carriles"]}
    reels = _reels(negocio_id)
    salida, por_red = [], {}
    for p in pubs:
        ultima = _ultima_foto(fotos.get(p["id"], []))
        if not ultima:
            continue
        d = ultima["datos"]
        primer_dia = next((f["datos"]["vistas"] for f in fotos[p["id"]] if f["momento"] in ("24h", "1h")), None)
        g = guionista.guion(negocio_id, p["guion_id"]) if p["guion_id"] else None
        pieza = estratega.pieza(negocio_id, g["pieza_id"]) if g else None
        vistas = d.get("vistas") or 0
        reel = reels.get(p["edicion_id"]) or {}
        titulo = (pieza or {}).get("titulo") or p["texto"][:80]
        if reel.get("de") and reel["de"] > 1:  # de una estructura salen varios reels: cada uno se mide aparte
            titulo = f"{reel.get('titulo') or titulo} (reel {reel['n']} de {reel['de']})"
        segundos = _segundos(g, reel)
        post = {
            "id": p["id"], "plataforma": p["plataforma"], "red": publicador.REDES.get(p["plataforma"], p["plataforma"]),
            "programado": p["programado"], "url": p["url"], "titulo": titulo,
            "vistas": vistas, "momento": ultima["momento"], "primer_dia": primer_dia,
            "envios": round(((d.get("compartidos") or 0) + (d.get("guardados") or 0)) / vistas, 4) if vistas else 0,
            "seguidores_mil": round(1000 * d["seguidores"] / vistas, 2) if vistas and d.get("seguidores") is not None else None,
            "salto": d.get("salto"), "comentarios": d.get("comentarios") or 0, "gancho_texto": "",
            "rasgos": {"gancho": _patron_gancho((g or {}).get("gancho_fuente", "")),
                       "carril": carriles.get((pieza or {}).get("carril"), (pieza or {}).get("carril") or "Sin carril"),
                       "formato": (pieza or {}).get("formato") or "Sin dato", "etapa": ((pieza or {}).get("etapa") or "—").upper(),
                       "tipo": estratega.TIPOS.get((pieza or {}).get("tipo"), "Sin guion"),
                       "cta": validador.CTAS.get((g or {}).get("cta"), "Sin dato"),
                       "duracion": _duracion(segundos) if segundos else "Sin dato",
                       "franja": _franja(p["programado"])},
        }
        if reel.get("gancho"):  # lo primero que dice en el reel montado
            post["gancho_texto"] = reel["gancho"]
        elif g and segundos:  # un guion para leer de los de antes
            post["gancho_texto"] = " ".join(validador.frases(g["texto"])[:1])
        por_red.setdefault(p["plataforma"], []).append(post)
        salida.append(post)
    # x contra la mediana de tus posts anteriores en la misma red (o de todos, si aún no hay anteriores).
    for red, lista in por_red.items():
        for i, post in enumerate(lista):
            previos = [q["vistas"] for q in lista[max(0, i - BASE_POSTS):i]] or [q["vistas"] for q in lista]
            base = median(previos) if previos else 0
            post["x"] = round(post["vistas"] / base, 2) if base else 1.0
            post["primer_dia_x"] = None
            dias = [q["primer_dia"] for q in lista[max(0, i - BASE_POSTS):i] if q["primer_dia"]]
            if post["primer_dia"] and dias and median(dias):
                post["primer_dia_x"] = round(post["primer_dia"] / median(dias), 2)
    return sorted(salida, key=lambda p: p["programado"], reverse=True)


# ---------------------------------------------------------------- qué funciona

def _intervalo(valores: list[float], veces: int = 300, semilla: int = 7) -> tuple[float, float]:
    """Intervalo del 80 % de la mediana, remuestreando (bootstrap)."""
    azar = random.Random(semilla)
    medias = sorted(median(azar.choices(valores, k=len(valores))) for _ in range(veces))
    return medias[int(0.1 * veces)], medias[int(0.9 * veces) - 1]


def veredicto(mediana_: float, bajo: float, alto: float) -> str:
    if bajo > 1.1:
        return "claro_mejor"
    if alto < 0.9:
        return "claro_peor"
    if mediana_ > 1.1:
        return "mejor"
    if mediana_ < 0.9:
        return "peor"
    return "igual"


def que_funciona(posts: list[dict], resultado: str = "x") -> dict[str, list[dict]]:
    """Por cada dimensión y valor: n, mediana del resultado frente a lo normal, intervalo y veredicto. Un valor con
    menos de MIN_N posts sale como hueco («Faltan datos»)."""
    validos = [p for p in posts if p.get(resultado) is not None]
    if not validos:
        return {}
    valores = [p[resultado] for p in validos]
    # Tu normal: la mediana o, si más de la mitad son cero (pasa con los envíos), la media.
    base = median(valores) or (sum(valores) / len(valores))
    if not base:
        return {}
    salida = {}
    for dim in DIMENSIONES:
        grupos: dict[str, list[float]] = {}
        for p in validos:
            grupos.setdefault(p["rasgos"][dim], []).append(p[resultado] / base)
        filas = []
        for valor, xs in grupos.items():
            if len(xs) < MIN_N:
                filas.append({"valor": valor, "n": len(xs), "hueco": True})
                continue
            m = median(xs)
            bajo, alto = _intervalo(xs)
            filas.append({"valor": valor, "n": len(xs), "mediana": round(m, 2), "subida": round((m - 1) * 100),
                          "bajo": round(bajo, 2), "alto": round(alto, 2), "veredicto": veredicto(m, bajo, alto),
                          "hueco": False})
        salida[dim] = sorted(filas, key=lambda f: (f["hueco"], -(f.get("mediana") or 0)))
    return salida


def mapa_horas(posts: list[dict]) -> dict:
    """Día × franja: la x media acercada a 1 con PRIOR_N posts imaginarios normales. Solo se nombra «mejor hora» a las
    franjas con al menos MIN_N_FRANJA posts."""
    celdas: dict[str, list[float]] = {}
    for p in posts:
        celdas.setdefault(p["rasgos"]["franja"], []).append(p["x"])
    tabla = {k: {"n": len(xs), "x": round((sum(xs) + PRIOR_N) / (len(xs) + PRIOR_N), 2)} for k, xs in celdas.items()}
    candidatas = [(k, v) for k, v in tabla.items() if v["n"] >= MIN_N_FRANJA]
    mejor = max(candidatas, key=lambda kv: kv[1]["x"])[0] if candidatas else None
    return {"celdas": tabla, "mejor": mejor}


def peso_de_carril(negocio_id: int) -> dict[str, float]:
    """Para Plani: cuánto rinde cada carril frente a lo normal (solo con datos suficientes)."""
    posts = mis_posts(negocio_id)
    if len(posts) < 20:  # hasta tener unos 20 posts tuyos, mandan las señales de la competencia
        return {}
    carriles = {c["nombre"]: c["id"] for c in kit_marca.leer(negocio_id)["carriles"]}
    return {carriles[f["valor"]]: f["mediana"] for f in que_funciona(posts).get("carril", [])
            if not f["hueco"] and f["valor"] in carriles}


# ---------------------------------------------------------------- post-mortems

ESQUEMA_PM = llm.obj(primeros_segundos=llm.S, causas=llm.lista(llm.S), donde=llm.S, siguiente=llm.S)

SISTEMA_PM = """Escribes el post-mortem de un vídeo corto de una marca personal, en español, con la misma profundidad si
fue bien que si fue mal. Te paso su guion, su gancho, sus números frente a lo normal de la cuenta y sus rasgos.
- primeros_segundos: qué pasa en los 3 primeros segundos y si engancha.
- causas: de 2 a 4, de la más a la menos probable, cada una apoyada en un dato que te paso.
- donde: en qué paso del proceso se ganó o se perdió (idea, gancho, guion, edición, hora de publicación…).
- siguiente: una acción concreta para el próximo vídeo.
No inventes cifras que no te haya dado."""


def postmortems(negocio_id: int, limite: int = 30) -> list[dict]:
    with db.conexion() as con:
        filas = [dict(f) for f in con.execute("SELECT * FROM postmortems WHERE negocio_id = ? ORDER BY id DESC LIMIT ?",
                                              (negocio_id, limite))]
    for f in filas:
        f["datos"] = json.loads(f["datos"])
    return filas


def preparar_postmortems(negocio: dict, posts: list[dict] | None = None) -> int:
    """Los despegues, los flops y los récords que aún no tienen post-mortem (solo con la foto de 72 h o más)."""
    nid = negocio["id"]
    posts = posts if posts is not None else mis_posts(nid)
    with db.conexion() as con:
        hechos = {(f["publicacion_id"], f["tipo"]) for f in con.execute(
            "SELECT publicacion_id, tipo FROM postmortems WHERE negocio_id = ?", (nid,))}
    record = max((p["x"] for p in posts), default=0)
    nuevos = 0
    for p in posts:
        if p["momento"] in ("1h", "24h"):
            continue
        tipo = ("record" if p["x"] == record and len(posts) >= 3 else
                "despegue" if p["x"] >= DESPEGUE_X else
                "flop" if p["x"] < FLOP_X or (p["salto"] or 0) >= FLOP_SALTO else None)
        if not tipo or (p["id"], tipo) in hechos:
            continue
        datos = {"titulo": p["titulo"], "x": p["x"], "vistas": p["vistas"], "red": p["red"]}
        if llm.disponible():
            peticion = (kit_marca.contexto(negocio) + "\n\n## El vídeo\n" + json.dumps(
                {k: p[k] for k in ("titulo", "red", "vistas", "x", "primer_dia_x", "envios", "seguidores_mil", "salto",
                                   "gancho_texto", "rasgos")}, ensure_ascii=False, indent=1))
            try:
                datos.update(llm.json_con_esquema(SISTEMA_PM, peticion, ESQUEMA_PM, effort="low"))
            except ErrorIA:
                pass
        with db.conexion() as con:
            con.execute("INSERT OR IGNORE INTO postmortems (negocio_id, publicacion_id, creado, tipo, x, datos) VALUES "
                        "(?, ?, ?, ?, ?, ?)", (nid, p["id"], _iso(_ahora()), tipo, p["x"], json.dumps(datos, ensure_ascii=False)))
        if datos.get("siguiente") and tipo in ("despegue", "record"):
            ap.proponer_leccion(nid, AGENTE, datos["siguiente"], f"Post-mortem de «{p['titulo']}» (×{p['x']:g})")
        nuevos += 1
    return nuevos


# ---------------------------------------------------------------- tu web: clics, leads, llamadas y ventas

def token_web(negocio_id: int) -> str:
    k = kit_marca.leer(negocio_id)
    if not k.get("token_web"):
        k = kit_marca.cambiar(negocio_id, token_web=secrets.token_urlsafe(12))
    return k["token_web"]


def negocio_por_token_web(token: str) -> int | None:
    with db.conexion() as con:
        for f in con.execute("SELECT negocio_id, datos FROM kits"):
            if json.loads(f["datos"]).get("token_web") == token:
                return f["negocio_id"]
    return None


def anotar_evento(negocio_id: int, tipo: str, utm_content: str = "", visitante: str = "", importe: float = 0) -> bool:
    if tipo not in ("clic", "lead", "llamada", "venta"):
        return False
    with db.conexion() as con:
        con.execute("INSERT INTO eventos (negocio_id, creado, tipo, utm_content, visitante, importe) VALUES (?, ?, ?, ?, ?, ?)",
                    (negocio_id, _iso(_ahora()), tipo, utm_content.strip().lower()[:120], visitante.strip()[:120],
                     max(0.0, float(importe or 0))))
    return True


def embudo(negocio_id: int, desde: str | None = None) -> dict:
    """Clics, leads, llamadas y ventas por post. Cada visitante cuenta para el primer post que le trajo."""
    with db.conexion() as con:
        eventos = [dict(f) for f in con.execute("SELECT * FROM eventos WHERE negocio_id = ? ORDER BY creado", (negocio_id,))]
        contactos = [dict(f) for f in con.execute("SELECT * FROM contactos WHERE negocio_id = ?", (negocio_id,))]
    primero: dict[str, str] = {}
    for e in eventos:
        if e["visitante"] and e["utm_content"]:
            primero.setdefault(e["visitante"], e["utm_content"])
    por_post: dict[str, dict] = {}
    totales = {"clic": 0, "lead": 0, "llamada": 0, "venta": 0, "importe": 0.0}
    for e in eventos:
        if desde and e["creado"] < desde:
            continue
        origen = primero.get(e["visitante"], e["utm_content"]) or "sin origen"
        fila = por_post.setdefault(origen, {"clic": 0, "lead": 0, "llamada": 0, "venta": 0, "importe": 0.0})
        fila[e["tipo"]] += 1
        totales[e["tipo"]] += 1
        if e["tipo"] == "venta":
            fila["importe"] += e["importe"]
            totales["importe"] += e["importe"]
    # Los correos que deja la gente en tus guías también son leads (con el utm del DM).
    for c in contactos:
        if c["origen"] != "guia" or (desde and c["creado"] < desde):
            continue
        utm = next((x.split("=", 1)[1] for x in c["utm"].split("&") if x.startswith("utm_content=")), "") or c["palabra"].lower()
        por_post.setdefault(utm or "sin origen", {"clic": 0, "lead": 0, "llamada": 0, "venta": 0, "importe": 0.0})["lead"] += 1
        totales["lead"] += 1
    return {"por_post": dict(sorted(por_post.items(), key=lambda kv: -kv[1]["importe"] - kv[1]["lead"])),
            "totales": totales}


# ---------------------------------------------------------------- el objetivo de la semana

def ritmo(negocio_id: int, ahora: datetime | None = None) -> dict:
    """Cómo vas con tu objetivo esta semana: lo hecho frente a lo que tocaría a estas alturas."""
    ahora = ahora or _ahora()
    objetivo = kit_marca.leer(negocio_id)["objetivo"]
    lunes = estratega.inicio_de_semana(ahora)
    e = embudo(negocio_id, desde=_iso(lunes))["totales"]
    if objetivo["metrica"] == "seguidores":
        hecho = sum((p.get("seguidores_mil") or 0) * p["vistas"] / 1000 for p in mis_posts(negocio_id)
                    if p["programado"] >= _iso(lunes))
    else:
        hecho = {"leads": e["lead"], "llamadas": e["llamada"], "ventas": e["importe"]}.get(objetivo["metrica"], 0)
    meta = float(objetivo["valor"] or 0)
    avance = (ahora - lunes).total_seconds() / (7 * 86400)
    esperado = meta * avance
    proyeccion = hecho / avance if avance > 0.05 else None
    if meta and hecho >= meta:
        estado = "cumplido"
    elif hecho >= esperado * 0.9:
        estado = "en_camino"
    elif hecho >= esperado * 0.6:
        estado = "en_riesgo"
    else:
        estado = "por_detras"
    return {"metrica": objetivo["metrica"], "nombre": OBJETIVOS.get(objetivo["metrica"], ""), "meta": meta,
            "hecho": round(hecho, 1), "esperado": round(esperado, 1), "proyeccion": round(proyeccion, 1) if proyeccion else None,
            "estado": estado}


# ---------------------------------------------------------------- frente a la competencia

def frente_a_competencia(negocio_id: int) -> list[dict]:
    """Tu post típico frente al de cada cuenta que sigues (medianas), por red."""
    with db.conexion() as con:
        filas = con.execute("SELECT c.usuario, c.plataforma, c.propia, p.vistas FROM posts p JOIN cuentas c ON "
                            "c.id = p.cuenta_id WHERE p.negocio_id = ?", (negocio_id,)).fetchall()
    grupos: dict[tuple, list[int]] = {}
    for f in filas:
        grupos.setdefault((f["plataforma"], f["usuario"], bool(f["propia"])), []).append(f["vistas"])
    salida = [{"plataforma": k[0], "cuenta": k[1], "propia": k[2], "mediana": median(v), "n": len(v)}
              for k, v in grupos.items() if v]
    return sorted(salida, key=lambda f: (f["plataforma"], not f["propia"], -f["mediana"]))


# ---------------------------------------------------------------- ¿gancho o perfil?

MIN_DIAGNOSTICO = 3


def diagnostico(posts: list[dict]) -> str:
    """Pocas vistas es un problema de gancho; vistas que no traen seguidores, un problema de perfil. Se separan antes
    de recomendar nada (si no hay datos suficientes, no se dice nada)."""
    con_seg = [p for p in posts if p.get("seguidores_mil") is not None]
    viajan = [p for p in con_seg if p["x"] >= DESPEGUE_X * 0.75]
    if len(viajan) >= MIN_DIAGNOSTICO and len(con_seg) >= 2 * MIN_DIAGNOSTICO:
        normal = median(p["seguidores_mil"] for p in con_seg)
        if normal and median(p["seguidores_mil"] for p in viajan) < 0.6 * normal:
            return ("Tus vídeos que más viajan casi no te traen seguidores: el problema no es el gancho, es tu perfil "
                    "(bio, foto, destacados y enlace). Revísalo antes de cambiar los vídeos.")
    recientes = [p for p in posts[:10] if p.get("salto") is not None]
    if len(recientes) >= 2 * MIN_DIAGNOSTICO and median(p["salto"] for p in recientes) >= FLOP_SALTO:
        return (f"Más de la mitad de la gente se va en los 3 primeros segundos en tus últimos {len(recientes)} vídeos: "
                "el problema está en el gancho. Ahí es donde hay que trabajar primero.")
    return ""


# ---------------------------------------------------------------- el informe semanal

ESQUEMA_INFORME = llm.obj(titular=llm.S, focos=llm.lista(llm.S))


def informe_semanal(negocio: dict, ahora: datetime | None = None) -> dict:
    """El informe de la semana pasada (o de la actual si se pide a mitad). Se guarda uno por semana."""
    nid = negocio["id"]
    ahora = ahora or _ahora()
    lunes = estratega.inicio_de_semana(ahora) - timedelta(days=7)
    domingo = lunes + timedelta(days=7)
    todos = mis_posts(nid)
    semana = [p for p in todos if _iso(lunes) <= p["programado"] < _iso(domingo)]
    funciona = que_funciona(todos)
    lifts = [(DIMENSIONES[d], f) for d, filas in funciona.items() for f in filas if not f["hueco"]]
    with db.conexion() as con:
        gasto = con.execute("SELECT COALESCE(SUM(coste_claude), 0), COALESCE(SUM(coste_apify), 0) FROM gastos WHERE "
                            "negocio_id = ? AND creado >= ? AND creado < ?", (nid, _iso(lunes), _iso(domingo))).fetchone()
    datos = {
        "semana": lunes.date().isoformat(),
        "posts": len(semana), "vistas": sum(p["vistas"] for p in semana),
        "mejor": max(semana, key=lambda p: p["x"], default=None), "peor": min(semana, key=lambda p: p["x"], default=None),
        "suben": [{"dim": d, **f} for d, f in lifts if f["veredicto"] in ("claro_mejor", "mejor")][:5],
        "bajan": [{"dim": d, **f} for d, f in lifts if f["veredicto"] in ("claro_peor", "peor")][:5],
        "huecos": [f"{DIMENSIONES[d]}: {f['valor']} ({f['n']} posts)" for d, filas in funciona.items() for f in filas
                   if f["hueco"]][:8],
        "embudo": embudo(nid, desde=_iso(lunes))["totales"], "ritmo": ritmo(nid, domingo - timedelta(seconds=1)),
        "mejor_hora": mapa_horas(todos)["mejor"], "competencia": frente_a_competencia(nid)[:8],
        "gasto": {"claude": round(gasto[0], 2), "apify": round(gasto[1], 2)},
        "diagnostico": diagnostico(todos), "titular": "", "focos": [],
    }
    if llm.disponible() and semana:
        resumen = {k: datos[k] for k in ("posts", "vistas", "suben", "bajan", "embudo", "ritmo", "mejor_hora",
                                         "diagnostico", "huecos")}
        resumen["mejor"] = datos["mejor"] and {k: datos["mejor"][k] for k in ("titulo", "x", "vistas", "rasgos")}
        resumen["peor"] = datos["peor"] and {k: datos["peor"][k] for k in ("titulo", "x", "vistas", "rasgos")}
        try:
            r = llm.json_con_esquema(
                "Escribes el informe semanal de contenido de un negocio, en español y sin palabras de moda. Un titular "
                "de una frase que empieza por el objetivo y cómo va (ritmo). Después, de 1 a 3 focos para la semana que "
                "viene: cada uno, algo que el dueño puede hacer (grabar, cambiar o probar) apoyado en una cifra de los "
                "datos. Lo que está en «huecos» son datos que faltan, nunca un hallazgo. Si hay diagnóstico, el primer "
                "foco va de eso. No inventes cifras.", json.dumps(resumen, ensure_ascii=False, default=str),
                ESQUEMA_INFORME, effort="low")
            datos.update(titular=r.get("titular", ""), focos=r.get("focos") or [])
        except ErrorIA:
            pass
    with db.conexion() as con:
        con.execute("INSERT INTO informes_semanales (negocio_id, semana, creado, datos) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(negocio_id, semana) DO UPDATE SET creado = excluded.creado, datos = excluded.datos",
                    (nid, datos["semana"], _iso(ahora), json.dumps(datos, ensure_ascii=False, default=str)))
    return datos


def ultimo_informe(negocio_id: int) -> dict | None:
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM informes_semanales WHERE negocio_id = ? ORDER BY semana DESC LIMIT 1",
                        (negocio_id,)).fetchone()
    return json.loads(f["datos"]) if f else None


def actualizar(negocio: dict) -> dict:
    """Lo que se hace al abrir Resultados (y, en piloto automático, cada pocas horas)."""
    publicador.actualizar_estados(negocio["id"])
    publicador.emparejar_instagram(negocio["id"])
    fotos = capturar(negocio["id"])
    posts = mis_posts(negocio["id"])
    return {"fotos": fotos, "postmortems": preparar_postmortems(negocio, posts) if fotos else 0}

