import React from 'react';
import {AbsoluteFill, Img, continueRender, delayRender, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {EfectoEnCaja} from './efectos';
import {PIEZAS_INTERFAZ, esInterfaz} from './interfaz';
import {Cta, Esquinas, Prompt, Rotulo, Terminal} from './rotulos';
import {Icono} from './iconos';
import {FondoAnimado} from './fondos';
import {fuentesListas} from './fuentes';
import {CLAMP, EXPO, EstiloCtx, IN, ramp, ruido, semillaDe, useEstilo} from './estilo';
import type {Estilo} from './estilo';
import {CAJAS, LADOS, ZONA, enCaja} from './zona';
import type {Grafico, Palabra, PlanoMontado} from './tipos';

const pad = (n: number) => String(Math.max(0, n)).padStart(5, '0');
const fotograma = (i: number) => staticFile(`frames/f_${pad(i)}.jpg`);
const mascara = (i: number) => staticFile(`frames/m_${pad(i)}.png`);

// ---------------------------------------------------------------------------
// Cámara: encuadre del montaje + cámara en mano + látigos + sacudida.
// ---------------------------------------------------------------------------

const camara = (p: PlanoMontado, f: number, titular?: {size: number; top: number; encima?: boolean; extra?: number}) => {
  const s = semillaDe(p.id);
  let zoom = p.zoom * 1.02; // margen para que la deriva no enseñe bordes
  let blur = 0;
  let x = ruido(f, s) * 4;
  let base = p.y;
  if (p.cabeza && titular) {
    const {size, top} = titular;
    // Detrás de la cabeza, la coronilla tapa la base de la palabra (72 %); encima, la cabeza queda justo debajo.
    const objetivo = top + size * (titular.encima ? 1.1 : 0.72) + (titular.encima ? titular.extra ?? 0 : 0);
    const cabeza = p.cabeza[Math.min(f, p.cabeza.length - 1)];
    // Origen de la escala en el 30 % de la altura (576 px). Si para subir la cabeza hasta el titular el borde de abajo
    // quedaría al aire, se acerca la imagen lo justo: así la base sigue cubierta (576 + 1344·zoom + y ≥ 1920).
    zoom = Math.max(zoom, (1920 - objetivo) / Math.max(1, 1920 - cabeza));
    // Sobre vídeo real, bajar la cabeza hasta el titular pide acercar (objetivo ≤ cabeza·zoom), hasta 1,35 como mucho:
    // con la zona segura el titular va más abajo y, sin esto, la cabeza tapaba el centro de la palabra.
    if (p.modo === 'real') zoom = Math.max(zoom, Math.min(1.35, objetivo / Math.max(1, cabeza)));
    base = objetivo - 576 - (cabeza - 576) * zoom;
    // Sobre vídeo real no se puede bajar la imagen: dejaría un hueco arriba (borde superior: 576 − 576·zoom + y ≤ 0).
    if (p.modo === 'real') base = Math.min(base, 576 * zoom - 576);
  }
  if (p.composicion === 'encima') {
    zoom = Math.min(zoom, 1.04);
  }
  if (p.grafico?.tipo === 'imagen' && p.grafico.forma !== 'pantalla') {
    // Tarjeta a la altura del pecho: el plano no se cierra tanto que la barbilla llegue a la tarjeta.
    zoom = Math.min(zoom, 1.06);
  }
  if (p.grafico?.tipo === 'imagen' && p.grafico.forma === 'pantalla') {
    // Pantalla partida: arriba la imagen; la persona baja hasta que su cara queda en la mitad de abajo.
    const entra = ramp(f, p.grafico.f, p.grafico.f + 10);
    base += entra * 760;
  }
  let y = base + ruido(f, s + 9) * 4;
  const rot = ruido(f, s + 17) * 0.15;
  if (p.entrada === 'latigo') {
    const t = ramp(f, 0, 6);
    zoom *= 1.45 - t * 0.45;
    blur = Math.max(blur, (1 - t) * 24);
  }
  if (p.salida === 'latigo') {
    const t = interpolate(f, [p.dur - 6, p.dur - 1], [0, 1], {...CLAMP, easing: IN});
    zoom *= 1 + t * 0.45;
    blur = Math.max(blur, Math.sqrt(t) * 24);
  }
  if (p.golpe !== undefined && f >= p.golpe) {
    // Golpe de zoom: se acerca en 3 fotogramas y se asienta un poco hacia atrás, como un punch-in hecho a mano.
    const k = f - p.golpe;
    const fuerza = p.golpeFuerza ?? 1;
    zoom *= 1 + 0.11 * fuerza * ramp(k, 0, 3) - 0.025 * fuerza * ramp(k, 3, 9);
  }
  if (p.sacudida !== undefined && f >= p.sacudida) {
    const k = (f - p.sacudida) / 9;
    const amp = k < 1 ? 22 * (1 - k) ** 2 : 0;
    x += Math.sin((f - p.sacudida) * 2.9) * amp;
    y += Math.cos((f - p.sacudida) * 3.7) * amp * 0.7;
  }
  return {
    transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${zoom})`,
    transformOrigin: '50% 30%',
    filter: blur > 0.3 ? `blur(${blur}px)` : undefined,
  } as React.CSSProperties;
};

/**
 * Pantalla partida: la persona se reencuadra para que su cara quede en el centro de la mitad de abajo (no se baja el
 * vídeo entero). Escala mínima para que la imagen cubra toda esa mitad aunque la cara no esté centrada en el bruto.
 */
const camaraPartida = (p: PlanoMontado, f: number): React.CSSProperties => {
  const [cx, cy] = p.cara?.[Math.min(f, (p.cara?.length ?? 1) - 1)] ?? [540, 700];
  const destino = [540, 1440];
  let z = Math.max(p.zoom * 1.02, 1.0);
  // Que cubra a lo ancho: x' = cx·z + tx ≤ 0 en la izquierda y ≥ 1080 en la derecha.
  z = Math.max(z, destino[0] / Math.max(1, cx), (1080 - destino[0]) / Math.max(1, 1080 - cx));
  // Que cubra de 960 a 1920: arriba y' ≤ 960 y abajo y' + 1920·z ≥ 1920.
  z = Math.max(z, (destino[1] - 960) / Math.max(1, cy), (1920 - destino[1]) / Math.max(1, 1920 - cy));
  const s = semillaDe(p.id);
  const tx = destino[0] - cx * z + ruido(f, s) * 4;
  const ty = destino[1] - cy * z + ruido(f, s + 9) * 4;
  return {transform: `translate(${tx}px, ${ty}px) scale(${z})`, transformOrigin: '0 0', clipPath: undefined};
};

/**
 * La silueta va como imagen de máscara en CSS, y Remotion no espera a esas imágenes: algún fotograma salía sin persona
 * (un parpadeo). El render espera a que la máscara esté cargada y descodificada.
 */
const useMascaraLista = (url: string, activo: boolean) => {
  React.useLayoutEffect(() => {
    if (!activo) return;
    const espera = delayRender(`Máscara ${url}`);
    const img = new Image();
    img.src = url;
    img.decode().then(() => continueRender(espera), () => continueRender(espera));
  }, [url, activo]);
};

/**
 * Transición del color de fondo: al entrar, el fondo se abre desde detrás de la cabeza y se come la habitación; al salir,
 * se cierra hacia la cabeza y la descubre. 10 fotogramas, con borde difuso: nunca un corte seco entre fondo y vídeo.
 */
const REVELA = 10;
const mascaraRevela = (p: PlanoMontado, f: number): React.CSSProperties | undefined => {
  let cubre = 1;
  if (p.entrada === 'revela') cubre = Math.min(cubre, ramp(f, 0, REVELA, (x) => x * x));
  if (p.salida === 'revela') cubre = Math.min(cubre, 1 - ramp(f, p.dur - REVELA, p.dur - 1, (x) => x * x));
  if (cubre >= 1) return undefined;
  const r = cubre * 2400;
  const m = `radial-gradient(circle at 50% 30%, #000 ${r}px, transparent ${r + 280}px)`;
  return {WebkitMaskImage: m, maskImage: m};
};

/** Fondo de las composiciones partida y completa: tu propio vídeo, ampliado, desenfocado y oscurecido. */
const VideoDesenfocado: React.FC<{src: number; alto?: number}> = ({src, alto = 1920}) => {
  const e = useEstilo();
  return (
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: alto, overflow: 'hidden'}}>
      <Img src={fotograma(src)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(1.5)',
                                        filter: e.vista ? 'blur(10px) saturate(0.85)' : 'blur(28px) saturate(0.85)'}} />
      <AbsoluteFill style={{backgroundColor: e.fondo, opacity: 0.62}} />
    </div>
  );
};

