import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile} from 'remotion';
import {CLAMP, EXPO, fontFamily, useEstilo} from './base';
import type {Plano, Props} from './tipos';

/** Diseño «viral» (referencias @nolosabia.ia y @explicadorapido): cada plano es una imagen o un clip real del objeto del
 * que se habla, a pantalla completa, con un empujón o un paneo lento; encima, un rótulo de 2 a 4 palabras en mayúsculas,
 * blanco, grueso y centrado en el tercio central, sin caja. Sin fondo de marca, sin subtítulo largo y sin fundidos. */

type P = {p: Plano; f: number; dur: number; fps: number};
const texto = (x: unknown) => (typeof x === 'string' ? x : '');

// Movimientos de cámara, por turnos para que dos planos seguidos no se muevan igual. Un plano puede pedir el suyo con
// "mov": "acerca" | "aleja" | "izquierda" | "derecha" | "sube".
const MOVS = ['acerca', 'derecha', 'aleja', 'izquierda', 'sube'];
const movimiento = (mov: string, k: number): string => {
  if (mov === 'aleja') return `scale(${1.16 - 0.12 * k})`;
  if (mov === 'derecha') return `scale(1.16) translateX(${-40 + 80 * k}px)`;
  if (mov === 'izquierda') return `scale(1.16) translateX(${40 - 80 * k}px)`;
  if (mov === 'sube') return `scale(1.16) translateY(${50 - 100 * k}px)`;
  return `scale(${1.04 + 0.12 * k})`;
};

