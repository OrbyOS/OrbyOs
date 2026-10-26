/* La portada de la landing: Orby en 3D, vivo. Flota, mira hacia el cursor, parpadea y su anillo respira.
   Se para cuando no se ve; sin WebGL (o con «reducir movimiento») se queda el render fijo. */
import { montar } from "/static/orby3d.js?v=2";

const lienzo = document.querySelector("[data-orby3d]");
const escenario = lienzo && lienzo.closest(".ln-escenario");
const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function arrancar() {
  let e;
  try {
    e = montar(lienzo, { camara: [0.7, 0.85, 8.9], mira: [0, 0.38, 0], fov: 24, opacidadSombra: 0.38, contraluz: 2.6 });
  } catch (err) {
    return;  // sin WebGL: se queda la imagen de respaldo
  }
  escenario.classList.add("en-3d");
  const p = e.orby.userData.partes, THREE = e.THREE;
  const raton = { x: 0, y: 0 }, mira = { x: 0, y: 0 };
  window.addEventListener("pointermove", (ev) => {
    raton.x = (ev.clientX / window.innerWidth) * 2 - 1;
    raton.y = (ev.clientY / window.innerHeight) * 2 - 1;
  }, { passive: true });
  // En pantallas estrechas, la cámara se aleja para que Orby quepa entero.
  const base = e.camara.position.clone();
  function encajar() {
    e.ajustar();
    const k = Math.max(1, 0.95 / e.camara.aspect);
    e.camara.position.copy(base).sub(e.mira).multiplyScalar(k).add(e.mira);
    e.camara.lookAt(e.mira);
  }
  encajar();
  window.addEventListener("resize", encajar);

  // Parpadeo: un instante con los ojos cerrados, cada pocos segundos.
  let proximo = performance.now() + 2200, cerrando = 0;
  let visible = true;
  new IntersectionObserver((es) => { visible = es[0].isIntersecting; if (visible) requestAnimationFrame(bucle); }).observe(escenario);

  const anilloBase = p.anillo.material.emissiveIntensity;
  function bucle(t) {
    if (!visible) return;
    const s = t / 1000;
    // Flota y respira
    e.orby.position.y = Math.sin(s * 1.1) * 0.08;
    e.orby.rotation.y = -0.25 + Math.sin(s * 0.35) * 0.08;
    p.brazoIzq.rotation.z = -0.13 - Math.sin(s * 1.1 + 0.6) * 0.06;
    p.brazoDer.rotation.z = 0.13 + Math.sin(s * 1.1 + 0.6) * 0.06;
    p.anillo.material.emissiveIntensity = anilloBase * (0.8 + 0.25 * Math.sin(s * 2.2));
    // La cabeza sigue al cursor, con suavidad
    mira.x += (raton.x - mira.x) * 0.06; mira.y += (raton.y - mira.y) * 0.06;
    p.cabeza.rotation.y = -0.1 + mira.x * 0.42;
    p.cabeza.rotation.x = 0.04 + mira.y * 0.22;
    p.cabeza.rotation.z = -0.1 - mira.x * 0.06;
    // Parpadeo
    if (t > proximo) { cerrando = t; proximo = t + 2600 + Math.random() * 3200; }
    const parpado = t - cerrando < 130;
    p.ojos.visible = !parpado; p.cerrados.visible = parpado;
    e.render();
    if (!quieto) requestAnimationFrame(bucle);
  }
  requestAnimationFrame(bucle);
}

if (lienzo && escenario) arrancar();
