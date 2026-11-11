import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {ConCara} from './ConCara';
import type {PropsConCara} from './ConCara';
import {Explicativo} from './Explicativo';
import type {Plano, Props} from './tipos';

// Sin props (Studio) se ve un muestrario de todos los planos (2 s cada uno); el render real recibe --props.
const ejemplos: Omit<Plano, 'inicio' | 'fin'>[] = [
  {tipo: 'objetos', objetos: ['lupa', 'libreta', 'claqueta'], textos: ['Ideas', 'Guion', 'Edición']},
  {tipo: 'robot', quien: 'jefa', accion: 'saluda', bocadillo: '¿Qué grabo hoy?'},
  {tipo: 'equipo'},
  {tipo: 'cifra', valor: 12, sufijo: ' h', etiqueta: 'a la semana haciendo contenido'},
  {tipo: 'grafica', modo: 'linea', valores: [3, 4, 3, 6, 9, 14], etiquetas: ['S1', 'S2', 'S3', 'S4', 'S5', 'S6'], titulo: 'Visitas al perfil'},
  {tipo: 'grafica', modo: 'barras', valores: [2, 3, 9], etiquetas: ['Me gusta', 'Comentarios', 'Envíos'], titulo: 'Lo que más pesa'},
  {tipo: 'lista', items: ['Empiezas saludando', 'Tardas en llegar', 'Sin texto en pantalla'], marca: 'cruz'},
  {tipo: 'versus', izq: {titulo: 'Tú solo', robot: 'jefa', items: ['Idea', 'Guion', 'Edición'], nota: '12 h'},
    der: {titulo: 'Con equipo', robot: 'editor', items: ['Grabas', 'Apruebas'], nota: '1 h'}, ganador: 'der'},
  {tipo: 'movil', modo: 'vistas', desde: 280, hasta: 312, sello: 'ATASCADO'},
  {tipo: 'movil', modo: 'mensajes', mensajes: [{nombre: 'Laura', texto: '¿Cuánto cuesta la mentoría?'}, {nombre: 'Javi', texto: 'Me interesa, ¿hablamos?'}, {nombre: 'Marta', texto: '¿Tienes plazas este mes?'}]},
  {tipo: 'chat', mensajes: [{de: 'ellos', texto: 'Hola, ¿cuánto cuesta?', hora: 'Viernes 22:41'}, {de: 'tu', texto: '¡Hola! Te cuento', hora: 'Lunes 10:15'}]},
  {tipo: 'palabra', texto: 'NO.', sub: 'Publicar más no vende más'},
  {tipo: 'frase', texto: 'En el mundo actual, la clave del éxito es…', tachar: true},
  {tipo: 'reloj', vueltas: 4, texto: '2 h 40 min'},
  {tipo: 'calendario', marcados: [0, 2, 4], notas: ['Graba', '', 'Revisa', '', 'Publica'], dias: ['L', 'M', 'X', 'J', 'V', 'S', 'D', '+']},
  {tipo: 'flujo', pasos: [{quien: 'analista', texto: 'Encuentra lo que funciona'}, {quien: 'estratega', texto: 'Decide qué grabas'},
    {quien: 'guionista', texto: 'Escribe el guion'}, {quien: 'editor', texto: 'Edita el vídeo'}, {quien: 'publicador', texto: 'Lo publica'}]},
  {tipo: 'cierre', palabra: 'EQUIPO', web: 'orbyos.es'},
];
const planos: Plano[] = ejemplos.map((e, i) => ({...e, inicio: i * 2.4, fin: (i + 1) * 2.4} as Plano));

const muestra: Props = {
  fps: 30,
  total: Math.round(planos.length * 2.4 * 30),
  audio: '',
  titulo: {texto: 'Tres tareas que te comen la semana', resalte: 'te comen la semana', insignia: '3 tareas', fin: 2.4},
  planos,
  rotulos: [{inicio: 4.8, fin: 9.6, texto: '1 · El equipo'}],
  palabras: [{texto: 'Tres', t: 0.2, fin: 0.5}, {texto: 'tareas', t: 0.5, fin: 0.9, enfasis: true}, {texto: 'que', t: 0.9, fin: 1.1}],
  estilo: {mesa: '#12275c', veta: 'rgba(120, 160, 255, 0.07)', acento: '#3D7BFF', texto: '#ffffff', subrayado: '#9cc4ff',
    caja: 'rgba(5, 10, 28, 0.85)', malo: '#ff5d73'},
};

const vacioConCara: PropsConCara = {fps: 30, total: 30, cara: {archivo: '', tramos: []}, capas: [], rotulos: [], palabras: [], sonidos: [],
  estilo: muestra.estilo};

const Root: React.FC = () => React.createElement(React.Fragment, null,
  React.createElement(Composition, {
    id: 'ConCara',
    component: ConCara as React.FC<any>,
    durationInFrames: 30,
    fps: 30,
    width: 1080,
    height: 1920,
    defaultProps: vacioConCara,
    calculateMetadata: ({props}: {props: Record<string, unknown>}) => {
      const p = props as unknown as PropsConCara;
      return {durationInFrames: Math.max(1, p.total), fps: p.fps};
    },
  }),
  React.createElement(Composition, {
    id: 'Explicativo',
    component: Explicativo as React.FC<any>,
    durationInFrames: muestra.total,
    fps: 30,
    width: 1080,
    height: 1920,
    defaultProps: muestra,
    calculateMetadata: ({props}: {props: Record<string, unknown>}) => {
      const p = props as unknown as Props;
      return {durationInFrames: Math.max(1, p.total), fps: p.fps};
    },
  }));

registerRoot(Root);
