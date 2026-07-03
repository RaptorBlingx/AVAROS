"""Regression checks for the live RENERYO wizard preset."""

from __future__ import annotations

import json
from pathlib import Path


_PRESET = (
    Path(__file__).resolve().parents[2]
    / "web-ui"
    / "frontend"
    / "public"
    / "wizard-preset-reneryo.json"
)
_GENERATOR_MAPPING = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "reneryo-data-generator"
    / "mapping_output.json"
)


def test_reneryo_resource_ids_use_resource_values_endpoint() -> None:
    """Resource UUID links must never be sent to the metric-item endpoint."""
    preset = json.loads(_PRESET.read_text(encoding="utf-8"))
    metrics = preset["metrics"]
    energy_total = next(
        mapping
        for mapping in metrics["mappings"]
        if mapping["canonical_metric"] == "energy_total"
    )

    endpoint = energy_total.get("endpoint", metrics["endpoint"])
    json_path = energy_total.get("json_path", metrics["json_path"])

    assert "/metric/resource/{resource_id}/values" in endpoint
    assert "/metric/item/{resource_id}" not in endpoint
    assert json_path == "$.records[0].value"


def test_non_energy_sensors_are_not_linked_as_energy() -> None:
    """Temperature and pressure resources must not be advertised as kWh."""
    preset = json.loads(_PRESET.read_text(encoding="utf-8"))

    assert "Meter-2" not in preset["linking"]
    assert "Meter-3" not in preset["linking"]


def test_main_electric_meter_matches_live_reneryo_resource() -> None:
    """Electric Main Meter must point at the resource used by RENERYO values UI."""
    preset = json.loads(_PRESET.read_text(encoding="utf-8"))

    assert (
        preset["linking"]["Electric-Main-Meter"]["energy_total"]
        == "525c5133-80eb-4c95-8f0c-06e56d2854fe"
    )


def test_line_links_match_the_bundled_generator_mapping() -> None:
    """The preset and default import file must describe the same resources."""
    preset = json.loads(_PRESET.read_text(encoding="utf-8"))
    generated = json.loads(_GENERATOR_MAPPING.read_text(encoding="utf-8"))

    assert len(generated) == 19
    for metric_name, assets in generated.items():
        assert set(assets) == {"Line-1", "Line-2", "Line-3"}
        for asset_id, resource_id in assets.items():
            assert preset["linking"][asset_id][metric_name] == resource_id
