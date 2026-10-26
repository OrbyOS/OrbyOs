"""Del bruto a lo que necesita el motor: fotogramas en SDR, silueta de la persona y transcripción con tiempos.

Deja en la carpeta de trabajo:
- frames/f_00000.jpg (fotograma) y frames/m_00000.png (silueta en el canal alfa), uno por fotograma;
- transcripcion.json: [{"t": inicio, "fin": fin, "w": palabra}, ...] en segundos del bruto.

Dos formas de sacar la silueta, con la misma salida:
- «vision»: tools/segmentar (Swift + Vision de macOS). La más fina en pelo y bordes; además pasa el HDR del iPhone
  a SDR con la conversión de Apple. Solo en Mac.
- «mediapipe»: el segmentador que ya usa el SaaS (radar/modelos/selfie_segmenter.tflite). Va en el servidor.
"""
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
APP = RAIZ.parent  # producto/app: para importar radar
SEGMENTAR = RAIZ / "tools" / "segmentar"


def _run(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def backend_por_defecto() -> str:
    return "vision" if platform.system() == "Darwin" and SEGMENTAR.exists() else "mediapipe"


def _es_hdr(bruto: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=color_transfer", "-of", "csv=p=0", str(bruto)], capture_output=True, text=True)
    return r.stdout.strip().strip(",") in ("arib-std-b67", "smpte2084")


def _filtros_disponibles() -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout


FPS = 30


def fotogramas_mediapipe(bruto: Path, frames: Path, *, rangos: list[tuple[float, float]] | None = None,
                         recorte: str = "") -> list[str]:
    """Extrae con ffmpeg y segmenta con MediaPipe. Devuelve los avisos.

    `rangos`: solo esos tramos del bruto (segundos); cada fotograma conserva su número en el bruto.
    `recorte`: filtro crop de ffmpeg para pasar un horizontal a 9:16 (el encuadre del SaaS). Siempre sale a 1080×1920.
    El HDR se convierte con zscale si este ffmpeg lo trae."""
    sys.path.insert(0, str(APP))
    from radar.editor import segmentacion  # noqa: E402

    if not segmentacion.disponible():
        raise RuntimeError("MediaPipe o su modelo no están disponibles.")
    frames.mkdir(parents=True, exist_ok=True)
    avisos = []
    filtros = []
    if _es_hdr(bruto):
        if " zscale " in _filtros_disponibles():
            filtros.append("zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                           "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
        else:
            avisos.append("El vídeo es HDR y el servidor no puede convertirlo: los colores pueden salir lavados.")
    if recorte:
        filtros.append(recorte)
    filtros += ["scale=1080:1920:flags=lanczos", "setsar=1", f"fps={FPS}"]
    vf = ",".join(filtros)
    for a, b in rangos or [(0.0, None)]:
        cmd = ["ffmpeg", "-v", "error", "-y"]
        if b is not None:
            cmd += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}"]
        cmd += ["-i", str(bruto), "-vf", vf, "-q:v", "2", "-start_number", str(round(a * FPS)),
                str(frames / "f_%05d.jpg")]
        _run(cmd)
    anterior = None
    for jpg in sorted(frames.glob("f_*.jpg")):
        if jpg.with_name(jpg.name.replace("f_", "m_").replace(".jpg", ".png")).exists():
            continue
        rgb = np.asarray(Image.open(jpg).convert("RGB"))
        mascara = segmentacion.suavizar(segmentacion.silueta(rgb), anterior)
        anterior = mascara
        alfa = (np.clip(mascara, 0, 1) * 255).astype(np.uint8)
        rgba = np.zeros((*alfa.shape, 4), np.uint8)
        rgba[..., 3] = alfa
        Image.fromarray(rgba).save(frames / jpg.name.replace("f_", "m_").replace(".jpg", ".png"))
    return avisos


MARGEN = 15  # fotogramas de más a cada lado de un tramo usado


def rangos_de(montajes: list[dict]) -> list[tuple[int, int]]:
    """Los tramos de fotogramas que usan los montajes (con margen), fusionados."""
    tramos = sorted((max(0, int(p["src"][0] * FPS) - MARGEN), int(p["src"][1] * FPS) + MARGEN)
                    for m in montajes for p in m.get("planos", []))
    fusion = []
    for a, b in tramos:
        if fusion and a <= fusion[-1][1] + 5:
            fusion[-1] = (fusion[-1][0], max(fusion[-1][1], b))
        else:
            fusion.append((a, b))
    return fusion


def fotogramas(bruto: Path, trabajo: Path, backend: str | None = None, rangos: list[tuple[int, int]] | None = None):
    """Fotogramas y silueta. Con `rangos` (números de fotograma), solo esos: en un bruto de 5 minutos, extraerlo
    entero son ~6 GB; los tramos que usan los reels, menos de la mitad."""
    frames = trabajo / "frames"
    if frames.is_dir() and any(frames.glob("m_*.png")):
        return
    backend = backend or backend_por_defecto()
    if backend == "vision":
        _run([str(SEGMENTAR), str(bruto), str(frames)]
             + ([",".join(f"{a}-{b}" for a, b in rangos)] if rangos else []))
    else:
        segundos = [(a / FPS, (b + 1) / FPS) for a, b in rangos] if rangos else None
        for aviso in fotogramas_mediapipe(bruto, frames, rangos=segundos):
            print("Aviso:", aviso)


def transcribir(bruto: Path, trabajo: Path) -> list[dict]:
    """Transcripción con tiempos por palabra, con el mismo faster-whisper que usa el SaaS."""
    destino = trabajo / "transcripcion.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    sys.path.insert(0, str(APP))
    from radar.modules import edicion  # noqa: E402

    wav = trabajo / "audio16k.wav"
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-ac", "1", "-ar", "16000", str(wav)])
    palabras = [{"t": w["start"], "fin": w["end"], "w": w["word"]} for w in edicion.transcribir(wav)]
    destino.write_text(json.dumps(palabras, ensure_ascii=False, indent=1), encoding="utf-8")
    return palabras


def preparar(bruto: Path, trabajo: Path, backend: str | None = None, *, solo_transcribir: bool = False) -> list[dict]:
    """Transcripción y, salvo `solo_transcribir`, todos los fotogramas. En brutos largos conviene transcribir, decidir
    los reels y después extraer solo sus tramos (orden «fotogramas»)."""
    trabajo.mkdir(parents=True, exist_ok=True)
    palabras = transcribir(bruto, trabajo)
    if not solo_transcribir:
        fotogramas(bruto, trabajo, backend)
    return palabras
