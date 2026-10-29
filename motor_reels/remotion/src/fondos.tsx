import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {useEstilo} from './estilo';
import type {Fondo} from './tipos';

/**
 * Fondos para quitar el fondo, la pantalla partida y los efectos a pantalla completa. Nunca un color liso (manual,
 * sección 4): luz en movimiento, rejilla en perspectiva o una foto del cliente con un acercamiento lento.
 */

/** Luz: tres manchas suaves de los colores del kit que derivan despacio, con viñeta. */
const Luz: React.FC = () => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const mancha = (cx: number, cy: number, r: number, color: string, fase: number) => {
    const x = cx + Math.sin(f / 70 + fase) * 9;
    const y = cy + Math.cos(f / 85 + fase * 1.3) * 7;
    return `radial-gradient(circle at ${x}% ${y}%, ${color} 0%, transparent ${r}%)`;
  };
  return (
    <AbsoluteFill style={{
      backgroundColor: e.fondo,
      backgroundImage: [
        mancha(30, 28, 55, `${e.fondoLuz}`, 0),
        mancha(78, 62, 45, `${e.acento}33`, 2.1),
        mancha(40, 90, 50, `${e.panel}`, 4.2),
        `radial-gradient(ellipse 120% 90% at 50% 45%, transparent 55%, ${e.fondo} 100%)`,
      ].join(', '),
    }} />
  );
};

/** Rejilla: suelo en perspectiva que avanza hacia la cámara, con el horizonte iluminado. */
const Rejilla: React.FC = () => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const avance = (f * 1.6) % 80;
  const horizontes = Array.from({length: 14}, (_, i) => i);
  return (
    <AbsoluteFill style={{backgroundColor: e.fondo, overflow: 'hidden'}}>
      <AbsoluteFill style={{background: `radial-gradient(ellipse 90% 40% at 50% 46%, ${e.fondoLuz} 0%, transparent 70%)`}} />
      <svg width="1080" height="1920" style={{position: 'absolute', inset: 0}}>
        {/* Líneas que fugan al centro del horizonte */}
        {Array.from({length: 17}, (_, i) => -800 + i * 167).map((x, i) => (
          <line key={`v${i}`} x1={540} y1={880} x2={540 + x * 2.2} y2={1920} stroke={e.acento} strokeOpacity={0.32} strokeWidth={1.6} />
        ))}
        {/* Líneas horizontales que avanzan: más juntas cerca del horizonte */}
        {horizontes.map((i) => {
          const d = (i * 80 + avance) / (14 * 80);
          const y = 880 + Math.pow(d, 2.2) * 1040;
          return <line key={`h${i}`} x1={0} y1={y} x2={1080} y2={y} stroke={e.acento} strokeOpacity={0.15 + d * 0.3} strokeWidth={1.4} />;
        })}
      </svg>
      <AbsoluteFill style={{background: `linear-gradient(to bottom, ${e.fondo} 0%, transparent 40%, transparent 70%, ${e.fondo}CC 100%)`}} />
    </AbsoluteFill>
  );
};

/** Foto del cliente: oscurecida para que lo de delante se lea, con un acercamiento lento. */
const Foto: React.FC<{archivo: string}> = ({archivo}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  return (
    <AbsoluteFill style={{backgroundColor: e.fondo, overflow: 'hidden'}}>
      <Img src={staticFile(`imagenes/${archivo}`)} style={{
        width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${1.08 + f * 0.0007})`, filter: 'blur(5px)',
      }} />
      <AbsoluteFill style={{background: `linear-gradient(to bottom, ${e.fondo}B3, ${e.fondo}80 40%, ${e.fondo}D9)`}} />
    </AbsoluteFill>
  );
};

/** Color sólido del kit (el gancho con la palabra gigante): plano, con una viñeta muy suave para que no parezca un hueco. */
const Solido: React.FC = () => {
  const e = useEstilo();
  return <AbsoluteFill style={{backgroundColor: e.fondoLuz, backgroundImage: `radial-gradient(ellipse 90% 70% at 50% 40%, transparent 55%, ${e.fondo}99)`}} />;
};

/**
 * Mosaico: capturas reales (miniaturas de vídeos, publicaciones) a pantalla completa por detrás de la persona, en
 * cuadrícula un poco girada que entra en cascada y sube despacio. Sin desenfoque: se tienen que reconocer. Un velo del
 * color de fondo arriba y abajo deja leer subtítulos y rótulos. Para cuando nombra «mil vídeos de YouTube» (cliente cero,
 * 28/10/2026: mejor que la pantalla partida en estos casos).
 */
const Mosaico: React.FC<{archivos: string[]}> = ({archivos}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  // Cinco columnas de miniaturas pequeñas: se tienen que ver muchos vídeos alrededor de él, no dos o tres (cliente cero).
  const cols = 5, w = 300, h = 169, gap = 12, filas = 15;
  const anchoTotal = cols * w + (cols - 1) * gap;
  const deriva = -f * 0.9;
  return (
    <AbsoluteFill style={{backgroundColor: e.fondo, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: (1080 - anchoTotal) / 2, top: -260 + deriva, width: anchoTotal,
        transform: 'rotate(-7deg) scale(1.08)', transformOrigin: '50% 40%', display: 'flex', flexWrap: 'wrap', gap}}>
        {Array.from({length: cols * filas}, (_, i) => {
          const entra = Math.min(1, Math.max(0, (f - (i % 13) * 0.5) / 6));
          return (
            <div key={i} style={{width: w, height: h, borderRadius: 14, overflow: 'hidden', opacity: entra,
              transform: `scale(${0.92 + 0.08 * entra})`, boxShadow: '0 10px 30px rgba(0, 0, 0, 0.45)'}}>
              <Img src={staticFile(`imagenes/${archivos[i % archivos.length]}`)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            </div>
          );
        })}
      </div>
      <AbsoluteFill style={{background: `linear-gradient(to bottom, ${e.fondo}B0 0%, transparent 22%, transparent 60%, ${e.fondo}D0 100%)`}} />
    </AbsoluteFill>
  );
};

export const FondoAnimado: React.FC<{fondo?: Fondo; style?: React.CSSProperties}> = ({fondo, style}) => (
  <AbsoluteFill style={style}>
    {fondo && typeof fondo === 'object' && 'mosaico' in fondo ? <Mosaico archivos={fondo.mosaico} />
      : fondo && typeof fondo === 'object' ? <Foto archivo={fondo.foto} /> : fondo === 'rejilla' ? <Rejilla /> : fondo === 'solido' ? <Solido /> : <Luz />}
  </AbsoluteFill>
);
