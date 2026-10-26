import {continueRender, delayRender, staticFile} from 'remotion';
import * as Archivo from '@remotion/google-fonts/Archivo';
import * as DMSerifDisplay from '@remotion/google-fonts/DMSerifDisplay';
import * as Fraunces from '@remotion/google-fonts/Fraunces';
import * as Inter from '@remotion/google-fonts/Inter';
import * as InstrumentSerif from '@remotion/google-fonts/InstrumentSerif';
import * as InterTight from '@remotion/google-fonts/InterTight';
import * as JetBrainsMono from '@remotion/google-fonts/JetBrainsMono';
import * as PlayfairDisplay from '@remotion/google-fonts/PlayfairDisplay';
import type {Fuente} from './tipos';

/**
 * Catálogo cerrado de fuentes para cuando el cliente no ha subido las suyas. Son pocas a propósito:
 * todas funcionan en titular gigante y en subtítulo pequeño.
 */
type Loader = {loadFont: (style?: any, opts?: any) => {fontFamily: string}};
const CATALOGO: Record<string, {mod: Loader; pesos: string[]; cursiva: boolean}> = {
  InstrumentSerif: {mod: InstrumentSerif, pesos: ['400'], cursiva: true},
  PlayfairDisplay: {mod: PlayfairDisplay, pesos: ['400', '700'], cursiva: true},
  Fraunces: {mod: Fraunces, pesos: ['400', '700'], cursiva: true},
  DMSerifDisplay: {mod: DMSerifDisplay, pesos: ['400'], cursiva: true},
  InterTight: {mod: InterTight, pesos: ['600', '700', '800', '900'], cursiva: false},
  Inter: {mod: Inter, pesos: ['600', '700', '800', '900'], cursiva: false},
  Archivo: {mod: Archivo, pesos: ['600', '700', '800', '900'], cursiva: false},
  JetBrainsMono: {mod: JetBrainsMono, pesos: ['400', '500'], cursiva: false},
};

const cargadas: Record<string, string> = {};
const pendientes: Promise<unknown>[] = [];

/** Se resuelve cuando todas las tipografías (propias y del catálogo) están listas para medir texto. */
export const fuentesListas = () => Promise.all(pendientes).then(() => document.fonts.ready);

/** Tipografía propia del cliente (su .ttf/.otf del Kit visual): se carga una vez y el render espera a que esté. */
const propia = (url: string): string => {
  const familia = `kit-${url.replace(/[^a-z0-9]/gi, '-')}`;
  const espera = delayRender(`Cargando ${url}`);
  const cara = new FontFace(familia, `url(${staticFile(url)})`);
  pendientes.push(cara.load().then((f) => {
    document.fonts.add(f);
    continueRender(espera);
  }).catch(() => continueRender(espera))); // si falla, el navegador tira de la siguiente de la pila
  return familia;
};

/** Carga la fuente (una sola vez) y devuelve su font-family, con una de reserva detrás. */
export const fuente = (f: Fuente): string => {
  const clave = typeof f === 'string' ? f : f.url;
  if (cargadas[clave]) return cargadas[clave];
  if (typeof f !== 'string') {
    cargadas[clave] = `"${propia(f.url)}", serif`;
    return cargadas[clave];
  }
  const c = CATALOGO[f];
  if (!c) throw new Error(`Fuente fuera del catálogo: ${f}`);
  const opts = {weights: c.pesos, subsets: ['latin', 'latin-ext']};
  cargadas[clave] = c.mod.loadFont('normal', opts).fontFamily;
  if (c.cursiva) c.mod.loadFont('italic', opts);
  return cargadas[clave];
};
