/* Orby y su equipo en 3D (Three.js): el modelo de verdad del que salen la landing y los renders de la oficina.
   Copia del retrato de Orby: porcelana mate crema con textura fina de papel arrugado, cabeza de huevo ladeada con
   costuras, visor negro grande con bisel, ojos enormes de cristal con iris de luz y destellos, sonrisa de luz, cuerpo
   de huevo abierto arriba con el anillo de luz dentro, costuras en S y brazos de pétalo que nacen en los hombros.
   Cada agente es el mismo modelo con su color y lo que lleva en la mano; Orby va limpio.

   crearOrby({ color, accesorio, dormido }) → THREE.Group (con .userData.partes para animar)
   montar(canvas, { color, accesorio, transparente, sombra }) → { escena, camara, render, orby, ...}   */
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

export const COLORES = { jefa: "#2F7BFF", analista: "#22D3EE", estratega: "#FBBF24", guionista: "#F472B6",
                         editor: "#34D399", publicador: "#A78BFA", comunidad: "#FB7185" };

// ------------------------------------------------------------------ texturas hechas a mano (canvas)
function lienzo(n, pintar, espacio = THREE.SRGBColorSpace) {
  const c = document.createElement("canvas");
  c.width = c.height = n;
  pintar(c.getContext("2d"), n);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = espacio;
  t.anisotropy = 8;
  return t;
}
function esOrby(color) { return String(color).toLowerCase() === COLORES.jefa.toLowerCase(); }
function mezclar(a, b, t) { const c = new THREE.Color(a); c.lerp(new THREE.Color(b), t); return "#" + c.getHexString(); }
let azar = 7;
function aleatorio() { azar = (azar * 16807) % 2147483647; return azar / 2147483647; }

