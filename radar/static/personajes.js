/* Los muñequitos del equipo: una sola familia, la del director. Cuerpo de porcelana en forma de huevo, cabeza con
   visor negro y ojos grandes que brillan, anillo de luz en el cuello y brazos que flotan. Cada agente se distingue por
   el color de sus ojos y de su luz, y por lo que lleva en la mano; el director (jefa) va limpio, como en la marca.
   RadarEquipo.robot(clave) devuelve el SVG. En cualquier página, un <span data-robot="analista"> se rellena solo. */
(function () {
  "use strict";
  var COLORES = { jefa: "#3D7BFF", analista: "#22D3EE", estratega: "#FBBF24", guionista: "#F472B6",
                  editor: "#34D399", publicador: "#A78BFA", comunidad: "#FB7185" };
  var n = 0;  // para que los degradados de cada muñeco tengan su propio id
  // Un tono más claro del color, para el anillo de luz del iris.
  function claro(c) {
    var x = c.replace("#", ""), r = [0, 2, 4].map(function (i) { return parseInt(x.substr(i, 2), 16); });
    return "#" + r.map(function (v) { return ("0" + Math.round(v + (255 - v) * 0.55).toString(16)).slice(-2); }).join("");
  }

  // Lo que lleva cada uno, junto a la mano derecha (lienzo de 100 × 120).
  var ACCESORIO = {
    analista: '<g class="r-cosa"><line x1="84" y1="96" x2="89" y2="89" stroke="#d9d4cb" stroke-width="3.5" stroke-linecap="round"/>' +
      '<circle cx="93" cy="83" r="8" fill="rgba(200,240,255,.3)" stroke="#f4f1ec" stroke-width="2.6"/><circle cx="90.5" cy="80.5" r="2.2" fill="#fff" opacity=".85"/></g>',
    estratega: '<g class="r-cosa"><rect x="80" y="78" width="18" height="24" rx="3" fill="#fffaf0" stroke="#d9c39a" stroke-width="1.6"/>' +
      '<rect x="85" y="75.5" width="8" height="4.5" rx="2" fill="#c9a35c"/><path d="M84 86h10M84 90.5h10M84 95h7" stroke="#e0b766" stroke-width="1.8" stroke-linecap="round"/></g>',
    guionista: '<g class="r-cosa" transform="rotate(-32 90 90)"><rect x="86.5" y="72" width="7" height="27" rx="2" fill="#fbcfe8"/>' +
      '<rect x="86.5" y="72" width="7" height="5" rx="2" fill="#f472b6"/><path d="M86.5 99l3.5 7 3.5-7z" fill="#f3dcc0"/><path d="M89.2 104l.8 2.2.8-2.2z" fill="#2b2b33"/></g>',
    editor: '<g class="r-cosa"><rect x="79" y="84" width="22" height="16" rx="3" fill="#1d2027"/>' +
      '<g class="r-claqueta"><rect x="79" y="77" width="22" height="7" rx="2" fill="#f7f5f1"/><path d="M83 77l3.5 7M90 77l3.5 7M97 77l3 6" stroke="#1d2027" stroke-width="2.6"/></g>' +
      '<circle cx="90" cy="92" r="2.8" fill="#34d399"/></g>',
    publicador: '<g class="r-cosa"><path d="M77 88l25-11-8 23-5.5-8z" fill="#fbfaf8" stroke="#c4b5fd" stroke-width="1.4" stroke-linejoin="round"/>' +
      '<path d="M88.5 92l13.5-15" stroke="#c4b5fd" stroke-width="1.4"/></g>',
    comunidad: '<g class="r-cosa"><path d="M74 4h24a8 8 0 0 1 8 8v7a8 8 0 0 1-8 8h-14l-7 6v-6h-3a8 8 0 0 1-8-8v-7a8 8 0 0 1 8-8z" fill="#fbfaf8" stroke="#fda4af" stroke-width="1.4"/>' +
      '<path d="M86 11c-1.6-2.5-5.8-1.5-4.8 1.7.6 2 4.8 4.8 4.8 4.8s4.2-2.8 4.8-4.8c1-3.2-3.2-4.2-4.8-1.7z" fill="#fb7185"/></g>',
    jefa: ""
  };

  function robot(clave, opciones) {
    var c = COLORES[clave] || "#3D7BFF", o = opciones || {}, id = "r" + (++n) + "-";
    var defs =
      '<defs>' +
        // Porcelana: blanco cálido con la luz arriba a la izquierda.
        '<radialGradient id="' + id + 'p" cx="36%" cy="28%" r="78%"><stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#f3efe8"/><stop offset="1" stop-color="#d9d2c6"/></radialGradient>' +
        // El visor: negro brillante, con un reflejo arriba.
        '<linearGradient id="' + id + 'v" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a2d36"/><stop offset=".35" stop-color="#0b0c10"/><stop offset="1" stop-color="#000"/></linearGradient>' +
        // El iris: claro en el centro, el color del agente y oscuro en el borde.
        '<radialGradient id="' + id + 'i" cx="50%" cy="55%" r="55%"><stop offset="0" stop-color="#0a1230"/><stop offset=".38" stop-color="#0a1230"/>' +
          '<stop offset=".44" stop-color="' + c + '"/><stop offset=".66" stop-color="' + claro(c) + '"/><stop offset=".86" stop-color="' + c + '"/><stop offset="1" stop-color="#0b1a44"/></radialGradient>' +
        '<radialGradient id="' + id + 'g" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="' + c + '" stop-opacity=".75"/><stop offset="1" stop-color="' + c + '" stop-opacity="0"/></radialGradient>' +
        // Volumen: la porcelana se oscurece hacia abajo, como con luz cenital.
        '<linearGradient id="' + id + 'b" x1="0" y1="0" x2="0" y2="1"><stop offset=".45" stop-color="#5b4a32" stop-opacity="0"/><stop offset="1" stop-color="#5b4a32" stop-opacity=".22"/></linearGradient>' +
      '</defs>';
    var ojo = function (x) {
      return '<g class="r-ojo">' +
        '<circle cx="' + x + '" cy="35" r="9.6" fill="#05060a" stroke="#2c3040" stroke-width="1"/>' +
        '<circle cx="' + x + '" cy="35" r="8.2" fill="url(#' + id + 'i)"/>' +
        '<circle cx="' + x + '" cy="35" r="8.2" fill="none" stroke="' + c + '" stroke-opacity=".55" stroke-width=".8"/>' +
        '<circle cx="' + (x + 2.6) + '" cy="31.6" r="2" fill="#fff"/><circle cx="' + (x - 2.4) + '" cy="38.4" r=".9" fill="#fff" opacity=".7"/></g>';
    };
    var cabeza =
      '<g class="r-cabeza"><g transform="rotate(-5 50 40)">' +
        // Brillo del anillo del cuello, que asoma bajo la cabeza.
        '<ellipse class="r-luz" cx="50" cy="61" rx="15" ry="5" fill="url(#' + id + 'g)"/>' +
        '<ellipse cx="50" cy="31.5" rx="31.5" ry="27.5" fill="url(#' + id + 'p)"/>' +
        '<path d="M26 18a30 26 0 0 1 22-11" stroke="#fff" stroke-width="2.4" stroke-linecap="round" fill="none" opacity=".9"/>' +
        '<path d="M73 14c4 5 6 10 6 16" stroke="#cfc7ba" stroke-width="1" fill="none" opacity=".8"/>' +
        '<ellipse cx="50" cy="31.5" rx="31.5" ry="27.5" fill="url(#' + id + 'b)"/>' +
        // Perfil de luz del color del agente, por la derecha.
        '<path d="M79.5 22c2.6 5.5 3.4 12 2 18.5" stroke="' + c + '" stroke-opacity=".45" stroke-width="1.4" stroke-linecap="round" fill="none"/>' +
        '<path d="M21.5 35c0-11 12.5-18 28.5-18s28.5 7 28.5 18-12.5 16-28.5 16-28.5-5-28.5-16z" fill="url(#' + id + 'v)" stroke="#000" stroke-width="1.8"/>' +
        '<path d="M31 24.5c5-3.5 12-5 19-5" stroke="#fff" stroke-opacity=".22" stroke-width="2" stroke-linecap="round" fill="none"/>' +
        // El brillo de los ojos dentro del visor y su reflejo abajo.
        '<ellipse class="r-brillo" cx="39" cy="35" rx="13" ry="12" fill="url(#' + id + 'g)" opacity=".7"/><ellipse class="r-brillo" cx="61" cy="35" rx="13" ry="12" fill="url(#' + id + 'g)" opacity=".7"/>' +
        '<path d="M30 46.5c6 2.6 13 3.6 20 3.6s14-1 20-3.6" stroke="' + c + '" stroke-opacity=".28" stroke-width="1.2" stroke-linecap="round" fill="none"/>' +
        '<g class="r-ojos">' + ojo(39) + ojo(61) + '</g>' +
        // Dormido: los ojos cerrados, en arco.
        '<g class="r-cerrados" stroke="' + c + '" stroke-width="2.2" stroke-linecap="round" fill="none"><path d="M33 36q6 4.5 12 0"/><path d="M55 36q6 4.5 12 0"/></g>' +
        '<path class="r-sonrisa" d="M47 44.4q3 2.2 6 0" stroke="' + c + '" stroke-width="1.8" stroke-linecap="round" fill="none"/>' +
        '<ellipse class="r-boca" cx="50" cy="45" rx="3" ry="1.8" fill="' + c + '"/>' +
      '</g>' +
        '<g class="r-zz" fill="#c9d3ef" font-weight="800" font-family="system-ui, sans-serif"><text x="80" y="10" font-size="12">z</text><text x="89" y="1" font-size="8">z</text></g>' +
      '</g>';
    var cuerpo = o.cabeza ? "" :
      '<g class="r-brazo r-brazo-izq"><path d="M23 68c-4 6-6 15-4 25 1 4 4 3 5-1 2-8 3-16 3-23 0-3-2-4-4-1z" fill="url(#' + id + 'p)" stroke="#d6cfc3" stroke-width=".6"/></g>' +
      '<g class="r-brazo r-brazo-der"><path d="M77 68c4 6 6 15 4 25-1 4-4 3-5-1-2-8-3-16-3-23 0-3 2-4 4-1z" fill="url(#' + id + 'p)" stroke="#d6cfc3" stroke-width=".6"/></g>' +
      // El anillo de luz del cuello.
      '<ellipse cx="50" cy="60.5" rx="10.5" ry="2.6" fill="' + c + '"/><ellipse cx="50" cy="60" rx="7" ry="1.2" fill="#fff" opacity=".7"/>' +
      '<path d="M50 61c13 0 21 9 21 24 0 14-9 24-21 24s-21-10-21-24c0-15 8-24 21-24z" fill="url(#' + id + 'p)"/>' +
      '<path d="M50 61c13 0 21 9 21 24 0 14-9 24-21 24s-21-10-21-24c0-15 8-24 21-24z" fill="url(#' + id + 'b)"/>' +
      '<path d="M68.5 74c2.4 5.5 3 12 1.8 18" stroke="' + c + '" stroke-opacity=".4" stroke-width="1.4" stroke-linecap="round" fill="none"/>' +
      '<path d="M57 64c-6 9-6 21 2 33" stroke="#cfc7ba" stroke-width="1" fill="none" opacity=".75"/>' +
      '<path d="M35 74a17 17 0 0 1 9-9" stroke="#fff" stroke-width="2.2" stroke-linecap="round" fill="none" opacity=".9"/>';
    return '<svg class="robot robot-' + clave + '" viewBox="' + (o.cabeza ? "14 2 72 62" : "-6 -12 112 134") + '" style="--o:' + c + '" aria-hidden="true" focusable="false">' +
      defs +
      (o.cabeza ? "" : '<ellipse class="r-sombra" cx="50" cy="118" rx="22" ry="4.5" fill="url(#' + id + 'g)"/>' +
        '<ellipse class="r-sombra r-contacto" cx="50" cy="117.5" rx="12" ry="2.4" fill="#000"/>') +
      '<g class="r-todo">' + cuerpo + cabeza + (o.cabeza ? "" : (ACCESORIO[clave] || "")) +
        '<g class="r-alerta"><circle cx="86" cy="12" r="8.5" fill="#fbbf24"/><text x="86" y="16.6" text-anchor="middle" font-size="12" font-weight="800" fill="#1a1300" font-family="system-ui, sans-serif">!</text></g>' +
      '</g></svg>';
  }

  function rellenar(raiz) {
    (raiz || document).querySelectorAll("[data-robot]:not([data-robot-listo])").forEach(function (e) {
      e.innerHTML = robot(e.dataset.robot, { cabeza: e.hasAttribute("data-robot-cabeza") });
      e.setAttribute("data-robot-listo", "");
    });
  }

  window.RadarEquipo = { robot: robot, colores: COLORES, rellenar: rellenar };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { rellenar(); });
  else rellenar();
})();
