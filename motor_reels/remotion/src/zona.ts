import datos from '../../zona_segura.json';

/** Zona segura del reel: ningún texto fuera (motor_reels/zona_segura.json, la misma que comprueba validar.py). */
export type CajaZona = {x0: number; x1: number; y0: number; y1: number};
export const ZONA: CajaZona = datos.zona;
export const CAJAS = datos.cajas as Record<keyof typeof datos.cajas, CajaZona>;

/** Estilo absoluto que ocupa una caja de la zona segura. */
export const enCaja = (c: CajaZona): React.CSSProperties => ({
  position: 'absolute', left: c.x0, width: c.x1 - c.x0, top: c.y0, height: c.y1 - c.y0,
});
/** Solo los márgenes laterales de la zona segura (para lo que fija su propia altura). */
export const LADOS = {left: ZONA.x0, right: 1080 - ZONA.x1};
