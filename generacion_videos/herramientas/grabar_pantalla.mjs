// Graba una página web en vídeo con el Chrome sin ventana de Remotion (protocolo de DevTools, sin dependencias).
// Uso: node grabar_pantalla.mjs config.json
// config: {url, salida, ancho, alto, escala, segundos, espera, cookies?: archivo Netscape, cajas?: [selectores],
//          acciones?: [{t, tipo: "scroll"|"click"|"eval"|"hover"|"cajas", y?, selector?, js?, selectores?}]}
// Además del vídeo deja <salida>.cajas.json con la posición de cada selector de «cajas» (para hacer zoom al montar).
import {spawn, execFileSync} from 'node:child_process';
import {mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync, existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const aqui = dirname(fileURLToPath(import.meta.url));
const CHROME = join(aqui, '../remotion/node_modules/.remotion/chrome-headless-shell/mac-arm64/chrome-headless-shell-mac-arm64/chrome-headless-shell');
const cfg = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const {ancho = 1440, alto = 900, escala = 1.5, segundos = 10, espera = 2} = cfg;
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

const perfil = mkdtempSync(join(tmpdir(), 'grabar-'));
const fotos = join(perfil, 'fotos');
mkdirSync(fotos);
const puerto = 9300 + Math.floor(Math.random() * 500);
const chrome = spawn(CHROME, [`--remote-debugging-port=${puerto}`, `--user-data-dir=${perfil}`, '--hide-scrollbars',
  '--disable-gpu', `--window-size=${ancho},${alto}`, 'about:blank'], {stdio: 'ignore'});

let info;
for (let i = 0; i < 50 && !info; i++) {
  try { info = await (await fetch(`http://127.0.0.1:${puerto}/json/version`)).json(); } catch { await dormir(200); }
}
const ws = new WebSocket(info.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let n = 0;
const pendientes = new Map();
const oyentes = [];
ws.addEventListener('message', (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pendientes.has(msg.id)) { pendientes.get(msg.id)(msg); pendientes.delete(msg.id); }
  else oyentes.forEach((o) => o(msg));
});
const cdp = (method, params = {}, sessionId) => new Promise((res) => {
  const id = ++n;
  pendientes.set(id, res);
  ws.send(JSON.stringify({id, method, params, sessionId}));
});

const {result: {targetId}} = await cdp('Target.createTarget', {url: 'about:blank'});
const {result: {sessionId}} = await cdp('Target.attachToTarget', {targetId, flatten: true});
const s = (m, p) => cdp(m, p, sessionId);
await s('Page.enable');
await s('Emulation.setDeviceMetricsOverride', {width: ancho, height: alto, deviceScaleFactor: escala, mobile: false});
if (cfg.cookies) {
  for (const linea of readFileSync(cfg.cookies, 'utf8').split('\n')) {
    const c = linea.replace(/^#HttpOnly_/, '').split('\t');
    if (c.length < 7 || linea.startsWith('# ')) continue;
    await s('Network.setCookie', {name: c[5], value: c[6], domain: c[0], path: c[2], httpOnly: linea.startsWith('#HttpOnly_')});
  }
}
if (cfg.modo === 'virtual') {
  // Reloj falso: la página solo avanza cuando se llama a __avanza(ms). Temporizadores, requestAnimationFrame, fecha y
  // animaciones CSS van con él, así cada foto cae justo 1/30 s después de la anterior.
  await s('Page.addScriptToEvaluateOnNewDocument', {source: `(() => {
    let t = 0, sig = 1; const D0 = Date.now(), DateReal = Date;
    let marcos = [], tempos = [];
    performance.now = () => t;
    window.Date = class extends DateReal { constructor(...a) { if (a.length) super(...a); else super(D0 + t); } static now() { return D0 + t; } };
    window.requestAnimationFrame = (f) => { marcos.push([sig, f]); return sig++; };
    window.cancelAnimationFrame = (id) => { marcos = marcos.filter((m) => m[0] !== id); };
    window.setTimeout = (f, ms = 0, ...a) => { tempos.push({id: sig, f, a, cuando: t + Math.max(0, ms)}); return sig++; };
    window.setInterval = (f, ms = 0, ...a) => { tempos.push({id: sig, f, a, cuando: t + Math.max(1, ms), cada: Math.max(1, ms)}); return sig++; };
    window.clearTimeout = window.clearInterval = (id) => { tempos = tempos.filter((x) => x.id !== id); };
    window.__avanza = (ms) => {
      const fin = t + ms;
      for (;;) {
        tempos.sort((x, y) => x.cuando - y.cuando);
        const x = tempos[0];
        if (!x || x.cuando > fin) break;
        t = x.cuando;
        if (x.cada) x.cuando += x.cada; else tempos.shift();
        try { typeof x.f === 'function' ? x.f(...x.a) : eval(x.f); } catch (e) {}
      }
      t = fin;
      for (const a of document.getAnimations()) { try { a.pause(); a.__t = (a.__t ?? (a.currentTime || 0)) + ms; a.currentTime = a.__t; } catch (e) {} }
      const ms2 = marcos; marcos = [];
      for (const [, f] of ms2) { try { f(t); } catch (e) {} }
    };
  })()`});
}
await s('Page.navigate', {url: cfg.url});
await dormir(espera * 1000);
if (cfg.modo === 'virtual') for (let i = 0; i < espera * 30; i++) await s('Runtime.evaluate', {expression: '__avanza(1000/30)'});

const cuadros = [];
oyentes.push((msg) => {
  if (msg.method !== 'Page.screencastFrame') return;
  const {data, metadata, sessionId: sid} = msg.params;
  const archivo = join(fotos, `${String(cuadros.length).padStart(6, '0')}.jpg`);
  writeFileSync(archivo, Buffer.from(data, 'base64'));
  cuadros.push({archivo, t: metadata.timestamp});
  cdp('Page.screencastFrameAck', {sessionId: sid}, sessionId);
});
const js = (expr) => s('Runtime.evaluate', {expression: expr, awaitPromise: true, returnByValue: true});
if (cfg.cajas) {
  const r = await js(`JSON.stringify(Object.fromEntries(${JSON.stringify(cfg.cajas)}.map((sel) => {
    const e = document.querySelector(sel); if (!e) return [sel, null];
    const b = e.getBoundingClientRect(); return [sel, {x: b.x, y: b.y + scrollY, w: b.width, h: b.height}]; })))`);
  writeFileSync(`${cfg.salida}.cajas.json`, JSON.stringify({ancho, alto, cajas: JSON.parse(r.result.result.value)}, null, 1));
}
const medidas = [];
if (cfg.modo === 'virtual') {
  // Tiempo virtual: la página avanza 1/30 s con el reloj falso, se hace la foto y vuelta a empezar. Sale fluido aunque
  // la página sea pesada (el screencast normal se queda en pocos fotogramas por segundo a mucha resolución).
  const acciones = (cfg.acciones || []).sort((x, y) => x.t - y.t);
  let k = 0;
  const total = Math.round(segundos * 30);
  for (let i = 0; i < total; i++) {
    const t = i / 30;
    while (k < acciones.length && acciones[k].t <= t) {
      const a = acciones[k++];
      if (a.tipo === 'click') await js(`document.querySelector(${JSON.stringify(a.selector)})?.dispatchEvent(new MouseEvent("click", {bubbles: true}))`);
      if (a.tipo === 'eval') await js(a.js);
      if (a.tipo === 'cajas') {
        const r = await js(`JSON.stringify(Object.fromEntries(${JSON.stringify(a.selectores)}.map((sel) => {
          const e = document.querySelector(sel); if (!e) return [sel, null];
          const b = e.getBoundingClientRect(); return [sel, {x: b.x, y: b.y, w: b.width, h: b.height}]; })))`);
        medidas.push({t, cajas: JSON.parse(r.result.result.value)});
      }
    }
    await s('Runtime.evaluate', {expression: '__avanza(1000/30)'});
    const foto = await s('Page.captureScreenshot', {format: 'jpeg', quality: 90});
    const archivo = join(fotos, `${String(i).padStart(6, '0')}.jpg`);
    writeFileSync(archivo, Buffer.from(foto.result.data, 'base64'));
    cuadros.push({archivo, t});
  }
  chrome.kill();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '30', '-i', join(fotos, '%06d.jpg'), '-c:v', 'libx264', '-crf', '16',
    '-pix_fmt', 'yuv420p', cfg.salida]);
  if (medidas.length) writeFileSync(`${cfg.salida}.medidas.json`, JSON.stringify({ancho, alto, medidas}, null, 1));
  rmSync(perfil, {recursive: true, force: true});
  console.log(`${cfg.salida} · ${cuadros.length} fotos (tiempo virtual)`);
  process.exit(0);
}
await s('Page.startScreencast', {format: 'jpeg', quality: 88, maxWidth: Math.round(ancho * escala), maxHeight: Math.round(alto * escala)});
const inicio = Date.now();
for (const a of (cfg.acciones || []).sort((x, y) => x.t - y.t)) {
  await dormir(Math.max(0, a.t * 1000 - (Date.now() - inicio)));
  if (a.tipo === 'scroll') await js(`window.scrollTo({top: ${a.y}, behavior: 'smooth'})`);
  if (a.tipo === "click") await js(`document.querySelector(${JSON.stringify(a.selector)})?.dispatchEvent(new MouseEvent("click", {bubbles: true}))`);
  if (a.tipo === 'hover') await js(`document.querySelector(${JSON.stringify(a.selector)})?.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}))`);
  if (a.tipo === 'eval') await js(a.js);
  if (a.tipo === 'cajas') {
    const r = await js(`JSON.stringify(Object.fromEntries(${JSON.stringify(a.selectores)}.map((sel) => {
      const e = document.querySelector(sel); if (!e) return [sel, null];
      const b = e.getBoundingClientRect(); return [sel, {x: b.x, y: b.y, w: b.width, h: b.height}]; })))`);
    medidas.push({t: (Date.now() - inicio) / 1000, cajas: JSON.parse(r.result.result.value)});
  }
}
await dormir(Math.max(0, segundos * 1000 - (Date.now() - inicio)));
const finEpoch = Date.now() / 1000;
await s('Page.stopScreencast');
await dormir(300);
chrome.kill();

// Cada foto dura hasta la siguiente: el vídeo sale a 30 fps con el tiempo real.
const lista = cuadros.map((c, i) => `file '${c.archivo}'\nduration ${Math.max(0.001, ((cuadros[i + 1]?.t ?? Math.max(finEpoch, c.t + 0.1)) - c.t)).toFixed(4)}`).join('\n');
writeFileSync(join(perfil, 'lista.txt'), `${lista}\nfile '${cuadros.at(-1).archivo}'\n`);
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(perfil, 'lista.txt'), '-vf',
  'fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', cfg.salida]);
if (medidas.length) writeFileSync(`${cfg.salida}.medidas.json`, JSON.stringify({ancho, alto, medidas}, null, 1));
rmSync(perfil, {recursive: true, force: true});
console.log(`${cfg.salida} · ${cuadros.length} fotos`);
process.exit(0);
