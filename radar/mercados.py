"""Mercados de referencia: países e idiomas de los que se mira contenido además del mercado principal (por ejemplo,
Brasil en portugués o Estados Unidos en inglés), y las búsquedas del negocio traducidas a su idioma."""
import re
import unicodedata

from . import config, llm
from .llm import S, lista, obj

# Código del país (el que usan YouTube y TikTok) → nombre, idioma habitual y cómo se escribe (sin tildes ni puntos).
PAISES = {
    "ES": ("España", "es", ("espana",)),
    "MX": ("México", "es", ("mexico",)),
    "AR": ("Argentina", "es", ("argentina",)),
    "CO": ("Colombia", "es", ("colombia",)),
    "CL": ("Chile", "es", ("chile",)),
    "PE": ("Perú", "es", ("peru",)),
    "UY": ("Uruguay", "es", ("uruguay",)),
    "EC": ("Ecuador", "es", ("ecuador",)),
    "BR": ("Brasil", "pt", ("brasil", "brazil")),
    "PT": ("Portugal", "pt", ("portugal",)),
    "US": ("Estados Unidos", "en", ("estados unidos", "eeuu", "ee uu", "usa", "eua")),
    "GB": ("Reino Unido", "en", ("reino unido", "uk", "inglaterra")),
    "IE": ("Irlanda", "en", ("irlanda",)),
    "CA": ("Canadá", "en", ("canada",)),
    "AU": ("Australia", "en", ("australia",)),
    "FR": ("Francia", "fr", ("francia",)),
    "IT": ("Italia", "it", ("italia",)),
    "DE": ("Alemania", "de", ("alemania",)),
}
# Zonas sin un código de país: se busca solo por idioma.
ZONAS = {"latinoamerica": ("Latinoamérica", "es"), "latam": ("Latinoamérica", "es"),
         "hispanoamerica": ("Latinoamérica", "es")}
IDIOMAS = {"es": ("español", ("espanol", "castellano")), "pt": ("portugués", ("portugues",)),
           "en": ("inglés", ("ingles",)), "fr": ("francés", ("frances",)), "it": ("italiano", ("italiano",)),
           "de": ("alemán", ("aleman",)), "ca": ("catalán", ("catalan",))}
MAXIMO = 3  # cada mercado repite las búsquedas de YouTube y TikTok: se limita para cuidar la cuota y el gasto

_PALABRAS = {**{alias: ("pais", codigo) for codigo, (_, _, alias_) in PAISES.items() for alias in alias_},
             **{alias: ("zona", alias) for alias in ZONAS},
             **{alias: ("idioma", codigo) for codigo, (_, alias_) in IDIOMAS.items() for alias in alias_}}
_PATRON = re.compile(r"\b(" + "|".join(sorted(map(re.escape, _PALABRAS), key=len, reverse=True)) + r")\b")


def sin_tildes(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def normalizar(texto: str) -> str:
    """«EE. UU. (Inglés)» → «ee uu ingles»: en minúsculas, sin tildes, puntos ni paréntesis."""
    return re.sub(r"\s+", " ", re.sub(r"[.()]", " ", sin_tildes(texto))).strip()


def leer(texto: str) -> list[dict]:
    """«Brasil en portugués, Estados Unidos en inglés» → [{pais: BR, idioma: pt, nombre, corto}, …].
    Un idioma que va detrás de un país es el de ese país; si va suelto, se busca solo por idioma. El mercado
    principal (RADAR_PAIS y RADAR_IDIOMA) no se repite."""
    encontrados: list[dict] = []
    for m in _PATRON.finditer(normalizar(texto)):
        tipo, valor = _PALABRAS[m.group(1)]
        ultimo = encontrados[-1] if encontrados else None
        if tipo == "pais":
            nombre, idioma, _ = PAISES[valor]
            encontrados.append({"pais": valor, "zona": nombre, "idioma": idioma, "habitual": idioma, "con_idioma": False})
        elif tipo == "zona":
            nombre, idioma = ZONAS[valor]
            encontrados.append({"pais": "", "zona": nombre, "idioma": idioma, "habitual": idioma, "con_idioma": False})
        elif ultimo and ultimo["zona"] and not ultimo["con_idioma"]:
            ultimo.update(idioma=valor, con_idioma=True)
        else:
            encontrados.append({"pais": "", "zona": "", "idioma": valor, "habitual": valor, "con_idioma": True})

    salida, vistos = [], {(config.PAIS, config.IDIOMA)}
    for e in encontrados:
        # Un idioma suelto sobra si ya hay un país o una zona que se busca en ese idioma.
        if not e["zona"] and any(x["zona"] and x["idioma"] == e["idioma"] for x in encontrados):
            continue
        clave = (e["pais"] or e["zona"], e["idioma"])
        if clave in vistos:
            continue
        vistos.add(clave)
        idioma = IDIOMAS[e["idioma"]][0]
        corto = e["zona"] or f"En {idioma}"
        nombre = f"{e['zona']} ({idioma})" if e["zona"] and e["idioma"] != e["habitual"] else corto
        salida.append({"pais": e["pais"], "idioma": e["idioma"], "nombre": nombre, "corto": corto})
    return salida[:MAXIMO]


def de_la_ficha(ficha: dict, avisos: list[str] | None = None) -> list[dict]:
    """Los mercados de referencia de la ficha. Si hay texto pero no se reconoce ningún país ni idioma, lo dice."""
    texto = str(ficha.get("mercados_referencia") or "").strip()
    mercados = leer(texto)
    if texto and not mercados and avisos is not None and not nombra_algun_mercado(texto):
        avisos.append(f"No se reconoce ningún país ni idioma en los mercados de referencia («{texto[:80]}»). "
                      "Escríbelos así: «Brasil en portugués, Estados Unidos en inglés».")
    return mercados


def nombra_algun_mercado(texto: str) -> bool:
    """Si el texto nombra algún país o idioma, aunque sea el del mercado principal."""
    return bool(_PATRON.search(normalizar(texto)))


# ---------------------------------------------------------------- las búsquedas en el idioma de cada mercado

ESQUEMA_TRADUCCION = obj(consultas=lista(S))
_traducidas: dict[tuple, list[str]] = {}


def consultas_en(consultas: list[str], idioma: str) -> list[str]:
    """Las búsquedas del negocio como las escribiría alguien que habla ese idioma. Las traduce Claude (una vez por
    proceso); sin su clave, o si falla, se quedan como están."""
    consultas = [c for c in consultas if c]
    if not consultas or idioma == config.IDIOMA or not llm.disponible():
        return consultas
    clave = (tuple(consultas), idioma)
    if clave not in _traducidas:
        try:
            datos = llm.json_con_esquema(
                "Traduces búsquedas de YouTube y TikTok. Devuelve cada búsqueda como la escribiría en el buscador "
                "alguien que habla ese idioma (no una traducción literal), en el mismo orden y sin añadir ninguna.",
                f"Idioma: {IDIOMAS.get(idioma, (idioma,))[0]}\n\nBúsquedas:\n" + "\n".join(f"- {c}" for c in consultas),
                ESQUEMA_TRADUCCION, effort="low",
            )
        except llm.ErrorIA:
            return consultas
        traducidas = [c.strip() for c in datos.get("consultas") or [] if c.strip()]
        _traducidas[clave] = traducidas[:len(consultas)] or consultas
    return _traducidas[clave]
