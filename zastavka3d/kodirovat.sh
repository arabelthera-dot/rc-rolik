#!/usr/bin/env bash
# Кодирование заставки (r521) — только в облаке GitHub Actions (Р243).
# kodirovat.sh <папка-кадров> <имя-без-расширения>: mp4 (H.264) и webm (VP9) ≤ 2 МБ без звука, постер webp ≤ 100 КБ.
# Последние 0,5 с ролик растворяется в первый кадр — цикл без скачка.
set -euo pipefail
F="$1"; NAME="$2"; LIM=$((2*1024*1024)); PLIM=$((100*1024))
n=$(ls "$F"/f*.png | wc -l); dur=$(echo "scale=4; $n/30" | bc); off=$(echo "scale=4; $dur-0.5" | bc)
FC="[0:v]fps=30,format=yuv420p,settb=AVTB[a];[1:v]fps=30,format=yuv420p,settb=AVTB[b];[a][b]xfade=transition=fade:duration=0.5:offset=$off,format=yuv420p[v]"
IN=(-framerate 30 -i "$F/f%05d.png" -loop 1 -framerate 30 -t 0.6 -i "$F/f00000.png")
size() { stat -c %s "$1"; }
for crf in 24 26 28 30 32 34 36 38; do
  ffmpeg -y -loglevel error "${IN[@]}" -filter_complex "$FC" -map "[v]" -t "$dur" -an \
    -c:v libx264 -preset slow -crf $crf -pix_fmt yuv420p -profile:v high -movflags +faststart "$NAME.mp4"
  echo "mp4 crf=$crf $(size "$NAME.mp4")"; [ "$(size "$NAME.mp4")" -le $LIM ] && break
done
for crf in 32 35 38 41 44 47 50; do
  ffmpeg -y -loglevel error "${IN[@]}" -filter_complex "$FC" -map "[v]" -t "$dur" -an \
    -c:v libvpx-vp9 -b:v 0 -crf $crf -deadline good -cpu-used 2 -row-mt 1 -pix_fmt yuv420p "$NAME.webm"
  echo "webm crf=$crf $(size "$NAME.webm")"; [ "$(size "$NAME.webm")" -le $LIM ] && break
done
for q in 82 75 68 60 50 40; do
  ffmpeg -y -loglevel error -i "$F/f00000.png" -c:v libwebp -quality $q "$NAME.webp"
  echo "webp q=$q $(size "$NAME.webp")"; [ "$(size "$NAME.webp")" -le $PLIM ] && break
done
for x in mp4 webm webp; do [ "$(size "$NAME.$x")" -le $([ $x = webp ] && echo $PLIM || echo $LIM) ] || { echo "::error::$NAME.$x больше предела"; exit 1; }; done
ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt:format=duration,nb_streams -of compact "$NAME.mp4"
ffprobe -v error -show_entries stream=codec_name,width,height:format=duration,nb_streams -of compact "$NAME.webm"
