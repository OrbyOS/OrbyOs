"""Reels de Instagram y vídeos de TikTok a través de Apify.

- Instagram: actor «apify/instagram-reel-scraper», a partir de los usuarios de la competencia.
- TikTok: actor «clockworks/tiktok-scraper», por palabras clave (no hace falta conocer las cuentas).
Los actores se pueden cambiar con APIFY_IG_ACTOR y APIFY_TIKTOK_ACTOR.
"""
import os
import re
from statistics import median

from .apify import ErrorApify, ejecutar_actor, primero  # noqa: F401

ACTOR_INSTAGRAM = "apify~instagram-reel-scraper"
ACTOR_PERFIL = "apify~instagram-profile-scraper"
ACTOR_TIKTOK = "clockworks~tiktok-scraper"


def usuario_instagram(valor: str) -> str:
    """«@marca», «instagram.com/marca/» o «marca» → «marca»."""
    valor = (valor or "").strip()
    if "instagram.com" in valor:
        valor = valor.split("instagram.com/")[-1]
    valor = valor.strip("/").split("/")[0].split("?")[0].lstrip("@")
    return valor if re.fullmatch(r"[A-Za-z0-9._]{1,30}", valor) else ""


def _entero(valor) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _con_ratio(videos: list[dict], agrupar_por_cuenta: bool) -> list[dict]:
    """Veces que cada vídeo supera la mediana de su cuenta (o de toda la búsqueda)."""
    grupos: dict[str, list[int]] = {}
    for v in videos:
        grupos.setdefault(v["cuenta"] if agrupar_por_cuenta else "*", []).append(v["vistas"])
    medianas = {k: (median(vs) or 1) for k, vs in grupos.items()}
    for v in videos:
        v["ratio"] = round(v["vistas"] / medianas[v["cuenta"] if agrupar_por_cuenta else "*"], 1)
    videos.sort(key=lambda v: (v["ratio"], v["vistas"]), reverse=True)
    return videos


def normalizar_reel(r: dict) -> dict:
    return {
        "plataforma": "Instagram",
        "cuenta": primero(r, "ownerUsername", "owner.username") or "",
        "texto": (primero(r, "caption") or "")[:500],
        "vistas": _entero(primero(r, "videoPlayCount", "videoViewCount", "playCount")),
        "likes": _entero(primero(r, "likesCount")),
        "comentarios": _entero(primero(r, "commentsCount")),
        "segundos": round(float(primero(r, "videoDuration") or 0)),
        "url": primero(r, "url") or (f"https://www.instagram.com/reel/{r['shortCode']}/" if r.get("shortCode") else ""),
        "fecha": str(primero(r, "timestamp") or "")[:10],
        "imagen": primero(r, "displayUrl") or "",
        # Enlace directo al mp4: caduca en unos días, sirve para sacar el estilo de edición.
        "video_url": primero(r, "videoUrl") or "",
    }


def perfil_instagram(usuario: str) -> dict | None:
    """Perfil público de una cuenta (seguidores, biografía y últimas publicaciones), sin que conecte nada."""
    usuario = usuario_instagram(usuario)
    if not usuario:
        return None
    datos = ejecutar_actor(os.getenv("APIFY_PERFIL_ACTOR", ACTOR_PERFIL), {"usernames": [usuario]}, con_errores=True)
    d = next((x for x in datos if not x.get("error") and x.get("username")), None)
    if not d:
        return None
    publicaciones = []
    for p in d.get("latestPosts") or []:
        es_video = p.get("type") == "Video" or p.get("productType") == "clips"
        publicaciones.append({
            "plataforma": "Instagram",
            "cuenta": d["username"],
            "formato": "reel" if es_video else ("carrusel" if p.get("type") == "Sidecar" else "imagen"),
            "texto": (p.get("caption") or "")[:500],
            "vistas": _entero(primero(p, "videoPlayCount", "videoViewCount")),
            "likes": _entero(p.get("likesCount")),
            "comentarios": _entero(p.get("commentsCount")),
            "url": p.get("url") or "",
            "fecha": str(p.get("timestamp") or "")[:10],
            "imagen": p.get("displayUrl") or "",
            "video_url": p.get("videoUrl") or "",
        })
    return {
        "usuario": d["username"],
        "nombre": d.get("fullName") or "",
        "seguidores": _entero(d.get("followersCount")),
        "publicaciones_total": _entero(d.get("postsCount")),
        "biografia": d.get("biography") or "",
        "enlace": d.get("externalUrl") or "",
        "categoria": d.get("businessCategoryName") or "",
        "imagen": d.get("profilePicUrlHD") or d.get("profilePicUrl") or "",
        "ultimas": publicaciones,
    }


