# HiveMind-core Docker Image for AVAROS
#
# Builds a minimal HiveMind-core container that connects to the OVOS
# messagebus and exposes a WebSocket endpoint for browser clients.
#
# hivemind-core v3.4.0 (Apache-2.0 license) — last pre-AGPL release.
# See DEC-026 in docs/DECISIONS.md for architecture rationale.
#
# Source: https://github.com/JarbasHiveMind/HiveMind-core

FROM python:3.11-slim

LABEL maintainer="AVAROS Team"
LABEL description="HiveMind-core WebSocket proxy for OVOS messagebus (DEC-026)"

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash hivemind

# Install hivemind-core (Apache-2.0 licensed version)
RUN pip install --no-cache-dir \
    "hivemind-core>=3.4.0,<4.0.0" \
    "hivemind-websocket-plugin>=0.0.1" \
    "hivemind-ovos-agent-plugin>=0.0.1"

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create config and data directories
RUN mkdir -p /home/hivemind/.config/hivemind-core && \
    mkdir -p /home/hivemind/.local/share/hivemind && \
    chown -R hivemind:hivemind /home/hivemind

USER hivemind
WORKDIR /home/hivemind

# WebSocket port
EXPOSE 5678

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
