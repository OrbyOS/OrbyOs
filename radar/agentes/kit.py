"""El Kit de marca: lo que todos los agentes leen antes de escribir. La oferta y el cliente ideal salen de la ficha
del negocio; aquí se guarda lo que la ficha no tiene: la voz, los carriles de contenido, el reparto por etapas, el
inventario de pruebas (la única fuente de cifras), las frases prohibidas, las lecciones y la autonomía de cada agente.

El código es genérico: todo lo que depende del negocio (sus límites, su manera de grabar, su llamada a la acción, sus
hashtags…) sale del onboarding y vive aquí. Sin dato, cada campo tiene un punto de partida neutro; los «presets» por
tipo de negocio dan los de arranque (carriles, reparto, publicación, fuentes y llamada a la acción)."""
import json
import re
import secrets
from datetime import datetime

from .. import db, llm, onboarding
from . import AGENTES, AUTONOMIA_INICIAL, AUTONOMIAS

ETAPAS = {"tofu": "Atraer (TOFU)", "mofu": "Convencer (MOFU)", "bofu": "Vender (BOFU)"}
MEZCLA_INICIAL = {"tofu": 50, "mofu": 30, "bofu": 20}

# Un punto de partida para marca personal, infoproducto y servicios. Cada negocio los cambia.
CARRILES_INICIALES = [
    {"id": "mito", "nombre": "Mito que cuesta dinero", "cuota": 2, "etapa": "tofu",
     "descripcion": "Una creencia de tu cliente que le hace perder tiempo o dinero, y por qué es falsa."},
    {"id": "historia", "nombre": "Tu historia", "cuota": 1, "etapa": "tofu",
     "descripcion": "Algo que te pasó y lo que aprendiste, contado en primera persona."},
    {"id": "metodo", "nombre": "Cómo lo hago", "cuota": 2, "etapa": "mofu",
     "descripcion": "Un paso de tu método explicado con un ejemplo real."},
    {"id": "caso", "nombre": "Resultado de un cliente", "cuota": 1, "etapa": "bofu",
     "descripcion": "Un caso real con sus cifras, sacado del inventario de pruebas."},
    {"id": "oferta", "nombre": "Tu oferta", "cuota": 1, "etapa": "bofu",
     "descripcion": "Para quién es, qué consigue y cómo se empieza."},
]

TIPOS_PRUEBA = {"resultado": "Resultado con cifras", "caso": "Caso de cliente", "objecion": "Objeción y respuesta",
                "pregunta": "Pregunta frecuente", "proceso": "Proceso o método", "historia": "Historia propia"}

VOZ_VACIA = {"resumen": "", "como_habla": [], "movimientos": [], "frases": [], "nunca": [], "muestras": [],
             "posiciones": [], "tacos": "no", "emojis": "pocos", "camara": "cara", "ppm": 150}
TACOS = {"no": "Nunca", "suaves": "Alguno suave", "si": "Sí, como habla"}
EMOJIS = {"nunca": "Nunca", "pocos": "Pocos", "libre": "Los que quiera"}
CAMARAS = {"cara": "A cámara", "voz": "Voz en off", "sin_cara": "Sin cara (pantalla, manos…)"}
MODOS_GRABACION = {"guion": "Lee un guion", "estructura": "Habla libre con una estructura de temas"}
CTAS = {"palabra_clave": "Comentar una palabra clave", "dm": "Escribir por DM", "bio": "Enlace de la bio",
        "seguir": "Seguir la cuenta", "guardar": "Guardar el post", "llamada": "Reservar una llamada"}
FORMATOS = {"reels": "Reels y vídeo corto", "carrusel": "Carruseles", "historias": "Historias",
            "texto": "Posts de texto (LinkedIn, X)"}
FUENTES = {"busqueda": "Búsqueda", "rss": "RSS", "reddit": "Reddit"}
# Variantes de prueba de cada reel (Publi): apagadas hasta que el negocio las active.
REELS_PRUEBA = {"activa": False, "al_dia": 9, "desde": "08:00", "hasta": "21:00", "comprobado": False}
LIMITES_VACIOS = {"temas_vetados": [], "no_se_dicen": [], "afirmaciones_prohibidas": [], "cifras_propias": True}
MAX_LECCIONES = 20  # las que van en cada petición a Claude: las más recientes

# Cuándo se publica en cada red (días: 0 = lunes). Instagram, por defecto, lo publicas tú para poder poner audio en
# tendencia: Publi te avisa con el vídeo y el texto a su hora.
PLAN_PUBLICACION = {
    "instagram": {"activa": True, "dias": [0, 1, 2, 3, 4], "horas": ["13:30"], "autopublicar": False},
    "tiktok": {"activa": True, "dias": [0, 1, 2, 3, 4, 5], "horas": ["19:00"], "autopublicar": True},
    "youtube": {"activa": True, "dias": [0, 2, 4], "horas": ["18:00"], "autopublicar": True},
    "linkedin": {"activa": False, "dias": [1, 3], "horas": ["09:00"], "autopublicar": True},
}


