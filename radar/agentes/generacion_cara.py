"""Generación de vídeos con la persona a cámara: su grabación leyendo un guion, montada con capas encima.

1. Se transcribe el bruto palabra a palabra (faster-whisper, en local).
2. Cada frase del guion se busca en la transcripción y se queda la última toma buena (si se equivoca, repite la frase
   y sigue): así salen solos los cortes de silencios y tomas falsas, sin cambiar el orden de lo que dice.
3. En las frases que lo piden entra una capa: una grabación de pantalla con zoom o un plano animado del explicativo,
   y los rótulos cortos. Los subtítulos son las palabras de la toma buena.

El montaje se describe en un JSON: {"bruto", "frases": [{"di", "ve"?, "rotulo"?}], "estilo"?}. «ve» es una capa
(`{"tipo": "pantalla", ...}` o `{"tipo": "plano", "plano": {...}}`) o nada (se ve a la persona).
"""
import difflib
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from . import generacion
from . import generacion_sonidos as sonidos

MODELO_WHISPER = "large-v3"
MARGEN_ANTES, MARGEN_DESPUES = 0.06, 0.14  # aire alrededor de cada toma, en segundos


def transcribir(bruto: Path) -> list[dict]:
    """Las palabras del bruto con su tiempo: [{texto, t, fin}]."""
    import numpy as np
    from faster_whisper import WhisperModel
    # El audio se saca con ffmpeg (16 kHz, mono): así no depende de la versión de PyAV.
    crudo = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(bruto), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                           capture_output=True, check=True).stdout
    modelo = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8", cpu_threads=4)
    trozos, _ = modelo.transcribe(np.frombuffer(crudo, dtype=np.float32), language="es", word_timestamps=True, vad_filter=True)
    return [{"texto": w.word.strip(), "t": round(w.start, 3), "fin": round(w.end, 3)} for s in trozos for w in s.words if w.word.strip()]


NUMEROS = dict(enumerate("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince "
                         "dieciseis diecisiete dieciocho diecinueve veinte".split()))


