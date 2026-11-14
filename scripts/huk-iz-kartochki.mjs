// Хук ролика — только из карточки дня rc-site (Р765, 14.11.2026): первая сцена days/<день>.json получает say и show
// дословно из поля hook карточки src/content/days/<музей>/ММ-ДД.json (ветка main), ручной хук в сценарии не живёт.
// Музей и дата дня — из sajt.muzei, иначе из пути в source_md, иначе по имени файла (nsДДмес — «Русские не сдаются»,
// ДДмес — «Изобретения»). Первая сцена не hook (было 30jan: «knyaz») — хук встаёт перед ней на её же кадре.
// render.yml (задание scenarij) зовёт для всех дней, кроме nsДДмес — те целиком собирает scripts/scenarij.mjs.
// Нет карточки или хука → код 1 с именем дня и пути карточки: старый хук не озвучивается.
// Запуск: node scripts/huk-iz-kartochki.mjs [день ...] (без дней — все days/*.json). RC_SITE=<путь> — карточки из своей копии.
// Откат: удалить файл и ветку «не НС» в задании scenarij render.yml.
import fs from 'node:fs';
import path from 'node:path';
import { kartochka, norm } from './zamok-huk.mjs';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MES = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

// музей и ключ ММ-ДД карточки сайта для сценария дня
export function denSajta(id, cfg) {
  const iz = String(cfg.source_md ?? '').match(/(?:days|full-pages|dni-shablon)\/([a-z-]+)\/(\d\d-\d\d)/);
  const m = id.match(/^(ns)?-?(\d{1,2})([a-z]{3})$/);
  const key = iz?.[2] ?? (m && MES.includes(m[3]) ? `${String(MES.indexOf(m[3]) + 1).padStart(2, '0')}-${m[2].padStart(2, '0')}` : null);
  const muzei = cfg.sajt?.muzei ?? iz?.[1] ?? (m ? (m[1] ? 'ne-sdayutsya' : 'izobreteniya') : null);
  return key && muzei ? { muzei, key } : null;
}

// JSON с ключами по алфавиту: порядок ключей сравнению не мешает
const kanon = (o) => JSON.stringify(o, (k, v) => (v && typeof v === 'object' && !Array.isArray(v)
  ? Object.fromEntries(Object.keys(v).sort().map((x) => [x, v[x]])) : v));

// доля слов хука, которые есть в тексте сцены
const slova = (t) => norm(t).toLowerCase().split(/[^а-яa-z0-9]+/).filter((w) => w.length > 2);
const pohozhe = (t, huk) => { const a = new Set(slova(t)); const b = slova(huk); return b.length ? b.filter((w) => a.has(w)).length / b.length : 0; };

// границы объекта {...} вокруг позиции p в тексте JSON (скобки внутри строк не считаются)
function obekt(t, p) {
  let ot = p, gl = 0;
  for (; ot >= 0; ot--) { if (t[ot] === '}') gl++; if (t[ot] === '{') { if (!gl) break; gl--; } }
  let d = ot, v = 0, str = false;
  for (; d < t.length; d++) {
    const c = t[d];
    if (str) { if (c === '\\') d++; else if (c === '"') str = false; continue; }
    if (c === '"') str = true; else if (c === '{') v++; else if (c === '}' && !--v) return [ot, d + 1];
  }
  throw new Error('нет конца объекта сцены');
}

// одна замена строки после позиции ot; не нашлась — ошибка, а не тихая пересборка файла
function zamenit(tekst, ot, staroe, novoe, id) {
  const i = tekst.indexOf(staroe, ot);
  if (i < 0) throw new Error(`${id}: в тексте сценария не найдено ${staroe.slice(0, 60)}…`);
  return tekst.slice(0, i) + novoe + tekst.slice(i + staroe.length);
}

