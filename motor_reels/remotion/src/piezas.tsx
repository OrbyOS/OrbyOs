import React from 'react';
import {AbsoluteFill, Img, continueRender, delayRender, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {EfectoEnCaja} from './efectos';
import {Icono} from './iconos';
import {FondoAnimado} from './fondos';
import {fuentesListas} from './fuentes';
import {CLAMP, EXPO, IN, ramp, ruido, semillaDe, useEstilo} from './estilo';
import {CAJAS, LADOS, ZONA, enCaja} from './zona';
import type {Grafico, Palabra, PlanoMontado} from './tipos';

const pad = (n: number) => String(Math.max(0, n)).padStart(5, '0');
const fotograma = (i: number) => staticFile(`frames/f_${pad(i)}.jpg`);
const mascara = (i: number) => staticFile(`frames/m_${pad(i)}.png`);

// ---------------------------------------------------------------------------
// Cámara: encuadre del montaje + cámara en mano + látigos + sacudida.
// ---------------------------------------------------------------------------

const camara = (p: PlanoMontado, f: number, titular?: {size: number; top: number}) => {
  const s = semillaDe(p.id);
  let zoom = p.zoom * 1.02; // margen para que la deriva no enseñe bordes
  let blur = 0;
  let x = ruido(f, s) * 4;
  let base = p.y;
  if (p.cabeza && titular) {
    const {size, top} = titular;
    const objetivo = top + size * 0.72;
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
    zoom *= 1 + 0.11 * ramp(k, 0, 3) - 0.025 * ramp(k, 3, 9);
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
                                        filter: 'blur(28px) saturate(0.85)'}} />
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
  const tamano = useTamanoTitular(g?.tipo === 'titular' ? g : undefined);
  const partida = p.composicion === 'partida';
  const cam = partida ? camaraPartida(p, f) : camara(p, f, g?.tipo === 'titular' ? tamano : undefined);
  if (p.composicion === 'completa') {
    // A pantalla completa la cara se va, pero el fondo sigue siendo su vídeo (desenfocado): nada de diapositiva.
    return <AbsoluteFill style={{backgroundColor: e.fondo}}><VideoDesenfocado src={src} /></AbsoluteFill>;
  }
  const quitar = g?.tipo === 'fondo' ? ramp(f, g.f + 3, g.f + 13, (x) => x * x) : 0;
  const titular = g?.tipo === 'titular' ? g : g?.tipo === 'fondo' && g.titular && quitar >= 1 ? g : undefined;
  const conPersona = p.modo === 'recorte' || quitar > 0 || g?.tipo === 'titular';
  useMascaraLista(mascara(src), conPersona);
  const mask = {
    WebkitMaskImage: `url(${mascara(src)})`, WebkitMaskSize: '100% 100%',
    maskImage: `url(${mascara(src)})`, maskSize: '100% 100%',
  } as React.CSSProperties;
  const r = quitar * 2600;
  const borrado = `radial-gradient(circle at 50% 26%, #000 ${r}px, transparent ${r + 260}px)`;
  return (
    <AbsoluteFill style={{backgroundColor: e.fondo, overflow: 'hidden'}}>
      {partida && <VideoDesenfocado src={src} alto={960} />}
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
      {titular && (
        <Titular
          g={titular.tipo === 'titular' ? titular : {tipo: 'titular', kicker: [], palabra: titular.titular!, f: titular.f + 13}}
          sobreVideo={p.modo === 'real' && quitar < 1}
          tamano={titular.tipo === 'titular' ? tamano : undefined}
        />
      )}
      {conPersona && (
        // La sombra va en el padre: si fuera en la capa con máscara, la máscara la recortaría.
        <AbsoluteFill style={{filter: p.modo === 'recorte' || quitar > 0.5 ? 'drop-shadow(0 34px 50px rgba(0, 0, 0, 0.42))' : undefined}}>
          <AbsoluteFill style={{...cam, ...mask}}>
            <Img src={fotograma(src)} style={{width: '100%', height: '100%'}} />
          </AbsoluteFill>
        </AbsoluteFill>
      )}
      {g?.tipo === 'icono' && <IconoAlLado g={g} />}
      {g?.tipo === 'chat' && <Chat g={g} />}
      {g?.tipo === 'imagen' && <Imagen g={g} />}
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
      <AbsoluteFill style={{pointerEvents: 'none'}}>
        <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 960, opacity: t}}>
          <EfectoEnCaja g={g} caja={CAJAS.efecto_partida} escala={1.0} />
        </div>
        <div style={{position: 'absolute', top: 958, left: 0, right: 0, height: 2, backgroundColor: e.acento, opacity: 0.8 * t}} />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity: t}}>
      <EfectoEnCaja g={g} caja={CAJAS.efecto_completa} escala={1} />
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
      <div style={{position: 'absolute', left: -80, right: -80, top: 940, height: 600, opacity: ramp(f, 0, 5),
                   backgroundColor: `${e.fondo}${tono === 'claro' ? 'D0' : 'B0'}`, backdropFilter: 'blur(22px)',
                   WebkitMaskImage: borde, maskImage: borde}} />
      <AbsoluteFill style={{filter: 'drop-shadow(0 3px 14px rgba(0, 0, 0, 0.55))'}}>
        <EfectoEnCaja g={g} caja={CAJAS.efecto_encima} escala={0.78} />
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
  const ancho = [...g.palabra].reduce((a, c) => a + (c === c.toUpperCase() && /\p{L}/u.test(c) ? 0.62 : 0.46), 0);
  const size = Math.min(340, ANCHO_TITULAR / ancho);
  const top = g.kicker.length ? CAJAS.titular.y0 + 90 : CAJAS.titular.y0;
  return {size, top};
};

