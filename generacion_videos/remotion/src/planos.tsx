import React from 'react';
import {AbsoluteFill, Easing, OffthreadVideo, interpolate, staticFile} from 'remotion';
import {ANCHO, CLAMP, CV, CX, Destellos, EXPO, ESCENARIO, Tarjeta, fontFamily, pop, ramp, sombra, sombraTexto, suave, useEstilo} from './base';
import {Defs, ILUSTRACIONES} from './ilustraciones';
import {NOMBRES, Robot, colorDe} from './robot';
import type {Plano} from './tipos';

/**
 * Los tipos de plano. Cada uno recibe el fotograma dentro del plano (f), lo que dura (dur) y sus campos del guion.
 * Regla de todos: algo se mueve siempre y cada cosa que entra lo hace con rebote.
 */
type P = {p: Plano; f: number; dur: number; fps: number};

const Caja: React.FC<{children: React.ReactNode; top?: number; alto?: number}> = ({children, top = ESCENARIO.top, alto = ESCENARIO.alto}) => (
  <div style={{position: 'absolute', left: CV - ANCHO / 2, width: ANCHO, top, height: alto, display: 'flex',
    flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>{children}</div>
);

/** Reparte n entradas a lo largo de la primera parte del plano. */
const turnos = (n: number, dur: number, parte = 0.62, minimo = 5, maximo = 16) =>
  Math.max(minimo, Math.min(maximo, (dur * parte) / Math.max(1, n)));

/** Cuándo entra la cosa i: en su palabra si el guion lo marca (^palabra), o repartido si no. */
const cuando = (p: Plano, i: number, porDefecto: number) => {
  const g = Array.isArray(p.golpes) ? (p.golpes as number[]) : [];
  return g.length ? (g[i] ?? g[g.length - 1] + (i - g.length + 1) * 8) : porDefecto;
};

const texto = (v: unknown) => (typeof v === 'string' ? v : '');
const lista = <T,>(v: unknown) => (Array.isArray(v) ? (v as T[]) : []);

// ---------------------------------------------------------------- objetos

const Ilus: React.FC<{nombre: string; lado: number; f: number; fps: number; i: number; entra?: number}> = ({nombre, lado, f, fps, i, entra}) => {
  const Comp = ILUSTRACIONES[nombre];
  if (!Comp) return null;
  const e0 = entra ?? i * 5;
  const s = pop(f, fps, e0);
  const estira = 1 + (1 - s) * 0.25; // aplastar y estirar al caer
  const flota = Math.sin((f + i * 17) / 14) * 9;
  const giro = interpolate(s, [0, 1], [-18 + i * 12, 0]) + Math.sin((f + i * 9) / 22) * 2.5;
  return (
    <div style={{position: 'relative', width: lado, height: lado}}>
      <Destellos f={f - e0 - 3} color="#9cc4ff" radio={lado * 0.45} />
      <svg width={lado} height={lado} viewBox="0 0 400 400" style={{transform:
        `translateY(${flota}px) scale(${s * (2 - estira)}, ${s * estira}) rotate(${giro}deg)`,
        filter: 'drop-shadow(0 26px 22px rgba(0,0,0,0.45))'}}>
        <Defs />
        <Comp />
      </svg>
    </div>
  );
};

const Objetos: React.FC<P> = ({p, f, fps}) => {
  const objs = lista<string>(p.objetos);
  const etiquetas = lista<string>(p.textos);
  const e = useEstilo();
  const lado = objs.length === 1 ? 600 : objs.length === 2 ? 400 : objs.length === 3 ? 290 : 215;
  return (
    <Caja>
      <div style={{display: 'flex', gap: objs.length > 2 ? 4 : 24, alignItems: 'flex-end'}}>
        {objs.map((o, i) => (
          <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14}}>
            <Ilus nombre={o} lado={lado} f={f} fps={fps} i={i} entra={cuando(p, i, i * 5)} />
            {etiquetas[i] ? (
              <div style={{fontFamily, fontWeight: 900, fontSize: 46, color: '#fff', background: e.acento, padding: '8px 26px', border: '4px solid #fff',
                borderRadius: 999, boxShadow: sombra, transform: `scale(${pop(f, fps, cuando(p, i, i * 5) + 6)})`}}>{etiquetas[i]}</div>
            ) : null}
          </div>
        ))}
      </div>
    </Caja>
  );
};

// ---------------------------------------------------------------- robots

const Bocadillo: React.FC<{texto: string; f: number; fps: number; color: string}> = ({texto: t, f, fps, color}) => {
  const s = pop(f, fps, 6);
  const letras = Math.round(interpolate(f, [8, 8 + t.length * 0.9], [0, t.length], CLAMP));
  return (
    <div style={{transform: `scale(${s})`, transformOrigin: '50% 100%', marginBottom: 18, position: 'relative'}}>
      <Tarjeta claro style={{padding: '24px 38px', fontSize: 56, fontWeight: 900, maxWidth: 760, textAlign: 'center', lineHeight: 1.12}}>
        {t.slice(0, letras)}<span style={{opacity: 0}}>{t.slice(letras)}</span>
      </Tarjeta>
      <div style={{position: 'absolute', left: '50%', bottom: -22, width: 44, height: 44, background: '#e9efff',
        transform: 'translateX(-50%) rotate(45deg)', borderRight: `3px solid #fff`, borderBottom: `3px solid ${color}`}} />
    </div>
  );
};

const RobotPlano: React.FC<P> = ({p, f, fps}) => {
  const quien = texto(p.quien) || 'jefa';
  const s = pop(f, fps, 0, 10);
  const boc = texto(p.bocadillo);
  const obj = texto(p.objeto);
  const robot = (
    <div style={{transform: `translateY(${(1 - s) * 260}px) scale(${0.6 + 0.4 * s})`, position: 'relative'}}>
      <Destellos f={f - 2} color={colorDe(quien)} radio={200} />
      <Robot clave={quien} f={f} tam={boc ? (obj ? 360 : 400) : 480} accion={texto(p.accion) || 'saluda'} />
    </div>
  );
  return (
    <Caja top={ESCENARIO.top - 40} alto={ESCENARIO.alto + 60}>
      {boc ? <Bocadillo texto={boc} f={f} fps={fps} color={colorDe(quien)} /> : null}
      {obj ? (
        <div style={{display: 'flex', alignItems: 'center', gap: 10, flexDirection: p.lado === 'der' ? 'row-reverse' : 'row'}}>
          {robot}
          <Ilus nombre={obj} lado={380} f={f - 6} fps={fps} i={0} />
        </div>
      ) : robot}
    </Caja>
  );
};

