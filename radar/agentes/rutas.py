"""Páginas del Kit de marca y de la cola de aprobaciones."""
from urllib.parse import quote

import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from .. import auth, claves, config, db, jobs, llm
from ..llm import ErrorIA
from . import (AGENTES, AUTONOMIAS, analista, aprendizaje, comentarios, comunidad, estado, estratega, guionista, identidad, instalacion,
               jefa, llamadas, piloto, produccion, publicador, regalos, sala, validador)
from . import aprobaciones as ap
from . import kit as kit_marca

router = APIRouter()
_pagina = None
_datos_espacio = None
_espacio = None


def configurar(pagina, espacio, datos_espacio):
    global _pagina, _espacio, _datos_espacio
    _pagina, _espacio, _datos_espacio = pagina, espacio, datos_espacio


def _propio(request: Request, negocio_id: int) -> dict:
    u = auth.requiere_usuario(request)
    return auth.negocio_propio(u, negocio_id) | {"_usuario": u}


def _volver(negocio_id: int, pagina: str, aviso: str = "", ancla: str = "") -> RedirectResponse:
    url = f"/negocios/{negocio_id}/{pagina}" + (f"?aviso={quote(aviso)}" if aviso else "") + (f"#{ancla}" if ancla else "")
    return RedirectResponse(url, status_code=303)


# ---------------------------------------------------------------- Kit de marca

