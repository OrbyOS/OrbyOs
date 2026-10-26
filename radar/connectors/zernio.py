"""Zernio: publicar y programar en Instagram, TikTok, YouTube y LinkedIn con una sola clave.

Comprobado el 20/10/2026 contra su especificación (https://zernio.com/openapi.json):
- Autenticación: `Authorization: Bearer sk_...`; base `https://zernio.com/api/v1`.
- `GET /accounts` (con `profileId` si hay): cuentas conectadas, con `needsReconnection` e `isActive`.
- `POST /media/presign` {filename, contentType, size} → `uploadUrl` (se sube con PUT, sin autenticación) y `publicUrl`.
- `POST /posts` con `content`, `mediaItems`, `platforms[{platform, accountId, customContent, platformSpecificData}]`,
  `scheduledFor` (ISO con zona), `timezone` y `metadata`. Portada (23/10/2026): `mediaItems[].instagramThumbnail` en
  Reels, `mediaItems[].thumbnail` en LinkedIn y `videoCoverTimestampMs` en TikTok. Los Shorts de YouTube no admiten
  miniatura propia. La cabecera `Idempotency-Key` hace que un reintento devuelva el mismo post.
- `GET /posts/{id}` para su estado y su enlace; `DELETE /posts/{id}` para cancelar uno que aún no ha salido.
Los DMs y las palabras clave no pasan por Zernio: van por el ManyChat del negocio (connectors/manychat.py).
"""
import os
from pathlib import Path

import httpx

BASE = "https://zernio.com/api/v1"
PLATAFORMAS = ("instagram", "tiktok", "youtube", "linkedin", "facebook", "threads")


class ErrorZernio(Exception):
    pass


def clave_por_defecto() -> str:
    """La de la instalación, solo si las claves se comparten (en un servidor abierto, cada negocio pone la suya)."""
    from .. import claves
    return os.getenv("ZERNIO_API_KEY", "").strip() if claves.compartidas() else ""


def _llamar(metodo: str, ruta: str, clave: str, *, reintentar: bool = True, **kwargs) -> dict:
    if not clave:
        raise ErrorZernio("Falta la clave de Zernio.")
    cabeceras = {"Authorization": f"Bearer {clave}", **kwargs.pop("headers", {})}
    try:
        r = httpx.request(metodo, BASE + ruta, headers=cabeceras, timeout=60, **kwargs)
    except httpx.HTTPError as e:
        raise ErrorZernio(f"No hay conexión con Zernio: {e.__class__.__name__}") from e
    if r.status_code == 429 and reintentar:
        import time
        time.sleep(min(30, float(r.headers.get("Retry-After") or 5)))
        return _llamar(metodo, ruta, clave, reintentar=False, headers=cabeceras, **kwargs)
    if r.status_code in (401, 403):
        raise ErrorZernio("La clave de Zernio no es válida o no tiene permiso para esto.")
    if r.status_code == 409:
        datos = _json(r)
        if datos.get("existingPostId"):  # el mismo post ya estaba creado: se usa ese
            return {"post": {"_id": datos["existingPostId"]}, "ya_existia": True}
    if r.status_code >= 400:
        datos = _json(r)
        motivo = datos.get("error") or datos.get("message") or r.text[:200]
        raise ErrorZernio(f"Zernio respondió {r.status_code}: {motivo}")
    return _json(r)


def _json(r: httpx.Response) -> dict:
    try:
        datos = r.json()
        return datos if isinstance(datos, dict) else {"datos": datos}
    except ValueError:
        return {}


def cuentas(clave: str, perfil: str = "") -> list[dict]:
    """Las cuentas conectadas en Zernio, con lo que hace falta saber de cada una."""
    params = {"limit": 100, **({"profileId": perfil} if perfil else {})}
    datos = _llamar("GET", "/accounts", clave, params=params)
    salida = []
    for a in datos.get("accounts") or []:
        if a.get("platform") not in PLATAFORMAS:
            continue
        perfil_a = a.get("profileId")
        salida.append({"id": a.get("_id"), "plataforma": a["platform"],
                       "perfil": perfil_a.get("_id", "") if isinstance(perfil_a, dict) else (perfil_a or ""), "usuario": (a.get("username") or "").lstrip("@"),
                       "nombre": a.get("displayName") or "", "activa": bool(a.get("isActive", True)) and a.get("enabled", True) is not False,
                       "reconectar": bool(a.get("needsReconnection")), "seguidores": a.get("followersCount") or 0})
    return salida


