"""El plan gratis y sus «puertas falsas».

Gratis: el negocio, su ficha y su Kit, las ideas y el plan de Plani, los guiones y estructuras de Escri y el resumen
de Orby. Todo con su propia clave de Claude (en un servidor abierto cada cuenta pone la suya): a la instalación no le
cuesta nada. Lo que tiene un coste (leer Instagram con Apify, editar en el servidor, publicar, los mensajes
automáticos, el piloto automático) se ve en la app, pero al usarlo lleva a una página que cuenta qué hace y apunta el
interés de quien lo pide: así se mide qué quiere la gente antes de construirlo o venderlo (y sirve para el correo).

Las cuentas con otro plan (o de administración) no ven ninguna puerta: todo funciona como siempre.
"""
import re
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import auth, db

GRATIS = "gratis"
LISTA_CORREO = "orby"  # la newsletter de quienes piden avisos desde una puerta falsa

# clave: (nombre, qué hace, rutas POST que la usan)
FUNCIONES = {
    "investigacion": ("Investigación de tu nicho",
                      "Lupi lee cada día los reels de tu competencia, encuentra los que despegan y los desmonta.",
                      [r"/investigacion/escanear$", r"/investigacion/sugerir-cuentas$", r"/investigacion/perfil$",
                       r"/investigacion/posts/\d+/desmontar$"]),
    "edicion": ("Edición de tus vídeos",
                "Monti edita tus brutos: quita silencios y fallos, reencuadra a vertical, subtitula y monta.",
                [r"/produccion/subir$", r"/produccion/\d+/(guion|cambios|reintentar)$"]),
    "publicacion": ("Publicación automática",
                    "Publi programa cada vídeo en Instagram, TikTok y YouTube con su texto y su enlace.",
                    [r"/publicacion/(zernio|plan)$", r"/publicacion/\d+/programar$"]),
    "comunidad": ("Respuestas automáticas",
                  "Chati contesta la palabra clave de tus reels y lleva tus mensajes directos.",
                  [r"/comunidad/(manychat|automatizaciones|leer)$", r"/regalos$", r"/conectores/instagram(/conectar)?$"]),
    "piloto": ("Piloto automático",
               "Tu equipo trabaja solo cada día: investiga, planifica y te deja lo que hay que grabar.",
               [r"/hoy/piloto$"]),
}
_RUTA = re.compile(r"^/negocios/(\d+)(/.*)$")


def es_gratis(u: dict | None) -> bool:
    return bool(u) and not u.get("es_admin") and (u.get("plan") or "") == GRATIS


def funcion_de(metodo: str, ruta: str) -> tuple[int, str] | None:
    """(negocio, función de pago) si esa petición usa una función que el plan gratis no tiene."""
    m = _RUTA.match(ruta)
    if metodo not in ("POST", "GET") or not m:
        return None
    resto = m.group(2)
    for clave, (_, _, patrones) in FUNCIONES.items():
        if any(re.search(p, resto) for p in patrones):
            if metodo == "GET" and not resto.endswith("/conectar"):
                return None  # ver una página no gasta: solo el botón que lanza el trabajo
            return int(m.group(1)), clave
    return None


async def puerta(request: Request, siguiente):
    """Middleware: en el plan gratis, lo que tiene coste lleva a su puerta falsa (y queda apuntada la visita)."""
    hallado = funcion_de(request.method, request.url.path)
    if hallado:
        u = auth.usuario_actual(request)
        if es_gratis(u):
            nid, clave = hallado
            apuntar(u["id"], nid, clave, "intento")
            if _quiere_json(request):  # la app enseña su aviso emergente sin cambiar de página
                return JSONResponse(aviso(clave), status_code=402)
            return RedirectResponse(f"/negocios/{nid}/mejorar?funcion={clave}", status_code=303)
    return await siguiente(request)


def _quiere_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "") or request.headers.get("x-orby-puerta") == "1"