/**
 * Un plano: fondo (vídeo o color del kit), titular detrás, persona recortada con sombra, y delante
 * tarjetas y subtítulos. Los gráficos no se animan al salir: se van con el corte.
 */
export const Plano: React.FC<{p: PlanoMontado}> = ({p}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const src = p.srcIn + f;
  const g = p.grafico;
  const tamano = useTamanoTitular(g?.tipo === 'titular' ? g : undefined, p.modo === 'real');
  // Con una captura arriba, la pantalla se parte cuando entra la captura (nunca un lienzo vacío esperando).
  const partida = p.composicion === 'partida' && !(g?.tipo === 'imagen' && f < g.f);
  const entero = g?.tipo === 'titular' && g.entero;
  // Encima: la palabra delante y la persona bajada hasta quedar justo debajo (el gancho del cliente cero).
  const encima = g?.tipo === 'titular' && !entero && Boolean(g.encima);
  const cam = partida ? camaraPartida(p, f) : camara(p, f, g?.tipo === 'titular' && !entero ? {...tamano, encima, extra: g.cursiva ? CURSIVA_GANCHO * 1.3 + 14 : 0} : undefined);
  if (p.composicion === 'completa') {
    // A pantalla completa la cara se va, pero el fondo sigue siendo su vídeo (desenfocado): nada de diapositiva.
    return <AbsoluteFill style={{backgroundColor: e.fondo}}><VideoDesenfocado src={src} /></AbsoluteFill>;
  }
  const quitar = g?.tipo === 'fondo' ? ramp(f, g.f + 3, g.f + 13, (x) => x * x) : 0;
  const titular = g?.tipo === 'titular' ? g : g?.tipo === 'fondo' && g.titular && quitar >= 1 ? g : undefined;
  const conPersona = p.modo === 'recorte' || quitar > 0 || (g?.tipo === 'titular' && !entero);
  useMascaraLista(mascara(src), conPersona);
  const mask = {
    WebkitMaskImage: `url(${mascara(src)})`, WebkitMaskSize: '100% 100%',
    maskImage: `url(${mascara(src)})`, maskSize: '100% 100%',
  } as React.CSSProperties;
  const r = quitar * 2600;
  const borrado = `radial-gradient(circle at 50% 26%, #000 ${r}px, transparent ${r + 260}px)`;
  return (
    <AbsoluteFill style={{backgroundColor: e.fondo, overflow: 'hidden'}}>
      {partida && (e.lienzo
        ? <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 960, backgroundColor: e.lienzo}} />
        : <VideoDesenfocado src={src} alto={960} />)}
      {p.modo === 'real' && (
        // El recorte de la mitad de abajo va en un contenedor sin transformar: si fuera en la capa con el encuadre,
        // se aplicaría antes de mover la imagen y cortaría la zona equivocada.
        <AbsoluteFill style={partida ? {clipPath: 'inset(960px 0 0 0)'} : undefined}>
          <AbsoluteFill style={cam}>
            <Img src={fotograma(src)} style={{width: '100%', height: '100%'}} />
          </AbsoluteFill>
        </AbsoluteFill>
      )}
      {p.modo === 'recorte' && (p.entrada === 'revela' || p.salida === 'revela') && (
        // Debajo del fondo está la habitación: así la transición la descubre en vez de cortar.
        <AbsoluteFill style={cam}><Img src={fotograma(src)} style={{width: '100%', height: '100%'}} /></AbsoluteFill>
      )}
      {(p.modo === 'recorte' || quitar > 0) && (
        <FondoAnimado fondo={p.fondo} style={p.modo === 'recorte' ? mascaraRevela(p, f) : {WebkitMaskImage: borrado, maskImage: borrado}} />
      )}
      {titular && !entero && !encima && (
        <Titular
          g={titular.tipo === 'titular' ? titular : {tipo: 'titular', kicker: [], palabra: titular.titular!, f: titular.f + 13}}
          sobreVideo={p.modo === 'real' && quitar < 1}
          tamano={titular.tipo === 'titular' ? tamano : undefined}
        />
      )}
      {conPersona && (
        // La sombra va en el padre: si fuera en la capa con máscara, la máscara la recortaría.
        <AbsoluteFill style={{filter: !e.vista && (p.modo === 'recorte' || quitar > 0.5) ? 'drop-shadow(0 34px 50px rgba(0, 0, 0, 0.42))' : undefined}}>
          <AbsoluteFill style={{...cam, ...mask}}>
            <Img src={fotograma(src)} style={{width: '100%', height: '100%'}} />
          </AbsoluteFill>
        </AbsoluteFill>
      )}
      {/* Titular entero: delante de la persona, más arriba y algo más pequeño (la cabeza no tapa nada de la palabra). */}
      {entero && g?.tipo === 'titular' && <Titular g={g} sobreVideo={false} entero tamano={tamano} />}
      {encima && g?.tipo === 'titular' && <Titular g={g} sobreVideo={p.modo === 'real'} tamano={tamano} />}
      {g?.tipo === 'icono' && <IconoAlLado g={g} />}
      {g?.tipo === 'chat' && <Chat g={g} />}
      {g?.tipo === 'imagen' && <Imagen g={g} />}
      {g?.tipo === 'logos' && <Logos g={g} />}
      {g?.tipo === 'titular' && g.esquinas && <Esquinas textos={g.esquinas} at={g.f} />}
      {g?.tipo === 'rotulo' && <Rotulo g={g} />}
      {g?.tipo === 'prompt' && <Prompt g={g} />}
      {g?.tipo === 'terminal' && <Terminal g={g} />}
      {g?.tipo === 'cta' && <Cta g={g} />}
      {p.textoGancho && <TextoGancho t={p.textoGancho} abajo={partida} />}
      {g?.tipo === 'sello' && <Sello g={g} />}
      {g?.tipo === 'ficha' && <Ficha g={g} />}
      {p.subtitulos && <Subtitulos palabras={p.palabras} hasta={g?.tipo === 'fondo' ? g.f + 3 : Infinity} />}
    </AbsoluteFill>
  );
};

