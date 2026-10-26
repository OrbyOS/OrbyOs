"""Del montaje (decisiones del editor) al reel terminado.

Pasa los tiempos del bruto a fotogramas locales de cada plano y aplica las reglas del MANUAL_EDITOR.md que no dependen
de criterio: anticipación de 2 fotogramas, subtítulos solo en planos reales sin titular, látigo de salida cuando el
siguiente entra en látigo, la cabeza siempre tapando solo la base del titular y los efectos de sonido por prioridad
con una separación mínima. Después renderiza en Remotion y mezcla la voz.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from . import imagenes, sonido

RAIZ = Path(__file__).resolve().parent.parent
REMOTION = RAIZ / "remotion"
FPS = 30
ANTICIPA = 2
GANCHO_ASENTADO = 8  # fotogramas: el titular del gancho «entra» antes del 0 para estar entero en el primero
SFX_SEPARACION = 3.0  # segundos entre efectos de sonido
# Prioridad de cada efecto de sonido (mayor gana cuando dos chocan), sonido y ganancia.
SFX_REGLAS = {"latigo": (5, "whoosh", 0.5), "fondo": (5, "whoosh", 0.45), "titular": (4, "impact_soft", 0.6),
              "sacudida": (4, "impact_soft", 0.5), "tiras": (3, "whoosh_soft", 0.45), "chat": (2, "tick", 0.35),
              "ficha": (1, "tick", 0.3), "efecto": (3, "whoosh_soft", 0.35), "golpe": (2, "impact_soft", 0.3),
              "icono": (1, "tick", 0.25), "revela": (3, "whoosh_soft", 0.3)}


def _run(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def _fr(seg: float) -> int:
    return int(round(seg * FPS))


def cargar_kit(nombre: str) -> dict:
    """Un kit por nombre: primero en la carpeta de MOTOR_REELS_KITS (los kits de cada cliente, fuera del repositorio)
    y si no, en kits/ (solo el de ejemplo). En el SaaS el kit no se carga así: sale de la identidad visual."""
    propia = os.environ.get("MOTOR_REELS_KITS", "").strip()
    for carpeta in ([Path(propia)] if propia else []) + [RAIZ / "kits"]:
        if (carpeta / f"{nombre}.json").exists():
            return json.loads((carpeta / f"{nombre}.json").read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No hay kit «{nombre}» (MOTOR_REELS_KITS o motor_reels/kits/).")


def preparacion(trabajo: Path) -> Path:
    """Dónde están los fotogramas y la transcripción del bruto: en la carpeta del montaje o, si el bruto da para
    varios reels (cada uno en su subcarpeta), en la carpeta del bruto. Se prepara una vez y se monta varias."""
    return trabajo if (trabajo / "frames").is_dir() or not (trabajo.parent / "frames").is_dir() else trabajo.parent


def palabras_del_bruto(m: dict, trabajo: Path) -> list[dict]:
    """Transcripción con las correcciones del montaje aplicadas (clave: segundo de la palabra con 2 decimales)."""
    palabras = json.loads((preparacion(trabajo) / "transcripcion.json").read_text(encoding="utf-8"))
    fixes = m.get("correcciones", {})
    return [{**w, "w": fixes.get(f"{w['t']:.2f}", w["w"])} for w in palabras]


def altura_cabeza(frames: Path, src_in: int, dur: int) -> list[int]:
    """Fila más alta de la cabeza en cada fotograma (px de fuente), suavizada a ~0,5 s, para que el titular quede
    tapado solo por abajo aunque la persona se incline."""
    alturas = []
    for i in range(src_in, src_in + dur):
        a = np.asarray(Image.open(frames / f"m_{i:05d}.png").getchannel("A"))[:, 300:780]
        filas = np.nonzero((a > 128).sum(axis=1) > 40)[0]
        alturas.append(int(filas[0]) if len(filas) else (alturas[-1] if alturas else 400))
    k = 15
    rel = np.pad(np.array(alturas, float), k // 2, mode="edge")
    return [int(v) for v in np.convolve(rel, np.ones(k) / k, mode="valid")]


def centro_cara(frames: Path, src_in: int, dur: int) -> list[list[int]]:
    """Centro de la cara por fotograma [x, y] (px de fuente), suavizado: para centrarla en la pantalla partida.
    Se estima con la silueta: lo alto de la cabeza y su anchura (la cara queda ~0,7 anchos por debajo)."""
    puntos = []
    for i in range(src_in, src_in + dur):
        a = np.asarray(Image.open(frames / f"m_{i:05d}.png").getchannel("A")) > 128
        filas = np.nonzero(a.sum(axis=1) > 40)[0]
        if not len(filas):
            puntos.append(puntos[-1] if puntos else [540, 700])
            continue
        arriba = int(filas[0])
        franja = a[arriba + 60:arriba + 220]
        cols = np.nonzero(franja.any(axis=0))[0]
        ancho = int(cols[-1] - cols[0]) if len(cols) else 420
        cx = int(cols.mean()) if len(cols) else 540
        puntos.append([cx, arriba + int(ancho * 0.7)])
    k = 15
    salida = []
    for eje in (0, 1):
        v = np.pad(np.array([q[eje] for q in puntos], float), k // 2, mode="edge")
        salida.append(np.convolve(v, np.ones(k) / k, mode="valid"))
    return [[int(x), int(y)] for x, y in zip(*salida)]


def tono_de_zona(frames: Path, src_in: int, dur: int, zona=(1060, 1880)) -> str:
    """Si la zona donde va un efecto «encima» (a la altura del pecho) es clara u oscura, con unos pocos fotogramas."""
    lum = []
    for i in range(src_in, src_in + dur, max(1, dur // 5)):
        ruta = frames / f"f_{i:05d}.jpg"
        if ruta.exists():
            lum.append(float(np.asarray(Image.open(ruta).convert("L"))[zona[0]:zona[1], 200:880].mean()))
    return "claro" if lum and float(np.median(lum)) > 135 else "oscuro"


def repartir(palabras_bruto: list[dict], planos: list[dict]) -> list[list[dict]]:
    """Cada palabra va al plano que contiene su punto medio; si cae en un hueco recortado, al plano con el que más
    se solapa. Whisper alarga las palabras hacia el silencio de antes, así que el inicio no es fiable en los bordes."""
    por_plano = [[] for _ in planos]
    for w in palabras_bruto:
        ini, fin = w["t"], w.get("fin", w["t"] + 0.2)
        medio = (ini + fin) / 2
        dentro = [i for i, p in enumerate(planos) if p["src"][0] <= medio < p["src"][1]]
        if not dentro:
            solapes = [(min(fin, p["src"][1]) - max(ini, p["src"][0]), i) for i, p in enumerate(planos)]
            mejor, i = max(solapes)
            if mejor <= 0:
                continue
            dentro = [i]
        por_plano[dentro[0]].append(w)
    return por_plano


REGLAS = {"subtitulos": "resaltado", "musica": False, "sonidos": True, "nunca": []}


def reglas_de(kit: dict) -> dict:
    """Las preferencias del cliente de su identidad visual (subtítulos, música, efectos de sonido y «nunca»)."""
    return {**REGLAS, **(kit.get("reglas") or {})}


def props(m: dict, kit: dict, palabras_bruto: list[dict], frames: Path) -> tuple[dict, list]:
    planos, sonidos, at, efectos = [], [], 0, []
    sin_subtitulos = reglas_de(kit)["subtitulos"] == "sin"
    reparto = repartir(palabras_bruto, m["planos"])
    for i, p in enumerate(m["planos"]):
        a, b = p["src"]
        src_in, dur = _fr(a), _fr(b) - _fr(a)

        def local(t):
            return min(dur - 1, max(0, _fr(t) - src_in))

        palabras = [{"w": w["w"], "f": local(w["t"])} for w in reparto[i]]
        g = p.get("grafico")
        grafico = None
        if g:
            tipo = g["tipo"]
            if tipo == "titular":
                kicker = g.get("kicker", [])
                grafico = {"tipo": tipo, "palabra": g["palabra"], "f": max(0, local(g["en"]) - ANTICIPA),
                           "kicker": [{"w": k, "f": max(0, w["f"] - ANTICIPA)} for k, w in zip(kicker, palabras)]}
                if i == 0:  # el gancho: entero y ya asentado en el fotograma 0, que es la portada en el feed
                    grafico["f"] = -GANCHO_ASENTADO
                    grafico["kicker"] = [{**k, "f": -GANCHO_ASENTADO} for k in grafico["kicker"]]
            elif tipo == "chat":
                grafico = {"tipo": tipo, "etiqueta": g["etiqueta"], "texto": g["texto"],
                           "f": local(g["en"]) - ANTICIPA, "envio": local(g["envio"])}
            elif tipo == "ficha":
                grafico = {"tipo": tipo, "filas": [{**{k: v for k, v in x.items() if k != "en"},
                                                    "f": local(x["en"]) - ANTICIPA} for x in g["filas"]]}
            elif tipo == "fondo":
                grafico = {"tipo": tipo, "f": local(g["en"]) - ANTICIPA, "titular": g.get("titular")}
            elif tipo == "efecto":
                efectos.append((i, g))  # se pinta como capa encima de todo su grupo (después del bucle)
            elif tipo == "icono":
                grafico = {"tipo": tipo, "f": max(0, local(g["en"]) - ANTICIPA), "icono": g["icono"],
                           "texto": g.get("texto", ""), "lado": g.get("lado", "izquierda")}
            elif tipo == "imagen":
                grafico = {"tipo": tipo, "f": max(0, local(g["en"]) - ANTICIPA), "archivo": g["archivo"],
                           "pie": g.get("pie", ""), "credito": g.get("credito", ""), "forma": g.get("forma", "tarjeta")}
            momento = at + (grafico["f"] if "f" in grafico else grafico["filas"][0]["f"]) if grafico else at
            if tipo == "titular" and grafico["f"] > 3:  # el titular de portada (fotograma 0) no lleva golpe
                sonidos.append((momento, "titular"))
            elif tipo in ("chat", "ficha", "fondo", "icono"):
                sonidos.append((momento, tipo))
        entrada = p.get("entrada", "corte")
        siguiente = m["planos"][i + 1] if i + 1 < len(m["planos"]) else {}
        anterior = m["planos"][i - 1] if i else {}
        # El color de fondo del kit nunca entra ni sale en seco (manual, sección 4): se abre o se cierra desde la cabeza.
        salida = "latigo" if siguiente.get("entrada") == "latigo" else "corte"
        if p["modo"] == "recorte":
            if anterior.get("modo") == "real" and entrada == "corte":
                entrada = "revela"
            if siguiente.get("modo") == "real" and siguiente.get("entrada", "corte") == "corte":
                salida = "revela"
        plano = {
            "id": p["id"], "from": at, "dur": dur, "srcIn": src_in, "modo": p["modo"],
            "zoom": p.get("zoom", 1.0), "y": p.get("y", 0), "entrada": entrada,
            "salida": salida,
            "palabras": palabras,
            # Con titular o imagen no hay subtítulos: el gráfico ya cuenta lo que se dice.
            "subtitulos": sin_subtitulos is False and p.get("subtitulos", p["modo"] == "real"
                                and not (g and g["tipo"] in ("titular", "imagen", "efecto"))),
        }
        if grafico:
            plano["grafico"] = grafico
        if g and g["tipo"] == "titular":  # en recorte y sobre vídeo real: la cabeza tapa solo la base del titular
            plano["cabeza"] = altura_cabeza(frames, src_in, dur)
        if p.get("fondo"):
            plano["fondo"] = p["fondo"]
        if "sacudida" in p:
            plano["sacudida"] = local(p["sacudida"])
            sonidos.append((at + plano["sacudida"], "sacudida"))
        if "golpe" in p:
            plano["golpe"] = local(p["golpe"])
            sonidos.append((at + plano["golpe"], "golpe"))
        if salida == "revela":
            sonidos.append((at + dur - 10, "revela"))
        if entrada == "latigo":
            sonidos.append((at - 5, "latigo"))
        elif entrada == "tiras":
            sonidos.append((at, "tiras"))
        planos.append(plano)
        at += dur

    # Efectos explicativos: una capa encima de todos los planos que abarcan, para que sobrevivan a los cortes.
    superpuestos = []
    for i, g in efectos:
        grupo = list(range(i, min(len(planos), i + m["planos"][i].get("abarca", 1))))

        def en_reel(t, grupo=grupo):
            for j in grupo:
                a, b = m["planos"][j]["src"]
                if a - 0.05 <= t <= b + 0.05:
                    return planos[j]["from"] + min(planos[j]["dur"] - 1, max(0, _fr(t) - planos[j]["srcIn"]))
            return planos[grupo[0]]["from"]

        desde = planos[grupo[0]]["from"]
        lugar = g.get("lugar", "encima")
        for j in grupo:
            planos[j]["composicion"] = lugar
            planos[j]["subtitulos"] = False
            if lugar == "partida":
                planos[j]["cara"] = centro_cara(frames, planos[j]["srcIn"], planos[j]["dur"])
        capa = {"tipo": "efecto", "clase": g["clase"], "lugar": lugar,
                "f": max(0, en_reel(g["en"]) - desde - ANTICIPA), "titulo": g.get("titulo", ""),
                "sufijo": g.get("sufijo", ""),
                "elementos": [{"texto": x.get("texto", ""), "valor": str(x.get("valor", "")),
                               "f": max(0, en_reel(x.get("en", g["en"])) - desde - ANTICIPA)} for x in g["elementos"]]}
        capa_props = {"from": desde, "dur": sum(planos[j]["dur"] for j in grupo), "grafico": capa,
                      "fondo": m["planos"][i].get("fondo")}
        if lugar == "encima":
            capa_props["tono"] = tono_de_zona(frames, planos[grupo[0]]["srcIn"], planos[grupo[0]]["dur"])
        superpuestos.append(capa_props)
        sonidos.append((desde + capa["f"], "efecto"))

    # Efectos de sonido: primero los de más prioridad; se descarta el que cae a menos de la separación.
    elegidos = []
    for f, k in sorted(sonidos, key=lambda s: -SFX_REGLAS[s[1]][0]):
        if all(abs(f - g) / FPS >= SFX_SEPARACION for g, _ in elegidos):
            elegidos.append((f, k))
    eventos = [(f / FPS, SFX_REGLAS[k][1], SFX_REGLAS[k][2]) for f, k in sorted(elegidos)]
    return {"kit": kit, "planos": planos, "superpuestos": superpuestos, "total": at, "fps": FPS}, eventos


def _enlazar(enlace: Path, destino: Path):
    if enlace.is_symlink() or enlace.exists():
        enlace.unlink()
    os.symlink(destino.resolve(), enlace)


def _carpeta_publica(trabajo: Path, kit: dict) -> tuple[Path, dict]:
    """Carpeta pública propia de cada trabajo (dos renders a la vez no se pisan los fotogramas) y el kit con sus
    tipografías propias servidas desde ella: {"archivo": ruta} pasa a {"url": "fuentes/<rol>.ttf"}."""
    pub = trabajo / "public"
    pub.mkdir(exist_ok=True)
    _enlazar(pub / "frames", preparacion(trabajo) / "frames")
    _enlazar(pub / "grano", REMOTION / "public" / "grano")
    (trabajo / "imagenes").mkdir(exist_ok=True)
    _enlazar(pub / "imagenes", trabajo / "imagenes")
    fuentes = pub / "fuentes"
    fuentes.mkdir(exist_ok=True)
    kit = {**kit, "fuentes": dict(kit.get("fuentes") or {})}
    for rol, f in list(kit["fuentes"].items()):
        if isinstance(f, dict) and f.get("archivo") and Path(f["archivo"]).exists():
            nombre = f"{rol}{Path(f['archivo']).suffix.lower()}"
            # Copia, no enlace: Remotion no sigue los enlaces a archivos sueltos de la carpeta pública.
            shutil.copyfile(f["archivo"], fuentes / nombre)
            kit["fuentes"][rol] = {"url": f"fuentes/{nombre}"}
        elif isinstance(f, dict):
            kit["fuentes"].pop(rol)  # archivo que ya no está: se queda la del catálogo
    return pub, kit


def tramos_de_voz(planos: list[dict]) -> list[list[float]]:
    """Une planos contiguos en el bruto: así los punch-in no meten microcortes en el audio."""
    tramos = []
    for p in planos:
        ini, dur = p["srcIn"] / FPS, p["dur"] / FPS
        if tramos and abs(tramos[-1][0] + tramos[-1][1] - ini) < 1e-6:
            tramos[-1][1] += dur
        else:
            tramos.append([ini, dur])
    return tramos


RITMO_MIN = 3.3   # palabras por segundo (ya sin silencios); por debajo, el reel se acelera
ACELERADO = 1.1


def velocidad_de(m: dict, palabras_bruto: list[dict]) -> float:
    """La del montaje si la fija; si no, x1,1 cuando la voz va lenta (menos de RITMO_MIN palabras/s)."""
    if m.get("velocidad"):
        return float(m["velocidad"])
    dur = sum(p["src"][1] - p["src"][0] for p in m["planos"])
    n = sum(1 for w in palabras_bruto for p in m["planos"] if p["src"][0] <= w["t"] < p["src"][1])
    return ACELERADO if dur and n / dur < RITMO_MIN else 1.0


def montar(montaje_path: Path, salida: Path, *, kit: dict | None = None, propias: dict[str, Path] | None = None) -> dict:
    """`kit`: el kit ya cargado (el SaaS lo guarda por negocio); si no, el de `kits/<montaje.kit>.json`.
    `propias`: {nombre: ruta} con las fotos y capturas del cliente, para los gráficos «imagen»."""
    m = json.loads(montaje_path.read_text(encoding="utf-8"))
    trabajo = montaje_path.resolve().parent
    # Las imágenes reales se buscan antes de renderizar; las que no aparecen se quitan del plano (y se avisa).
    m, avisos = imagenes.resolver(m, trabajo / "imagenes", propias)
    montaje_path.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    bruto = Path(m["bruto"])
    publica, kit = _carpeta_publica(trabajo, kit or cargar_kit(m["kit"]))
    for rol, defecto in (("titular", "InterTight"), ("golpe", "InterTight"), ("mono", "JetBrainsMono")):
        kit["fuentes"].setdefault(rol, defecto)
    palabras_bruto = palabras_del_bruto(m, trabajo)
    velocidad = velocidad_de(m, palabras_bruto)
    datos, eventos = props(m, kit, palabras_bruto, preparacion(trabajo) / "frames")
    props_path = trabajo / "props.json"
    props_path.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")

    video = trabajo / "video.mp4"
    _run(["npx", "remotion", "render", "src/index.ts", "Reel", str(video), f"--props={props_path}",
          f"--public-dir={publica}", "--log=error"], cwd=REMOTION)

    tramos = tramos_de_voz(datos["planos"])
    partes = [f"[0:a]atrim=start={ini:.4f}:duration={dur:.4f},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.008,afade=t=out:st={dur - 0.008:.4f}:d=0.008[a{i}]"
              for i, (ini, dur) in enumerate(tramos)]
    filtro = ";".join(partes) + ";" + "".join(f"[a{i}]" for i in range(len(tramos))) + \
        f"concat=n={len(tramos)}:v=0:a=1,aresample=48000[v]"
    voz = trabajo / "voz.wav"
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(bruto), "-filter_complex", filtro, "-map", "[v]", "-ac", "2", str(voz)])

    if not reglas_de(kit)["sonidos"]:  # el cliente no quiere efectos de sonido: pista en silencio
        eventos = []
    efectos = trabajo / "sfx.wav"
    sonido.write_wav(str(efectos), sonido.build_track(eventos, datos["total"] / FPS))

    salida.parent.mkdir(parents=True, exist_ok=True)
    mezcla = "[1:a]loudnorm=I=-14:TP=-1.5:LRA=9[vz];[2:a]volume=0.5[fx];[vz][fx]amix=inputs=2:normalize=0:duration=first"
    if velocidad == 1.0:
        filtro, video_args = mezcla + "[a]", ["-map", "0:v", "-c:v", "copy"]
    else:
        # Todo el reel a la vez (imagen, voz y efectos), sin cambiar el tono de la voz; se recodifica sin pérdida visible.
        filtro = f"{mezcla},atempo={velocidad}[a];[0:v]setpts=PTS/{velocidad},fps={FPS}[v]"
        video_args = ["-map", "[v]", "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p"]
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(voz), "-i", str(efectos), "-filter_complex",
          filtro, *video_args, "-map", "[a]", "-c:a", "aac", "-b:a", "192k",
          "-movflags", "+faststart", "-shortest", str(salida)])
    return {"salida": str(salida), "duracion": datos["total"] / FPS / velocidad, "velocidad": velocidad,
            "sonidos": [(round(t, 2), k) for t, k, _ in eventos], "avisos": avisos}
