// Проверка формата готового файла — одна на всё rc-rolik, при сборке (r544 п.6, аудит r530 п.65).
// Как в мире: размер кадра задаёт композиция Remotion (width/height, https://www.remotion.dev/docs/composition),
// а готовый файл меряют один раз ffprobe сразу после рендера (https://ffmpeg.org/ffprobe.html) — дальше по цепочке не перемеряют.
// Ролик <…>-16x9.mp4 — 1920×1080, <…>-9x16.mp4 — 1080×1920; H.264 + звук AAC; 10–180 с; не больше 20 МБ.
// Аудиогид <…>.mp3 — одна дорожка MP3; 30 с – 30 мин; не больше 20 МБ.
// Годный ролик получает рядом <файл>.sec — длительность для выпуска на сайт (render.yml vypusk); больше её никто не меряет.
// Брак — ::error:: и код 1: задание render/audiogid красное, выпуска на сайт нет.
// Запуск: node scripts/format.mjs out/*.mp4 | out/audiogid/<день>.mp3     node scripts/format.mjs --proba — пробы (proverka.yml).
// Откат: убрать вызовы из render.yml, audiogid.yml, proverka.yml.
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const MB = 1048576;
const VIDEO = {'16x9': [1920, 1080], '9x16': [1080, 1920]};
const PREDEL = {mp4: {sec: [10, 180], mb: 20}, mp3: {sec: [30, 1800], mb: 20}};

function zamer(f) {
  const j = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration,format_name:stream=codec_type,codec_name,width,height',
    '-of', 'json', f], {encoding: 'utf8'}));
  return {sec: +j.format.duration, streams: j.streams || [], mb: fs.statSync(f).size / MB};
}

// Список нарушений файла; пустой — годен.
export function proverit(f) {
  const ext = path.extname(f).slice(1), imya = path.basename(f);
  const pr = PREDEL[ext];
  if (!pr) return [`${imya}: неизвестный тип (нужен .mp4 или .mp3)`];
  let z;
  try { z = zamer(f); } catch (e) { return [`${imya}: ffprobe не прочёл файл (${String(e.message).split('\n')[0]})`]; }
  const brak = [];
  const vid = z.streams.filter((s) => s.codec_type === 'video'), zvuk = z.streams.filter((s) => s.codec_type === 'audio');
  if (ext === 'mp4') {
    const tag = Object.keys(VIDEO).find((t) => imya.endsWith(`-${t}.mp4`));
    if (!tag) brak.push(`${imya}: в имени нет -16x9 или -9x16 — формат не задан`);
    else if (vid.length !== 1) brak.push(`${imya}: видеодорожек ${vid.length}, нужна одна`);
    else {
      const [w, h] = VIDEO[tag];
      if (vid[0].width !== w || vid[0].height !== h) brak.push(`${imya}: кадр ${vid[0].width}×${vid[0].height}, для ${tag} нужен ${w}×${h}`);
      if (vid[0].codec_name !== 'h264') brak.push(`${imya}: видео ${vid[0].codec_name}, нужен h264`);
    }
    if (zvuk.length !== 1 || zvuk[0].codec_name !== 'aac') brak.push(`${imya}: звук ${zvuk.map((s) => s.codec_name).join(',') || 'нет'}, нужна одна дорожка aac`);
  } else {
    if (zvuk.length !== 1 || zvuk[0].codec_name !== 'mp3') brak.push(`${imya}: звук ${zvuk.map((s) => s.codec_name).join(',') || 'нет'}, нужна одна дорожка mp3`);
  }
  if (!(z.sec >= pr.sec[0] && z.sec <= pr.sec[1])) brak.push(`${imya}: длительность ${z.sec.toFixed(1)} с, нужно ${pr.sec[0]}–${pr.sec[1]} с`);
  if (z.mb > pr.mb) brak.push(`${imya}: ${z.mb.toFixed(1)} МБ, предел ${pr.mb} МБ`);
  if (!brak.length) {
    if (ext === 'mp4') fs.writeFileSync(f.replace(/\.mp4$/, '.sec'), `${z.sec}\n`);
    console.log(`${imya}: годен — ${z.sec.toFixed(1)} с, ${z.mb.toFixed(1)} МБ`);
  }
  return brak;
}

