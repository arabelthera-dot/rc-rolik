# Ролики «Русской цивилизации» — сборка на машинах GitHub

Шаблон ролика дня на Remotion. Слои кадров (`scripts/layers.py`) готовятся у нас и лежат в `public/days/`;
голос (`scripts/tts.py`, словарь `udareniya.json`), звук (`scripts/sfx.py`) и рендер — здесь, сценарий
`.github/workflows/render.yml`: озвучка один раз на день, каждый файл ролика на своей машине.
Поправили словарь или сценарий — достаточно коммита и запуска; `-f ozvuchka=false` — взять готовую озвучку из репо.

Запуск: `gh workflow run render.yml -R arabelthera-dot/rc-rolik -f zadacha="05jan:AB"`;
готовое — `gh run download <номер> -R arabelthera-dot/rc-rolik -D out/`.

# Ролик дня на Remotion (проба по Р233, день 5 января — Шухов)

Шаблон один на все дни: композиции `Day16x9` (1920×1080) и `Day9x16` (1080×1920, перекомпоновка: фото-панель + размытый фон + зона схемы + плашка субтитров), всё про день — в `days/<id>.json`.

## Новый день одной строкой
```bash
scripts/day.sh <день> AB     # days/<день>.json -> голос, слои, звук -> out/<день>-{A,B}-{16x9,9x16}.mp4
```
Для варианта B заранее положить `public/days/<день>/insert.mp4`; без вставки — `scripts/day.sh <день> A`. Рендер одного файла 16:9 — ~10 мин на 8 ядрах, 4 файла ~45 мин: запускать отдельным процессом (`setsid nohup scripts/day.sh … > log &`), не ждать в одном вызове.
Проверено 24.10 на копии 05jan: json -> все ресурсы в public/days/<день>/ -> стоп-кадр композиции.

## Как собрать день (по шагам)
```bash
cd ~/projects/russian-civilization/lab/rolik-remotion
npm i                                                    # remotion 4.0.538
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 LD_LIBRARY_PATH=$HOME/opt/libs/lib/x86_64-linux-gnu:$HOME/opt/libs/usr/lib/x86_64-linux-gnu
PY=~/.venvs/agent/bin/python
$PY scripts/tts.py 05jan     # голос edge-tts ru-RU-DmitryNeural +18%, слова WordBoundary -> timeline.json
$PY scripts/layers.py 05jan  # 2.5D: подлинные кадры -> фон + передний план (band / GrabCut)
$PY scripts/sfx.py 05jan     # звуковые акценты + сведение -> mix.mp3
# только для варианта Б: кадрирование правее решётчатой вышки и до 5,0 с (без качалок XX в.), растяжка до длины хука
ffmpeg -y -t 5.0 -i genosai/insert-raw.mp4 -vf "crop=1100:619:820:360,setpts=1.12*PTS,scale=1920:1080:flags=lanczos,fps=30" -an -c:v libx264 -crf 18 -pix_fmt yuv420p public/days/05jan/insert.mp4
node scripts/render.mjs 05jan AB   # -> out/05jan-A-16x9.mp4, -A-9x16, -B-16x9, -B-9x16 (≤20 МБ, H.264)
```
Chromium: `~/.cache/ms-playwright/chromium_headless_shell-1234/.../chrome-headless-shell` (переопределить — `CHROME=`), `--gl=swangle`.
Быстрый кадр: `npx remotion still src/index.ts Day9x16 f.jpg --frame=30 --props='{"day":"05jan","variant":"A"}' --browser-executable=$CHROME --gl=swangle`.

Новый день: скопировать `days/05jan.json`, вписать `segments` (say — что говорит голос, show — как писать в субтитрах цифрами; image; fx: pipe-sweep | dust | formulas | pipeline-map | tower-mesh | endcard) и `images` (src из pilot-izobreteniya, `band` — где начинается передний план, или `fg_rect` для GrabCut; `"parallax": false` — без переднего плана, если полоса даёт шов). Факты — только из md дня.

## Музыка и звук — лицензия
Чужой музыки нет. Гул-подложка, удар и «вжухи» синтезированы `scripts/sfx.py` (numpy/scipy) — собственная работа, CC0. Голос — Microsoft Edge TTS.

## Источники кадров
Подлинные кадры из `pilot-izobreteniya/day-05jan-shukhov-*.jpg`: karavan, podvoda, portret, balakhany1880, shabolovka. Не взяты: poster.jpg (сгенерирован, не подлинник), promysel1888 (водяной знак Azerhistory), velo (нет факта в md).
Вставка Б: `genosai/insert-raw.mp4` — veo-3.1-lite 6 с по образцу `genosai/probe2.jpg` (z-image), в кадре подпись «реконструкция». Кредиты: 1+1 (z-image) + 35 (veo) = 37.

## ПЕРЕДАЧА (24.10, arabelthera-dot)
- Сделано: проект Remotion, сценарий 44,5 с (хук «Русский инженер Шухов первым в мире рассчитал нефтепровод…» с 0,25 с), голос, слои, звук, композиция; тестовые кадры обоих форматов проверены глазами (субтитры не налезают после правки, лица только подлинный портрет). Вставка Б сгенерирована (лиц нет).
- НЕ сделано: рендер 4 файлов, ffprobe и 4 кадра из каждого, — остановлено сторожем контекста.
- Следующий шаг: команды выше от `cp genosai/...` и `node scripts/render.mjs 05jan AB`, затем самопроверка (ffmpeg -ss 0.8/12/25/41) и коммит out/*.mp4 поимённо.
- Слабо: кадры 730 px растянуты до 2200 (мыло на крупных планах); параллакс «полосой» даёт лёгкий шов на караване; во вставке Б мелькает качалка (анахронизм, XX в.) и решётчатые вышки рядом с деревянными; схема башни ярусами похожа на ёлку.
