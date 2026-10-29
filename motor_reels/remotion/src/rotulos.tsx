import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {CLAMP, ramp, useEstilo} from './estilo';
import {LADOS} from './zona';
import type {Grafico} from './tipos';

/**
 * Piezas del estilo de rótulos (referencia: cuentas de IA en Instagram), todas con los colores del kit: rótulo sans + cursiva, esquinas de
 * portada de revista, barra de prompt, pantalla oscura de terminal y CTA con el comentario. Entran con un salto corto y se
 * van con su plano: nada se queda fijo.
 */
type G<T extends Grafico['tipo']> = Extract<Grafico, {tipo: T}>;

const useSalto = (at: number) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: f - at, fps, config: {damping: 15, mass: 0.6, stiffness: 210}});
};

/** «BIGGER captions.»: la palabra en sans gruesa, blanca y con sombra; debajo, la cursiva serif en una pastilla del panel. */
export const Rotulo: React.FC<{g: G<'rotulo'>}> = ({g}) => {
  const e = useEstilo();
  const a = useSalto(g.f);
  const b = useSalto(g.f + 4);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {/* Centrado y arriba del todo: entero por encima de los ojos, también en los planos cerrados. */}
      <div style={{position: 'absolute', top: 244, ...LADOS, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center'}}>
        <div style={{fontFamily: e.sans, fontWeight: 900, fontSize: 108, lineHeight: 0.92, letterSpacing: '-0.04em', paddingRight: '0.04em', color: '#FFFFFF',
          textTransform: 'uppercase', textShadow: '0 8px 34px rgba(0, 0, 0, 0.45)', transform: `scale(${0.9 + 0.1 * a})`,
          transformOrigin: '50% 100%', opacity: Math.min(1, a * 2)}}>{g.palabra}</div>
        {g.cursiva && (
          <div style={{display: 'inline-block', marginTop: 10, padding: '2px 22px 10px', backgroundColor: e.panel,
            fontFamily: e.serif, fontStyle: 'italic', fontSize: 80, lineHeight: 1, color: e.texto,
            transform: `scaleX(${b})`, transformOrigin: '50% 50%', boxShadow: '0 12px 36px rgba(0, 0, 0, 0.35)'}}>{g.cursiva}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};

/** Esquinas de portada de revista: las de arriba, en una línea espaciada encima del titular; las de abajo, a los lados del pecho. */
export const Esquinas: React.FC<{textos: string[]; at: number}> = ({textos, at}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const t = interpolate(f, [at + 4, at + 8], [0, 1], CLAMP);
  const sitio: React.CSSProperties[] = [
    {top: 240, left: LADOS.left}, {top: 240, right: LADOS.right, textAlign: 'right'},
    {top: 1150, left: LADOS.left}, {top: 1150, right: LADOS.right, textAlign: 'right'},
  ];
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: t}}>
      {textos.slice(0, 4).map((x, i) => x && (
        <div key={i} style={{position: 'absolute', ...sitio[i], maxWidth: 330, fontFamily: e.sans, fontWeight: 700, fontSize: 30,
          lineHeight: 1.12, letterSpacing: '0.01em', color: '#FFFFFF', whiteSpace: 'pre-line', textShadow: '0 2px 12px rgba(0, 0, 0, 0.5)',
          ...(i < 2 ? {fontSize: 24, letterSpacing: '0.12em', whiteSpace: 'nowrap'} : {})}}>{x}</div>
      ))}
    </AbsoluteFill>
  );
};

/** Barra de prompt arriba: etiqueta pequeña y el texto, que se escribe a ritmo de tecleo, con el botón de enviar. */
export const Prompt: React.FC<{g: G<'prompt'>}> = ({g}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const s = useSalto(g.f);
  const letras = Math.floor(interpolate(f, [g.f + 6, g.f + 6 + g.texto.length * 0.9], [0, g.texto.length], CLAMP));
  const cursor = Math.floor(f / 8) % 2 === 0 && letras < g.texto.length;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', top: 270, ...LADOS, transform: `translateY(${(1 - s) * -30}px)`, opacity: Math.min(1, s * 2)}}>
        <div style={{background: 'rgba(250, 250, 248, 0.97)', borderRadius: 26, padding: '22px 26px 24px 30px', boxShadow: '0 18px 50px rgba(0, 0, 0, 0.35)',
          display: 'flex', alignItems: 'flex-end', gap: 20}}>
          <div style={{flex: 1}}>
            <div style={{fontFamily: e.mono, fontSize: 20, letterSpacing: 3, textTransform: 'uppercase', color: 'rgba(21, 23, 26, 0.45)'}}>{g.etiqueta}</div>
            <div style={{marginTop: 10, fontFamily: e.sans, fontSize: 36, lineHeight: 1.25, color: '#15171A', minHeight: 45}}>
              {g.texto.slice(0, letras)}{cursor && <span style={{color: e.acento}}>|</span>}
            </div>
          </div>
          <div style={{width: 54, height: 54, borderRadius: 27, flexShrink: 0, background: e.acento, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <svg width={22} height={22} viewBox="0 0 20 20"><path d="M10 16V4M4 9l6-6 6 6" stroke="#fff" strokeWidth={2.6} fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Pantalla oscura de editor: la barra con el nombre del archivo y las líneas, que aparecen cuando se nombran. */
export const Terminal: React.FC<{g: G<'terminal'>}> = ({g}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const s = useSalto(g.f);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', top: 260, ...LADOS, transform: `scale(${0.94 + 0.06 * s})`, opacity: Math.min(1, s * 2),
        background: e.fondo, border: `1px solid ${e.filete}`, borderRadius: 18, boxShadow: '0 26px 70px rgba(0, 0, 0, 0.55)', overflow: 'hidden'}}>
        <div style={{height: 52, display: 'flex', alignItems: 'center', gap: 10, padding: '0 22px', borderBottom: `1px solid ${e.filete}`, backgroundColor: e.panel}}>
          {['#ff5f57', '#febc2e', '#28c840'].map((c) => <div key={c} style={{width: 13, height: 13, borderRadius: 7, background: c, opacity: 0.85}} />)}
          <div style={{marginLeft: 14, fontFamily: e.mono, fontSize: 21, color: e.apagado}}>{g.titulo}</div>
        </div>
        <div style={{padding: '26px 30px 30px', display: 'flex', flexDirection: 'column', gap: 16}}>
          {g.lineas.map((l, i) => {
            const t = interpolate(f, [l.f, l.f + 3], [0, 1], CLAMP);
            const encabezado = l.texto.startsWith('#');
            return (
              <div key={i} style={{display: 'flex', gap: 22, opacity: t}}>
                <span style={{fontFamily: e.mono, fontSize: 24, color: e.apagado, width: 28, textAlign: 'right'}}>{i + 1}</span>
                <span style={{fontFamily: encabezado ? e.serif : e.mono, fontSize: encabezado ? 46 : 28, lineHeight: 1.2,
                  color: encabezado ? e.texto : l.texto.startsWith('-') ? e.acento : e.texto}}>{l.texto}</span>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** CTA: el texto arriba, el comentario con la palabra, la respuesta que se va enviando y el botón de seguir. */
export const Cta: React.FC<{g: G<'cta'>}> = ({g}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const titulo = useSalto(g.f);
  const comentario = useSalto(g.f + 8);
  const respuesta = useSalto(g.envio);
  const seguir = useSalto(g.envio + 18);
  const tarjeta: React.CSSProperties = {background: 'rgba(250, 250, 248, 0.97)', borderRadius: 22, boxShadow: '0 16px 44px rgba(0, 0, 0, 0.35)',
    display: 'flex', alignItems: 'center', gap: 18, padding: '18px 24px'};
  const avatar = (c: string) => <div style={{width: 46, height: 46, borderRadius: 23, flexShrink: 0, background: c}} />;
  const puntos = '.'.repeat(1 + (Math.floor(f / 6) % 3));
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', top: 260, ...LADOS, textAlign: 'center', fontFamily: e.sans, fontWeight: 800, fontSize: 54, lineHeight: 1.08,
        letterSpacing: '-0.02em', color: '#FFFFFF', textShadow: '0 4px 20px rgba(0, 0, 0, 0.5)', opacity: Math.min(1, titulo * 2),
        transform: `scale(${0.92 + 0.08 * titulo})`}}>{g.texto}</div>
      <div style={{position: 'absolute', top: 420, ...LADOS, display: 'flex', flexDirection: 'column', gap: 14}}>
        <div style={{...tarjeta, opacity: Math.min(1, comentario * 2), transform: `translateY(${(1 - comentario) * 24}px)`}}>
          {avatar('linear-gradient(135deg, #c9d2e3, #8fa0bf)')}
          <div style={{flex: 1, fontFamily: e.sans, fontWeight: 800, fontSize: 38, color: '#15171A'}}>{g.palabra}</div>
          <svg width={30} height={28} viewBox="0 0 24 22"><path d="M12 21s-9-5.6-9-12a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 6.4-9 12-9 12z" fill="none" stroke="#15171A" strokeWidth={2} /></svg>
        </div>
        <div style={{...tarjeta, opacity: Math.min(1, respuesta * 2), transform: `translateY(${(1 - respuesta) * 24}px)`}}>
          {avatar(e.acento)}
          <div>
            <div style={{fontFamily: e.sans, fontWeight: 700, fontSize: 26, color: '#15171A'}}>{g.cuenta}</div>
            <div style={{fontFamily: e.sans, fontSize: 28, color: 'rgba(21, 23, 26, 0.6)'}}>Enviando{puntos}</div>
          </div>
        </div>
      </div>
      <div style={{position: 'absolute', top: 1120, ...LADOS, display: 'flex', justifyContent: 'center'}}>
      <div style={{...tarjeta, padding: '14px 18px 14px 16px', borderRadius: 40,
        opacity: Math.min(1, seguir * 2), transform: `scale(${0.85 + 0.15 * seguir})`, transformOrigin: '50% 50%'}}>
        {avatar(e.acento)}
        <div style={{fontFamily: e.sans, fontWeight: 700, fontSize: 28, color: '#15171A'}}>{g.cuenta}</div>
        <div style={{marginLeft: 8, padding: '10px 24px', borderRadius: 24, background: ramp(f, g.envio + 40, g.envio + 44) > 0.5 ? 'rgba(21, 23, 26, 0.08)' : e.acento,
          color: ramp(f, g.envio + 40, g.envio + 44) > 0.5 ? '#15171A' : '#fff', fontFamily: e.sans, fontWeight: 700, fontSize: 26}}>
          {ramp(f, g.envio + 40, g.envio + 44) > 0.5 ? 'Siguiendo' : 'Seguir'}
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};
