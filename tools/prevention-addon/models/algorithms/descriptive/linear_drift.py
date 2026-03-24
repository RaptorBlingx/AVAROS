"""
Linear Drift Analysis Algorithm for PREVENTION.

Implements drift detection using linear regression on time-series
data to identify gradual KPI degradation or improvement. Follows
PREVENTION's SimpleDescriptiveAlgorithm pattern.

Detection Method:
    Fit a linear regression (y = mx + b) to the recent N periods.
    If the slope is statistically significant (based on R² and
    magnitude), report drift direction and rate.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

try:
    from prevention.models.algorithms.base import SimpleDescriptiveAlgorithm
except ImportError:
    class SimpleDescriptiveAlgorithm:
        def __init__(self, algorithm_function=None, model_data=None):
            self.algorithm_function = algorithm_function
            self.model_data = model_data or {}


def _compute_drift_direction(slope: float, r_squared: float) -> str:
    """Classify drift direction from regression slope and R²."""
    if r_squared < 0.3:
        return "stable"
    if slope > 0:
        return "increasing"
    return "decreasing"


def linear_drift_detect(
    data: pd.DataFrame,
    window_periods: int = 7,
) -> pd.DataFrame:
    """
    Detect gradual drift in time-series data using linear regression.

    Args:
        data: DataFrame with 'value' and 'timestamp' columns
        window_periods: Number of recent periods to analyze

    Returns:
        DataFrame with drift analysis results:
            - has_drift, drift_direction, drift_rate
            - r_squared, periods_analyzed, description
    """
    if data.empty or 'value' not in data.columns:
        return pd.DataFrame([{
            'has_drift': False,
            'drift_direction': 'stable',
            'drift_rate': 0.0,
            'r_squared': 0.0,
            'periods_analyzed': 0,
            'description': 'Insufficient data for drift analysis.',
        }])

    # Sort by timestamp and take the most recent N periods
    sorted_data = data.sort_values('timestamp', ascending=True)
    recent = sorted_data.tail(window_periods)

    if len(recent) < 3:
        return pd.DataFrame([{
            'has_drift': False,
            'drift_direction': 'stable',
            'drift_rate': 0.0,
            'r_squared': 0.0,
            'periods_analyzed': len(recent),
            'description': 'Insufficient data points for drift analysis.',
        }])

    values = recent['value'].astype(float).values
    x = np.arange(len(values), dtype=float)

    # Linear regression via least squares
    x_mean = x.mean()
    y_mean = values.mean()
    ss_xy = np.sum((x - x_mean) * (values - y_mean))
    ss_xx = np.sum((x - x_mean) ** 2)

    if ss_xx == 0:
        slope = 0.0
        r_squared = 0.0
    else:
        slope = ss_xy / ss_xx
        ss_yy = np.sum((values - y_mean) ** 2)
        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy > 0 else 0.0

    direction = _compute_drift_direction(slope, r_squared)
    has_drift = direction != "stable"

    description = (
        f"Linear trend analysis over {len(recent)} periods: "
        f"slope={slope:.4f}/period, R²={r_squared:.3f}. "
        f"Direction: {direction}."
    )

    return pd.DataFrame([{
        'has_drift': has_drift,
        'drift_direction': direction,
        'drift_rate': round(slope, 4),
        'r_squared': round(r_squared, 3),
        'periods_analyzed': len(recent),
        'description': description,
    }])


class LINEAR_DRIFT(SimpleDescriptiveAlgorithm):
    """
    Linear drift detection for manufacturing KPIs.

    Configuration (model_data):
        window_periods: int — Number of recent periods to analyze
                              (default: 7)
    """

    def __init__(
        self,
        algorithm_function: Optional[callable] = linear_drift_detect,
        model_data: Optional[dict] = None,
    ):
        super().__init__(
            algorithm_function=algorithm_function,
            model_data=model_data,
        )
