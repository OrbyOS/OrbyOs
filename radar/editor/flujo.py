"""Lo que pasa en cada paso del editor: al subir, al revisar, al preparar el plan, al pedir un cambio y al montar.

Los pasos que tardan (transcribir, el plan, el montaje) van en un hilo aparte; la página va mirando por dónde van.
"""
import json
import shutil
import threading
import traceback
from pathlib import Path

from .. import config, db, gasto, llm
from ..modules import edicion as motor
from . import frases as fr
from . import modelo, montaje, montaje_motor, plan_motor
from . import plan as pl


def en_segundo_plano(funcion, *args):
    import contextvars  # el hilo hereda el negocio en el que se lanza (y sus claves)
    contexto = contextvars.copy_context()
    threading.Thread(target=contexto.run, args=(funcion, *args), daemon=True).start()


def carpeta(edicion_id: int) -> Path:
    return motor.carpeta(edicion_id)


def capturas_dir(edicion_id: int) -> Path:
    c = carpeta(edicion_id) / "capturas"
    c.mkdir(exist_ok=True)
    return c


def capturas(edicion_id: int) -> list[str]:
    return sorted(p.name for p in capturas_dir(edicion_id).iterdir()
                  if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and not p.name.startswith("web_"))


def marca_dir(negocio_id: int) -> Path:
    c = config.MARCAS_DIR / str(negocio_id)
    c.mkdir(parents=True, exist_ok=True)
    return c


def logo(negocio_id: int) -> Path | None:
    nombre = db.marca(negocio_id).get("logo")
    ruta = marca_dir(negocio_id) / nombre if nombre else None
    return ruta if ruta and ruta.exists() else None


def ajustes_de(ed: dict) -> dict:
    """Los ajustes de esta edición: lo recordado en la marca del negocio y, encima, lo cambiado en este reel."""
    from ..agentes import identidad
    marca = db.marca(ed["negocio_id"])
    guardados = {**(marca.get("ajustes") or {}), **({"color": marca["color"]} if marca.get("color") else {})}
    propios = ed["datos"].get("ajustes") or {}
    # La identidad visual del Kit: su tipografía y su color de texto, salvo que este reel ya lleve otros.
    texto = identidad.color_texto(ed["negocio_id"])
    if texto and "color_texto" not in propios:
        guardados["color_texto"] = texto
    tipografia = identidad.tipografia_subtitulos(ed["negocio_id"])
    if tipografia and "fuente" not in (propios.get("subtitulos") or {}):
        guardados["subtitulos"] = {**(guardados.get("subtitulos") or {}), "fuente": f"marca:{tipografia}"}
    # El paquete de movimiento de la marca y, encima, lo que se haya cambiado en este reel.
    movimiento = {**identidad.leer(ed["negocio_id"])["movimiento"], **(propios.get("movimiento") or {})}
    combinados = {**guardados, **propios, "movimiento": movimiento}
    salida = modelo.ajustes(combinados, estilo_competencia=db.estilo(ed["negocio_id"]))
    # «De editor» sin motor disponible para este reel (Monti, o un servidor sin Node): se monta con el estilo natural
    # y la identidad de la marca.
    if modelo.ESTILOS[salida["estilo"]].get("motor") and not modelo.usa_motor(salida, ed.get("modo", ""), ed["datos"]):
        salida = modelo.ajustes({**combinados, "estilo": modelo.ESTILO_SIN_MOTOR},
                                estilo_competencia=db.estilo(ed["negocio_id"]))
    return salida


def palabras(edicion_id: int) -> list[dict]:
    ruta = carpeta(edicion_id) / "palabras.json"
    return json.loads(ruta.read_text()) if ruta.exists() else []


def _paso(edicion_id: int, texto: str):
    db.actualizar_edicion(edicion_id, paso=texto, linea=texto)


def _gasto_ia(ed: dict, concepto: str):
    u = gasto.uso()
    if u.get("llamadas"):
        gid = db.abrir_gasto(usuario_id=ed["datos"].get("usuario_id"), negocio_id=ed["negocio_id"], concepto=concepto,
                             referencia=ed["id"])
        db.cerrar_gasto(gid, u)


# ---------------------------------------------------------------- 1 → 2: subir y preparar la revisión

