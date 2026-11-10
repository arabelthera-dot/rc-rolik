#!/bin/sh
# Отпечаток входов ролика (r713 п.60): scripts/otpechatok.sh <день> <вариант> <формат> -> sha256
# Всё, что читает render.mjs: сценарий дня, кадры, голос/звук/слои public/days/<день>/ (и insert.mp4),
# шрифты, шаблон src/, render.mjs/check.mjs/format.mjs, package-lock.json, ffmpeg; плюс вариант и формат.
# Те же входы — тот же отпечаток (как ключ actions/cache от hashFiles); поменялся любой байт — другой.
set -e
cd "$(dirname "$0")/.."
DAY=$1; V=$2; F=$3
[ -n "$DAY" ] && [ -n "$V" ] && [ -n "$F" ] || { echo "запуск: scripts/otpechatok.sh <день> <вариант> <формат>" >&2; exit 1; }
[ -f "days/$DAY.json" ] || { echo "нет days/$DAY.json" >&2; exit 1; }
{
  echo "rolik $DAY $V $F"
  # seg*.json — служебные ключи озвучки (их нет в репо), сам голос — seg*.mp3/voice.mp3/mix.mp3
  find "days/$DAY.json" "kadry/$DAY" "public/days/$DAY" public/fonts src \
       scripts/render.mjs scripts/check.mjs scripts/format.mjs package-lock.json .github/actions/ffmpeg \
       -type f ! -name 'seg*.json' 2>/dev/null | LC_ALL=C sort | while read -r f; do
    sha256sum "$f"
  done
} | sha256sum | cut -c1-64