# Puntos de partida por tipo de negocio: se aplican al elegirlo en el onboarding (y se cambian después en el Kit).
_CARRIL = lambda i, n, c, e, d: {"id": i, "nombre": n, "cuota": c, "etapa": e, "descripcion": d}  # noqa: E731
PRESETS = {
    "coach": {
        "nombre": "Coach o consultor",
        "carriles": [dict(c) for c in CARRILES_INICIALES],  # los de siempre: los Kits ya creados no cambian
        "mezcla": {"tofu": 50, "mofu": 30, "bofu": 20}, "cta": "palabra_clave",
        "fuentes": [{"tipo": "busqueda", "valor": "tendencias en tu sector"}]},
    "agencia": {
        "nombre": "Agencia",
        "carriles": [
            _CARRIL("error", "Error que vemos en clientes", 2, "tofu", "Un fallo habitual en tu sector y cómo se arregla."),
            _CARRIL("entre_bastidores", "Así trabajamos", 1, "mofu", "Un proceso del equipo, enseñado con un caso."),
            _CARRIL("caso", "Caso de cliente", 2, "bofu", "Antes y después de un cliente, con su prueba."),
            _CARRIL("opinion", "Opinión del sector", 1, "tofu", "Lo que defiendes frente a lo que dice el mercado."),
            _CARRIL("oferta", "Cómo trabajar con nosotros", 1, "bofu", "Qué incluye, para quién es y cómo se empieza.")],
        "mezcla": {"tofu": 40, "mofu": 30, "bofu": 30}, "cta": "llamada",
        "fuentes": [{"tipo": "busqueda", "valor": "novedades de tu sector"}]},
    "infoproducto": {
        "nombre": "Infoproducto",
        "carriles": [
            _CARRIL("leccion", "Lección rápida", 2, "tofu", "Una idea útil que se aplica hoy, sacada de tu programa."),
            _CARRIL("mito", "Mito del nicho", 1, "tofu", "Lo que todos repiten y no funciona."),
            _CARRIL("alumno", "Resultado de un alumno", 2, "bofu", "Lo que consiguió alguien con tu programa, con su prueba."),
            _CARRIL("historia", "Tu historia", 1, "mofu", "Cómo llegaste a enseñar esto."),
            _CARRIL("oferta", "Tu programa", 1, "bofu", "Qué se aprende, para quién es y cómo se entra.")],
        "mezcla": {"tofu": 50, "mofu": 25, "bofu": 25}, "cta": "palabra_clave",
        "fuentes": [{"tipo": "busqueda", "valor": "novedades de tu nicho"}]},
    "servicios": {
        "nombre": "Servicios profesionales",
        "carriles": [
            _CARRIL("pregunta", "Pregunta de cliente", 2, "tofu", "Una duda que te hacen siempre, respondida claro."),
            _CARRIL("error", "Error caro", 1, "tofu", "Lo que le sale caro a tu cliente por no saberlo."),
            _CARRIL("proceso", "Cómo trabajo", 2, "mofu", "Tu proceso paso a paso, con un ejemplo."),
            _CARRIL("caso", "Caso real", 1, "bofu", "Un cliente, su problema y cómo acabó."),
            _CARRIL("oferta", "Tu servicio", 1, "bofu", "Qué incluye y cómo se pide.")],
        "mezcla": {"tofu": 45, "mofu": 30, "bofu": 25}, "cta": "dm",
        "fuentes": [{"tipo": "busqueda", "valor": "cambios en tu sector"}]},
}
NICHO_INICIAL = "coach"


def preset(nicho: str) -> dict:
    return PRESETS.get(nicho) or PRESETS[NICHO_INICIAL]


def aplicar_preset(negocio_id: int, nicho: str) -> dict:
    """Pone los puntos de partida de un tipo de negocio. No pisa lo que ya salió de las llamadas o se cambió a mano:
    solo rellena carriles, reparto, fuentes y llamada a la acción si siguen como al empezar."""
    if nicho not in PRESETS:
        return leer(negocio_id)
    kit, p = leer(negocio_id), PRESETS[nicho]
    cambios = {"nicho": nicho}
    if kit["carriles"] == preset(kit.get("nicho") or NICHO_INICIAL)["carriles"]:
        cambios["carriles"] = [dict(c) for c in p["carriles"]]
    if kit["mezcla"] == preset(kit.get("nicho") or NICHO_INICIAL)["mezcla"]:
        cambios["mezcla"] = dict(p["mezcla"])
    if not kit["fuentes"]:
        cambios["fuentes"] = [dict(f) for f in p["fuentes"]]
    if kit["cta"]["principal"] == preset(kit.get("nicho") or NICHO_INICIAL)["cta"]:
        cambios["cta"] = {**kit["cta"], "principal": p["cta"]}
    return cambiar(negocio_id, **cambios)


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _id() -> str:
    return secrets.token_hex(4)


