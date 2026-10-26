/* Orby y su equipo en 3D (Three.js): el modelo de verdad del que salen la landing y los renders de la oficina.
   Porcelana con barniz, visor de cristal negro, ojos que emiten luz, anillo en el cuello y brazos que flotan.
   Cada agente es el mismo modelo con su color y lo que lleva en la mano; Orby va limpio.

   crearOrby({ color, accesorio, dormido }) → THREE.Group (con .partes para animar)
   montar(canvas, { color, accesorio, transparente, sombra }) → { escena, camara, render, orby, ...}   */
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export const COLORES = { jefa: "#3D7BFF", analista: "#22D3EE", estratega: "#FBBF24", guionista: "#F472B6",
                         editor: "#34D399", publicador: "#A78BFA", comunidad: "#FB7185" };

// ------------------------------------------------------------------ texturas hechas a mano (canvas)
function lienzo(n, pintar) {
  const c = document.createElement("canvas");
  c.width = c.height = n;
  pintar(c.getContext("2d"), n);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}
function aclarar(hex, t) {
  const c = new THREE.Color(hex); c.lerp(new THREE.Color("#ffffff"), t);
  return "#" + c.getHexString();
}
// El iris: anillo de luz del color del agente, pupila grande y dos brillos.
function texturaIris(color) {
  return lienzo(512, (g, n) => {
    const m = n / 2;
    g.fillStyle = "#03040a"; g.fillRect(0, 0, n, n);
    let r = g.createRadialGradient(m, m * 1.04, n * 0.12, m, m, n * 0.5);
    r.addColorStop(0, "#04081c"); r.addColorStop(0.34, "#061235");
    r.addColorStop(0.46, color); r.addColorStop(0.68, aclarar(color, 0.55)); r.addColorStop(0.8, color);
    r.addColorStop(0.95, "#0a1a52"); r.addColorStop(1, "#02030a");
    g.fillStyle = r; g.beginPath(); g.arc(m, m, n * 0.5, 0, Math.PI * 2); g.fill();
    // fibras del iris
    g.globalAlpha = 0.22; g.strokeStyle = "#ffffff"; g.lineWidth = 2;
    for (let i = 0; i < 90; i++) {
      const a = (i / 90) * Math.PI * 2, r1 = n * 0.2, r2 = n * (0.36 + 0.06 * Math.random());
      g.beginPath(); g.moveTo(m + Math.cos(a) * r1, m + Math.sin(a) * r1); g.lineTo(m + Math.cos(a) * r2, m + Math.sin(a) * r2); g.stroke();
    }
    g.globalAlpha = 1;
    // pupila
    r = g.createRadialGradient(m, m, 0, m, m, n * 0.2);
    r.addColorStop(0, "#000"); r.addColorStop(0.85, "#020615"); r.addColorStop(1, "rgba(2,6,21,0)");
    g.fillStyle = r; g.beginPath(); g.arc(m, m, n * 0.2, 0, Math.PI * 2); g.fill();
    // brillos
    g.fillStyle = "#fff"; g.beginPath(); g.arc(m + n * 0.12, m - n * 0.13, n * 0.075, 0, Math.PI * 2); g.fill();
    g.globalAlpha = 0.75; g.beginPath(); g.arc(m - n * 0.11, m + n * 0.12, n * 0.035, 0, Math.PI * 2); g.fill();
  });
}
// Halo de luz (para sprites aditivos)
function texturaHalo() {
  return lienzo(256, (g, n) => {
    const r = g.createRadialGradient(n / 2, n / 2, 0, n / 2, n / 2, n / 2);
    r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.25, "rgba(255,255,255,.45)"); r.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = r; g.fillRect(0, 0, n, n);
  });
}
// Grano de la porcelana (relieve muy fino, como en el retrato)
function texturaGrano() {
  const t = lienzo(512, (g, n) => {
    const d = g.createImageData(n, n);
    for (let i = 0; i < d.data.length; i += 4) {
      const v = 128 + (Math.random() - 0.5) * 70;
      d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255;
    }
    g.putImageData(d, 0, 0);
  });
  t.colorSpace = THREE.NoColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(3, 3);
  return t;
}

let GRANO = null, HALO = null;
function porcelana() {
  GRANO = GRANO || texturaGrano();
  return new THREE.MeshPhysicalMaterial({
    color: "#efe9df", roughness: 0.45, metalness: 0, clearcoat: 0.55, clearcoatRoughness: 0.28,
    sheen: 0.35, sheenColor: new THREE.Color("#ffffff"), sheenRoughness: 0.6, bumpMap: GRANO, bumpScale: 0.0035,
  });
}
function emisivo(color, fuerza = 2.2) {
  return new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: fuerza, roughness: 0.3 });
}

