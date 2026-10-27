"""Efectos de sonido de los vídeos generados, sintetizados en código (sin bancos de sonidos ni licencias).

Cada efecto es un array de numpy a 44,1 kHz entre -1 y 1. `mezclar` pone la voz y los efectos en una sola pista.
"""
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 44100


def _t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur)) / SR


def _ruido(n: int, semilla: int) -> np.ndarray:
    return np.random.default_rng(semilla).standard_normal(n)


def _filtrar(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Pasa-banda por FFT (sin scipy)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def _norm(x: np.ndarray, pico: float = 0.9) -> np.ndarray:
    m = np.max(np.abs(x)) or 1.0
    return x / m * pico


def pop() -> np.ndarray:
    """Burbuja corta: un tono que cae de 900 a 300 Hz."""
    t = _t(0.09)
    frec = 900 * np.exp(-t * 14) + 300
    fase = 2 * np.pi * np.cumsum(frec) / SR
    env = np.exp(-t * 45) * np.minimum(1, t * 900)
    return _norm(np.sin(fase) * env)


def tic() -> np.ndarray:
    """Clic seco y agudo (listas, marcas)."""
    t = _t(0.035)
    x = np.sin(2 * np.pi * 2600 * t) * np.exp(-t * 160) + _filtrar(_ruido(len(t), 3), 2000, 9000) * np.exp(-t * 400) * 0.6
    return _norm(x)


def barrido(dur: float = 0.32) -> np.ndarray:
    """Whoosh: ruido cuyo filtro sube y baja, con subida y caída suaves."""
    n = int(SR * dur)
    x = _ruido(n, 7)
    trozos, out = 24, np.zeros(n)
    tam = n // trozos
    for b in range(trozos):
        u = b / (trozos - 1)
        centro = 500 + 4500 * np.sin(np.pi * u)
        s, e = b * tam, n if b == trozos - 1 else (b + 1) * tam
        out[s:e] = _filtrar(x[s:e], centro * 0.5, centro * 1.6)
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6
    return _norm(out * env)


def campana() -> np.ndarray:
    """Ding limpio: tres parciales con caída larga."""
    t = _t(0.9)
    x = (np.sin(2 * np.pi * 1568 * t) + 0.5 * np.sin(2 * np.pi * 2349 * t) + 0.22 * np.sin(2 * np.pi * 3136 * t))
    return _norm(x * np.exp(-t * 6) * np.minimum(1, t * 400))


def golpe() -> np.ndarray:
    """Impacto grave para sellos y palabras grandes."""
    t = _t(0.35)
    frec = 95 * np.exp(-t * 9) + 38
    x = np.sin(2 * np.pi * np.cumsum(frec) / SR) * np.exp(-t * 11)
    x += _filtrar(_ruido(len(t), 11), 60, 1800) * np.exp(-t * 38) * 0.5
    return _norm(x)


EFECTOS = {"pop": pop, "tic": tic, "barrido": barrido, "campana": campana, "golpe": golpe}
VOLUMEN = {"pop": 0.2, "tic": 0.13, "barrido": 0.16, "campana": 0.15, "golpe": 0.3}


@lru_cache(maxsize=None)
def efecto(nombre: str) -> np.ndarray:
    return EFECTOS[nombre]()


def leer_wav(ruta: Path) -> np.ndarray:
    with wave.open(str(ruta)) as w:
        assert w.getframerate() == SR and w.getsampwidth() == 2, "la voz tiene que venir a 44,1 kHz y 16 bits"
        datos = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
        return datos.reshape(-1, w.getnchannels()).mean(axis=1)


def escribir_wav(ruta: Path, x: np.ndarray) -> None:
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def mezclar(voz: np.ndarray, eventos: list[tuple[float, str]], duracion: float) -> np.ndarray:
    """La voz con los efectos encima. eventos: (segundo, nombre del efecto)."""
    n = int(duracion * SR) + SR // 2
    out = np.zeros(n)
    voz = _norm(voz, 0.89)
    out[:len(voz)] += voz[:n]
    for t, nombre in eventos:
        x = efecto(nombre) * VOLUMEN[nombre]
        i = max(0, int(t * SR))
        j = min(n, i + len(x))
        out[i:j] += x[:j - i]
    pico = np.max(np.abs(out))
    return out / pico * 0.95 if pico > 0.95 else out
