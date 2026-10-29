import React from 'react';
import {Img, interpolate, spring, staticFile} from 'remotion';
import * as Caveat from '@remotion/google-fonts/Caveat';
import {CLAMP, EXPO, fontFamily, ramp, useEstilo} from './base';
import type {Estilo, Palabra} from './tipos';

/**
 * Piezas del vídeo a cámara con «lienzo»: la interfaz limpia sobre blanco que se ve en los reels de creadores de IA
 * (carpetas en las que se marca una fila, tarjetas que se abanican, capturas con rotulador y notas a mano), los logos
 * que saltan junto a la cabeza, el sello de la sección y los subtítulos cortos. Todo sale del kit (EstiloCara): nada de
 * un creador concreto va aquí.
 */
export type EstiloCara = Estilo & {
  lienzo?: string;      // fondo de la interfaz (blanco por defecto)
  interfaz?: string;    // color de lo que se marca en la interfaz (la fila, la tarjeta)
  marcador?: string;    // rotulador de las pruebas
  notas?: string;       // tinta de las notas a mano
  subtitulos?: 'cortos' | 'normales';
};
export const useEstiloCara = () => useEstilo() as EstiloCara;
type PP = {p: Record<string, unknown>; f: number; fps: number; dur: number; ancho: number; alto: number};

const mano = Caveat.loadFont('normal', {weights: ['600', '700'], subsets: ['latin', 'latin-ext']}).fontFamily;
const lista = <T,>(v: unknown) => (Array.isArray(v) ? (v as T[]) : []);
const txt = (v: unknown) => (typeof v === 'string' ? v : '');
const golpe = (p: Record<string, unknown>, i: number, porDefecto: number) => {
  const g = lista<number>(p.golpes);
  return g.length ? (g[i] ?? g[g.length - 1] + (i - g.length + 1) * 8) : porDefecto;
};
const tinta = '#16181d';
const sombraUI = '0 1px 2px rgba(16,24,40,0.06), 0 12px 32px rgba(16,24,40,0.12)';

export const FondoLienzo: React.FC = () => {
  const e = useEstiloCara();
  return <div style={{position: 'absolute', inset: 0, background: e.lienzo ?? '#FFFFFF'}} />;
};

/** Ventana de una app (tres puntos y título): el marco de las interfaces del lienzo. */
const Ventana: React.FC<{titulo?: string; ancho: number; children: React.ReactNode; style?: React.CSSProperties}> = ({titulo, ancho, children, style}) => (
  <div style={{width: ancho, background: '#fff', borderRadius: 22, boxShadow: sombraUI, border: '1px solid rgba(16,24,40,0.08)', ...style}}>
    <div style={{height: 46, display: 'flex', alignItems: 'center', gap: 9, padding: '0 20px', borderBottom: '1px solid rgba(16,24,40,0.06)'}}>
      {['#ff5f57', '#febc2e', '#28c840'].map((c) => <div key={c} style={{width: 13, height: 13, borderRadius: 7, background: c}} />)}
      <div style={{flex: 1, textAlign: 'center', fontFamily, fontSize: 19, fontWeight: 600, color: 'rgba(22,24,29,0.55)', marginRight: 60}}>{titulo}</div>
    </div>
    {children}
  </div>
);

const Carpeta: React.FC<{color: string}> = ({color}) => (
  <svg width={30} height={24} viewBox="0 0 30 24"><path d="M2 4a2 2 0 0 1 2-2h7l3 3h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z" fill={color} /></svg>
);

/** Carpetas: una lista de carpetas en su ventana; en su golpe se marca una fila en el color de la interfaz (barrido de
 * izquierda a derecha) y, con «acerca», esa fila se adelanta y crece como si se abriera. */
