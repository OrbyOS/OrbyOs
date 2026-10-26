"""Paso 5 con el estilo «De editor»: el reel lo monta motor_reels (Remotion) con el kit visual del negocio.

Del editor del SaaS se reutilizan la transcripción, la revisión frase a frase y el encuadre a 9:16; del motor, la
silueta, el render y la mezcla. Solo se extraen los fotogramas de los tramos que se usan.
"""
import json
import subprocess
from pathlib import Path

from motor_reels.motor import montar as motor_montar
from motor_reels.motor import preparar, validar

from .. import config
from ..modules import edicion as motor
from . import montaje
from . import plan_motor

MARGEN = (0.1, 0.25)  # segundos de más antes y después de cada tramo: ningún fotograma que pida el render falta


def _rangos(planos: list[dict]) -> list[tuple[float, float]]:
    rangos = []
    for p in sorted(planos, key=lambda p: p["src"][0]):
        a, b = max(0.0, p["src"][0] - MARGEN[0]), p["src"][1] + MARGEN[1]
        if rangos and a <= rangos[-1][1]:
            rangos[-1] = (rangos[-1][0], max(rangos[-1][1], b))
        else:
            rangos.append((a, b))
    return rangos


def renderizar(montaje_json: Path, salida: Path, *, kit: dict, propias: dict[str, Path] | None = None, paso=None,
               fotogramas: dict | None = None) -> dict:
    """La silueta (si se pasan `fotogramas`: bruto, frames, rangos y recorte) y el render. Con worker de renders
    (config.cola_renders), se encarga y se espera; si no, se hace aquí mismo."""
    from motor_reels import cola
    paso = paso or (lambda texto: None)
    carpeta_cola = config.cola_renders()
    if carpeta_cola:
        encargo = {"montaje": str(montaje_json), "salida": str(salida), "kit": kit,
                   "propias": {k: str(v) for k, v in (propias or {}).items()}, "fotogramas": fotogramas}
        try:
            return cola.esperar(carpeta_cola, cola.encolar(carpeta_cola, encargo), paso=paso)
        except RuntimeError as e:
            raise montaje.ErrorMontaje(f"El render del reel ha fallado: {e}") from e
    avisos = []
    if fotogramas:
        try:
            avisos = preparar.fotogramas_mediapipe(Path(fotogramas["bruto"]), Path(fotogramas["frames"]),
                                                   rangos=fotogramas["rangos"], recorte=fotogramas["recorte"])
        except (RuntimeError, subprocess.CalledProcessError) as e:
            raise montaje.ErrorMontaje(f"No se ha podido recortar la silueta: {e}") from e
    paso("Montando el reel con tu kit visual")
    try:
        hecho = motor_montar.montar(montaje_json, salida, kit=kit, propias=propias)
    except subprocess.CalledProcessError as e:
        raise montaje.ErrorMontaje("El render del reel ha fallado.") from e
    hecho["avisos"] = avisos + (hecho.get("avisos") or [])
    return hecho


def montar(dir_: Path, *, frases: list[dict], palabras: list[dict], montaje_: dict, kit: dict, paso,
           propias: dict[str, Path] | None = None) -> dict:
    bruto = next(iter(sorted(dir_.glob("bruto.*"))), None)
    if not bruto:
        raise montaje.ErrorMontaje("No se encuentra el vídeo subido.")
    if not config.motor_reels_activo():
        raise montaje.ErrorMontaje("El estilo «De editor» no está disponible en este servidor. Elige otro estilo.")
    dims = motor.info(bruto)
    trabajo = dir_ / "motor"
    trabajo.mkdir(exist_ok=True)

    m = {**montaje_, "bruto": str(bruto)}
    errores, avisos = validar.validar(m)
    if errores:
        raise montaje.ErrorMontaje("El plan no cumple las reglas del estilo: " + " ".join(errores[:2]))
    (trabajo / "montaje.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    quedan, _ = plan_motor.material(frases, palabras)
    (trabajo / "transcripcion.json").write_text(json.dumps(
        [{"t": w["start"], "fin": w["end"], "w": w["word"]} for w in quedan], ensure_ascii=False), encoding="utf-8")

    paso("Recortando tu silueta")
    rangos = _rangos(m["planos"])
    recorte = ""
    if abs(dims["ancho"] / dims["alto"] - 9 / 16) > 0.01:
        recorte = montaje.encuadre(bruto, rangos, dims)["crop"]
    for viejo in (trabajo / "frames").glob("*") if (trabajo / "frames").exists() else []:
        viejo.unlink()
    final = dir_ / "final.mp4"
    hecho = renderizar(trabajo / "montaje.json", final, kit=kit, propias=propias, paso=paso,
                       fotogramas={"bruto": str(bruto), "frames": str(trabajo / "frames"), "rangos": rangos,
                                   "recorte": recorte})
    motor.portada(final, dir_ / "portada.jpg")

    m = json.loads((trabajo / "montaje.json").read_text(encoding="utf-8"))  # ya con las imágenes resueltas
    graficos = [p["grafico"]["tipo"] for p in m["planos"] if p.get("grafico")]
    transiciones = [p["entrada"] for p in m["planos"] if p.get("entrada") in ("latigo", "tiras")]
    texto = " ".join(w["word"] for w in quedan)
    return {
        "duracion_original": round(dims["duracion"], 1),
        "duracion_final": round(hecho["duracion"], 1),
        "cortes": len(m["planos"]) - 1,
        "efectos": len(graficos) + len(transiciones),
        "estilo": "editor",
        "velocidad": hecho.get("velocidad", 1.0),
        "revision": {"arreglos": [], "avisos": avisos + hecho.get("avisos", [])},
        "texto": texto[:3000],
    }
