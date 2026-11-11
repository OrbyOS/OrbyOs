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
import functools
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
PAUSA = 0.15  # silencio entre escenas, en segundos
# Pausas de oratoria, metidas en el montaje como silencio exacto (la voz no las respeta siempre): tras el gancho, antes
# de una cifra o de un giro (el plano lleva "pausa" o es una cifra) y antes del cierre.
PAUSA_GANCHO, PAUSA_CIFRA, PAUSA_CIERRE = 0.35, 0.15, 0.25
PAUSA_FRASE, PAUSA_COMA = 0.25, 0.12  # el aire que deja quien habla al cerrar una frase o en una coma
PAUSA_PLANO = 0.0  # un respiro cuando cambia lo que se ve
# Ritmo objetivo en palabras por minuto: si un guion sale más rápido, se estiran todas las pausas a la vez (la voz no
# cambia ni se vuelve a pagar) hasta entrar en el margen; si sale lento, se acortan.
RITMO = (182, 192)
PAUSA_MAX = 0.55  # ninguna pausa más larga: más, y suena a frases sueltas
AIRE_MAX = 1.3
AIRE_MIN = 0.7  # nunca menos: sin respirar entre frases suena a robot; antes se acelera la voz
AIRE = 1.0  # multiplicador de todas las pausas; lo ajusta generar()
TEMPO = 1.0  # si ni sin pausas llega al ritmo, la voz se acelera un poco (sin cambiar el tono ni pagarla otra vez)
ANTICIPA = 2  # fotogramas que cada cosa entra antes de su palabra (como un editor: ni a la vez ni tarde)
# Las voces pagadas se guardan aquí: volver a montar un vídeo con el mismo texto no gasta créditos otra vez.
VOCES_DIR = REMOTION_DIR.parent / "voces"
# Los muñecos del equipo (renders de la app): el montaje los lee de su carpeta pública.
AGENTES_DIR = Path(__file__).resolve().parents[1] / "static" / "marca" / "agentes"
# Ajustes de la voz en ElevenLabs: casi a la velocidad natural (a 1.08 iba atropellada; a 0.86 sonaba a robot) y cada
# escena con el texto de la anterior y de la siguiente, para que la entonación siga y no se reinicie.
AJUSTES_VOZ = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True, "speed": 1.0}

# Punto de partida (los azules de Orby, la cuenta de la casa). Cada negocio usa el suyo: estilo_de_marca().
ESTILO = {"mesa": "#12275c", "veta": "rgba(120, 160, 255, 0.07)", "acento": "#3D7BFF", "texto": "#ffffff",
          "subrayado": "#9cc4ff", "caja": "rgba(5, 10, 28, 0.85)", "malo": "#ff5d73"}


def estilo_de_marca(negocio_id: int, publica: Path | None = None) -> dict:
    """El estilo de los vídeos de un negocio, sacado de su identidad visual del Kit (lo mismo que usa Monti): el color
    principal es el acento, el fondo es ese tono muy oscuro, la tipografía de titulares y el logo. Sin identidad, los
    puntos de partida neutros de ESTILO. Con `publica`, copia la tipografía y el logo a la carpeta del render."""
    from . import identidad
    from ..editor import flujo
    ident = identidad.leer(negocio_id)
    if not ident["colores"] and not ident["tipografias"] and not flujo.logo(negocio_id):
        return dict(ESTILO)
    kit = identidad.kit_motor(negocio_id)
    c = kit["colores"]
    principal = ident["colores"][0]["hex"] if ident["colores"] else ESTILO["acento"]
    estilo = {**ESTILO, "acento": principal, "subrayado": c["acento"], "texto": c["texto"],
              "mesa": identidad._hls(principal, 0.2), "caja": c["fondo"] + "D9",
              "veta": "rgba({}, {}, {}, 0.07)".format(*(int(principal[i:i + 2], 16) for i in (1, 3, 5)))}
    if isinstance(kit["fuentes"].get("titular"), str):  # una del catálogo por nombre (la serif de titular, por ejemplo)
        estilo["titular"] = kit["fuentes"]["titular"]
    if publica:
        titular = kit["fuentes"].get("titular")
        if isinstance(titular, dict) and Path(titular["archivo"]).exists():
            destino = publica / ("fuente" + Path(titular["archivo"]).suffix.lower())
            shutil.copyfile(titular["archivo"], destino)
            estilo["fuente"] = destino.name
        logo = flujo.logo(negocio_id)
        if logo:
            shutil.copyfile(logo, publica / ("logo" + logo.suffix.lower()))
            estilo["logo"] = "logo" + logo.suffix.lower()
    return estilo


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


