#!/bin/sh
# Ролики месяца по этапам (r713 п.56): scripts/mesyac.sh <день[:варианты]|месяц>… [16x9|9x16|oba] [--suho] [--kesh]
#   scripts/mesyac.sh 01feb 02feb ns01feb ns02feb --suho   — план без коммита и запуска
#   scripts/mesyac.sh feb                                   — все days/??feb.json и days/ns??feb.json, вариант A
# Все дни — один прогон render.yml: задание render ждёт все задания ozvuchka (needs), поэтому сначала
# озвучиваются все дни месяца, потом собираются все ролики (как стадии сборки в GitHub Actions — needs).
# Каждый день проходит те же проверки, что в day.sh (--proverit); не прошёл — в прогон не идёт.
# Прогон отдаётся облаку и не ждётся (Р686 п.3): ролики на сайт приносит rolik-na-sait. --kesh — render.yml -f kesh=true.
set -e
cd "$(dirname "$0")/.."
REPO=arabelthera-dot/rc-rolik
SUHO=; KESH=false; F=oba; TOK=
for a; do case $a in
  --suho) SUHO=1 ;; --kesh) KESH=true ;; 16x9|9x16|oba) F=$a ;;
  jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)
    for f in days/[0-9][0-9]"$a".json days/ns[0-9][0-9]"$a".json; do [ -f "$f" ] && TOK="$TOK $(basename "$f" .json)"; done ;;
  -*) echo "не знаю флаг $a"; exit 1 ;;
  *) TOK="$TOK $a" ;;
esac; done
[ -n "$TOK" ] || { echo "запуск: scripts/mesyac.sh <день[:варианты]|месяц>… [16x9|9x16|oba] [--suho] [--kesh]"; exit 1; }
fmts="16x9 9x16"; [ "$F" = oba ] || fmts=$F
ZAD=; NET=; N=0
for t in $TOK; do
  d=${t%%:*}; v=${t#*:}; [ "$v" = "$t" ] && v=A
  if sh scripts/day.sh "$d" "$v" "$F" --proverit >/tmp/mesyac-$$.log 2>&1; then
    ZAD="$ZAD $d:$v"; N=$((N + ${#v} * $(echo $fmts | wc -w)))
  else
    NET="$NET\n  ✗ $d:$v — $(tail -1 /tmp/mesyac-$$.log)"
  fi
done
rm -f /tmp/mesyac-$$.log
ZAD=${ZAD# }
echo "План (один прогон render.yml, формат $F, кэш готовых роликов: $KESH):"
NS=$(for z in $ZAD; do echo "${z%%:*}"; done | grep -E '^ns[0-9]{2}[a-z]{3}$' | tr '\n' ' ')
[ -n "$NS" ] && echo "  этап 0 — сценарий НС из карточки rc-site main: $NS"
echo "  этап 1 — озвучка (по 2 дня разом): $(echo "$ZAD" | sed 's/:[AB]*//g')"
echo "  этап 2 — слои кадров, параллельно с озвучкой: те же дни"
echo "  этап 3 — ролики, после всех озвучек: $N ($(for z in $ZAD; do for v in $(echo "${z#*:}" | grep -o .); do for f in $fmts; do printf '%s ' "${z%%:*}-$v-$f"; done; done; done))"
[ "$F" = oba ] && echo "  этап 4 — выпуск на сайт: дни с полем sajt в days/<день>.json"
[ -n "$NET" ] && printf '%b\n' "Не идут в прогон (не прошли проверки day.sh):$NET"
[ -n "$ZAD" ] || { echo "нечего собирать"; exit 1; }
[ -n "$SUHO" ] && { echo "--suho: ничего не закоммичено и не запущено"; exit 0; }

oblako_net() { echo "облако недоступно: $1 — ролики не собраны, локально не собираю (Р243)"; exit 2; }
gh auth status >/dev/null 2>&1 || oblako_net "gh не вошёл в GitHub"
BR=$(git rev-parse --abbrev-ref HEAD)
for z in $ZAD; do
  d=${z%%:*}; git add "days/$d.json"; [ -d "kadry/$d" ] && git add "kadry/$d"
  case ${z#*:} in *B*) git add "public/days/$d/insert.mp4" ;; esac
done
git diff --cached --quiet || git commit -q -m "mesyac: дни для роликов (${ZAD})"
git push -q origin "HEAD:$BR" || oblako_net "не отправился коммит в $REPO"
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run render.yml -R "$REPO" --ref "$BR" -f zadacha="$ZAD" -f format="$F" -f kesh="$KESH" || oblako_net "не запустился render.yml"
for i in $(seq 30); do
  sleep 4
  ID=$(gh run list -R "$REPO" -w render.yml -b "$BR" -e workflow_dispatch -L 5 --json databaseId,createdAt \
       -q "[.[] | select(.createdAt >= \"$START\")][-1].databaseId")
  [ -n "$ID" ] && break
done
[ -n "$ID" ] || oblako_net "прогон не появился"
echo "прогон $ID: https://github.com/$REPO/actions/runs/$ID — отдан облаку, не жду"
