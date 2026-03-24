"""
AVAROS Addon for PREVENTION Platform.

Provides anomaly detection and drift monitoring for manufacturing KPIs.
Implements z-score anomaly detection and linear drift analysis as
PREVENTION DESCRIPTIVE algorithms.

Addon name 'avaros' determines:
  - MongoDB collection prefix
  - GraphQL endpoint URL (/avaros)
  - Internal addon identifier
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

my_name = 'avaros'


def load_from_json(datasource: Any, data_path: str) -> dict:
    """
    Load raw data from a JSON file for PREVENTION ingestion.

    Args:
        datasource: PREVENTION SimpleDataSource instance
        data_path: Absolute path to the addon's data directory

    Returns:
        Dictionary of loaded data records
    """
    import json
    import os

    file_path = os.path.join(data_path, datasource.file_name)
    if not os.path.exists(file_path):
        logger.warning("Data file not found: %s", file_path)
        return {}

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


# =========================================================================
# Datasource Definitions
# =========================================================================

# Each datasource maps to a JSON file exported by the AVAROS data-sync
# pipeline from RENERYO. Files are written to the shared Docker volume
# mounted at data/.

simple_datasources = [
    {
        'name': 'EnergyMetrics',
        'file_name': 'energy_metrics.json',
        'source_type': 'json',
        'identifier': 'id',
        'date_column': 'timestamp',
        'last_index': 0,
        'load_function': load_from_json,
    },
    {
        'name': 'ProductionMetrics',
        'file_name': 'production_metrics.json',
        'source_type': 'json',
        'identifier': 'id',
        'date_column': 'timestamp',
        'last_index': 0,
        'load_function': load_from_json,
    },
    {
        'name': 'MaterialMetrics',
        'file_name': 'material_metrics.json',
        'source_type': 'json',
        'identifier': 'id',
        'date_column': 'timestamp',
        'last_index': 0,
        'load_function': load_from_json,
    },
    {
        'name': 'CarbonMetrics',
        'file_name': 'carbon_metrics.json',
        'source_type': 'json',
        'identifier': 'id',
        'date_column': 'timestamp',
        'last_index': 0,
        'load_function': load_from_json,
    },
    {
        'name': 'SupplierMetrics',
        'file_name': 'supplier_metrics.json',
        'source_type': 'json',
        'identifier': 'id',
        'date_column': 'timestamp',
        'last_index': 0,
        'load_function': load_from_json,
    },
]


def initialize_addon(addon: Any, dataset_dict: dict) -> None:
    """
    Initialize the AVAROS addon with analysis entities.

    Called by PREVENTION framework at startup. Creates Model,
    Analysis, and DeploymentConf entities for each analysis goal.

    Args:
        addon: PREVENTION addon instance
        dataset_dict: Dictionary of loaded dataset objects keyed by name
    """
    from .initilization.init_data import addon_init_data
    addon_init_data(addon, dataset_dict)
