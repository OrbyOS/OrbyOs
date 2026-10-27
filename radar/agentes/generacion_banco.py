"""Vídeos de banco (Pixabay) para los vídeos generados, sin que parezcan de banco.

Lo mínimo posible: antes van las grabaciones de pantalla y los planos animados. Cuando hace falta uno:
1. `buscar`: solo clips grandes (aguantan el vertical 1080×1920), cortos y sin las etiquetas que delatan el stock de
   catálogo (gente sonriendo a cámara, apretones de manos, pulgares arriba…). Mejor detalle: manos, pantallas, objetos, luz.
2. `hoja`: una hoja de contacto con los candidatos, para revisarlos a ojo antes de usar ninguno.
3. `tratar`: el clip elegido se recorta a vertical y se iguala a la marca (color apagado y azulado, grano y viñeta
   suaves), de 1,5 a 3 s. El empujón lento de cámara lo pone el montaje. Así todos parecen del mismo vídeo.
Los clips se guardan en generacion_videos/banco (fuera de git). Pixabay: uso libre, sin atribución obligatoria.
"""
import os
import subprocess
from pathlib import Path

import httpx

BANCO_DIR = Path(__file__).resolve().parents[2] / "generacion_videos" / "banco"
API = "https://pixabay.com/api/videos/"

# Lo que suele delatar el stock barato: fuera.
CUTRE = {"smile", "smiling", "happy", "handshake", "thumbs", "thumb", "teamwork", "success", "celebration", "cheering",
         "applause", "pointing", "presentation", "confident", "cheerful", "excited", "fist", "victory", "dollar", "money",
         "cartoon", "animation", "3d", "render", "green screen", "chroma", "text", "intro", "logo", "countdown",
         # el «tecnología» de catálogo: datos flotando, hologramas, redes de puntos
         "digital", "network", "data", "futuristic", "hologram", "binary", "cyber", "matrix", "virtual", "abstract",
         "particles", "glitch", "hud", "interface", "fireworks", "landscape", "mountain", "castle", "drone", "aerial"}


def _clave() -> str:
    k = os.getenv("PIXABAY_API_KEY", "").strip()
    if not k:
        raise RuntimeError("Falta PIXABAY_API_KEY en el .env")
    return k