/** La capa de un efecto que abarca varios planos (sobrevive a los cortes de debajo). */
export const CapaEfecto: React.FC<{g: Extract<Grafico, {tipo: 'efecto'}>; fondo?: PlanoMontado['fondo']; tono?: 'claro' | 'oscuro'}> = ({g, tono}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const t = ramp(f, 0, 6);
  if (g.lugar === 'encima') return <Encima g={g} tono={tono} />;
  if (g.lugar === 'partida') {
    // Arriba, el efecto sobre el vídeo desenfocado (lo pinta el plano); la junta, un filete de acento.
    return (
      <EstiloCtx.Provider value={e.lienzo && esClaro(e.lienzo) ? enLienzo(e) : e}>
        <AbsoluteFill style={{pointerEvents: 'none'}}>
          <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 960, opacity: t}}>
            {esInterfaz(g.clase)
              ? React.createElement(PIEZAS_INTERFAZ[g.clase], {g})
              : <EfectoEnCaja g={g} caja={CAJAS.efecto_partida} escala={1.3} />}
          </div>
          {!e.lienzo && <div style={{position: 'absolute', top: 958, left: 0, right: 0, height: 2, backgroundColor: e.acento, opacity: 0.8 * t}} />}
        </AbsoluteFill>
      </EstiloCtx.Provider>
    );
  }
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: t}}>
      <EfectoEnCaja g={g} caja={CAJAS.efecto_completa} escala={1.55} />
    </AbsoluteFill>
  );
};

/**
 * Efecto encima: la cara entera y el efecto a la altura del pecho. Detrás, un velo difuso en el color de fondo del kit (cristal
 * desenfocado que se funde por los bordes, sin caja): sobre una camisa clara o con las manos moviéndose, el texto en
 * claro se sigue leyendo. Sin velo, el texto se pierde entre las manos.
 */
const Encima: React.FC<{g: Extract<Grafico, {tipo: 'efecto'}>; tono?: 'claro' | 'oscuro'}> = ({tono, g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const borde = 'radial-gradient(ellipse 64% 44% at 50% 50%, #000 38%, transparent 100%)';
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', left: -80, right: -80, top: 980, height: 480, opacity: ramp(f, 0, 5),
                   backgroundColor: `${e.fondo}${tono === 'claro' ? 'D0' : 'B0'}`, backdropFilter: e.vista ? undefined : 'blur(22px)',
                   WebkitMaskImage: borde, maskImage: borde}} />
      <AbsoluteFill style={{filter: 'drop-shadow(0 3px 14px rgba(0, 0, 0, 0.55))'}}>
        <EfectoEnCaja g={g} caja={CAJAS.efecto_encima} escala={1.0} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** Icono de línea junto a la cabeza (izquierda o derecha), con su palabra debajo si la lleva. */