def aviso(funcion: str) -> dict:
    """Lo que dice el aviso emergente de una función premium."""
    nombre, que_hace, _ = FUNCIONES.get(funcion, ("Esta función", "", []))
    return {"puerta": funcion, "nombre": nombre, "que_hace": que_hace, "plan": "premium",
            "texto": f"{nombre} es del plan premium. Todavía no lo hemos abierto: si te interesa, deja tu correo y "
                     "te avisamos el primero."}


def apuntar(usuario_id: int, negocio_id: int, funcion: str, tipo: str):
    with db.conexion() as con:
        con.execute("INSERT INTO interes (usuario_id, negocio_id, funcion, tipo, creado) VALUES (?, ?, ?, ?, ?)",
                    (usuario_id, negocio_id, funcion, tipo, datetime.now().isoformat(timespec="seconds")))


def resumen_interes(dias: int = 30) -> list[dict]:
    """Para Administración y las métricas: por función, intentos, «avísame» y personas distintas."""
    from datetime import timedelta
    desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    with db.conexion() as con:
        filas = con.execute("SELECT funcion, SUM(tipo = 'intento') AS intentos, SUM(tipo = 'avisame') AS avisame, "
                            "COUNT(DISTINCT usuario_id) AS personas FROM interes WHERE creado >= ? GROUP BY funcion "
                            "ORDER BY avisame DESC, intentos DESC", (desde,)).fetchall()
    return [{"funcion": f["funcion"], "nombre": FUNCIONES.get(f["funcion"], (f["funcion"],))[0],
             "intentos": f["intentos"] or 0, "avisame": f["avisame"] or 0, "personas": f["personas"]} for f in filas]


router = APIRouter()
_pagina = None  # la pone main.configurar (para pintar con la plantilla de la app)


def configurar(pagina):
    global _pagina
    _pagina = pagina


@router.get("/negocios/{negocio_id}/mejorar")
def mejorar(request: Request, negocio_id: int, funcion: str = ""):
    """La puerta falsa: qué hace la función y un botón para que le avisen (o pedir la implementación)."""
    u = auth.requiere_usuario(request)
    auth.negocio_propio(u, negocio_id)
    nombre, que_hace, _ = FUNCIONES.get(funcion, ("Esta función", "Está en la versión completa de Orby.", []))
    apuntar(u["id"], negocio_id, funcion or "-", "vista")
    datos = dict(funcion=funcion, nombre_funcion=nombre, que_hace=que_hace, FUNCIONES=FUNCIONES)
    try:
        return _pagina(request, "mejorar.html", vista="mejorar", **datos)
    except Exception:  # noqa: BLE001 — hasta que exista su plantilla, la página de aviso de siempre
        return _pagina(request, "error.html", titulo=nombre, mensaje=f"{que_hace} Está en la versión completa de Orby.")


@router.post("/negocios/{negocio_id}/mejorar")
def avisame(request: Request, negocio_id: int, funcion: str = Form(""), acepto: str = Form(""), email: str = Form("")):
    """«Avísame cuando esté»: apunta el interés y, con su permiso, le apunta al correo (el de su cuenta u otro que
    escriba en el aviso). Desde el aviso emergente (Accept: application/json) contesta {ok}."""
    u = auth.requiere_usuario(request)
    auth.negocio_propio(u, negocio_id)
    apuntar(u["id"], negocio_id, funcion or "-", "avisame")
    if acepto == "si":
        from . import newsletter
        newsletter.suscribir(LISTA_CORREO, {"nombre": u.get("nombre") or u["email"].split("@")[0],
                                            "email": (email or u["email"]).strip(),
                                            "acepto": "si", "origen": funcion,
                                            "texto_consentimiento": "Acepta recibir correos de Orby sobre esta función "
                                                                    "y la versión completa."}, f"usuario-{u['id']}")
    if _quiere_json(request):
        return {"ok": True}
    return RedirectResponse(f"/negocios/{negocio_id}/mejorar?funcion={funcion}&apuntado=1", status_code=303)
