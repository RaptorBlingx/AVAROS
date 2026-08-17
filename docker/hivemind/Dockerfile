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

# hivemind-websocket-protocol 0.0.3 invokes ``write_message`` from the
# OVOS bus client's worker thread.  Modern Tornado requires WebSocket writes
# and closes to run on its IOLoop; otherwise one disconnected browser can
# break delivery for every subsequent client.
old_send = '''        def do_send(payload: str, is_bin: bool):
            self.loop.install()  # TODO is this needed?
            self.write_message(payload, is_bin)

        def do_disconnect():
            self.loop.install()  # TODO is this needed?
            self.close()
'''
new_send = '''        def do_send(payload: str, is_bin: bool):
            self.loop.add_callback(self.write_message, payload, is_bin)

        def do_disconnect():
            self.loop.add_callback(self.close)
'''
if old_send not in source:
    raise SystemExit("Expected websocket send block not found; patch aborted")
source = source.replace(old_send, new_send)

module_path.write_text(source, encoding="utf-8")
print(f"Patched HiveMind auth parser at {module_path}")

# The OVOS agent's catch-all bus callback can disconnect a client while it is
# iterating the live client dictionary.  Iterate over a snapshot to avoid a
# RuntimeError that otherwise disconnects HiveMind from the OVOS bus.
hpm_spec = importlib.util.find_spec("ovos_bus_client.hpm")
if hpm_spec is None or hpm_spec.origin is None:
    raise SystemExit("ovos_bus_client.hpm not found")
hpm_path = Path(hpm_spec.origin)
hpm_source = hpm_path.read_text(encoding="utf-8")
old_clients = "            for peer, client in self.clients.items():\n"
new_clients = "            for peer, client in list(self.clients.items()):\n"
if old_clients not in hpm_source:
    raise SystemExit("Expected HiveMind client iteration not found; patch aborted")
hpm_path.write_text(
    hpm_source.replace(old_clients, new_clients),
    encoding="utf-8",
)
print(f"Patched HiveMind OVOS client iteration at {hpm_path}")
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
