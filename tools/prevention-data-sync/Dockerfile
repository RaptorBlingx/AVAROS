FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/opt/avaros

WORKDIR /opt/avaros

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY skill/ ./skill/
COPY tools/prevention-data-sync/ ./tools/prevention-data-sync/

CMD ["python", "/opt/avaros/tools/prevention-data-sync/exporter.py", "--daemon"]
