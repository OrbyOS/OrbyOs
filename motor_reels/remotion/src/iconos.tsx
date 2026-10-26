import React from 'react';

/**
 * Iconos de línea propios (24×24, trazo redondeado), dibujados para el motor: nada de emoticonos ni de bancos de
 * iconos. Pocos y genéricos a propósito; si hace falta uno nuevo, se añade aquí y en ICONOS de validar.py.
 */
const TRAZOS: Record<string, React.ReactNode> = {
  idea: (<>
    <path d="M9 18h6M10 21h4" />
    <path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z" />
  </>),
  rayo: <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z" />,
  check: (<><circle cx="12" cy="12" r="9" /><path d="m8 12.5 2.8 2.8L16.5 9.5" /></>),
  dinero: (<>
    <circle cx="12" cy="12" r="9" />
    <path d="M15.5 8.6A4 4 0 0 0 9 10.5v3a4 4 0 0 0 6.5 1.9M7.5 11h5M7.5 13.5h5" />
  </>),
  reloj: (<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></>),
  subida: (<><path d="M3 17l6-6 4 4 8-8" /><path d="M15 7h6v6" /></>),
  persona: (<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>),
  equipo: (<>
    <circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <circle cx="17" cy="9" r="2.8" /><path d="M16 14.2A5.5 5.5 0 0 1 21.5 20" />
  </>),
  chat: <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />,
  codigo: <path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" />,
  ia: (<>
    <rect x="5" y="8" width="14" height="11" rx="2.5" />
    <path d="M12 8V4.5M10 4.5h4M9.5 13v.5M14.5 13v.5M9.5 16.5h5M3 12.5v3M21 12.5v3" />
  </>),
  cohete: (<>
    <path d="M12 2.5c3 2 4.5 5.5 4.5 9.5l-2 4h-5l-2-4c0-4 1.5-7.5 4.5-9.5z" />
    <circle cx="12" cy="9.5" r="1.6" /><path d="M9.5 16l-2.5 3M14.5 16l2.5 3M12 17v4" />
  </>),
  objetivo: (<><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.2" /></>),
  mundo: (<><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" /></>),
  candado: (<><rect x="5" y="10.5" width="14" height="10" rx="2" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3M12 14.5v2.5" /></>),
  flecha: <path d="M4 12h15M13 6l6 6-6 6" />,
  negocio: (<><rect x="3" y="7.5" width="18" height="12" rx="2" /><path d="M9 7.5V5.5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5.5v2M3 13h18" /></>),
  chispa: (<><path d="M12 3v5M12 16v5M3 12h5M16 12h5" /><path d="M6.5 6.5l2 2M15.5 15.5l2 2M17.5 6.5l-2 2M8.5 15.5l-2 2" /></>),
};

export const NOMBRES_ICONOS = Object.keys(TRAZOS);

export const Icono: React.FC<{nombre: string; tam: number; color: string; grosor?: number}> = ({nombre, tam, color, grosor = 1.6}) => (
  <svg width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={grosor}
       strokeLinecap="round" strokeLinejoin="round">
    {TRAZOS[nombre] ?? TRAZOS.chispa}
  </svg>
);
