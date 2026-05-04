"""
AVAROS addon build analysis.

Implements z-score anomaly detection, linear drift monitoring, and a modest
linear KPI forecast for PREVENTION analytics.
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
        if model_type == "LINEAR_FORECAST":
            return _linear_forecast(data_df, config)

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


def _linear_forecast(data_df, config):
    """Explainable linear KPI forecast per metric+asset group."""
    horizon_periods = int(config.get("horizon_periods", 7))
    min_points = int(config.get("min_points", 10))
    results = []

    for (metric, asset), group in data_df.groupby(["metric_name", "asset_id"]):
        group = group.sort_values("timestamp")
        values = group["value"].astype(float).values
        training_points = len(values)
        if training_points < min_points:
            results.append({
                "metric_name": str(metric),
                "asset_id": str(asset),
                "horizon_periods": horizon_periods,
                "predicted_value": None,
                "confidence": 0.0,
                "fit_quality": 0.0,
                "training_points": training_points,
                "method_name": "linear_forecast",
                "forecast_timestamp": "",
                "available": False,
                "description": (
                    f"Insufficient data for {metric} on {asset}: "
                    f"{training_points} points available, {min_points} required."
                ),
                "recommended_action": "Collect more history before using this forecast.",
            })
            continue

        x = np.arange(training_points, dtype=float)
        a_matrix = np.vstack([x, np.ones(training_points)]).T
        slope, intercept = np.linalg.lstsq(a_matrix, values, rcond=None)[0]
        predicted = float(slope * (training_points + horizon_periods) + intercept)
        predicted = max(predicted, 0.0)

        fitted = slope * x + intercept
        ss_res = np.sum((values - fitted) ** 2)
        ss_tot = np.sum((values - np.mean(values)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
        fit_quality = max(0.0, min(1.0, float(r_squared)))
        confidence = max(0.1, min(0.95, fit_quality * min(training_points / 30.0, 1.0)))
        last_timestamp = group["timestamp"].iloc[-1]
        forecast_timestamp = last_timestamp + pd.to_timedelta(
            horizon_periods,
            unit="D",
        )

        direction = "stable"
        if abs(slope) > 0.001:
            direction = "increasing" if slope > 0 else "decreasing"

        action = "Monitor this KPI and review operational drivers if the trend continues."
        if direction == "increasing":
            action = "Review the main operational contributors before this increase becomes material."
        elif direction == "decreasing":
            action = "Verify whether this decrease is expected and beneficial for the process."

        results.append({
            "metric_name": str(metric),
            "asset_id": str(asset),
            "horizon_periods": horizon_periods,
            "predicted_value": round(predicted, 6),
            "confidence": round(float(confidence), 4),
            "fit_quality": round(float(fit_quality), 4),
            "training_points": training_points,
            "method_name": "linear_forecast",
            "forecast_timestamp": str(forecast_timestamp),
            "available": True,
            "description": (
                f"{metric} on {asset}: {direction} forecast "
                f"(slope={slope:.6f}, R²={fit_quality:.4f})"
            ),
            "recommended_action": action,
        })

    if not results:
        results.append({
            "metric_name": "",
            "asset_id": "",
            "horizon_periods": horizon_periods,
            "predicted_value": None,
            "confidence": 0.0,
            "fit_quality": 0.0,
            "training_points": 0,
            "method_name": "linear_forecast",
            "forecast_timestamp": "",
            "available": False,
            "description": "No forecast data",
            "recommended_action": None,
        })

    return pd.DataFrame(results)
