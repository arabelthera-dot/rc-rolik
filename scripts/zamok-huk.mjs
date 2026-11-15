// Замок сценария (r544 п.5, Р534/Р536; Р765 — все музеи): хук ролика = хук утверждённой карточки дня дословно.
// Для каждого days/*.json (музей и дата — как в scripts/huk-iz-kartochki.mjs): первая сцена — id hook; её текст (show, а нет — say без знаков ударения) совпадает
// с полем hook карточки rc-site src/content/days/<музей>/ММ-ДД.json (ветка main). Кадры сцен дней nsДДмес — только kadry/<день>/ этого дня.
// Расхождение, нет карточки или кадра → код 1, проверка заявки красная.
// Запуск: node scripts/zamok-huk.mjs [день ...] (без дней — все days/*.json). RC_SITE=<путь> — карточки из своей копии сайта.
// Откат: удалить файл и шаг «замок хука» в .github/workflows/proverka.yml.
import fs from 'node:fs';
import path from 'node:path';
import { denSajta } from './huk-iz-kartochki.mjs';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MES = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
const RAW = 'https://raw.githubusercontent.com/arabelthera-dot/rc-site';
const REF = process.env.RC_SITE_REF || 'main'; // r763: RC_SITE_REF — ветка заявки дня rc-site

// точка в конце, ё/е, знак ударения и пробелы не считаются расхождением; слова, порядок и кавычки — считаются
export const norm = (s) => String(s ?? '').normalize('NFD').replace(/́/g, '').normalize('NFC')
  .replace(/<[^>]+>/g, '').replace(/ё/gi, 'е').replace(/\s+/g, ' ').replace(/[\s.!…]+$/, '').trim();

export const kluchDnya = (id) => {
  const m = id.match(/^ns-?(\d{1,2})([a-z]{3})$/);
  if (!m || !MES.includes(m[2])) return null;
  return `${String(MES.indexOf(m[2]) + 1).padStart(2, '0')}-${m[1].padStart(2, '0')}`;
};

export async function kartochka(key, muzei = 'ne-sdayutsya', ref = REF) {
  if (process.env.RC_SITE) {
    const f = path.join(process.env.RC_SITE, 'src/content/days', muzei, `${key}.json`);
    return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null;
  }
  const r = await fetch(`${RAW}/${ref}/src/content/days/${muzei}/${key}.json`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`rc-site ${ref} ${key}.json: HTTP ${r.status}`);
  return r.json();
}

// ветки открытых заявок rc-site (не черновики, не из чужих копий) — как zayavki() в scripts/avto.py (r763)
let zayavki;
async function vetkiZayavok() {
  if (zayavki) return zayavki;
  const h = process.env.GITHUB_TOKEN ? { authorization: `Bearer ${process.env.GITHUB_TOKEN}` } : {};
  const r = await fetch('https://api.github.com/repos/arabelthera-dot/rc-site/pulls?state=open&per_page=100', { headers: h });
  if (!r.ok) throw new Error(`rc-site: список открытых заявок HTTP ${r.status}`);
  zayavki = (await r.json()).filter((z) => !z.draft && z.head?.repo?.full_name === 'arabelthera-dot/rc-site').map((z) => z.head.ref);
  return zayavki;
}

// хуки карточки дня: сначала из REF (main), затем из открытых заявок rc-site — ролик собирается из заявки страницы
// до её слияния (r763), такой сценарий уже стоит в main rc-rolik раньше карточки в main rc-site (04feb, r764)
export async function hukiKartochki(key, muzei, tekst) {
  const chist = (k) => String(k?.hook ?? '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  const out = [];
  const glavnaya = chist(await kartochka(key, muzei));
  if (glavnaya) out.push({ ref: REF, huk: glavnaya });
  if (process.env.RC_SITE || process.env.RC_SITE_REF || (glavnaya && norm(tekst) === norm(glavnaya))) return out;
  for (const ref of await vetkiZayavok()) {
    const huk = chist(await kartochka(key, muzei, ref));
    if (huk && !out.some((x) => x.huk === huk)) out.push({ ref, huk });
  }
  return out;
}

export async function zamokDnya(id) {
  const oshibki = [];
  const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'days', `${id}.json`), 'utf8'));
  const den = denSajta(id, cfg);
  if (!den) return [`${id}: не понять музей и дату дня сайта (нет sajt.muzei, source_md и имени ДДмес)`];
  const { muzei, key } = den;
  const hook = cfg.segments?.[0];
  const huki = await hukiKartochki(key, muzei, hook?.show ?? hook?.say);
  if (!huki.length) return [`${id}: нет утверждённой карточки с хуком rc-site src/content/days/${muzei}/${key}.json`];
  if (hook?.id !== 'hook') oshibki.push(`${id}: первая сцена не hook`);
  else {
    const tekst = hook.show ?? hook.say;
    if (!huki.some((x) => norm(tekst) === norm(x.huk))) oshibki.push(`${id}: хук ролика «${tekst}» ≠ хук карточки ${key} «${huki[0].huk}» (${huki.map((x) => x.ref).join(', ')})`);
  }
  if (kluchDnya(id)) for (const [imya, im] of Object.entries(cfg.images || {})) {
    if (!String(im.src).startsWith(`kadry/${id}/`)) oshibki.push(`${id}: кадр «${imya}» ${im.src} не из kadry/${id}/ — кадры только этого дня`);
    else if (!fs.existsSync(path.join(ROOT, im.src))) oshibki.push(`${id}: нет файла кадра ${im.src}`);
  }
  return oshibki;
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  const dni = process.argv.length > 2 ? process.argv.slice(2)
    : fs.readdirSync(path.join(ROOT, 'days')).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', '')).sort();
  let vse = [];
  for (const d of dni) vse = vse.concat(await zamokDnya(d));
  vse.forEach((e) => console.error(`::error file=days/${e.split(':')[0]}.json::${e}`));
  if (vse.length) process.exit(1);
  console.log(`замок хука: ${dni.length} дн. — хук = карточка, у nsДДмес кадры свои`);
}