// El iris, copiado del retrato a tamaño grande: aro azul muy luminoso que pasa a cian abajo a la izquierda, con
// fibras finas y chispas; pupila enorme azul noche con polvo de galaxia, desplazada hacia arriba a la derecha (mira
// hacia allí) con un filo de luz; y los dos brillos, el grande y el pequeño, junto a la pupila.
function texturaIris(color) {
  return lienzo(1024, (g, n) => {
    const m = n / 2, R = n / 2 * 0.97;
    // Los tonos medidos en el retrato: abajo a la izquierda cian casi blanco, a la izquierda azul vivo, arriba azul
    // marino y a la derecha casi negro. El iris está iluminado desde abajo a la izquierda.
    // Orby lleva los azules medidos en el retrato; el resto del equipo, los mismos tonos sacados de su color.
    const azul = esOrby(color);
    const cian = azul ? mezclar(color, "#55e6ff", 0.42) : mezclar(color, "#ffffff", 0.45);
    const vivo = azul ? mezclar(color, "#1f8fff", 0.3) : color;
    const marino = azul ? mezclar(color, "#062a78", 0.7) : mezclar(color, "#000000", 0.62);
    const noche = azul ? "#03123f" : mezclar(color, "#000000", 0.86);
    g.fillStyle = "#01030c"; g.fillRect(0, 0, n, n);
    g.save(); g.beginPath(); g.arc(m, m, R, 0, Math.PI * 2); g.clip();
    let r = g.createRadialGradient(m, m, R * 0.5, m, m, R);
    r.addColorStop(0, marino); r.addColorStop(0.75, noche); r.addColorStop(1, "#01051a");
    g.fillStyle = r; g.fillRect(0, 0, n, n);
    const l = g.createLinearGradient(m - R * 0.78, m + R * 0.78, m + R * 0.55, m - R * 0.55);
    l.addColorStop(0.02, cian); l.addColorStop(0.13, vivo); l.addColorStop(0.38, mezclar(vivo, "#001060", 0.35) + "dd"); l.addColorStop(0.68, "rgba(0,0,0,0)");
    g.fillStyle = l; g.fillRect(0, 0, n, n);
    // arriba a la derecha el iris cae a azul marino casi negro
    const s2 = g.createLinearGradient(m + R * 0.7, m - R * 0.7, m - R * 0.1, m + R * 0.1);
    s2.addColorStop(0, "rgba(0,6,40,.85)"); s2.addColorStop(1, "rgba(0,6,40,0)");
    g.fillStyle = s2; g.fillRect(0, 0, n, n);
    // el canto exterior, un poco más oscuro
    const canto = g.createRadialGradient(m, m, R * 0.86, m, m, R);
    canto.addColorStop(0, "rgba(0,4,20,0)"); canto.addColorStop(1, "rgba(0,4,20,.75)");
    g.fillStyle = canto; g.fillRect(0, 0, n, n);
    g.restore();
    // fibras finas y chispas
    for (let i = 0; i < 1400; i++) {
      const a = aleatorio() * Math.PI * 2, r1 = R * (0.52 + aleatorio() * 0.1), r2 = r1 + R * (0.06 + aleatorio() * 0.28);
      g.strokeStyle = aleatorio() < 0.7 ? `rgba(190,235,255,${0.04 + aleatorio() * 0.1})` : "rgba(0,20,80,.22)"; g.lineWidth = 0.6 + aleatorio() * 1.3;
      g.beginPath(); g.moveTo(m + Math.cos(a) * r1, m + Math.sin(a) * r1); g.lineTo(m + Math.cos(a) * r2, m + Math.sin(a) * r2); g.stroke();
    }
    for (let i = 0; i < 160; i++) {
      const a = aleatorio() * Math.PI * 2, d = R * (0.58 + aleatorio() * 0.32);
      g.fillStyle = "rgba(220,245,255,.8)"; g.beginPath(); g.arc(m + Math.cos(a) * d, m + Math.sin(a) * d, 0.8 + aleatorio() * 1.4, 0, Math.PI * 2); g.fill();
    }
    // el anillo exterior del iris, rayado como una esfera de reloj: marcas finas y un filo de luz
    for (let k = 0; k < 220; k++) {
      const a = (k / 220) * Math.PI * 2, largo = k % 5 === 0 ? 0.12 : 0.07;
      g.strokeStyle = `rgba(200,240,255,${k % 5 === 0 ? 0.32 : 0.18})`; g.lineWidth = 1.2;
      g.beginPath(); g.moveTo(m + Math.cos(a) * R * (0.92 - largo), m + Math.sin(a) * R * (0.92 - largo));
      g.lineTo(m + Math.cos(a) * R * 0.92, m + Math.sin(a) * R * 0.92); g.stroke();
    }
    g.strokeStyle = "rgba(150,220,255,.35)"; g.lineWidth = 2;
    g.beginPath(); g.arc(m, m, R * 0.93, 0, Math.PI * 2); g.stroke();
    // La pupila, como en el retrato: grande, un poco arriba a la derecha, sin borde duro. Negro azulado en el
    // centro que se abre a añil hacia fuera, con una nebulosa violeta abajo a la izquierda y estrellas finas
    // sobre todo en el borde.
    const px = m + R * 0.08, py = m - R * 0.06, RP = R * 0.6;
    r = g.createRadialGradient(px, py, 0, px, py, RP * 1.14);
    r.addColorStop(0, "#000105"); r.addColorStop(0.6, "#01030f"); r.addColorStop(0.76, "#040928");
    r.addColorStop(0.88, "rgba(12,22,96,.95)"); r.addColorStop(1, "rgba(20,40,140,0)");
    g.fillStyle = r; g.beginPath(); g.arc(px, py, RP * 1.14, 0, Math.PI * 2); g.fill();
    // nebulosa violeta y magenta, en el borde de abajo a la izquierda
    g.save(); g.beginPath(); g.arc(px, py, RP * 1.05, 0, Math.PI * 2); g.clip();
    [[-0.55, 0.6, 0.6, "rgba(150,70,235,.55)"], [-0.2, 0.85, 0.38, "rgba(225,90,210,.36)"], [-0.85, 0.2, 0.42, "rgba(100,70,235,.35)"]].forEach(([dx, dy, rr, col]) => {
      const n2 = g.createRadialGradient(px + dx * RP, py + dy * RP, 0, px + dx * RP, py + dy * RP, rr * RP);
      n2.addColorStop(0, col); n2.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = n2; g.fillRect(0, 0, n, n);
    });
    // el centro vuelve a ser casi negro
    const centro = g.createRadialGradient(px + RP * 0.05, py - RP * 0.05, 0, px, py, RP * 0.6);
    centro.addColorStop(0, "rgba(0,1,6,.9)"); centro.addColorStop(1, "rgba(0,1,6,0)");
    g.fillStyle = centro; g.fillRect(0, 0, n, n);
    g.restore();
    // estrellas: muchas finas en el borde de la pupila, pocas en el centro; rosas abajo a la izquierda
    for (let i = 0; i < 150; i++) {
      const a = aleatorio() * Math.PI * 2, d = RP * (aleatorio() < 0.2 ? 0.2 + aleatorio() * 0.5 : 0.72 + aleatorio() * 0.4);
      const abajoIzq = Math.cos(a) < -0.2 && Math.sin(a) > 0.2;
      g.fillStyle = abajoIzq && aleatorio() < 0.5 ? "#ff8fe0" : (aleatorio() < 0.6 ? "#ffffff" : "#9fd0ff");
      g.globalAlpha = 0.35 + aleatorio() * 0.6;
      g.beginPath(); g.arc(px + Math.cos(a) * d, py + Math.sin(a) * d, 0.5 + Math.pow(aleatorio(), 3) * 1.5, 0, Math.PI * 2); g.fill();
    }
    g.globalAlpha = 1;
    // Los brillos: dos perlas, con su volumen (blanco arriba, un gris perla abajo), junto al borde de la pupila
    const brillo = (x, y, rr) => {
      const b = g.createRadialGradient(x - rr * 0.3, y - rr * 0.35, 0, x, y, rr);
      b.addColorStop(0, "#ffffff"); b.addColorStop(0.55, "#f6f8fb"); b.addColorStop(0.9, "#cfd6e2"); b.addColorStop(1, "rgba(200,210,225,0)");
      g.fillStyle = b; g.beginPath(); g.arc(x, y, rr, 0, Math.PI * 2); g.fill();
    };
    brillo(m + R * 0.47, m - R * 0.34, R * 0.135);
    brillo(m + R * 0.3, m - R * 0.16, R * 0.058);
  });
}
function texturaHalo() {
  return lienzo(256, (g, n) => {
    const r = g.createRadialGradient(n / 2, n / 2, 0, n / 2, n / 2, n / 2);
    r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.25, "rgba(255,255,255,.4)"); r.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = r; g.fillRect(0, 0, n, n);
  });
}
// La textura de la porcelana del retrato: un relieve finísimo de pliegues, como papel arrugado o fieltro.
function texturaPliegues() {
  const t = lienzo(1024, (g, n) => {
    g.fillStyle = "#808080"; g.fillRect(0, 0, n, n);
    g.lineCap = g.lineJoin = "round";
    // pliegues: líneas quebradas largas, cada una con su lado de luz y su lado de sombra
    for (let i = 0; i < 700; i++) {
      let x = aleatorio() * n, y = aleatorio() * n, a = aleatorio() * Math.PI * 2;
      const tramos = 3 + Math.floor(aleatorio() * 6), puntos = [[x, y]];
      for (let k = 0; k < tramos; k++) { a += (aleatorio() - 0.5) * 1.3; const l = 10 + aleatorio() * 30; x += Math.cos(a) * l; y += Math.sin(a) * l; puntos.push([x, y]); }
      const w = 1.2 + aleatorio() * 2.4, f = 0.18 + aleatorio() * 0.22;
      [[`rgba(255,255,255,${f})`, -w * 0.6], [`rgba(0,0,0,${f})`, w * 0.6]].forEach(([c, d]) => {
        g.strokeStyle = c; g.lineWidth = w; g.beginPath();
        puntos.forEach(([px, py], k) => (k ? g.lineTo(px + d, py + d) : g.moveTo(px + d, py + d)));
        g.stroke();
      });
    }
    // un solo desenfoque suave para que los pliegues no tengan bordes duros
    const copia = document.createElement("canvas"); copia.width = copia.height = n;
    copia.getContext("2d").drawImage(g.canvas, 0, 0);
    g.filter = "blur(1.2px)"; g.drawImage(copia, 0, 0); g.filter = "none";
    // y un fondo de grano fino, como el fieltro
    for (let i = 0; i < 40000; i++) {
      g.fillStyle = aleatorio() < 0.5 ? "rgba(255,255,255,.12)" : "rgba(0,0,0,.12)";
      g.fillRect(aleatorio() * n, aleatorio() * n, 1.5, 1.5);
    }
  }, THREE.NoColorSpace);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}
