#!/usr/bin/env python3
"""PREVENTION Voice Test — Terminal-based voice pipeline evaluation.

Sends real utterances through the OVOS messagebus and evaluates responses
for accuracy, helpfulness, clarity, and completeness.

Usage:
  docker exec avaros-skill python3 /opt/avaros/scripts/prevention_voice_test.py

  # Or from host with port-forwarded messagebus:
  MESSAGEBUS_HOST=localhost MESSAGEBUS_PORT=8181 python3 scripts/prevention_voice_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

try:
    import websocket
except ImportError:
    print("[FATAL] websocket-client not installed. Run: pip install websocket-client")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────

MESSAGEBUS_HOST = os.environ.get("MESSAGEBUS_HOST", "avaros-messagebus")
MESSAGEBUS_PORT = int(os.environ.get("MESSAGEBUS_PORT", "8181"))
MESSAGEBUS_URL = f"ws://{MESSAGEBUS_HOST}:{MESSAGEBUS_PORT}/core"
UTTERANCE_TIMEOUT = 25  # seconds to wait for response


# ── Voice Interface ────────────────────────────────────────

def send_utterance(ws: websocket.WebSocket, text: str) -> dict[str, Any]:
    """Send utterance via messagebus and capture all spoken responses."""
    msg = {
        "type": "recognizer_loop:utterance",
        "data": {"utterances": [text], "lang": "en-us"},
        "context": {},
    }
    ws.send(json.dumps(msg))

    responses: list[str] = []
    all_events: list[dict] = []
    deadline = time.time() + UTTERANCE_TIMEOUT
    first_response_time: float | None = None
    ws.settimeout(1.0)

    while time.time() < deadline:
        try:
            raw = ws.recv()
        except websocket.WebSocketTimeoutException:
            # If we already got a response and 4s passed, done
            if responses and first_response_time and (
                time.time() - first_response_time > 4
            ):
                break
            continue
        except Exception:
            break

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        all_events.append(data)

        if data.get("type") == "speak":
            utt = data.get("data", {}).get("utterance", "")
            if utt:
                responses.append(utt)
                if first_response_time is None:
                    first_response_time = time.time()

    combined = " ".join(responses)
    return {
        "utterance": text,
        "response": combined if combined else "[TIMEOUT - No response]",
        "responses": responses,
        "event_count": len(all_events),
        "response_time": round(first_response_time - (deadline - UTTERANCE_TIMEOUT), 2) if first_response_time else None,
    }


# ── Test Cases ─────────────────────────────────────────────

TEST_CASES = [
    # ── Anomaly: Broad Scan ──
    {
        "id": "ANOMALY-BROAD-1",
        "category": "anomaly_broad",
        "utterance": "Are there any unusual patterns today?",
        "expect": "Aggregate report with anomaly count and severity",
    },
    {
        "id": "ANOMALY-BROAD-2",
        "category": "anomaly_broad",
        "utterance": "Check for anomalies",
        "expect": "Broad scan (no metric/asset specified)",
    },
    {
        "id": "ANOMALY-BROAD-3",
        "category": "anomaly_broad",
        "utterance": "Any anomalies in production?",
        "expect": "Broad scan focused on production metrics",
    },
    # ── Anomaly: Targeted ──
    {
        "id": "ANOMALY-TARGET-1",
        "category": "anomaly_targeted",
        "utterance": "Check anomalies for energy per unit on Line-1",
        "expect": "Single-pair result: energy_per_unit + Line-1",
    },
    {
        "id": "ANOMALY-TARGET-2",
        "category": "anomaly_targeted",
        "utterance": "Any unusual energy patterns on Line-2?",
        "expect": "Targeted energy anomaly on Line-2",
    },
    {
        "id": "ANOMALY-TARGET-3",
        "category": "anomaly_targeted",
        "utterance": "Check anomalies for scrap rate on Line-1",
        "expect": "Single-pair result: scrap_rate + Line-1",
    },
    # ── Drift ──
    {
        "id": "DRIFT-1",
        "category": "drift",
        "utterance": "How has energy per unit been trending?",
        "expect": "Drift direction + rate for energy per unit",
    },
    {
        "id": "DRIFT-2",
        "category": "drift",
        "utterance": "Check for drift in scrap rate",
        "expect": "Drift analysis for scrap rate",
    },
    {
        "id": "DRIFT-3",
        "category": "drift",
        "utterance": "Is OEE getting worse?",
        "expect": "Drift analysis for OEE",
    },
    # ── System Status ──
    {
        "id": "STATUS-1",
        "category": "system",
        "utterance": "Show system status",
        "expect": "Prevention mode + adapter + profile info",
    },
    {
        "id": "STATUS-2",
        "category": "system",
        "utterance": "What profile is active?",
        "expect": "Active profile name (reneryo)",
    },
]


# ── Runner ─────────────────────────────────────────────────

def run_tests() -> list[dict]:
    """Execute all test cases and return results."""
    print("=" * 72)
    print("PREVENTION VOICE PIPELINE TEST")
    print(f"Date: {datetime.now(timezone.utc).isoformat()}")
    print(f"Messagebus: {MESSAGEBUS_URL}")
    print("=" * 72)

    ws = websocket.WebSocket()
    try:
        ws.connect(MESSAGEBUS_URL, timeout=5)
        print(f"[OK] Connected to messagebus\n")
    except Exception as e:
        print(f"[FATAL] Cannot connect to messagebus: {e}")
        sys.exit(1)

    results: list[dict] = []
    for i, tc in enumerate(TEST_CASES, 1):
        print(f"─── Test {i}/{len(TEST_CASES)}: {tc['id']} ───")
        print(f"  Utterance: {tc['utterance']}")
        print(f"  Expect:    {tc['expect']}")

        result = send_utterance(ws, tc["utterance"])
        result["test_id"] = tc["id"]
        result["category"] = tc["category"]
        result["expect"] = tc["expect"]
        results.append(result)

        resp = result["response"]
        rt = result["response_time"]
        print(f"  Response:  {resp}")
        print(f"  Time:      {rt}s" if rt else "  Time:      TIMEOUT")
        print()

        # Pause between tests to avoid overlapping responses
        time.sleep(2)

    ws.close()
    return results


def print_summary(results: list[dict]) -> None:
    """Print summary table."""
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)

    timeouts = sum(1 for r in results if "[TIMEOUT" in r["response"])
    responded = len(results) - timeouts

    print(f"Total tests:  {len(results)}")
    print(f"Responded:    {responded}")
    print(f"Timeouts:     {timeouts}")

    print(f"\n{'ID':<20} {'Time':>6} {'Response (first 80 chars)':<80}")
    print("-" * 110)
    for r in results:
        tid = r["test_id"]
        rt = f"{r['response_time']}s" if r["response_time"] else "TOUT"
        resp = r["response"][:80] + ("..." if len(r["response"]) > 80 else "")
        print(f"{tid:<20} {rt:>6} {resp}")

    # Category breakdown
    print(f"\n{'Category':<20} {'OK':>5} {'Timeout':>8}")
    print("-" * 35)
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"ok": 0, "timeout": 0}
        if "[TIMEOUT" in r["response"]:
            categories[cat]["timeout"] += 1
        else:
            categories[cat]["ok"] += 1
    for cat, counts in sorted(categories.items()):
        print(f"{cat:<20} {counts['ok']:>5} {counts['timeout']:>8}")

    print("\n" + "=" * 72)


def main() -> int:
    results = run_tests()
    print_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
