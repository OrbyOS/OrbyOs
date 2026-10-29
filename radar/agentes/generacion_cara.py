"""Generación de vídeos con la persona a cámara: su grabación leyendo un guion, montada con capas encima.

1. Se transcribe el bruto palabra a palabra (faster-whisper, en local).
2. Cada frase del guion se busca en la transcripción y se queda la última toma buena (si se equivoca, repite la frase
   y sigue): así salen solos los cortes de silencios y tomas falsas, sin cambiar el orden de lo que dice.
3. En las frases que lo piden entra una capa: una grabación de pantalla con zoom o un plano animado del explicativo,
   y los rótulos cortos. Los subtítulos son las palabras de la toma buena.

El montaje se describe en un JSON: {"bruto", "frases": [{"di", "ve"?, "rotulo"?}], "negocio_id"? | "kit"?, "estilo"?}. «ve» es una capa
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
FPS = 30
ANTICIPA = 2 / FPS  # lo que entra con una palabra entra 2 fotogramas antes que ella
# Reencuadres (punch-ins) secos: en el gancho, cada 1,5-2 s; después, uno por frase. Escalas alternas, centradas en la cara.
GANCHO_HASTA = 6.0
CADA_GANCHO = 1.7
ESCALAS = (1.0, 1.18, 1.08)
MIN_CLAVE = 1.2
# Cómo se marca el título del reel si el guion no lo hace con *palabra*: la última palabra en cursiva y en el acento, y
# en el del gancho, además, un trazo fino que se dibuja debajo. El kit o el montaje lo cambian con "titulo".
TITULO = {"cursiva": True, "subraya_gancho": True}  # segundos que una palabra clave está en pantalla como mínimo


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


def alinear(frases: list[str], palabras: list[dict], minimo: float = 0.62,
            ganchos: set[int] = frozenset()) -> list[tuple[int, int] | None]:
    """Para cada frase, el trozo de palabras [i, j) que mejor la dice. Si la dijo varias veces seguidas (repetir una
    toma), se queda la última que está casi tan bien como la mejor. Las frases se buscan en orden y cerca de la anterior,
    salvo las de `ganchos` (el gancho que se adelanta al principio): esas se buscan en todo el bruto y no mueven el orden."""
    norm = [_norma(w["texto"]) for w in palabras]
    out, desde = [], 0
    for k, frase in enumerate(frases):
        gancho = k in ganchos
        guardado, desde = desde, (0 if gancho else desde)
        objetivo = [x for x in (_norma(w) for w in frase.split()) if x]
        n = len(objetivo)
        candidatos = []
        for i in range(desde, len(norm) if gancho else min(len(norm), desde + 6 * n + 40)):
            for j in range(i + max(1, n - 3), min(len(norm), i + n + 4) + 1):
                r = difflib.SequenceMatcher(None, objetivo, norm[i:j]).ratio()
                if r >= minimo:
                    candidatos.append((r, i, j))
        if not candidatos:
            out.append(None)
            desde = guardado
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
        desde = guardado if gancho else j
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
        ve = c.get("ve") if isinstance(c.get("ve"), dict) else {}
        if ve.get("tipo") in ("pantalla", "imagen"):
            shutil.copyfile(ve["fuente"], publica / Path(ve["fuente"]).name)
        _copiar_archivos(ve.get("plano") or {}, publica)
    shutil.copytree(generacion.AGENTES_DIR, publica / "agentes", dirs_exist_ok=True)
    palabras = montaje.get("palabras") or transcribir(bruto)
    montaje["palabras"] = palabras  # quien llama puede guardarla y no volver a transcribir
    trozos = alinear([f["di"] for f in montaje["frases"]], palabras,
                     ganchos={k for k, f in enumerate(montaje["frases"]) if f.get("gancho")})
    tramos, salida, capas, rotulos, sonidos_ev, t = [], [], [], [], [], 0.0
    claves, zooms, n_zoom = [], [], 0
    kit = json.loads(Path(montaje["kit"]).read_text()) if montaje.get("kit") else {}
    titulo = {**TITULO, **kit.get("titulo", {}), **montaje.get("titulo", {})}
    # Ritmo de reencuadres: por defecto solo en el gancho; con "reencuadre_cada" (segundos), en todo el vídeo (estilo de
    # cortes cada 1,2-1,4 s). "escalas" cambia lo que se acerca (más leve: 1,0 / 1,08 / 1,04).
    ritmo = {**kit.get("ritmo", {}), **montaje.get("ritmo", {})}
    cada, hasta = ritmo.get("reencuadre_cada", CADA_GANCHO), (1e9 if ritmo.get("reencuadre_cada") else GANCHO_HASTA)
    escalas = tuple(ritmo.get("escalas", ESCALAS))
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
        # Reencuadre seco al empezar la frase y, dentro del gancho, cada ~1,7 s en el principio de una palabra.
        cortes = [t]
        for w in palabras[i:j]:
            tw = t + w["t"] - desde
            if tw < hasta and tw - cortes[-1] >= cada and t + dur - tw > 0.8:
                cortes.append(tw - ANTICIPA)
        for c in cortes:
            escala = f.get("zoom") if c == t and f.get("zoom") else escalas[n_zoom % len(escalas)]
            zooms.append({"t": round(max(0.0, c), 3), "escala": escala})
            n_zoom += 1
        # La palabra clave junto a la cara: entra cuando la dice y se va con la frase.
        if f.get("clave"):
            primera = _norma(f["clave"].split()[0])
            w = next((w for w in palabras[i:j] if _norma(w["texto"]) == primera), palabras[i])
            ini = max(t, t + w["t"] - desde - ANTICIPA)
            texto = f["clave"]
            if titulo["cursiva"] and "*" not in texto and len(texto.split()) > 1:
                texto = " ".join(texto.split()[:-1]) + f" *{texto.split()[-1]}*"
            claves.append({"inicio": round(ini, 3), "fin": round(t + dur, 3), "texto": texto, "lugar": f.get("lugar", "arriba"),
                           **({"ante": f["ante"]} if f.get("ante") else {}),
                           **({"subraya": True} if f.get("gancho") and titulo["subraya_gancho"] and "*" in texto else {})})
            if f.get("remate"):
                sonidos_ev.append({"t": ini, "archivo": "sfx/golpe.wav", "volumen": 0.3})
        ve = f.get("ve")
        if ve == "sigue" and capas:  # la visual de la frase anterior sigue en pantalla (una lista que se completa, por ejemplo)
            capas[-1]["fin"] = round(t + dur, 3)
        elif ve:
            capa = {**ve, "inicio": round(t, 3), "fin": round(t + dur, 3)}
            if ve["tipo"] in ("pantalla", "imagen"):
                capa["archivo"] = Path(ve["fuente"]).name
                capa["encuadres"] = _resolver_encuadres(ve)
                for k in ("fuente", "medidas"):
                    capa.pop(k, None)
            capas.append(capa)
            if f.get("remate") and not f.get("clave"):  # efectos de sonido solo en los remates, por debajo de la voz
                sonidos_ev.append({"t": max(0.0, t - 0.1), "archivo": "sfx/barrido.wav", "volumen": 0.3})
        if f.get("rotulo"):
            rotulos.append({"inicio": round(t, 3), "fin": round(t + dur, 3), "texto": f["rotulo"], "arriba": f.get("rotulo_arriba", True)})
        t += dur
    # Una palabra clave dicha al final de su frase se iría antes de poder leerla: aguanta al menos 1,2 s (hasta la siguiente).
    for k, sig in zip(claves, claves[1:] + [{"inicio": t}]):
        k["fin"] = round(max(k["fin"], min(k["inicio"] + MIN_CLAVE, sig["inicio"], t)), 3)
    (publica / "sfx").mkdir(exist_ok=True)
    for nombre in ("barrido", "pop", "golpe", "tic"):
        sonidos.escribir_wav(publica / "sfx" / f"{nombre}.wav", sonidos.efecto(nombre) * 0.9)
    faltan = [f["di"] for f, tr in zip(montaje["frases"], trozos) if not tr]
    return {"fps": generacion.FPS, "total": int(t * generacion.FPS) + 1, "cara": {"archivo": "cara.mp4", "tramos": tramos,
                     "zooms": zooms, "centro": montaje.get("cara", {"x": 0.5, "y": 0.34})},
            "capas": capas, "claves": claves, "rotulos": rotulos, "palabras": salida, "sonidos": sonidos_ev,
            "estilo": {**estilo_del_montaje(montaje, publica), **montaje.get("estilo", {})}, "_faltan": faltan}


def _copiar_archivos(plano: dict, publica: Path) -> None:
    """Las piezas del lienzo llevan su imagen (`fuente`, una captura) o sus logos (`fuentes`): se copian a la carpeta
    pública y la pieza se queda con el nombre (`archivo` / `archivos`)."""
    if plano.get("fuente"):
        shutil.copyfile(plano["fuente"], publica / Path(plano["fuente"]).name)
        plano["archivo"] = Path(plano.pop("fuente")).name
    if plano.get("fuentes"):
        for x in plano["fuentes"]:
            shutil.copyfile(x, publica / Path(x).name)
        plano["archivos"] = [Path(x).name for x in plano.pop("fuentes")]


def estilo_de_kit(kit: dict) -> dict:
    """El estilo a partir de un kit visual del motor de reels (`{"colores", "fuentes"}`), el formato con el que se trabaja
    la marca en la skill antes de pasarla al Kit del SaaS: texto y acento del kit, fondo con su tono y su titular."""
    c, f = kit.get("colores", {}), kit.get("fuentes", {})
    estilo = {**generacion.ESTILO, **{k: c[v] for k, v in (("texto", "texto"), ("subrayado", "acento"), ("acento", "acento"), ("mesa", "fondo")) if c.get(v)}}
    if isinstance(f.get("titular"), str):
        estilo["titular"] = f["titular"]
    # Lo del lienzo (interfaz sobre blanco, rotulador, notas a mano) y el tipo de subtítulos, si el kit lo trae.
    estilo.update({k: c[k] for k in ("lienzo", "interfaz", "marcador", "notas") if c.get(k)})
    if kit.get("reglas", {}).get("subtitulos") in ("cortos", "normales"):
        estilo["subtitulos"] = kit["reglas"]["subtitulos"]
    return estilo


def estilo_del_montaje(montaje: dict, publica: Path) -> dict:
    """La marca sale del Kit del negocio (`negocio_id`) o de un kit visual en JSON (`kit`: ruta); si no, los neutros."""
    if montaje.get("negocio_id"):
        return generacion.estilo_de_marca(montaje["negocio_id"], publica)
    if montaje.get("kit"):
        return estilo_de_kit(json.loads(Path(montaje["kit"]).read_text()))
    return dict(generacion.ESTILO)


def render(props: dict, carpeta: Path, salida: Path, concurrencia: int = 2) -> Path:
    """Renderiza con pocos hilos: el Mac no aguanta varios trabajos pesados a la vez."""
    props = {k: v for k, v in props.items() if not k.startswith("_")}
    ruta_props = carpeta / "props.json"
    ruta_props.write_text(json.dumps(props, ensure_ascii=False))
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "ConCara", str(salida.resolve()), f"--props={ruta_props.resolve()}",
                    f"--public-dir={(carpeta / 'publica').resolve()}", f"--concurrency={concurrencia}", "--log=error"], cwd=generacion.REMOTION_DIR, check=True)
    generacion.normalizar_volumen(salida)  # -14 LUFS: el bruto llega con el volumen de cada día y la cámara
    return salida


if __name__ == "__main__":
    # python -m radar.agentes.generacion_cara montaje.json salida.mp4 [--trabajo carpeta]
    import argparse
    import tempfile

    a = argparse.ArgumentParser(description="Monta un vídeo a cámara a partir de su montaje.json")
    a.add_argument("montaje", type=Path)
    a.add_argument("salida", type=Path)
    a.add_argument("--trabajo", type=Path, help="carpeta de trabajo (se queda: props.json y la transcripción)")
    x = a.parse_args()
    m = json.loads(x.montaje.read_text())
    trabajo = x.trabajo or Path(tempfile.mkdtemp(prefix="concara-"))
    guardadas = trabajo / "palabras.json"
    if not m.get("palabras") and guardadas.exists():  # la transcripción se reutiliza: Whisper es lo que más tarda
        m["palabras"] = json.loads(guardadas.read_text())
    props = preparar(m, trabajo)
    if not guardadas.exists():
        guardadas.write_text(json.dumps(m["palabras"], ensure_ascii=False))
    if props["_faltan"]:
        print("No están en el bruto:", *props["_faltan"], sep="\n  ")
    render(props, trabajo, x.salida)
    print(x.salida)
