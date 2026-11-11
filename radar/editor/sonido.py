"""Efectos de sonido sintetizados (sin bancos de sonido ni licencias) y la mezcla final de la voz con ellos."""
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

TASA = 48000


def _guardar(muestras: np.ndarray, destino: Path):
    muestras = np.clip(muestras, -1, 1)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TASA)
        w.writeframes((muestras * 32767).astype(np.int16).tobytes())


def golpe(destino: Path):
    """Un impacto grave con un chasquido al principio: para la palabra gigante."""
    t = np.arange(int(TASA * 0.45)) / TASA
    frecuencia = 70 * np.exp(-t * 6) + 38
    grave = np.sin(2 * np.pi * np.cumsum(frecuencia) / TASA) * np.exp(-t * 7.5)
    ruido = np.random.default_rng(1).normal(0, 1, len(t)) * np.exp(-t * 60) * 0.35
    _guardar(0.95 * grave + ruido, destino)


def pop(destino: Path):
    """Un «pop» corto y agudo: para cada elemento de una lista o del gancho."""
    t = np.arange(int(TASA * 0.12)) / TASA
    frecuencia = 950 - 2800 * t
    _guardar(0.55 * np.sin(2 * np.pi * np.cumsum(frecuencia) / TASA) * np.exp(-t * 32), destino)


def barrido(destino: Path):
    """Un «whoosh»: ruido filtrado que sube y baja, para los cambios de plano y la pantalla partida."""
    n = int(TASA * 0.5)
    ruido = np.random.default_rng(2).normal(0, 1, n)
    suave = np.convolve(ruido, np.ones(18) / 18, mode="same")  # quita los agudos más ásperos
    envolvente = np.sin(np.linspace(0, np.pi, n)) ** 2
    _guardar(0.5 * suave / (np.abs(suave).max() or 1) * envolvente, destino)


SONIDOS = {"golpe": golpe, "pop": pop, "barrido": barrido}


def preparar(carpeta: Path) -> dict[str, Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, crear in SONIDOS.items():
        ruta = carpeta / f"{nombre}.wav"
        if not ruta.exists():
            crear(ruta)
        rutas[nombre] = ruta
    return rutas


VOLUMEN = {"golpe": 0.85, "pop": 0.45, "barrido": 0.35}
# −14 LUFS es a lo que dejan el volumen Instagram, TikTok y YouTube: así el reel no suena más bajo que los demás.
OBJETIVO = "I=-14:TP=-1.5:LRA=11"


def medir(video: Path, ffmpeg: str) -> dict | None:
    """Primera pasada del loudnorm: cuánto suena la voz. Con la medida, la segunda pasada ajusta de forma lineal
    (sin «bombear» el volumen). Idea de ai-video-editor (MIT)."""
    try:
        r = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(video), "-map", "0:a:0",
                            "-af", f"loudnorm={OBJETIVO}:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=600)
        datos = json.loads(re.findall(r"\{[^{}]*\}", r.stderr)[-1])
        medida = {k: float(datos[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (IndexError, KeyError, ValueError, json.JSONDecodeError, subprocess.SubprocessError, OSError):
        return None
    return medida if all(abs(v) != float("inf") for v in medida.values()) and medida["input_i"] > -70 else None


def _loudnorm(medida: dict | None) -> str:
    if not medida:
        return f"loudnorm={OBJETIVO}"
    return (f"loudnorm={OBJETIVO}:measured_I={medida['input_i']}:measured_TP={medida['input_tp']}:"
            f"measured_LRA={medida['input_lra']}:measured_thresh={medida['input_thresh']}:"
            f"offset={medida['target_offset']}:linear=true")


def filtro_mezcla(eventos: list[tuple[float, str]], indices: dict[str, int], entrada_voz: str = "0:a",
                  medida: dict | None = None) -> str:
    """El filtro de ffmpeg que deja la voz a un volumen constante y le suma cada sonido en su momento."""
    partes = [f"[{entrada_voz}]{_loudnorm(medida)},aresample=48000[voz]"]
    etiquetas = ["[voz]"]
    for n, (t, nombre) in enumerate(eventos):
        ms = max(0, int(t * 1000))
        partes.append(f"[{indices[nombre]}:a]adelay={ms}:all=1,volume={VOLUMEN.get(nombre, 0.5)}[s{n}]")
        etiquetas.append(f"[s{n}]")
    if len(etiquetas) == 1:
        partes.append("[voz]alimiter=limit=0.95[audio]")
    else:
        partes.append(f"{''.join(etiquetas)}amix=inputs={len(etiquetas)}:normalize=0:duration=first,"
                      f"alimiter=limit=0.95[audio]")
    return ";".join(partes)