def normalizar_tiktok(t: dict) -> dict:
    return {
        "plataforma": "TikTok",
        "cuenta": primero(t, "authorMeta.name", "author.uniqueId", "author") or "",
        "texto": (primero(t, "text", "desc") or "")[:500],
        "vistas": _entero(primero(t, "playCount", "stats.playCount")),
        "likes": _entero(primero(t, "diggCount", "stats.diggCount")),
        "comentarios": _entero(primero(t, "commentCount", "stats.commentCount")),
        "compartidos": _entero(primero(t, "shareCount", "stats.shareCount")),
        "guardados": _entero(primero(t, "collectCount", "stats.collectCount")),
        "segundos": _entero(primero(t, "videoMeta.duration")),
        "url": primero(t, "webVideoUrl") or "",
        "fecha": str(primero(t, "createTimeISO") or "")[:10],
        "imagen": primero(t, "videoMeta.coverUrl") or "",
    }


def reels_instagram(usuarios: list[str], *, por_cuenta: int = 20, dias: int = 120,
                    cuantos: int = 12) -> tuple[list[dict], list[str]]:
    """Devuelve los reels que más destacan y las cuentas de las que no se ha podido sacar nada."""
    usuarios = [u for u in dict.fromkeys(usuario_instagram(u) for u in usuarios) if u][:8]
    if not usuarios:
        return [], []
    datos = ejecutar_actor(os.getenv("APIFY_IG_ACTOR", ACTOR_INSTAGRAM), {
        "username": usuarios,
        "resultsLimit": por_cuenta,
        "onlyPostsNewerThan": f"{dias} days",
        "skipPinnedPosts": True,
    }, con_errores=True)
    reels = [normalizar_reel(r) for r in datos if not r.get("error")]
    reels = [r for r in reels if r["vistas"] or r["likes"]]
    con_reels = {r["cuenta"].lower() for r in reels}
    sin_datos = [u for u in usuarios if u.lower() not in con_reels]
    return _con_ratio(reels, agrupar_por_cuenta=True)[:cuantos], sin_datos


def videos_tiktok(consultas: list[str], *, por_consulta: int = 30, cuantos: int = 12, idioma: str = "es",
                  pais: str = "") -> list[dict]:
    """Con `pais` (un mercado de referencia), la búsqueda sale desde ese país (el proxy del actor)."""
    consultas = [c for c in dict.fromkeys(c.strip() for c in consultas) if c][:3]
    if not consultas:
        return []
    entrada = {"searchQueries": consultas, "resultsPerPage": por_consulta}
    if pais:
        entrada["proxyCountryCode"] = pais
    datos = ejecutar_actor(os.getenv("APIFY_TIKTOK_ACTOR", ACTOR_TIKTOK), entrada)
    # La búsqueda de TikTok mezcla países e idiomas: se quedan los vídeos en el idioma del mercado.
    videos = [normalizar_tiktok(t) for t in datos
              if primero(t, "webVideoUrl") and (t.get("textLanguage") in (None, "", "un", idioma))]
    vistos, unicos = set(), []
    for v in videos:
        if v["url"] not in vistos:
            vistos.add(v["url"])
            unicos.append(v)
    # En una búsqueda salen cuentas distintas: se compara con la mediana de toda la búsqueda.
    return _con_ratio(unicos, agrupar_por_cuenta=False)[:cuantos]
