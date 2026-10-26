/* Los muñecos del equipo: renders 3D de Orby y su equipo (static/orby3d.js, guardados en static/marca/agentes).
   Cada agente tiene su render despierto, dormido (ojos cerrados) y su cara sola. El SVG solo los coloca y añade
   los estados: dormido, parpadeo (la imagen de ojos cerrados un instante), aviso y «zz».
   RadarEquipo.robot(clave) devuelve el SVG. En cualquier página, un <span data-robot="analista"> se rellena solo. */
(function () {
  "use strict";
  var COLORES = { jefa: "#3D7BFF", analista: "#22D3EE", estratega: "#FBBF24", guionista: "#F472B6",
                  editor: "#34D399", publicador: "#A78BFA", comunidad: "#FB7185" };
  var RUTA = "/static/marca/agentes/", V = "?v=1";

  function robot(clave, opciones) {
    var c = COLORES[clave] || COLORES.jefa, o = opciones || {}, k = COLORES[clave] ? clave : "jefa";
    if (o.cabeza) {
      return '<svg class="robot robot-' + clave + ' robot-cara" viewBox="0 0 80 70" style="--o:' + c + '" aria-hidden="true" focusable="false">' +
        '<g class="r-todo"><image class="r-img" href="' + RUTA + k + "-cara.webp" + V + '" x="0" y="0" width="80" height="70"/></g></svg>';
    }
    return '<svg class="robot robot-' + clave + '" viewBox="-6 -12 112 134" style="--o:' + c + '" aria-hidden="true" focusable="false">' +
      '<g class="r-todo">' +
        '<image class="r-img r-despierto" href="' + RUTA + k + ".webp" + V + '" x="-6" y="-12" width="112" height="134"/>' +
        '<image class="r-img r-dormido" href="' + RUTA + k + "-dormido.webp" + V + '" x="-6" y="-12" width="112" height="134"/>' +
        '<g class="r-zz" fill="#c9d3ef" font-weight="800" font-family="system-ui, sans-serif"><text x="78" y="4" font-size="12">z</text><text x="87" y="-5" font-size="8">z</text></g>' +
        '<g class="r-alerta"><circle cx="84" cy="6" r="8" fill="#fbbf24"/><text x="84" y="10.5" text-anchor="middle" font-size="11.5" font-weight="800" fill="#1a1300" font-family="system-ui, sans-serif">!</text></g>' +
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
