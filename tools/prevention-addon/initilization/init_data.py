"""AVAROS initialization for PREVENTION platform.

Creates the Dataset → Model → Analysis entity chain for all 9 analytics
goals (5 anomaly + 4 drift) in MongoDB. Follows PREVENTION's
Initialization ABC pattern.
"""

import urllib.parse

from core.initialization import Initialization
from core.utils.datasources.mongo import mongo_utils
from addons.avaros.services.lifecycle.build.build_analysis import (
    AvarosBuildAnalysis,
)
from pymongo import MongoClient


# All data columns available in the KPI time-series
KPI_ATTRIBUTES = [
    "id", "metric_name", "asset_id", "timestamp", "value",
]

# Standard preprocess: parse timestamp column
PREPROCESS_ACTIONS = [
    {
        "in_attr": "timestamp",
        "out_attr": "timestamp",
        "preprocess_action": "PARSE_DATETIME",
    },
]

# Analytics goals: (name, goal_key, model_type, model_config)
# NOTE: z_score_threshold is set to 1.0 here so PREVENTION pre-computes
# ALL potential anomalies. The actual user-configured sensitivity threshold
# is applied client-side by HttpPreventionClient._parse_anomaly_results().
ANOMALY_GOALS = [
    ("Energy Anomaly Check", "ENERGY_ANOMALY_CHECK", "ZSCORE_ANOMALY",
     {"z_score_threshold": 1.0, "metric_filter": ["energy_per_unit", "energy_total", "peak_demand", "peak_tariff_exposure"]}),
    ("Production Anomaly Check", "PRODUCTION_ANOMALY_CHECK", "ZSCORE_ANOMALY",
     {"z_score_threshold": 1.0, "metric_filter": ["oee", "throughput", "cycle_time", "changeover_time"]}),
    ("Material Anomaly Check", "MATERIAL_ANOMALY_CHECK", "ZSCORE_ANOMALY",
     {"z_score_threshold": 1.0, "metric_filter": ["scrap_rate", "rework_rate", "material_efficiency", "recycled_content"]}),
    ("CO2 Anomaly Check", "CO2_ANOMALY_CHECK", "ZSCORE_ANOMALY",
     {"z_score_threshold": 1.0, "metric_filter": ["co2_per_unit", "co2_total", "co2_per_batch"]}),
    ("Supplier Anomaly Check", "SUPPLIER_ANOMALY_CHECK", "ZSCORE_ANOMALY",
     {"z_score_threshold": 1.0, "metric_filter": ["supplier_lead_time", "supplier_defect_rate", "supplier_on_time", "supplier_co2_per_kg"]}),
]

DRIFT_GOALS = [
    ("Energy Drift Check", "ENERGY_DRIFT_CHECK", "LINEAR_DRIFT",
     {"window_periods": 7, "metric_filter": ["energy_per_unit", "energy_total", "peak_demand", "peak_tariff_exposure"]}),
    ("Production Drift Check", "PRODUCTION_DRIFT_CHECK", "LINEAR_DRIFT",
     {"window_periods": 7, "metric_filter": ["oee", "throughput", "cycle_time", "changeover_time"]}),
    ("Material Drift Check", "MATERIAL_DRIFT_CHECK", "LINEAR_DRIFT",
     {"window_periods": 7, "metric_filter": ["scrap_rate", "rework_rate", "material_efficiency", "recycled_content"]}),
    ("CO2 Drift Check", "CO2_DRIFT_CHECK", "LINEAR_DRIFT",
     {"window_periods": 7, "metric_filter": ["co2_per_unit", "co2_total", "co2_per_batch"]}),
    ("Supplier Drift Check", "SUPPLIER_DRIFT_CHECK", "LINEAR_DRIFT",
     {"window_periods": 7, "metric_filter": ["supplier_lead_time", "supplier_defect_rate", "supplier_on_time", "supplier_co2_per_kg"]}),
]


class AvarosInit(Initialization):
    """Create PREVENTION entities for AVAROS analytics goals."""

    def init_data(self):
        """Create Dataset → Model → Analysis chain for all goals."""
        dataset = self._create_dataset()
        if dataset is None:
            print("[AVAROS] Failed to create dataset — aborting init")
            return

        source_record_count = self._count_source_records()
        if source_record_count == 0:
            print("[AVAROS] No KPI records found — skipping analytics initialization")
            return

        all_goals = ANOMALY_GOALS + DRIFT_GOALS
        for name, goal_key, model_type, config in all_goals:
            self._create_analysis_chain(
                dataset=dataset,
                name=name,
                goal_key=goal_key,
                model_type=model_type,
                config=config,
            )
        print(f"[AVAROS] Initialized {len(all_goals)} analytics goals")

    def _count_source_records(self) -> int:
        """Return the number of KPI rows currently loaded into MongoDB."""
        client = MongoClient(
            f"mongodb://{mongo_utils.mongo_username}:"
            f"{urllib.parse.quote_plus(mongo_utils.mongo_pass)}"
            f"@{mongo_utils.mongo_host}:{int(mongo_utils.mongo_port)}/"
        )
        try:
            return int(client["init_data"]["kpi_metrics"].count_documents({}))
        finally:
            client.close()

    def _create_dataset(self) -> dict | None:
        """Create the shared KPI metrics dataset entity."""
        result = mongo_utils.create_dataset(
            name="AVAROS KPI Metrics",
            db_name="init_data",
            collection_name="kpi_metrics",
            id_name="id",
            last_id=0,
            attributes=KPI_ATTRIBUTES,
        )
        return mongo_utils.get_dataset_with_id(result.inserted_id)

    def _create_analysis_chain(
        self,
        dataset: dict,
        name: str,
        goal_key: str,
        model_type: str,
        config: dict,
    ) -> None:
        """Create Model → Analysis → build for a single analytics goal."""
        model_result = mongo_utils.create_model(
            name=f"{name} Model",
            model_type=model_type,
            model_data=config,
            status="CREATED",
            train=False,
            input_attributes=KPI_ATTRIBUTES,
        )
        model = mongo_utils.get_model_with_id(model_result.inserted_id)
        if model is None:
            print(f"[AVAROS] Failed to create model for {goal_key}")
            return

        analysis_result = mongo_utils.create_analysis(
            name=name,
            analytics_type="DESCRIPTIVE",
            analytics_goal=goal_key,
            input_features=KPI_ATTRIBUTES,
            preprocess_actions=PREPROCESS_ACTIONS,
            dataset=dataset["_id"],
            model=model["_id"],
            results_type_conf="DA",
        )
        analysis = mongo_utils.get_analysis_with_id(
            analysis_result.inserted_id,
        )
        if analysis is None:
            print(f"[AVAROS] Failed to create analysis for {goal_key}")
            return

        AvarosBuildAnalysis().build(analysis_result.inserted_id, "DA")
        print(f"[AVAROS] Built analysis: {goal_key}")
