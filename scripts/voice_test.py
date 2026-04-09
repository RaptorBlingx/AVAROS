"""Voice test script for PREVENTION-related utterances."""

import json
import sys
import time
import uuid

import websocket


def _make_session_context() -> dict:
    """Build minimal OVOS session context to prevent double-dispatch."""
    session_id = str(uuid.uuid4())
    return {
        "session": {
            "session_id": session_id,
        },
        "source": "voice_test",
        "destination": "skills",
    }


def ask(ws, utterance: str, timeout: int = 30) -> str:
    """Send utterance and collect spoken responses."""
    msg = json.dumps({
        "type": "recognizer_loop:utterance",
        "data": {"utterances": [utterance], "lang": "en-us"},
        "context": _make_session_context(),
    })
    ws.send(msg)
    responses: list[str] = []
    ws.settimeout(1.0)
    end = time.time() + timeout
    first_resp = None
    while time.time() < end:
        try:
            raw = ws.recv()
            data = json.loads(raw)
            if data.get("type") == "speak":
                utt = data["data"].get("utterance", "")
                if utt:
                    responses.append(utt)
                    if first_resp is None:
                        first_resp = time.time()
        except websocket.WebSocketTimeoutException:
            if responses and (time.time() - (first_resp or 0)) > 3:
                break
            continue
        except Exception:
            break
    return " ".join(responses) if responses else "[TIMEOUT]"


def main() -> None:
    ws = websocket.WebSocket()
    ws.connect("ws://avaros-messagebus:8181/core", timeout=5)
    print("[OK] Connected to messagebus", flush=True)

    tests = [
        ("Broad Anomaly Scan", "Are there any unusual patterns today?"),
        ("Targeted Anomaly", "Check anomalies for energy per unit on Line-1"),
        ("Drift (no asset)", "How has energy per unit been trending?"),
        ("Unscoped Anomaly", "Check for anomalies"),
        ("System Status", "Show system status"),
        ("Scrap Rate Anomaly", "Any anomalies in scrap rate?"),
        ("CO2 Anomaly (fix)", "Check for unusual carbon patterns on Line-2"),
        ("Supplier Drift", "Is supplier lead time getting worse?"),
        ("OEE Targeted", "Check anomalies for OEE on Line-1"),
    ]

    passed = 0
    failed = 0
    for i, (label, utterance) in enumerate(tests, 1):
        print(flush=True)
        print("=" * 70, flush=True)
        print(f"TEST {i}: {label}", flush=True)
        print(f"  Utterance: {utterance}", flush=True)
        resp = ask(ws, utterance)
        ok = resp != "[TIMEOUT]" and "not found" not in resp.lower()
        print(f"  Response:  {resp}", flush=True)
        print(f"  Status:    {'PASS' if ok else 'FAIL'}", flush=True)
        if ok:
            passed += 1
        else:
            failed += 1
        time.sleep(2)

    ws.close()
    print(flush=True)
    print("=" * 70, flush=True)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}", flush=True)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
