// Проверка сценариев перед сборкой: node scripts/check.mjs [день ...]  (без дней — все days/*.json)
// fx plate (r254): рамка рисуется только с содержимым — labels.image (кадр дня из images) или labels.steklo
// (рамка сама изображает стеклянную пластинку, 26jan). Без них рамки нет, только надпись — предупреждение.
// Падает: labels.image нет в images дня или нет его файла в kadry/ (рамка вышла бы пустой); нет ни надписи, ни картинки.
// r256: без рамки в 16:9 фото сцены (seg.image) идёт на весь кадр с начала сцены — нет фото или файла → падает
// (иначе до слова key кадр пустой). Надписи с диапазоном «11–21 день» → падает: после диапазона — родительный, «11–21 дня».
// r265 (03, 04, 06 янв.): геометрия шаблона — src/layout.json, общая с Video.tsx. Падает: лента лет в 9:16 заходит
// на двухстрочный субтитр; год на карточке длиннее y_max знаков (шаблон пишет его одной строкой, длинный — нечитаем);
// кадр на весь экран 16:9 показывает меньше половины высоты снимка (портрет без crop — наезд срезает голову и глаза) —
// пока предупреждение: так собраны уже показанные 19, 20, 22, 28 янв.; их кадры — смотреть глазами.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const LAYOUT = JSON.parse(fs.readFileSync(path.join(ROOT, 'src', 'layout.json'), 'utf8'));
const MIN_VIDNO = 0.5; // доля высоты снимка, видимая в кадре 16:9 на весь экран

// ширина и высота JPEG/PNG без сторонних пакетов
const imgSize = (file) => {
  const b = fs.readFileSync(file);
  if (b[0] === 0x89 && b[1] === 0x50) return {w: b.readUInt32BE(16), h: b.readUInt32BE(20)};
  for (let i = 2; i < b.length - 9;) {
    if (b[i] !== 0xff) { i++; continue; }
    const m = b[i + 1];
    if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) return {w: b.readUInt16BE(i + 7), h: b.readUInt16BE(i + 5)};
    i += 2 + b.readUInt16BE(i + 2);
  }
  return null;
};

// верх двухстрочного субтитра 9:16 и низ ленты лет — доли высоты кадра 1080×1920
export const checkLayout = () => {
  const S = LAYOUT.sub, H = 1920;
  const subTop = 1 - S.bottom_v - (S.lines * S.font_v * S.line + 2 * S.pad_v + S.border) / H;
  const [, y, , h] = LAYOUT.years_v;
  return y + h > subTop - 0.005
    ? [`шаблон: лента лет 9:16 кончается на ${((y + h) * 100).toFixed(1)} % высоты, а двухстрочный субтитр начинается с ${(subTop * 100).toFixed(1)} % — плашка наедет на субтитр (src/layout.json years_v)`]
    : [];
};

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
  // кадр на весь экран 16:9 (фото, plate без рамки, pipeline-map): видно меньше половины высоты снимка → срезана голова
  const vesKadr = (seg) => !['years', 'formulas', 'tower-mesh', 'altitude', 'endcard'].includes(seg.fx)
    && !(seg.fx === 'plate' && (seg.labels?.image || seg.labels?.steklo));
  for (const seg of cfg.segments) {
    const im = seg.image && (cfg.images || {})[seg.image];
    if (!im || !vesKadr(seg) || !fs.existsSync(path.join(ROOT, im.src))) continue;
    const sz = imgSize(path.join(ROOT, im.src));
    if (!sz) continue;
    const [x0, y0, x1, y1] = im.crop || [0, 0, 1, 1];
    const vidno = Math.min(1, (sz.w * (x1 - x0)) / (sz.h * (y1 - y0)) / (16 / 9));
    if (vidno < MIN_VIDNO) warnings.push(`${day}, сцена ${seg.id}: кадр «${seg.image}» на весь экран 16:9 показывает ${Math.round(vidno * 100)} % высоты снимка — срежет голову/верх; дай crop по лицу (шире, чем выше)`);
  }
  for (const seg of cfg.segments) {
    if (seg.fx !== 'years') continue;
    for (const it of seg.labels?.items || []) {
      if (String(it.y).length > LAYOUT.y_max) errors.push(`${day}, сцена ${seg.id}: год на карточке «${it.y}» длиннее ${LAYOUT.y_max} знаков — одной строкой станет мелким; сократи («40–50 к.»)`);
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
  let errors = checkLayout();
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
