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


const Bombilla = () => (
  <g>
    <circle cx="200" cy="160" r="150" fill="url(#halo)" />
    <path d="M200 40 C120 40 80 100 80 160 C80 210 110 240 135 270 L135 300 L265 300 L265 270 C290 240 320 210 320 160 C320 100 280 40 200 40 Z" fill="#fff6c9" stroke={contorno} strokeWidth="3" />
    <path d="M120 150 C125 100 160 75 195 70" stroke="#fff" strokeWidth="16" strokeLinecap="round" fill="none" opacity="0.9" />
    <path d="M170 300 L170 220 Q200 190 230 220 L230 300" stroke="#f2b632" strokeWidth="8" fill="none" />
    <rect x="135" y="300" width="130" height="24" rx="8" fill="#9aa1b2" />
    <rect x="145" y="324" width="110" height="22" rx="8" fill="#7d8496" />
    <rect x="160" y="346" width="80" height="22" rx="10" fill="#5b6172" />
  </g>
);

const Microfono = () => (
  <g>
    <rect x="140" y="40" width="120" height="190" rx="60" fill="#2b2f3a" />
    {[0, 1, 2, 3, 4].map((i) => <rect key={i} x="150" y={70 + i * 30} width="100" height="8" rx="4" fill="#4a5163" />)}
    <path d="M165 60 Q180 48 205 46" stroke="#fff" strokeWidth="10" strokeLinecap="round" fill="none" opacity="0.4" />
    <path d="M100 170 Q100 280 200 280 Q300 280 300 170" stroke="#9aa1b2" strokeWidth="18" fill="none" strokeLinecap="round" />
    <rect x="190" y="280" width="20" height="70" fill="#9aa1b2" />
    <rect x="130" y="345" width="140" height="22" rx="11" fill="#7d8496" />
    <circle cx="300" cy="80" r="16" fill="#3D7BFF" />
  </g>
);

const Sobre = () => (
  <g>
    <rect x="60" y="100" width="280" height="200" rx="18" fill="#eef2fb" stroke={contorno} strokeWidth="3" />
    <path d="M66 110 L200 220 L334 110" stroke="#a9b8d8" strokeWidth="10" fill="none" strokeLinejoin="round" />
    <path d="M66 292 L165 200 M334 292 L235 200" stroke="#c9d3ec" strokeWidth="6" />
    <circle cx="320" cy="104" r="40" fill="#ff5d73" stroke="#fff" strokeWidth="6" />
    <text x="320" y="120" textAnchor="middle" fontSize="44" fontWeight="900" fill="#fff" fontFamily="system-ui">1</text>
  </g>
);

const Tijeras = () => (
  <g>
    <g transform="rotate(-20 200 200)">
      <path d="M200 190 L340 80" stroke="#c9d3ec" strokeWidth="26" strokeLinecap="round" />
      <path d="M200 210 L340 320" stroke="#dbe4f5" strokeWidth="26" strokeLinecap="round" />
      <circle cx="120" cy="140" r="56" fill="none" stroke="#3D7BFF" strokeWidth="26" />
      <circle cx="120" cy="260" r="56" fill="none" stroke="#3D7BFF" strokeWidth="26" />
      <circle cx="200" cy="200" r="12" fill="#5b6172" />
    </g>
  </g>
);

const Cohete = () => (
  <g transform="rotate(30 200 200)">
    <path d="M170 300 Q200 380 230 300 Z" fill="#9cc4ff" />
    <path d="M182 300 Q200 350 218 300 Z" fill="#fff" />
    <path d="M200 30 C260 80 270 180 250 300 L150 300 C130 180 140 80 200 30 Z" fill="#eef2fb" stroke={contorno} strokeWidth="3" />
    <circle cx="200" cy="150" r="34" fill="#3D7BFF" stroke="#fff" strokeWidth="10" />
    <path d="M150 230 L100 300 L150 290 Z M250 230 L300 300 L250 290 Z" fill="#3D7BFF" />
    <path d="M200 30 C230 55 245 85 252 115 L148 115 C155 85 170 55 200 30 Z" fill="#3D7BFF" />
  </g>
);

const Diana = () => (
  <g>
    {[150, 115, 80, 45].map((r, i) => <circle key={r} cx="190" cy="210" r={r} fill={i % 2 ? '#eef2fb' : '#3D7BFF'} stroke="#fff" strokeWidth="4" />)}
    <path d="M190 210 L350 60" stroke="#2b2f3a" strokeWidth="10" strokeLinecap="round" />
    <path d="M330 50 L370 40 L360 80 Z" fill="#9cc4ff" />
  </g>
);

const Corazon = () => (
  <g>
    <path d="M200 340 C60 250 40 160 90 110 C140 60 190 90 200 130 C210 90 260 60 310 110 C360 160 340 250 200 340 Z" fill="#ff5d73" stroke="#fff" strokeWidth="8" />
    <path d="M110 140 Q120 100 160 100" stroke="#fff" strokeWidth="14" strokeLinecap="round" fill="none" opacity="0.6" />
  </g>
);

const Avion = () => (
  <g>
    <path d="M40 200 L360 60 L280 340 L200 250 Z" fill="#eef2fb" stroke={contorno} strokeWidth="3" strokeLinejoin="round" />
    <path d="M200 250 L360 60 L170 300 Z" fill="#c9d3ec" />
    <path d="M200 250 L360 60" stroke="#a9b8d8" strokeWidth="4" />
  </g>
);