def voz_elevenlabs(texto: str, destino: Path, clave: str, voz: str, antes: str = "", despues: str = "") -> list[dict]:
    """La voz del negocio en ElevenLabs, con el tiempo exacto de cada carácter."""
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps",
                   headers={"xi-api-key": clave}, timeout=120,
                   json={"text": texto, "model_id": os.getenv("ELEVENLABS_MODELO", "eleven_multilingual_v2"), "voice_settings": AJUSTES_VOZ,
                         **({"previous_text": antes} if antes else {}), **({"next_text": despues} if despues else {})})
    r.raise_for_status()
    datos = r.json()
    mp3 = destino.with_suffix(".mp3")
    mp3.write_bytes(base64.b64decode(datos["audio_base64"]))
    _a_wav(mp3, destino)
    al = datos["alignment"]
    return _palabras_de_caracteres("".join(al["characters"]), al["character_start_times_seconds"],
                                   al["character_end_times_seconds"])


# Voz de los explicativos: el clon profesional de la cuenta, buscado por su nombre (ELEVENLABS_VOZ_NOMBRE en el entorno o en
# la configuración del cliente), con el modelo eleven_v4_exp. ELEVENLABS_VOZ_FORZADA, ELEVENLABS_VOZ y ELEVENLABS_MODELO mandan
# sobre esto. Sin nombre, la voz de ELEVENLABS_VOZ.
MODELO_VOZ = "eleven_v4_exp"


@functools.lru_cache(maxsize=1)
def _voz_por_nombre(clave: str, nombre: str) -> str:
    try:
        vs = httpx.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": clave}, timeout=30).json()["voices"]
        return next((v["voice_id"] for v in vs if v["name"] == nombre), "")
    except Exception:
        return ""


def _voz(texto: str, destino: Path, borrador: bool = False, antes: str = "", despues: str = "") -> list[dict]:
    clave = os.getenv("ELEVENLABS_API_KEY", "")
    forzada = os.getenv("ELEVENLABS_VOZ_FORZADA", "")
    nombre_voz = os.getenv("ELEVENLABS_VOZ_NOMBRE", "")
    voz = forzada or (_voz_por_nombre(clave, nombre_voz) if clave and nombre_voz else "") or os.getenv("ELEVENLABS_VOZ", "")
    if borrador or not (clave and voz):
        return voz_mac(texto, destino)
    modelo = os.getenv("ELEVENLABS_MODELO") or (MODELO_VOZ if not forzada and voz != os.getenv("ELEVENLABS_VOZ", "") else "eleven_multilingual_v2")
    os.environ.setdefault("ELEVENLABS_MODELO", modelo)
    # El modelo cuenta en la caché solo si no es el de siempre: así las voces ya pagadas siguen valiendo.
    nombre = hashlib.sha1(f"{voz}\n{json.dumps(AJUSTES_VOZ, sort_keys=True)}\n{antes}\n{texto}\n{despues}{'' if modelo == 'eleven_multilingual_v2' else chr(10) + modelo}".encode()).hexdigest()[:16]
    wav, tiempos = VOCES_DIR / f"{nombre}.wav", VOCES_DIR / f"{nombre}.json"
    if not (wav.exists() and tiempos.exists()):
        VOCES_DIR.mkdir(parents=True, exist_ok=True)
        tiempos.write_text(json.dumps(voz_elevenlabs(texto, wav, clave, voz, antes, despues), ensure_ascii=False))
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


def _dicho(escena: dict) -> str:
    """Lo que se dice en una escena, sin las marcas del guion."""
    return " ".join(w for p in escena["planos"] for w, _, _ in _fichas(p["di"]))


def _pausa(plano: dict, base: float = 0.0) -> float:
    """Silencio antes de un plano: el que pida el guion ("pausa") o el de oratoria según lo que enseña."""
    if "pausa" in plano:
        return float(plano["pausa"])
    tipo = plano["ve"]["tipo"]
    return max(base, PAUSA_CIERRE if tipo == "cierre" else PAUSA_CIFRA if tipo == "cifra" else PAUSA_PLANO)