// ------------------------------------------------------------------ el modelo
export function crearOrby(opciones = {}) {
  const color = opciones.color || COLORES.jefa;
  const c = new THREE.Color(color);
  const orby = new THREE.Group(), partes = {};
  const piel = porcelana();

  // El cuerpo: un huevo (torno) algo más ancho arriba.
  const perfil = [];
  for (let i = 0; i <= 48; i++) {
    const u = -1 + (2 * i) / 48, y = -0.22 + 0.8 * u;  // de -1,02 a 0,58
    const r = 0.6 * Math.sqrt(Math.max(0, 1 - u * u)) * (1 + 0.1 * u) * (1 - 0.05 * u * u);
    perfil.push(new THREE.Vector2(Math.max(r, 0.0001), y));
  }
  const cuerpo = new THREE.Mesh(new THREE.LatheGeometry(perfil, 96), piel);
  cuerpo.castShadow = true; cuerpo.receiveShadow = true;
  orby.add(cuerpo); partes.cuerpo = cuerpo;

  // El cuello: un anillo de luz del color del agente.
  const cuello = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.3, 0.16, 48), new THREE.MeshStandardMaterial({ color: "#1a1d26", roughness: 0.4 }));
  cuello.position.y = 0.6; orby.add(cuello);
  const anillo = new THREE.Mesh(new THREE.TorusGeometry(0.29, 0.034, 16, 72), emisivo(color, 2.6));
  anillo.rotation.x = Math.PI / 2; anillo.position.y = 0.6; orby.add(anillo); partes.anillo = anillo;

  // La cabeza (grupo propio, para que mire y se ladee).
  const cabeza = new THREE.Group();
  cabeza.position.y = 1.34;
  orby.add(cabeza); partes.cabeza = cabeza;
  const RX = 0.9, RY = 0.74, RZ = 0.84;
  const craneo = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64), piel);
  craneo.scale.set(RX, RY, RZ); craneo.castShadow = true;
  cabeza.add(craneo);
  // El visor: otro elipsoide que asoma por delante; el corte entre los dos dibuja el óvalo.
  const V = { rx: 0.78, ry: 0.52, rz: 0.6, cz: 0.3 };
  const visor = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64), new THREE.MeshPhysicalMaterial({
    color: "#040508", roughness: 0.07, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.04, reflectivity: 0.6 }));
  visor.scale.set(V.rx, V.ry, V.rz); visor.position.set(0, -0.03, V.cz);
  cabeza.add(visor);
  // Un punto sobre el visor y su normal (para pegar ojos y sonrisa).
  const sobreVisor = (x, y, saca = 0.004) => {
    const yy = y + 0.03, k = 1 - (x / V.rx) ** 2 - (yy / V.ry) ** 2;
    const z = V.cz + V.rz * Math.sqrt(Math.max(0, k));
    const n = new THREE.Vector3(x / V.rx ** 2, yy / V.ry ** 2, (z - V.cz) / V.rz ** 2).normalize();
    return { p: new THREE.Vector3(x, y, z).addScaledVector(n, saca), n };
  };
  const pegar = (malla, x, y, saca) => {
    const { p, n } = sobreVisor(x, y, saca);
    malla.position.copy(p); malla.lookAt(p.clone().add(n));
    return malla;
  };

  // Los ojos: borde oscuro, iris que emite luz y un halo.
  HALO = HALO || texturaHalo();
  const iris = texturaIris(color);
  const ojos = new THREE.Group(); cabeza.add(ojos); partes.ojos = ojos;
  const cerrados = new THREE.Group(); cabeza.add(cerrados); partes.cerrados = cerrados;
  [-0.29, 0.29].forEach((x) => {
    const ojo = new THREE.Group();
    const borde = pegar(new THREE.Mesh(new THREE.CircleGeometry(0.24, 64), new THREE.MeshPhysicalMaterial({ color: "#0b0e18", roughness: 0.2, clearcoat: 1 })), x, 0.02, 0.006);
    const disco = pegar(new THREE.Mesh(new THREE.CircleGeometry(0.205, 64), new THREE.MeshStandardMaterial({
      map: iris, emissiveMap: iris, emissive: "#ffffff", emissiveIntensity: 1.25, roughness: 0.25 })), x, 0.02, 0.012);
    // la córnea: una cúpula de cristal que coge los reflejos
    const cornea = pegar(new THREE.Mesh(new THREE.SphereGeometry(0.212, 48, 24, 0, Math.PI * 2, 0, 0.9),
      new THREE.MeshPhysicalMaterial({ color: "#ffffff", transparent: true, opacity: 0.12, roughness: 0.02, clearcoat: 1, transmission: 0 })), x, 0.02, -0.11);
    cornea.rotateX(Math.PI / 2);
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: HALO, color: c, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.scale.set(0.9, 0.9, 1); halo.position.copy(sobreVisor(x, 0.02, 0.05).p);
    ojo.add(borde, disco, cornea, halo);
    ojos.add(ojo);
    // dormido: un arco de luz
    const arco = pegar(new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.02, 10, 32, Math.PI), emisivo(color, 2)), x, -0.01, 0.012);
    arco.rotateZ(Math.PI);
    cerrados.add(arco);
  });
  // La sonrisa
  const sonrisa = pegar(new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.015, 10, 32, Math.PI * 0.8), emisivo(color, 2.4)), 0, -0.24, 0.01);
  sonrisa.rotateZ(Math.PI + Math.PI * 0.1);
  cabeza.add(sonrisa); partes.sonrisa = sonrisa;
  cabeza.rotation.set(0.04, -0.1, -0.1);
  ojos.visible = !opciones.dormido; cerrados.visible = !!opciones.dormido;

  // Los brazos: aletas que flotan a los lados.
  const brazo = (lado) => {
    const g = new THREE.Group();
    const perfilB = [];
    for (let i = 0; i <= 24; i++) {
      const t = i / 24, y = -0.36 + 0.78 * t;
      perfilB.push(new THREE.Vector2(Math.max(0.0001, 0.115 * Math.pow(Math.sin(Math.PI * t), 0.65) * (0.7 + 0.3 * t)), y));
    }
    const m = new THREE.Mesh(new THREE.LatheGeometry(perfilB, 48), piel);
    m.scale.set(1, 1, 0.62); m.castShadow = true;
    g.add(m);
    g.position.set(lado * 0.76, -0.2, 0.02);
    g.rotation.z = lado * 0.13;
    return g;
  };
  partes.brazoIzq = brazo(-1); partes.brazoDer = brazo(1);
  orby.add(partes.brazoIzq, partes.brazoDer);

  // Lo que lleva cada uno, junto a la mano derecha.
  if (opciones.accesorio) {
    const a = accesorio(opciones.accesorio, color);
    if (a) { a.position.add(new THREE.Vector3(1.0, -0.42, 0.3)); orby.add(a); partes.accesorio = a; }
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
  renderer.toneMappingExposure = opciones.exposicion || 0.92;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setClearColor(0x000000, 0);

  const escena = new THREE.Scene();
  const pm = new THREE.PMREMGenerator(renderer);
  escena.environment = pm.fromScene(new RoomEnvironment(renderer), 0.04).texture;
  escena.environmentIntensity = opciones.ambiente ?? 0.6;

  const color = new THREE.Color(opciones.color || COLORES.jefa);
  // Luz principal arriba a la izquierda, relleno frío, contraluz del color del agente.
  const clave = new THREE.DirectionalLight("#fff6ec", 2.4);
  clave.position.set(-1.8, 7, 3.2); clave.castShadow = true;
  clave.shadow.mapSize.set(2048, 2048); clave.shadow.radius = 6; clave.shadow.bias = -0.0005;
  Object.assign(clave.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 0.5, far: 20 });
  escena.add(clave);
  const relleno = new THREE.DirectionalLight("#c9d8ff", 0.6); relleno.position.set(4, 1.5, 3); escena.add(relleno);
  const contra = new THREE.DirectionalLight(color, opciones.contraluz ?? 2.2); contra.position.set(2.5, 3, -4); escena.add(contra);
  const contra2 = new THREE.DirectionalLight(color, (opciones.contraluz ?? 2.2) * 0.6); contra2.position.set(-3, 1, -3); escena.add(contra2);

  // El suelo invisible que solo recoge la sombra.
  if (opciones.sombra !== false) {
    const suelo = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.ShadowMaterial({ opacity: opciones.opacidadSombra ?? 0.28 }));
    suelo.rotation.x = -Math.PI / 2; suelo.position.y = -1.42; suelo.receiveShadow = true;
    escena.add(suelo);
  }

  const orby = crearOrby({ color: opciones.color, accesorio: opciones.accesorio, dormido: opciones.dormido });
  escena.add(orby);

  const camara = new THREE.PerspectiveCamera(opciones.fov || 26, 1, 0.1, 100);
  camara.position.set(...(opciones.camara || [1.1, 0.75, 8.2]));
  const mira = new THREE.Vector3(...(opciones.mira || [0, 0.45, 0]));
  camara.lookAt(mira);

  function ajustar() {
    const w = canvas.clientWidth || canvas.width, h = canvas.clientHeight || canvas.height;
    renderer.setSize(w, h, false);
    camara.aspect = w / h; camara.updateProjectionMatrix();
  }
  ajustar();
  return { THREE, renderer, escena, camara, orby, mira, ajustar, render: () => renderer.render(escena, camara) };
}