@router.get("/negocios/{negocio_id}/kit")
def ver_kit(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    from ..editor import flujo, modelo
    marca = db.marca(negocio_id)
    return _pagina(request, "kit.html", vista="kit", kit=kit_marca.leer(negocio_id), ETAPAS_KIT=kit_marca.ETAPAS,
                   marca=marca, estilo_actual=(marca.get("ajustes") or {}).get("estilo", "impacto"),
                   ESTILOS={k: v for k, v in modelo.ESTILOS.items() if k != "competencia"},
                   color_actual=marca.get("color") or modelo.AJUSTES_BASE.get("color", "#2563EB"),
                   hay_logo=bool(flujo.logo(negocio_id)), identidad=identidad.leer(negocio_id),
                   MOVIMIENTOS=modelo.MOVIMIENTOS, muestra=_muestra(negocio_id),
                   capacidad=kit_marca.capacidad(neg),
                   TIPOS_IDENTIDAD=identidad.TIPOS,
                   TIPOS_PRUEBA=kit_marca.TIPOS_PRUEBA, AGENTES=AGENTES, AUTONOMIAS=AUTONOMIAS,
                   ia=llm.disponible(), **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/kit/estilo")
def guardar_estilo_edicion(request: Request, negocio_id: int, estilo: str = Form("impacto"), color: str = Form(""),
                           preferencias: str = Form("")):
    """El estilo de edición de la casa: lo que usa Monti en cada vídeo de Producción."""
    from ..editor import modelo
    _propio(request, negocio_id)
    m = db.marca(negocio_id)
    ajustes = dict(m.get("ajustes") or {})
    if estilo in modelo.ESTILOS and estilo != "competencia":
        ajustes["estilo"] = estilo
    if modelo.HEX.fullmatch(color.strip()):
        m["color"] = color.strip()
        m["color_a_mano"] = True  # elegido aquí: la paleta de la identidad visual ya no lo cambia
        ajustes["color"] = color.strip()
    m["ajustes"] = ajustes
    m["preferencias"] = kit_marca.lineas(preferencias, 10)
    db.guardar_marca(negocio_id, m)
    return _volver(negocio_id, "kit", "Estilo de edición guardado.", "estilo")


@router.post("/negocios/{negocio_id}/kit/negocio")
async def guardar_como_trabajas(request: Request, negocio_id: int):
    """«Cómo trabajas»: límites, voz (tacos, emojis, cámara, ritmo), cómo graba, formatos, llamada a la acción,
    ofertas, hashtags, fuentes y reels de prueba. Solo cambia lo que llega en el formulario."""
    _propio(request, negocio_id)
    form = await request.form()
    cambios = kit_marca.desde_formulario(form, kit_marca.leer(negocio_id))
    if cambios:
        kit_marca.cambiar(negocio_id, **cambios)
    return _volver(negocio_id, "kit", "Guardado.", "negocio")


@router.post("/negocios/{negocio_id}/kit/identidad")
def guardar_identidad(request: Request, negocio_id: int, colores: str = Form(""), reels: str = Form(""),
                      notas: str = Form(""), palabras: str | None = Form(None), subtitulos: str | None = Form(None),
                      musica: str | None = Form(None), sonidos: str | None = Form(None), nunca: str | None = Form(None)):
    """La identidad visual: la paleta (una línea por color: «#1A2B3C principal»), los reels de referencia, notas y
    los nombres que hay que escribir bien en los subtítulos (si el formulario los manda)."""
    _propio(request, negocio_id)
    si = lambda v: None if v is None else v in ("1", "si", "on", "true")  # noqa: E731 — sin el campo, no se toca
    ident = identidad.cambiar(negocio_id, colores=colores, reels=reels, notas=notas, palabras=palabras,
                              subtitulos=subtitulos, musica=si(musica), sonidos=si(sonidos), nunca=nunca)
    return _volver(negocio_id, "kit", f"Identidad visual guardada: {len(ident['colores'])} colores y "
                                      f"{len(ident['reels'])} reels de referencia.", "identidad")


def _muestra(negocio_id: int) -> dict:
    """Cómo va el vídeo de muestra del movimiento: {estado: lista | haciendo | "", url}."""
    identidad.preparar_muestra(negocio_id)
    estado = identidad.estado_muestra(negocio_id)
    return {"estado": estado, "url": f"/negocios/{negocio_id}/kit/identidad/{identidad.ruta_muestra(negocio_id).name}"
            if estado == "lista" else ""}


@router.post("/negocios/{negocio_id}/kit/identidad/movimiento")
async def guardar_movimiento(request: Request, negocio_id: int):
    """El paquete de movimiento elegido a mano: un campo por elemento (gancho, choque, lista, subtitulos,
    fondo_texto, zooms) con la opción elegida."""
    from ..editor import modelo
    _propio(request, negocio_id)
    form = await request.form()
    elegido = {k: str(form.get(k)) for k in modelo.MOVIMIENTOS if form.get(k)}
    identidad.cambiar_movimiento(negocio_id, elegido, motivo="")
    return _volver(negocio_id, "kit", "Movimiento guardado: Monti lo usará en tus próximos vídeos.", "movimiento")


@router.post("/negocios/{negocio_id}/kit/identidad/movimiento/proponer")
def proponer_movimiento(request: Request, negocio_id: int):
    """Que Monti proponga el movimiento con lo que sabe de la marca (lo mismo que hace al terminar el onboarding)."""
    _propio(request, negocio_id)
    if not llm.disponible():
        return _volver(negocio_id, "kit", "Conecta tu clave de Claude en Conectores para que Monti lo proponga.",
                       "movimiento")
    neg = db.negocio(negocio_id)
    try:
        identidad.proponer_movimiento(neg)
    except llm.ErrorIA as e:
        return _volver(negocio_id, "kit", f"No se ha podido proponer: {e}", "movimiento")
    return _volver(negocio_id, "kit", "Monti ha propuesto un movimiento: mira la muestra.", "movimiento")


@router.get("/negocios/{negocio_id}/kit/movimiento/muestra")
def estado_muestra(request: Request, negocio_id: int):
    """Para que la página espere a la muestra sin recargar."""
    _propio(request, negocio_id)
    return _muestra(negocio_id)


@router.post("/negocios/{negocio_id}/kit/identidad/archivo")
async def subir_identidad(request: Request, negocio_id: int, tipo: str = Form(""), uso: str = Form(""),
                          archivo: UploadFile = File(...)):
    """Una tipografía (.ttf/.otf), un diseño de referencia o una foto para las portadas."""
    from ..editor.rutas import _guardar_subida
    _propio(request, negocio_id)
    from .. import limpieza
    error = identidad.error_archivo(tipo, archivo.filename or "") or limpieza.puede_subir(negocio_id, getattr(archivo, "size", 0) or 0)
    if error:
        return _volver(negocio_id, "kit", error, "identidad")
    destino = identidad.destino_nuevo(negocio_id, tipo, archivo.filename or tipo)
    if not await _guardar_subida(archivo, destino, identidad.LIMITE_MB[tipo]):
        destino.unlink(missing_ok=True)
        return _volver(negocio_id, "kit", f"Pesa demasiado: el máximo son {identidad.LIMITE_MB[tipo]} MB.", "identidad")
    entrada, error = identidad.anadir(negocio_id, tipo, destino, archivo.filename or tipo, uso)
    return _volver(negocio_id, "kit", error or f"{identidad.TIPOS[tipo]} guardada.", "identidad")


@router.post("/negocios/{negocio_id}/kit/identidad/quitar")
def quitar_identidad(request: Request, negocio_id: int, tipo: str = Form(""), archivo: str = Form("")):
    _propio(request, negocio_id)
    identidad.quitar(negocio_id, tipo, archivo)
    return _volver(negocio_id, "kit", "Quitado.", "identidad")


@router.get("/negocios/{negocio_id}/kit/identidad/{archivo}")
def ver_identidad(request: Request, negocio_id: int, archivo: str):
    from fastapi.responses import FileResponse
    _propio(request, negocio_id)
    ruta = identidad.ruta(negocio_id, archivo)
    if not ruta:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return FileResponse(ruta)


@router.post("/negocios/{negocio_id}/kit/voz")
def guardar_voz(request: Request, negocio_id: int, resumen: str = Form(""), como_habla: str = Form(""),
                movimientos: str = Form(""), frases: str = Form(""), nunca: str = Form("")):
    _propio(request, negocio_id)
    voz = kit_marca.limpiar_voz({"resumen": resumen, "como_habla": como_habla, "movimientos": movimientos,
                                 "frases": frases, "nunca": nunca})
    kit_marca.cambiar(negocio_id, voz=voz)
    return _volver(negocio_id, "kit", "Voz guardada.", "voz")


@router.post("/negocios/{negocio_id}/kit/carriles")
async def guardar_carriles(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    form = await request.form()
    columnas = [form.getlist(f"carril_{c}") for c in ("id", "nombre", "cuota", "etapa", "descripcion")]
    carriles = [dict(zip(("id", "nombre", "cuota", "etapa", "descripcion"), fila)) for fila in zip(*columnas)]
    mezcla = {e: form.get(f"mezcla_{e}") for e in kit_marca.ETAPAS}
    kit_marca.cambiar(negocio_id, carriles=kit_marca.limpiar_carriles(carriles), mezcla=kit_marca.limpiar_mezcla(mezcla))
    return _volver(negocio_id, "kit", "Carriles guardados.", "carriles")


@router.post("/negocios/{negocio_id}/kit/prohibidas")
def guardar_prohibidas(request: Request, negocio_id: int, prohibidas: str = Form("")):
    _propio(request, negocio_id)
    kit_marca.cambiar(negocio_id, prohibidas=kit_marca.lineas(prohibidas, 60))
    return _volver(negocio_id, "kit", "Frases prohibidas guardadas.", "prohibidas")


@router.post("/negocios/{negocio_id}/kit/pruebas")
def anadir_prueba(request: Request, negocio_id: int, tipo: str = Form("resultado"), titulo: str = Form(""),
                  texto: str = Form(""), cifra: str = Form(""), fuente: str = Form(""), consentimiento: str = Form("")):
    _propio(request, negocio_id)
    if cifra.strip() and not fuente.strip():
        return _volver(negocio_id, "kit", "Una cifra necesita su fuente: de dónde sale y cómo se puede comprobar.", "pruebas")
    nueva = kit_marca.anadir_prueba(negocio_id, {"tipo": tipo, "titulo": titulo, "texto": texto, "cifra": cifra,
                                                 "fuente": fuente, "consentimiento": consentimiento == "1"})
    return _volver(negocio_id, "kit", "Prueba añadida." if nueva else "Escribe al menos el título.", "pruebas")


@router.post("/negocios/{negocio_id}/kit/pruebas/{prueba_id}/borrar")
def borrar_prueba(request: Request, negocio_id: int, prueba_id: str):
    _propio(request, negocio_id)
    kit_marca.borrar_prueba(negocio_id, prueba_id)
    return _volver(negocio_id, "kit", "Prueba borrada.", "pruebas")


@router.post("/negocios/{negocio_id}/kit/lecciones")
def anadir_leccion(request: Request, negocio_id: int, regla: str = Form("")):
    _propio(request, negocio_id)
    nueva = kit_marca.anadir_leccion(negocio_id, regla)
    return _volver(negocio_id, "kit", "Lección guardada: todo el equipo la cumple desde ya." if nueva
                   else "Esa lección ya estaba o está vacía.", "lecciones")


@router.post("/negocios/{negocio_id}/kit/lecciones/{leccion_id}/borrar")
def borrar_leccion(request: Request, negocio_id: int, leccion_id: str):
    _propio(request, negocio_id)
    kit_marca.borrar_leccion(negocio_id, leccion_id)
    return _volver(negocio_id, "kit", "Lección borrada.", "lecciones")


@router.post("/negocios/{negocio_id}/kit/autonomia")
async def guardar_autonomia(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    form = await request.form()
    actual = kit_marca.leer(negocio_id)["autonomia"]
    nueva = {a: form.get(f"autonomia_{a}") if form.get(f"autonomia_{a}") in AUTONOMIAS else actual[a] for a in AGENTES}
    kit_marca.cambiar(negocio_id, autonomia=nueva)
    return _volver(negocio_id, "kit", "Autonomía guardada.", "autonomia")


def _redactar(negocio: dict):
    try:
        borrador = kit_marca.redactar_borrador(negocio)
        kit_marca.cambiar(negocio["id"], redactando=False, error_borrador="")
        ap.pedir(negocio["id"], "jefa", "kit", "Borrador del Kit de marca: voz, carriles y pruebas sacados de la ficha",
                 borrador)
    except ErrorIA as e:
        kit_marca.cambiar(negocio["id"], redactando=False, error_borrador=str(e))
    except Exception:  # noqa: BLE001 — que el aviso no se quede «redactando» para siempre
        kit_marca.cambiar(negocio["id"], redactando=False, error_borrador="No se ha podido redactar el borrador.")
        raise


@router.post("/negocios/{negocio_id}/kit/borrador")
def pedir_borrador(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    if not llm.disponible():
        return _volver(negocio_id, "kit", "Para redactar el borrador hace falta la clave de Claude.")
    if kit_marca.leer(negocio_id).get("redactando"):
        return _volver(negocio_id, "kit", "El borrador ya se está redactando.")
    kit_marca.cambiar(negocio_id, redactando=True, error_borrador="")
    neg.pop("_usuario", None)
    jobs.en_segundo_plano(_redactar, neg)
    return _volver(negocio_id, "kit", "Redactando el borrador. Te llegará a Aprobaciones en un minuto.")


# ---------------------------------------------------------------- aprobaciones

@router.get("/negocios/{negocio_id}/aprobaciones")
def ver_aprobaciones(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    return _pagina(request, "aprobaciones.html", vista="aprobaciones", pendientes=ap.pendientes(negocio_id),
                   decididas=[a for a in ap.de_negocio(negocio_id, limite=40) if a["estado"] != "pendiente"],
                   ESTADOS_AP=ap.ESTADOS, ETAPAS_KIT=kit_marca.ETAPAS, TIPOS_PRUEBA=kit_marca.TIPOS_PRUEBA,
                   **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/aprobaciones/{ap_id}")
def decidir(request: Request, negocio_id: int, ap_id: int, decision: str = Form(""), nota: str = Form("")):
    neg = _propio(request, negocio_id)
    a = ap.por_ref(negocio_id, str(ap_id))
    if not a or decision not in {"aprobar", "rechazar", "cambios"}:
        return _volver(negocio_id, "aprobaciones", "Esa aprobación no existe.")
    if a["estado"] != "pendiente":
        return _volver(negocio_id, "aprobaciones", f"{a['ref']} ya estaba decidida.")
    if decision == "cambios" and not nota.strip():
        return _volver(negocio_id, "aprobaciones", "Escribe qué quieres cambiar.", a["ref"])
    ap.decidir(a["id"], decision, nota=nota, por=neg["_usuario"]["email"])
    texto = {"aprobar": "Aprobado", "rechazar": "Rechazado", "cambios": "Cambios pedidos"}[decision]
    return _volver(negocio_id, "aprobaciones", f"{texto}: {a['ref']}.")


@router.post("/negocios/{negocio_id}/aprobaciones/{ap_id}/quitar")
def quitar_de_aprobacion(request: Request, negocio_id: int, ap_id: int, parte: str = Form(""), indice: int = Form(-1),
                         clave: str = Form("")):
    """Quitar un elemento suelto de un borrador del Kit antes de aprobarlo."""
    _propio(request, negocio_id)
    a = ap.por_ref(negocio_id, str(ap_id))
    hecho = bool(a) and ap.quitar_parte(a["id"], parte, indice if indice >= 0 else None, clave)
    return _volver(negocio_id, "aprobaciones", "Quitado." if hecho else "Eso ya no se puede quitar.", a["ref"] if a else "")


# ---------------------------------------------------------------- Analista: investigación

@router.get("/negocios/{negocio_id}/investigacion")
def ver_investigacion(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    if not analista.cuentas(negocio_id):
        analista.desde_la_ficha(neg)
    return _pagina(request, "investigacion.html", vista="investigacion", cuentas=analista.cuentas(negocio_id),
                   destacados=analista.destacados(negocio_id), propios=analista.destacados(negocio_id, propios=True),
                   tus_posts=analista.tus_posts(negocio_id, 12), medianas=analista.medianas(negocio_id),
                   estado_analista=estado.leer(negocio_id, analista.AGENTE), PLATAFORMAS=analista.PLATAFORMAS,
                   NIVELES=analista.NIVELES, umbral=analista.UMBRAL_X, ia=llm.disponible(),
                   despegando=analista.despegando(negocio_id), descartados=analista.descartados(negocio_id),
                   publico=estado.leer(negocio_id, analista.AGENTE).get("publico") or {}, TIPOS_POST=analista.TIPOS_POST,
                   **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/investigacion/cuentas")
def anadir_cuenta(request: Request, negocio_id: int, plataforma: str = Form(""), usuario: str = Form(""),
                  propia: str = Form(""), nivel: int = Form(2)):
    _propio(request, negocio_id)
    cuenta, error = analista.anadir_cuenta(negocio_id, plataforma, usuario, propia=propia == "1", nivel=nivel)
    return _volver(negocio_id, "investigacion", error or f"Añadida: {cuenta['usuario']}.", "cuentas")


@router.post("/negocios/{negocio_id}/investigacion/cuentas/{cuenta_id}/quitar")
def quitar_cuenta(request: Request, negocio_id: int, cuenta_id: int):
    _propio(request, negocio_id)
    analista.quitar_cuenta(negocio_id, cuenta_id)
    return _volver(negocio_id, "investigacion", "Cuenta quitada.", "cuentas")


@router.post("/negocios/{negocio_id}/investigacion/cuentas/{cuenta_id}/nivel")
def nivel_cuenta(request: Request, negocio_id: int, cuenta_id: int, nivel: int = Form(2)):
    _propio(request, negocio_id)
    analista.cambiar_nivel(negocio_id, cuenta_id, nivel)
    return _volver(negocio_id, "investigacion", "", "cuentas")


@router.post("/negocios/{negocio_id}/investigacion/escanear")
def escanear(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    if estado.leer(negocio_id, analista.AGENTE).get("trabajando"):
        return _volver(negocio_id, "investigacion", "Lupi ya está escaneando.")
    if not analista.cuentas(negocio_id):
        return _volver(negocio_id, "investigacion", "Añade al menos una cuenta.")
    estado.cambiar(negocio_id, analista.AGENTE, trabajando=True, avisos=[])
    jobs.en_segundo_plano(analista.trabajo_escaneo, negocio_id, neg["_usuario"]["id"])
    return _volver(negocio_id, "investigacion", "Escaneando. La página se actualiza sola al terminar.")


@router.get("/negocios/{negocio_id}/investigacion/estado")
def estado_escaneo(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    e = estado.leer(negocio_id, analista.AGENTE)
    return {"estado": "en_curso" if e.get("trabajando") else "listo", "hechas": [e.get("ultimo") or ""]}


@router.post("/negocios/{negocio_id}/investigacion/posts/{post_id}/desmontar")
def desmontar(request: Request, negocio_id: int, post_id: int):
    _propio(request, negocio_id)
    if not llm.disponible():
        return _volver(negocio_id, "investigacion", "Para desmontar un vídeo hace falta la clave de Claude.")
    p = analista.post(negocio_id, post_id)
    if not p:
        return _volver(negocio_id, "investigacion", "Ese post no existe.")
    with db.conexion() as con:  # un desmontaje pedido a mano siempre se intenta, aunque fallara antes
        con.execute("UPDATE posts SET intentos = 0, estado_plantilla = '' WHERE id = ?", (post_id,))
    jobs.en_segundo_plano(analista.desmontar, negocio_id, post_id)
    return _volver(negocio_id, "investigacion", "Desmontando el vídeo: en un minuto tendrás su plantilla.", f"post-{post_id}")


@router.post("/negocios/{negocio_id}/investigacion/sugerir-cuentas")
def sugerir_cuentas(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    if not llm.disponible():
        return _volver(negocio_id, "investigacion", "Para buscar cuentas hace falta la clave de Claude.", "cuentas")
    from . import analista_web
    jobs.en_segundo_plano(analista_web.trabajo_sugerir_cuentas, negocio_id)
    return _volver(negocio_id, "investigacion", "Lupi está buscando cuentas: te las propondrá en Aprobaciones.", "cuentas")


@router.post("/negocios/{negocio_id}/investigacion/perfil")
def puntuar_perfil(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    if not llm.disponible() or not config.apify_activo():
        return _volver(negocio_id, "investigacion", "Para puntuar el perfil hacen falta Claude y Apify, en Conectores.", "perfil")
    from . import analista_web
    jobs.en_segundo_plano(analista_web.trabajo_perfil, negocio_id)
    return _volver(negocio_id, "investigacion", "Lupi está puntuando tu perfil: en un minuto tendrás la nota.", "perfil")


@router.post("/negocios/{negocio_id}/investigacion/borrador-ficha")
def borrador_ficha(request: Request, negocio_id: int, url: str = Form("")):
    neg = _propio(request, negocio_id)
    if not llm.disponible():
        return _volver(negocio_id, "investigacion", "Para leer la web hace falta la clave de Claude.")
    url = url.strip() or str(neg["ficha"].get("web") or "").strip()
    if not url:
        return _volver(negocio_id, "investigacion", "Falta la web: escríbela o ponla en la ficha.")
    from . import analista_web
    jobs.en_segundo_plano(analista_web.trabajo_borrador_ficha, negocio_id, url)
    return _volver(negocio_id, "investigacion", "Lupi está leyendo tu web: el borrador de la ficha llegará a Aprobaciones.")


# ---------------------------------------------------------------- Estratega: Graba hoy

@router.get("/negocios/{negocio_id}/estrategia")
def ver_estrategia(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    kit = kit_marca.leer(negocio_id)
    hoy = estratega._hoy()
    de_hoy = [p for p in estratega.piezas(negocio_id, dia=hoy) if p["estado"] != "rechazada"]
    pendientes = [p for p in estratega.piezas(negocio_id, estados=("aprobada",)) if p["dia"] != hoy]
    guion_de = {g["pieza_id"]: g["id"] for g in reversed(guionista.guiones(negocio_id))}  # pieza → su estructura
    return _pagina(request, "estrategia.html", vista="estrategia", de_hoy=de_hoy, pendientes_grabar=pendientes,
                   guion_de=guion_de,
                   semana=estratega.semana(negocio_id, kit), mezcla=kit["mezcla"],
                   reparto=estratega.reparto_reciente(negocio_id), ETAPAS_KIT=kit_marca.ETAPAS,
                   carriles={c["id"]: c["nombre"] for c in kit["carriles"]},
                   n_candidatos=len(estratega.candidatos(neg, kit)), ia=llm.disponible(),
                   estado_estratega=estado.leer(negocio_id, estratega.AGENTE), **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/estrategia/planificar")
def planificar(request: Request, negocio_id: int, lote: str = Form("")):
    neg = _propio(request, negocio_id)
    if estado.leer(negocio_id, estratega.AGENTE).get("trabajando"):
        return _volver(negocio_id, "estrategia", "Plani ya está preparando el plan.")
    usuario_id = neg.pop("_usuario")["id"]
    estado.cambiar(negocio_id, estratega.AGENTE, trabajando=True, avisos=[])
    jobs.en_segundo_plano(estratega.trabajo_planificar, neg, lote == "1", "", usuario_id)
    return _volver(negocio_id, "estrategia", "Preparando el plan. Te llegará a Aprobaciones.")


@router.post("/negocios/{negocio_id}/estrategia/reaprovechar")
def reaprovechar_grabacion(request: Request, negocio_id: int, texto: str = Form(""), titulo: str = Form(""),
                           video_propio: str = Form("1")):
    """Una grabación larga (su transcripción) se convierte en una semana de piezas: llegan a Aprobaciones."""
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    if len(texto.split()) < 150:
        return _volver(negocio_id, "estrategia", "El texto es muy corto: pega la transcripción entera.", "reaprovechar")
    if not llm.disponible():
        return _volver(negocio_id, "estrategia", "Conecta Claude en Conectores para reaprovechar una grabación.",
                       "reaprovechar")
    propio = video_propio in ("1", "si", "on", "true")
    jobs.en_segundo_plano(lambda: estratega.reaprovechar(neg, texto[:200_000], titulo.strip()[:160], video_propio=propio))
    return _volver(negocio_id, "estrategia", "Plani está sacando las piezas de tu grabación: te llegarán a Aprobaciones.",
                   "reaprovechar")


@router.get("/negocios/{negocio_id}/estrategia/estado")
def estado_estrategia(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    e = estado.leer(negocio_id, estratega.AGENTE)
    return {"estado": "en_curso" if e.get("trabajando") else "listo", "hechas": [e.get("ultimo") or ""]}


@router.post("/negocios/{negocio_id}/estrategia/piezas/{pieza_id}/descartar")
def descartar_pieza(request: Request, negocio_id: int, pieza_id: int, motivo: str = Form("")):
    _propio(request, negocio_id)
    estratega.descartar(negocio_id, pieza_id, motivo)
    return _volver(negocio_id, "estrategia", "Descartada. Plani no volverá a proponer esa idea.")


# ---------------------------------------------------------------- Guionista

@router.get("/negocios/{negocio_id}/guiones")
def ver_guiones(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    todos = guionista.guiones(negocio_id, estados=("bloqueado", "pendiente", "aprobado"))
    piezas = {p["id"]: p for p in estratega.piezas(negocio_id)}
    sin_guion = [p for p in piezas.values() if p["estado"] == "aprobada"
                 and not guionista.guion_de_pieza(negocio_id, p["id"])]
    return _pagina(request, "guiones.html", vista="guiones", guiones=todos, piezas=piezas, sin_guion=sin_guion,
                   CTAS=validador.CTAS, ia=llm.disponible(), estado_guionista=estado.leer(negocio_id, guionista.AGENTE),
                   **_datos_espacio(u, neg, inf))


@router.get("/negocios/{negocio_id}/guiones/estado")
def estado_guiones(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    e = estado.leer(negocio_id, guionista.AGENTE)
    return {"estado": "en_curso" if e.get("trabajando") else "listo", "hechas": [e.get("ultimo") or ""]}


@router.get("/negocios/{negocio_id}/guiones/{guion_id}")
def ver_guion(request: Request, negocio_id: int, guion_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    g = guionista.guion(negocio_id, guion_id)
    if not g:
        raise auth.SinPermiso()
    pieza = estratega.pieza(negocio_id, g["pieza_id"])
    return _pagina(request, "guion.html", vista="guiones", g=g, pieza=pieza, CTAS=validador.CTAS,
                   PLATAFORMAS_TEXTO=guionista.PLATAFORMAS_TEXTO, ia=llm.disponible(),
                   carriles={c["id"]: c["nombre"] for c in kit_marca.leer(negocio_id)["carriles"]},
                   **_datos_espacio(u, neg, inf))


def _lanzar_guiones(negocio_id: int, neg: dict, ids: list[int], nota: str = ""):
    usuario_id = neg.pop("_usuario")["id"]
    estado.cambiar(negocio_id, guionista.AGENTE, trabajando=True, avisos=[])
    jobs.en_segundo_plano(guionista.trabajo_escribir, neg, ids, nota, usuario_id)


@router.post("/negocios/{negocio_id}/guiones/escribir")
def escribir_pendientes(request: Request, negocio_id: int, pieza_id: int = Form(0)):
    neg = _propio(request, negocio_id)
    if not llm.disponible():
        return _volver(negocio_id, "guiones", "Para escribir guiones hace falta la clave de Claude.")
    ids = [pieza_id] if pieza_id else [p["id"] for p in estratega.piezas(negocio_id, estados=("aprobada",))
                                       if not guionista.guion_de_pieza(negocio_id, p["id"])]
    if not ids:
        return _volver(negocio_id, "guiones", "No hay piezas aprobadas sin guion.")
    _lanzar_guiones(negocio_id, neg, ids)
    return _volver(negocio_id, "guiones", "Escribiendo. Cada guion que pase el validador te llegará a Aprobaciones.")


@router.post("/negocios/{negocio_id}/guiones/nuevo")
def nuevo_guion(request: Request, negocio_id: int, tema: str = Form(""), texto: str = Form(""),
                cta: str = Form("ninguna"), palabra_clave: str = Form(""), hashtags: str = Form(""),
                modo: str = Form("ia")):
    neg = _propio(request, negocio_id)
    if not tema.strip():
        return _volver(negocio_id, "guiones", "Escribe de qué va el guion.")
    if modo == "yo":
        if not texto.strip():
            return _volver(negocio_id, "guiones", "Escribe el guion.")
        neg.pop("_usuario")
        g = guionista.escribir_a_mano(neg, tema, texto, cta=cta, palabra_clave=palabra_clave, hashtags=hashtags)
        return RedirectResponse(f"/negocios/{negocio_id}/guiones/{g['id']}", status_code=303)
    if not llm.disponible():
        return _volver(negocio_id, "guiones", "Para pedírselo a la IA hace falta la clave de Claude.")
    pieza_id = guionista.pedir_sobre(neg, tema)
    _lanzar_guiones(negocio_id, neg, [pieza_id])
    remix = estratega.pieza(negocio_id, pieza_id)["tipo"] != "original"
    return _volver(negocio_id, "guiones", "Escribiendo. " + ("He encontrado un post probado sobre ese tema y lo voy a "
                                                             "rehacer." if remix else "No hay un post probado sobre ese tema: será original."))


@router.post("/negocios/{negocio_id}/investigacion/posts/{post_id}/adaptar")
def adaptar_post(request: Request, negocio_id: int, post_id: int):
    """«Adaptar a mi voz» en Ideas: Escri rehace ese reel con tu voz (si hace falta, Lupi lo desmonta antes)."""
    neg = _propio(request, negocio_id)
    if not llm.disponible():
        return _volver(negocio_id, "investigacion", "Para adaptar un reel hace falta la clave de Claude.")
    try:
        pieza_id = guionista.adaptar_post(neg, post_id)
    except ValueError as e:
        return _volver(negocio_id, "investigacion", str(e))
    usuario_id = neg.pop("_usuario")["id"]
    estado.cambiar(negocio_id, guionista.AGENTE, trabajando=True, avisos=[])
    jobs.en_segundo_plano(guionista.trabajo_adaptar, neg, pieza_id, post_id, usuario_id)
    return _volver(negocio_id, "guiones", "Escri está adaptando ese reel a tu voz. En unos minutos tienes la estructura aquí.")


@router.post("/negocios/{negocio_id}/guiones/{guion_id}/editar")
def editar_guion(request: Request, negocio_id: int, guion_id: int, texto: str = Form(""), palabra_clave: str = Form("")):
    neg = _propio(request, negocio_id)
    g = guionista.guion(negocio_id, guion_id)
    if not g or not texto.strip():
        return _volver(negocio_id, "guiones", "Ese guion no existe o está vacío.")
    neg.pop("_usuario")
    nuevo = guionista.editar(neg, guion_id, texto, palabra_clave)
    return RedirectResponse(f"/negocios/{negocio_id}/guiones/{nuevo['id']}?aviso={quote('Guardado y aprobado.')}",
                            status_code=303)


@router.post("/negocios/{negocio_id}/guiones/{guion_id}/grabado")
def guion_grabado(request: Request, negocio_id: int, guion_id: int):
    _propio(request, negocio_id)
    guionista.marcar_grabado(negocio_id, guion_id)
    return RedirectResponse(f"/negocios/{negocio_id}/guiones/{guion_id}?aviso={quote('Marcado como grabado.')}",
                            status_code=303)


@router.post("/negocios/{negocio_id}/guiones/{guion_id}/reintentar")
def reintentar_guion(request: Request, negocio_id: int, guion_id: int, nota: str = Form("")):
    neg = _propio(request, negocio_id)
    g = guionista.guion(negocio_id, guion_id)
    if not g or not llm.disponible():
        return _volver(negocio_id, "guiones", "No se puede reescribir ahora.")
    _lanzar_guiones(negocio_id, neg, [g["pieza_id"]], nota)
    return _volver(negocio_id, "guiones", "Reescribiendo el guion.")


# ---------------------------------------------------------------- Producción: tomas, cola y revisión

EXT_TOMA = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


@router.get("/negocios/{negocio_id}/produccion")
def ver_produccion(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    todas = produccion.tomas(negocio_id)
    guiones = {g["id"]: g for g in guionista.guiones(negocio_id, estados=("aprobado",))}
    piezas = {p["id"]: p for p in estratega.piezas(negocio_id)}
    trabajando = any(t["etapa"] in ("en_cola", "cortando", "plan", "montando") for t in todas)
    from .. import limpieza
    return _pagina(request, "produccion.html", vista="produccion", tomas=todas, guiones=guiones, piezas=piezas,
                   espacio=limpieza.resumen(negocio_id),
                   candidatos=produccion.candidatos(negocio_id), versiones=produccion.versiones,
                   trabajando=trabajando, **_datos_espacio(u, neg, inf))


@router.get("/negocios/{negocio_id}/produccion/estado")
def estado_produccion(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    todas = produccion.tomas(negocio_id)
    en_marcha = any(t["etapa"] in ("en_cola", "cortando", "plan", "montando") for t in todas)
    return {"estado": "en_curso" if en_marcha else "listo", "hechas": [f"{t['id']}:{t['etapa']}" for t in todas]}


@router.post("/negocios/{negocio_id}/produccion/subir")
async def subir_tomas(request: Request, negocio_id: int, archivos: list[UploadFile] = File(...),
                      sin_guion: str = Form("")):
    neg = _propio(request, negocio_id)
    u = neg["_usuario"]
    from ..editor.rutas import _guardar_subida
    subidas, avisos = 0, []
    from .. import limpieza
    for archivo in archivos:
        extension = Path(archivo.filename or "").suffix.lower()
        sin_espacio = limpieza.puede_subir(negocio_id, getattr(archivo, "size", 0) or 0)
        if sin_espacio:
            avisos.append(sin_espacio)
            break
        if extension not in EXT_TOMA:
            avisos.append(f"{archivo.filename}: no es un vídeo.")
            continue
        if auth.cupo(u)["ediciones"] <= 0:
            avisos.append("Has llegado al límite de vídeos editados de tu plan este mes.")
            break
        edicion_id = produccion.crear_toma(negocio_id, Path(archivo.filename or "toma").stem, u["id"])
        destino = produccion.motor.carpeta(edicion_id) / f"bruto{extension}"
        if not await _guardar_subida(archivo, destino, config.MAX_MB_BRUTO):
            db.actualizar_edicion(edicion_id, estado="error", paso=f"Pesa más de {config.MAX_MB_BRUTO} MB.")
            avisos.append(f"{archivo.filename}: pesa más de {config.MAX_MB_BRUTO} MB.")
            continue
        if sin_guion == "1":
            produccion._guardar(edicion_id, emparejado="sin_guion")
        gasto_id = db.abrir_gasto(usuario_id=u["id"], negocio_id=negocio_id, concepto="edicion", referencia=edicion_id)
        db.cerrar_gasto(gasto_id, {"coste_claude": 0, "apify_coste": 0})
        subidas += 1
    if subidas:
        produccion.despertar()
    texto = f"{subidas} toma{'s' if subidas != 1 else ''} en la cola." + (" " + " ".join(avisos) if avisos else "")
    return _volver(negocio_id, "produccion", texto)


def _toma_propia(request: Request, negocio_id: int, edicion_id: int) -> dict:
    _propio(request, negocio_id)
    ed = db.edicion(edicion_id)
    if not ed or ed["negocio_id"] != negocio_id or not produccion.es_toma(ed):
        raise auth.SinPermiso()
    return ed


@router.post("/negocios/{negocio_id}/produccion/{edicion_id}/guion")
def elegir_guion(request: Request, negocio_id: int, edicion_id: int, guion_id: int = Form(0)):
    _toma_propia(request, negocio_id, edicion_id)
    produccion.asignar(negocio_id, edicion_id, guion_id or None, "confirmado" if guion_id else "sin_guion")
    return _volver(negocio_id, "produccion", "En la cola de edición.")


@router.post("/negocios/{negocio_id}/produccion/{edicion_id}/cambios")
async def cambios_video(request: Request, negocio_id: int, edicion_id: int):
    _toma_propia(request, negocio_id, edicion_id)
    form = await request.form()
    try:
        notas = json.loads(form.get("notas") or "[]")
    except ValueError:
        notas = []
    if not produccion.motor.bruto(edicion_id):
        return _volver(negocio_id, "produccion", "La toma original ya se borró (se guarda 14 días tras aprobar el vídeo): "
                                                 "para otra versión, vuelve a subirla.", f"t{edicion_id}")
    if not produccion.pedir_cambios(negocio_id, edicion_id, notas if isinstance(notas, list) else [],
                                    str(form.get("general") or "")):
        return _volver(negocio_id, "produccion", "Escribe al menos una nota.", f"t{edicion_id}")
    return _volver(negocio_id, "produccion", "Monti está haciendo la versión siguiente con tus notas.")


@router.post("/negocios/{negocio_id}/produccion/{edicion_id}/aprobar")
def aprobar_video(request: Request, negocio_id: int, edicion_id: int):
    neg = _propio(request, negocio_id)
    ed = _toma_propia(request, negocio_id, edicion_id)
    a = ap.aprobacion(ed["datos"]["produccion"].get("aprobacion_id") or 0)
    if a and a["estado"] == "pendiente":
        ap.decidir(a["id"], "aprobar", por=neg["_usuario"]["email"])
    elif produccion.etapa(ed) == "revisar":
        produccion._guardar(edicion_id, aprobado=True, aprobado_por=neg["_usuario"]["email"])
    return _volver(negocio_id, "produccion", "Aprobado: listo para publicar.")


@router.post("/negocios/{negocio_id}/produccion/{edicion_id}/reintentar")
def reintentar_toma(request: Request, negocio_id: int, edicion_id: int):
    _toma_propia(request, negocio_id, edicion_id)
    ok = produccion.reintentar(negocio_id, edicion_id)
    return _volver(negocio_id, "produccion", "Otra vez en la cola." if ok else "Esa toma ya está en marcha.")


@router.get("/negocios/{negocio_id}/produccion/{edicion_id}/v{version}.mp4")
def version_anterior(request: Request, negocio_id: int, edicion_id: int, version: int):
    from fastapi.responses import FileResponse
    _toma_propia(request, negocio_id, edicion_id)
    ruta = produccion.motor.carpeta(edicion_id) / f"v{version}.mp4"
    if not ruta.exists():
        raise auth.SinPermiso()
    return FileResponse(ruta, media_type="video/mp4")


# ---------------------------------------------------------------- Publicador

DIAS = ["L", "M", "X", "J", "V", "S", "D"]


@router.get("/negocios/{negocio_id}/publicacion")
def ver_publicacion(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    publicador.actualizar_estados(negocio_id)
    kit = kit_marca.leer(negocio_id)
    videos = publicador.videos_aprobados(negocio_id)
    publicador.preparar_los_que_falten(negocio_id, videos)
    activas = [r for r, p in kit["publicacion"].items() if p.get("activa")]
    for v in videos:
        hechas = {p["plataforma"] for p in v["publicaciones"] if p["estado"] in publicador.VIVAS and p["modo"] != "prueba"}
        v["faltan"] = [r for r in activas if r not in hechas]
        v["textos"] = {r: publicador.texto_para(v, r, kit=kit) for r in publicador.REDES}
        v["huecos"] = {r: publicador.proximo_hueco(negocio_id, r) for r in v["faltan"]}
    con = publicador.conexion(negocio_id)
    return _pagina(request, "publicacion.html", vista="publicacion", videos=videos,
                   pendientes=[v for v in videos if v["faltan"]], te_toca=publicador.te_toca(negocio_id),
                   calendario=publicador.calendario(negocio_id), cuentas_redes=publicador.estado_cuentas(negocio_id),
                   conectado=publicador.conectado(negocio_id), con_clave_propia=bool(con.get("clave")),
                   perfil=con.get("perfil", ""), comprobado=con.get("comprobado", ""), plan=kit["publicacion"],
                   REDES=publicador.REDES, DIAS=DIAS, **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/publicacion/zernio")
def conectar_zernio(request: Request, negocio_id: int, clave: str = Form(""), perfil: str = Form("")):
    _propio(request, negocio_id)
    try:
        datos = publicador.conectar(negocio_id, clave, perfil)
    except publicador.zernio.ErrorZernio as e:
        return _volver(negocio_id, "conectores", str(e), "zernio")
    return _volver(negocio_id, "conectores", f"Zernio conectado: ve {len(datos['cuentas'])} cuentas.", "zernio")


@router.post("/negocios/{negocio_id}/publicacion/plan")
async def guardar_plan(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    form = await request.form()
    plan = {}
    for red in publicador.REDES:
        horas = [h.strip().zfill(5) for h in str(form.get(f"{red}_horas") or "").replace(";", ",").split(",") if h.strip()]
        plan[red] = {"activa": form.get(f"{red}_activa") == "1",
                     "dias": sorted({int(d) for d in form.getlist(f"{red}_dias") if str(d).isdigit() and 0 <= int(d) <= 6}),
                     "horas": sorted({h for h in horas if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", h)}),
                     "autopublicar": form.get(f"{red}_autopublicar") == "1" if red == "instagram" else True}
    plan["instagram"]["colaboradores"] = publicador.limpiar_colaboradores(str(form.get("instagram_colaboradores") or ""))
    kit_marca.cambiar(negocio_id, publicacion=plan)
    return _volver(negocio_id, "publicacion", "Plan de publicación guardado.", "plan")


@router.post("/negocios/{negocio_id}/publicacion/{edicion_id}/programar")
async def programar(request: Request, negocio_id: int, edicion_id: int):
    _propio(request, negocio_id)
    form = await request.form()
    redes = [r for r in form.getlist("redes") if r in publicador.REDES]
    cuando = None
    if form.get("cuando"):
        try:
            cuando = datetime.fromisoformat(str(form["cuando"]))
        except ValueError:
            return _volver(negocio_id, "publicacion", "Esa fecha no es válida.")
    if not redes:
        return _volver(negocio_id, "publicacion", "Marca al menos una red.")
    textos = {r: str(form.get(f"texto_{r}") or "") for r in redes}
    r = publicador.programar(negocio_id, edicion_id, redes, cuando=cuando, textos=textos, ensayo=form.get("ensayo") == "1")
    if form.get("ensayo") == "1":  # el ensayo: qué saldría, sin mandar nada
        lineas = [f"{p['red_nombre']}: {p['cuando']:%d/%m %H:%M} · " + (" ".join(p["problemas"]) or "listo")
                  + (f" {p['aviso']}" if p["aviso"] else "") if p["cuando"] else f"{p['red_nombre']}: "
                  + " ".join(p["problemas"]) for p in r["plan"]]
        return _volver(negocio_id, "publicacion", "Ensayo, no se ha mandado nada. " + " · ".join(lineas)
                       if lineas else "Ya estaba programado.")
    partes = []
    if r["programadas"]:
        partes.append("Programado en " + ", ".join(f"{publicador.REDES[p['red']]} ({p['cuando']:%d/%m %H:%M})"
                                                   for p in r["programadas"]) + ".")
    partes += r["fallos"]
    return _volver(negocio_id, "publicacion", " ".join(partes) or "Ya estaba programado.")


@router.post("/negocios/{negocio_id}/publicacion/{edicion_id}/colaboradores")
def colaboradores_del_video(request: Request, negocio_id: int, edicion_id: int, colaboradores: str = Form("")):
    _propio(request, negocio_id)
    lista = publicador.poner_colaboradores(negocio_id, edicion_id, colaboradores)
    return _volver(negocio_id, "publicacion", "Colaboradores: " + ", ".join(f"@{u}" for u in lista) + "."
                   if lista else "Este vídeo usa los colaboradores del plan.")


@router.post("/negocios/{negocio_id}/publicacion/{edicion_id}/reels-prueba")
def proponer_reels_prueba(request: Request, negocio_id: int, edicion_id: int):
    _propio(request, negocio_id)
    r = publicador.proponer_reels_prueba(negocio_id, edicion_id)
    if r["fallos"]:
        return _volver(negocio_id, "publicacion", " ".join(r["fallos"]))
    return _volver(negocio_id, "publicacion", f"Reels de prueba pendientes de tu OK ({r['aprobacion']['resumen']}).")


@router.post("/negocios/{negocio_id}/publicacion/reels-prueba/fuera-del-perfil")
def reels_prueba_fuera_del_perfil(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    publicador.confirmar_fuera_del_perfil(negocio_id)
    return _volver(negocio_id, "publicacion", "Hecho: los próximos reels de prueba salen en lote.")


@router.post("/negocios/{negocio_id}/publicacion/p/{publicacion_id}/publicada")
def marcar_publicada(request: Request, negocio_id: int, publicacion_id: int, url: str = Form("")):
    _propio(request, negocio_id)
    publicador.marcar_publicada(negocio_id, publicacion_id, url)
    return _volver(negocio_id, "publicacion", "Marcada como publicada.")


@router.post("/negocios/{negocio_id}/publicacion/p/{publicacion_id}/cancelar")
def cancelar_publicacion(request: Request, negocio_id: int, publicacion_id: int):
    _propio(request, negocio_id)
    error = publicador.cancelar(negocio_id, publicacion_id)
    return _volver(negocio_id, "publicacion", error or "Cancelada.")


# ---------------------------------------------------------------- Comunidad

@router.get("/negocios/{negocio_id}/comunidad")
def ver_comunidad(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    guiones = [g for g in guionista.guiones(negocio_id, estados=("aprobado", "pendiente")) if g["palabra_clave"]]
    con_guia = {g["palabra"] for g in comunidad.guias(negocio_id)}
    return _pagina(request, "comunidad.html", vista="comunidad", conversaciones=comunidad.bandeja(negocio_id),
                   guias=comunidad.guias(negocio_id), sin_guia=[g for g in guiones if g["palabra_clave"] not in con_guia],
                   automatizaciones=comunidad.automatizaciones(negocio_id), contactos=comunidad.contactos(negocio_id, 50),
                   ajustes_comunidad=comunidad.ajustes(negocio_id), estado_comunidad=estado.leer(negocio_id, comunidad.AGENTE),
                   url_publica=config.URL_PUBLICA, conectado=comunidad.conectado(negocio_id), ia=llm.disponible(),
                   manychat=_estado_manychat(negocio_id), TEMPERATURAS=comunidad.TEMPERATURAS,
                   posts_propios=comentarios.publicaciones_propias(negocio_id), TIPOS_DM=comunidad.TIPOS_DM,
                   regalos=regalos.lista(negocio_id), **_datos_espacio(u, neg, inf))


def _trabajo_bandeja(negocio: dict):
    estado.cambiar(negocio["id"], comunidad.AGENTE, trabajando=True, avisos=[])
    try:
        r = comunidad.sincronizar_bandeja(negocio)
        estado.cambiar(negocio["id"], comunidad.AGENTE, trabajando=False, ultimo=comunidad._ahora(), avisos=r["avisos"])
    except Exception as e:  # noqa: BLE001
        estado.cambiar(negocio["id"], comunidad.AGENTE, trabajando=False, avisos=[f"La bandeja se ha parado: {e}"])
        raise


@router.post("/negocios/{negocio_id}/comunidad/leer")
def leer_bandeja(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    if not comunidad.conectado(negocio_id):
        return _volver(negocio_id, "comunidad", "Conecta ManyChat para recibir tus DMs.")
    jobs.en_segundo_plano(_trabajo_bandeja, neg)
    return _volver(negocio_id, "comunidad", "Clasificando tus DMs. Los borradores de respuesta te llegarán a Aprobaciones.")


@router.get("/negocios/{negocio_id}/comunidad/estado")
def estado_bandeja(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    e = estado.leer(negocio_id, comunidad.AGENTE)
    return {"estado": "en_curso" if e.get("trabajando") else "listo", "hechas": [e.get("ultimo") or ""]}


@router.post("/negocios/{negocio_id}/comunidad/ajustes")
def ajustes_comunidad(request: Request, negocio_id: int, dm_automaticos: str = Form(""), mensaje_dm: str = Form(""),
                      crm_webhook: str = Form("")):
    _propio(request, negocio_id)
    webhook = crm_webhook.strip()
    if webhook and not webhook.startswith("https://"):
        return _volver(negocio_id, "comunidad", "El webhook del CRM tiene que empezar por https://", "ajustes")
    kit_marca.cambiar(negocio_id, comunidad={"dm_automaticos": dm_automaticos == "1", "crm_webhook": webhook,
                                             "mensaje_dm": mensaje_dm.strip()[:500] or "Aquí tienes lo que pediste:"})
    return _volver(negocio_id, "comunidad", "Guardado.", "ajustes")


@router.post("/negocios/{negocio_id}/comunidad/automatizaciones")
def activar_automatizaciones(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    avisos = comunidad.sincronizar_automatizaciones(neg)
    texto = " ".join(avisos) or "ManyChat conectado: las palabras clave responden solas."
    if comunidad.conectado(negocio_id) and comunidad.direccion(negocio_id):
        texto += f" Dirección para la petición externa de ManyChat: {comunidad.direccion(negocio_id)}"
    return _volver(negocio_id, "comunidad", texto, "automatizaciones")


def _estado_manychat(negocio_id: int) -> dict:
    """Lo que hace falta para conectar ManyChat: si hay clave, la cuenta, la dirección y el cuerpo de la petición."""
    con = comunidad.conexion(negocio_id)
    return {"conectado": comunidad.conectado(negocio_id), "con_clave_propia": bool(con.get("clave")),
            "cuenta": con.get("cuenta") or {}, "comprobado": con.get("comprobado", ""),
            "direccion": comunidad.direccion(negocio_id) if comunidad.conectado(negocio_id) else "",
            "cuerpo": comunidad.CUERPO_PETICION, "respuesta": comunidad.CAMPOS_RESPUESTA,
            "comentarios": [{"palabra": g["palabra"], "nombre": f"Equipo · {g['palabra']}",
                             "cuerpo": comunidad.cuerpo_comentario(g["palabra"])} for g in comunidad.guias(negocio_id)]}


@router.post("/negocios/{negocio_id}/comunidad/manychat")
def conectar_manychat(request: Request, negocio_id: int, clave: str = Form("")):
    _propio(request, negocio_id)
    try:
        datos = comunidad.conectar(negocio_id, clave)
    except comunidad.manychat.ErrorManyChat as e:
        return _volver(negocio_id, "conectores", str(e), "manychat")
    nombre = (datos.get("cuenta") or {}).get("nombre") or "tu cuenta"
    return _volver(negocio_id, "conectores", f"ManyChat conectado con {nombre}.", "manychat")


@router.get("/negocios/{negocio_id}/comunidad/manychat")
def ver_manychat(request: Request, negocio_id: int):
    """El estado de la conexión en JSON (para la página de Comunidad y para montar la automatización maestra)."""
    _propio(request, negocio_id)
    return {**_estado_manychat(negocio_id), "avisos": comunidad.comprobar(negocio_id)}


@router.post("/m/{token}")
async def desde_manychat(request: Request, token: str):
    """La automatización maestra de ManyChat manda aquí cada comentario y cada DM, y recibe qué contestar."""
    from fastapi.responses import JSONResponse
    nid = comunidad.negocio_por_token(token)
    neg = db.negocio(nid) if nid else None
    claves.usar(nid)  # lo que haga Chati con este mensaje, con las claves de ese negocio
    if not neg:
        return JSONResponse({"error": "no encontrado"}, status_code=404)
    try:
        datos = await request.json()
    except ValueError:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    return JSONResponse(comunidad.recibir(neg, datos))


@router.post("/negocios/{negocio_id}/comunidad/guias")
def crear_guia(request: Request, negocio_id: int, guion_id: int = Form(0)):
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    try:
        g = comunidad.redactar_guia(neg, guion_id)
    except (ValueError, ErrorIA) as e:
        return _volver(negocio_id, "comunidad", str(e), "guias")
    return _volver(negocio_id, "comunidad", f"Guía de {g['palabra']} lista: revísala.", f"guia-{g['id']}")


@router.post("/negocios/{negocio_id}/comunidad/dm")
def escribir_dm(request: Request, negocio_id: int, tipo: str = Form("primer"), usuario: str = Form(""),
                motivo: str = Form(""), idea: str = Form("")):
    """Primer mensaje o propuesta de colaboración: un borrador para mandar a mano, con sus dos seguimientos."""
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    try:
        a = comunidad.escribir_dm(neg, tipo, usuario, motivo, idea)
    except (ValueError, ErrorIA) as e:
        return _volver(negocio_id, "comunidad", str(e), "mensajes")
    return _volver(negocio_id, "aprobaciones", f"Mensaje listo en Aprobaciones ({a['ref']}): lo mandas tú.")


@router.post("/negocios/{negocio_id}/comunidad/comentarios")
def ordenar_comentarios(request: Request, negocio_id: int, texto: str = Form(""), publicacion_id: int = Form(0),
                        traer: str = Form("")):
    """Los comentarios de un post propio (pegados o, si se pide, traídos con Apify): ordenados y con sus respuestas."""
    from ..connectors.apify import ErrorApify
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    post = next((p for p in comentarios.publicaciones_propias(negocio_id, 100) if p["id"] == publicacion_id), None)
    try:
        lista = comentarios.traer(post["url"]) if traer == "1" and post else comentarios.leer_pegados(texto)
        a = comentarios.ordenar(neg, lista, post=post["url"] if post else "", palabra=(post or {}).get("palabra_clave") or "")
    except (ValueError, ErrorIA, ErrorApify) as e:
        return _volver(negocio_id, "comunidad", str(e), "comentarios")
    return _volver(negocio_id, "aprobaciones", f"Comentarios ordenados ({a['ref']}): copia las respuestas que quieras.")


@router.post("/negocios/{negocio_id}/comunidad/guias/{guia_id}")
def editar_guia(request: Request, negocio_id: int, guia_id: int, titulo: str = Form(""), contenido: str = Form(""),
                enlace_externo: str = Form(""), pedir_email: str = Form("")):
    _propio(request, negocio_id)
    g = next((x for x in comunidad.guias(negocio_id) if x["id"] == guia_id), None)
    if not g:
        return _volver(negocio_id, "comunidad", "Esa guía no existe.")
    if enlace_externo.strip() and not enlace_externo.strip().startswith("https://"):
        return _volver(negocio_id, "comunidad", "El enlace externo tiene que empezar por https://", f"guia-{guia_id}")
    comunidad.guardar_guia(negocio_id, g["palabra"], titulo or g["titulo"], contenido, enlace_externo=enlace_externo,
                           pedir_email=pedir_email == "1")
    return _volver(negocio_id, "comunidad", "Guía guardada.", f"guia-{guia_id}")


@router.get("/negocios/{negocio_id}/comunidad/contactos.csv")
def contactos_csv(request: Request, negocio_id: int):
    import csv
    import io

    from fastapi.responses import Response
    _propio(request, negocio_id)
    salida = io.StringIO()
    w = csv.writer(salida)
    campos = ["creado", "nombre", "email", "usuario", "plataforma", "origen", "palabra", "temperatura", "utm", "crm"]
    w.writerow(campos)
    for c in comunidad.contactos(negocio_id, 10000):
        w.writerow([c[k] for k in campos])
    return Response(salida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=contactos.csv"})


# ---------------------------------------------------------------- la guía pública (sin cuenta)

@router.get("/g/{token}")
def guia_publica(request: Request, token: str):
    g = comunidad.guia_por_token(token)
    if not g:
        return _pagina(request, "error.html", status_code=404, titulo="No encontrada", mensaje="Esta guía no existe.",
                       compartido=True)
    if g["enlace_externo"]:
        return RedirectResponse(g["enlace_externo"], status_code=302)
    if not request.query_params.get("enviado") and not request.query_params.get("error"):
        comunidad.visita(token)  # volver tras dejar el correo no cuenta como otra visita
    neg = db.negocio(g["negocio_id"])
    return _pagina(request, "guia_publica.html", guia=g, bloques=comunidad.bloques(g["contenido"]),
                   marca=neg["nombre"] if neg else "", compartido=True,
                   enviado=request.query_params.get("enviado") == "1", utm=str(request.url.query or ""))


@router.post("/g/{token}")
def guia_correo(request: Request, token: str, nombre: str = Form(""), email: str = Form(""), utm: str = Form(""),
                acepto: str = Form("")):
    g = comunidad.guia_por_token(token)
    if not g or not auth.email_valido(email.strip()) or acepto != "1":
        return RedirectResponse(f"/g/{token}?error=1", status_code=303)
    comunidad.correo_desde_guia(g, nombre=nombre, email=email, utm=utm)
    return RedirectResponse(f"/g/{token}?enviado=1", status_code=303)


# ---------------------------------------------------------------- Aprendizaje: resultados

@router.get("/negocios/{negocio_id}/resultados")
def ver_resultados(request: Request, negocio_id: int, resultado: str = "x"):
    u, neg, inf = _espacio(request, negocio_id)
    aprendizaje.actualizar(neg)
    posts = aprendizaje.mis_posts(negocio_id)
    resultado = resultado if resultado in ("x", "envios", "seguidores_mil") else "x"
    return _pagina(request, "resultados.html", vista="resultados", posts=posts,
                   funciona=aprendizaje.que_funciona(posts, resultado), resultado=resultado,
                   horas=aprendizaje.mapa_horas(posts), postmortems=aprendizaje.postmortems(negocio_id),
                   ritmo=aprendizaje.ritmo(negocio_id), embudo=aprendizaje.embudo(negocio_id),
                   competencia=aprendizaje.frente_a_competencia(negocio_id),
                   informe_semana=aprendizaje.ultimo_informe(negocio_id),
                   objetivo=kit_marca.leer(negocio_id)["objetivo"], OBJETIVOS=aprendizaje.OBJETIVOS,
                   DIMENSIONES=aprendizaje.DIMENSIONES, VEREDICTOS=aprendizaje.VEREDICTOS, MIN_N=aprendizaje.MIN_N,
                   token_web=aprendizaje.token_web(negocio_id), url_publica=config.URL_PUBLICA,
                   **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/resultados/objetivo")
def guardar_objetivo(request: Request, negocio_id: int, metrica: str = Form("leads"), valor: float = Form(10)):
    _propio(request, negocio_id)
    if metrica not in aprendizaje.OBJETIVOS:
        metrica = "leads"
    kit_marca.cambiar(negocio_id, objetivo={"metrica": metrica, "valor": max(0.0, valor)})
    return _volver(negocio_id, "resultados", "Objetivo guardado.", "objetivo")


@router.post("/negocios/{negocio_id}/resultados/informe")
def pedir_informe(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    jobs.en_segundo_plano(aprendizaje.informe_semanal, neg)
    return _volver(negocio_id, "resultados", "Preparando el informe de la semana pasada. Recarga en un minuto.", "informe")


@router.post("/w/{token}")
async def evento_de_la_web(request: Request, token: str):
    """Tu web avisa de un clic, un lead, una llamada o una venta (JSON o formulario), con el utm_content del enlace."""
    from fastapi.responses import JSONResponse
    negocio_id = aprendizaje.negocio_por_token_web(token)
    if not negocio_id:
        return JSONResponse({"ok": False}, status_code=404)
    try:
        datos = await request.json() if "json" in (request.headers.get("content-type") or "") else dict(await request.form())
    except ValueError:
        datos = {}
    try:
        importe = float(datos.get("importe") or 0)
    except (TypeError, ValueError):
        importe = 0.0
    ok = aprendizaje.anotar_evento(negocio_id, str(datos.get("tipo") or ""), str(datos.get("utm_content") or ""),
                                   str(datos.get("visitante") or ""), importe)
    return JSONResponse({"ok": ok}, status_code=200 if ok else 400)


# ---------------------------------------------------------------- Vega: hoy, Telegram y avisos

@router.get("/negocios/{negocio_id}/hoy")
def ver_hoy(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    r = jefa.resumen(neg)
    tg = jefa.conexion(negocio_id)
    return _pagina(request, "hoy.html", vista="hoy", r=r, piloto=piloto.ajustes(negocio_id), TAREAS=piloto.TAREAS,
                   pasos=jefa.primeros_pasos(neg),
                   registro_piloto=(estado.leer(negocio_id, piloto.AGENTE).get("registro") or [])[:12], tg_bot=tg.get("bot", ""), tg_chat=bool(tg.get("chat")),
                   tg_enlace=jefa.enlace_de_inicio(negocio_id), avisos=kit_marca.leer(negocio_id)["avisos"],
                   silencio=jefa.en_silencio(negocio_id), carriles={c["id"]: c["nombre"] for c in kit_marca.leer(negocio_id)["carriles"]},
                   **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/hoy/telegram")
def conectar_telegram(request: Request, negocio_id: int, token: str = Form("")):
    _propio(request, negocio_id)
    if not token.strip():
        return _volver(negocio_id, "conectores", "Pega el token que te dio @BotFather.", "telegram")
    try:
        jefa.conectar(negocio_id, token)
    except jefa.telegram.ErrorTelegram as e:
        return _volver(negocio_id, "conectores", str(e), "telegram")
    return _volver(negocio_id, "conectores", "Bot guardado. Ahora pulsa «Abrir mi bot» y dale a Iniciar.", "telegram")


@router.post("/negocios/{negocio_id}/hoy/telegram/comprobar")
def comprobar_telegram(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    jefa.recibir(neg)
    if not jefa.conectado(negocio_id):
        return _volver(negocio_id, "conectores", "Todavía no veo tu mensaje: abre el bot desde el botón y pulsa Iniciar.", "telegram")
    jefa.encolar(negocio_id, f"Mensaje de prueba de {config.APP_NOMBRE}: si lo lees, ya está todo conectado. ✅", prioridad="alta")
    jefa.despachar(negocio_id)
    return _volver(negocio_id, "conectores", "Telegram conectado: te he mandado un mensaje de prueba.", "telegram")


@router.post("/negocios/{negocio_id}/hoy/telegram/quitar")
def quitar_telegram(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    jefa.desconectar(negocio_id)
    return _volver(negocio_id, "conectores", "Telegram desconectado.", "telegram")


@router.post("/negocios/{negocio_id}/hoy/avisos")
def guardar_avisos(request: Request, negocio_id: int, hora_resumen: str = Form("07:30"), silencio_inicio: str = Form(""),
                   silencio_fin: str = Form(""), avisar_aprobaciones: str = Form("")):
    _propio(request, negocio_id)
    valida = lambda h: h if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", h.strip()) else ""  # noqa: E731
    kit_marca.cambiar(negocio_id, avisos={"hora_resumen": valida(hora_resumen) or "07:30",
                                          "silencio_inicio": valida(silencio_inicio), "silencio_fin": valida(silencio_fin),
                                          "avisar_aprobaciones": avisar_aprobaciones == "1"})
    return _volver(negocio_id, "hoy", "Avisos guardados.", "avisos")


@router.post("/negocios/{negocio_id}/hoy/resumen")
def mandar_resumen_ahora(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    if not jefa.conectado(negocio_id):
        return _volver(negocio_id, "hoy", "Conecta Telegram para recibir el resumen en el móvil.")
    jefa.encolar(negocio_id, jefa.texto_resumen(neg), prioridad="alta")
    jefa.despachar(negocio_id)
    return _volver(negocio_id, "hoy", "Resumen enviado a Telegram.")


# ---------------------------------------------------------------- Piloto automático

@router.post("/negocios/{negocio_id}/hoy/piloto")
async def guardar_piloto(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    form = await request.form()
    valida = lambda h, d: h if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(h or "").strip()) else d  # noqa: E731
    try:
        dia = int(form.get("dia_grabacion") or -1)
    except ValueError:
        dia = -1
    kit_marca.cambiar(negocio_id, piloto={
        "activo": form.get("activo") == "1", "hora_escaneo": valida(form.get("hora_escaneo"), "06:00"),
        "hora_plan": valida(form.get("hora_plan"), "07:00"), "dia_grabacion": dia if -1 <= dia <= 6 else -1,
        "tareas": {t: form.get(f"tarea_{t}") == "1" for t in piloto.TAREAS}})
    return _volver(negocio_id, "hoy", "Piloto automático " + ("encendido." if form.get("activo") == "1" else "apagado."),
                   "piloto")


# ---------------------------------------------------------------- Administración: claves y ajustes de la instalación

# Las claves de servicios externos solo se tocan desde Conectores; aquí quedan los ajustes de la instalación.
CLAVES_DE_CONECTORES = ("RADAR_MOTOR", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "APIFY_TOKEN", "YOUTUBE_API_KEY",
                        "ZERNIO_API_KEY", "MANYCHAT_API_KEY", "RADAR_IG_APP_ID", "RADAR_IG_APP_SECRETO")


@router.get("/admin/claves")
def ver_claves(request: Request):
    auth.requiere_admin(request)
    return _pagina(request, "admin_claves.html",
                   claves=[c for c in instalacion.estado() if c["var"] not in CLAVES_DE_CONECTORES])


@router.post("/admin/claves")
async def guardar_claves(request: Request):
    auth.requiere_admin(request)
    form = await request.form()
    hechos = instalacion.guardar({k: str(v) for k, v in form.items()})
    aviso = ("Guardado: " + ", ".join(hechos) + ".") if hechos else "No había nada nuevo que guardar."
    volver = str(form.get("volver") or "")
    if re.fullmatch(r"/negocios/\d+/conectores", volver):
        return RedirectResponse(f"{volver}?aviso={quote(aviso)}#instalacion", status_code=303)
    return RedirectResponse(f"/admin/claves?aviso={quote(aviso)}", status_code=303)


# ---------------------------------------------------------------- Conectores: todas las conexiones con servicios externos

def _final(clave: str | None) -> str:
    """Los 4 últimos caracteres de una clave larga, para reconocerla sin enseñarla."""
    clave = (clave or "").strip()
    return clave[-4:] if len(clave) >= 12 else ""


@router.get("/negocios/{negocio_id}/conectores")
def ver_conectores(request: Request, negocio_id: int):
    """Un solo sitio para conectar Claude, Apify, Zernio, ManyChat y Telegram. Las claves de la instalación solo las
    ve quien administra; las del negocio, su dueño."""
    u, neg, inf = _espacio(request, negocio_id)
    zernio = publicador.conexion(negocio_id)
    tg = jefa.conexion(negocio_id)
    instalacion_ = {c["var"]: c for c in instalacion.estado()}
    return _pagina(request, "conectores.html", vista="conectores",
                   instalacion=instalacion_, MOTORES=instalacion.MOTORES, motor=llm.motor(),
                   claude_code=bool(llm.claude_bin()), ia=llm.disponible(), apify=config.apify_activo(),
                   zernio_conectado=publicador.conectado(negocio_id), zernio_propia=bool(zernio.get("clave")),
                   zernio_perfil=zernio.get("perfil", ""), zernio_comprobado=zernio.get("comprobado", ""),
                   cuentas_redes=publicador.estado_cuentas(negocio_id), manychat=_estado_manychat(negocio_id),
                   tg_bot=tg.get("bot", ""), tg_chat=bool(tg.get("chat")), tg_enlace=jefa.enlace_de_inicio(negocio_id),
                   claves_negocio={v: {**e, "final": _final(claves.del_negocio(negocio_id).get(v))}
                                   for v, e in claves.estado(negocio_id).items()},
                   claves_compartidas=claves.compartidas(), zernio_final=_final(zernio.get("clave")),
                   manychat_final=_final(comunidad.conexion(negocio_id).get("clave")),
                   **_datos_espacio(u, neg, inf))


@router.post("/negocios/{negocio_id}/conectores/claves")
async def guardar_claves_negocio(request: Request, negocio_id: int):
    """Las claves de ESTE negocio (Claude, Apify, YouTube): las usa todo lo que hace su equipo, y el gasto es suyo."""
    _propio(request, negocio_id)
    form = await request.form()
    cambios = {var: str(form.get(var) or "").strip() for var in claves.PROPIAS}
    errores = [e for var, v in cambios.items() if v for e in [claves.comprobar(var, v)] if e]
    if errores:
        return _volver(negocio_id, "conectores", " ".join(errores), "claves")
    quitar = tuple(v for v in form.getlist("quitar") if v in claves.PROPIAS)
    hechos = claves.guardar(negocio_id, cambios, quitar)
    return _volver(negocio_id, "conectores", ("Guardado: " + ", ".join(hechos) + ".") if hechos else
                   "No había nada nuevo que guardar.", "claves")


@router.get("/negocios/{negocio_id}/hoy/vivo")
def sala_en_vivo(request: Request, negocio_id: int):
    """Los datos de la sala de control, para refrescarla cada pocos segundos."""
    from fastapi.responses import JSONResponse
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    return JSONResponse(sala.estado_sala(neg))


# ---------------------------------------------------------------- Onboarding: 8 preguntas, llamada 1 + informe, llamada 2

@router.get("/negocios/{negocio_id}/onboarding")
def ver_onboarding(request: Request, negocio_id: int):
    u, neg, inf = _espacio(request, negocio_id)
    return _pagina(request, "onboarding.html", vista="onboarding", onboarding=llamadas.vista(negocio_id), ia=llm.disponible(),
                   **_datos_espacio(u, neg, inf))


@router.get("/negocios/{negocio_id}/onboarding/estado")
def estado_onboarding(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    v = llamadas.vista(negocio_id)
    return {k: v[k] for k in ("paso", "respondidas", "llamadas", "listas", "extraccion_estado", "extraccion_al_dia",
                              "aprobacion_id", "aplicado")}


@router.post("/negocios/{negocio_id}/onboarding/preguntas")
async def guardar_preguntas_onboarding(request: Request, negocio_id: int):
    _propio(request, negocio_id)
    form = await request.form()
    respuestas = {k: (form.getlist(k) if t.startswith("checks") else form.get(k))
                  for _, _, campos in llamadas.PREGUNTAS for k, _, t in campos if k in form}
    n = llamadas.guardar_preguntas(negocio_id, respuestas)
    return _volver(negocio_id, "onboarding", "Datos guardados.", "preguntas")


@router.post("/negocios/{negocio_id}/onboarding/llamada/{n}")
async def subir_llamada(request: Request, negocio_id: int, n: int, texto: str = Form(""), notas: str = Form(""),
                        archivo: UploadFile | None = File(None)):
    """La transcripción pegada o un archivo: .txt, .md, .vtt, .srt, o el audio o el vídeo de la llamada."""
    from pathlib import Path

    from ..editor.rutas import _guardar_subida
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    if not 1 <= n <= llamadas.MAX_LLAMADAS:
        return _volver(negocio_id, "onboarding", f"Puedes subir hasta {llamadas.MAX_LLAMADAS} llamadas.")
    nombre = (archivo.filename or "") if archivo else ""
    ext = Path(nombre).suffix.lower()
    try:
        if archivo and nombre and ext in llamadas.EXT_AUDIO:
            from .. import limpieza
            sin_espacio = limpieza.puede_subir(negocio_id, getattr(archivo, "size", 0) or 0)
            if sin_espacio:
                return _volver(negocio_id, "onboarding", sin_espacio, f"llamada{n}")
            destino = config.DATA_DIR / f"llamada-{negocio_id}-{n}{ext}"
            if not await _guardar_subida(archivo, destino, 2000):
                return _volver(negocio_id, "onboarding", "El archivo pasa de 2 GB.", f"llamada{n}")
            llamadas._cambiar_llamada(negocio_id, n, estado="transcribiendo", archivo=nombre, error="")
            jobs.en_segundo_plano(llamadas.trabajo_audio, neg, n, destino, nombre, notas)
            return _volver(negocio_id, "onboarding", "Transcribiendo la llamada en este ordenador: puede tardar un rato.",
                           f"llamada{n}")
        if archivo and nombre:
            if ext not in llamadas.EXT_TEXTO:
                return _volver(negocio_id, "onboarding", "Sube la transcripción (.txt, .vtt o .srt) o el audio o vídeo.",
                               f"llamada{n}")
            texto = (await archivo.read(llamadas.MAX_TEXTO * 4)).decode("utf-8", errors="replace")
        llamadas.subir_texto(neg, n, texto, archivo=nombre, notas=notas)
    except ValueError as e:
        return _volver(negocio_id, "onboarding", str(e), f"llamada{n}")
    return _volver(negocio_id, "onboarding", f"Llamada {n} guardada. Cuando estén todas, prepara la ficha y el Kit.",
                   f"llamada{n}")


@router.post("/negocios/{negocio_id}/onboarding/extraer")
def rehacer_extraccion(request: Request, negocio_id: int):
    neg = _propio(request, negocio_id)
    neg.pop("_usuario")
    if not llm.disponible():
        return _volver(negocio_id, "onboarding", "Conecta Claude en Conectores para preparar la ficha y el Kit.")
    if not llamadas.subidas(negocio_id):
        return _volver(negocio_id, "onboarding", "Sube al menos una llamada.", "llamada1")
    llamadas._cambiar(negocio_id, extraccion_estado="preparando")
    jobs.en_segundo_plano(llamadas.trabajo, llamadas.extraer, neg)
    return _volver(negocio_id, "onboarding", "Preparando la ficha y el Kit: te llegarán a Aprobaciones.", "extraer")
