import React from 'react';
import {Img, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import * as Caveat from '@remotion/google-fonts/Caveat';
import {ramp, useEstilo} from './estilo';
import type {Grafico} from './tipos';

/**
 * Interfaz sobre el lienzo (mitad de arriba de la pantalla partida), al estilo de los reels de creadores de IA: logos de
 * apps, cuadrícula de miniaturas con barra de chat, tarjeta de pasos con nota a mano, píldora, tarjetas en abanico que se
 * enfocan, tarjetas de perfil y carpeta con miniaturas. Mismo lenguaje que generacion_videos/remotion/src/lienzo.tsx.
 * Las imágenes son las del reel (carpeta pública «imagenes/»): `valor` de cada elemento es su archivo.
 */
type Efecto = Extract<Grafico, {tipo: 'efecto'}>;
type Pieza = React.FC<{g: Efecto}>;

const mano = Caveat.loadFont('normal', {weights: ['700'], subsets: ['latin', 'latin-ext']}).fontFamily;
const tinta = '#16181d';
const gris = 'rgba(16,24,40,0.08)';
const sombraUI = '0 1px 2px rgba(16,24,40,0.06), 0 12px 32px rgba(16,24,40,0.12)';
const imagen = (archivo?: string) => staticFile(`imagenes/${archivo ?? ''}`);

/** Entrada con rebote corto (el de la interfaz de referencia): 0 → 1. */
const useSalto = (at: number, duro = false) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: f - at, fps, config: duro ? {damping: 11, mass: 0.6, stiffness: 220} : {damping: 16, mass: 0.6, stiffness: 200}});
};

const Caja: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 960}}>{children}</div>
);

/** Logos de las apps que nombra, en baldosa blanca, saltando en arco encima de la cabeza. */
const Logos: Pieza = ({g}) => {
  const sitios = [[-300, 60], [0, -30], [300, 60], [-150, 230], [150, 230]];
  return (
    <Caja>
      {/* En el gancho (fotograma 0, la portada) el primero ya está asentado; los demás saltan a su tiempo. */}
      {g.elementos.map((el, i) => <Logo key={i} archivo={el.valor} at={el.f <= 0 ? -30 : el.f} sitio={sitios[i % sitios.length]} giro={i % 2 ? 6 : -6} />)}
    </Caja>
  );
};
const Logo: React.FC<{archivo?: string; at: number; sitio: number[]; giro: number}> = ({archivo, at, sitio, giro}) => {
  const s = useSalto(at, true);
  const tam = 210;
  return (
    <div style={{position: 'absolute', left: 540 + sitio[0] - tam / 2, top: 470 + sitio[1] - tam / 2, width: tam, height: tam, borderRadius: 50,
      background: '#fff', boxShadow: sombraUI, display: 'flex', alignItems: 'center', justifyContent: 'center',
      transform: `scale(${s}) rotate(${giro * s}deg)`}}>
      <Img src={imagen(archivo)} style={{width: tam * 0.62, height: tam * 0.62, objectFit: 'contain'}} />
    </div>
  );
};

