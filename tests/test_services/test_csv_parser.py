"""
CSV Parser Test Suite

Covers:
    - Valid CSV → correct ProductionRecord list
    - Missing required columns → error
    - Invalid date format → per-row error
    - Negative values → per-row error
    - Column alias mapping (all aliases work)
    - Edge cases: empty file, header-only, delimiter detection
"""

from __future__ import annotations

from datetime import date

import pytest

from skill.domain.production import ProductionRecord
from skill.services.csv_parser import (
    CsvParseResult,
    CsvRowError,
    parse_production_csv,
)


# ══════════════════════════════════════════════════════════
# Valid CSV Parsing
# ══════════════════════════════════════════════════════════


class TestValidCsvParsing:
    """Parse well-formed CSV content."""

    def test_parse_basic_csv(self) -> None:
        """Standard CSV with required + optional columns."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg,shift\n"
            "2026-01-15,Line-1,500,485,120.5,morning\n"
        )
        result = parse_production_csv(csv)

        assert result.total_rows == 1
        assert result.valid_rows == 1
        assert len(result.errors) == 0
        assert len(result.records) == 1

        record = result.records[0]
        assert record.record_date == date(2026, 1, 15)
        assert record.asset_id == "Line-1"
        assert record.production_count == 500
        assert record.good_count == 485
        assert record.material_consumed_kg == 120.5
        assert record.shift == "morning"

    def test_parse_multiple_rows(self) -> None:
        """Multiple valid rows all parsed."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,500,485,120.5\n"
            "2026-01-15,Line-2,600,590,140.0\n"
            "2026-01-16,Line-1,480,470,115.0\n"
        )
        result = parse_production_csv(csv)
        assert result.total_rows == 3
        assert result.valid_rows == 3
        assert len(result.records) == 3

    def test_optional_columns_default_empty(self) -> None:
        """Missing optional columns default to empty string."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        record = result.records[0]
        assert record.shift == ""
        assert record.batch_id == ""
        assert record.notes == ""

    def test_missing_good_count_defaults_zero(self) -> None:
        """good_count empty cell defaults to 0."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,100,,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1
        assert result.records[0].good_count == 0

    def test_bytes_input(self) -> None:
        """Accepts bytes content (e.g. from file upload)."""
        csv = (
            b"date,asset_id,production_count,good_count,"
            b"material_consumed_kg\n"
            b"2026-01-15,Line-1,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1

    def test_utf8_bom_handled(self) -> None:
        """UTF-8 BOM prefix is stripped correctly."""
        csv = (
            "\ufeffdate,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,100,95,50.0\n"
        )
        result = parse_production_csv(csv.encode("utf-8-sig"))
        assert result.valid_rows == 1


# ══════════════════════════════════════════════════════════
# Column Alias Mapping
# ══════════════════════════════════════════════════════════


class TestColumnAliases:
    """Flexible column naming for ERP/MES exports."""

    def test_record_date_alias(self) -> None:
        """'record_date' header works."""
        csv = (
            "record_date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1

    def test_production_date_alias(self) -> None:
        """'production_date' header works."""
        csv = (
            "production_date,asset_id,produced,good,material_kg\n"
            "2026-01-15,Line-1,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1

    def test_datum_alias(self) -> None:
        """German 'datum' header works."""
        csv = (
            "datum,machine,quantity,passed,input_kg\n"
            "2026-01-15,Line-1,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1
        assert result.records[0].asset_id == "Line-1"

    def test_equipment_alias(self) -> None:
        """'equipment' header maps to asset_id."""
        csv = (
            "date,equipment,output,ok_count,material\n"
            "2026-01-15,Lathe-3,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1
        assert result.records[0].asset_id == "Lathe-3"


# ══════════════════════════════════════════════════════════
# Delimiter Detection
# ══════════════════════════════════════════════════════════


class TestDelimiterDetection:
    """Auto-detect comma vs semicolon delimiters."""

    def test_semicolon_delimiter(self) -> None:
        """Semicolon-separated (common in EU ERP exports)."""
        csv = (
            "date;asset_id;production_count;good_count;"
            "material_consumed_kg\n"
            "2026-01-15;Line-1;100;95;50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1

    def test_explicit_delimiter(self) -> None:
        """Explicit delimiter overrides auto-detection."""
        csv = (
            "date\tasset_id\tproduction_count\tgood_count\t"
            "material_consumed_kg\n"
            "2026-01-15\tLine-1\t100\t95\t50.0\n"
        )
        result = parse_production_csv(csv, delimiter="\t")
        assert result.valid_rows == 1


# ══════════════════════════════════════════════════════════
# Error Handling
# ══════════════════════════════════════════════════════════


class TestCsvErrors:
    """Per-row error handling and reporting."""

    def test_missing_required_columns(self) -> None:
        """CSV without required columns returns header-level error."""
        csv = "name,value\nfoo,123\n"
        result = parse_production_csv(csv)
        assert result.valid_rows == 0
        assert len(result.errors) == 1
        assert result.errors[0].row_num == 0  # header-level

    def test_invalid_date_format(self) -> None:
        """Non-ISO date format generates per-row error."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "15/01/2026,Line-1,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 0
        assert len(result.errors) == 1
        assert result.errors[0].column == "record_date"

    def test_negative_production_count(self) -> None:
        """Negative integer generates per-row error."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,-5,0,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 0
        assert any("must be >= 0" in e.message for e in result.errors)

    def test_non_numeric_production_count(self) -> None:
        """Non-numeric value in integer field."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,abc,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 0
        assert any("Invalid integer" in e.message for e in result.errors)

    def test_good_exceeds_production(self) -> None:
        """good_count > production_count generates error."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,10,15,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 0
        assert any("good_count" in e.column for e in result.errors)

    def test_missing_asset_id(self) -> None:
        """Empty asset_id generates error."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,,100,95,50.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 0
        assert any("asset_id" in e.column for e in result.errors)

    def test_partial_success(self) -> None:
        """Mix of valid and invalid rows: valid kept, errors reported."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,100,95,50.0\n"
            "BAD-DATE,Line-2,100,95,50.0\n"
            "2026-01-16,Line-1,200,190,80.0\n"
        )
        result = parse_production_csv(csv)
        assert result.total_rows == 3
        assert result.valid_rows == 2
        assert len(result.errors) == 1
        assert result.errors[0].row_num == 2

    def test_negative_material_kg(self) -> None:
        """Negative float generates per-row error."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,100,95,-10.0\n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 0


# ══════════════════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════════════════


class TestCsvEdgeCases:
    """Boundary and edge-case testing."""

    def test_empty_content(self) -> None:
        """Empty string returns empty result."""
        result = parse_production_csv("")
        assert result.total_rows == 0
        assert result.valid_rows == 0

    def test_header_only(self) -> None:
        """CSV with only headers, no data rows."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
        )
        result = parse_production_csv(csv)
        assert result.total_rows == 0
        assert result.valid_rows == 0
        assert len(result.errors) == 0

    def test_whitespace_trimmed(self) -> None:
        """Leading/trailing whitespace in cells is trimmed."""
        csv = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            " 2026-01-15 , Line-1 , 100 , 95 , 50.0 \n"
        )
        result = parse_production_csv(csv)
        assert result.valid_rows == 1
        assert result.records[0].asset_id == "Line-1"
