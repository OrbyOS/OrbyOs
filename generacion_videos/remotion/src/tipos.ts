/** Lo que manda radar/agentes/generacion.py (tiempos en segundos). */
export type Palabra = {texto: string; t: number; fin: number};

export type Escena = {
  inicio: number;
  fin: number;
  /** Etiqueta de arriba («1 · BUSCAR IDEAS»). La primera escena lleva el título del vídeo en su lugar. */
  etiqueta?: string;
  /** Cinta que aparece a mitad de escena con el remate («La que más cuesta»). */
  cinta?: string;
  /** Ilustraciones del catálogo (ilustraciones.tsx), de izquierda a derecha. */
  objetos: string[];
};

export type Estilo = {
  mesa: string;       // color de la superficie del fondo
  veta: string;       // vetas de la superficie
  acento: string;     // palabra resaltada, insignias y cintas
  texto: string;
  subrayado: string;  // la palabra que suena en los subtítulos
  caja: string;       // caja del título
};

export type Props = {
  fps: number;
  total: number; // fotogramas
  audio: string; // archivo en la carpeta pública del render
  titulo: {texto: string; resalte: string; insignia?: string};
  escenas: Escena[];
  palabras: Palabra[];
  estilo: Estilo;
};
