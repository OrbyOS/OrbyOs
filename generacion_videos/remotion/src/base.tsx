import React from 'react';
import {Easing, continueRender, delayRender, interpolate, spring, staticFile} from 'remotion';
import {loadFont} from '@remotion/google-fonts/InterTight';
import type {Estilo} from './tipos';

const inter = loadFont('normal', {weights: ['600', '700', '800', '900'], subsets: ['latin', 'latin-ext']});
// La tipografía de la marca (la del Kit, si la hay) va en la variable --fuente-marca; si no, Inter Tight.
export const fontFamily = `var(--fuente-marca, ${inter.fontFamily})`;

export const W = 1080;
export const H = 1920;
// Zona segura de Instagram (la misma que el motor de reels): el texto va entre x 60-850 e y 230-1440.
export const CX = 470;
export const ANCHO = 780;
export const ESCENARIO = {top: 590, alto: 680}; // donde va lo principal de cada plano
// Lo dibujado va algo más al centro de la pantalla que el texto: a la derecha solo tapan los botones más abajo.
export const CV = 510;

export const CLAMP = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const EXPO = Easing.bezier(0.16, 1, 0.3, 1);
export const ramp = (f: number, a: number, b: number, ease = EXPO) => interpolate(f, [a, b], [0, 1], {...CLAMP, easing: ease});

/** Cómo entra todo: un muelle muy amortiguado, rápido y casi sin rebote (se asienta en unos 8 fotogramas).
 * «rebote» queda por compatibilidad: cuanto más bajo, algo más vivo, pero nunca bota. */
export const pop = (f: number, fps: number, retraso = 0, rebote = 9) =>
  spring({frame: f - retraso, fps, config: {damping: 18 + rebote * 0.6, mass: 0.5, stiffness: 230}});
export const suave = (f: number, fps: number, retraso = 0) =>
  spring({frame: f - retraso, fps, config: {damping: 18, mass: 0.6}});

export const sombra = '0 8px 0 rgba(0,0,0,0.22), 0 22px 44px rgba(0,0,0,0.45)';
export const sombraTexto = '0 4px 0 rgba(0,0,0,0.3), 0 10px 26px rgba(0,0,0,0.55)';

export const EstiloCtx = React.createContext<Estilo>(null as unknown as Estilo);
export const useEstilo = () => React.useContext(EstiloCtx);

/** Tarjeta de cristal azul, la de la app. */
export const Tarjeta: React.FC<{children: React.ReactNode; style?: React.CSSProperties; claro?: boolean}> = ({children, style, claro}) => (
  <div style={{
    background: claro ? 'linear-gradient(180deg, #ffffff, #e9efff)' : 'linear-gradient(180deg, rgba(40, 70, 160, 0.55), rgba(12, 24, 70, 0.75))',
    border: claro ? '3px solid #ffffff' : '2px solid rgba(150, 185, 255, 0.35)',
    boxShadow: `${sombra}, inset 0 2px 0 rgba(255,255,255,${claro ? 1 : 0.18})`,
    borderRadius: 34, color: claro ? '#0c1a44' : '#fff', fontFamily, ...style,
  }}>{children}</div>
);

/** Texto con una parte resaltada. */
export const ConResalte: React.FC<{texto: string; resalte?: string; color: string}> = ({texto, resalte, color}) => {
  const i = resalte ? texto.indexOf(resalte) : -1;
  if (i < 0 || !resalte) return <>{texto}</>;
  return <>{texto.slice(0, i)}<span style={{color}}>{resalte}</span>{texto.slice(i + resalte.length)}</>;
};

/** Destellos que saltan alrededor de algo cuando aparece. Apagados: eran un efecto más encima de cada entrada y la
 * regla es un efecto a la vez. Se dejan solo si un plano los pide expresamente (forzar). */
