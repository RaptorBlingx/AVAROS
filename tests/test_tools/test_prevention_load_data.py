from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


def _load_prevention_load_data_module():
    core_module = types.ModuleType("core")
    initialization_module = types.ModuleType("core.initialization")
    utils_module = types.ModuleType("core.utils")
    datasources_module = types.ModuleType("core.utils.datasources")
    mongo_module = types.ModuleType("core.utils.datasources.mongo")

    class DataLoad:
        pass

    mongo_utils = types.SimpleNamespace(
        drop_all_collections=lambda db_name: None,
        mongo_username="prevention",
        mongo_pass="prevention",
        mongo_host="localhost",
        mongo_port="27017",
    )

    initialization_module.DataLoad = DataLoad
    mongo_module.mongo_utils = mongo_utils

    sys.modules["core"] = core_module
    sys.modules["core.initialization"] = initialization_module
    sys.modules["core.utils"] = utils_module
    sys.modules["core.utils.datasources"] = datasources_module
    sys.modules["core.utils.datasources.mongo"] = mongo_module

    module_path = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "prevention-addon"
        / "initilization"
        / "load_data.py"
    )
    spec = importlib.util.spec_from_file_location(
        "prevention_load_data",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_load_data_skips_all_empty_exports(tmp_path, monkeypatch) -> None:
    module = _load_prevention_load_data_module()

    for filename in module.DATA_FILES:
        (tmp_path / filename).write_text("[]", encoding="utf-8")

    insert_calls: list[tuple] = []
    monkeypatch.setattr(
        module,
        "_insert_to_mongo",
        lambda *args, **kwargs: insert_calls.append((args, kwargs)),
    )

    loader = module.AvarosDataLoad()
    loader.data_path = f"{tmp_path}/"

    loader.load_data()

    assert insert_calls == []


def test_load_data_ignores_empty_files_when_valid_data_exists(tmp_path, monkeypatch) -> None:
    module = _load_prevention_load_data_module()

    for filename in module.DATA_FILES:
        (tmp_path / filename).write_text("[]", encoding="utf-8")

    energy_record = [
        {
            "id": 1,
            "metric_name": "energy_per_unit",
            "asset_id": "Line-1",
            "timestamp": "2026-04-17T09:00:00.000Z",
            "value": 2.5,
            "unit": "kWh/unit",
        },
    ]
    (tmp_path / "energy_metrics.json").write_text(
        json.dumps(energy_record),
        encoding="utf-8",
    )

    captured_frames: list = []

    def _capture_insert(df, **kwargs):
        captured_frames.append((df.copy(), kwargs))

    monkeypatch.setattr(module, "_insert_to_mongo", _capture_insert)

    loader = module.AvarosDataLoad()
    loader.data_path = f"{tmp_path}/"

    loader.load_data()

    assert len(captured_frames) == 1
    df, kwargs = captured_frames[0]
    assert df["timestamp"].iloc[0].isoformat() == "2026-04-17T09:00:00+00:00"
    assert kwargs["collection_name"] == "kpi_metrics"
    assert kwargs["db_name"] == "init_data"