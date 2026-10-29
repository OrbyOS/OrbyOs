"""Control de calidad de un vídeo con motion graphics, antes de entregarlo.

Uso (desde producto/app):
    .venv/bin/python generacion_videos/herramientas/revisar.py <video.mp4> <props.json> [--hoja carpeta]

Mide lo que se puede medir (volumen, ritmo, rótulos, emoticonos, planos demasiado cortos o largos, capas sin aire
entre ellas) y da una nota automática sobre 10. Deja la hoja de contactos a 2 fps para la revisión a ojo, que es la
otra mitad de la nota (ver MANUAL.md, «Control de calidad»). Sirve para el explicativo y para el vídeo a cámara.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EMOTICONO = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
MAX_PALABRAS_ROTULO = 6


def volumen(video: Path) -> tuple[float, float]:
    """Volumen integrado (LUFS) y pico real (dBTP)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    resumen = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", resumen)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", resumen)
    return (float(i.group(1)) if i else 0.0), (float(p.group(1)) if p else 0.0)


def duracion(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def hoja(video: Path, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = carpeta / f"{video.stem}_hoja.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "fps=2,scale=180:-1,tile=10x8",
                    "-frames:v", "1", str(salida)], check=True)
    return salida


# Contraste del texto blanco con lo que tiene detrás (relación de WCAG). Texto grande y negrita: 3 como mínimo; 4,5, bien.
CONTRASTE_MIN, CONTRASTE_BIEN = 3.0, 4.5
W, H, ANCHO_TITULO = 1080, 1920, 900  # el título va centrado (x 540), como en ConCara.tsx


def fotograma(video: Path, t: float):
    """El fotograma en t segundos como matriz RGB (0-1)."""
    import numpy as np
    crudo = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(crudo, dtype=np.uint8).reshape(H, W, 3) / 255.0