// El grano de la porcelana: un moteado finísimo que le quita el aspecto de plástico.
function texturaGrano() {
  const t = lienzo(512, (g, n) => {
    g.fillStyle = "#ffffff"; g.fillRect(0, 0, n, n);
    for (let i = 0; i < 26000; i++) {
      g.fillStyle = aleatorio() < 0.6 ? "rgba(110,86,60,.16)" : "rgba(255,255,255,.6)";
      g.fillRect(aleatorio() * n, aleatorio() * n, 1 + aleatorio() * 1.5, 1 + aleatorio() * 1.5);
    }
  });
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}
let PLIEGUES = null, HALO = null, GRANO = null;
function porcelana(repetir = 3) {
  PLIEGUES = PLIEGUES || texturaPliegues();
  GRANO = GRANO || texturaGrano();
  const relieve = PLIEGUES.clone(); relieve.needsUpdate = true; relieve.repeat.set(repetir, repetir);
  const grano = GRANO.clone(); grano.needsUpdate = true; grano.repeat.set(repetir * 2, repetir * 2);
  return new THREE.MeshPhysicalMaterial({
    color: "#f0d3b6", roughness: 0.7, metalness: 0, clearcoat: 0.05, clearcoatRoughness: 0.6,
    sheen: 0.25, sheenColor: new THREE.Color("#fff1dc"), sheenRoughness: 0.75, map: grano, bumpMap: relieve, bumpScale: 0.6,
  });
}
// La luz de verdad (ojos cerrados, sonrisa, anillo): el color del agente, aclarado hacia el cian y por encima de 1,
// para que el resplandor lo recoja.
function luz(color, fuerza = 2) {
  const c = new THREE.Color(esOrby(color) ? mezclar(color, "#1f3fff", 0.5) : color).multiplyScalar(fuerza);
  const m = new THREE.MeshBasicMaterial({ color: c, toneMapped: false });
  m.userData.brilla = true;
  return m;
}
function emisivo(color, fuerza = 2.2) {
  return new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: fuerza, roughness: 0.3 });
}
const COSTURA = new THREE.MeshStandardMaterial({ color: "#cdc3b4", roughness: 0.9 });
function costura(puntos, grosor = 0.0065) {
  const curva = new THREE.CatmullRomCurve3(puntos);
  return new THREE.Mesh(new THREE.TubeGeometry(curva, 80, grosor, 6, false), COSTURA);
}