def procesar(edicion_id: int):
    """Transcribe, parte en frases, elige el trozo (vídeo largo) y marca tomas falsas. Deja la edición en «revisar»."""
    gasto.empezar()
    ed = db.edicion(edicion_id)
    datos, modo, dir_ = ed["datos"], ed["modo"], carpeta(edicion_id)
    bruto = next(iter(sorted(dir_.glob("bruto.*"))), None)
    db.actualizar_edicion(edicion_id, estado="en_curso")
    try:
        if not bruto:
            raise motor.ErrorEdicion("No se encuentra el archivo subido.")
        _paso(edicion_id, "Preparando tu vídeo")
        if modo == "voz":
            duracion = montaje._duracion(bruto)
        else:
            duracion = motor.info(bruto)["duracion"]
        limite = config.MAX_SEGUNDOS_LARGO if modo == "largo" else config.MAX_SEGUNDOS_BRUTO
        if duracion > limite:
            raise motor.ErrorEdicion(f"Dura más de {limite // 60} minutos. "
                                     + ("Para vídeos largos, usa «Recortar un vídeo largo»." if modo != "largo" else ""))
        _paso(edicion_id, "Escuchando la voz")
        wav = dir_ / "voz.wav"
        montaje._ffmpeg(["-i", str(bruto), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        from ..agentes import identidad
        vocabulario = identidad.leer(ed["negocio_id"])["palabras"]
        lista_palabras = motor.corregir_ortografia(motor.transcribir(wav, vocabulario=vocabulario), vocabulario)
        if not lista_palabras:
            wav.unlink(missing_ok=True)
            raise motor.ErrorEdicion("No se ha entendido ninguna palabra. ¿Tiene voz?")
        (dir_ / "palabras.json").write_text(json.dumps(lista_palabras, ensure_ascii=False))
        lista_frases = fr.partir(lista_palabras)
        # Cómo suena cada frase: para elegir el trozo (vídeo largo) y la mejor toma de cada parte (brutos largos).
        if modo == "largo" or duracion > fr.TOMAS_LARGAS:
            try:
                fr.medir_voz(wav, lista_frases, lista_palabras)
            except (OSError, ValueError):
                pass
        wav.unlink(missing_ok=True)
        avisos = []
        if modo == "largo" and llm.disponible():
            _paso(edicion_id, "Buscando el mejor trozo para el reel")
            try:
                trozo = fr.elegir_trozo(lista_frases)
                fr.aplicar_trozo(lista_frases, trozo)
                datos["trozo"] = trozo
            except llm.ErrorIA as e:
                avisos.append(f"No se ha podido elegir el trozo automáticamente ({e}). Quita tú las frases que sobran.")
        if llm.disponible():
            _paso(edicion_id, "Buscando tomas falsas y repeticiones")
            try:
                dentro = [f for f in lista_frases if not f.get("fuera")]
                fr.limpiar(dentro)
            except llm.ErrorIA as e:
                avisos.append(f"No se han podido marcar las tomas falsas ({e}). Revísalas tú.")
        datos.update(frases=lista_frases, duracion=round(duracion, 1), avisos=avisos)
        db.guardar_datos_edicion(edicion_id, datos, fase="revisar")
        db.actualizar_edicion(edicion_id, estado="listo", paso="Listo para revisar")
        _gasto_ia(ed, "edicion_ia")
        if datos.get("automatico"):
            preparar_plan(edicion_id, montar_despues=True)
    except (motor.ErrorEdicion, montaje.ErrorMontaje) as e:
        db.actualizar_edicion(edicion_id, estado="error", paso=str(e), linea=str(e))
    except Exception as e:  # noqa: BLE001
        db.actualizar_edicion(edicion_id, estado="error", paso="Error inesperado al preparar el vídeo",
                              linea=f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=3)}")


# ---------------------------------------------------------------- 2 → 3: el plan

def guardar_revision(edicion_id: int, cambios: dict[str, dict]):
    """Aplica lo que el usuario ha tocado en la revisión: texto corregido y frases quitadas o recuperadas."""
    ed = db.edicion(edicion_id)
    for f in ed["datos"].get("frases", []):
        c = cambios.get(f["id"])
        if not c:
            continue
        if "texto" in c and c["texto"].strip():
            f["texto"] = c["texto"].strip()
        if "quitada" in c:
            f["quitada"] = bool(c["quitada"])
            if not f["quitada"]:
                f["motivo"] = ""
    # Los planos del estilo «De editor» se calculan sobre las palabras que quedan: con otras frases ya no valen.
    ed["datos"].pop("montaje", None)
    db.guardar_datos_edicion(edicion_id, ed["datos"])


def preparar_plan(edicion_id: int, *, montar_despues: bool = False):
    gasto.empezar()
    ed = db.edicion(edicion_id)
    datos = ed["datos"]
    db.actualizar_edicion(edicion_id, estado="en_curso", paso="Preparando el plan bloque a bloque")
    try:
        ajustes = ajustes_de(ed)
        preferencias = db.marca(ed["negocio_id"]).get("preferencias") or []
        if modelo.usa_motor(ajustes, ed["modo"], ed["datos"]):
            datos["montaje"] = _plan_motor(ed, preferencias)
            # Plan clásico sin IA de reserva, por si cambia a otro estilo.
            datos["plan"] = {**pl.basico(datos["frases"], modo=ed["modo"]), "avisos": datos["montaje"]["avisos"]}
            datos.setdefault("ajustes", {})
            db.guardar_datos_edicion(edicion_id, datos, fase="plan")
            db.actualizar_edicion(edicion_id, estado="listo", paso="Plan listo")
            _gasto_ia(ed, "edicion_ia")
            if montar_despues:
                montar(edicion_id)
            return
        try:
            plan = pl.proponer(datos["frases"], modo=ed["modo"], ajustes=ajustes, capturas=capturas(edicion_id),
                               preferencias=preferencias) if llm.disponible() else pl.basico(datos["frases"], modo=ed["modo"])
        except llm.ErrorIA as e:
            plan = pl.basico(datos["frases"], modo=ed["modo"])
            plan["avisos"].insert(0, f"No se ha podido preparar el plan con IA ({e}).")
        datos["plan"] = plan
        datos.setdefault("ajustes", {})
        db.guardar_datos_edicion(edicion_id, datos, fase="plan")
        db.actualizar_edicion(edicion_id, estado="listo", paso="Plan listo")
        _gasto_ia(ed, "edicion_ia")
        if montar_despues:
            montar(edicion_id)
    except Exception as e:  # noqa: BLE001
        db.actualizar_edicion(edicion_id, estado="error", paso="No se ha podido preparar el plan",
                              linea=f"{e.__class__.__name__}: {e}")


def cambiar_bloques(edicion_id: int, cambios: list[dict]):
    """Cambios a mano en el plan: el tipo de cada bloque, su texto, los elementos de una lista o su captura."""
    ed = db.edicion(edicion_id)
    plan = ed["datos"].get("plan") or {"bloques": []}
    por_id = {b["id"]: b for b in plan["bloques"]}
    for c in cambios:
        b = por_id.get(c.get("id"))
        if not b:
            continue
        for clave in ("tipo", "texto", "captura", "web"):
            if clave in c:
                b[clave] = c[clave]
        if "items" in c:
            b["items"] = [x.strip() for x in c["items"] if x.strip()]
    ajustes = ajustes_de(ed)
    ed["datos"]["plan"] = pl.normalizar({**plan, "avisos": []}, ed["datos"]["frases"], modo=ed["modo"],
                                        capturas=capturas(edicion_id), efectos_max=ajustes["efectos_max"],
                                        forzar_gancho=False)
    db.guardar_datos_edicion(edicion_id, ed["datos"])


def cambiar_ajustes(edicion_id: int, nuevos: dict, *, recordar: bool = False):
    ed = db.edicion(edicion_id)
    actuales = ajustes_de(ed)
    combinados = {**actuales, **{k: v for k, v in nuevos.items() if k != "subtitulos"}}
    combinados["subtitulos"] = {**actuales["subtitulos"], **(nuevos.get("subtitulos") or {})}
    ed["datos"]["ajustes"] = modelo.cambios_de_ajustes(modelo.ajustes(combinados))
    db.guardar_datos_edicion(edicion_id, ed["datos"])
    if recordar:
        _recordar(ed["negocio_id"], ajustes=ed["datos"]["ajustes"])


def _recordar(negocio_id: int, *, ajustes: dict | None = None, instruccion: str | None = None):
    if ajustes and ajustes.get("movimiento"):  # el movimiento vive en la identidad visual del Kit
        from ..agentes import identidad
        identidad.cambiar_movimiento(negocio_id, ajustes["movimiento"])
    m = db.marca(negocio_id)
    if ajustes:
        recordado = (m.get("ajustes") or {}).get("estilo")
        m["ajustes"] = {k: v for k, v in ajustes.items() if k not in ("logo", "movimiento")}
        # Si la marca eligió «De editor» y este reel salió con el estilo de reserva, la elección no se pierde.
        if modelo.ESTILOS.get(recordado, {}).get("motor") and ajustes.get("estilo") == modelo.ESTILO_SIN_MOTOR:
            m["ajustes"]["estilo"] = recordado
        m["color"] = ajustes.get("color") or m.get("color")
    if instruccion:
        m["preferencias"] = list(dict.fromkeys([*(m.get("preferencias") or []), instruccion]))[-10:]
    db.guardar_marca(negocio_id, m)


def pedir_cambio(edicion_id: int, instruccion: str, *, recordar: bool = False) -> str:
    """«Dile lo que quieres»: Claude cambia el plan y los ajustes. Devuelve el resumen de lo que ha cambiado."""
    gasto.empezar()
    ed = db.edicion(edicion_id)
    ajustes = ajustes_de(ed)
    if modelo.usa_motor(ajustes, ed["modo"], ed["datos"]):
        actual = (ed["datos"].get("montaje") or {}).get("por_palabras")
        ed["datos"]["montaje"] = _plan_motor(ed, [], instruccion=instruccion, actual=actual)
        resumen = ed["datos"]["montaje"]["resumen"] or "Hecho."
        ed["datos"].setdefault("cambios", []).append({"pedido": instruccion, "resumen": resumen})
        db.guardar_datos_edicion(edicion_id, ed["datos"])
        if recordar:
            _recordar(ed["negocio_id"], instruccion=instruccion)
        _gasto_ia(ed, "edicion_ia")
        return resumen
    plan, nuevos, resumen = pl.pedir_cambio(instruccion, plan=ed["datos"]["plan"], ajustes=ajustes,
                                            frases=ed["datos"]["frases"], modo=ed["modo"],
                                            capturas=capturas(edicion_id))
    ed["datos"]["plan"] = plan
    ed["datos"]["ajustes"] = modelo.cambios_de_ajustes(modelo.ajustes(nuevos))
    ed["datos"].setdefault("cambios", []).append({"pedido": instruccion, "resumen": resumen})
    db.guardar_datos_edicion(edicion_id, ed["datos"])
    if recordar:
        _recordar(ed["negocio_id"], ajustes=ed["datos"]["ajustes"], instruccion=instruccion)
    _gasto_ia(ed, "edicion_ia")
    return resumen


# ---------------------------------------------------------------- 3 → 4: montar

def montar(edicion_id: int):
    ed = db.edicion(edicion_id)
    datos = ed["datos"]
    neg = db.negocio(ed["negocio_id"])
    db.guardar_datos_edicion(edicion_id, datos, fase="montando")
    db.actualizar_edicion(edicion_id, estado="en_curso", paso="Empezando el montaje")
    try:
        ajustes = ajustes_de(ed)
        if modelo.usa_motor(ajustes, ed["modo"], ed["datos"]):
            if not datos.get("montaje"):
                _paso(edicion_id, "Preparando los planos")
                datos["montaje"] = _plan_motor(ed, db.marca(ed["negocio_id"]).get("preferencias") or [])
                db.guardar_datos_edicion(edicion_id, datos)
            resultado = montaje_motor.montar(
                carpeta(edicion_id), frases=datos["frases"], palabras=palabras(edicion_id),
                montaje_=datos["montaje"]["segundos"], kit=kit_de(ed, ajustes), propias=material_propio(ed),
                paso=lambda texto: _paso(edicion_id, texto))
            db.guardar_datos_edicion(edicion_id, db.edicion(edicion_id)["datos"], fase="listo")
            db.actualizar_edicion(edicion_id, estado="listo", paso="Listo", resultado=resultado,
                                  linea=f"Listo: {resultado['duracion_final']} s, {resultado['efectos']} efectos")
            return
        resultado = montaje.montar(
            carpeta(edicion_id), modo=ed["modo"], palabras=palabras(edicion_id), frases=datos["frases"],
            plan=datos["plan"] if (datos.get("plan") or {}).get("bloques") else pl.basico(datos["frases"], modo=ed["modo"]),
            ajustes=ajustes,
            capturas_dir=capturas_dir(edicion_id), logo=logo(ed["negocio_id"]), nombre=neg["nombre"] if neg else "",
            paso=lambda texto: _paso(edicion_id, texto))
        db.guardar_datos_edicion(edicion_id, db.edicion(edicion_id)["datos"], fase="listo")
        db.actualizar_edicion(edicion_id, estado="listo", paso="Listo", resultado=resultado,
                              linea=f"Listo: {resultado['duracion_final']} s, {resultado['efectos']} efectos")
    except (montaje.ErrorMontaje, motor.ErrorEdicion, llm.ErrorIA) as e:
        db.guardar_datos_edicion(edicion_id, db.edicion(edicion_id)["datos"], fase="plan")
        db.actualizar_edicion(edicion_id, estado="error", paso=str(e), linea=str(e))
    except Exception as e:  # noqa: BLE001
        db.guardar_datos_edicion(edicion_id, db.edicion(edicion_id)["datos"], fase="plan")
        db.actualizar_edicion(edicion_id, estado="error", paso="Error inesperado al montar",
                              linea=f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=4)}")


