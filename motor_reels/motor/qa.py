"""Control de calidad del reel terminado (punto 8 del MANUAL_EDITOR.md).

Saca lo que hay que mirar antes de entregar: una hoja de contactos a 2 fps, cada transición fotograma a fotograma y
el volumen. Lo que se puede medir lo deja en qa/informe.md; lo que hay que ver con ojos, en imágenes.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

LUFS_OBJETIVO = -14.0


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


# Para que Whisper no limpie las muletillas al transcribir el render: un ejemplo de transcripción literal.
PROMPT_LITERAL = "Eh... es, es que, o sea, bueno, eh, la, la idea es esta. Mmm, vale, vale."
CENTRO, TOLERANCIA = 540, 2


def repeticiones_del_render(reel: Path, carpeta: Path) -> tuple[list[dict], list[str]]:
    """Transcribe el render palabra a palabra (literal) y busca palabras repetidas seguidas y arranques en falso
    («pa- paso»). Sin esta comprobación no se entrega (regla del cliente cero, 28/10/2026)."""
    import sys
    import wave

    import numpy as np
    wav = carpeta / "render16k.wav"
    _ffmpeg("-i", str(reel), "-ac", "1", "-ar", "16000", str(wav))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from faster_whisper import WhisperModel
    from radar import config
    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    modelo = WhisperModel(config.WHISPER_MODELO, device="cpu", compute_type="int8")
    segmentos, _ = modelo.transcribe(audio, language=config.IDIOMA, word_timestamps=True, vad_filter=False,
                                     initial_prompt=PROMPT_LITERAL, condition_on_previous_text=False)
    palabras = [{"t": round(x.start, 2), "w": x.word.strip()} for seg in segmentos for x in seg.words]
    wav.unlink(missing_ok=True)
    from .validar import repetidas_en
    limpia = lambda x: re.sub(r"[^\wáéíóúüñ]", "", x.lower())
    texto = [limpia(x["w"]) for x in palabras]
    fallos = [f"{palabras[i]['t']} s: {x}" for i, x in repetidas_en(texto)]
    for i in range(1, len(palabras)):
        a, b = texto[i - 1], texto[i]
        if a and len(a) <= 3 and b.startswith(a) and len(b) > len(a) + 1 and palabras[i - 1]["w"].endswith("-"):
            fallos.append(f"{palabras[i]['t']} s: arranque en falso «{palabras[i - 1]['w']} {b}»")
    return palabras, fallos


def centrado(trabajo: Path, paso: int = 15) -> list[str]:
    """Centro horizontal de todo lo que el motor pone encima del vídeo, medido en fotogramas renderizados con el vídeo
    cambiado por gris (remotion/qa_centrado.mjs): en cada franja (subtítulos y mitad de arriba), el centro de lo que
    no es gris tiene que caer a ±2 px de x=540. Un fotograma cada `paso` (15 = medio segundo)."""
    import numpy as np
    from PIL import Image
    remotion = Path(__file__).resolve().parents[1] / "remotion"
    gris = trabajo / "qa" / "gris.jpg"
    Image.new("RGB", (1080, 1920), (128, 128, 128)).save(gris, quality=98)
    indice = trabajo / "qa" / "centrado.json"
    subprocess.run(["node", "qa_centrado.mjs", str(trabajo / "props.json"), str(trabajo / "public"), str(indice), str(gris), str(paso)],
                   cwd=remotion, check=True, capture_output=True)
    datos = json.loads(indice.read_text(encoding="utf-8"))
    fallos = []
    for foto in datos["fotos"]:
        a = np.asarray(Image.open(foto["ruta"]).convert("RGB")).astype(int)
        encima = np.abs(a - 128).max(axis=2) > 24
        for nombre, (y0, y1) in {"subtítulos": (1270, 1440), "arriba": (230, 1000)}.items():
            m = encima[y0:y1]
            cols = np.where(m.sum(axis=0) > 1)[0]
            if len(cols) < 20:
                continue
            x0, x1 = int(cols.min()), int(cols.max())
            cx = (x0 + x1) / 2
            if abs(cx - CENTRO) > TOLERANCIA:
                fallos.append(f"fotograma {foto['f']}, {nombre}: centro en x={cx:.1f} (de {x0} a {x1})")
    shutil.rmtree(datos["carpeta"], ignore_errors=True)
    gris.unlink(missing_ok=True)
    indice.unlink(missing_ok=True)
    return fallos


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

    palabras, repetidas = repeticiones_del_render(reel, qa)
    (qa / "transcripcion_render.json").write_text(json.dumps(palabras, ensure_ascii=False, indent=1), encoding="utf-8")
    descentrados = centrado(trabajo)

    informe = {
        "duracion": round(datos["total"] / datos["fps"], 2),
        "planos": len(planos),
        "plano_medio": round(datos["total"] / datos["fps"] / len(planos), 2),
        "lufs": lufs, "pico": pico, "volumen_ok": abs(lufs - LUFS_OBJETIVO) <= 1 and pico <= -1.0,
        "imagenes": ["hoja.jpg", *imagenes],
        "repeticiones": repetidas, "descentrados": descentrados,
        "entregable": not repetidas and not descentrados,
    }
    lineas = [f"# Control de calidad: {reel.name}", "",
              f"- Duración: {informe['duracion']} s en {informe['planos']} planos ({informe['plano_medio']} s de media)",
              f"- Volumen: {lufs} LUFS, pico {pico} dBFS → {'bien' if informe['volumen_ok'] else 'REVISAR'}",
              f"- Repeticiones en el render (transcripción literal): {len(repetidas) or 'ninguna'}",
              *[f"  - {x}" for x in repetidas],
              f"- Centrado (±{TOLERANCIA} px de x={CENTRO}): {len(descentrados) or 'todo centrado'}",
              *[f"  - {x}" for x in descentrados[:30]],
              f"- Entregable: {'sí' if informe['entregable'] else 'NO'}",
              "", "Mirar con ojos:", "1. hoja.jpg: ¿dos gráficos a la vez? ¿dos planos seguidos iguales?",
              "2. transicion_*.jpg: sin fotogramas negros ni saltos de silueta.",
              "3. Leer los gráficos sin audio: ¿alguno repite la frase literal?"]
    (qa / "informe.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return informe
