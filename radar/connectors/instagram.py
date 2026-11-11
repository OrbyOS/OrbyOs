"""Instagram por su API oficial («Instagram API with Instagram Login»): la palabra clave sin ManyChat.

Comprobado el 27/10/2026 contra la documentación de Meta (developers.facebook.com/docs/instagram-platform):
- Base `https://graph.instagram.com/<versión>`; el token de la cuenta va en `Authorization: Bearer <token>`.
- `GET /me?fields=user_id,username`: la cuenta (sirve para comprobar el token). `user_id` es el id que llega en los
  avisos (entry[].id) y el que se usa para mandar mensajes.
- `POST /me/subscribed_apps?subscribed_fields=comments,messages`: que Meta avise de los comentarios y los mensajes.
- Avisos (webhooks): Meta comprueba la dirección con un GET (hub.mode=subscribe, hub.verify_token, hub.challenge) y
  luego manda cada comentario por POST, firmado en `X-Hub-Signature-256` (HMAC-SHA256 del cuerpo con la clave secreta
  de la app de Instagram). Cada comentario: entry[].changes[] con field «comments» y value {id, text, from{id,
  username}, media{id, media_product_type}}.
- Respuesta privada: `POST /<user_id>/messages` {recipient: {comment_id}, message: {text, quick_replies}}. Una por
  comentario y en los 7 días siguientes. Después solo se puede volver a escribir cuando esa persona conteste, y dentro
  de las 24 h siguientes a su respuesta: `POST /<user_id>/messages` {recipient: {id: <su id>}, message: {text}}.
- Los mensajes que llegan (campo «messages» de los avisos): entry[].messaging[] con sender.id, recipient.id y
  message {mid, text, quick_reply{payload}, is_echo}.
- Respuesta pública: `POST /<comment_id>/replies` {message}.
- Renovar el token (dura 60 días): `GET /refresh_access_token?grant_type=ig_refresh_token`. Solo si tiene más de 24 h.
- Permisos: instagram_business_basic, instagram_business_manage_comments e instagram_business_manage_messages. Mientras
  la app de Meta está en modo desarrollo, solo se puede escribir a cuentas con un rol en la app.
"""
import hashlib
import hmac

import httpx

VERSION = "v23.0"
BASE = f"https://graph.instagram.com/{VERSION}"


class ErrorInstagram(Exception):
    pass


def _llamar(metodo: str, ruta: str, token: str, **kwargs) -> dict:
    if not token:
        raise ErrorInstagram("Falta el token de Instagram.")
    url = ruta if ruta.startswith("https://") else BASE + ruta
    try:
        r = httpx.request(metodo, url, headers={"Authorization": f"Bearer {token}"}, timeout=30, **kwargs)
    except httpx.HTTPError as e:
        raise ErrorInstagram(f"No hay conexión con Instagram: {e.__class__.__name__}") from e
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    if r.status_code >= 400:
        error = (datos.get("error") or {}) if isinstance(datos, dict) else {}
        if r.status_code in (401, 403) or error.get("code") == 190:
            raise ErrorInstagram("El token de Instagram no vale o ha caducado: genera uno nuevo en el panel de Meta.")
        if error.get("code") == 10 or "permission" in (error.get("message") or "").lower():
            raise ErrorInstagram("Instagram no da permiso: falta un permiso en el token, o la app de Meta está en modo "
                                 "desarrollo y esa cuenta no tiene un rol en ella.")
        raise ErrorInstagram(f"Instagram ha respondido {r.status_code}: {(error.get('message') or '')[:200]}")
    return datos if isinstance(datos, dict) else {}


def cuenta(token: str) -> dict:
    """{id, usuario} de la cuenta del token."""
    d = _llamar("GET", "/me", token, params={"fields": "user_id,username"})
    return {"id": str(d.get("user_id") or d.get("id") or ""), "usuario": d.get("username", "")}


CAMPOS = "comments,messages"


def suscribir(token: str) -> bool:
    d = _llamar("POST", "/me/subscribed_apps", token, params={"subscribed_fields": CAMPOS})
    return bool(d.get("success", True))


def _mensaje(texto: str, botones: list[tuple[str, str]] | None) -> dict:
    m = {"text": texto}
    if botones:
        m["quick_replies"] = [{"content_type": "text", "title": t[:20], "payload": p} for t, p in botones]
    return m


def responder_en_privado(token: str, cuenta_id: str, comentario_id: str, texto: str,
                         botones: list[tuple[str, str]] | None = None) -> str:
    """Manda un mensaje privado a quien ha escrito ese comentario. `botones`: [(título, payload)] de respuesta rápida.
    Devuelve el id del mensaje."""
    d = _llamar("POST", f"/{cuenta_id}/messages", token,
                json={"recipient": {"comment_id": comentario_id}, "message": _mensaje(texto, botones)})
    return str(d.get("message_id") or "")