const IconoAlLado: React.FC<{g: Extract<Grafico, {tipo: 'icono'}>}> = ({g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const visible = interpolate(f, [g.f, g.f + 2], [0, 1], CLAMP);
  const escala = 0.82 + 0.18 * ramp(f, g.f, g.f + 7) + 0.04 * Math.sin(Math.PI * ramp(f, g.f + 2, g.f + 9, (x) => x));
  const flota = Math.sin((f - g.f) / 14) * 5;
  const izquierda = g.lado !== 'derecha';
  return (
    <div style={{position: 'absolute', top: CAJAS.icono.y0 + flota, [izquierda ? 'left' : 'right']: izquierda ? CAJAS.icono.x0 : 1080 - CAJAS.icono.x1,
                 width: 180, display: 'flex',
                 flexDirection: 'column', alignItems: 'center', gap: 14, opacity: visible, transform: `scale(${escala})`,
                 filter: 'drop-shadow(0 6px 18px rgba(0, 0, 0, 0.45))'}}>
      <Icono nombre={g.icono} tam={120} color={e.texto} />
      {g.texto && <div style={{fontFamily: e.sans, fontWeight: 800, fontSize: 36, letterSpacing: '-0.02em', color: e.texto,
                               textAlign: 'center', lineHeight: 1.05}}>{g.texto}</div>}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Texto: entra cortado por una línea (nunca desenfoque + subida).
// ---------------------------------------------------------------------------

/**
 * Texto que entra como lo pondría un editor: aparece de golpe al ritmo de la voz (2 fotogramas) y se asienta con un
 * leve ajuste de escala. Nada de letra a letra ni de subir desde una línea: eso es lo que delata la plantilla.
 */
export const Linea: React.FC<{at: number; children: React.ReactNode; dur?: number; style?: React.CSSProperties}> = ({
  at, children, dur = 6, style,
}) => {
  const f = useCurrentFrame();
  const visible = interpolate(f, [at, at + 2], [0, 1], CLAMP);
  const asienta = ramp(f, at, at + dur);
  return (
    <span style={{display: 'inline-block', opacity: visible, transform: `scale(${1.05 - asienta * 0.05})`, ...style}}>
      {children}
    </span>
  );
};

/** Medidas del titular: ajuste al ancho (la serif condensada ocupa ~0,46 em por minúscula y ~0,62 por mayúscula). */
const ANCHO_TITULAR = (CAJAS.titular.x1 - CAJAS.titular.x0) * 0.97;
const medidaTitular = (g: Extract<Grafico, {tipo: 'titular'}>) => {
  const ancho = g.sans ? [...g.palabra].length * 0.66
    : [...g.palabra].reduce((a, c) => a + (c === c.toUpperCase() && /\p{L}/u.test(c) ? 0.62 : 0.46), 0);
  const size = Math.min(340, ANCHO_TITULAR / ancho);
  const top = g.kicker.length ? CAJAS.titular.y0 + 90 : CAJAS.titular.y0;
  return {size, top};
};

/**
 * Tamaño final del titular: el estimado y, cuando las fuentes han cargado, ajustado al ancho real medido.
 * Así cabe con cualquier tipografía del cliente, ancha o estrecha.
 */
/** El texto del titular tal como se pinta: en la sans gruesa y apretada, el espacio normal casi desaparece («TUIA»), así
 * que va un espacio de un tercio de eme. Se mide lo mismo que se pinta. */
const textoTitular = (g: Extract<Grafico, {tipo: 'titular'}>) => (g.sans ? g.palabra.replace(/ /g, '\u2004') : g.palabra);

/** Ancho de un titular sobre el vídeo real (detrás de la cabeza): más estrecho que sobre color, para que la cabeza no tape
 * el centro de la palabra (con todo el ancho, «PENSAR» se leía «PE…AR»). */
const ANCHO_SOBRE_VIDEO = 560;

const useTamanoTitular = (g?: Extract<Grafico, {tipo: 'titular'}>, sobreVideo = false) => {
  const e = useEstilo();
  const base = g ? medidaTitular(g) : {size: 0, top: 0};
  const [size, setSize] = React.useState(base.size);
  const [dx, setDx] = React.useState(0);
  React.useLayoutEffect(() => {
    if (!g) return;
    const espera = delayRender('Midiendo el titular');
    fuentesListas().then(async () => {
      const ctx = document.createElement('canvas').getContext('2d')!;
      // En el canvas, un nombre de familia con espacios sin comillas («Instrument Serif») no se entiende y mide con la
      // fuente por defecto: se entrecomilla.
      const familia = (x: string) => (/^["']/.test(x) || x.includes(',') || !x.includes(' ') ? x : `"${x}"`);
      const fuenteDe = (t: number) => (g.sans ? `900 ${t}px ${familia(e.sans)}` : `${t}px ${familia(e.serif)}`);
      // El canvas solo usa la fuente si ya está cargada para ese estilo: si no, mide con la de reserva (más ancha) y el
      // titular salía estrecho y descentrado. Se pide explícitamente antes de medir.
      await document.fonts.load(fuenteDe(base.size), textoTitular(g)).catch(() => undefined);
      ctx.font = fuenteDe(base.size);
      const ancho = ctx.measureText(textoTitular(g)).width * 0.985;
      // Ajustada al ancho medido: crece o mengua hasta llenarlo (la serif condensada ocupa menos de lo estimado), con tope.
      const final = Math.min(g.sans ? base.size * 1.15 : 340, (base.size * (sobreVideo && !g.sans ? ANCHO_SOBRE_VIDEO : ANCHO_TITULAR)) / Math.max(1, ancho));
      setSize(final);
      // Centrado óptico: lo que se centra es el dibujo de las letras (sin el aire de la P o la R ni el espaciado tras la
      // última), no la caja del texto. Desplazamiento = centro de la caja − centro de los trazos.
      ctx.font = fuenteDe(final);
      // Se dibuja letra a letra con el mismo espaciado que la página (y sin kerning, como el titular): así la tinta
      // del lienzo cae exactamente donde la pinta el navegador.
      const ls = (g.sans ? -0.045 : -0.015) * final;
      const letras = [...textoTitular(g)];
      const avances = letras.map((c) => ctx.measureText(c).width + ls);
      const total = avances.reduce((x, y) => x + y, 0);
      const margen = Math.ceil(final);
      const lienzo = document.createElement('canvas');
      lienzo.width = Math.ceil(total) + 2 * margen;
      lienzo.height = Math.ceil(final * 1.6);
      const c2 = lienzo.getContext('2d')!;
      c2.font = ctx.font;
      c2.textBaseline = 'alphabetic';
      let x = margen;
      letras.forEach((c, i) => { c2.fillText(c, x, final * 1.15); x += avances[i]; });
      const px = c2.getImageData(0, 0, lienzo.width, lienzo.height).data;
      let x0 = lienzo.width, x1 = -1;
      for (let cx = 0; cx < lienzo.width; cx++) {
        for (let y = 0; y < lienzo.height; y++) {
          if (px[(y * lienzo.width + cx) * 4 + 3] > 24) { x0 = Math.min(x0, cx); x1 = Math.max(x1, cx); break; }
        }
      }
      // Caja que centra el navegador: la suma de avances más los espaciados (también el de la última letra).
      const m = {width: total};
      setDx(x1 >= 0 ? m.width / 2 - ((x0 + x1 + 1) / 2 - margen) : 0);
      continueRender(espera);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g?.palabra, e.serif, sobreVideo]);
  return {size, top: base.top, dx};
};

/** Titular gigante detrás de la cabeza, letra a letra; con antetítulo palabra a palabra. */
const Titular: React.FC<{g: Extract<Grafico, {tipo: 'titular'}>; sobreVideo: boolean; tamano?: {size: number; top: number; dx?: number}; entero?: boolean}> = ({
  g, sobreVideo, tamano, entero,
}) => {
  const e = useEstilo();
  const medido = useTamanoTitular(tamano ? undefined : g);
  const base = tamano ?? medido;
  const {size, top} = entero ? {size: base.size * 0.72, top: CAJAS.titular.y0 - 40} : base;
  const dx = (base.dx ?? 0) * (entero ? 0.72 : 1);
  return (
    <AbsoluteFill>
      {g.kicker.length > 0 && (
        <div style={{
          position: 'absolute', top: CAJAS.antetitulo.y0, ...LADOS, textAlign: 'center', fontFamily: e.sans, fontWeight: 800,
          fontSize: 54, letterSpacing: '-0.02em', textTransform: 'uppercase', color: e.acento, lineHeight: 1.1,
        }}>
          {g.kicker.map((k, i) => (
            <React.Fragment key={i}>{i ? ' ' : ''}<Linea at={k.f} dur={7}>{k.w}</Linea></React.Fragment>
          ))}
        </div>
      )}
      <div style={{
        position: 'absolute', top, ...LADOS, textAlign: 'center',
        fontFamily: g.sans ? e.sans : e.serif, fontWeight: g.sans ? 900 : undefined, textTransform: g.sans ? 'uppercase' : undefined,
        fontSize: size, lineHeight: 1, letterSpacing: g.sans ? '-0.045em' : '-0.015em', fontKerning: 'none',
        // Centrado óptico (medido en useTamanoTitular): el dibujo de la palabra, no su caja, queda en x=540.
        transform: `translateX(${dx}px)`,
        // Sobre el vídeo, en el color de texto del kit (claro) con una sombra suave: en oscuro se perdía contra la pared.
        color: entero || g.sans ? '#FFFFFF' : e.texto, whiteSpace: 'nowrap',
        textShadow: entero ? '0 6px 30px rgba(0, 0, 0, 0.4)' : sobreVideo ? '0 6px 40px rgba(0, 0, 0, 0.35)' : undefined,
      }}>
        {/* Entra de golpe, sin el ajuste de escala: escalando, el dibujo se apartaba de x=540 los primeros fotogramas. */}
        <Linea at={g.f} dur={8} style={{transform: 'none'}}>{textoTitular(g)}</Linea>
      </div>
      {g.cursiva && <CursivaTitular texto={g.cursiva} at={g.f} top={top + size * 0.95 + 12} />}
    </AbsoluteFill>
  );
};

/** Segunda línea del titular (el gancho que engancha): la cursiva serif en una pastilla del acento, centrada. */
const CURSIVA_GANCHO = 104;
const CursivaTitular: React.FC<{texto: string; at: number; top: number}> = ({texto, at, top}) => {
  const e = useEstilo();
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  // En el gancho (fotograma 0, la portada) ya está entera; si entra más tarde, se abre desde el centro.
  const s = at <= 0 ? 1 : spring({frame: f - at - 4, fps, config: {damping: 15, mass: 0.6, stiffness: 210}});
  // Formato raw: la promesa, en la sans fina y blanca, sin pastilla ni cursiva. Entra con un fundido corto.
  if (e.promesa === 'simple') return (
    <div style={{position: 'absolute', top: top + 6, ...LADOS, textAlign: 'center', fontFamily: e.sans, fontWeight: 500,
      fontSize: Math.min(64, 900 / Math.max(1, texto.length * 0.5)), lineHeight: 1.05, letterSpacing: '-0.01em',
      color: e.texto, whiteSpace: 'nowrap', fontKerning: 'none', textShadow: '0 4px 24px rgba(0, 0, 0, 0.45)', opacity: Math.min(1, s * 1.5)}}>{texto}</div>
  );
  return (
    <div style={{position: 'absolute', top, ...LADOS, display: 'flex', justifyContent: 'center'}}>
      {/* Se ajusta al ancho: una promesa más larga («escribiendo contenido de 10.») baja de tamaño y nunca se sale. */}
      <div style={{padding: '4px 30px 16px', backgroundColor: e.acento, fontFamily: e.serif, fontStyle: 'italic',
        fontSize: Math.min(CURSIVA_GANCHO, 740 / Math.max(1, texto.length * 0.4)),
        lineHeight: 1, color: '#FFFFFF', whiteSpace: 'nowrap', transform: `scaleX(${s})`, boxShadow: '0 14px 40px rgba(0, 0, 0, 0.3)'}}>{texto}</div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Tarjetas: entran con escala corta y sombra, sin desenfoque.
// ---------------------------------------------------------------------------

const entradaTarjeta = (f: number, at: number): React.CSSProperties => {
  const t = ramp(f, at, at + 10);
  return {opacity: Math.min(1, t * 1.6), transform: `translateY(${(1 - t) * 34}px) scale(${0.96 + t * 0.04})`};
};

/** Cadencia de tecleo humana: pausas desiguales y un respiro en los espacios. */
const tecleo = (texto: string, desde: number, hasta: number) => {
  const pesos = [...texto].map((c, i) => (c === ' ' ? 2.2 : 1) * (0.7 + ((i * 7919) % 13) / 20));
  const total = pesos.reduce((a, b) => a + b, 0);
  let acc = 0;
  return pesos.map((p) => desde + ((acc += p) / total) * (hasta - desde));
};

const Chat: React.FC<{g: Extract<Grafico, {tipo: 'chat'}>}> = ({g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const tiempos = tecleo(g.texto, g.f + 5, g.envio - 2);
  const n = tiempos.filter((t) => f >= t).length;
  const enviado = f >= g.envio;
  const pulsa = 1 - 0.1 * Math.sin(Math.PI * ramp(f, g.envio, g.envio + 5, (x) => x));
  return (
    <div style={{position: 'absolute', top: CAJAS.chat.y0, ...LADOS, ...entradaTarjeta(f, g.f)}}>
      <div style={{
        backgroundColor: e.texto, borderRadius: 30, padding: '24px 24px 24px 34px', display: 'flex',
        alignItems: 'center', gap: 22, boxShadow: '0 24px 60px rgba(0, 0, 0, 0.28), 0 2px 6px rgba(0, 0, 0, 0.12)',
      }}>
        <div style={{flex: 1}}>
          <div style={{fontFamily: e.mono, fontSize: 22, letterSpacing: 4, textTransform: 'uppercase', color: 'rgba(8, 21, 40, 0.5)'}}>
            {enviado ? 'Enviado ✓' : g.etiqueta}
          </div>
          <div style={{fontFamily: e.sans, fontWeight: 600, fontSize: 44, color: e.fondo, marginTop: 8, letterSpacing: '-0.02em'}}>
            {g.texto.slice(0, n)}
            <span style={{opacity: !enviado && Math.floor(f / 9) % 2 === 0 ? 0.8 : 0}}>|</span>
          </div>
        </div>
        <div style={{
          width: 72, height: 72, borderRadius: 36, backgroundColor: e.fondo, color: e.texto, display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontFamily: e.sans, fontWeight: 800, fontSize: 36,
          transform: `scale(${pulsa})`, opacity: n >= g.texto.length ? 1 : 0.35,
        }}>↑</div>
      </div>
    </div>
  );
};

const Ficha: React.FC<{g: Extract<Grafico, {tipo: 'ficha'}>}> = ({g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const etiqueta = (t: string) => (
    <div style={{fontFamily: e.mono, fontSize: 22, letterSpacing: 4, textTransform: 'uppercase', color: e.acento}}>{t}</div>
  );
  return (
    <div style={{position: 'absolute', top: CAJAS.ficha.y0, ...LADOS, ...entradaTarjeta(f, g.filas[0].f - 3)}}>
      <div style={{backgroundColor: e.panel, borderRadius: 28, padding: 12, boxShadow: '0 24px 60px rgba(0, 0, 0, 0.35)'}}>
        <div style={{border: `1px solid ${e.filete}`, borderRadius: 18, padding: '24px 32px'}}>
          {g.filas.map((fila, i) => {
            const abre = i === 0 ? 1 : ramp(f, fila.f - 2, fila.f + 8);
            const valor = fila.cifra
              ? String(Math.round(interpolate(f, [fila.f, fila.f + 12], [0, Number(fila.valor)], {...CLAMP, easing: EXPO})))
              : fila.valor;
            return (
              <div key={i} style={{height: i === 0 ? undefined : abre * 168, overflow: 'hidden'}}>
                {i > 0 && <div style={{height: 1, backgroundColor: e.filete, margin: '22px 0 20px'}} />}
                {etiqueta(fila.etiqueta)}
                <div style={{display: 'flex', alignItems: 'baseline', gap: 16, marginTop: 4}}>
                  {fila.cifra ? (
                    <span style={{fontFamily: e.sans, fontWeight: 900, fontSize: 104, lineHeight: 1, letterSpacing: '-0.04em', color: e.texto}}>{valor}</span>
                  ) : (
                    <span style={{fontFamily: e.serif, fontSize: 100, lineHeight: 1.05, color: e.texto}}>
                      <Linea at={fila.f}>{valor}</Linea>
                    </span>
                  )}
                  {fila.sufijo && (
                    <span style={{fontFamily: e.serif, fontStyle: 'italic', fontSize: 60, color: e.acento}}>
                      <Linea at={fila.f + 4}>{fila.sufijo}</Linea>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Imagen real: tarjeta a la altura del pecho o pantalla partida arriba.
// ---------------------------------------------------------------------------

const Pie: React.FC<{texto: string; credito: string; style?: React.CSSProperties}> = ({texto, credito, style}) => {
  const e = useEstilo();
  return (
    <div style={{display: 'flex', flexDirection: 'column', gap: 6, ...style}}>
      {texto && <div style={{fontFamily: e.mono, fontSize: 22, letterSpacing: 4, textTransform: 'uppercase', color: e.acento}}>{texto}</div>}
      {credito && <div style={{fontFamily: e.mono, fontSize: 15, letterSpacing: 1, color: e.apagado}}>{credito}</div>}
    </div>
  );
};

/** Entrada de una captura: sube deslizando, crece desde un poco más pequeña o solo aparece. */
const entradaCaptura = (tipo: string, t: number): React.CSSProperties =>
  tipo === 'escalar' ? {transform: `scale(${0.86 + 0.14 * t})`} : tipo === 'aparecer' ? {} : {transform: `translateY(${(1 - t) * 40}px)`};

const Imagen: React.FC<{g: Extract<Grafico, {tipo: 'imagen'}>}> = ({g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  // Se descubre de abajo arriba (tarjeta) o de arriba abajo (pantalla), sin desenfoque, y dentro sigue un
  // acercamiento lento: la foto no se queda clavada.
  const t = ramp(f, g.f, g.f + 10);
  const empuje = 1.06 - t * 0.06 + Math.max(0, f - g.f) * 0.0008;
  const src = staticFile(`imagenes/${g.archivo}`);
  if (g.forma === 'flotante') {
    // Flotante: la captura como tarjeta en la parte de arriba, sobre el propio vídeo (la persona no se mueve).
    return (
      <AbsoluteFill style={{pointerEvents: 'none'}}>
        <div style={{position: 'absolute', top: CAJAS.chat.y0, ...LADOS, display: 'flex', justifyContent: 'center',
                     opacity: Math.min(1, t * 1.8), ...entradaCaptura(e.entradaPantalla, t)}}>
          <div style={{width: ZONA.x1 - ZONA.x0, maxHeight: 560, overflow: 'hidden', borderRadius: 20,
                       transform: `scale(${empuje})`, boxShadow: '0 24px 60px rgba(0, 0, 0, 0.35)'}}>
            <Img src={src} style={{width: '100%', height: 'auto', display: 'block'}} />
          </div>
        </div>
      </AbsoluteFill>
    );
  }
  if (g.forma === 'pantalla' && e.lienzo) {
    // Sobre el lienzo: la captura como una tarjeta limpia, centrada en la mitad de arriba, que sube y se asienta.
    return (
      <AbsoluteFill style={{pointerEvents: 'none'}}>
        <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 960, display: 'flex', flexDirection: 'column',
                     alignItems: 'center', justifyContent: 'center', gap: 14, opacity: Math.min(1, t * 1.8), ...entradaCaptura(e.entradaPantalla, t)}}>
          {/* A lo ancho y, si la captura es alta (una web en el móvil), solo su parte de arriba. */}
          <div style={{width: 900, maxHeight: 800, overflow: 'hidden', borderRadius: 20, transform: `scale(${empuje})`,
                       boxShadow: '0 22px 60px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.08)'}}>
            <Img src={src} style={{width: '100%', height: 'auto', display: 'block'}} />
          </div>
          {(g.pie || g.credito) && (
            <div style={{fontFamily: e.mono, fontSize: 20, color: 'rgba(21, 23, 26, 0.55)'}}>
              {[g.pie, g.credito].filter(Boolean).join(' · ')}
            </div>
          )}
        </div>
      </AbsoluteFill>
    );
  }
  if (g.forma === 'pantalla') {
    return (
      <AbsoluteFill style={{pointerEvents: 'none'}}>
        <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 940, overflow: 'hidden',
                     clipPath: `inset(0 0 ${(1 - t) * 100}% 0)`, backgroundColor: e.fondo}}>
          <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center top',
                                 transform: `scale(${empuje})`}} />
          {/* Velo que funde la imagen con el vídeo de debajo: sin filo duro ni caja. */}
          <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 220,
                       background: `linear-gradient(to bottom, transparent, ${e.fondo}E6)`}} />
          <Pie texto={g.pie} credito={g.credito} style={{position: 'absolute', ...LADOS, bottom: 940 - CAJAS.imagen_pie_pantalla.y1}} />
        </div>
      </AbsoluteFill>
    );
  }
  return (
    <div style={{...enCaja(CAJAS.imagen_tarjeta), display: 'flex', flexDirection: 'column',
                 alignItems: 'center', gap: 14, opacity: Math.min(1, t * 2)}}>
      <div style={{width: 400, height: 330, borderRadius: 22, overflow: 'hidden', border: `1px solid ${e.filete}`,
                   boxShadow: '0 30px 70px rgba(0, 0, 0, 0.45)', clipPath: `inset(${(1 - t) * 100}% 0 0 0 round 22px)`,
                   transform: `translateY(${(1 - t) * 40}px)`, backgroundColor: e.panel}}>
        <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center 30%',
                               transform: `scale(${empuje})`}} />
      </div>
      <Pie texto={g.pie} credito={g.credito} style={{alignItems: 'center', textAlign: 'center', maxWidth: ZONA.x1 - ZONA.x0}} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Subtítulos: grupos de 2-3 palabras que cambian en seco.
// ---------------------------------------------------------------------------

/** Palabras que no pueden cerrar una línea de subtítulos: artículos, preposiciones y conjunciones. */
const ENLACES = new Set(['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'lo', 'al', 'del', 'a', 'ante', 'con',
  'contra', 'de', 'desde', 'en', 'entre', 'hacia', 'hasta', 'para', 'por', 'según', 'sin', 'sobre', 'tras', 'y', 'e', 'o',
  'u', 'ni', 'que', 'pero', 'si', 'porque', 'como', 'mi', 'tu', 'su', 'mis', 'tus', 'sus', 'se', 'te', 'me', 'nos']);

const Subtitulos: React.FC<{palabras: Palabra[]; hasta: number}> = ({palabras, hasta}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  if (f >= hasta) return null;
  const grupos: Palabra[][] = [];
  let g: Palabra[] = [];
  palabras.forEach((p) => {
    // Una línea nunca acaba en artículo, preposición o conjunción («nadie dirá un»): esa palabra abre la siguiente.
    if (g.length === 3 && ENLACES.has(g[2].w.toLowerCase())) {
      const suelta = g.pop()!;
      grupos.push(g);
      g = [suelta];
    }
    g.push(p);
    if ((g.length === 3 && !ENLACES.has(p.w.toLowerCase())) || /[.,]$/.test(p.w)) {
      grupos.push(g);
      g = [];
    }
  });
  if (g.length) grupos.push(g);
  const activo = [...grupos].reverse().find((gr) => f >= gr[0].f);
  if (!activo) return null;
  if (e.limpio) {
    // Limpios: blancos, pequeños, sin caja; solo una sombra suave para que se lean sobre cualquier fondo. Entran
    // todos a la vez, palabra a palabra, en karaoke (la que se dice, iluminada) o con un salto corto; la palabra clave
    // (la más larga del grupo) puede ir en color, subrayada o en negrita.
    const clave = activo.reduce((a, b) => (b.w.replace(/[.,;:]/g, '').length > a.w.replace(/[.,;:]/g, '').length ? b : a));
    const salto = e.subsAnim === 'salto' ? interpolate(f - activo[0].f, [0, 3, 6], [0.85, 1.06, 1], CLAMP) : 1;
    return (
      <div style={{position: 'absolute', top: e.subsAbajo ? CAJAS.subtitulos.y1 - 30 : CAJAS.subtitulos.y0, ...LADOS,
                   display: 'flex', justifyContent: 'center', textAlign: 'center', transform: `scale(${salto})`,
                   fontFamily: e.subsLimpia, fontWeight: 700, fontSize: e.subsAbajo ? 56 : 50, letterSpacing: '-0.01em', color: '#FFFFFF',
                   textShadow: '0 2px 10px rgba(0, 0, 0, 0.55), 0 1px 2px rgba(0, 0, 0, 0.4)'}}>
        <span>
          {activo.map((p, i) => {
            const dicha = f >= p.f;
            const esClave = p === clave && activo.length > 1 && e.subsResalte !== 'nada';
            return (
              <span key={i} style={{
                opacity: e.subsAnim === 'palabra' && !dicha ? 0 : e.subsAnim === 'karaoke' && !dicha ? 0.45 : 1,
                color: esClave && e.subsResalte === 'color' ? e.lienzoAcento : undefined,
                textDecoration: esClave && e.subsResalte === 'subrayado' ? 'underline' : undefined,
                textDecorationColor: e.lienzoAcento, textDecorationThickness: 5, textUnderlineOffset: 8,
                fontWeight: esClave && e.subsResalte === 'negrita' ? 900 : undefined,
              }}>{(i ? ' ' : '') + p.w}</span>
            );
          })}
        </span>
      </div>
    );
  }
  return (
    <div style={{position: 'absolute', top: CAJAS.subtitulos.y0, ...LADOS, display: 'flex', justifyContent: 'center', textAlign: 'center'}}>
      <div style={{fontFamily: e.subs, fontSize: 64, lineHeight: 1, padding: '8px 18px 12px', backgroundColor: e.panel}}>
        {activo.map((p, i) => (
          <span key={i} style={{color: f >= p.f || !e.resaltar ? e.texto : e.apagado}}>{(i ? ' ' : '') + p.w}</span>
        ))}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Acabado de todo el reel.
// ---------------------------------------------------------------------------

/** Grano fino: 4 placas de ruido que cambian cada 2 fotogramas, como una emulsión. */
export const Grano: React.FC = () => {
  const f = useCurrentFrame();
  const e = useEstilo();
  if (e.vista) return null; // en la vista previa del estudio, sin grano: es caro y a ese tamaño no se ve
  return (
    <AbsoluteFill style={{mixBlendMode: 'overlay', opacity: 0.22, pointerEvents: 'none'}}>
      <Img src={staticFile(`grano/g${Math.floor(f / 2) % 4}.png`)} style={{width: '100%', height: '100%'}} />
    </AbsoluteFill>
  );
};

/** Entrada en tres tiras con desenfoque de movimiento vertical (filtro SVG direccional). */
export const Tiras: React.FC<{children: React.ReactNode; id: string}> = ({children, id}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      {[0, 1, 2].map((i) => {
        const a = i * 2;
        const t = ramp(f, a, a + 8);
        const v = ramp(f, a, a + 8) - ramp(f - 1, a, a + 8); // velocidad en fracción de pantalla por fotograma
        const fid = `mb-${id}-${i}`;
        return (
          <AbsoluteFill key={i} style={{clipPath: `inset(0 ${(2 - i) * 33.34}% 0 ${i * 33.33}%)`}}>
            <svg width="0" height="0" style={{position: 'absolute'}}>
              <filter id={fid} x="0" y="-20%" width="100%" height="140%">
                <feGaussianBlur stdDeviation={`0 ${Math.min(60, v * 1920 * 0.35)}`} />
              </filter>
            </svg>
            <AbsoluteFill style={{transform: `translateY(${(1 - t) * 100}%)`, filter: v > 0.002 ? `url(#${fid})` : undefined}}>
              {children}
            </AbsoluteFill>
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};

/** Si un color es claro (luminancia alta): sobre un lienzo claro, los efectos van en tinta oscura. */
const esClaro = (hex: string) => {
  const c = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(c.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.6;
};

/** La paleta de los efectos sobre el lienzo (claro): tinta oscura y la fila activa en el acento del lienzo. */
const enLienzo = (e: Estilo): Estilo => ({
  ...e, texto: '#15171A', apagado: 'rgba(21, 23, 26, 0.42)', acento: e.lienzoAcento, filete: 'rgba(21, 23, 26, 0.16)',
});

/** Sitios alrededor de la cabeza para los logos: a los lados y por encima, nunca sobre la cara. */
const SITIOS_LOGO: [number, number, number][] = [[120, 520, -8], [760, 470, 7], [170, 760, 5], [720, 730, -6], [460, 300, 0]];

/** Logos de las apps que nombra: saltan uno tras otro alrededor de la cabeza (escala con rebote corto y flotan). */
const Logos: React.FC<{g: Extract<Grafico, {tipo: 'logos'}>}> = ({g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {g.logos.slice(0, SITIOS_LOGO.length).map((logo, i) => {
        const at = g.f + i * 4;
        const t = interpolate(f, [at, at + 5, at + 9], [0, 1.14, 1], CLAMP);
        const [x, y, giro] = SITIOS_LOGO[i];
        const flota = Math.sin((f - at) / 12 + i) * 6;
        // Tachado: una línea roja que cruza el logo de esquina a esquina, poco después de que se asiente.
        const raya = g.tachar ? interpolate(f, [at + 10, at + 16], [0, 1], CLAMP) : 0;
        return (
          <div key={logo} style={{position: 'absolute', left: x, top: y + flota, width: 170, height: 170,
            transform: `scale(${t}) rotate(${giro}deg)`, opacity: Math.min(1, t * 3)}}>
            <Img src={staticFile(`logos/${logo}`)} style={{width: '100%', height: '100%', objectFit: 'contain',
              filter: 'drop-shadow(0 10px 22px rgba(0, 0, 0, 0.35))'}} />
            {raya > 0 && (
              <svg width={170} height={170} viewBox="0 0 170 170" style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
                <line x1={6} y1={164} x2={6 + 158 * raya} y2={164 - 158 * raya} stroke={(e as unknown as {notas?: string}).notas ?? '#E5322D'}
                  strokeWidth={13} strokeLinecap="round" />
              </svg>
            )}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/** Sello de la serie: el texto grande entra con un rebote corto y la cinta en cursiva se desenrolla debajo. */
const Sello: React.FC<{g: Extract<Grafico, {tipo: 'sello'}>}> = ({g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const t = interpolate(f, [g.f, g.f + 5, g.f + 9], [0, 1.08, 1], CLAMP);
  const cinta = ramp(f, g.f + 5, g.f + 13);
  return (
    <div style={{position: 'absolute', top: CAJAS.antetitulo.y0 + 30, ...LADOS, display: 'flex', flexDirection: 'column',
                 alignItems: 'center', transform: `scale(${t})`, opacity: Math.min(1, t * 3)}}>
      <div style={{fontFamily: e.sans, fontWeight: 900, fontSize: 170, lineHeight: 0.9, letterSpacing: '-0.05em', color: '#FFFFFF',
                   textShadow: '0 6px 24px rgba(0, 0, 0, 0.35)'}}>{g.texto}</div>
      {g.cinta && (
        <div style={{marginTop: -10, marginLeft: 120, transform: 'rotate(-6deg)', backgroundColor: e.lienzoAcento,
                     padding: '6px 26px 10px', clipPath: `inset(0 ${(1 - cinta) * 100}% 0 0)`,
                     boxShadow: '0 8px 20px rgba(0, 0, 0, 0.25)'}}>
          <span style={{fontFamily: e.serif, fontStyle: 'italic', fontSize: 64, color: '#FFFFFF'}}>{g.cinta}</span>
        </div>
      )}
    </div>
  );
};

/** Entrada de un plano: deslizamiento lateral corto o un destello blanco que se apaga (además del corte seco). */
export const Entrada: React.FC<{tipo: PlanoMontado['entrada']; children: React.ReactNode}> = ({tipo, children}) => {
  const f = useCurrentFrame();
  if (tipo === 'desliza') {
    const t = ramp(f, 0, 7);
    return <AbsoluteFill style={{transform: `translateX(${(1 - t) * 140}px)`, opacity: Math.min(1, 0.4 + t)}}>{children}</AbsoluteFill>;
  }
  if (tipo === 'destello') {
    return (
      <AbsoluteFill>
        {children}
        <AbsoluteFill style={{backgroundColor: '#FFFFFF', opacity: interpolate(f, [0, 5], [0.85, 0], CLAMP), pointerEvents: 'none'}} />
      </AbsoluteFill>
    );
  }
  return <>{children}</>;
};

/** Look de imagen: natural (sin tocar), cálido, frío o con más contraste. Va sobre todo el reel. */
export const filtroLook = (look?: string): string | undefined =>
  look === 'calido' ? 'sepia(0.12) saturate(1.08) hue-rotate(-6deg)' : look === 'frio' ? 'saturate(0.95) hue-rotate(8deg) brightness(1.02)'
    : look === 'contraste' ? 'contrast(1.12) saturate(1.05)' : undefined;

/** Barra de progreso fina abajo, en el acento del kit. */
export const Progreso: React.FC<{total: number}> = ({total}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  return (
    <div style={{position: 'absolute', left: 0, bottom: 0, height: 8, width: `${(f / Math.max(1, total)) * 100}%`,
                 backgroundColor: e.lienzoAcento, boxShadow: `0 0 12px ${e.lienzoAcento}`}} />
  );
};

/**
 * Texto del gancho: arriba (o bajo la pantalla partida), visible desde el fotograma 0 porque es la portada. Con
 * subrayado, una línea en el acento se dibuja debajo; palabra a palabra, cada palabra entra 4 fotogramas después.
 */
const TextoGancho: React.FC<{t: NonNullable<PlanoMontado['textoGancho']>; abajo: boolean}> = ({t, abajo}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  const palabras = t.texto.split(/\s+/).filter(Boolean);
  const linea = t.modo === 'subrayado' ? ramp(f, 4, 18) : 0;
  return (
    <div style={{position: 'absolute', top: abajo ? 990 : CAJAS.antetitulo.y0 + 20, ...LADOS, display: 'flex', justifyContent: 'center'}}>
      <div style={{position: 'relative', textAlign: 'center', fontFamily: e.subsLimpia, fontWeight: 800, fontSize: 76, lineHeight: 1.05,
                   letterSpacing: '-0.005em', color: '#FFFFFF', textShadow: '0 4px 18px rgba(0, 0, 0, 0.5)'}}>
        {palabras.map((w, i) => (
          <span key={i} style={{opacity: t.modo === 'palabra' ? interpolate(f, [i * 4, i * 4 + 2], [0, 1], CLAMP) : 1}}>{(i ? ' ' : '') + w}</span>
        ))}
        {t.modo === 'subrayado' && (
          <div style={{position: 'absolute', left: 0, bottom: -14, height: 10, borderRadius: 5, width: `${linea * 100}%`,
                       backgroundColor: e.lienzoAcento, boxShadow: `0 0 16px ${e.lienzoAcento}`}} />
        )}
      </div>
    </div>
  );
};
