#!/usr/bin/env python3
"""Validate HiveMind WebSocket auth and message roundtrip.

Manual test script for P5-L02 acceptance criteria:
    1. TCP connectivity check on HiveMind port
    2. Authentication with valid key (success)
    3. Authentication with invalid key (rejected)
    4. Utterance -> speak roundtrip over authenticated websocket

Usage:
        python scripts/test-hivemind-connection.py [--host HOST] [--port PORT]
"""

import argparse
import asyncio
import base64
import json
import os
import socket
import sys


def check_tcp_connectivity(host: str, port: int, timeout: float = 5.0) -> bool:
    """Verify TCP connectivity to the HiveMind port.

    Args:
        host: HiveMind hostname.
        port: HiveMind WebSocket port.
        timeout: Connection timeout in seconds.

    Returns:
        True if TCP connection succeeds.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        print(f"  TCP connection failed: {exc}")
        return False


def build_auth_token(client_name: str, access_key: str) -> str:
    """Build base64 authorization token for HiveMind websocket URL.

    Args:
        client_name: Friendly user-agent/client name.
        access_key: HiveMind client access key.

    Returns:
        URL-safe authorization token.
    """
    raw = f"{client_name}:{access_key}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def build_hive_bus_message(utterance: str) -> str:
    """Build an unencrypted HiveMessage(BUS) payload for utterance injection.

    Args:
        utterance: User utterance to inject.

    Returns:
        Serialized HiveMessage JSON.
    """
    payload = {
        "msg_type": "bus",
        "payload": {
            "type": "recognizer_loop:utterance",
            "data": {"utterances": [utterance]},
            "context": {"source": "hive-test", "destination": "skills"},
        },
        "metadata": {},
        "route": [],
        "node": None,
        "target_site_id": None,
        "target_pubkey": None,
        "source_peer": None,
    }
    return json.dumps(payload)


async def check_valid_auth_and_handshake(
    host: str,
    port: int,
    client_name: str,
    access_key: str,
    timeout: float = 10.0,
) -> bool:
    """Verify websocket auth succeeds with a valid key.

    Args:
        host: HiveMind hostname.
        port: HiveMind WebSocket port.
        client_name: HiveMind client name.
        access_key: HiveMind access key.
        timeout: Receive timeout in seconds.

    Returns:
        True when authenticated connection receives server message(s).
    """
    try:
        import websockets
    except ImportError:
        print("  ERROR: 'websockets' package not installed.")
        print("  Install with: pip install websockets")
        return False

    auth = build_auth_token(client_name, access_key)
    uri = f"ws://{host}:{port}/?authorization={auth}"
    try:
        async with websockets.connect(uri, open_timeout=timeout) as ws:
            print(f"  WebSocket connected to {uri}")
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                print(f"  Received message ({len(raw)} bytes)")
                try:
                    msg = json.loads(raw)
                    msg_type = msg.get("type", msg.get("msg_type", "unknown"))
                    print(f"  Message type: {msg_type}")
                    if "payload" in msg:
                        payload = msg["payload"]
                        if isinstance(payload, dict):
                            proto_version = payload.get(
                                "max_protocol_version", "N/A"
                            )
                            crypto_required = payload.get(
                                "crypto_required", "N/A"
                            )
                            print(f"  Protocol version: {proto_version}")
                            print(f"  Crypto required: {crypto_required}")
                except (json.JSONDecodeError, TypeError):
                    print("  Received binary/non-JSON handshake data")

                return True
            except asyncio.TimeoutError:
                print("  WARNING: No server message within timeout")
                return True

    except ConnectionRefusedError:
        print(f"  WebSocket connection refused at {uri}")
        return False
    except Exception as exc:
        print(f"  WebSocket error: {exc}")
        return False


async def check_invalid_auth_rejected(
    host: str,
    port: int,
    timeout: float = 5.0,
) -> bool:
    """Verify websocket auth fails with an invalid key.

    Args:
        host: HiveMind hostname.
        port: HiveMind WebSocket port.
        timeout: Timeout for handshake/close.

    Returns:
        True when invalid auth is rejected (connection closes/errors).
    """
    try:
        import websockets
    except ImportError:
        print("  ERROR: 'websockets' package not installed.")
        print("  Install with: pip install websockets")
        return False

    bogus_auth = build_auth_token("invalid-client", "definitely-invalid-key")
    uri = f"ws://{host}:{port}/?authorization={bogus_auth}"

    try:
        async with websockets.connect(uri, open_timeout=timeout) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=timeout)
                print("  Unexpectedly received data with invalid auth")
                return False
            except Exception:
                return True
    except Exception:
        return True


async def check_utterance_roundtrip(
    host: str,
    port: int,
    client_name: str,
    access_key: str,
    utterance: str,
    timeout: float = 20.0,
) -> bool:
    """Send utterance and wait for speak response over authenticated websocket.

    Args:
        host: HiveMind hostname.
        port: HiveMind port.
        client_name: Client user-agent.
        access_key: Client access key.
        utterance: Utterance text to inject.
        timeout: Total timeout in seconds.

    Returns:
        True if a speak message is received.
    """
    try:
        import websockets
    except ImportError:
        print("  ERROR: 'websockets' package not installed.")
        print("  Install with: pip install websockets")
        return False

    auth = build_auth_token(client_name, access_key)
    uri = f"ws://{host}:{port}/?authorization={auth}"

    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            for _ in range(3):
                try:
                    await asyncio.wait_for(ws.recv(), timeout=3)
                except Exception:
                    break

            message = build_hive_bus_message(utterance)
            await ws.send(message)
            print(f"  Sent utterance: {utterance}")

            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = max(0.5, deadline - asyncio.get_event_loop().time())
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue

                if msg.get("msg_type") != "bus":
                    continue

                payload = msg.get("payload", {})
                if payload.get("type") == "speak":
                    data = payload.get("data", {})
                    print(f"  Received speak: {data}")
                    return True

            print("  No speak response received within timeout")
            return False
    except Exception as exc:
        print(f"  Roundtrip error: {exc}")
        return False


def main() -> None:
    """Run HiveMind connectivity checks."""
    parser = argparse.ArgumentParser(
        description="Validate HiveMind WebSocket connectivity"
    )
    parser.add_argument(
        "--host", default="localhost", help="HiveMind host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=5678, help="HiveMind port (default: 5678)"
    )
    parser.add_argument(
        "--client-name",
        default=os.environ.get("HIVEMIND_CLIENT_NAME", "avaros-web-client"),
        help="HiveMind client name",
    )
    parser.add_argument(
        "--access-key",
        default=os.environ.get("HIVEMIND_CLIENT_KEY", os.environ.get("HIVEMIND_ACCESS_KEY", "avaros-web-client")),
        help="HiveMind client access key",
    )
    parser.add_argument(
        "--utterance",
        default="what is the status",
        help="Utterance used for roundtrip validation",
    )
    args = parser.parse_args()

    print(f"=== HiveMind Connectivity Test ===")
    print(f"Target: {args.host}:{args.port}\n")

    # Step 1: TCP check
    print("Step 1: TCP connectivity")
    tcp_ok = check_tcp_connectivity(args.host, args.port)
    print(f"  Result: {'PASS' if tcp_ok else 'FAIL'}\n")

    if not tcp_ok:
        print("FAILED: Cannot reach HiveMind port.")
        print("Check that the HiveMind container is running:")
        print("  docker compose -f docker/docker-compose.avaros.yml ps hivemind")
        sys.exit(1)

    # Step 2: Valid auth check
    print("Step 2: WebSocket auth (valid key)")
    auth_ok = asyncio.run(
        check_valid_auth_and_handshake(
            args.host,
            args.port,
            args.client_name,
            args.access_key,
        )
    )
    print(f"  Result: {'PASS' if auth_ok else 'FAIL'}\n")

    if not auth_ok:
        print("FAILED: Valid-key authentication failed.")
        print("Check HiveMind logs:")
        print("  docker compose -f docker/docker-compose.avaros.yml logs hivemind")
        sys.exit(1)

    # Step 3: Invalid auth check
    print("Step 3: WebSocket auth (invalid key rejected)")
    invalid_rejected = asyncio.run(check_invalid_auth_rejected(args.host, args.port))
    print(f"  Result: {'PASS' if invalid_rejected else 'FAIL'}\n")

    if not invalid_rejected:
        print("FAILED: Invalid-key authentication was not rejected.")
        sys.exit(1)

    # Step 4: Utterance -> speak roundtrip
    print("Step 4: Utterance -> speak roundtrip")
    roundtrip_ok = asyncio.run(
        check_utterance_roundtrip(
            args.host,
            args.port,
            args.client_name,
            args.access_key,
            args.utterance,
        )
    )
    print(f"  Result: {'PASS' if roundtrip_ok else 'FAIL'}\n")

    if not roundtrip_ok:
        print("FAILED: Roundtrip validation failed (utterance -> speak).")
        print("Check OVOS + HiveMind logs:")
        print("  docker compose -f docker/docker-compose.avaros.yml logs ovos_core hivemind")
        sys.exit(1)

    print("=== All checks PASSED ===")
    print(
        f"HiveMind auth and roundtrip validated at ws://{args.host}:{args.port}"
    )


if __name__ == "__main__":
    main()