// ------------------------------------------------------------------ el modelo
export function crearOrby(opciones = {}) {
  const color = opciones.color || COLORES.jefa;
  const c = new THREE.Color(color);
  const orby = new THREE.Group(), partes = {};
  // El tronco (cuerpo, cuello y brazos) va un poco inclinado hacia delante, como en el retrato: así se ve la boca
  // del cuerpo desde arriba y la franja de luz del cuello dibuja su curva.
  const INCLINA = 0.2, tronco = new THREE.Group();
  tronco.rotation.x = INCLINA; orby.add(tronco); partes.tronco = tronco;
  const piel = porcelana(3), pielBrazo = porcelana(1.5);

  // El cuerpo: un huevo más ancho arriba, abierto por arriba (ahí asoma el anillo de luz).
  const radio = (u) => 0.73 * Math.sqrt(Math.max(0, 1 - u * u)) * (1 + 0.02 * u);
  const altura = (u) => -0.28 + 0.92 * u;
  const U_ARRIBA = 0.83, perfil = [];
  for (let i = 0; i <= 64; i++) {
    const u = -1 + (U_ARRIBA + 1) * (i / 64);
    perfil.push(new THREE.Vector2(Math.max(radio(u), 0.0001), altura(u)));
  }
  const cuerpo = new THREE.Mesh(new THREE.LatheGeometry(perfil, 128), piel);
  cuerpo.castShadow = true; cuerpo.receiveShadow = true;
  tronco.add(cuerpo); partes.cuerpo = cuerpo;
  const yBoca = altura(U_ARRIBA), rBoca = radio(U_ARRIBA);
  // El cuello, como en el retrato: el borde redondeado de la abertura, dentro un collarín oscuro y brillante con una
  // franja de luz alrededor justo por encima del borde, y encima el cuello corto donde se apoya la cabeza.
  const negroCuello = new THREE.MeshPhysicalMaterial({ color: "#0a0c12", roughness: 0.22, metalness: 0.2, clearcoat: 1, clearcoatRoughness: 0.1 });
  const borde = new THREE.Mesh(new THREE.TorusGeometry(rBoca - 0.02, 0.034, 24, 128), piel);
  borde.rotation.x = Math.PI / 2; borde.position.y = yBoca; borde.castShadow = borde.receiveShadow = true; tronco.add(borde);
  const collarin = new THREE.Mesh(new THREE.CylinderGeometry(rBoca - 0.055, rBoca - 0.045, 0.12, 96), negroCuello);
  collarin.position.y = yBoca - 0.03; tronco.add(collarin);
  const anillo = new THREE.Mesh(new THREE.CylinderGeometry(rBoca - 0.065, rBoca - 0.047, 0.065, 128, 1, true),
    Object.assign(new THREE.MeshBasicMaterial({ color: new THREE.Color(esOrby(color) ? mezclar(color, "#0a2cff", 0.35) : color).multiplyScalar(1.35), toneMapped: false }), { userData: { brilla: true } }));
  anillo.position.y = yBoca + 0.04; tronco.add(anillo); partes.anillo = anillo;
  const cuello = new THREE.Mesh(new THREE.CylinderGeometry(rBoca * 0.62, rBoca - 0.07, 0.16, 64), negroCuello);
  cuello.position.y = yBoca + 0.13; tronco.add(cuello);
  HALO = HALO || texturaHalo();
  const brilloAnillo = new THREE.Sprite(new THREE.SpriteMaterial({ map: HALO, color: c, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending, depthWrite: false }));
  brilloAnillo.scale.set(rBoca * 2.8, rBoca * 0.7, 1); brilloAnillo.position.set(0, yBoca + 0.05, rBoca * 0.75); tronco.add(brilloAnillo);
  // la franja de luz tiñe de azul el borde del cuerpo y la barbilla
  const luzCuello = new THREE.PointLight(color, 2.4, 1.0, 2); luzCuello.position.set(0, yBoca + 0.06, rBoca * 0.7); tronco.add(luzCuello);
  // Costuras del cuerpo: una en S por delante a la izquierda y otra en el costado derecho.
  const sobreCuerpo = (u, phi) => { const r = radio(u) * 1.003; return new THREE.Vector3(r * Math.sin(phi), altura(u), r * Math.cos(phi)); };
  const s1 = [], s2 = [];
  for (let i = 0; i <= 24; i++) {
    const t = i / 24, u = 0.74 - 1.6 * t;
    s1.push(sobreCuerpo(u, -0.32 - 0.62 * Math.sin(Math.PI * t * 0.95) - 0.18 * t));
    s2.push(sobreCuerpo(0.7 - 1.5 * t, 1.05 + 0.25 * Math.sin(Math.PI * t)));
  }
  tronco.add(costura(s1), costura(s2));

  // La cabeza: un huevo algo ladeado, con su visor.
  const cabeza = new THREE.Group();
  cabeza.position.set(0.07, (yBoca + 0.76) * Math.cos(INCLINA), (yBoca + 0.76) * Math.sin(INCLINA) - 0.12);
  orby.add(cabeza); partes.cabeza = cabeza;
  const HX = 0.93, HY = 0.78, HZ = 0.88;
  const geoCraneo = new THREE.SphereGeometry(1, 128, 96), pos = geoCraneo.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    const arriba = Math.max(0, v.y);
    v.z -= 0.1 * arriba * arriba;             // la parte de arriba se va un poco hacia atrás (huevo)
    v.x *= 1 + 0.04 * arriba;
    v.y *= v.y < 0 ? 0.97 : 1;                 // la barbilla, más recogida
    pos.setXYZ(i, v.x * HX, v.y * HY, v.z * HZ);
  }
  geoCraneo.computeVertexNormals();
  const craneo = new THREE.Mesh(geoCraneo, piel);
  craneo.castShadow = craneo.receiveShadow = true; cabeza.add(craneo);
  // costuras de la cabeza: arriba a la izquierda y en el lateral derecho
  const sobreCraneo = (lat, lon) => new THREE.Vector3(Math.cos(lat) * Math.sin(lon) * HX * 1.004, Math.sin(lat) * HY * 1.004 * (lat < 0 ? 0.97 : 1), (Math.cos(lat) * Math.cos(lon) - 0.1 * Math.max(0, Math.sin(lat)) ** 2) * HZ * 1.004);
  const h1 = [], h2 = [];
  for (let i = 0; i <= 20; i++) {
    const t = i / 20;
    h1.push(sobreCraneo(1.25 - 1.1 * t, -0.55 - 0.75 * t));
    h2.push(sobreCraneo(0.9 - 0.75 * t, 1.25 + 0.15 * t));
  }
  cabeza.add(costura(h1, 0.006), costura(h2, 0.006));

  // El visor: un óvalo de esquinas suaves, negro brillante, pegado a la cara y apenas abombado, con su bisel.
  // Se construye sobre la propia superficie del cráneo, así encaja sin huecos aunque la cabeza sea un huevo.
  const zCraneo = (X, Y) => {
    const sy = Y >= 0 ? Y / HY : Y / (HY * 0.97), sx = X / (HX * (1 + 0.04 * Math.max(0, sy)));
    const k = 1 - sx * sx - sy * sy;
    return k < 0 ? 0 : (Math.sqrt(k) - 0.1 * Math.max(0, sy) ** 2) * HZ;
  };
  const V = { rx: 0.76, ry: 0.5, cy: -0.06, n: 2.2 };
  const enVisor = (r, t) => {
    const cs = Math.cos(t), sn = Math.sin(t);
    // el extremo izquierdo, más alto y redondo; el derecho se estrecha un poco
    const n = V.n + 0.1 * cs, alto = 1 - 0.08 * cs;
    return [V.rx * r * Math.sign(cs) * Math.abs(cs) ** (2 / n), V.cy + V.ry * alto * r * Math.sign(sn) * Math.abs(sn) ** (2 / n)];
  };
  const zVisor = (X, Y) => {
    const r = Math.min(1, Math.hypot(X / V.rx, (Y - V.cy) / V.ry));
    return zCraneo(X, Y) + 0.024 + 0.022 * (1 - r * r);
  };
  const NR = 36, NT = 192, vis = [], idx = [];
  for (let i = 0; i <= NR; i++) for (let k = 0; k < NT; k++) {
    const [X, Y] = enVisor(i / NR, (k / NT) * Math.PI * 2);
    vis.push(X, Y, zVisor(X, Y));
  }
  for (let i = 0; i < NR; i++) for (let k = 0; k < NT; k++) {
    const a = i * NT + k, b = i * NT + (k + 1) % NT, c2 = a + NT, d = b + NT;
    idx.push(a, c2, b, b, c2, d);
  }
  const geoVisor = new THREE.BufferGeometry();
  geoVisor.setAttribute("position", new THREE.Float32BufferAttribute(vis, 3)); geoVisor.setIndex(idx); geoVisor.computeVertexNormals();
  const visor = new THREE.Mesh(geoVisor, new THREE.MeshPhysicalMaterial({
    color: "#030407", roughness: 0.3, metalness: 0.05, envMapIntensity: 0.35, clearcoat: 0.7, clearcoatRoughness: 0.25, side: THREE.DoubleSide }));
  cabeza.add(visor);
  const contorno = [];
  for (let k = 0; k < NT; k++) { const [X, Y] = enVisor(1, (k / NT) * Math.PI * 2); contorno.push(new THREE.Vector3(X, Y, zCraneo(X, Y) + 0.018)); }
  const bisel = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(contorno, true), 256, 0.02, 12, true),
    new THREE.MeshPhysicalMaterial({ color: "#14161d", roughness: 0.2, metalness: 0.3, clearcoat: 1 }));
  cabeza.add(bisel);
  const sobreVisor = (x, y, saca = 0.004) => {
    const e = 0.004, z = zVisor(x, y);
    const n = new THREE.Vector3(-(zVisor(x + e, y) - zVisor(x - e, y)) / (2 * e), -(zVisor(x, y + e) - zVisor(x, y - e)) / (2 * e), 1).normalize();
    return { p: new THREE.Vector3(x, y, z).addScaledVector(n, saca), n };
  };
  const pegar = (malla, x, y, saca) => {
    const { p, n } = sobreVisor(x, y, saca);
    malla.position.copy(p); malla.lookAt(p.clone().add(n));
    return malla;
  };

  // Los ojos: enormes, con su bisel de cristal, el iris que emite luz y una córnea que recoge los reflejos.
  const iris = texturaIris(color);
  const ojos = new THREE.Group(); cabeza.add(ojos); partes.ojos = ojos;
  const cerrados = new THREE.Group(); cabeza.add(cerrados); partes.cerrados = cerrados;
  const RO = 0.25;
  const negroBrillante = new THREE.MeshPhysicalMaterial({ color: "#07080c", roughness: 0.2, metalness: 0.1, envMapIntensity: 0.6, clearcoat: 1, clearcoatRoughness: 0.08 });
  [-0.35, 0.3].forEach((x) => {
    const y = 0.01, ojo = new THREE.Group();
    // el engaste: un aro negro grueso y redondeado que recoge la luz en su canto
    const engaste = pegar(new THREE.Mesh(new THREE.TorusGeometry(RO * 1.1, RO * 0.11, 24, 128), negroBrillante), x, y, 0.004);
    const fondo = pegar(new THREE.Mesh(new THREE.CircleGeometry(RO * 1.1, 96), new THREE.MeshBasicMaterial({ color: "#000000" })), x, y, 0.003);
    // el iris: brilla por sí mismo (por encima de 1, para que el resplandor lo recoja)
    const disco = pegar(new THREE.Mesh(new THREE.CircleGeometry(RO, 128), Object.assign(new THREE.MeshBasicMaterial({ map: iris, color: new THREE.Color(0.95, 0.95, 0.95), toneMapped: false }), { userData: { brilla: true } })), x, y, 0.008);
    // la córnea: una cúpula de cristal que deja reflejos suaves
    const RC = RO * 1.45, TC = Math.asin(1 / 1.45);
    const cornea = pegar(new THREE.Mesh(new THREE.SphereGeometry(RC, 64, 32, 0, Math.PI * 2, 0, TC),
      new THREE.MeshPhysicalMaterial({ color: "#ffffff", transparent: true, opacity: 0.025, roughness: 0.03, clearcoat: 1, depthWrite: false, envMapIntensity: 0.6 })), x, y, 0.01 - RC * Math.cos(TC));
    cornea.rotateX(Math.PI / 2);
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: HALO, color: c, transparent: true, opacity: 0.1, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.scale.set(RO * 3.4, RO * 3.4, 1); halo.position.copy(sobreVisor(x, y, 0.08).p);
    ojo.add(fondo, engaste, disco, cornea, halo);
    ojos.add(ojo);
    const arco = pegar(new THREE.Mesh(new THREE.TorusGeometry(RO * 0.62, 0.022, 10, 40, Math.PI), luz(color, 1.4)), x, y - 0.02, 0.012);
    arco.rotateZ(Math.PI);
    cerrados.add(arco);
  });
  // La sonrisa: un arco de luz pequeño entre los ojos
  const sonrisa = pegar(new THREE.Mesh(new THREE.TorusGeometry(0.085, 0.017, 12, 40, Math.PI * 0.72), luz(color, 0.9)), -0.03, -0.3, 0.012);
  sonrisa.rotateZ(Math.PI + Math.PI * 0.14);
  cabeza.add(sonrisa); partes.sonrisa = sonrisa;
  // ladeada y un poco girada, como en el retrato
  cabeza.rotation.set(0.06, 0.3, -0.3);
  ojos.visible = !opciones.dormido; cerrados.visible = !!opciones.dormido;

  // Los brazos: pétalos largos que nacen en los hombros, más gruesos arriba, con su costura.
  const brazo = (lado) => {
    const g = new THREE.Group(), perfilB = [];
    for (let i = 0; i <= 40; i++) {
      const t = i / 40, y = -0.62 + 1.24 * t;
      perfilB.push(new THREE.Vector2(Math.max(0.0001, 0.155 * Math.pow(Math.sin(Math.PI * t), 0.6) * (0.62 + 0.38 * t)), y));
    }
    const m = new THREE.Mesh(new THREE.LatheGeometry(perfilB, 64), pielBrazo);
    m.scale.set(1, 1, 0.55); m.castShadow = m.receiveShadow = true;
    g.add(m);
    const linea = [];
    for (let i = 0; i <= 16; i++) {
      const t = 0.08 + 0.84 * (i / 16), y = -0.62 + 1.24 * t, r = 0.155 * Math.pow(Math.sin(Math.PI * t), 0.6) * (0.62 + 0.38 * t);
      linea.push(new THREE.Vector3(-lado * r * 0.25, y, r * 0.55 * 1.02));
    }
    g.add(costura(linea, 0.0045));
    g.position.set(lado * 0.78, -0.25, 0.05);
    g.rotation.z = lado * 0.1;
    return g;
  };
  partes.brazoIzq = brazo(-1); partes.brazoDer = brazo(1);
  tronco.add(partes.brazoIzq, partes.brazoDer);

  if (opciones.accesorio) {
    const a = accesorio(opciones.accesorio, color);
    if (a) { a.position.add(new THREE.Vector3(1.0, -0.45, 0.3)); orby.add(a); partes.accesorio = a; }
  }
  orby.userData.partes = partes;
  return orby;
}

