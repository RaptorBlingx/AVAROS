#!/usr/bin/env python3
"""Re-test PREVENTION voice queries after bugfixes."""
from __future__ import annotations

import json
import time
from websocket import create_connection

WS_URL = "ws://avaros-messagebus:8181/core"
TIMEOUT = 15

TEST_CASES = [
    # BUG-1: Targeted anomaly with dash-separated asset
    ("Targeted anomaly (Line-1)", "Check anomalies for energy per unit on Line-1"),
    ("Targeted anomaly (Line-2)", "Check anomalies for scrap rate on Line-2"),
    # BUG-1: Targeted anomaly with space-separated asset (should still work)
    ("Targeted anomaly (line 1 space)", "Check anomalies for energy per unit on line 1"),
    # BUG-2: Drift without explicit asset
    ("Drift no asset", "How has energy per unit been trending?"),
    ("Drift getting worse", "Is OEE getting worse?"),
    # BUG-2: Drift with explicit asset
    ("Drift with asset", "Check for drift on Line-1"),
    # Broad anomaly (should still work)
    ("Broad anomaly scan", "Are there any unusual patterns today?"),
    # System status (should still work)
    ("System status", "What is the prevention status?"),
]


def send_utterance(ws, text: str) -> list[str]:
    """Send utterance and collect speak responses."""
    msg = json.dumps({
        "type": "recognizer_loop:utterance",
        "data": {"utterances": [text], "lang": "en-us"},
        "context": {},
    })
    ws.send(msg)

    responses = []
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        ws.settimeout(max(0.1, deadline - time.time()))
        try:
            raw = ws.recv()
        except Exception:
            break
        parsed = json.loads(raw)
        if parsed.get("type") == "speak":
            utterance = parsed.get("data", {}).get("utterance", "")
            if utterance:
                responses.append(utterance)
                deadline = time.time() + 3  # short grace after last speak
    return responses


def main() -> None:
    ws = create_connection(WS_URL, timeout=10)
    print("[OK] Connected to messagebus\n")

    results = []
    for label, utterance in TEST_CASES:
        print(f"{'=' * 60}")
        print(f"TEST: {label}")
        print(f"  Utterance: {utterance}")

        responses = send_utterance(ws, utterance)
        print(f"  Responses ({len(responses)}):")
        for i, r in enumerate(responses, 1):
            print(f"    [{i}] {r[:200]}")

        results.append((label, utterance, responses))
        time.sleep(2)

    ws.close()

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for label, utterance, responses in results:
        status = "OK" if responses else "NO RESPONSE"
        # Check for targeted vs broad
        if "targeted" in label.lower():
            is_targeted = any("anomalies across" not in r.lower() for r in responses)
            status = "TARGETED" if is_targeted else "BROAD (BUG)"
        if "drift" in label.lower():
            has_error = any("couldn't find" in r.lower() for r in responses)
            status = "ERROR" if has_error else "OK"
        print(f"  [{status:8s}] {label}: {responses[0][:80] if responses else 'N/A'}")


if __name__ == "__main__":
    main()
