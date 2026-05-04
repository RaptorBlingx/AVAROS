from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd


def _load_build_analysis_module():
    core_module = types.ModuleType("core")
    services_module = types.ModuleType("core.services")
    errors_module = types.ModuleType("core.services.errors")
    prevention_errors_module = types.ModuleType("core.services.errors.prevention_errors")
    lifecycle_module = types.ModuleType("core.services.lifecycle")
    build_package = types.ModuleType("core.services.lifecycle.build")
    build_module = types.ModuleType("core.services.lifecycle.build.build_analysis")
    utils_module = types.ModuleType("core.utils")
    datasources_module = types.ModuleType("core.utils.datasources")
    mongo_module = types.ModuleType("core.utils.datasources.mongo")

    class PreventionError(Exception):
        pass

    class BuildAnalysis:
        def build(self, *args, **kwargs):
            return None

    prevention_errors_module.PreventionError = PreventionError
    build_module.BuildAnalysis = BuildAnalysis
    mongo_module.mongo_utils = types.SimpleNamespace()

    sys.modules["core"] = core_module
    sys.modules["core.services"] = services_module
    sys.modules["core.services.errors"] = errors_module
    sys.modules["core.services.errors.prevention_errors"] = prevention_errors_module
    sys.modules["core.services.lifecycle"] = lifecycle_module
    sys.modules["core.services.lifecycle.build"] = build_package
    sys.modules["core.services.lifecycle.build.build_analysis"] = build_module
    sys.modules["core.utils"] = utils_module
    sys.modules["core.utils.datasources"] = datasources_module
    sys.modules["core.utils.datasources.mongo"] = mongo_module

    module_path = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "prevention-addon"
        / "services"
        / "lifecycle"
        / "build"
        / "build_analysis.py"
    )
    spec = importlib.util.spec_from_file_location(
        "prevention_build_analysis",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _forecast_frame(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "metric_name": ["energy_per_unit"] * len(values),
            "asset_id": ["Line-1"] * len(values),
            "timestamp": pd.date_range("2026-04-01", periods=len(values), freq="D"),
            "value": values,
        },
    )


def test_linear_forecast_with_enough_data_predicts_future_value() -> None:
    module = _load_build_analysis_module()

    result = module._linear_forecast(
        _forecast_frame([10, 11, 12, 13, 14, 15, 16, 17, 18, 19]),
        {"horizon_periods": 7, "min_points": 3},
    )
    row = result.iloc[0].to_dict()

    assert row["available"] is True
    assert row["metric_name"] == "energy_per_unit"
    assert row["asset_id"] == "Line-1"
    assert row["predicted_value"] > 19
    assert row["training_points"] == 10
    assert row["method_name"] == "linear_forecast"


def test_linear_forecast_returns_unavailable_when_insufficient_data() -> None:
    module = _load_build_analysis_module()

    result = module._linear_forecast(
        _forecast_frame([10, 11]),
        {"horizon_periods": 7, "min_points": 3},
    )
    row = result.iloc[0].to_dict()

    assert row["available"] is False
    assert row["predicted_value"] is None
    assert row["training_points"] == 2
    assert "Insufficient data" in row["description"]


def test_linear_forecast_flat_data_has_high_fit_quality() -> None:
    module = _load_build_analysis_module()

    result = module._linear_forecast(
        _forecast_frame([5.0] * 12),
        {"horizon_periods": 7, "min_points": 3},
    )
    row = result.iloc[0].to_dict()

    assert row["available"] is True
    assert row["predicted_value"] == 5.0
    assert row["fit_quality"] == 1.0


def test_linear_forecast_noisy_data_still_returns_bounded_confidence() -> None:
    module = _load_build_analysis_module()

    result = module._linear_forecast(
        _forecast_frame([10, 14, 9, 15, 11, 13, 12, 16, 10, 17, 12, 18]),
        {"horizon_periods": 7, "min_points": 3},
    )
    row = result.iloc[0].to_dict()

    assert row["available"] is True
    assert 0.1 <= row["confidence"] <= 0.95
    assert 0.0 <= row["fit_quality"] <= 1.0