const EquipoPlano: React.FC<P> = ({p, f, fps, dur}) => {
  const quienes = lista<string>(p.quienes).length ? lista<string>(p.quienes)
    : ['jefa', 'analista', 'estratega', 'guionista', 'editor', 'publicador', 'comunidad'];
  const paso = turnos(quienes.length, dur, 0.7, 4, 14);
  const filas = quienes.length > 4 ? [quienes.slice(0, Math.ceil(quienes.length / 2)), quienes.slice(Math.ceil(quienes.length / 2))] : [quienes];
  const tam = quienes.length > 4 ? 236 : quienes.length > 2 ? 260 : 330;
  let k = 0;
  return (
    <Caja top={ESCENARIO.top - 30} alto={ESCENARIO.alto + 40}>
      {filas.map((fila, fi) => (
        <div key={fi} style={{display: 'flex', gap: 0, marginTop: fi ? 0 : 0}}>
          {fila.map((q) => {
            const i = k++;
            const e0 = cuando(p, i, i * paso);
            const s = pop(f, fps, e0);
            const n = NOMBRES[q] ?? {nombre: q, rol: ''};
            return (
              <div key={q} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: tam + 4,
                transform: `translateY(${(1 - s) * 120}px) scale(${s})`, opacity: Math.min(1, s * 2)}}>
                <Robot clave={q} f={f} tam={tam * 0.82} accion={f - e0 < 18 ? 'saluda' : 'quieto'} semilla={i} />
                {p.nombres === false ? null : (
                  <div style={{fontFamily, textAlign: 'center', marginTop: -6}}>
                    <div style={{fontWeight: 900, fontSize: 46, color: '#fff', textShadow: sombraTexto}}>{n.nombre}</div>
                    <div style={{fontWeight: 800, fontSize: 30, color: colorDe(q), letterSpacing: 1, textTransform: 'uppercase'}}>{n.rol}</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </Caja>
  );
};

// ---------------------------------------------------------------- números y gráficas

const Cifra: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const valor = Number(p.valor ?? 0);
  const desde = Number(p.desde ?? 0);
  const llega = Math.max(12, Math.min(dur * 0.6, 40));
  const k = ramp(f, 2, llega);
  const n = desde + (valor - desde) * k;
  const dec = Number(p.decimales ?? 0);
  const num = n.toLocaleString('es-ES', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  const s = pop(f, fps, 0, 8);
  const golpe = f > llega ? pop(f, fps, llega, 6) : 0; // el número da un golpe al llegar
  const r = 250;
  const largo = 2 * Math.PI * r;
  const color = p.malo ? e.malo : e.acento;
  return (
    <Caja>
      <div style={{position: 'relative', width: 600, height: 600, transform: `scale(${s})`}}>
        <svg width="600" height="600" viewBox="-300 -300 600 600" style={{position: 'absolute', inset: 0}}>
          <circle r={r} fill="rgba(10, 22, 66, 0.65)" stroke="rgba(150,185,255,0.18)" strokeWidth="34" />
          <circle r={r} fill="none" stroke={color} strokeWidth="34" strokeLinecap="round" transform="rotate(-90)"
            strokeDasharray={largo} strokeDashoffset={largo * (1 - (p.tope ? Math.min(1, n / Number(p.tope)) : k))}
            style={{filter: `drop-shadow(0 0 18px ${color})`}} />
        </svg>
        <Destellos f={f - llega} color={color} radio={280} n={10} />
        <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', fontFamily, color: '#fff', textAlign: 'center'}}>
          <div style={{fontWeight: 900, fontSize: num.length > 4 ? 150 : 200, lineHeight: 1, letterSpacing: -4,
            transform: `scale(${1 + golpe * 0.12 - (f > llega + 8 ? 0.12 * pop(f, fps, llega + 8, 12) : 0)})`, textShadow: sombraTexto}}>
            {texto(p.prefijo)}{num}<span style={{fontSize: '0.45em', letterSpacing: 0}}>{texto(p.sufijo)}</span>
          </div>
          <div style={{fontWeight: 800, fontSize: 40, color: e.subrayado, marginTop: 10, maxWidth: 420, lineHeight: 1.1}}>{texto(p.etiqueta)}</div>
        </div>
      </div>
    </Caja>
  );
};

const Grafica: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const vals = lista<number>(p.valores);
  const etqs = lista<string>(p.etiquetas);
  const max = Math.max(...vals, 1);
  const w = 680, h = 420;
  const s = suave(f, fps);
  const k = ramp(f, 4, Math.max(14, dur * 0.65));
  const resalte = Number(p.resalte ?? vals.length - 1);
  if (p.modo === 'barras') {
    const bw = w / vals.length * 0.62;
    return (
      <Caja>
        <Tarjeta style={{padding: '36px 40px 26px', transform: `scale(${0.9 + 0.1 * s})`, opacity: s}}>
          <div style={{fontWeight: 900, fontSize: 48, marginBottom: 18, color: e.subrayado}}>{texto(p.titulo)}</div>
          <div style={{display: 'flex', alignItems: 'flex-end', gap: w / vals.length * 0.38, height: h}}>
            {vals.map((v, i) => {
              const g = pop(f, fps, cuando(p, i, 4 + i * turnos(vals.length, dur, 0.5, 3, 10)), 11);
              const malo = i !== resalte && p.malo_resto;
              return (
                <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10}}>
                  <div style={{fontWeight: 900, fontSize: 34, opacity: g}}>{texto(lista<string>(p.rotulos)[i])}</div>
                  <div style={{width: bw, height: Math.max(8, (v / max) * (h - 110) * g), borderRadius: 16,
                    background: i === resalte ? `linear-gradient(180deg, #9cc4ff, ${e.acento})` : malo ? 'rgba(160,175,210,0.35)' : 'rgba(120,160,255,0.55)',
                    boxShadow: i === resalte ? `0 0 30px ${e.acento}` : 'none'}} />
                  <div style={{fontWeight: 800, fontSize: 32, color: 'rgba(255,255,255,0.85)'}}>{etqs[i] ?? ''}</div>
                </div>
              );
            })}
          </div>
        </Tarjeta>
      </Caja>
    );
  }
  const pts = vals.map((v, i) => [i / Math.max(1, vals.length - 1) * w, h - (v / max) * (h - 30)] as const);
  const d = pts.map((q, i) => `${i ? 'L' : 'M'}${q[0]},${q[1]}`).join(' ');
  const largo = pts.reduce((a, q, i) => (i ? a + Math.hypot(q[0] - pts[i - 1][0], q[1] - pts[i - 1][1]) : 0), 0);
  const ultimo = pts[Math.min(pts.length - 1, Math.floor(k * (pts.length - 1) + 0.001))];
  return (
    <Caja>
      <Tarjeta style={{padding: '36px 40px', transform: `scale(${0.9 + 0.1 * s})`, opacity: s}}>
        <div style={{fontWeight: 900, fontSize: 48, marginBottom: 14, color: e.subrayado}}>{texto(p.titulo)}</div>
        <svg width={w} height={h} style={{overflow: 'visible'}}>
          {[0.25, 0.5, 0.75].map((y) => <line key={y} x1="0" x2={w} y1={h * y} y2={h * y} stroke="rgba(150,185,255,0.15)" strokeWidth="2" />)}
          <path d={`${d} L${w},${h} L0,${h} Z`} fill={`url(#rel-${p.inicio})`} opacity={k} />
          <defs><linearGradient id={`rel-${p.inicio}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={p.malo ? e.malo : e.acento} stopOpacity="0.45" /><stop offset="1" stopColor={e.acento} stopOpacity="0" />
          </linearGradient></defs>
          <path d={d} fill="none" stroke={p.malo ? e.malo : '#9cc4ff'} strokeWidth="12" strokeLinecap="round" strokeLinejoin="round"
            strokeDasharray={largo} strokeDashoffset={largo * (1 - k)} style={{filter: 'drop-shadow(0 0 12px rgba(120,170,255,0.8))'}} />
          {ultimo ? <circle cx={ultimo[0]} cy={ultimo[1]} r={18 + Math.sin(f / 3) * 3} fill="#fff" stroke={e.acento} strokeWidth="8" /> : null}
        </svg>
        <div style={{display: 'flex', justifyContent: 'space-between', fontWeight: 800, fontSize: 34, color: 'rgba(255,255,255,0.8)', marginTop: 12}}>
          {etqs.map((t, i) => <span key={i}>{t}</span>)}
        </div>
      </Tarjeta>
    </Caja>
  );
};


type Partida = {texto: string; valor: number};

/** Una suma que se va haciendo: cada partida entra en su palabra y el total del anillo sube con ella. */
const Suma: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const items = lista<Partida>(p.items);
  const paso = turnos(items.length, dur, 0.8, 8, 30);
  const entra = items.map((_, i) => cuando(p, i, i * paso));
  const desde = Number(p.desde ?? 0);
  const dec = Number(p.decimales ?? 0);
  const tope = Number(p.tope ?? Math.max(desde, desde + items.reduce((a, x) => a + x.valor, 0)));
  let total = desde;
  items.forEach((x, i) => { total += x.valor * suave(f, fps, entra[i] + 2); });
  const num = (v: number) => v.toLocaleString('es-ES', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  const n = num(total);
  const r = 192, largo = 2 * Math.PI * r;
  const ultimo = entra.filter((x) => f >= x).length - 1;
  const late = ultimo >= 0 ? Math.max(0, 1 - (f - entra[ultimo]) / 10) : 0;
  return (
    <Caja>
      <div style={{display: 'flex', alignItems: 'center', gap: 26}}>
        <div style={{position: 'relative', width: 440, height: 440, transform: `scale(${pop(f, fps, 0, 10) * (1 + late * 0.06)})`}}>
          <svg width="440" height="440" viewBox="-220 -220 440 440" style={{position: 'absolute', inset: 0}}>
            <circle r={r} fill="rgba(10, 22, 66, 0.65)" stroke="rgba(150,185,255,0.18)" strokeWidth="30" />
            <circle r={r} fill="none" stroke={e.acento} strokeWidth="30" strokeLinecap="round" transform="rotate(-90)"
              strokeDasharray={largo} strokeDashoffset={largo * (1 - Math.min(1, total / tope))} style={{filter: `drop-shadow(0 0 16px ${e.acento})`}} />
          </svg>
          <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            fontFamily, color: '#fff'}}>
            <div style={{fontWeight: 900, fontSize: n.length > 5 ? 96 : n.length > 3 ? 120 : 150, lineHeight: 1, letterSpacing: -4, textShadow: sombraTexto,
              color: total < desde * 0.2 && desde > 0 ? e.malo : '#fff'}}>{n}</div>
            <div style={{fontWeight: 900, fontSize: 44, color: e.subrayado}}>{texto(p.sufijo).trim()}</div>
          </div>
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 14, width: 370}}>
          {items.map((x, i) => {
            const s = pop(f, fps, entra[i], 11);
            return (
              <div key={i} style={{transform: `translateX(${(1 - s) * 300}px) scale(${0.8 + 0.2 * s})`, opacity: Math.min(1, s * 2)}}>
                <Tarjeta claro={i === ultimo} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 22px',
                  fontSize: 40, fontWeight: 800, borderRadius: 22}}>
                  <span>{x.texto}</span><span style={{fontWeight: 900, color: x.valor < 0 ? e.malo : i === ultimo ? e.acento : e.subrayado}}>
                    {x.valor < 0 ? '−' : '+'}{num(Math.abs(x.valor))}</span>
                </Tarjeta>
              </div>
            );
          })}
        </div>
      </div>
    </Caja>
  );
};

// ---------------------------------------------------------------- listas y comparaciones

const Marca: React.FC<{tipo: string; k: number; color: string}> = ({tipo, k, color}) => (
  <svg width="70" height="70" viewBox="0 0 70 70">
    <circle cx="35" cy="35" r="33" fill={color} />
    {tipo === 'cruz'
      ? <path d="M22 22 L48 48 M48 22 L22 48" stroke="#fff" strokeWidth="9" strokeLinecap="round" strokeDasharray="80" strokeDashoffset={80 * (1 - k)} />
      : <path d="M19 36 L30 47 L52 24" stroke="#fff" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" fill="none" strokeDasharray="60" strokeDashoffset={60 * (1 - k)} />}
  </svg>
);

const Lista: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const items = lista<string>(p.items);
  const paso = turnos(items.length, dur, 0.7, 6, 22);
  const tipo = texto(p.marca) || 'check';
  return (
    <Caja>
      <div style={{display: 'flex', flexDirection: 'column', gap: 22, width: ANCHO - 40}}>
        {items.map((it, i) => {
          const e0 = cuando(p, i, i * paso);
          const s = pop(f, fps, e0, 11);
          const k = ramp(f, e0 + 6, e0 + 16);
          const tachado = tipo === 'cruz' ? ramp(f, e0 + 10, e0 + 20) : 0;
          return (
            <div key={i} style={{transform: `translateX(${(1 - s) * -500}px) rotate(${(1 - s) * -6}deg)`, opacity: Math.min(1, s * 2)}}>
              <Tarjeta style={{display: 'flex', alignItems: 'center', gap: 26, padding: '22px 30px'}}>
                {tipo === 'num'
                  ? <div style={{width: 70, height: 70, borderRadius: 35, background: e.acento, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', fontWeight: 900, fontSize: 42, flexShrink: 0}}>{i + 1}</div>
                  : <div style={{flexShrink: 0, transform: `scale(${pop(f, fps, e0 + 5, 7)})`}}>
                      <Marca tipo={tipo} k={k} color={tipo === 'cruz' ? e.malo : e.acento} /></div>}
                <div style={{fontWeight: 800, fontSize: 52, lineHeight: 1.12, position: 'relative'}}>
                  {it}
                  {tipo === 'cruz' ? <div style={{position: 'absolute', left: 0, top: '52%', height: 7, borderRadius: 4,
                    width: `${tachado * 100}%`, background: e.malo}} /> : null}
                </div>
              </Tarjeta>
            </div>
          );
        })}
      </div>
    </Caja>
  );
};

type Lado = {titulo?: string; objeto?: string; robot?: string; items?: string[]; nota?: string};

const Versus: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const lados = [p.izq as Lado, p.der as Lado];
  const gana = p.ganador === 'izq' ? 0 : p.ganador === 'der' ? 1 : -1;
  const veredicto = ramp(f, dur * 0.55, dur * 0.55 + 10);
  return (
    <Caja top={ESCENARIO.top - 20} alto={ESCENARIO.alto + 30}>
      <div style={{display: 'flex', gap: 24, alignItems: 'stretch', position: 'relative'}}>
        {lados.map((l, i) => {
          const s = pop(f, fps, cuando(p, i, i * 8), 11);
          const pierde = gana >= 0 && i !== gana;
          return (
            <div key={i} style={{width: 410, opacity: Math.min(1, s * 1.6), transform: `translateY(${(1 - s) * 400}px) scale(${1 - (pierde ? 0.06 : -0.03) * veredicto})`,
              filter: pierde ? `grayscale(${veredicto * 0.9}) brightness(${1 - veredicto * 0.35})` : 'none'}}>
              <Tarjeta claro={!pierde && gana >= 0 && veredicto > 0.5} style={{padding: '26px 22px', height: '100%', display: 'flex',
                flexDirection: 'column', alignItems: 'center', gap: 14, boxSizing: 'border-box',
                boxShadow: !pierde && gana >= 0 ? `${sombra}, 0 0 ${50 * veredicto}px ${e.acento}` : sombra}}>
                <div style={{fontWeight: 900, fontSize: 50, textAlign: 'center', lineHeight: 1.05}}>{l?.titulo}</div>
                {l?.objeto ? <Ilus nombre={l.objeto} lado={210} f={f} fps={fps} i={i} /> : null}
                {l?.robot ? <Robot clave={l.robot} f={f} tam={180} accion={!pierde && veredicto > 0.5 ? 'celebra' : 'quieto'} /> : null}
                {(l?.items ?? []).map((it, j) => (
                  <div key={j} style={{fontWeight: 800, fontSize: 40, textAlign: 'center', lineHeight: 1.12, opacity: pop(f, fps, 10 + i * 8 + j * 6)}}>{it}</div>
                ))}
                {l?.nota ? <div style={{fontWeight: 900, fontSize: 76, color: pierde ? e.malo : e.acento, marginTop: 'auto'}}>{l.nota}</div> : null}
              </Tarjeta>
            </div>
          );
        })}
        <div style={{position: 'absolute', left: '50%', top: '42%', transform: `translate(-50%, -50%) scale(${pop(f, fps, 12, 7)}) rotate(-8deg)`,
          width: 120, height: 120, borderRadius: 60, background: e.acento, border: '6px solid #fff', boxShadow: sombra,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily, fontWeight: 900, fontSize: 52, color: '#fff'}}>VS</div>
      </div>
    </Caja>
  );
};

// ---------------------------------------------------------------- el móvil

type Mensaje = {de?: string; nombre?: string; texto: string; hora?: string};

const Movil: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const s = pop(f, fps, 0, 12);
  const modo = texto(p.modo) || 'vistas';
  const W = 460, Hh = 780;
  let pantalla: React.ReactNode = null;
  if (modo === 'vistas') {
    const desde = Number(p.desde ?? 0), hasta = Number(p.hasta ?? 0);
    const k = ramp(f, 6, Math.max(16, dur * 0.7));
    const n = Math.round(desde + (hasta - desde) * k);
    const atascado = hasta <= desde * 1.05;
    pantalla = (
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(160deg, #24306a, #0d1430)'}}>
        <div style={{position: 'absolute', left: '50%', top: '42%', transform: 'translate(-50%,-50%)', width: 110, height: 110,
          borderRadius: 55, background: 'rgba(255,255,255,0.18)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{width: 0, height: 0, borderTop: '26px solid transparent', borderBottom: '26px solid transparent', borderLeft: '42px solid #fff', marginLeft: 10}} />
        </div>
        {['corazon', 'burbuja', 'avion'].map((ic, i) => (
          <div key={ic} style={{position: 'absolute', right: 18, top: 330 + i * 92, width: 56, height: 56, borderRadius: 28,
            background: 'rgba(255,255,255,0.2)'}} />
        ))}
        <div style={{position: 'absolute', left: 22, bottom: 70, fontFamily, color: '#fff'}}>
          <div style={{fontWeight: 800, fontSize: 26, opacity: 0.85}}>{texto(p.cuenta) || '@tu_marca'}</div>
          <div style={{width: 220, height: 12, borderRadius: 6, background: 'rgba(255,255,255,0.45)', marginTop: 12}} />
        </div>
        <div style={{position: 'absolute', left: 24, top: 74, fontFamily, fontWeight: 900, fontSize: 64, color: '#fff',
          display: 'flex', alignItems: 'center', gap: 14, textShadow: sombraTexto,
          transform: atascado ? `translateX(${Math.sin(f * 1.7) * (f > dur * 0.5 ? 4 : 0)}px)` : `scale(${1 + 0.06 * Math.sin(f / 2) * (k < 1 ? 1 : 0)})`}}>
          <div style={{width: 0, height: 0, borderTop: '18px solid transparent', borderBottom: '18px solid transparent', borderLeft: '28px solid #fff'}} />
          {n.toLocaleString('es-ES')}
        </div>
      </div>
    );
  } else if (modo === 'mensajes') {
    const msgs = lista<Mensaje>(p.mensajes);
    const paso = turnos(msgs.length, dur, 0.75, 5, 18);
    pantalla = (
      <div style={{position: 'absolute', inset: 0, background: '#0b1230', padding: '70px 18px 0', fontFamily}}>
        <div style={{color: '#fff', fontWeight: 900, fontSize: 40, marginBottom: 18}}>Mensajes</div>
        {msgs.map((m, i) => {
          const a = pop(f, fps, cuando(p, i, i * paso), 12);
          return (
            <div key={i} style={{display: 'flex', gap: 14, alignItems: 'center', padding: '14px 12px', marginBottom: 10, borderRadius: 18,
              background: 'rgba(80,120,255,0.18)', transform: `translateY(${(1 - a) * -90}px)`, opacity: a}}>
              <div style={{width: 62, height: 62, borderRadius: 31, background: `hsl(${215 + i * 25}, 70%, 60%)`, flexShrink: 0}} />
              <div style={{minWidth: 0}}>
                <div style={{color: '#fff', fontWeight: 900, fontSize: 32}}>{m.nombre}</div>
                <div style={{color: 'rgba(255,255,255,0.85)', fontWeight: 700, fontSize: 29, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: 320}}>{m.texto}</div>
              </div>
              <div style={{width: 16, height: 16, borderRadius: 8, background: e.acento, marginLeft: 'auto', flexShrink: 0}} />
            </div>
          );
        })}
      </div>
    );
  } else if (modo === 'comentarios') {
    const cs = lista<Mensaje>(p.mensajes);
    const paso = turnos(cs.length, dur, 0.7, 5, 16);
    pantalla = (
      <div style={{position: 'absolute', inset: 0, background: '#0b1230', padding: '74px 20px 0', fontFamily, color: '#fff'}}>
        <div style={{fontWeight: 900, fontSize: 36, textAlign: 'center', marginBottom: 22}}>Comentarios</div>
        {cs.map((m, i) => {
          const a = pop(f, fps, cuando(p, i, i * paso), 12);
          const marca = p.marcar ? ramp(f, cuando(p, i, i * paso) + 10, cuando(p, i, i * paso) + 18) : 0;
          return (
            <div key={i} style={{display: 'flex', gap: 14, alignItems: 'flex-start', marginBottom: 20, opacity: a,
              transform: `translateX(${(1 - a) * 200}px)`, background: `rgba(255,93,115,${0.22 * marca})`, borderRadius: 16, padding: 8,
              outline: marca > 0.5 ? `3px solid ${e.malo}` : 'none'}}>
              <div style={{width: 56, height: 56, borderRadius: 28, background: `hsl(${200 + i * 40}, 15%, 55%)`, flexShrink: 0}} />
              <div>
                <div style={{fontWeight: 800, fontSize: 26, opacity: 0.75}}>{m.nombre}</div>
                <div style={{fontWeight: 700, fontSize: 32, lineHeight: 1.15}}>{m.texto}</div>
              </div>
            </div>
          );
        })}
      </div>
    );
  } else {
    // perfil: sus números, y debajo sus publicaciones (con sus me gusta) o una lista de lo que tiene que tener
    const partes = lista<string>(p.partes);
    const rejilla = lista<string>(p.rejilla);
    const paso = turnos(Math.max(partes.length, rejilla.length), dur, 0.7, 4, 16);
    const datos = [texto(p.publicaciones) || '48', texto(p.seguidores) || '1,2 mil', texto(p.seguidos) || '310'];
    const late = p.resaltar === 'seguidores' ? 1 + 0.08 * Math.sin(f / 3.5) : 1;
    pantalla = (
      <div style={{position: 'absolute', inset: 0, background: '#0b1230', padding: '74px 20px 0', fontFamily, color: '#fff'}}>
        <div style={{fontWeight: 900, fontSize: 30, marginBottom: 16}}>{texto(p.cuenta) || '@tu_marca'}</div>
        <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
          <div style={{width: 104, height: 104, borderRadius: 52, background: 'linear-gradient(135deg, #9cc4ff, #3D7BFF)', border: '4px solid #fff', flexShrink: 0}} />
          {[0, 1, 2].map((i) => (
            <div key={i} style={{textAlign: 'center', flex: 1, transform: i === 1 ? `scale(${late})` : undefined}}>
              <div style={{fontWeight: 900, fontSize: i === 1 && p.resaltar === 'seguidores' ? 40 : 30, color: i === 1 && p.resaltar ? e.subrayado : '#fff'}}>{datos[i]}</div>
              <div style={{fontSize: 19, opacity: 0.7}}>{['posts', 'seguidores', 'seguidos'][i]}</div>
            </div>
          ))}
        </div>
        {rejilla.length ? (
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 26}}>
            {rejilla.map((t, i) => {
              const a = pop(f, fps, cuando(p, i, 6 + i * paso), 11);
              return (
                <div key={i} style={{height: 170, borderRadius: 8, background: `linear-gradient(160deg, hsl(${215 + i * 12}, 45%, 35%), #141c40)`,
                  display: 'flex', alignItems: 'flex-end', justifyContent: 'center', paddingBottom: 12, opacity: a, transform: `scale(${0.8 + 0.2 * a})`}}>
                  <div style={{fontWeight: 900, fontSize: 30, display: 'flex', alignItems: 'center', gap: 6,
                    color: p.malo ? '#ffd0d6' : '#fff'}}><span style={{color: e.malo}}>♥</span>{t}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{marginTop: 24, display: 'flex', flexDirection: 'column', gap: 12}}>
            {partes.map((t, i) => {
              const a = pop(f, fps, cuando(p, i, 6 + i * paso), 10);
              return (
                <div key={i} style={{display: 'flex', alignItems: 'center', gap: 12, fontWeight: 800, fontSize: 28,
                  background: 'rgba(80,120,255,0.18)', borderRadius: 14, padding: '12px 14px', transform: `scale(${a})`, opacity: a}}>
                  <div style={{width: 36, height: 36, borderRadius: 18, background: e.acento, flexShrink: 0, display: 'flex',
                    alignItems: 'center', justifyContent: 'center', fontSize: 22}}>{i + 1}</div>{t}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }
  return (
    <Caja top={ESCENARIO.top - 100} alto={Hh + 20}>
      <div style={{width: W, height: Hh, borderRadius: 60, background: '#11141c', padding: 14, boxShadow: `${sombra}, 0 0 0 4px #2b2f3a`,
        transform: `translateY(${(1 - s) * 500}px) rotate(${(1 - s) * 10 + Math.sin(f / 20) * 1.2}deg)`}}>
        <div style={{position: 'relative', width: '100%', height: '100%', borderRadius: 48, overflow: 'hidden'}}>
          {pantalla}
          <div style={{position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)', width: 120, height: 34, borderRadius: 17, background: '#000'}} />
        </div>
      </div>
    </Caja>
  );
};


type Bono = {texto: string; valor: string};

/** La página de venta de un curso y sus trucos: el precio tachado, la cuenta atrás y los bonos «valorados en». */
const Venta: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const s = pop(f, fps, 0, 12);
  const g = (i: number, d: number) => cuando(p, i, d);
  const modo = texto(p.modo) || 'precio';
  let cuerpo: React.ReactNode = null;
  if (modo === 'precio') {
    const tacha = ramp(f, g(0, dur * 0.3), g(0, dur * 0.3) + 8);
    const nuevo = pop(f, fps, g(1, dur * 0.45), 8);
    cuerpo = (
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6}}>
        <div style={{position: 'relative', fontWeight: 900, fontSize: 120, color: tacha > 0.5 ? '#8a94b3' : '#0c1a44'}}>
          {texto(p.antes)}
          <div style={{position: 'absolute', left: -10, right: -10, top: '52%', height: 14, borderRadius: 7, background: e.malo,
            transform: `scaleX(${tacha}) rotate(-8deg)`, transformOrigin: '0 50%'}} />
        </div>
        <div style={{fontWeight: 900, fontSize: 150, color: e.acento, transform: `scale(${nuevo})`, lineHeight: 1}}>{texto(p.ahora)}</div>
        <div style={{fontWeight: 900, fontSize: 40, color: '#fff', background: e.malo, padding: '6px 22px', borderRadius: 12,
          transform: `scale(${pop(f, fps, g(1, dur * 0.45) + 6, 8)}) rotate(-3deg)`, marginTop: 10}}>{texto(p.oferta) || 'SOLO HOY'}</div>
      </div>
    );
  } else if (modo === 'cuenta') {
    const reinicio = g(0, dur * 0.6);
    const segundos = f < reinicio ? 15 * 60 - 1 - Math.floor(f * 5) : 15 * 60 - 1 - Math.floor((f - reinicio) * 5);
    const mm = String(Math.floor(segundos / 60)).padStart(2, '0'), ss = String(segundos % 60).padStart(2, '0');
    const flash = f >= reinicio && f < reinicio + 6 ? 1 - (f - reinicio) / 6 : 0;
    cuerpo = (
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16}}>
        <div style={{fontWeight: 900, fontSize: 40, color: e.malo}}>{texto(p.aviso) || 'La oferta termina en'}</div>
        <div style={{display: 'flex', gap: 14}}>
          {[mm, ss].map((v, i) => (
            <div key={i} style={{background: '#0c1a44', color: '#fff', fontWeight: 900, fontSize: 130, borderRadius: 22, padding: '6px 22px',
              fontVariantNumeric: 'tabular-nums'}}>{v}</div>
          ))}
        </div>
        {f >= reinicio ? (
          <div style={{fontWeight: 900, fontSize: 40, color: '#fff', background: e.acento, padding: '6px 22px', borderRadius: 12,
            transform: `scale(${pop(f, fps, reinicio + 2, 8)})`}}>{texto(p.nota) || 'Recargas la página… y vuelve a empezar'}</div>
        ) : null}
        <div style={{position: 'absolute', inset: 0, background: '#fff', opacity: flash, borderRadius: 34}} />
      </div>
    );
  } else {
    const bonos = lista<Bono>(p.bonos);
    const paso = turnos(bonos.length + 1, dur, 0.75, 6, 18);
    const fin = g(bonos.length, bonos.length * paso);
    cuerpo = (
      <div style={{display: 'flex', flexDirection: 'column', gap: 12, width: '100%'}}>
        {bonos.map((b, i) => {
          const a = pop(f, fps, g(i, i * paso), 11);
          return (
            <div key={i} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#eef2fb', borderRadius: 16,
              padding: '14px 20px', fontWeight: 800, fontSize: 36, opacity: a, transform: `translateX(${(1 - a) * -300}px)`}}>
              <span>{b.texto}</span><span style={{color: e.acento, fontWeight: 900, fontSize: 30}}>Valorado en {b.valor}</span>
            </div>
          );
        })}
        <div style={{textAlign: 'center', fontWeight: 900, fontSize: 56, color: e.malo, marginTop: 8, transform: `scale(${pop(f, fps, fin, 8)})`}}>
          {texto(p.total)}</div>
      </div>
    );
  }
  return (
    <Caja>
      <div style={{width: ANCHO - 20, transform: `translateY(${(1 - s) * 400}px) rotate(${(1 - s) * -6}deg)`}}>
        <Tarjeta claro style={{padding: 0, overflow: 'hidden', position: 'relative'}}>
          <div style={{background: '#dfe6f7', padding: '14px 22px', display: 'flex', alignItems: 'center', gap: 10}}>
            {['#ff5d73', '#fbbf24', '#34d399'].map((c) => <div key={c} style={{width: 18, height: 18, borderRadius: 9, background: c}} />)}
            <div style={{flex: 1, marginLeft: 12, background: '#fff', borderRadius: 10, padding: '6px 16px', fontWeight: 700, fontSize: 24,
              color: '#5b6b95'}}>{texto(p.web) || 'micurso.com/oferta'}</div>
          </div>
          <div style={{padding: '30px 30px 36px', display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative'}}>
            {p.titulo ? <div style={{fontWeight: 900, fontSize: 44, marginBottom: 18, textAlign: 'center'}}>{texto(p.titulo)}</div> : null}
            {cuerpo}
          </div>
        </Tarjeta>
      </div>
    </Caja>
  );
};

// ---------------------------------------------------------------- chat

const Chat: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const msgs = lista<Mensaje>(p.mensajes);
  const paso = turnos(msgs.length, dur, 0.8, 10, 30);
  return (
    <Caja>
      <div style={{display: 'flex', flexDirection: 'column', gap: 18, width: ANCHO - 60}}>
        {msgs.map((m, i) => {
          const llega = cuando(p, i, i * paso);
          const tu = m.de === 'tu';
          const escribe = !tu && f >= llega - 9 && f < llega;
          const a = pop(f, fps, llega, 11);
          if (f < llega - 9) return null;
          return (
            <div key={i} style={{alignSelf: tu ? 'flex-end' : 'flex-start', maxWidth: '82%'}}>
              {escribe ? (
                <div style={{background: '#fff', borderRadius: 30, padding: '18px 26px', display: 'flex', gap: 10}}>
                  {[0, 1, 2].map((d) => <div key={d} style={{width: 16, height: 16, borderRadius: 8, background: '#7d8496',
                    transform: `translateY(${Math.sin((f + d * 4) / 2.5) * 5}px)`}} />)}
                </div>
              ) : (
                <div style={{transform: `scale(${a})`, transformOrigin: tu ? '100% 100%' : '0% 100%'}}>
                  <div style={{background: tu ? e.acento : '#ffffff', color: tu ? '#fff' : '#0c1a44', fontFamily, fontWeight: 700,
                    fontSize: 42, lineHeight: 1.18, padding: '20px 30px', borderRadius: 34, boxShadow: sombra,
                    borderBottomRightRadius: tu ? 8 : 34, borderBottomLeftRadius: tu ? 34 : 8}}>{m.texto}</div>
                  {m.hora ? <div style={{fontFamily, fontWeight: 700, fontSize: 26, color: 'rgba(255,255,255,0.7)', marginTop: 6,
                    textAlign: tu ? 'right' : 'left'}}>{m.hora}</div> : null}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Caja>
  );
};

// ---------------------------------------------------------------- texto grande

const PalabraPlano: React.FC<P> = ({p, f, fps}) => {
  const e = useEstilo();
  const t = texto(p.texto);
  const s = pop(f, fps, 0, 7);
  const tam = t.length <= 4 ? 260 : t.length <= 8 ? 190 : t.length <= 12 ? 140 : 110;
  const sub = texto(p.sub);
  return (
    <Caja>
      <div style={{fontFamily, fontWeight: 900, fontSize: tam, lineHeight: 0.95, color: p.malo ? e.malo : '#fff', textAlign: 'center',
        letterSpacing: -3, transform: `scale(${(2.2 - 1.2 * s) * (1 + 0.035 * Math.sin(f / 7))}) rotate(${(1 - s) * -8 + Math.sin(f / 15) * 1.5}deg)`, opacity: Math.min(1, s * 1.5),
        filter: `blur(${(1 - Math.min(1, s)) * 14}px)`, textShadow: `${sombraTexto}, 0 0 ${50 + 25 * Math.sin(f / 5)}px ${p.malo ? e.malo : e.acento}`}}>{t}</div>
      {sub ? (
        <div style={{marginTop: 40, transform: `scale(${pop(f, fps, 8)})`}}>
          <Tarjeta style={{padding: '16px 34px', fontSize: 48, fontWeight: 800, textAlign: 'center'}}>{sub}</Tarjeta>
        </div>
      ) : null}
    </Caja>
  );
};

const Frase: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const s = pop(f, fps, 0, 11);
  const enTacha = Array.isArray(p.golpes) && (p.golpes as number[]).length ? (p.golpes as number[])[0] : dur * 0.45;
  const tacha = p.tachar ? ramp(f, enTacha, enTacha + 8) : 0;
  const fuera = p.tachar ? ramp(f, enTacha + 10, enTacha + 24) : 0;
  return (
    <Caja>
      <div style={{transform: `rotate(${(1 - s) * 12 - 2 + fuera * 5 + Math.sin(f / 13) * 0.8}deg) scale(${s * (1 - 0.1 * fuera)}) translateY(${Math.sin(f / 11) * 6}px)`,
        position: 'relative', filter: `grayscale(${fuera * 0.8}) brightness(${1 - fuera * 0.25})`}}>
        <Tarjeta claro style={{padding: '56px 56px 48px', maxWidth: ANCHO, position: 'relative'}}>
          <div style={{position: 'absolute', top: -78, left: 26, fontSize: 190, fontWeight: 900, color: e.acento, lineHeight: 1}}>“</div>
          <div style={{fontWeight: 900, fontSize: 66, lineHeight: 1.12}}>{texto(p.texto)}</div>
          {p.autor ? <div style={{fontWeight: 700, fontSize: 32, color: '#5b6b95', marginTop: 20}}>{texto(p.autor)}</div> : null}
          {p.tachar ? <div style={{position: 'absolute', left: 30, right: 30, top: '50%', height: 14, borderRadius: 7, background: e.malo,
            transform: `scaleX(${tacha}) rotate(-4deg)`, transformOrigin: '0 50%'}} /> : null}
        </Tarjeta>
      </div>
    </Caja>
  );
};

// ---------------------------------------------------------------- tiempo

const RelojPlano: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const s = pop(f, fps, 0, 9);
  const vueltas = Number(p.vueltas ?? 3);
  const k = ramp(f, 0, dur * 0.85, (x) => x);
  const min = vueltas * 360 * k, hora = vueltas * 30 * k;
  const tiembla = Math.sin(f * 2.4) * 3 * (1 - Math.abs(k - 0.5) * 2);
  return (
    <Caja>
      <svg width="470" height="470" viewBox="0 0 400 400" style={{transform: `scale(${s}) rotate(${tiembla}deg)`,
        filter: 'drop-shadow(0 26px 22px rgba(0,0,0,0.45))', overflow: 'visible'}}>
        <circle cx="120" cy="80" r="40" fill={e.acento} /><circle cx="280" cy="80" r="40" fill={e.acento} />
        <circle cx="200" cy="210" r="160" fill={e.acento} />
        <circle cx="200" cy="210" r="134" fill="#f5f8ff" />
        {Array.from({length: 12}).map((_, i) => (
          <rect key={i} x="195" y="86" width="10" height={i % 3 === 0 ? 26 : 14} rx="5" fill="#0c1a44" transform={`rotate(${i * 30} 200 210)`} />
        ))}
        <path d={`M200 210 L200 ${210 - 104 * k}`} />
        <rect x="193" y="122" width="14" height="94" rx="7" fill="#0c1a44" transform={`rotate(${min} 200 210)`} />
        <rect x="193" y="150" width="14" height="66" rx="7" fill="#3D7BFF" transform={`rotate(${hora + 60} 200 210)`} />
        <circle cx="200" cy="210" r="14" fill="#0c1a44" />
      </svg>
      {p.texto ? (
        <div style={{marginTop: 18, transform: `scale(${pop(f, fps, 6)})`}}>
          <Tarjeta style={{padding: '14px 34px', fontSize: 54, fontWeight: 900}}>{texto(p.texto)}</Tarjeta>
        </div>
      ) : null}
    </Caja>
  );
};

const Calendario: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const dias = lista<string>(p.dias).length ? lista<string>(p.dias) : ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
  const notas = lista<string>(p.notas);
  const marcados = lista<number>(p.marcados);
  const tipo = texto(p.marca) || 'check';
  const paso = turnos(marcados.length, dur, 0.7, 5, 14);
  return (
    <Caja>
      <div style={{display: 'grid', gridTemplateColumns: `repeat(${dias.length <= 5 ? dias.length : 4}, ${dias.length === 5 ? 168 : 190}px)`, gap: 18}}>
        {dias.map((d, i) => {
          const s = pop(f, fps, i * 2, 12);
          const orden = marcados.indexOf(i);
          const e0 = cuando(p, orden, 8 + orden * paso);
          const m = orden >= 0 ? pop(f, fps, e0, 8) : 0;
          const color = tipo === 'cruz' ? e.malo : e.acento;
          return (
            <div key={i} style={{transform: `scale(${s})`, position: 'relative'}}>
              <Tarjeta claro={m > 0.5 && tipo !== 'cruz'} style={{height: dias.length === 5 ? 230 : 190, display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', padding: 8, boxSizing: 'border-box'}}>
                <div style={{fontWeight: 900, fontSize: 64}}>{d}</div>
                {notas[i] ? <div style={{fontWeight: 800, fontSize: 28, textAlign: 'center', lineHeight: 1.05, opacity: 0.9}}>{notas[i]}</div> : null}
              </Tarjeta>
              {orden >= 0 ? (
                <div style={{position: 'absolute', right: -10, top: -10, transform: `scale(${m}) rotate(${(1 - m) * 90}deg)`}}>
                  <Marca tipo={tipo} k={ramp(f, e0, e0 + 6)} color={color} />
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </Caja>
  );
};

// ---------------------------------------------------------------- el equipo trabajando

type Paso = {quien: string; texto: string};

const Flujo: React.FC<P> = ({p, f, fps, dur}) => {
  const pasos = lista<Paso>(p.pasos);
  const paso = (dur * 0.85) / Math.max(1, pasos.length);
  const entra = pasos.map((_, i) => cuando(p, i, i * paso));
  const activo = Math.max(0, entra.filter((x) => f >= x).length - 1);
  return (
    <Caja top={ESCENARIO.top - 60} alto={ESCENARIO.alto + 80}>
      <div style={{display: 'flex', flexDirection: 'column', gap: 10, width: ANCHO - 40, position: 'relative'}}>
        {pasos.map((x, i) => {
          const s = pop(f, fps, entra[i], 12);
          const on = i === activo;
          const hecho = i < activo;
          const c = x.quien === 'tu' ? '#ffffff' : colorDe(x.quien);
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 18, opacity: f < entra[i] ? 0.25 : 1,
              transform: `scale(${on ? 1.04 : 0.96}) translateX(${on ? 0 : 0}px)`}}>
              <div style={{width: 100, height: 100, flexShrink: 0, transform: `scale(${0.7 + 0.3 * s})`, display: 'flex',
                alignItems: 'center', justifyContent: 'center'}}>
                {x.quien === 'tu'
                  ? <div style={{width: 84, height: 84, borderRadius: 42, background: '#fff', color: '#0c1a44', fontWeight: 900, fontSize: 34,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: on ? '0 0 30px #fff' : 'none'}}>Tú</div>
                  : <Robot clave={x.quien} f={f} tam={92} accion={on ? 'trabaja' : hecho ? 'quieto' : 'duerme'} semilla={i} />}
              </div>
              <div style={{flex: 1, fontFamily, borderRadius: 22, padding: '14px 22px', color: '#fff',
                background: on ? `linear-gradient(90deg, ${c}55, rgba(20,40,110,0.7))` : 'rgba(20,40,110,0.45)',
                border: `2px solid ${on ? c : 'rgba(150,185,255,0.18)'}`, boxShadow: on ? `0 0 34px ${c}88` : 'none'}}>
                <div style={{fontWeight: 900, fontSize: 32, color: c}}>{x.quien === 'tu' ? 'Tú' : NOMBRES[x.quien]?.nombre ?? x.quien}</div>
                <div style={{fontWeight: 800, fontSize: 38, lineHeight: 1.1}}>{x.texto}</div>
              </div>
              <div style={{width: 46, flexShrink: 0, transform: `scale(${hecho ? pop(f, fps, entra[i + 1] ?? f, 8) : 0})`}}>
                <Marca tipo="check" k={1} color={c} />
              </div>
            </div>
          );
        })}
      </div>
    </Caja>
  );
};


type Encuadre = {t: number; x: number; y: number; w: number};
type Punto = {t: number; x: number; y: number; clic?: boolean};

/** Una grabación de pantalla de la app (con un negocio de prueba): el encuadre viaja de un rectángulo a otro y un
 * cursor señala lo que se dice. Ocupa toda la pantalla, por debajo de rótulos y subtítulos. */
const Pantalla: React.FC<P> = ({p, f, fps}) => {
  const t = f / fps;
  const es = lista<Encuadre>(p.encuadres);
  const ancho = Number(p.ancho), alto = Number(p.alto);
  let r = es[0] ?? {t: 0, x: 0, y: 0, w: ancho};
  for (let i = 0; i < es.length - 1; i++) {
    if (t >= es[i].t && t <= es[i + 1].t) {
      const k = interpolate(t, [es[i].t, es[i + 1].t], [0, 1], {...CLAMP, easing: Easing.bezier(0.65, 0, 0.35, 1)});
      r = {t, x: es[i].x + (es[i + 1].x - es[i].x) * k, y: es[i].y + (es[i + 1].y - es[i].y) * k, w: es[i].w + (es[i + 1].w - es[i].w) * k};
    } else if (t > es[i + 1].t) r = es[i + 1];
  }
  const escala = 1080 / r.w;
  const cur = lista<Punto>(p.cursor).filter((x) => x.t <= t + 0.6);
  let cx: number | null = null, cy = 0, clic = 0;
  if (cur.length) {
    const a = cur.length > 1 ? cur[cur.length - 2] : cur[0], b = cur[cur.length - 1];
    const k = interpolate(t, [b.t - 0.6, b.t], [0, 1], {...CLAMP, easing: Easing.bezier(0.65, 0, 0.35, 1)});
    cx = a.x + (b.x - a.x) * k; cy = a.y + (b.y - a.y) * k;
    if (b.clic && t >= b.t) clic = Math.max(0, 1 - (t - b.t) / 0.4);
  }
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: '#05070f'}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: ancho, height: alto, transformOrigin: '0 0',
        transform: `translate(${-r.x * escala}px, ${-r.y * escala}px) scale(${escala})`}}>
        <OffthreadVideo src={staticFile(texto(p.archivo))} startFrom={Math.round(Number(p.desde ?? 0) * fps)} muted style={{width: ancho, height: alto}} />
        {cx !== null ? (
          <div style={{position: 'absolute', left: cx, top: cy, transform: `scale(${2.2 / escala})`, transformOrigin: '0 0'}}>
            {clic ? <div style={{position: 'absolute', left: -30, top: -30, width: 60, height: 60, borderRadius: 30, border: '4px solid #9cc4ff',
              transform: `scale(${1 + (1 - clic) * 1.2})`, opacity: clic}} /> : null}
            <svg width="34" height="40" viewBox="0 0 34 40" style={{filter: 'drop-shadow(0 3px 4px rgba(0,0,0,0.5))'}}>
              <path d="M2 2 L2 32 L10 25 L16 38 L22 35 L16 23 L27 23 Z" fill="#fff" stroke="#0c1a44" strokeWidth="2.5" strokeLinejoin="round" />
            </svg>
          </div>
        ) : null}
      </div>
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(5,7,15,0.55) 0%, transparent 22%, transparent 62%, rgba(5,7,15,0.7) 100%)'}} />
    </div>
  );
};

// ---------------------------------------------------------------- cierre

const Cierre: React.FC<P> = ({p, f, fps}) => {
  const e = useEstilo();
  const clave = texto(p.palabra);
  const web = texto(p.web);
  const s = pop(f, fps, 6, 8);
  const late = 1 + 0.05 * Math.sin(f / 4);
  return (
    <Caja top={ESCENARIO.top - 80} alto={ESCENARIO.alto + 80}>
      <Robot clave="jefa" f={f} tam={280} accion="saluda" />
      {p.enlace ? (
        <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 4}}>
          <svg width="90" height="90" viewBox="0 0 90 90" style={{transform: `translateY(${-Math.abs(Math.sin(f / 5)) * 22}px) scale(${pop(f, fps, 3)})`}}>
            <path d="M45 8 L80 46 L58 46 L58 84 L32 84 L32 46 L10 46 Z" fill="#fff" stroke={e.acento} strokeWidth="5" strokeLinejoin="round" />
          </svg>
          <div style={{transform: `scale(${s * late}) rotate(-3deg)`, marginTop: 10, position: 'relative'}}>
            <Destellos f={f - 8} color={e.subrayado} radio={280} n={10} />
            <div style={{fontFamily, fontWeight: 900, fontSize: 84, color: '#fff', background: e.acento, padding: '10px 40px', borderRadius: 30,
              border: '7px solid #fff', textAlign: 'center', lineHeight: 1.02, textTransform: 'uppercase',
              boxShadow: `${sombra}, 0 0 ${50 + 20 * Math.sin(f / 4)}px ${e.acento}`}}>Enlace<br />en el perfil</div>
          </div>
          {p.texto ? <div style={{fontFamily, fontWeight: 800, fontSize: 44, color: '#fff', marginTop: 24, textShadow: sombraTexto, textAlign: 'center',
            maxWidth: ANCHO, transform: `scale(${pop(f, fps, 14)})`}}>{texto(p.texto)}</div> : null}
        </div>
      ) : clave ? (
        <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 6}}>
          <div style={{fontFamily, fontWeight: 900, fontSize: 54, color: '#fff', textShadow: sombraTexto, transform: `scale(${pop(f, fps, 3)})`}}>Comenta</div>
          <div style={{transform: `scale(${s * late}) rotate(-3deg)`, marginTop: 8, position: 'relative'}}>
            <Destellos f={f - 8} color={e.subrayado} radio={260} n={10} />
            <div style={{fontFamily, fontWeight: 900, fontSize: 120, color: '#fff', letterSpacing: 2, background: e.acento,
              padding: '6px 46px', borderRadius: 30, border: '7px solid #fff', boxShadow: `${sombra}, 0 0 ${50 + 20 * Math.sin(f / 4)}px ${e.acento}`}}>{clave}</div>
          </div>
          <div style={{fontFamily, fontWeight: 800, fontSize: 44, color: '#fff', marginTop: 22, textShadow: sombraTexto,
            transform: `scale(${pop(f, fps, 14)})`}}>{texto(p.texto) || 'y te mando el enlace'}</div>
        </div>
      ) : (
        <div style={{transform: `scale(${s})`, marginTop: 10, fontFamily, fontWeight: 900, fontSize: 104, color: '#fff', letterSpacing: -2,
          textShadow: `${sombraTexto}, 0 0 50px ${e.acento}`}}>{web}</div>
      )}
      {(clave || p.enlace) && web ? <div style={{fontFamily, fontWeight: 800, fontSize: 34, color: e.subrayado, marginTop: 14, opacity: pop(f, fps, 20)}}>{web}</div> : null}
    </Caja>
  );
};

/** Un vídeo de recurso (banco, ya tratado con el color de la marca) a pantalla completa: empujón lento de cámara,
 *  sombra arriba y abajo para que se lean el título y los subtítulos, y un rótulo opcional encima. */
const Recurso: React.FC<P> = ({p, f, fps, dur}) => {
  const e = useEstilo();
  const k = interpolate(f, [0, Math.max(1, dur)], [0, 1], CLAMP);
  const t = texto(p.texto);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{transform: `scale(${1.02 + 0.06 * k})`}}>
        <OffthreadVideo src={staticFile(texto(p.archivo))} muted style={{width: 1080, height: 1920, objectFit: 'cover'}} />
      </AbsoluteFill>
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(4,8,24,0.75) 0%, rgba(4,8,24,0) 28%, rgba(4,8,24,0) 58%, rgba(4,8,24,0.8) 100%)'}} />
      {t ? (
        <Caja>
          <div style={{fontFamily, fontWeight: 900, fontSize: t.length > 14 ? 92 : 120, lineHeight: 1, color: '#fff', textAlign: 'center',
            letterSpacing: -2, textShadow: `${sombraTexto}, 0 0 40px ${e.acento}`, opacity: ramp(f, 2, 10),
            transform: `translateY(${(1 - ramp(f, 2, 14)) * 30}px)`}}>{t}</div>
        </Caja>
      ) : null}
    </AbsoluteFill>
  );
};

