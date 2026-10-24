#!/bin/sh
# Ролик дня одной строкой: scripts/day.sh <день> [A|B|AB] [16x9|9x16]
# days/<день>.json -> голос, слои, звук -> out/<день>-<V>-<формат>.mp4. Для B нужен public/days/<день>/insert.mp4.
set -e
cd "$(dirname "$0")/.."
DAY=$1; V=${2:-A}
[ -f "days/$DAY.json" ] || { echo "нет days/$DAY.json"; exit 1; }
PY=${PY:-$HOME/.venvs/agent/bin/python}
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
export LD_LIBRARY_PATH=$HOME/opt/libs/lib/x86_64-linux-gnu:$HOME/opt/libs/usr/lib/x86_64-linux-gnu
[ -d node_modules ] || npm i
$PY scripts/tts.py "$DAY"
$PY scripts/layers.py "$DAY"
$PY scripts/sfx.py "$DAY"
case $V in *B*) [ -f "public/days/$DAY/insert.mp4" ] || { echo "нет public/days/$DAY/insert.mp4 для варианта B"; exit 1; } ;; esac
node scripts/render.mjs "$DAY" "$V" $3
