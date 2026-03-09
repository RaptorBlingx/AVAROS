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

# Install HiveMind runtime dependencies.
# NOTE: hivemind-websocket-plugin / hivemind-ovos-agent-plugin are plugin IDs,
# not PyPI package names. The corresponding PyPI packages are:
# - hivemind-websocket-protocol
# - ovos-bus-client (+ hivemind-bus-client)
RUN pip install --no-cache-dir \
    "hivemind-core==3.4.0" \
    "hivemind-websocket-protocol>=0.0.3,<0.1.0" \
    "hivemind-bus-client>=0.4.4" \
    "ovos-bus-client>=1.3.2"

# Patch websocket auth parsing to accept proxied URI/query variants.
# Some reverse proxies normalize or encode query values differently; this
# keeps HiveMind auth parsing tolerant without changing client credentials.
RUN python - <<'PY'
from pathlib import Path
import importlib.util

spec = importlib.util.find_spec("hivemind_websocket_protocol")
if spec is None or spec.origin is None:
    raise SystemExit("hivemind_websocket_protocol not found")

module_path = Path(spec.origin)
source = module_path.read_text(encoding="utf-8")

old = '''    @staticmethod
    def decode_auth(auth: str) -> Tuple[str, str]:
        """
        Decode the base64 encoded authorization string.

        Args:
            auth (str): The base64 encoded authorization string.

        Returns:
            Tuple[str, str]: The decoded username and key.
        """
        userpass_encoded = bytes(auth, encoding="utf-8")
        userpass_decoded = pybase64.b64decode(userpass_encoded).decode("utf-8")
        name, key = userpass_decoded.split(":")
        return name, key
'''

new = '''    @staticmethod
    def decode_auth(auth: str) -> Tuple[str, str]:
        """Decode authorization from raw token or URI/query-string form."""
        from urllib.parse import unquote

        token = auth or ""
        if "authorization=" in token:
            token = token.split("authorization=", 1)[-1]
        token = token.split("&", 1)[0]
        token = unquote(token)
        if len(token) % 4:
            token = token + ("=" * (4 - (len(token) % 4)))

        userpass_encoded = bytes(token, encoding="utf-8")
        try:
            userpass_decoded = pybase64.b64decode(userpass_encoded).decode("utf-8")
        except Exception:
            LOG.error("Failed to decode websocket auth token: %r", token)
            raise
        name, key = userpass_decoded.split(":", 1)
        return name, key
'''

if old not in source:
    raise SystemExit("Expected decode_auth block not found; patch aborted")

source = source.replace(old, new)

old_open = '        auth = self.request.uri.split("/?authorization=")[-1]\n'
new_open = '''        auth = self.get_argument("authorization", default="")
        if not auth:
            auth = self.request.headers.get("X-HiveMind-Auth", "")
        if not auth:
            default_name = os.environ.get("HIVEMIND_CLIENT_NAME", "")
            default_key = os.environ.get("HIVEMIND_CLIENT_KEY", "")
            if default_name and default_key:
                auth = pybase64.b64encode(
                    f"{default_name}:{default_key}".encode("utf-8")
                ).decode("utf-8")
        if not auth:
            auth = self.request.uri
'''
if old_open not in source:
    raise SystemExit("Expected open() auth extraction line not found; patch aborted")
source = source.replace(old_open, new_open)

module_path.write_text(source, encoding="utf-8")
print(f"Patched HiveMind auth parser at {module_path}")
PY

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