export const Destellos: React.FC<{f: number; color: string; radio?: number; n?: number; forzar?: boolean}> = ({f, color, radio = 260, n = 8, forzar}) => {
  if (!forzar || f < 0 || f > 22) return null;
  const p = ramp(f, 0, 20);
  return (
    <svg width={radio * 3} height={radio * 3} viewBox={`${-radio * 1.5} ${-radio * 1.5} ${radio * 3} ${radio * 3}`}
      style={{position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', pointerEvents: 'none'}}>
      {Array.from({length: n}).map((_, i) => {
        const a = (i / n) * Math.PI * 2 + 0.3;
        const r1 = radio * (0.7 + 0.5 * p), r2 = r1 + 50 * (1 - p);
        return <line key={i} x1={Math.cos(a) * r1} y1={Math.sin(a) * r1} x2={Math.cos(a) * r2} y2={Math.sin(a) * r2}
          stroke={color} strokeWidth={12 * (1 - p) + 1} strokeLinecap="round" opacity={1 - p} />;
      })}
    </svg>
  );
};

/** Velo difuso detrás del texto: cristal desenfocado que se funde por los bordes, nunca una caja. Va en el color de
 * fondo de la marca para que el texto se lea encima de cualquier cosa. */
export const Velo: React.FC<{children: React.ReactNode; style?: React.CSSProperties; fuerza?: number}> = ({children, style, fuerza = 1}) => {
  const e = useEstilo();
  return (
    <div style={{position: 'relative', ...style}}>
      <div style={{position: 'absolute', inset: '-40px -70px', borderRadius: '50%', filter: 'blur(36px)',
        background: `radial-gradient(ellipse at center, color-mix(in srgb, ${e.mesa} ${Math.round(78 * fuerza)}%, transparent) 0%, transparent 72%)`}} />
      <div style={{position: 'relative'}}>{children}</div>
    </div>
  );
};

/** Rótulo plano: texto limpio con un filete de acento debajo que se dibuja con él. Sin caja, sin píldora, sin inclinar. */
export const Filete: React.FC<{texto: React.ReactNode; k: number; tam?: number; color?: string; mayus?: boolean; ancho?: number}> = ({
  texto, k, tam = 44, color, mayus = true, ancho = 120,
}) => {
  const e = useEstilo();
  return (
    <Velo>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: Math.round(tam * 0.32)}}>
        <div style={{fontFamily, fontWeight: 800, fontSize: tam, letterSpacing: mayus ? tam * 0.06 : 0, lineHeight: 1.1, color: '#fff',
          textTransform: mayus ? 'uppercase' : 'none', textAlign: 'center', opacity: Math.min(1, k * 1.4),
          transform: `translateY(${(1 - k) * 14}px)`, textShadow: '0 2px 18px rgba(0,0,0,0.45)'}}>{texto}</div>
        <div style={{height: Math.max(4, Math.round(tam * 0.09)), width: ancho * k, borderRadius: 4, background: color ?? e.acento}} />
      </div>
    </Velo>
  );
};

/** Raíz de cada composición: carga la tipografía de la marca (si el Kit trae una) y la deja en --fuente-marca. */
export const ConMarca: React.FC<{estilo: Estilo; children: React.ReactNode}> = ({estilo, children}) => {
  const [lista, setLista] = React.useState(!estilo.fuente);
  React.useEffect(() => {
    if (!estilo.fuente) return;
    const espera = delayRender('Tipografía de la marca');
    new FontFace('FuenteMarca', `url(${staticFile(estilo.fuente)})`).load()
      .then((f) => { document.fonts.add(f); setLista(true); })
      .catch(() => setLista(true))
      .finally(() => continueRender(espera));
  }, [estilo.fuente]);
  return (
    <EstiloCtx.Provider value={estilo}>
      <div style={{position: 'absolute', inset: 0, ...(estilo.fuente && lista ? {['--fuente-marca' as string]: 'FuenteMarca'} : {})}}>{children}</div>
    </EstiloCtx.Provider>
  );
};
