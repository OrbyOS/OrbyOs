"""Producción: de la toma grabada al vídeo aprobado.

- Subes todas las tomas de golpe. Cada una se transcribe y se compara con tus guiones (por las palabras y por el gancho):
  si el parecido es claro, se empareja sola y entra en la cola; si no, te enseña la mejor opción para que la confirmes,
  elijas otro guion o digas que no tiene guion.
- La cola edita una toma detrás de otra (primero las que hay que grabar antes) con el editor de reels en automático:
  cortar, plan, subtítulos y montaje con su revisión de calidad.
- Un bruto largo (varias partes, 3-5 minutos) puede dar más de un reel: Claude elige los tramos que se sostienen solos y
  cada uno se monta como su propia edición («Reel 2 de 3 · …»), con el mismo bruto. Si solo da para uno, sale uno.
- Cuando está, te llega a «Listo para ti». Con «Necesita cambios» fijas notas en momentos del vídeo y notas generales: el
  editor hace la versión siguiente (v2, v3…) con ellas. Con «Se ve bien», queda aprobado para publicar.
"""
import copy
import os
import shutil
import threading
import traceback
from datetime import datetime

from .. import claves, db, llm
from ..editor import flujo
from ..editor import frases as fr
from ..modules import edicion as motor
from . import estratega, guionista, validador
from . import aprobaciones as ap
from . import kit as kit_marca

AGENTE = "editor"
EMPAREJAR_DESDE = 0.62   # lo seguro que tiene que estar para emparejar solo
MARGEN = 0.12            # y cuánto tiene que ganar al segundo
EMPAREJAR_ESTRUCTURA = 0.5  # con una estructura (temas, no un texto para leer) se habla libre: basta con los temas
SEGUNDOS_MUESTRA = 60

ETAPAS = {"emparejar": "Falta saber su guion", "en_cola": "En cola", "cortando": "Cortando",
          "plan": "Preparando el montaje", "montando": "Subtitulando y montando", "revisar": "Listo para ti",
          "aprobado": "Aprobado", "error": "Se ha parado"}

_cerrojo = threading.Lock()
_trabajando = threading.Event()


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- tomas

def es_toma(ed: dict) -> bool:
    return bool((ed.get("datos") or {}).get("produccion"))


def etapa(ed: dict) -> str:
    p = ed["datos"].get("produccion") or {}
    if p.get("aprobado"):
        return "aprobado"
    if ed["estado"] == "error":
        return "error"
    if p.get("emparejado") == "pendiente":
        return "emparejar"
    if ed["estado"] == "en_cola":
        return "en_cola"
    if ed["fase"] == "procesando":
        return "cortando"
    if ed["fase"] in ("revisar", "plan"):
        return "plan"
    if ed["fase"] == "montando":
        return "montando"
    return "revisar" if ed["fase"] == "listo" and ed["estado"] == "listo" else "en_cola"


def tomas(negocio_id: int) -> list[dict]:
    salida = []
    for ed in db.ediciones_de(negocio_id):
        if es_toma(ed):
            ed["etapa"] = etapa(ed)
            ed["etapa_nombre"] = ETAPAS[ed["etapa"]]
            ed["toma"] = ed["datos"]["produccion"]
            salida.append(ed)
    return salida


def _guardar(edicion_id: int, **cambios) -> dict:
    ed = db.edicion(edicion_id)
    ed["datos"]["produccion"] = {**(ed["datos"].get("produccion") or {}), **cambios}
    db.guardar_datos_edicion(edicion_id, ed["datos"])
    return ed["datos"]["produccion"]


def crear_toma(negocio_id: int, titulo: str, usuario_id: int | None) -> int:
    return db.crear_edicion(negocio_id, titulo[:120], {}, modo="camara", datos={
        "usuario_id": usuario_id, "automatico": False,
        "produccion": {"emparejado": "", "version": 1, "notas": [], "creado": _ahora()}})


# ---------------------------------------------------------------- emparejar con su guion

def candidatos(negocio_id: int) -> list[dict]:
    """Guiones aprobados cuya pieza aún no tiene vídeo."""
    con_video = {t["toma"].get("guion_id") for t in tomas(negocio_id) if t["toma"].get("guion_id")}
    return [g for g in guionista.guiones(negocio_id, estados=("aprobado",)) if g["id"] not in con_video]


