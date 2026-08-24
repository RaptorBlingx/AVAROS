"""Publish transparent live demo telemetry through ThingsBoard's device API.

This companion process is intended for demonstrations without physical sensors.
It never writes to the ThingsBoard database and never backfills history.  Every
sample is submitted at the current time through the native HTTP device transport.
"""

from __future__ import annotations

import json
import math
import os
import signal
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TB_URL", "http://thingsboard-ce:8080").rstrip("/")
USERNAME = os.getenv("TB_USERNAME", "tenant@thingsboard.org")
PASSWORD = os.getenv("TB_PASSWORD", "tenant")
INTERVAL_SECONDS = max(5, int(os.getenv("TB_INTERVAL_SECONDS", "15")))
DEVICES = ("Test Device A1", "Test Device A2")

_running = True


def _stop(_signum: int, _frame: object) -> None:
    global _running
    _running = False


def _json_request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(
        url,
        data=data,
        headers=request_headers,
        method=method,
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body) if body else None


def _login() -> str:
    response = _json_request(
        "POST",
        f"{BASE_URL}/api/auth/login",
        payload={"username": USERNAME, "password": PASSWORD},
    )
    return str(response["token"])


def _resolve_devices(jwt_token: str) -> dict[str, dict[str, str]]:
    headers = {"X-Authorization": f"Bearer {jwt_token}"}
    resolved: dict[str, dict[str, str]] = {}
    for name in DEVICES:
        device = _json_request(
            "GET",
            f"{BASE_URL}/api/tenant/devices?deviceName={quote(name)}",
            headers=headers,
        )
        device_id = str(device["id"]["id"])
        credentials = _json_request(
            "GET",
            f"{BASE_URL}/api/device/{device_id}/credentials",
            headers=headers,
        )
        resolved[name] = {
            "device_id": device_id,
            "access_token": str(credentials["credentialsId"]),
        }
    return resolved


def _latest_total(jwt_token: str, device_id: str, fallback: float) -> float:
    headers = {"X-Authorization": f"Bearer {jwt_token}"}
    response = _json_request(
        "GET",
        (
            f"{BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}"
            "/values/timeseries?keys=energy_total_kwh"
        ),
        headers=headers,
    )
    try:
        return float(response["energy_total_kwh"][0]["value"])
    except (KeyError, IndexError, TypeError, ValueError):
        return fallback


def _sample(device_index: int, sequence: int, total: float) -> tuple[dict[str, float], float]:
    phase = sequence / 8.0 + device_index * 0.9
    energy_per_unit = 1.72 + device_index * 0.19 + 0.08 * math.sin(phase)
    oee = 88.5 - device_index * 3.2 + 2.1 * math.cos(phase / 1.4)
    increment = (0.42 + device_index * 0.06) * INTERVAL_SECONDS / 60.0
    next_total = total + increment
    return (
        {
            "energy_total_kwh": round(next_total, 3),
            "energy_per_unit_kwh": round(energy_per_unit, 3),
            "oee_percent": round(oee, 2),
        },
        next_total,
    )


def _publish(access_token: str, sample: dict[str, float]) -> None:
    _json_request(
        "POST",
        f"{BASE_URL}/api/v1/{quote(access_token)}/telemetry",
        payload=sample,
    )


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while _running:
        try:
            jwt_token = _login()
            devices = _resolve_devices(jwt_token)
            totals = {
                "Test Device A1": _latest_total(
                    jwt_token,
                    devices["Test Device A1"]["device_id"],
                    1250.0,
                ),
                "Test Device A2": _latest_total(
                    jwt_token,
                    devices["Test Device A2"]["device_id"],
                    980.0,
                ),
            }
            break
        except (HTTPError, URLError, KeyError, TimeoutError) as exc:
            print(f"ThingsBoard not ready ({exc}); retrying in 10 seconds", flush=True)
            time.sleep(10)

    print(
        "AVAROS ThingsBoard demo publisher ready: live simulated samples, "
        "native HTTP device transport, no historical backfill",
        flush=True,
    )
    sequence = 0
    while _running:
        try:
            for device_index, name in enumerate(DEVICES):
                sample, totals[name] = _sample(device_index, sequence, totals[name])
                _publish(devices[name]["access_token"], sample)
            if sequence % 20 == 0:
                print(
                    f"Published live telemetry for {', '.join(DEVICES)}",
                    flush=True,
                )
            sequence += 1
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"Telemetry publish failed ({exc}); retrying", flush=True)
        for _ in range(INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
