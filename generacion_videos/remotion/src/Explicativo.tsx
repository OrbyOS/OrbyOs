import React from 'react';
import {AbsoluteFill, Audio, Easing, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/InterTight';
import {Defs, ILUSTRACIONES, Marco} from './ilustraciones';
import type {Escena, Palabra, Props} from './tipos';

const {fontFamily} = loadFont('normal', {weights: ['700', '800', '900'], subsets: ['latin', 'latin-ext']});

// Zona segura de Instagram (la misma que el motor de reels): el texto va entre x 60-850 e y 230-1440.
const CENTRO_X = 455;
const ANCHO_TEXTO = 760;
const CLAMP = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const EXPO = Easing.bezier(0.16, 1, 0.3, 1);

const sombra = '0 6px 0 rgba(0,0,0,0.25), 0 14px 30px rgba(0,0,0,0.35)';

const Mesa: React.FC<{p: Props}> = ({p}) => (
  <AbsoluteFill style={{
    background: `repeating-linear-gradient(90deg, transparent 0 34px, ${p.estilo.veta} 34px 36px, transparent 36px 118px),
      repeating-linear-gradient(90deg, transparent 0 7px, rgba(0,0,0,0.035) 7px 8px),
      radial-gradient(ellipse at 50% 42%, rgba(120,170,255,0.28), transparent 65%), ${p.estilo.mesa}`,
  }}>
    <AbsoluteFill style={{boxShadow: 'inset 0 0 260px rgba(0,0,0,0.55)'}} />
  </AbsoluteFill>
);

/** Texto con una parte resaltada en el color de acento. */
const ConResalte: React.FC<{texto: string; resalte: string; acento: string}> = ({texto, resalte, acento}) => {
  const i = resalte ? texto.indexOf(resalte) : -1;
  if (i < 0) return <>{texto}</>;
  return <>{texto.slice(0, i)}<span style={{color: acento}}>{resalte}</span>{texto.slice(i + resalte.length)}</>;
};

const Titulo: React.FC<{p: Props; f: number; fps: number; fin: number}> = ({p, f, fps, fin}) => {
  const entra = spring({frame: f, fps, config: {damping: 14, mass: 0.7}});
  const sale = interpolate(f, [fin - 8, fin], [1, 0], CLAMP);
  const insignia = spring({frame: f - 12, fps, config: {damping: 9, mass: 0.6}});
  return (
    <div style={{position: 'absolute', top: 250, left: CENTRO_X - ANCHO_TEXTO / 2, width: ANCHO_TEXTO, opacity: sale,
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 34}}>
      <div style={{background: p.estilo.caja, borderRadius: 22, padding: '22px 34px', transform: `scale(${0.85 + 0.15 * entra})`,
        opacity: entra, color: p.estilo.texto, fontFamily, fontWeight: 800, fontSize: 64, lineHeight: 1.12,
        textAlign: 'center', boxShadow: sombra}}>
        <ConResalte texto={p.titulo.texto} resalte={p.titulo.resalte} acento={p.estilo.subrayado} />
      </div>
      {p.titulo.insignia ? (
        <div style={{background: p.estilo.acento, color: '#fff', fontFamily, fontWeight: 900, fontSize: 60,
          padding: '10px 36px', borderRadius: 999, border: '5px solid #fff', boxShadow: sombra,
          transform: `scale(${insignia}) rotate(-3deg)`}}>{p.titulo.insignia}</div>
      ) : null}
    </div>
  );
};

const Etiqueta: React.FC<{e: Escena; p: Props; f: number; fps: number}> = ({e, p, f, fps}) => {
  const entra = spring({frame: f, fps, config: {damping: 16}});
  const largo = (e.fin - e.inicio) * fps;
  const cinta = spring({frame: f - largo * 0.45, fps, config: {damping: 10, mass: 0.6}});
  return (
    <div style={{position: 'absolute', top: 260, left: CENTRO_X - ANCHO_TEXTO / 2, width: ANCHO_TEXTO,
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26}}>
      <div style={{background: p.estilo.acento, color: '#fff', fontFamily, fontWeight: 800, fontSize: 40, letterSpacing: 1,
        padding: '10px 26px', borderRadius: 14, border: '4px solid #fff', textTransform: 'uppercase', boxShadow: sombra,
        transform: `translateY(${(1 - entra) * -40}px)`, opacity: entra}}>{e.etiqueta}</div>
      {e.cinta ? (
        <div style={{background: p.estilo.caja, color: p.estilo.texto, fontFamily, fontWeight: 800, fontSize: 54,
          padding: '12px 30px', borderRadius: 12, boxShadow: sombra, transform: `scale(${cinta}) rotate(-2deg)`}}>{e.cinta}</div>
      ) : null}
    </div>
  );
};

const Objetos: React.FC<{e: Escena; f: number; fps: number; primera: boolean}> = ({e, f, fps, primera}) => {
  const n = e.objetos.length;
  const lado = n === 1 ? 640 : n === 2 ? 420 : 300;
  const fin = (e.fin - e.inicio) * fps;
  const sale = interpolate(f, [fin - 6, fin], [1, 0], CLAMP);
  return (
    <div style={{position: 'absolute', top: primera ? 760 : 620, left: 0, width: 1080, height: lado + 80,
      display: 'flex', justifyContent: 'center', alignItems: 'center', gap: n > 2 ? 0 : 30, opacity: sale}}>
      {e.objetos.map((nombre, i) => {
        const Ilus = ILUSTRACIONES[nombre];
        if (!Ilus) return null;
        const s = spring({frame: f - 4 - i * 6, fps, config: {damping: 11, mass: 0.7}});
        const flota = Math.sin((f + i * 20) / 18) * 8;
        const giro = interpolate(s, [0, 1], [-14, 0]);
        return (
          <svg key={i} width={lado} height={lado} viewBox="0 0 400 400"
            style={{transform: `translateY(${flota}px) scale(${s}) rotate(${giro}deg)`,
              filter: 'drop-shadow(0 22px 18px rgba(0,0,0,0.38))'}}>
            <Defs />
            <Ilus />
          </svg>
        );
      })}
    </div>
  );
};

/** Subtítulos de tres en tres palabras, con la que suena en el color de acento. */
const Subtitulos: React.FC<{p: Props; t: number}> = ({p, t}) => {
  const grupos: Palabra[][] = [];
  p.palabras.forEach((w) => {
    const g = grupos[grupos.length - 1];
    if (!g || g.length >= 3 || /[.,:;?!]$/.test(g[g.length - 1].texto)) grupos.push([w]);
    else g.push(w);
  });
  const g = grupos.find((x) => t >= x[0].t && t < x[x.length - 1].fin + 0.05);
  if (!g) return null;
  return (
    <div style={{position: 'absolute', top: 1290, left: CENTRO_X - ANCHO_TEXTO / 2, width: ANCHO_TEXTO, textAlign: 'center',
      fontFamily, fontWeight: 800, fontSize: 70, lineHeight: 1.1, color: p.estilo.texto,
      textShadow: '0 4px 0 rgba(0,0,0,0.35), 0 10px 24px rgba(0,0,0,0.6)'}}>
      {g.map((w, i) => {
        const activa = t >= w.t && t < w.fin;
        const s = interpolate(t, [w.t, w.t + 0.08], [0.9, 1], {...CLAMP, easing: EXPO});
        return (
          <span key={i} style={{display: 'inline-block', margin: '0 10px', color: activa ? p.estilo.subrayado : p.estilo.texto,
            transform: `scale(${t >= w.t ? s : 0.9})`, opacity: t >= w.t ? 1 : 0.55}}>{w.texto}</span>
        );
      })}
    </div>
  );
};

export const Explicativo: React.FC<Props> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const actual = p.escenas.findIndex((e) => t >= e.inicio && t < e.fin);
  const e = p.escenas[actual === -1 ? p.escenas.length - 1 : actual];
  const f = frame - Math.round(e.inicio * fps);
  const primera = e === p.escenas[0];
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <Mesa p={p} />
      <Marco />
      {primera
        ? <Titulo p={p} f={f} fps={fps} fin={Math.round((e.fin - e.inicio) * fps)} />
        : e.etiqueta ? <Etiqueta e={e} p={p} f={f} fps={fps} /> : null}
      <Objetos key={actual} e={e} f={f} fps={fps} primera={primera} />
      <Subtitulos p={p} t={t} />
      {p.audio ? <Audio src={staticFile(p.audio)} /> : null}
    </AbsoluteFill>
  );
};