export async function hukIzKartochki(id) {
  const f = path.join(ROOT, 'days', `${id}.json`);
  let syroj = fs.readFileSync(f, 'utf8');
  const cfg = JSON.parse(syroj);
  const den = denSajta(id, cfg);
  if (!den) return { id, otkaz: 'не понять музей и дату дня (нет sajt.muzei, source_md и имени ДДмес)' };
  const k = await kartochka(den.key, den.muzei);
  const huk = String(k?.hook ?? '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  if (!huk) return { id, ...den, otkaz: `нет поля hook в карточке rc-site src/content/days/${den.muzei}/${den.key}.json` };
  const s0 = cfg.segments[0];
  const bylo = s0.show ?? s0.say;
  if (s0.id === 'hook' && norm(bylo) === norm(huk)) return { id, ...den, huk, izmenen: false };
  // правка в тексте файла, а не пересборкой JSON: остальной сценарий остаётся байт в байт
  const nachalo = syroj.indexOf('"segments"');
  let tekst;
  if (s0.id === 'hook') {
    tekst = zamenit(syroj, nachalo, `"say": ${JSON.stringify(s0.say)}`, `"say": ${JSON.stringify(huk)}`, id);
    if (s0.show != null) tekst = zamenit(tekst, nachalo, `"show": ${JSON.stringify(s0.show)}`, `"show": ${JSON.stringify(huk)}`, id);
    else {
      const i = tekst.indexOf(`"say": ${JSON.stringify(huk)}`, nachalo);
      const otstup = tekst.slice(tekst.lastIndexOf('\n', i) + 1, i);
      const konec = i + `"say": ${JSON.stringify(huk)}`.length;
      tekst = tekst.slice(0, konec) + `,\n${otstup}"show": ${JSON.stringify(huk)}` + tekst.slice(konec);
    }
    s0.say = huk; s0.show = huk;
  } else {
    // первая сцена не hook: сцена, которая уже говорит хук карточки, встаёт первой (иначе повтор), нет такой — новая сцена
    const j = cfg.segments.findIndex((x) => pohozhe(x.show ?? x.say, huk) >= 0.5);
    const i = syroj.indexOf('{', syroj.indexOf('[', nachalo));
    const otstup = syroj.slice(syroj.lastIndexOf('\n', i) + 1, i);
    let blok;
    if (j > 0) {
      const sc = cfg.segments[j];
      const [ot, d] = obekt(syroj, syroj.indexOf(`"id": ${JSON.stringify(sc.id)}`, nachalo));
      const zap = syroj.slice(d).match(/^\s*,/)?.[0].length ?? 0;
      const kusok = syroj.slice(syroj.lastIndexOf('\n', ot), d + zap);
      syroj = syroj.slice(0, syroj.lastIndexOf('\n', ot)) + syroj.slice(d + zap);
      blok = zamenit(kusok.trim().replace(/,$/, ''), 0, `"id": ${JSON.stringify(sc.id)}`, '"id": "hook"', id);
      blok = zamenit(blok, 0, `"say": ${JSON.stringify(sc.say)}`, `"say": ${JSON.stringify(huk)}`, id);
      blok = zamenit(blok, 0, `"show": ${JSON.stringify(sc.show)}`, `"show": ${JSON.stringify(huk)}`, id);
      cfg.segments.splice(j, 1);
      cfg.segments.unshift({ ...sc, id: 'hook', say: huk, show: huk });
    } else {
      const novaya = { id: 'hook', say: huk, show: huk, image: s0.image, fx: 'photo' };
      const shag = syroj.match(/^\{\r?\n([ \t]+)"/)?.[1] ?? '  ';
      blok = JSON.stringify(novaya, null, shag).replace(/\n/g, `\n${otstup}`);
      cfg.segments.unshift(novaya);
    }
    tekst = syroj.slice(0, i) + blok + `,\n${otstup}` + syroj.slice(i);
  }
  if (kanon(JSON.parse(tekst)) !== kanon(cfg)) throw new Error(`${id}: правка хука в тексте сценария дала не тот JSON — файл не записан`);
  fs.writeFileSync(f, tekst);
  return { id, ...den, huk, bylo, izmenen: true };
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  const dni = process.argv.length > 2 ? process.argv.slice(2)
    : fs.readdirSync(path.join(ROOT, 'days')).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', '')).sort();
  let plohie = 0, izm = 0;
  for (const d of dni) {
    const r = await hukIzKartochki(d);
    if (r.otkaz) { plohie++; console.error(`::error file=days/${d}.json::${d}: ${r.otkaz}`); continue; }
    if (r.izmenen) { izm++; console.log(`✎ ${d} (${r.muzei} ${r.key}): «${r.bylo}» → «${r.huk}»`); }
    else console.log(`✓ ${d} (${r.muzei} ${r.key}): хук = карточка`);
  }
  console.log(`хук из карточки: ${dni.length} дн., исправлено ${izm}, отказ ${plohie}`);
  if (plohie) process.exit(1);
}
