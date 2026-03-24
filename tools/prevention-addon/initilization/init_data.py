"""
AVAROS addon initialization data.

Defines all analysis entities (Model → Analysis → DeploymentConf)
for manufacturing KPI anomaly detection and drift monitoring.

Analysis Goals:
    - ENERGY_ANOMALY_CHECK:     Z-score anomaly detection on energy metrics
    - PRODUCTION_ANOMALY_CHECK: Z-score anomaly detection on production metrics
    - MATERIAL_ANOMALY_CHECK:   Z-score anomaly detection on material metrics
    - CO2_ANOMALY_CHECK:        Z-score anomaly detection on carbon metrics
    - SUPPLIER_ANOMALY_CHECK:   Z-score anomaly detection on supplier metrics
    - ENERGY_DRIFT_CHECK:       Linear drift analysis on energy metrics
    - PRODUCTION_DRIFT_CHECK:   Linear drift analysis on production metrics
    - MATERIAL_DRIFT_CHECK:     Linear drift analysis on material metrics
    - SUPPLIER_DRIFT_CHECK:     Linear drift analysis on supplier metrics
"""

from __future__ import annotations

from typing import Any


# =========================================================================
# Analysis Goal Definitions
# =========================================================================

ANOMALY_GOALS = [
    {
        'goal': 'ENERGY_ANOMALY_CHECK',
        'name': 'Energy Anomaly Detection',
        'dataset': 'EnergyMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'z_score_threshold': 2.0},
    },
    {
        'goal': 'PRODUCTION_ANOMALY_CHECK',
        'name': 'Production Anomaly Detection',
        'dataset': 'ProductionMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'z_score_threshold': 2.0},
    },
    {
        'goal': 'MATERIAL_ANOMALY_CHECK',
        'name': 'Material Anomaly Detection',
        'dataset': 'MaterialMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'z_score_threshold': 2.0},
    },
    {
        'goal': 'CO2_ANOMALY_CHECK',
        'name': 'Carbon Anomaly Detection',
        'dataset': 'CarbonMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'z_score_threshold': 2.0},
    },
    {
        'goal': 'SUPPLIER_ANOMALY_CHECK',
        'name': 'Supplier Anomaly Detection',
        'dataset': 'SupplierMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'z_score_threshold': 2.0},
    },
]

DRIFT_GOALS = [
    {
        'goal': 'ENERGY_DRIFT_CHECK',
        'name': 'Energy Drift Analysis',
        'dataset': 'EnergyMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'window_periods': 7},
    },
    {
        'goal': 'PRODUCTION_DRIFT_CHECK',
        'name': 'Production Drift Analysis',
        'dataset': 'ProductionMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'window_periods': 7},
    },
    {
        'goal': 'MATERIAL_DRIFT_CHECK',
        'name': 'Material Drift Analysis',
        'dataset': 'MaterialMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'window_periods': 7},
    },
    {
        'goal': 'SUPPLIER_DRIFT_CHECK',
        'name': 'Supplier Drift Analysis',
        'dataset': 'SupplierMetrics',
        'features': ['timestamp', 'value', 'metric_name', 'asset_id', 'unit'],
        'config': {'window_periods': 7},
    },
]


def addon_init_data(addon: Any, dataset_dict: dict) -> None:
    """
    Create all AVAROS analysis entities in PREVENTION.

    For each analysis goal, creates:
        1. Model — algorithm + resolver + configuration
        2. Analysis — goal + features + dataset + model
        3. DeploymentConf — deployment mode (ONE-OFF)

    Args:
        addon: PREVENTION addon instance with db_manager
        dataset_dict: Loaded datasets keyed by datasource name
    """
    my_analysis_goals: list[str] = []

    # Create anomaly detection analyses
    for goal_def in ANOMALY_GOALS:
        goal_name = goal_def['goal']
        my_analysis_goals.append(goal_name)

        model = addon.db_manager.Model.create_model(
            name=f"Model - {goal_def['name']}",
            algorithm="ZSCORE_ANOMALY",
            resolver='AddonDescriptiveResolver',
            model_data=goal_def['config'],
        )

        dataset_name = goal_def['dataset']
        dataset_ids = (
            [dataset_dict[dataset_name].id]
            if dataset_name in dataset_dict
            else []
        )

        analysis = addon.db_manager.Analysis.create_analysis(
            name=goal_def['name'],
            analytics_type="DESCRIPTIVE",
            analytics_goal=goal_name,
            input_features=goal_def['features'],
            preprocess_actions=[],
            datasets=dataset_ids,
            model=model.id,
            results_type_conf=["UI"],
        )

        addon.db_manager.DeploymentConf.create_deployment_conf(
            name=f"Deploy - {goal_name}",
            analysis=analysis.id,
            deployment_mode="ONE-OFF",
        )

    # Create drift monitoring analyses
    for goal_def in DRIFT_GOALS:
        goal_name = goal_def['goal']
        my_analysis_goals.append(goal_name)

        model = addon.db_manager.Model.create_model(
            name=f"Model - {goal_def['name']}",
            algorithm="LINEAR_DRIFT",
            resolver='AddonDescriptiveResolver',
            model_data=goal_def['config'],
        )

        dataset_name = goal_def['dataset']
        dataset_ids = (
            [dataset_dict[dataset_name].id]
            if dataset_name in dataset_dict
            else []
        )

        analysis = addon.db_manager.Analysis.create_analysis(
            name=goal_def['name'],
            analytics_type="DESCRIPTIVE",
            analytics_goal=goal_name,
            input_features=goal_def['features'],
            preprocess_actions=[],
            datasets=dataset_ids,
            model=model.id,
            results_type_conf=["UI"],
        )

        addon.db_manager.DeploymentConf.create_deployment_conf(
            name=f"Deploy - {goal_name}",
            analysis=analysis.id,
            deployment_mode="ONE-OFF",
        )
