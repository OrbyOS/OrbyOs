"""Control de calidad del reel terminado (punto 8 del MANUAL_EDITOR.md).

Saca lo que hay que mirar antes de entregar: una hoja de contactos a 2 fps, cada transición fotograma a fotograma y
el volumen. Lo que se puede medir lo deja en qa/informe.md; lo que hay que ver con ojos, en imágenes.
"""
import json
import re
import subprocess
from pathlib import Path

LUFS_OBJETIVO = -14.0


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def revisar(reel: Path, trabajo: Path) -> dict:
    qa = trabajo / "qa"
    qa.mkdir(exist_ok=True)
    datos = json.loads((trabajo / "props.json").read_text(encoding="utf-8"))
    planos = datos["planos"]

    columnas = 17
    filas = -(-int(datos["total"] / 15) // columnas) or 1
    _ffmpeg("-i", str(reel), "-vf", f"fps=2,scale=216:-1,tile={columnas}x{filas}", "-frames:v", "1",
            str(qa / "hoja.jpg"))

    # Cada transición y cada borrado de fondo: de 6 fotogramas antes a 12 después.
    momentos = []
    for p in planos:
        if p["entrada"] != "corte":
            momentos.append((p["id"], p["from"]))
        g = p.get("grafico", {})
        if g.get("tipo") == "fondo":
            momentos.append((p["id"] + "-fondo", p["from"] + g["f"]))
    imagenes = []
    for nombre, f in momentos:
        destino = qa / f"transicion_{nombre}.jpg"
        _ffmpeg("-i", str(reel), "-vf", f"select='between(n\\,{max(0, f - 6)}\\,{f + 12})',scale=180:-1,tile=19x1",
                "-vsync", "0", "-frames:v", "1", str(destino))
        imagenes.append(destino.name)

    r = subprocess.run(["ffmpeg", "-i", str(reel), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
    pico = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])

    informe = {
        "duracion": round(datos["total"] / datos["fps"], 2),
        "planos": len(planos),
        "plano_medio": round(datos["total"] / datos["fps"] / len(planos), 2),
        "lufs": lufs, "pico": pico, "volumen_ok": abs(lufs - LUFS_OBJETIVO) <= 1 and pico <= -1.0,
        "imagenes": ["hoja.jpg", *imagenes],
    }
    lineas = [f"# Control de calidad: {reel.name}", "",
              f"- Duración: {informe['duracion']} s en {informe['planos']} planos ({informe['plano_medio']} s de media)",
              f"- Volumen: {lufs} LUFS, pico {pico} dBFS → {'bien' if informe['volumen_ok'] else 'REVISAR'}",
              "", "Mirar con ojos:", "1. hoja.jpg: ¿dos gráficos a la vez? ¿dos planos seguidos iguales?",
              "2. transicion_*.jpg: sin fotogramas negros ni saltos de silueta.",
              "3. Leer los gráficos sin audio: ¿alguno repite la frase literal?"]
    (qa / "informe.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return informe
