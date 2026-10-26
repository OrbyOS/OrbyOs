"""La app web: cuentas, la ficha de cada negocio, el equipo de agentes de contenido (Hoy, Graba hoy, Guiones,
Producción, Publicación, Comunidad, Resultados, Investigación, Aprobaciones y Kit de marca) y la administración."""
import os
import re
import shutil
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth, claves, config, db, llm, metodo, onboarding, vega
from .agentes import aprobaciones
from .modules import edicion
from .modules import ficha as modulo_ficha


@asynccontextmanager
async def _vida(_app):
    # Telegram, avisos, resumen de la mañana y piloto automático: una vuelta cada pocos segundos mientras la app está abierta.
    from .agentes import jefa, produccion
    produccion.reanudar()  # las tomas que se cortaron al cerrar la app siguen solas
    jefa.arrancar_bucle()
    yield


AQUI = config.Path(__file__).parent
app = FastAPI(title=config.APP_NOMBRE, lifespan=_vida)
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
plantillas = Jinja2Templates(directory=AQUI / "templates")
db.iniciar()

# Lo que se pide del negocio: quién es, a quién vende, su oferta, sus redes, su competencia y su tono.
SECCIONES_FICHA = ("negocio", "cliente", "oferta", "contenido", "competencia", "marca")
FICHA = [s for s in onboarding.SECCIONES if s["clave"] in SECCIONES_FICHA]
CAMPOS_FICHA = [c[0] for s in FICHA for c in s["campos"] if c[0] not in onboarding.PRIVADOS]


# ---------------------------------------------------------------- filtros de las plantillas

def _fecha(iso: str | None) -> str:
    """2026-10-16T18:38:20 → 16/10/2026, 18:38"""
    if not iso:
        return ""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}, {iso[11:16]}"


