# Готовый образ машины для роликов (r713 п.69): всё, что render.yml ставит на каждом прогоне, — здесь один раз.
# Как в мире: образ Remotion по их документации (https://www.remotion.dev/docs/docker) — node:22-bookworm-slim,
# библиотеки Chrome из apt, «npx remotion browser ensure»; задание GitHub в контейнере
# (https://docs.github.com/en/actions/writing-workflows/choosing-where-your-workflow-runs/running-jobs-in-a-container).
# Собирает .github/workflows/obraz.yml при изменении этого файла, package-lock.json или .github/actions/ffmpeg;
# ffmpeg — та же сборка BtbN, что в .github/actions/ffmpeg (FF_TAG/FF_FAJL/FF_SHA256 передаёт obraz.yml оттуда).
# Включается в render.yml входом obraz=true; по умолчанию выключен.
FROM node:22-bookworm-slim

# библиотеки Chrome — список из документации Remotion; git — для actions/checkout; шрифты — запасные, как на машине GitHub
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 libxkbcommon-dev libxfixes3 \
      libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
      git ca-certificates curl xz-utils zstd python3 python3-venv fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ARG FF_TAG
ARG FF_FAJL
ARG FF_SHA256
RUN test -n "$FF_TAG" && test -n "$FF_FAJL" && test -n "$FF_SHA256" \
    && curl -fsSL --retry 3 -o /tmp/ff.tar.xz "https://github.com/BtbN/FFmpeg-Builds/releases/download/$FF_TAG/$FF_FAJL.tar.xz" \
    && echo "$FF_SHA256  /tmp/ff.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/ff.tar.xz -C /usr/local/bin --strip-components=2 "$FF_FAJL/bin/ffmpeg" "$FF_FAJL/bin/ffprobe" \
    && rm /tmp/ff.tar.xz && ffmpeg -version | head -1

# Python-пакеты ozvuchka и layers — те же версии, что в render.yml; venv в PATH, «python» — он
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install -q --no-cache-dir edge-tts==7.3.1 pyyaml==6.0.2 numpy==2.4.6 scipy==1.17.1 \
         opencv-python-headless==5.0.0.93
ENV PATH=/opt/venv/bin:$PATH

# node-пакеты по lock и Chrome Remotion; render.yml кладёт ссылку node_modules -> /opt/rolik/node_modules
WORKDIR /opt/rolik
COPY package.json package-lock.json ./
RUN npm ci && npx remotion browser ensure \
    && ln -s "$(find /opt/rolik /root -type f -name chrome-headless-shell | head -1)" /usr/local/bin/chrome-headless-shell \
    && /usr/local/bin/chrome-headless-shell --version
ENV CHROME=/usr/local/bin/chrome-headless-shell
WORKDIR /
LABEL org.opencontainers.image.source=https://github.com/arabelthera-dot/rc-rolik
