// Сценарий ролика «Русские не сдаются» — машиной из записи дня сайта (r544 п.5, Р534/Р536; аудит r530 п.57).
// Как в мире: данные ролика — входные props из записи дня, не вторая копия руками (https://www.remotion.dev/docs/passing-props).
// Источник — только rc-site (ветка main или своя копия RC_SITE=<путь>):
//   src/content/days/ne-sdayutsya/ММ-ДД.json — хук карточки, дословно первой сценой (замок scripts/zamok-huk.mjs);
//   src/content/dni-shablon/ne-sdayutsya/ММ-ДД.yaml — факты страницы (fakty[].udary: n + kadr) и обложка;
//   src/data/utverzhdeno/ne-sdayutsya/ММ-ДД.json — копия утверждённого: текст фактов (zagolovok) и порядок (poryadok), как у сайта —
//   правило сопоставления факта yaml (n) с копией берётся модулем сайта src/lib/fakty-iz-utverzhdeno.mjs, своего нет (Р686 п.1);
//   нет копии — прежний путь, summary из yaml; RC_FAKTY_IZ_UTVERZHDENO=0 — текст yaml главнее, как на сайте;
//   их кадры public/muzei/ne-sdayutsya/img/… копируются в kadry/<день>/ — других кадров в ролике нет.
// Сцены: hook (обложка) → факты по порядку страницы (каждый на кадре страницы), пока ролик укладывается в 40–60 с, последний кончается
// «Русские не сдаются.» → cta. Ударения ставит scripts/tts.py по udareniya.json и словарю имён сайта; числа в say читает голос.
// Факт без своего кадра идёт на следующем кадре страницы; не набралось 40 с, нет хука или обложки — день не пишется, код 2.
// Запуск: node scripts/scenarij.mjs 01-06..01-15 [--proba] — --proba только печатает мерило, ничего не пишет.
// Изобретения (r713 п.57) — только с флагом --muzej=izobreteniya: те же поля сайта музея izobreteniya, день ДДмес (02feb),
// без «Русские не сдаются.», в ролик — все кадры страницы (обложка, кадры фактов, figures). Готовые days/ДДмес.json
// не перезаписываются: --v=<папка> пишет в <папка>/days/ и <папка>/kadry/, в days/ репо — только с --zamenit.
// Откат: удалить файл; days/*.json, собранные им, остаются обычными сценариями.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import yaml from 'js-yaml';
import { kartochka, zamokDnya, norm } from './zamok-huk.mjs';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MES = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
const RAW = 'https://raw.githubusercontent.com/arabelthera-dot/rc-site/main';
const ZNAKOV_V_SEK = 13.2; // ns04jan: 625 знаков озвучки — 47,5 с в облаке (rate +18%)
const MIN_SEK = 40, MAX_SEK = 60, CEL_SEK = 52;
const CTA = { id: 'cta', say: 'Смотри день целиком на сайте рашн-цивилизейшн точка ру.', show: 'Смотри день целиком на russian-civilization.ru', image: null, fx: 'endcard', labels: { deco: 'none' } };
const argi = process.argv.slice(2);
const PROBA = argi.includes('--proba');
const flag = (imya) => argi.find((x) => x.startsWith(`--${imya}=`))?.slice(imya.length + 3);
const MUZEJ = flag('muzej') ?? 'ne-sdayutsya';
const MUZEI = {
  'ne-sdayutsya': { pref: 'ns', reestr: 'nesdayutsya', final: 'Русские не сдаются.' },
  izobreteniya: { pref: '', reestr: 'izobreteniya', final: '' },
};
if (!MUZEI[MUZEJ]) { console.error(`ОСТАНОВ: --muzej=${MUZEJ} — умею ${Object.keys(MUZEI).join(', ')}`); process.exit(1); }
const { pref: PREF, reestr: REESTR, final: FINAL } = MUZEI[MUZEJ];
const KUDA = flag('v') ? path.resolve(flag('v')) : ROOT;
const ZAMENIT = argi.includes('--zamenit');
const dni = [];
for (const a of argi.filter((x) => !x.startsWith('--'))) {
  const m = a.match(/^(\d\d)-(\d\d)(?:\.\.(\d\d)-(\d\d))?$/);
  if (!m) { console.error(`ОСТАНОВ: день — ММ-ДД или ММ-ДД..ММ-ДД, а не ${a}`); process.exit(1); }
  for (let d = +m[2]; d <= +(m[4] ?? m[2]); d++) dni.push(`${m[1]}-${String(d).padStart(2, '0')}`);
}
if (!dni.length) { console.error('запуск: node scripts/scenarij.mjs 01-06..01-15 [--proba]'); process.exit(1); }

