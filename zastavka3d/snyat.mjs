// Съёмка заставки из 3D-сцены (r521). Только в облаке GitHub Actions (Р243) — локально не запускать.
// Детерминированно: ручные часы (performance.now / Date.now / requestAnimationFrame / setTimeout),
// шаг 1/30 с, скриншот #r3Stage на каждый кадр. Кадры — PNG в out/<format>/f00000.png …
// node zastavka3d/snyat.mjs <папка-сцены> <W> <H> <выход>
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const [dir, W, H, out] = [process.argv[2], +process.argv[3], +process.argv[4], process.argv[5]];
const FPS = 30, STEP = 1000 / FPS;
const START = +(process.env.START || 4.2);   // секунда отсчёта, с которой снимаем (зажигание — 4,5 с, отрыв — 8,1 с)
const DUR = +(process.env.DUR || 8);           // длина съёмки, с
fs.mkdirSync(out, { recursive: true });

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.wasm': 'application/wasm', '.mp3': 'audio/mpeg', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.json': 'application/json' };
const root = path.resolve(dir);
const srv = http.createServer((q, r) => {
  let p = decodeURIComponent(new URL(q.url, 'http://x').pathname); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(root, p);
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); r.end(); return; }
  r.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(r);
}).listen(0, '127.0.0.1');
await new Promise((ok) => srv.once('listening', ok));
const port = srv.address().port;

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required', '--mute-audio'] });
// Ширина окна ≥ 800: иначе сцена считает себя телефоном (SLAB) и урезает частицы и тени. Сцена — ровно W×H в левом верхнем углу.
const page = await browser.newPage({ viewport: { width: Math.max(W, 800), height: H }, deviceScaleFactor: 1, reducedMotion: 'no-preference' });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.addInitScript(() => {
  let t = 1000; const d0 = Date.now();
  performance.now = () => t; Date.now = () => d0 + t;
  let cbs = [], rid = 0;
  window.requestAnimationFrame = (cb) => { cbs.push([++rid, cb]); return rid; };
  window.cancelAnimationFrame = (i) => { cbs = cbs.filter((c) => c[0] !== i); };
  const rST = window.setTimeout.bind(window), rCT = window.clearTimeout.bind(window);
  let timers = [], tid = 1e9, virt = false;
  window.setTimeout = (fn, ms, ...a) => { if (!virt) return rST(fn, ms, ...a); timers.push({ id: ++tid, at: t + (+ms || 0), fn, a }); return tid; };
  window.clearTimeout = (i) => { if (i > 1e9) timers = timers.filter((x) => x.id !== i); else rCT(i); };
  let s = 521;   // mulberry32: тряска, пламя и дым одинаковы от прогона к прогону
  Math.random = () => { s |= 0; s = (s + 0x6D2B79F5) | 0; let z = Math.imul(s ^ (s >>> 15), 1 | s); z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z; return ((z ^ (z >>> 14)) >>> 0) / 4294967296; };
  window.__vt = {
    step(ms) {
      t += ms;
      const due = timers.filter((x) => x.at <= t); timers = timers.filter((x) => x.at > t);
      for (const x of due) { try { typeof x.fn === 'function' ? x.fn(...x.a) : 0; } catch (e) { console.error(e); } }
      const c = cbs; cbs = []; for (const [, cb] of c) cb(t);
    },
    virt(on) { virt = on; },
  };
});
await page.goto(`http://127.0.0.1:${port}/index.html?w=${W}&h=${H}`);
const step = (n = 1) => page.evaluate(([n, ms]) => { for (let i = 0; i < n; i++) window.__vt.step(ms); }, [n, STEP]);
const st = () => page.evaluate(() => window.__r7 ? window.__r7.st() : null);

for (let i = 0; !(await st()); i++) {   // сцена грузится (настоящее время для сети), часы стоят, кадры шагаем вручную
  if (i > 600) throw new Error('сцена не загрузилась за 60 с');
  await step(); await page.waitForTimeout(100);
}
await step(15);
await page.evaluate(() => { window.__r7.pick('scheme', 'pack'); window.__r7.pick('drop', 'drop'); });
for (let i = 0; i < 20; i++) { await step(3); await page.waitForTimeout(50); }   // сборка пакета доезжает
await page.evaluate(() => { window.__vt.virt(true); document.getElementById('r3Go').click(); });
let s = await st(); console.log('после «Пуска»:', s);
while (s.phase === 'count' && s.T < START - 1e-6) { await step(); s = await st(); }
console.log('начало съёмки:', s);
// Rapier догружается по «Пуску» по-настоящему; к разделению (11 с полёта) не успеваем, но пусть будет.
const stage = page.locator('#r3Stage');
const N = Math.round(DUR * FPS);
for (let k = 0; k < N; k++) {
  await stage.screenshot({ path: path.join(out, `f${String(k).padStart(5, '0')}.png`), animations: 'allow' });
  await step();
  if (k % 30 === 0) console.log('кадр', k, await st());
}
console.log('конец съёмки:', await st());
await browser.close(); srv.close();