/** Cuadrícula de miniaturas (3 por fila) que entran una tras otra y, si hay `titulo`, debajo la barra de chat con ese texto. */
const Miniaturas: Pieza = ({g}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const imgs = g.elementos.filter((x) => x.valor);
  const w = 272, h = 153, gap = 16;
  const x0 = (1080 - (3 * w + 2 * gap)) / 2;
  const filas = Math.ceil(imgs.length / 3);
  const y0 = g.titulo ? 250 : 480 - (filas * (h + gap) - gap) / 2;
  const yChat = y0 + filas * (h + gap) + 30;
  const chat = ramp(f, g.f + 8, g.f + 16);
  return (
    <Caja>
      {imgs.map((el, i) => <Miniatura key={i} archivo={el.valor} at={el.f} x={x0 + (i % 3) * (w + gap)} y={y0 + Math.floor(i / 3) * (h + gap)} w={w} h={h} />)}
      {g.titulo && <div style={{position: 'absolute', left: x0, width: 3 * w + 2 * gap, top: yChat, height: 104, borderRadius: 28, background: '#fff',
        border: '1px solid rgba(16,24,40,0.12)', boxShadow: sombraUI, opacity: chat, transform: `translateY(${(1 - chat) * 24}px)`,
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', padding: '0 18px 16px 28px', boxSizing: 'border-box'}}>
        <div style={{fontFamily: e.sans, fontSize: 28, color: 'rgba(22,24,29,0.45)'}}>{g.titulo}</div>
        <div style={{width: 46, height: 46, borderRadius: 23, background: 'rgba(16,24,40,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <svg width={20} height={20} viewBox="0 0 20 20"><path d="M10 16V4M4 9l6-6 6 6" stroke="#fff" strokeWidth={2.6} fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
      </div>}
    </Caja>
  );
};
const Miniatura: React.FC<{archivo?: string; at: number; x: number; y: number; w: number; h: number}> = ({archivo, at, x, y, w, h}) => {
  const s = useSalto(at);
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, borderRadius: 14, overflow: 'hidden', boxShadow: sombraUI,
      opacity: Math.min(1, s * 1.5), transform: `translateY(${(1 - s) * 30}px) scale(${0.92 + 0.08 * s})`}}>
      <Img src={imagen(archivo)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
    </div>
  );
};

/** Tarjeta de pasos: lista numerada en una tarjeta blanca; el elemento con valor «nota» es la nota a mano en rojo. */
const Pasos: Pieza = ({g}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const pasos = g.elementos.filter((x) => x.valor !== 'nota');
  const nota = g.elementos.find((x) => x.valor === 'nota');
  const entra = ramp(f, g.f, g.f + 7);
  const roja = (e as unknown as {notas?: string}).notas ?? '#E5322D';
  return (
    <Caja>
      <div style={{position: 'absolute', left: 150, top: 300, width: 560, background: '#fff', borderRadius: 22, boxShadow: sombraUI,
        border: '1px solid rgba(16,24,40,0.08)', padding: '26px 34px 18px', boxSizing: 'border-box', opacity: entra,
        transform: `translateY(${(1 - entra) * 26}px)`}}>
        {g.titulo && <div style={{fontFamily: e.sans, fontSize: 20, fontWeight: 700, letterSpacing: 3, textTransform: 'uppercase',
          color: 'rgba(22,24,29,0.4)', marginBottom: 12}}>{g.titulo}</div>}
        {pasos.map((el, i) => {
          const t = ramp(f, el.f, el.f + 6);
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 20, height: 74, borderTop: i ? `1px solid ${gris}` : undefined,
              opacity: 0.25 + 0.75 * t}}>
              <div style={{fontFamily: e.sans, fontSize: 24, fontWeight: 700, color: 'rgba(22,24,29,0.35)', width: 36}}>{String(i + 1).padStart(2, '0')}</div>
              <div style={{fontFamily: e.sans, fontSize: 40, fontWeight: 700, color: tinta}}>{el.texto}</div>
            </div>
          );
        })}
      </div>
      {nota && <Nota texto={nota.texto} at={nota.f} color={roja} />}
    </Caja>
  );
};
const Nota: React.FC<{texto: string; at: number; color: string}> = ({texto, at, color}) => {
  const s = useSalto(at, true);
  return (
    <div style={{position: 'absolute', left: 700, top: 250, width: 250, padding: '20px 22px', background: '#fff', borderRadius: 16, boxShadow: sombraUI,
      transform: `rotate(${6 * s}deg) scale(${s})`, fontFamily: mano, fontWeight: 700, fontSize: 50, lineHeight: 1, color, textAlign: 'center'}}>
      {texto}
    </div>
  );
};

/** Píldora del color de la interfaz, sola, colgando de un hilo desde arriba. */
const Pildora: Pieza = ({g}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const s = useSalto(g.f, true);
  const hilo = ramp(f, g.f, g.f + 8);
  return (
    <Caja>
      <div style={{position: 'absolute', left: 539, top: 0, width: 3, height: 430 * hilo, background: e.lienzoAcento, opacity: 0.85}} />
      <div style={{position: 'absolute', left: 0, right: 0, top: 430, display: 'flex', justifyContent: 'center'}}>
        <div style={{padding: '22px 52px', borderRadius: 60, background: e.lienzoAcento, color: '#fff', fontFamily: e.sans, fontWeight: 700,
          fontSize: 54, boxShadow: `0 14px 40px ${e.lienzoAcento}55`, transform: `scale(${s})`}}>{g.titulo}</div>
      </div>
    </Caja>
  );
};