// ------------------------------------------------------------------ los objetos de cada oficio
function accesorio(tipo, color) {
  const g = new THREE.Group();
  const blanco = new THREE.MeshPhysicalMaterial({ color: "#f6f3ee", roughness: 0.35, clearcoat: 0.4 });
  const oscuro = new THREE.MeshPhysicalMaterial({ color: "#1b1e27", roughness: 0.35, clearcoat: 0.5 });
  const de = (c, extra = {}) => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.35, clearcoat: 0.4, ...extra });
  if (tipo === "analista") {  // la lupa
    const aro = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.035, 16, 48), de("#e9ecf2", { metalness: 0.6, roughness: 0.25 }));
    const cristal = new THREE.Mesh(new THREE.CircleGeometry(0.19, 48), new THREE.MeshPhysicalMaterial({ color: color, transparent: true, opacity: 0.28, roughness: 0, clearcoat: 1 }));
    const mango = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.04, 0.34, 16), oscuro);
    mango.position.set(-0.17, -0.3, 0); mango.rotation.z = 0.6;
    g.add(aro, cristal, mango); g.rotation.set(0.1, -0.5, -0.15);
  } else if (tipo === "estratega") {  // la carpeta con el plan
    const tabla = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.5, 0.03), de("#c9a35c"));
    const hoja = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.42, 0.01), blanco); hoja.position.z = 0.02;
    const pinza = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.06, 0.05), de("#e7e9ee", { metalness: 0.7, roughness: 0.25 })); pinza.position.set(0, 0.24, 0.03);
    g.add(tabla, hoja, pinza);
    [0.1, 0.02, -0.06, -0.14].forEach((y, i) => { const l = new THREE.Mesh(new THREE.BoxGeometry(i === 3 ? 0.14 : 0.22, 0.02, 0.005), de("#e0b766")); l.position.set(i === 3 ? -0.04 : 0, y, 0.028); g.add(l); });
    g.rotation.set(0.05, -0.45, -0.12);
  } else if (tipo === "guionista") {  // el lápiz
    const cuerpo = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.5, 6), de("#fbcfe8"));
    const goma = new THREE.Mesh(new THREE.CylinderGeometry(0.046, 0.046, 0.07, 6), de(color)); goma.position.y = 0.28;
    const punta = new THREE.Mesh(new THREE.ConeGeometry(0.045, 0.12, 6), de("#f3dcc0")); punta.position.y = -0.31; punta.rotation.x = Math.PI;
    const mina = new THREE.Mesh(new THREE.ConeGeometry(0.015, 0.04, 6), oscuro); mina.position.y = -0.36; mina.rotation.x = Math.PI;
    g.add(cuerpo, goma, punta, mina); g.rotation.set(0.2, 0, -0.65);
  } else if (tipo === "editor") {  // la claqueta
    const caja = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.3, 0.05), oscuro);
    const tapa = new THREE.Group(); tapa.position.set(-0.22, 0.17, 0);
    const liston = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.07, 0.05), blanco); liston.position.x = 0.22; tapa.add(liston);
    [0.06, 0.18, 0.3].forEach((x) => { const r = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.072, 0.052), oscuro); r.position.x = x; r.rotation.z = 0.5; tapa.add(r); });
    tapa.rotation.z = 0.22;
    const luz = new THREE.Mesh(new THREE.CircleGeometry(0.04, 24), emisivo(color, 2)); luz.position.set(0, -0.04, 0.03);
    g.add(caja, tapa, luz); g.rotation.set(0.05, -0.45, -0.08);
  } else if (tipo === "publicador") {  // el avión de papel
    const geo = new THREE.BufferGeometry();
    const v = [0, 0, 0.42, -0.26, 0, -0.2, 0, 0.02, -0.1, 0, 0, 0.42, 0, 0.02, -0.1, 0.26, 0, -0.2, 0, 0, 0.42, 0, 0.02, -0.1, 0, -0.12, -0.12];
    geo.setAttribute("position", new THREE.Float32BufferAttribute(v, 3)); geo.computeVertexNormals();
    const avion = new THREE.Mesh(geo, new THREE.MeshPhysicalMaterial({ color: "#f8f6f2", roughness: 0.5, side: THREE.DoubleSide }));
    g.add(avion); g.rotation.set(0.5, -0.9, 0.3);
  } else if (tipo === "comunidad") {  // el bocadillo con un corazón
    const burbuja = new THREE.Mesh(new THREE.SphereGeometry(0.24, 48, 32), blanco); burbuja.scale.set(1.25, 0.95, 0.5);
    const cola = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.16, 16), blanco); cola.position.set(-0.17, -0.22, 0); cola.rotation.z = -2.5;
    const corazon = new THREE.Shape();
    corazon.moveTo(0, -0.07); corazon.bezierCurveTo(-0.1, 0, -0.08, 0.09, 0, 0.04); corazon.bezierCurveTo(0.08, 0.09, 0.1, 0, 0, -0.07);
    const c3 = new THREE.Mesh(new THREE.ExtrudeGeometry(corazon, { depth: 0.03, bevelEnabled: true, bevelSize: 0.01, bevelThickness: 0.01, bevelSegments: 3 }), emisivo(color, 0.6));
    c3.position.set(0, 0, 0.11);
    g.add(burbuja, cola, c3); g.position.set(0.05, 1.6, 0); g.rotation.set(0, -0.35, 0);
  } else return null;
  return g;
}