def parecido(dicho: str, guion: str) -> float:
    """De 0 a 1: cuánto de lo que se dice en la toma está en el guion, con más peso para el gancho."""
    d, g = validador.normal(dicho).split(), validador.normal(guion).split()
    if not d or not g:
        return 0.0
    palabras_d, palabras_g = {w for w in d if len(w) > 3}, {w for w in g if len(w) > 3}
    if not palabras_d or not palabras_g:
        return 0.0
    cuerpo = len(palabras_d & palabras_g) / len(palabras_d)
    gancho_d, gancho_g = set(d[:15]), set(g[:15])
    gancho = len(gancho_d & gancho_g) / max(1, len(gancho_g))
    return round(0.65 * cuerpo + 0.35 * gancho, 2)


def es_estructura(texto: str) -> bool:
    """Escri entrega estructuras («Idea: …», bloques numerados, «Cierre: …»), no un guion para leer."""
    return validador.normal((texto or "").lstrip()[:10]).startswith("idea")


def _raices(texto: str) -> set[str]:
    return {w[:5] for w in validador.normal(texto).split() if len(w) > 4}


def parecido_estructura(dicho: str, estructura: str) -> float:
    """De 0 a 1: cuántos de los temas de la estructura salen en lo que se dice en toda la toma (las palabras con
    contenido, por su raíz: «vender», «vendes» y «ventas» cuentan igual)."""
    temas, dichas = _raices(estructura), _raices(dicho)
    return round(len(temas & dichas) / len(temas), 2) if temas and dichas else 0.0


def emparejar(negocio_id: int, dicho: str, completo: str = "") -> dict:
    """La mejor opción y si es lo bastante clara para emparejar sola. Las estructuras se comparan con toda la toma."""
    def nota(g):
        if es_estructura(g["texto"]):
            return parecido_estructura(completo or dicho, g["texto"]), EMPAREJAR_ESTRUCTURA
        return parecido(dicho, g["texto"]), EMPAREJAR_DESDE
    opciones = sorted(((*nota(g), g) for g in candidatos(negocio_id)), key=lambda x: x[0], reverse=True)
    if not opciones:
        return {"guion_id": None, "parecido": 0.0, "seguro": False}
    mejor, umbral, g = opciones[0]
    segundo = opciones[1][0] if len(opciones) > 1 else 0.0
    return {"guion_id": g["id"], "parecido": mejor, "seguro": mejor >= umbral and mejor - segundo >= MARGEN}


def _dicho(edicion_id: int, segundos: float | None = SEGUNDOS_MUESTRA) -> str:
    return " ".join(w["word"] for w in flujo.palabras(edicion_id) if segundos is None or w["start"] <= segundos)


def asignar(negocio_id: int, edicion_id: int, guion_id: int | None, como: str):
    """Liga la toma a un guion (o a ninguno) y la pone en la cola de edición."""
    g = guionista.guion(negocio_id, guion_id) if guion_id else None
    pieza = estratega.pieza(negocio_id, g["pieza_id"]) if g else None
    _guardar(edicion_id, guion_id=g["id"] if g else None, pieza_id=pieza["id"] if pieza else None, emparejado=como,
             grabar_antes=(pieza or {}).get("grabar_antes") or "")
    if g:
        with db.conexion() as con:
            con.execute("UPDATE ediciones SET titulo = ? WHERE id = ?", (pieza["titulo"][:120], edicion_id))
        estratega.cambiar_estado(negocio_id, [pieza["id"]], "grabada")
    db.actualizar_edicion(edicion_id, estado="en_cola", paso="En cola")
    despertar()


# ---------------------------------------------------------------- la cola

def siguiente() -> dict | None:
    """La toma que toca: las que hay que grabar antes primero; luego, por orden de llegada."""
    with db.conexion() as con:
        filas = con.execute("SELECT id FROM ediciones WHERE estado = 'en_cola' AND datos LIKE '%\"produccion\"%' "
                            "ORDER BY id").fetchall()
    listas = []
    for f in filas:
        ed = db.edicion(f["id"])
        p = ed["datos"].get("produccion") or {}
        if p.get("emparejado") == "pendiente" or p.get("aprobado"):
            continue
        listas.append((p.get("grabar_antes") or "9999", ed["id"], ed))
    return min(listas, key=lambda x: (x[0], x[1]))[2] if listas else None


