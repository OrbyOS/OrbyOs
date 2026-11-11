"""Saca el estilo de edición de los reels de la competencia que más destacan y lo guarda como plantilla.

Por cada referencia: se descarga el vídeo (solo para medirlo, no se guarda ni se reutiliza), se cuentan los
cortes con el detector de escenas de ffmpeg y se le enseñan a Claude tres fotogramas para que describa los
subtítulos (posición, mayúsculas, palabras por pantalla, colores) y si hay zooms o texto en pantalla.
"""
import re
import statistics
import subprocess
import tempfile
from pathlib import Path

import httpx

from .. import config, db, llm, metodo
from ..connectors import apify_social
from ..llm import B, N, S, lista, obj
from . import edicion

MAX_REFERENCIAS = 3
MAX_MB = 80

ESQUEMA = obj(
    descripcion=S,
    subtitulos=obj(
        hay=B,
        posicion={"type": "string", "enum": list(edicion.POSICIONES)},
        mayusculas=B,
        palabras_por_bloque=N,
        color_texto=S,
        color_resaltado=S,
        resalta_palabra=B,
        contorno=B,
        fondo_caja=B,
        tamano={"type": "string", "enum": list(edicion.TAMANOS)},
        fuente={"type": "string", "enum": list(edicion.FUENTES)},
    ),
    zoom_en_cortes=B,
    texto_en_pantalla=S,
    gancho=S,
    por_referencia=lista(obj(cuenta=S, nota=S)),
)


def referencias(negocio_id: int) -> list[dict]:
    """Los reels de la competencia del último análisis, de más a menos destacado, que tengan vídeo."""
    inf = db.ultimo_informe(negocio_id)
    corto = ((inf or {}).get("secciones") or {}).get("contenido_corto") or {}
    reels = [r for r in corto.get("reels") or [] if r.get("video_url")]
    reels.sort(key=lambda r: (r.get("ratio") or 0, r.get("vistas") or 0), reverse=True)
    # Una referencia por cuenta, para no sacar el estilo de una sola marca.
    salida, cuentas = [], set()
    for r in reels:
        if r["cuenta"] not in cuentas:
            cuentas.add(r["cuenta"])
            salida.append(r)
    return salida


