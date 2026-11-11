"""Instagram por su API oficial: los avisos de Meta (/ig/<token>), el conector y las palabras clave. Y los enlaces
cortos (/r/<nombre>) que cuentan cuántos abren cada regalo."""
import secrets
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

from .. import auth, cortos
from ..connectors.instagram import ErrorInstagram
from . import instagram_dm, regalos

router = APIRouter()


def _propio(request: Request, negocio_id: int) -> dict:
    return auth.negocio_propio(auth.requiere_usuario(request), negocio_id)


def _volver(negocio_id: int, pagina: str, aviso: str) -> RedirectResponse:
    return RedirectResponse(f"/negocios/{negocio_id}/{pagina}?aviso={quote(aviso)}#instagram", status_code=303)


@router.get("/ig/{token}")
def comprobar_aviso(request: Request, token: str):
    """Meta comprueba la dirección antes de mandar nada: devuelve el «challenge» si el «verify token» es este."""
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and instagram_dm.negocio_por_token(token) is not None and \
            secrets.compare_digest(q.get("hub.verify_token") or "", token):
        return PlainTextResponse(q.get("hub.challenge") or "")
    return PlainTextResponse("no", status_code=403)


@router.post("/ig/{token}")
async def aviso_de_instagram(request: Request, token: str, tareas: BackgroundTasks):
    """Cada comentario nuevo. Se contesta enseguida (Meta repite el aviso si tarda) y se atiende después."""
    nid = instagram_dm.negocio_por_token(token)
    if nid is None:
        return JSONResponse({"error": "no encontrado"}, status_code=404)
    pendientes = instagram_dm.recibir(nid, await request.body(), request.headers.get("x-hub-signature-256", ""))
    if pendientes is None:
        return JSONResponse({"error": "firma"}, status_code=403)
    if pendientes:
        tareas.add_task(instagram_dm.atender_todos, pendientes)
    return {"ok": True}


