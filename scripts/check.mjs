// Проверка сценариев перед сборкой: node scripts/check.mjs [день ...]  (без дней — все days/*.json)
// fx plate (r254): рамка рисуется только с содержимым — labels.image (кадр дня из images) или labels.steklo
// (рамка сама изображает стеклянную пластинку, 26jan). Без них рамки нет, только надпись — предупреждение.
// Падает: labels.image нет в images дня или нет его файла в kadry/ (рамка вышла бы пустой); нет ни надписи, ни картинки.
// r256: без рамки в 16:9 фото сцены (seg.image) идёт на весь кадр с начала сцены — нет фото или файла → падает
// (иначе до слова key кадр пустой). Надписи с диапазоном «11–21 день» → падает: после диапазона — родительный, «11–21 дня».
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');

export const checkDay = (day) => {
  const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'days', `${day}.json`), 'utf8'));
  const errors = [], warnings = [];
  for (const seg of cfg.segments) {
    if (seg.fx !== 'plate') continue;
    const l = seg.labels || {};
    const where = `${day}, сцена ${seg.id}, fx plate`;
    if (l.image) {
      const im = (cfg.images || {})[l.image];
      if (!im) errors.push(`${where}: labels.image «${l.image}» нет в images дня — рамка вышла бы пустой`);
      else if (!fs.existsSync(path.join(ROOT, im.src))) errors.push(`${where}: нет файла ${im.src} для labels.image «${l.image}»`);
    } else if (!l.steklo) {
      if (!l.text) errors.push(`${where}: нет ни labels.text, ни labels.image — сцене нечего показать`);
      else warnings.push(`${where}: нет содержимого рамки (labels.image) — рамка не рисуется, только надпись «${l.text}»`);
      const im = (cfg.images || {})[seg.image];
      if (!im) errors.push(`${where}: без рамки фото сцены идёт на весь кадр, а image «${seg.image}» нет в images дня — кадр вышел бы пустым`);
      else if (!fs.existsSync(path.join(ROOT, im.src))) errors.push(`${where}: нет файла ${im.src} для image «${seg.image}»`);
    }
  }
  const nadpisi = [];
  const walk = (o, p) => {
    if (typeof o === 'string') nadpisi.push([p, o]);
    else if (o && typeof o === 'object') for (const k of Object.keys(o)) if (k !== 'say') walk(o[k], p ? `${p}.${k}` : k);
  };
  cfg.segments.forEach((seg) => walk({show: seg.show, labels: seg.labels}, `сцена ${seg.id}`));
  for (const [p, t] of nadpisi) {
    const m = t.match(/\d+\s*[–—-]\s*\d+\s+(день|год|час|раз|метр|килограмм|грамм|километр)(?![а-яё])/i);
    if (m) errors.push(`${day}, ${p}: «${m[0]}» — после диапазона нужен родительный падеж («…${m[1] === 'день' ? 'дня' : m[1] + 'а'}»)`);
  }
  return {errors, warnings};
};

export const checkDays = (days) => {
  let errors = [];
  for (const day of days) {
    const r = checkDay(day);
    r.warnings.forEach((w) => console.warn(`предупреждение: ${w}`));
    errors = errors.concat(r.errors);
  }
  errors.forEach((e) => console.error(`ОШИБКА: ${e}`));
  return errors.length === 0;
};

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  const days = process.argv.length > 2 ? process.argv.slice(2)
    : fs.readdirSync(path.join(ROOT, 'days')).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', '')).sort();
  if (!checkDays(days)) process.exit(1);
  console.log(`проверка сценариев: ${days.length} дн., ошибок нет`);
}