FUNDIDO = 0.012  # s de fundido en cada borde de un trozo de voz: sin él, el corte suena seco


def _punto_callado(x, i: int, desde: int) -> int:
    """La muestra más callada (ventanas de 10 ms) entre 250 ms antes y 50 ms después de i, sin pasar de «desde»."""
    sr = sonidos.SR
    a, b = max(desde + 1, i - int(0.25 * sr)), min(len(x) - 1, i + int(0.05 * sr))
    if b - a < int(0.02 * sr):
        return max(desde + 1, min(i, len(x) - 1))
    paso = int(0.005 * sr)
    v = int(0.01 * sr)
    mejor, energia = i, float("inf")
    for c in range(a, b - v, paso):
        e = float(sonidos.np.mean(x[c:c + v] ** 2))
        if e < energia:
            mejor, energia = c + v // 2, e
    # Un poco más dentro de la pausa (20 ms): si la palabra empieza con una consonante fuerte, su arranque no se queda fuera.
    return max(desde + 1, mejor - int(0.02 * sr))


def _puerta(x, umbral_db: float = -62):
    """Deja en silencio de verdad lo que está por debajo de -62 dB (el siseo que deja acelerar o frenar la voz), con
    rampas de 5 ms para que la puerta no se oiga."""
    sr = sonidos.SR
    v = sr // 100
    n = len(x) // v
    if n < 3:
        return x
    rms = sonidos.np.sqrt(sonidos.np.mean(x[:n * v].reshape(n, v) ** 2, axis=1))
    abierto = (20 * sonidos.np.log10(rms + 1e-12) > umbral_db).astype(float)
    # Abierta también una ventana antes y después de la voz, para no recortar colas ni arranques.
    abierto = sonidos.np.maximum.reduce([abierto, sonidos.np.roll(abierto, 1), sonidos.np.roll(abierto, -1)])
    mascara = sonidos.np.repeat(abierto, v)
    suave = int(0.005 * sr)
    mascara = sonidos.np.convolve(mascara, sonidos.np.ones(suave) / suave, mode="same")
    y = x.copy()
    y[:len(mascara)] *= mascara
    return y


def _suavizar_arranques(x, ataque: float = 0.035):
    """La voz de ElevenLabs a veces trae silencio digital entre frases y la palabra siguiente arranca de golpe (de nada a
    voz plena en menos de 5 ms): suena a corte. En cada arranque así se pone un ataque de 35 ms, sin tocar lo demás."""
    sr = sonidos.SR
    v = sr // 1000
    n = len(x) // v
    if n < 10:
        return x
    db = 20 * sonidos.np.log10(sonidos.np.sqrt(sonidos.np.mean(x[:n * v].reshape(n, v) ** 2, axis=1)) + 1e-12)
    x = x.copy()
    m = int(ataque * sr)
    rampa = sonidos.np.linspace(0, 1, m) ** 2
    ultimo = -10 ** 9
    for i in range(n - 6):
        if db[i] < -58 and db[i + 1:i + 6].max() > -42 and i - ultimo > 50:
            a = i * v
            b = min(len(x), a + m)
            x[a:b] *= rampa[:b - a]
            ultimo = i
    return x


