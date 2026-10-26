"""Telegram: el resumen de cada mañana, tus aprobaciones con botones y el chat con Vega en el móvil.

Bot API (https://core.telegram.org/bots/api), sin webhooks: la app pregunta cada pocos segundos con getUpdates, así que
funciona aunque Radar esté en tu ordenador. El token lo da @BotFather.
"""
import json
from pathlib import Path

import httpx

BASE = "https://api.telegram.org/bot{token}/{metodo}"
LIMITE_TEXTO = 4096


class ErrorTelegram(Exception):
    pass


def _llamar(token: str, metodo: str, *, timeout: float = 30, files=None, **datos) -> dict | list:
    if not token:
        raise ErrorTelegram("Falta el token del bot de Telegram.")
    try:
        if files:
            r = httpx.post(BASE.format(token=token, metodo=metodo), data=datos, files=files, timeout=timeout)
        else:
            r = httpx.post(BASE.format(token=token, metodo=metodo), json=datos, timeout=timeout)
    except httpx.HTTPError as e:
        raise ErrorTelegram(f"No hay conexión con Telegram: {e.__class__.__name__}") from e
    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = {}
    if r.status_code == 401:
        raise ErrorTelegram("El token del bot no es válido. Cópialo otra vez de @BotFather.")
    if not cuerpo.get("ok"):
        raise ErrorTelegram(f"Telegram respondió {r.status_code}: {cuerpo.get('description') or r.text[:200]}")
    return cuerpo.get("result")


def bot(token: str) -> dict:
    r = _llamar(token, "getMe")
    return {"usuario": r.get("username", ""), "nombre": r.get("first_name", "")}


def novedades(token: str, desde: int = 0) -> list[dict]:
    """Mensajes y pulsaciones de botones nuevos (desde = el último update_id visto + 1)."""
    return _llamar(token, "getUpdates", offset=desde, timeout=0, allowed_updates=["message", "callback_query"]) or []


def enviar(token: str, chat: str, texto: str, botones: list[list[dict]] | None = None) -> int:
    datos = {"chat_id": chat, "text": texto[:LIMITE_TEXTO], "disable_web_page_preview": True}
    if botones:
        datos["reply_markup"] = {"inline_keyboard": botones}
    return (_llamar(token, "sendMessage", **datos) or {}).get("message_id", 0)


def enviar_video(token: str, chat: str, ruta: Path, texto: str) -> int:
    with open(ruta, "rb") as f:
        r = _llamar(token, "sendVideo", timeout=300, files={"video": (ruta.name, f, "video/mp4")},
                    chat_id=chat, caption=texto[:1024])
    return (r or {}).get("message_id", 0)


def contestar_boton(token: str, id_pulsacion: str, texto: str = ""):
    _llamar(token, "answerCallbackQuery", callback_query_id=id_pulsacion, text=texto[:200])


def quitar_botones(token: str, chat: str, mensaje: int, texto: str):
    _llamar(token, "editMessageText", chat_id=chat, message_id=mensaje, text=texto[:LIMITE_TEXTO],
            reply_markup=json.loads('{"inline_keyboard": []}'))
