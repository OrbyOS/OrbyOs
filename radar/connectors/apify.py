"""Llamada común a Apify: lanza un actor, espera a que termine y devuelve sus resultados."""

import httpx

from .. import gasto

ESPERA_MAXIMA = 300  # segundos; es el máximo de las ejecuciones síncronas de Apify


class ErrorApify(Exception):
    pass


def ejecutar_actor(actor: str, entrada: dict, *, con_errores: bool = False) -> list[dict]:
    actor = actor.replace("/", "~")
    from .. import claves
    token = claves.clave("APIFY_TOKEN")
    if not token:
        raise ErrorApify("Falta el token de Apify: conéctalo en Conectores.")
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    try:
        r = httpx.post(
            url,
            params={"timeout": ESPERA_MAXIMA, "format": "json", "clean": "true"},
            headers={"Authorization": f"Bearer {token}"},
            json=entrada,
            timeout=ESPERA_MAXIMA + 30,
        )
    except httpx.HTTPError as e:
        raise ErrorApify(f"No hay conexión con Apify: {e.__class__.__name__}") from e
    if r.status_code == 401:
        raise ErrorApify("El token de Apify no es válido. Revisa APIFY_TOKEN en el archivo .env.")
    if r.status_code == 402:
        raise ErrorApify("Se ha acabado el saldo de Apify de este mes. Revisa tu plan en apify.com.")
    if r.status_code == 408:
        raise ErrorApify("Apify ha tardado más de 5 minutos. Prueba con menos competidores o vuelve a intentarlo.")
    if r.status_code >= 400:
        try:
            motivo = r.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            motivo = r.text[:200]
        raise ErrorApify(f"Apify respondió {r.status_code}: {motivo}")
    datos = r.json()
    if not isinstance(datos, list):
        raise ErrorApify("Apify ha devuelto un formato inesperado.")
    datos = [d for d in datos if isinstance(d, dict)]
    gasto.sumar_apify(actor, sum(1 for d in datos if not d.get("error") and not d.get("errorCode")))
    if con_errores:
        return datos
    return [d for d in datos if not d.get("errorCode") and not d.get("error")]


def primero(d: dict, *claves):
    """Devuelve el primer valor no vacío entre varias claves posibles («a.b» entra en diccionarios anidados)."""
    for clave in claves:
        valor = d
        for parte in clave.split("."):
            valor = valor.get(parte) if isinstance(valor, dict) else None
        if valor not in (None, "", [], {}):
            return valor
    return None
