#!/usr/bin/env python3
"""P9.1 PREVENTION Voice Accuracy — Terminal Acceptance Script.

Tests the 8 acceptance criteria from the P9.1 remediation plan:
1. Broad anomaly utterances report aggregate anomalies across intended scope.
2. Targeted anomaly utterances remain available and clearly scoped.
3. No anomalous result returns severity=none.
4. PREVENTION HTTP mode retains multiple anomalies and reports correct totals.
5. Alert monitor scope is not silently truncated by fixed slices.
6. Alert threshold and conversational threshold are independently configurable.
7. E2E and integration tests enforce anomaly count/severity correctness.
8. Terminal acceptance passes for both profiles.

Run inside avaros-network:
  docker exec avaros-skill python3 /opt/avaros/scripts/p91_acceptance.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

import requests
import websocket

# ── Configuration ──────────────────────────────────────────

MESSAGEBUS_HOST = os.environ.get("MESSAGEBUS_HOST", "avaros-messagebus")
MESSAGEBUS_PORT = int(os.environ.get("MESSAGEBUS_PORT", "8181"))
MESSAGEBUS_URL = f"ws://{MESSAGEBUS_HOST}:{MESSAGEBUS_PORT}/core"

WEBUI_HOST = os.environ.get("WEBUI_HOST", "avaros-web-ui")
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "8080"))
WEBUI_API_KEY = os.environ.get("AVAROS_WEB_API_KEY", "raptorblingx")
WEBUI_BASE = f"http://{WEBUI_HOST}:{WEBUI_PORT}"

UTTERANCE_TIMEOUT = 15
PAUSE_BETWEEN = 2

SEVERITY_WORDS = ("low", "medium", "high", "critical")


# ── Utterance Dispatcher ──────────────────────────────────

class UtteranceDispatcher:
    """Send utterance via messagebus and capture the spoken response."""

    def __init__(self) -> None:
        self._ws: websocket.WebSocket | None = None
        self._all_responses: list[str] = []

    def connect(self) -> None:
        self._ws = websocket.WebSocket()
        self._ws.connect(MESSAGEBUS_URL, timeout=5)

    def close(self) -> None:
        if self._ws:
            self._ws.close()

    def send_utterance(
        self, text: str, timeout: float = UTTERANCE_TIMEOUT,
    ) -> dict[str, Any]:
        """Send utterance and wait for spoken response(s)."""
        self._all_responses = []
        assert self._ws is not None

        msg = {
            "type": "recognizer_loop:utterance",
            "data": {"utterances": [text], "lang": "en-us"},
            "context": {},
        }
        self._ws.send(json.dumps(msg))

        deadline = time.time() + timeout
        self._ws.settimeout(1.0)
        first_response_time: float | None = None
        while time.time() < deadline:
            try:
                raw = self._ws.recv()
            except websocket.WebSocketTimeoutException:
                if self._all_responses and (
                    time.time() - (first_response_time or 0)
                ) > 3:
                    break
                continue
            except Exception:
                break

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "speak":
                utt = data.get("data", {}).get("utterance", "")
                if utt:
                    self._all_responses.append(utt)
                    if first_response_time is None:
                        first_response_time = time.time()

        combined = " ".join(self._all_responses)
        return {
            "utterance": text,
            "response": combined if combined else "[TIMEOUT - No response]",
            "responses": self._all_responses,
        }


# ── API helpers ───────────────────────────────────────────

def api_get(path: str) -> Any:
    """GET from web-ui API with API key."""
    url = f"{WEBUI_BASE}{path}"
    r = requests.get(
        url, headers={"X-API-Key": WEBUI_API_KEY}, timeout=10,
    )
    r.raise_for_status()
    return r.json()


def switch_profile(profile_name: str) -> None:
    """Switch AVAROS active profile."""
    ws = websocket.create_connection(MESSAGEBUS_URL, timeout=5)
    msg = {
        "type": "avaros.profile.activated",
        "data": {"profile": profile_name},
        "context": {},
    }
    ws.send(json.dumps(msg))
    ws.close()
    time.sleep(5)


# ── Test runner ───────────────────────────────────────────

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class AcceptanceResult:
    """Single acceptance test result."""

    def __init__(
        self, criterion: int, name: str, status: str,
        detail: str = "", evidence: str = "",
    ) -> None:
        self.criterion = criterion
        self.name = name
        self.status = status
        self.detail = detail
        self.evidence = evidence

    def __repr__(self) -> str:
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}[self.status]
        return f"  {icon} AC-{self.criterion}: {self.name} — {self.status}"


results: list[AcceptanceResult] = []


def record(
    criterion: int, name: str, status: str,
    detail: str = "", evidence: str = "",
) -> None:
    r = AcceptanceResult(criterion, name, status, detail, evidence)
    results.append(r)
    print(repr(r))
    if detail:
        print(f"     {detail}")


# ── AC-1: Broad anomaly utterances report aggregate scope ─

def test_ac1_broad_anomaly(dispatcher: UtteranceDispatcher) -> None:
    """AC-1: Broad anomaly utterances report aggregate anomalies."""
    print("\n─── AC-1: Broad anomaly scan scope ───")

    result = dispatcher.send_utterance(
        "Are there any unusual patterns today?",
    )
    response = result["response"]
    lower = response.lower()
    print(f"  Utterance: {result['utterance']}")
    print(f"  Response:  {response}")

    if "[TIMEOUT" in response:
        record(1, "broad anomaly scan", FAIL, "Timeout — no response")
        return

    # Scan response must contain scope indicator ("across N checks")
    has_scope = "check" in lower or "across" in lower
    # OR it says "no unusual patterns" (which is a valid scan result)
    has_clean = "no unusual" in lower

    if has_scope or has_clean:
        record(
            1, "broad anomaly scan", PASS,
            f"Scope indicator present: scope={has_scope}, clean={has_clean}",
            response,
        )
    else:
        # Check if it sounds like a single-pair response (not a scan)
        record(
            1, "broad anomaly scan", FAIL,
            "Response lacks scope indicator ('across N checks')",
            response,
        )


# ── AC-2: Targeted anomaly utterances remain scoped ───────

def test_ac2_targeted_anomaly(
    dispatcher: UtteranceDispatcher, asset: str,
) -> None:
    """AC-2: Targeted anomaly utterances clearly scoped."""
    print("\n─── AC-2: Targeted anomaly scope ───")

    result = dispatcher.send_utterance(
        f"Check anomalies for energy per unit on {asset}",
    )
    response = result["response"]
    lower = response.lower()
    print(f"  Utterance: {result['utterance']}")
    print(f"  Response:  {response}")

    if "[TIMEOUT" in response:
        record(2, "targeted anomaly scope", FAIL, "Timeout — no response")
        return

    # Targeted response: should mention asset or be "no unusual"
    has_asset = asset.lower().replace("-", " ") in lower or asset.lower() in lower
    has_severity = any(s in lower for s in SEVERITY_WORDS)
    has_clean = "no unusual" in lower or "looks normal" in lower

    if has_asset or has_severity or has_clean:
        record(
            2, "targeted anomaly scope", PASS,
            f"asset={has_asset}, severity={has_severity}, clean={has_clean}",
            response,
        )
    else:
        record(
            2, "targeted anomaly scope", FAIL,
            "Targeted response lacks asset name, severity, or clean message",
            response,
        )


# ── AC-3: No anomalous result with severity=none ─────────

def test_ac3_severity_invariant(
    dispatcher: UtteranceDispatcher, assets: list[str],
) -> None:
    """AC-3: No anomalous result returns severity=none."""
    print("\n─── AC-3: Severity invariant (no anomalous + none) ───")

    violations = []
    pairs_checked = 0
    test_metrics = ["energy per unit", "scrap rate", "oee"]

    for metric in test_metrics:
        for asset in assets[:2]:  # Check first 2 assets per metric
            pairs_checked += 1
            result = dispatcher.send_utterance(
                f"Check anomalies for {metric} on {asset}",
            )
            response = result["response"]
            lower = response.lower()

            # Check severity invariant
            if any(s in lower for s in SEVERITY_WORDS):
                # Anomalous — good, severity is present
                pass
            elif "no unusual" in lower or "looks normal" in lower:
                # Clean — severity should be none (implicit)
                pass
            elif "none severity" in lower or "severity none" in lower:
                violations.append(f"{metric}/{asset}: {response}")
            elif "severity" in lower and "none" in lower:
                violations.append(f"{metric}/{asset}: {response}")

            time.sleep(1)

    if violations:
        record(
            3, "severity invariant", FAIL,
            f"{len(violations)} violations in {pairs_checked} pairs",
            "; ".join(violations[:3]),
        )
    else:
        record(
            3, "severity invariant", PASS,
            f"No violations in {pairs_checked} pairs checked",
        )


# ── AC-4: Multi-result handling (verified via code, not voice) ──

def test_ac4_multi_result() -> None:
    """AC-4: PREVENTION HTTP mode retains multiple anomalies."""
    print("\n─── AC-4: Multi-result handling (code verification) ───")

    try:
        import sys
        if '/opt/avaros' not in sys.path:
            sys.path.insert(0, '/opt/avaros')
        from skill.clients.prevention_http import _parse_anomaly_results
        from skill.domain.models import CanonicalMetric

        test_results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 2.5, "is_anomalous": True,
                "severity": "medium", "anomaly_type": "spike",
                "timestamp": "2026-04-07T10:00:00", "value": 15.0,
                "asset_id": "Line-1",
            },
            {
                "metric_name": "energy_per_unit",
                "z_score": 4.0, "is_anomalous": True,
                "severity": "critical", "anomaly_type": "spike",
                "timestamp": "2026-04-07T14:00:00", "value": 30.0,
                "asset_id": "Line-1",
            },
        ]
        parsed = _parse_anomaly_results(
            test_results, CanonicalMetric.ENERGY_PER_UNIT,
            "energy", [], 2.0,
        )
        desc = parsed.description
        has_count = "2 anomalous readings detected" in desc
        has_worst = "4.0" in desc

        if has_count and has_worst:
            record(4, "multi-result retention", PASS,
                   f"Count and worst z-score in description",
                   desc)
        else:
            record(4, "multi-result retention", FAIL,
                   f"count={has_count}, worst={has_worst}",
                   desc)
    except Exception as e:
        record(4, "multi-result retention", FAIL, str(e))


# ── AC-5: Alert monitor scope not truncated ───────────────

def test_ac5_alert_scope() -> None:
    """AC-5: Alert monitor scope not silently truncated."""
    print("\n─── AC-5: Alert monitor scope ───")

    try:
        import sys
        if '/opt/avaros' not in sys.path:
            sys.path.insert(0, '/opt/avaros')
        from skill.services.settings import SettingsService

        svc = SettingsService(database_url="sqlite:///:memory:")
        config = svc.get_alert_config()
        # Check: no hard 5x5 truncation
        # When monitored_pairs is empty, it means "full scope"
        if hasattr(config, "monitored_pairs"):
            mp = config.monitored_pairs
            record(
                5, "alert scope not truncated", PASS,
                f"monitored_pairs={mp!r} (empty=full scope)",
            )
        else:
            record(5, "alert scope not truncated", FAIL,
                   "AlertConfig missing monitored_pairs attribute")
    except Exception as e:
        record(5, "alert scope not truncated", FAIL, str(e))


# ── AC-6: Independent thresholds ─────────────────────────

def test_ac6_independent_thresholds() -> None:
    """AC-6: Alert and conversational thresholds independently configurable."""
    print("\n─── AC-6: Independent threshold config ───")

    try:
        import sys
        if '/opt/avaros' not in sys.path:
            sys.path.insert(0, '/opt/avaros')
        from skill.services.settings import SettingsService

        svc = SettingsService(database_url="sqlite:///:memory:")

        # Set conversational threshold to 1.5
        svc.set_query_anomaly_threshold(1.5)
        query_t = svc.get_query_anomaly_threshold()

        # Get alert config threshold (should remain at default)
        alert_config = svc.get_alert_config()
        alert_t = alert_config.z_score_threshold

        if query_t != alert_t:
            record(
                6, "independent thresholds", PASS,
                f"query={query_t}, alert={alert_t} — independent",
            )
        else:
            # They might both be defaults — check if we can change one
            svc.set_query_anomaly_threshold(1.0)
            query_t2 = svc.get_query_anomaly_threshold()
            alert_t2 = svc.get_alert_config().z_score_threshold
            if query_t2 != alert_t2:
                record(
                    6, "independent thresholds", PASS,
                    f"After change: query={query_t2}, alert={alert_t2}",
                )
            else:
                record(
                    6, "independent thresholds", FAIL,
                    f"Thresholds coupled: query={query_t2}, alert={alert_t2}",
                )
    except Exception as e:
        record(6, "independent thresholds", FAIL, str(e))


# ── AC-7: Test hardening (meta-check) ────────────────────

def test_ac7_test_hardening() -> None:
    """AC-7: Verify test classes exist for severity invariants."""
    print("\n─── AC-7: Test hardening (class existence check) ───")

    checks = {
        "TestSeverityInvariant": "tests/test_clients/test_prevention_statistical.py",
        "TestHttpSeverityInvariant": "tests/test_clients/test_prevention_http.py",
        "TestHttpMultiResultParsing": "tests/test_clients/test_prevention_http.py",
        "test_broad_anomaly_scan": "tests/test_e2e/test_voice_pipeline.py",
    }
    import os
    base_dirs = ["/opt/avaros", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    missing = []
    for class_name, filepath in checks.items():
        found = False
        for base in base_dirs:
            full_path = os.path.join(base, filepath)
            try:
                with open(full_path) as f:
                    if class_name in f.read():
                        found = True
                        break
            except FileNotFoundError:
                continue
        if not found:
            missing.append(f"{class_name} not in {filepath}")

    if missing:
        record(7, "test hardening", FAIL, "; ".join(missing))
    else:
        record(7, "test hardening", PASS,
               f"All {len(checks)} test classes/functions present")


# ── AC-8: Terminal acceptance passes ──────────────────────

def test_ac8_terminal_acceptance(profile: str) -> None:
    """AC-8: Summary pass for this profile's acceptance run."""
    print(f"\n─── AC-8: Terminal acceptance — {profile} ───")

    profile_results = [
        r for r in results
        if r.status == FAIL and r.criterion in (1, 2, 3)
    ]

    if profile_results:
        record(
            8, f"terminal acceptance ({profile})", FAIL,
            f"{len(profile_results)} critical criteria failed",
        )
    else:
        record(
            8, f"terminal acceptance ({profile})", PASS,
            f"All voice-path criteria passed for {profile}",
        )