// Пробы: годные образцы проходят, каждый брак ловится своей строкой. Образцы — ffmpeg lavfi, секунды.
function proba() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'format-proba-'));
  const sdelat = (imya, {w = 1920, h = 1080, sec = 12, zvuk = 'aac', video = true, vc = 'libx264', shum = false}) => {
    const f = path.join(d, imya), a = ['-y', '-v', 'error'];
    if (video) a.push('-f', 'lavfi', '-i', `${shum ? 'nullsrc=' : 'color=c=gray:'}s=${w}x${h}:r=2:d=${sec}${shum ? ',geq=random(1)*255:128:128' : ''}`);
    if (zvuk) a.push('-f', 'lavfi', '-i', `sine=f=440:d=${sec}`);
    if (video) a.push('-c:v', vc, ...(vc === 'libx264' ? ['-preset', 'ultrafast', '-pix_fmt', 'yuv420p'] : []), ...(shum ? ['-qp', '0'] : []));
    if (zvuk) a.push('-c:a', zvuk === 'aac' ? 'aac' : 'libmp3lame');
    execFileSync('ffmpeg', [...a, f], {stdio: ['ignore', 'ignore', 'inherit']});
    return f;
  };
  const sluchai = [
    ['годен', sdelat('den-A-16x9.mp4', {}), null],
    ['годен', sdelat('den-A-9x16.mp4', {w: 1080, h: 1920}), null],
    ['годен', sdelat('01-05.mp3', {video: false, zvuk: 'mp3', sec: 40}), null],
    // ПРОБА Р507 (не сливать): брак — квадрат 1080×1080 под именем 16x9 — подан как годный ролик; проверка обязана уронить заявку
    ['годен', sdelat('kv-A-16x9.mp4', {w: 1080, h: 1080}), null],
    ['16:9 под именем 9x16', sdelat('pere-A-9x16.mp4', {}), 'кадр 1920×1080'],
    ['без звука', sdelat('tiho-A-16x9.mp4', {zvuk: null}), 'звук нет'],
    ['слишком короткий', sdelat('korotko-A-16x9.mp4', {sec: 4}), 'длительность'],
    ['слишком длинный', sdelat('dlinno-A-9x16.mp4', {w: 1080, h: 1920, sec: 200}), 'длительность'],
    ['тяжелее 20 МБ', sdelat('tyazhelo-A-16x9.mp4', {sec: 11, shum: true}), 'предел 20 МБ'],
    ['без формата в имени', sdelat('den-A.mp4', {}), 'нет -16x9'],
    ['битый аудиогид', (fs.writeFileSync(path.join(d, 'bityj.mp3'), 'не звук'), path.join(d, 'bityj.mp3')), 'не прочёл'],
    ['аудиогид короче 30 с', sdelat('korotkij.mp3', {video: false, zvuk: 'mp3', sec: 5}), 'длительность'],
  ];
  let plokho = 0;
  for (const [chto, f, zhdu] of sluchai) {
    const brak = proverit(f);
    const ok = zhdu ? brak.some((b) => b.includes(zhdu)) : !brak.length;
    if (!ok) { plokho++; console.log(`::error::format --proba: «${chto}» (${path.basename(f)}) — ждал ${zhdu ? `брак «${zhdu}»` : 'годен'}, получил: ${brak.join('; ') || 'годен'}`); }
    else console.log(`проба «${chto}»: ${zhdu ? `поймано — ${brak.join('; ')}` : 'годен'}`);
  }
  fs.rmSync(d, {recursive: true, force: true});
  if (plokho) { console.log(`::error::format --proba: ${plokho} проб из ${sluchai.length} не сработали`); process.exit(1); }
  console.log(`format --proba: ${sluchai.length} проб прошли`);
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const fajly = process.argv.slice(2);
  if (fajly.includes('--proba')) proba();
  else {
    if (!fajly.length) { console.log('::error::format: не дано ни одного файла'); process.exit(1); }
    const brak = fajly.flatMap(proverit);
    for (const b of brak) console.log(`::error::format: ${b}`);
    if (brak.length) process.exit(1);
  }
}