def enviar_mensaje(token: str, cuenta_id: str, destinatario_id: str, texto: str) -> str:
    """Un mensaje a alguien que ha escrito en las últimas 24 h."""
    d = _llamar("POST", f"/{cuenta_id}/messages", token,
                json={"recipient": {"id": destinatario_id}, "message": {"text": texto}})
    return str(d.get("message_id") or "")


def nombre_de(token: str, usuario_id: str) -> str:
    """El nombre del perfil de alguien (GET /<id>?fields=name). Vacío si Meta no lo da (no siempre lo hace)."""
    try:
        return str(_llamar("GET", f"/{usuario_id}", token, params={"fields": "name"}).get("name") or "")
    except ErrorInstagram:
        return ""


def responder_en_publico(token: str, comentario_id: str, texto: str) -> str:
    d = _llamar("POST", f"/{comentario_id}/replies", token, data={"message": texto})
    return str(d.get("id") or "")


AUTORIZAR = "https://www.instagram.com/oauth/authorize"
PERMISOS = "instagram_business_basic,instagram_business_manage_comments,instagram_business_manage_messages"


def enlace_autorizar(app_id: str, volver: str, estado: str) -> str:
    """La página de Instagram donde la persona entra con su cuenta y da permiso a la app."""
    from urllib.parse import urlencode
    return AUTORIZAR + "?" + urlencode({"client_id": app_id, "redirect_uri": volver, "response_type": "code",
                                        "scope": PERMISOS, "state": estado})


def token_desde_codigo(app_id: str, secreto: str, volver: str, codigo: str) -> str:
    """El código que devuelve Instagram → token de 60 días."""
    try:
        r = httpx.post("https://api.instagram.com/oauth/access_token", timeout=30,
                       data={"client_id": app_id, "client_secret": secreto, "grant_type": "authorization_code",
                             "redirect_uri": volver, "code": codigo.split("#")[0]})
    except httpx.HTTPError as e:
        raise ErrorInstagram(f"No hay conexión con Instagram: {e.__class__.__name__}") from e
    corto = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("access_token")
    if r.status_code >= 400 or not corto:
        raise ErrorInstagram("Instagram no ha aceptado el permiso. Vuelve a intentarlo.")
    d = _llamar("GET", "https://graph.instagram.com/access_token", corto,
                params={"grant_type": "ig_exchange_token", "client_secret": secreto, "access_token": corto})
    return d.get("access_token") or corto


def renovar(token: str) -> dict:
    """{token, segundos}: el token renovado (otros 60 días)."""
    d = _llamar("GET", "https://graph.instagram.com/refresh_access_token", token,
                params={"grant_type": "ig_refresh_token", "access_token": token})
    return {"token": d.get("access_token", ""), "segundos": int(d.get("expires_in") or 0)}


def firma_valida(cuerpo: bytes, cabecera: str, secreto: str) -> bool:
    """La cabecera X-Hub-Signature-256 («sha256=<hex>») corresponde a este cuerpo con la clave secreta de la app."""
    if not secreto or not (cabecera or "").startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, cabecera.split("=", 1)[1].strip())


def comentarios(aviso: dict) -> list[dict]:
    """Los comentarios que trae un aviso: [{cuenta_id, id, texto, autor_id, autor, media_id}]."""
    if not isinstance(aviso, dict) or aviso.get("object") != "instagram":
        return []
    salida = []
    for entrada in aviso.get("entry") or []:
        for cambio in (entrada or {}).get("changes") or []:
            if (cambio or {}).get("field") != "comments":
                continue
            v = cambio.get("value") or {}
            autor = v.get("from") or {}
            if not v.get("id"):
                continue
            salida.append({"cuenta_id": str(entrada.get("id") or ""), "id": str(v["id"]), "texto": v.get("text") or "",
                           "autor_id": str(autor.get("id") or ""), "autor": autor.get("username") or "",
                           "media_id": str((v.get("media") or {}).get("id") or ""),
                           "respuesta_a": str(v.get("parent_id") or "")})
    return salida


def mensajes(aviso: dict) -> list[dict]:
    """Los mensajes privados que trae un aviso (sin los que manda la propia cuenta): [{cuenta_id, autor_id, texto,
    payload, id}]."""
    if not isinstance(aviso, dict) or aviso.get("object") != "instagram":
        return []
    salida = []
    for entrada in aviso.get("entry") or []:
        for m in (entrada or {}).get("messaging") or []:
            cuerpo = (m or {}).get("message") or {}
            autor = str(((m or {}).get("sender") or {}).get("id") or "")
            if not cuerpo or cuerpo.get("is_echo") or not autor or autor == str(entrada.get("id") or ""):
                continue
            salida.append({"cuenta_id": str(entrada.get("id") or ""), "autor_id": autor, "texto": cuerpo.get("text") or "",
                           "payload": (cuerpo.get("quick_reply") or {}).get("payload") or "",
                           "id": str(cuerpo.get("mid") or "")})
    return salida
