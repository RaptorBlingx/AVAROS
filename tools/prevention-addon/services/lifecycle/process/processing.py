"""
AVAROS addon data processing service.

Handles any custom pre-processing needed for manufacturing
KPI data before it enters the PREVENTION analytics pipeline.
"""

from __future__ import annotations

import pandas as pd


def preprocess_metric_data(data: pd.DataFrame) -> pd.DataFrame:
    """
    Pre-process raw metric data for PREVENTION analysis.

    Ensures consistent column types and handles missing values.

    Args:
        data: Raw metric data from RENERYO export

    Returns:
        Cleaned DataFrame ready for analysis algorithms
    """
    if data.empty:
        return data

    result = data.copy()

    # Ensure timestamp column is datetime
    if 'timestamp' in result.columns:
        result['timestamp'] = pd.to_datetime(
            result['timestamp'], errors='coerce',
        )

    # Ensure value column is numeric
    if 'value' in result.columns:
        result['value'] = pd.to_numeric(
            result['value'], errors='coerce',
        )

    # Drop rows with missing critical fields
    result = result.dropna(subset=['timestamp', 'value'])

    return result