@router.get("/negocios/{negocio_id}/conectores/instagram")
def ver_instagram(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    return instagram_dm.estado(negocio_id)


@router.post("/negocios/{negocio_id}/conectores/instagram")
def conectar_instagram(request: Request, negocio_id: int, token: str = Form(""), secreto: str = Form(""),
                       quitar: str = Form("")):
    _propio(request, negocio_id)
    if quitar:
        instagram_dm.desconectar(negocio_id)
        return _volver(negocio_id, "conectores", "Instagram desconectado.")
    try:
        e = instagram_dm.conectar(negocio_id, token, secreto)
    except ErrorInstagram as err:
        return _volver(negocio_id, "conectores", str(err))
    falta = "" if e["secreto"] else " Falta la clave secreta de la app: sin ella no se aceptan los avisos."
    return _volver(negocio_id, "conectores", f"Instagram conectado con @{e['usuario']}.{falta}")


@router.get("/negocios/{negocio_id}/conectores/instagram/conectar")
def conectar_con_instagram(request: Request, negocio_id: int):
    """El botón «Conectar Instagram»: a la página de Instagram, que vuelve a /instagram/volver."""
    _propio(request, negocio_id)
    try:
        return RedirectResponse(instagram_dm.enlace_conectar(negocio_id), status_code=303)
    except ErrorInstagram as err:
        return _volver(negocio_id, "conectores", str(err))


@router.get("/instagram/volver")
def vuelta_de_instagram(request: Request, code: str = "", state: str = "", error_description: str = ""):
    nid_txt = state.partition(".")[0]
    if nid_txt.isdigit():
        _propio(request, int(nid_txt))  # solo quien es dueño de ese negocio
    if not code:
        destino = int(nid_txt) if nid_txt.isdigit() else None
        aviso = "No se ha conectado Instagram" + (f": {error_description}" if error_description else ".")
        return _volver(destino, "conectores", aviso) if destino else RedirectResponse("/app", status_code=303)
    try:
        nid = instagram_dm.completar_conexion(state, code)
    except ValueError:
        return RedirectResponse("/app", status_code=303)
    except ErrorInstagram as err:
        return _volver(int(nid_txt), "conectores", str(err))
    return _volver(nid, "conectores", f"Instagram conectado con @{instagram_dm.conexion(nid).get('usuario', '')}.")


@router.post("/negocios/{negocio_id}/comunidad/instagram/palabras")
def palabra_instagram(request: Request, negocio_id: int, palabra: str = Form(""), enlace: str = Form(""),
                      mensaje: str = Form(""), media_id: str = Form(""), publica: str | None = Form(None),
                      quitar: str = Form("")):
    _propio(request, negocio_id)
    if quitar:
        instagram_dm.quitar_palabra(negocio_id, palabra, media_id)
        return _volver(negocio_id, "comunidad", f"Palabra {palabra.upper()} quitada.")
    try:
        p = instagram_dm.poner_palabra(negocio_id, palabra, enlace, mensaje=mensaje, media_id=media_id, publica=publica)
    except ValueError as err:
        return _volver(negocio_id, "comunidad", str(err))
    return _volver(negocio_id, "comunidad", f"Palabra {p['palabra']} lista.")


@router.post("/negocios/{negocio_id}/comunidad/instagram/ajustes")
def ajustes_instagram(request: Request, negocio_id: int, activa: str = Form(""), tope: int = Form(0),
                      publica: str | None = Form(None)):
    _propio(request, negocio_id)
    instagram_dm.ajustar(negocio_id, activa=bool(activa), tope=tope or None, publica=publica)
    return _volver(negocio_id, "comunidad", "Guardado.")


@router.get("/r/{nombre}")
def enlace_corto(request: Request, nombre: str):
    destino = cortos.destino(nombre)
    if not destino:
        return PlainTextResponse("Este enlace no existe.", status_code=404)
    cortos.contar(nombre, request.headers.get("user-agent", ""))
    return RedirectResponse(destino, status_code=302)


# ---------------------------------------------------------------- regalos: palabra + enlace corto + destino, con sus números

def _a_regalos(negocio_id: int, aviso: str) -> RedirectResponse:
    return RedirectResponse(f"/negocios/{negocio_id}/comunidad?aviso={quote(aviso)}#regalos", status_code=303)


@router.get("/negocios/{negocio_id}/regalos")
def ver_regalos(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    return regalos.lista(negocio_id)


@router.post("/negocios/{negocio_id}/regalos")
def guardar_regalo(request: Request, negocio_id: int, palabra: str = Form(""), destino: str = Form(""),
                   guia_id: int = Form(0), regalo_id: int = Form(0), activa: str = Form(""), exacta: str = Form(""),
                   mensaje: str = Form(""), pregunta: str = Form(""), media_id: str = Form(""),
                   dominio: str | None = Form(None), apertura: str | None = Form(None)):
    """Crea un regalo o, con regalo_id, lo cambia. «activa» y «exacta» son casillas (vacío = no)."""
    _propio(request, negocio_id)
    try:
        r = regalos.guardar(negocio_id, palabra=palabra, destino=destino, guia_id=guia_id or None,
                            regalo_id=regalo_id or None, activa=bool(activa), exacta=bool(exacta), mensaje=mensaje,
                            pregunta=pregunta, media_id=media_id, dominio=dominio, apertura=apertura)
    except ValueError as err:
        return _a_regalos(negocio_id, str(err))
    return _a_regalos(negocio_id, f"Regalo {r['palabra']} {'listo' if r['activa'] else 'guardado en pausa'}: {r['enlace_corto']}")


@router.post("/negocios/{negocio_id}/regalos/{regalo_id}/quitar")
def quitar_regalo(request: Request, negocio_id: int, regalo_id: int):
    _propio(request, negocio_id)
    return _a_regalos(negocio_id, "Regalo quitado." if regalos.quitar(negocio_id, regalo_id) else "Ese regalo no existe.")
