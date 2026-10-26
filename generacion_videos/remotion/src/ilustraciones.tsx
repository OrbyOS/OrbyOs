import React from 'react';

/**
 * Catálogo de ilustraciones dibujadas en código (SVG, lienzo de 400×400). Genéricas: objetos de trabajo de un
 * negocio de una persona, en tonos azules (los de Orby). Para un nicho nuevo se añaden aquí; el guion las pide por su nombre.
 */
const contorno = 'rgba(10, 20, 50, 0.5)';

const Lupa = () => (
  <g>
    <rect x="232" y="236" width="44" height="140" rx="20" transform="rotate(-45 254 306)" fill="#2b2f3a" />
    <rect x="236" y="236" width="14" height="120" rx="7" transform="rotate(-45 254 306)" fill="#4a5163" />
    <circle cx="170" cy="170" r="118" fill="#3a3f4d" />
    <circle cx="170" cy="170" r="96" fill="#cfe6ff" />
    <circle cx="170" cy="170" r="96" fill="url(#brillo)" />
    <path d="M110 128 Q130 92 172 86" stroke="#fff" strokeWidth="14" strokeLinecap="round" fill="none" opacity="0.8" />
  </g>
);

const Libreta = () => (
  <g>
    <rect x="70" y="56" width="250" height="300" rx="16" fill="#eef2fb" stroke={contorno} strokeWidth="3" />
    <rect x="70" y="56" width="34" height="300" rx="12" fill="#3D7BFF" />
    {[0, 1, 2, 3, 4, 5, 6].map((i) => (
      <rect key={i} x="128" y={110 + i * 34} width={i === 6 ? 90 : 160} height="8" rx="4" fill="#a9b8d8" />
    ))}
    <g transform="rotate(32 300 250)">
      <rect x="282" y="110" width="30" height="210" rx="6" fill="#7fa8ff" />
      <rect x="282" y="110" width="30" height="26" rx="6" fill="#c9d8ff" />
      <rect x="282" y="132" width="30" height="10" fill="#c9c9c9" />
      <path d="M282 320 L297 362 L312 320 Z" fill="#e6ecfa" />
      <path d="M292 348 L297 362 L302 348 Z" fill="#2b2f3a" />
    </g>
  </g>
);

const Claqueta = () => (
  <g>
    <rect x="70" y="170" width="260" height="180" rx="14" fill="#23262f" />
    <rect x="96" y="214" width="208" height="10" rx="5" fill="#5b6172" />
    <rect x="96" y="250" width="150" height="10" rx="5" fill="#5b6172" />
    <rect x="96" y="286" width="180" height="10" rx="5" fill="#5b6172" />
    <g transform="rotate(-16 76 166)">
      <rect x="70" y="118" width="264" height="50" rx="8" fill="#23262f" />
      {[0, 1, 2, 3, 4].map((i) => (
        <path key={i} d={`M${92 + i * 52} 118 L${122 + i * 52} 118 L${100 + i * 52} 168 L${70 + i * 52} 168 Z`} fill="#eef2fb" />
      ))}
    </g>
    <circle cx="76" cy="168" r="10" fill="#8a90a0" />
  </g>
);

const Movil = () => (
  <g>
    <rect x="112" y="40" width="176" height="330" rx="30" fill="#1d2029" />
    <rect x="124" y="58" width="152" height="294" rx="20" fill="url(#pantalla)" />
    <rect x="176" y="48" width="48" height="8" rx="4" fill="#3a3f4d" />
    <circle cx="200" cy="200" r="34" fill="rgba(255,255,255,0.88)" />
    <path d="M190 182 L218 200 L190 218 Z" fill="#3D7BFF" />
    <path d="M250 270 c-10-14-30-4-20 12 l20 18 l20-18 c10-16-10-26-20-12z" fill="#9cc4ff" />
    <rect x="140" y="320" width="80" height="8" rx="4" fill="rgba(255,255,255,0.7)" />
  </g>
);

const Reloj = () => (
  <g>
    <circle cx="120" cy="96" r="40" fill="#3D7BFF" />
    <circle cx="280" cy="96" r="40" fill="#3D7BFF" />
    <rect x="116" y="320" width="22" height="50" rx="10" transform="rotate(30 127 345)" fill="#1a3a8a" />
    <rect x="262" y="320" width="22" height="50" rx="10" transform="rotate(-30 273 345)" fill="#1a3a8a" />
    <circle cx="200" cy="210" r="140" fill="#3D7BFF" />
    <circle cx="200" cy="210" r="116" fill="#f5f8ff" />
    {Array.from({length: 12}).map((_, i) => (
      <rect key={i} x="196" y="104" width="8" height={i % 3 === 0 ? 22 : 12} rx="4" fill="#2b2f3a" transform={`rotate(${i * 30} 200 210)`} />
    ))}
    <rect x="194" y="140" width="12" height="76" rx="6" fill="#2b2f3a" />
    <rect x="194" y="200" width="12" height="62" rx="6" fill="#2b2f3a" transform="rotate(120 200 210)" />
    <circle cx="200" cy="210" r="12" fill="#3D7BFF" />
  </g>
);