def _norma(w: str) -> str:
    w = unicodedata.normalize("NFD", w.lower())
    w = re.sub(r"[^a-z0-9ñ]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))
    return NUMEROS.get(int(w), w) if w.isdigit() else w  # Whisper escribe «7» donde el guion dice «siete»


def alinear(frases: list[str], palabras: list[dict], minimo: float = 0.62) -> list[tuple[int, int] | None]:
    """Para cada frase, el trozo de palabras [i, j) que mejor la dice. Si la dijo varias veces seguidas (repetir una
    toma), se queda la última que está casi tan bien como la mejor. Las frases se buscan en orden y cerca de la anterior."""
    norm = [_norma(w["texto"]) for w in palabras]
    out, desde = [], 0
    for frase in frases:
        objetivo = [x for x in (_norma(w) for w in frase.split()) if x]
        n = len(objetivo)
        candidatos = []
        for i in range(desde, min(len(norm), desde + 6 * n + 40)):
            for j in range(i + max(1, n - 3), min(len(norm), i + n + 4) + 1):
                r = difflib.SequenceMatcher(None, objetivo, norm[i:j]).ratio()
                if r >= minimo:
                    candidatos.append((r, i, j))
        if not candidatos:
            out.append(None)
            continue
        tope = max(c[0] for c in candidatos)
        _, i, j = max((c for c in candidatos if c[0] >= tope - 0.08), key=lambda c: (c[1], c[0]))
        # Dentro de la toma elegida, el corte que mejor la ajusta (con empate, el que empieza antes y acaba después).
        r, i, j = max((c for c in candidatos if abs(c[1] - i) <= 2), key=lambda c: (round(c[0], 3), -c[1], c[2]))
        # Si el principio de la frase se transcribió mal («si corrijo» → «si corriendo. Dijo»), esas palabras quedan
        # fuera: se recuperan las que van pegadas justo antes, sin pausa, hasta tres.
        k = 0
        while (norm[i] != objetivo[0] and k < 3 and i - 1 >= desde
               and palabras[i]["t"] - palabras[i - 1]["fin"] < 0.3):
            i, k = i - 1, k + 1
        out.append((i, j))
        desde = j
    return out


def _textos_del_guion(frase: str, palabras: list[dict]) -> list[str | None]:
    """Los subtítulos con las palabras del guion (nombres como Monti u Orby bien escritos) y los tiempos de la
    transcripción. Donde no casan palabra por palabra («corriendo. Dijo» por «corrijo»), las del guion ocupan los huecos
    de lo transcrito: si sobran huecos, None (ese tiempo va con la palabra anterior); si faltan, se juntan en el último."""
    guion = [w for w in frase.replace("*", "").replace("^", "").split() if _norma(w)]
    textos: list[str | None] = [w["texto"] for w in palabras]
    sm = difflib.SequenceMatcher(None, [_norma(w) for w in guion], [_norma(w["texto"]) for w in palabras], autojunk=False)
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "delete" and b1 > 0:
            textos[b1 - 1] = f"{textos[b1 - 1]} {' '.join(guion[a1:a2])}"
        elif op == "insert":
            textos[b1:b2] = [None] * (b2 - b1) if b1 > 0 else textos[b1:b2]
        elif op in ("equal", "replace"):
            g = guion[a1:a2]
            hueco = b2 - b1
            textos[b1:b2] = (g + [None] * (hueco - len(g))) if len(g) <= hueco else g[:hueco - 1] + [" ".join(g[hueco - 1:])]
    return textos


def _resolver_encuadres(ve: dict) -> list[dict]:
    """Los encuadres pueden apuntar a una caja medida al grabar ({"t", "caja", "aire"}): se convierten en un rectángulo
    vertical (9:16) centrado en esa caja. {"t", "todo": true} es el vídeo entero; {"t", "x", "y", "w"}, a mano."""
    med = json.loads(Path(ve["medidas"]).read_text()) if ve.get("medidas") else None
    out = []
    for e in ve["encuadres"]:
        if "caja" in e and med:
            momento = ve.get("desde", 0) + e["t"]
            m = min(med["medidas"], key=lambda x: abs(x["t"] - momento))
            c = m["cajas"][e["caja"]]
            w = max(c["w"], c["h"] * 9 / 16) * e.get("aire", 1.5)
            cx, cy = c["x"] + c["w"] / 2, c["y"] + c["h"] / 2 + e.get("bajar", 0)
            out.append({"t": e["t"], "x": round(cx - w / 2, 1), "y": round(cy - w * 16 / 9 / 2, 1), "w": round(w, 1)})
        elif e.get("todo"):
            out.append({"t": e["t"], "x": 0, "y": 0, "w": ve["ancho"]})
        else:
            out.append(e)
    return out


def preparar(montaje: dict, carpeta: Path) -> dict:
    """Corta el bruto por frases, coloca capas y rótulos y devuelve las props de la composición ConCara."""
    publica = carpeta / "publica"
    publica.mkdir(parents=True, exist_ok=True)
    bruto = Path(montaje["bruto"])
    shutil.copyfile(bruto, publica / "cara.mp4")
    for c in montaje["frases"]:
        ve = c.get("ve") or {}
        if ve.get("tipo") == "pantalla":
            shutil.copyfile(ve["fuente"], publica / Path(ve["fuente"]).name)
    shutil.copytree(generacion.AGENTES_DIR, publica / "agentes", dirs_exist_ok=True)
    palabras = montaje.get("palabras") or transcribir(bruto)
    trozos = alinear([f["di"] for f in montaje["frases"]], palabras)
    tramos, salida, capas, rotulos, sonidos_ev, t = [], [], [], [], [], 0.0
    for f, tr in zip(montaje["frases"], trozos):
        if not tr:
            continue  # la frase no está en el bruto: se salta y se avisa al final
        i, j = tr
        desde = max(0.0, palabras[i]["t"] - MARGEN_ANTES)
        hasta = palabras[j - 1]["fin"] + MARGEN_DESPUES
        tramos.append({"desde": round(desde, 3), "hasta": round(hasta, 3)})
        enf = {_norma(w) for w in re.findall(r"\*([^*]+)\*", f["di"]) for w in w.split()}
        for w, texto in zip(palabras[i:j], _textos_del_guion(f["di"], palabras[i:j])):
            if texto is None:
                salida[-1]["fin"] = round(t + w["fin"] - desde, 3)
                continue
            salida.append({"texto": texto, "t": round(t + w["t"] - desde, 3), "fin": round(t + w["fin"] - desde, 3),
                           "enfasis": _norma(w["texto"]) in enf})
        dur = hasta - desde
        ve = f.get("ve")
        if ve:
            capa = {**ve, "inicio": round(t, 3), "fin": round(t + dur, 3)}
            if ve["tipo"] == "pantalla":
                capa["archivo"] = Path(ve["fuente"]).name
                capa["encuadres"] = _resolver_encuadres(ve)
                for k in ("fuente", "medidas"):
                    capa.pop(k, None)
            capas.append(capa)
            sonidos_ev.append({"t": max(0.0, t - 0.1), "archivo": "sfx/barrido.wav", "volumen": 0.35})
        if f.get("rotulo"):
            rotulos.append({"inicio": round(t, 3), "fin": round(t + dur, 3), "texto": f["rotulo"], "arriba": f.get("rotulo_arriba", True)})
            sonidos_ev.append({"t": t + 0.05, "archivo": "sfx/pop.wav", "volumen": 0.4})
        t += dur
    (publica / "sfx").mkdir(exist_ok=True)
    for nombre in ("barrido", "pop", "golpe", "tic"):
        sonidos.escribir_wav(publica / "sfx" / f"{nombre}.wav", sonidos.efecto(nombre) * 0.9)
    faltan = [f["di"] for f, tr in zip(montaje["frases"], trozos) if not tr]
    return {"fps": generacion.FPS, "total": int(t * generacion.FPS) + 1, "cara": {"archivo": "cara.mp4", "tramos": tramos},
            "capas": capas, "rotulos": rotulos, "palabras": salida, "sonidos": sonidos_ev,
            "estilo": {**generacion.ESTILO, **montaje.get("estilo", {})}, "_faltan": faltan}


def render(props: dict, carpeta: Path, salida: Path, concurrencia: int = 2) -> Path:
    """Renderiza con pocos hilos: el Mac no aguanta varios trabajos pesados a la vez."""
    props = {k: v for k, v in props.items() if not k.startswith("_")}
    ruta_props = carpeta / "props.json"
    ruta_props.write_text(json.dumps(props, ensure_ascii=False))
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "ConCara", str(salida.resolve()), f"--props={ruta_props.resolve()}",
                    f"--public-dir={(carpeta / 'publica').resolve()}", f"--concurrency={concurrencia}", "--log=error"], cwd=generacion.REMOTION_DIR, check=True)
    # Volumen de redes (-14 LUFS): el bruto llega con el volumen de cada día y la cámara.
    tmp = salida.with_suffix(".sin_normalizar.mp4")
    salida.replace(tmp)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(salida)], check=True)
    tmp.unlink()
    return salida
