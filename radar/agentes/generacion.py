"""Generación de vídeos: sección nueva, todavía oculta.

Está apagada salvo que el servidor arranque con RADAR_GENERACION=1. Con el interruptor apagado, su página da 404 y
no sale en ningún menú. Como el resto del SaaS, es genérica: lo de cada negocio sale del Kit o del onboarding.

Primer tipo de vídeo, el «explicativo»: sin cámara, voz en off, ilustraciones animadas sobre una mesa y subtítulos
palabra a palabra (1080×1920). El tema va para el público amplio y la venta, en el texto del post. Pasos:
1. guion: escenas con su texto hablado, su etiqueta, su cinta y las ilustraciones (catálogo de
   generacion_videos/remotion/src/ilustraciones.tsx);
2. voz: ElevenLabs con la voz del negocio si hay clave (ELEVENLABS_API_KEY y ELEVENLABS_VOZ); si no, la voz del Mac
   como borrador, sin gastar nada;
3. montaje: Remotion (generacion_videos/remotion) con los tiempos de cada palabra.
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import httpx

REMOTION_DIR = Path(__file__).resolve().parents[2] / "generacion_videos" / "remotion"
FPS = 30
PAUSA = 0.3  # silencio entre escenas, en segundos
# Las voces pagadas se guardan aquí: volver a montar un vídeo con el mismo texto no gasta créditos otra vez.
VOCES_DIR = REMOTION_DIR.parent / "voces"

# Punto de partida: los azules de Orby. Cada negocio lo cambia con su identidad visual.
ESTILO = {"mesa": "#12275c", "veta": "rgba(120, 160, 255, 0.07)", "acento": "#3D7BFF", "texto": "#ffffff",
          "subrayado": "#9cc4ff", "caja": "rgba(5, 10, 28, 0.85)"}


def activa() -> bool:
    """El interruptor de la sección. Se lee en cada petición para poder encenderlo sin tocar código."""
    return os.getenv("RADAR_GENERACION") == "1"


def _duracion(audio: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _palabras_repartidas(texto: str, duracion: float) -> list[dict]:
    """Sin tiempos reales (voz del Mac): reparte la duración por el largo de cada palabra."""
    trozos = texto.split()
    pesos = [len(w) + 1 for w in trozos]
    total, t, out = sum(pesos), 0.0, []
    for w, p in zip(trozos, pesos):
        d = duracion * p / total
        out.append({"texto": w, "t": round(t, 3), "fin": round(t + d, 3)})
        t += d
    return out


def _palabras_de_caracteres(texto: str, inicios: list[float], fines: list[float]) -> list[dict]:
    """Con ElevenLabs: junta los tiempos de cada carácter en palabras."""
    out, actual = [], None
    for c, a, b in zip(texto, inicios, fines):
        if c.isspace():
            if actual:
                out.append(actual)
            actual = None
        elif actual is None:
            actual = {"texto": c, "t": a, "fin": b}
        else:
            actual["texto"] += c
            actual["fin"] = b
    if actual:
        out.append(actual)
    return out


def voz_mac(texto: str, destino: Path) -> list[dict]:
    """Borrador gratis con la voz del sistema (macOS). Devuelve las palabras con tiempos aproximados."""
    aiff = destino.with_suffix(".aiff")
    subprocess.run(["say", "-v", "Mónica", "-r", "190", "-o", str(aiff), texto], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "44100", "-ac", "1", str(destino)], check=True)
    aiff.unlink()
    return _palabras_repartidas(texto, _duracion(destino))


def voz_elevenlabs(texto: str, destino: Path, clave: str, voz: str) -> list[dict]:
    """La voz del negocio en ElevenLabs, con el tiempo exacto de cada carácter."""
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps",
                   headers={"xi-api-key": clave}, timeout=120,
                   json={"text": texto, "model_id": "eleven_multilingual_v2"})
    r.raise_for_status()
    datos = r.json()
    mp3 = destino.with_suffix(".mp3")
    mp3.write_bytes(base64.b64decode(datos["audio_base64"]))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(destino)], check=True)
    mp3.unlink()
    al = datos["alignment"]
    return _palabras_de_caracteres("".join(al["characters"]), al["character_start_times_seconds"],
                                   al["character_end_times_seconds"])


def _voz(texto: str, destino: Path) -> list[dict]:
    clave, voz = os.getenv("ELEVENLABS_API_KEY", ""), os.getenv("ELEVENLABS_VOZ", "")
    if not (clave and voz):
        return voz_mac(texto, destino)
    nombre = hashlib.sha1(f"{voz}\n{texto}".encode()).hexdigest()[:16]
    wav, tiempos = VOCES_DIR / f"{nombre}.wav", VOCES_DIR / f"{nombre}.json"
    if not (wav.exists() and tiempos.exists()):
        VOCES_DIR.mkdir(parents=True, exist_ok=True)
        tiempos.write_text(json.dumps(voz_elevenlabs(texto, wav, clave, voz), ensure_ascii=False))
    shutil.copyfile(wav, destino)
    return json.loads(tiempos.read_text())


def preparar(guion: dict, carpeta: Path) -> dict:
    """Pone la voz a cada escena, junta el audio y devuelve las props del montaje."""
    publica = carpeta / "publica"
    publica.mkdir(parents=True, exist_ok=True)
    escenas, palabras, trozos, t = [], [], [], 0.0
    for i, e in enumerate(guion["escenas"]):
        audio = carpeta / f"escena_{i}.wav"
        ws = _voz(e["texto"], audio)
        d = _duracion(audio) + PAUSA
        palabras += [{"texto": w["texto"], "t": round(t + w["t"], 3), "fin": round(t + w["fin"], 3)} for w in ws]
        escenas.append({"inicio": round(t, 3), "fin": round(t + d, 3), "etiqueta": e.get("etiqueta"),
                        "cinta": e.get("cinta"), "objetos": e.get("objetos", [])})
        trozos.append(audio)
        t += d
    # Cada escena acaba con su pausa: se rellena con silencio al juntar.
    filtro = "".join(f"[{i}:a]apad=pad_dur={PAUSA}[a{i}];" for i in range(len(trozos)))
    filtro += "".join(f"[a{i}]" for i in range(len(trozos))) + f"concat=n={len(trozos)}:v=0:a=1[s]"
    entradas = [x for a in trozos for x in ("-i", str(a))]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *entradas, "-filter_complex", filtro, "-map", "[s]",
                    str(publica / "voz.wav")], check=True)
    for a in trozos:
        a.unlink()
    return {"fps": FPS, "total": int(t * FPS) + 1, "audio": "voz.wav", "titulo": guion["titulo"],
            "escenas": escenas, "palabras": palabras, "estilo": {**ESTILO, **guion.get("estilo", {})}}


def render(props: dict, carpeta: Path, salida: Path) -> Path:
    """Monta el vídeo con Remotion. Necesita Node y las dependencias de generacion_videos/remotion."""
    ruta_props = carpeta / "props.json"
    ruta_props.write_text(json.dumps(props, ensure_ascii=False))
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "Explicativo", str(salida.resolve()),
                    f"--props={ruta_props.resolve()}", f"--public-dir={(carpeta / 'publica').resolve()}"],
                   cwd=REMOTION_DIR, check=True)
    return salida


def generar(guion: dict, carpeta: Path, salida: Path) -> Path:
    """Guion → voz → vídeo. La carpeta de trabajo se borra al acabar."""
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        return render(preparar(guion, carpeta), carpeta, salida)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