const Portatil = () => (
  <g>
    <rect x="74" y="80" width="252" height="176" rx="14" fill="#2b2f3a" />
    <rect x="88" y="94" width="224" height="148" rx="6" fill="url(#pantalla)" />
    <rect x="108" y="118" width="120" height="12" rx="6" fill="rgba(255,255,255,0.8)" />
    <rect x="108" y="146" width="170" height="10" rx="5" fill="rgba(255,255,255,0.45)" />
    <rect x="108" y="168" width="150" height="10" rx="5" fill="rgba(255,255,255,0.45)" />
    <rect x="108" y="190" width="90" height="26" rx="13" fill="#7fa8ff" />
    <path d="M40 262 L360 262 L338 300 L62 300 Z" fill="#9aa1b2" />
    <rect x="170" y="262" width="60" height="10" rx="5" fill="#7d8496" />
  </g>
);

const Taza = () => (
  <g>
    <ellipse cx="200" cy="330" rx="130" ry="26" fill="rgba(0,0,0,0.25)" />
    <path d="M300 170 c70 0 70 110 0 110" stroke="#eef2fb" strokeWidth="26" fill="none" />
    <path d="M90 140 L310 140 L290 320 Q200 345 110 320 Z" fill="#eef2fb" stroke={contorno} strokeWidth="3" />
    <ellipse cx="200" cy="140" rx="110" ry="26" fill="#1b2a55" />
    <ellipse cx="200" cy="140" rx="110" ry="26" fill="none" stroke="#eef2fb" strokeWidth="10" />
    <path d="M160 100 q-20-30 0-60 M210 100 q-20-30 0-60" stroke="rgba(255,255,255,0.6)" strokeWidth="10" strokeLinecap="round" fill="none" />
  </g>
);

const Calendario = () => (
  <g>
    <rect x="70" y="80" width="260" height="270" rx="18" fill="#f5f8ff" stroke={contorno} strokeWidth="3" />
    <rect x="70" y="80" width="260" height="64" rx="18" fill="#3D7BFF" />
    <rect x="70" y="120" width="260" height="24" fill="#3D7BFF" />
    <rect x="120" y="56" width="16" height="50" rx="8" fill="#2b2f3a" />
    <rect x="264" y="56" width="16" height="50" rx="8" fill="#2b2f3a" />
    {Array.from({length: 15}).map((_, i) => (
      <rect key={i} x={96 + (i % 5) * 44} y={166 + Math.floor(i / 5) * 56} width="32" height="32" rx="8"
        fill={i === 7 ? '#3D7BFF' : '#dbe4f5'} />
    ))}
  </g>
);

export const ILUSTRACIONES: Record<string, React.FC> = {
  lupa: Lupa, libreta: Libreta, claqueta: Claqueta, movil: Movil, reloj: Reloj, portatil: Portatil, taza: Taza,
  calendario: Calendario,
};

/** Degradados compartidos por todas las ilustraciones. */
export const Defs = () => (
  <defs>
    <radialGradient id="brillo" cx="35%" cy="30%" r="75%">
      <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
      <stop offset="1" stopColor="#7fb2ff" stopOpacity="0.15" />
    </radialGradient>
    <linearGradient id="pantalla" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stopColor="#5b8fff" />
      <stop offset="1" stopColor="#2b4fd6" />
    </linearGradient>
  </defs>
);

/** Lápiz y bolígrafo que enmarcan la mesa, como los cubiertos de un plato. */
export const Marco = () => (
  <svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0}}>
    <g opacity="0.95">
      <rect x="70" y="560" width="30" height="560" rx="8" fill="#7fa8ff" />
      <rect x="70" y="560" width="30" height="40" rx="8" fill="#c9d8ff" />
      <path d="M70 1120 L85 1180 L100 1120 Z" fill="#e6ecfa" />
      <rect x="985" y="540" width="26" height="600" rx="13" fill="#2b2f3a" />
      <rect x="989" y="560" width="8" height="200" rx="4" fill="#5b6172" />
      <path d="M985 1140 L998 1196 L1011 1140 Z" fill="#9aa1b2" />
    </g>
  </svg>
);
