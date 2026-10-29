/** Lo que manda radar/agentes/generacion.py (tiempos en segundos). */
export type Palabra = {texto: string; t: number; fin: number; enfasis?: boolean};

/** Un plano: lo que se ve mientras suena un trozo de la voz. Cada tipo lee sus propios campos (planos.tsx). */
export type Plano = {
  inicio: number;
  fin: number;
  tipo: string;
  [campo: string]: unknown;
};

export type Rotulo = {inicio: number; fin: number; texto: string};

export type Estilo = {
  mesa: string;       // fondo
  veta: string;       // rejilla del fondo
  acento: string;     // insignias, cintas y lo que se marca
  texto: string;
  subrayado: string;  // la palabra que suena en los subtítulos y el resalte del título
  caja: string;       // caja del título
  malo: string;       // cruces, sellos y lo que está mal
  titular?: string;   // tipografía de titular del catálogo por nombre (InstrumentSerif…), si el Kit no sube la suya
  fuente?: string;    // archivo de la tipografía de la marca en la carpeta pública (del Kit); sin él, Inter Tight
  logo?: string;      // archivo del logo de la marca (del Kit), para el cierre
  // "cazzap": fondo oscuro uniforme, subtítulo arriba con la palabra clave seleccionada como en un editor y cifras sin
  // aro con su fuente debajo (referencia @cazzap.app). "viral": tomas reales a pantalla completa y rótulo en mayúsculas en
  // el centro (viral.tsx). Sin él, el diseño de siempre.
  diseno?: string;
};

export type Props = {
  fps: number;
  total: number; // fotogramas
  audio: string; // archivo en la carpeta pública del render
  titulo: {texto: string; resalte: string; insignia?: string; fin: number};
  planos: Plano[];
  rotulos: Rotulo[]; // la etiqueta de arriba de cada bloque («1 · Tiempo de visionado»)
  palabras: Palabra[];
  estilo: Estilo;
};