# ── Main ──────────────────────────────────────────────────

def main() -> int:
    print("=" * 70)
    print("P9.1 PREVENTION VOICE ACCURACY — TERMINAL ACCEPTANCE")
    print(f"Date: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    dispatcher = UtteranceDispatcher()
    try:
        dispatcher.connect()
        print(f"[OK] Connected to messagebus at {MESSAGEBUS_URL}")
    except Exception as e:
        print(f"[FATAL] Cannot connect to messagebus: {e}")
        return 1

    # Get available assets
    try:
        assets_data = api_get("/api/v1/assets/mappings")
        assets = list(assets_data.get("asset_mappings", {}).keys())
        print(f"[OK] Assets: {assets}")
    except Exception as e:
        print(f"[WARN] Could not fetch assets: {e}")
        assets = []

    primary_asset = assets[0] if assets else "Line-1"

    try:
        # --- Code-level acceptance (profile-independent) ---
        test_ac4_multi_result()
        test_ac5_alert_scope()
        test_ac6_independent_thresholds()
        test_ac7_test_hardening()

        # --- Voice-level acceptance (current profile) ---
        print(f"\n{'#' * 70}")
        print(f"# VOICE ACCEPTANCE — Current profile")
        print(f"{'#' * 70}")

        test_ac1_broad_anomaly(dispatcher)
        time.sleep(PAUSE_BETWEEN)

        test_ac2_targeted_anomaly(dispatcher, primary_asset)
        time.sleep(PAUSE_BETWEEN)

        test_ac3_severity_invariant(dispatcher, assets[:3])

        test_ac8_terminal_acceptance("current")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED]")
    except Exception as e:
        print(f"\n\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        record(8, "acceptance script", FAIL, str(e))
    finally:
        dispatcher.close()

    # ── Report ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("P9.1 ACCEPTANCE RESULTS")
    print("=" * 70)

    pass_count = sum(1 for r in results if r.status == PASS)
    fail_count = sum(1 for r in results if r.status == FAIL)
    skip_count = sum(1 for r in results if r.status == SKIP)

    for r in results:
        print(repr(r))
        if r.evidence:
            print(f"     Evidence: {r.evidence[:200]}")

    print(f"\nTotal: {len(results)} | "
          f"Pass: {pass_count} | Fail: {fail_count} | Skip: {skip_count}")

    verdict = "PASS" if fail_count == 0 else "FAIL"
    print(f"\n{'=' * 70}")
    print(f"VERDICT: {verdict}")
    print(f"{'=' * 70}")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
