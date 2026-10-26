"""Módulo 0: completa la ficha del negocio y encuentra a su competencia."""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from .. import llm, metodo, onboarding
from ..connectors import apify_social, linkedin, web
from ..llm import S, lista, obj

ESQUEMA = obj(
    resumen=S,
    cliente_ideal=S,
    ofertas_actuales=lista(obj(nombre=S, precio=S, formato=S)),
    tono=S,
    competidores=lista(obj(nombre=S, web=S, instagram=S, linkedin=S, youtube=S, motivo=S)),
    palabras_clave=lista(S),
    dudas=lista(S),
)


def _competidor(fila: dict) -> dict:
    """Una fila del formulario (un campo por dato), con el Instagram y el LinkedIn normalizados."""
    c = {"nombre": str(fila.get("nombre") or "").strip(), "web": str(fila.get("web") or "").strip(),
         "instagram": apify_social.usuario_instagram(str(fila.get("instagram") or "")),
         "linkedin": linkedin.url_linkedin(str(fila.get("linkedin") or "")),
         "youtube": str(fila.get("youtube") or "").strip(), "motivo": "Lo indicó el negocio"}
    c["nombre"] = c["nombre"] or c["web"] or c["instagram"] or c["linkedin"].rstrip("/").split("/")[-1] or c["youtube"]
    return c


def leer_competidores(valor) -> list[dict]:
    """Los competidores de la ficha. Se guardan como filas, un campo por dato, para que una coma en el nombre no
    rompa nada. Las fichas antiguas los tienen en texto, una línea por competidor: «Nombre, web, @instagram, enlace
    de LinkedIn, enlace de YouTube» (todo opcional), y se siguen leyendo."""
    if isinstance(valor, list):
        return [c for c in (_competidor(f) for f in valor if isinstance(f, dict)) if c["nombre"]]
    salida = []
    for linea in (valor or "").splitlines():
        partes = [p.strip() for p in linea.split(",") if p.strip()]
        if not partes:
            continue
        c = {"nombre": "", "web": "", "instagram": "", "linkedin": "", "youtube": "", "motivo": "Lo indicó el negocio"}
        for p in partes:
            if "linkedin.com/" in p.lower():
                c["linkedin"] = linkedin.url_linkedin(p)
            elif p.startswith("@") or "instagram.com" in p:
                c["instagram"] = p.rstrip("/").split("/")[-1].lstrip("@")
            elif "youtube.com" in p or "youtu.be" in p:
                c["youtube"] = p
            elif "." in p and " " not in p:
                c["web"] = p
            elif not c["nombre"]:
                c["nombre"] = p
        c["nombre"] = c["nombre"] or c["web"] or c["instagram"]
        salida.append(c)
    return salida


def filas_del_formulario(valor) -> list[dict]:
    """Las filas de competidores para el formulario: tal cual se guardaron o, en una ficha antigua, leídas del texto."""
    if isinstance(valor, list):
        return [dict(f) for f in valor if isinstance(f, dict)]
    return leer_competidores(valor)


def palabras_de_la_ficha(ficha: dict) -> list[str]:
    propias = [p.strip() for p in (ficha.get("palabras_clave") or "").split(",") if p.strip()]
    if propias:
        return propias
    que_vende = (ficha.get("que_vende") or "").strip()
    return [que_vende[:60]] if que_vende else []


def combinar(perfil: dict, ficha: dict) -> dict:
    """Aplica al perfil de un informe lo que se haya cambiado después en la ficha (competidores, Instagram,
    palabras clave), para que «Rehacer» una sección use la ficha actual sin repetir la investigación."""
    perfil = {**perfil, "competidores": [dict(c) for c in perfil.get("competidores", [])]}
    for nuevo in leer_competidores(ficha.get("competidores", "")):
        igual = next((c for c in perfil["competidores"]
                      if c["nombre"].lower() == nuevo["nombre"].lower()
                      or (nuevo["web"] and nuevo["web"].lower().replace("www.", "") in (c.get("web") or "").lower())), None)
        if igual is None:
            perfil["competidores"].append(nuevo)
        else:
            for campo in ("instagram", "linkedin", "youtube", "web"):
                if nuevo[campo]:
                    igual[campo] = nuevo[campo]
    propias = [p.strip() for p in (ficha.get("palabras_clave") or "").split(",") if p.strip()]
    if propias:
        perfil["palabras_clave"] = propias + [p for p in perfil.get("palabras_clave", []) if p not in propias]
    return perfil


NO_SON_CUENTAS = {"p", "reel", "reels", "explore", "stories", "accounts", "tv", "about", "legal", "direct"}


def redes_de_la_web(url: str) -> dict:
    """El Instagram y el YouTube que enlaza una web (suelen estar en el pie)."""
    pagina = web.descargar(url, timeout=12)
    if not pagina.ok:
        return {}
    salida = {}
    for enlace in pagina.enlaces_externos:
        if "instagram.com/" in enlace and "instagram" not in salida:
            usuario = apify_social.usuario_instagram(enlace)
            if usuario and usuario.lower() not in NO_SON_CUENTAS:
                salida["instagram"] = usuario
        elif "linkedin.com/" in enlace and "linkedin" not in salida and linkedin.url_linkedin(enlace):
            salida["linkedin"] = linkedin.url_linkedin(enlace)
        elif re.search(r"youtube\.com/(@|channel/|c/|user/)", enlace) and "youtube" not in salida:
            salida["youtube"] = enlace.split("?")[0]
    return salida