def _completar(datos: dict | None) -> dict:
    datos = dict(datos or {})
    datos["voz"] = {**VOZ_VACIA, **(datos.get("voz") or {})}
    inicial = preset(datos.get("nicho") or NICHO_INICIAL)
    datos.setdefault("nicho", "")
    datos.setdefault("carriles", [dict(c) for c in inicial["carriles"]])
    datos["mezcla"] = {**inicial["mezcla"], **(datos.get("mezcla") or {})}
    # Lo que define cómo trabaja el equipo para este negocio (sale del onboarding; sin dato, lo neutro).
    datos.setdefault("zona", "Europe/Madrid")
    datos.setdefault("idioma", "es-ES")
    datos.setdefault("modo_grabacion", "estructura")
    datos.setdefault("dia_grabacion", "")
    datos["formatos"] = {"reels": True, "carrusel": False, "historias": False, "texto": False,
                         **(datos.get("formatos") or {})}
    datos["cta"] = {"principal": inicial["cta"], "web": "", "prefijo_utm": "", **(datos.get("cta") or {})}
    datos["limites"] = {**LIMITES_VACIOS, **(datos.get("limites") or {})}
    datos["reels_prueba"] = {**REELS_PRUEBA, **(datos.get("reels_prueba") or {})}
    datos["angulos"] = {"principal": "", "sub": [], **(datos.get("angulos") or {})}
    for clave in ("ofertas", "nunca_prometer", "hashtags", "fuentes"):
        datos.setdefault(clave, [])
    for clave in ("pruebas", "lecciones", "prohibidas", "rechazados"):
        datos.setdefault(clave, [])
    datos["contexto"] = limpiar_contexto(datos.get("contexto") or {})
    datos["comunidad"] = {"dm_automaticos": False, "crm_webhook": "", "mensaje_dm":
                          "Aquí tienes lo que pediste:", **(datos.get("comunidad") or {})}
    datos["avisos"] = {"hora_resumen": "07:30", "silencio_inicio": "", "silencio_fin": "", "avisar_aprobaciones": True,
                       **(datos.get("avisos") or {})}
    datos["objetivo"] = {"metrica": "leads", "valor": 10, **(datos.get("objetivo") or {})}
    plan = datos.get("publicacion") or {}
    datos["publicacion"] = {red: {**valores, **(plan.get(red) or {})} for red, valores in PLAN_PUBLICACION.items()}
    autonomia = datos.get("autonomia") or {}
    datos["autonomia"] = {a: autonomia.get(a) if autonomia.get(a) in AUTONOMIAS else AUTONOMIA_INICIAL for a in AGENTES}
    return datos


def leer(negocio_id: int) -> dict:
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM kits WHERE negocio_id = ?", (negocio_id,)).fetchone()
    return _completar(json.loads(f["datos"]) if f else None)


def guardar(negocio_id: int, datos: dict) -> dict:
    datos = _completar(datos)
    with db.conexion() as con:
        con.execute("INSERT INTO kits (negocio_id, actualizado, datos) VALUES (?, ?, ?) "
                    "ON CONFLICT(negocio_id) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
                    (negocio_id, _ahora(), json.dumps(datos, ensure_ascii=False)))
    return datos


def cambiar(negocio_id: int, **partes) -> dict:
    return guardar(negocio_id, {**leer(negocio_id), **partes})


# ---------------------------------------------------------------- limpieza de lo que llega de formularios o de Claude

def lineas(texto: str, maximo: int = 30) -> list[str]:
    """Un campo de texto con una cosa por línea → lista sin vacíos ni repetidos."""
    salida = []
    for linea in (texto or "").splitlines():
        linea = linea.strip(" -•\t")[:300]
        if linea and linea.lower() not in {s.lower() for s in salida}:
            salida.append(linea)
    return salida[:maximo]


def limpiar_voz(voz: dict) -> dict:
    limpia = {"resumen": str(voz.get("resumen") or "").strip()[:400]}
    for clave in ("como_habla", "movimientos", "frases", "nunca"):
        valor = voz.get(clave) or []
        limpia[clave] = lineas("\n".join(valor) if isinstance(valor, list) else str(valor), 15)
    # Fragmentos literales de cómo habla (de las llamadas): lo que mejor enseña a Escri a sonar como él.
    limpia["muestras"] = [" ".join(str(m).split())[:1500] for m in voz.get("muestras") or [] if str(m).strip()][:6]
    valor = voz.get("posiciones") or []
    limpia["posiciones"] = lineas("\n".join(valor) if isinstance(valor, list) else str(valor), 5)
    for clave, opciones in (("tacos", TACOS), ("emojis", EMOJIS), ("camara", CAMARAS)):
        limpia[clave] = voz.get(clave) if voz.get(clave) in opciones else VOZ_VACIA[clave]
    try:
        limpia["ppm"] = max(90, min(240, int(voz.get("ppm") or VOZ_VACIA["ppm"])))
    except (TypeError, ValueError):
        limpia["ppm"] = VOZ_VACIA["ppm"]
    return limpia


def _lista(valor, maximo: int = 30) -> list[str]:
    return lineas("\n".join(map(str, valor)) if isinstance(valor, list) else str(valor or ""), maximo)


