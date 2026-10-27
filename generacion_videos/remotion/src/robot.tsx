import React from 'react';
import {Img, staticFile} from 'remotion';

/**
 * Los muñecos del equipo de Orby: los mismos renders 3D de la app (radar/static/marca/agentes, que generacion.py
 * copia a la carpeta pública del render). Como son imágenes, se animan enteros: flotar, saludar, pensar, celebrar,
 * y el parpadeo cambia un instante a la versión con los ojos cerrados.
 */
export const NOMBRES: Record<string, {nombre: string; rol: string}> = {
  jefa: {nombre: 'Orby', rol: 'Dirige'},
  analista: {nombre: 'Lupi', rol: 'Investiga'},
  estratega: {nombre: 'Plani', rol: 'Planifica'},
  guionista: {nombre: 'Escri', rol: 'Escribe'},
  editor: {nombre: 'Monti', rol: 'Edita'},
  publicador: {nombre: 'Publi', rol: 'Publica'},
  comunidad: {nombre: 'Chati', rol: 'Responde'},
};
const COLORES: Record<string, string> = {
  jefa: '#3D7BFF', analista: '#22D3EE', estratega: '#FBBF24', guionista: '#F472B6', editor: '#34D399', publicador: '#A78BFA',
  comunidad: '#FB7185',
};
export const colorDe = (clave: string) => COLORES[clave] ?? COLORES.jefa;

export const Robot: React.FC<{clave: string; f: number; tam: number; accion?: string; semilla?: number}> = ({
  clave, f, tam, accion = 'quieto', semilla = 0,
}) => {
  const k = COLORES[clave] ? clave : 'jefa';
  const ciclo = (f + semilla * 37) % 90;
  const dormido = accion === 'duerme' || ciclo >= 86; // parpadeo: 4 fotogramas con los ojos cerrados
  const flota = Math.sin((f + semilla * 20) / 11) * tam * 0.018;
  let giro = Math.sin((f + semilla * 13) / 23) * 1.5, salto = 0, estira = 1;
  if (accion === 'saluda') giro = Math.sin(f / 4) * 7;
  if (accion === 'piensa') giro = -7 + Math.sin(f / 10) * 2;
  if (accion === 'trabaja') { salto = Math.abs(Math.sin(f / 3.2)) * tam * 0.03; giro = Math.sin(f / 3.2) * 3; }
  if (accion === 'celebra') { salto = Math.abs(Math.sin(f / 4.5)) * tam * 0.12; estira = 1 + Math.sin(f / 4.5 * 2) * 0.04; }
  const img = (sufijo: string, visible: boolean) => (
    <Img src={staticFile(`agentes/${k}${sufijo}.webp`)} style={{position: 'absolute', left: '-17%', top: '-17%', width: '134%', height: '134%',
      objectFit: 'contain', opacity: visible ? 1 : 0}} />
  );
  return (
    <div style={{width: tam, height: tam * 1.2, position: 'relative',
      transform: `translateY(${flota - salto}px) rotate(${giro}deg) scale(${2 - estira}, ${estira})`, transformOrigin: '50% 90%',
      filter: `drop-shadow(0 ${tam * 0.06}px ${tam * 0.05}px rgba(0,0,0,0.45)) drop-shadow(0 0 ${tam * 0.08}px ${colorDe(k)}55)`}}>
      {img('', !dormido)}
      {img('-dormido', dormido)}
    </div>
  );
};
