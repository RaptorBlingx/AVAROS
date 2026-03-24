"""
Z-Score Anomaly Detection Algorithm for PREVENTION.

Implements statistical anomaly detection using z-score analysis on
manufacturing KPI time-series data. Follows PREVENTION's
SimpleDescriptiveAlgorithm pattern.

Detection Method:
    For each data point, compute z-score = (value - mean) / std_dev.
    Points exceeding the configured threshold are flagged as anomalies.
    Severity is assigned based on z-score magnitude:
        - low:      threshold <= |z| < threshold + 1
        - medium:   threshold + 1 <= |z| < threshold + 2
        - high:     threshold + 2 <= |z| < threshold + 3
        - critical: |z| >= threshold + 3
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

try:
    from prevention.models.algorithms.base import SimpleDescriptiveAlgorithm
except ImportError:
    # Standalone testing — define minimal stub
    class SimpleDescriptiveAlgorithm:
        def __init__(self, algorithm_function=None, model_data=None):
            self.algorithm_function = algorithm_function
            self.model_data = model_data or {}


def _classify_severity(z_score: float, threshold: float) -> str:
    """Classify anomaly severity based on z-score magnitude."""
    abs_z = abs(z_score)
    if abs_z >= threshold + 3:
        return "critical"
    if abs_z >= threshold + 2:
        return "high"
    if abs_z >= threshold + 1:
        return "medium"
    return "low"


def _classify_anomaly_type(z_score: float) -> str:
    """Classify anomaly type based on z-score direction."""
    return "spike" if z_score > 0 else "dip"


def zscore_anomaly_detect(
    data: pd.DataFrame,
    z_score_threshold: float = 2.0,
) -> pd.DataFrame:
    """
    Detect anomalies in time-series data using z-score analysis.

    Args:
        data: DataFrame with 'value' and 'timestamp' columns
        z_score_threshold: Standard deviation threshold for flagging

    Returns:
        DataFrame with anomaly detection results:
            - timestamp, value, z_score, is_anomalous
            - severity, anomaly_type, metric_name, asset_id
    """
    if data.empty or 'value' not in data.columns:
        return pd.DataFrame(columns=[
            'timestamp', 'value', 'z_score', 'is_anomalous',
            'severity', 'anomaly_type', 'metric_name', 'asset_id',
        ])

    values = data['value'].astype(float)
    mean_val = values.mean()
    std_val = values.std()

    # Avoid division by zero for constant series
    if std_val == 0 or pd.isna(std_val):
        result = data.copy()
        result['z_score'] = 0.0
        result['is_anomalous'] = False
        result['severity'] = 'none'
        result['anomaly_type'] = None
        return result

    result = data.copy()
    result['z_score'] = (values - mean_val) / std_val
    result['is_anomalous'] = result['z_score'].abs() > z_score_threshold
    result['severity'] = result.apply(
        lambda row: _classify_severity(row['z_score'], z_score_threshold)
        if row['is_anomalous'] else 'none',
        axis=1,
    )
    result['anomaly_type'] = result.apply(
        lambda row: _classify_anomaly_type(row['z_score'])
        if row['is_anomalous'] else None,
        axis=1,
    )

    return result


class ZSCORE_ANOMALY(SimpleDescriptiveAlgorithm):
    """
    Z-score anomaly detection for manufacturing KPIs.

    Configuration (model_data):
        z_score_threshold: float — Standard deviations for flagging
                                   (default: 2.0)
    """

    def __init__(
        self,
        algorithm_function: Optional[callable] = zscore_anomaly_detect,
        model_data: Optional[dict] = None,
    ):
        super().__init__(
            algorithm_function=algorithm_function,
            model_data=model_data,
        )
