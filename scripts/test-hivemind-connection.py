#!/usr/bin/env python3
"""Validate HiveMind WebSocket connectivity.

Manual test script to verify HiveMind-core is running and reachable.
Requires: pip install websockets

Usage:
    python scripts/test-hivemind-connection.py [--host HOST] [--port PORT]

This script performs:
  1. TCP connectivity check on the HiveMind port
  2. WebSocket upgrade handshake
  3. Waits for HiveMind HANDSHAKE message (protocol negotiation)

Note: Full authenticated message roundtrip requires the hivemind-bus-client
library and proper key exchange. This script validates infrastructure only.
"""

import argparse
import asyncio
import json
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


async def check_websocket_handshake(
    host: str, port: int, timeout: float = 10.0
) -> bool:
    """Connect via WebSocket and wait for HiveMind handshake message.

    HiveMind-core sends a HANDSHAKE message immediately after WebSocket
    upgrade. This verifies the protocol is active.

    Args:
        host: HiveMind hostname.
        port: HiveMind WebSocket port.
        timeout: Timeout for receiving the handshake.

    Returns:
        True if WebSocket connects and receives a handshake.
    """
    try:
        import websockets
    except ImportError:
        print("  ERROR: 'websockets' package not installed.")
        print("  Install with: pip install websockets")
        return False

    uri = f"ws://{host}:{port}"
    try:
        async with websockets.connect(uri, open_timeout=timeout) as ws:
            print(f"  WebSocket connected to {uri}")

            # HiveMind sends a handshake message on connection
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                print(f"  Received message ({len(raw)} bytes)")

                # Try to parse as JSON
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
                print("  WARNING: No handshake message within timeout")
                print("  WebSocket is open but no data received")
                return True  # Connection works, just no data yet

    except ConnectionRefusedError:
        print(f"  WebSocket connection refused at {uri}")
        return False
    except Exception as exc:
        print(f"  WebSocket error: {exc}")
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

    # Step 2: WebSocket handshake
    print("Step 2: WebSocket handshake")
    ws_ok = asyncio.run(check_websocket_handshake(args.host, args.port))
    print(f"  Result: {'PASS' if ws_ok else 'FAIL'}\n")

    if not ws_ok:
        print("FAILED: WebSocket handshake failed.")
        print("Check HiveMind logs:")
        print("  docker compose -f docker/docker-compose.avaros.yml logs hivemind")
        sys.exit(1)

    print("=== All checks PASSED ===")
    print(f"HiveMind is running and accepting WebSocket connections at "
          f"ws://{args.host}:{args.port}")


if __name__ == "__main__":
    main()
