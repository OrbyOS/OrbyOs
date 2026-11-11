"""Cuentas: contraseñas con scrypt, sesiones en una cookie y comprobación de permisos."""
import hashlib
import hmac
import re
import secrets

from fastapi import Request

from . import config, db

COOKIE = "sesion"
DIAS_SESION = 30
_N, _R, _P = 2**14, 8, 1


class NoAutenticado(Exception):
    """La página necesita una sesión: main.py la convierte en una redirección a /entrar."""


class SinPermiso(Exception):
    pass


def cifrar(clave: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${sal.hex()}${h.hex()}"


def comprobar(clave: str, guardada: str) -> bool:
    try:
        _, sal, h = guardada.split("$")
    except ValueError:
        return False
    calculada = hashlib.scrypt(clave.encode(), salt=bytes.fromhex(sal), n=_N, r=_R, p=_P, dklen=32)
    return hmac.compare_digest(calculada.hex(), h)


def email_valido(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""))


def registrar(email: str, nombre: str, clave: str, tipo: str = "negocio") -> tuple[dict | None, str]:
    """Devuelve el usuario creado o el motivo por el que no se ha podido crear."""
    email = (email or "").strip().lower()
    if not email_valido(email):
        return None, "Ese correo no parece válido."
    if len(clave or "") < 8:
        return None, "La contraseña tiene que tener al menos 8 caracteres."
    if db.usuario_por_email(email):
        return None, "Ya hay una cuenta con ese correo. Entra con tu contraseña."
    tipo = tipo if tipo in config.TIPOS_CUENTA else "negocio"
    es_admin = db.contar_usuarios() == 0 or email in config.ADMIN_EMAILS
    uid = db.crear_usuario(email, (nombre or "").strip(), cifrar(clave), es_admin=es_admin, tipo=tipo,
                           plan="interno" if es_admin else config.plan_inicial(tipo))
    return db.usuario(uid), ""


def entrar(email: str, clave: str) -> dict | None:
    u = db.usuario_por_email((email or "").strip())
    if u and u["activo"] and comprobar(clave or "", u["clave"]):
        return u
    return None


def abrir_sesion(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.crear_sesion(token, usuario_id, DIAS_SESION)
    return token


def poner_cookie(respuesta, token: str):
    respuesta.set_cookie(COOKIE, token, max_age=DIAS_SESION * 86400, httponly=True, samesite="lax",
                         secure=config.COOKIE_SEGURA)


def usuario_actual(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    return db.usuario_de_sesion(token) if token else None


def requiere_usuario(request: Request) -> dict:
    u = usuario_actual(request)
    if not u:
        raise NoAutenticado()
    return u


def requiere_admin(request: Request) -> dict:
    u = requiere_usuario(request)
    if not u["es_admin"]:
        raise SinPermiso()
    return u


def nuevo_token() -> str:
    return secrets.token_urlsafe(18)


def negocio_propio(usuario: dict, negocio_id: int) -> dict:
    """El negocio, si es de este usuario (el administrador ve todos)."""
    neg = db.negocio(negocio_id)
    if not neg or (neg["usuario_id"] != usuario["id"] and not usuario["es_admin"]):
        raise SinPermiso()
    return neg


def cupo(usuario: dict) -> dict:
    """Lo que le queda este mes según su plan."""
    p = config.plan(usuario["plan"])
    u = db.uso_del_mes(usuario["id"])
    return {
        "plan": p,
        "uso": u,
        "negocios": max(0, p.negocios - db.contar_negocios(usuario["id"])),
        "analisis": max(0, p.analisis_mes - u["analisis"]),
        "actualizaciones": max(0, p.actualizaciones_mes - u["actualizaciones"]),
        "ediciones": max(0, p.ediciones_mes - u["ediciones"]),
    }
