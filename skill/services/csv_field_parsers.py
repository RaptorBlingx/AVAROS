"""
CSV Field Parsers

Type-safe parsers for individual CSV cell values and
``CsvRowError`` dataclass for structured error reporting.

Split from ``csv_parser.py`` to keep files under 300 lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CsvRowError:
    """Error encountered while parsing a single CSV row.

    Attributes:
        row_num: 1-based row number (excluding header).
        column: Column name that caused the error.
        message: Human-readable error description.
    """

    row_num: int
    column: str
    message: str


def parse_date(
    value: str, row_num: int, errors: list[CsvRowError],
) -> date | None:
    """Parse ISO 8601 date string.

    Args:
        value: Date string (YYYY-MM-DD).
        row_num: Row number for error reporting.
        errors: Error accumulator list.

    Returns:
        Parsed date or None (with error appended).
    """
    if not value:
        errors.append(
            CsvRowError(row_num, "record_date", "Missing date"),
        )
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(
            CsvRowError(
                row_num, "record_date",
                f"Invalid date format: '{value}' (expected YYYY-MM-DD)",
            ),
        )
        return None


def parse_int(
    value: str, column: str, row_num: int,
    errors: list[CsvRowError], *, default: int | None = None,
) -> int:
    """Parse integer value from CSV cell.

    Args:
        value: Raw string value.
        column: Column name for error reporting.
        row_num: Row number for error reporting.
        errors: Error accumulator list.
        default: Default if value is empty. None means required.

    Returns:
        Parsed integer (or default / 0 on error).
    """
    if not value:
        if default is not None:
            return default
        errors.append(
            CsvRowError(row_num, column, f"Missing {column}"),
        )
        return 0
    try:
        result = int(value)
    except ValueError:
        errors.append(
            CsvRowError(
                row_num, column, f"Invalid integer: '{value}'",
            ),
        )
        return 0
    if result < 0:
        errors.append(
            CsvRowError(
                row_num, column,
                f"{column} must be >= 0, got {result}",
            ),
        )
        return 0
    return result


def parse_float(
    value: str, column: str, row_num: int,
    errors: list[CsvRowError], *, default: float | None = None,
) -> float:
    """Parse float value from CSV cell.

    Args:
        value: Raw string value.
        column: Column name for error reporting.
        row_num: Row number for error reporting.
        errors: Error accumulator list.
        default: Default if value is empty. None means required.

    Returns:
        Parsed float (or default / 0.0 on error).
    """
    if not value:
        if default is not None:
            return default
        errors.append(
            CsvRowError(row_num, column, f"Missing {column}"),
        )
        return 0.0
    try:
        result = float(value)
    except ValueError:
        errors.append(
            CsvRowError(
                row_num, column, f"Invalid number: '{value}'",
            ),
        )
        return 0.0
    if result < 0:
        errors.append(
            CsvRowError(
                row_num, column,
                f"{column} must be >= 0, got {result}",
            ),
        )
        return 0.0
    return result
