"""Silueta de la persona y posición de su cara, con los modelos de MediaPipe (en radar/modelos).

La silueta sirve para poner textos «por detrás» de quien habla; la cara, para reencuadrar a 9:16 sin cortarla.
"""
import threading
from pathlib import Path

import numpy as np

MODELOS = Path(__file__).resolve().parent.parent / "modelos"
_cerrojo = threading.Lock()
_segmentador = None
_detector = None


def _mp():
    import mediapipe as mp  # tarda en importar: solo cuando hace falta
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    return mp, mp_python, vision


def disponible() -> bool:
    try:
        _mp()
    except Exception:  # noqa: BLE001 — sin MediaPipe, los textos van por delante
        return False
    return (MODELOS / "selfie_segmenter.tflite").exists()


def silueta(rgb: np.ndarray) -> np.ndarray:
    """Máscara de la persona (float32 de 0 a 1, mismo tamaño que la imagen)."""
    global _segmentador
    mp, mp_python, vision = _mp()
    with _cerrojo:
        if _segmentador is None:
            _segmentador = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(MODELOS / "selfie_segmenter.tflite")),
                output_confidence_masks=True, output_category_mask=False))
        imagen = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        resultado = _segmentador.segment(imagen)
    mascara = resultado.confidence_masks[0].numpy_view().astype(np.float32)
    if mascara.ndim == 3:
        mascara = mascara[..., 0]
    return mascara


def suavizar(mascara: np.ndarray, anterior: np.ndarray | None, peso: float = 0.6) -> np.ndarray:
    """Mezcla con la máscara del fotograma anterior para que el borde no tiemble."""
    import cv2
    m = cv2.GaussianBlur(mascara, (0, 0), 2.0)
    if anterior is not None and anterior.shape == m.shape:
        m = peso * m + (1 - peso) * anterior
    return np.clip(m, 0, 1)


def centro_de_la_cara(rgb: np.ndarray) -> tuple[float, float] | None:
    """Centro de la cara más grande, en proporción (0 a 1) del ancho y del alto, o None si no hay cara."""
    global _detector
    mp, mp_python, vision = _mp()
    with _cerrojo:
        if _detector is None:
            _detector = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(MODELOS / "blaze_face_short_range.tflite")),
                min_detection_confidence=0.5))
        resultado = _detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not resultado.detections:
        return None
    caja = max((d.bounding_box for d in resultado.detections), key=lambda b: b.width * b.height)
    alto, ancho = rgb.shape[:2]
    return (caja.origin_x + caja.width / 2) / ancho, (caja.origin_y + caja.height / 2) / alto


def cabeza(mascara: np.ndarray, umbral: float = 0.5) -> tuple[float, float] | None:
    """Centro de la cabeza a partir de la silueta (la franja de arriba de la persona), en proporción del ancho y
    del alto. Funciona también en planos abiertos, donde el detector de caras falla."""
    filas = np.where((mascara > umbral).mean(axis=1) > 0.01)[0]
    if len(filas) < 10:
        return None
    arriba, abajo = filas[0], filas[-1]
    franja = mascara[arriba:arriba + max(4, int((abajo - arriba) * 0.18))] > umbral
    columnas = np.where(franja.any(axis=0))[0]
    if not len(columnas):
        return None
    peso = franja.sum(axis=0)
    x = float((np.arange(mascara.shape[1]) * peso).sum() / max(peso.sum(), 1))
    alto, ancho = mascara.shape
    return x / ancho, (arriba + (abajo - arriba) * 0.09) / alto


def borde_superior(mascara: np.ndarray, umbral: float = 0.5) -> float | None:
    """Dónde empieza la persona por arriba (proporción del alto): cuánto aire hay sobre la cabeza."""
    filas = np.where((mascara > umbral).mean(axis=1) > 0.01)[0]
    return float(filas[0] / mascara.shape[0]) if len(filas) else None
