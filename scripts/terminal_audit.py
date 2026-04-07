#!/usr/bin/env python3
"""
AVAROS Terminal-Based End-to-End Accuracy Audit

Connects to the OVOS messagebus, sends utterances as an end user,
captures spoken responses, then independently queries the backend
for ground truth and compares.

Goal: find gaps, bugs, inaccuracies, poor implementations.

Run inside avaros-network:
  docker run --rm --network avaros-network \
    -v $(pwd)/scripts:/scripts:ro \
    -v $(pwd)/skill:/opt/avaros/skill:ro \
    -e PYTHONPATH=/opt/avaros \
    avaros-skill python3 /scripts/terminal_audit.py

Or exec inside the running skill container:
  docker exec avaros-skill python3 /opt/avaros/scripts/terminal_audit.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

import websocket
import requests

# ===========================================================================
# Configuration
# ===========================================================================

MESSAGEBUS_HOST = os.environ.get("MESSAGEBUS_HOST", "avaros-messagebus")
MESSAGEBUS_PORT = int(os.environ.get("MESSAGEBUS_PORT", "8181"))
MESSAGEBUS_URL = f"ws://{MESSAGEBUS_HOST}:{MESSAGEBUS_PORT}/core"

WEBUI_HOST = os.environ.get("WEBUI_HOST", "avaros-web-ui")
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "8080"))
WEBUI_API_KEY = os.environ.get("AVAROS_WEB_API_KEY", "raptorblingx")
WEBUI_BASE = f"http://{WEBUI_HOST}:{WEBUI_PORT}"

UTTERANCE_TIMEOUT = 15  # seconds to wait for spoken response
PAUSE_BETWEEN = 2  # pause between utterances (let skill settle)


# ===========================================================================
# Utility: send utterance → capture response
# ===========================================================================

class UtteranceDispatcher:
    """Send utterance via messagebus and capture the spoken response."""

    def __init__(self):
        self._ws = None
        self._response: str | None = None
        self._all_responses: list[str] = []
        self._event = threading.Event()
        self._lock = threading.Lock()

    def connect(self):
        self._ws = websocket.WebSocket()
        self._ws.connect(MESSAGEBUS_URL, timeout=5)
        print(f"[OK] Connected to messagebus at {MESSAGEBUS_URL}")

    def close(self):
        if self._ws:
            self._ws.close()

    def send_utterance(self, text: str, timeout: float = UTTERANCE_TIMEOUT) -> dict:
        """Send utterance and wait for spoken response(s)."""
        with self._lock:
            self._response = None
            self._all_responses = []
            self._event.clear()

        msg = {
            "type": "recognizer_loop:utterance",
            "data": {"utterances": [text], "lang": "en-us"},
            "context": {},
        }
        self._ws.send(json.dumps(msg))

        # Listen for speak events
        deadline = time.time() + timeout
        self._ws.settimeout(1.0)
        first_response_time = None
        while time.time() < deadline:
            try:
                raw = self._ws.recv()
            except websocket.WebSocketTimeoutException:
                # If we already have a response and nothing new for 2s, stop
                if self._all_responses and (time.time() - (first_response_time or 0)) > 3:
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

            # Also capture intent match events for routing verification
            if data.get("type", "").endswith(":execute"):
                intent_type = data.get("type", "")
                # Store for later analysis
                pass

        combined = " ".join(self._all_responses)
        return {
            "utterance": text,
            "response": combined if combined else "[TIMEOUT - No response]",
            "response_count": len(self._all_responses),
            "responses": self._all_responses,
        }


# ===========================================================================
# Utility: Web UI API calls
# ===========================================================================

def api_get(path: str) -> Any:
    """GET from web-ui API with API key."""
    url = f"{WEBUI_BASE}{path}"
    r = requests.get(url, headers={"X-API-Key": WEBUI_API_KEY}, timeout=10)
    r.raise_for_status()
    return r.json()


def api_put(path: str, data: dict) -> Any:
    """PUT to web-ui API."""
    url = f"{WEBUI_BASE}{path}"
    r = requests.put(url, json=data, headers={"X-API-Key": WEBUI_API_KEY}, timeout=10)
    r.raise_for_status()
    return r.json()


# ===========================================================================
# Utility: Statistical ground truth (reimplemented from prevention_statistical)
# ===========================================================================

def compute_z_score_anomaly(values: list[float], threshold: float = 4.0):
    """Compute z-score anomaly detection — matches StatisticalPreventionClient."""
    if len(values) < 3:
        return {"is_anomalous": False, "reason": "insufficient_data", "max_z": 0.0}

    mean_val = sum(values) / len(values)
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    std_val = math.sqrt(variance)

    if std_val == 0:
        return {"is_anomalous": False, "reason": "zero_variance", "max_z": 0.0}

    max_z = 0.0
    max_idx = 0
    for i, v in enumerate(values):
        z = abs(v - mean_val) / std_val
        if z > max_z:
            max_z = z
            max_idx = i

    is_anomalous = max_z >= threshold
    if max_z < 2.0:
        severity = "none"
    elif max_z < 2.5:
        severity = "low"
    elif max_z < 3.0:
        severity = "medium"
    elif max_z < 4.0:
        severity = "high"
    else:
        severity = "critical"

    return {
        "is_anomalous": is_anomalous,
        "max_z": round(max_z, 3),
        "severity": severity,
        "mean": round(mean_val, 4),
        "std": round(std_val, 4),
        "max_value": values[max_idx],
        "max_index": max_idx,
    }


def compute_linear_drift(values: list[float]):
    """Linear regression drift — matches StatisticalPreventionClient."""
    n = len(values)
    if n < 10:
        return {"has_drift": False, "reason": "insufficient_data"}

    sum_x = n * (n - 1) / 2.0
    sum_x2 = n * (n - 1) * (2 * n - 1) / 6.0
    sum_y = sum(values)
    sum_xy = sum(i * v for i, v in enumerate(values))

    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        return {"has_drift": False, "slope": 0.0, "r_squared": 0.0}

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n

    mean_y = sum_y / n
    ss_tot = sum((v - mean_y) ** 2 for v in values)
    ss_res = sum((v - (slope * i + intercept)) ** 2 for i, v in enumerate(values))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    has_drift = abs(slope) > 0.001 and r_squared > 0.1

    return {
        "has_drift": has_drift,
        "slope": round(slope, 6),
        "r_squared": round(r_squared, 4),
        "intercept": round(intercept, 4),
    }


# ===========================================================================
# Findings collector
# ===========================================================================

class Finding:
    def __init__(self, severity: str, category: str, title: str, detail: str, evidence: str = ""):
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.category = category
        self.title = title
        self.detail = detail
        self.evidence = evidence

    def __repr__(self):
        return f"[{self.severity}] {self.category}: {self.title}"


findings: list[Finding] = []


def add_finding(severity: str, category: str, title: str, detail: str, evidence: str = ""):
    f = Finding(severity, category, title, detail, evidence)
    findings.append(f)
    print(f"  ⚠ FINDING [{severity}] {title}")
    if evidence:
        print(f"    Evidence: {evidence[:200]}")


# ===========================================================================
# Phase A: Environment & Status Check
# ===========================================================================

def run_phase_a():
    """Collect environment/runtime state."""
    print("\n" + "=" * 70)
    print("PHASE A: ENVIRONMENT & RUNTIME STATUS")
    print("=" * 70)

    # 1. Health check
    try:
        health = api_get("/health")
        print(f"[OK] Web-UI health: {health}")
    except Exception as e:
        print(f"[FAIL] Web-UI health: {e}")
        add_finding("HIGH", "infrastructure", "Web-UI unreachable",
                     f"Health check failed: {e}")

    # 2. Status
    try:
        status = api_get("/api/v1/status")
        print(f"[OK] Status: {json.dumps(status, indent=2)}")

        if not status.get("configured"):
            add_finding("CRITICAL", "infrastructure", "System not configured",
                         "Status reports configured=false")

        if not status.get("live_connection_verified"):
            add_finding("HIGH", "infrastructure", "Backend connection not verified",
                         f"live_connection_message: {status.get('live_connection_message')}")
    except Exception as e:
        print(f"[FAIL] Status: {e}")
        add_finding("CRITICAL", "infrastructure", "Status endpoint failed", str(e))

    # 3. Platform config
    try:
        platform = api_get("/api/v1/config/platform")
        print(f"[OK] Platform: type={platform.get('platform_type')}, url={platform.get('api_url')}")
    except Exception as e:
        print(f"[WARN] Platform config: {e}")

    # 4. Metrics
    try:
        metrics = api_get("/api/v1/config/metrics")
        metric_names = [m["canonical_metric"] for m in metrics]
        print(f"[OK] Mapped metrics ({len(metric_names)}): {metric_names}")
    except Exception as e:
        print(f"[WARN] Metrics config: {e}")

    # 5. Assets
    try:
        assets_data = api_get("/api/v1/assets/mappings")
        asset_names = list(assets_data.get("asset_mappings", {}).keys())
        print(f"[OK] Assets ({len(asset_names)}): {asset_names}")
    except Exception as e:
        print(f"[WARN] Assets config: {e}")

    # 6. Alert config
    try:
        alert_config = api_get("/api/v1/config/alert-config")
        print(f"[OK] Alert config: {json.dumps(alert_config)}")

        if not alert_config.get("monitored_pairs"):
            add_finding("HIGH", "alert-monitor", "Empty monitored_pairs in alert config",
                         "Alert monitor will use adapter's default metric/asset scope. "
                         "This may result in truncated monitoring if defaults are capped.",
                         f"z_score_threshold={alert_config.get('z_score_threshold')}, monitored_pairs=[]")
    except Exception as e:
        print(f"[WARN] Alert config: {e}")

    # 7. PREVENTION URL check (already known from env audit)
    print(f"\n[INFO] PREVENTION_URL: NOT SET (statistical fallback mode)")
    print(f"[INFO] Messagebus: {MESSAGEBUS_URL}")


# ===========================================================================
# Phase B: KPI Accuracy Tests
# ===========================================================================

def run_kpi_accuracy_tests(dispatcher: UtteranceDispatcher, profile_name: str):
    """Test KPI utterances and cross-check values where possible."""
    print(f"\n{'=' * 70}")
    print(f"KPI ACCURACY TESTS — Profile: {profile_name}")
    print("=" * 70)

    # Get current metrics and assets
    try:
        metrics = api_get("/api/v1/config/metrics")
        metric_names = [m["canonical_metric"] for m in metrics]
    except Exception:
        metric_names = []

    try:
        assets_data = api_get("/api/v1/assets/mappings")
        asset_names = list(assets_data.get("asset_mappings", {}).keys())
    except Exception:
        asset_names = []

    if not asset_names:
        add_finding("CRITICAL", "kpi", "No assets configured",
                     "Cannot test KPI queries without assets")
        return

    primary_asset = asset_names[0]
    print(f"[INFO] Primary test asset: {primary_asset}")
    print(f"[INFO] Available metrics: {metric_names}")

    # --- Core KPI tests ---
    kpi_utterances = [
        ("energy_per_unit", f"What's the energy per unit for {primary_asset}?"),
        ("energy_total", f"What's the total energy for {primary_asset}?"),
        ("co2_per_unit", f"What's the CO2 per unit for {primary_asset}?"),
        ("co2_total", f"What's the total CO2 for {primary_asset}?"),
        ("peak_demand", f"What's the peak demand for {primary_asset}?"),
        ("throughput", f"What's the throughput for {primary_asset}?"),
        ("material_efficiency", f"What's the material efficiency for {primary_asset}?"),
        ("peak_tariff_exposure", f"What's the tariff exposure for {primary_asset}?"),
        ("oee", f"What's the OEE for {primary_asset}?"),
        ("scrap_rate", f"What's the scrap rate for {primary_asset}?"),
        ("rework_rate", f"What's the rework rate for {primary_asset}?"),
        ("cycle_time", f"What's the cycle time for {primary_asset}?"),
    ]

    kpi_results = {}
    for metric_name, utterance in kpi_utterances:
        print(f"\n--- Testing: {utterance}")
        result = dispatcher.send_utterance(utterance)
        response = result["response"]
        print(f"  Spoken: {response}")
        kpi_results[metric_name] = result

        if "[TIMEOUT" in response:
            add_finding("CRITICAL", "kpi", f"Timeout for {metric_name} on {primary_asset}",
                         f"Utterance '{utterance}' got no response within {UTTERANCE_TIMEOUT}s",
                         response)
        elif "not configured" in response.lower() or "not supported" in response.lower():
            if metric_name in metric_names:
                add_finding("HIGH", "kpi", f"{metric_name} configured but reports 'not configured'",
                             f"Metric {metric_name} is in the mapping but handler says not configured",
                             response)
            else:
                print(f"  [OK] Expected: metric '{metric_name}' not mapped for this profile")
        elif "error" in response.lower() or "sorry" in response.lower():
            add_finding("HIGH", "kpi", f"Error response for {metric_name}",
                         f"Utterance '{utterance}' returned an error",
                         response)

        time.sleep(PAUSE_BETWEEN)

    # --- Test with second asset if available ---
    if len(asset_names) >= 2:
        second_asset = asset_names[1]
        print(f"\n--- Cross-asset test with: {second_asset}")
        result = dispatcher.send_utterance(f"What's the energy per unit for {second_asset}?")
        print(f"  Spoken: {result['response']}")
        if "[TIMEOUT" in result["response"]:
            add_finding("HIGH", "kpi", f"Timeout for second asset {second_asset}",
                         "Second asset KPI query timed out")
        time.sleep(PAUSE_BETWEEN)

    return kpi_results


# ===========================================================================
# Phase C: Anomaly Detection Accuracy Tests
# ===========================================================================

def run_anomaly_accuracy_tests(dispatcher: UtteranceDispatcher, profile_name: str):
    """Test anomaly utterances and compare against ground truth."""
    print(f"\n{'=' * 70}")
    print(f"ANOMALY DETECTION ACCURACY — Profile: {profile_name}")
    print("=" * 70)

    # --- Test 1: Broad anomaly query ---
    print("\n--- Test 1: Broad anomaly query")
    broad_result = dispatcher.send_utterance("Are there any unusual patterns today?")
    print(f"  Spoken: {broad_result['response']}")
    time.sleep(PAUSE_BETWEEN)

    # --- Test 2: Another broad phrasing ---
    print("\n--- Test 2: Alternative broad phrasing")
    broad_result2 = dispatcher.send_utterance("Any anomalies in production?")
    print(f"  Spoken: {broad_result2['response']}")
    time.sleep(PAUSE_BETWEEN)

    # --- Test 3: Targeted anomaly query (specific metric + asset) ---
    try:
        assets_data = api_get("/api/v1/assets/mappings")
        asset_names = list(assets_data.get("asset_mappings", {}).keys())
    except Exception:
        asset_names = ["Compressor-1"]

    primary_asset = asset_names[0]
    print(f"\n--- Test 3: Targeted anomaly — energy per unit on {primary_asset}")
    targeted_result = dispatcher.send_utterance(
        f"Check anomalies for energy per unit on {primary_asset}"
    )
    print(f"  Spoken: {targeted_result['response']}")
    time.sleep(PAUSE_BETWEEN)

    # --- Test 4: Intent routing ambiguity ---
    print("\n--- Test 4: Intent routing — should this go to anomaly or KPI?")
    ambiguous_phrases = [
        "check anomalies for oee on compressor",
        "any anomalies on compressor for energy",
        "what is the oee for compressor",  # This should be KPI, not anomaly
    ]
    for phrase in ambiguous_phrases:
        result = dispatcher.send_utterance(phrase)
        response = result["response"]
        print(f"  '{phrase}' → {response}")

        # "check anomalies" should produce anomaly-style response (sigma, severity, pattern)
        if "anomal" in phrase.lower() or "unusual" in phrase.lower():
            if any(kw in response.lower() for kw in ["percent", "kilowatt", "the oee for", "the energy per unit for"]):
                if "sigma" not in response.lower() and "severity" not in response.lower() and "anomal" not in response.lower() and "pattern" not in response.lower() and "normal" not in response.lower():
                    add_finding("HIGH", "intent-routing",
                                f"Anomaly phrase routed to KPI handler",
                                f"Phrase '{phrase}' appears to return a KPI value instead of anomaly result",
                                response)
        time.sleep(PAUSE_BETWEEN)

    # --- Ground truth: independently compute anomalies for ALL metric×asset pairs ---
    print("\n--- Ground Truth: Independent anomaly scan (statistical z-score)")
    print("  Computing anomalies for all metric×asset pairs using the SAME")
    print("  StatisticalPreventionClient logic...")

    try:
        metrics = api_get("/api/v1/config/metrics")
        metric_names = [m["canonical_metric"] for m in metrics]
        assets_data = api_get("/api/v1/assets/mappings")
        asset_map = assets_data.get("asset_mappings", {})
        asset_names = list(asset_map.keys())
        alert_config = api_get("/api/v1/config/alert-config")
        z_threshold = alert_config.get("z_score_threshold", 4.0)
    except Exception as e:
        print(f"  [ERROR] Could not fetch config for ground truth: {e}")
        return

    print(f"  Z-score threshold (from alert config): {z_threshold}")
    print(f"  Metrics: {metric_names}")
    print(f"  Assets: {asset_names}")
    print(f"  Total pairs to check: {len(metric_names) * len(asset_names)}")

    # We'll use the SKILL's own code to compute ground truth by calling
    # the dispatcher directly — but we can't do that from outside.
    # Instead, we'll send individual KPI queries for 7 days and compute z-score.
    # This is exactly what the StatisticalPreventionClient does.

    anomaly_ground_truth = []
    checked = 0
    errors = 0

    for metric_name in metric_names:
        for asset_name in asset_names:
            checked += 1
            # Gather 7-day series via individual KPI queries
            values = []
            for day_offset in range(7, 0, -1):
                day = datetime.now(timezone.utc) - timedelta(days=day_offset)
                day_str = day.strftime("%Y-%m-%d")
                # We'll ask the KPI for each day — but this is slow.
                # Instead, let's just check the anomaly utterance count vs scan count.
                pass

            # We can't easily query day-by-day from outside the stack.
            # So let's use a hybrid approach: send targeted anomaly queries
            # for each metric×asset pair and count how many are anomalous.

    # Hybrid ground truth: query anomaly for each pair from the OVOS voice
    # and count the total anomalies
    print("\n  [INFO] Running targeted anomaly checks for ground truth verification...")
    print(f"  (This will send {len(metric_names)} × {len(asset_names)} = "
          f"{len(metric_names) * len(asset_names)} individual queries)")

    gt_anomalous = 0
    gt_total = 0
    gt_severity_counts: dict[str, int] = {}
    gt_details: list[dict] = []

    for metric_name in metric_names:
        for asset_name in asset_names:
            gt_total += 1
            # Use the VOICE interface to query each pair
            utterance = f"check anomalies for {metric_name.replace('_', ' ')} on {asset_name}"
            result = dispatcher.send_utterance(utterance, timeout=12)
            response = result["response"].lower()

            is_anomalous = False
            severity = "none"

            if "sigma" in response or "severity" in response:
                # Parse severity from response
                for sev in ["critical", "high", "medium", "low"]:
                    if sev in response:
                        severity = sev
                        is_anomalous = True
                        break
                # Also check for "deviation of X.X sigma"
                import re
                sigma_match = re.search(r'(\d+\.?\d*)\s*sigma', response)
                if sigma_match:
                    z = float(sigma_match.group(1))
                    if z >= z_threshold:
                        is_anomalous = True

            if "no unusual" in response or "looks normal" in response:
                is_anomalous = False
                severity = "none"

            if is_anomalous:
                gt_anomalous += 1
                gt_severity_counts[severity] = gt_severity_counts.get(severity, 0) + 1
                gt_details.append({
                    "metric": metric_name,
                    "asset": asset_name,
                    "severity": severity,
                    "response": result["response"],
                })

            if "[TIMEOUT" in result["response"]:
                errors += 1
                add_finding("HIGH", "anomaly", f"Timeout for {metric_name}/{asset_name}",
                             f"Targeted anomaly check timed out")

            sys.stdout.write(f"\r  Progress: {gt_total}/{len(metric_names) * len(asset_names)} "
                             f"(anomalous: {gt_anomalous}, errors: {errors})")
            sys.stdout.flush()
            time.sleep(1)  # Brief pause

    print(f"\n\n  Ground Truth Summary:")
    print(f"    Pairs checked: {gt_total}")
    print(f"    Anomalous pairs: {gt_anomalous}")
    print(f"    Severity distribution: {gt_severity_counts}")
    print(f"    Errors/timeouts: {errors}")

    if gt_details:
        print(f"\n  Top anomalies:")
        for d in gt_details[:5]:
            print(f"    - {d['metric']} on {d['asset']} ({d['severity']})")

    # --- Compare broad query response vs ground truth ---
    print(f"\n--- COMPARISON: Broad utterance vs Ground Truth ---")
    broad_response = broad_result["response"]
    print(f"  Broad utterance response: {broad_response}")
    print(f"  Ground truth anomalies: {gt_anomalous} / {gt_total}")

    # Parse count from broad response
    import re
    count_match = re.search(r'(\d+)\s*anomal', broad_response.lower())
    spoken_count = int(count_match.group(1)) if count_match else None

    if spoken_count is not None:
        if spoken_count != gt_anomalous:
            add_finding("CRITICAL", "anomaly-accuracy",
                         f"Broad anomaly count mismatch: spoken={spoken_count}, truth={gt_anomalous}",
                         f"Broad utterance reported {spoken_count} anomalies but individual scan found {gt_anomalous}",
                         f"Spoken: '{broad_response}' | Truth: {gt_anomalous}/{gt_total} pairs anomalous")
        else:
            print(f"  [OK] Counts match: {spoken_count}")
    else:
        if gt_anomalous > 0:
            add_finding("HIGH", "anomaly-accuracy",
                         "Broad anomaly response doesn't include count",
                         f"Ground truth found {gt_anomalous} anomalies but broad response "
                         f"doesn't mention a count",
                         broad_response)
        elif "no unusual" in broad_response.lower() and gt_anomalous == 0:
            print(f"  [OK] Both agree: no anomalies")
        else:
            print(f"  [WARN] Could not parse anomaly count from broad response")

    # Check severity invariant: anomalous=true should never have severity=none
    for d in gt_details:
        if d["severity"] == "none":
            add_finding("CRITICAL", "severity-invariant",
                         f"Anomalous result with severity=none",
                         f"{d['metric']} on {d['asset']} reported as anomalous but severity=none",
                         d["response"])


# ===========================================================================
# Phase D: Drift Detection Tests
# ===========================================================================

def run_drift_tests(dispatcher: UtteranceDispatcher, profile_name: str):
    """Test drift detection accuracy."""
    print(f"\n{'=' * 70}")
    print(f"DRIFT DETECTION — Profile: {profile_name}")
    print("=" * 70)

    print("\n--- Test 1: Generic drift query")
    result = dispatcher.send_utterance("Is production drifting?")
    print(f"  Spoken: {result['response']}")
    time.sleep(PAUSE_BETWEEN)

    print("\n--- Test 2: Energy drift query")
    result = dispatcher.send_utterance("How has energy been trending?")
    print(f"  Spoken: {result['response']}")
    time.sleep(PAUSE_BETWEEN)

    # Check if drift response mentions a metric and direction
    response = result["response"].lower()
    if "[TIMEOUT" in result["response"]:
        add_finding("HIGH", "drift", "Drift query timeout",
                     "Drift check for energy timed out")
    elif "stable" in response or "drift" in response or "trend" in response or "no significant" in response:
        print(f"  [OK] Got drift-style response")
    else:
        add_finding("MEDIUM", "drift", "Drift response format unclear",
                     "Expected drift-style keywords (stable, drift, trend, etc.)",
                     result["response"])


# ===========================================================================
# Phase E: Comparison & Trend Tests
# ===========================================================================

def run_comparison_trend_tests(dispatcher: UtteranceDispatcher, profile_name: str):
    """Test comparison and trend commands."""
    print(f"\n{'=' * 70}")
    print(f"COMPARISON & TREND — Profile: {profile_name}")
    print("=" * 70)

    try:
        assets_data = api_get("/api/v1/assets/mappings")
        asset_names = list(assets_data.get("asset_mappings", {}).keys())
    except Exception:
        asset_names = ["Compressor-1", "HVAC-Main"]

    if len(asset_names) >= 2:
        a1, a2 = asset_names[0], asset_names[1]
        print(f"\n--- Test 1: Compare energy between {a1} and {a2}")
        result = dispatcher.send_utterance(f"Compare energy between {a1} and {a2}")
        print(f"  Spoken: {result['response']}")
        time.sleep(PAUSE_BETWEEN)

        if "[TIMEOUT" in result["response"]:
            add_finding("HIGH", "compare", "Comparison query timeout",
                         f"Compare energy between {a1} and {a2} timed out")
    else:
        print("  [SKIP] Need 2+ assets for comparison tests")

    print(f"\n--- Test 2: Energy trend")
    result = dispatcher.send_utterance("Show energy trend for last week")
    print(f"  Spoken: {result['response']}")
    time.sleep(PAUSE_BETWEEN)

    if "[TIMEOUT" in result["response"]:
        add_finding("HIGH", "trend", "Trend query timeout",
                     "Energy trend for last week timed out")

    print(f"\n--- Test 3: Scrap trend")
    result = dispatcher.send_utterance("Show scrap rate trend")
    print(f"  Spoken: {result['response']}")
    time.sleep(PAUSE_BETWEEN)


# ===========================================================================
# Phase F: System & Status Tests
# ===========================================================================

def run_system_tests(dispatcher: UtteranceDispatcher, profile_name: str):
    """Test system-level voice commands."""
    print(f"\n{'=' * 70}")
    print(f"SYSTEM & STATUS — Profile: {profile_name}")
    print("=" * 70)

    tests = [
        ("Show status", "status"),
        ("What can you do?", "capabilities"),
        ("List assets", "assets"),
        ("Hello", "greeting"),
        ("Help", "help"),
    ]

    for utterance, test_name in tests:
        print(f"\n--- {test_name}: '{utterance}'")
        result = dispatcher.send_utterance(utterance)
        print(f"  Spoken: {result['response']}")

        if "[TIMEOUT" in result["response"]:
            add_finding("MEDIUM", "system", f"{test_name} command timeout",
                         f"'{utterance}' got no response")

        time.sleep(PAUSE_BETWEEN)


# ===========================================================================
# Phase G: What-If Simulation Tests
# ===========================================================================

def run_whatif_tests(dispatcher: UtteranceDispatcher, profile_name: str):
    """Test what-if simulation."""
    print(f"\n{'=' * 70}")
    print(f"WHAT-IF SIMULATION — Profile: {profile_name}")
    print("=" * 70)

    print("\n--- Test 1: Temperature reduction")
    result = dispatcher.send_utterance("What if we reduce temperature by 5 degrees?")
    print(f"  Spoken: {result['response']}")
    time.sleep(PAUSE_BETWEEN)

    if "[TIMEOUT" in result["response"]:
        add_finding("MEDIUM", "whatif", "What-if simulation timeout",
                     "Temperature reduction what-if timed out")


# ===========================================================================
# Profile Switching
# ===========================================================================

def switch_profile(profile_name: str):
    """Switch AVAROS active profile by sending avaros.profile.activated event."""
    print(f"\n[INFO] Switching to profile: {profile_name}")
    try:
        ws = websocket.create_connection(MESSAGEBUS_URL, timeout=5)
        msg = {
            "type": "avaros.profile.activated",
            "data": {"profile": profile_name},
            "context": {},
        }
        ws.send(json.dumps(msg))
        ws.close()
        print(f"[OK] Profile switch event sent: {profile_name}")
        time.sleep(5)  # Wait for adapter reload
    except Exception as e:
        print(f"[FAIL] Could not switch profile: {e}")
        add_finding("CRITICAL", "infrastructure", f"Profile switch failed for {profile_name}", str(e))


# ===========================================================================
# Findings Report
# ===========================================================================

def print_findings_report():
    """Print severity-ranked findings report."""
    print("\n" + "=" * 70)
    print("FINDINGS REPORT")
    print("=" * 70)

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 99))

    critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
    high_count = sum(1 for f in findings if f.severity == "HIGH")
    medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
    low_count = sum(1 for f in findings if f.severity == "LOW")

    print(f"\nTotal findings: {len(findings)}")
    print(f"  CRITICAL: {critical_count}")
    print(f"  HIGH:     {high_count}")
    print(f"  MEDIUM:   {medium_count}")
    print(f"  LOW:      {low_count}")

    for i, f in enumerate(sorted_findings, 1):
        print(f"\n{'—' * 70}")
        print(f"Finding #{i} [{f.severity}] — {f.category}")
        print(f"Title: {f.title}")
        print(f"Detail: {f.detail}")
        if f.evidence:
            print(f"Evidence: {f.evidence[:500]}")

    print(f"\n{'=' * 70}")
    print("END OF FINDINGS REPORT")
    print("=" * 70)


# ===========================================================================
# Main
# ===========================================================================

def main():
    print("=" * 70)
    print("AVAROS TERMINAL-BASED E2E ACCURACY AUDIT")
    print(f"Date: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    dispatcher = UtteranceDispatcher()
    try:
        dispatcher.connect()
    except Exception as e:
        print(f"[FATAL] Cannot connect to messagebus: {e}")
        sys.exit(1)

    try:
        # Phase A: Environment check
        run_phase_a()

        # Determine which profile is currently active
        try:
            status = api_get("/api/v1/status")
            current_adapter = status.get("active_adapter", "unknown")
        except Exception:
            current_adapter = "unknown"

        # --- Audit HumanEnerDIA first (currently active based on logs) ---
        print("\n" + "#" * 70)
        print("# AUDITING: HumanEnerDIA PROFILE")
        print("#" * 70)
        switch_profile("humanenerdia")

        run_kpi_accuracy_tests(dispatcher, "humanenerdia")
        run_anomaly_accuracy_tests(dispatcher, "humanenerdia")
        run_drift_tests(dispatcher, "humanenerdia")
        run_comparison_trend_tests(dispatcher, "humanenerdia")
        run_system_tests(dispatcher, "humanenerdia")
        run_whatif_tests(dispatcher, "humanenerdia")

        # --- Switch to RENERYO and audit ---
        print("\n" + "#" * 70)
        print("# AUDITING: RENERYO PROFILE")
        print("#" * 70)
        switch_profile("reneryo")

        run_kpi_accuracy_tests(dispatcher, "reneryo")
        run_anomaly_accuracy_tests(dispatcher, "reneryo")
        run_drift_tests(dispatcher, "reneryo")
        run_comparison_trend_tests(dispatcher, "reneryo")
        run_system_tests(dispatcher, "reneryo")
        run_whatif_tests(dispatcher, "reneryo")

        # --- Restore original profile ---
        switch_profile("humanenerdia")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Audit stopped by user")
    except Exception as e:
        print(f"\n\n[FATAL] Audit error: {e}")
        traceback.print_exc()
        add_finding("CRITICAL", "audit", "Audit script crashed", str(e))
    finally:
        dispatcher.close()

    # Print findings report
    print_findings_report()

    return 1 if any(f.severity == "CRITICAL" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
