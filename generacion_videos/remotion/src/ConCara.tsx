import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ANCHO, CLAMP, CV, CX, ESCENARIO, EXPO, ConMarca, EstiloCtx, Filete, Tarjeta, Velo, fontFamily, pop, ramp, sombra, sombraTexto, useEstilo} from './base';
import {Robot} from './robot';
import {FondoLienzo, Logos, PIEZAS_LIENZO, SelloSerie, SubtitulosCortos, type EstiloCara} from './lienzo';
import * as InstrumentSerif from '@remotion/google-fonts/InstrumentSerif';
import * as PlayfairDisplay from '@remotion/google-fonts/PlayfairDisplay';
import * as Fraunces from '@remotion/google-fonts/Fraunces';
import * as DMSerifDisplay from '@remotion/google-fonts/DMSerifDisplay';
import {Fondo, PlanoVivo, Subtitulos} from './Explicativo';
import type {Estilo, Palabra, Plano, Props as PropsExplicativo} from './tipos';

/**
 * Reel con la persona a cámara: su vídeo (ya sin silencios ni repeticiones) es la base, y encima entran capas en las
 * frases que lo piden: grabaciones de pantalla con zoom (la app, la oficina) y planos animados del explicativo.
 * Los rótulos son cortos (6 palabras como mucho) y van en la zona segura.
 */
type Tramo = {desde: number; hasta: number}; // segundos del bruto que se quedan
type Encuadre = {t: number; x: number; y: number; w: number}; // segundos dentro de la capa · rectángulo del vídeo fuente
// «dividida»: pantalla partida (la visual arriba, la cara abajo, los subtítulos en la costura). «pasos» + «paso»: los
// pasos del proceso que se cuenta, arriba del todo, con el actual marcado; sirve de hilo entre varias divididas.
// «alto»: la parte de la visual (0,45-0,5; 0,5 por defecto). «fondo»: "marca" (el fondo oscuro de la marca, con la línea
// de la costura) o "lienzo" (blanco limpio, sin línea). «flota»: una pieza del lienzo sobre el vídeo, sin partir la pantalla.
type Division = {dividida?: boolean; pasos?: string[]; paso?: number; alto?: number; fondo?: 'marca' | 'lienzo'; flota?: boolean};
type Capa = Division & (
  | {inicio: number; fin: number; tipo: 'pantalla' | 'imagen'; archivo: string; desde: number; ancho: number; alto: number; encuadres: Encuadre[];
     cursor?: {t: number; x: number; y: number; clic?: boolean}[]}
  | {inicio: number; fin: number; tipo: 'plano' | 'encima'; plano: Omit<Plano, 'inicio' | 'fin'>});
type Rotulo = {inicio: number; fin: number; texto: string; arriba?: boolean};
type ConPlano = Extract<Capa, {plano: unknown}>;
// «*palabra*» en el texto: esa palabra en cursiva y en el acento de la marca. «ante»: antetítulo pequeño encima.
// «subraya»: un trazo fino del acento que se dibuja debajo de la palabra marcada.
type Clave = {inicio: number; fin: number; texto: string; lugar?: 'izq' | 'der' | 'arriba'; ante?: string; subraya?: boolean};
type Sonido = {t: number; archivo: string; volumen?: number};

export type PropsConCara = {
  fps: number;
  total: number;
  cara: {archivo: string; tramos: Tramo[]; zooms?: {t: number; escala: number}[]; centro?: {x: number; y: number}};
  capas: Capa[];
  claves?: Clave[];
  rotulos: Rotulo[];
  palabras: Palabra[];
  sonidos: Sonido[];
  estilo: Estilo;
};

const W = 1080, H = 1920, CAMBIO = 5;

/** La persona: cada tramo del bruto en su sitio y los reencuadres (punch-ins) secos, como un corte de editor, con el
 * centro en la cara para que nunca se salga de cuadro. */
