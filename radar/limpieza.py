"""El disco: lo que más pesa son los vídeos. Se borra solo en cuanto deja de hacer falta, y cada cuenta tiene un tope.

Lo que se guarda de cada toma de Producción, y cuándo se borra:
- Los intermedios del montaje (la pista de subtítulos con transparencia, la base, la versión con gráficos, el audio
  para transcribir, los efectos): en cuanto el vídeo está montado. Se vuelven a generar si hace falta otra versión.
- Las versiones anteriores (v1, v2…): al aprobar el vídeo.
- El bruto (la toma que subiste): DIAS_BRUTO días después de aprobarlo. Sin bruto ya no se puede pedir otra versión.
- El vídeo final: DIAS_FINAL días después de su última publicación; si nunca se publica, DIAS_SIN_PUBLICAR días después
  de aprobarlo. Mientras tenga una publicación programada, nunca.
- Lo que se quedó a medias o se descartó: DIAS_ABANDONO días después de subirlo.
Las transcripciones, los planes y las métricas (texto, poco peso) se quedan siempre.
"""
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from . import config, db

CUOTA_GB = float(os.getenv("RADAR_CUOTA_GB", "10"))         # por cuenta (negocio)
MIN_LIBRE_GB = float(os.getenv("RADAR_MIN_LIBRE_GB", "5"))  # por debajo, no se aceptan subidas nuevas
DIAS_BRUTO = 14
DIAS_FINAL = 30
DIAS_SIN_PUBLICAR = 60
DIAS_ABANDONO = 30
INTERMEDIOS = ("base.mp4", "con_graficos.mp4", "subtitulos.mov", "subtitulos.txt", "voz.wav", "vacio.png", "cierre.png",
               "fondo.png", "logo_esquina.png")
CARPETAS_INTERMEDIAS = ("subs", "efectos", "sonidos")
CADA = timedelta(hours=6)
_ultima: datetime | None = None


def _gb(n: int | float) -> float:
    return round(n / 1024 ** 3, 2)


def tam(ruta: Path) -> int:
    if not ruta.exists():
        return 0
    if ruta.is_file():
        return ruta.stat().st_size
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file())


def _carpeta(edicion_id: int) -> Path:
    return config.EDICIONES_DIR / str(edicion_id)


def uso(negocio_id: int) -> int:
    """Lo que ocupa una cuenta en disco: sus vídeos y su marca (logo, tipografías, fotos)."""
    total = tam(config.MARCAS_DIR / str(negocio_id))
    with db.conexion() as con:
        for f in con.execute("SELECT id FROM ediciones WHERE negocio_id = ?", (negocio_id,)):
            total += tam(_carpeta(f["id"]))
    return total


def libre() -> int:
    return shutil.disk_usage(config.DATA_DIR).free


def puede_subir(negocio_id: int, previsto: int = 0) -> str:
    """Antes de aceptar un archivo grande: vacío si cabe; si no, el motivo para enseñarlo."""
    if libre() - previsto < MIN_LIBRE_GB * 1024 ** 3:
        return "El servidor está casi lleno: ahora mismo no se pueden subir archivos. Avisa a quien lo administra."
    usado = uso(negocio_id)
    if usado + previsto > CUOTA_GB * 1024 ** 3:
        return (f"Has llegado a tu espacio ({_gb(usado)} de {CUOTA_GB:g} GB). Los vídeos ya publicados se borran solos al "
                f"cabo de {DIAS_FINAL} días; también puedes borrar tomas que no vayas a usar.")
    return ""


def resumen(negocio_id: int) -> dict:
    """Para enseñar en la app: lo que ocupa la cuenta y su tope."""
    usado = uso(negocio_id)
    tope = CUOTA_GB * 1024 ** 3
    return {"usado_gb": _gb(usado), "cuota_gb": CUOTA_GB, "por_ciento": min(100, round(100 * usado / tope)) if tope else 100}


# ---------------------------------------------------------------- borrar

def _borrar(ruta: Path) -> int:
    n = tam(ruta)
    if ruta.is_dir():
        shutil.rmtree(ruta, ignore_errors=True)
    elif ruta.exists():
        ruta.unlink(missing_ok=True)
    return n