async function sajt(rel, kak = 'text') {
  if (process.env.RC_SITE) {
    const f = path.join(process.env.RC_SITE, rel);
    if (!fs.existsSync(f)) return null;
    return kak === 'text' ? fs.readFileSync(f, 'utf8') : fs.readFileSync(f);
  }
  const r = await fetch(`${RAW}/${rel}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`rc-site ${rel}: HTTP ${r.status}`);
  return kak === 'text' ? r.text() : Buffer.from(await r.arrayBuffer());
}

// Факты yaml с текстом и порядком утверждённого — функцией сайта faktyIzUtverzhdeno (src/lib/fakty-iz-utverzhdeno.mjs).
// С RC_SITE модуль и копия читаются из неё; без — скачиваются из main во временный корень, модулю нужен только node:fs.
async function izUtverzhdeno(st, key) {
  const MOD = 'src/lib/fakty-iz-utverzhdeno.mjs', UTV = `src/data/utverzhdeno/${MUZEJ}/${key}.json`;
  let koren = process.env.RC_SITE;
  if (!koren) {
    const [mod, utv] = await Promise.all([sajt(MOD), sajt(UTV)]);
    if (!mod) throw new Error(`rc-site ${MOD}: нет модуля`);
    koren = fs.mkdtempSync(path.join(os.tmpdir(), 'scenarij-'));
    for (const [rel, t] of [[MOD, mod], [UTV, utv]].filter(([, t]) => t != null)) {
      fs.mkdirSync(path.dirname(path.join(koren, rel)), { recursive: true });
      fs.writeFileSync(path.join(koren, rel), t);
    }
  }
  const { faktyIzUtverzhdeno } = await import(pathToFileURL(path.join(koren, MOD)).href);
  const iz = fs.existsSync(path.join(koren, UTV));
  const r = faktyIzUtverzhdeno(st, MUZEJ, key, koren);
  if (!process.env.RC_SITE) fs.rmSync(koren, { recursive: true, force: true });
  return { ...r, iz };
}

const chistyj = (s) => String(s ?? '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().replace(/([^.!?…»])$/, '$1.');
const sek = (segs) => segs.reduce((n, s) => n + s.say.length, 0) / ZNAKOV_V_SEK;

// ширина и высота JPEG/PNG — для crop портретов (check.mjs: в 16:9 видно не меньше половины высоты)
const razmer = (b) => {
  if (b[0] === 0x89 && b[1] === 0x50) return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
  for (let i = 2; i < b.length - 9;) {
    if (b[i] !== 0xff) { i++; continue; }
    const m = b[i + 1];
    if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) return { w: b.readUInt16BE(i + 7), h: b.readUInt16BE(i + 5) };
    i += 2 + b.readUInt16BE(i + 2);
  }
  return null;
};

async function denOdin(key) {
  const [mm, dd] = key.split('-');
  const id = `${PREF}${dd}${MES[+mm - 1]}`;
  const k = await kartochka(key, MUZEJ);
  if (!k?.hook) return { id, key, otkaz: `нет поля hook в карточке src/content/days/${MUZEJ}/${key}.json` };
  const yt = await sajt(`src/content/dni-shablon/${MUZEJ}/${key}.yaml`);
  if (!yt) return { id, key, otkaz: `нет страницы src/content/dni-shablon/${MUZEJ}/${key}.yaml` };
  const utv = await izUtverzhdeno(yaml.load(yt), key);
  if (utv.oshibki.length) return { id, key, otkaz: utv.oshibki.join('; ') };
  const st = utv.syroe;
  if (!st.oblozhka?.src) return { id, key, otkaz: 'нет обложки страницы (oblozhka.src) для сцены хука' };

  const kadry = new Map(); // src сайта → имя кадра в сценарии
  const kadr = (src) => {
    if (!kadry.has(src)) kadry.set(src, `k${kadry.size + 1}`);
    return kadry.get(src);
  };
  const segs = [{ id: 'hook', say: k.hook.trim(), image: kadr(st.oblozhka.src), fx: 'photo', show: k.hook.trim() }];
  const fakty = (st.fakty || []).flatMap((b) => b.udary || []).filter((u) => u.summary);
  if (!fakty.length) return { id, key, otkaz: `нет текста фактов: у fakty[].udary пустой summary в yaml и нет копии src/data/utverzhdeno/${MUZEJ}/${key}.json` };
  const bezKadra = fakty.filter((u) => !u.kadr?.src).length;
  // пул кадров страницы: обложка, кадры фактов, figures; факт без своего кадра берёт следующий ещё не показанный
  const pul = [st.oblozhka.src, ...fakty.map((u) => u.kadr?.src), ...(st.figures || []).map((f) => f.src)]
    .filter((x, i, a) => x && a.indexOf(x) === i);
  let po = 0;
  const svobodnyj = () => {
    const net = pul.find((x) => !kadry.has(x));
    return net ?? pul[po++ % pul.length];
  };
  for (const u of fakty) {
    const say = chistyj(u.summary);
    if (segs.some((x) => x.say === say)) continue;
    const nov = { id: `f${segs.length}`, say, show: say, fx: 'photo' };
    if (sek([...segs, nov, CTA]) + FINAL.length / ZNAKOV_V_SEK > CEL_SEK) break;
    nov.image = kadr(u.kadr?.src && !segs.some((x) => x.image === kadry.get(u.kadr.src)) ? u.kadr.src : svobodnyj());
    segs.push(nov);
  }
  if (segs.length < 2) return { id, key, otkaz: 'ни одного факта с кадром на странице' };
  const posl = segs[segs.length - 1];
  if (FINAL) {
    posl.say = `${posl.say} ${FINAL}`;
    posl.show = `${posl.show} ${FINAL}`;
  }
  segs.push(CTA);
  const dlit = +sek(segs).toFixed(1);

  const staryj = fs.existsSync(path.join(ROOT, 'days', `${id}.json`)) ? JSON.parse(fs.readFileSync(path.join(ROOT, 'days', `${id}.json`), 'utf8')) : null;
  const slug = String(st.audioguide?.audioSrc ?? '').match(/audio-guide-(.+?)-ru/)?.[1];
  // имя файлов ролика — как у конвейера сайта (scripts/ns-konveyer.mjs): дата + имя аудиогида; video.klyuch страницы бывает старым (06aug)
  const imya = slug ? `${dd}${MES[+mm - 1]}-${slug}` : staryj?.sajt?.imya;
  const cfg = {
    id,
    source_md: `rc-site src/content/days/${MUZEJ}/${key}.json (hook); src/content/dni-shablon/${MUZEJ}/${key}.yaml (факты, кадры)${utv.iz ? `; src/data/utverzhdeno/${MUZEJ}/${key}.json (текст и порядок фактов)` : ''} — собрано scripts/scenarij.mjs`,
    voice: 'ru-RU-DmitryNeural',
    rate: '+18%',
    ...(imya ? { sajt: { muzei: MUZEJ, reestr: REESTR, imya } } : {}),
    segments: segs,
    images: {},
  };
  const fajly = [];
  for (const [src, im] of kadry) {
    const b = await sajt(`public${src}`, 'bin');
    if (!b) return { id, key, otkaz: `нет файла кадра public${src} на сайте` };
    const f = `kadry/${id}/${path.basename(src)}`;
    const r = razmer(b);
    const obraz = { src: f, parallax: false };
    // портрет: в 16:9 без crop видно меньше половины высоты — берём верх снимка, где лицо
    if (r && r.w / r.h / (16 / 9) < 0.5) obraz.crop = [0, 0.05, 1, +Math.min(1, 0.05 + r.w / r.h / (16 / 9) / 0.55).toFixed(3)];
    cfg.images[im] = obraz;
    fajly.push([f, b]);
  }
  const meril = {
    dlit, vOkne: dlit >= MIN_SEK && dlit <= MAX_SEK,
    hukDoslovno: norm(segs[0].show) === norm(k.hook),
    kadryNashi: Object.values(cfg.images).every((x) => x.src.startsWith(`kadry/${id}/`)),
    faktov: segs.length - 2, bezKadra,
  };
  return { id, key, cfg, fajly, meril };
}

let plohih = 0;
for (const key of dni) {
  const r = await denOdin(key);
  if (r.otkaz) { plohih++; console.log(`✗ ${key} ${r.id}: ${r.otkaz}`); continue; }
  const m = r.meril, ok = m.vOkne && m.hukDoslovno && m.kadryNashi;
  if (!ok) plohih++;
  console.log(`${ok ? '✓' : '✗'} ${key} ${r.id}: ~${m.dlit} с, фактов ${m.faktov} (без кадра на странице ${m.bezKadra}), хук ${m.hukDoslovno ? '= карточка' : '≠ карточка'}, кадров ${Object.keys(r.cfg.images).length}`);
  if (PROBA || !ok) continue;
  const fd = path.join(KUDA, 'days', `${r.id}.json`);
  if (MUZEJ !== 'ne-sdayutsya' && KUDA === ROOT && fs.existsSync(fd) && !ZAMENIT) {
    plohih++; console.log(`  ✗ days/${r.id}.json уже есть — не перезаписываю; --v=<папка> для пробы или --zamenit`); continue;
  }
  fs.mkdirSync(path.join(KUDA, 'kadry', r.id), { recursive: true });
  fs.mkdirSync(path.join(KUDA, 'days'), { recursive: true });
  for (const [f, b] of r.fajly) fs.writeFileSync(path.join(KUDA, f), b);
  fs.writeFileSync(fd, `${JSON.stringify(r.cfg, null, 2)}\n`);
  console.log(`  записано ${path.relative(process.cwd(), fd)}`);
  if (MUZEJ !== 'ne-sdayutsya' || KUDA !== ROOT) continue; // замок хука — для days/ns*.json репо
  const z = await zamokDnya(r.id);
  if (z.length) { plohih++; z.forEach((e) => console.log(`  ✗ замок: ${e}`)); }
}
process.exit(plohih ? 2 : 0);
