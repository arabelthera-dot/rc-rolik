#!/bin/sh
# Ролик дня одной строкой: scripts/day.sh <день> [A|B|AB] [16x9|9x16|oba] [--lokalno]
# Сборка — в облаке rc-rolik (render.yml, Р243): здесь только коммит days/<день>.json, kadry/<день>/
# (и public/days/<день>/insert.mp4 для B), запуск прогона и скачивание готового в out/.
# Голос, звук, слои и рендер идут на машинах GitHub. --lokalno — старая сборка на нашем сервере, только в крайнем случае.
set -e
cd "$(dirname "$0")/.."
REPO=arabelthera-dot/rc-rolik
LOKALNO=; ARGS=
for a; do case $a in --lokalno) LOKALNO=1 ;; *) ARGS="$ARGS $a" ;; esac; done
set -- $ARGS
DAY=$1; V=${2:-A}; F=${3:-oba}
[ -n "$DAY" ] || { echo "запуск: scripts/day.sh <день> [A|B|AB] [16x9|9x16|oba] [--lokalno]"; exit 1; }
[ -f "days/$DAY.json" ] || { echo "нет days/$DAY.json"; exit 1; }
case $V in A|B|AB) ;; *) echo "вариант — A, B или AB, а не $V"; exit 1 ;; esac
case $F in 16x9|9x16|oba) ;; *) echo "формат — 16x9, 9x16 или oba, а не $F"; exit 1 ;; esac
case $V in *B*) [ -f "public/days/$DAY/insert.mp4" ] || { echo "нет public/days/$DAY/insert.mp4 для варианта B"; exit 1; } ;; esac
# картинки дня — в самом репо (src от корня, kadry/<день>/), иначе облако их не увидит
python3 - "$DAY" <<'E' || exit 1
import json, sys, pathlib
day = sys.argv[1]
miss = [im["src"] for im in json.loads(pathlib.Path(f"days/{day}.json").read_text())["images"].values()
        if not pathlib.Path(im["src"]).is_file()]
if miss:
    sys.exit("нет картинок в репо (src — от корня rc-rolik, обычно kadry/%s/):\n  " % day + "\n  ".join(miss))
E
# сценарий: fx plate без содержимого и т. п. (scripts/check.mjs, r254) — то же падение, что в облаке, но до пуша
node scripts/check.mjs "$DAY" || exit 1

if [ -n "$LOKALNO" ]; then
  echo "ВНИМАНИЕ: --lokalno — сборка на нашем сервере, против Р243 (ролики — в GitHub Actions). Только если облако недоступно и Михаил согласен."
  PY=${PY:-$HOME/.venvs/agent/bin/python}
  export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
  export LD_LIBRARY_PATH=$HOME/opt/libs/lib/x86_64-linux-gnu:$HOME/opt/libs/usr/lib/x86_64-linux-gnu
  [ -d node_modules ] || npm i
  $PY scripts/tts.py "$DAY"
  $PY scripts/layers.py "$DAY"
  $PY scripts/sfx.py "$DAY"
  [ "$F" = oba ] && F=
  exec node scripts/render.mjs "$DAY" "$V" $F
fi

oblako_net() { echo "облако недоступно: $1 — ролик не собран, локально не собираю (Р243). Повтори позже или scripts/day.sh … --lokalno"; exit 2; }
command -v gh >/dev/null || oblako_net "нет gh"
gh auth status >/dev/null 2>&1 || oblako_net "gh не вошёл в GitHub"
[ "$(gh api "repos/$REPO" -q .permissions.push 2>/dev/null)" = true ] || oblako_net "нет доступа к $REPO"

BR=$(git rev-parse --abbrev-ref HEAD)
git add "days/$DAY.json" "kadry/$DAY"
case $V in *B*) git add "public/days/$DAY/insert.mp4" ;; esac
git diff --cached --quiet || git commit -q -m "$DAY: день для ролика (day.sh)"
git push -q origin "HEAD:$BR" || oblako_net "не отправился коммит в $REPO"

START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run render.yml -R "$REPO" --ref "$BR" -f zadacha="$DAY:$V" -f format="$F" || oblako_net "не запустился render.yml"
ID=
for i in $(seq 30); do
  sleep 4
  ID=$(gh run list -R "$REPO" -w render.yml -b "$BR" -e workflow_dispatch -L 5 --json databaseId,createdAt \
       -q "[.[] | select(.createdAt >= \"$START\")][-1].databaseId")
  [ -n "$ID" ] && break
done
[ -n "$ID" ] || oblako_net "прогон не появился"
echo "прогон $ID: https://github.com/$REPO/actions/runs/$ID — жду"
gh run watch "$ID" -R "$REPO" --exit-status --interval 30 >/dev/null || { echo "прогон $ID упал: https://github.com/$REPO/actions/runs/$ID"; exit 1; }
TMP=$(mktemp -d)
gh run download "$ID" -R "$REPO" -p "$DAY-*" -D "$TMP"
mkdir -p out
find "$TMP" -name '*.mp4' -exec mv {} out/ \;
rm -r "$TMP"
ls -l out/"$DAY"-*.mp4
