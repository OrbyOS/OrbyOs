import React from 'react';
import {AbsoluteFill, Audio, interpolate, random, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ANCHO, CLAMP, CX, ConResalte, EXPO, EstiloCtx, fontFamily, pop, sombra, sombraTexto} from './base';
import {PLANOS, Sello} from './planos';
import {colorDe} from './robot';
import type {Palabra, Plano, Props} from './tipos';

const SALIDA = 6; // fotogramas que tarda en irse un plano mientras entra el siguiente
const ENTRADA = 9;

// ---------------------------------------------------------------- fondo

export const Fondo: React.FC<{f: number; p: Props}> = ({f, p}) => {
  const e = p.estilo;
  const manchas = [0, 1, 2].map((i) => ({
    x: 540 + Math.sin(f / (90 + i * 30) + i * 2) * 380,
    y: 900 + Math.cos(f / (110 + i * 25) + i) * 600,
    r: 520 + i * 80,
  }));
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 40%, #1d3c8f 0%, ${e.mesa} 55%, #060d26 100%)`}}>
      {manchas.map((m, i) => (
        <div key={i} style={{position: 'absolute', left: m.x - m.r, top: m.y - m.r, width: m.r * 2, height: m.r * 2, borderRadius: '50%',
          background: `radial-gradient(circle, ${i === 1 ? 'rgba(61,123,255,0.30)' : 'rgba(120,170,255,0.16)'} 0%, transparent 65%)`}} />
      ))}
      <AbsoluteFill style={{
        backgroundImage: `linear-gradient(${e.veta} 2px, transparent 2px), linear-gradient(90deg, ${e.veta} 2px, transparent 2px)`,
        backgroundSize: '90px 90px', backgroundPosition: `0 ${(f * 0.6) % 90}px`,
        maskImage: 'radial-gradient(ellipse at 50% 45%, black 20%, transparent 75%)',
        WebkitMaskImage: 'radial-gradient(ellipse at 50% 45%, black 20%, transparent 75%)'}} />
      {Array.from({length: 26}).map((_, i) => {
        const x = random(`x${i}`) * 1080;
        const v = 0.4 + random(`v${i}`) * 1.2;
        const y = (random(`y${i}`) * 2100 - f * v) % 2100;
        const yy = y < -60 ? y + 2100 : y;
        const r = 3 + random(`r${i}`) * 6;
        return <div key={i} style={{position: 'absolute', left: x + Math.sin((f + i * 30) / 40) * 20, top: yy, width: r, height: r,
          borderRadius: r, background: '#9cc4ff', opacity: 0.15 + random(`o${i}`) * 0.35, boxShadow: '0 0 12px #9cc4ff'}} />;
      })}
      <AbsoluteFill style={{boxShadow: 'inset 0 0 300px rgba(0,0,0,0.6)'}} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- título y rótulos

const Titulo: React.FC<{p: Props; f: number; fps: number}> = ({p, f, fps}) => {
  const fin = Math.round(p.titulo.fin * fps);
  if (f > fin) return null;
  const sale = interpolate(f, [fin - SALIDA, fin], [1, 0], CLAMP);
  // Visible desde el fotograma 0 (es la portada); solo da un pequeño bote al empezar.
  const bote = 1 + 0.07 * Math.sin(Math.min(f, 14) / 14 * Math.PI);
  const insignia = pop(f, fps, 10, 8);
  return (
    <div style={{position: 'absolute', top: 245, left: CX - ANCHO / 2, width: ANCHO, display: 'flex', flexDirection: 'column',
      alignItems: 'center', gap: 26, opacity: sale, transform: `scale(${bote * (0.9 + 0.1 * sale)}) translateY(${(1 - sale) * -60}px)`}}>
      <div style={{background: p.estilo.caja, borderRadius: 26, padding: '22px 36px', color: '#fff', fontFamily, fontWeight: 900,
        fontSize: p.titulo.texto.length > 34 ? 60 : 68, lineHeight: 1.08, textAlign: 'center', boxShadow: sombra,
        border: '2px solid rgba(150,185,255,0.25)'}}>
        <ConResalte texto={p.titulo.texto} resalte={p.titulo.resalte} color={p.estilo.subrayado} />
      </div>
      {p.titulo.insignia ? (
        <div style={{background: p.estilo.acento, color: '#fff', fontFamily, fontWeight: 900, fontSize: 56, padding: '8px 36px',
          borderRadius: 999, border: '5px solid #fff', boxShadow: sombra, transform: `scale(${insignia}) rotate(-4deg)`}}>{p.titulo.insignia}</div>
      ) : null}
    </div>
  );
};

const Rotulos: React.FC<{p: Props; t: number; fps: number}> = ({p, t, fps}) => {
  const r = p.rotulos.find((x) => t >= x.inicio && t < x.fin);
  if (!r) return null;
  const f = Math.round((t - r.inicio) * fps);
  const s = pop(f, fps, 0, 10);
  const sale = interpolate(t, [r.fin - SALIDA / fps, r.fin], [1, 0], CLAMP);
  return (
    <div style={{position: 'absolute', top: 255, left: CX - ANCHO / 2, width: ANCHO, display: 'flex', justifyContent: 'center', opacity: sale}}>
      <div style={{background: p.estilo.acento, color: '#fff', fontFamily, fontWeight: 900, fontSize: 46, letterSpacing: 1,
        padding: '12px 30px', borderRadius: 18, border: '4px solid #fff', textTransform: 'uppercase', boxShadow: sombra,
        transform: `translateY(${(1 - s) * -80}px) scale(${0.7 + 0.3 * s}) rotate(-2deg)`}}>{r.texto}</div>
    </div>
  );
};

// ---------------------------------------------------------------- planos con transición

const TRANSICIONES = ['zoom', 'barrido', 'sube', 'gira'];

const entrada = (tipo: string, k: number): React.CSSProperties => {
  const q = 1 - k;
  if (tipo === 'barrido') return {transform: `translateX(${q * 900}px) skewX(${q * -12}deg)`, filter: `blur(${q * 20}px)`};
  if (tipo === 'sube') return {transform: `translateY(${q * 700}px)`, filter: `blur(${q * 12}px)`};
  if (tipo === 'gira') return {transform: `rotate(${q * -14}deg) scale(${0.6 + 0.4 * k})`, filter: `blur(${q * 10}px)`};
  return {transform: `scale(${1 + q * 0.45})`, filter: `blur(${q * 22}px)`, opacity: k};
};

export const PlanoVivo: React.FC<{pl: Plano; i: number; frame: number; fps: number}> = ({pl, i, frame, fps}) => {
  const ini = Math.round(pl.inicio * fps);
  const fin = Math.round(pl.fin * fps);
  const f = frame - ini + (i === 0 ? 30 : 0);
  if (frame < ini || frame > fin + SALIDA) return null;
  const Comp = PLANOS[pl.tipo];
  if (!Comp) return null;
  const k = interpolate(f, [0, ENTRADA], [0, 1], {...CLAMP, easing: EXPO});
  const sale = interpolate(frame, [fin, fin + SALIDA], [0, 1], CLAMP);
  const est = i === 0 ? {} : entrada(typeof pl.transicion === 'string' ? pl.transicion : TRANSICIONES[(i - 1) % TRANSICIONES.length], k);
  const dur = fin - ini + (i === 0 ? 30 : 0);
  return (
    <AbsoluteFill style={{...est, opacity: ((est.opacity as number) ?? 1) * (1 - sale),
      transform: `${est.transform ?? ''} scale(${1 - sale * 0.12})`}}>
      <Foco pl={pl} f={f} />
      <Comp p={pl} f={f} dur={dur} fps={fps} />
      {typeof pl.fuente === 'string' ? (
        <div style={{position: 'absolute', left: 60, width: 790, top: 1236, textAlign: 'center', fontFamily, fontWeight: 700, fontSize: 26,
          letterSpacing: 1, color: 'rgba(200,215,255,0.75)', textTransform: 'uppercase'}}>Fuente · {pl.fuente}</div>
      ) : null}
      {typeof pl.sello === 'string' ? <Sello texto={pl.sello} f={f} fps={fps} dur={dur} abajo={pl.tipo === 'palabra'}
        en={Array.isArray(pl.golpes) && pl.golpes.length ? (pl.golpes as number[])[0] : undefined} /> : null}
    </AbsoluteFill>
  );
};

/** Luz detrás de lo principal del plano: late cuando entra algo. */
const Foco: React.FC<{pl: Plano; f: number}> = ({pl, f}) => {
  const c = pl.tipo === 'robot' && typeof pl.quien === 'string' ? colorDe(pl.quien) : '#5a96ff';
  const golpes = [0, ...(Array.isArray(pl.golpes) ? (pl.golpes as number[]) : [])];
  const late = golpes.reduce((a, g) => (f >= g && f < g + 12 ? Math.max(a, 1 - (f - g) / 12) : a), 0);
  const tam = 980 + late * 140;
  return (
    <div style={{position: 'absolute', left: 510 - tam / 2, top: 930 - tam / 2, width: tam, height: tam, borderRadius: '50%',
      background: `radial-gradient(circle, ${c}6b 0%, ${c}29 38%, transparent 68%)`,
      opacity: 0.75 + late * 0.25}} />
  );
};

/** Destello claro en los cambios de plano marcados con «flash». */
const Flash: React.FC<{p: Props; frame: number; fps: number}> = ({p, frame, fps}) => {
  const pl = p.planos.find((x, i) => i > 0 && x.flash && frame >= x.inicio * fps && frame < x.inicio * fps + 4);
  if (!pl) return null;
  const k = (frame - pl.inicio * fps) / 4;
  return <AbsoluteFill style={{background: '#cfe0ff', opacity: 0.28 * (1 - k)}} />;
};

// ---------------------------------------------------------------- subtítulos

const grupos = (palabras: Palabra[]) => {
  const out: Palabra[][] = [];
  palabras.forEach((w) => {
    const g = out[out.length - 1];
    const corta = g && (g.length >= 3 || /[.,:;?!]$/.test(g[g.length - 1].texto) || w.t - g[g.length - 1].fin > 0.25);
    if (!g || corta) out.push([w]);
    else g.push(w);
  });
  return out;
};

export const Subtitulos: React.FC<{p: Props; t: number}> = ({p, t}) => {
  const gs = React.useMemo(() => grupos(p.palabras), [p.palabras]);
  const g = gs.find((x) => t >= x[0].t - 0.04 && t < x[x.length - 1].fin + 0.12);
  if (!g) return null;
  return (
    <div style={{position: 'absolute', top: 1300, left: CX - ANCHO / 2, width: ANCHO, textAlign: 'center', fontFamily, fontWeight: 900,
      fontSize: 72, lineHeight: 1.08, color: '#fff', textShadow: sombraTexto}}>
      {g.map((w, i) => {
        const dentro = t >= w.t - 0.04;
        const s = interpolate(t, [w.t - 0.04, w.t + 0.1], [0.6, 1], {...CLAMP, easing: EXPO});
        const extra = w.enfasis ? interpolate(t, [w.t, w.t + 0.08, w.t + 0.25], [1, 1.28, 1.14], CLAMP) : 1;
        return (
          <span key={i} style={{display: 'inline-block', margin: '0 11px', transformOrigin: '50% 80%',
            color: w.enfasis ? p.estilo.subrayado : '#ffffff',
            transform: `scale(${(dentro ? s : 0.6) * extra}) rotate(${w.enfasis ? -2 : 0}deg)`, opacity: dentro ? 1 : 0,
            background: w.enfasis && dentro ? 'rgba(61,123,255,0.28)' : 'transparent', borderRadius: 14, padding: w.enfasis ? '0 10px' : 0,
          }}>{w.texto}</span>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- cámara

const camara = (p: Props, frame: number, fps: number) => {
  const t = frame / fps;
  const pl = p.planos.find((x) => t >= x.inicio && t < x.fin);
  const k = pl ? (t - pl.inicio) / Math.max(0.1, pl.fin - pl.inicio) : 0;
  let sx = 0, sy = 0, rot = 0;
  for (const w of p.palabras) {
    if (!w.enfasis) continue;
    const d = frame - w.t * fps;
    if (d >= 0 && d < 9) {
      const a = (1 - d / 9) * 9;
      sx += Math.sin(d * 2.9) * a;
      sy += Math.cos(d * 3.7) * a * 0.7;
      rot += Math.sin(d * 2.1) * a * 0.06;
    }
  }
  return `translate(${sx}px, ${sy}px) rotate(${rot}deg) scale(${1 + 0.035 * k})`;
};

export const Explicativo: React.FC<Props> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return (
    <EstiloCtx.Provider value={p.estilo}>
      <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
        <Fondo f={frame} p={p} />
        <AbsoluteFill style={{transform: camara(p, frame, fps), transformOrigin: `${CX}px 900px`}}>
          {p.planos.map((pl, i) => <PlanoVivo key={i} pl={pl} i={i} frame={frame} fps={fps} />)}
        </AbsoluteFill>
        <Titulo p={p} f={frame} fps={fps} />
        <Rotulos p={p} t={t} fps={fps} />
        <Subtitulos p={p} t={t} />
        <Flash p={p} frame={frame} fps={fps} />
        {p.audio ? <Audio src={staticFile(p.audio)} /> : null}
      </AbsoluteFill>
    </EstiloCtx.Provider>
  );
};
