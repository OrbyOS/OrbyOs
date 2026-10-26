import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Explicativo} from './Explicativo';
import type {Props} from './tipos';

// Sin props (Studio) se ve una escena de muestra; el render real recibe --props desde generacion.py.
const muestra: Props = {
  fps: 30,
  total: 90,
  audio: '',
  titulo: {texto: 'Tres tareas que te comen la semana', resalte: 'te comen la semana', insignia: '3 tareas'},
  escenas: [{inicio: 0, fin: 3, objetos: ['lupa', 'libreta', 'claqueta']}],
  palabras: [],
  estilo: {mesa: '#12275c', veta: 'rgba(120, 160, 255, 0.07)', acento: '#3D7BFF', texto: '#ffffff', subrayado: '#9cc4ff', caja: 'rgba(5, 10, 28, 0.85)'},
};

const Root: React.FC = () =>
  React.createElement(Composition, {
    id: 'Explicativo',
    component: Explicativo as React.FC<any>,
    durationInFrames: 90,
    fps: 30,
    width: 1080,
    height: 1920,
    defaultProps: muestra,
    calculateMetadata: ({props}: {props: Record<string, unknown>}) => {
      const p = props as unknown as Props;
      return {durationInFrames: Math.max(1, p.total), fps: p.fps};
    },
  });

registerRoot(Root);