const Ojo = () => (
  <g>
    <path d="M30 200 Q200 40 370 200 Q200 360 30 200 Z" fill="#eef2fb" stroke={contorno} strokeWidth="3" />
    <circle cx="200" cy="200" r="90" fill="#3D7BFF" />
    <circle cx="200" cy="200" r="44" fill="#0b1640" />
    <circle cx="230" cy="170" r="18" fill="#fff" />
  </g>
);

const Candado = () => (
  <g>
    <path d="M120 180 L120 130 Q120 50 200 50 Q280 50 280 130 L280 180" stroke="#9aa1b2" strokeWidth="34" fill="none" />
    <rect x="80" y="170" width="240" height="190" rx="28" fill="#3D7BFF" />
    <rect x="80" y="170" width="240" height="40" rx="20" fill="#5b8fff" />
    <circle cx="200" cy="255" r="26" fill="#0b1640" />
    <rect x="190" y="265" width="20" height="50" rx="8" fill="#0b1640" />
  </g>
);

const Creador = () => (
  <g>
    <rect x="292" y="70" width="10" height="290" rx="5" fill="#5b6172" />
    <circle cx="297" cy="70" r="52" fill="none" stroke="#eef2fb" strokeWidth="16" />
    <circle cx="297" cy="70" r="52" fill="none" stroke="#9cc4ff" strokeWidth="5" opacity="0.8" />
    <path d="M70 380 C70 290 110 250 165 250 C220 250 260 290 260 380 Z" fill="#3D7BFF" />
    <path d="M140 250 L165 290 L190 250 Z" fill="#eef2fb" />
    <rect x="150" y="215" width="30" height="40" rx="10" fill="#f1c7a8" />
    <ellipse cx="165" cy="170" rx="58" ry="64" fill="#f6d2b6" />
    <path d="M105 160 C100 100 140 90 165 92 C200 92 232 108 226 160 C215 128 190 120 165 122 C135 122 115 135 105 160 Z" fill="#2b2f3a" />
    <circle cx="145" cy="175" r="7" fill="#2b2f3a" /><circle cx="186" cy="175" r="7" fill="#2b2f3a" />
    <path d="M150 205 Q166 216 182 205" stroke="#2b2f3a" strokeWidth="6" fill="none" strokeLinecap="round" />
    <rect x="232" y="232" width="56" height="96" rx="12" fill="#1d2029" transform="rotate(12 260 280)" />
    <path d="M250 300 L232 262" stroke="#f6d2b6" strokeWidth="22" strokeLinecap="round" />
  </g>
);

const Barras = () => (
  <g>
    <rect x="50" y="60" width="300" height="290" rx="26" fill="#eef2fb" stroke={contorno} strokeWidth="3" />
    <rect x="95" y="230" width="44" height="80" rx="10" fill="#9cc4ff" />
    <rect x="178" y="180" width="44" height="130" rx="10" fill="#5b8fff" />
    <rect x="261" y="110" width="44" height="200" rx="10" fill="#3D7BFF" />
    <path d="M90 210 L190 160 L280 90" stroke="#0b1640" strokeWidth="8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M262 82 L294 80 L288 112 Z" fill="#0b1640" />
  </g>
);

const Calculadora = () => (
  <g>
    <rect x="90" y="40" width="220" height="320" rx="30" fill="#2b2f3a" />
    <rect x="112" y="64" width="176" height="74" rx="12" fill="#cfe6ff" />
    <text x="276" y="120" textAnchor="end" fontSize="48" fontWeight="800" fill="#0b1640" fontFamily="system-ui">2:40</text>
    {[0, 1, 2, 3].map((r) => [0, 1, 2].map((c) => (
      <rect key={`${r}${c}`} x={114 + c * 60} y={160 + r * 48} width="50" height="38" rx="9"
        fill={c === 2 ? '#3D7BFF' : '#4a5163'} />
    )))}
  </g>
);

export const ILUSTRACIONES: Record<string, React.FC> = {
  lupa: Lupa, libreta: Libreta, claqueta: Claqueta, movil: Movil, reloj: Reloj, portatil: Portatil, taza: Taza,
  calendario: Calendario, bombilla: Bombilla, microfono: Microfono, sobre: Sobre, tijeras: Tijeras, cohete: Cohete,
  diana: Diana, corazon: Corazon, avion: Avion, ojo: Ojo, candado: Candado, creador: Creador, barras: Barras,
  calculadora: Calculadora,
};

/** Degradados compartidos por todas las ilustraciones. */
export const Defs = () => (
  <defs>
    <radialGradient id="brillo" cx="35%" cy="30%" r="75%">
      <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
      <stop offset="1" stopColor="#7fb2ff" stopOpacity="0.15" />
    </radialGradient>
    <radialGradient id="halo" cx="50%" cy="50%" r="50%">
      <stop offset="0" stopColor="#fff3a0" stopOpacity="0.55" />
      <stop offset="1" stopColor="#fff3a0" stopOpacity="0" />
    </radialGradient>
    <linearGradient id="pantalla" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stopColor="#5b8fff" />
      <stop offset="1" stopColor="#2b4fd6" />
    </linearGradient>
  </defs>
);
