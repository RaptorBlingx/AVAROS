#!/usr/bin/env python3
"""
AVAROS Deep Accuracy Audit — Cross-validates voice responses against raw API data.

Methodology:
  1. For each test, query voice (via OVOS messagebus) AND query raw API directly
  2. Compare spoken value vs. raw API value
  3. Flag any discrepancy, missing response, or incorrect formatting
  4. Test all command types: KPI, comparison, trend, anomaly, drift, what-if, system

Usage:
  docker exec -e MESSAGEBUS_HOST=avaros-messagebus \
    avaros-skill python3 /tmp/deep_audit.py
"""

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta

import requests
from websocket import create_connection

# === Configuration ===
MESSAGEBUS_HOST = os.environ.get("MESSAGEBUS_HOST", "avaros-messagebus")
MESSAGEBUS_PORT = int(os.environ.get("MESSAGEBUS_PORT", "8181"))
WEBUI_HOST = os.environ.get("WEBUI_HOST", "avaros-web-ui")
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "8080"))
API_KEY = os.environ.get("AVAROS_WEB_API_KEY", "raptorblingx")

WS_URL = f"ws://{MESSAGEBUS_HOST}:{MESSAGEBUS_PORT}/core"
WEBUI_BASE = f"http://{WEBUI_HOST}:{WEBUI_PORT}/api/v1"
HEADERS = {"X-API-Key": API_KEY}

# Findings accumulator
findings = []
test_results = []
test_count = 0
pass_count = 0
fail_count = 0
warn_count = 0


def add_finding(severity, category, title, detail):
    """Record an audit finding."""
    findings.append({
        "severity": severity,
        "category": category,
        "title": title,
        "detail": detail,
    })


def record_test(name, status, voice_resp, api_value=None, notes=""):
    """Record a test result."""
    global test_count, pass_count, fail_count, warn_count
    test_count += 1
    if status == "PASS":
        pass_count += 1
    elif status == "FAIL":
        fail_count += 1
    elif status == "WARN":
        warn_count += 1
    test_results.append({
        "name": name,
        "status": status,
        "voice_response": voice_resp,
        "api_value": api_value,
        "notes": notes,
    })
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭"}.get(status, "?")
    print(f"  {icon} {name}: {status}")
    if notes:
        print(f"      → {notes}")
    if voice_resp and len(str(voice_resp)) < 200:
        print(f"      Voice: {voice_resp}")
    if api_value is not None:
        print(f"      API:   {api_value}")


# === OVOS Messagebus Voice Interface ===
ws = None


def connect_ws():
    global ws
    ws = create_connection(WS_URL)


def ask_voice(utterance, timeout=20):
    """Send utterance to OVOS and capture the spoken response."""
    msg = json.dumps({
        "type": "recognizer_loop:utterance",
        "data": {"utterances": [utterance]},
        "context": {},
    })
    ws.send(msg)
    responses = []
    end_time = time.time() + timeout
    while time.time() < end_time:
        ws.settimeout(1.0)
        try:
            raw = ws.recv()
            r = json.loads(raw)
            if r.get("type") == "speak":
                responses.append(r["data"].get("utterance", ""))
        except Exception:
            continue
    return " ".join(responses) if responses else None


def ask_voice_all_events(utterance, timeout=20):
    """Send utterance and capture ALL messagebus events."""
    msg = json.dumps({
        "type": "recognizer_loop:utterance",
        "data": {"utterances": [utterance]},
        "context": {},
    })
    ws.send(msg)
    events = []
    end_time = time.time() + timeout
    while time.time() < end_time:
        ws.settimeout(1.0)
        try:
            raw = ws.recv()
            r = json.loads(raw)
            events.append(r)
        except Exception:
            continue
    speaks = [e["data"].get("utterance", "") for e in events if e.get("type") == "speak"]
    return speaks, events


# === Raw API Direct Access ===
def get_reneryo_api_config():
    """Get the RENERYO API connection (URL + auth) from the profile."""
    resp = requests.get(f"{WEBUI_BASE}/config/profiles/reneryo", headers=HEADERS)
    return resp.json()


