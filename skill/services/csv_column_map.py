"""
CSV Column Aliases and Mapping Helpers

Maps flexible column names from ERP/MES exports to AVAROS canonical
column names.  Split from ``csv_parser.py`` to keep files under 300
lines.

Supported aliases cover English and German (``datum``) header
conventions so that factory operators can upload data from most
common export formats without manual renaming.
"""

from __future__ import annotations


#: Maps normalised alias → canonical column name.
COLUMN_ALIASES: dict[str, str] = {
    # date
    "date": "record_date",
    "record_date": "record_date",
    "production_date": "record_date",
    "datum": "record_date",
    # asset_id
    "asset_id": "asset_id",
    "machine": "asset_id",
    "line": "asset_id",
    "equipment": "asset_id",
    # production_count
    "production_count": "production_count",
    "produced": "production_count",
    "quantity": "production_count",
    "output": "production_count",
    # good_count
    "good_count": "good_count",
    "good": "good_count",
    "passed": "good_count",
    "ok_count": "good_count",
    # material_consumed_kg
    "material_consumed_kg": "material_consumed_kg",
    "material_kg": "material_consumed_kg",
    "material": "material_consumed_kg",
    "input_kg": "material_consumed_kg",
    # optional
    "shift": "shift",
    "batch_id": "batch_id",
    "batch": "batch_id",
    "notes": "notes",
    "note": "notes",
    "comment": "notes",
}

REQUIRED_COLUMNS: frozenset[str] = frozenset({
    "record_date",
    "asset_id",
    "production_count",
})


def build_column_map(headers: list[str]) -> dict[str, str]:
    """Map raw CSV headers to canonical column names.

    Args:
        headers: Raw header names from the CSV file.

    Returns:
        Dict mapping raw header → canonical column name.
    """
    col_map: dict[str, str] = {}
    for raw in headers:
        normalised = raw.strip().lower().replace(" ", "_").replace("-", "_")
        canonical = COLUMN_ALIASES.get(normalised)
        if canonical:
            col_map[raw] = canonical
    return col_map
