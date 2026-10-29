import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, random, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ANCHO, CLAMP, CX, ConResalte, EXPO, ConMarca, EstiloCtx, Filete, Velo, fontFamily, pop, ramp, sombraTexto, useEstilo} from './base';
import {PLANOS, Sello} from './planos';
import {colorDe} from './robot';
import type {Palabra, Plano, Props} from './tipos';
import {MascotaOrby, PLANOS_VIRAL, RotuloAbajo, RotuloViral, TitularFijo} from './viral';
import {Robot} from './robot';

const SALIDA = 5; // fotogramas que tarda en irse un plano mientras entra el siguiente
const ENTRADA = 7;

// ---------------------------------------------------------------- fondo

export const Fondo: React.FC<{f: number; p: Props}> = ({f, p}) => {
  const e = p.estilo;
  if (e.diseno === 'cazzap' || e.diseno === 'herramienta') return <FondoOscuro f={f} p={p} />;
  if (e.diseno === 'viral') return <AbsoluteFill style={{background: '#000'}} />;
  const manchas = [0, 1, 2].map((i) => ({
    x: 540 + Math.sin(f / (90 + i * 30) + i * 2) * 380,
    y: 900 + Math.cos(f / (110 + i * 25) + i) * 600,
    r: 520 + i * 80,
  }));
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 40%, color-mix(in srgb, ${e.mesa} 70%, ${e.acento}) 0%, ${e.mesa} 55%, color-mix(in srgb, ${e.mesa} 35%, black) 100%)`}}>
      {manchas.map((m, i) => (
        <div key={i} style={{position: 'absolute', left: m.x - m.r, top: m.y - m.r, width: m.r * 2, height: m.r * 2, borderRadius: '50%',
          background: `radial-gradient(circle, color-mix(in srgb, ${i === 1 ? e.acento : e.subrayado} ${i === 1 ? 30 : 16}%, transparent) 0%, transparent 65%)`}} />
      ))}
      <AbsoluteFill style={{
        backgroundImage: `linear-gradient(${e.veta} 2px, transparent 2px), linear-gradient(90deg, ${e.veta} 2px, transparent 2px)`,
        backgroundSize: '90px 90px', backgroundPosition: `0 ${(f * 0.6) % 90}px`,
        maskImage: 'radial-gradient(ellipse at 50% 45%, black 20%, transparent 75%)',
        WebkitMaskImage: 'radial-gradient(ellipse at 50% 45%, black 20%, transparent 75%)'}} />
      {Array.from({length: 26}).map((_, i) => {
        const x = random(`x${i}`) * 1080;
        const v = 0.4 + random(`v${i}`) * 1.2;
        const y = (random(`y${i}`) * 2100 - f * v) % 2100;
        const yy = y < -60 ? y + 2100 : y;
        const r = 3 + random(`r${i}`) * 6;
        return <div key={i} style={{position: 'absolute', left: x + Math.sin((f + i * 30) / 40) * 20, top: yy, width: r, height: r,
          borderRadius: r, background: e.subrayado, opacity: 0.12 + random(`o${i}`) * 0.25, boxShadow: `0 0 12px ${e.subrayado}`}} />;
      })}
      <AbsoluteFill style={{boxShadow: 'inset 0 0 300px rgba(0,0,0,0.6)'}} />
    </AbsoluteFill>
  );
};

/** Diseño «cazzap»: un solo color oscuro de la marca para todo el vídeo, sin rejilla, con dos luces que se mueven muy
 * despacio y motas que suben, para que el fondo respire sin distraer. */
// Tonos con los que rota el fondo cada dos planos: el de la marca y tres vecinos (índigo, petróleo, ciruela), siempre
// oscuros, para que el vídeo no sea «un fondo azul y ya» sin dejar de parecer de la misma marca.
const TONOS = ['', '#2a1f7a', '#0d4a5e', '#4a1f6b'];
const FondoOscuro: React.FC<{f: number; p: Props}> = ({f, p}) => {
  const e = p.estilo;
  const t = f / 30;
  const i = Math.max(0, p.planos.findIndex((x) => t >= x.inicio && t < x.fin));
  const tono = (k: number) => (TONOS[k % TONOS.length] ? `color-mix(in srgb, ${e.mesa} 55%, ${TONOS[k % TONOS.length]})` : e.mesa);
  const bloque = Math.floor(i / 2);
  const ini = p.planos[bloque * 2]?.inicio ?? 0;
  const mezcla = interpolate(t, [ini, ini + 0.5], [0, 1], CLAMP);
  const capa = (mesa: string, op: number) => (
    <AbsoluteFill style={{opacity: op, background: `linear-gradient(180deg, color-mix(in srgb, ${mesa} 45%, black) 0%, color-mix(in srgb, ${mesa} 62%, black) 45%, color-mix(in srgb, ${mesa} 80%, black) 100%)`}} />
  );
  return (
    <AbsoluteFill>
      {capa(tono(Math.max(0, bloque - 1)), 1)}
      {capa(tono(bloque), mezcla)}
      {[0, 1].map((i) => {
        const x = 540 + Math.sin(f / (220 + i * 70) + i * 3) * 300;
        const y = 820 + Math.cos(f / (260 + i * 50) + i) * 420;
        const r = 620 + i * 120;
        return <div key={i} style={{position: 'absolute', left: x - r, top: y - r, width: r * 2, height: r * 2, borderRadius: '50%',
          background: `radial-gradient(circle, color-mix(in srgb, ${e.acento} ${i ? 10 : 14}%, transparent) 0%, transparent 62%)`}} />;
      })}
      {Array.from({length: 22}).map((_, i) => {
        const x = random(`cx${i}`) * 1080;
        const v = 0.15 + random(`cv${i}`) * 0.45;
        const y = (random(`cy${i}`) * 2100 - f * v) % 2100;
        const yy = y < -40 ? y + 2100 : y;
        const r = 3 + random(`cr${i}`) * 4;
        const brillo = 0.12 + 0.2 * (0.5 + 0.5 * Math.sin(f / 25 + i * 1.7));
        return <div key={i} style={{position: 'absolute', left: x + Math.sin((f + i * 40) / 60) * 14, top: yy, width: r, height: r,
          borderRadius: r, background: e.subrayado, opacity: brillo, boxShadow: `0 0 10px ${e.subrayado}`}} />;
      })}
      <Suelo e={e} f={f} />
      <AbsoluteFill style={{boxShadow: 'inset 0 0 260px rgba(0,0,0,0.55)'}} />
    </AbsoluteFill>
  );
};

/** Un suelo en perspectiva debajo de la escena: las cosas se apoyan en algo en vez de flotar en el vacío. */
const HORIZONTE = 1420;
const Suelo: React.FC<{e: Props['estilo']; f: number}> = ({e, f}) => {
  const fuga = {x: 540, y: 980};
  const lineas = Array.from({length: 13}).map((_, i) => -900 + i * 240 + ((f * 0.4) % 240));
  return (
    <svg width={1080} height={1920} style={{position: 'absolute', inset: 0}}>
      <defs>
        <linearGradient id="suelo" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={e.acento} stopOpacity="0.16" />
          <stop offset="1" stopColor="#000" stopOpacity="0.25" />
        </linearGradient>
        <clipPath id="bajo"><rect x={0} y={HORIZONTE} width={1080} height={1920 - HORIZONTE} /></clipPath>
      </defs>
      <rect x={0} y={HORIZONTE} width={1080} height={1920 - HORIZONTE} fill="url(#suelo)" />
      <g clipPath="url(#bajo)" stroke={e.subrayado} strokeOpacity="0.09" strokeWidth="2">
        {lineas.map((x, i) => <line key={i} x1={fuga.x} y1={fuga.y} x2={x} y2={1920} />)}
        {[0, 1, 2, 3, 4].map((i) => { const y = HORIZONTE + Math.pow((i + ((f * 0.01) % 1)) / 5, 2) * (1920 - HORIZONTE);
          return <line key={`h${i}`} x1={0} y1={y} x2={1080} y2={y} />; })}
      </g>
      <line x1={0} y1={HORIZONTE} x2={1080} y2={HORIZONTE} stroke={e.subrayado} strokeOpacity="0.22" strokeWidth="2" />
    </svg>
  );
};

/** Diseño «cazzap»: la escena llena la pantalla bajo el subtítulo. Cada tipo de plano crece lo que le cabe y baja hasta
 * apoyarse en el suelo; los que ya ocupan todo (escenas, pantallas) van tal cual. */
const ESCALA_CAZZAP: Record<string, number> = {
  // Los que ocupan todo el ancho de su caja (780 px) crecen menos: con 1,12 caben en 1080 con más de 60 px a cada lado.
  objetos: 1.55, robot: 1.3, equipo: 1.5, reloj: 1.55, calendario: 1.12, palabra: 1.3, frase: 1.12, cifra: 1.3, lista: 1.3,
  chat: 1.12, versus: 1.0, flujo: 1.12, movil: 1.3, grafica: 1.12, suma: 1.12, venta: 1.12, cierre: 1.25,
};
const CON_SOMBRA = new Set(['objetos', 'robot', 'equipo', 'reloj']);

// En el explicativo, todo el texto va centrado en la pantalla (540). El vídeo a cámara usa CX (470), que deja aire a
// los botones de Instagram.
const CENTRO = 540;

// ---------------------------------------------------------------- título y rótulos

const Titulo: React.FC<{p: Props; f: number; fps: number}> = ({p, f, fps}) => {
  const fin = Math.round(p.titulo.fin * fps);
  // En «cazzap» la portada es el propio subtítulo de arriba, que sale entero desde el primer fotograma.
  if (p.estilo.diseno === 'herramienta') return <TitularFijo p={p} />;
  if (f > fin || p.estilo.diseno === 'cazzap' || p.estilo.diseno === 'viral') return null;
  const sale = interpolate(f, [fin - SALIDA, fin], [1, 0], CLAMP);
  // Visible desde el fotograma 0 (es la portada): texto plano sobre un velo, sin caja. La insignia, un filete debajo.
  return (
    <div style={{position: 'absolute', top: 250, left: CENTRO - ANCHO / 2, width: ANCHO, display: 'flex', flexDirection: 'column',
      alignItems: 'center', gap: 22, opacity: sale}}>
      <Velo>
        <div style={{color: '#fff', fontFamily, fontWeight: 900, fontSize: p.titulo.texto.length > 34 ? 64 : 74, lineHeight: 1.06,
          letterSpacing: -0.5, textAlign: 'center', textShadow: '0 2px 22px rgba(0,0,0,0.45)'}}>
          <ConResalte texto={p.titulo.texto} resalte={p.titulo.resalte} color={p.estilo.subrayado} />
        </div>
      </Velo>
      {p.titulo.insignia ? <Filete texto={p.titulo.insignia} k={ramp(f, 8, 16)} tam={38} /> : null}
    </div>
  );
};

const Rotulos: React.FC<{p: Props; t: number; fps: number}> = ({p, t, fps}) => {
  const r = p.rotulos.find((x) => t >= x.inicio && t < x.fin);
  if (!r || p.estilo.diseno === 'cazzap' || p.estilo.diseno === 'viral' || p.estilo.diseno === 'herramienta') return null;
  const f = Math.round((t - r.inicio) * fps);
  const sale = interpolate(t, [r.fin - SALIDA / fps, r.fin], [1, 0], CLAMP);
  return (
    <div style={{position: 'absolute', top: 262, left: CENTRO - ANCHO / 2, width: ANCHO, display: 'flex', justifyContent: 'center', opacity: sale}}>
      <Filete texto={r.texto} k={ramp(f, 0, 8)} tam={40} />
    </div>
  );
};

// ---------------------------------------------------------------- planos con transición

// Dos entradas, cortas y limpias. «barrido» y «gira» se aceptan en guiones antiguos y van como las nuevas.
const TRANSICIONES = ['zoom', 'sube'];

const entrada = (tipo: string, k: number): React.CSSProperties => {
  const q = 1 - k;
  if (tipo === 'sube' || tipo === 'barrido') return {transform: `translateY(${q * 90}px)`, filter: `blur(${q * 6}px)`, opacity: k};
  return {transform: `scale(${1 + q * 0.08})`, filter: `blur(${q * 8}px)`, opacity: k};
};

const empujon = (i: number, k: number): React.CSSProperties => {
  const q = 1 - k;
  return i % 2 ? {transform: `translateY(${q * 70}px)`} : {transform: `scale(${1 + q * 0.06})`};
};

export const PlanoVivo: React.FC<{pl: Plano; i: number; frame: number; fps: number; corte?: boolean; seco?: boolean}> = ({pl, i, frame, fps, corte, seco}) => {
  const ini = Math.round(pl.inicio * fps);
  const fin = Math.round(pl.fin * fps);
  const f = frame - ini + (i === 0 ? 30 : 0);
  // «corte»: el siguiente plano entra en seco (el cierre), así que este no se queda fundiéndose debajo: sin doble Orby.
  // «seco» (los explicativos): nunca hay dos planos a la vez. El que sale desaparece en el fotograma en que entra el
  // siguiente, y el que entra lo hace con un empujón, sin fundido: nada de un plano encima de otro ni contadores a medias.
  if (frame < ini || (corte || seco ? frame >= fin : frame > fin + SALIDA)) return null;
  const viral = useEstilo().diseno === 'viral';
  // En «viral» las tomas reales van a pantalla completa y cambian en seco, sin el empujón de entrada.
  const Comp = (viral && PLANOS_VIRAL[pl.tipo]) || PLANOS[pl.tipo];
  if (!Comp) return null;
  const k = interpolate(f, [0, ENTRADA], [0, 1], {...CLAMP, easing: EXPO});
  const sale = seco ? 0 : interpolate(frame, [fin, fin + SALIDA], [0, 1], CLAMP);
  const est = i === 0 || pl.tipo === 'cierre' || viral ? {} : seco ? empujon(i, k) : entrada(typeof pl.transicion === 'string' ? pl.transicion : TRANSICIONES[(i - 1) % TRANSICIONES.length], k);
  const dur = fin - ini + (i === 0 ? 30 : 0);
  // «herramienta» coloca los planos como «cazzap» (debajo del titular fijo).
  const cazzap = ['cazzap', 'herramienta'].includes(useEstilo().diseno ?? '');
  return (
    <AbsoluteFill style={{...est, opacity: ((est.opacity as number) ?? 1) * (1 - sale),
      transform: `${est.transform ?? ''} scale(${1 - sale * 0.04})`}}>
      <Foco pl={pl} f={f} centro={seco ? CENTRO : 510} />
      {/* Dentro de su propia secuencia: así un vídeo del plano (una grabación de pantalla) empieza en el plano, no en el 0. */}
      {cazzap && CON_SOMBRA.has(pl.tipo) ? (
        <div style={{position: 'absolute', left: CENTRO - 330, top: HORIZONTE - 40, width: 660, height: 90, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(0,0,0,0.5) 0%, transparent 70%)', opacity: ramp(f, 0, 10)}} />
      ) : null}
      <AbsoluteFill style={seco && ESCALA_CAZZAP[pl.tipo] && !cazzap ? {transform: 'translateX(30px)'} : cazzap && ESCALA_CAZZAP[pl.tipo] ? {transformOrigin: '510px 930px',
        transform: `translateX(30px) translateY(${CON_SOMBRA.has(pl.tipo) ? 70 : -20}px) scale(${ESCALA_CAZZAP[pl.tipo]})`} : undefined}>
        <Sequence from={ini} layout="none">
          <Comp p={pl} f={f} dur={dur} fps={fps} />
        </Sequence>
      </AbsoluteFill>
      {typeof pl.fuente === 'string' && cazzap && pl.tipo !== 'cifra' ? (
        <div style={{position: 'absolute', left: CENTRO - 410, width: 820, top: 1250, textAlign: 'center', fontFamily, fontWeight: 500, fontSize: 27,
          color: 'rgba(255,255,255,0.5)'}}>Fuente · {pl.fuente}</div>
      ) : null}
      {typeof pl.fuente === 'string' && !cazzap ? (
        <div style={{position: 'absolute', left: (seco ? CENTRO : 455) - 395, width: 790, top: 1236, textAlign: 'center', fontFamily, fontWeight: 700, fontSize: 26,
          letterSpacing: 1, color: 'rgba(200,215,255,0.75)', textTransform: 'uppercase'}}>Fuente · {pl.fuente}</div>
      ) : null}
      {typeof pl.sello === 'string' ? <AbsoluteFill style={{transform: seco ? 'translateX(30px)' : undefined}}><Sello texto={pl.sello} f={f} fps={fps} dur={dur} abajo={pl.tipo === 'palabra'}
        en={Array.isArray(pl.golpes) && pl.golpes.length ? (pl.golpes as number[])[0] : undefined} /></AbsoluteFill> : null}
    </AbsoluteFill>
  );
};

/** Luz detrás de lo principal del plano: late cuando entra algo. */
const Foco: React.FC<{pl: Plano; f: number; centro: number}> = ({pl, f, centro}) => {
  const c = pl.tipo === 'robot' && typeof pl.quien === 'string' ? colorDe(pl.quien) : '#5a96ff';
  const late = 0; // la luz ya no late con cada golpe: un efecto a la vez
  const tam = 980 + 40 * ramp(f, 0, 30);
  return (
    <div style={{position: 'absolute', left: centro - tam / 2, top: 930 - tam / 2, width: tam, height: tam, borderRadius: '50%',
      background: `radial-gradient(circle, ${c}55 0%, ${c}22 38%, transparent 68%)`,
      opacity: 0.75 + late * 0.25}} />
  );
};

/** Destello claro en los cambios de plano marcados con «flash». */
const Flash: React.FC<{p: Props; frame: number; fps: number}> = ({p, frame, fps}) => {
  const pl = p.planos.find((x, i) => i > 0 && x.flash && frame >= x.inicio * fps && frame < x.inicio * fps + 4);
  if (!pl) return null;
  const k = (frame - pl.inicio * fps) / 4;
  return <AbsoluteFill style={{background: '#cfe0ff', opacity: 0.28 * (1 - k)}} />;
};

// ---------------------------------------------------------------- subtítulos

const grupos = (palabras: Palabra[]) => {
  const out: Palabra[][] = [];
  palabras.forEach((w) => {
    const g = out[out.length - 1];
    const corta = g && (g.length >= 3 || /[.,:;?!]$/.test(g[g.length - 1].texto) || w.t - g[g.length - 1].fin > 0.25);
    if (!g || corta) out.push([w]);
    else g.push(w);
  });
  return out;
};

/** Diseño «cazzap»: frases de hasta dos líneas arriba, que aparecen palabra a palabra; la palabra clave va en negrita y
 * «seleccionada» como en un editor de texto (recuadro fino y dos tiradores). El primer grupo sale entero desde el
 * fotograma 0: es la portada. */
const gruposArriba = (palabras: Palabra[]) => {
  const out: Palabra[][] = [];
  palabras.forEach((w) => {
    const g = out[out.length - 1];
    const letras = g ? g.reduce((s, x) => s + x.texto.length + 1, 0) : 0;
    const ultima = g ? g[g.length - 1].texto : '';
    // Se corta al acabar una frase, en una coma si ya hay 4 palabras, en una pausa larga o si no cabe en dos líneas.
    const corta = g && (letras + w.texto.length > 46 || /[.:;?!]$/.test(ultima) || (/[,]$/.test(ultima) && g.length >= 4)
      || (w.t - g[g.length - 1].fin > 0.45 && g.length >= 3));
    if (!g || corta) out.push([w]);
    else g.push(w);
  });
  // Un grupo no acaba en artículo, preposición o conjunción: esas palabras pasan al principio del siguiente.
  for (let i = 0; i < out.length - 1; i++) {
    while (out[i].length > 1 && ATADAS.has(out[i][out[i].length - 1].texto.toLowerCase())) out[i + 1].unshift(out[i].pop() as Palabra);
  }
  // Nada de una o dos palabras sueltas: se juntan con el grupo de al lado si caben en dos líneas.
  const largo = (g: Palabra[]) => g.reduce((s, x) => s + x.texto.length + 1, 0);
  for (let i = 0; i < out.length; i++) {
    if (out[i].length > 2 || out.length === 1) continue;
    const ant = out[i - 1], sig = out[i + 1];
    // El final de una frase se queda con su frase (aunque la apriete un poco), nunca con la siguiente.
    const cierra = /[.?!]$/.test(out[i][out[i].length - 1].texto);
    if (ant && largo(ant) + largo(out[i]) <= (cierra ? 58 : 50) && !/[.?!]$/.test(ant[ant.length - 1].texto)) { ant.push(...out[i]); out.splice(i, 1); i--; }
    else if (sig && !cierra && largo(sig) + largo(out[i]) <= 50) { sig.unshift(...out[i]); out.splice(i, 1); i--; }
  }
  return out;
};

const Seleccion: React.FC<{k: number; color: string; children: React.ReactNode}> = ({k, color, children}) => {
  const tirador = (estilo: React.CSSProperties) => (
    <span style={{position: 'absolute', width: 12, height: 12, borderRadius: 6, background: '#fff', border: `2.5px solid ${color}`,
      opacity: k, ...estilo}} />
  );
  return (
    <span style={{position: 'relative', display: 'inline-block', padding: '0 10px', margin: '0 -4px'}}>
      <span style={{position: 'absolute', inset: '2px 0', border: `2.5px solid ${color}`, background: `color-mix(in srgb, ${color} 22%, transparent)`,
        clipPath: `inset(0 ${(1 - k) * 100}% 0 0)`}} />
      {tirador({left: -6, top: -6})}
      {tirador({right: -6, bottom: -6})}
      <span style={{position: 'relative'}}>{children}</span>
    </span>
  );
};

const ATADAS = new Set(['a', 'al', 'de', 'del', 'el', 'la', 'los', 'las', 'lo', 'un', 'una', 'unos', 'unas', 'y', 'e', 'o', 'u', 'ni',
  'en', 'con', 'por', 'para', 'sin', 'que', 'se', 'su', 'sus', 'mi', 'tu', 'te', 'me', 'le', 'les', 'nos', 'no', 'muy', 'más', 'cada',
  'solo', 'ni']);
const unidades = (g: Palabra[]) => {
  const out: number[][] = [];
  g.forEach((w, i) => {
    const ant = out[out.length - 1];
    const prev = i ? g[i - 1].texto : '';
    if (ant && ATADAS.has(prev.toLowerCase()) ) ant.push(i);
    else out.push([i]);
  });
  return out;
};

const SubtitulosArriba: React.FC<{p: Props; t: number}> = ({p, t}) => {
  const gs = React.useMemo(() => gruposArriba(p.palabras), [p.palabras]);
  const g = t < (gs[0]?.[0]?.t ?? 0) ? gs[0] : gs.find((x, i) => t >= x[0].t - 0.04 && t < (gs[i + 1]?.[0].t ?? x[x.length - 1].fin + 0.6) - 0.04);
  if (!g) return null;
  const portada = g === gs[0];
  const color = p.estilo.subrayado;
  return (
    <>
    {/* Velo oscuro arriba: el subtítulo se lee también encima de una web blanca o de un clip claro. */}
    <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 560,
      background: 'linear-gradient(180deg, rgba(3,8,24,0.82) 0%, rgba(3,8,24,0.6) 55%, transparent 100%)'}} />
    <div style={{position: 'absolute', top: 190, left: CENTRO - 430, width: 860, textAlign: 'center', fontFamily, fontWeight: 500,
      fontSize: 66, lineHeight: 1.2, textWrap: 'balance', color: 'rgba(255,255,255,0.93)', textShadow: '0 2px 18px rgba(0,0,0,0.5)'}}>
      {unidades(g).map((u, j) => (
        // Un artículo, preposición o conjunción va pegado a la palabra siguiente: ninguna línea acaba en «de», «y» o «un».
        <span key={j} style={{display: 'inline-block', whiteSpace: 'nowrap'}}>
          {u.map((i) => {
            const w = g[i];
            // Las palabras atadas salen con la que las sostiene: nunca se queda «de una» esperando al final de la línea.
            const sostiene = g[u[u.length - 1]];
            const desde = Math.max(w.t, sostiene.t);
            const dentro = portada || t >= desde - 0.04;
            const k = portada && t < desde ? 1 : interpolate(t, [desde - 0.04, desde + 0.14], [0, 1], {...CLAMP, easing: EXPO});
            const [, nucleo, signo] = /^(.*?)([.,:;?!»]*)$/.exec(w.texto) ?? ['', w.texto, ''];
            const palabra = <span style={{fontWeight: w.enfasis ? 800 : 500, color: '#fff'}}>{w.enfasis ? nucleo : w.texto}</span>;
            // La frase entera está desde el principio, centrada y quieta; lo que aún no se ha dicho, al 35 %.
            return (
              <span key={i} style={{display: 'inline-block', margin: '0 8px', opacity: dentro ? 1 : 0.35,
                transform: `translateY(${dentro ? (1 - k) * 6 : 0}px)`}}>
                {w.enfasis ? <><Seleccion k={k} color={color}>{palabra}</Seleccion>{signo}</> : palabra}
              </span>
            );
          })}
        </span>
      ))}
    </div>
    </>
  );
};

export const Subtitulos: React.FC<{p: Props; t: number; centro?: number}> = ({p, t, centro = CX}) => {
  if (p.estilo.diseno === 'cazzap') return <SubtitulosArriba p={p} t={t} />;
  if (p.estilo.diseno === 'viral') return <RotuloViral p={p} t={t} fps={30} />;
  if (p.estilo.diseno === 'herramienta') return <><RotuloAbajo p={p} t={t} fps={30} /><MascotaOrby p={p} t={t} fps={30} Robot={Robot} /></>;
  const gs = React.useMemo(() => grupos(p.palabras), [p.palabras]);
  const g = gs.find((x) => t >= x[0].t - 0.04 && t < x[x.length - 1].fin + 0.12);
  if (!g) return null;
  return (
    <div style={{position: 'absolute', top: 1300, left: centro - ANCHO / 2, width: ANCHO, textAlign: 'center', fontFamily, fontWeight: 900,
      fontSize: 72, lineHeight: 1.08, color: '#fff', textShadow: sombraTexto}}>
      {g.map((w, i) => {
        const dentro = t >= w.t - 0.04;
        const s = interpolate(t, [w.t - 0.04, w.t + 0.08], [0.92, 1], {...CLAMP, easing: EXPO});
        const extra = w.enfasis ? interpolate(t, [w.t, w.t + 0.1], [1, 1.06], {...CLAMP, easing: EXPO}) : 1;
        return (
          <span key={i} style={{display: 'inline-block', margin: '0 11px', transformOrigin: '50% 80%',
            color: w.enfasis && dentro ? p.estilo.subrayado : '#ffffff',
            // En el explicativo la frase entera se ve desde el principio (al 35 %), para que el bloque no se mueva.
            transform: `scale(${(dentro ? s : 1) * extra})`, opacity: dentro ? 1 : centro === CENTRO ? 0.35 : 0,
          }}>{w.texto}</span>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- cámara

const camara = (p: Props, frame: number, fps: number) => {
  const t = frame / fps;
  const pl = p.planos.find((x) => t >= x.inicio && t < x.fin);
  const k = pl ? (t - pl.inicio) / Math.max(0.1, pl.fin - pl.inicio) : 0;
  // Sin sacudida en cada énfasis (un efecto a la vez): solo el empujón lento de cada plano.
  const sx = 0, sy = 0, rot = 0;
  return `translate(${sx}px, ${sy}px) rotate(${rot}deg) scale(${1 + 0.035 * k})`;
};

export const Explicativo: React.FC<Props> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return (
    <ConMarca estilo={p.estilo}>
      <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
        <Fondo f={frame} p={p} />
        <AbsoluteFill style={{transform: camara(p, frame, fps), transformOrigin: `${CENTRO}px 900px`}}>
          {p.planos.map((pl, i) => <PlanoVivo key={i} pl={pl} i={i} frame={frame} fps={fps} corte={p.planos[i + 1]?.tipo === 'cierre'} seco />)}
        </AbsoluteFill>
        <Titulo p={p} f={frame} fps={fps} />
        <Rotulos p={p} t={t} fps={fps} />
        <Subtitulos p={p} t={t} centro={CENTRO} />
        <Flash p={p} frame={frame} fps={fps} />
        {p.audio ? <Audio src={staticFile(p.audio)} /> : null}
      </AbsoluteFill>
    </ConMarca>
  );
};
