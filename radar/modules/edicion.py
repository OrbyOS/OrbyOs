"""Edición: el cliente sube un vídeo en crudo y lo recibe en 9:16 con el estilo de su mercado.

Pasos: transcribir con tiempos por palabra → quitar silencios y muletillas → reencuadrar a 9:16 (con zoom
alterno en los cortes si el estilo lo pide) → quemar los subtítulos. Los subtítulos se dibujan con Pillow en
PNG transparentes y se ensamblan en una sola pista con alfa (qtrle) que se superpone de una vez, así no
hace falta un ffmpeg con libass.
"""
import json
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import config, db

ANCHO, ALTO, FPS = 1080, 1920, 30
ZOOM = 1.12
MULETILLAS = {"eh", "ehh", "ehm", "em", "emm", "mm", "mmm", "hmm", "este"}
STOP = set(
    "de la el los las un una unos unas y o a en que se su tu mi lo le les nos os con por para no ni al del es "
    "son era como más ya me te si sí pero muy hay ha he han eso esto esa ese esta este cada todo toda".split())

FUENTES = {"condensada": "Anton.ttf", "redonda": "Poppins-ExtraBold.ttf", "clasica": "Archivo-Bold.ttf"}
TAMANOS = {"pequeno": 0.034, "medio": 0.042, "grande": 0.052}
POSICIONES = {"arriba": 0.20, "centro": 0.50, "abajo": 0.70}
RITMOS = {"rapido": 0.25, "medio": 0.40, "pausado": 0.60}

ESTILO_BASE = {
    "origen": "base",
    "descripcion": "Estilo base: subtítulos grandes abajo, la palabra que suena resaltada y zoom suave en cada corte.",
    "ritmo": "medio",
    "cortes_por_minuto": 0,
    "zoom_en_cortes": True,
    "subtitulos": {
        "posicion": "abajo", "mayusculas": False, "palabras_por_bloque": 3, "color_texto": "#FFFFFF",
        "color_resaltado": "#F5D642", "resalta_palabra": True, "contorno": True, "fondo_caja": False,
        "tamano": "medio", "fuente": "redonda",
    },
    "referencias": [],
}


class ErrorEdicion(Exception):
    pass


def completar_estilo(estilo: dict | None) -> dict:
    """Rellena con el estilo base lo que falte, para que una plantilla incompleta no rompa la edición."""
    estilo = dict(estilo or {})
    salida = {**ESTILO_BASE, **{k: v for k, v in estilo.items() if v is not None and k != "subtitulos"}}
    salida["subtitulos"] = {**ESTILO_BASE["subtitulos"], **(estilo.get("subtitulos") or {})}
    s = salida["subtitulos"]
    s["palabras_por_bloque"] = min(6, max(1, int(s.get("palabras_por_bloque") or 3)))
    for clave, opciones in (("posicion", POSICIONES), ("tamano", TAMANOS), ("fuente", FUENTES)):
        if s.get(clave) not in opciones:
            s[clave] = ESTILO_BASE["subtitulos"][clave]
    for clave in ("color_texto", "color_resaltado"):
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(s.get(clave) or "")):
            s[clave] = ESTILO_BASE["subtitulos"][clave]
    if salida.get("ritmo") not in RITMOS:
        salida["ritmo"] = "medio"
    return salida


# ---------------------------------------------------------------- utilidades de ffmpeg

def _ejecutar(cmd: list[str], *, timeout: int = 1800) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise ErrorEdicion(f"ffmpeg ha fallado: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.returncode}")
    return r


