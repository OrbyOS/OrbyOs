"""Las claves de cada negocio: cada cuenta conecta su Claude, su Apify y su YouTube, y paga su propio gasto.

- Se guardan con el negocio (Conectores) y no se vuelven a enseñar: solo se ve si están puestas.
- Todo lo que hace un negocio (una página, un trabajo en segundo plano, el piloto, un mensaje de ManyChat) se ejecuta
  «dentro» de ese negocio, y entonces `clave()` devuelve la suya.
- Sin clave propia: en una instalación para uno mismo (RADAR_CLAVES_COMPARTIDAS=1, lo normal en tu ordenador) vale la
  de la instalación; en un servidor abierto a más gente (RADAR_CLAVES_COMPARTIDAS=0) no hay clave: cada uno, la suya.
"""
import contextvars
import json
import os
from contextlib import contextmanager
from datetime import datetime

PROPIAS = {
    "ANTHROPIC_API_KEY": "Clave de la API de Claude",
    "APIFY_TOKEN": "Token de Apify",
    "YOUTUBE_API_KEY": "Clave de YouTube (YouTube Data API v3)",
}

NEGOCIO: contextvars.ContextVar[int | None] = contextvars.ContextVar("radar_negocio", default=None)


def compartidas() -> bool:
    return os.getenv("RADAR_CLAVES_COMPARTIDAS", "1").strip() == "1"


def actual() -> int | None:
    return NEGOCIO.get()


def usar(negocio_id: int | None):
    """Desde aquí, lo que se haga es de este negocio (hasta que acabe la petición o el hilo)."""
    return NEGOCIO.set(negocio_id)


@contextmanager
def en(negocio_id: int | None):
    marca = NEGOCIO.set(negocio_id)
    try:
        yield
    finally:
        NEGOCIO.reset(marca)


def del_negocio(negocio_id: int) -> dict:
    from . import db
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM conexiones WHERE negocio_id = ? AND servicio = 'claves'", (negocio_id,)).fetchone()
    return json.loads(f["datos"]) if f else {}


def guardar(negocio_id: int, cambios: dict[str, str], quitar: tuple[str, ...] = ()) -> list[str]:
    """Guarda las que llegan (lo vacío no toca lo que había) y quita las que se pidan. Devuelve qué ha cambiado."""
    from . import db
    datos, hechos = del_negocio(negocio_id), []
    for var, valor in cambios.items():
        if var in PROPIAS and (valor or "").strip():
            datos[var] = valor.strip()
            hechos.append(PROPIAS[var])
    for var in quitar:
        if datos.pop(var, None):
            hechos.append(f"{PROPIAS[var]} (quitada)")
    with db.conexion() as con:
        con.execute("INSERT INTO conexiones (negocio_id, servicio, actualizado, datos) VALUES (?, 'claves', ?, ?) "
                    "ON CONFLICT(negocio_id, servicio) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
                    (negocio_id, datetime.now().isoformat(timespec="seconds"), json.dumps(datos)))
    return hechos


def propia(var: str, negocio_id: int | None = None) -> bool:
    nid = negocio_id if negocio_id is not None else actual()
    return bool(nid and del_negocio(nid).get(var))


def clave(var: str) -> str:
    """La clave de este negocio o, si se comparten, la de la instalación."""
    nid = actual()
    if nid:
        propia_ = del_negocio(nid).get(var, "")
        if propia_:
            return propia_
        if not compartidas():
            return ""
    return os.getenv(var, "").strip()


def comprobar(var: str, valor: str) -> str:
    """Prueba una clave antes de guardarla. Devuelve el error, o vacío si vale (o si no se ha podido comprobar)."""
    import httpx
    try:
        if var == "ANTHROPIC_API_KEY":
            r = httpx.get("https://api.anthropic.com/v1/models", params={"limit": 1}, timeout=15,
                          headers={"x-api-key": valor, "anthropic-version": "2023-06-01"})
        elif var == "APIFY_TOKEN":
            r = httpx.get("https://api.apify.com/v2/users/me", headers={"Authorization": f"Bearer {valor}"}, timeout=15)
        elif var == "YOUTUBE_API_KEY":
            r = httpx.get("https://www.googleapis.com/youtube/v3/videos", timeout=15,
                          params={"part": "id", "id": "dQw4w9WgXcQ", "key": valor})
        else:
            return ""
    except httpx.HTTPError:
        return ""  # sin conexión ahora mismo: se guarda y se verá al usarla
    if r.status_code in (400, 401, 403):
        return f"{PROPIAS[var]}: no es válida (el servicio la ha rechazado)."
    return ""


def estado(negocio_id: int) -> dict[str, dict]:
    """Para Conectores: cada clave, si es suya, si usa la de la instalación o si falta."""
    suyas = del_negocio(negocio_id)
    return {var: {"etiqueta": e, "propia": bool(suyas.get(var)),
                  "instalacion": compartidas() and bool(os.getenv(var, "").strip())} for var, e in PROPIAS.items()}
