# AVAROS OVOS Skill - Docker Image
# Simplified single-stage build for OVOS integration

# ============================================================================
# Base: Python 3.10 (matching OVOS requirements)
# ============================================================================
FROM python:3.10-slim

# Labels for container metadata
LABEL org.opencontainers.image.title="AVAROS OVOS Skill" \
      org.opencontainers.image.description="AI Voice Assistant for Manufacturing KPIs" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="AVAROS Project"

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create ovos user (uid 1000) to match WASABI conventions
RUN groupadd --gid 1000 ovos && \
    useradd --uid 1000 --gid ovos --shell /bin/bash --create-home ovos

# Set working directory
WORKDIR /opt/avaros

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for OVOS configuration
RUN mkdir -p /home/ovos/.config/mycroft /tmp/mycroft /opt/avaros/logs && \
    chown -R ovos:ovos /home/ovos /tmp/mycroft /opt/avaros

# Copy application code
COPY --chown=ovos:ovos skill/ ./skill/
COPY --chown=ovos:ovos launch_skill.py ./launch_skill.py

# Make launcher executable
RUN chmod +x ./launch_skill.py

# Switch to ovos user
USER ovos

# Environment variables for AVAROS
ENV ADAPTER_TYPE=mock \
    LOG_LEVEL=INFO \
    AVAROS_LOG_LEVEL=INFO \
    PATH=/home/ovos/.local/bin:$PATH

# Health check: verify skill can be imported
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "from skill import AVAROSSkill; print('Skill OK')" || exit 1

# Default command: Run the skill launcher
# This will connect to OVOS messagebus and register intents
CMD ["python", "/opt/avaros/launch_skill.py"]

