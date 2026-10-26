"""Paso 5: el montaje del reel en dos pasadas y la revisión automática.

Pasada A (imagen base): cortes de silencios y frases quitadas, reencuadre a 9:16 siguiendo la cabeza, zooms,
pantalla partida con capturas y tarjeta de cierre. En el modo «solo voz», un fondo de color con las capturas.
Pasada B (gráficos): subtítulos, gancho, listas, texto en movimiento y la palabra gigante por detrás de la persona,
cada uno como una capa transparente encima. Al final, la mezcla del sonido: la voz a volumen constante y los efectos.
"""
import json
import statistics
import subprocess
from pathlib import Path

import httpx
import numpy as np

from .. import config
from ..modules import edicion as motor
from . import frases as fr
from . import graficos, modelo, segmentacion, sonido

ANCHO, ALTO, FPS = motor.ANCHO, motor.ALTO, motor.FPS
QUIETO_MAX = 3.0          # segundos sin ningún cambio de imagen antes de añadir un zoom suave
SOLO_CARA_MAX = 0.60      # proporción del reel que es solo la persona con subtítulos
CIERRE_SEGUNDOS = 1.3


class ErrorMontaje(Exception):
    pass


def _ffmpeg(cmd: list[str], *, timeout: int = 3600):
    r = subprocess.run([config.FFMPEG, "-y", "-v", "error", *cmd], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        ultima = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else str(r.returncode)
        raise ErrorMontaje(f"ffmpeg ha fallado: {ultima}")


# ---------------------------------------------------------------- tiempos de cada bloque en el reel

def ventanas(plan: dict, palabras_salida: list[dict], total: float) -> list[dict]:
    """Cada bloque con su inicio y su fin en el reel ya cortado (el fin es el inicio del bloque siguiente)."""
    por_frase: dict[str, list[dict]] = {}
    for w in palabras_salida:
        por_frase.setdefault(w.get("frase"), []).append(w)
    salida = []
    for b in plan.get("bloques", []):
        ws = [w for f in b["frases"] for w in por_frase.get(f, [])]
        if not ws:
            continue
        salida.append({**b, "inicio": min(w["start"] for w in ws), "fin_voz": max(w["end"] for w in ws), "palabras": ws})
    for n, v in enumerate(salida):
        siguiente = salida[n + 1]["inicio"] if n + 1 < len(salida) else total
        v["fin"] = max(v["inicio"] + 0.6, min(siguiente, total))
    if salida:
        salida[0]["inicio"] = 0.0
    return salida


def tiempos_de_lista(v: dict) -> list[float]:
    """Cuándo entra cada elemento de una lista: cuando se dice su primera palabra o, si no, repartidos."""
    items, ws = v.get("items") or [], v["palabras"]
    tiempos, desde = [], 0
    for n, item in enumerate(items):
        clave = motor._limpia((item.split() or [""])[0])
        t = None
        for i in range(desde, len(ws)):
            if clave and motor._limpia(ws[i]["word"]) == clave:
                t, desde = ws[i]["start"] - v["inicio"], i + 1
                break
        if t is None:
            t = (v["fin_voz"] - v["inicio"]) * n / max(1, len(items))
        tiempos.append(max(0.0, t))
    return tiempos


# ---------------------------------------------------------------- revisión automática

def tramos_quietos(vents: list[dict], cortes: list[float], total: float) -> list[tuple[float, float]]:
    """Los trozos del reel donde la imagen no cambia: ni corte ni ningún efecto (solo la persona con subtítulos)."""
    con_efecto = sorted((v["inicio"], v["fin"]) for v in vents if v["tipo"] not in ("subtitulo", "cinetico"))
    libres, t = [], 0.0
    for a, b in con_efecto:
        if a > t:
            libres.append((t, a))
        t = max(t, b)
    if t < total:
        libres.append((t, total))
    salida = []
    for a, b in libres:  # cada corte de plano rompe la quietud
        puntos = [a, *[c for c in cortes if a < c < b], b]
        salida += [(x, y) for x, y in zip(puntos, puntos[1:])]
    return salida


def revisar(vents: list[dict], cortes: list[float], total: float, *, modo: str, zoom_suave: bool) -> dict:
    """Lo que se arregla solo (zoom suave en los tramos quietos) y lo que se avisa antes de publicar."""
    zooms, arreglos, avisos = [], [], []
    if modo != "voz":
        for a, b in tramos_quietos(vents, cortes, total):
            if b - a <= QUIETO_MAX:
                continue
            if zoom_suave:
                zooms.append({"inicio": a + 0.1, "fin": b - 0.1, "tipo": "suave"})
                arreglos.append(f"Del segundo {a:.1f} al {b:.1f} no cambiaba nada ({b - a:.1f} s): le he puesto un "
                                f"zoom suave para que no quede quieto.")
            else:
                avisos.append(f"Del segundo {a:.1f} al {b:.1f} ({b - a:.1f} s) la imagen no cambia.")
        cubierto = sum(v["fin"] - v["inicio"] for v in vents if v["tipo"] in {"gancho", "choque", "lista", "pantalla"})
        solo_cara = 1 - cubierto / total if total else 0
        if solo_cara > SOLO_CARA_MAX:
            avisos.append(f"El {solo_cara:.0%} del reel es solo la persona con subtítulos (en los reels más dinámicos "
                          f"suele quedarse por debajo del {SOLO_CARA_MAX:.0%}).")
    gancho = next((v for v in vents if v["tipo"] == "gancho"), None)
    if gancho and gancho["fin"] - gancho["inicio"] > 4:
        avisos.append(f"El gancho dura {gancho['fin'] - gancho['inicio']:.1f} s: los primeros 3 segundos son los que deciden.")
    if total > 180:
        avisos.append(f"Dura {total:.0f} s: Instagram no lo publicará como reel (el máximo son 3 minutos).")
    return {"zooms": zooms, "arreglos": arreglos, "avisos": avisos}


# ---------------------------------------------------------------- encuadre

def _fotograma(video: Path, t: float, ancho: int = 640) -> np.ndarray | None:
    r = subprocess.run([config.FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={ancho}:-2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=60)
    if r.returncode or not r.stdout:
        return None
    alto = len(r.stdout) // (ancho * 3)
    return np.frombuffer(r.stdout, np.uint8)[: ancho * alto * 3].reshape(alto, ancho, 3)


def encuadre(video: Path, tramos: list[tuple[float, float]], dims: dict) -> dict:
    """Dónde está la cabeza (mediana de varios fotogramas): para recortar a 9:16 sin cortarla."""
    xs, ys, arriba = [], [], []
    if segmentacion.disponible():
        momentos = [a + (b - a) / 2 for a, b in tramos][:: max(1, len(tramos) // 8)][:8]
        for t in momentos:
            img = _fotograma(video, t)
            if img is None:
                continue
            m = segmentacion.silueta(img)
            c = segmentacion.cabeza(m)
            if c:
                xs.append(c[0])
                ys.append(c[1])
            borde = segmentacion.borde_superior(m)
            if borde is not None:
                arriba.append(borde)
    cx = statistics.median(xs) if xs else 0.5
    cy = statistics.median(ys) if ys else 0.3
    ancho, alto = dims["ancho"], dims["alto"]
    if ancho / alto > 9 / 16:
        cw, ch = alto * 9 / 16, alto
    else:
        cw, ch = ancho, ancho * 16 / 9
    x = min(max(0, cx * ancho - cw / 2), ancho - cw)
    y = min(max(0, cy * alto - ch * 0.3), alto - ch) if ch < alto else 0
    return {"crop": f"crop={int(cw) // 2 * 2}:{int(ch) // 2 * 2}:{int(x)}:{int(y)}",
            "cabeza_y": (cy * alto - y) / ch, "aire": statistics.median(arriba) if arriba else 0.1}


# ---------------------------------------------------------------- capas transparentes

class _Escritor:
    """Recibe fotogramas RGBA y los guarda como vídeo con transparencia (qtrle)."""

    def __init__(self, destino: Path):
        self.p = subprocess.Popen([config.FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                                   "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-", "-c:v", "qtrle",
                                   "-pix_fmt", "argb", str(destino)], stdin=subprocess.PIPE)

    def escribir(self, imagen):
        self.p.stdin.write(imagen.tobytes())

    def cerrar(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise ErrorMontaje("No se ha podido guardar una capa de gráficos.")


class _Lector:
    """Lee fotogramas del vídeo base (en pequeño) para calcular la silueta en cada uno."""

    def __init__(self, video: Path, inicio: float, duracion: float, ancho: int = 540, alto: int = 960):
        self.ancho, self.alto = ancho, alto
        self.p = subprocess.Popen([config.FFMPEG, "-v", "error", "-ss", f"{inicio:.3f}", "-t", f"{duracion:.3f}",
                                   "-i", str(video), "-vf", f"scale={ancho}:{alto},fps={FPS}", "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def siguiente(self) -> np.ndarray | None:
        datos = self.p.stdout.read(self.ancho * self.alto * 3)
        if len(datos) < self.ancho * self.alto * 3:
            return None
        return np.frombuffer(datos, np.uint8).reshape(self.alto, self.ancho, 3)

    def cerrar(self):
        self.p.stdout.close()
        self.p.wait()


def capa(efecto, duracion: float, destino: Path, *, base: Path | None = None, inicio: float = 0.0):
    """Dibuja un efecto fotograma a fotograma. Con `base`, calcula la silueta para dejarlo detrás de la persona."""
    escritor = _Escritor(destino)
    lector = _Lector(base, inicio, duracion) if base is not None and segmentacion.disponible() else None
    anterior = None
    try:
        for n in range(max(1, int(round(duracion * FPS)))):
            mascara = None
            if lector:
                img = lector.siguiente()
                if img is not None:
                    anterior = segmentacion.suavizar(segmentacion.silueta(img), anterior)
                mascara = anterior
            escritor.escribir(efecto.fotograma(n / FPS, mascara))
    finally:
        if lector:
            lector.cerrar()
        escritor.cerrar()


# ---------------------------------------------------------------- capturas de webs

def captura_web(dominio: str, destino: Path) -> bool:
    """Captura de la portada de una web (servicio público de capturas). Si falla, el bloque se queda sin pantalla
    partida y se avisa."""
    dominio = dominio.strip().removeprefix("https://").removeprefix("http://").split("/")[0]
    if not dominio or "." not in dominio:
        return False
    try:
        r = httpx.get(f"https://image.thum.io/get/width/1200/crop/1500/noanimate/https://{dominio}", timeout=40,
                      follow_redirects=True)
    except httpx.HTTPError:
        return False
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image") or len(r.content) < 5000:
        return False
    destino.write_bytes(r.content)
    # Una página que no cargó o la de «verificando que no eres un robot» (Cloudflare) no es una captura de la web.
    from motor_reels.motor.imagenes import captura_valida  # solo Pillow y numpy: no depende de Node ni del render
    if not captura_valida(destino):
        destino.unlink(missing_ok=True)
        return False
    return True


# ---------------------------------------------------------------- subtítulos

def estilo_subtitulos(ajustes: dict) -> dict:
    s = ajustes["subtitulos"]
    return {"posicion": s["posicion"], "mayusculas": s["mayusculas"], "palabras_por_bloque": s["palabras"],
            "color_texto": ajustes.get("color_texto", "#FFFFFF"), "color_resaltado": ajustes["color"],
            "resalta_palabra": s["resalta"], "contorno": s["contorno"], "fondo_caja": False, "tamano": "medio",
            "fuente": s["fuente"], "tam_px": int(ALTO * 0.042 * s["tamano_pct"] / 100),
            "entrada": ajustes["movimiento"]["subtitulos"]}


# ---------------------------------------------------------------- montaje completo

def montar(dir_: Path, *, modo: str, palabras: list[dict], frases: list[dict], plan: dict, ajustes: dict,
           capturas_dir: Path, logo: Path | None, nombre: str, paso) -> dict:
    """Monta el reel y devuelve el resultado (duraciones, revisión). `paso(texto)` va contando por dónde va."""
    bruto = next(iter(sorted(dir_.glob("bruto.*"))), None)
    if not bruto:
        raise ErrorMontaje("No se encuentra el vídeo subido.")
    dims = motor.info(bruto) if modo != "voz" else {"duracion": _duracion(bruto), "ancho": 0, "alto": 0}

    paso("Cortando silencios")
    quedan = motor.sin_tartamudeos(fr.palabras_que_quedan(frases, palabras))
    if not quedan:
        raise ErrorMontaje("No queda ninguna frase: recupera alguna en el paso de revisión.")
    tramos = motor.tramos_hablados(quedan, dims["duracion"], ajustes["silencio_max"])
    total = round(sum(b - a for a, b in tramos), 3)
    salida_palabras = motor.mapear(quedan, tramos)
    cortes, acumulado = [], 0.0
    for a, b in tramos[:-1]:
        acumulado += b - a
        cortes.append(round(acumulado, 3))
    vents = ventanas(plan, salida_palabras, total)
    sin_zooms = ajustes["movimiento"]["zooms"] == "sin"
    revision = revisar(vents, cortes, total, modo=modo, zoom_suave=ajustes["zoom_suave"] and not sin_zooms)

    paso("Dibujando los gráficos")
    capturas: dict[str, Path] = {}
    for v in vents:
        if v["tipo"] not in ("pantalla", "imagen"):
            continue
        origen = capturas_dir / v["captura"] if v.get("captura") else None
        if not (origen and origen.exists()) and v.get("web"):
            origen = capturas_dir / f"web_{v['id']}.png"
            if not origen.exists() and not captura_web(v["web"], origen):
                revision["avisos"].append(f"No se ha podido capturar {v['web']}: el bloque {v['id'][1:]} va sin pantalla partida.")
                v["tipo"] = "subtitulo" if modo != "voz" else "cinetico"
                continue
        if not (origen and origen.exists()):
            v["tipo"] = "subtitulo" if modo != "voz" else "cinetico"
            continue
        preparada = dir_ / f"captura_{v['id']}.png"
        graficos.captura_vertical(origen, preparada, alto=ALTO if v["tipo"] == "imagen" else ALTO // 2)
        capturas[v["id"]] = preparada

    cierre = None
    if ajustes.get("cierre") and (logo and logo.exists()):
        cierre = dir_ / "cierre.png"
        graficos.cierre(cierre, color=ajustes["color"], logo=logo, nombre=nombre)

    paso("Montando la imagen base")
    base = dir_ / "base.mp4"
    datos_encuadre = _pasada_a(base, bruto, modo=modo, tramos=tramos, dims=dims, vents=vents, revision=revision,
                               capturas=capturas, ajustes=ajustes, cierre=cierre, total=total, carpeta=dir_)

    paso("Escribiendo los subtítulos")
    sin_subtitulos = [(v["inicio"], v["fin"]) for v in vents if v["tipo"] in ("gancho", "choque", "lista", "cinetico")]
    con_subtitulos = [w for w in salida_palabras if not any(a <= w["start"] < b for a, b in sin_subtitulos)]
    subs_dir = dir_ / "subs"
    subs_dir.mkdir(exist_ok=True)
    for viejo in subs_dir.glob("*"):
        viejo.unlink()
    pista, y_subs = (motor.pista_subtitulos(con_subtitulos, estilo_subtitulos(ajustes), total, subs_dir)
                     if con_subtitulos else (None, 0))

    paso("Dibujando los efectos")
    capas_fx, eventos = _efectos(dir_, vents, base=base, modo=modo, ajustes=ajustes, encuadre_=datos_encuadre)

    paso("Montando fotograma a fotograma")
    con_graficos = dir_ / "con_graficos.mp4"
    _pasada_b(con_graficos, base, pista, y_subs, capas_fx, logo if ajustes.get("logo_esquina") else None, dir_, total)

    paso("Mezclando el sonido")
    final = dir_ / "final.mp4"
    _mezcla(final, con_graficos, eventos if ajustes.get("sonidos") else [], dir_)
    motor.portada(final, dir_ / "portada.jpg")
    for temporal in (base, con_graficos):
        temporal.unlink(missing_ok=True)

    efectos = [v["tipo"] for v in vents if v["tipo"] not in ("subtitulo", "cinetico")]
    return {
        "duracion_original": round(dims["duracion"], 1),
        "duracion_final": round(total + (CIERRE_SEGUNDOS if cierre else 0), 1),
        "cortes": len(cortes),
        "efectos": len(efectos),
        "estilo": ajustes["estilo"],
        "revision": {"arreglos": revision["arreglos"], "avisos": revision["avisos"] + (plan.get("avisos") or [])},
        "texto": " ".join(w["word"] for w in salida_palabras)[:3000],
    }


def _duracion(ruta: Path) -> float:
    r = subprocess.run([config.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError as e:
        raise ErrorMontaje("No se puede leer el audio.") from e


def _zoompan(zooms: list[dict], cabeza_y: float, intensidad: str = "suaves") -> str:
    """Expresión de zoom por tramos: «golpe» rápido para los bloques de zoom y «suave» para los tramos quietos."""
    golpe, suave = modelo.ZOOMS.get(intensidad, modelo.ZOOMS["suaves"])
    expr = "1"
    for z in reversed(zooms):
        a, b = z["inicio"], z["fin"]
        if z["tipo"] == "suave":
            dentro = f"1+{suave}*(it-{a:.3f})/{max(0.1, b - a):.3f}"
        else:
            dentro = f"1+{golpe}*min(1,(it-{a:.3f})/0.25)"
        expr = f"if(between(it,{a:.3f},{b:.3f}),{dentro},{expr})"
    y = min(0.45, max(0.2, cabeza_y))
    return (f"zoompan=z='{expr}':x='iw/2-(iw/zoom/2)':y='ih*{y:.3f}-(ih/zoom*{y:.3f})':d=1:"
            f"s={ANCHO}x{ALTO}:fps={FPS}")


def _pasada_a(destino: Path, bruto: Path, *, modo, tramos, dims, vents, revision, capturas, ajustes, cierre, total,
              carpeta) -> dict:
    entradas = ["-i", str(bruto)]
    partes, siguiente = [], 1
    datos_encuadre = {"cabeza_y": 0.3, "aire": 0.1}

    # Voz: cada tramo con sus fundidos, y todos seguidos.
    for i, (a, b) in enumerate(tramos):
        partes.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.012,afade=t=out:st={max(0.0, b - a - 0.012):.3f}:d=0.012[a{i}]")

    if modo == "voz":
        fondo = carpeta / "fondo.png"
        graficos.fondo(ajustes["color"], fondo)
        entradas += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(fondo)]
        indice_fondo = siguiente
        siguiente += 1
        partes.append(f"{''.join(f'[a{i}]' for i in range(len(tramos)))}concat=n={len(tramos)}:v=0:a=1[ac]")
        partes.append(f"[{indice_fondo}:v]scale={ANCHO}:{ALTO},setsar=1,fps={FPS},format=yuv420p,"
                      f"zoompan=z='1+0.05*it/{max(total, 1):.3f}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                      f"s={ANCHO}x{ALTO}:fps={FPS}[vz]")
    else:
        datos_encuadre = encuadre(bruto, tramos, dims)
        sdr = motor.filtro_sdr(dims)
        for i, (a, b) in enumerate(tramos):
            partes.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,{sdr}{datos_encuadre['crop']},"
                          f"scale={ANCHO}:{ALTO},setsar=1,fps={FPS}[v{i}]")
        partes.append(f"{''.join(f'[v{i}][a{i}]' for i in range(len(tramos)))}concat=n={len(tramos)}:v=1:a=1[vc][ac]")
        zooms = [{"inicio": v["inicio"], "fin": v["fin"], "tipo": "golpe"} for v in vents if v["tipo"] == "zoom"]
        zooms += revision["zooms"]
        intensidad = ajustes["movimiento"]["zooms"]
        zooms = [z for z in zooms if z["fin"] - z["inicio"] > 0.3 and intensidad != "sin"]
        partes.append(f"[vc]{_zoompan(sorted(zooms, key=lambda z: z['inicio']), datos_encuadre['cabeza_y'], intensidad)}[vz]"
                      if zooms else "[vc]null[vz]")

    actual = "vz"
    for n, v in enumerate(x for x in vents if x["id"] in capturas):
        entradas += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(capturas[v["id"]])]
        idx = siguiente
        siguiente += 1
        cuando = f"between(t,{v['inicio']:.3f},{v['fin']:.3f})"
        if v["tipo"] == "imagen" or modo == "voz":
            partes.append(f"[{idx}:v]scale={ANCHO}:{ALTO},setsar=1,format=yuv420p[cap{n}]")
            partes.append(f"[{actual}][cap{n}]overlay=0:0:enable='{cuando}'[p{n}]")
        else:
            # Pantalla partida: arriba la captura y abajo la persona (la franja de la cabeza y el pecho).
            y_persona = int(min(max(0, datos_encuadre["cabeza_y"] * ALTO - ALTO * 0.12), ALTO / 2))
            partes.append(f"[{actual}]split=2[m{n}][q{n}]")
            partes.append(f"[q{n}]crop={ANCHO}:{ALTO // 2}:0:{y_persona},setsar=1[abajo{n}]")
            partes.append(f"[{idx}:v]scale={ANCHO}:{ALTO // 2},setsar=1,format=yuv420p[cap{n}]")
            partes.append(f"[m{n}][cap{n}]overlay=0:0:enable='{cuando}'[o{n}]")
            partes.append(f"[o{n}][abajo{n}]overlay=0:{ALTO // 2}:enable='{cuando}',"
                          f"drawbox=x=0:y={ALTO // 2 - 3}:w={ANCHO}:h=6:color=0x{ajustes['color'].lstrip('#')}@1:t=fill:"
                          f"enable='{cuando}'[p{n}]")
        actual = f"p{n}"

    if cierre:
        entradas += ["-loop", "1", "-t", f"{CIERRE_SEGUNDOS}", "-i", str(cierre),
                     "-f", "lavfi", "-t", f"{CIERRE_SEGUNDOS}", "-i", "anullsrc=r=48000:cl=mono"]
        ic, ia = siguiente, siguiente + 1
        partes.append(f"[{actual}]format=yuv420p,setsar=1,fps={FPS}[vm]")
        partes.append(f"[{ic}:v]scale={ANCHO}:{ALTO},setsar=1,fps={FPS},format=yuv420p,fade=t=in:d=0.25[ve]")
        partes.append("[ac]aresample=48000,aformat=channel_layouts=mono[am]")
        partes.append(f"[{ia}:a]aformat=channel_layouts=mono[ae]")
        partes.append("[vm][am][ve][ae]concat=n=2:v=1:a=1[vout][aout]")
    else:
        partes.append(f"[{actual}]format=yuv420p[vout]")
        partes.append("[ac]anull[aout]")
    grafo = ";".join(partes)
    (carpeta / "grafo_a.txt").write_text(grafo)
    _ffmpeg([*entradas, "-filter_complex", grafo, "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", str(destino)])
    return datos_encuadre


def _efectos(dir_: Path, vents: list[dict], *, base: Path, modo: str, ajustes: dict, encuadre_: dict):
    """Las capas de gráficos (gancho, palabra gigante, listas, texto en movimiento) y los sonidos de cada una."""
    fx_dir = dir_ / "efectos"
    fx_dir.mkdir(exist_ok=True)
    for viejo in fx_dir.glob("*"):
        viejo.unlink()
    capas, eventos = [], []
    s = ajustes["subtitulos"]
    mov = ajustes["movimiento"]
    con_persona = modo != "voz"
    aire = encuadre_.get("aire", 0.1)
    for v in vents:
        duracion = v["fin"] - v["inicio"]
        destino = fx_dir / f"{v['id']}.mov"
        if v["tipo"] == "gancho":
            # Arriba si hay hueco sobre la cabeza; si no, sobre el pecho, donde no tapa la cara.
            y0 = 0.05 if (not con_persona or aire > 0.17) else 0.56
            efecto = graficos.Gancho(v["texto"], min(duracion, 4.5), color=ajustes["color"],
                                     fuente_=s["fuente"], mayusculas=s["mayusculas"], y0=y0, entrada=mov["gancho"],
                                     fondo=mov["fondo_texto"])
            capa(efecto, efecto.duracion, destino)
            eventos.append((v["inicio"] + 0.02, "pop"))
        elif v["tipo"] == "choque":
            dur = min(max(duracion, 1.2), 3.0)
            efecto = graficos.Choque(v["texto"], dur, color=ajustes["color"],
                                     centro_y=min(0.42, max(0.24, encuadre_.get("cabeza_y", 0.3))) if con_persona else 0.45,
                                     entrada=mov["choque"], fondo=mov["fondo_texto"])
            capa(efecto, dur, destino, base=base if con_persona else None, inicio=v["inicio"])
            eventos.append((v["inicio"] + 0.1, "golpe"))
        elif v["tipo"] == "lista":
            tiempos = tiempos_de_lista(v)
            efecto = graficos.Lista(v["items"], tiempos, duracion, color=ajustes["color"], fuente_="redonda",
                                    y0=0.5 if con_persona else 0.32, marca=mov["lista"], fondo=mov["fondo_texto"])
            capa(efecto, duracion, destino)
            eventos += [(v["inicio"] + t + 0.05, "pop") for t in tiempos]
        elif v["tipo"] == "cinetico":
            relativas = [{**w, "start": w["start"] - v["inicio"], "end": w["end"] - v["inicio"]} for w in v["palabras"]]
            efecto = graficos.Cinetico(relativas, duracion, color=ajustes["color"], fuente_=s["fuente"],
                                       mayusculas=s["mayusculas"])
            capa(efecto, duracion, destino)
        elif v["tipo"] in ("pantalla", "imagen"):
            eventos.append((max(0.0, v["inicio"] - 0.15), "barrido"))
            continue
        else:
            continue
        capas.append((destino, v["inicio"]))
    return capas, eventos


def _pasada_b(destino: Path, base: Path, pista: Path | None, y_subs: int, capas: list[tuple[Path, float]],
              logo: Path | None, carpeta: Path, total: float):
    entradas = ["-i", str(base)]
    partes, actual, n = [], "0:v", 1
    if pista:
        entradas += ["-i", str(pista)]
        partes.append(f"[{actual}][{n}:v]overlay=0:{y_subs}:format=auto:eof_action=pass[s]")
        actual, n = "s", n + 1
    for k, (ruta, inicio) in enumerate(capas):
        entradas += ["-i", str(ruta)]
        partes.append(f"[{n}:v]setpts=PTS-STARTPTS+{inicio:.3f}/TB[e{k}]")
        partes.append(f"[{actual}][e{k}]overlay=0:0:format=auto:eof_action=pass[x{k}]")
        actual, n = f"x{k}", n + 1
    if logo and logo.exists():
        pequeno = carpeta / "logo_esquina.png"
        graficos.logo_esquina(logo, pequeno)
        entradas += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(pequeno)]
        partes.append(f"[{actual}][{n}:v]overlay=W-w-48:64:enable='lt(t,{total:.3f})'[lg]")
        actual, n = "lg", n + 1
    if not partes:
        partes.append("[0:v]null[vout]")
    else:
        partes[-1] = partes[-1].rsplit("[", 1)[0] + "[vout]"
    grafo = ";".join(partes)
    (carpeta / "grafo_b.txt").write_text(grafo)
    _ffmpeg([*entradas, "-filter_complex", grafo, "-map", "[vout]", "-map", "0:a", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy",
             "-movflags", "+faststart", str(destino)])


def _mezcla(destino: Path, video: Path, eventos: list[tuple[float, str]], carpeta: Path):
    sonidos = sonido.preparar(carpeta / "sonidos")
    entradas = ["-i", str(video)]
    indices = {}
    for nombre in sorted({e[1] for e in eventos}):
        entradas += ["-i", str(sonidos[nombre])]
        indices[nombre] = len(indices) + 1
    grafo = sonido.filtro_mezcla(sorted(eventos), indices, medida=sonido.medir(video, config.FFMPEG))
    _ffmpeg([*entradas, "-filter_complex", grafo, "-map", "0:v", "-map", "[audio]", "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(destino)])


def guardar_json(ruta: Path, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False))
