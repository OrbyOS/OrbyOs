import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {H, W} from './estilo';
import {Reel} from './Reel';
import type {Props} from './tipos';

// Sin props (Studio) se ve un reel vacío del kit por defecto; el render real recibe --props.
const vacio: Props = {
  kit: {
    cliente: 'demo',
    colores: {fondo: '#15171A', fondoLuz: '#23272C', panel: '#1C1F23', texto: '#F5F5F2',
      apagado: 'rgba(245, 245, 242, 0.42)', acento: '#9DB8D9', filete: 'rgba(245, 245, 242, 0.22)'},
    fuentes: {titular: 'InterTight', golpe: 'InterTight', mono: 'JetBrainsMono'},
  },
  planos: [],
  total: 30,
  fps: 30,
};

const Root: React.FC = () =>
  React.createElement(Composition, {
    id: 'Reel',
    component: Reel as React.FC<any>,
    durationInFrames: 30,
    fps: 30,
    width: W,
    height: H,
    defaultProps: vacio,
    calculateMetadata: ({props}: {props: Record<string, unknown>}) => {
      const p = props as unknown as Props;
      return {durationInFrames: Math.max(1, p.total), fps: p.fps};
    },
  });

registerRoot(Root);
