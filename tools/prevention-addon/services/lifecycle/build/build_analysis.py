"""
AVAROS addon build analysis.

Implements z-score anomaly detection and linear drift monitoring
as PREVENTION DESCRIPTIVE algorithms.
"""

import numpy as np
import pandas as pd
from core.services.errors.prevention_errors import PreventionError
from core.services.lifecycle.build.build_analysis import BuildAnalysis
from core.utils.datasources.mongo import mongo_utils


class AvarosBuildAnalysis(BuildAnalysis):

    def build(self, analysis_id, results_type):
        super().build(
            analysis_id, results_type,
            self.preprocess_dataframe, self.create_model, self.run_model,
        )

    def create_model(self, model, data_df, analysis_goal):
        pass

    def run_model(self, data_df, model):
        data_df.dropna(inplace=True)
        model_type = model["type"]
        config = model.get("model_data", {})

        metric_filter = config.get("metric_filter")
        if metric_filter and "metric_name" in data_df.columns:
            data_df = data_df[data_df["metric_name"].isin(metric_filter)]

        if model_type == "ZSCORE_ANOMALY":
            return _zscore_anomaly_detect(data_df, config)
        if model_type == "LINEAR_DRIFT":
            return _linear_drift_detect(data_df, config)

        raise PreventionError(
            f"Unknown AVAROS model type: {model_type}",
            300, keyword="model_type",
        )

    def preprocess_dataframe(self, data_df, preprocess_actions_dict):
        for action in preprocess_actions_dict:
            action_type = action.get("preprocess_action", "")
            if action_type in ("PARSE_DATETIME", "DATETIME_TO_DATE"):
                col = action.get("in_attr", "timestamp")
                if col in data_df.columns:
                    data_df[col] = pd.to_datetime(
                        data_df[col], errors="coerce",
                    )
        if "value" in data_df.columns:
            data_df["value"] = pd.to_numeric(
                data_df["value"], errors="coerce",
            )
        data_df = data_df.dropna(subset=["timestamp", "value"])
        return data_df


def _zscore_anomaly_detect(data_df, config):
    """Z-score anomaly detection per metric+asset group."""
    threshold = config.get("z_score_threshold", 2.0)
    results = []

    for (metric, asset), group in data_df.groupby(["metric_name", "asset_id"]):
        values = group["value"].astype(float)
        if len(values) < 3:
            continue
        mean_val = values.mean()
        std_val = values.std()
        if std_val == 0:
            continue

        for _, row in group.iterrows():
            z = abs((float(row["value"]) - mean_val) / std_val)
            if z > threshold:
                if z < 2.5:
                    severity = "low"
                elif z < 3.0:
                    severity = "medium"
                elif z < 4.0:
                    severity = "high"
                else:
                    severity = "critical"
                anomaly_type = "spike" if float(row["value"]) > mean_val else "dip"
                results.append({
                    "timestamp": str(row.get("timestamp", "")),
                    "value": float(row["value"]),
                    "z_score": round(z, 4),
                    "is_anomalous": True,
                    "severity": severity,
                    "anomaly_type": anomaly_type,
                    "metric_name": str(metric),
                    "asset_id": str(asset),
                })

    if not results:
        results.append({
            "timestamp": "", "value": 0, "z_score": 0,
            "is_anomalous": False, "severity": "none",
            "anomaly_type": "none", "metric_name": "",
            "asset_id": "",
        })

    return pd.DataFrame(results)


def _linear_drift_detect(data_df, config):
    """Linear regression drift detection per metric+asset group."""
    window_periods = config.get("window_periods", 7)
    results = []

    for (metric, asset), group in data_df.groupby(["metric_name", "asset_id"]):
        group = group.sort_values("timestamp").tail(window_periods * 96)
        values = group["value"].astype(float).values
        if len(values) < 10:
            continue

        x = np.arange(len(values), dtype=float)
        a_matrix = np.vstack([x, np.ones(len(x))]).T
        slope, _intercept = np.linalg.lstsq(a_matrix, values, rcond=None)[0]

        ss_res = np.sum((values - (slope * x + _intercept)) ** 2)
        ss_tot = np.sum((values - np.mean(values)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        has_drift = abs(slope) > 0.001 and r_squared > 0.1
        direction = "stable"
        if has_drift:
            direction = "increasing" if slope > 0 else "decreasing"

        results.append({
            "metric_name": str(metric),
            "asset_id": str(asset),
            "has_drift": has_drift,
            "drift_direction": direction,
            "drift_rate": round(float(slope), 6),
            "r_squared": round(float(r_squared), 4),
            "periods_analyzed": len(values),
            "description": (
                f"{metric} on {asset}: {direction} "
                f"(slope={slope:.6f}, R²={r_squared:.4f})"
            ),
        })

    if not results:
        results.append({
            "metric_name": "", "asset_id": "",
            "has_drift": False, "drift_direction": "stable",
            "drift_rate": 0, "r_squared": 0,
            "periods_analyzed": 0, "description": "No data",
        })

    return pd.DataFrame(results)