/**
 * Tamaño final del titular: el estimado y, cuando las fuentes han cargado, ajustado al ancho real medido.
 * Así cabe con cualquier tipografía del cliente, ancha o estrecha.
 */
const useTamanoTitular = (g?: Extract<Grafico, {tipo: 'titular'}>) => {
  const e = useEstilo();
  const base = g ? medidaTitular(g) : {size: 0, top: 0};
  const [size, setSize] = React.useState(base.size);
  React.useLayoutEffect(() => {
    if (!g) return;
    const espera = delayRender('Midiendo el titular');
    fuentesListas().then(() => {
      const ctx = document.createElement('canvas').getContext('2d')!;
      ctx.font = `${base.size}px ${e.serif}`;
      const ancho = ctx.measureText(g.palabra).width * 0.985;
      setSize(Math.min(base.size, (base.size * ANCHO_TITULAR) / Math.max(1, ancho)));
      continueRender(espera);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g?.palabra, e.serif]);
  return {size, top: base.top};
};

/** Titular gigante detrás de la cabeza, letra a letra; con antetítulo palabra a palabra. */
const Titular: React.FC<{g: Extract<Grafico, {tipo: 'titular'}>; sobreVideo: boolean; tamano?: {size: number; top: number}}> = ({
  g, sobreVideo, tamano,
}) => {
  const e = useEstilo();
  const medido = useTamanoTitular(tamano ? undefined : g);
  const {size, top} = tamano ?? medido;
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
        fontFamily: e.serif, fontSize: size, lineHeight: 1, letterSpacing: '-0.015em',
        color: sobreVideo ? e.fondo : e.texto, whiteSpace: 'nowrap',
      }}>
        <Linea at={g.f} dur={8}>{g.palabra}</Linea>
      </div>
    </AbsoluteFill>
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

const Imagen: React.FC<{g: Extract<Grafico, {tipo: 'imagen'}>}> = ({g}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  // Se descubre de abajo arriba (tarjeta) o de arriba abajo (pantalla), sin desenfoque, y dentro sigue un
  // acercamiento lento: la foto no se queda clavada.
  const t = ramp(f, g.f, g.f + 10);
  const empuje = 1.06 - t * 0.06 + Math.max(0, f - g.f) * 0.0008;
  const src = staticFile(`imagenes/${g.archivo}`);
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

const Subtitulos: React.FC<{palabras: Palabra[]; hasta: number}> = ({palabras, hasta}) => {
  const f = useCurrentFrame();
  const e = useEstilo();
  if (f >= hasta) return null;
  const grupos: Palabra[][] = [];
  let g: Palabra[] = [];
  palabras.forEach((p) => {
    g.push(p);
    if (g.length === 3 || /[.,]$/.test(p.w)) {
      grupos.push(g);
      g = [];
    }
  });
  if (g.length) grupos.push(g);
  const activo = [...grupos].reverse().find((gr) => f >= gr[0].f);
  if (!activo) return null;
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
