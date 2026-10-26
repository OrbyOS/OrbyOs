import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {CLAMP, EXPO, ramp, useEstilo} from './estilo';
import {Linea} from './piezas';
import type {Grafico} from './tipos';

/**
 * Efectos explicativos tipo After Effects: lista, cifra, comparación, proceso y gráfica. Todos con el mismo lenguaje:
 * cada elemento entra de golpe cuando se dice y se asienta, y los números cuentan. Se pintan dentro de una caja
 * (la zona que les deja la composición) y escalan con ella.
 */
export type Efecto = Extract<Grafico, {tipo: 'efecto'}>;
export type Caja = {x0: number; x1: number; y0: number; y1: number};

/** Una línea que aparece con su elemento (sin dibujarse de un extremo al otro: demasiado perfecto). */
const Trazo: React.FC<{x1: number; y1: number; x2: number; y2: number; at: number; dur?: number; color: string; grosor?: number}> = ({
  x1, y1, x2, y2, at, color, grosor = 3,
}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [at, at + 3], [0, 1], CLAMP);
  return <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={grosor} strokeLinecap="round" opacity={t} />;
};

/** Número que cuenta desde 0 hasta su valor (respeta decimales y separador de miles). */
const contar = (f: number, at: number, valor: string, dur = 18) => {
  const n = Number(valor.replace(/\./g, '').replace(',', '.'));
  if (!isFinite(n)) return valor;
  const v = interpolate(f, [at, at + dur], [0, n], {...CLAMP, easing: EXPO});
  const decimales = (valor.split(',')[1] || '').length;
  return v.toLocaleString('es-ES', {minimumFractionDigits: decimales, maximumFractionDigits: decimales});
};

const Antetitulo: React.FC<{texto?: string; at: number}> = ({texto, at}) => {
  const e = useEstilo();
  if (!texto) return null;
  return (
    <div style={{fontFamily: e.mono, fontSize: 26, letterSpacing: 6, textTransform: 'uppercase', color: e.acento, marginBottom: 34}}>
      <Linea at={at} dur={8}>{texto}</Linea>
    </div>
  );
};

const Lista: React.FC<{g: Efecto; escala: number}> = ({g, escala}) => {
  const e = useEstilo();
  return (
    <div style={{width: 860, transform: `scale(${escala})`, transformOrigin: 'center'}}>
      <Antetitulo texto={g.titulo} at={g.f} />
      {g.elementos.map((el, i) => (
        <div key={i} style={{display: 'flex', alignItems: 'center', gap: 30, marginBottom: 26}}>
          <span style={{fontFamily: e.serif, fontSize: 92, lineHeight: 1, color: e.acento, width: 120}}>
            <Linea at={el.f} dur={9}>{String(i + 1).padStart(2, '0')}</Linea>
          </span>
          <div style={{flex: 1}}>
            <div style={{fontFamily: e.sans, fontWeight: 800, fontSize: 54, letterSpacing: '-0.02em', color: e.texto, lineHeight: 1.08}}>
              <Linea at={el.f + 2}>{el.texto}</Linea>
            </div>
            <svg width="700" height="8" style={{display: 'block', marginTop: 14}}>
              <Trazo x1={0} y1={4} x2={700} y2={4} at={el.f + 4} color={e.filete} grosor={2} />
            </svg>
          </div>
        </div>
      ))}
    </div>
  );
};

const Cifra: React.FC<{g: Efecto; escala: number}> = ({g, escala}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const el = g.elementos[0] ?? {texto: '', valor: '0', f: g.f};
  return (
    <div style={{width: 940, textAlign: 'center', transform: `scale(${escala})`}}>
      <Antetitulo texto={g.titulo} at={g.f} />
      <div style={{fontFamily: e.sans, fontWeight: 900, fontSize: 260, lineHeight: 0.9, letterSpacing: '-0.05em', color: e.texto}}>
        {contar(f, el.f, el.valor ?? '0')}
        {g.sufijo && <span style={{fontFamily: e.serif, fontWeight: 400, fontStyle: 'italic', fontSize: 120, color: e.acento, letterSpacing: 0}}> {g.sufijo}</span>}
      </div>
      <svg width="560" height="10" style={{display: 'block', margin: '28px auto 22px'}}>
        <Trazo x1={0} y1={5} x2={560} y2={5} at={el.f + 6} dur={16} color={e.acento} grosor={4} />
      </svg>
      <div style={{fontFamily: e.serif, fontSize: 68, color: e.texto}}><Linea at={el.f + 10}>{el.texto}</Linea></div>
    </div>
  );
};

