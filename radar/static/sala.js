/* La sala de «Hoy»: la oficina del equipo.
   Una planta isométrica de 3 × 3 con mamparas de cristal: cada agente en su cuarto, con los muebles de su oficio y
   sus datos en las pantallas; en el centro, Orby; en la esquina de delante, el Kit de marca; y una sala de proyección
   con tus reels. Ventanales con la ciudad de noche, el neón con el nombre de la app y un haz de luz sobre cada cuarto.
   La cámara entra volando, deriva despacio y vuela al cuarto que tocas. «Pantalla completa» deja solo la oficina, y
   agente con su rótulo. El trabajo viaja por el suelo de un cuarto al siguiente. Debajo de cada cuarto, en plano y bien
   legible, quién es y qué hace ahora; quien tiene un primer paso pendiente está con la luz apagada. */
(function () {
  "use strict";
  var raiz = document.querySelector("[data-sala]");
  if (!raiz || !window.RadarEquipo) return;

  var URL_VIVO = raiz.dataset.vivo, APP = (raiz.dataset.app || "Orby").toUpperCase();
  // Escaparate (la landing): la oficina con datos de ejemplo y la actividad simulada encendida sola.
  var ESCAPARATE = raiz.hasAttribute("data-escaparate");
  var QUIETO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var C = 0.8660254, S = 0.5, CELDA = 220, LADO = 660, HM = 200, NS = "http://www.w3.org/2000/svg";
  // Dónde está cada uno en la planta (columna, fila). La esquina de arriba es (0, 0).
  var PLANO = { analista: [0, 0], estratega: [1, 0], guionista: [2, 0], cine: [0, 1], jefa: [1, 1], editor: [2, 1],
                comunidad: [0, 2], publicador: [1, 2], ascensor: [2, 2] };
  // El camino del trabajo por el suelo, de cuarto en cuarto (pasa por el ascensor y por la sala de proyección).
  var RUTA = ["analista", "estratega", "guionista", "editor", "ascensor", "publicador", "comunidad", "cine"];
  // La planta de cada uno en el ascensor: cuanto más avanza el trabajo, más arriba.
  var PISOS = { analista: 1, estratega: 2, guionista: 3, editor: 4, publicador: 5, comunidad: 6, jefa: 7 };

  var escena = raiz.querySelector(".sala-escena");
  var mundo = raiz.querySelector(".sala-mundo");
  var rotulos = raiz.querySelector(".sala-rotulos");
  var ticker = raiz.querySelector(".sala-ticker ul");
  var botonDemo = raiz.querySelector("[data-sala-demo]");
  var botonPantalla = raiz.querySelector("[data-sala-pantalla]");
  var botonGeneral = raiz.querySelector("[data-sala-general]");
  var estado = null, anterior = null, cuartos = {}, etiquetas = {}, vistos = {}, demo = false, demoDatos = null;
  var enfocado = null, capaPaquetes = null;
  var vista = null, objetivo = null, base = null, rodando = false;
  // La oficina de noche (tema oscuro, el de siempre) o de día (tema claro), con la marca de Orby: muebles de la
  // misma porcelana crema que los muñecos, pantallas negras y brillantes como su visor, y luz azul como la franja de
  // su cuello. De noche, el estudio es casi negro con un punto de azul, para que la porcelana y la luz destaquen.
  var PALETAS = {
    oscuro: { suelo: "#0d1018", muro: "#11151f", cielo: ["#03050b", "#0a1226"], edificio: "#070a14", marco: "#1a1f2c", luces: 0.28, letrero: "#05070d",
              base: "#2a2f3b", poste: "#7a7f8c", cabina: "#2a3042", torre: "#cdbb9f", torreTapa: "#e6d8c2", escalon: "#c9b699", estrado: "#bfa98a",
              mueble: "#e6d6bf", papel: "#f4ece0", gris: "#c9b9a1", pantalla: "#07080c" },
    claro: { suelo: "#e9dfcf", muro: "#f5eee3", cielo: ["#c4d6ee", "#f7efe3"], edificio: "#cfc4b2", marco: "#ddd2c0", luces: 0.06, letrero: "#fffbf4",
             base: "#d9ccb7", poste: "#a8977d", cabina: "#e9e0d1", torre: "#d6c4a8", torreTapa: "#ece0cc", escalon: "#d9c9b0", estrado: "#c8b496",
             mueble: "#efe3d0", papel: "#fbf6ee", gris: "#d2c3ab", pantalla: "#0b0d13" }
  };
  function paleta() { return PALETAS[document.documentElement.dataset.tono === "claro" ? "claro" : "oscuro"]; }

  // ------------------------------------------------------------------ utilidades
  function el(tag, clase, texto) {
    var e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto != null) e.textContent = texto;
    return e;
  }
  function cifra(n) {
    n = Number(n) || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(".", ",").replace(",0", "") + " M";
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace(".", ",").replace(",0", "") + " mil";
    return String(Math.round(n));
  }
  function veces(x) { return "×" + String(Math.round((Number(x) || 0) * 10) / 10).replace(".", ","); }
  function azar(a) { return a[Math.floor(Math.random() * a.length)]; }
  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function agente(clave) {
    if (!estado) return null;
    for (var i = 0; i < estado.agentes.length; i++) if (estado.agentes[i].clave === clave) return estado.agentes[i];
    return null;
  }
  function hex(c) { c = c.replace("#", ""); return [parseInt(c.substr(0, 2), 16), parseInt(c.substr(2, 2), 16), parseInt(c.substr(4, 2), 16)]; }
  function mezcla(a, b, t) {
    var x = hex(a), y = hex(b);
    return "#" + [0, 1, 2].map(function (i) { return ("0" + Math.round(x[i] * (1 - t) + y[i] * t).toString(16)).slice(-2); }).join("");
  }
  function repetir(n, f) { var s = ""; for (var i = 0; i < n; i++) s += f(i); return s; }
  var semilla = 7;
  function aleatorio() { semilla = (semilla * 9301 + 49297) % 233280; return semilla / 233280; }

  // ------------------------------------------------------------------ dibujar en isométrico
  var ox = 0, oy = 0;  // el origen del cuarto que se está dibujando
  function P(x, y, z) { x += ox; y += oy; return [(x - y) * C, (x + y) * S - (z || 0)]; }
  function f1(n) { return n.toFixed(1); }
  function puntos(lista) { return lista.map(function (p) { var q = P(p[0], p[1], p[2]); return f1(q[0]) + "," + f1(q[1]); }).join(" "); }
  function poli(lista, relleno, extra) { return '<polygon points="' + puntos(lista) + '" fill="' + relleno + '"' + (extra || "") + "/>"; }
  function caja(x, y, z, w, d, h, col) {
    var a = P(x, y + d, z + h), b = P(x + w, y + d, z + h), c = P(x + w, y, z + h);
    return poli([[x, y + d, z], [x + w, y + d, z], [x + w, y + d, z + h], [x, y + d, z + h]], mezcla(col, "#000000", 0.38)) +
      poli([[x + w, y, z], [x + w, y + d, z], [x + w, y + d, z + h], [x + w, y, z + h]], mezcla(col, "#000000", 0.2)) +
      poli([[x, y, z + h], [x + w, y, z + h], [x + w, y + d, z + h], [x, y + d, z + h]], col) +
      // El bisel: la arista de delante, con un hilo de luz (da volumen sin ensuciar).
      '<polyline points="' + f1(a[0]) + "," + f1(a[1]) + " " + f1(b[0]) + "," + f1(b[1]) + " " + f1(c[0]) + "," + f1(c[1]) + '" fill="none" stroke="' + mezcla(col, "#ffffff", 0.45) + '" stroke-opacity=".7" stroke-width=".9" stroke-linejoin="round"/>';
  }
  function vidrio(x, y, w, d, h) {
    var a = P(x, y + d, h), b = P(x + w, y + d, h), c = P(x + w, y, h);
    return '<g class="vidrio">' +
      poli([[x, y + d, 0], [x + w, y + d, 0], [x + w, y + d, h], [x, y + d, h]], "url(#cristal-mampara)") +
      poli([[x + w, y, 0], [x + w, y + d, 0], [x + w, y + d, h], [x + w, y, h]], "url(#cristal-mampara)") +
      poli([[x, y, h], [x + w, y, h], [x + w, y + d, h], [x, y + d, h]], "rgba(210,224,255,.6)") +
      '<polyline class="vidrio-canto" points="' + f1(a[0]) + "," + f1(a[1]) + " " + f1(b[0]) + "," + f1(b[1]) + " " + f1(c[0]) + "," + f1(c[1]) + '" fill="none" stroke="#dbe6ff" stroke-opacity=".55" stroke-width="1"/></g>';
  }
  function linea(a, b, color, ancho) { return '<line x1="' + f1(a[0]) + '" y1="' + f1(a[1]) + '" x2="' + f1(b[0]) + '" y2="' + f1(b[1]) + '" stroke="' + color + '" stroke-width="' + ancho + '" stroke-linecap="round"/>'; }
  // Lo que va pegado a una superficie, en sus coordenadas (u hacia la derecha, v hacia abajo).
  function enPlano(o, a, b, c, d, svg) { return '<g transform="matrix(' + a + "," + b + "," + c + "," + d + "," + f1(o[0]) + "," + f1(o[1]) + ')">' + svg + "</g>"; }
  function enMuroDer(u0, v0, svg) { var o = [u0 * C, u0 * S - HM + v0]; return enPlano(o, C, S, 0, 1, svg); }               // pared y = 0
  function enMuroIzq(u0, v0, svg) { var o = [(u0 - LADO) * C, (LADO - u0) * S - HM + v0]; return enPlano(o, C, -S, 0, 1, svg); } // pared x = 0
  function enSuelo(svg) { return enPlano(P(0, 0, 0), C, S, -C, S, svg); }
  function enFrente(x, y, z, svg) { return enPlano(P(x, y, z), C, S, 0, 1, svg); }   // de pie, mirando hacia delante
  function maceta(x, y) {
    var p = P(x + 9, y + 9, 22);
    return caja(x, y, 0, 18, 18, 18, "#c4835a") +
      '<g class="planta"><circle cx="' + f1(p[0]) + '" cy="' + f1(p[1] - 6) + '" r="11" fill="#2f9e6e"/><circle cx="' + f1(p[0] - 8) + '" cy="' + f1(p[1]) + '" r="8" fill="#38b47d"/>' +
      '<circle cx="' + f1(p[0] + 8) + '" cy="' + f1(p[1] - 1) + '" r="8" fill="#2a8a60"/></g>';
  }
  // El muñequito de un agente, listo para meter en un grupo plantado en el suelo.
  function muneco(k) {
    // Con la clase «robot»: así sus estados (dormido, atención, habla…) se ven igual que fuera de la oficina.
    return '<svg class="robot robot-' + k + '" x="-48" y="-112" width="96" height="115" viewBox="-6 -12 112 134" overflow="visible">' +
      RadarEquipo.robot(k).replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "") + "</svg>";
  }
  function cinta(u, v, ancho, alto, id) {
    return '<clipPath id="' + id + '"><rect x="' + u + '" y="' + v + '" width="' + ancho + '" height="' + alto + '" rx="4"/></clipPath>' +
      '<rect x="' + (u - 3) + '" y="' + (v - 3) + '" width="' + (ancho + 6) + '" height="' + (alto + 6) + '" rx="6" fill="#070b18" stroke="currentColor" stroke-opacity=".55"/>' +
      '<g clip-path="url(#' + id + ')"><g transform="translate(' + u + "," + v + ')"><g class="cinta" data-cinta="' + id + '" data-alto="' + alto + '"></g></g></g>';
  }
  function holo(ancho, alto, c, svg) {
    return '<g class="holo"><rect width="' + ancho + '" height="' + alto + '" rx="6" fill="' + c + '" fill-opacity=".12" stroke="' + c + '" stroke-opacity=".75"/>' +
      '<rect width="' + ancho + '" height="' + alto + '" rx="6" fill="url(#lineas-holo)"/>' + svg + "</g>";
  }

  // ------------------------------------------------------------------ cada cuarto
  // der / izq: lo que va en la pared del fondo (solo los cuartos que la tocan); u de 0 a 200, v de 0 (z = 120) a 120.
  var CUARTOS = {
    analista: function (c) {
      return {
        der: '<text x="12" y="8" class="muro-rotulo">TU NICHO, AHORA</text>' + cinta(12, 16, 176, 74, "cinta-nicho"),
        izq: '<rect x="30" y="10" width="110" height="70" rx="6" fill="#070b18" stroke="' + c + '" stroke-opacity=".6"/>' +
          repetir(6, function (i) { var h = [18, 30, 22, 44, 34, 54][i]; return '<rect class="barra" style="animation-delay:' + (-i * 0.4) + 's" x="' + (40 + i * 13) + '" y="' + (72 - h) + '" width="8" height="' + h + '" rx="2" fill="' + c + '"/>'; }) +
          '<text x="150" y="40" class="dato-cifra">0</text><text x="150" y="56" class="dato-etiqueta">destacan</text>',
        fondo: maceta(16, 16) + caja(120, 40, 0, 64, 38, 32, paleta().mueble) + caja(136, 44, 32, 34, 4, 24, paleta().pantalla) +
          enFrente(138, 48, 54, '<rect class="pantalla" width="30" height="20" fill="' + c + '" opacity=".75"/><circle cx="12" cy="9" r="5" fill="none" stroke="#fff" stroke-width="2"/><path d="M16 13l5 5" stroke="#fff" stroke-width="2"/>'),
        sitios: [[112, 134], [150, 110], [70, 160]]
      };
    },
    // Plani tiene la pizarra grande de la oficina: el embudo del panel de mando, en vivo.
    estratega: function (c) {
      var etiquetas_ = ["Nicho", "Plan", "Guion", "Edición", "Public.", "Vistas", "Leads"];
      var colores = ["#22D3EE", "#FBBF24", "#F472B6", "#34D399", "#60A5FA", "#22D3EE", "#FB7185"];
      return {
        der: '<g class="tablero" data-tablero>' +
          '<rect x="-6" y="-62" width="214" height="166" rx="8" fill="#060a1c" stroke="' + c + '" stroke-opacity=".75"/>' +
          '<text x="6" y="-46" class="muro-rotulo">DEL NICHO AL LEAD · 14 DÍAS</text>' +
          '<line x1="6" y1="74" x2="202" y2="74" stroke="#fff" stroke-opacity=".12"/>' +
          repetir(7, function (i) {
            var x = 8 + i * 28.4;
            return '<rect class="tb-barra" data-i="' + i + '" x="' + f1(x) + '" y="72" width="20" height="2" rx="2" fill="' + colores[i] + '"/>' +
              '<text class="tb-n" data-i="' + i + '" x="' + f1(x + 10) + '" y="88" text-anchor="middle">0</text>' +
              '<text class="tb-etiqueta" x="' + f1(x + 10) + '" y="98" text-anchor="middle">' + etiquetas_[i] + "</text>" +
              (i < 6 ? '<path d="M' + f1(x + 23) + " 60l3 3-3 3" + '" fill="none" stroke="#fff" stroke-opacity=".3"/>' : "");
          }) + "</g>",
        fondo: caja(70, 74, 0, 84, 52, 30, paleta().mueble) +
          poli([[80, 82, 30.5], [104, 82, 30.5], [104, 100, 30.5], [80, 100, 30.5]], paleta().papel) + poli([[112, 96, 30.5], [136, 96, 30.5], [136, 116, 30.5], [112, 116, 30.5]], "#fde68a") +
          maceta(186, 30),
        sitios: [[112, 160], [176, 110], [52, 124]]
      };
    },
    guionista: function (c) {
      var libros = "", colores = ["#f472b6", "#60a5fa", "#fbbf24", "#34d399", "#a78bfa", "#fb7185"];
      [6, 36, 66].forEach(function (z, n) { for (var i = 0; i < 6; i++) libros += caja(124 + i * 13, 6, z, 9, 12, 22 - (i % 2) * 4, colores[(i + n) % 6]); });
      var b = P(60, 70, 30), t = P(60, 70, 58);
      return {
        der: '<rect x="20" y="4" width="84" height="96" rx="4" fill="' + paleta().papel + '"/><text x="28" y="18" class="muro-rotulo oscuro">GUION</text>' +
          repetir(7, function (i) { return '<rect class="renglon" style="animation-delay:' + (i * 0.3) + 's" x="28" y="' + (26 + i * 10) + '" width="' + [62, 52, 66, 40, 58, 30, 48][i] + '" height="4" rx="2" fill="' + (i === 0 ? c : paleta().gris) + '"/>'; }),
        fondo: caja(118, 0, 0, 84, 20, 96, "#a9774d") + libros + caja(30, 60, 0, 74, 40, 30, paleta().mueble) + caja(70, 66, 30, 26, 18, 8, paleta().papel) +
          linea(b, t, paleta().gris, 3) + '<path d="M' + f1(t[0] - 10) + " " + f1(t[1] + 8) + 'l10-12 10 12z" fill="' + c + '"/>' +
          enFrente(150, 110, 96, holo(56, 34, c, '<text x="8" y="22" class="dato-cifra peque">0</text><text x="30" y="22" class="dato-etiqueta">listos</text>')),
        sitios: [[90, 134], [150, 160], [60, 160]]
      };
    },
    cine: function (c) {
      var butacas = "";
      [[96, 46], [96, 96], [96, 146], [150, 46], [150, 96], [150, 146]].forEach(function (p) {
        butacas += caja(p[0], p[1], 0, 22, 34, 12, "#3b2a6e") + caja(p[0] + 22, p[1], 0, 8, 34, 30, "#4c3a86");
      });
      return {
        izq: '<text x="12" y="8" class="muro-rotulo">TUS REELS</text>' + cinta(12, 16, 176, 92, "cinta-tuyos"),
        fondo: butacas,
        sitios: []
      };
    },
    // Orby dirige desde lo alto: un estrado redondo sobre una columna, distinto a todo lo demás de la oficina.
    jefa: function (c) {
      var T = 72, G = 9, pal = paleta();  // altura de la torre y grosor del estrado
      var cil = function (x, y, z0, z1, r, lado, tapa, extra) {
        var b = P(x, y, z0), t = P(x, y, z1), rx = r * 1.2247, ry = r * 0.7071;
        return '<path d="M' + f1(b[0] - rx) + "," + f1(t[1]) + " L" + f1(b[0] - rx) + "," + f1(b[1]) + " A" + f1(rx) + "," + f1(ry) + " 0 0 0 " + f1(b[0] + rx) + "," + f1(b[1]) +
          " L" + f1(b[0] + rx) + "," + f1(t[1]) + ' Z" fill="' + lado + '"/>' +
          '<ellipse cx="' + f1(t[0]) + '" cy="' + f1(t[1]) + '" rx="' + f1(rx) + '" ry="' + f1(ry) + '" fill="' + tapa + '"' + (extra || "") + "/>";
      };
      var aro = function (z, r, clase, color) { var q = P(110, 110, z); return '<ellipse class="' + clase + '" cx="' + f1(q[0]) + '" cy="' + f1(q[1]) + '" rx="' + f1(r * 1.2247) + '" ry="' + f1(r * 0.7071) + '" fill="none" stroke="' + color + '"/>'; };
      var cima = P(110, 110, T + G), cielo = P(110, 110, 560), mastil = P(150, 70, T + G), baliza = P(150, 70, T + G + 70);
      var escalera = repetir(7, function (i) { return caja(176, 76 + i * 12, 0, 22, 12, (i + 1) * 10.6, pal.escalon); });
      return {
        fondo: aro(0, 86, "torre-suelo", c) +
          cil(110, 110, 0, T, 20, pal.torre, pal.torreTapa) +
          repetir(3, function (i) { var q = P(110, 110, 16 + i * 20); return '<ellipse class="torre-franja" style="animation-delay:' + (i * 0.4) + 's" cx="' + f1(q[0]) + '" cy="' + f1(q[1]) + '" rx="24.5" ry="14.1" fill="none" stroke="' + c + '" stroke-width="2"/>'; }) +
          '<polygon class="rayo-orbi" points="' + f1(cima[0] - 7) + "," + f1(cima[1]) + " " + f1(cima[0] + 7) + "," + f1(cima[1]) + " " + f1(cielo[0] + 2) + "," + f1(cielo[1]) + " " + f1(cielo[0] - 2) + "," + f1(cielo[1]) + '" fill="url(#rayo-orbi)"/>' +
          cil(110, 110, T, T + G, 66, pal.estrado, "url(#estrado)", ' stroke="#3D7BFF" stroke-width="2.5" class="estrado"') +
          aro(T + G + 0.5, 54, "estrado-oro", "#6f9bff") + aro(T + G + 0.5, 30, "estrado-anillo", c) +
          linea(mastil, baliza, "#8fb2ff", 2.5) + '<circle class="baliza" cx="' + f1(baliza[0]) + '" cy="' + f1(baliza[1]) + '" r="5" fill="#fbbf24"/>' +
          caja(80, 76, T + G, 60, 20, 14, paleta().mueble) + poli([[82, 78, T + G + 14], [138, 78, T + G + 14], [138, 90, T + G + 19], [82, 90, T + G + 19]], paleta().pantalla) +
          repetir(5, function (i) { var q = P(90 + i * 10, 84, T + G + 16.5); return '<circle class="boton-luz" style="animation-delay:' + (i * 0.3) + 's" cx="' + f1(q[0]) + '" cy="' + f1(q[1]) + '" r="2.2" fill="' + ["#22d3ee", "#fbbf24", "#f472b6", "#34d399", "#60a5fa"][i] + '"/>'; }),
        frente: escalera + aro(T + G + 20, 70, "halo-orbi", c) +
          enFrente(196, 112, T + 124, holo(56, 40, "#fbbf24", '<text x="6" y="13" class="muro-rotulo">POR APROBAR</text><text x="8" y="34" class="dato-cifra peque">0</text>')),
        sitios: [[118, 132, T + G], [96, 124, T + G], [132, 118, T + G]],
        escala: 1.4
      };
    },
    editor: function (c) {
      var montaje = '<rect width="38" height="24" fill=paleta().pantalla/>' +
        '<rect x="3" y="4" width="14" height="4" rx="1" fill="#f472b6"/><rect x="18" y="4" width="17" height="4" rx="1" fill="#60a5fa"/>' +
        '<rect x="3" y="11" width="22" height="4" rx="1" fill="' + c + '"/><rect x="26" y="11" width="9" height="4" rx="1" fill="#fbbf24"/>' +
        '<rect x="3" y="18" width="30" height="3" rx="1" fill="#334155"/><rect class="cabezal" x="10" y="2" width="1.6" height="20" fill="#fff"/>';
      var pie = P(186, 160, 0), aro = P(186, 160, 76);
      return {
        fondo: enFrente(30, 14, 130, holo(150, 44, c,
            repetir(4, function (i) { return '<rect x="' + (10 + i * 34) + '" y="10" width="28" height="12" rx="2" fill="' + ["#f472b6", c, "#60a5fa", "#fbbf24"][i] + '" opacity=".85"/>'; }) +
            '<text x="10" y="38" class="dato-cifra peque">0</text><text x="40" y="38" class="dato-etiqueta">reels</text>')) +
          caja(40, 40, 0, 124, 40, 30, paleta().mueble) + caja(52, 44, 30, 40, 4, 26, paleta().pantalla) + caja(104, 44, 30, 40, 4, 26, paleta().pantalla) +
          enFrente(53, 48, 55, montaje) + enFrente(105, 48, 55, montaje) +
          linea(pie, aro, "#94a3b8", 3) + '<circle class="aro-luz" cx="' + f1(aro[0]) + '" cy="' + f1(aro[1]) + '" r="17" fill="none" stroke="#fff" stroke-width="5"/>',
        sitios: [[104, 124], [150, 116], [70, 164]]
      };
    },
    comunidad: function (c) {
      return {
        izq: '<rect x="20" y="4" width="120" height="84" rx="6" fill=paleta().pantalla stroke="' + c + '" stroke-opacity=".5"/>' +
          repetir(4, function (i) { return '<rect class="dm" style="animation-delay:' + (i * 0.5) + 's" x="' + (i % 2 ? 56 : 28) + '" y="' + (12 + i * 18) + '" width="' + (i % 2 ? 76 : 70) + '" height="13" rx="6.5" fill="' + (i % 2 ? c : "#2a3460") + '"/>'; }) +
          '<text x="152" y="36" class="dato-cifra">0</text><text x="152" y="52" class="dato-etiqueta">leads</text>' +
          '<path class="corazon" d="M170 70c-4-6-15-3-12 4 1 4 12 11 12 11s11-7 12-11c3-7-8-10-12-4z" fill="' + c + '"/>',
        fondo: caja(6, 110, 0, 10, 80, 38, mezcla(c, "#1a2142", 0.45)) + caja(16, 110, 0, 34, 80, 16, mezcla(c, "#1a2142", 0.3)) +
          caja(18, 114, 16, 26, 14, 8, mezcla(c, "#ffffff", 0.35)) + maceta(186, 186) +
          repetir(3, function (i) { var q = P(118 + i * 22, 70, 80 + i * 10); return '<g class="burbuja" style="animation-delay:' + (i * 1.1) + 's"><rect x="' + f1(q[0] - 12) + '" y="' + f1(q[1] - 9) + '" width="24" height="16" rx="8" fill="#fff"/><text x="' + f1(q[0]) + '" y="' + f1(q[1] + 3) + '" text-anchor="middle" font-size="10" fill="' + c + '">' + ["♥", "…", "✓"][i] + "</text></g>"; }),
        sitios: [[112, 134], [150, 160], [90, 170]]
      };
    },
    publicador: function (c) {
      var p = P(166, 166, 10);
      var cohete = '<g class="cohete" transform="translate(' + f1(p[0]) + "," + f1(p[1]) + ')"><g class="cohete-vuelo"><path class="llama" d="M-5 0q5 14 10 0z" fill="#fbbf24"/>' +
        '<path d="M-8 0h16l-3-30q-5-10-10 0z" fill="#f8fafc"/><circle cx="0" cy="-16" r="3.5" fill="' + c + '"/><path d="M-8 0l-6 4 4-12zM8 0l6 4-4-12z" fill="' + c + '"/></g></g>';
      return {
        fondo: enFrente(24, 24, 120, holo(120, 74, c,
            '<rect width="120" height="14" rx="6" fill="' + c + '" fill-opacity=".5"/><text x="8" y="10" class="muro-rotulo">ESTA SEMANA</text>' +
            repetir(12, function (i) { return '<text x="' + (10 + (i % 4) * 16) + '" y="' + (32 + Math.floor(i / 4) * 14) + '" class="check" fill="' + (i < 7 ? c : "#64748b") + '">' + (i < 7 ? "✓" : "·") + "</text>"; }) +
            '<text x="80" y="44" class="dato-cifra peque">0</text>')) +
          caja(36, 70, 0, 52, 40, 28, paleta().mueble) + caja(44, 76, 28, 24, 16, 2, paleta().pantalla) + caja(148, 148, 0, 36, 36, 10, paleta().gris) + cohete,
        sitios: [[110, 140], [80, 170], [150, 110]]
      };
    },
    // Un ascensor de cristal: la cabina sube por el hueco, que se alarga hacia el cielo cuando alguien viaja.
    ascensor: function () {
      var pal = paleta(), H = 150, ALTO = 760, postes = [[58, 58], [156, 58], [58, 156]];
      var poste = function (x, y, z0, z1) { return caja(x, y, z0, 6, 6, z1 - z0, pal.poste); };
      var cristal = function (lista, a) { return poli(lista, "rgba(160,185,255," + a + ")"); };
      var anillos = repetir(8, function (i) {
        var z = H + 70 + i * 74;
        return '<polygon points="' + puntos([[58, 58, z], [162, 58, z], [162, 162, z], [58, 162, z]]) + '" fill="none" stroke="#8b9cff" stroke-opacity=".45"/>' +
          enFrente(162, 162, z + 10, '<text x="-24" y="0" class="piso-led">' + (i + 1) + "</text>");
      });
      return {
        fondo: caja(52, 52, 0, 116, 116, 6, pal.base) +
          '<g class="hueco-alto">' + postes.map(function (p) { return poste(p[0], p[1], H, ALTO); }).join("") + anillos + "</g>" +
          postes.map(function (p) { return poste(p[0], p[1], 6, H); }).join("") +
          '<g class="cabina">' + caja(66, 66, 6, 88, 88, 4, pal.cabina) +
            cristal([[66, 66, 10], [66, 154, 10], [66, 154, 100], [66, 66, 100]], 0.2) + cristal([[66, 66, 10], [154, 66, 10], [154, 66, 100], [66, 66, 100]], 0.24) +
            poli([[67, 67, 11], [67, 153, 11], [67, 153, 99], [67, 67, 99]], "currentColor", ' class="cabina-luz"') +
            poli([[67, 67, 11], [153, 67, 11], [153, 67, 99], [67, 67, 99]], "currentColor", ' class="cabina-luz"') +
            '<g class="cabina-ser"></g>' +
            cristal([[154, 66, 10], [154, 154, 10], [154, 154, 100], [154, 66, 100]], 0.1) + cristal([[66, 154, 10], [154, 154, 10], [154, 154, 100], [66, 154, 100]], 0.12) +
            [[66, 66], [154, 66], [66, 154], [154, 154]].map(function (e) { return linea(P(e[0], e[1], 10), P(e[0], e[1], 100), "currentColor", 2.2); }).join("") +
            caja(66, 66, 100, 88, 88, 5, pal.cabina) + enFrente(96, 154, 112, '<rect width="28" height="9" rx="2" fill="#05070f"/><text x="14" y="7.2" text-anchor="middle" class="piso-led cabina-piso">0</text>') +
          "</g>" + poste(156, 156, 0, H) + '<g class="hueco-alto">' + poste(156, 156, H, ALTO) + "</g>",
        sitios: []
      };
    }
  };

  // ------------------------------------------------------------------ montar la oficina
  function definiciones() {
    var colores = { analista: "#22D3EE", estratega: "#FBBF24", guionista: "#F472B6", editor: "#34D399", publicador: "#A78BFA", comunidad: "#FB7185", jefa: "#3D7BFF", cine: "#C084FC", ascensor: "#8B9CFF" };
    return "<defs>" +
      '<linearGradient id="cielo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + paleta().cielo[0] + '"/><stop offset="1" stop-color="' + paleta().cielo[1] + '"/></linearGradient>' +
      '<linearGradient id="brillo-suelo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".07"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#8b9cff" stop-opacity=".06"/></linearGradient>' +
      (paleta() === PALETAS.claro
        ? '<radialGradient id="estrado" cx=".45" cy=".4" r=".65"><stop offset="0" stop-color="#fbf5ec"/><stop offset=".7" stop-color="#ead9c2"/><stop offset="1" stop-color="#d4bf9f"/></radialGradient>'
        : '<radialGradient id="estrado" cx=".45" cy=".4" r=".65"><stop offset="0" stop-color="#f1e5d3"/><stop offset=".7" stop-color="#d9c6a8"/><stop offset="1" stop-color="#b8a281"/></radialGradient>') +
      '<linearGradient id="rayo-orbi" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#a9c3ff" stop-opacity=".75"/><stop offset="1" stop-color="#3D7BFF" stop-opacity="0"/></linearGradient>' +
      (paleta() === PALETAS.claro
        ? '<linearGradient id="rayo-ventana" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff3c4" stop-opacity=".75"/><stop offset="1" stop-color="#ffe7a3" stop-opacity="0"/></linearGradient>' +
          '<linearGradient id="rayo-ventana-2" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff3c4" stop-opacity=".7"/><stop offset="1" stop-color="#ffe7a3" stop-opacity="0"/></linearGradient>' +
          '<linearGradient id="barrido" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6366f1" stop-opacity="0"/><stop offset=".85" stop-color="#6366f1" stop-opacity=".22"/><stop offset="1" stop-color="#4f46e5" stop-opacity=".5"/></linearGradient>'
        : '<linearGradient id="rayo-ventana" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c7d2fe" stop-opacity=".22"/><stop offset="1" stop-color="#818cf8" stop-opacity="0"/></linearGradient>' +
          '<linearGradient id="rayo-ventana-2" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c7d2fe" stop-opacity=".2"/><stop offset="1" stop-color="#818cf8" stop-opacity="0"/></linearGradient>' +
          '<linearGradient id="barrido" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee" stop-opacity="0"/><stop offset=".85" stop-color="#22d3ee" stop-opacity=".18"/><stop offset="1" stop-color="#a5f3fc" stop-opacity=".55"/></linearGradient>') +
      '<pattern id="lineas-holo" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" fill-opacity=".06"/></pattern>' +
      '<filter id="neon" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
      // El cristal de las mamparas: más luz arriba, con el canto encendido.
      '<linearGradient id="cristal-mampara" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c9d8ff" stop-opacity=".2"/><stop offset=".5" stop-color="#9fb6ff" stop-opacity=".08"/><stop offset="1" stop-color="#9fb6ff" stop-opacity=".03"/></linearGradient>' +
      Object.keys(colores).map(function (k) {
        return '<radialGradient id="piso-' + k + '"><stop offset="0" stop-color="' + colores[k] + '" stop-opacity=".85"/><stop offset=".45" stop-color="' + colores[k] + '" stop-opacity=".35"/><stop offset="1" stop-color="' + colores[k] + '" stop-opacity="0"/></radialGradient>';
      }).join("") +
      Object.keys(colores).map(function (k) {
        return '<linearGradient id="haz-' + k + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + colores[k] + '" stop-opacity=".0"/>' +
          '<stop offset=".25" stop-color="' + colores[k] + '" stop-opacity=".16"/><stop offset="1" stop-color="' + colores[k] + '" stop-opacity=".05"/></linearGradient>';
      }).join("") + "</defs>";
  }

  // La ciudad de noche por los ventanales (siempre la misma: el azar tiene semilla).
  function ciudad(ancho, id) {
    semilla = 11;
    var pal = paleta(), dia = pal === PALETAS.claro, u = 0;
    // El cielo vive: de día pasan nubes; de noche titilan las estrellas y, de vez en cuando, cruza una fugaz.
    var cielo = dia
      ? repetir(5, function (i) {
          var y = 6 + (i % 3) * 9, w = 30 + (i * 13) % 28;
          return '<g class="nube" style="animation-duration:' + (38 + i * 9) + "s;animation-delay:" + (-i * 11) + 's"><ellipse cx="0" cy="' + y + '" rx="' + w / 2 + '" ry="5" fill="#fff" opacity=".85"/>' +
            '<ellipse cx="' + w / 4 + '" cy="' + (y - 3) + '" rx="' + w / 3.2 + '" ry="5" fill="#fff" opacity=".9"/></g>';
        })
      : repetir(26, function (i) {
          return '<circle class="estrella" style="animation-delay:' + (-(i * 0.37) % 4).toFixed(2) + 's" cx="' + f1((i * 97) % ancho) + '" cy="' + f1(3 + (i * 13) % 30) + '" r="' + (i % 4 ? 0.7 : 1.1) + '" fill="#fff"/>';
        }) + '<line class="fugaz" x1="0" y1="0" x2="26" y2="9" stroke="#fff" stroke-width="1.2" stroke-linecap="round"/>';
    var html = '<clipPath id="ventana-' + id + '"><rect width="' + ancho + '" height="64"/></clipPath>' +
      '<g clip-path="url(#ventana-' + id + ')"><rect x="0" y="0" width="' + ancho + '" height="64" fill="url(#cielo)"/>' + cielo + "</g>";
    while (u < ancho) {
      var w = 18 + aleatorio() * 34, h = 16 + aleatorio() * 40;
      html += '<rect x="' + f1(u) + '" y="' + f1(64 - h) + '" width="' + f1(w) + '" height="' + f1(h) + '" fill="' + pal.edificio + '"/>';
      for (var vy = 64 - h + 5; vy < 60; vy += 7) for (var vx = u + 3; vx < u + w - 4; vx += 6) {
        if (aleatorio() < pal.luces) html += '<rect class="' + (aleatorio() < 0.15 ? "ventana-tilila" : "") + '" x="' + f1(vx) + '" y="' + f1(vy) + '" width="2.6" height="3" fill="' + (aleatorio() < 0.7 ? "#fde68a" : "#a5f3fc") + '" opacity=".75"/>';
      }
      u += w + 2;
    }
    return html + repetir(Math.ceil(ancho / 110), function (i) { return '<rect x="' + (i * 110) + '" y="0" width="4" height="64" fill="' + pal.marco + '"/>'; }) +
      '<rect x="0" y="62" width="' + ancho + '" height="4" fill="' + pal.marco + '"/>';
  }

  function construir() {
    var html = definiciones();
    var pal = paleta(), suelo = pal.suelo, muro = pal.muro;
    ox = 0; oy = 0;
    // El suelo, brillante, con su rejilla.
    html += caja(-14, -14, -22, LADO + 14, LADO + 14, 22, suelo) +
      enSuelo('<rect width="' + LADO + '" height="' + LADO + '" fill="url(#brillo-suelo)"/><g stroke="#fff" stroke-opacity=".045">' +
        repetir(11, function (i) { var k = (i + 1) * 55; return '<line x1="' + k + '" y1="0" x2="' + k + '" y2="' + LADO + '"/><line x1="0" y1="' + k + '" x2="' + LADO + '" y2="' + k + '"/>'; }) + "</g>");
    // Las dos paredes del fondo, con ventanales, el neón y lo que cuelga en cada cuarto.
    html += caja(-14, -14, 0, 14, 14, HM, muro) + caja(0, -14, 0, LADO, 14, HM, muro) + caja(-14, 0, 0, 14, LADO, HM, muro);
    var z0 = P(0, 0, 1), zd = P(LADO, 0, 1), zi = P(0, LADO, 1);
    html += '<polyline class="zocalo" points="' + f1(zi[0]) + "," + f1(zi[1]) + " " + f1(z0[0]) + "," + f1(z0[1]) + " " + f1(zd[0]) + "," + f1(zd[1]) + '" fill="none" stroke="#3D7BFF" stroke-width="2.4" stroke-linecap="round"/>';
    html += enMuroDer(0, 0, '<g transform="translate(10,12)">' + ciudad(LADO - 20, "der") + "</g>");
    html += enMuroIzq(0, 0, '<g transform="translate(10,12)">' + ciudad(LADO - 20, "izq") + "</g>" +
      '<rect x="' + (LADO / 2 - 150) + '" y="10" width="300" height="68" rx="10" fill="' + pal.letrero + '"/>' +
      '<text class="neon" x="' + (LADO / 2) + '" y="58" text-anchor="middle" filter="url(#neon)">' + esc(APP) + "</text>");
    // Un barrido de escaneo recorre el suelo cada pocos segundos.
    html += enSuelo('<g class="barrido-suelo"><rect x="-60" y="0" width="60" height="' + LADO + '" fill="url(#barrido)"/></g>');
    // La luz entra en diagonal por los ventanales: luna de noche, sol de día.
    html += '<g class="rayos-ventana">' +
      [[70, 150], [300, 380], [520, 590]].map(function (r, i) {
        return '<polygon class="rayo-ventana" style="animation-delay:' + (-i * 3.1) + 's" points="' + puntos([[0, r[0], 186], [0, r[1], 186], [320, r[1] + 150, 0], [320, r[0] + 150, 0]]) + '" fill="url(#rayo-ventana)"/>';
      }).join("") +
      [[120, 190], [400, 470]].map(function (r, i) {
        return '<polygon class="rayo-ventana" style="animation-delay:' + (-(i + 2) * 2.3) + 's" points="' + puntos([[r[0], 0, 186], [r[1], 0, 186], [r[1] + 150, 320, 0], [r[0] + 150, 320, 0]]) + '" fill="url(#rayo-ventana-2)"/>';
      }).join("") + "</g>";
    // Los raíles de luz del techo, que cruzan la oficina.
    var capaCuartos = "";
    // Los cuartos, de atrás hacia delante, cada uno con sus mamparas.
    var orden = Object.keys(PLANO).sort(function (a, b) { return (PLANO[a][0] + PLANO[a][1]) - (PLANO[b][0] + PLANO[b][1]); });
    var paredes = "";
    orden.forEach(function (k) {
      var i = PLANO[k][0], j = PLANO[k][1], a = agente(k), c = a ? a.color : (k === "cine" ? "#C084FC" : "#8B9CFF");
      ox = i * CELDA; oy = j * CELDA;
      var partes = CUARTOS[k](c);
      if (j === 0 && partes.der) paredes += '<g class="decorado" data-de="' + k + '" style="color:' + c + '">' + enMuroDer(i * CELDA + 10, HM - 120, partes.der) + "</g>";
      if (i === 0 && partes.izq) paredes += '<g class="decorado" data-de="' + k + '" style="color:' + c + '">' + enMuroIzq(LADO - (j + 1) * CELDA + 10, HM - 120, partes.izq) + "</g>";
      var g = '<g class="cuarto cuarto-' + k + '" data-clave="' + k + '" style="color:' + c + '">';
      if (i > 0) g += vidrio(-2, 0, 4, 76, 54) + vidrio(-2, 144, 4, 76, 54);
      if (j > 0) g += vidrio(0, -2, 76, 4, 54) + vidrio(144, -2, 76, 4, 54);
      if (i > 0 && j > 0) g += caja(-6, -6, 0, 12, 12, 62, pal.base);
      g += enSuelo('<circle class="suelo-luz" cx="110" cy="115" r="96" fill="url(#piso-' + k + ')"/>');
      g += poli([[4, 4, 0], [216, 4, 0], [216, 216, 0], [4, 216, 0]], "#000", ' fill-opacity="0" class="zona-toque" pointer-events="all"');
      g += '<g class="muebles">' + partes.fondo + "</g>";
      if (partes.sitios && partes.sitios.length) {
        var s = partes.sitios[0], p = P(s[0], s[1], s[2] || 0);
        g += '<g class="cuarto-ser"><g class="ser" style="transform: translate(' + f1(p[0]) + "px," + f1(p[1]) + "px)" + (partes.escala ? " scale(" + partes.escala + ")" : "") + '">' + muneco(k) + "</g></g>";
      }
      if (partes.frente) g += '<g class="muebles">' + partes.frente + "</g>";
      // El haz de luz que cae sobre el cuarto.
      var arriba = P(110, 110, 300), abajo1 = P(30, 190, 0), abajo2 = P(190, 30, 0);
      g += '<polygon class="haz" points="' + f1(arriba[0] - 14) + "," + f1(arriba[1]) + " " + f1(arriba[0] + 14) + "," + f1(arriba[1]) + " " +
        f1(abajo2[0]) + "," + f1(abajo2[1]) + " " + f1(abajo1[0]) + "," + f1(abajo1[1]) + '" fill="url(#haz-' + k + ')"/>';
      g += "</g>";
      capaCuartos += g;
      cuartos[k] = { sitios: partes.sitios || [], sitio: 0, ox: ox, oy: oy, escala: partes.escala || 1 };
    });
    ox = 0; oy = 0;
    html += paredes + '<g class="caminos">' + caminos() + '</g><g class="paquetes"></g>' + capaCuartos + '<g class="chispas"></g>';
    mundo.innerHTML = html;
    capaPaquetes = mundo.querySelector(".paquetes");
    // La pizarra de Plani es el embudo: al tocarla, bajas al panel de mando.
    var tablero = mundo.querySelector("[data-tablero]");
    if (tablero) tablero.addEventListener("click", function (e) { e.stopPropagation(); raiz.querySelector(".mando").scrollIntoView({ behavior: "smooth", block: "start" }); });
    Object.keys(cuartos).forEach(function (k) {
      var g = mundo.querySelector('.cuarto[data-clave="' + k + '"]');
      cuartos[k].g = g;
      cuartos[k].decorados = Array.prototype.slice.call(mundo.querySelectorAll('.decorado[data-de="' + k + '"]'));
      g.addEventListener("click", function (e) { e.stopPropagation(); if (agente(k)) { botar(k); enfocar(k); } });
      etiquetas[k] = crearEtiqueta(k);
      // La etiqueta solo sale al pasar por encima: el dibujo queda limpio.
      g.addEventListener("mouseenter", function () { etiquetas[k].classList.add("ver"); });
      g.addEventListener("mouseleave", function () { etiquetas[k].classList.remove("ver"); });
    });
    // El polvo que flota en la luz.
    var polvo = raiz.querySelector(".sala-polvo");
    if (polvo && !polvo.children.length && !QUIETO) {
      for (var n = 0; n < 28; n++) {
        var mota = el("i");
        mota.style.left = (Math.random() * 100).toFixed(1) + "%";
        mota.style.top = (20 + Math.random() * 80).toFixed(1) + "%";
        mota.style.animationDuration = (9 + Math.random() * 12).toFixed(1) + "s";
        mota.style.animationDelay = (-Math.random() * 20).toFixed(1) + "s";
        mota.style.setProperty("--t", (1 + Math.random() * 2.2).toFixed(1) + "px");
        polvo.appendChild(mota);
      }
    }
    encuadrar(!vista);
    if (!rodando) {
      rodando = true;
      if (window.ResizeObserver) new ResizeObserver(function () { encuadrar(false); }).observe(escena);
      requestAnimationFrame(rodar);
    }
  }

  // ------------------------------------------------------------------ los caminos del trabajo por el suelo
  function centro(k) { var i = PLANO[k][0], j = PLANO[k][1], o = ox, p = oy; ox = 0; oy = 0; var q = P(i * CELDA + 110, j * CELDA + 110, 0); ox = o; oy = p; return q; }
  function caminos() {
    var d = "M" + RUTA.map(function (k) { var q = centro(k); return f1(q[0]) + "," + f1(q[1]); }).join(" L") + " Z";
    var radios = Object.keys(PLANO).filter(function (k) { return k !== "jefa"; }).map(function (k) {
      var a = centro("jefa"), b = centro(k);
      a = [a[0], a[1] - 81];  // los hilos salen del estrado de lo alto de la torre
      return '<line class="radio" x1="' + f1(a[0]) + '" y1="' + f1(a[1]) + '" x2="' + f1(b[0]) + '" y2="' + f1(b[1]) + '"/>';
    }).join("");
    return '<path class="camino" d="' + d + '"/>' + radios;
  }
  function tramo(de, a) {
    if (de === "jefa") return [centro("jefa"), centro(a)];
    var i = RUTA.indexOf(de), j = RUTA.indexOf(a);
    if (i < 0 || j < 0) return null;
    var pts = [centro(de)];
    for (var n = (i + 1) % RUTA.length; ; n = (n + 1) % RUTA.length) { pts.push(centro(RUTA[n])); if (n === j) break; }
    return pts;
  }
  function paquete(de, a, color) {
    if (QUIETO || document.hidden || !capaPaquetes) return;
    var pts = tramo(de, a);
    if (!pts) return;
    var largos = [0];
    for (var i = 1; i < pts.length; i++) largos.push(largos[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    var total = largos[largos.length - 1];
    var g = document.createElementNS(NS, "g");
    g.innerHTML = '<ellipse rx="16" ry="8" fill="' + color + '" opacity=".35"/><circle r="5" fill="#fff"/><circle r="9" fill="none" stroke="' + color + '" stroke-width="2" opacity=".8"/>';
    capaPaquetes.appendChild(g);
    var t0 = null, dur = 900 + total * 2.2;
    function paso(t) {
      if (!t0) t0 = t;
      var k = Math.min(1, (t - t0) / dur), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2, l = total * e, n = 1;
      while (n < largos.length - 1 && largos[n] < l) n++;
      var f = (l - largos[n - 1]) / Math.max(1, largos[n] - largos[n - 1]);
      var x = pts[n - 1][0] + (pts[n][0] - pts[n - 1][0]) * f, y = pts[n - 1][1] + (pts[n][1] - pts[n - 1][1]) * f;
      g.setAttribute("transform", "translate(" + f1(x) + "," + f1(y) + ")");
      if (k < 1) requestAnimationFrame(paso);
      else { g.remove(); botar(a); destello(a); }
    }
    requestAnimationFrame(paso);
  }

  // ------------------------------------------------------------------ la cámara
  function medidas() { var r = escena.getBoundingClientRect(); return { w: Math.max(1, r.width), h: Math.max(1, r.height) }; }
  // Toda la oficina en plano, con el mismo ancho/alto que la escena (así las etiquetas caen en su sitio).
  function encuadre() {
    var m = medidas(), ar = m.w / m.h, h = Math.max(960, 1250 / ar), w = h * ar;
    if (ESCAPARATE) { h = Math.max(800, 1160 / ar); w = h * ar; }  // en la landing, la oficina llena el marco
    if (m.w < 720) { w = ESCAPARATE ? 1000 : 900; h = w / ar; }  // en el móvil, más cerca: se recortan un poco los lados
    return { x: -w / 2, y: 238 - h / 2, w: w, h: h };  // de lo alto de las paredes (-220) a la esquina de delante (700)
  }
  function encuadrar(primera) {
    base = encuadre();
    if (primera) {
      var c = centro("jefa"), ar = base.w / base.h, h = 300;
      vista = { x: c[0] - h * ar / 2, y: c[1] - h * 0.62, w: h * ar, h: h };
    }
    if (enfocado) apuntar(enfocado, true);
    else objetivo = clon(base);
  }
  function clon(v) { return { x: v.x, y: v.y, w: v.w, h: v.h }; }
  function apuntar(k, conPanel) {
    var m = medidas(), ar = m.w / m.h, c = centro(k);
    var h = m.w < 720 ? 520 : 470, w = h * ar;
    var hueco = conPanel && m.w >= 720 ? Math.min(360, m.w * 0.36) : 0;
    var fx = ((m.w - hueco) / 2) / m.w;
    objetivo = { x: c[0] - fx * w, y: c[1] - 120 - h * 0.42, w: w, h: h };
  }
  var tiempo0 = performance.now();
  function rodar(t) {
    if (vista && objetivo) {
      var o = objetivo;
      if (!enfocado && !QUIETO) {
        // Deriva lenta, como una cámara en grúa.
        var s = (t - tiempo0) / 1000, z = 1 + 0.025 * Math.sin(s / 9);
        o = { x: objetivo.x + objetivo.w * 0.018 * Math.sin(s / 7) - objetivo.w * (z - 1) / 2, y: objetivo.y + objetivo.h * 0.01 * Math.cos(s / 8) - objetivo.h * (z - 1) / 2, w: objetivo.w * z, h: objetivo.h * z };
      }
      var k = QUIETO ? 1 : (viajando ? 0.12 : 0.055);
      vista.x += (o.x - vista.x) * k; vista.y += (o.y - vista.y) * k; vista.w += (o.w - vista.w) * k; vista.h += (o.h - vista.h) * k;
      mundo.setAttribute("viewBox", f1(vista.x) + " " + f1(vista.y) + " " + f1(vista.w) + " " + f1(vista.h));
      colocarEtiquetas();
    }
    requestAnimationFrame(rodar);
  }

  // ------------------------------------------------------------------ las etiquetas, en plano
  var NOMBRES = { cine: ["Sala de proyección", "Tus reels"], ascensor: ["Ascensor", "Pulsa un cuarto para subir a su planta"] };
  function crearEtiqueta(k) {
    var a = agente(k), e = el("button", "etiqueta" + (a ? "" : " etiqueta-sitio"));
    e.type = "button";
    e.style.setProperty("--c", a ? a.color : "#a5b4fc");
    if (a) {
      e.innerHTML = '<span class="et-cabeza"><i class="et-punto"></i><b></b><small></small><em class="et-cifra"></em></span><span class="et-texto"></span><span class="et-dice"></span>';
      e.querySelector("b").textContent = a.nombre;
      e.querySelector("small").textContent = a.rol;
      e.addEventListener("click", function (ev) { ev.stopPropagation(); botar(k); enfocar(k); });
    } else {
      e.innerHTML = '<span class="et-cabeza"><i class="et-punto"></i><b></b></span><span class="et-texto"></span>';
      e.querySelector("b").textContent = NOMBRES[k][0];
      e.querySelector(".et-texto").textContent = NOMBRES[k][1];
      e.tabIndex = -1;
    }
    rotulos.appendChild(e);
    return e;
  }
  function colocarEtiquetas() {
    var m = medidas(), s = m.w / vista.w;
    Object.keys(etiquetas).forEach(function (k) {
      var i = PLANO[k][0], j = PLANO[k][1], o = ox, p = oy;
      ox = 0; oy = 0;
      var q = P(i * CELDA + 196, j * CELDA + 196, 0);
      ox = o; oy = p;
      var x = (q[0] - vista.x) * s, y = (q[1] - vista.y) * s, e = etiquetas[k];
      var t = "translate(" + Math.round(x) + "px," + Math.round(y) + "px) translate(-50%, -30%)";
      if (e._t !== t) { e.style.transform = t; e._t = t; }
    });
  }

  // ------------------------------------------------------------------ vida de cada agente
  function decir(k, texto, ms) {
    var e = etiquetas[k], c = cuartos[k];
    if (!e || !texto || !agente(k)) return;
    e.querySelector(".et-dice").textContent = texto;
    e.classList.add("habla"); c.g.classList.add("habla");
    clearTimeout(e._habla);
    e._habla = setTimeout(function () { e.classList.remove("habla"); c.g.classList.remove("habla"); }, ms || 2600);
  }
  function botar(k) {
    var c = cuartos[k];
    if (!c || QUIETO) return;
    c.g.classList.remove("bota"); void c.g.getBoundingClientRect(); c.g.classList.add("bota");
  }
  function onda(k) {
    if (QUIETO || !capaPaquetes || !PLANO[k]) return;
    var c = centro(k), a = agente(k), e = document.createElementNS(NS, "ellipse");
    e.setAttribute("cx", f1(c[0])); e.setAttribute("cy", f1(c[1])); e.setAttribute("rx", "90"); e.setAttribute("ry", "52");
    e.setAttribute("class", "onda-suelo"); e.setAttribute("stroke", a ? a.color : "#8b9cff");
    capaPaquetes.appendChild(e);
    setTimeout(function () { e.remove(); }, 1300);
  }
  function destello(k) {
    onda(k);
    var c = cuartos[k];
    if (!c) return;
    c.g.classList.remove("destella"); void c.g.getBoundingClientRect(); c.g.classList.add("destella");
  }
  function moverse() {
    if (!estado || QUIETO || document.hidden) return;
    var ks = Object.keys(cuartos).filter(function (k) { var a = agente(k); return a && !a.dormido && cuartos[k].sitios.length > 1; });
    if (!ks.length) return;
    var k = azar(ks), c = cuartos[k];
    c.sitio = (c.sitio + 1 + Math.floor(Math.random() * (c.sitios.length - 1))) % c.sitios.length;
    var s = c.sitios[c.sitio], o = ox, p = oy;
    ox = c.ox; oy = c.oy;
    var q = P(s[0], s[1], s[2] || 0);
    ox = o; oy = p;
    c.g.classList.add("anda");
    c.g.querySelector(".ser").style.transform = "translate(" + f1(q[0]) + "px," + f1(q[1]) + "px)" + (c.escala !== 1 ? " scale(" + c.escala + ")" : "");
    setTimeout(function () { c.g.classList.remove("anda"); }, 1800);
  }

  // ------------------------------------------------------------------ pintar los datos
  function pintarAgente(a) {
    var c = cuartos[a.clave], e = etiquetas[a.clave];
    if (!c || !e) return;
    var est = a.dormido ? "dormido" : a.estado, valor = typeof a.cifra === "number" ? cifra(a.cifra) : a.cifra;
    c.g.setAttribute("data-estado", est);
    c.decorados.forEach(function (d) { d.setAttribute("data-estado", est); });
    e.dataset.estado = est;
    e.querySelector(".et-texto").textContent = a.dormido ? "Luz apagada · " + a.dormido.texto : a.texto;
    var ci = e.querySelector(".et-cifra");
    ci.textContent = a.dormido ? "" : valor;
    ci.title = a.etiqueta || "";
    c.g.querySelectorAll(".dato-cifra").forEach(function (t) { t.textContent = valor; });
    c.decorados.forEach(function (d) { d.querySelectorAll(".dato-cifra").forEach(function (t) { t.textContent = valor; }); });
  }

  function pintarCinta(id, datos) {
    var g = mundo.querySelector('[data-cinta="' + id + '"]');
    if (!g) return;
    var items = (datos && datos.items) || [];
    var firma = items.map(function (it) { return [it.cuenta, it.titulo, it.vistas, it.imagen].join("|"); }).join("¦");
    if (g.dataset.firma === firma) return;
    g.dataset.firma = firma;
    var alto = Number(g.dataset.alto) || 74, ancho = Math.round(alto * 0.56), hueco = 8;
    if (!items.length) {
      g.innerHTML = '<text x="88" y="' + (alto / 2 + 4) + '" text-anchor="middle" class="muro-vacio">' + (id === "cinta-nicho" ? "Aún sin escanear" : "Aún sin reels") + "</text>";
      g.classList.remove("corre");
      return;
    }
    var lista = items.slice(0, 8), html = "";
    while (lista.length < 5) lista = lista.concat(lista);
    lista.concat(lista).forEach(function (it, i) {
      html += '<g transform="translate(' + i * (ancho + hueco) + ',0)"><rect width="' + ancho + '" height="' + alto + '" rx="4" fill="' + ["#2a3a7a", "#3b2a6e", "#1f4d63", "#5b2a4e"][i % 4] + '"/>' +
        (it.imagen ? '<image href="' + esc(it.imagen) + '" width="' + ancho + '" height="' + alto + '" preserveAspectRatio="xMidYMid slice"/>' : "") +
        '<rect y="' + (alto - 20) + '" width="' + ancho + '" height="20" fill="#000" opacity=".55"/>' +
        '<text x="4" y="' + (alto - 6) + '" class="reel-dato">' + esc(it.x ? veces(it.x) : (it.vistas ? cifra(it.vistas) : "")) + "</text></g>";
    });
    g.innerHTML = html;
    g.style.setProperty("--n", (-lista.length * (ancho + hueco)) + "px");
    g.style.animationDuration = (lista.length * 3.4) + "s";
    g.classList.add("corre");
  }

  // ------------------------------------------------------------------ el panel de mando, debajo de la oficina
  var mando = raiz.querySelector(".mando");
  function contar(nodo, hasta, formato) {
    if (!nodo) return;
    var desde = Number(nodo.dataset.valor || 0), t0 = null, dur = QUIETO ? 1 : 1100;
    if (desde === hasta && nodo.textContent) return;
    nodo.dataset.valor = hasta;
    function paso(t) {
      if (!t0) t0 = t;
      var k = Math.min(1, (t - t0) / dur), v = desde + (hasta - desde) * (1 - Math.pow(1 - k, 3));
      nodo.textContent = formato(v);
      if (k < 1) requestAnimationFrame(paso);
    }
    requestAnimationFrame(paso);
  }
  function entero(v) { return cifra(v); }
  // El embudo: un paso por fila del trabajo, con su muñequito, su cifra y una barra que dice cuánto pesa.
  function pintarEmbudo(panel) {
    var ol = mando.querySelector(".mando-embudo"), pasos = (panel && panel.embudo) || [];
    if (ol.children.length !== pasos.length) {
      ol.innerHTML = "";
      pasos.forEach(function (p, i) {
        var a = agente(p.clave), li = el("li", "mando-paso");
        li.style.setProperty("--c", a ? a.color : "#8b9cff");
        li.style.animationDelay = (i * 0.07) + "s";
        li.innerHTML = '<span class="mp-robot" data-robot="' + p.clave + '" data-robot-cabeza></span><span class="mp-etapa"></span>' +
          '<b class="mp-valor">0</b><span class="mp-unidad"></span><span class="mp-barra"><i></i></span><span class="mp-detalle"></span><i class="mp-flecha" aria-hidden="true"></i>';
        ol.appendChild(li);
      });
      RadarEquipo.rellenar(ol);
    }
    var max = Math.max.apply(null, pasos.map(function (p) { return Math.log10(1 + p.valor); }).concat([1]));
    pasos.forEach(function (p, i) {
      var li = ol.children[i], a = agente(p.clave);
      li.querySelector(".mp-etapa").textContent = p.etapa + (a ? " · " + a.nombre : "");
      li.querySelector(".mp-unidad").textContent = p.unidad;
      li.querySelector(".mp-detalle").textContent = p.detalle;
      li.querySelector(".mp-barra i").style.width = (Math.log10(1 + p.valor) / max * 100).toFixed(0) + "%";
      li.classList.toggle("vacio", !p.valor);
      li.dataset.estado = a ? (a.dormido ? "dormido" : a.estado) : "";
      contar(li.querySelector(".mp-valor"), p.valor, entero);
    });
    // La pizarra de Plani, en la oficina, enseña el mismo embudo.
    pasos.forEach(function (p, i) {
      var barra = mundo.querySelector('.tb-barra[data-i="' + i + '"]'), n = mundo.querySelector('.tb-n[data-i="' + i + '"]');
      if (!barra || !n) return;
      var alto = Math.max(2, Math.log10(1 + p.valor) / max * 104);
      barra.setAttribute("y", f1(72 - alto)); barra.setAttribute("height", f1(alto));
      var t = cifra(p.valor);
      if (n.textContent !== t) n.textContent = t;
    });
  }
  // Tu contenido: el mejor post, lo que se comparte y se comenta, cada red y el rasgo que mejor te funciona.
  function texto(sel, t) { var n = mando.querySelector(sel); if (n && n.textContent !== t) n.textContent = t; }
  function pintarContenido(c, m) {
    contar(mando.querySelector("[data-m=por-post]"), c.vistas_por_post || 0, cifra);
    contar(mando.querySelector("[data-m=envios]"), c.envios_mil || 0, function (v) { return v.toFixed(1).replace(".", ","); });
    contar(mando.querySelector("[data-m=comentarios]"), c.comentarios || 0, cifra);
    texto("[data-m=publicados]", (c.publicados || 0) + (c.publicados === 1 ? " publicado" : " publicados"));
    texto("[data-m=posts]", (m.posts || 0) + " posts medidos en total");
    if (c.mejor) {
      texto("[data-m=mejor-titulo]", c.mejor.titulo || "Sin título");
      texto("[data-m=mejor-datos]", cifra(c.mejor.vistas) + " visualizaciones" + (c.mejor.x ? " · " + veces(c.mejor.x) + " tu normal" : "") + " · " + c.mejor.red);
    }
    if (c.funciona) {
      texto("[data-m=funciona]", c.funciona.dimension + ": " + c.funciona.valor);
      texto("[data-m=funciona-datos]", "+" + c.funciona.subida + " % sobre tu normal en " + c.funciona.n + " posts" + (c.mejor_franja ? " · mejor hora: " + c.mejor_franja : ""));
    } else if (c.mejor_franja) texto("[data-m=funciona-datos]", "Mejor hora hasta ahora: " + c.mejor_franja);
    var redes = mando.querySelector("[data-m=redes]"), lista = c.por_red || [];
    var firma = lista.map(function (r) { return r.red + r.vistas; }).join("|");
    if (redes.dataset.firma !== firma) {
      redes.dataset.firma = firma;
      var max = Math.max.apply(null, lista.map(function (r) { return r.vistas; }).concat([1]));
      redes.innerHTML = lista.length ? lista.slice(0, 4).map(function (r) {
        return '<p class="red"><span>' + esc(r.red) + "</span><i><em style=\"width:" + Math.max(4, r.vistas / max * 100).toFixed(0) + '%"></em></i><b>' + esc(cifra(r.vistas)) + "</b></p>";
      }).join("") : "<span>Sin publicaciones</span>";
    }
  }
  function pintarMando(m, panel) {
    pintarEmbudo(panel);
    contar(mando.querySelector("[data-m=vistas]"), m.vistas_14d, cifra);
    contar(mando.querySelector("[data-m=posts]"), m.posts, function (v) { return String(Math.round(v)); });
    contar(mando.querySelector("[data-m=x]"), m.x_medio, function (v) { return "×" + v.toFixed(2).replace(".", ","); });
    contar(mando.querySelector("[data-m=aprobar]"), (panel && panel.por_aprobar) || 0, function (v) { return String(Math.round(v)); });
    pintarContenido((panel && panel.contenido) || {}, m);
    mando.querySelector(".mando-aprobar").classList.toggle("urge", !!(panel && panel.por_aprobar));
    var o = m.objetivo || {};
    mando.querySelector("[data-m=objetivo]").textContent = (o.hecho || 0) + " / " + (o.meta || 0);
    mando.querySelector("[data-m=objetivo-nombre]").textContent = o.nombre || "Objetivo";
    var pct = o.meta ? Math.min(1, (o.hecho || 0) / o.meta) : 0;
    mando.querySelector(".anillo-valor").style.strokeDashoffset = String(100 - pct * 100);
    var serie = m.serie || [], max = Math.max.apply(null, serie.concat([1]));
    var pts = serie.map(function (v, i) { return (i * 100 / Math.max(1, serie.length - 1)).toFixed(1) + "," + (36 - v / max * 32).toFixed(1); });
    var l = mando.querySelector(".curva-linea"), area = mando.querySelector(".curva-area"), nuevos = pts.join(" ");
    if (l.getAttribute("points") !== nuevos) {
      l.setAttribute("points", nuevos);
      area.setAttribute("points", "0,38 " + nuevos + " 100,38");
      l.classList.remove("dibuja"); void l.getBoundingClientRect(); l.classList.add("dibuja");
    }
  }

  // ------------------------------------------------------------------ enciende a tu equipo
  var bola = raiz.querySelector(".sala-desbloqueo");
  function pintarPasos(pasos) {
    if (!bola || !pasos) return;
    var hechos = pasos.filter(function (p) { return p.hecho; }).length, total = pasos.length;
    var antes = Number(bola.dataset.hechos || -1);
    bola.dataset.hechos = hechos;
    if (hechos >= total) {
      if (antes >= 0 && antes < total) { bola.classList.add("estalla"); setTimeout(function () { bola.hidden = true; }, 1600); }
      else bola.hidden = true;
      return;
    }
    bola.hidden = false;
    bola.querySelector("[data-pasos-cuenta]").textContent = hechos + "/" + total;
    bola.querySelector(".bola-anillo-valor").style.strokeDashoffset = String(100 - (hechos / total) * 100);
    if (antes >= 0 && hechos > antes) { bola.classList.remove("sube"); void bola.offsetWidth; bola.classList.add("sube"); }
    var lista = bola.querySelector(".pasos-lista");
    lista.innerHTML = "";
    var siguiente = true;
    pasos.forEach(function (p, i) {
      var li = el("li", p.hecho ? "hecho" : (siguiente ? "siguiente" : ""));
      li.appendChild(el("span", "paso-marca", p.hecho ? "✓" : String(i + 1)));
      var t = el("span", "paso-texto", p.texto);
      var quien = (p.agentes || []).map(function (k) { var a = agente(k); return a ? a.nombre : ""; }).filter(Boolean);
      if (!p.hecho && quien.length === estado.agentes.length) t.appendChild(el("small", "", "Enciende la luz de todo el equipo"));
      else if (!p.hecho && quien.length) t.appendChild(el("small", "", "Enciende la luz de " + quien.join(" y ")));
      li.appendChild(t);
      if (!p.hecho) { var a = el("a", "paso-ir", "Hacerlo"); a.href = p.enlace; li.appendChild(a); siguiente = false; }
      lista.appendChild(li);
    });
  }
  if (bola) {
    bola.querySelector(".bola").addEventListener("click", function (e) { e.stopPropagation(); bola.classList.toggle("abierta"); });
    bola.addEventListener("click", function (e) { e.stopPropagation(); });
    document.addEventListener("click", function () { bola.classList.remove("abierta"); });
  }

  // ------------------------------------------------------------------ el ascensor: subir a la planta de cada agente
  var planta = raiz.querySelector(".planta"), ascensor = raiz.querySelector(".ascensor");
  var indicador = ascensor.querySelector(".ascensor-indicador b"), flecha = ascensor.querySelector(".ascensor-indicador i");
  var viajando = false;
  function marcar(k) {
    raiz.classList.toggle("enfocada", !!k);
    Object.keys(cuartos).forEach(function (n) { cuartos[n].g.classList.toggle("activa", n === k); });
  }
  function contarPisos(desde, hasta, ms, alFinal) {
    var paso = desde < hasta ? 1 : -1, n = desde, veces_ = Math.abs(hasta - desde) || 1, cada = ms / veces_;
    flecha.textContent = paso > 0 ? "▲" : "▼";
    indicador.textContent = n === 0 ? "O" : String(n);
    var t = setInterval(function () {
      n += paso;
      indicador.textContent = n === 0 ? "O" : String(n);
      if (n === hasta) { clearInterval(t); if (alFinal) alFinal(); }
    }, cada);
    if (desde === hasta) { clearInterval(t); if (alFinal) alFinal(); }
  }
  // Clic en un cuarto: el muñequito se va al ascensor de cristal, la cabina sube por el hueco (la cámara la sigue y el
  // contador marca las plantas) y, al llegar, se abre su planta. Menos de dos segundos.
  var SUBIDA = 560;
  function apuntarAscensor(sube) {
    var m = medidas(), ar = m.w / m.h, c = centro("ascensor"), h = m.w < 720 ? 680 : 560, w = h * ar;
    objetivo = { x: c[0] - w / 2, y: c[1] - 50 - sube - h / 2, w: w, h: h };
  }
  function piezasAscensor() {
    var g = cuartos.ascensor.g;
    return { g: g, cabina: g.querySelector(".cabina"), ser: g.querySelector(".cabina-ser"), led: g.querySelector(".cabina-piso") };
  }
  function enfocar(k) {
    if (viajando || !agente(k) || !cuartos.ascensor) return;
    if (enfocado) { planta.classList.remove("abierta"); planta.hidden = true; cuartos[enfocado].g.classList.remove("fuera"); }
    viajando = true;
    enfocado = k;
    marcar(k);
    var a = agente(k), as = piezasAscensor(), c = cuartos.ascensor, o = ox, q = oy;
    ascensor.style.setProperty("--c", a.color);
    as.g.style.color = a.color;  // la cabina se ilumina con el color de quien viaja
    // El muñequito deja su cuarto y aparece dentro de la cabina.
    cuartos[k].g.classList.add("fuera");
    ox = c.ox; oy = c.oy;
    var p = P(110, 112, 10);
    ox = o; oy = q;
    as.ser.innerHTML = '<g class="ser" style="transform: translate(' + f1(p[0]) + "px," + f1(p[1]) + 'px)">' + muneco(k) + "</g>";
    as.g.classList.add("viaje");
    as.cabina.style.transform = "translateY(0px)";
    apuntarAscensor(0);
    ascensor.classList.add("sube");
    indicador.textContent = "O"; flecha.textContent = "▲";
    setTimeout(function () {
      as.cabina.style.transform = "translateY(" + (-SUBIDA) + "px)";
      apuntarAscensor(SUBIDA);
      contarPisos(0, PISOS[k], 1000, function () {
        if (as.led) as.led.textContent = String(PISOS[k]);
        setTimeout(function () {
          abrirPlanta(k);
          ascensor.classList.remove("sube");
          viajando = false;
        }, 150);
      });
    }, QUIETO ? 0 : 520);
  }
  function general() {
    if (!enfocado || viajando) return;
    viajando = true;
    var k = enfocado, as = piezasAscensor();
    planta.classList.remove("abierta");
    setTimeout(function () { planta.hidden = true; }, 300);
    ascensor.classList.add("sube");
    as.cabina.style.transform = "translateY(0px)";
    apuntarAscensor(0);
    contarPisos(PISOS[k], 0, 700, function () {
      setTimeout(function () {
        as.g.classList.remove("viaje");
        as.ser.innerHTML = "";
        if (as.led) as.led.textContent = "0";
        if (cuartos[k]) cuartos[k].g.classList.remove("fuera");
        ascensor.classList.remove("sube");
        enfocado = null;
        viajando = false;
        marcar(null); objetivo = clon(base);
      }, 200);
    });
  }
  botonGeneral.addEventListener("click", function (e) { e.stopPropagation(); general(); });
  planta.querySelector(".planta-bajar").addEventListener("click", function (e) { e.stopPropagation(); general(); });
  planta.addEventListener("click", function (e) { e.stopPropagation(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && enfocado) general(); });


  // La planta: el muñequito en grande sobre la plataforma del ascensor y, al lado, todo lo de su bloque.
  function abrirPlanta(clave) {
    var a = agente(clave);
    if (!a) return;
    planta.style.setProperty("--c", a.color);
    var cara = planta.querySelector(".planta-robot");
    if (cara.dataset.clave !== clave) { cara.dataset.clave = clave; cara.innerHTML = RadarEquipo.robot(clave); }
    planta.querySelector(".planta-muneco").dataset.estado = a.dormido ? "dormido" : a.estado;
    planta.querySelector(".planta-piso").textContent = "Planta " + PISOS[clave] + " · " + a.rol;
    planta.querySelector(".panel-nombre").textContent = a.nombre;
    planta.querySelector(".panel-rol").textContent = a.hace;
    planta.querySelector(".panel-hace").textContent = "";
    planta.querySelector(".panel-estado").textContent = a.dormido ? "Con la luz apagada hasta que hagas un paso" : a.texto;
    // Las cifras de su bloque: las del embudo que le tocan y la suya.
    var kpis = planta.querySelector(".planta-kpis"), html = "";
    ((estado.panel && estado.panel.embudo) || []).filter(function (p) { return p.clave === clave; }).forEach(function (p) {
      html += '<div class="pk"><b>' + esc(cifra(p.valor)) + "</b><small>" + esc(p.unidad) + "</small><span>" + esc(p.detalle) + "</span></div>";
    });
    if (!html) html = '<div class="pk"><b>' + esc(typeof a.cifra === "number" ? cifra(a.cifra) : a.cifra) + "</b><small>" + esc(a.etiqueta || "") + "</small></div>";
    if (clave === "jefa" && estado.panel) html += '<div class="pk"><b>' + estado.panel.por_aprobar + "</b><small>esperan tu OK</small><span>" + (estado.piloto ? "Piloto automático encendido" : "Piloto automático apagado") + "</span></div>";
    kpis.innerHTML = html;
    var despertar = planta.querySelector(".panel-despertar");
    if (a.dormido) {
      despertar.hidden = false;
      despertar.querySelector("span").textContent = "Para encender su luz: " + a.dormido.texto;
      despertar.querySelector("a").href = a.dormido.enlace;
    } else despertar.hidden = true;
    var lista = planta.querySelector(".panel-lista");
    lista.innerHTML = "";
    (a.pantalla || []).forEach(function (it) {
      var li = el("li"), img = it.imagen || it.portada;
      if (img) { var i = el("img"); i.src = img; i.alt = ""; i.referrerPolicy = "no-referrer"; i.onerror = function () { i.remove(); }; li.appendChild(i); }
      var txt = it.texto || it.titulo || ((it.red || "") + " · " + (it.hora || ""));
      if (it.cuenta) txt = "@" + String(it.cuenta).replace(/^@/, "") + " · " + veces(it.x);
      if (it.etapa) txt += " · " + it.etapa;
      var span = el("span", "", txt);
      if (it.url || it.video) { var e = el("a"); e.href = it.url || it.video; e.target = "_blank"; e.rel = "noopener"; e.appendChild(span); li.appendChild(e); }
      else li.appendChild(span);
      lista.appendChild(li);
    });
    planta.querySelector(".panel-ir").href = a.enlace || "#";
    var accion = planta.querySelector(".panel-accion");
    if (a.accion && !demo && !a.dormido) {
      accion.hidden = false;
      accion.textContent = a.accion.texto;
      accion.onclick = function (ev) {
        ev.stopPropagation();
        accion.disabled = true;
        fetch(a.accion.url, { method: "POST", credentials: "same-origin" }).then(function () {
          botar(clave); accion.disabled = false; setTimeout(pedir, 800);
        }).catch(function () { accion.disabled = false; });
      };
    } else accion.hidden = true;
    planta.hidden = false;
    requestAnimationFrame(function () { planta.classList.add("abierta"); });
  }

  // ------------------------------------------------------------------ lo último que ha pasado
  function anotar(ev, nuevo) {
    var li = el("li", nuevo ? "nuevo" : "");
    li.style.setProperty("--c", ev.color);
    li.appendChild(el("b", "", ev.nombre));
    li.appendChild(el("span", "", ev.texto));
    li.appendChild(el("time", "", (ev.cuando || "").slice(11, 16)));
    ticker.insertBefore(li, ticker.firstChild);
    while (ticker.children.length > 30) ticker.removeChild(ticker.lastChild);
  }

  // ------------------------------------------------------------------ montar y refrescar
  function aplicar(nuevo) {
    anterior = estado;
    estado = nuevo;
    if (!Object.keys(cuartos).length) {
      construir();
      if (ESCAPARATE && !demo) setTimeout(function () { if (!demo) botonDemo.click(); }, 1200);
      estado.eventos.slice().reverse().forEach(function (ev) { vistos[ev.cuando + ev.texto] = true; anotar(ev, false); });
    }
    estado.agentes.forEach(function (a) {
      pintarAgente(a);
      var antes = anterior && anterior.agentes.filter(function (x) { return x.clave === a.clave; })[0];
      if (antes && (a.cifra !== antes.cifra || a.estado !== antes.estado || !!a.dormido !== !!antes.dormido)) {
        decir(a.clave, antes.dormido && !a.dormido ? "¡Luz encendida! Me pongo" : a.texto, 3200);
        var i = estado.cadena.indexOf(a.clave);
        if (i > 0) paquete(estado.cadena[i - 1], a.clave, agente(estado.cadena[i - 1]).color);
        else botar(a.clave);
      }
    });
    if (estado.muros) { pintarCinta("cinta-nicho", estado.muros.izq); pintarCinta("cinta-tuyos", estado.muros.der); }
    pintarMando(estado.metricas, estado.panel);
    pintarPasos(estado.pasos);
    var chip = raiz.querySelector("[data-sala-piloto]");
    chip.textContent = estado.piloto ? "Piloto automático encendido" : "Piloto automático apagado";
    chip.classList.toggle("on", !!estado.piloto);
    estado.eventos.slice().reverse().forEach(function (ev) {
      var k = ev.cuando + ev.texto;
      if (!vistos[k]) { vistos[k] = true; anotar(ev, true); botar(ev.agente); }
    });
    if (enfocado && !viajando) abrirPlanta(enfocado);
  }

  function pedir() {
    if (demo || document.hidden) return;
    fetch(URL_VIVO, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(aplicar).catch(function () {});
  }

  // ------------------------------------------------------------------ simulación (para grabar la pantalla)
  var DEMO = {
    analista: ["Ha encontrado un reel ×7,4 en tu nicho", "Ha escaneado 6 cuentas", "Plantilla de remix lista"],
    estratega: ["Ha preparado 3 piezas para hoy", "Remix de un post con 1,2 M de visualizaciones"],
    guionista: ["Guion listo: «Por qué tus llamadas no cierran»", "El validador ha aprobado 2 guiones"],
    editor: ["Montando «3 errores al vender por llamada»", "Vídeo listo para revisar (v2 con tus notas)"],
    publicador: ["Programado en TikTok a las 19:00", "Publicado en YouTube Shorts"],
    comunidad: ["Nuevo lead: Laura (GUIA)", "3 DMs calientes con respuesta preparada"],
    jefa: ["Resumen de la mañana enviado", "Aprobado: Graba hoy"]
  };
  var DEMO_CUENTAS = ["marketing.claro", "ventas.con.ia", "growth.latino", "ia.para.negocios", "creadores.pro", "embudos.top"];
  var DEMO_TITULOS = ["3 prompts que uso cada día", "El error de los precios", "Cómo vendo sin llamadas", "Mi equipo de IA", "Ganchos que funcionan", "IA para tu oferta"];
  if (ESCAPARATE) {  // en la landing, sin cifras ni cuentas que parezcan de verdad
    DEMO = {
      analista: ["Ha encontrado un reel que despega en tu nicho", "Plantilla de remix lista", "Ha leído las noticias del sector"],
      estratega: ["«Graba hoy» listo para tu visto bueno", "Plan de la semana preparado"],
      guionista: ["Estructura lista para grabar", "El validador ha dado el visto bueno"],
      editor: ["Montando los reels de tu grabación", "Vídeo listo para revisar"],
      publicador: ["Programado en TikTok para esta tarde", "Publicado en Instagram"],
      comunidad: ["Guía enviada a quien comentó tu palabra", "Respuesta preparada para un DM"],
      jefa: ["Resumen de la mañana enviado", "Plan aprobado: el equipo se pone"]
    };
    DEMO_CUENTAS = ["referente.1", "referente.2", "referente.3", "referente.4", "referente.5"];
    DEMO_TITULOS = ["Lo que nadie te cuenta", "El error de los precios", "Mi equipo de contenido", "Ganchos que funcionan"];
  }
  function tickDemo() {
    if (!demo) return;
    var d = demoDatos, clave = azar(Object.keys(DEMO));
    d.agentes.forEach(function (a) {
      a.dormido = null;
      if (a.clave === clave) {
        a.estado = azar(["trabajando", "trabajando", "listo", "atencion"]);
        a.cifra = (Number(a.cifra) || 0) + 1;
        a.texto = azar(DEMO[clave]);
      } else if (Math.random() < 0.25) a.estado = azar(["listo", "trabajando"]);
    });
    d.metricas.vistas_14d += Math.round(800 + Math.random() * 6000);
    d.metricas.serie = d.metricas.serie.slice(1).concat([Math.round(2000 + Math.random() * 18000)]);
    d.metricas.posts += Math.random() < 0.3 ? 1 : 0;
    d.metricas.x_medio = Math.round((1.2 + Math.random() * 2.4) * 100) / 100;
    d.metricas.objetivo.hecho = Math.min(d.metricas.objetivo.meta, d.metricas.objetivo.hecho + (Math.random() < 0.4 ? 1 : 0));
    if (d.panel && d.panel.contenido && d.panel.contenido.mejor) {
      d.panel.contenido.comentarios += Math.floor(Math.random() * 4);
      d.panel.contenido.por_red.forEach(function (r) { r.vistas += Math.round(Math.random() * 900); });
    }
    if (d.panel) d.panel.embudo.forEach(function (p, i) {
      if (p.etapa === "Visto") p.valor = d.metricas.vistas_14d;
      else if (Math.random() < 0.3 + i * 0.03) p.valor += 1 + Math.floor(Math.random() * (i ? 2 : 6));
    });
    if (Math.random() < 0.35) d.muros.izq.items.unshift({ cuenta: azar(DEMO_CUENTAS), vistas: Math.round(40000 + Math.random() * 900000), x: Math.round((2 + Math.random() * 8) * 10) / 10 });
    if (Math.random() < 0.25) d.muros.der.items.unshift({ titulo: azar(DEMO_TITULOS), vistas: Math.round(3000 + Math.random() * 80000) });
    d.muros.izq.items = d.muros.izq.items.slice(0, 10); d.muros.der.items = d.muros.der.items.slice(0, 10);
    var ag = d.agentes.filter(function (a) { return a.clave === clave; })[0];
    d.eventos = [{ cuando: new Date().toISOString().slice(0, 19), agente: clave, nombre: ag.nombre, color: ag.color, texto: ag.texto }]
      .concat(d.eventos).slice(0, 24);
    aplicar(JSON.parse(JSON.stringify(d)));
    if (clave === "publicador" && cuartos.publicador) { var g = cuartos.publicador.g; g.classList.remove("despega"); void g.getBoundingClientRect(); g.classList.add("despega"); }
  }
  botonDemo.addEventListener("click", function (e) {
    e.stopPropagation();
    demo = !demo;
    botonDemo.classList.toggle("on", demo);
    botonDemo.textContent = demo ? "Simulación activa" : "Simular actividad";
    raiz.classList.toggle("en-demo", demo);
    if (demo) {
      demoDatos = JSON.parse(JSON.stringify(estado));
      demoDatos.metricas.vistas_14d = demoDatos.metricas.vistas_14d || 48200;
      demoDatos.metricas.serie = demoDatos.metricas.serie.map(function () { return Math.round(1500 + Math.random() * 15000); });
      demoDatos.metricas.posts = demoDatos.metricas.posts || 23;
      demoDatos.metricas.objetivo = { nombre: "Leads a la semana", hecho: 4, meta: 10 };
      if (demoDatos.panel) demoDatos.panel.contenido = {
        mejor: { titulo: "3 errores al vender por llamada", vistas: 128400, x: 6.2, red: "Instagram" },
        envios_mil: 18.4, comentarios: 312, publicados: 9, vistas_por_post: 14200,
        por_red: [{ red: "Instagram", vistas: 61200 }, { red: "TikTok", vistas: 44800 }, { red: "YouTube Shorts", vistas: 21900 }],
        funciona: { dimension: "Gancho", valor: "Pregunta incómoda", subida: 64, n: 7 }, mejor_franja: "Martes tarde"
      };
      if (demoDatos.panel) demoDatos.panel.embudo.forEach(function (p, i) { p.valor = Math.max(p.valor, [86, 21, 14, 9, 7, 0, 18][i] || 5); });
      demoDatos.muros = demoDatos.muros || {};
      ["izq", "der"].forEach(function (l) { demoDatos.muros[l] = demoDatos.muros[l] || { titulo: "", items: [] }; });
      tickDemo();
    } else pedir();
  });
  botonPantalla.addEventListener("click", function (e) {
    e.stopPropagation();
    // Solo la oficina, a toda pantalla (Esc o el botón de la esquina para salir).
    if (document.fullscreenElement) document.exitFullscreen();
    else if (escena.requestFullscreen) escena.requestFullscreen();
  });

  // La oficina respira: parpadeos, paseos por cada cuarto y trabajo viajando por el suelo.
  setInterval(function () {
    var ks = Object.keys(cuartos).filter(function (k) { return agente(k); });
    if (!ks.length) return;
    var g = cuartos[azar(ks)].g;
    g.classList.add("parpadea");
    setTimeout(function () { g.classList.remove("parpadea"); }, 170);
  }, 650);
  setInterval(moverse, 2600);
  setInterval(function () {
    if (!estado || QUIETO || document.hidden) return;
    var capa = mundo.querySelector(".chispas");
    if (!capa) return;
    estado.agentes.forEach(function (a) {
      if (a.estado !== "trabajando" || a.dormido || !PLANO[a.clave]) return;
      var c = centro(a.clave), t = document.createElementNS(NS, "text");
      t.setAttribute("x", f1(c[0] + (Math.random() - 0.5) * 90)); t.setAttribute("y", f1(c[1] - 40 - Math.random() * 30));
      t.setAttribute("class", "chispa"); t.setAttribute("fill", a.color);
      t.textContent = azar(["1", "0", "◆", "▲", "✦", "01", "10"]);
      capa.appendChild(t);
      setTimeout(function () { t.remove(); }, 2300);
    });
  }, 700);
  setInterval(function () {
    if (!estado || QUIETO) return;
    var despiertos = estado.cadena.filter(function (k) { var a = agente(k); return a && !a.dormido; });
    estado.agentes.forEach(function (a) {
      if (a.estado === "trabajando" && !a.dormido) {
        var i = estado.cadena.indexOf(a.clave);
        if (i >= 0) paquete(a.clave, estado.cadena[(i + 1) % estado.cadena.length], a.color);
      }
    });
    var orbi = agente("jefa");
    if (despiertos.length && orbi && !orbi.dormido) paquete("jefa", azar(despiertos), orbi.color);
  }, 2400);
  setInterval(function () { if (demo) tickDemo(); }, 2600);
  setInterval(pedir, 5000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) pedir(); });

  var salir = escena.querySelector("[data-sala-salir]");
  if (salir) salir.addEventListener("click", function (e) { e.stopPropagation(); if (document.fullscreenElement) document.exitFullscreen(); });

  // Al cambiar entre claro y oscuro, la oficina se redibuja con la otra paleta (sin perder la cámara).
  new MutationObserver(function () {
    if (!estado || !Object.keys(cuartos).length || viajando) return;
    var actual = estado, abierto = enfocado;
    if (abierto) { planta.hidden = true; planta.classList.remove("abierta"); enfocado = null; marcar(null); }
    cuartos = {}; etiquetas = {}; rotulos.innerHTML = "";
    estado = null;
    aplicar(actual);
    if (abierto) { objetivo = clon(base); }
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-tono"] });

  pedir();
})();