def _hace(iso: str | None) -> str:
    """Cuánto hace de una fecha, corto: «5 h», «2 días»."""
    from datetime import datetime
    try:
        horas = max(0, int((datetime.now() - datetime.fromisoformat((iso or "")[:19])).total_seconds() // 3600))
    except ValueError:
        return ""
    return f"{horas} h" if horas < 48 else f"{horas // 24} días"


def _cifra(n) -> str:
    """12345 → 12,3 mil · 1800000 → 1,8 M"""
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M".replace(".", ",").replace(",0 ", " ")
    if n >= 1_000:
        return f"{n / 1_000:.1f} mil".replace(".", ",").replace(",0 ", " ")
    return f"{int(n)}"


def _dolares(x) -> str:
    return f"{float(x or 0):.2f}".replace(".", ",") + " $"


def _host(url: str | None) -> str:
    return (url or "").split("//")[-1].split("/")[0].replace("www.", "")


TECNICO = (".env", "token", "clave de", "api", "apify", "claude", "conectar", "conectad", "anthropic", "workspace",
           "error inesperado", "ffmpeg", "youtube respondió", "meta respondió", "saldo")


def _avisos_para(avisos: list[str] | None, usuario: dict | None) -> list[str]:
    """Quien no administra no ve los detalles técnicos de las cuentas del proyecto."""
    if usuario and usuario.get("es_admin"):
        return list(avisos or [])
    salida = []
    for a in avisos or []:
        if any(t in a.lower() for t in TECNICO):
            a = "Una de las fuentes de datos no ha respondido esta vez. Prueba más tarde."
        if a not in salida:
            salida.append(a)
    return salida


def _equipo_vista() -> dict:
    """Qué agente lleva cada página: su muñequito sale en la cabecera y su color tiñe la página."""
    from .agentes import AGENTES
    from .agentes.sala import COLORES
    vistas = {"hoy": "jefa", "aprobaciones": "jefa", "estrategia": "estratega", "guiones": "guionista",
              "produccion": "editor", "publicacion": "publicador", "comunidad": "comunidad",
              "resultados": "analista", "investigacion": "analista"}
    return {v: {"clave": k, "nombre": AGENTES[k]["nombre"], "rol": AGENTES[k]["rol"], "color": COLORES[k]}
            for v, k in vistas.items()}


def _quedan(iso: str | None) -> int | None:
    """Minutos que quedan hasta una fecha (negativo si ya pasó); None si no hay fecha."""
    from datetime import datetime
    try:
        return int((datetime.fromisoformat((iso or "")[:19]) - datetime.now()).total_seconds() // 60)
    except ValueError:
        return None


def _leer_estructura(texto: str | None) -> dict:
    """La estructura de Escri (idea, bloques y cierre) para pintarla; vacía si no se puede leer."""
    from .agentes import validador
    try:
        return validador.leer_estructura(texto or "")
    except Exception:  # noqa: BLE001 — es solo para enseñar: si no se lee, sale en párrafos
        return {"idea": "", "bloques": [], "cierre": ""}


def _lupi_de(negocio_id: int) -> dict:
    """Lo nuevo de Lupi para Investigación: la mesa de noticias, la nota del perfil y las fórmulas de gancho que funcionan."""
    from .agentes import analista, analista_web, noticias
    salida = {"noticias": [], "perfil": {}, "formulas": {}, "TIPOS_CUENTA": analista.TIPOS_CUENTA,
              "VISUALES": noticias.VISUALES, "ESTADOS_DATO": noticias.ESTADOS_DATO}
    for clave, fn in (("noticias", noticias.noticias), ("perfil", analista_web.perfil_guardado),
                      ("formulas", analista.formulas_que_funcionan)):
        try:
            salida[clave] = fn(negocio_id) or salida[clave]
        except Exception:  # noqa: BLE001 — es solo para enseñar: si una parte falla, el resto de la página sigue
            pass
    return salida


def _revision_kit(negocio: dict) -> list[dict]:
    """Lo que le falta al Kit (Orby), de lo que más pesa a lo que menos: texto, quién lo necesita y dónde se completa."""
    from .agentes import jefa
    try:
        return jefa.revision(negocio)
    except Exception:  # noqa: BLE001 — es solo para enseñar
        return []


def _nombre_formula(formula_id) -> str:
    """El nombre de una fórmula de gancho del catálogo de Escri («El error que todos cometen»); vacío si no hay."""
    from .agentes import ganchos
    try:
        return ganchos.nombre(int(formula_id)) if formula_id not in (None, "") else ""
    except (ValueError, TypeError):
        return ""


def _historias_de_hoy(negocio_id: int) -> dict:
    """Las historias del día que Plani mandó con el último plan (en su aprobación), si las hay."""
    from .agentes import aprobaciones
    for a in aprobaciones.de_negocio(negocio_id, limite=20):
        if a["tipo"] == "brief" and (a["datos"] or {}).get("historias"):
            return a["datos"]["historias"]
    return {}


def _modo_de(negocio_id: int) -> str:
    """Cómo graba el negocio (Kit): «guion» o «estructura» (lo que Escri le escribe)."""
    from .agentes import kit as kit_marca
    try:
        return "guion" if kit_marca.leer(negocio_id).get("modo_grabacion") == "guion" else "estructura"
    except Exception:  # noqa: BLE001
        return "estructura"


def _reels_prueba_de(negocio_id: int) -> dict:
    """Los reels de prueba del Kit (Publi): activa, al_dia, desde, hasta y comprobado."""
    from .agentes import kit as kit_marca
    try:
        return kit_marca.leer(negocio_id).get("reels_prueba") or {}
    except Exception:  # noqa: BLE001
        return {}


def _ruta_existe(ruta: str, metodo: str = "POST") -> bool:
    """Si la app tiene esta ruta (para pintar un formulario solo cuando ya hay quien lo reciba)."""
    return any(getattr(r, "path", None) == ruta and metodo in (getattr(r, "methods", None) or ()) for r in app.routes)


def _opciones_kit() -> dict:
    """Las opciones de «Cómo trabajas» (Kit), con sus nombres: tacos, emojis, cámara, modos, llamadas a la acción y formatos."""
    from .agentes import kit as k
    return {"tacos": k.TACOS, "emojis": k.EMOJIS, "camaras": k.CAMARAS, "modos": k.MODOS_GRABACION, "ctas": k.CTAS,
            "formatos": k.FORMATOS}


def _planos_de(toma: dict) -> list[dict]:
    """«Así queda cada plano» de un reel montado con el motor (estilo «De editor»); vacío si no."""
    from .editor import flujo, plan_motor
    try:
        return plan_motor.para_ver(toma.get("datos") or {}, flujo.palabras(toma["id"]))
    except Exception:  # noqa: BLE001 — es solo para enseñar: si algo no cuadra, no se pinta
        return []


plantillas.env.filters.update(fecha=_fecha, hace=_hace, cifra=_cifra, dolares=_dolares, host=_host, quedan=_quedan)
plantillas.env.globals.update(
    APP=config.APP_NOMBRE, avisos_para=_avisos_para, TIPOS_CUENTA=config.TIPOS_CUENTA, ONBOARDING=FICHA,
    opciones_onb=onboarding.opciones, filas_competidores=modulo_ficha.filas_del_formulario,
    pendientes_de=aprobaciones.contar_pendientes, EQUIPO_VISTA=_equipo_vista(),
    # Los enlaces de la landing: dónde se pide la implementación (una página de citas, por ejemplo) y el repositorio.
    URL_SOLICITAR=os.getenv("RADAR_URL_SOLICITAR", "").strip() or "/registro",
    URL_GITHUB=os.getenv("RADAR_URL_GITHUB", "").strip(),
    ruta_existe=_ruta_existe, opciones_kit=_opciones_kit,
    motor_reels_activo=config.motor_reels_activo, planos_de=_planos_de, leer_estructura=_leer_estructura, lupi_de=_lupi_de, revision_kit=_revision_kit, nombre_formula=_nombre_formula, modo_de=_modo_de, reels_prueba_de=_reels_prueba_de, historias_de_hoy=_historias_de_hoy,
    CLASES_PIEZA={"prueba": "Prueba", "ensenar": "Enseñar", "opinion": "Opinión", "historia": "Historia", "oferta": "Oferta"},
    PEGATINAS={"encuesta": "Encuesta", "preguntas": "Caja de preguntas", "quiz": "Quiz", "deslizador": "Deslizador",
               "enlace": "Enlace", "cuenta_atras": "Cuenta atrás", "anade_el_tuyo": "Añade el tuyo", "ninguna": ""},
)


_RUTA_NEGOCIO = re.compile(r"^/negocios/(\d+)(/|$)")


@app.middleware("http")
async def _negocio_de_la_peticion(request: Request, siguiente):
    """Lo que se hace en las páginas de un negocio usa SUS claves (las comprueba cada ruta: solo su dueño entra)."""
    m = _RUTA_NEGOCIO.match(request.url.path)
    marca = claves.usar(int(m.group(1)) if m else None)
    try:
        return await siguiente(request)
    finally:
        claves.NEGOCIO.reset(marca)


@app.middleware("http")
async def _direccion_publica(request: Request, siguiente):
    """La primera vez que alguien entra por https, esa dirección queda como la pública de la app: así las guías de
    las palabras clave se pueden abrir desde un DM sin configurar nada."""
    if not config.URL_PUBLICA and request.url.scheme == "https" and request.url.hostname not in ("localhost", "127.0.0.1"):
        from .agentes import instalacion
        instalacion.guardar({"RADAR_URL_PUBLICA": f"https://{request.url.netloc}"})
    return await siguiente(request)


# ---------------------------------------------------------------- errores de permisos

@app.exception_handler(auth.NoAutenticado)
def _sin_sesion(request: Request, _exc):
    return RedirectResponse(f"/entrar?siguiente={quote(request.url.path)}", status_code=303)


@app.exception_handler(auth.SinPermiso)
def _sin_permiso(request: Request, _exc):
    return _pagina(request, "error.html", status_code=404, titulo="No encontrado",
                   mensaje="Esta página no existe o no es de tu cuenta.")


def _pagina(request: Request, archivo: str, /, *, status_code: int = 200, **datos) -> HTMLResponse:
    usuario = None if datos.get("compartido") else (datos.get("usuario") or auth.usuario_actual(request))
    datos.update(usuario=usuario, ruta=request.url.path)
    if usuario and not datos.get("negocio"):
        # Cuenta, Administración…: el menú del negocio sigue a la izquierda.
        propio = db.negocios(usuario["id"])
        if propio:
            datos.setdefault("negocio", propio[0])
            datos.setdefault("base_n", f"/negocios/{propio[0]['id']}")
    return plantillas.TemplateResponse(request, archivo, datos, status_code=status_code)


def _espacio(request: Request, negocio_id: int, _a: int | None = None) -> tuple[dict, dict, None]:
    u = auth.requiere_usuario(request)
    return u, auth.negocio_propio(u, negocio_id), None


def _datos_espacio(u: dict | None, neg: dict, _inf=None, **_) -> dict:
    """Lo que necesitan todas las páginas de un negocio."""
    return {"usuario": u, "negocio": neg, "base_n": f"/negocios/{neg['id']}", "cupo": auth.cupo(u) if u else None}


# El estilo de edición (logo) y el equipo de agentes viven en sus propios módulos de rutas.
from .agentes import estado as estado_agentes  # noqa: E402
from .agentes import rutas as rutas_agentes  # noqa: E402
from .agentes import rutas_generacion  # noqa: E402
from .editor import rutas as rutas_editor  # noqa: E402

rutas_editor.configurar(_pagina)
app.include_router(rutas_editor.router)
rutas_agentes.configurar(_pagina, _espacio, _datos_espacio)
app.include_router(rutas_agentes.router)
app.include_router(rutas_generacion.router)  # oculta: 404 sin RADAR_GENERACION=1
estado_agentes.interrumpidos()


# ---------------------------------------------------------------- cuentas

@app.get("/")
def inicio(request: Request):
    """Con sesión, a la app. Sin sesión, la landing (en una instalación nueva, primero la cuenta de administración)."""
    if auth.usuario_actual(request):
        return RedirectResponse("/app", status_code=303)
    if not db.contar_usuarios():
        return RedirectResponse("/entrar", status_code=303)
    return _pagina(request, "landing.html")


def _siguiente(valor: str | None) -> str:
    return valor if valor and valor.startswith("/") and not valor.startswith("//") else "/app"


@app.get("/entrar", response_class=HTMLResponse)
def entrar_form(request: Request, siguiente: str = "/app"):
    if not db.contar_usuarios():
        return RedirectResponse("/registro", status_code=303)  # instalación nueva: primero, la cuenta de administración
    return _pagina(request, "entrar.html", registro_abierto=config.REGISTRO_ABIERTO, siguiente=_siguiente(siguiente))


@app.post("/entrar")
def entrar(request: Request, email: str = Form(""), clave: str = Form(""), siguiente: str = Form("/app")):
    u = auth.entrar(email, clave)
    if not u:
        return _pagina(request, "entrar.html", status_code=400, error="Correo o contraseña incorrectos.",
                       email=email, siguiente=_siguiente(siguiente), registro_abierto=config.REGISTRO_ABIERTO)
    r = RedirectResponse(_siguiente(siguiente), status_code=303)
    auth.poner_cookie(r, auth.abrir_sesion(u["id"]))
    return r


def _puede_registrar(request: Request) -> bool:
    """La primera cuenta se crea sola (la de administración); después, un administrador da de alta otras o, con el
    registro abierto, cada uno se crea la suya."""
    u = auth.usuario_actual(request)
    return not db.contar_usuarios() or bool(u and u["es_admin"]) or (config.REGISTRO_ABIERTO and not u)


@app.get("/registro", response_class=HTMLResponse)
def registro_form(request: Request):
    if not _puede_registrar(request):
        return RedirectResponse("/entrar", status_code=303)
    return _pagina(request, "registro.html", primera=not db.contar_usuarios(), por_admin=bool(auth.usuario_actual(request)))


@app.post("/registro")
def registro(request: Request, email: str = Form(""), nombre: str = Form(""), clave: str = Form("")):
    if not _puede_registrar(request):
        return RedirectResponse("/entrar", status_code=303)
    primera = not db.contar_usuarios()
    u, error = auth.registrar(email, nombre, clave, "negocio")
    if not u:
        return _pagina(request, "registro.html", status_code=400, error=error, email=email, nombre=nombre, primera=primera,
                       por_admin=bool(auth.usuario_actual(request)))
    if not primera and auth.usuario_actual(request):  # un administrador ha dado de alta a otra persona: sigue con la suya
        aviso = "Cuenta creada: " + u["email"] + "."
        return RedirectResponse(f"/admin?aviso={quote(aviso)}#usuarios", status_code=303)
    r = RedirectResponse("/app", status_code=303)
    auth.poner_cookie(r, auth.abrir_sesion(u["id"]))
    return r


@app.post("/salir")
def salir(request: Request):
    token = request.cookies.get(auth.COOKIE)
    if token:
        db.borrar_sesion(token)
    r = RedirectResponse("/entrar", status_code=303)
    r.delete_cookie(auth.COOKIE)
    return r


@app.get("/cuenta", response_class=HTMLResponse)
def cuenta(request: Request):
    u = auth.requiere_usuario(request)
    return _pagina(request, "cuenta.html", usuario=u, cupo=auth.cupo(u))


# ---------------------------------------------------------------- negocios y su ficha

@app.get("/app", response_class=HTMLResponse)
def mis_negocios(request: Request):
    u = auth.requiere_usuario(request)
    # Una cuenta, un negocio: se entra directo a él (o a crearlo, la primera vez).
    lista = db.negocios(u["id"])
    aviso = request.query_params.get("aviso")
    sufijo = f"?aviso={quote(aviso)}" if aviso else ""
    if not lista:
        return RedirectResponse(f"/negocios/nuevo{sufijo}", status_code=303)
    return RedirectResponse(f"/negocios/{lista[0]['id']}/hoy{sufijo}", status_code=303)


async def _ficha_del_formulario(request: Request) -> dict:
    form = await request.form()
    datos = {c: (form.get(c) or "").strip() for c in CAMPOS_FICHA}
    if not datos.get("nombre") or not datos.get("que_vende"):
        raise HTTPException(400, "Faltan el nombre o qué vende el negocio.")
    filas = onboarding.competidores_del_formulario(form)
    if filas is not None:
        datos["competidores"] = filas
    for campo, opciones in (("ticket", metodo.TICKETS), ("tipo_negocio", metodo.TIPOS_NEGOCIO)):
        if campo in datos and datos[campo] not in opciones:
            datos[campo] = ""
    return datos


def _puede_crear(u: dict) -> bool:
    """De momento, cada cuenta tiene un solo negocio."""
    return db.contar_negocios(u["id"]) == 0


@app.get("/negocios/nuevo", response_class=HTMLResponse)
def nuevo_negocio(request: Request):
    u = auth.requiere_usuario(request)
    if not _puede_crear(u):
        return RedirectResponse("/app", status_code=303)  # ya tiene su negocio
    # Todo empieza por el onboarding: el negocio se crea con su nombre y se va directo a las 8 preguntas.
    negocio_id = db.crear_negocio({"nombre": (u.get("nombre") or "Mi negocio").strip()[:120]}, u["id"])
    aviso = "Bienvenido. Empieza por aquí: 8 preguntas para preparar tu llamada de onboarding."
    return RedirectResponse(f"/negocios/{negocio_id}/onboarding?aviso={quote(aviso)}#preguntas", status_code=303)


@app.post("/negocios")
async def crear(request: Request):
    u = auth.requiere_usuario(request)
    if not _puede_crear(u):
        return RedirectResponse("/negocios/nuevo", status_code=303)
    negocio_id = db.crear_negocio(await _ficha_del_formulario(request), u["id"])
    return RedirectResponse(f"/negocios/{negocio_id}/kit?aviso={quote('Negocio creado. Empieza por tu Kit de marca.')}",
                            status_code=303)


@app.get("/negocios/{negocio_id}")
def negocio_inicio(negocio_id: int):
    return RedirectResponse(f"/negocios/{negocio_id}/hoy", status_code=303)


@app.get("/negocios/{negocio_id}/ficha")
def ver_ficha(request: Request, negocio_id: int):
    """La ficha ya no tiene pantalla: la rellena el onboarding (datos básicos y las llamadas)."""
    _espacio(request, negocio_id)
    return RedirectResponse(f"/negocios/{negocio_id}/onboarding", status_code=303)


@app.post("/negocios/{negocio_id}/ficha")
async def guardar_ficha(request: Request, negocio_id: int):
    u = auth.requiere_usuario(request)
    neg = auth.negocio_propio(u, negocio_id)
    db.actualizar_negocio(negocio_id, {**neg["ficha"], **await _ficha_del_formulario(request)})
    return RedirectResponse(f"/negocios/{negocio_id}/onboarding?guardado=1", status_code=303)


@app.post("/negocios/{negocio_id}/eliminar")
def eliminar(request: Request, negocio_id: int, confirmar: str = Form("")):
    u = auth.requiere_usuario(request)
    neg = auth.negocio_propio(u, negocio_id)
    volver = f"/negocios/{negocio_id}/conectores"
    if confirmar.strip().lower() != neg["nombre"].strip().lower():
        return RedirectResponse(f"{volver}?aviso={quote('Escribe el nombre exacto para confirmar que quieres eliminarlo.')}#eliminar",
                                status_code=303)
    if db.trabajo_en_marcha(negocio_id):
        return RedirectResponse(f"{volver}?aviso={quote('Hay una edición en marcha: espera a que termine para eliminarlo.')}#eliminar",
                                status_code=303)
    for edicion_id in db.eliminar_negocio(negocio_id):
        shutil.rmtree(config.EDICIONES_DIR / str(edicion_id), ignore_errors=True)
    aviso = "«" + neg["nombre"] + "» eliminado."
    return RedirectResponse(f"/app?aviso={quote(aviso)}", status_code=303)


# ---------------------------------------------------------------- hablar con Vega

@app.get("/negocios/{negocio_id}/vega")
def vega_conversacion(request: Request, negocio_id: int):
    u = auth.requiere_usuario(request)
    auth.negocio_propio(u, negocio_id)
    return JSONResponse({"mensajes": [{"rol": m["rol"], "texto": m["texto"]} for m in db.mensajes_vega(negocio_id)],
                         "sugerencias": vega.SUGERENCIAS, "disponible": llm.disponible()})


@app.post("/negocios/{negocio_id}/vega")
def vega_preguntar(request: Request, negocio_id: int, texto: str = Form("")):
    u = auth.requiere_usuario(request)
    neg = auth.negocio_propio(u, negocio_id)
    texto = texto.strip()[:2000]
    if not texto:
        return PlainTextResponse("Escribe tu pregunta.", status_code=400)
    if not llm.disponible():
        return PlainTextResponse("Vega necesita Claude para hablar: conéctalo en Administración → Claves y ajustes.",
                                 status_code=503)
    if not u["es_admin"] and db.mensajes_vega_hoy(u["id"]) >= vega.MAX_DIA:
        return PlainTextResponse("Has llegado al límite de preguntas de hoy. Mañana sigo contigo.", status_code=429)
    return StreamingResponse(vega.responder(neg, None, u, texto), media_type="text/plain; charset=utf-8",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/negocios/{negocio_id}/vega/nueva")
def vega_nueva(request: Request, negocio_id: int):
    u = auth.requiere_usuario(request)
    auth.negocio_propio(u, negocio_id)
    db.borrar_mensajes_vega(negocio_id)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------- los vídeos editados

def _edicion_propia(request: Request, edicion_id: int) -> dict:
    u = auth.requiere_usuario(request)
    ed = db.edicion(edicion_id)
    if not ed:
        raise auth.SinPermiso()
    auth.negocio_propio(u, ed["negocio_id"])
    return ed


@app.get("/ediciones/{edicion_id}/estado")
def estado_edicion(request: Request, edicion_id: int):
    ed = _edicion_propia(request, edicion_id)
    return JSONResponse({"estado": ed["estado"], "paso": ed["paso"]})


@app.get("/ediciones/{edicion_id}/video")
def video_editado(request: Request, edicion_id: int, descargar: int = 0):
    ed = _edicion_propia(request, edicion_id)
    ruta = edicion.carpeta(edicion_id) / "final.mp4"
    if not ruta.exists():
        raise auth.SinPermiso()
    nombre = re.sub(r"[^\w-]+", "_", ed["titulo"] or f"video_{edicion_id}").strip("_") or f"video_{edicion_id}"
    return FileResponse(ruta, media_type="video/mp4", filename=f"{nombre}_9x16.mp4" if descargar else None)


@app.get("/ediciones/{edicion_id}/portada")
def portada_edicion(request: Request, edicion_id: int):
    _edicion_propia(request, edicion_id)
    ruta = edicion.carpeta(edicion_id) / "portada.jpg"
    if not ruta.exists():
        raise auth.SinPermiso()
    return FileResponse(ruta, media_type="image/jpeg")


# ---------------------------------------------------------------- administración

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    u = auth.requiere_admin(request)
    return _pagina(request, "admin.html", usuario=u, usuarios=db.usuarios_con_uso(), gastos=db.gastos_recientes(),
                   total=db.gasto_total(), conectores=config.conectores(), planes=config.PLANES, todos=db.negocios(),
                   solicitudes=db.solicitudes(), ESTADOS_SOLICITUD=ESTADOS_SOLICITUD)


ESTADOS_SOLICITUD = {"nueva": "Nueva", "contactada": "Contactada", "agendada": "Llamada agendada",
                     "cliente": "Cliente", "descartada": "Descartada"}


@app.post("/solicitar")
async def solicitar(request: Request):
    """«Solicitar implementación» de la landing: pública, con un campo trampa y un máximo por IP y hora."""
    from . import solicitudes
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    resultado = solicitudes.recibir(await request.form(), ip)
    return RedirectResponse(f"/?solicitud={resultado}#solicitar", status_code=303)


@app.post("/admin/solicitudes/{solicitud_id}")
def admin_solicitud(request: Request, solicitud_id: int, estado: str = Form(""), notas: str | None = Form(None)):
    auth.requiere_admin(request)
    cambios = {"estado": estado} if estado in ESTADOS_SOLICITUD else {}
    if notas is not None:
        cambios["notas"] = notas.strip()[:3000]
    db.actualizar_solicitud(solicitud_id, **cambios)
    return RedirectResponse("/admin#solicitudes", status_code=303)


@app.post("/admin/usuarios/{usuario_id}")
def admin_usuario(request: Request, usuario_id: int, plan: str = Form(...), es_admin: str = Form(""),
                  activo: str = Form("")):
    yo = auth.requiere_admin(request)
    if plan not in config.PLANES:
        raise HTTPException(400, "Ese plan no existe.")
    cambios = {"plan": plan, "activo": int(activo == "1" or usuario_id == yo["id"]),
               "es_admin": int(es_admin == "1" or usuario_id == yo["id"])}  # uno no se quita a sí mismo el acceso
    db.actualizar_usuario(usuario_id, **cambios)
    return RedirectResponse("/admin#usuarios", status_code=303)
