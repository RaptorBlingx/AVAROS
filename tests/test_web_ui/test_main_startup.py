"""Tests for Web UI startup lifecycle hooks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if WEB_UI_DIR not in sys.path:
    sys.path.insert(0, WEB_UI_DIR)

import main  # noqa: E402


class FakeScheduler:
    """Scheduler stub that records start invocations."""

    def __init__(self) -> None:
        self.started = False

    async def start(self) -> None:
        self.started = True


class FailingScheduler:
    """Scheduler stub that raises from start()."""

    async def start(self) -> None:
        raise RuntimeError("missing baselines")


@pytest.mark.asyncio
async def test_startup_check_calls_kpi_scheduler_start(monkeypatch) -> None:
    """Startup hook should invoke KPIScheduler.start()."""
    scheduler = FakeScheduler()

    monkeypatch.setattr(main, "get_kpi_scheduler", lambda: scheduler)

    await main.startup_check()

    assert scheduler.started is True


@pytest.mark.asyncio
async def test_startup_check_catches_scheduler_failure(monkeypatch) -> None:
    """Scheduler start failures should be logged as warning, not raised."""
    warnings: list[str] = []

    monkeypatch.setattr(main, "get_kpi_scheduler", lambda: FailingScheduler())
    monkeypatch.setattr(main.logger, "warning", lambda message, *args: warnings.append(message % args))

    await main.startup_check()

    assert any("KPI scheduler startup skipped" in entry for entry in warnings)