/** Una toma real (clip o foto) a pantalla completa. */
export const Toma: React.FC<P & {i?: number}> = ({p, f, dur}) => {
  const k = interpolate(f, [0, Math.max(1, dur)], [0, 1], CLAMP);
  const n = Math.round(p.inicio * 7.3);
  const mov = texto(p.mov) || MOVS[n % MOVS.length];
  const src = staticFile(texto(p.archivo));
  // "x" (0-100): por dónde se recorta en horizontal una toma apaisada, para que el objeto quede en el centro.
  const estilo: React.CSSProperties = {width: 1080, height: 1920, objectFit: 'cover', objectPosition: `${Number(p.x ?? 50)}% 50%`};
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${Number(p.zoom ?? 1)}) ${movimiento(mov, k)}`}}>
        {p.tipo === 'imagen' ? <Img src={src} style={estilo} /> : (
          <OffthreadVideo src={src} muted startFrom={Math.round(Number(p.empieza ?? 0) * 30)} style={estilo} />
        )}
      </AbsoluteFill>
      {p.marcador ? <Marcador m={p.marcador as {x?: number; y?: number}} f={f} /> : null}
    </AbsoluteFill>
  );
};

/** "marcador": {"x", "y"}: un pin de ubicación que cae sobre ese punto de la toma, rebota y deja una onda en el suelo. */
const Marcador: React.FC<{m: {x?: number; y?: number}; f: number}> = ({m, f}) => {
  const e = useEstilo();
  const x = m.x ?? 540, y = m.y ?? 1100;
  const cae = interpolate(f, [4, 12, 15, 18], [-700, 0, -36, 0], CLAMP);
  const onda = interpolate(f, [12, 34], [0, 1], CLAMP);
  return (
    <>
      <div style={{position: 'absolute', left: x - 90 * onda - 20, top: y - 22 * onda - 6, width: 180 * onda + 40, height: 44 * onda + 12,
        borderRadius: '50%', border: `5px solid ${e.subrayado}`, opacity: f < 12 ? 0 : 1 - onda}} />
      <svg width={150} height={200} viewBox="0 0 30 40" style={{position: 'absolute', left: x - 75, top: y - 196 + cae,
        filter: 'drop-shadow(0 10px 18px rgba(0,0,0,0.55))'}}>
        <path d="M15 39 C15 39 2 23 2 14 A13 13 0 0 1 28 14 C28 23 15 39 15 39 Z" fill={e.subrayado} stroke="#fff" strokeWidth={1.6} />
        <circle cx={15} cy={14} r={5} fill="#fff" />
      </svg>
    </>
  );
};

export const PLANOS_VIRAL: Record<string, React.FC<P>> = {recurso: Toma, imagen: Toma};

/** El rótulo del plano que suena: "rotulo" en el plano del guion. Entra de golpe con un pequeño asentamiento. */
export const RotuloViral: React.FC<{p: Props; t: number; fps: number}> = ({p, t, fps}) => {
  const pl = p.planos.find((x) => t >= x.inicio && t < x.fin);
  const r = pl ? texto(pl.rotulo).toUpperCase() : '';
  if (!pl || !r) return null;
  const f = (t - pl.inicio) * fps;
  const k = interpolate(f, [0, 5], [0, 1], {...CLAMP, easing: EXPO});
  const largo = r.length;
  return (
    <div style={{position: 'absolute', left: 90, width: 900, top: 960, transform: `translateY(-50%) scale(${1.08 - 0.08 * k})`,
      textAlign: 'center', fontFamily, fontWeight: 900, fontSize: largo > 22 ? 96 : largo > 14 ? 112 : 128, lineHeight: 1.02,
      letterSpacing: -1, color: '#fff', textWrap: 'balance',
      // Sombra suave en dos capas: se lee encima de un cielo blanco o de un fondo negro sin necesitar caja.
      textShadow: '0 4px 28px rgba(0,0,0,0.6), 0 2px 6px rgba(0,0,0,0.55), 0 0 2px rgba(0,0,0,0.7)'}}>
      {r}
    </div>
  );
};

// ---------------------------------------------------------------- plantilla B: «herramienta» (referencia @blackdarketing)

/** Diseño «herramienta»: el fondo oscuro de la marca, el titular del vídeo fijo arriba todo el reel, en el centro la
 * pantalla real de la herramienta o de su GitHub (o los planos de siempre) y Orby asomado junto a la pantalla. */
export const TitularFijo: React.FC<{p: Props}> = ({p}) => {
  const e = useEstilo();
  const {texto: tx, resalte} = p.titulo;
  const i = resalte ? tx.toLowerCase().indexOf(resalte.toLowerCase()) : -1;
  return (
    <div style={{position: 'absolute', top: 150, left: 90, width: 900, textAlign: 'center', fontFamily, fontWeight: 900, fontSize: tx.length > 30 ? 66 : 76,
      lineHeight: 1.08, letterSpacing: -1, color: '#fff', textWrap: 'balance', textShadow: '0 3px 20px rgba(0,0,0,0.5)'}}>
      {i < 0 ? tx : <>{tx.slice(0, i)}<span style={{color: e.subrayado}}>{tx.slice(i, i + resalte.length)}</span>{tx.slice(i + resalte.length)}</>}
    </div>
  );
};

/** El rótulo del plano, debajo de la pantalla (en «herramienta» el centro lo ocupa la pantalla). */
export const RotuloAbajo: React.FC<{p: Props; t: number; fps: number}> = ({p, t, fps}) => {
  const pl = p.planos.find((x) => t >= x.inicio && t < x.fin);
  const r = pl ? texto(pl.rotulo).toUpperCase() : '';
  if (!pl || !r) return null;
  const k = interpolate((t - pl.inicio) * fps, [0, 5], [0, 1], {...CLAMP, easing: EXPO});
  return (
    <div style={{position: 'absolute', left: 90, width: 900, top: 1500, transform: `scale(${1.08 - 0.08 * k})`, textAlign: 'center', fontFamily,
      fontWeight: 900, fontSize: r.length > 18 ? 70 : 84, lineHeight: 1.05, color: '#fff', textShadow: '0 4px 24px rgba(0,0,0,0.6)'}}>{r}</div>
  );
};

/** Orby, la mascota, asomado a la esquina de la pantalla mientras se ve una web. */
export const MascotaOrby: React.FC<{p: Props; t: number; fps: number; Robot: React.FC<{clave: string; f: number; tam: number; accion?: string}>}> = ({p, t, fps, Robot}) => {
  const pl = p.planos.find((x) => t >= x.inicio && t < x.fin);
  if (!pl || pl.tipo !== 'pantalla') return null;
  const f = (t - pl.inicio) * fps;
  const sube = interpolate(f, [2, 10], [120, 0], {...CLAMP, easing: EXPO});
  return (
    <div style={{position: 'absolute', left: 820, top: 1250 + sube, transform: 'rotate(-8deg)'}}>
      <Robot clave="jefa" f={Math.round(f)} tam={200} accion="saluda" />
    </div>
  );
};
