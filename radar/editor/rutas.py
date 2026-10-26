"""El logo del estilo de edición (se pone en el Kit de marca). El motor de edición lo usa Producción."""
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from .. import auth, db
from . import flujo

router = APIRouter()
_pagina = None  # main.py la pone al arrancar (evita importar main desde aquí)

EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".webp"}


def configurar(pagina):
    global _pagina
    _pagina = pagina


async def _guardar_subida(archivo: UploadFile, destino: Path, limite_mb: int) -> bool:
    total, limite = 0, limite_mb * 1024 * 1024
    with open(destino, "wb") as f:
        while trozo := await archivo.read(1 << 20):
            total += len(trozo)
            if total > limite:
                return False
            f.write(trozo)
    return True


@router.post("/negocios/{negocio_id}/logo")
async def subir_logo(request: Request, negocio_id: int, logo: UploadFile = File(...), volver: str = Form("")):
    u = auth.requiere_usuario(request)
    auth.negocio_propio(u, negocio_id)
    ext = Path(logo.filename or "").suffix.lower()
    destino = volver if volver.startswith("/") and not volver.startswith("//") else f"/negocios/{negocio_id}/kit#estilo"
    base, _, ancla = destino.partition("#")
    sep = "&" if "?" in base else "?"

    def ir(aviso: str) -> RedirectResponse:
        return RedirectResponse(f"{base}{sep}aviso={quote(aviso)}{'#' + ancla if ancla else ''}", status_code=303)

    if ext not in EXT_IMAGEN:
        return ir("El logo tiene que ser una imagen (mejor PNG con fondo transparente).")
    for viejo in flujo.marca_dir(negocio_id).glob("logo.*"):
        viejo.unlink()
    if not await _guardar_subida(logo, flujo.marca_dir(negocio_id) / f"logo{ext}", 10):
        return ir("El logo pesa demasiado.")
    m = db.marca(negocio_id)
    m["logo"] = f"logo{ext}"
    db.guardar_marca(negocio_id, m)
    return ir("Logo guardado.")


@router.get("/negocios/{negocio_id}/logo")
def ver_logo(request: Request, negocio_id: int):
    u = auth.requiere_usuario(request)
    auth.negocio_propio(u, negocio_id)
    ruta = flujo.logo(negocio_id)
    if not ruta:
        raise auth.SinPermiso()
    return FileResponse(ruta)