/** Tarjetas en abanico: entran todas desenfocadas y cada una se enfoca (borde y barra azules) cuando se nombra. */
const Abanico: Pieza = ({g}) => {
  const n = g.elementos.length;
  return (
    <Caja>
      {g.elementos.map((el, i) => <Tarjeta key={i} i={i} n={n} texto={el.texto} entra={g.f + i * 3} foco={el.f} />)}
    </Caja>
  );
};
const Tarjeta: React.FC<{i: number; n: number; texto: string; entra: number; foco: number}> = ({i, n, texto, entra, foco}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const s = useSalto(entra);
  const k = ramp(f, foco, foco + 8);
  const cw = 270;
  const centro = i - (n - 1) / 2;
  return (
    <div style={{position: 'absolute', left: 540 - cw / 2, top: 290, width: cw, height: cw * 1.25, borderRadius: 18, background: '#fff', boxShadow: sombraUI,
      border: `${k > 0.5 ? 3 : 1}px solid ${k > 0.5 ? e.lienzoAcento : 'rgba(16,24,40,0.1)'}`, padding: 22, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', opacity: Math.min(1, s * 1.4), zIndex: k > 0.5 ? 5 : i,
      transform: `translate(${centro * cw * 0.98 * s}px, ${(1 - s) * 40 + Math.abs(centro) * 16 * s - k * 14}px) rotate(${centro * 5 * s}deg)`}}>
      <div style={{filter: `blur(${(1 - k) * 7}px)`, display: 'flex', flexDirection: 'column', flex: 1}}>
        <div style={{fontFamily: e.sans, fontSize: 22, fontWeight: 700, color: 'rgba(22,24,29,0.4)'}}>{String(i + 1).padStart(2, '0')}</div>
        <div style={{fontFamily: e.sans, fontSize: 38, fontWeight: 700, color: tinta, lineHeight: 1.12, marginTop: 10}}>{texto}</div>
        <div style={{flex: 1}} />
        <div style={{height: 6, borderRadius: 3, background: k > 0.5 ? e.lienzoAcento : gris, width: `${45 + 25 * k}%`}} />
      </div>
    </div>
  );
};

/** Tarjetas de perfil de creador (cabecera de canal), genéricas: sin nombres, cuando no hay capturas reales. */
const Perfiles: Pieza = ({g}) => (
  <Caja>
    {g.elementos.map((el, i) => <Perfil key={i} at={el.f} x={150 + i * 60} y={250 + i * 230} />)}
  </Caja>
);
const Perfil: React.FC<{at: number; x: number; y: number}> = ({at, x, y}) => {
  const s = useSalto(at);
  const raya = (w: number, h = 16, c = gris) => <div style={{width: w, height: h, borderRadius: h / 2, background: c}} />;
  return (
    <div style={{position: 'absolute', left: x, top: y, width: 720, height: 250, background: '#fff', borderRadius: 22, boxShadow: sombraUI,
      border: '1px solid rgba(16,24,40,0.08)', display: 'flex', gap: 28, padding: 30, boxSizing: 'border-box',
      opacity: Math.min(1, s * 1.4), transform: `translateY(${(1 - s) * 36}px)`}}>
      <div style={{width: 150, height: 150, borderRadius: 75, flexShrink: 0, background: 'linear-gradient(135deg, #d9dde6, #b8bfcc)'}} />
      <div style={{display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 8}}>
        {raya(260, 30, 'rgba(16,24,40,0.22)')}
        {raya(380)}
        {raya(320)}
        <div style={{marginTop: 6, width: 150, height: 46, borderRadius: 23, background: tinta}} />
      </div>
    </div>
  );
};

/** Carpeta de la skill: la píldora con el nombre y, debajo, las miniaturas (en vertical, como reels) que contiene. */
const CarpetaSkill: Pieza = ({g}) => {
  const e = useEstilo();
  const s = useSalto(g.f, true);
  const imgs = g.elementos.filter((x) => x.valor);
  const w = 196, h = 300, gap = 16;
  const x0 = (1080 - (imgs.length * w + (imgs.length - 1) * gap)) / 2;
  return (
    <Caja>
      <div style={{position: 'absolute', left: 0, right: 0, top: 250, display: 'flex', justifyContent: 'center'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 16, padding: '18px 34px', borderRadius: 40, background: e.lienzoAcento, color: '#fff',
          fontFamily: e.sans, fontWeight: 700, fontSize: 40, boxShadow: `0 14px 40px ${e.lienzoAcento}55`, transform: `scale(${s})`}}>
          <svg width={38} height={30} viewBox="0 0 30 24"><path d="M2 4a2 2 0 0 1 2-2h7l3 3h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z" fill="#fff" /></svg>
          {g.titulo}
        </div>
      </div>
      {imgs.map((el, i) => <Miniatura key={i} archivo={el.valor} at={el.f} x={x0 + i * (w + gap)} y={400} w={w} h={h} />)}
    </Caja>
  );
};

export const PIEZAS_INTERFAZ: Record<string, Pieza> = {
  logos: Logos, miniaturas: Miniaturas, pasos: Pasos, pildora: Pildora, abanico: Abanico, perfiles: Perfiles, carpeta: CarpetaSkill,
};
export const esInterfaz = (clase: string) => clase in PIEZAS_INTERFAZ;
