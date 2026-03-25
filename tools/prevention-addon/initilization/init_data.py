"""
AVAROS addon initialization.

Creates Dataset, Model, Analysis, and Deployment entities for
manufacturing KPI anomaly detection and drift monitoring.
"""

from core.initialization import Initialization
from core.utils.datasources.mongo import mongo_utils
from addons.avaros.services.lifecycle.build.build_analysis import (
    AvarosBuildAnalysis,
)


METRIC_ATTRIBUTES = [
    "id", "timestamp", "value", "metric_name", "asset_id", "unit",
]

ANOMALY_GOALS = [
    ("ENERGY_ANOMALY_CHECK", "Energy Anomaly Detection",
     "energy_metrics", 2.0),
    ("PRODUCTION_ANOMALY_CHECK", "Production Anomaly Detection",
     "production_metrics", 2.0),
    ("MATERIAL_ANOMALY_CHECK", "Material Anomaly Detection",
     "material_metrics", 2.0),
    ("CO2_ANOMALY_CHECK", "Carbon Anomaly Detection",
     "carbon_metrics", 2.0),
    ("SUPPLIER_ANOMALY_CHECK", "Supplier Anomaly Detection",
     "supplier_metrics", 2.0),
]

DRIFT_GOALS = [
    ("ENERGY_DRIFT_CHECK", "Energy Drift Analysis",
     "energy_metrics", 7),
    ("PRODUCTION_DRIFT_CHECK", "Production Drift Analysis",
     "production_metrics", 7),
    ("MATERIAL_DRIFT_CHECK", "Material Drift Analysis",
     "material_metrics", 7),
    ("SUPPLIER_DRIFT_CHECK", "Supplier Drift Analysis",
     "supplier_metrics", 7),
]

CATEGORY_COLLECTIONS = {
    "energy_metrics": "EnergyMetrics",
    "production_metrics": "ProductionMetrics",
    "material_metrics": "MaterialMetrics",
    "carbon_metrics": "CarbonMetrics",
    "supplier_metrics": "SupplierMetrics",
}


class AvarosInit(Initialization):

    def init_data(self):
        datasets = {}
        for collection_name, display_name in CATEGORY_COLLECTIONS.items():
            result = mongo_utils.create_dataset(
                name=display_name,
                db_name="init_data",
                collection_name=collection_name,
                id_name="id",
                last_id=0,
                attributes=METRIC_ATTRIBUTES,
            )
            datasets[collection_name] = mongo_utils.get_dataset_with_id(
                result.inserted_id,
            )

        builder = AvarosBuildAnalysis()

        for goal, name, ds_key, threshold in ANOMALY_GOALS:
            self._create_analysis(
                builder, datasets, goal, name, ds_key,
                model_type="ZSCORE_ANOMALY",
                model_data={"z_score_threshold": threshold},
            )

        for goal, name, ds_key, window in DRIFT_GOALS:
            self._create_analysis(
                builder, datasets, goal, name, ds_key,
                model_type="LINEAR_DRIFT",
                model_data={"window_periods": window},
            )

    def _create_analysis(
        self,
        builder,
        datasets,
        goal,
        name,
        ds_key,
        model_type,
        model_data,
    ):
        dataset = datasets.get(ds_key)
        if not dataset:
            print(f"[AVAROS] Skipping {goal}: no dataset for {ds_key}")
            return

        model_result = mongo_utils.create_model(
            name=f"Model - {name}",
            model_type=model_type,
            model_data=model_data,
            status="CREATED",
            train=False,
            input_attributes=["timestamp", "value", "metric_name", "asset_id"],
        )
        model = mongo_utils.get_model_with_id(model_result.inserted_id)
        if not model:
            return

        analysis_result = mongo_utils.create_analysis(
            name=name,
            analytics_type="DESCRIPTIVE",
            analytics_goal=goal,
            input_features=METRIC_ATTRIBUTES,
            preprocess_actions=[],
            dataset=dataset["_id"],
            model=model["_id"],
            results_type_conf="UI",
        )

        try:
            builder.build(analysis_result.inserted_id, "UI")
        except Exception as exc:
            print(f"[AVAROS] Build failed for {goal}: {exc}")
