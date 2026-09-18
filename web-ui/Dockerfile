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
    AVAROS_PIPER_CONFIG_PATH=/opt/avaros/tts/piper/en_US-lessac-medium.onnx.json \
    AVAROS_PIPER_TR_MODEL_PATH=/opt/avaros/tts/piper/tr_TR-dfki-medium.onnx \
    AVAROS_PIPER_TR_CONFIG_PATH=/opt/avaros/tts/piper/tr_TR-dfki-medium.onnx.json

WORKDIR /opt/avaros/web-ui

RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY web-ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir piper-tts==1.4.2 \
    && mkdir -p /opt/avaros/tts/piper \
    && python -c "from pathlib import Path; from urllib.request import urlretrieve; target=Path('/opt/avaros/tts/piper'); voices={'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium':('en_US-lessac-medium.onnx','en_US-lessac-medium.onnx.json'),'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/tr/tr_TR/dfki/medium':('tr_TR-dfki-medium.onnx','tr_TR-dfki-medium.onnx.json')}; [urlretrieve(f'{base}/{name}', target / name) for base,names in voices.items() for name in names if not (target / name).exists()]" \
    && echo "2844717f524ab965d3fe86e60562cbb601d3e456836efcc2196cc3a14112a8fb  /opt/avaros/tts/piper/tr_TR-dfki-medium.onnx" | sha256sum -c -

COPY web-ui/ ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
