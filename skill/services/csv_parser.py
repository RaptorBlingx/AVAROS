"""
CSV Parser for Production Data

Platform-agnostic parser that converts CSV files into validated
ProductionRecord domain objects. Supports flexible column naming
(aliases) to accept exports from common ERP/MES systems.

Usage:
    result = parse_production_csv(csv_content)
    if result.errors:
        log.warning("Skipped %d rows", len(result.errors))
    service.add_records_bulk(result.records)

Column aliases live in ``csv_column_map.py``.
Field-level parsers live in ``csv_field_parsers.py``.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

from skill.domain.production import ProductionRecord
from skill.services.csv_column_map import (
    REQUIRED_COLUMNS,
    build_column_map,
)
from skill.services.csv_field_parsers import (
    CsvRowError,
    parse_date,
    parse_float,
    parse_int,
)


logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────


@dataclass(frozen=True)
class CsvParseResult:
    """Result of parsing a production CSV file.

    Attributes:
        records: Successfully parsed ProductionRecord objects.
        errors: Per-row errors for rows that could not be parsed.
        total_rows: Total data rows encountered (excluding header).
        valid_rows: Number of rows successfully parsed.
    """

    records: tuple[ProductionRecord, ...]
    errors: tuple[CsvRowError, ...]
    total_rows: int
    valid_rows: int


# ── Public API ───────────────────────────────────────────


def parse_production_csv(
    content: str | bytes,
    delimiter: str | None = None,
) -> CsvParseResult:
    """Parse CSV content into ProductionRecord list.

    Expected columns (case-insensitive, flexible naming):
        date, asset_id, production_count, good_count,
        material_consumed_kg, [shift], [batch_id], [notes]

    Args:
        content: Raw CSV string or bytes.
        delimiter: Column delimiter. Auto-detected if None.

    Returns:
        CsvParseResult with records, errors, and row counts.
    """
    text = _to_text(content)
    if not text.strip():
        return CsvParseResult(
            records=(), errors=(), total_rows=0, valid_rows=0,
        )

    if delimiter is None:
        delimiter = _detect_delimiter(text)

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    col_map = build_column_map(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - set(col_map.values())
    if missing:
        err = CsvRowError(
            row_num=0,
            column=", ".join(sorted(missing)),
            message=f"Missing required columns: {sorted(missing)}",
        )
        return CsvParseResult(
            records=(), errors=(err,), total_rows=0, valid_rows=0,
        )

    records: list[ProductionRecord] = []
    errors: list[CsvRowError] = []
    total = 0

    for row_num, raw_row in enumerate(reader, start=1):
        total += 1
        row = _remap_row(raw_row, col_map)
        record, row_errors = _parse_row(row, row_num)
        if row_errors:
            errors.extend(row_errors)
        else:
            records.append(record)  # type: ignore[arg-type]

    return CsvParseResult(
        records=tuple(records),
        errors=tuple(errors),
        total_rows=total,
        valid_rows=len(records),
    )


# ── Helpers ──────────────────────────────────────────────


def _to_text(content: str | bytes) -> str:
    """Convert bytes to str if necessary, stripping BOM."""
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig")
    else:
        text = content
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def _detect_delimiter(text: str) -> str:
    """Auto-detect CSV delimiter (comma vs semicolon).

    Args:
        text: Raw CSV text.

    Returns:
        Detected delimiter character.
    """
    first_line = text.split("\n", maxsplit=1)[0]
    if first_line.count(";") > first_line.count(","):
        return ";"
    return ","


def _remap_row(
    raw_row: dict[str, str],
    col_map: dict[str, str],
) -> dict[str, str]:
    """Remap a CSV row using the column map.

    Args:
        raw_row: Row with original header keys.
        col_map: Mapping from original headers to canonical names.

    Returns:
        Row dict keyed by canonical column names.
    """
    return {
        canonical: (raw_row.get(raw_header) or "").strip()
        for raw_header, canonical in col_map.items()
    }


def _parse_row(
    row: dict[str, str],
    row_num: int,
) -> tuple[ProductionRecord | None, list[CsvRowError]]:
    """Parse a single remapped CSV row into a ProductionRecord.

    Args:
        row: Canonical-keyed row values.
        row_num: 1-based row number for error reporting.

    Returns:
        Tuple of (record_or_None, list_of_errors).
    """
    errors: list[CsvRowError] = []

    record_date = parse_date(row.get("record_date", ""), row_num, errors)
    asset_id = row.get("asset_id", "").strip()
    if not asset_id:
        errors.append(CsvRowError(row_num, "asset_id", "Missing asset_id"))

    production_count = parse_int(
        row.get("production_count", ""), "production_count", row_num, errors,
    )
    good_count = parse_int(
        row.get("good_count", ""), "good_count", row_num, errors,
        default=0,
    )
    material_kg = parse_float(
        row.get("material_consumed_kg", ""),
        "material_consumed_kg", row_num, errors, default=0.0,
    )

    if errors:
        return None, errors

    if good_count > production_count:
        errors.append(
            CsvRowError(
                row_num, "good_count",
                f"good_count ({good_count}) > production_count "
                f"({production_count})",
            ),
        )
        return None, errors

    try:
        record = ProductionRecord(
            record_date=record_date,  # type: ignore[arg-type]
            asset_id=asset_id,
            production_count=production_count,
            good_count=good_count,
            material_consumed_kg=material_kg,
            shift=row.get("shift", ""),
            batch_id=row.get("batch_id", ""),
            notes=row.get("notes", ""),
        )
    except ValueError as exc:
        errors.append(CsvRowError(row_num, "record", str(exc)))
        return None, errors

    return record, []