export const Carpetas: React.FC<PP> = ({p, f, ancho, alto}) => {
  const e = useEstiloCara();
  const azul = e.interfaz ?? '#2F5BEA';
  const filas = lista<string>(p.items);
  const marca = typeof p.marca === 'number' ? p.marca : -1;
  const g = golpe(p, 0, 12);
  const k = interpolate(f, [g, g + 8], [0, 1], {...CLAMP, easing: EXPO});
  const acerca = p.acerca ? interpolate(f, [g + 14, g + 26], [0, 1], {...CLAMP, easing: EXPO}) : 0;
  const entra = ramp(f, 0, 7);
  const w = 640;
  const zoom = Math.min((ancho - 140) / w, (alto - 120) / (46 + 30 + filas.length * 58));
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{opacity: entra, transform: `scale(${zoom * (1.03 - 0.03 * entra)})`}}>
        <Ventana titulo={txt(p.titulo)} ancho={w}>
          <div style={{padding: '12px 14px 18px'}}>
            {filas.map((x, i) => {
              const activa = i === marca;
              return (
                <div key={i} style={{position: 'relative', height: 58, display: 'flex', alignItems: 'center', gap: 16, padding: '0 16px',
                  borderRadius: 12, zIndex: activa ? 2 : 1,
                  transform: activa ? `scale(${1 + 0.18 * acerca})` : undefined, boxShadow: activa && acerca ? `0 18px 50px ${azul}55` : undefined}}>
                  {activa && <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: `${k * 100}%`, background: azul, borderRadius: 12}} />}
                  <div style={{position: 'relative', display: 'flex', alignItems: 'center', gap: 16, flex: 1}}>
                    <Carpeta color={activa && k > 0.5 ? '#fff' : azul} />
                    <div style={{fontFamily, fontSize: 25, fontWeight: 600, color: activa && k > 0.5 ? '#fff' : tinta}}>{x}</div>
                  </div>
                  <div style={{position: 'relative', fontFamily, fontSize: 18, color: activa && k > 0.5 ? 'rgba(255,255,255,0.8)' : 'rgba(22,24,29,0.4)'}}>
                    {activa && k > 0.5 && txt(p.etiqueta) ? txt(p.etiqueta) : '···'}
                  </div>
                </div>
              );
            })}
          </div>
        </Ventana>
      </div>
    </div>
  );
};

/** Tarjetas: un mazo que se abanica (cada una entra en su golpe, girada un poco) con número, título y una barra; la
 * tarjeta «marca» se queda con el borde y la barra del color de la interfaz. */
export const Tarjetas: React.FC<PP> = ({p, f, fps, ancho}) => {
  const e = useEstiloCara();
  const azul = e.interfaz ?? '#2F5BEA';
  const items = lista<string>(p.items);
  const marca = typeof p.marca === 'number' ? p.marca : -1;
  const n = items.length;
  const cw = Math.min(330, (ancho - 120) / Math.max(1, n) + 90);
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      {items.map((x, i) => {
        const g = golpe(p, i, 6 + i * 6);
        const s = spring({frame: f - g, fps, config: {damping: 16, mass: 0.6, stiffness: 200}});
        const centro = i - (n - 1) / 2;
        const dx = centro * (cw * 0.95) * s;
        const giro = centro * 4 * s;
        const activa = i === marca && f >= g + 10;
        return (
          <div key={i} style={{position: 'absolute', width: cw, height: cw * 1.25, borderRadius: 18, background: '#fff', boxShadow: sombraUI,
            border: `${activa ? 3 : 1}px solid ${activa ? azul : 'rgba(16,24,40,0.1)'}`, opacity: Math.min(1, s * 1.4),
            transform: `translate(${dx}px, ${(1 - s) * 40 + Math.abs(centro) * 14 * s}px) rotate(${giro}deg)`, padding: 22, boxSizing: 'border-box',
            display: 'flex', flexDirection: 'column', zIndex: activa ? 5 : i}}>
            <div style={{fontFamily, fontSize: 22, fontWeight: 700, color: 'rgba(22,24,29,0.4)'}}>{String(i + 1).padStart(2, '0')}</div>
            <div style={{fontFamily, fontSize: 38, fontWeight: 700, color: tinta, lineHeight: 1.12, marginTop: 10}}>{x}</div>
            <div style={{flex: 1}} />
            <div style={{height: 6, borderRadius: 3, background: activa ? azul : 'rgba(16,24,40,0.08)', width: activa ? '70%' : '45%'}} />
          </div>
        );
      })}
    </div>
  );
};

type Marca = {x: number; y: number; w: number; h: number; en?: number};
type Nota = {texto: string; x: number; y: number; en?: number; giro?: number};
type Circulo = {x: number; y: number; w: number; h: number; en?: number};

