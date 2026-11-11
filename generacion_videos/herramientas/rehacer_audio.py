"""Rehace solo la pista de audio de un explicativo ya montado, con la voz en caché, y la vuelve a meter en el vídeo sin
tocar la imagen (-c:v copy). Para arreglos del sonido que no cambian los tiempos de los planos.

Uso: .venv/bin/python generacion_videos/herramientas/rehacer_audio.py <guion.json> <video_origen.mp4> <video_salida.mp4>
También: ... --comprobar <video.mp4>   (solo el detector de arranques secos)
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))
# El turno pesado único del Mac, si existe (TURNO_PESADO o, por defecto, Edicion/herramientas de la carpeta de la marca).
TURNO = os.getenv("TURNO_PESADO") or str(APP.parents[2] / "Edicion" / "herramientas" / "turno_pesado.sh")


def arranques_secos(video: Path) -> list[float]:
    from radar.agentes.generacion import arranques_secos as detector
    return detector(video)


def rehacer(guion_json: Path, origen: Path, salida: Path) -> None:
    from dotenv import load_dotenv
    load_dotenv(APP / ".env")
    from radar.agentes import generacion as g
    guion = json.loads(guion_json.read_text())
    with tempfile.TemporaryDirectory() as d:
        props = g._preparar_a_ritmo(guion, Path(d))
        cuadros = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                                      "stream=nb_read_packets", "-of", "csv=p=0", str(origen)], capture_output=True, text=True).stdout)
        if abs(cuadros - props["total"]) > 1:
            raise SystemExit(f"los tiempos han cambiado ({cuadros} fotogramas en el vídeo, {props['total']} ahora): hay que volver a montarlo")
        subprocess.run([*(["bash", TURNO] if Path(TURNO).exists() else []), "ffmpeg", "-y", "-loglevel", "error", "-i", str(origen), "-i", str(Path(d) / "publica" / "audio.wav"),
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", str(salida)], check=True)


if __name__ == "__main__":
    if sys.argv[1] == "--comprobar":
        m = arranques_secos(Path(sys.argv[2]))
        print(f"arranques secos: {len(m)}", m)
    else:
        rehacer(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
        m = arranques_secos(Path(sys.argv[3]))
        print(f"{sys.argv[3]} · arranques secos: {len(m)}", m)
