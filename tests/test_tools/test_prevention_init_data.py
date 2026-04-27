from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_prevention_init_data_module():
    core_module = types.ModuleType("core")
    initialization_module = types.ModuleType("core.initialization")
    utils_module = types.ModuleType("core.utils")
    datasources_module = types.ModuleType("core.utils.datasources")
    mongo_module = types.ModuleType("core.utils.datasources.mongo")

    addons_module = types.ModuleType("addons")
    avaros_module = types.ModuleType("addons.avaros")
    services_module = types.ModuleType("addons.avaros.services")
    lifecycle_module = types.ModuleType("addons.avaros.services.lifecycle")
    build_package_module = types.ModuleType("addons.avaros.services.lifecycle.build")
    build_module = types.ModuleType("addons.avaros.services.lifecycle.build.build_analysis")

    class Initialization:
        pass

    class AvarosBuildAnalysis:
        def build(self, analysis_id, results_type):
            return None

    mongo_utils = types.SimpleNamespace(
        mongo_username="prevention",
        mongo_pass="prevention",
        mongo_host="localhost",
        mongo_port="27017",
        create_dataset=lambda **kwargs: types.SimpleNamespace(inserted_id="dataset-id"),
        get_dataset_with_id=lambda dataset_id: {"_id": dataset_id},
        create_model=lambda **kwargs: types.SimpleNamespace(inserted_id="model-id"),
        get_model_with_id=lambda model_id: {"_id": model_id, "type": "ZSCORE_ANOMALY"},
        create_analysis=lambda **kwargs: types.SimpleNamespace(inserted_id="analysis-id"),
        get_analysis_with_id=lambda analysis_id: {"_id": analysis_id},
    )

    initialization_module.Initialization = Initialization
    mongo_module.mongo_utils = mongo_utils
    build_module.AvarosBuildAnalysis = AvarosBuildAnalysis

    sys.modules["core"] = core_module
    sys.modules["core.initialization"] = initialization_module
    sys.modules["core.utils"] = utils_module
    sys.modules["core.utils.datasources"] = datasources_module
    sys.modules["core.utils.datasources.mongo"] = mongo_module
    sys.modules["addons"] = addons_module
    sys.modules["addons.avaros"] = avaros_module
    sys.modules["addons.avaros.services"] = services_module
    sys.modules["addons.avaros.services.lifecycle"] = lifecycle_module
    sys.modules["addons.avaros.services.lifecycle.build"] = build_package_module
    sys.modules["addons.avaros.services.lifecycle.build.build_analysis"] = build_module

    module_path = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "prevention-addon"
        / "initilization"
        / "init_data.py"
    )
    spec = importlib.util.spec_from_file_location(
        "prevention_init_data",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_init_data_skips_analysis_build_when_no_records(monkeypatch) -> None:
    module = _load_prevention_init_data_module()

    init = module.AvarosInit()
    chain_calls: list[dict] = []

    monkeypatch.setattr(init, "_count_source_records", lambda: 0)
    monkeypatch.setattr(
        init,
        "_create_analysis_chain",
        lambda **kwargs: chain_calls.append(kwargs),
    )

    init.init_data()

    assert chain_calls == []


def test_init_data_builds_all_goals_when_records_exist(monkeypatch) -> None:
    module = _load_prevention_init_data_module()

    init = module.AvarosInit()
    chain_calls: list[dict] = []

    monkeypatch.setattr(init, "_count_source_records", lambda: 3)
    monkeypatch.setattr(
        init,
        "_create_analysis_chain",
        lambda **kwargs: chain_calls.append(kwargs),
    )

    init.init_data()

    assert len(chain_calls) == len(module.ANOMALY_GOALS) + len(module.DRIFT_GOALS)