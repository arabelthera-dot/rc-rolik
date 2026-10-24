// Рендер дня: node scripts/render.mjs <day> [A|B|AB]  -> out/<day>-<V>-16x9.mp4, out/<day>-<V>-9x16.mp4
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {checkDays} from './check.mjs';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const day = process.argv[2];
const variants = (process.argv[3] || 'A').split('');
const only = process.argv[4]; // необязательно: 16x9 или 9x16
// сценарий дня до сборки: fx plate без содержимого и т. п. (scripts/check.mjs, r254) — ошибка валит сборку
if (!checkDays([day])) { console.error(`days/${day}.json не прошёл проверку — сборки нет`); process.exit(1); }

// Бережная сборка (Михаил, 24.10.2026: сервер завис — remotion, Chrome и ffmpeg заняли все ядра и 6 ГБ).
// Потоков не больше 2, ffmpeg на 2 ядрах, один ролик на весь сервер за раз (замок). Нужно больше — карточка Михаилу.
// На машинах GitHub (CI=true) сервер не общий — берём все ядра; у нас — не больше 2.
const CONC = process.env.CI ? os.cpus().length : Math.min(2, Number(process.env.CONC || 2));
const THREADS = String(process.env.CI ? os.cpus().length : 2);
const LOCK = '/tmp/remotion-render.lock';
try { fs.writeFileSync(LOCK, String(process.pid), {flag: 'wx'}); }
catch {
  const pid = Number(fs.readFileSync(LOCK, 'utf8'));
  let alive = false; try { process.kill(pid, 0); alive = true; } catch {}
  if (alive) { console.error(`Сборка уже идёт (pid ${pid}) — один ролик за раз. Повтори после неё.`); process.exit(3); }
  fs.writeFileSync(LOCK, String(process.pid));
}
process.on('exit', () => { try { if (fs.readFileSync(LOCK, 'utf8') === String(process.pid)) fs.unlinkSync(LOCK); } catch {} });
const MAX_MB = 19.5;
const localChrome = path.join(os.homedir(), '.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell');
// Нет нашего Chrome (машина GitHub) — Remotion скачает свой.
const browserExecutable = process.env.CHROME || (fs.existsSync(localChrome) ? localChrome : null);

const serveUrl = await bundle({entryPoint: path.join(ROOT, 'src/index.ts'), publicDir: path.join(ROOT, 'public')});
fs.mkdirSync(path.join(ROOT, 'out'), {recursive: true});
for (const variant of variants) {
  for (const [id, tag] of [['Day16x9', '16x9'], ['Day9x16', '9x16']]) {
    if (only && only !== tag) continue;
    const inputProps = {day, variant};
    const composition = await selectComposition({serveUrl, id, inputProps, browserExecutable});
    const out = path.join(ROOT, 'out', `${day}-${variant}-${tag}.mp4`);
    const raw = out.replace('.mp4', '.raw.mp4');
    const t = Date.now();
    await renderMedia({
      composition, serveUrl, codec: 'h264', outputLocation: raw, inputProps, browserExecutable,
      crf: 18, audioBitrate: '160k', concurrency: CONC,
      chromiumOptions: {gl: 'swangle'},
      onProgress: ({progress}) => process.stdout.write(`\r${path.basename(out)} ${(progress * 100).toFixed(0)}%   `),
    });
    // итоговое сжатие: H.264 с потолком битрейта, чтобы файл гарантированно ≤ 20 МБ
    const dur = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', raw]).toString());
    const vk = Math.floor((MAX_MB * 8 * 1024 * 0.95) / dur - 160);
    execFileSync('ffmpeg', ['-y', '-v', 'error', '-threads', THREADS, '-i', raw, '-c:v', 'libx264', '-threads', THREADS, '-preset', 'slow', '-crf', '20', '-maxrate', `${vk}k`,
      '-bufsize', `${vk * 2}k`, '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '160k', out]);
    fs.unlinkSync(raw);
    const mb = fs.statSync(out).size / 1048576;
    console.log(`\n${path.basename(out)}: ${dur.toFixed(1)} с, ${mb.toFixed(1)} МБ, ${((Date.now() - t) / 1000).toFixed(0)} с рендера`);
  }
}