def procesar_toma(ed: dict):
    """Un paso de la cola para una toma: transcribir y emparejar, o montar si ya tiene guion (o no lo necesita)."""
    p = ed["datos"]["produccion"]
    edicion_id = ed["id"]
    if not flujo.palabras(edicion_id):
        flujo.procesar(edicion_id)  # transcribe, parte en frases y marca tomas falsas; deja la edición en «revisar»
        ed = db.edicion(edicion_id)
        if ed["estado"] == "error":
            return
        if not p.get("emparejado"):
            r = emparejar(ed["negocio_id"], _dicho(edicion_id), _dicho(edicion_id, None))
            if r["seguro"]:
                asignar(ed["negocio_id"], edicion_id, r["guion_id"], "auto")
            else:
                _guardar(edicion_id, emparejado="pendiente", sugerencia=r)
                db.actualizar_edicion(edicion_id, estado="listo", paso="Falta saber su guion")
                return
        else:
            db.actualizar_edicion(edicion_id, estado="en_cola", paso="En cola")
        ed = db.edicion(edicion_id)
    p = ed["datos"]["produccion"]
    if p.get("version", 1) > 1 and ed["datos"].get("plan"):
        # Una versión nueva: se aplican tus notas al plan que ya había y se vuelve a montar.
        aplicar_cambio_pendiente(ed)
        flujo.montar(edicion_id)
    else:
        repartir(ed)  # un bruto largo puede dar varios reels: este se queda con el primero
        # Plan, subtítulos y montaje, con la revisión automática de calidad.
        flujo.preparar_plan(edicion_id, montar_despues=True)
    ed = db.edicion(edicion_id)
    if ed["fase"] == "listo" and ed["estado"] == "listo":
        al_terminar(ed)


# ---------------------------------------------------------------- varios reels de un bruto

def solo_el_tramo(frases: list[dict], reel: dict) -> list[dict]:
    """Las frases de un reel: las de fuera de su tramo, quitadas (se pueden recuperar en la revisión)."""
    salida = copy.deepcopy(frases)
    ids = [f["id"] for f in salida]
    a, b = sorted((ids.index(reel["desde"]), ids.index(reel["hasta"])))
    for i, f in enumerate(salida):
        if not a <= i <= b:
            f.update(quitada=True, motivo="En otro reel de esta toma", fuera=True)
    return salida


def _enlazar(origen, destino):
    """El bruto de la toma, compartido sin ocupar el doble de disco (si el sistema no deja, se copia)."""
    try:
        os.link(origen, destino)
    except OSError:
        shutil.copy(origen, destino)


def repartir(ed: dict) -> dict:
    """Con un bruto largo, los reels que salen de él: la toma queda como el reel 1 y el resto, como tomas hijas que
    entran en la cola. Devuelve la toma (ya con solo su tramo si se ha repartido)."""
    datos, p = ed["datos"], ed["datos"]["produccion"]
    frases = datos.get("frases") or []
    if p.get("serie") or p.get("reel") or not frases or not llm.disponible():
        return ed
    if frases[-1]["fin"] - frases[0]["inicio"] <= fr.TOMAS_LARGAS:
        return ed
    from ..editor import plan_motor
    try:
        g = guionista.guion(ed["negocio_id"], p["guion_id"]) if p.get("guion_id") else None
        estructura = (g or {}).get("texto", "") if es_estructura((g or {}).get("texto", "")) else ""
        reels = plan_motor.mapa_de_reels(frases, estructura=estructura,
                                         ppm=kit_marca.leer(ed["negocio_id"])["voz"]["ppm"])
    except (llm.ErrorIA, ValueError, ImportError):
        reels = []
    ids = {f["id"] for f in frases}
    reels = [r for r in reels if r.get("desde") in ids and r.get("hasta") in ids]
    if len(reels) < 2:
        _guardar(ed["id"], serie={"reels": 1})
        return db.edicion(ed["id"])
    total, base = len(reels), ed["titulo"]
    bruto, palabras = motor.bruto(ed["id"]), motor.carpeta(ed["id"]) / "palabras.json"
    hijas = []
    for n, r in enumerate(reels[1:], 2):
        hija = {k: copy.deepcopy(v) for k, v in datos.items() if k not in ("plan", "montaje", "frases", "produccion")}
        hija["frases"] = solo_el_tramo(frases, r)
        hija["reel"] = {**r, "n": n, "de": total}
        hija["produccion"] = {**{k: v for k, v in p.items() if k not in ("aprobacion_id", "sugerencia")},
                              "version": 1, "notas": [], "padre": ed["id"], "creado": _ahora(),
                              "reel": {"n": n, "de": total, "titulo": r.get("titulo", ""),
                                       "formula": (r.get("gancho_nota") or {}).get("formula")}}
        hid = db.crear_edicion(ed["negocio_id"], f"Reel {n} de {total} · {r.get('titulo') or base}"[:120], {},
                               modo=ed["modo"], datos=hija)
        if bruto:
            _enlazar(bruto, motor.carpeta(hid) / bruto.name)
        if palabras.exists():
            shutil.copy(palabras, motor.carpeta(hid) / "palabras.json")
        db.guardar_datos_edicion(hid, hija, fase="revisar")
        db.actualizar_edicion(hid, estado="en_cola", paso="En cola")
        hijas.append(hid)
    datos["frases"] = solo_el_tramo(frases, reels[0])
    datos["reel"] = {**reels[0], "n": 1, "de": total}
    datos["produccion"] = {**p, "serie": {"reels": total, "hijas": hijas},
                           "reel": {"n": 1, "de": total, "titulo": reels[0].get("titulo", ""),
                                    "formula": (reels[0].get("gancho_nota") or {}).get("formula")}}
    db.guardar_datos_edicion(ed["id"], datos)
    with db.conexion() as con:
        con.execute("UPDATE ediciones SET titulo = ? WHERE id = ?",
                    (f"Reel 1 de {total} · {reels[0].get('titulo') or base}"[:120], ed["id"]))
    return db.edicion(ed["id"])