/** Captura de prueba: la imagen real centrada en su caja, con la cifra subrayada con rotulador (se pinta de izquierda a
 * derecha en su golpe, debajo del texto) y notas a mano con un círculo que se dibuja. Medidas en píxeles de la imagen. */
export const Captura: React.FC<PP> = ({p, f, ancho, alto}) => {
  const e = useEstiloCara();
  const iw = Number(p.ancho) || 1080, ih = Number(p.alto) || 1080;
  const margen = p.flota ? 0 : 70;
  const esc = Math.min((ancho - 2 * margen - 40) / iw, (alto - 2 * margen) / ih);
  const w = iw * esc, h = ih * esc;
  const entra = ramp(f, 0, 7);
  const rotulador = e.marcador ?? '#FFE14D';
  const roja = e.notas ?? '#E5484D';
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'relative', width: w, height: h, opacity: entra, transform: `scale(${1.03 - 0.03 * entra})`,
        borderRadius: 18, boxShadow: sombraUI, background: '#fff'}}>
        {lista<Marca>(p.marcas).map((m, i) => {
          const k = interpolate(f, [m.en ?? 12, (m.en ?? 12) + 9], [0, 1], {...CLAMP, easing: EXPO});
          return <div key={i} style={{position: 'absolute', left: (m.x - 6) * esc, top: (m.y + m.h * 0.12) * esc, height: m.h * 0.82 * esc,
            width: (m.w + 12) * esc * k, background: rotulador, borderRadius: 6, transform: 'skewX(-8deg)', opacity: 0.9}} />;
        })}
        <Img src={staticFile(txt(p.archivo))} style={{position: 'absolute', inset: 0, width: w, height: h, borderRadius: 18, mixBlendMode: 'multiply'}} />
        <svg width={w} height={h} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
          {lista<Circulo>(p.circulos).map((c, i) => {
            const k = interpolate(f, [c.en ?? 14, (c.en ?? 14) + 12], [0, 1], {...CLAMP, easing: EXPO});
            const rx = (c.w / 2 + 14) * esc, ry = (c.h / 2 + 12) * esc, largo = Math.PI * (rx + ry) * 1.1;
            return <ellipse key={i} cx={(c.x + c.w / 2) * esc} cy={(c.y + c.h / 2) * esc} rx={rx} ry={ry} fill="none" stroke={roja}
              strokeWidth={4} strokeLinecap="round" strokeDasharray={largo} strokeDashoffset={largo * (1 - k)} transform={`rotate(-4 ${(c.x + c.w / 2) * esc} ${(c.y + c.h / 2) * esc})`} />;
          })}
        </svg>
        {lista<Nota>(p.notas).map((n, i) => (
          <div key={i} style={{position: 'absolute', left: n.x * esc, top: n.y * esc, fontFamily: mano, fontWeight: 700, fontSize: 38, color: roja,
            lineHeight: 1, whiteSpace: 'pre', opacity: ramp(f, n.en ?? 16, (n.en ?? 16) + 5), transform: `rotate(${n.giro ?? -4}deg)`}}>{n.texto}</div>
        ))}
      </div>
    </div>
  );
};

/** Logos de las apps que nombra: saltan alrededor de la cabeza (con algo de rebote, es su gracia), cada uno en su golpe,
 * y se van con su frase. Las posiciones rodean la cara sin taparla. */
export const Logos: React.FC<{p: Record<string, unknown>; f: number; fps: number; centro: {x: number; y: number}}> = ({p, f, fps, centro}) => {
  const items = lista<string>(p.archivos);
  const cx = centro.x * 1080, cy = centro.y * 1920;
  const sitios = [[-300, -40], [270, -170], [300, 120], [-250, 230], [-120, -330], [160, 330]];
  return (
    <>
      {items.map((a, i) => {
        const g = golpe(p, i, i * 4);
        const s = spring({frame: f - g, fps, config: {damping: 11, mass: 0.6, stiffness: 220}});
        const [dx, dy] = sitios[i % sitios.length];
        const tam = 176;
        return (
          <Img key={i} src={staticFile(a)} style={{position: 'absolute', left: cx + dx - tam / 2, top: cy + dy - tam / 2, width: tam, height: tam,
            borderRadius: 40, transform: `scale(${s}) rotate(${(i % 2 ? 6 : -6) * s}deg)`, boxShadow: '0 14px 40px rgba(0,0,0,0.35)', objectFit: 'cover'}} />
        );
      })}
    </>
  );
};

