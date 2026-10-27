"""Generación de vídeos: sección nueva, todavía oculta.

Está apagada salvo que el servidor arranque con RADAR_GENERACION=1. Con el interruptor apagado, su página da 404 y
no sale en ningún menú. Como el resto del SaaS, es genérica: lo de cada negocio sale del Kit o del onboarding.

Primer tipo de vídeo, el «explicativo»: sin cámara, voz en off, planos animados que cambian con cada frase y
subtítulos palabra a palabra (1080×1920). El guion va por escenas; cada escena tiene sus planos, y cada plano, lo que
se dice («di», con *énfasis* entre asteriscos) y lo que se ve («ve», un tipo de generacion_videos/remotion/src/planos.tsx).
Pasos:
1. voz: ElevenLabs con la voz del negocio si hay clave (ELEVENLABS_API_KEY y ELEVENLABS_VOZ); si no, la voz del Mac
   como borrador, sin gastar nada. La voz pagada se guarda y no se vuelve a pagar si el texto no cambia;
2. tiempos: cada plano empieza en su primera palabra; los efectos de sonido caen donde entra cada cosa;
3. montaje: Remotion (generacion_videos/remotion).
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import httpx

from . import generacion_sonidos as sonidos

REMOTION_DIR = Path(__file__).resolve().parents[2] / "generacion_videos" / "remotion"
FPS = 30
# Un render pesado a la vez y con 2 hilos de Remotion como mucho: con más, el Mac se queda sin memoria.
PAUSA = 0.28  # silencio entre escenas, en segundos
# Las voces pagadas se guardan aquí: volver a montar un vídeo con el mismo texto no gasta créditos otra vez.
VOCES_DIR = REMOTION_DIR.parent / "voces"
# Los muñecos del equipo (renders de la app): el montaje los lee de su carpeta pública.
AGENTES_DIR = Path(__file__).resolve().parents[1] / "static" / "marca" / "agentes"
# Ajustes de la voz en ElevenLabs: algo más rápida que la natural, para el ritmo de un reel.
AJUSTES_VOZ = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True, "speed": 1.08}

# Punto de partida: los azules de Orby. Cada negocio lo cambia con su identidad visual.
ESTILO = {"mesa": "#12275c", "veta": "rgba(120, 160, 255, 0.07)", "acento": "#3D7BFF", "texto": "#ffffff",
          "subrayado": "#9cc4ff", "caja": "rgba(5, 10, 28, 0.85)", "malo": "#ff5d73"}


def activa() -> bool:
    """El interruptor de la sección. Se lee en cada petición para poder encenderlo sin tocar código."""
    return os.getenv("RADAR_GENERACION") == "1"


# ---------------------------------------------------------------- voz

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


def _a_wav(origen: Path, destino: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(origen), "-ar", str(sonidos.SR), "-ac", "1",
                    "-sample_fmt", "s16", str(destino)], check=True)
    origen.unlink()


def voz_mac(texto: str, destino: Path) -> list[dict]:
    """Borrador gratis con la voz del sistema (macOS). Devuelve las palabras con tiempos aproximados."""
    aiff = destino.with_suffix(".aiff")
    subprocess.run(["say", "-v", "Mónica", "-r", "200", "-o", str(aiff), texto], check=True)
    _a_wav(aiff, destino)
    return _palabras_repartidas(texto, _duracion(destino))


def voz_elevenlabs(texto: str, destino: Path, clave: str, voz: str) -> list[dict]:
    """La voz del negocio en ElevenLabs, con el tiempo exacto de cada carácter."""
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps",
                   headers={"xi-api-key": clave}, timeout=120,
                   json={"text": texto, "model_id": "eleven_multilingual_v2", "voice_settings": AJUSTES_VOZ})
    r.raise_for_status()
    datos = r.json()
    mp3 = destino.with_suffix(".mp3")
    mp3.write_bytes(base64.b64decode(datos["audio_base64"]))
    _a_wav(mp3, destino)
    al = datos["alignment"]
    return _palabras_de_caracteres("".join(al["characters"]), al["character_start_times_seconds"],
                                   al["character_end_times_seconds"])


def _voz(texto: str, destino: Path, borrador: bool = False) -> list[dict]:
    clave, voz = os.getenv("ELEVENLABS_API_KEY", ""), os.getenv("ELEVENLABS_VOZ", "")
    if borrador or not (clave and voz):
        return voz_mac(texto, destino)
    nombre = hashlib.sha1(f"{voz}\n{json.dumps(AJUSTES_VOZ, sort_keys=True)}\n{texto}".encode()).hexdigest()[:16]
    wav, tiempos = VOCES_DIR / f"{nombre}.wav", VOCES_DIR / f"{nombre}.json"
    if not (wav.exists() and tiempos.exists()):
        VOCES_DIR.mkdir(parents=True, exist_ok=True)
        tiempos.write_text(json.dumps(voz_elevenlabs(texto, wav, clave, voz), ensure_ascii=False))
    shutil.copyfile(wav, destino)
    return json.loads(tiempos.read_text())


# ---------------------------------------------------------------- tiempos

def _fichas(di: str) -> list[tuple[str, bool, bool]]:
    """Las palabras de lo que se dice, con su énfasis (*palabra* o *varias palabras*) y sus golpes (^palabra: en esa
    palabra entra la siguiente cosa del plano, como el siguiente punto de una lista)."""
    out, dentro = [], False
    for w in di.split():
        golpe = w.startswith("^")
        w = w.lstrip("^")
        empieza, acaba = w.startswith("*"), w.rstrip(".,:;?!»").endswith("*")
        enf = dentro or empieza
        dentro = (dentro or empieza) and not acaba
        out.append((w.replace("*", ""), enf, golpe))
    return out


def _entra_vacio(ve: dict) -> bool:
    """Los planos que no enseñan nada hasta su primer golpe (las cosas entran una a una)."""
    return ve["tipo"] in ("lista", "flujo", "chat", "equipo", "objetos", "versus") or (
        ve["tipo"] == "movil" and ve.get("modo") in ("mensajes", "comentarios"))


def _turnos(n: int, dur: float, parte: float, minimo: float, maximo: float) -> float:
    """El mismo reparto que planos.tsx: cada cuántos fotogramas entra la siguiente cosa."""
    return max(minimo, min(maximo, dur * parte / max(1, n)))


def eventos_de_sonido(planos: list[dict]) -> list[tuple[float, str]]:
    """Dónde cae cada efecto: un barrido en cada cambio de plano y lo propio de cada tipo cuando entra cada cosa."""
    ev: list[tuple[float, str]] = []
    for i, p in enumerate(planos):
        t0, dur = p["inicio"], (p["fin"] - p["inicio"]) * FPS
        en = lambda fr: t0 + fr / FPS  # noqa: E731
        if not i:
            continue  # el primer plano ya sale entero: es la portada
        ev.append((max(0.0, t0 - 0.12), "barrido"))
        tipo = p["tipo"]
        if p.get("golpes"):
            # Con golpes marcados en el guion, cada cosa entra (y suena) en su palabra.
            efecto = {"lista": "tic", "flujo": "tic", "calendario": "tic", "frase": "tic"}.get(tipo, "pop")
            if tipo == "palabra" or (tipo == "frase" and p.get("sello")):
                ev.append((en(1), "golpe"))
            ev += [(en(fr + (8 if tipo in ("lista", "calendario") else 1)), efecto) for fr in p["golpes"]]
            if tipo == "versus":
                ev.append((en(dur * 0.55 + 4), "campana"))
        elif tipo == "objetos":
            ev += [(en(k * 5 + 2), "pop") for k in range(len(p.get("objetos", [])))]
        elif tipo == "equipo":
            n = len(p.get("quienes") or range(7))
            ev += [(en(k * _turnos(n, dur, 0.7, 4, 14) + 2), "pop") for k in range(n)]
        elif tipo == "lista":
            paso = _turnos(len(p.get("items", [])), dur, 0.7, 6, 22)
            ev += [(en(k * paso + 8), "tic") for k in range(len(p.get("items", [])))]
        elif tipo == "cifra":
            ev.append((en(max(12, min(dur * 0.6, 40))), "campana"))
        elif tipo in ("palabra", "robot", "frase", "reloj"):
            ev.append((en(1), "golpe" if tipo == "palabra" else "pop"))
        elif tipo == "chat":
            paso = _turnos(len(p.get("mensajes", [])), dur, 0.8, 10, 30)
            ev += [(en(k * paso + 1), "pop") for k in range(len(p.get("mensajes", [])))]
        elif tipo == "movil" and p.get("modo") == "mensajes":
            paso = _turnos(len(p.get("mensajes", [])), dur, 0.75, 5, 18)
            ev += [(en(k * paso + 1), "tic") for k in range(len(p.get("mensajes", [])))]
        elif tipo == "movil" and p.get("modo") == "perfil":
            paso = _turnos(len(p.get("partes", [])), dur, 0.7, 6, 16)
            ev += [(en(6 + k * paso + 1), "pop") for k in range(len(p.get("partes", [])))]
        elif tipo == "calendario":
            paso = _turnos(len(p.get("marcados", [])), dur, 0.7, 5, 14)
            ev += [(en(8 + k * paso + 1), "tic") for k in range(len(p.get("marcados", [])))]
        elif tipo == "flujo":
            paso = dur * 0.85 / max(1, len(p.get("pasos", [])))
            ev += [(en(k * paso + 1), "tic") for k in range(len(p.get("pasos", [])))]
        elif tipo == "versus":
            ev += [(en(2), "pop"), (en(10), "pop"), (en(dur * 0.55 + 4), "campana")]
        elif tipo == "grafica":
            ev.append((en(max(14, dur * 0.65)), "campana"))
        elif tipo == "cierre":
            ev.append((en(7), "campana"))
        if p.get("sello"):
            ev.append((en((p["golpes"][0] if p.get("golpes") else round(dur * 0.5)) + 2), "golpe"))
    return ev


def _pantalla(ve: dict, publica: Path) -> dict:
    """Plano «pantalla»: copia la grabación a la carpeta pública y convierte los encuadres que apuntan a una caja medida al
    grabar ({"t", "caja", "aire"}) en un rectángulo vertical centrado en ella."""
    fuente = Path(ve["fuente"])
    shutil.copyfile(fuente, publica / fuente.name)
    med = json.loads(Path(ve["medidas"]).read_text()) if ve.get("medidas") else None
    encuadres = []
    for e in ve.get("encuadres", []):
        if "caja" in e and med:
            m = min(med["medidas"], key=lambda x: abs(x["t"] - (ve.get("desde", 0) + e["t"])))
            c = m["cajas"][e["caja"]]
            w = max(c["w"], c["h"] * 9 / 16) * e.get("aire", 1.5)
            cx, cy = c["x"] + c["w"] / 2, c["y"] + c["h"] / 2
            encuadres.append({"t": e["t"], "x": round(cx - w / 2, 1), "y": round(cy - w * 16 / 9 / 2, 1), "w": round(w, 1)})
        else:
            encuadres.append(e)
    return {k: v for k, v in ve.items() if k not in ("fuente", "medidas")} | {"archivo": fuente.name, "encuadres": encuadres}


def preparar(guion: dict, carpeta: Path, borrador: bool = False) -> dict:
    """Pone la voz a cada escena, reparte los planos sobre las palabras, mezcla los efectos y devuelve las props."""
    publica = carpeta / "publica"
    publica.mkdir(parents=True, exist_ok=True)
    shutil.copytree(AGENTES_DIR, publica / "agentes", dirs_exist_ok=True)
    planos, palabras, rotulos, voces, t = [], [], [], [], 0.0
    fin_titulo = 0.0
    for ei, esc in enumerate(guion["escenas"]):
        fichas = [(pi, w, enf, g) for pi, pl in enumerate(esc["planos"]) for w, enf, g in _fichas(pl["di"])]
        audio = carpeta / f"escena_{ei}.wav"
        ws = _voz(" ".join(w for _, w, _, _ in fichas), audio, borrador)
        dur = _duracion(audio)
        voces.append((t, sonidos.leer_wav(audio)))
        audio.unlink()
        # Las palabras de la voz y las del guion casi siempre coinciden una a una; si no, se reparten en proporción.
        idx = (list(range(len(fichas))) if len(ws) == len(fichas)
               else [min(len(fichas) - 1, round(i * len(fichas) / max(1, len(ws)))) for i in range(len(ws))])
        inicios: dict[int, float] = {}
        golpes: dict[int, list[float]] = {}
        for w, j in zip(ws, idx):
            pi, _, enf, g = fichas[j]
            inicios.setdefault(pi, t + w["t"])
            if g:
                golpes.setdefault(pi, []).append(t + w["t"])
            palabras.append({"texto": w["texto"], "t": round(t + w["t"], 3), "fin": round(t + w["fin"], 3), "enfasis": enf})
        for pi, pl in enumerate(esc["planos"]):
            ini = t if pi == 0 else max(t, inicios.get(pi, t) - 0.07)
            if pi in golpes and (ei or pi) and _entra_vacio(pl["ve"]):
                # Un plano que espera a que se nombre su primera cosa no entra vacío: el anterior aguanta hasta entonces
                # (como mucho 2,5 s, para que no se quede quieto).
                ini = max(ini, min(golpes[pi][0] - 0.35, ini + 2.5))
            ve = _pantalla(pl["ve"], publica) if pl["ve"]["tipo"] == "pantalla" else pl["ve"]
            if ve["tipo"] == "recurso":  # vídeo de banco, tratado con el color de la marca
                from . import generacion_banco
                ve = {**ve, "archivo": generacion_banco.preparar_recurso(ve, publica)}
            plano = {**ve, "inicio": round(ini, 3)}
            if pi in golpes and (ei or pi):  # en fotogramas desde el inicio del plano, un poco antes de la palabra
                # (el primer plano del vídeo ya sale entero: es la portada)
                plano["golpes"] = [max(0, round((g - ini) * FPS) - 3) for g in golpes[pi]]
            planos.append(plano)
        fin = t + dur + PAUSA
        if esc.get("rotulo"):
            rotulos.append({"inicio": round(t, 3), "fin": round(fin, 3), "texto": esc["rotulo"]})
        if ei == 0:
            fin_titulo = fin
        t = fin
    for a, b in zip(planos, planos[1:] + [{"inicio": t}]):
        a["fin"] = b["inicio"]
    voz = sonidos.np.zeros(int(t * sonidos.SR) + 1)
    for t0, x in voces:
        i = int(t0 * sonidos.SR)
        voz[i:i + len(x)] += x[:len(voz) - i]
    mezcla = carpeta / "mezcla.wav"
    sonidos.escribir_wav(mezcla, sonidos.mezclar(voz, eventos_de_sonido(planos), t))
    # Volumen de redes (-14 LUFS), con margen para que no sature.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mezcla), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", str(sonidos.SR), str(publica / "audio.wav")], check=True)
    mezcla.unlink()
    return {"fps": FPS, "total": int(t * FPS) + 1, "audio": "audio.wav",
            "titulo": {**guion["titulo"], "fin": round(fin_titulo, 3)}, "planos": planos, "rotulos": rotulos,
            "palabras": palabras, "estilo": {**ESTILO, **guion.get("estilo", {})}}


# ---------------------------------------------------------------- montaje

def render(props: dict, carpeta: Path, salida: Path, escala: float = 1.0) -> Path:
    """Monta el vídeo con Remotion. Necesita Node y las dependencias de generacion_videos/remotion."""
    ruta_props = carpeta / "props.json"
    ruta_props.write_text(json.dumps(props, ensure_ascii=False))
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "Explicativo", str(salida.resolve()),
                    f"--props={ruta_props.resolve()}", f"--public-dir={(carpeta / 'publica').resolve()}",
                    f"--scale={escala}", "--log=error", "--concurrency=2"], cwd=REMOTION_DIR, check=True)
    return salida


def generar(guion: dict, carpeta: Path, salida: Path, borrador: bool = False, escala: float = 1.0) -> Path:
    """Guion → voz y efectos → vídeo. La carpeta de trabajo se borra al acabar."""
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        return render(preparar(guion, carpeta, borrador), carpeta, salida, escala)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == "__main__":
    # python -m radar.agentes.generacion guion.json salida.mp4 [--borrador] [--escala 0.5]
    import argparse
    import tempfile

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    a = argparse.ArgumentParser(description="Monta un vídeo explicativo a partir de su guion")
    a.add_argument("guion", type=Path)
    a.add_argument("salida", type=Path)
    a.add_argument("--borrador", action="store_true", help="voz del Mac, sin gastar créditos")
    a.add_argument("--escala", type=float, default=1.0)
    x = a.parse_args()
    generar(json.loads(x.guion.read_text()), Path(tempfile.mkdtemp(prefix="generacion-")), x.salida, x.borrador, x.escala)
    print(x.salida)
