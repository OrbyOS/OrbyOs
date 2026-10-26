"""Página de la generación de vídeos. Oculta: da 404 mientras el interruptor (generacion.activa) esté apagado."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from .. import auth
from . import generacion

router = APIRouter()


@router.get("/negocios/{negocio_id}/generacion", response_class=HTMLResponse)
def pagina_generacion(request: Request, negocio_id: int):
    if not generacion.activa():
        raise HTTPException(404)
    auth.negocio_propio(auth.requiere_usuario(request), negocio_id)
    return "<p>Generación de vídeos: en construcción.</p>"
