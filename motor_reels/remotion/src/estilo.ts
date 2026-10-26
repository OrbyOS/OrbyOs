import React from 'react';
import {Easing, interpolate} from 'remotion';
import {fuente} from './fuentes';
import type {Kit} from './tipos';

export const W = 1080;
export const H = 1920;

/** Anticipación del manual: todo entra 2 fotogramas antes de la palabra (ya aplicada en el montaje). */
export const CLAMP = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
/** Exponencial de salida: el gesto de un editor de After Effects, rápido y se asienta. */
export const EXPO = Easing.bezier(0.16, 1, 0.3, 1);
export const IN = Easing.bezier(0.7, 0, 0.84, 0);

export const ramp = (f: number, a: number, b: number, ease: (x: number) => number = EXPO) =>
  interpolate(f, [a, b], [0, 1], {...CLAMP, easing: ease});

/** Tokens del kit del cliente, con las fuentes ya cargadas. */
export type Estilo = Kit['colores'] & {serif: string; sans: string; mono: string; subs: string; resaltar: boolean};
export const crearEstilo = (kit: Kit): Estilo => ({
  ...kit.colores,
  serif: fuente(kit.fuentes.titular),
  sans: fuente(kit.fuentes.golpe),
  mono: fuente(kit.fuentes.mono),
  subs: fuente(kit.fuentes.subtitulos ?? kit.fuentes.titular),
  resaltar: kit.reglas?.subtitulos !== 'simple',
});
export const EstiloCtx = React.createContext<Estilo>(null as unknown as Estilo);
export const useEstilo = () => React.useContext(EstiloCtx);

/** Ruido suave y determinista (suma de senos con fases por semilla) para la cámara en mano. */
export const ruido = (t: number, semilla: number) =>
  Math.sin(t * 0.045 + semilla * 1.7) * 0.6 + Math.sin(t * 0.11 + semilla * 3.1) * 0.3 + Math.sin(t * 0.23 + semilla * 5.3) * 0.1;

export const semillaDe = (s: string) => [...s].reduce((a, c) => a + c.charCodeAt(0), 0);