def subir_video(clave: str, ruta: Path) -> str:
    """Sube el vídeo a Zernio y devuelve su dirección pública."""
    return _subir(clave, ruta, "video/mp4")


def subir_imagen(clave: str, ruta: Path) -> str:
    """Sube una imagen (la portada) a Zernio y devuelve su dirección pública."""
    return _subir(clave, ruta, "image/png" if ruta.suffix.lower() == ".png" else "image/jpeg")


def _subir(clave: str, ruta: Path, tipo: str) -> str:
    tam = ruta.stat().st_size
    firma = _llamar("POST", "/media/presign", clave, json={"filename": ruta.name, "contentType": tipo, "size": tam})
    if not firma.get("uploadUrl") or not firma.get("publicUrl"):
        raise ErrorZernio("Zernio no ha devuelto dónde subir el archivo.")
    try:
        with open(ruta, "rb") as f:
            r = httpx.put(firma["uploadUrl"], content=f.read(), headers={"Content-Type": tipo}, timeout=600)
    except httpx.HTTPError as e:
        raise ErrorZernio(f"No se ha podido subir el archivo: {e.__class__.__name__}") from e
    if r.status_code >= 400:
        raise ErrorZernio(f"No se ha podido subir el archivo ({r.status_code}).")
    return firma["publicUrl"]


def crear_post(clave: str, cuerpo: dict, idempotencia: str) -> dict:
    """Crea (o programa) el post. Devuelve {id, estado, plataformas}."""
    datos = _llamar("POST", "/posts", clave, json=cuerpo, headers={"Idempotency-Key": idempotencia})
    post = datos.get("post") or {}
    return {"id": post.get("_id") or "", "estado": post.get("status") or ("scheduled" if datos.get("ya_existia") else ""),
            "plataformas": post.get("platforms") or []}


def post(clave: str, post_id: str) -> dict:
    datos = _llamar("GET", f"/posts/{post_id}", clave)
    p = datos.get("post") or datos
    plataformas = p.get("platforms") or []
    primera = plataformas[0] if plataformas else {}
    return {"id": p.get("_id") or post_id, "estado": p.get("status") or "", "url": primera.get("platformPostUrl") or "",
            "estado_plataforma": primera.get("status") or "", "error": primera.get("errorMessage") or "",
            "publicado": primera.get("publishedAt") or ""}


def cancelar(clave: str, post_id: str):
    _llamar("DELETE", f"/posts/{post_id}", clave)


# ---------------------------------------------------------------- métricas de tus posts

def metricas_post(clave: str, post_id: str) -> dict:
    """`GET /analytics?postId=`: los números de un post publicado con Zernio. La tasa de salto llega en %, el tiempo
    visto en milisegundos: aquí se devuelven en tanto por uno y en segundos."""
    datos = _llamar("GET", "/analytics", clave, params={"postId": post_id})
    a = datos.get("analytics") or {}
    return {"vistas": int(a.get("views") or a.get("impressions") or 0), "alcance": int(a.get("reach") or 0),
            "likes": int(a.get("likes") or 0), "comentarios": int(a.get("comments") or 0),
            "compartidos": int(a.get("shares") or 0), "guardados": int(a.get("saves") or 0),
            "clics": int(a.get("clicks") or 0), "seguidores": a.get("follows"),
            "salto": round(float(a.get("reelsSkipRate") or 0) / 100, 3) or None,
            "visto_medio": round(float(a.get("igReelsAvgWatchTime") or 0) / 1000, 1) or None,
            "completado": float(a.get("completionRate") or 0) or None, "publicado": datos.get("publishedAt") or ""}
