"""Publicaciones de LinkedIn (perfiles personales y páginas de empresa) a través de Apify, sin cookies.

Actor por defecto: «harvestapi/linkedin-profile-posts» (unos 2 $ por cada 1.000 publicaciones). Se puede cambiar
con APIFY_LINKEDIN_ACTOR. LinkedIn no enseña visualizaciones: lo que destaca se mide por interacciones
(me gusta, comentarios y veces compartido) frente a la mediana de la propia cuenta.
"""
import os
import re
from datetime import date, timedelta
from statistics import median

from .apify import ErrorApify, ejecutar_actor, primero  # noqa: F401

ACTOR = "harvestapi~linkedin-profile-posts"


def url_linkedin(valor: str) -> str:
    """«linkedin.com/in/ana-lopez/», «https://es.linkedin.com/company/marca» → URL limpia, o vacío si no vale."""
    valor = (valor or "").strip()
    m = re.search(r"linkedin\.com/(in|company|school)/([^/?#\s]+)", valor, re.I)
    if not m:
        return ""
    return f"https://www.linkedin.com/{m.group(1).lower()}/{m.group(2).strip('/')}/"


def _entero(valor) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _imagen(p: dict) -> str:
    imagenes = p.get("postImages") or []
    if imagenes and isinstance(imagenes[0], dict):
        return imagenes[0].get("url") or ""
    if imagenes and isinstance(imagenes[0], str):
        return imagenes[0]
    paginas = ((p.get("document") or {}).get("coverPages") or [])
    if paginas and (paginas[0].get("imageUrls") or []):
        return paginas[0]["imageUrls"][0]
    video = p.get("postVideo") or {}
    return video.get("thumbnailUrl") or primero(p, "author.avatar.url") or ""


def _formato(p: dict) -> str:
    if p.get("document"):
        return "documento"
    if p.get("postVideo"):
        return "vídeo"
    if p.get("postImages"):
        return "imagen"
    return "texto"


def normalizar(p: dict) -> dict:
    autor = p.get("author") or {}
    eng = p.get("engagement") or {}
    likes, comentarios, compartidos = _entero(eng.get("likes")), _entero(eng.get("comments")), _entero(eng.get("shares"))
    cuenta = autor.get("publicIdentifier") or autor.get("universalName") or autor.get("name") or ""
    return {
        "plataforma": "LinkedIn",
        "cuenta": cuenta,
        "nombre": autor.get("name") or cuenta,
        "formato_publicacion": _formato(p),
        "texto": (p.get("content") or (p.get("document") or {}).get("title") or "")[:600],
        "likes": likes,
        "comentarios": comentarios,
        "compartidos": compartidos,
        # Los comentarios y los compartidos pesan más que un me gusta.
        "interaccion": likes + 2 * comentarios + 3 * compartidos,
        "url": p.get("linkedinUrl") or (p.get("socialContent") or {}).get("shareUrl") or "",
        "fecha": str(primero(p, "postedAt.date") or "")[:10],
        "imagen": _imagen(p),
    }


def _con_ratio(publicaciones: list[dict]) -> list[dict]:
    grupos: dict[str, list[int]] = {}
    for x in publicaciones:
        grupos.setdefault(x["cuenta"], []).append(x["interaccion"])
    medianas = {k: (median(v) or 1) for k, v in grupos.items()}
    for x in publicaciones:
        x["ratio"] = round(x["interaccion"] / medianas[x["cuenta"]], 1)
    publicaciones.sort(key=lambda x: (x["ratio"], x["interaccion"]), reverse=True)
    return publicaciones


def publicaciones(urls: list[str], *, por_cuenta: int = 12, dias: int = 180, cuantos: int = 12,
                  con_ratio: bool = True) -> tuple[list[dict], list[str]]:
    """Las publicaciones que más destacan de esas cuentas y las cuentas de las que no se ha sacado nada."""
    urls = [u for u in dict.fromkeys(url_linkedin(u) for u in urls) if u][:8]
    if not urls:
        return [], []
    datos = ejecutar_actor(os.getenv("APIFY_LINKEDIN_ACTOR", ACTOR), {
        "targetUrls": urls,
        "maxPosts": por_cuenta,
        "postedLimitDate": (date.today() - timedelta(days=dias)).isoformat(),
        "includeReposts": False,
        "includeQuotePosts": True,
        "scrapeReactions": False,
        "scrapeComments": False,
    }, con_errores=True)
    posts = [normalizar(p) for p in datos if not p.get("error") and (p.get("type") in (None, "post"))]
    posts = [p for p in posts if p["url"] and (p["texto"] or p["imagen"])]
    con_datos = {p["cuenta"].lower() for p in posts}
    sin_datos = [u for u in urls if u.rstrip("/").split("/")[-1].lower() not in con_datos]
    if con_ratio:
        posts = _con_ratio(posts)
    return posts[:cuantos], sin_datos
