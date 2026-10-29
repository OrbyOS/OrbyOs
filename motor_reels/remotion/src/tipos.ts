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
  /**
   * Estilo de edición del cliente (opcional; sin él, el de siempre). «subtitulos» limpio: blancos, pequeños, sin caja.
   * «lienzo»: color de la mitad de arriba en pantalla partida (p. ej. blanco) en vez del vídeo desenfocado, con los
   * efectos en tinta oscura y la fila activa en «lienzoAcento». «sello»: el de su serie (texto grande + cinta).
   */
  estilo?: {subtitulos?: 'caja' | 'limpio' | 'abajo'; lienzo?: string; lienzoAcento?: string;
    promesa?: 'simple' | 'pastilla';
            sello?: {texto: string; cinta?: string};
            /** Subtítulos limpios: cómo entran, su tipografía (catálogo) y cómo se marca la palabra clave. */
            subsAnim?: 'aparecen' | 'palabra' | 'karaoke' | 'salto'; subsFuente?: string;
            subsResalte?: 'color' | 'subrayado' | 'negrita' | 'nada';
            /** Cómo entra la captura en la pantalla partida o flotante. */
            entradaPantalla?: 'deslizar' | 'escalar' | 'aparecer';
            /** Look de imagen (por defecto natural: sin etalonaje) y barra de progreso fina abajo. */
            look?: 'natural' | 'calido' | 'frio' | 'contraste'; progreso?: boolean;
            /** Vista previa del estudio (Montaje): sin grano, desenfoques ligeros y sin sombras grandes. Nunca en el render. */
            vista?: boolean};
};

export type Fuente = string | {url: string};

export type Palabra = {w: string; f: number};

export type Grafico =
  /** `entero`: delante de la persona y más arriba (la cabeza no lo tapa), en vez de detrás de la cabeza. */
  | {tipo: 'titular'; kicker: Palabra[]; palabra: string; f: number; entero?: boolean;
      /** `sans`: la palabra en la sans del kit, gruesa y en mayúsculas (el gancho sobre color). `esquinas`: textos pequeños
       * en las cuatro esquinas (arriba izq., arriba der., abajo izq., abajo der.): portada de revista. */
      sans?: boolean; esquinas?: string[];
      /** Encima de la cabeza (delante y con la persona debajo), en vez de detrás: con kit estilo.ganchoEncima. */
      encima?: boolean;
      /** Segunda línea en cursiva serif sobre una pastilla del acento («TU IA» / «escribe fatal.»): el gancho que engancha. */
      cursiva?: string}
  /** Rótulo: una palabra en sans gruesa y, debajo, el resto en cursiva serif sobre el color del panel («BIGGER captions.»). */
  | {tipo: 'rotulo'; f: number; palabra: string; cursiva: string}
  /** Barra de prompt arriba: su etiqueta y el texto, que se escribe. */
  | {tipo: 'prompt'; f: number; etiqueta: string; texto: string}
  /** Pantalla oscura de terminal o editor: el nombre del archivo y sus líneas, cada una en su momento. */
  | {tipo: 'terminal'; f: number; titulo: string; lineas: {texto: string; f: number}[]}
  /** CTA: el texto arriba, el comentario con la palabra, la respuesta que se envía y el botón de seguir. */
  | {tipo: 'cta'; f: number; texto: string; palabra: string; cuenta: string; envio: number}
  | {tipo: 'chat'; etiqueta: string; texto: string; f: number; envio: number}
  | {tipo: 'ficha'; filas: {etiqueta: string; valor: string; cifra?: boolean; sufijo?: string; f: number}[]}
  | {tipo: 'fondo'; f: number; titular?: string}
  /** Icono de línea junto a la cabeza (iconos.tsx), con su palabra si la lleva. */
  | {tipo: 'icono'; f: number; icono: string; texto?: string; lado: 'izquierda' | 'derecha'}
  /** Imagen real (foto o captura). `archivo` está en la carpeta pública «imagenes/». */
  | {tipo: 'imagen'; f: number; archivo: string; pie: string; credito: string; forma: 'tarjeta' | 'pantalla' | 'flotante'}
  /** Logos de las apps que nombra (carpeta pública «logos/»), que saltan alrededor de la cabeza uno tras otro. */
  | {tipo: 'logos'; f: number; logos: string[]; /** Tachados con una línea roja (lo que ya no hace falta). */ tachar?: boolean}
  /** Sello de la serie: texto grande y una cinta en cursiva, cuando presenta la sección. */
  | {tipo: 'sello'; f: number; texto: string; cinta?: string}
  /** Efecto explicativo tipo After Effects, en una de las tres composiciones del manual. */
  | {
      tipo: 'efecto';
      clase: 'lista' | 'cifra' | 'comparacion' | 'proceso' | 'grafica'
        /** Interfaz sobre el lienzo (solo en «partida»); `valor` de cada elemento: su imagen, o «nota» en los pasos. */
        | 'logos' | 'miniaturas' | 'pasos' | 'pildora' | 'abanico' | 'perfiles' | 'carpeta';
      lugar: 'encima' | 'partida' | 'completa';
      f: number;
      titulo?: string;
      sufijo?: string;
      elementos: {texto: string; valor?: string; f: number}[];
    };

/** Fondo animado de los recortes y las composiciones: luz, rejilla o una foto del cliente. */
/** `mosaico`: capturas reales a pantalla completa por detrás de la persona (archivos de «imagenes/»). */
export type Fondo = 'luz' | 'rejilla' | 'solido' | {foto: string} | {mosaico: string[]};

export type PlanoMontado = {
  id: string;
  from: number;
  dur: number;
  srcIn: number;
  modo: 'real' | 'recorte';
  zoom: number;
  y: number;
  /** «revela»: el color de fondo de un recorte se abre (entrada) o se cierra (salida) en vez de cortar. */
  entrada: 'corte' | 'latigo' | 'tiras' | 'revela' | 'desliza' | 'destello';
  salida: 'corte' | 'latigo' | 'revela';
  sacudida?: number;
  /** Golpe de zoom (fotograma local): acercamiento rápido en la frase fuerte. */
  golpe?: number;
  /** Texto del gancho encima del plano (el primero): titular arriba, con subrayado que se dibuja o palabra a palabra. */
  textoGancho?: {texto: string; modo: 'titular' | 'subrayado' | 'palabra'};
  /** Fuerza del golpe de zoom (1 = el de siempre). */
  golpeFuerza?: number;
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