def descubrir_redes(perfil: dict) -> list[str]:
    """Completa en el perfil el Instagram y el YouTube de los competidores que no lo tienen, mirando su web.
    Devuelve los competidores a los que se les ha encontrado algo."""
    pendientes = [c for c in perfil.get("competidores", [])
                  if c.get("web") and not (c.get("instagram") and c.get("linkedin"))][:10]
    if not pendientes:
        return []
    with ThreadPoolExecutor(max_workers=5) as grupo:
        encontradas = list(grupo.map(lambda c: redes_de_la_web(c["web"]), pendientes))
    completados = []
    for c, redes in zip(pendientes, encontradas):
        if redes.get("instagram") and not c.get("instagram"):
            c["instagram"] = redes["instagram"]
            completados.append(c["nombre"])
        if redes.get("linkedin") and not c.get("linkedin"):
            c["linkedin"] = redes["linkedin"]
            if c["nombre"] not in completados:
                completados.append(c["nombre"])
        if redes.get("youtube") and not c.get("youtube"):
            c["youtube"] = redes["youtube"]
    return completados


def perfil_basico(ficha: dict) -> dict:
    return {
        "resumen": ficha.get("que_vende", ""),
        "cliente_ideal": ficha.get("a_quien", ""),
        "ofertas_actuales": [],
        "tono": ficha.get("tono", ""),
        "competidores": leer_competidores(ficha.get("competidores", "")),
        "palabras_clave": palabras_de_la_ficha(ficha),
        "dudas": [],
    }


def completar(ficha: dict) -> dict:
    avisos = []
    pagina = web.descargar(ficha["web"]) if ficha.get("web") else None
    if pagina and not pagina.ok:
        avisos.append(f"No se pudo leer la web del negocio ({pagina.error}).")

    perfil = perfil_basico(ficha)
    if not llm.disponible():
        avisos.append("Sin la clave de Claude, la ficha se queda con lo que has escrito y los competidores que has puesto.")
        return {"estado": "parcial", "avisos": avisos, "perfil": perfil, "web": pagina.resumen() if pagina else None}

    try:
        return _completar_con_ia(ficha, pagina, perfil, avisos)
    except llm.ErrorIA as e:
        avisos.append(f"{e} La ficha se queda con lo que has escrito.")
        return {"estado": "parcial", "avisos": avisos, "perfil": perfil, "web": pagina.resumen() if pagina else None}


def _completar_con_ia(ficha: dict, pagina, perfil: dict, avisos: list[str]) -> dict:
    contexto = {
        "ficha": onboarding.para_ia(ficha),
        "web_del_negocio": pagina.resumen() if pagina and pagina.ok else "no disponible",
    }
    investigacion = llm.investigar(
        metodo.BASE,
        "Investiga en la web a este negocio y a su competencia directa en su mercado "
        f"({ficha.get('mercado') or 'España'}). Busca entre 5 y 8 competidores que estén haciendo marketing "
        "activo (web, Instagram, LinkedIn, YouTube o anuncios): marcas personales, infoproductores, consultores, "
        "mentores, servicios online o agencias que vendan algo parecido al mismo tipo de cliente. Para cada uno, "
        "apunta su web, su usuario de Instagram, su LinkedIn (perfil personal o página de empresa) y su canal de "
        "YouTube, con la URL donde lo has visto. El Instagram y el LinkedIn son importantes: búscalos expresamente "
        "(por ejemplo, «nombre del competidor instagram» o «nombre linkedin») o míralos en el pie de su web. "
        "Apunta también las palabras con "
        "las que su cliente busca este tipo de solución en YouTube y en Google, y las ofertas y precios que "
        "veas en la web del propio negocio.\n\n"
        f"{json.dumps(contexto, ensure_ascii=False)}",
    )
    datos = llm.json_con_esquema(
        metodo.BASE,
        "Con la ficha, la web del negocio y la investigación, rellena el perfil del negocio. "
        "En «competidores», incluye siempre los que puso el negocio y añade los de la investigación. "
        "Si no conoces la web, el Instagram o el YouTube de un competidor, deja el campo vacío. "
        "En «instagram», escribe solo el usuario, sin @ ni enlace. En «linkedin», la URL completa del perfil o de "
        "la página de empresa. "
        "En «motivo», en una frase, por qué es competencia (qué vende y a quién), sin consejos ni valoraciones. "
        "En «palabras_clave», pon entre 3 y 6 búsquedas en español que usaría su cliente. "
        "En «dudas», lo que no has podido confirmar.\n\n"
        f"{json.dumps(contexto, ensure_ascii=False)}\n\nInvestigación:\n{investigacion}",
        ESQUEMA,
    )
    for c in datos["competidores"]:
        c["instagram"] = apify_social.usuario_instagram(c.get("instagram", ""))
        c["linkedin"] = linkedin.url_linkedin(c.get("linkedin", ""))
    # Los competidores que puso el negocio no se pierden aunque la IA no los incluya
    # (se comparan por nombre y por dominio, porque la IA a veces los renombra).
    def dominio(url: str) -> str:
        return web.normalizar_url(url).split("//")[-1].split("/")[0].replace("www.", "").lower() if url else ""

    nombres = {c["nombre"].lower() for c in datos["competidores"]}
    dominios = {dominio(c["web"]) for c in datos["competidores"] if c.get("web")}
    for c in perfil["competidores"]:
        if c["nombre"].lower() not in nombres and (not c.get("web") or dominio(c["web"]) not in dominios):
            datos["competidores"].append(c)
    descubrir_redes(datos)
    return {"estado": "ok", "avisos": avisos, "perfil": datos, "investigacion": investigacion,
            "web": pagina.resumen() if pagina else None}