def kit_de(ed: dict, ajustes: dict) -> dict:
    """El kit del motor de reels, sacado de la identidad visual del Kit del negocio."""
    from ..agentes import identidad
    return identidad.kit_motor(ed["negocio_id"], ajustes["color"])


def material_propio(ed: dict) -> dict[str, Path]:
    """Fotos y capturas propias del cliente para las imágenes reales del estilo «De editor»: las fotos y los diseños
    de su Kit visual (por su nombre) y las capturas subidas a este reel (por su archivo)."""
    from ..agentes import identidad
    ident = identidad.leer(ed["negocio_id"])
    salida = {}
    for entrada in ident["fotos"] + ident["disenos"]:
        ruta = identidad.ruta(ed["negocio_id"], entrada["archivo"])
        if ruta and ruta.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            salida[entrada.get("nombre") or entrada["archivo"]] = ruta
    for nombre in capturas(ed["id"]):
        salida[nombre] = capturas_dir(ed["id"]) / nombre
    return salida


def _plan_motor(ed: dict, preferencias: list[str], *, instruccion: str = "", actual: dict | None = None) -> dict:
    """Los planos del estilo «De editor»: con IA si hay clave; si no (o si falla), el plan automático."""
    from ..agentes import identidad
    datos = ed["datos"]
    bruto = next(iter(sorted(carpeta(ed["id"]).glob("bruto.*"))), None)
    # Reel de un bruto con varios (Monti): su gancho puede estar fuera de su tramo (manual, 0 bis).
    from ..agentes import kit as kit_marca
    comun = {"bruto": str(bruto or ""), "kit": f"negocio-{ed['negocio_id']}",
             "gancho": (datos.get("reel") or {}).get("gancho"),
             "emojis": kit_marca.leer(ed["negocio_id"])["voz"].get("emojis", "nunca")}
    if llm.disponible():
        try:
            return plan_motor.proponer(datos["frases"], palabras(ed["id"]), preferencias=preferencias,
                                       instruccion=instruccion, actual=actual, propias=list(material_propio(ed)),
                                       nunca=identidad.leer(ed["negocio_id"])["nunca"], **comun)
        except llm.ErrorIA as e:
            if instruccion:
                raise
            plan = plan_motor.basico(datos["frases"], palabras(ed["id"]), **comun)
            plan["avisos"].insert(0, f"No se han podido preparar los planos con IA ({e}).")
            return plan
    return plan_motor.basico(datos["frases"], palabras(ed["id"]), **comun)


def lanzar_procesar(edicion_id: int):
    en_segundo_plano(procesar, edicion_id)


def lanzar_plan(edicion_id: int):
    en_segundo_plano(preparar_plan, edicion_id)


def lanzar_montaje(edicion_id: int):
    en_segundo_plano(montar, edicion_id)


def borrar_capturas_web(edicion_id: int):
    for p in capturas_dir(edicion_id).glob("web_*"):
        p.unlink(missing_ok=True)


def copiar_logo(negocio_id: int, origen: Path, extension: str) -> str:
    nombre = f"logo{extension}"
    shutil.copy(origen, marca_dir(negocio_id) / nombre)
    return nombre
