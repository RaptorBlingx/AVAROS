"""
Tests for generator.py — CLI, metric creation, seed flow, mapping output.

Uses mocked ReneryoClient to test generator logic without network access.

Run:
    cd tools/reneryo-mock
    pip install -r requirements.txt pytest pytest-asyncio
    pytest tests/test_generator.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from generator import (
    MAPPING_FILE,
    _load_mapping,
    _parse_args,
    _save_mapping,
    _write_batched,
    ensure_metrics_exist,
    seed,
    verify,
)
from patterns import METRIC_PROFILES
from reneryo_client import ReneryoApiError


# =========================================================================
# CLI argument parsing
# =========================================================================


class TestParseArgs:
    """CLI argument tests."""

    def test_seed_mode(self) -> None:
        args = _parse_args(["--seed"])
        assert args.seed is True
        assert args.daemon is False

    def test_daemon_mode(self) -> None:
        args = _parse_args(["--daemon"])
        assert args.daemon is True
        assert args.seed is False

    def test_verify_mode(self) -> None:
        args = _parse_args(["--verify"])
        assert args.verify is True

    def test_list_mode(self) -> None:
        args = _parse_args(["--list"])
        assert getattr(args, "list") is True

    def test_custom_days(self) -> None:
        args = _parse_args(["--seed", "--days", "30"])
        assert args.days == 30

    def test_custom_interval(self) -> None:
        args = _parse_args(["--daemon", "--interval", "60"])
        assert args.interval == 60

    def test_custom_batch_delay(self) -> None:
        args = _parse_args(["--seed", "--batch-delay", "50"])
        assert args.batch_delay == 50

    def test_mutually_exclusive_modes(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args(["--seed", "--daemon"])

    def test_default_values(self) -> None:
        args = _parse_args(["--seed"])
        assert args.days == 90
        assert args.interval == 900
        assert args.batch_delay == 100


# =========================================================================
# Mapping file I/O
# =========================================================================


class TestMappingIO:
    """Tests for mapping_output.json read/write."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        mapping = {"oee": {"Line-1": "res-1", "Line-2": "res-2"}}
        test_file = tmp_path / "mapping_output.json"

        with patch("generator.MAPPING_FILE", test_file):
            _save_mapping(mapping)
            loaded = _load_mapping()

        assert loaded == mapping

    def test_load_missing_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "nonexistent.json"
        with patch("generator.MAPPING_FILE", test_file):
            result = _load_mapping()
        assert result == {}

    def test_load_corrupt_json(self, tmp_path: Path) -> None:
        test_file = tmp_path / "bad.json"
        test_file.write_text("not json{{{")
        with patch("generator.MAPPING_FILE", test_file):
            result = _load_mapping()
        assert result == {}

    def test_mapping_output_sorted(self, tmp_path: Path) -> None:
        mapping = {
            "zzz_metric": {"Line-1": "r1"},
            "aaa_metric": {"Line-1": "r2"},
        }
        test_file = tmp_path / "mapping_output.json"
        with patch("generator.MAPPING_FILE", test_file):
            _save_mapping(mapping)
        content = test_file.read_text()
        data = json.loads(content)
        assert list(data.keys()) == ["aaa_metric", "zzz_metric"]


# =========================================================================
# ensure_metrics_exist tests
# =========================================================================


class TestEnsureMetrics:
    """Tests for metric creation / lookup."""

    @pytest.mark.asyncio
    async def test_creates_missing_metrics(self) -> None:
        client = AsyncMock()
        client.list_metrics = AsyncMock(return_value=[])
        client.create_metric = AsyncMock(side_effect=lambda **kw: f"id-{kw['name']}")

        result = await ensure_metrics_exist(client)

        assert len(result) == 19
        assert client.create_metric.call_count == 19

    @pytest.mark.asyncio
    async def test_reuses_existing_metrics(self) -> None:
        existing = [
            {"name": p.display_name, "id": f"existing-{p.name}"}
            for p in METRIC_PROFILES
        ]
        client = AsyncMock()
        client.list_metrics = AsyncMock(return_value=existing)
        client.create_metric = AsyncMock()

        result = await ensure_metrics_exist(client)

        assert len(result) == 19
        assert client.create_metric.call_count == 0
        assert result["oee"] == "existing-oee"

    @pytest.mark.asyncio
    async def test_mixed_existing_and_new(self) -> None:
        existing = [
            {"name": "AVAROS OEE", "id": "oee-existing"},
            {"name": "AVAROS Throughput", "id": "tp-existing"},
        ]
        client = AsyncMock()
        client.list_metrics = AsyncMock(return_value=existing)
        client.create_metric = AsyncMock(
            side_effect=lambda **kw: f"new-{kw['name']}"
        )

        result = await ensure_metrics_exist(client)

        assert len(result) == 19
        assert result["oee"] == "oee-existing"
        assert result["throughput"] == "tp-existing"
        assert client.create_metric.call_count == 17

    @pytest.mark.asyncio
    async def test_duplicate_name_create_fallback_reuses_metric(self) -> None:
        """On create 4xx, ensure_metrics_exist re-queries and reuses existing metric."""
        existing_after_error = {
            "AVAROS OEE": "oee-existing-after-error",
        }
        client = AsyncMock()
        client.list_metrics = AsyncMock(
            side_effect=[[], [{"name": "AVAROS OEE", "id": "oee-existing-after-error"}]],
        )

        async def create_metric_side_effect(**kwargs: str) -> str:
            if kwargs["name"] == "AVAROS OEE":
                raise ReneryoApiError("400 duplicate")
            return f"new-{kwargs['name']}"

        client.create_metric = AsyncMock(side_effect=create_metric_side_effect)

        result = await ensure_metrics_exist(client)

        assert result["oee"] == existing_after_error["AVAROS OEE"]