def buscar(consulta: str, n: int = 12, min_seg: float = 4, max_seg: float = 40) -> list[dict]:
    """Candidatos ordenados por calidad: [{id, url, ancho, alto, segundos, etiquetas, miniatura, pagina}]."""
    r = httpx.get(API, params={"key": _clave(), "q": consulta, "per_page": 80, "safesearch": "true", "order": "popular"}, timeout=30)
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        etiquetas = {t.strip().lower() for t in h.get("tags", "").split(",")}
        if etiquetas & CUTRE or not (min_seg <= h.get("duration", 0) <= max_seg):
            continue
        v = h["videos"].get("large") or {}
        if not v.get("url"):
            continue
        ancho, alto = v["width"], v["height"]
        vertical = alto > ancho
        # Para sacar 1080×1920: un vertical de 1080 de ancho, o un horizontal de 1920 de alto (4K) que se recorta.
        if (vertical and ancho < 1080) or (not vertical and alto < 1920):
            continue
        out.append({"id": h["id"], "url": v["url"], "ancho": ancho, "alto": alto, "segundos": h["duration"],
                    "etiquetas": sorted(etiquetas), "miniatura": v.get("thumbnail"), "pagina": h.get("pageURL"),
                    "vertical": vertical, "gusta": h.get("likes", 0)})
    # Que tenga que ver con lo buscado: cuántas palabras de la consulta salen en sus etiquetas.
    palabras = [w for w in consulta.lower().split() if len(w) > 2]
    for x in out:
        x["parecido"] = sum(any(w in t for t in x["etiquetas"]) for w in palabras)
    out = [x for x in out if x["parecido"] >= max(1, len(palabras) // 2)]
    out.sort(key=lambda x: (x["parecido"], x["vertical"], x["gusta"]), reverse=True)
    return out[:n]


def descargar(c: dict) -> Path:
    BANCO_DIR.mkdir(parents=True, exist_ok=True)
    destino = BANCO_DIR / f"pixabay_{c['id']}.mp4"
    if not destino.exists():
        with httpx.stream("GET", c["url"], timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(destino, "wb") as f:
                for trozo in r.iter_bytes():
                    f.write(trozo)
    return destino


def hoja(candidatos: list[dict], salida: Path) -> Path:
    """Hoja de contacto con la miniatura de cada candidato (sin descargar los vídeos)."""
    carpeta = salida.parent / (salida.stem + "_mini")
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for i, c in enumerate(candidatos):
        p = carpeta / f"{i:02d}.jpg"
        p.write_bytes(httpx.get(c["miniatura"], timeout=30, follow_redirects=True).content)
        rutas.append(p)
    entradas = [x for p in rutas for x in ("-i", str(p))]
    # Sin números encima (este ffmpeg no trae drawtext): el orden es de izquierda a derecha y de arriba abajo.
    filtro = "".join(f"[{i}]scale=360:640:force_original_aspect_ratio=increase,crop=360:640,pad=364:644:2:2[v{i}];" for i in range(len(rutas)))
    columnas = min(6, len(rutas))
    filas = (len(rutas) + columnas - 1) // columnas
    capas = "".join(f"[v{i}]" for i in range(len(rutas)))
    disposicion = "|".join(f"{(i % columnas) * 364}_{(i // columnas) * 644}" for i in range(len(rutas)))
    filtro += f"{capas}xstack=inputs={len(rutas)}:layout={disposicion}:fill=black" if len(rutas) > 1 else "[v0]null"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *entradas, "-filter_complex", filtro, "-frames:v", "1", str(salida)], check=True)
    return salida


def tratar(origen: Path, salida: Path, desde: float = 0.0, segundos: float = 2.2, oscurecer: float = 0.0) -> Path:
    """Recorte vertical 1080×1920 con el tratamiento de la marca. `oscurecer` (0-1) para usarlo de fondo."""
    n = round(segundos * 30)
    filtro = (
        # Vertical a 1080×1920 (el empujón de cámara lo hace el montaje, más suave que el zoompan de ffmpeg).
        "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,fps=30,"
        "eq=saturation=0.72:contrast=1.04:brightness=-0.02,"
        "colorbalance=bs=0.06:bm=0.04:rh=-0.03,"                          # hacia el azul de la marca
        "noise=alls=7:allf=t,vignette=PI/5"
        + (f",eq=brightness={-0.22 * oscurecer}:saturation={1 - 0.3 * oscurecer}" if oscurecer else "")
    )
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(desde), "-i", str(origen), "-t", str(segundos + 0.2), "-an",
                    "-vf", filtro, "-frames:v", str(n), "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", str(salida)], check=True)
    return salida


def preparar_recurso(ve: dict, publica: Path) -> str:
    """Para el plano «recurso» de un guion: deja el clip tratado en la carpeta pública del render y devuelve su nombre.
    ve: {"pixabay": id, "desde"?: s, "segundos"?: s, "oscurecer"?: 0-1}. El clip descargado se guarda en el banco."""
    destino_dir = publica / "recursos"
    destino_dir.mkdir(parents=True, exist_ok=True)
    nombre = f"pixabay_{ve['pixabay']}_{ve.get('desde', 0)}_{ve.get('oscurecer', 0)}.mp4"
    tratado = BANCO_DIR / "tratados" / nombre
    if not tratado.exists():
        origen = BANCO_DIR / f"pixabay_{ve['pixabay']}.mp4"
        if not origen.exists():
            r = httpx.get(API, params={"key": _clave(), "id": ve["pixabay"]}, timeout=30)
            r.raise_for_status()
            v = r.json()["hits"][0]["videos"]["large"]
            descargar({"id": ve["pixabay"], "url": v["url"]})
        tratar(origen, tratado, ve.get("desde", 0), ve.get("segundos", 8), ve.get("oscurecer", 0))
    (destino_dir / nombre).write_bytes(tratado.read_bytes())
    return f"recursos/{nombre}"
