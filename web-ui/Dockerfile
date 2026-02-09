FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend

COPY web-ui/frontend/package.json ./
RUN npm install

COPY web-ui/frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/opt/avaros:/opt/avaros/web-ui

WORKDIR /opt/avaros/web-ui

COPY web-ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY web-ui/ ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
