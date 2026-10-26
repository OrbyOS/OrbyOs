"""Descarga una página web y saca lo que importa para entender un negocio o un funnel."""
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

NAVEGADOR = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
MAX_TEXTO = 12000

# 1.234,56 € · 97€ · 1.997 euros · €97 · $97 · 97 USD
_PRECIO = re.compile(
    r"(?:(?:€|\$)\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)"
    r"|(?:\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?\s?(?:€|euros?|EUR|USD|\$))",
    re.IGNORECASE,
)


@dataclass
class Pagina:
    url: str
    ok: bool
    url_final: str = ""
    estado: int = 0
    titulo: str = ""
    descripcion: str = ""
    encabezados: list[str] = field(default_factory=list)
    botones: list[str] = field(default_factory=list)
    campos_formulario: list[str] = field(default_factory=list)
    enlaces_externos: list[str] = field(default_factory=list)
    precios: list[str] = field(default_factory=list)
    texto: str = ""
    error: str = ""

    def resumen(self) -> dict:
        d = asdict(self)
        d["texto"] = self.texto[:4000]
        return d


def normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url


def descargar(url: str, timeout: float = 15.0) -> Pagina:
    url = normalizar_url(url)
    if not url:
        return Pagina(url="", ok=False, error="Sin URL")
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": NAVEGADOR}) as c:
            r = c.get(url)
    except httpx.HTTPError as e:
        return Pagina(url=url, ok=False, error=f"No se pudo abrir: {e.__class__.__name__}")
    if "html" not in r.headers.get("content-type", "html"):
        return Pagina(url=url, ok=False, url_final=str(r.url), estado=r.status_code, error="No es una página HTML")
    pagina = analizar_html(r.text, str(r.url))
    pagina.url = url
    pagina.estado = r.status_code
    pagina.ok = r.status_code < 400
    if not pagina.ok:
        pagina.error = f"La página respondió {r.status_code}"
    return pagina


def analizar_html(html: str, url_final: str) -> Pagina:
    sopa = BeautifulSoup(html, "html.parser")
    for etiqueta in sopa(["script", "style", "noscript", "svg"]):
        etiqueta.decompose()

    titulo = (sopa.title.get_text(strip=True) if sopa.title else "")[:200]
    meta = sopa.find("meta", attrs={"name": "description"})
    descripcion = (meta.get("content", "") if meta else "")[:400]
    encabezados = _unicos(h.get_text(" ", strip=True) for h in sopa.find_all(["h1", "h2", "h3"]))[:30]
    botones = _unicos(
        b.get_text(" ", strip=True)
        for b in sopa.find_all(["button", "a"])
        if b.name == "button" or "btn" in " ".join(b.get("class", [])) or "button" in " ".join(b.get("class", []))
    )[:30]
    campos = _unicos(
        (i.get("type") or i.name) + ":" + (i.get("name") or i.get("placeholder") or "")
        for i in sopa.find_all(["input", "select", "textarea"])
        if (i.get("type") or "") not in ("hidden", "submit")
    )[:20]

    dominio = urlparse(url_final).netloc.replace("www.", "")
    externos = []
    for a in sopa.find_all("a", href=True):
        destino = urljoin(url_final, a["href"])
        host = urlparse(destino).netloc.replace("www.", "")
        if host and host != dominio:
            externos.append(destino)
    texto = re.sub(r"\s+", " ", sopa.get_text(" ", strip=True))

    return Pagina(
        url=url_final, ok=True, url_final=url_final, titulo=titulo, descripcion=descripcion,
        encabezados=encabezados, botones=botones, campos_formulario=campos,
        enlaces_externos=_unicos(externos)[:40], precios=_unicos(_PRECIO.findall(texto))[:15],
        texto=texto[:MAX_TEXTO],
    )


def _unicos(valores) -> list[str]:
    vistos, salida = set(), []
    for v in valores:
        v = (v or "").strip()
        if v and v.lower() not in vistos:
            vistos.add(v.lower())
            salida.append(v)
    return salida