export const PLANOS: Record<string, React.FC<P>> = {
  objetos: Objetos, robot: RobotPlano, equipo: EquipoPlano, cifra: Cifra, grafica: Grafica, lista: Lista, versus: Versus,
  movil: Movil, chat: Chat, palabra: PalabraPlano, frase: Frase, reloj: RelojPlano, calendario: Calendario, flujo: Flujo,
  cierre: Cierre, suma: Suma, venta: Venta, pantalla: Pantalla, recurso: Recurso,
};

/** Sello que cae encima de cualquier plano a mitad («MITO», «ERROR»). */
export const Sello: React.FC<{texto: string; f: number; fps: number; dur: number; en?: number; abajo?: boolean}> = ({texto: t, f, fps, dur, en, abajo}) => {
  const e = useEstilo();
  const llega = en ?? Math.round(dur * 0.5);
  if (f < llega) return null;
  const s = pop(f, fps, llega, 9);
  return (
    <div style={{position: 'absolute', left: CV, top: ESCENARIO.top + ESCENARIO.alto * (abajo ? 0.7 : 0.45), transform:
      `translate(-50%, -50%) rotate(-12deg) scale(${3 - 2 * s})`, opacity: Math.min(1, s * 2), fontFamily, fontWeight: 900,
      fontSize: 120, color: e.malo, border: `12px solid ${e.malo}`, borderRadius: 26, padding: '6px 40px', letterSpacing: 4,
      background: 'rgba(255,255,255,0.92)', boxShadow: sombra}}>{t}</div>
  );
};

export const desplazamiento = (f: number) => interpolate(f, [0, 8], [1, 0], {...CLAMP, easing: EXPO});