const Comparacion: React.FC<{g: Efecto; escala: number}> = ({g, escala}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const [a, b] = [g.elementos[0], g.elementos[1] ?? g.elementos[0]];
  const tachado = ramp(f, b.f, b.f + 10);
  const columna = (el: typeof a, apagada: boolean, lado: 'izq' | 'der') => (
    <div style={{flex: 1, textAlign: 'center', opacity: apagada ? 1 - tachado * 0.55 : 1}}>
      <div style={{fontFamily: e.mono, fontSize: 26, letterSpacing: 6, textTransform: 'uppercase', color: lado === 'der' ? e.acento : e.texto, opacity: lado === 'der' ? 1 : 0.7}}>
        <Linea at={el.f}>{el.texto}</Linea>
      </div>
      <div style={{position: 'relative', display: 'inline-block', marginTop: 22, fontFamily: e.serif, fontSize: 120, lineHeight: 1, color: e.texto}}>
        <Linea at={el.f + 3}>{el.valor && /\d/.test(el.valor) ? contar(f, el.f + 3, el.valor, 14) : el.valor}</Linea>
        {apagada && <div style={{position: 'absolute', left: -10, right: -10, top: '52%', height: 5, backgroundColor: e.acento,
                                  transform: `scaleX(${tachado})`, transformOrigin: 'left'}} />}
      </div>
    </div>
  );
  return (
    <div style={{width: 960, transform: `scale(${escala})`}}>
      <Antetitulo texto={g.titulo} at={g.f} />
      <div style={{display: 'flex', alignItems: 'center'}}>
        {columna(a, true, 'izq')}
        <svg width="6" height="260"><Trazo x1={3} y1={0} x2={3} y2={260} at={a.f + 4} dur={14} color={e.filete} grosor={2} /></svg>
        {columna(b, false, 'der')}
      </div>
    </div>
  );
};

const Proceso: React.FC<{g: Efecto; escala: number}> = ({g, escala}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const n = Math.max(2, g.elementos.length);
  const paso = 760 / (n - 1);
  return (
    <div style={{width: 960, transform: `scale(${escala})`}}>
      <Antetitulo texto={g.titulo} at={g.f} />
      <svg width="960" height="140" style={{display: 'block'}}>
        {g.elementos.slice(1).map((el, i) => (
          <Trazo key={i} x1={100 + i * paso + 48} y1={70} x2={100 + (i + 1) * paso - 48} y2={70} at={el.f - 8} dur={10} color={e.filete} grosor={3} />
        ))}
        {g.elementos.map((el, i) => {
          const t = ramp(f, el.f, el.f + 10);
          const activo = f >= el.f;
          return (
            <g key={i}>
              {/* El círculo se dibuja como un trazo y se rellena al activarse */}
              <circle cx={100 + i * paso} cy={70} r={44} fill={activo && i === g.elementos.length - 1 ? e.acento : 'transparent'}
                      stroke={activo ? e.acento : e.filete} strokeWidth={4} opacity={Math.min(1, t * 3)} />
              <text x={100 + i * paso} y={82} textAnchor="middle" fontFamily={e.mono} fontSize={34} opacity={t}
                    fill={activo && i === g.elementos.length - 1 ? e.fondo : e.texto}>{i + 1}</text>
            </g>
          );
        })}
      </svg>
      <div style={{position: 'relative', height: 140}}>
        {g.elementos.map((el, i) => (
          <div key={i} style={{position: 'absolute', left: 100 + i * paso - 150, width: 300, textAlign: 'center', top: 14,
                               fontFamily: e.sans, fontWeight: 800, fontSize: 50, lineHeight: 1.08, color: e.texto}}>
            <Linea at={el.f + 3}>{el.texto}</Linea>
          </div>
        ))}
      </div>
    </div>
  );
};

const Grafica: React.FC<{g: Efecto; escala: number}> = ({g, escala}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const valores = g.elementos.map((el) => Number(String(el.valor ?? '0').replace(/\./g, '').replace(',', '.')) || 0);
  const max = Math.max(1, ...valores);
  const ancho = 760 / g.elementos.length;
  return (
    <div style={{width: 900, transform: `scale(${escala})`}}>
      <Antetitulo texto={g.titulo} at={g.f} />
      <svg width="900" height="520">
        <Trazo x1={70} y1={440} x2={860} y2={440} at={g.f} dur={12} color={e.filete} grosor={2} />
        {g.elementos.map((el, i) => {
          const t = ramp(f, el.f, el.f + 14);
          const h = (valores[i] / max) * 360 * t;
          const x = 90 + i * ancho;
          const ultima = i === g.elementos.length - 1;
          return (
            <g key={i}>
              <rect x={x} y={440 - h} width={ancho * 0.62} height={h} rx={6} fill={ultima ? e.acento : e.fondoLuz}
                    stroke={ultima ? 'none' : e.filete} />
              <text x={x + ancho * 0.31} y={440 - h - 16} textAnchor="middle" fontFamily={e.sans} fontWeight={800} fontSize={52}
                    fill={e.texto} opacity={t}>{contar(f, el.f, String(el.valor ?? '0'), 14)}</text>
              <text x={x + ancho * 0.31} y={496} textAnchor="middle" fontFamily={e.mono} fontSize={30} letterSpacing={3}
                    fill={e.apagado} opacity={t}>{el.texto.toUpperCase()}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const PIEZAS = {lista: Lista, cifra: Cifra, comparacion: Comparacion, proceso: Proceso, grafica: Grafica};

/** El efecto centrado en su caja, con la escala que le toca a cada composición. */
export const EfectoEnCaja: React.FC<{g: Efecto; caja: Caja; escala: number}> = ({g, caja, escala}) => {
  const P = PIEZAS[g.clase];
  return (
    <div style={{position: 'absolute', left: caja.x0, width: caja.x1 - caja.x0, top: caja.y0, height: caja.y1 - caja.y0, display: 'flex',
                 alignItems: 'center', justifyContent: 'center'}}>
      {/* Las piezas se diseñan a 960 px de ancho: se encogen para caber en la zona segura. */}
      <P g={g} escala={escala * Math.min(1, (caja.x1 - caja.x0) / 960)} />
    </div>
  );
};
