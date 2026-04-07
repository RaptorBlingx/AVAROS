#!/usr/bin/env python3
"""Cross-validate voice responses against raw RENERYO API values."""
import json, requests
from urllib.parse import unquote

api_base = "http://deploys.int.arti.ac:30377"
raw_key = "50e2a9a7-a030-4356-9b47-3db126c17c8d.azDOYokXB9DNsm9xBPb3SRJ5N36HQ6E5ehmH1RdyWyI%3D"
cookie_val = f"S={unquote(raw_key)}"
headers = {"Cookie": cookie_val}

line1 = {
    "energy_per_unit": "16fa8587-7d6a-4830-83c7-3c595f30cc26",
    "energy_total": "56982573-c88b-436d-b5b8-d37f6e5c9d42",
    "oee": "f1b1acb5-3dba-4a94-9cc8-aa55734ea991",
    "scrap_rate": "aa6a90f9-d75b-4b20-86ab-b41303acf765",
    "co2_per_unit": "851d75b6-a6b7-4e61-84e7-2ece4d6b3a9b",
    "co2_total": "029b5bc2-83ac-46e7-8097-916d3bcc8c71",
    "throughput": "9fcfd093-e749-4b84-bfb5-6d2d8e43c2ec",
    "material_efficiency": "b715894b-9196-43f2-8972-f89a3299f706",
    "cycle_time": "3e3e8e14-317b-4549-9c54-b27122882c07",
    "peak_demand": "83ab21fe-1d4b-4ec2-ab2c-eaca60b09fd7",
    "rework_rate": "d0a19a1e-3b76-440b-a88a-eb1410396921",
    "changeover_time": "c0aad49b-c8e1-4465-b86a-ceb93ab44da2",
    "peak_tariff_exposure": "6b2b45fd-e30b-48f2-95c7-be530784bb1a",
    "recycled_content": "812ac4be-5bdb-4677-a41e-a3f52b878254",
    "supplier_co2_per_kg": "5255432d-e2f7-40e7-85fd-b62759ef83a7",
    "supplier_defect_rate": "c4007178-f60a-4f32-8e5d-841f2cfdf226",
    "supplier_lead_time": "f2ba406e-277d-4586-aeac-dc2b3df7aeb6",
    "supplier_on_time": "9caa2399-9f69-403e-99eb-96c36f34a9a4",
}

line2 = {
    "energy_per_unit": "6a3d1fb7-8338-4d33-ab9d-72e48523753f",
    "oee": "81d338e2-ede6-4c34-976d-954d46ba93e9",
    "scrap_rate": "338d153c-c5bc-40eb-8613-19f659d1df05",
}

line3 = {
    "energy_per_unit": "cc037918-8c95-4771-998b-a9f37ff76be4",
}

meters = {
    "Electric-Main-Meter": "34d89fed-3ba6-4ceb-bb77-1bcf6fac0ac3",
    "Gas-Main-Meter": "d69b53df-bc42-4b20-a3e0-234a7f707d5c",
    "Water-Main-Meter": "86b30169-3532-4385-be29-217299ed94db",
}

def get_val(resource_id, endpoint_type="values"):
    if endpoint_type == "values":
        url = f"{api_base}/api/u/measurement/metric/resource/{resource_id}/values?period=RAW&datetimeMin=2021-01-01T00:00:00.000Z&datetimeMax=2026-04-07T00:00:00.000Z&count=1&page=1"
    else:
        url = f"{api_base}/api/u/measurement/metric/item/{resource_id}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return f"HTTP-{r.status_code}"
        data = r.json()
        if endpoint_type == "values":
            recs = data.get("records", [])
            return recs[0].get("value") if recs else "NO_RECORDS"
        else:
            return data.get("lastValue", "NO_VALUE")
    except Exception as e:
        return f"ERR:{e}"

# Captured voice values from the audit
voice_values = {
    "energy_per_unit": 2.2,
    "energy_total": 17138.6,
    "oee": 68.3,
    "scrap_rate": 4.1,
    "co2_per_unit": 1.4,
    "co2_total": 11119.8,
    "throughput": 109.8,
    "material_efficiency": 89.4,
    "cycle_time": 27.3,
    "peak_demand": 347.4,
    "rework_rate": 3.0,
    "changeover_time": 45.4,
}

print("=" * 80)
print("CROSS-VALIDATION: Voice vs Raw RENERYO API for Line-1")
print("=" * 80)
print(f"{'Metric':<25} {'Voice':<12} {'API':<12} {'Match?':<8} {'Note'}")
print("-" * 80)

for metric, resource_id in line1.items():
    endpoint_type = "item" if metric == "energy_total" else "values"
    api_val = get_val(resource_id, endpoint_type)
    voice_val = voice_values.get(metric, "N/A")

    if isinstance(api_val, (int, float)):
        if voice_val != "N/A":
            diff = abs(float(voice_val) - float(api_val))
            match = "OK" if diff < 0.15 else "DIFF"
            note = f"diff={diff:.3f}" if diff >= 0.15 else ""
        else:
            match = "SKIP"
            note = "No voice query"
    else:
        match = "WARN"
        note = str(api_val)

    print(f"{metric:<25} {str(voice_val):<12} {str(api_val):<12} {match:<8} {note}")

print()
print("=" * 80)
print("CROSS-VALIDATION: Line-2, Line-3 (diversity check)")
print("=" * 80)
for asset_name, resources in [("Line-2", line2), ("Line-3", line3)]:
    print(f"\n--- {asset_name} ---")
    for metric, resource_id in resources.items():
        api_val = get_val(resource_id, "values")
        l1_val = get_val(line1[metric], "values")
        same = "SAME!" if api_val == l1_val else "DIFF"
        print(f"  {metric:<25} {asset_name}={str(api_val):<12} L1={str(l1_val):<12} {same}")

print()
print("=" * 80)
print("CROSS-VALIDATION: Meters energy_total")
print("=" * 80)
meter_voice = {
    "Electric-Main-Meter": 86541.0,
    "Gas-Main-Meter": 172741.5,
    "Water-Main-Meter": 28847.0,
}
for meter, resource_id in meters.items():
    api_val = get_val(resource_id, "item")
    voice_val = meter_voice.get(meter, "N/A")
    if isinstance(api_val, (int, float)):
        diff = abs(float(voice_val) - float(api_val))
        match = "OK" if diff < 1.0 else "DIFF"
        note = f"diff={diff:.1f}" if diff >= 1.0 else ""
    else:
        match = "WARN"
        note = str(api_val)
    print(f"  {meter:<25} Voice={str(voice_val):<12} API={str(api_val):<12} {match} {note}")
