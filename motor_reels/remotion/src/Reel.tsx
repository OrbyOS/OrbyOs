import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {EstiloCtx, crearEstilo} from './estilo';
import {CapaEfecto, Grano, Plano, Tiras} from './piezas';
import type {Props} from './tipos';

/** Fotogramas que un plano sigue vivo debajo del siguiente cuando este entra en tiras. */
const SOLAPE_TIRAS = 10;

export const Reel: React.FC<Props> = ({kit, planos, superpuestos = []}) => {
  const estilo = React.useMemo(() => crearEstilo(kit), [kit]);
  return (
    <EstiloCtx.Provider value={estilo}>
      <AbsoluteFill style={{backgroundColor: estilo.fondo}}>
        {planos.map((p, i) => {
          const siguiente = planos[i + 1];
          const extra = siguiente?.entrada === 'tiras' ? SOLAPE_TIRAS : 0;
          return (
            <Sequence key={p.id} from={p.from} durationInFrames={p.dur + extra}>
              {p.entrada === 'tiras' ? <Tiras id={p.id}><Plano p={p} /></Tiras> : <Plano p={p} />}
            </Sequence>
          );
        })}
        {superpuestos.map((s, i) => (
          <Sequence key={`efecto-${i}`} from={s.from} durationInFrames={s.dur}>
            <CapaEfecto g={s.grafico} fondo={s.fondo} tono={s.tono} />
          </Sequence>
        ))}
        <Grano />
      </AbsoluteFill>
    </EstiloCtx.Provider>
  );
};
