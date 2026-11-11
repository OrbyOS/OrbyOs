"""Variantes de un reel para los reels de prueba de Instagram (las publica Publi: publicador.CARPETA_VARIANTES).

El mismo vídeo con un solo cambio cada vez, para ver qué retiene más sin gastar el perfil: otra velocidad (hasta x1,1),
otro color, otro encuadre y, con el estilo «De editor», otro titular de gancho (texto y estilo). Solo se hacen si el
negocio tiene los reels de prueba activados en su Kit, y nunca lo que su identidad visual diga que no quiere.
"""
import copy
import json
import subprocess
from pathlib import Path

from .. import config
from ..modules import edicion as motor

CARPETA = "variantes"   # la misma que publicador.CARPETA_VARIANTES
VELOCIDAD_MAX = 1.1
# Cada variante de imagen: nombre, filtro de ffmpeg y palabras de «nunca» que la descartan.
FILTROS = {
    "color": ("eq=contrast=1.05:saturation=1.12:gamma=0.98", ("etalon", "color", "filtro", "saturac")),
    "encuadre": ("scale=iw*1.08:ih*1.08,crop=1080:1920:(iw-1080)/2:(ih-1920)*0.3", ("zoom", "encuadre", "recorte")),
}


def carpeta(edicion_id: int) -> Path:
    c = motor.carpeta(edicion_id) / CARPETA
    c.mkdir(parents=True, exist_ok=True)
    return c


def _veta(nunca: list[str], palabras: tuple[str, ...]) -> bool:
    return any(p in n.lower() for n in nunca for p in palabras)


def _ffmpeg(origen: Path, destino: Path, video: str, audio: str = ""):
    temporal = destino.with_name(destino.stem + ".tmp.mp4")
    orden = [config.FFMPEG, "-y", "-v", "error", "-i", str(origen), "-vf", video, "-c:v", "libx264", "-crf", "18",
             "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    orden += (["-af", audio, "-c:a", "aac", "-b:a", "160k"] if audio else ["-c:a", "copy"])
    subprocess.run([*orden, str(temporal)], check=True, capture_output=True)
    temporal.replace(destino)


def de_imagen(final: Path, destino: Path, *, velocidad_actual: float = 1.0, nunca: list[str] | None = None) -> list[Path]:
    """Las variantes que salen del vídeo final con ffmpeg (sin volver a montar). Devuelve las hechas."""
    nunca = nunca or []
    hechas = []
    if velocidad_actual < VELOCIDAD_MAX - 0.01:
        v = round(VELOCIDAD_MAX / velocidad_actual, 3)
        salida = destino / "velocidad.mp4"
        _ffmpeg(final, salida, f"setpts=PTS/{v},fps=30", f"atempo={v}")
        hechas.append(salida)
    for nombre, (filtro, vetos) in FILTROS.items():
        if _veta(nunca, vetos):
            continue
        salida = destino / f"{nombre}.mp4"
        _ffmpeg(final, salida, filtro)
        hechas.append(salida)
    return hechas


def titular_alternativo(montaje: dict) -> dict | None:
    """El mismo montaje del motor con el gancho cambiado de estilo (sobre el vídeo ↔ sobre el color del kit) y de
    texto (otra palabra de lo que se dice, la más larga del antetítulo). None si el primer plano no abre con titular."""
    m = copy.deepcopy(montaje)
    p = m["planos"][0]
    g = p.get("grafico") or {}
    if g.get("tipo") != "titular":
        return None
    if p.get("modo") == "recorte":
        p["modo"], p["zoom"] = "real", 1.1
        p.pop("fondo", None)
    else:
        p["modo"], p["fondo"] = "recorte", "luz"
    otras = [k for k in g.get("kicker", []) if len(k) > 3 and k.lower() != g["palabra"].lower()]
    if otras:
        nueva = max(otras, key=len)
        g["kicker"] = [k for k in g["kicker"] if k != nueva]
        g["palabra"] = nueva[:1].upper() + nueva[1:12]
    return m


def hacer(edicion_id: int) -> list[str]:
    """Todas las variantes de una edición terminada. Devuelve los nombres de los archivos hechos."""
    from .. import db
    from ..agentes import identidad
    from ..agentes import kit as kit_marca
    ed = db.edicion(edicion_id)
    if not ed or not kit_marca.leer(ed["negocio_id"])["reels_prueba"]["activa"]:
        return []
    final = motor.carpeta(edicion_id) / "final.mp4"
    if not final.exists():
        return []
    destino = carpeta(edicion_id)
    resultado = ed.get("resultado") or {}
    nunca = identidad.leer(ed["negocio_id"])["nunca"]
    hechas = de_imagen(final, destino, velocidad_actual=float(resultado.get("velocidad") or 1.0), nunca=nunca)
    # Con el motor, además, otro titular de gancho (vuelve a montar: solo si el motor está disponible aquí).
    montaje_json = motor.carpeta(edicion_id) / "motor" / "montaje.json"
    if config.motor_reels_activo() and montaje_json.exists():
        alternativo = titular_alternativo(json.loads(montaje_json.read_text(encoding="utf-8")))
        if alternativo:
            from . import flujo, montaje, montaje_motor
            trabajo = montaje_json.parent / "titular"
            trabajo.mkdir(exist_ok=True)
            (trabajo / "montaje.json").write_text(json.dumps(alternativo, ensure_ascii=False), encoding="utf-8")
            salida = destino / "titular.mp4"
            try:
                montaje_motor.renderizar(trabajo / "montaje.json", salida,
                                         kit=flujo.kit_de(ed, {"color": db.marca(ed["negocio_id"]).get("color") or ""}),
                                         propias=flujo.material_propio(ed))
                hechas.append(salida)
            except (OSError, montaje.ErrorMontaje):
                pass  # sin fotogramas o sin render: quedan las variantes de imagen
    return [h.name for h in hechas]
