"""Cola de renders: el trabajo pesado del motor (silueta con MediaPipe + render con Remotion) en un proceso aparte.

El servidor web no renderiza: deja un encargo en la carpeta de la cola (compartida, p. ej. /datos/cola_renders) y
espera su resultado. El worker (`python -m motor_reels trabajar <cola>`, su propio contenedor con Node y Chromium)
los hace de uno en uno, por orden de llegada: así un reel nunca ahoga la web ni compite con otro por los núcleos.

Un encargo es un JSON: {montaje, salida, kit, propias, fotogramas?: {bruto, frames, rangos, recorte}}.
Estados por archivo: <id>.json (en cola) → <id>.en_curso → <id>.hecho o <id>.error (con el resultado o el error).
"""
import json
import os
import time
import traceback
import uuid
from pathlib import Path

ESPERA_COLA = 3        # segundos entre vistazos a la cola vacía
ESPERA_MAX = 45 * 60   # lo que espera la web a un encargo antes de darlo por perdido


def encolar(cola: Path, encargo: dict) -> str:
    cola.mkdir(parents=True, exist_ok=True)
    nombre = f"{time.time():.6f}-{uuid.uuid4().hex[:8]}"
    temporal = cola / f"{nombre}.tmp"
    temporal.write_text(json.dumps(encargo, ensure_ascii=False, default=str), encoding="utf-8")
    temporal.rename(cola / f"{nombre}.json")  # aparece entero o no aparece
    return nombre


def delante(cola: Path, nombre: str) -> int:
    """Cuántos encargos hay antes que este (para decirle al cliente cuánto le falta)."""
    return sum(1 for p in cola.glob("*.json") if p.stem < nombre) + len(list(cola.glob("*.en_curso")))


def esperar(cola: Path, nombre: str, *, paso=None, espera_max: float = ESPERA_MAX) -> dict:
    """Bloquea hasta que el worker termina el encargo. Devuelve su resultado o lanza RuntimeError con su error."""
    fin = time.monotonic() + espera_max
    avisado = None
    while time.monotonic() < fin:
        for estado in ("hecho", "error"):
            r = cola / f"{nombre}.{estado}"
            if r.exists():
                datos = json.loads(r.read_text(encoding="utf-8"))
                r.unlink(missing_ok=True)
                if estado == "error":
                    raise RuntimeError(datos.get("error") or "El render ha fallado.")
                return datos
        if paso:
            n = delante(cola, nombre) if (cola / f"{nombre}.json").exists() else 0
            texto = f"En la cola de renders: {n} delante" if n else "Montando el reel con tu kit visual"
            if texto != avisado:
                paso(texto)
                avisado = texto
        time.sleep(1)
    raise RuntimeError("El render tarda demasiado: el worker de renders no responde.")


def ejecutar(encargo: dict) -> dict:
    """Lo que hace el worker con un encargo: la silueta (si hace falta) y el render."""
    from .motor import montar, preparar
    avisos = []
    f = encargo.get("fotogramas")
    if f:
        avisos += preparar.fotogramas_mediapipe(Path(f["bruto"]), Path(f["frames"]),
                                                rangos=[tuple(r) for r in f.get("rangos") or []] or None,
                                                recorte=f.get("recorte") or "")
    propias = {k: Path(v) for k, v in (encargo.get("propias") or {}).items()}
    hecho = montar.montar(Path(encargo["montaje"]), Path(encargo["salida"]), kit=encargo.get("kit"), propias=propias)
    hecho["avisos"] = avisos + (hecho.get("avisos") or [])
    return hecho


def _siguiente(cola: Path) -> Path | None:
    for p in sorted(cola.glob("*.json")):
        destino = p.with_suffix(".en_curso")
        try:
            p.rename(destino)  # atómico: si hubiera dos workers, solo uno se lo queda
            return destino
        except FileNotFoundError:
            continue
    return None


def trabajar(cola: Path, *, una_vez: bool = False):
    """El bucle del worker. Al arrancar, lo que quedó a medias (el contenedor se reinició) vuelve a la cola."""
    cola.mkdir(parents=True, exist_ok=True)
    for viejo in cola.glob("*.en_curso"):
        viejo.rename(viejo.with_suffix(".json"))
    while True:
        actual = _siguiente(cola)
        if not actual:
            if una_vez:
                return
            time.sleep(ESPERA_COLA)
            continue
        nombre = actual.stem
        try:
            resultado = ejecutar(json.loads(actual.read_text(encoding="utf-8")))
            estado, datos = "hecho", resultado
        except Exception as e:  # noqa: BLE001 — un encargo roto no para la cola
            estado, datos = "error", {"error": f"{e.__class__.__name__}: {e}",
                                      "detalle": traceback.format_exc(limit=4)}
        temporal = cola / f"{nombre}.{estado}.tmp"
        temporal.write_text(json.dumps(datos, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(temporal, cola / f"{nombre}.{estado}")
        actual.unlink(missing_ok=True)
        if una_vez:
            return