def _con_fundidos(trozo, entrada: float = 0.025):
    n = min(len(trozo) // 2, int(FUNDIDO * sonidos.SR))
    m = min(len(trozo) // 2, int(entrada * sonidos.SR))
    if n < 2 or m < 2:
        return trozo
    trozo = trozo.copy()
    trozo[:m] *= sonidos.np.linspace(0, 1, m) ** 2
    trozo[-n:] *= sonidos.np.linspace(1, 0, n)
    return trozo


def _con_pausas(x, ws: list[dict], idx: list[int], fichas: list, planos: list[dict], ei: int):
    """Mete silencio dentro de la voz de una escena justo antes de los planos que lo piden y corre las palabras."""
    primera: dict[int, int] = {}
    for k, j in enumerate(idx):
        primera.setdefault(fichas[j][0], k)
    cortes = []
    for pi in range(1, len(planos)):
        p = PAUSA_GANCHO if ei == 0 and pi == 1 else _pausa(planos[pi])
        k = primera.get(pi)
        if p > 0 and k:
            cortes.append((k, min(PAUSA_MAX, p * AIRE)))
    # Y el aire de quien explica al cerrar una frase o en una coma (la voz lo encadena todo casi sin respirar).
    ya = {k for k, _ in cortes}
    for k in range(1, len(ws)):
        fin = ws[k - 1]["texto"].rstrip("»”\"'")
        p = PAUSA_FRASE if fin.endswith((".", "?", "!", ":")) else PAUSA_COMA if fin.endswith((",", ";")) else 0
        if p and k not in ya:
            cortes.append((k, min(PAUSA_MAX, p * AIRE)))
    cortes.sort()
    if not cortes:
        return _con_fundidos(x), ws
    trozos, ant = [], 0
    for k, p in cortes:
        # Las marcas de tiempo de la voz a veces llegan tarde: cortar en ellas se come el principio de la palabra. Se corta
        # en el punto más callado entre 250 ms antes y 50 ms después de la marca, con un fundido corto a cada lado.
        i = _punto_callado(x, int(ws[k]["t"] * sonidos.SR), ant)
        trozos += [_con_fundidos(x[ant:i]), sonidos.np.zeros(int(p * sonidos.SR))]
        ant = i
    trozos.append(_con_fundidos(x[ant:]))
    corre, nuevas = 0.0, []
    for k, w in enumerate(ws):
        corre += sum(p for kk, p in cortes if kk == k)
        nuevas.append({**w, "t": w["t"] + corre, "fin": w["fin"] + corre})
    return sonidos.np.concatenate(trozos), nuevas


MUSICA_DB = -28  # la música de fondo, respecto a la voz cuando suena


def _musica(archivo: Path, voz, nivel_db: float):
    """Música de fondo suave y constante (sin derechos, Pixabay Music), en bucle durante todo el vídeo, a `nivel_db` de la
    voz: se mide la voz solo donde suena. Entra en 0,3 s y se va en 1,2 s al final."""
    sr = sonidos.SR
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(archivo), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    m = sonidos.np.frombuffer(pcm, dtype=sonidos.np.float32).astype(float)
    m = sonidos.np.tile(m, len(voz) // max(1, len(m)) + 1)[:len(voz)]
    v = sr // 20
    n = len(voz) // v
    rms = sonidos.np.sqrt(sonidos.np.mean(voz[:n * v].reshape(n, v) ** 2, axis=1))
    suena = rms[rms > rms.max() * 0.1]
    rms_voz = float(sonidos.np.sqrt(sonidos.np.mean(suena ** 2))) if len(suena) else 0.1
    rms_m = float(sonidos.np.sqrt(sonidos.np.mean(m ** 2))) or 1.0
    m *= rms_voz * 10 ** (nivel_db / 20) / rms_m
    ent, sal = int(0.3 * sr), int(1.2 * sr)
    m[:ent] *= sonidos.np.linspace(0, 1, min(ent, len(m)))
    m[-sal:] *= sonidos.np.linspace(1, 0, min(sal, len(m)))
    return m


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
        ws = _voz(" ".join(w for _, w, _, _ in fichas), audio, borrador,
                  antes=_dicho(guion["escenas"][ei - 1]) if ei else "",
                  despues=_dicho(guion["escenas"][ei + 1]) if ei + 1 < len(guion["escenas"]) else "")
        if TEMPO != 1.0:
            rapida = audio.with_name(audio.stem + "_rapida.wav")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-filter:a", f"atempo={TEMPO:.4f}",
                            "-ar", str(sonidos.SR), "-ac", "1", str(rapida)], check=True)
            audio.unlink()
            audio = rapida
            ws = [{**w, "t": w["t"] / TEMPO, "fin": w["fin"] / TEMPO} for w in ws]
        x = sonidos.leer_wav(audio)
        audio.unlink()
        # Las palabras de la voz y las del guion casi siempre coinciden una a una; si no, se reparten en proporción.
        idx = (list(range(len(fichas))) if len(ws) == len(fichas)
               else [min(len(fichas) - 1, round(i * len(fichas) / max(1, len(ws)))) for i in range(len(ws))])
        x, ws = _con_pausas(x, ws, idx, fichas, esc["planos"], ei)
        dur = len(x) / sonidos.SR
        voces.append((t, x))
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
            viral = guion.get("estilo", {}).get("diseno") == "viral"
            if ve["tipo"] == "recurso":  # vídeo de banco, tratado con el color de la marca (en «viral», con el suyo)
                from . import generacion_banco
                ve = {**ve, "archivo": generacion_banco.preparar_recurso({"natural": viral, **ve}, publica)}
            elif ve["tipo"] == "imagen":
                from . import generacion_banco
                ve = {**ve, "archivo": generacion_banco.preparar_imagen(ve, publica)}
            plano = {**ve, "inicio": round(ini, 3)}
            if pi in golpes and (ei or pi):  # en fotogramas desde el inicio del plano, un poco antes de la palabra
                # (el primer plano del vídeo ya sale entero: es la portada)
                plano["golpes"] = [max(0, round((g - ini) * FPS) - ANTICIPA) for g in golpes[pi]]
            planos.append(plano)
        fin = t + dur + min(PAUSA_MAX, AIRE * (max(PAUSA, PAUSA_GANCHO) if ei == 0 else _pausa(guion["escenas"][ei + 1]["planos"][0], PAUSA)
                                if ei + 1 < len(guion["escenas"]) else PAUSA))
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
    voz = _suavizar_arranques(_puerta(voz))
    m = min(len(voz), int(0.06 * sonidos.SR))  # el vídeo no empieza con la voz de golpe
    voz[:m] *= sonidos.np.linspace(0, 1, m) ** 2
    viral = guion.get("estilo", {}).get("diseno") == "viral"
    if guion.get("musica"):
        voz = voz + _musica(Path(guion["musica"]).expanduser(), voz, guion.get("musica_db", MUSICA_DB))
    mezcla = carpeta / "mezcla.wav"
    # En «viral» no hay barridos ni golpes: con un cambio de plano cada dos segundos serían ruido; manda la música.
    sonidos.escribir_wav(mezcla, sonidos.mezclar(voz, [] if viral else eventos_de_sonido(planos), t))
    # Volumen de redes (-14 LUFS), con margen para que no sature.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mezcla), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", str(sonidos.SR), str(publica / "audio.wav")], check=True)
    mezcla.unlink()
    return {"fps": FPS, "total": int(t * FPS) + 1, "audio": "audio.wav",
            "titulo": {**guion["titulo"], "fin": round(fin_titulo, 3)}, "planos": planos, "rotulos": rotulos,
            "palabras": palabras, "estilo": {**(estilo_de_marca(guion["negocio_id"], publica) if guion.get("negocio_id") else ESTILO),
                                              **guion.get("estilo", {})}}


# ---------------------------------------------------------------- montaje

def render(props: dict, carpeta: Path, salida: Path, escala: float = 1.0) -> Path:
    """Monta el vídeo con Remotion. Necesita Node y las dependencias de generacion_videos/remotion."""
    ruta_props = carpeta / "props.json"
    ruta_props.write_text(json.dumps(props, ensure_ascii=False))
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "Explicativo", str(salida.resolve()),
                    f"--props={ruta_props.resolve()}", f"--public-dir={(carpeta / 'publica').resolve()}",
                    f"--scale={escala}", "--log=error", "--concurrency=2"], cwd=REMOTION_DIR, check=True)
    normalizar_volumen(salida)
    comprobar_voz(salida)
    return salida