def al_terminar(ed: dict):
    """El vídeo está montado: a tus aprobaciones (siempre espera, salvo con Monti en piloto automático)."""
    p = ed["datos"]["produccion"]
    g = guionista.guion(ed["negocio_id"], p["guion_id"]) if p.get("guion_id") else None
    avisos = (ed.get("resultado") or {}).get("avisos") or []
    a = ap.pedir(ed["negocio_id"], AGENTE, "video", f"Vídeo v{p.get('version', 1)}: {ed['titulo']}",
                 {"edicion_id": ed["id"], "version": p.get("version", 1), "guion_id": p.get("guion_id"),
                  "palabra_clave": (g or {}).get("palabra_clave", ""), "avisos": avisos[:6]}, clave=True)
    _guardar(ed["id"], aprobacion_id=a["id"])
    # Reels de prueba activados en el Kit: las variantes (otra velocidad, color, encuadre o titular), en segundo plano.
    from . import kit as kit_marca
    if kit_marca.leer(ed["negocio_id"])["reels_prueba"]["activa"]:
        from ..editor import variantes
        flujo.en_segundo_plano(variantes.hacer, ed["id"])


def _trabajador():
    try:
        while True:
            ed = siguiente()
            if not ed:
                return
            db.actualizar_edicion(ed["id"], estado="en_curso", paso="Empezando")
            try:
                with claves.en(ed["negocio_id"]):  # cada toma, con las claves de su negocio
                    procesar_toma(db.edicion(ed["id"]))
            except Exception as e:  # noqa: BLE001 — una toma rota no para la cola
                db.actualizar_edicion(ed["id"], estado="error", paso="Error inesperado en la cola",
                                      linea=f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=3)}")
            ahora = db.edicion(ed["id"])
            if ahora and ahora["estado"] == "en_curso":  # nada debe quedarse «en curso» al salir de aquí
                db.actualizar_edicion(ed["id"], estado="error", paso="Se ha parado sin terminar.")
    finally:
        _trabajando.clear()


def despertar():
    """Arranca la cola si no está ya en marcha. Una sola toma a la vez: la máquina no se satura."""
    with _cerrojo:
        if _trabajando.is_set():
            return
        _trabajando.set()
    flujo.en_segundo_plano(_trabajador)


# ---------------------------------------------------------------- revisión: notas y versiones

def nota_para_el_editor(notas: list[dict], general: str) -> str:
    lineas = [f"En el segundo {n['segundo']:.1f} del vídeo montado: {n['texto']}" for n in notas if n.get("texto")]
    if general.strip():
        lineas.append(general.strip())
    return "\n".join(lineas)