def caja_clave(k: dict, centro: dict) -> tuple[int, int, int, int]:
    """Dónde cae una palabra clave (x0, y0, x1, y1), con la misma geometría que ClaveJunto en ConCara.tsx."""
    cy = centro.get("y", 0.34) * H
    lugar = k.get("lugar") or "arriba"
    hueco = 0 if lugar == "arriba" else ((850 - (centro.get("x", 0.5) * W + 200)) if lugar == "der" else centro.get("x", 0.5) * W - 290)
    if hueco and hueco / (len(k["texto"]) * 0.62) < 80:
        hueco, lugar = 0, "arriba"
    if lugar == "arriba":
        tam = 150 if len(k["texto"]) <= 14 else 128  # el de la serif, el más alto de los dos
        texto = k["texto"].replace("*", "")
        lineas = max(1, -(-len(texto) * 0.5 * tam // ANCHO_TITULO))
        top = max(250, cy - 470)
        return (W - ANCHO_TITULO) // 2, int(top), (W + ANCHO_TITULO) // 2, int(top + lineas * tam)
    x0 = 60 if lugar == "izq" else int(centro.get("x", 0.5) * W + 200)
    return x0, int(cy - 60), int(x0 + hueco), int(cy + 40)


def contraste(img, caja: tuple[int, int, int, int]) -> float:
    """Relación de contraste del blanco con el fondo de esa zona (se descartan las letras, que son lo más claro)."""
    import numpy as np
    x0, y0, x1, y1 = caja
    zona = img[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3)
    lin = np.where(zona <= 0.04045, zona / 12.92, ((zona + 0.055) / 1.055) ** 2.4)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    fondo = lum[lum < 0.75]  # fuera las letras (blanco casi puro); queda lo que hay detrás, con su sombra y su velo
    if not fondo.size:
        return 1.0
    return round(1.05 / (float(np.percentile(fondo, 80)) + 0.05), 2)  # lo más claro del fondo es donde se pierde la letra


def textos(props: dict) -> list[str]:
    """Todo el texto que sale en pantalla, para buscar emoticonos."""
    out = [r.get("texto", "") for r in props.get("rotulos", [])] + [w["texto"] for w in props.get("palabras", [])]
    if props.get("titulo"):
        out += [props["titulo"].get("texto", ""), props["titulo"].get("insignia", "")]
    for x in props.get("planos", []) + [c.get("plano", c) for c in props.get("capas", [])]:
        out += [str(v) for v in json.dumps(x, ensure_ascii=False).split('"') if v.strip()]
    return out


def revisar(video: Path, props: dict) -> tuple[float, list[str], list[str]]:
    fallos, avisos = [], []
    dur = duracion(video)
    lufs, pico = volumen(video)
    if abs(lufs + 14) > 1:
        fallos.append(f"Volumen {lufs:.1f} LUFS (tiene que ser -14 ±1)")
    if pico > -1.0:
        fallos.append(f"Pico {pico:.1f} dBTP (como mucho -1,5)")
    for r in props.get("rotulos", []):
        if len(r["texto"].split()) > MAX_PALABRAS_ROTULO:
            fallos.append(f"Rótulo de más de {MAX_PALABRAS_ROTULO} palabras: «{r['texto']}»")
    if any(EMOTICONO.search(t) for t in textos(props)):
        fallos.append("Hay emoticonos en pantalla")
    # Ritmo: lo que cambia en pantalla (planos del explicativo o capas del vídeo a cámara).
    tramos = [(p["inicio"], p["fin"], p["tipo"]) for p in props.get("planos", [])] or \
             [(c["inicio"], c["fin"], c.get("plano", {}).get("tipo") or c["tipo"]) for c in props.get("capas", [])]
    for a, b, tipo in tramos:
        if b - a < 0.8:
            avisos.append(f"Plano «{tipo}» de {b - a:.1f} s en {a:.1f} s: demasiado rápido para leerse")
        if b - a > 7:
            avisos.append(f"Plano «{tipo}» de {b - a:.1f} s en {a:.1f} s: mucho rato sin cambiar")
    for (a1, b1, t1), (a2, b2, t2) in zip(tramos, tramos[1:]):
        divididas = {c["inicio"] for c in props.get("capas", []) if c.get("dividida")}
        if props.get("capas") and 0 < a2 - b1 < 1.0 and a2 not in divididas:  # en la dividida la cara no se va
            avisos.append(f"Solo {a2 - b1:.1f} s de cara entre «{t1}» y «{t2}» ({b1:.1f} s): mejor juntarlas o dar 1 s de aire")
        if t1 == t2 and t1 not in ("pantalla", "venta", "movil"):  # estos siguen la misma escena a propósito
            avisos.append(f"Dos planos «{t1}» seguidos en {a2:.1f} s: parece un salto, no un corte")
    centro = (props.get("cara") or {}).get("centro") or {"x": 0.5, "y": 0.34}
    for k in props.get("claves", []):
        c = contraste(fotograma(video, (k["inicio"] + k["fin"]) / 2), caja_clave(k, centro))
        if c < CONTRASTE_MIN:
            fallos.append(f"Contraste {c}:1 de «{k['texto']}» con su fondo (mínimo {CONTRASTE_MIN})")
        elif c < CONTRASTE_BIEN:
            avisos.append(f"Contraste justo, {c}:1, de «{k['texto']}» (bien a partir de {CONTRASTE_BIEN})")
    palabras = props.get("palabras", [])
    if palabras:
        habla = sum(w["fin"] - w["t"] for w in palabras)
        pps = len(palabras) / max(1.0, palabras[-1]["fin"] - palabras[0]["t"])
        if pps < 2.3:
            avisos.append(f"Ritmo de la voz bajo: {pps:.1f} palabras por segundo")
        if habla / dur < 0.6:
            avisos.append("Más de un 40 % del vídeo sin voz")
    nota = max(0.0, 10 - 1.5 * len(fallos) - 0.5 * len(avisos))
    return round(nota, 1), fallos, avisos


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Control de calidad de un vídeo con motion graphics")
    a.add_argument("video", type=Path)
    a.add_argument("props", type=Path)
    a.add_argument("--hoja", type=Path, help="carpeta para la hoja de contactos (por defecto, la del vídeo)")
    x = a.parse_args()
    nota, fallos, avisos = revisar(x.video, json.loads(x.props.read_text()))
    print(f"Nota automática: {nota}/10 (la otra mitad es la revisión a ojo de la hoja de contactos)")
    for f in fallos:
        print("  FALLO ", f)
    for w in avisos:
        print("  AVISO ", w)
    print("Hoja de contactos:", hoja(x.video, x.hoja or x.video.parent))
    sys.exit(1 if fallos else 0)
