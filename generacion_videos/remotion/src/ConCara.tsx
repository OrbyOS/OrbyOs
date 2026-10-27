import React from 'react';
import {AbsoluteFill, Audio, Easing, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ANCHO, CLAMP, CV, CX, EXPO, EstiloCtx, Tarjeta, fontFamily, pop, ramp, sombra, sombraTexto, useEstilo} from './base';
import {Robot} from './robot';
import {Fondo, PlanoVivo, Subtitulos} from './Explicativo';
import type {Estilo, Palabra, Plano, Props as PropsExplicativo} from './tipos';

/**
 * Reel con la persona a cámara: su vídeo (ya sin silencios ni repeticiones) es la base, y encima entran capas en las
 * frases que lo piden: grabaciones de pantalla con zoom (la app, la oficina) y planos animados del explicativo.
 * Los rótulos son cortos (6 palabras como mucho) y van en la zona segura.
 */
type Tramo = {desde: number; hasta: number}; // segundos del bruto que se quedan
type Encuadre = {t: number; x: number; y: number; w: number}; // segundos dentro de la capa · rectángulo del vídeo fuente
type Capa =
  | {inicio: number; fin: number; tipo: 'pantalla'; archivo: string; desde: number; ancho: number; alto: number; encuadres: Encuadre[];
     cursor?: {t: number; x: number; y: number; clic?: boolean}[]}
  | {inicio: number; fin: number; tipo: 'plano' | 'encima'; plano: Omit<Plano, 'inicio' | 'fin'>};
type Rotulo = {inicio: number; fin: number; texto: string; arriba?: boolean};
type Sonido = {t: number; archivo: string; volumen?: number};

export type PropsConCara = {
  fps: number;
  total: number;
  cara: {archivo: string; tramos: Tramo[]; zooms?: {t: number; escala: number}[]};
  capas: Capa[];
  rotulos: Rotulo[];
  palabras: Palabra[];
  sonidos: Sonido[];
  estilo: Estilo;
};

const W = 1080, H = 1920, CAMBIO = 5;

/** La persona: cada tramo del bruto en su sitio, con un pequeño empujón de cámara en los momentos marcados. */
const Cara: React.FC<{p: PropsConCara; frame: number; fps: number}> = ({p, frame, fps}) => {
  let acum = 0;
  const t = frame / fps;
  const zs = (p.cara.zooms ?? []).filter((x) => x.t <= t);
  const z = zs[zs.length - 1];
  const escala = z ? interpolate(t - z.t, [0, 0.25], [1, z.escala], {...CLAMP, easing: EXPO}) : 1.0;
  return (
    <AbsoluteFill style={{transform: `scale(${escala})`}}>
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

/** Grabación de pantalla con zoom: el encuadre va de un rectángulo del vídeo fuente al siguiente. */
const Pantalla: React.FC<{c: Extract<Capa, {tipo: 'pantalla'}>; f: number; fps: number}> = ({c, f, fps}) => {
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
        <OffthreadVideo src={staticFile(c.archivo)} startFrom={Math.round(c.desde * fps)} muted style={{width: c.ancho, height: c.alto}} />
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

const PROPIOS: Record<string, React.FC<PP>> = {copias: Copias, transcripcion: Transcripcion, partir: Partir};

/** Rótulo corto: caja oscura, entra con rebote, en la zona segura (arriba, o encima de los subtítulos). */
const RotuloCaja: React.FC<{r: Rotulo; frame: number; fps: number; e: Estilo}> = ({r, frame, fps, e}) => {
  const ini = Math.round(r.inicio * fps), fin = Math.round(r.fin * fps);
  if (frame < ini || frame > fin) return null;
  const f = frame - ini;
  const s = pop(f, fps, 0, 9);
  const sale = interpolate(frame, [fin - CAMBIO, fin], [1, 0], CLAMP);
  return (
    <div style={{position: 'absolute', left: CX - ANCHO / 2, width: ANCHO, top: r.arriba === false ? 1080 : 250, display: 'flex',
      justifyContent: 'center', opacity: sale}}>
      <div style={{background: e.caja, color: '#fff', fontFamily, fontWeight: 900, fontSize: 70, lineHeight: 1.05, textAlign: 'center',
        padding: '18px 34px', borderRadius: 24, border: `3px solid ${e.acento}`, boxShadow: sombra, textTransform: 'uppercase',
        transform: `scale(${0.7 + 0.3 * s}) rotate(-2deg)`, maxWidth: ANCHO}}>{r.texto}</div>
    </div>
  );
};

export const ConCara: React.FC<PropsConCara> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const comoExplicativo = {...p, planos: [], rotulos: [], titulo: {texto: '', resalte: '', fin: 0}, audio: ''} as unknown as PropsExplicativo;
  return (
    <EstiloCtx.Provider value={p.estilo}>
      <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
        <Cara p={p} frame={frame} fps={fps} />
        {p.capas.map((c, i) => {
          const ini = Math.round(c.inicio * fps), fin = Math.round(c.fin * fps);
          if (frame < ini - 1 || frame > fin + CAMBIO) return null;
          const f = frame - ini;
          const entra = interpolate(f, [0, CAMBIO], [0, 1], {...CLAMP, easing: EXPO});
          const sale = interpolate(frame, [fin, fin + CAMBIO], [0, 1], CLAMP);
          if (c.tipo === 'encima') {
            const Comp = c.plano.tipo === 'grabando' ? Grabando : null;
            return Comp ? <AbsoluteFill key={i} style={{opacity: 1 - sale}}><Comp p={c.plano} f={f} fps={fps} dur={fin - ini} /></AbsoluteFill> : null;
          }
          const Propio = c.tipo === 'plano' ? PROPIOS[String(c.plano.tipo)] : undefined;
          return (
            <AbsoluteFill key={i} style={{opacity: entra * (1 - sale), transform: `scale(${1.08 - 0.08 * entra + 0.04 * sale})`}}>
              {c.tipo === 'pantalla' ? <Pantalla c={c} f={f} fps={fps} /> : (
                <AbsoluteFill>
                  <Fondo f={frame} p={comoExplicativo} />
                  {Propio ? <Propio p={c.plano} f={f} fps={fps} dur={fin - ini} />
                    : <PlanoVivo pl={{...c.plano, inicio: c.inicio, fin: c.fin} as Plano} i={1} frame={frame} fps={fps} />}
                </AbsoluteFill>
              )}
            </AbsoluteFill>
          );
        })}
        {p.rotulos.map((r, i) => <RotuloCaja key={i} r={r} frame={frame} fps={fps} e={p.estilo} />)}
        <Subtitulos p={comoExplicativo} t={t} />
        {p.sonidos.map((s, i) => (
          <Sequence key={i} from={Math.max(0, Math.round(s.t * fps))}>
            <Audio src={staticFile(s.archivo)} volume={s.volumen ?? 0.5} />
          </Sequence>
        ))}
      </AbsoluteFill>
    </EstiloCtx.Provider>
  );
};
