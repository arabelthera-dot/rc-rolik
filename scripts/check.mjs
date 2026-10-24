// Проверка сценариев перед сборкой: node scripts/check.mjs [день ...]  (без дней — все days/*.json)
// fx plate (r254): рамка рисуется только с содержимым — labels.image (кадр дня из images) или labels.steklo
// (рамка сама изображает стеклянную пластинку, 26jan). Без них рамки нет, только надпись — предупреждение.
// Падает: labels.image нет в images дня или нет его файла в kadry/ (рамка вышла бы пустой); нет ни надписи, ни картинки.
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
    }
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