/** Sello de la sección (el «… of the week» de cada creador, con su nombre): la palabra grande en blanco, la cinta del
 * color de la marca en cursiva a mano debajo y un lazo encima. Entra de golpe y se va con su frase: nunca se queda fijo. */
export const SelloSerie: React.FC<{p: Record<string, unknown>; f: number; fps: number}> = ({p, f, fps}) => {
  const e = useEstiloCara();
  const s = spring({frame: f, fps, config: {damping: 13, mass: 0.6, stiffness: 210}});
  const cinta = spring({frame: f - 5, fps, config: {damping: 15, mass: 0.6, stiffness: 200}});
  const lazo = e.notas ?? '#E5484D';
  return (
    <div style={{position: 'absolute', left: 90, top: 260, transform: `scale(${0.85 + 0.15 * s})`, transformOrigin: '0 50%', opacity: Math.min(1, s * 1.5)}}>
      {p.lazo !== false && (
        <svg width={90} height={70} viewBox="0 0 90 70" style={{position: 'absolute', left: 140, top: -78}}>
          <path d="M45 40 C25 10 5 20 15 40 C22 52 38 46 45 40 Z M45 40 C65 10 85 20 75 40 C68 52 52 46 45 40 Z" fill={lazo} />
          <rect x={20} y={40} width={50} height={26} rx={4} fill={lazo} />
        </svg>
      )}
      <div style={{fontFamily, fontWeight: 800, fontSize: 190, lineHeight: 0.9, color: '#fff', letterSpacing: '-0.03em',
        textShadow: '0 6px 30px rgba(0,0,0,0.35)'}}>{txt(p.palabra)}</div>
      <div style={{position: 'absolute', left: 120, top: 150, padding: '8px 26px 14px', background: e.subrayado,
        transform: `rotate(-6deg) scaleX(${cinta})`, transformOrigin: '0 50%', boxShadow: '0 10px 30px rgba(0,0,0,0.3)'}}>
        <div style={{fontFamily: mano, fontWeight: 700, fontSize: 64, color: '#fff', whiteSpace: 'nowrap', lineHeight: 1}}>{txt(p.cinta)}</div>
      </div>
    </div>
  );
};

/** Subtítulos cortos: 1-3 palabras cada vez, blancos y pequeños, sin caja (sombra suave), centrados a la altura del
 * pecho. Un grupo se corta en una pausa, en una coma o al llegar a 3 palabras. */
export const SubtitulosCortos: React.FC<{palabras: Palabra[]; t: number; top?: number}> = ({palabras, t, top = 1240}) => {
  const grupos = React.useMemo(() => {
    const gs: Palabra[][] = [];
    let g: Palabra[] = [];
    palabras.forEach((w, i) => {
      g.push(w);
      const sig = palabras[i + 1];
      if (g.length >= 3 || /[.,;:?!]$/.test(w.texto) || !sig || sig.t - w.fin > 0.25) { gs.push(g); g = []; }
    });
    return gs;
  }, [palabras]);
  const g = grupos.find((x) => t >= x[0].t - 0.03 && t < x[x.length - 1].fin + 0.08);
  if (!g) return null;
  return (
    <div style={{position: 'absolute', top, left: 90, width: 900, textAlign: 'center', fontFamily, fontWeight: 600, fontSize: 52, color: '#fff',
      letterSpacing: '-0.01em', textShadow: '0 2px 10px rgba(0,0,0,0.45), 0 1px 2px rgba(0,0,0,0.5)'}}>
      {g.map((w) => w.texto).join(' ')}
    </div>
  );
};

// Piezas que se dibujan en la mitad de arriba (o flotando sobre el vídeo): reciben su caja.
export const PIEZAS_LIENZO: Record<string, React.FC<PP>> = {carpetas: Carpetas, tarjetas: Tarjetas, captura: Captura};