def _descargar(url: str, destino: Path) -> bool:
    try:
        with httpx.stream("GET", url, timeout=60, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"}) as r:
            if r.status_code != 200:
                return False
            total = 0
            with open(destino, "wb") as f:
                for trozo in r.iter_bytes(1 << 16):
                    total += len(trozo)
                    if total > MAX_MB * 1024 * 1024:
                        return False
                    f.write(trozo)
        return destino.stat().st_size > 50_000
    except httpx.HTTPError:
        return False


def cortes_por_minuto(video: Path, duracion: float) -> float:
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-i", str(video), "-an", "-vf",
                        "scale=320:-2,scdet=threshold=12", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    cortes = len(re.findall(r"lavfi\.scd\.time:\s*[\d.]+", r.stderr))
    return round(cortes / duracion * 60, 1) if duracion else 0.0


def fotogramas(video: Path, duracion: float, carpeta: Path, nombre: str) -> list[bytes]:
    salida = []
    for n, momento in enumerate((0.15, 0.45, 0.75)):
        foto = carpeta / f"{nombre}_{n}.jpg"
        subprocess.run([config.FFMPEG, "-y", "-v", "error", "-ss", f"{duracion * momento:.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "5", str(foto)],
                       capture_output=True, timeout=60)
        if foto.exists():
            salida.append(foto.read_bytes())
    return salida


def _ritmo(cpm: float) -> str:
    return "rapido" if cpm >= 24 else "medio" if cpm >= 10 else "pausado"


def _frescas(negocio_id: int) -> list[dict]:
    """Los enlaces a los mp4 caducan: si ya no sirven, se vuelven a pedir los reels de las mejores cuentas."""
    cuentas = [r["cuenta"] for r in referencias(negocio_id)][:MAX_REFERENCIAS]
    if not cuentas:
        inf = db.ultimo_informe(negocio_id)
        perfil = (((inf or {}).get("secciones") or {}).get("ficha") or {}).get("perfil") or {}
        cuentas = [c["instagram"] for c in perfil.get("competidores", []) if c.get("instagram")][:MAX_REFERENCIAS]
    if not cuentas or not config.apify_activo():
        return []
    reels, _ = apify_social.reels_instagram(cuentas, por_cuenta=6, dias=180, cuantos=12)
    salida, vistas = [], set()
    for r in reels:
        if r.get("video_url") and r["cuenta"] not in vistas:
            vistas.add(r["cuenta"])
            salida.append(r)
    return salida


def sacar(negocio_id: int) -> dict:
    """Devuelve la plantilla de estilo (y la guarda). Si no hay referencias, se queda con el estilo base."""
    if not config.ffmpeg_activo():
        raise edicion.ErrorEdicion("Falta el motor de edición en el servidor.")
    medidas, imagenes = [], []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for intento in (referencias, _frescas):
            for r in intento(negocio_id):
                if len(medidas) >= MAX_REFERENCIAS:
                    break
                video = tmp / f"ref{len(medidas)}.mp4"
                if not _descargar(r["video_url"], video):
                    continue
                try:
                    dur = edicion.info(video)["duracion"]
                except edicion.ErrorEdicion:
                    continue
                medidas.append({"cuenta": r["cuenta"], "url": r["url"], "imagen": r.get("imagen", ""),
                                "vistas": r.get("vistas"), "ratio": r.get("ratio"), "segundos": round(dur),
                                "cortes_por_minuto": cortes_por_minuto(video, dur)})
                imagenes += fotogramas(video, dur, tmp, f"ref{len(medidas)}")
            if medidas:
                break
    if not medidas:
        plantilla = {**edicion.ESTILO_BASE, "aviso": "No se han podido descargar reels de la competencia; "
                                                      "se usa el estilo base hasta el próximo análisis."}
        db.guardar_estilo(negocio_id, plantilla)
        return plantilla

    cpm = statistics.median(m["cortes_por_minuto"] for m in medidas)
    lectura, aviso = None, ""
    if llm.disponible() and imagenes:
        try:
            lectura = llm.json_con_esquema(
                metodo.BASE,
                "Estos son fotogramas de los reels de la competencia que más destacan (tres por vídeo, en orden). "
                "Describe su estilo de edición para poder copiarlo en otros vídeos:\n"
                "- «subtitulos»: si hay; dónde van (arriba, centro, abajo); si van en mayúsculas; cuántas palabras salen "
                "a la vez; color del texto y del resaltado en hexadecimal; si se resalta la palabra que suena; si "
                "llevan contorno o caja de fondo; tamaño; tipo de letra (condensada tipo Anton, redonda tipo Poppins "
                "o clásica).\n"
                "- «zoom_en_cortes»: si el encuadre cambia de tamaño entre planos.\n"
                "- «texto_en_pantalla» y «gancho»: qué textos fijos usan y cómo arrancan.\n"
                "- «descripcion»: el estilo en una frase, como se lo contarías a un editor.\n\n"
                f"Medidas de cada vídeo: {medidas}",
                ESQUEMA,
                imagenes=imagenes[:9],
            )
        except llm.ErrorIA as e:
            # Sin la lectura de los fotogramas, el ritmo medido sigue valiendo; los subtítulos quedan como el base.
            aviso = f"No se han podido leer los subtítulos de las referencias ({e}); se usa el ritmo medido."
    sub = (lectura or {}).get("subtitulos") or {}
    if lectura and not sub.get("hay", True):
        # Copiar «sin subtítulos» a un vídeo hablando a cámara no tiene sentido: se quedan los del estilo base.
        sub = {}
        aviso = "Los reels de referencia no llevan subtítulos; se usan los del estilo base y el ritmo medido."
    previo = db.estilo(negocio_id)
    if not lectura and previo and previo.get("origen") == "competencia":
        sub = previo.get("subtitulos") or {}  # se conservan los subtítulos que ya se habían leído
    plantilla = edicion.completar_estilo({
        "origen": "competencia",
        "descripcion": (lectura or {}).get("descripcion") or "Estilo medido en los reels que más destacan.",
        "ritmo": _ritmo(cpm),
        "cortes_por_minuto": cpm,
        "zoom_en_cortes": bool((lectura or {}).get("zoom_en_cortes", True)) or cpm >= 24,
        "subtitulos": {k: v for k, v in sub.items() if k != "hay"},
        "texto_en_pantalla": (lectura or {}).get("texto_en_pantalla", ""),
        "gancho": (lectura or {}).get("gancho", ""),
        "referencias": medidas,
        "notas": (lectura or {}).get("por_referencia", []),
        "aviso": aviso,
    })
    db.guardar_estilo(negocio_id, plantilla)
    return plantilla
