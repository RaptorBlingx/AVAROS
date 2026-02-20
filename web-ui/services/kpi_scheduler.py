"""Lightweight asyncio-based scheduler for periodic KPI data collection.

Runs as a background ``asyncio.Task`` inside the FastAPI event-loop —
no external dependencies (APScheduler, Celery, etc.) required.
"""

from __future__ import annotations

import asyncio
import logging
import os

from services.kpi_collector import KPICollector

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_HOURS = 6
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 30


class KPIScheduler:
    """Periodically invokes :meth:`KPICollector.collect_snapshots`.

    Args:
        collector: The collector that talks to the adapter + DB.
        site_id: Pilot site identifier (default ``"pilot-1"``).
        interval_hours: Hours between collection runs.  Overridable via
            the ``KPI_COLLECTION_INTERVAL_HOURS`` environment variable.
    """

    def __init__(
        self,
        collector: KPICollector,
        site_id: str = "pilot-1",
        interval_hours: float | None = None,
    ) -> None:
        self._collector = collector
        self._site_id = site_id
        self._interval_hours = interval_hours or float(
            os.environ.get(
                "KPI_COLLECTION_INTERVAL_HOURS",
                str(_DEFAULT_INTERVAL_HOURS),
            ),
        )
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Launch the background loop (idempotent)."""
        if self._task is not None and not self._task.done():
            logger.debug("KPI scheduler already running")
            return
        self._task = asyncio.create_task(self._loop(), name="kpi-scheduler")
        logger.info(
            "KPI scheduler started (interval=%.1fh, site=%s)",
            self._interval_hours, self._site_id,
        )

    def stop(self) -> None:
        """Cancel the background task."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            logger.info("KPI scheduler stopped")
        self._task = None

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        interval = self._interval_hours * 3600
        while True:
            try:
                await asyncio.sleep(interval)
                await self._run_with_retry()
            except asyncio.CancelledError:
                logger.debug("KPI scheduler loop cancelled")
                return
            except Exception:
                logger.exception("Unexpected error in KPI scheduler loop")

    async def _run_with_retry(self) -> None:
        backoff = _INITIAL_BACKOFF_SECONDS
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                count = await self._collector.collect_snapshots(self._site_id)
                logger.info(
                    "KPI collection completed: %d snapshots (attempt %d)",
                    count, attempt,
                )
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "KPI collection attempt %d/%d failed",
                    attempt, _MAX_RETRIES,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        logger.error(
            "KPI collection failed after %d retries", _MAX_RETRIES,
        )
