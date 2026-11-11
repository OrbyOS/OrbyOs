"""Gasto de cada análisis: tokens de Claude y resultados de Apify, anotados por hilo de trabajo.

Cada análisis o edición se ejecuta en su propio hilo; al terminar, el total se guarda en la base de
datos con el usuario que lo generó. Los precios son aproximados y sirven para controlar el margen.
"""
import threading

_hilo = threading.local()

# $ por millón de tokens de claude-opus-5-5
PRECIOS_CLAUDE = {"entrada": 4.0, "salida": 20.0, "cache": 0.20}
PRECIO_BUSQUEDA_WEB = 0.01
# $ por resultado de cada actor de Apify (plan gratuito), más un coste fijo por ejecución
PRECIOS_APIFY = {
    "valev-lab~facebook-ads-library": 0.0004,
    "apify~instagram-reel-scraper": 0.0026,
    "apify~instagram-profile-scraper": 0.0026,
    "clockworks~tiktok-scraper": 0.0017,
    "harvestapi~linkedin-profile-posts": 0.002,
}
COSTE_EJECUCION_APIFY = 0.005


def empezar():
    _hilo.uso = {"llamadas": 0, "entrada": 0, "salida": 0, "cache": 0, "busquedas": 0,
                 "apify_resultados": 0, "apify_coste": 0.0}


def sumar_claude(usage):
    u = getattr(_hilo, "uso", None)
    if u is None or usage is None:
        return
    u["llamadas"] += 1
    u["entrada"] += (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
    u["salida"] += usage.output_tokens or 0
    u["cache"] += getattr(usage, "cache_read_input_tokens", 0) or 0
    herramientas = getattr(usage, "server_tool_use", None)
    u["busquedas"] += (getattr(herramientas, "web_search_requests", 0) or 0) if herramientas else 0


def sumar_apify(actor: str, resultados: int):
    u = getattr(_hilo, "uso", None)
    if u is None:
        return
    u["apify_resultados"] += resultados
    u["apify_coste"] += COSTE_EJECUCION_APIFY + resultados * PRECIOS_APIFY.get(actor, 0.0025)


def uso_de(usage) -> dict:
    """El gasto de una sola llamada a Claude, con el mismo formato que `uso()`."""
    empezar()
    sumar_claude(usage)
    return uso()


def uso() -> dict:
    u = dict(getattr(_hilo, "uso", None) or {})
    if not u:
        return {}
    u["coste_claude"] = round(
        u["entrada"] / 1e6 * PRECIOS_CLAUDE["entrada"] + u["salida"] / 1e6 * PRECIOS_CLAUDE["salida"]
        + u["cache"] / 1e6 * PRECIOS_CLAUDE["cache"] + u["busquedas"] * PRECIO_BUSQUEDA_WEB, 4)
    u["apify_coste"] = round(u["apify_coste"], 4)
    u["coste"] = round(u["coste_claude"] + u["apify_coste"], 4)
    return u


def sumar_llamada():
    """Una llamada a Claude Code con tu plan: cuenta la llamada; el coste va en tu suscripción."""
    u = getattr(_hilo, "uso", None)
    if u is not None:
        u["llamadas"] += 1