const Cara: React.FC<{p: PropsConCara; frame: number; fps: number}> = ({p, frame, fps}) => {
  let acum = 0;
  const t = frame / fps;
  const zs = (p.cara.zooms ?? []).filter((x) => x.t <= t + 1e-6);
  const escala = zs.length ? zs[zs.length - 1].escala : 1.0;
  const c = p.cara.centro ?? {x: 0.5, y: 0.34};
  return (
    <AbsoluteFill style={{transform: `scale(${escala})`, transformOrigin: `${c.x * W}px ${c.y * H}px`}}>
      {p.cara.tramos.map((tr, i) => {
        const dur = Math.round((tr.hasta - tr.desde) * fps);
        const desde = Math.round(acum);
        acum += dur;
        return (
          <Sequence key={i} from={desde} durationInFrames={dur}>
            <OffthreadVideo src={staticFile(p.cara.archivo)} startFrom={Math.round(tr.desde * fps)}
              style={{width: W, height: H, objectFit: 'cover'}} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// Tipografías de titular del catálogo (las mismas que el motor de reels) por si el Kit nombra una en vez de subir la suya.
// Las serif van en caja normal y peso 400, como en el kit; las de palo, en mayúsculas y negra.
const SERIF: Record<string, {loadFont: (s?: any, o?: any) => {fontFamily: string}}> = {InstrumentSerif, PlayfairDisplay, Fraunces, DMSerifDisplay};
const titular = (nombre?: string) => {
  const f = nombre ? SERIF[nombre] : undefined;
  return f ? {familia: f.loadFont('normal', {weights: ['400'], subsets: ['latin', 'latin-ext']}).fontFamily, serif: true} : {familia: fontFamily, serif: false};
};

/** Ancho libre al lado de la cara para una palabra clave (0 si no cabe con al menos 80 px de letra). La cabeza ocupa
 * unos 200 px a cada lado de su centro, más con el reencuadre; el texto no pasa de x 850 (zona segura). */
// El título va centrado de verdad (x 540): encima de la cabeza no hay botones de Instagram que esquivar.
const ANCHO_TITULO = 900;
/** Cuerpo del título encima de la cabeza: la serif es más estrecha y se lee a más tamaño; los largos bajan para caber en dos líneas. */
const tamTitulo = (texto: string, serif: boolean) => serif ? (texto.length > 14 ? 128 : 150) : (texto.length > 14 ? 88 : 104);

const lugar0 = (k: Clave, centro: {x: number; y: number}) => {
  if (!k.lugar || k.lugar === 'arriba') return 0;
  const ancho = k.lugar === 'der' ? 850 - (centro.x * W + 200) : centro.x * W - 230 - 60;
  return ancho / (k.texto.length * 0.62) >= 80 ? ancho : 0;
};

/** La palabra clave (el título del reel) en el momento en que la dice: centrada encima de la cabeza, con la tipografía de
 * titular y el color de texto de la marca, sin borde ni caja y con una sombra suave para que se lea sobre el vídeo.
 * Aparece de golpe, se asienta (1,06 → 1) y se va con su frase. Al lado de la cara solo si el montaje lo pide. */
const ClaveJunto: React.FC<{k: Clave; frame: number; fps: number; centro: {x: number; y: number}}> = ({k, frame, fps, centro}) => {
  const ini = Math.round(k.inicio * fps), fin = Math.round(k.fin * fps);
  if (frame < ini || frame >= fin) return null;
  const a = ramp(frame - ini, 0, 6);
  // Al lado de la cara solo si cabe sin tocarla (el hueco es estrecho en un vertical); si no, encima de la cabeza.
  const cy = centro.y * H;
  const hueco = lugar0(k, centro);
  const lugar = hueco > 0 ? k.lugar : 'arriba';
  const e = useEstilo();
  const t = titular(e.titular);
  const tamLado = Math.min(92, hueco / (k.texto.length * 0.62));
  const pos: React.CSSProperties = lugar === 'arriba'
    ? {left: (W - ANCHO_TITULO) / 2, width: ANCHO_TITULO, top: Math.max(250, cy - 470), textAlign: 'center'}
    : lugar === 'der'
      ? {left: centro.x * W + 200, width: hueco, top: cy - 60, textAlign: 'left'}
      : {left: 60, width: hueco, top: cy - 60, textAlign: 'left'};
  // Sobre fondo claro (techo, pared) el blanco se pierde: un velo muy leve que oscurece la parte de arriba (o el lado) solo
  // mientras está el texto, en degradado y sin bordes, y una sombra difusa detrás de las letras. Nunca una caja.
  const velo = lugar === 'arriba'
    ? `linear-gradient(180deg, rgba(0,0,0,0.42) 0%, rgba(0,0,0,0.30) ${Math.round((Number(pos.top) + 260) / H * 100)}%, rgba(0,0,0,0) ${Math.round((Number(pos.top) + 520) / H * 100)}%)`
    : `radial-gradient(ellipse 520px 300px at ${lugar === 'der' ? '85%' : '15%'} ${Math.round((cy + 40) / H * 100)}%, rgba(0,0,0,0.38), rgba(0,0,0,0) 70%)`;
  return (
    <>
    <AbsoluteFill style={{background: velo, opacity: Math.min(1, a * 1.5)}} />
    <div style={{position: 'absolute', ...pos}}><Velo fuerza={0.55}><div style={{fontFamily: t.familia, fontWeight: t.serif ? 400 : 900, color: e.texto, lineHeight: t.serif ? 1.02 : 0.98,
      letterSpacing: t.serif ? '-0.015em' : -0.5, textTransform: t.serif ? 'none' : 'uppercase', opacity: Math.min(1, a * 2),
      fontSize: lugar === 'arriba' ? tamTitulo(k.texto, t.serif) : tamLado,
      transform: `scale(${1.06 - 0.06 * a})`, transformOrigin: lugar === 'der' ? '0% 50%' : lugar === 'izq' ? '100% 50%' : '50% 50%',
      textShadow: '0 2px 6px rgba(0,0,0,0.45), 0 0 40px rgba(0,0,0,0.55), 0 10px 60px rgba(0,0,0,0.45)'}}>
      {k.ante && <div style={{fontFamily, fontWeight: 700, fontSize: 30, letterSpacing: '0.22em', textTransform: 'uppercase',
        color: e.texto, opacity: 0.72, marginBottom: 14, fontStyle: 'normal'}}>{k.ante}</div>}
      {k.texto.split(/(\*[^*]+\*)/).filter(Boolean).map((trozo, i) => trozo.startsWith('*')
        ? <span key={i} style={{position: 'relative', display: 'inline-block', fontStyle: t.serif ? 'italic' : 'normal', color: e.subrayado,
            paddingRight: t.serif ? '0.06em' : 0}}>{trozo.slice(1, -1)}
            {k.subraya && <span style={{position: 'absolute', left: 0, bottom: '-0.02em', height: 5, borderRadius: 3, background: e.subrayado,
              width: `${interpolate(frame - ini, [4, 14], [0, 100], {...CLAMP, easing: EXPO})}%`}} />}</span>
        : <span key={i}>{trozo}</span>)}</div></Velo></div>
    </>
  );
};

/** Grabación de pantalla con zoom: el encuadre va de un rectángulo del vídeo fuente al siguiente. */
const Pantalla: React.FC<{c: Extract<Capa, {tipo: 'pantalla' | 'imagen'}>; f: number; fps: number}> = ({c, f, fps}) => {
  const t = f / fps;
  const es = c.encuadres;
  let r = es[0];
  for (let i = 0; i < es.length - 1; i++) {
    if (t >= es[i].t && t <= es[i + 1].t) {
      const k = interpolate(t, [es[i].t, es[i + 1].t], [0, 1], {...CLAMP, easing: Easing.bezier(0.65, 0, 0.35, 1)});
      r = {t, x: es[i].x + (es[i + 1].x - es[i].x) * k, y: es[i].y + (es[i + 1].y - es[i].y) * k, w: es[i].w + (es[i + 1].w - es[i].w) * k};
    } else if (t > es[i + 1].t) r = es[i + 1];
  }
  const escala = W / r.w;
  const cur = (c.cursor ?? []).filter((x) => x.t <= t + 0.6);
  let cx: number | null = null, cy = 0, clic = 0;
  if (cur.length) {
    const a = cur.length > 1 ? cur[cur.length - 2] : cur[0], b = cur[cur.length - 1];
    const k = interpolate(t, [b.t - 0.6, b.t], [0, 1], {...CLAMP, easing: Easing.bezier(0.65, 0, 0.35, 1)});
    cx = a.x + (b.x - a.x) * k; cy = a.y + (b.y - a.y) * k;
    if (b.clic && t >= b.t) clic = Math.max(0, 1 - (t - b.t) / 0.4);
  }
  return (
    <AbsoluteFill style={{overflow: 'hidden', background: '#05070f'}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: c.ancho, height: c.alto, transformOrigin: '0 0',
        transform: `translate(${-r.x * escala}px, ${-r.y * escala + (H - (c.alto * W / c.ancho)) * 0}px) scale(${escala})`}}>
        {c.tipo === 'imagen'
          ? <Img src={staticFile(c.archivo)} style={{width: c.ancho, height: c.alto, objectFit: 'cover'}} />
          : <OffthreadVideo src={staticFile(c.archivo)} startFrom={Math.round(c.desde * fps)} muted style={{width: c.ancho, height: c.alto}} />}
        {cx !== null ? (
          <div style={{position: 'absolute', left: cx, top: cy, transform: `scale(${1 / escala * 2.2})`, transformOrigin: '0 0'}}>
            {clic ? <div style={{position: 'absolute', left: -30, top: -30, width: 60, height: 60, borderRadius: 30,
              border: '4px solid #9cc4ff', transform: `scale(${1 + (1 - clic) * 1.2})`, opacity: clic}} /> : null}
            <svg width="34" height="40" viewBox="0 0 34 40" style={{filter: 'drop-shadow(0 3px 4px rgba(0,0,0,0.5))'}}>
              <path d="M2 2 L2 32 L10 25 L16 38 L22 35 L16 23 L27 23 Z" fill="#fff" stroke="#0c1a44" strokeWidth="2.5" strokeLinejoin="round" />
            </svg>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- planos propios de los vídeos a cámara

type PP = {p: Record<string, unknown>; f: number; fps: number; dur: number};
const txt = (v: unknown) => (typeof v === 'string' ? v : '');
const lst = <T,>(v: unknown) => (Array.isArray(v) ? (v as T[]) : []);

/** La misma respuesta genérica, multiplicada: primero una sola en grande y luego diez copias iguales. */
const Copias: React.FC<PP> = ({p, f, fps, dur}) => {
  const n = Number(p.n ?? 10);
  const en = Math.round(dur * 0.22);
  const sola = 1 - ramp(f, en, en + 10);
  const tarjeta = (escala: number) => (
    <Tarjeta claro style={{width: 380, padding: '20px 24px', boxSizing: 'border-box', transform: `scale(${escala})`}}>
      <div style={{fontWeight: 900, fontSize: 30, lineHeight: 1.12}}>{txt(p.texto)}</div>
      {[0.92, 0.78, 0.6].map((w, i) => <div key={i} style={{height: 12, borderRadius: 6, background: '#c9d5f2', marginTop: 12, width: `${w * 100}%`}} />)}
    </Tarjeta>
  );
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 120, top: 590, width: 784, display: 'grid', gridTemplateColumns: 'repeat(2, 380px)', gap: 24}}>
        {Array.from({length: n}).map((_, i) => {
          const s = pop(f, fps, en + 4 + i * 2.2, 10);
          return <div key={i} style={{transform: `scale(${0.5 + 0.5 * s}) rotate(${(i % 3 - 1) * 1.5}deg)`, opacity: Math.min(1, s * 1.4),
            filter: `saturate(${0.4 + 0.6 * (1 - ramp(f, dur * 0.6, dur))})`}}>{tarjeta(1)}</div>;
        })}
      </div>
      {sola > 0 ? (
        <div style={{position: 'absolute', left: CV - 190, top: 800, opacity: sola}}>{tarjeta(pop(f, fps, 0, 10) * (1.5 - 0.3 * (1 - sola)))}</div>
      ) : null}
    </AbsoluteFill>
  );
};

/** Encima de la persona: el piloto de grabación y el contador corriendo rápido hasta los minutos que dice. */
const Grabando: React.FC<PP> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const seg = Math.floor(Number(p.segundos ?? 300) * ramp(f, 4, dur - 6, (x) => x));
  const s = pop(f, fps, 0, 10);
  const reloj = `${String(Math.floor(seg / 60)).padStart(2, '0')}:${String(seg % 60).padStart(2, '0')}`;
  return (
    <div style={{position: 'absolute', left: CX - 230, width: 460, top: 250, display: 'flex', justifyContent: 'center', transform: `scale(${s})`}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 22, background: e.caja, borderRadius: 60, padding: '18px 40px',
        boxShadow: sombra, fontFamily, fontWeight: 900, fontSize: 70, color: '#fff', fontVariantNumeric: 'tabular-nums'}}>
        <div style={{width: 40, height: 40, borderRadius: 20, background: e.malo, opacity: Math.floor(f / 12) % 2 ? 0.35 : 1,
          boxShadow: `0 0 24px ${e.malo}`}} />
        <span style={{fontSize: 44, letterSpacing: 2}}>REC</span>
        <span>{reloj}</span>
      </div>
    </div>
  );
};

/** La transcripción de la grabación: Monti arriba y las frases buenas (entre *asteriscos*) se iluminan una a una. */
const Transcripcion: React.FC<PP> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const trozos = txt(p.texto).split('*');
  const n = Math.floor(trozos.length / 2);
  const paso = (dur * 0.7 - 12) / Math.max(1, n);
  let k = -1;
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: CV - 110, top: 300, transform: `scale(${pop(f, fps, 0, 10)})`}}>
        <Robot clave={txt(p.quien) || 'editor'} f={f} tam={220} accion="trabaja" />
      </div>
      <div style={{position: 'absolute', left: CV - 400, width: 800, top: 560, transform: `scale(${pop(f, fps, 3, 12)})`}}>
        <Tarjeta claro style={{padding: '30px 38px'}}>
          <div style={{fontWeight: 800, fontSize: 28, color: '#5b6b95', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 14}}>{txt(p.titulo) || 'Transcripción'}</div>
          <div style={{fontWeight: 600, fontSize: 38, lineHeight: 1.42, color: '#3a4770'}}>
            {trozos.map((t, i) => {
              if (i % 2 === 0) return <span key={i}>{t}</span>;
              k += 1;
              const a = ramp(f, 12 + k * paso, 12 + k * paso + 12, (x) => x);
              return <span key={i} style={{color: a > 0.5 ? '#0c1a44' : undefined, fontWeight: a > 0.5 ? 800 : 600, borderRadius: 8,
                backgroundImage: `linear-gradient(${e.subrayado}, ${e.subrayado})`, backgroundRepeat: 'no-repeat',
                backgroundSize: `${a * 100}% 100%`, boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone', padding: '0 4px'}}>{t}</span>;
            })}
          </div>
        </Tarjeta>
      </div>
    </AbsoluteFill>
  );
};

/** Una grabación larga (barra con su onda) se corta y cada trozo vuela a un vídeo vertical con su gancho. */
const Partir: React.FC<PP> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const g = lst<string>(p.ganchos);
  const n = Math.max(1, g.length);
  const BX = 80, BW = 860, BY = 620, BH = 150, GAP = 20, CW = (BW - GAP * (n - 1)) / n, CH = CW * 16 / 9;
  const corta = Math.round(dur * 0.18), vuela = Math.round(dur * 0.32);
  const s = pop(f, fps, 0, 12);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: BX, width: BW, top: BY - 70, textAlign: 'center', fontFamily, fontWeight: 900, fontSize: 40,
        color: '#fff', textShadow: sombraTexto, opacity: 1 - ramp(f, vuela, vuela + 8)}}>{txt(p.titulo) || 'Tu grabación'}</div>
      {g.map((gancho, i) => {
        const k = ramp(f, vuela + i * 3, vuela + i * 3 + 16);
        const x0 = BX + (BW / n) * i, w0 = BW / n;
        const x = x0 + (BX + i * (CW + GAP) - x0) * k, w = w0 + (CW - w0) * k;
        const y = BY + (BY + 10 - BY) * k, h = BH + (CH - BH) * k;
        const sep = ramp(f, corta + i * 2, corta + i * 2 + 8) * (1 - k) * 8;
        return (
          <div key={i} style={{position: 'absolute', left: x + (i - (n - 1) / 2) * sep, top: y, width: w, height: h, transform: `scale(${s})`,
            borderRadius: 18 + 10 * k, overflow: 'hidden', boxShadow: sombra, border: `3px solid ${k > 0.5 ? '#fff' : 'rgba(150,185,255,0.4)'}`,
            background: `linear-gradient(180deg, ${e.acento}, #12275c)`}}>
            <svg width="100%" height={BH} viewBox={`0 0 ${w0} ${BH}`} preserveAspectRatio="none" style={{position: 'absolute', top: (h - BH) / 2, opacity: 1 - k}}>
              {Array.from({length: Math.round(w0 / 12)}).map((_, j) => {
                const a = 20 + 50 * Math.abs(Math.sin((i * 31 + j) * 0.7) * Math.cos((i * 31 + j) * 0.23));
                return <rect key={j} x={j * 12 + 3} y={BH / 2 - a / 2} width={6} height={a} rx={3} fill="rgba(255,255,255,0.75)" />;
              })}
            </svg>
            <div style={{position: 'absolute', inset: 0, padding: 16, display: 'flex', flexDirection: 'column', justifyContent: 'center',
              opacity: ramp(f, vuela + i * 3 + 10, vuela + i * 3 + 18), fontFamily, color: '#fff'}}>
              <div style={{fontWeight: 800, fontSize: 22, opacity: 0.8, marginBottom: 10}}>Reel {i + 1}</div>
              <div style={{fontWeight: 900, fontSize: 30, lineHeight: 1.12}}>{gancho}</div>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// Pantalla dividida: la costura va a media altura. La cara se recoloca en la mitad de abajo con la cara centrada; la
// visual, en la de arriba con su escenario (y 590-1270 en el plano completo) centrado en ella.
const COSTURA = H / 2;

/** Los pasos del proceso, en texto plano: el actual en el acento y con su filete, los demás apagados. Nunca pastillas. */
const Pasos: React.FC<{pasos: string[]; paso: number; f: number}> = ({pasos, paso, f}) => {
  const e = useEstilo();
  return (
    <div style={{position: 'absolute', top: 150, left: 0, width: W, display: 'flex', justifyContent: 'center', gap: 44}}>
      {pasos.map((x, i) => {
        const activo = i + 1 === paso;
        return (
          <div key={i} style={{fontFamily, fontWeight: 700, fontSize: 26, letterSpacing: '0.16em', textTransform: 'uppercase',
            color: activo ? e.subrayado : e.texto, opacity: activo ? 1 : 0.42, position: 'relative', paddingBottom: 10}}>
            <span style={{opacity: 0.6, marginRight: 10}}>{i + 1}</span>{x}
            {activo && <div style={{position: 'absolute', left: 0, bottom: 0, height: 3, borderRadius: 2, background: e.subrayado,
              width: `${interpolate(f, [2, 12], [0, 100], {...CLAMP, easing: EXPO})}%`}} />}
          </div>
        );
      })}
    </div>
  );
};

/** Fondo de la mitad de arriba: el fondo de la marca casi plano, con una rejilla fina del color del texto y algo más de
 * luz en el centro. Nada que se mueva por su cuenta: lo que se mueve es la pieza. */
const FondoDividido: React.FC<{f: number}> = ({f}) => {
  const e = useEstilo();
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse 80% 70% at 50% 45%, color-mix(in srgb, ${e.mesa} 86%, ${e.subrayado}) 0%, ${e.mesa} 70%)`}}>
      <AbsoluteFill style={{opacity: 0.06, backgroundImage: `linear-gradient(${e.texto} 1px, transparent 1px), linear-gradient(90deg, ${e.texto} 1px, transparent 1px)`,
        backgroundSize: '60px 60px', backgroundPosition: `0 ${(f * 0.25) % 60}px`}} />
    </AbsoluteFill>
  );
};

/** Lista en la tipografía de titular de la marca, centrada en la mitad de arriba. «titulo»: una línea pequeña encima, con
 * palabras de la frase, que está desde el primer fotograma (la mitad de arriba nunca espera vacía a la primera línea). Cada línea entra en su golpe (fundido
 * y 1,04 → 1, sin subir ni desenfocar) y, con marca «cruz», un trazo del acento la tacha y la apaga. «queda»: la línea
 * final que sobrevive, en cursiva y en el acento. */
const Tachar: React.FC<PP> = ({p, f}) => {
  const e = useEstilo();
  const t = titular(e.titular);
  const items = (Array.isArray(p.items) ? p.items : []) as string[];
  const golpes = (Array.isArray(p.golpes) ? p.golpes : []) as number[];
  const queda = typeof p.queda === 'string' ? p.queda : '';
  const todas = queda ? [...items, queda] : items;
  const tam = todas.some((x) => x.length > 18) ? 96 : 120;
  const encabezado = typeof p.titulo === 'string' ? p.titulo : '';
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 10, paddingTop: 60}}>
      {encabezado && <div style={{fontFamily, fontWeight: 700, fontSize: 28, letterSpacing: '0.2em', textTransform: 'uppercase',
        color: e.texto, opacity: 0.6 * ramp(f, 0, 6), marginBottom: 26}}>{encabezado}</div>}
      {todas.map((x, i) => {
        const g = golpes[i] ?? i * 20;
        const k = ramp(f, g, g + 7);
        const final = queda && i === items.length;
        const tacha = p.marca === 'cruz' && !final ? interpolate(f, [g + 10, g + 20], [0, 1], {...CLAMP, easing: EXPO}) : 0;
        return (
          <div key={i} style={{position: 'relative', fontFamily: t.familia, fontWeight: t.serif ? 400 : 800, fontSize: tam, lineHeight: 1.1,
            color: final ? e.subrayado : e.texto, fontStyle: final && t.serif ? 'italic' : 'normal', opacity: k * (1 - 0.55 * tacha),
            transform: `scale(${1.04 - 0.04 * k})`, textTransform: t.serif ? 'none' : 'uppercase'}}>
            {x}
            <div style={{position: 'absolute', left: -8, top: '55%', height: 4, borderRadius: 2, background: e.subrayado,
              width: `calc(${tacha * 100}% + ${tacha * 16}px)`}} />
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// Piezas hechas para la mitad de arriba de la pantalla dividida (se dibujan en su caja de 1080 × 960).
const DIVIDIDAS: Record<string, React.FC<PP>> = {tachar: Tachar};

const PROPIOS: Record<string, React.FC<PP>> = {copias: Copias, transcripcion: Transcripcion, partir: Partir};

/** Rótulo corto: texto plano con su filete de acento sobre un velo difuso (nunca una caja), en la zona segura: arriba o
 * encima de los subtítulos. Entra en 6 fotogramas y se asienta sin rebote. */
const RotuloCaja: React.FC<{r: Rotulo; frame: number; fps: number; e: Estilo}> = ({r, frame, fps}) => {
  const ini = Math.round(r.inicio * fps), fin = Math.round(r.fin * fps);
  if (frame < ini || frame > fin) return null;
  const sale = interpolate(frame, [fin - CAMBIO, fin], [1, 0], CLAMP);
  return (
    <div style={{position: 'absolute', left: CX - ANCHO / 2, width: ANCHO, top: r.arriba === false ? 1080 : 250, display: 'flex',
      justifyContent: 'center', opacity: sale}}>
      <Filete texto={r.texto} k={ramp(frame - ini, 0, 6)} tam={60} ancho={150} />
    </div>
  );
};

export const ConCara: React.FC<PropsConCara> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const comoExplicativo = {...p, planos: [], rotulos: [], titulo: {texto: '', resalte: '', fin: 0}, audio: ''} as unknown as PropsExplicativo;
  const division = p.capas.find((c) => c.dividida && frame >= Math.round(c.inicio * fps) && frame < Math.round(c.fin * fps));
  const c0 = p.cara.centro ?? {x: 0.5, y: 0.34};
  const costura = Math.round(H * (division?.alto ?? COSTURA / H));
  // La cara centrada en la parte de abajo, sin salirse del vídeo.
  const bajaCara = Math.min(0, Math.max(-(H - costura), (H - costura) / 2 - c0.y * H));
  const cortos = (p.estilo as EstiloCara).subtitulos === 'cortos';
  return (
    <ConMarca estilo={p.estilo}>
      <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
        {division ? (
          <div style={{position: 'absolute', left: 0, top: costura, width: W, height: H - costura, overflow: 'hidden'}}>
            <div style={{position: 'absolute', left: 0, top: bajaCara, width: W, height: H}}><Cara p={p} frame={frame} fps={fps} /></div>
          </div>
        ) : <Cara p={p} frame={frame} fps={fps} />}
        {p.capas.map((c, i) => {
          const ini = Math.round(c.inicio * fps), fin = Math.round(c.fin * fps);
          if (frame < ini - 1 || frame > fin + CAMBIO) return null;
          const f = frame - ini;
          const entra = interpolate(f, [0, CAMBIO], [0, 1], {...CLAMP, easing: EXPO});
          const sale = interpolate(frame, [fin, fin + CAMBIO], [0, 1], CLAMP);
          if (c.tipo === 'encima') {
            if (c.plano.tipo === 'logos') return <AbsoluteFill key={i} style={{opacity: 1 - sale}}><Logos p={c.plano} f={f} fps={fps} centro={c0} /></AbsoluteFill>;
            if (c.plano.tipo === 'serie') return frame < fin ? <AbsoluteFill key={i}><SelloSerie p={c.plano} f={f} fps={fps} /></AbsoluteFill> : null;
            const Comp = c.plano.tipo === 'grabando' ? Grabando : null;
            return Comp ? <AbsoluteFill key={i} style={{opacity: 1 - sale}}><Comp p={c.plano} f={f} fps={fps} dur={fin - ini} /></AbsoluteFill> : null;
          }
          const Propio = c.tipo === 'plano' ? PROPIOS[String(c.plano.tipo)] : undefined;
          const Lienzo = c.tipo === 'plano' ? PIEZAS_LIENZO[String(c.plano.tipo)] : undefined;
          if (c.flota && Lienzo && !c.dividida) {
            // Flotando sobre el vídeo, en la parte de arriba: entra y sale con corte seco, como en el lienzo.
            if (frame >= fin) return null;
            return (
              <div key={i} style={{position: 'absolute', left: 0, top: 170, width: W, height: 760}}>
                <Lienzo p={{...(c as ConPlano).plano, flota: true}} f={f} fps={fps} dur={fin - ini} ancho={W} alto={760} />
              </div>
            );
          }
          if (c.dividida) {
            if (frame >= fin) return null; // corte seco al volver a la cara entera, como un editor
            const sube = -(ESCENARIO.top + ESCENARIO.alto / 2 - costura / 2 - (c.pasos ? 50 : 0));
            const lienzo = c.fondo === 'lienzo';
            return (
              <div key={i} style={{position: 'absolute', left: 0, top: 0, width: W, height: costura, overflow: 'hidden'}}>
                {lienzo ? <FondoLienzo /> : <FondoDividido f={frame} />}
                {Lienzo ? <Lienzo p={(c as ConPlano).plano} f={f} fps={fps} dur={fin - ini} ancho={W} alto={costura} />
                : c.tipo === 'plano' && DIVIDIDAS[String(c.plano.tipo)] ? (
                  React.createElement(DIVIDIDAS[String(c.plano.tipo)], {p: (c as ConPlano).plano, f, fps, dur: fin - ini})
                ) : c.tipo === 'pantalla' || c.tipo === 'imagen' ? (
                  <div style={{position: 'absolute', left: W * 0.26, top: (costura - H * 0.48) / 2 + (c.pasos ? 40 : 0), width: W, height: H,
                    transform: 'scale(0.48)', transformOrigin: '0 0', borderRadius: 60, overflow: 'hidden', boxShadow: sombra}}>
                    <Pantalla c={c} f={f} fps={fps} />
                  </div>
                ) : (
                  <div style={{position: 'absolute', left: 0, top: sube, width: W, height: H}}>
                    {Propio ? <Propio p={(c as ConPlano).plano} f={f} fps={fps} dur={fin - ini} />
                      : <PlanoVivo pl={{...(c as ConPlano).plano, inicio: c.inicio, fin: c.fin} as Plano} i={1} frame={frame} fps={fps} />}
                  </div>
                )}
                {c.pasos && <Pasos pasos={c.pasos} paso={c.paso ?? 1} f={f} />}
                {!lienzo && <div style={{position: 'absolute', left: 0, bottom: 0, width: W, height: 2, background: p.estilo.subrayado, opacity: 0.55}} />}
              </div>
            );
          }
          return (
            <AbsoluteFill key={i} style={{opacity: entra * (1 - sale), transform: `scale(${1.08 - 0.08 * entra + 0.04 * sale})`}}>
              {c.tipo === 'pantalla' || c.tipo === 'imagen' ? <Pantalla c={c} f={f} fps={fps} /> : (
                <AbsoluteFill>
                  <Fondo f={frame} p={comoExplicativo} />
                  {Propio ? <Propio p={(c as ConPlano).plano} f={f} fps={fps} dur={fin - ini} />
                    : <PlanoVivo pl={{...(c as ConPlano).plano, inicio: c.inicio, fin: c.fin} as Plano} i={1} frame={frame} fps={fps} />}
                </AbsoluteFill>
              )}
            </AbsoluteFill>
          );
        })}
        {!division && (p.claves ?? []).map((k, i) => <ClaveJunto key={`k${i}`} k={k} frame={frame} fps={fps} centro={p.cara.centro ?? {x: 0.5, y: 0.34}} />)}
        {p.rotulos.map((r, i) => <RotuloCaja key={i} r={r} frame={frame} fps={fps} e={p.estilo} />)}
        {/* En la dividida, los subtítulos suben a la costura y se centran. */}
        {/* Los cortos se quedan siempre a la altura del pecho, también con la pantalla partida. */}
        {cortos ? <SubtitulosCortos palabras={p.palabras} t={t} top={division ? Math.max(1240, costura + 420) : 1240} /> : (
        <div style={{position: 'absolute', inset: 0, transform: division ? `translate(${W / 2 - CX}px, ${costura - 120 - 1300}px)` : undefined}}>
          <Subtitulos p={comoExplicativo} t={t} />
        </div>)}
        {p.sonidos.map((s, i) => (
          <Sequence key={i} from={Math.max(0, Math.round(s.t * fps))}>
            <Audio src={staticFile(s.archivo)} volume={s.volumen ?? 0.5} />
          </Sequence>
        ))}
      </AbsoluteFill>
    </ConMarca>
  );
};
