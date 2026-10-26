/**
 * Props que recibe el motor. Las prepara tools/montar_reel.py a partir del kit del cliente
 * y del montaje del vídeo: aquí todo llega ya en fotogramas locales de cada plano.
 */
export type Kit = {
  cliente: string;
  colores: {fondo: string; fondoLuz: string; panel: string; texto: string; apagado: string; acento: string; filete: string};
  /** Nombre del catálogo (fuentes.ts) o un archivo propio del cliente, servido desde la carpeta pública. */
  fuentes: {titular: Fuente; golpe: Fuente; mono: Fuente; subtitulos?: Fuente};
  /** Preferencias de su identidad visual. «simple»: la frase sin resaltar la palabra que se dice. */
  reglas?: {subtitulos?: 'resaltado' | 'simple' | 'sin'};
};

export type Fuente = string | {url: string};

export type Palabra = {w: string; f: number};

export type Grafico =
  | {tipo: 'titular'; kicker: Palabra[]; palabra: string; f: number}
  | {tipo: 'chat'; etiqueta: string; texto: string; f: number; envio: number}
  | {tipo: 'ficha'; filas: {etiqueta: string; valor: string; cifra?: boolean; sufijo?: string; f: number}[]}
  | {tipo: 'fondo'; f: number; titular?: string}
  /** Icono de línea junto a la cabeza (iconos.tsx), con su palabra si la lleva. */
  | {tipo: 'icono'; f: number; icono: string; texto?: string; lado: 'izquierda' | 'derecha'}
  /** Imagen real (foto o captura). `archivo` está en la carpeta pública «imagenes/». */
  | {tipo: 'imagen'; f: number; archivo: string; pie: string; credito: string; forma: 'tarjeta' | 'pantalla'}
  /** Efecto explicativo tipo After Effects, en una de las tres composiciones del manual. */
  | {
      tipo: 'efecto';
      clase: 'lista' | 'cifra' | 'comparacion' | 'proceso' | 'grafica';
      lugar: 'encima' | 'partida' | 'completa';
      f: number;
      titulo?: string;
      sufijo?: string;
      elementos: {texto: string; valor?: string; f: number}[];
    };

/** Fondo animado de los recortes y las composiciones: luz, rejilla o una foto del cliente. */
export type Fondo = 'luz' | 'rejilla' | {foto: string};

export type PlanoMontado = {
  id: string;
  from: number;
  dur: number;
  srcIn: number;
  modo: 'real' | 'recorte';
  zoom: number;
  y: number;
  /** «revela»: el color de fondo de un recorte se abre (entrada) o se cierra (salida) en vez de cortar. */
  entrada: 'corte' | 'latigo' | 'tiras' | 'revela';
  salida: 'corte' | 'latigo' | 'revela';
  sacudida?: number;
  /** Golpe de zoom (fotograma local): acercamiento rápido en la frase fuerte. */
  golpe?: number;
  /** Fila más alta de la cabeza por fotograma (px de fuente); solo en recortes con titular. */
  cabeza?: number[];
  /** Centro de la cara por fotograma [x, y] (px de fuente); solo en pantallas partidas. */
  cara?: [number, number][];
  fondo?: Fondo;
  /** Composición que impone un efecto que abarca este plano (el efecto va en una capa aparte). */
  composicion?: 'encima' | 'partida' | 'completa';
  palabras: Palabra[];
  subtitulos: boolean;
  grafico?: Grafico;
};

/** Un efecto explicativo pintado por encima de varios planos seguidos: sobrevive a los cortes de debajo. */
export type Superpuesto = {
  from: number; dur: number; grafico: Extract<Grafico, {tipo: 'efecto'}>; fondo?: Fondo;
  /** Lo que hay detrás de un efecto «encima»: claro → texto en el color de fondo del kit; oscuro → el color de texto. */
  tono?: 'claro' | 'oscuro';
};

export type Props = {kit: Kit; planos: PlanoMontado[]; superpuestos?: Superpuesto[]; total: number; fps: number};
