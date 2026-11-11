#!/usr/bin/env python3
"""Sintetiza los efectos de sonido de transicion (whoosh e impacto)."""
import numpy as np

SR = 48000


def _env(n, attack, decay, curve=2.0):
    a = int(n * attack)
    d = n - a
    up = np.linspace(0, 1, a) ** curve if a else np.array([])
    down = np.linspace(1, 0, d) ** curve if d else np.array([])
    return np.concatenate([up, down])[:n]


def _onepole_bp(x, f_lo, f_hi):
    """Pasa-banda barato encadenando un pasa-altos y un pasa-bajos de 1 polo."""
    out = np.empty_like(x)
    a_hi = np.exp(-2 * np.pi * f_hi / SR)
    lp, prev_in, hp = 0.0, 0.0, 0.0
    a_lo = np.exp(-2 * np.pi * f_lo / SR)
    for i, s in enumerate(x):
        lp = (1 - a_hi) * s + a_hi * lp
        hp = a_lo * (hp + lp - prev_in)
        prev_in = lp
        out[i] = hp
    return out


def whoosh(dur=0.42, f0=400, f1=5200, reverse=False):
    """Barrido de ruido filtrado: el clasico 'swish' de transicion."""
    n = int(SR * dur)
    noise = np.random.default_rng(7).standard_normal(n)
    # barrido de frecuencia aplicando un filtro variable por bloques
    out = np.zeros(n)
    blocks = 48
    size = n // blocks
    for b in range(blocks):
        s, e = b * size, min((b + 1) * size, n)
        u = b / (blocks - 1)
        f = f0 * (f1 / f0) ** u
        seg = _onepole_bp(noise[s:e], f * 0.55, f * 1.9)
        out[s:e] = seg
    out *= _env(n, 0.72, 0.28, 1.6)
    if reverse:
        out = out[::-1]
    peak = np.abs(out).max()
    return out / peak if peak else out


def impact(dur=0.55, f_start=110, f_end=42):
    """Golpe grave con caida rapida: aterriza el movimiento."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = f_start * (f_end / f_start) ** (t / dur)
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * np.exp(-t * 7.5)
    click = (np.random.default_rng(3).standard_normal(n)
             * np.exp(-t * 90) * 0.35)
    out = body + _onepole_bp(click, 900, 7000)
    peak = np.abs(out).max()
    return out / peak if peak else out


def tick(dur=0.09):
    """Pequeno 'pop' para la entrada de un rotulo."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    out = (np.sin(2 * np.pi * 1850 * t) * np.exp(-t * 55)
           + np.sin(2 * np.pi * 3100 * t) * np.exp(-t * 80) * 0.5)
    peak = np.abs(out).max()
    return out / peak if peak else out


def build_track(events, total_dur):
    """events: lista de (tiempo, tipo, ganancia)."""
    n = int(SR * total_dur) + SR
    track = np.zeros(n)
    cache = {"whoosh": whoosh(), "whoosh_soft": whoosh(0.34, 300, 3200),
             "impact": impact(), "impact_soft": impact(0.40, 90, 38),
             "tick": tick()}
    for t, kind, gain in events:
        s = int(t * SR)
        clip = cache[kind] * gain
        e = min(s + len(clip), n)
        if s < n:
            track[s:e] += clip[:e - s]
    peak = np.abs(track).max()
    if peak > 0.98:
        track *= 0.98 / peak
    return track[:int(SR * total_dur)]


def write_wav(path, mono, sr=SR):
    import wave
    import struct
    data = np.clip(mono, -1, 1)
    pcm = (data * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1).flatten()
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack("<%dh" % len(stereo), *stereo))