class VozConCortes(Exception):
    pass


def arranques_secos(video: Path, sr: int = 48000) -> list[float]:
    """Momentos en que el sonido pasa de menos de -55 dB a más de -28 dB en 5 ms o menos: un corte sin ataque, que se oye
    como si se comiera el principio de la palabra. Solo cuenta si los 20 ms de antes estaban callados (todos por debajo
    de -50 dB): con música de fondo, los huecos de 1 ms entre golpes de la música no son un corte."""
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:a", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = sonidos.np.frombuffer(pcm, dtype=sonidos.np.float32)
    v = sr // 1000
    n = len(x) // v
    db = 20 * sonidos.np.log10(sonidos.np.sqrt(sonidos.np.mean(x[:n * v].reshape(n, v) ** 2, axis=1)) + 1e-9)
    malos: list[float] = []
    for i in range(n - 5):
        if db[i] < -55 and db[i + 1:i + 6].max() > -28 and db[max(0, i - 20):i + 1].max() < -50 and (not malos or i / 1000 - malos[-1] > 0.05):
            malos.append(round(i / 1000, 2))
    return malos


def comprobar_voz(video: Path) -> None:
    """Control de calidad del sonido: con un solo arranque seco el vídeo no se entrega (se renombra a _FALLIDO)."""
    malos = arranques_secos(video)
    if malos:
        fallido = video.with_name(video.stem + "_FALLIDO" + video.suffix)
        video.replace(fallido)
        raise VozConCortes(f"{len(malos)} arranques secos en la voz ({', '.join(f'{m} s' for m in malos[:8])}): {fallido.name}")


