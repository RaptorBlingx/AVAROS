FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

COPY web-ui/frontend/package.json web-ui/frontend/package-lock.json ./
RUN npm ci

COPY web-ui/frontend/ ./
RUN npm run build && npm run build:widget

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/opt/avaros:/opt/avaros/web-ui \
    AVAROS_SERVER_TTS_ENGINE=auto \
    AVAROS_PIPER_MODEL_PATH=/opt/avaros/tts/piper/en_US-lessac-medium.onnx \
    AVAROS_PIPER_CONFIG_PATH=/opt/avaros/tts/piper/en_US-lessac-medium.onnx.json

WORKDIR /opt/avaros/web-ui

RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY web-ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir piper-tts==1.4.2 \
    && mkdir -p /opt/avaros/tts/piper \
    && python -c "from pathlib import Path; from urllib.request import urlretrieve; base='https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium'; target=Path('/opt/avaros/tts/piper'); [urlretrieve(f'{base}/{name}', target / name) for name in ('en_US-lessac-medium.onnx', 'en_US-lessac-medium.onnx.json') if not (target / name).exists()]"

COPY web-ui/ ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
