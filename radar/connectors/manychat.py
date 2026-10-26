"""ManyChat: los DMs y la palabra clave de Instagram, con el ManyChat del propio negocio (plan Pro).

Comprobado el 21/10/2026 contra su especificación (https://api.manychat.com/swagger, «Page API»):
- Autenticación: `Authorization: Bearer <clave>` (ManyChat → Settings → API); base `https://api.manychat.com`.
  Cada respuesta llega como {"status": "success", "data": …}.
- `GET /fb/page/getInfo`: la cuenta (sirve para comprobar la clave).
- `GET /fb/page/getTags`, `POST /fb/page/createTag` {name}; `GET /fb/page/getCustomFields`,
  `POST /fb/page/createCustomField` {caption, type, description}; `GET /fb/page/getFlows` → {flows: [{ns, name}]}.
- `POST /fb/subscriber/addTagByName` y `removeTagByName` {subscriber_id, tag_name};
  `POST /fb/subscriber/setCustomFieldByName` {subscriber_id, field_name, field_value}; `GET /fb/subscriber/getInfo`.
- `POST /fb/sending/sendContent` {subscriber_id, data}: un mensaje con el formato de bloque dinámico v2. Instagram solo
  deja escribir por la API dentro de las 24 h siguientes al último mensaje de esa persona.
La API no crea automatizaciones ni lee la bandeja: por eso una automatización de ManyChat («Equipo · DMs») le pasa a la
app cada DM, y Radar le contesta qué mandar. ManyChat tampoco da el texto de un comentario (ni el post) a una petición
externa (foro de ManyChat, 14/08/2026): cada palabra clave lleva su propia automatización de comentarios, que manda la
palabra fija.
"""
import os
import time

import httpx

BASE = "https://api.manychat.com"

# Lo que Radar deja en cada contacto de ManyChat, para que el negocio lo use en sus propias automatizaciones.
ETIQUETAS = {"caliente": "equipo-caliente", "templado": "equipo-templado", "frio": "equipo-frio"}
CAMPOS = {
    "equipo_respuesta": "Lo que la app quiere que ManyChat mande ahora",
    "equipo_responder": "«si» si hay que mandar equipo_respuesta",
    "equipo_palabra": "La última palabra clave que ha usado",
    "equipo_temperatura": "caliente, templado o frio, según la app",
    "equipo_origen": "El post que lo trajo (utm_content)",
    "equipo_email": "El correo que dejó en la guía",
}


class ErrorManyChat(Exception):
    pass


def clave_por_defecto() -> str:
    """La de la instalación, solo si las claves se comparten (en un servidor abierto, cada negocio pone la suya)."""
    from .. import claves
    return os.getenv("MANYCHAT_API_KEY", "").strip() if claves.compartidas() else ""


def _llamar(metodo: str, ruta: str, clave: str, *, reintentar: bool = True, **kwargs):
    if not clave:
        raise ErrorManyChat("Falta la clave de ManyChat.")
    try:
        r = httpx.request(metodo, BASE + ruta, headers={"Authorization": f"Bearer {clave}", "Accept": "application/json"},
                          timeout=30, **kwargs)
    except httpx.HTTPError as e:
        raise ErrorManyChat(f"No hay conexión con ManyChat: {e.__class__.__name__}") from e
    if r.status_code == 429 and reintentar:
        time.sleep(2)
        return _llamar(metodo, ruta, clave, reintentar=False, **kwargs)
    if r.status_code in (401, 403):
        raise ErrorManyChat("La clave de ManyChat no es válida, o la cuenta no tiene el plan Pro (la API lo necesita).")
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    if r.status_code >= 400 or (isinstance(datos, dict) and datos.get("status") == "error"):
        motivo = (datos.get("message") or datos.get("details") or r.text[:200]) if isinstance(datos, dict) else r.text[:200]
        raise ErrorManyChat(f"ManyChat respondió {r.status_code}: {motivo}")
    return datos.get("data") if isinstance(datos, dict) else None


# ---------------------------------------------------------------- la cuenta

def cuenta(clave: str) -> dict:
    d = _llamar("GET", "/fb/page/getInfo", clave) or {}
    return {"id": str(d.get("id") or ""), "nombre": d.get("name") or "", "usuario": d.get("username") or "",
            "pro": d.get("is_pro")}


def etiquetas(clave: str) -> list[str]:
    return [t.get("name") or "" for t in _llamar("GET", "/fb/page/getTags", clave) or []]


def crear_etiqueta(clave: str, nombre: str):
    _llamar("POST", "/fb/page/createTag", clave, json={"name": nombre})


def campos(clave: str) -> list[str]:
    return [c.get("name") or "" for c in _llamar("GET", "/fb/page/getCustomFields", clave) or []]


def crear_campo(clave: str, nombre: str, descripcion: str = ""):
    _llamar("POST", "/fb/page/createCustomField", clave, json={"caption": nombre, "type": "text",
                                                               "description": descripcion[:200]})


def flujos(clave: str) -> list[dict]:
    d = _llamar("GET", "/fb/page/getFlows", clave) or {}
    return [{"ns": f.get("ns") or "", "nombre": f.get("name") or ""} for f in d.get("flows") or []]


def preparar(clave: str) -> list[str]:
    """Crea en la cuenta las etiquetas y los campos de Radar que falten. Devuelve lo que ha creado."""
    creados = []
    hay = {t.lower() for t in etiquetas(clave)}
    for nombre in ETIQUETAS.values():
        if nombre not in hay:
            crear_etiqueta(clave, nombre)
            creados.append(nombre)
    hay = {c.lower() for c in campos(clave)}
    for nombre, descripcion in CAMPOS.items():
        if nombre not in hay:
            crear_campo(clave, nombre, descripcion)
            creados.append(nombre)
    return creados


# ---------------------------------------------------------------- cada contacto

def contacto(clave: str, suscriptor: str) -> dict:
    return _llamar("GET", "/fb/subscriber/getInfo", clave, params={"subscriber_id": int(suscriptor)}) or {}


def poner_etiqueta(clave: str, suscriptor: str, nombre: str):
    _llamar("POST", "/fb/subscriber/addTagByName", clave, json={"subscriber_id": int(suscriptor), "tag_name": nombre})


def quitar_etiqueta(clave: str, suscriptor: str, nombre: str):
    _llamar("POST", "/fb/subscriber/removeTagByName", clave, json={"subscriber_id": int(suscriptor), "tag_name": nombre})


def poner_campo(clave: str, suscriptor: str, nombre: str, valor: str):
    _llamar("POST", "/fb/subscriber/setCustomFieldByName", clave,
            json={"subscriber_id": int(suscriptor), "field_name": nombre, "field_value": str(valor)[:1000]})


def temperatura(clave: str, suscriptor: str, nueva: str):
    """Deja una sola etiqueta de temperatura en el contacto, y la temperatura en su campo."""
    for t, etiqueta in ETIQUETAS.items():
        if t == nueva:
            poner_etiqueta(clave, suscriptor, etiqueta)
        else:
            quitar_etiqueta(clave, suscriptor, etiqueta)
    poner_campo(clave, suscriptor, "equipo_temperatura", nueva)


def enviar_texto(clave: str, suscriptor: str, texto: str, canal: str = "instagram"):
    """Un mensaje de texto al contacto, por Instagram (o el canal que se diga)."""
    datos = {"version": "v2", "content": {"type": canal, "messages": [{"type": "text", "text": texto[:1000]}]}}
    _llamar("POST", "/fb/sending/sendContent", clave, json={"subscriber_id": int(suscriptor), "data": datos})