def get_asset_mappings():
    resp = requests.get(f"{WEBUI_BASE}/assets/mappings", headers=HEADERS)
    return resp.json().get("asset_mappings", {})


def get_metric_mappings():
    resp = requests.get(f"{WEBUI_BASE}/config/metrics", headers=HEADERS)
    return resp.json()


def get_alert_config():
    resp = requests.get(f"{WEBUI_BASE}/config/alert-config", headers=HEADERS)
    return resp.json()


def get_active_profile():
    resp = requests.get(f"{WEBUI_BASE}/config/profiles", headers=HEADERS)
    data = resp.json()
    return data.get("active_profile", "unknown")


def fetch_raw_metric(api_base, resource_id, metric_endpoint, json_path, session=None):
    """Fetch a metric value directly from the platform API."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=365*5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    url = api_base.rstrip("/") + metric_endpoint.replace(
        "{resource_id}", resource_id
    ).replace(
        "{start_date}", start
    ).replace(
        "{end_date}", end
    )

    try:
        s = session or requests
        resp = s.get(url, timeout=15)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        # Simple JSON path extraction for $.records[0].value and $.lastValue
        if json_path == "$.records[0].value":
            records = data.get("records", [])
            if records:
                return records[0].get("value"), None
            return None, "Empty records array"
        elif json_path == "$.lastValue":
            val = data.get("lastValue")
            return val, None if val is not None else "lastValue is null"
        else:
            return None, f"Unsupported json_path: {json_path}"
    except Exception as e:
        return None, str(e)


def extract_number_from_voice(text):
    """Extract the first numeric value from a voice response."""
    if not text:
        return None
    # Match numbers like 2.2, 86541.0, 72, 0.4, etc.
    m = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)', text)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def extract_all_numbers(text):
    """Extract all numbers from text."""
    if not text:
        return []
    return [float(m.replace(",", "")) for m in re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', text)]


# =====================================================
# AUDIT SECTIONS
# =====================================================

def audit_system_commands():
    """Test system/help commands."""
    print("\n" + "=" * 70)
    print("SECTION 1: SYSTEM COMMANDS")
    print("=" * 70)

    # 1a. Greeting
    resp = ask_voice("hello")
    if resp:
        record_test("greeting", "PASS", resp)
    else:
        record_test("greeting", "FAIL", resp, notes="No response to greeting")

    # 1b. Capabilities
    resp = ask_voice("what can you do")
    if resp and ("energy" in resp.lower() or "kpi" in resp.lower() or "metric" in resp.lower()):
        record_test("capabilities", "PASS", resp)
    elif resp:
        record_test("capabilities", "WARN", resp, notes="Response doesn't mention key capabilities")
    else:
        record_test("capabilities", "FAIL", resp, notes="No response")

    # 1c. Status
    resp = ask_voice("what is the system status")
    if resp:
        record_test("system_status", "PASS", resp)
    else:
        record_test("system_status", "FAIL", resp, notes="No response to status query")

    # 1d. Asset list
    resp = ask_voice("what assets are you monitoring")
    if resp:
        record_test("asset_list", "PASS", resp)
    else:
        record_test("asset_list", "FAIL", resp, notes="No response to asset query")

    # 1e. Unknown command
    resp = ask_voice("tell me a joke about manufacturing")
    record_test("unknown_command", "PASS" if resp is None else "WARN", resp,
                notes="Should have no response or graceful deflection" if resp else "Correctly ignored")


def audit_kpi_queries(api_base, asset_mappings, metric_mappings, session):
    """Test KPI queries and cross-validate against raw API."""
    print("\n" + "=" * 70)
    print("SECTION 2: KPI QUERIES (with API cross-validation)")
    print("=" * 70)

    # Build lookup for metric endpoints
    metric_lookup = {}
    for m in metric_mappings:
        metric_lookup[m["canonical_metric"]] = m

    # Test key metrics for Line-1
    asset = "Line-1"
    asset_data = asset_mappings.get(asset, {})
    resources = asset_data.get("metric_resources", {})

    test_metrics = [
        ("energy_per_unit", "what is the energy per unit for Line 1"),
        ("energy_total", "what is the total energy for Line 1"),
        ("oee", "what is the OEE for Line 1"),
        ("scrap_rate", "what is the scrap rate for Line 1"),
        ("co2_per_unit", "what is the CO2 per unit for Line 1"),
        ("co2_total", "what is the CO2 total for Line 1"),
        ("throughput", "what is the throughput for Line 1"),
        ("material_efficiency", "what is the material efficiency for Line 1"),
        ("cycle_time", "what is the cycle time for Line 1"),
        ("peak_demand", "what is the peak demand for Line 1"),
        ("rework_rate", "what is the rework rate for Line 1"),
        ("changeover_time", "what is the changeover time for Line 1"),
    ]

    for metric_name, utterance in test_metrics:
        resource_id = resources.get(metric_name)
        mapping = metric_lookup.get(metric_name)

        if not resource_id or not mapping:
            record_test(f"kpi_{metric_name}_Line1", "SKIP", None,
                        notes=f"No resource mapping for {metric_name}")
            continue

        # Get voice response
        voice_resp = ask_voice(utterance)

        # Get raw API value
        api_val, api_err = fetch_raw_metric(
            api_base, resource_id, mapping["endpoint"], mapping["json_path"], session
        )

        if voice_resp is None:
            record_test(f"kpi_{metric_name}_Line1", "FAIL", voice_resp,
                        api_value=api_val, notes="No voice response")
            add_finding("HIGH", "KPI", f"{metric_name} returns no voice response",
                        f"Utterance: {utterance}, API value: {api_val}, API error: {api_err}")
            continue

        if api_val is not None:
            voice_num = extract_number_from_voice(voice_resp)
            if voice_num is not None:
                # Allow small floating point tolerance
                if abs(voice_num - float(api_val)) < 0.15:
                    record_test(f"kpi_{metric_name}_Line1", "PASS", voice_resp,
                                api_value=api_val, notes=f"Voice={voice_num}, API={api_val}")
                else:
                    record_test(f"kpi_{metric_name}_Line1", "FAIL", voice_resp,
                                api_value=api_val,
                                notes=f"VALUE MISMATCH: Voice={voice_num} vs API={api_val}")
                    add_finding("CRITICAL", "KPI_ACCURACY",
                                f"{metric_name} value mismatch",
                                f"Voice said {voice_num} but API returned {api_val}")
            else:
                record_test(f"kpi_{metric_name}_Line1", "WARN", voice_resp,
                            api_value=api_val, notes="Could not extract number from voice response")
        elif api_err:
            if "trouble connecting" in (voice_resp or "").lower() or "error" in (voice_resp or "").lower():
                record_test(f"kpi_{metric_name}_Line1", "WARN", voice_resp,
                            notes=f"Both voice and API failed: {api_err}")
            else:
                record_test(f"kpi_{metric_name}_Line1", "WARN", voice_resp,
                            notes=f"API error: {api_err}")

    # Test metrics for non-Line assets (meters only have energy_total)
    for meter_asset in ["Electric-Main-Meter", "Gas-Main-Meter", "Water-Main-Meter"]:
        meter_data = asset_mappings.get(meter_asset, {})
        meter_resources = meter_data.get("metric_resources", {})
        et_resource = meter_resources.get("energy_total")
        display = meter_data.get("display_name", meter_asset)

        if not et_resource:
            continue

        voice_resp = ask_voice(f"what is the total energy for {display}")
        api_val, api_err = fetch_raw_metric(
            api_base, et_resource,
            metric_lookup.get("energy_total", {}).get("endpoint", ""),
            metric_lookup.get("energy_total", {}).get("json_path", "$.lastValue"),
            session,
        )

        if voice_resp and api_val is not None:
            voice_num = extract_number_from_voice(voice_resp)
            if voice_num is not None and abs(voice_num - float(api_val)) < 1.0:
                record_test(f"kpi_energy_total_{meter_asset}", "PASS", voice_resp,
                            api_value=api_val)
            elif voice_num is not None:
                record_test(f"kpi_energy_total_{meter_asset}", "FAIL", voice_resp,
                            api_value=api_val,
                            notes=f"VALUE MISMATCH: Voice={voice_num} vs API={api_val}")
            else:
                record_test(f"kpi_energy_total_{meter_asset}", "WARN", voice_resp,
                            api_value=api_val, notes="No number in voice response")
        elif voice_resp is None:
            record_test(f"kpi_energy_total_{meter_asset}", "FAIL", None,
                        api_value=api_val, notes="No voice response")
        else:
            record_test(f"kpi_energy_total_{meter_asset}", "WARN", voice_resp,
                        notes=f"API error: {api_err}")


def audit_comparisons():
    """Test comparison commands."""
    print("\n" + "=" * 70)
    print("SECTION 3: COMPARISON QUERIES")
    print("=" * 70)

    tests = [
        ("compare energy between Line 1 and Line 2", "compare_energy_L1_L2"),
        ("compare energy between Line 1 and Line 3", "compare_energy_L1_L3"),
        ("compare energy between Line 2 and Line 3", "compare_energy_L2_L3"),
        ("compare OEE between Line 1 and Line 2", "compare_oee_L1_L2"),
        ("compare scrap rate between Line 1 and Line 2", "compare_scrap_L1_L2"),
        ("compare throughput between Line 1 and Line 2", "compare_throughput_L1_L2"),
        ("compare CO2 between Line 1 and Line 2", "compare_co2_L1_L2"),
    ]

    for utterance, test_name in tests:
        resp = ask_voice(utterance)
        if resp and ("more" in resp.lower() or "less" in resp.lower()
                     or "higher" in resp.lower() or "lower" in resp.lower()
                     or "efficient" in resp.lower() or "same" in resp.lower()
                     or "difference" in resp.lower()):
            record_test(test_name, "PASS", resp)
        elif resp:
            # Got a response but it might not be a comparison
            if "trouble" in resp.lower() or "error" in resp.lower():
                record_test(test_name, "FAIL", resp, notes="Error response instead of comparison")
                add_finding("HIGH", "COMPARISON", f"{test_name} returns error",
                            f"Response: {resp}")
            else:
                record_test(test_name, "WARN", resp, notes="Response doesn't look like a comparison")
        else:
            record_test(test_name, "FAIL", resp, notes="No response")
            add_finding("HIGH", "COMPARISON", f"{test_name} returns no response",
                        f"Utterance: {utterance}")


def audit_trends():
    """Test trend commands."""
    print("\n" + "=" * 70)
    print("SECTION 4: TREND QUERIES")
    print("=" * 70)

    tests = [
        ("show energy trend for today", "trend_energy_today"),
        ("show energy trend for last week", "trend_energy_week"),
        ("how has energy changed this month", "trend_energy_month"),
        ("show scrap rate trend", "trend_scrap"),
        ("show OEE trend for last week", "trend_oee_week"),
        ("show throughput trend", "trend_throughput"),
    ]

    for utterance, test_name in tests:
        resp = ask_voice(utterance)
        if resp and ("trend" in resp.lower() or "increased" in resp.lower()
                     or "decreased" in resp.lower() or "stable" in resp.lower()
                     or "changed" in resp.lower() or "points" in resp.lower()
                     or "data" in resp.lower() or "average" in resp.lower()
                     or "couldn't find" in resp.lower()):
            record_test(test_name, "PASS", resp)
        elif resp:
            if "trouble" in resp.lower() or "error" in resp.lower():
                record_test(test_name, "FAIL", resp, notes="Error instead of trend data")
                add_finding("MEDIUM", "TREND", f"{test_name} returns error", resp)
            else:
                record_test(test_name, "WARN", resp, notes="Response may not be trend data")
        else:
            record_test(test_name, "FAIL", resp, notes="No response")
            add_finding("MEDIUM", "TREND", f"{test_name} returns no response", utterance)


def audit_anomalies():
    """Test anomaly detection commands."""
    print("\n" + "=" * 70)
    print("SECTION 5: ANOMALY DETECTION")
    print("=" * 70)

    # Broad scan
    resp = ask_voice("are there any anomalies in production")
    if resp:
        record_test("anomaly_broad_scan", "PASS", resp)
        # Check if the number claimed matches reality
        nums = extract_all_numbers(resp)
        if nums:
            print(f"      [INFO] Anomaly scan reported numbers: {nums}")
    else:
        record_test("anomaly_broad_scan", "FAIL", resp, notes="No response")

    # Specific asset anomaly
    resp = ask_voice("any unusual patterns for Line 1")
    if resp:
        record_test("anomaly_line1", "PASS", resp)
    else:
        record_test("anomaly_line1", "FAIL", resp, notes="No response")

    # Specific metric + asset
    resp = ask_voice("check for anomalies in energy per unit for Line 1")
    if resp:
        record_test("anomaly_epu_line1", "PASS", resp)
    else:
        record_test("anomaly_epu_line1", "FAIL", resp, notes="No response")

    # Different phrasings
    resp = ask_voice("any spikes or issues")
    if resp:
        record_test("anomaly_spikes", "PASS", resp)
    else:
        record_test("anomaly_spikes", "FAIL", resp, notes="No response")


def audit_drift():
    """Test drift detection commands."""
    print("\n" + "=" * 70)
    print("SECTION 6: DRIFT DETECTION")
    print("=" * 70)

    tests = [
        ("how has energy been trending", "drift_energy"),
        ("check for drift in production", "drift_production"),
        ("is there any drift in energy consumption", "drift_energy_consumption"),
    ]

    for utterance, test_name in tests:
        resp = ask_voice(utterance)
        if resp and ("drift" in resp.lower() or "stable" in resp.lower()
                     or "detected" in resp.lower() or "significant" in resp.lower()
                     or "trending" in resp.lower()):
            record_test(test_name, "PASS", resp)
        elif resp:
            record_test(test_name, "WARN", resp, notes="Response may not be drift data")
        else:
            record_test(test_name, "FAIL", resp, notes="No response")


def audit_whatif():
    """Test what-if simulation commands."""
    print("\n" + "=" * 70)
    print("SECTION 7: WHAT-IF SIMULATION")
    print("=" * 70)

    resp = ask_voice("what if we reduce temperature by 5 degrees")
    if resp and ("temperature" in resp.lower() or "energy" in resp.lower()
                 or "reduce" in resp.lower() or "change" in resp.lower()
                 or "simulation" in resp.lower() or "estimated" in resp.lower()
                 or "would" in resp.lower()):
        record_test("whatif_temp_5", "PASS", resp)
    elif resp:
        record_test("whatif_temp_5", "WARN", resp, notes="Response doesn't match expected what-if format")
    else:
        record_test("whatif_temp_5", "FAIL", resp, notes="No response")

    resp = ask_voice("simulate reducing temperature by 10")
    if resp:
        record_test("whatif_temp_10", "PASS", resp)
    else:
        record_test("whatif_temp_10", "FAIL", resp, notes="No response")


def audit_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 70)
    print("SECTION 8: EDGE CASES & ERROR HANDLING")
    print("=" * 70)

    # Nonexistent asset
    resp = ask_voice("what is the energy per unit for Compressor 99")
    record_test("nonexistent_asset", "PASS" if resp else "WARN", resp,
                notes="Should handle gracefully")

    # Nonexistent metric
    resp = ask_voice("what is the humidity for Line 1")
    record_test("nonexistent_metric", "PASS" if resp is None else "WARN", resp,
                notes="Should not answer or deflect gracefully")

    # Very specific asset reference
    resp = ask_voice("energy per unit for l1")
    if resp and ("line 1" in resp.lower() or "l1" in resp.lower() or extract_number_from_voice(resp)):
        record_test("alias_l1", "PASS", resp, notes="Alias 'l1' resolved correctly")
    elif resp:
        record_test("alias_l1", "WARN", resp, notes="May not have resolved alias")
    else:
        record_test("alias_l1", "FAIL", resp, notes="No response for alias")

    # Alias: "electric meter"
    resp = ask_voice("total energy for electric meter")
    if resp and extract_number_from_voice(resp):
        record_test("alias_electric_meter", "PASS", resp)
    elif resp:
        record_test("alias_electric_meter", "WARN", resp)
    else:
        record_test("alias_electric_meter", "FAIL", resp, notes="No response for alias")

    # Rapid-fire: two queries back-to-back
    resp1 = ask_voice("energy per unit for Line 1", timeout=10)
    resp2 = ask_voice("scrap rate for Line 2", timeout=10)
    record_test("rapid_fire_1", "PASS" if resp1 else "FAIL", resp1)
    record_test("rapid_fire_2", "PASS" if resp2 else "FAIL", resp2)


def audit_cross_asset_consistency(api_base, asset_mappings, metric_mappings, session):
    """Verify same metric across all Line assets returns consistent & different values."""
    print("\n" + "=" * 70)
    print("SECTION 9: CROSS-ASSET CONSISTENCY CHECK")
    print("=" * 70)

    metric_lookup = {m["canonical_metric"]: m for m in metric_mappings}
    test_metric = "energy_per_unit"
    mapping = metric_lookup.get(test_metric)
    if not mapping:
        record_test("cross_asset_consistency", "SKIP", None, notes="No mapping for energy_per_unit")
        return

    values = {}
    for asset_name in ["Line-1", "Line-2", "Line-3"]:
        asset_data = asset_mappings.get(asset_name, {})
        resource_id = asset_data.get("metric_resources", {}).get(test_metric)
        if not resource_id:
            continue

        # Voice query
        display = asset_data.get("display_name", asset_name)
        voice_resp = ask_voice(f"what is energy per unit for {display}")
        voice_num = extract_number_from_voice(voice_resp) if voice_resp else None

        # API query
        api_val, _ = fetch_raw_metric(api_base, resource_id, mapping["endpoint"], mapping["json_path"], session)

        values[asset_name] = {
            "voice": voice_num,
            "api": float(api_val) if api_val is not None else None,
            "voice_resp": voice_resp,
        }

    # Check: are Line-1, Line-2, Line-3 all returning the same value? That'd be suspicious.
    voice_vals = [v["voice"] for v in values.values() if v["voice"] is not None]
    api_vals = [v["api"] for v in values.values() if v["api"] is not None]

    if len(set(voice_vals)) == 1 and len(voice_vals) > 1:
        record_test("cross_asset_voice_diversity", "WARN", str(values),
                     notes=f"All Lines return same voice value: {voice_vals[0]} — suspicious")
        add_finding("MEDIUM", "DATA_QUALITY", "All Lines return same energy_per_unit",
                    f"Voice values: {values}")
    elif voice_vals:
        record_test("cross_asset_voice_diversity", "PASS", str(values),
                     notes="Lines show different values — good")

    if len(set(api_vals)) == 1 and len(api_vals) > 1:
        record_test("cross_asset_api_diversity", "WARN", str(api_vals),
                     notes="API returns same value for all Lines")
    elif api_vals:
        record_test("cross_asset_api_diversity", "PASS", str(api_vals))


def audit_response_format():
    """Check response formatting quality."""
    print("\n" + "=" * 70)
    print("SECTION 10: RESPONSE FORMAT QUALITY")
    print("=" * 70)

    # Check unit consistency
    resp = ask_voice("what is the energy per unit for Line 1")
    if resp:
        if "kwh" in resp.lower() or "kilowatt" in resp.lower():
            record_test("unit_energy_per_unit", "PASS", resp, notes="Correct unit (kWh)")
        else:
            record_test("unit_energy_per_unit", "WARN", resp, notes="Missing or wrong unit")
            add_finding("LOW", "FORMAT", "energy_per_unit missing unit in response", resp)

    resp = ask_voice("what is the OEE for Line 1")
    if resp:
        if "percent" in resp.lower() or "%" in resp:
            record_test("unit_oee", "PASS", resp, notes="Correct unit (percent)")
        else:
            record_test("unit_oee", "WARN", resp, notes="Missing percent unit")

    resp = ask_voice("what is the scrap rate for Line 1")
    if resp:
        if "percent" in resp.lower() or "%" in resp:
            record_test("unit_scrap_rate", "PASS", resp, notes="Correct unit (percent)")
        else:
            record_test("unit_scrap_rate", "WARN", resp, notes="Missing percent unit")

    resp = ask_voice("what is the cycle time for Line 1")
    if resp:
        if "second" in resp.lower() or "sec" in resp.lower():
            record_test("unit_cycle_time", "PASS", resp, notes="Correct unit")
        else:
            record_test("unit_cycle_time", "WARN", resp, notes="Missing or wrong time unit")


# =====================================================
# MAIN
# =====================================================

def main():
    print("=" * 70)
    print("AVAROS DEEP ACCURACY AUDIT")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # Connect
    connect_ws()
    print("[✓] Connected to OVOS messagebus")

    # Get configuration
    profile = get_active_profile()
    print(f"[✓] Active profile: {profile}")

    asset_mappings = get_asset_mappings()
    print(f"[✓] Assets loaded: {list(asset_mappings.keys())}")

    metric_mappings = get_metric_mappings()
    print(f"[✓] Metric mappings: {len(metric_mappings)}")

    alert_config = get_alert_config()
    print(f"[✓] Alert config: enabled={alert_config.get('enabled')}, pairs={len(alert_config.get('monitored_pairs', []))}")

    # Setup API session with RENERYO auth
    reneryo_config = get_reneryo_api_config()
    api_base = reneryo_config.get("api_url", "").rstrip("/")
    session = requests.Session()
    # RENERYO uses cookie auth — authenticate
    auth_resp = session.get(f"{api_base}/api/authenticate", params={
        "username": "admin@2.2",
        "password": "Arti@2024I=",
    }, timeout=10)
    if auth_resp.status_code == 200:
        print("[✓] Authenticated to RENERYO API")
    else:
        print(f"[!] RENERYO auth failed: {auth_resp.status_code}")
        session = requests

    # Run all audit sections
    try:
        audit_system_commands()
        audit_kpi_queries(api_base, asset_mappings, metric_mappings, session)
        audit_comparisons()
        audit_trends()
        audit_anomalies()
        audit_drift()
        audit_whatif()
        audit_edge_cases()
        audit_cross_asset_consistency(api_base, asset_mappings, metric_mappings, session)
        audit_response_format()
    except Exception:
        print(f"\n[!!!] Audit crashed:\n{traceback.format_exc()}")

    ws.close()

    # Summary
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    print(f"Total tests: {test_count}")
    print(f"  ✅ PASS: {pass_count}")
    print(f"  ❌ FAIL: {fail_count}")
    print(f"  ⚠️  WARN: {warn_count}")
    print(f"  ⏭  SKIP: {test_count - pass_count - fail_count - warn_count}")

    if findings:
        print(f"\nFINDINGS ({len(findings)}):")
        for i, f in enumerate(findings, 1):
            print(f"\n  [{f['severity']}] Finding {i}: {f['title']}")
            print(f"    Category: {f['category']}")
            print(f"    Detail: {f['detail'][:300]}")

    # Dump full results as JSON
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "summary": {
            "total": test_count,
            "pass": pass_count,
            "fail": fail_count,
            "warn": warn_count,
        },
        "findings": findings,
        "test_results": test_results,
    }
    print("\n\n=== JSON DUMP ===")
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
