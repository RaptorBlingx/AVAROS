"""Validate windows against Reneryo's existing UTC aggregate-bucket contract.

This selects a source resolution or abstains; it never prorates or rebuilds
Reneryo counter deltas. See UtilMetricResourceValuePeriod / UtilMetricValueQuery.
"""

from datetime import timedelta, timezone


def history_resolution(period, preferred: str) -> str:
    start = period.start.astimezone(timezone.utc)
    if preferred == "MONTHLY" and (start.day != 1 or start.hour or start.minute):
        preferred = "DAILY"
    if preferred == "DAILY" and (start.hour or start.minute):
        preferred = "HOURLY"
    if preferred == "HOURLY" and start.minute:
        preferred = "MINUTELY"
    return preferred


def meter_window_exact(start, end) -> bool:
    """Conservative boundary check for Reneryo meter auto-resolution.

    >7 days can use DAILY, >=10 calendar months MONTHLY, >12h HOURLY,
    otherwise MINUTELY. An unaligned boundary cannot prove a period total.
    Use the coarser resolution at thresholds to cover inclusive API bounds.
    """
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    inclusive_end = end - timedelta(microseconds=1)
    months = (inclusive_end.year - start.year) * 12 + inclusive_end.month - start.month
    days = (inclusive_end - start).total_seconds() / 86400
    resolution = (
        "MONTHLY"
        if months >= 10
        else "DAILY"
        if days > 7
        else "HOURLY"
        if days > 0.5
        else "MINUTELY"
    )
    for value in (start, end):
        if value.second or value.microsecond:
            return False
        if resolution != "MINUTELY" and value.minute:
            return False
        if resolution in {"DAILY", "MONTHLY"} and value.hour:
            return False
        if resolution == "MONTHLY" and value.day != 1:
            return False
    return True
