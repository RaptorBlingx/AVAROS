# AVAROS OVOS Skill - Docker Image
# Multi-stage build for optimized image size

# ============================================================================
# Stage 1: Base Python image with dependencies
# ============================================================================
FROM python:3.11-slim as base

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Stage 2: Builder - Install Python dependencies
# ============================================================================
FROM base as builder

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ============================================================================
# Stage 3: Runtime - Final slim image
# ============================================================================
FROM python:3.11-slim as runtime

# Labels for container metadata
LABEL org.opencontainers.image.title="AVAROS OVOS Skill" \
      org.opencontainers.image.description="AI Voice Assistant for Manufacturing KPIs" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="AVAROS Project"

# Runtime environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AVAROS_LOG_LEVEL=INFO \
    AVAROS_DATA_PATH=/data

# Create non-root user for security
RUN groupadd --gid 1000 avaros && \
    useradd --uid 1000 --gid avaros --shell /bin/bash --create-home avaros

# Copy installed packages from builder
COPY --from=builder /root/.local /home/avaros/.local
ENV PATH=/home/avaros/.local/bin:$PATH

# Create data directory for SQLite persistence
RUN mkdir -p /data && chown avaros:avaros /data
VOLUME /data

# Copy application code
WORKDIR /app
COPY --chown=avaros:avaros . .

# Switch to non-root user
USER avaros

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from skill import AVAROSSkill; print('OK')" || exit 1

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "skill"]
