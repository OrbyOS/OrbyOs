"""YouTube Data API v3 (oficial): busca vídeos y calcula cuáles destacan dentro de su canal."""
import re
from datetime import datetime, timedelta, timezone
from statistics import median

import httpx

BASE = "https://www.googleapis.com/youtube/v3"


class ErrorYouTube(Exception):
    pass


def _get(ruta: str, **params) -> dict:
    from .. import claves
    params["key"] = claves.clave("YOUTUBE_API_KEY")
    try:
        r = httpx.get(f"{BASE}/{ruta}", params=params, timeout=20)
    except httpx.HTTPError as e:
        raise ErrorYouTube(f"No hay conexión con YouTube: {e.__class__.__name__}") from e
    if r.status_code != 200:
        try:
            motivo = r.json()["error"]["message"]
        except (ValueError, KeyError):
            motivo = r.text[:200]
        raise ErrorYouTube(f"YouTube respondió {r.status_code}: {motivo}")
    return r.json()


def segundos(duracion_iso: str) -> int:
    """PT1H2M3S → 3723."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duracion_iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def ratio_outlier(vistas: int, mediana_canal: float) -> float:
    if mediana_canal <= 0:
        return 0.0
    return round(vistas / mediana_canal, 1)


def buscar(consulta: str, *, duracion: str = "any", dias: int = 365, maximo: int = 25,
           region: str = "ES", idioma: str = "es") -> list[str]:
    """Sin región (un mercado de referencia que es solo un idioma o una zona), se busca en todo YouTube."""
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filtros = {"regionCode": region} if region else {}
    datos = _get(
        "search", part="id", q=consulta, type="video", order="viewCount", maxResults=maximo,
        publishedAfter=desde, relevanceLanguage=idioma, videoDuration=duracion, **filtros,
    )
    return [i["id"]["videoId"] for i in datos.get("items", []) if i.get("id", {}).get("videoId")]


def detalles(ids: list[str]) -> list[dict]:
    salida = []
    for i in range(0, len(ids), 50):
        datos = _get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))
        for v in datos.get("items", []):
            salida.append({
                "id": v["id"],
                "titulo": v["snippet"]["title"],
                "canal": v["snippet"]["channelTitle"],
                "canal_id": v["snippet"]["channelId"],
                "publicado": v["snippet"]["publishedAt"][:10],
                "vistas": int(v.get("statistics", {}).get("viewCount", 0)),
                "segundos": segundos(v.get("contentDetails", {}).get("duration", "")),
                "url": f"https://www.youtube.com/watch?v={v['id']}",
                "imagen": f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
                "plataforma": "YouTube",
            })
    return salida


def mediana_canal(canal_id: str, cache: dict, n: int = 15) -> float:
    if canal_id in cache:
        return cache[canal_id]
    datos = _get("channels", part="contentDetails", id=canal_id)
    items = datos.get("items", [])
    if not items:
        cache[canal_id] = 0.0
        return 0.0
    subidas = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    lista = _get("playlistItems", part="contentDetails", playlistId=subidas, maxResults=n)
    ids = [i["contentDetails"]["videoId"] for i in lista.get("items", [])]
    vistas = [v["vistas"] for v in detalles(ids)] if ids else []
    cache[canal_id] = float(median(vistas)) if vistas else 0.0
    return cache[canal_id]


def outliers(consultas: list[str], *, formato: str, cuantos: int = 12, region: str = "ES",
             idioma: str = "es") -> list[dict]:
    """formato: 'largo' (más de 4 minutos) o 'corto' (Shorts, hasta 3 minutos)."""
    duracion = "short" if formato == "corto" else "any"
    ids: list[str] = []
    for q in consultas:
        for vid in buscar(q, duracion=duracion, dias=180 if formato == "corto" else 365, region=region, idioma=idioma):
            if vid not in ids:
                ids.append(vid)
    videos = detalles(ids)
    if formato == "corto":
        videos = [v for v in videos if 0 < v["segundos"] <= 180]
    else:
        videos = [v for v in videos if v["segundos"] > 240]

    cache: dict = {}
    for v in videos:
        v["mediana_canal"] = mediana_canal(v["canal_id"], cache)
        v["ratio"] = ratio_outlier(v["vistas"], v["mediana_canal"])
    videos.sort(key=lambda v: (v["ratio"], v["vistas"]), reverse=True)
    return videos[:cuantos]


def canal(valor: str) -> dict | None:
    """Datos públicos de un canal a partir de «@usuario», su enlace o su ID."""
    valor = (valor or "").strip().rstrip("/")
    if not valor:
        return None
    m = re.search(r"youtube\.com/(@[\w.-]+|channel/(UC[\w-]{20,}))", valor)
    usuario = re.search(r"youtube\.com/user/([\w.-]+)", valor)
    if m:
        params = {"id": m.group(2)} if m.group(2) else {"forHandle": m.group(1)}
    elif usuario:
        params = {"forUsername": usuario.group(1)}
    elif valor.startswith("UC") and len(valor) > 20:
        params = {"id": valor}
    else:
        params = {"forHandle": valor if valor.startswith("@") else f"@{valor}"}
    items = _get("channels", part="snippet,statistics,contentDetails", **params).get("items", [])
    if not items:
        return None
    c = items[0]
    est = c.get("statistics", {})
    return {
        "id": c["id"],
        "nombre": c["snippet"]["title"],
        "suscriptores": int(est.get("subscriberCount", 0) or 0),
        "videos": int(est.get("videoCount", 0) or 0),
        "vistas": int(est.get("viewCount", 0) or 0),
        "url": f"https://www.youtube.com/channel/{c['id']}",
        "subidas": c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
    }


def videos_del_canal(valor: str, *, n: int = 30, cuantos: int = 4) -> dict | None:
    """Los últimos vídeos y Shorts de un canal (su lista de subidas), cada uno con su ratio frente a la mediana de
    su formato en ese canal: un Short y un vídeo largo no se comparan entre sí. Se guardan los que más destacan."""
    datos = canal(valor)
    if not datos or not datos["subidas"]:
        return None
    lista = _get("playlistItems", part="contentDetails", playlistId=datos["subidas"], maxResults=min(n, 50))
    ids = [i["contentDetails"]["videoId"] for i in lista.get("items", [])]
    videos = detalles(ids) if ids else []
    salida = {**datos, "analizados": len(videos)}
    # Los directos programados no tienen duración ni visualizaciones: no entran en ningún grupo.
    for clave, grupo in (("videos", [v for v in videos if v["segundos"] > 180]),
                         ("shorts", [v for v in videos if 0 < v["segundos"] <= 180])):
        mediana_ = float(median([v["vistas"] for v in grupo])) if grupo else 0.0
        for v in grupo:
            v["mediana_canal"] = mediana_
            v["ratio"] = ratio_outlier(v["vistas"], mediana_)
        grupo.sort(key=lambda v: (v["ratio"], v["vistas"]), reverse=True)
        salida[f"mediana_{clave}"] = mediana_
        salida[clave] = grupo[:cuantos]
    return salida


def comentarios(video_id: str, *, n: int = 40, largo: int = 300) -> list[str]:
    """Los comentarios más relevantes de un vídeo, en texto plano. Si están desactivados, ninguno."""
    try:
        datos = _get("commentThreads", part="snippet", videoId=video_id, order="relevance", maxResults=min(n, 100),
                     textFormat="plainText")
    except ErrorYouTube:
        return []
    salida = []
    for i in datos.get("items", []):
        texto = " ".join(str(i["snippet"]["topLevelComment"]["snippet"].get("textDisplay") or "").split())
        if texto:
            salida.append(texto[:largo])
    return salida


def info_canales(ids: list[str]) -> dict[str, dict]:
    """Nombre, descripción y suscriptores de varios canales a la vez (50 por llamada)."""
    salida = {}
    for i in range(0, len(ids), 50):
        for c in _get("channels", part="snippet,statistics", id=",".join(ids[i:i + 50])).get("items", []):
            est = c.get("statistics", {})
            salida[c["id"]] = {"id": c["id"], "nombre": c["snippet"]["title"],
                               "descripcion": (c["snippet"].get("description") or "")[:300],
                               "suscriptores": int(est.get("subscriberCount", 0) or 0),
                               "url": f"https://www.youtube.com/channel/{c['id']}"}
    return salida