def normalizar_volumen(video: Path) -> None:
    """Deja el vídeo final a -14 LUFS (pico -1,5 dBTP). Hace falta aquí, al final: al codificar el vídeo el audio pierde
    algo más de 1 dB aunque la mezcla saliera ya a -14. La imagen se copia tal cual."""
    tmp = video.with_suffix(".sin_normalizar.mp4")
    video.replace(tmp)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(video)], check=True)
    tmp.unlink()


def generar(guion: dict, carpeta: Path, salida: Path, borrador: bool = False, escala: float = 1.0) -> Path:
    """Guion → voz y efectos → vídeo. La carpeta de trabajo se borra al acabar."""
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        return render(_preparar_a_ritmo(guion, carpeta, borrador), carpeta, salida, escala)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


def palabras_por_minuto(guion: dict, props: dict) -> float:
    palabras = sum(len(_fichas(p["di"])) for e in guion["escenas"] for p in e["planos"])
    return palabras / (props["total"] / FPS) * 60


def _preparar_a_ritmo(guion: dict, carpeta: Path, borrador: bool = False) -> dict:
    """preparar(), estirando o encogiendo las pausas hasta que el ritmo cae en RITMO. La voz sale de la caché desde la
    segunda vuelta, así que reintentar no gasta créditos."""
    global AIRE, TEMPO

    def a_ritmo() -> tuple[dict, float, float]:
        """Con el TEMPO de ahora, el AIRE que deja el ritmo en el centro de RITMO. Devuelve también el ritmo sin estirar."""
        global AIRE
        AIRE = 1.0
        props = preparar(guion, carpeta, borrador)
        ppm1 = ppm = palabras_por_minuto(guion, props)
        if not (RITMO[0] <= ppm <= RITMO[1] or borrador):
            # La duración crece en línea recta con el multiplicador: con dos medidas sale el que hace falta.
            d1 = props["total"] / FPS
            AIRE = 2.0
            pausas = preparar(guion, carpeta, borrador)["total"] / FPS - d1
            objetivo = ppm * d1 / (sum(RITMO) / 2)
            # Como mucho 1,3 veces las pausas: antes 190-195 ppm con pausas naturales que frases sueltas.
            AIRE = max(AIRE_MIN, min(AIRE_MAX, 1 + (objetivo - d1) / max(pausas, 0.1)))
            props = preparar(guion, carpeta, borrador)
            ppm = palabras_por_minuto(guion, props)
        return props, ppm, ppm1

    try:
        props, ppm, ppm1 = a_ritmo()
        if AIRE >= AIRE_MAX and ppm > RITMO[1] and not borrador:
            # Una voz rápida con las pausas muy estiradas suena a frases sueltas: mejor frenarla un poco (hasta un 8 %)
            # y dejar las pausas cerca de lo natural.
            TEMPO = max(0.95, min(1.0, (sum(RITMO) / 2) / ppm1 * 1.04))
            props, ppm, _ = a_ritmo()
        if ppm < RITMO[0] and AIRE <= AIRE_MIN + 0.01 and not borrador:
            # Ni con las pausas al mínimo: se acelera la voz lo justo (como mucho un 6 %) y se vuelven a ajustar las pausas.
            # (un guion puede permitir algo más con "acelerar_max", p. ej. 1.10: atempo cambia el ritmo, no el tono)
            TEMPO = min(float(guion.get("acelerar_max", 1.06)), (sum(RITMO) / 2) / ppm * 1.01)
            props, ppm, _ = a_ritmo()
        print(f"ritmo: {ppm:.0f} palabras por minuto (pausas x{AIRE:.2f}, voz x{TEMPO:.2f})")
        return props
    finally:
        AIRE, TEMPO = 1.0, 1.0


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