def limpiar_estrategia(d: dict) -> dict:
    """Lo del onboarding que no es voz ni contexto: límites, ángulos, ofertas, llamada a la acción, formatos, hashtags
    y fuentes. Devuelve solo las claves que trae `d`, ya limpias (para cambiar() sin pisar lo demás)."""
    salida = {}
    if "limites" in d:
        l = d["limites"] or {}
        salida["limites"] = {k: _lista(l.get(k), 20) for k in ("temas_vetados", "no_se_dicen", "afirmaciones_prohibidas")}
        cp = l.get("cifras_propias", True)
        salida["limites"]["cifras_propias"] = cp not in (False, "no", "false", "0", 0)
    if "angulos" in d:
        a = d["angulos"] or {}
        salida["angulos"] = {"principal": str(a.get("principal") or "").strip()[:300], "sub": _lista(a.get("sub"), 6)}
    if "ofertas" in d:
        salida["ofertas"] = [{"id": str(o.get("id") or "") or _id(), "nombre": str(o.get("nombre") or "").strip()[:120],
                              "url": str(o.get("url") or "").strip()[:300] if str(o.get("url") or "").startswith("http") else "",
                              "cta": str(o.get("cta") or "").strip()[:200]}
                             for o in d["ofertas"] or [] if isinstance(o, dict) and str(o.get("nombre") or "").strip()][:10]
    if "cta" in d:
        c = d["cta"] or {}
        salida["cta"] = {"principal": c.get("principal") if c.get("principal") in CTAS else "palabra_clave",
                         "web": str(c.get("web") or "").strip()[:300] if str(c.get("web") or "").startswith("http") else "",
                         "prefijo_utm": re.sub(r"[^a-z0-9_-]", "", str(c.get("prefijo_utm") or "").lower())[:30]}
    if "formatos" in d:
        salida["formatos"] = {k: bool((d["formatos"] or {}).get(k)) for k in FORMATOS}
    if "hashtags" in d:
        salida["hashtags"] = list(dict.fromkeys(
            "#" + re.sub(r"[^\wáéíóúñü]", "", h.lstrip("#")).lower() for h in _lista(d["hashtags"], 30)
            if re.sub(r"[^\wáéíóúñü]", "", h.lstrip("#"))))[:20]
    if "fuentes" in d:
        salida["fuentes"] = [{"tipo": f.get("tipo") if f.get("tipo") in FUENTES else "busqueda",
                              "valor": str(f.get("valor") or "").strip()[:200]}
                             for f in d["fuentes"] or [] if isinstance(f, dict) and str(f.get("valor") or "").strip()][:15]
    if "reels_prueba" in d:
        r = {**REELS_PRUEBA, **(d["reels_prueba"] or {})}
        try:
            al_dia = max(1, min(20, int(r["al_dia"])))
        except (TypeError, ValueError):
            al_dia = REELS_PRUEBA["al_dia"]
        hora = lambda h, defecto: h if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(h)) else defecto  # noqa: E731
        salida["reels_prueba"] = {"activa": r["activa"] not in (False, "no", "0", 0, ""), "al_dia": al_dia,
                                  "desde": hora(r["desde"], REELS_PRUEBA["desde"]),
                                  "hasta": hora(r["hasta"], REELS_PRUEBA["hasta"]), "comprobado": bool(r["comprobado"])}
    if "nunca_prometer" in d:
        salida["nunca_prometer"] = _lista(d["nunca_prometer"], 20)
    for clave, opciones in (("modo_grabacion", MODOS_GRABACION), ("nicho", PRESETS)):
        if d.get(clave) in opciones:
            salida[clave] = d[clave]
    for clave in ("zona", "idioma", "dia_grabacion"):
        if clave in d:
            salida[clave] = str(d[clave] or "").strip()[:40]
    return salida