// ------------------------------------------------------------------ escena lista para pintar
export function montar(canvas, opciones = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: !!opciones.captura });
  // Para capturar, la resolución que se pida; en pantalla, la del dispositivo (como mucho ×2).
  renderer.setPixelRatio(opciones.captura ? (opciones.pixeles || 2) : Math.min(window.devicePixelRatio || 1, opciones.pixeles || 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = opciones.exposicion || 1.0;
  renderer.shadowMap.enabled = opciones.sombras !== false;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  // Fondo: transparente por defecto; «crema» es el del retrato.
  if (opciones.fondo) renderer.setClearColor(new THREE.Color(opciones.fondo), 1); else renderer.setClearColor(0x000000, 0);

  const escena = new THREE.Scene();
  const pm = new THREE.PMREMGenerator(renderer);
  escena.environment = pm.fromScene(new RoomEnvironment(renderer), 0.04).texture;

  const color = new THREE.Color(opciones.color || COLORES.jefa);
  // Luz de estudio como la del retrato: una principal grande y cálida arriba a la izquierda que modela el volumen
  // (y hace que la cabeza dé sombra sobre el cuerpo), sombras cálidas que rebotan del suelo, un relleno suave a la
  // derecha y luz por detrás que dibuja el contorno.
  const clave = new THREE.DirectionalLight("#fff0e0", opciones.luzClave ?? 3.4);
  clave.position.set(3.2, 4.8, 3.4); clave.castShadow = true;
  clave.shadow.mapSize.set(2048, 2048); clave.shadow.radius = 6; clave.shadow.bias = -0.0004; clave.shadow.normalBias = 0.02;
  Object.assign(clave.shadow.camera, { left: -2.5, right: 2.5, top: 3, bottom: -2.5, near: 0.5, far: 20 });
  escena.add(clave);
  escena.add(new THREE.HemisphereLight("#fff0e0", "#9a6a44", 0.45));
  const relleno = new THREE.DirectionalLight("#ffd2a8", 0.15); relleno.position.set(-4.5, 0.5, 3); escena.add(relleno);
  const contra = new THREE.DirectionalLight(color, opciones.contraluz ?? 1.0); contra.position.set(3, 2, -4); escena.add(contra);
  const detras = new THREE.DirectionalLight("#fff1dc", opciones.luzDetras ?? 1.8); detras.position.set(-2.2, 2.2, -4.5); escena.add(detras);
  // y un resplandor suave en el fondo, detrás de Orby (solo si se pide: en los renders transparentes no va)
  if (opciones.aura) {
    const t = lienzo(256, (g, n) => {
      const r = g.createRadialGradient(n / 2, n / 2, 0, n / 2, n / 2, n / 2);
      r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.4, "rgba(255,255,255,.45)"); r.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = r; g.fillRect(0, 0, n, n);
    });
    const aura = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: t, color: opciones.aura, transparent: true,
      opacity: opciones.opacidadAura ?? 1, depthWrite: false, toneMapped: false }));
    aura.scale.set(6, 7, 1); aura.position.set(0, 0.6, -2.5); escena.add(aura);
  }

  // La sombra en el suelo: una mancha difusa, como la de una foto de estudio.
  if (opciones.sombra !== false) {
    const t = lienzo(256, (g, n) => {
      const r = g.createRadialGradient(n / 2, n / 2, 0, n / 2, n / 2, n / 2);
      r.addColorStop(0, "rgba(40,30,20,1)"); r.addColorStop(0.35, "rgba(40,30,20,.55)"); r.addColorStop(1, "rgba(40,30,20,0)");
      g.fillStyle = r; g.fillRect(0, 0, n, n);
    });
    const suelo = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.2), new THREE.MeshBasicMaterial({ map: t, transparent: true, opacity: opciones.opacidadSombra ?? 0.28, depthWrite: false }));
    suelo.rotation.x = -Math.PI / 2; suelo.position.set(0.1, -1.5, 0);
    escena.add(suelo);
  }

  const orby = crearOrby({ color: opciones.color, accesorio: opciones.accesorio, dormido: opciones.dormido });
  escena.add(orby);
  // La luz ambiente del estudio (en esta versión de Three se regula material a material)
  const ambiente = Number(opciones.ambiente ?? 0.55);
  const vistos = new Set();
  orby.traverse((o) => { const m = o.material; if (m && "envMapIntensity" in m && !vistos.has(m)) { vistos.add(m); m.envMapIntensity *= ambiente; } });

  const camara = new THREE.PerspectiveCamera(opciones.fov || 26, 1, 0.1, 100);
  camara.position.set(...(opciones.camara || [1.1, 0.75, 8.2]));
  const mira = new THREE.Vector3(...(opciones.mira || [0, 0.45, 0]));
  camara.lookAt(mira);

  // El resplandor: solo lo que brilla de verdad (ojos, sonrisa, anillo) suelta un halo, como en el retrato.
  // Se pinta aparte la escena con todo lo demás en negro, se difumina y se suma encima del render normal.
  let resplandor = null, capaBrillo = null;
  const camaraPlana = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  if (opciones.brillo !== false) {
    resplandor = new EffectComposer(renderer);
    resplandor.renderToScreen = false;
    resplandor.addPass(new RenderPass(escena, camara));
    resplandor.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), Number(opciones.brillo ?? 0.38), 0.2, 0));
    capaBrillo = new THREE.Scene();
    capaBrillo.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
      uniforms: { tBrillo: { value: resplandor.renderTarget2.texture } },
      vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
      fragmentShader: `uniform sampler2D tBrillo; varying vec2 vUv;
        void main() { vec3 g = texture2D(tBrillo, vUv).rgb; gl_FragColor = vec4(g, clamp(max(g.r, max(g.g, g.b)), 0.0, 1.0));
          #include <colorspace_fragment>
        }`,
      blending: THREE.AdditiveBlending, transparent: true, depthTest: false, depthWrite: false, toneMapped: false,
    })));
  }
  const NEGRO = new THREE.MeshBasicMaterial({ color: 0x000000 }), guardados = new Map();
  function pintarResplandor() {
    const fondoAntes = new THREE.Color(), alfaAntes = renderer.getClearAlpha();
    renderer.getClearColor(fondoAntes); renderer.setClearColor(0x000000, 0);
    escena.traverse((o) => {
      if (!o.isMesh && !o.isSprite) return;
      if (o.material && o.material.userData.brilla) return;
      if (o.isSprite || o.material.transparent) { guardados.set(o, o.visible); o.visible = false; }
      else { guardados.set(o, o.material); o.material = NEGRO; }
    });
    resplandor.render();
    guardados.forEach((v, o) => { if (typeof v === "boolean") o.visible = v; else o.material = v; });
    guardados.clear();
    renderer.setClearColor(fondoAntes, alfaAntes);
  }
  function render() {
    if (resplandor) pintarResplandor();
    renderer.render(escena, camara);
    if (capaBrillo) { renderer.autoClear = false; renderer.render(capaBrillo, camaraPlana); renderer.autoClear = true; }
  }

  function ajustar() {
    const w = canvas.clientWidth || canvas.width, h = canvas.clientHeight || canvas.height;
    renderer.setSize(w, h, false);
    [resplandor].forEach((c) => c && (c.setPixelRatio(renderer.getPixelRatio()), c.setSize(w, h)));
    camara.aspect = w / h; camara.updateProjectionMatrix();
  }
  ajustar();
  return { THREE, renderer, escena, camara, orby, mira, ajustar, render };
}
