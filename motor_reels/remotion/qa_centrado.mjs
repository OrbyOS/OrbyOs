// Centrado medido (control de calidad): renderiza fotogramas del reel con el vídeo cambiado por un gris plano y mide el
// centro horizontal de todo lo que va encima (subtítulos, titulares, rótulos, tarjetas). Así lo que se mide es solo lo
// que pone el motor, sin la lámpara ni la camisa. Uso: node qa_centrado.mjs <props.json> <public> <salida.json> <gris.jpg> [paso]
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const [propsRuta, publica, salida, gris, paso = '15', desde = '0', hasta = ''] = process.argv.slice(2);
const props = JSON.parse(fs.readFileSync(propsRuta, 'utf8'));
// Todo a vídeo real y sin fondo de color: el gris lo ocupa todo y cualquier otro píxel es un gráfico.
props.planos = props.planos.map((p) => ({...p, modo: 'real', fondo: undefined, entrada: 'corte', salida: 'corte'}));
props.kit = {...props.kit, estilo: {...(props.kit.estilo || {}), vista: true}};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-centrado-'));
for (const x of fs.readdirSync(publica)) if (x !== 'frames') fs.symlinkSync(path.resolve(publica, x), path.join(tmp, x));
fs.mkdirSync(path.join(tmp, 'frames'));
// El gris se copia dentro y se enlaza con enlaces duros: el servidor de Remotion no sirve bien un enlace a otro enlace.
const grisLocal = path.join(tmp, 'gris.jpg');
fs.copyFileSync(gris, grisLocal);
for (const x of fs.readdirSync(path.join(publica, 'frames'))) {
  if (x.startsWith('f_')) fs.linkSync(grisLocal, path.join(tmp, 'frames', x));
  else fs.symlinkSync(fs.realpathSync(path.resolve(publica, 'frames', x)), path.join(tmp, 'frames', x));
}

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: tmp});
const composition = await selectComposition({serveUrl, id: 'Reel', inputProps: props});
const fotos = [];
for (let f = Number(desde); f < Math.min(composition.durationInFrames, Number(hasta || Infinity)); f += Number(paso)) {
  const out = path.join(tmp, `c_${String(f).padStart(5, '0')}.png`);
  await renderStill({composition, serveUrl, output: out, frame: f, inputProps: props, imageFormat: 'png'});
  fotos.push({f, ruta: out});
}
fs.writeFileSync(salida, JSON.stringify({carpeta: tmp, fotos}));
console.log(fotos.length);