def _id_de(nombre: str, usados: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")[:24] or "carril"
    candidato, n = base, 2
    while candidato in usados:
        candidato, n = f"{base}-{n}", n + 1
    return candidato


def limpiar_carriles(carriles: list[dict]) -> list[dict]:
    salida, usados = [], set()
    for c in carriles[:12]:
        nombre = str(c.get("nombre") or "").strip()[:60]
        if not nombre:
            continue
        try:
            cuota = max(0, min(14, int(c.get("cuota") or 0)))
        except (TypeError, ValueError):
            cuota = 0
        cid = str(c.get("id") or "").strip() or _id_de(nombre, usados)
        if cid in usados:
            cid = _id_de(nombre, usados)
        usados.add(cid)
        salida.append({"id": cid, "nombre": nombre, "cuota": cuota,
                       "etapa": c.get("etapa") if c.get("etapa") in ETAPAS else "tofu",
                       "descripcion": str(c.get("descripcion") or "").strip()[:300]})
    return salida


def limpiar_mezcla(mezcla: dict) -> dict:
    """El reparto por etapas, en porcentajes que suman 100."""
    valores = {}
    for etapa in ETAPAS:
        try:
            valores[etapa] = max(0, int(mezcla.get(etapa) or 0))
        except (TypeError, ValueError):
            valores[etapa] = 0
    total = sum(valores.values())
    if not total:
        return dict(MEZCLA_INICIAL)
    reparto = {e: round(100 * v / total) for e, v in valores.items()}
    reparto["tofu"] += 100 - sum(reparto.values())
    return reparto


def limpiar_contexto(c: dict) -> dict:
    """Lo que sale de las llamadas de onboarding y no cabe en la ficha: historias, opiniones, objeciones con su
    respuesta, frases literales de sus clientes y preguntas frecuentes."""
    def lista(clave, campos, maximo=30):
        return [{k: str(x.get(k) or "").strip()[:600] for k in campos} for x in (c.get(clave) or [])
                if isinstance(x, dict) and str(x.get(campos[0]) or "").strip()][:maximo]
    return {"historias": lista("historias", ("titulo", "resumen", "cita")),
            "opiniones": lista("opiniones", ("opinion", "por_que", "cita")),
            "objeciones": lista("objeciones", ("objecion", "respuesta", "cita")),
            "frases_cliente": lista("frases_cliente", ("frase", "contexto"), 40),
            "preguntas_frecuentes": [str(x).strip()[:300] for x in c.get("preguntas_frecuentes") or [] if str(x).strip()][:30],
            "cliente_no": str(c.get("cliente_no") or "").strip()[:600]}


def limpiar_prueba(p: dict) -> dict | None:
    titulo = str(p.get("titulo") or "").strip()[:120]
    texto = str(p.get("texto") or "").strip()[:1500]
    if not titulo and not texto:
        return None
    return {"id": str(p.get("id") or "") or _id(), "tipo": p.get("tipo") if p.get("tipo") in TIPOS_PRUEBA else "resultado",
            "titulo": titulo or texto[:60], "texto": texto, "cifra": str(p.get("cifra") or "").strip()[:80],
            "fuente": str(p.get("fuente") or "").strip()[:200],
            "consentimiento": bool(p.get("consentimiento")), "creado": p.get("creado") or _ahora()}


# ---------------------------------------------------------------- pruebas y lecciones

def anadir_prueba(negocio_id: int, prueba: dict) -> dict | None:
    limpia = limpiar_prueba(prueba)
    if limpia:
        kit = leer(negocio_id)
        cambiar(negocio_id, pruebas=kit["pruebas"] + [limpia])
    return limpia


def borrar_prueba(negocio_id: int, prueba_id: str):
    kit = leer(negocio_id)
    cambiar(negocio_id, pruebas=[p for p in kit["pruebas"] if p["id"] != prueba_id])


def desde_formulario(form, actual: dict) -> dict:
    """La sección «Cómo trabajas» del Kit, tal como llega del formulario. Solo cambia lo que trae: un campo que no
    viene no se toca. Devuelve las partes ya limpias para cambiar()."""
    tiene = lambda *claves: any(k in form for k in claves)  # noqa: E731
    texto = lambda k: str(form.get(k) or "")  # noqa: E731
    d = {}
    for k in ("zona", "idioma", "dia_grabacion", "modo_grabacion", "nunca_prometer", "hashtags"):
        if k in form:
            d[k] = texto(k)
    if tiene("limites_temas", "limites_no_se_dicen", "limites_afirmaciones", "cifras_propias"):
        l = actual["limites"]
        d["limites"] = {"temas_vetados": texto("limites_temas") if "limites_temas" in form else l["temas_vetados"],
                        "no_se_dicen": texto("limites_no_se_dicen") if "limites_no_se_dicen" in form else l["no_se_dicen"],
                        "afirmaciones_prohibidas": texto("limites_afirmaciones") if "limites_afirmaciones" in form
                        else l["afirmaciones_prohibidas"],
                        "cifras_propias": texto("cifras_propias") != "no" if "cifras_propias" in form else l["cifras_propias"]}
    if tiene("angulo_principal", "angulos_sub"):
        d["angulos"] = {"principal": texto("angulo_principal") if "angulo_principal" in form else actual["angulos"]["principal"],
                        "sub": texto("angulos_sub") if "angulos_sub" in form else actual["angulos"]["sub"]}
    if tiene("formatos", "formatos_enviado"):  # checkboxes: sin marcar no llegan, por eso el campo oculto
        marcados = set(form.getlist("formatos")) if hasattr(form, "getlist") else set(form.get("formatos") or [])
        d["formatos"] = {f: f in marcados for f in FORMATOS}
    if tiene("cta_principal", "cta_web", "cta_prefijo"):
        c = actual["cta"]
        d["cta"] = {"principal": texto("cta_principal") if "cta_principal" in form else c["principal"],
                    "web": texto("cta_web") if "cta_web" in form else c["web"],
                    "prefijo_utm": texto("cta_prefijo") if "cta_prefijo" in form else c["prefijo_utm"]}
    if "fuentes" in form:  # una por línea: «rss https://…», «reddit r/marketing» o una búsqueda tal cual
        d["fuentes"] = []
        for linea in lineas(texto("fuentes"), 15):
            tipo, _, resto = linea.partition(" ")
            d["fuentes"].append({"tipo": tipo.lower(), "valor": resto} if tipo.lower() in FUENTES and resto
                                else {"tipo": "busqueda", "valor": linea})
    if "ofertas" in form:  # una por línea: «Nombre | https://… | cómo se empieza»
        d["ofertas"] = []
        for linea in lineas(texto("ofertas"), 10):
            nombre, url, cta = (list(map(str.strip, linea.split("|"))) + ["", ""])[:3]
            d["ofertas"].append({"nombre": nombre, "url": url, "cta": cta})
    if tiene("reels_prueba_activa", "reels_prueba_al_dia", "reels_prueba_desde", "reels_prueba_hasta"):
        r = actual["reels_prueba"]
        d["reels_prueba"] = {**r, **{k: texto(f"reels_prueba_{k}") for k in ("al_dia", "desde", "hasta")
                                     if f"reels_prueba_{k}" in form}}
        if "reels_prueba_activa" in form:
            d["reels_prueba"]["activa"] = texto("reels_prueba_activa") in ("1", "si", "on", "true")
    salida = limpiar_estrategia(d)
    if tiene("posiciones", "tacos", "emojis", "camara", "ppm"):
        voz = dict(actual["voz"])
        if "posiciones" in form:
            voz["posiciones"] = texto("posiciones")
        for k in ("tacos", "emojis", "camara", "ppm"):
            if k in form:
                voz[k] = texto(k)
        salida["voz"] = limpiar_voz(voz)
    return salida


def cifras_permitidas(kit: dict) -> list[str]:
    """Las cifras que un guion puede usar: solo las del inventario de pruebas que tienen fuente. Si el negocio no
    permite cifras propias (límites del Kit), ninguna."""
    if not kit.get("limites", LIMITES_VACIOS).get("cifras_propias", True):
        return []
    return [p["cifra"] for p in kit["pruebas"] if p.get("cifra") and p.get("fuente")]


_VACIAS_LECCION = set("""para como pero porque cuando donde desde hasta sobre entre todos todas siempre nunca cada
esto esta este estos estas mismo misma tienes puedes quieres hacer usar""".split())


def _claves(texto: str) -> set[str]:
    texto = texto.lower()
    for a, b in zip("áéíóúü", "aeiouu"):
        texto = texto.replace(a, b)
    return {w for w in re.findall(r"[a-zñ]{4,}", texto) if w not in _VACIAS_LECCION}


def parecida(a: str, b: str) -> bool:
    """Dos reglas que dicen casi lo mismo (comparten el 75 % de sus palabras con contenido)."""
    x, y = _claves(a), _claves(b)
    return bool(x and y) and len(x & y) / min(len(x), len(y)) >= 0.75


def anadir_leccion(negocio_id: int, regla: str, *, origen: str = "tú", evidencia: str = "",
                   activa: bool = True) -> dict | None:
    """Cada corrección se convierte en una regla con fecha que todos los agentes leen. Las que propone un agente
    esperan a que las apruebes."""
    regla = " ".join((regla or "").split())[:300]
    if not regla:
        return None
    kit = leer(negocio_id)
    if any(l["regla"].lower() == regla.lower() or parecida(l["regla"], regla) for l in kit["lecciones"]):
        return None  # ya hay una igual o casi igual
    leccion = {"id": _id(), "fecha": _ahora()[:10], "regla": regla, "origen": origen,
               "evidencia": evidencia.strip()[:300], "estado": "activa" if activa else "pendiente"}
    cambiar(negocio_id, lecciones=kit["lecciones"] + [leccion])
    return leccion


def activar_leccion(negocio_id: int, leccion_id: str):
    kit = leer(negocio_id)
    for l in kit["lecciones"]:
        if l["id"] == leccion_id:
            l["estado"] = "activa"
    guardar(negocio_id, kit)


def borrar_leccion(negocio_id: int, leccion_id: str):
    kit = leer(negocio_id)
    cambiar(negocio_id, lecciones=[l for l in kit["lecciones"] if l["id"] != leccion_id])


def anadir_rechazado(negocio_id: int, concepto: str, motivo: str = ""):
    """Las ideas que dices que no: Plani no las vuelve a proponer."""
    concepto = concepto.strip()[:200]
    if concepto:
        kit = leer(negocio_id)
        cambiar(negocio_id, rechazados=(kit["rechazados"] + [{"concepto": concepto, "motivo": motivo.strip()[:200],
                                                              "fecha": _ahora()[:10]}])[-100:])


# Cuántos vídeos caben a la semana según el tiempo que tiene para grabar (las respuestas del onboarding).
# Si no dice cuántos vídeos quiere, un tope según el tiempo que tiene para grabar («Más de 4 horas»: sin tope).
TOPE_POR_TIEMPO = {"Menos de 1 hora": 2, "De 1 a 2 horas": 4, "De 2 a 4 horas": 7, "Más de 4 horas": None}
VIDEOS_POR_HORA = 2.5   # grabar, repetir tomas y cambiarse: unos 25 minutos por vídeo corto


def videos_pedidos(ficha: dict) -> int | None:
    """Los vídeos a la semana que ha pedido (onboarding): manda sobre todo lo demás."""
    m = re.search(r"\d+", str(ficha.get("videos_semana") or ""))
    return max(1, min(70, int(m.group()))) if m else None


def tope_semanal(ficha: dict) -> int | None:
    """Los vídeos de su semana: los que ha pedido; si no lo dijo, los que caben en su tiempo; sin nada, sin tope."""
    pedidos = videos_pedidos(ficha)
    if pedidos:
        return pedidos
    tiempo = str(ficha.get("tiempo") or "").strip()
    if tiempo in TOPE_POR_TIEMPO:
        return TOPE_POR_TIEMPO[tiempo]
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(h|hora)", tiempo.lower())  # texto libre de la ficha: «3 horas a la semana»
    return max(1, round(float(m.group(1).replace(",", ".")) * VIDEOS_POR_HORA)) if m else None


def cuotas_que_caben(carriles: list[dict], tope: int | None, exacto: bool = False) -> list[dict]:
    """Reparte los vídeos de la semana entre los carriles, en proporción a sus cuotas. Si los carriles piden más de lo
    que cabe, se recortan; con `exacto` (el número que ha pedido el usuario), también se amplían hasta llegar. El hueco
    que sobra va primero a los de vender. Devuelve los carriles con su cuota de esta semana."""
    total = sum(c["cuota"] for c in carriles)
    if not tope or not total or total == tope or (total < tope and not exacto):
        return [dict(c) for c in carriles]
    exactas = [(c, c["cuota"] * tope / total) for c in carriles]
    salida = [{**c, "cuota": int(x), "cuota_kit": c["cuota"]} for c, x in exactas]
    sobra = tope - sum(c["cuota"] for c in salida)
    # El hueco que queda, a los de mayor resto; a igualdad, primero los de vender (BOFU) y luego los de convencer.
    orden = sorted(range(len(salida)), key=lambda i: (-(exactas[i][1] % 1), {"bofu": 0, "mofu": 1}.get(salida[i]["etapa"], 2)))
    for i in orden[:sobra]:
        salida[i]["cuota"] += 1
    return salida


def capacidad(negocio: dict, kit: dict | None = None) -> dict:
    """Para la página del Kit y para Plani: lo que piden los carriles frente a lo que cabe en su semana."""
    kit = kit or leer(negocio["id"])
    ficha = negocio.get("ficha") or {}
    tope = tope_semanal(ficha)
    pedidos = sum(c["cuota"] for c in kit["carriles"])
    return {"tope": tope, "pedidos": pedidos, "recortado": bool(tope and pedidos > tope and not videos_pedidos(ficha)),
            "ajustado": bool(videos_pedidos(ficha) and pedidos != tope), "videos_semana": videos_pedidos(ficha),
            "tiempo": ficha.get("tiempo", "")}


def autonomia(negocio_id: int, agente: str) -> str:
    return leer(negocio_id)["autonomia"].get(agente, AUTONOMIA_INICIAL)


# ---------------------------------------------------------------- lo que leen los agentes

def contexto(negocio: dict, kit: dict | None = None) -> str:
    """El Kit de marca en texto, para ponerlo delante de cualquier petición a Claude."""
    kit = kit or leer(negocio["id"])
    partes = ["## El negocio (de la ficha)", json.dumps(onboarding.resumen(onboarding.para_ia(negocio["ficha"])),
                                                         ensure_ascii=False, indent=1)]
    voz = kit["voz"]
    if voz["resumen"] or voz["como_habla"]:
        partes.append("## Su voz")
        if voz["resumen"]:
            partes.append(voz["resumen"])
        for clave, titulo in (("como_habla", "Cómo habla"), ("movimientos", "Sus recursos"),
                              ("frases", "Frases suyas"), ("nunca", "Lo que nunca dice")):
            if voz[clave]:
                partes.append(f"{titulo}:\n" + "\n".join(f"- {x}" for x in voz[clave]))
        if voz.get("muestras"):
            partes.append("Así habla (fragmentos literales de sus llamadas; imita su ritmo y sus expresiones, no el "
                          "contenido):\n" + "\n---\n".join(voz["muestras"]))
        if voz.get("posiciones"):
            partes.append("Lo que defiende (posiciones que no todos comparten):\n" + "\n".join(f"- {x}" for x in voz["posiciones"]))
    partes.append(f"Tacos: {TACOS[voz['tacos']].lower()}. Emojis: {EMOJIS[voz['emojis']].lower()}. "
                  f"Graba: {CAMARAS[voz['camara']].lower()}, a unas {voz['ppm']} palabras por minuto.")
    partes.append(f"## Cómo graba\n{MODOS_GRABACION[kit['modo_grabacion']]}"
                  + (" (Escri le da los temas en bloques; los ganchos salen de lo que diga)."
                     if kit["modo_grabacion"] == "estructura" else ".")
                  + (f" Día de grabación: {kit['dia_grabacion']}." if kit["dia_grabacion"] else "")
                  + " Formatos activos: " + ", ".join(FORMATOS[f].lower() for f, si in kit["formatos"].items() if si) + ".")
    if kit["angulos"]["principal"] or kit["angulos"]["sub"]:
        partes.append("## Ángulo de la marca\n" + (kit["angulos"]["principal"] or "")
                      + "".join(f"\n- {x}" for x in kit["angulos"]["sub"]))
    cta = kit["cta"]
    partes.append(f"## Llamada a la acción principal\n{CTAS[cta['principal']]}"
                  + (f" · web: {cta['web']}" if cta["web"] else ""))
    if kit["ofertas"]:
        partes.append("## Ofertas y cómo se empieza\n" + "\n".join(
            f"- {o['nombre']}" + (f": {o['cta']}" if o["cta"] else "") + (f" ({o['url']})" if o["url"] else "")
            for o in kit["ofertas"]))
    if kit["hashtags"]:
        partes.append("## Hashtags del nicho (de 3 a 5 por post)\n" + " ".join(kit["hashtags"]))
    partes.append("## Carriles de contenido (cuota semanal y etapa)")
    partes += [f"- {c['id']}: {c['nombre']} · {c['cuota']}/semana · {c['etapa'].upper()} · {c['descripcion']}"
               for c in kit["carriles"]]
    partes.append("Reparto objetivo por etapas: " + ", ".join(f"{e.upper()} {v} %" for e, v in kit["mezcla"].items()))
    if kit["pruebas"]:
        partes.append("## Inventario de pruebas (la única fuente de cifras; cita su id)")
        for p in kit["pruebas"]:
            linea = f"- [{p['id']}] {TIPOS_PRUEBA[p['tipo']]}: {p['titulo']}"
            if p["cifra"]:
                linea += f" · cifra: {p['cifra']}" + (f" (fuente: {p['fuente']})" if p["fuente"] else " (SIN FUENTE: no usar)")
            if p["texto"]:
                linea += f" · {p['texto']}"
            if p["tipo"] == "caso" and not p["consentimiento"]:
                linea += " · sin permiso para nombrar al cliente"
            partes.append(linea)
    else:
        partes.append("## Inventario de pruebas\nVacío: no hay cifras propias. No uses ninguna cifra sin fuente citada.")
    c = kit["contexto"]
    if c["frases_cliente"]:
        partes.append("## Lo que dicen sus clientes (frases literales: los mejores ganchos)\n" + "\n".join(
            f"- «{f['frase']}»" + (f" ({f['contexto']})" if f["contexto"] else "") for f in c["frases_cliente"]))
    if c["objeciones"]:
        partes.append("## Objeciones y cómo las responde\n" + "\n".join(
            f"- {o['objecion']} → {o['respuesta']}" for o in c["objeciones"]))
    if c["opiniones"]:
        partes.append("## Lo que defiende contra su sector\n" + "\n".join(
            f"- {o['opinion']}" + (f" (por qué: {o['por_que']})" if o["por_que"] else "") for o in c["opiniones"]))
    if c["historias"]:
        partes.append("## Historias suyas que puede contar\n" + "\n".join(
            f"- {h['titulo']}: {h['resumen']}" for h in c["historias"]))
    if c["preguntas_frecuentes"]:
        partes.append("## Lo que le preguntan una y otra vez\n" + "\n".join(f"- {q}" for q in c["preguntas_frecuentes"]))
    if c["cliente_no"]:
        partes.append(f"## A quién no quiere como cliente\n{c['cliente_no']}")
    if kit["prohibidas"]:
        partes.append("## Frases prohibidas\n" + "\n".join(f"- {x}" for x in kit["prohibidas"]))
    lim = kit["limites"]
    limites = [f"- Temas vetados: {', '.join(lim['temas_vetados'])}" if lim["temas_vetados"] else "",
               f"- No se nombra: {', '.join(lim['no_se_dicen'])}" if lim["no_se_dicen"] else "",
               f"- Afirmaciones prohibidas: {', '.join(lim['afirmaciones_prohibidas'])}" if lim["afirmaciones_prohibidas"] else "",
               f"- Nunca se promete: {', '.join(kit['nunca_prometer'])}" if kit["nunca_prometer"] else "",
               "" if lim["cifras_propias"] else "- NADA de cifras propias (facturación, clientes, resultados con número)."]
    if any(limites):
        partes.append("## Límites (se cumplen siempre)\n" + "\n".join(x for x in limites if x))
    activas = [l for l in kit["lecciones"] if l["estado"] == "activa"]
    if activas:
        recientes = activas[-MAX_LECCIONES:]  # si dos chocan, manda la más reciente: va la última
        partes.append("## Lecciones (reglas que hay que cumplir siempre; si dos chocan, manda la de fecha más reciente)\n"
                      + "\n".join(f"- ({l['fecha']}) {l['regla']}" for l in recientes))
    if kit["rechazados"]:
        partes.append("## Ideas rechazadas (no proponer)\n" + "\n".join(f"- {r['concepto']}" for r in kit["rechazados"][-30:]))
    return "\n\n".join(partes)


# ---------------------------------------------------------------- borrador del kit con Claude

ESQUEMA_BORRADOR = llm.obj(
    voz=llm.obj(resumen=llm.S, como_habla=llm.lista(llm.S), movimientos=llm.lista(llm.S), frases=llm.lista(llm.S),
                nunca=llm.lista(llm.S)),
    carriles=llm.lista(llm.obj(nombre=llm.S, cuota=llm.N, etapa={"type": "string", "enum": list(ETAPAS)},
                               descripcion=llm.S)),
    pruebas=llm.lista(llm.obj(tipo={"type": "string", "enum": list(TIPOS_PRUEBA)}, titulo=llm.S, texto=llm.S,
                              cifra=llm.S, fuente=llm.S)),
)

SISTEMA_BORRADOR = """Eres Orby, quien dirige un equipo de contenido para marcas personales en español. Con la ficha del negocio
(y, si las hay, transcripciones de sus vídeos), redacta el borrador de su Kit de marca.

- Voz: cómo habla de verdad. Una línea de resumen y listas cortas. Las «frases» son expresiones que usa él, no
  eslóganes inventados. Si no hay transcripciones, sácalo del tono de la ficha y dilo en el resumen («provisional»).
- Carriles: de 4 a 6 tipos de pieza que repetir cada semana, con su cuota semanal (el total cabe en el tiempo que
  tiene para contenido) y su etapa del embudo.
- Pruebas: solo lo que está en la ficha (resultados, casos, objeciones, preguntas, su método). Cada cifra lleva como
  fuente el campo de la ficha del que sale, por ejemplo «ficha: resultados». No inventes ninguna cifra ni ningún caso.
"""


def redactar_borrador(negocio: dict, transcripciones: list[str] | None = None) -> dict:
    """Voz, carriles y pruebas propuestos por Claude a partir de la ficha. Se aprueban antes de entrar en el kit."""
    peticion = "Ficha del negocio:\n" + json.dumps(onboarding.resumen(onboarding.para_ia(negocio["ficha"])),
                                                   ensure_ascii=False, indent=1)
    if transcripciones:
        peticion += "\n\nTranscripciones de sus vídeos:\n" + "\n---\n".join(t[:4000] for t in transcripciones[:8])
    datos = llm.json_con_esquema(SISTEMA_BORRADOR, peticion, ESQUEMA_BORRADOR, effort="medium")
    return {"voz": limpiar_voz(datos.get("voz") or {}), "carriles": limpiar_carriles(datos.get("carriles") or []),
            "pruebas": [p for p in (limpiar_prueba(x) for x in datos.get("pruebas") or []) if p]}