def pedir_cambios(negocio_id: int, edicion_id: int, notas: list[dict], general: str = "") -> bool:
    """«Necesita cambios»: Monti rehace el vídeo con tus notas. El vídeo anterior se guarda como v1, v2…"""
    ed = db.edicion(edicion_id)
    if not ed or ed["negocio_id"] != negocio_id or not es_toma(ed) or not motor.bruto(edicion_id):
        return False  # sin la toma original (se borra a los 14 días de aprobar el vídeo) no hay otra versión
    notas = [{"segundo": max(0.0, float(n.get("segundo") or 0)), "texto": str(n.get("texto") or "").strip()[:300]}
             for n in notas if str(n.get("texto") or "").strip()][:20]
    instruccion = nota_para_el_editor(notas, general)
    if not instruccion:
        return False
    p = ed["datos"]["produccion"]
    version = p.get("version", 1)
    final = motor.carpeta(edicion_id) / "final.mp4"
    if final.exists():
        shutil.copy(final, motor.carpeta(edicion_id) / f"v{version}.mp4")
    if p.get("aprobacion_id"):
        a = ap.aprobacion(p["aprobacion_id"])
        if a and a["estado"] == "pendiente":
            ap.decidir(a["id"], "cambios", nota=instruccion, por="tú")
            return True  # el manejador de «cambios» hace el resto
    _rehacer(ed, instruccion, notas)
    return True


def _rehacer(ed: dict, instruccion: str, notas: list[dict] | None = None):
    p = ed["datos"]["produccion"]
    historial = (p.get("notas") or []) + [{"version": p.get("version", 1), "notas": notas or [], "general": instruccion,
                                           "fecha": _ahora()}]
    _guardar(ed["id"], version=p.get("version", 1) + 1, notas=historial, aprobado=False, aprobacion_id=None,
             pendiente_cambio=instruccion)
    db.actualizar_edicion(ed["id"], estado="en_cola", paso="En cola para la versión siguiente")
    despertar()


def aplicar_cambio_pendiente(ed: dict) -> dict:
    """Antes de montar una versión nueva, Claude aplica tus notas al plan del vídeo."""
    p = ed["datos"]["produccion"]
    if p.get("pendiente_cambio") and llm.disponible():
        try:
            flujo.pedir_cambio(ed["id"], p["pendiente_cambio"])
        except llm.ErrorIA:
            pass
    _guardar(ed["id"], pendiente_cambio="")
    return db.edicion(ed["id"])


@ap.al_aprobar("video")
def _video_aprobado(a: dict):
    edicion_id = a["datos"].get("edicion_id")
    if edicion_id and db.edicion(edicion_id):
        _guardar(edicion_id, aprobado=True, aprobado_el=_ahora(), aprobado_por=a["decidido_por"])


@ap.al_rechazar("video")
def _video_con_cambios(a: dict):
    ed = db.edicion(a["datos"].get("edicion_id") or 0)
    if not ed:
        return
    if a["estado"] == "cambios":
        _rehacer(ed, a["nota"])
    else:
        _guardar(ed["id"], descartado=True)


def versiones(edicion_id: int) -> list[int]:
    return sorted(int(f.stem[1:]) for f in motor.carpeta(edicion_id).glob("v*.mp4") if f.stem[1:].isdigit())


def reintentar(negocio_id: int, edicion_id: int) -> bool:
    ed = db.edicion(edicion_id)
    if not ed or ed["negocio_id"] != negocio_id or not es_toma(ed) or ed["estado"] in ("en_cola", "en_curso"):
        return False
    db.actualizar_edicion(edicion_id, estado="en_cola", paso="En cola")
    despertar()
    return True


def reanudar() -> int:
    """Al arrancar la app: las tomas que se cortaron al cerrarla vuelven a la cola solas."""
    with db.conexion() as con:
        filas = con.execute("SELECT id FROM ediciones WHERE estado = 'error' AND datos LIKE '%\"produccion\"%' AND "
                            "registro LIKE '%Interrumpido: la app se cerró%'").fetchall()
    for f in filas:
        ed = db.edicion(f["id"])
        if ed["fase"] == "listo":
            continue
        with db.conexion() as con:  # que el aviso de corte no la vuelva a marcar la próxima vez
            con.execute("UPDATE ediciones SET registro = replace(registro, 'Interrumpido: la app se cerró', 'Retomada tras cerrar la app') "
                        "WHERE id = ?", (f["id"],))
        db.actualizar_edicion(f["id"], estado="en_cola", paso="En cola (retomada)")
    if filas:
        despertar()
    return len(filas)
