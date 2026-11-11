import datos from '../../zona_segura.json';

/** Zona segura del reel: ningún texto fuera (motor_reels/zona_segura.json, la misma que comprueba validar.py). */
export type CajaZona = {x0: number; x1: number; y0: number; y1: number};
export const ZONA: CajaZona = datos.zona;
export const CAJAS = datos.cajas as Record<keyof typeof datos.cajas, CajaZona>;

/** Estilo absoluto que ocupa una caja de la zona segura. */
export const enCaja = (c: CajaZona): React.CSSProperties => ({
  position: 'absolute', left: c.x0, width: c.x1 - c.x0, top: c.y0, height: c.y1 - c.y0,
});
/**
 * Márgenes laterales de todo lo centrado (subtítulos, titulares, rótulos, tarjetas): simétricos, con el centro en x=540.
 * Con los de la zona segura (60 y 230) el centro caía en 455 y se notaba torcido (28/10/2026). El ancho que
 * queda (800) es el del titular; lo que va pegado a un lado sigue usando ZONA.
 */
export const CENTRO = 540;
export const LADOS = {left: CENTRO - 400, right: 1080 - CENTRO - 400};