# =========================================================================
# _write_batched tests
# =========================================================================


class TestWriteBatched:
    """Tests for batch writing logic."""

    @pytest.mark.asyncio
    async def test_writes_in_batches_of_500(self) -> None:
        client = AsyncMock()
        client.write_values = AsyncMock(return_value="res-1")

        points = [
            {"value": float(i), "datetime": f"2026-01-{(i // 96) + 1:02d}T{(i % 96) * 15 // 60:02d}:{(i % 96) * 15 % 60:02d}:00.000Z"}
            for i in range(1200)
        ]

        result = await _write_batched(
            client, "m1", points, asset="Line-1", delay_s=0,
        )

        assert result == "res-1"
        # 1200 / 500 = 3 batches (500, 500, 200)
        assert client.write_values.call_count == 3

    @pytest.mark.asyncio
    async def test_single_batch_under_500(self) -> None:
        client = AsyncMock()
        client.write_values = AsyncMock(return_value="res-2")

        points = [{"value": 1.0, "datetime": "2026-01-01T00:00:00.000Z"}]

        result = await _write_batched(
            client, "m1", points, asset="Line-1", delay_s=0,
        )

        assert result == "res-2"
        assert client.write_values.call_count == 1

    @pytest.mark.asyncio
    async def test_labels_include_asset(self) -> None:
        client = AsyncMock()
        client.write_values = AsyncMock(return_value="res-3")

        points = [{"value": 1.0, "datetime": "2026-01-01T00:00:00.000Z"}]

        await _write_batched(
            client, "m1", points, asset="Line-2", delay_s=0,
        )

        call_args = client.write_values.call_args
        labels = call_args[0][3]  # 4th positional arg
        assert labels == [{"key": "asset", "value": "Line-2"}]


# =========================================================================
# seed flow tests
# =========================================================================


class TestSeedFlow:
    """Tests for the full seed workflow."""

    @pytest.mark.asyncio
    async def test_seed_creates_mapping_for_all_metrics(
        self, tmp_path: Path
    ) -> None:
        client = AsyncMock()
        client.list_metrics = AsyncMock(return_value=[])
        client.create_metric = AsyncMock(
            side_effect=lambda **kw: f"mid-{kw['name']}"
        )
        client.write_values = AsyncMock(return_value="res-test")

        test_file = tmp_path / "mapping_output.json"
        with patch("generator.MAPPING_FILE", test_file):
            mapping = await seed(client, days=1, batch_delay_ms=0)

        assert len(mapping) == 19
        for metric_name, assets in mapping.items():
            assert len(assets) == 3, f"{metric_name} missing assets"
            for asset in ("Line-1", "Line-2", "Line-3"):
                assert asset in assets

    @pytest.mark.asyncio
    async def test_seed_saves_mapping_file(self, tmp_path: Path) -> None:
        client = AsyncMock()
        client.list_metrics = AsyncMock(return_value=[])
        client.create_metric = AsyncMock(return_value="mid-1")
        client.write_values = AsyncMock(return_value="res-1")

        test_file = tmp_path / "mapping_output.json"
        with patch("generator.MAPPING_FILE", test_file):
            await seed(client, days=1, batch_delay_ms=0)

        assert test_file.exists()
        data = json.loads(test_file.read_text())
        assert len(data) == 19

    @pytest.mark.asyncio
    async def test_seed_idempotent_with_existing_metrics(
        self, tmp_path: Path
    ) -> None:
        """Re-running seed with existing metrics doesn't error."""
        existing = [
            {"name": p.display_name, "id": f"existing-{p.name}"}
            for p in METRIC_PROFILES
        ]
        client = AsyncMock()
        client.list_metrics = AsyncMock(return_value=existing)
        client.create_metric = AsyncMock()
        client.write_values = AsyncMock(return_value="res-1")

        test_file = tmp_path / "mapping_output.json"
        with patch("generator.MAPPING_FILE", test_file):
            mapping = await seed(client, days=1, batch_delay_ms=0)

        assert client.create_metric.call_count == 0
        assert len(mapping) == 19


# =========================================================================
# verify tests
# =========================================================================


class TestVerify:
    """Tests for verify mode."""

    @pytest.mark.asyncio
    async def test_verify_reads_from_mapping(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mapping = {
            "oee": {"Line-1": "res-oee-1"},
        }
        test_file = tmp_path / "mapping_output.json"
        test_file.write_text(json.dumps(mapping))

        client = AsyncMock()
        client.read_values = AsyncMock(return_value={
            "recordCount": 100,
            "records": [
                {"value": 82.5, "datetime": "2026-03-10T12:00:00.000Z"},
            ],
        })

        with patch("generator.MAPPING_FILE", test_file):
            await verify(client, count=5)

        output = capsys.readouterr().out
        assert "OK" in output
        assert "oee" in output
        assert "1/1" in output

    @pytest.mark.asyncio
    async def test_verify_no_mapping_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        test_file = tmp_path / "nonexistent.json"
        client = AsyncMock()

        with patch("generator.MAPPING_FILE", test_file):
            await verify(client)

        # Should not crash, just log error
        assert client.read_values.call_count == 0