def intermedios(edicion_id: int) -> int:
    """Lo que solo sirve mientras se monta: se borra en cuanto el vídeo está listo."""
    dir_ = _carpeta(edicion_id)
    return (sum(_borrar(dir_ / n) for n in INTERMEDIOS) + sum(_borrar(dir_ / n) for n in CARPETAS_INTERMEDIAS))


def _fecha(valor: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(str(valor or "")[:19])
    except ValueError:
        return None


def _marcar(ed: dict, **cambios):
    datos = ed["datos"]
    datos["limpieza"] = {**(datos.get("limpieza") or {}), **cambios}
    db.guardar_datos_edicion(ed["id"], datos)


def limpiar_edicion(ed: dict, ahora: datetime) -> int:
    """Aplica las reglas a una edición. Devuelve los bytes liberados."""
    if ed["estado"] in ("en_curso", "en_cola"):
        return 0  # trabajando con ella: no se toca
    dir_ = _carpeta(ed["id"])
    if not dir_.exists():
        return 0
    liberado = 0
    montada = ed.get("fase") == "listo" and (dir_ / "final.mp4").exists()
    if montada:
        liberado += intermedios(ed["id"])
    p = (ed.get("datos") or {}).get("produccion") or {}
    creado = _fecha(ed.get("creado")) or ahora
    aprobado = _fecha(p.get("aprobado_el")) if p.get("aprobado") else None
    if aprobado:
        liberado += sum(_borrar(v) for v in dir_.glob("v*.mp4") if v.stem[1:].isdigit())
        if ahora - aprobado >= timedelta(days=DIAS_BRUTO):
            brutos = list(dir_.glob("bruto.*"))
            if brutos:
                liberado += sum(_borrar(b) for b in brutos)
                _marcar(ed, bruto_borrado=ahora.isoformat(timespec="seconds"))
        with db.conexion() as con:
            pubs = [dict(f) for f in con.execute("SELECT estado, programado FROM publicaciones WHERE edicion_id = ?",
                                                 (ed["id"],))]
        pendiente = any(x["estado"] in ("programada", "tu_publicas") for x in pubs)
        ultima = max((_fecha(x["programado"]) for x in pubs if _fecha(x["programado"])), default=None)
        caduca = (ultima and ahora - ultima >= timedelta(days=DIAS_FINAL)) or (
            not pubs and ahora - aprobado >= timedelta(days=DIAS_SIN_PUBLICAR))
        if not pendiente and caduca and (dir_ / "final.mp4").exists():
            liberado += _borrar(dir_ / "final.mp4") + _borrar(dir_ / "portada.jpg")
            _marcar(ed, final_borrado=ahora.isoformat(timespec="seconds"))
    elif (p.get("descartado") or ed["estado"] == "error" or not montada) and ahora - creado >= timedelta(days=DIAS_ABANDONO):
        # A medias, con error o descartada, y ya vieja: fuera todos los vídeos (se queda lo que es texto).
        liberado += sum(_borrar(f) for f in dir_.iterdir() if f.is_dir() or f.suffix.lower() not in (".json", ".txt"))
        _marcar(ed, abandonada=ahora.isoformat(timespec="seconds"))
    elif not p and montada and ahora - creado >= timedelta(days=DIAS_SIN_PUBLICAR):
        # Una edición suelta (fuera de Producción) terminada hace mucho.
        liberado += sum(_borrar(f) for f in dir_.glob("bruto.*")) + _borrar(dir_ / "final.mp4")
        _marcar(ed, final_borrado=ahora.isoformat(timespec="seconds"))
    return liberado


def limpiar(ahora: datetime | None = None) -> dict:
    """Una pasada por todas las ediciones de todas las cuentas. Devuelve cuánto se ha liberado."""
    ahora = ahora or datetime.now()
    with db.conexion() as con:
        ids = [f["id"] for f in con.execute("SELECT id FROM ediciones")]
    liberado = 0
    for i in ids:
        ed = db.edicion(i)
        if ed:
            try:
                liberado += limpiar_edicion(ed, ahora)
            except OSError:
                continue
    return {"liberado_gb": _gb(liberado), "libre_gb": _gb(libre())}


def si_toca(ahora: datetime | None = None) -> dict | None:
    """Para el bucle de la app: una pasada cada CADA."""
    global _ultima
    ahora = ahora or datetime.now()
    if _ultima and ahora - _ultima < CADA:
        return None
    _ultima = ahora
    return limpiar(ahora)
