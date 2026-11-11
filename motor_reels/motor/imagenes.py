"""Imágenes reales para reforzar lo que se nombra (sección «Reforzar con imágenes reales» del manual).

Por este orden: el material propio del cliente, la imagen principal del artículo exacto de Wikipedia (licencias
libres, con autor y licencia para el pie) y la captura de la web que se nombra. Nunca Google Imágenes: tienen dueño
y los reels se usan en anuncios. No se busca por nombre a ciegas («Sagrada Familia» también es un cuadro; «Notion»,
un artista): quien decide el plano da el título exacto del artículo o el dominio. Si no aparece la imagen exacta, no
se pone ninguna: mejor un punch-in que una foto que no es.
"""
import html
import os
import re
import shutil
from pathlib import Path

import httpx

COMMONS = "https://commons.wikimedia.org/w/api.php"
CAPTURAS = "https://image.thum.io/get/width/1200/crop/1500/noanimate/https://{}"
# Wikimedia pide que cada herramienta se identifique con un contacto (si no, responde 403). En producción, pon una web
# o un correo del proyecto en MOTOR_REELS_CONTACTO.
CABECERAS = {"User-Agent": "RadarMotorReels/0.1 (+{})".format(
    os.getenv("MOTOR_REELS_CONTACTO") or "https://meta.wikimedia.org/wiki/User-Agent_policy")}
ANCHO_MIN = 600
FORMATOS = {"image/jpeg", "image/png", "image/webp"}
# Licencias que dejan reutilizar con fines comerciales, citando al autor.
LICENCIAS_OK = ("cc0", "public domain", "dominio público", "cc by", "cc-by", "pd")
IMAGEINFO = {"prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1400}


def _sin_html(texto: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", texto or "")).split())


def _guardar_de_commons(c: httpx.Client, paginas: list[dict], destino: Path) -> dict | None:
    """La primera página de archivo de Commons que vale (formato de foto, al menos 600 px y licencia libre).
    La descarga y devuelve {archivo, credito}."""
    for p in paginas:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licencia = _sin_html((meta.get("LicenseShortName") or {}).get("value", ""))
        if info.get("mime") not in FORMATOS or info.get("width", 0) < ANCHO_MIN:
            continue
        if not any(lic in licencia.lower() for lic in LICENCIAS_OK):
            continue
        img = c.get(info.get("thumburl") or info["url"])
        if img.status_code != 200 or not img.headers.get("content-type", "").startswith("image"):
            continue
        destino.write_bytes(img.content)
        autor = _sin_html((meta.get("Artist") or {}).get("value", ""))[:40]
        return {"archivo": destino, "credito": f"Foto: {autor} · {licencia}" if autor else licencia}
    return None


def de_wikipedia(articulo: str, destino: Path, *, cliente: httpx.Client | None = None) -> dict | None:
    """La imagen principal de UN artículo concreto de Wikipedia, por su título exacto en inglés (o en español):
    «Sagrada Família», «Notion (productivity software)». Es la foto reconocible por definición."""
    if not articulo.strip():
        return None
    c = cliente or httpx.Client(timeout=30, headers=CABECERAS, follow_redirects=True)
    try:
        for idioma in ("en", "es"):
            r = c.get(f"https://{idioma}.wikipedia.org/w/api.php", params={
                "action": "query", "format": "json", "titles": articulo.strip(), "redirects": 1,
                "prop": "pageimages", "piprop": "name", "pilicense": "free"})
            for p in (r.json().get("query") or {}).get("pages", {}).values():
                if "missing" in p or not p.get("pageimage"):
                    continue
                info = c.get(COMMONS, params={"action": "query", "format": "json",
                                              "titles": f"File:{p['pageimage']}", **IMAGEINFO})
                hallada = _guardar_de_commons(c, list((info.json().get("query") or {}).get("pages", {}).values()),
                                              destino)
                if hallada:
                    return hallada
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    finally:
        if cliente is None:
            c.close()
    return None


def captura_valida(ruta: Path) -> bool:
    """Descarta las capturas que no enseñan la web: casi en blanco (página que no cargó) o la pantalla de
    «verificando que no eres un robot» de Cloudflare y similares."""
    import numpy as np
    from PIL import Image
    with Image.open(ruta) as img:
        gris = np.asarray(img.convert("L").resize((120, 150)), dtype=np.float32)
    return (gris > 235).mean() < 0.88 and gris.std() > 18


def de_web(dominio: str, destino: Path) -> dict | None:
    """Captura de la portada de la web que se nombra."""
    dominio = dominio.strip().removeprefix("https://").removeprefix("http://").split("/")[0]
    if not dominio or "." not in dominio:
        return None
    try:
        r = httpx.get(CAPTURAS.format(dominio), timeout=40, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image") or len(r.content) < 5000:
        return None
    destino.write_bytes(r.content)
    if not captura_valida(destino):
        destino.unlink(missing_ok=True)
        return None
    return {"archivo": destino, "credito": dominio}


def resolver(montaje: dict, carpeta: Path, propias: dict[str, Path] | None = None) -> tuple[dict, list[str]]:
    """Busca la imagen de cada gráfico «imagen» y la deja en `carpeta`. Lo que no se encuentra se quita del montaje
    (y se avisa). `propias`: {nombre: ruta} con el material del cliente."""
    carpeta.mkdir(parents=True, exist_ok=True)
    propias = propias or {}
    avisos = []
    for p in montaje.get("planos", []):
        # Fondo con una foto del cliente: se copia a la carpeta del render; si no está, fondo de luz animada.
        fondo = p.get("fondo")
        if isinstance(fondo, dict) and fondo.get("foto") and not (carpeta / fondo["foto"]).exists():
            origen = propias.get(fondo["foto"])
            if origen and origen.exists():
                nombre = f"fondo_{p['id']}{origen.suffix.lower()}"
                shutil.copyfile(origen, carpeta / nombre)
                p["fondo"] = {"foto": nombre}
            else:
                p["fondo"] = "luz"
        g = p.get("grafico") or {}
        if g.get("tipo") != "imagen" or g.get("archivo"):
            continue
        destino = carpeta / f"{p['id']}.jpg"
        hallada = None
        if g.get("propia") and g["propia"] in propias and propias[g["propia"]].exists():
            origen = propias[g["propia"]]
            destino = destino.with_suffix(origen.suffix.lower())
            shutil.copyfile(origen, destino)
            hallada = {"archivo": destino, "credito": ""}
        else:
            # Primero el artículo exacto de Wikipedia (personas, lugares, productos) y, si no hay o no tiene foto
            # libre, la captura de su web (marcas y herramientas, cuyos logos no suelen ser libres).
            hallada = (de_wikipedia(g["wikipedia"], destino) if g.get("wikipedia") else None) or \
                (de_web(g["web"], destino) if g.get("web") else None)
        if hallada:
            g["archivo"] = hallada["archivo"].name
            g["credito"] = hallada["credito"]
        else:
            que = g.get("propia") or g.get("wikipedia") or g.get("web") or "la imagen"
            avisos.append(f"No he encontrado una imagen real y exacta de «{que}»: ese plano va sin imagen.")
            p.pop("grafico")
    return montaje, avisos