def info(ruta: Path) -> dict:
    """Duración y tamaño real del vídeo (ya girado, como lo ve ffmpeg al decodificarlo)."""
    r = subprocess.run([config.FFPROBE, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,color_transfer", "-of", "json", str(ruta)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ErrorEdicion("No se puede leer el vídeo. Prueba con un MP4 o MOV.")
    datos = json.loads(r.stdout or "{}")
    tipos = {s.get("codec_type") for s in datos.get("streams", [])}
    if "video" not in tipos:
        raise ErrorEdicion("El archivo no tiene vídeo.")
    if "audio" not in tipos:
        raise ErrorEdicion("El vídeo no tiene sonido: hace falta la voz para cortar y subtitular.")
    duracion = float(datos.get("format", {}).get("duration") or 0)
    # HDR (los iPhone graban así por defecto): sin pasarlo a SDR, en Instagram se ve lavado y gris.
    hdr = any(s.get("codec_type") == "video" and s.get("color_transfer") in TRANSFERENCIAS_HDR
              for s in datos.get("streams", []))
    with tempfile.TemporaryDirectory() as tmp:
        foto = Path(tmp) / "f.png"
        _ejecutar([config.FFMPEG, "-y", "-v", "error", "-ss", str(min(1.0, duracion / 2)), "-i", str(ruta),
                   "-frames:v", "1", str(foto)], timeout=120)
        with Image.open(foto) as img:
            ancho, alto = img.size
    return {"duracion": duracion, "ancho": ancho, "alto": alto, "hdr": hdr}


TRANSFERENCIAS_HDR = {"smpte2084", "arib-std-b67"}
# De HDR a SDR sin etalonar: solo deja los colores como se ven en el móvil (idea de ai-video-editor, MIT).
A_SDR = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
_filtros: set[str] | None = None


def filtro_sdr(dims: dict) -> str:
    """El filtro que pasa el vídeo a SDR si es HDR y el ffmpeg instalado sabe hacerlo; si no, nada."""
    global _filtros
    if not dims.get("hdr"):
        return ""
    if _filtros is None:
        r = subprocess.run([config.FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True)
        _filtros = {linea.split()[1] for linea in r.stdout.splitlines() if len(linea.split()) > 2}
    return A_SDR + "," if {"zscale", "tonemap"} <= _filtros else ""


# ---------------------------------------------------------------- transcripción

_modelo = None
_cerrojo = threading.Lock()


def transcribir(wav: Path, idioma: str | None = "", *, vocabulario: list[str] | None = None) -> list[dict]:
    """`wav` es audio PCM de 16 bits, mono y a 16 kHz (lo que sale de ffmpeg con -ac 1 -ar 16000).
    `idioma`: vacío, el de la app (RADAR_IDIOMA); None, que lo detecte (vídeos de otros creadores, que pueden ser en
    inglés). `vocabulario`: nombres de la marca (productos, herramientas) que tiene que reconocer bien."""
    global _modelo
    import wave

    import numpy as np
    from faster_whisper import WhisperModel  # tarda en importar: solo cuando hace falta

    # Se le pasa el audio ya decodificado: así no depende de la versión de PyAV instalada.
    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    with _cerrojo:  # un modelo compartido y una transcripción a la vez, para no saturar la máquina
        if _modelo is None:
            _modelo = WhisperModel(config.WHISPER_MODELO, device="cpu", compute_type="int8")
        extra = {"hotwords": ", ".join(vocabulario)[:400]} if vocabulario else {}
        segmentos, _ = _modelo.transcribe(audio, language=(config.IDIOMA if idioma == "" else idioma), vad_filter=True,
                                          word_timestamps=True, **extra)
        palabras = []
        for seg in segmentos:
            for w in seg.words or []:
                texto = w.word.strip()
                if texto:
                    palabras.append({"start": round(w.start, 3), "end": round(w.end, 3), "word": texto})
    return palabras


def _limpia(palabra: str) -> str:
    return re.sub(r"[^0-9a-záéíóúñü]", "", palabra.lower())


def _plano(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if c.isalnum())


def corregir_ortografia(palabras: list[dict], vocabulario: list[str]) -> list[dict]:
    """Escribe bien los nombres de la marca: «many chat» o «Manichat» → «ManyChat». Junta las palabras que forman
    un nombre (hasta tres) y respeta la puntuación de la última."""
    import difflib
    objetivos = [(v, _plano(v)) for v in vocabulario if len(_plano(v)) >= 3]
    if not objetivos:
        return palabras
    salida, i = [], 0
    while i < len(palabras):
        hecho = False
        for n in (3, 2, 1):
            grupo = palabras[i:i + n]
            if len(grupo) < n:
                continue
            plano = _plano("".join(w["word"] for w in grupo))
            for bueno, objetivo in objetivos:
                # Juntando palabras, solo si coinciden letra a letra; una palabra suelta puede estar mal oída.
                parecido = plano == objetivo or (n == 1 and len(objetivo) >= 5 and abs(len(plano) - len(objetivo)) <= 2
                                                 and difflib.SequenceMatcher(None, plano, objetivo).ratio() >= 0.8)
                if parecido:
                    cola = re.search(r"[.,;:?!…]+$", grupo[-1]["word"])
                    salida.append({**grupo[0], "end": grupo[-1]["end"], "word": bueno + (cola.group(0) if cola else "")})
                    i += n
                    hecho = True
                    break
            if hecho:
                break
        if not hecho:
            salida.append(palabras[i])
            i += 1
    return salida


TARTAMUDEO_MAX = 0.6  # segundos entre una palabra y su repetición para tomarlo por un tropiezo


def sin_tartamudeos(palabras: list[dict]) -> list[dict]:
    """Quita la primera de dos palabras iguales seguidas casi pegadas («que… que lo») y se queda con la buena.
    Idea de ai-video-editor (MIT). Los números y las palabras con signos («no, no») se dejan: suelen ser a propósito."""
    salida, quitada = [], False
    for i, w in enumerate(palabras):
        sig = palabras[i + 1] if i + 1 < len(palabras) else None
        clave = _limpia(w["word"])
        if (sig and clave and clave == _limpia(sig["word"]) and not clave.isdigit()
                and not re.search(r"[.,;:?!…]$", w["word"]) and sig["start"] - w["end"] <= TARTAMUDEO_MAX):
            quitada = True
            continue
        # La que se queda lleva la marca para que el corte salte el tropiezo aunque no haya silencio.
        salida.append({**w, "corte_antes": True} if quitada else w)
        quitada = False
    return salida


# ---------------------------------------------------------------- cortes

def tramos_hablados(palabras: list[dict], duracion: float, silencio_max: float) -> list[tuple[float, float]]:
    """Los trozos con voz: se corta cada silencio de más de `silencio_max` segundos y las muletillas."""
    utiles = [w for w in palabras if _limpia(w["word"]) not in MULETILLAS]
    if not utiles:
        return [(0.0, duracion)]
    antes, despues = 0.10, 0.14
    tramos, inicio, fin = [], max(0.0, utiles[0]["start"] - antes), utiles[0]["end"]
    for w in utiles[1:]:
        if w.get("corte_antes") and w["start"] - fin > 0.08:  # un tartamudeo quitado: corte justo, sin márgenes
            tramos.append((inicio, min(duracion, fin + 0.03)))
            inicio = max(0.0, w["start"] - 0.03)
        elif w["start"] - fin > silencio_max:
            tramos.append((inicio, min(duracion, fin + despues)))
            inicio = max(0.0, w["start"] - antes)
        fin = max(fin, w["end"])
    tramos.append((inicio, min(duracion, fin + 0.25)))
    # Une los que se pisan por los márgenes y descarta trozos de menos de un fotograma.
    unidos = []
    for a, b in tramos:
        if unidos and a <= unidos[-1][1]:
            unidos[-1] = (unidos[-1][0], max(unidos[-1][1], b))
        elif b - a > 1 / FPS:
            unidos.append((a, b))
    return unidos


def mapear(palabras: list[dict], tramos: list[tuple[float, float]]) -> list[dict]:
    """Pasa los tiempos de las palabras del bruto a la línea de tiempo del vídeo ya cortado."""
    salida, acumulado = [], 0.0
    for a, b in tramos:
        for w in palabras:
            if a <= w["start"] < b and _limpia(w["word"]) not in MULETILLAS:
                salida.append({**w, "start": round(w["start"] - a + acumulado, 3),
                               "end": round(min(w["end"], b) - a + acumulado, 3)})
        acumulado += b - a
    return salida


# ---------------------------------------------------------------- subtítulos

def _rgba(hexa: str, alfa: int = 255) -> tuple:
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4)) + (alfa,)


def bloques(palabras: list[dict], por_bloque: int) -> list[list[dict]]:
    """Agrupa las palabras en bloques cortos; corta en la puntuación y en las pausas."""
    res, actual = [], []
    for i, w in enumerate(palabras):
        actual.append(w)
        siguiente = palabras[i + 1] if i + 1 < len(palabras) else None
        pausa = (siguiente["start"] - w["end"]) if siguiente else 999
        lleno = len(actual) >= por_bloque and _limpia(w["word"]) not in STOP
        if re.search(r"[.,;:?!]$", w["word"]) or pausa > 0.45 or lleno or len(actual) >= por_bloque + 1:
            res.append(actual)
            actual = []
    if actual:
        res.append(actual)
    return res


def _clave(bloque: list[dict]) -> int:
    mejor, largo = -1, 0
    for i, w in enumerate(bloque):
        t = _limpia(w["word"])
        if t not in STOP and len(t) >= 5 and len(t) > largo:
            mejor, largo = i, len(t)
    return mejor


class Rotulador:
    """Dibuja un bloque de subtítulos en una franja transparente con el estilo de la plantilla."""

    def __init__(self, sub: dict):
        self.sub = sub
        self.tam = int(sub.get("tam_px") or ALTO * TAMANOS[sub["tamano"]])
        self.alto_franja = int(self.tam * 2.9)
        self.y = int(ALTO * POSICIONES[sub["posicion"]] - self.alto_franja / 2)
        self.ruta_fuente = str(config.FUENTES_DIR / FUENTES[sub["fuente"]])
        self.color = _rgba(sub["color_texto"])
        self.resalte = _rgba(sub["color_resaltado"])

    def _texto(self, w: dict) -> str:
        t = re.sub(r"[.,;:]+$", "", w["word"].strip())
        return t.upper() if self.sub["mayusculas"] else t

    def dibujar(self, bloque: list[dict], resaltada: int, salida: Path, escala: float = 1.0):
        img = Image.new("RGBA", (ANCHO, self.alto_franja), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        palabras = [self._texto(w) for w in bloque]
        tam = self.tam
        while True:
            fuente = ImageFont.truetype(self.ruta_fuente, tam)
            espacio = d.textlength(" ", font=fuente)
            anchos = [d.textlength(p, font=fuente) for p in palabras]
            lineas = [list(range(len(palabras)))]
            if sum(anchos) + espacio * (len(palabras) - 1) > ANCHO * 0.86 and len(palabras) > 1:
                mitad = (len(palabras) + 1) // 2
                lineas = [list(range(mitad)), list(range(mitad, len(palabras)))]
            ancho_max = max(sum(anchos[i] for i in l) + espacio * (len(l) - 1) for l in lineas)
            if ancho_max <= ANCHO * 0.9 or tam <= 30:
                break
            tam -= 4
        alto_linea = tam * 1.18
        y0 = (self.alto_franja - alto_linea * len(lineas)) / 2
        trazo = max(int(tam * 0.12), 3) if self.sub["contorno"] else 0
        for n, linea in enumerate(lineas):
            ancho_linea = sum(anchos[i] for i in linea) + espacio * (len(linea) - 1)
            x, y = (ANCHO - ancho_linea) / 2, y0 + n * alto_linea
            if self.sub["fondo_caja"]:
                d.rounded_rectangle((x - tam * 0.35, y - tam * 0.12, x + ancho_linea + tam * 0.35, y + alto_linea),
                                    radius=int(tam * 0.25), fill=(0, 0, 0, 170))
            for i in linea:
                d.text((x, y), palabras[i], font=fuente, fill=self.resalte if i == resaltada else self.color,
                       stroke_width=trazo, stroke_fill=(0, 0, 0, 255))
                x += anchos[i] + espacio
        if escala != 1.0:  # el «salto» de entrada: más pequeño, centrado en la franja
            pequena = img.resize((int(ANCHO * escala), int(self.alto_franja * escala)), Image.BICUBIC)
            img = Image.new("RGBA", img.size, (0, 0, 0, 0))
            img.alpha_composite(pequena, ((ANCHO - pequena.width) // 2, (self.alto_franja - pequena.height) // 2))
        img.save(salida)

    def con_entrada(self, bloque: list[dict], resaltada: int, base: Path, a: float, z: float) -> list:
        """Los tramos de un bloque que empieza: con «pop», dos fotogramas más pequeños antes del normal."""
        if self.sub.get("entrada") != "pop" or z - a < 3 / FPS + 0.04:
            return [(a, z, base)]
        tramos, t = [], a
        for k, escala in enumerate((0.86, 0.95)):
            png = base.with_name(f"{base.stem}_e{k}.png")
            self.dibujar(bloque, resaltada, png, escala)
            tramos.append((t, t + 1 / FPS, png))
            t += 1 / FPS
        return tramos + [(t, z, base)]


def pista_subtitulos(palabras: list[dict], sub: dict, duracion: float, carpeta: Path) -> tuple[Path, int]:
    """Crea la pista transparente con todos los subtítulos. Devuelve la ruta y la altura a la que va."""
    rot = Rotulador(sub)
    eventos = []
    for b in bloques(palabras, sub["palabras_por_bloque"]):
        eventos.append([b[0]["start"], b[-1]["end"] + 0.2, b])
    for i in range(len(eventos) - 1):
        eventos[i][1] = min(eventos[i][1], eventos[i + 1][0])
    eventos = [e for e in eventos if e[1] - e[0] >= 0.12]

    vacio = carpeta / "vacio.png"
    Image.new("RGBA", (ANCHO, rot.alto_franja), (0, 0, 0, 0)).save(vacio)
    tramos = []
    for n, (ini, fin, b) in enumerate(eventos):
        if sub["resalta_palabra"]:
            for j, w in enumerate(b):
                a = max(w["start"], ini)
                z = min(b[j + 1]["start"] if j + 1 < len(b) else fin, fin)
                if z - a > 0.04:
                    png = carpeta / f"s{n:04d}_{j:02d}.png"
                    rot.dibujar(b, j, png)
                    tramos += rot.con_entrada(b, j, png, a, z) if j == 0 else [(a, z, png)]
        else:
            png = carpeta / f"s{n:04d}.png"
            rot.dibujar(b, _clave(b), png)
            tramos += rot.con_entrada(b, _clave(b), png, ini, fin)
    tramos.sort(key=lambda t: t[0])
    lineas, t = [], 0.0
    for ini, fin, png in tramos:
        if ini > t + 1e-3:
            lineas.append((vacio, ini - t))
        ini = max(ini, t)
        lineas.append((png, max(fin - ini, 1 / FPS)))
        t = max(t, fin)
    if duracion > t:
        lineas.append((vacio, duracion - t))
    if not lineas:
        lineas = [(vacio, duracion)]
    lista = carpeta / "subtitulos.txt"
    lista.write_text("".join(f"file '{p}'\nduration {d:.3f}\n" for p, d in lineas) + f"file '{lineas[-1][0]}'\n")
    pista = carpeta / "subtitulos.mov"
    _ejecutar([config.FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
               "-r", str(FPS), "-c:v", "qtrle", "-pix_fmt", "argb", str(pista)])
    return pista, rot.y


# ---------------------------------------------------------------- montaje

def _encuadre(ancho: int, alto: int, zoom: float) -> str:
    """Recorte centrado a 9:16 (con zoom opcional, un poco hacia arriba, donde suele estar la cara)."""
    if ancho / alto > 9 / 16:
        cw, ch = alto * 9 / 16, alto
    else:
        cw, ch = ancho, ancho * 16 / 9
    cw, ch = cw / zoom, ch / zoom
    cx = (ancho - cw) / 2
    cy = (alto - ch) * (0.35 if zoom > 1 else 0.5)
    return f"crop={int(cw) // 2 * 2}:{int(ch) // 2 * 2}:{int(cx)}:{int(cy)},scale={ANCHO}:{ALTO},setsar=1"


def montar(bruto: Path, tramos: list[tuple[float, float]], estilo: dict, dims: dict,
           subtitulos: Path | None, y_subs: int, salida: Path, carpeta: Path):
    partes, etiquetas = [], []
    for i, (a, b) in enumerate(tramos):
        zoom = ZOOM if estilo["zoom_en_cortes"] and i % 2 == 1 else 1.0
        partes.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,"
                      f"{_encuadre(dims['ancho'], dims['alto'], zoom)},fps={FPS}[v{i}]")
        partes.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.012,afade=t=out:st={max(0.0, b - a - 0.012):.3f}:d=0.012[a{i}]")
        etiquetas.append(f"[v{i}][a{i}]")
    partes.append(f"{''.join(etiquetas)}concat=n={len(tramos)}:v=1:a=1[vc][ac]")
    if subtitulos:
        partes.append(f"[vc][1:v]overlay=0:{y_subs}:format=auto:eof_action=pass[vf]")
    else:
        partes.append("[vc]null[vf]")
    grafo = ";".join(partes)
    (carpeta / "grafo.txt").write_text(grafo)  # para revisar a mano si algo sale mal
    cmd = [config.FFMPEG, "-y", "-v", "error", "-i", str(bruto)]
    if subtitulos:
        cmd += ["-i", str(subtitulos)]
    # El grafo va en línea (y no en un archivo) para que funcione con cualquier versión de ffmpeg.
    cmd += ["-filter_complex", grafo, "-map", "[vf]", "-map", "[ac]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(salida)]
    _ejecutar(cmd)


def portada(video: Path, salida: Path):
    _ejecutar([config.FFMPEG, "-y", "-v", "error", "-ss", "0.5", "-i", str(video), "-frames:v", "1",
               "-vf", "scale=540:-2", "-q:v", "4", str(salida)], timeout=120)


# ---------------------------------------------------------------- trabajo completo

def carpeta(edicion_id: int) -> Path:
    c = config.EDICIONES_DIR / str(edicion_id)
    c.mkdir(parents=True, exist_ok=True)
    return c


def bruto(edicion_id: int) -> Path | None:
    return next(iter(sorted(carpeta(edicion_id).glob("bruto.*"))), None)


def editar(edicion_id: int):
    ed = db.edicion(edicion_id)
    estilo = completar_estilo(ed["estilo"])
    dir_ = carpeta(edicion_id)
    entrada = bruto(edicion_id)

    def paso(texto: str):
        db.actualizar_edicion(edicion_id, paso=texto, linea=texto)

    db.actualizar_edicion(edicion_id, estado="en_curso")
    try:
        if not entrada:
            raise ErrorEdicion("No se encuentra el vídeo subido.")
        paso("Leyendo el vídeo")
        dims = info(entrada)
        if dims["duracion"] > config.MAX_SEGUNDOS_BRUTO:
            raise ErrorEdicion(f"El vídeo dura más de {config.MAX_SEGUNDOS_BRUTO // 60} minutos.")
        paso("Transcribiendo la voz")
        wav = dir_ / "voz.wav"
        _ejecutar([config.FFMPEG, "-y", "-v", "error", "-i", str(entrada), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        palabras = transcribir(wav)
        (dir_ / "palabras.json").write_text(json.dumps(palabras, ensure_ascii=False))
        if not palabras:
            raise ErrorEdicion("No se ha entendido ninguna palabra. ¿El vídeo tiene voz?")

        paso("Quitando silencios y muletillas")
        tramos = tramos_hablados(palabras, dims["duracion"], RITMOS[estilo["ritmo"]])
        duracion = sum(b - a for a, b in tramos)

        paso("Dibujando los subtítulos")
        subs_dir = dir_ / "subs"
        subs_dir.mkdir(exist_ok=True)
        pista, y = pista_subtitulos(mapear(palabras, tramos), estilo["subtitulos"], duracion, subs_dir)

        paso("Montando el vídeo en 9:16")
        final = dir_ / "final.mp4"
        montar(entrada, tramos, estilo, dims, pista, y, final, dir_)
        portada(final, dir_ / "portada.jpg")
        wav.unlink(missing_ok=True)

        resultado = {
            "duracion_original": round(dims["duracion"], 1),
            "duracion_final": round(duracion, 1),
            "cortes": max(0, len(tramos) - 1),
            "palabras": len(palabras),
            "texto": " ".join(w["word"] for w in palabras)[:3000],
        }
        db.actualizar_edicion(edicion_id, estado="listo", paso="Listo", resultado=resultado,
                              linea=f"Listo: {resultado['duracion_original']} s → {resultado['duracion_final']} s, "
                                    f"{resultado['cortes']} cortes")
    except ErrorEdicion as e:
        db.actualizar_edicion(edicion_id, estado="error", paso=str(e), linea=str(e))
    except Exception as e:  # noqa: BLE001 — cualquier fallo se enseña en la ficha de la edición
        db.actualizar_edicion(edicion_id, estado="error", paso="Error inesperado al editar",
                              linea=f"{e.__class__.__name__}: {e}")


def en_segundo_plano(funcion, *args):
    import contextvars  # el hilo hereda el negocio en el que se lanza (y sus claves)
    contexto = contextvars.copy_context()
    threading.Thread(target=contexto.run, args=(funcion, *args), daemon=True).start()


def lanzar(edicion_id: int):
    en_segundo_plano(editar, edicion_id)
