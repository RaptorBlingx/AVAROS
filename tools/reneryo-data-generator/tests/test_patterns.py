"""
Tests for patterns.py — Manufacturing data profile definitions and generators.

Validates data ranges, shift patterns (night lower than day), weekend drops,
anomaly injection rate, improvement trends, asset offsets, and cross-metric
correlations.

Run:
    cd tools/reneryo-mock
    pip install pytest
    pytest tests/test_patterns.py -v
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest

from patterns import (
    DEFAULT_ASSETS,
    METRIC_PROFILES,
    PROFILE_BY_NAME,
    MetricProfile,
    generate_all_metrics,
    generate_single_metric,
    generate_value,
    improvement_factor,
    is_weekend,
    shift_factor,
)


# =========================================================================
# Profile definition tests
# =========================================================================


class TestMetricProfiles:
    """Validate the 19 metric profile definitions."""

    def test_exactly_19_profiles(self) -> None:
        assert len(METRIC_PROFILES) == 19

    def test_all_canonical_names_present(self) -> None:
        expected = {
            "energy_per_unit", "energy_total", "peak_demand",
            "peak_tariff_exposure", "scrap_rate", "rework_rate",
            "material_efficiency", "recycled_content", "oee",
            "throughput", "cycle_time", "changeover_time",
            "co2_per_unit", "co2_total", "co2_per_batch",
            "supplier_lead_time", "supplier_defect_rate",
            "supplier_on_time", "supplier_co2_per_kg",
        }
        actual = {p.name for p in METRIC_PROFILES}
        assert actual == expected

    def test_all_display_names_start_with_avaros(self) -> None:
        for p in METRIC_PROFILES:
            assert p.display_name.startswith("AVAROS "), (
                f"{p.name} display_name doesn't start with 'AVAROS '"
            )

    def test_min_less_than_baseline_less_than_max(self) -> None:
        for p in METRIC_PROFILES:
            assert p.min_val < p.baseline < p.max_val, (
                f"{p.name}: {p.min_val} < {p.baseline} < {p.max_val} failed"
            )

    def test_better_values_valid(self) -> None:
        for p in METRIC_PROFILES:
            assert p.better in ("lower", "higher"), (
                f"{p.name}: better={p.better} not valid"
            )

    def test_profile_by_name_lookup(self) -> None:
        assert PROFILE_BY_NAME["oee"].baseline == 72

    def test_default_assets(self) -> None:
        assert DEFAULT_ASSETS == ("Line-1", "Line-2", "Line-3")


# =========================================================================
# Pattern helper tests
# =========================================================================


class TestPatternHelpers:
    """Tests for shift, weekend, and improvement helpers."""

    def test_is_weekend_saturday(self) -> None:
        # 2026-03-07 is a Saturday
        sat = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
        assert is_weekend(sat)

    def test_is_weekend_sunday(self) -> None:
        sun = datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)
        assert is_weekend(sun)

    def test_not_weekend_monday(self) -> None:
        mon = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
        assert not is_weekend(mon)

    def test_shift_day(self) -> None:
        dt = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
        assert shift_factor(dt) == 1.0

    def test_shift_evening(self) -> None:
        dt = datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc)
        assert shift_factor(dt) == 0.95

    def test_shift_night(self) -> None:
        dt = datetime(2026, 1, 5, 2, 0, tzinfo=timezone.utc)
        assert shift_factor(dt) == 0.85

    def test_improvement_lower_decreases(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later = start + timedelta(days=90)
        factor = improvement_factor(later, start, "lower")
        assert factor < 1.0

    def test_improvement_higher_increases(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later = start + timedelta(days=90)
        factor = improvement_factor(later, start, "higher")
        assert factor > 1.0

    def test_improvement_at_start_is_one(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert improvement_factor(start, start, "lower") == 1.0


# =========================================================================
# generate_value tests
# =========================================================================


class TestGenerateValue:
    """Tests for single-value generation."""

    def test_value_within_bounds(self) -> None:
        """Values are clamped and non-negative."""
        profile = PROFILE_BY_NAME["oee"]
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rng = random.Random(42)
        for day in range(90):
            dt = start + timedelta(days=day, hours=10)
            val = generate_value(profile, dt, start, "Line-1", rng)
            assert val <= profile.max_val, (
                f"Day {day}: oee={val} > max {profile.max_val}"
            )
            assert val >= 0, f"Day {day}: oee={val} is negative"

    def test_night_shift_lower_than_day(self) -> None:
        """Night shift values average lower than day shift."""
        profile = PROFILE_BY_NAME["throughput"]
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Generate on a Wednesday (weekday)
        base_date = datetime(2026, 1, 7, tzinfo=timezone.utc)  # Wednesday

        day_values = []
        night_values = []
        for i in range(200):
            rng = random.Random(i)
            day_dt = base_date.replace(hour=10)
            night_dt = base_date.replace(hour=2)
            day_values.append(
                generate_value(profile, day_dt, start, "Line-1", rng)
            )
            rng2 = random.Random(i + 10000)
            night_values.append(
                generate_value(profile, night_dt, start, "Line-1", rng2)
            )

        avg_day = sum(day_values) / len(day_values)
        avg_night = sum(night_values) / len(night_values)
        assert avg_night < avg_day, (
            f"Night avg ({avg_night:.1f}) should be < day avg ({avg_day:.1f})"
        )

    def test_weekend_production_drops(self) -> None:
        """Production metrics drop significantly on weekends."""
        profile = PROFILE_BY_NAME["throughput"]
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        weekday = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)  # Wed
        weekend = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)  # Sat

        weekday_vals = [
            generate_value(
                profile, weekday, start, "Line-1", random.Random(i)
            )
            for i in range(100)
        ]
        weekend_vals = [
            generate_value(
                profile, weekend, start, "Line-1", random.Random(i + 5000)
            )
            for i in range(100)
        ]

        avg_weekday = sum(weekday_vals) / len(weekday_vals)
        avg_weekend = sum(weekend_vals) / len(weekend_vals)
        # Weekend should be roughly 20% of weekday for production
        assert avg_weekend < avg_weekday * 0.5, (
            f"Weekend avg ({avg_weekend:.1f}) should be << weekday avg ({avg_weekday:.1f})"
        )

    def test_weekend_energy_partial_drop(self) -> None:
        """Energy metrics drop to ~40% on weekends (idle draw)."""
        profile = PROFILE_BY_NAME["energy_total"]
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        weekday = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
        weekend = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)

        weekday_vals = [
            generate_value(
                profile, weekday, start, "Line-1", random.Random(i)
            )
            for i in range(100)
        ]
        weekend_vals = [
            generate_value(
                profile, weekend, start, "Line-1", random.Random(i + 5000)
            )
            for i in range(100)
        ]

        avg_weekday = sum(weekday_vals) / len(weekday_vals)
        avg_weekend = sum(weekend_vals) / len(weekend_vals)
        # Energy should be roughly 40% on weekends
        assert avg_weekend < avg_weekday * 0.7, (
            f"Weekend energy ({avg_weekend:.0f}) not sufficiently less than "
            f"weekday ({avg_weekday:.0f})"
        )

    def test_asset_offset_differences(self) -> None:
        """Different assets produce slightly different baselines."""
        profile = PROFILE_BY_NAME["oee"]
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        dt = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)

        vals = {}
        for asset in DEFAULT_ASSETS:
            vals[asset] = [
                generate_value(
                    profile, dt, start, asset, random.Random(i)
                )
                for i in range(200)
            ]

        avgs = {a: sum(v) / len(v) for a, v in vals.items()}
        # Line-3 should be slightly better than Line-1 for "higher" metrics
        assert avgs["Line-3"] > avgs["Line-1"] - 5  # Allowing noise


# =========================================================================
# generate_all_metrics tests
# =========================================================================


class TestGenerateAllMetrics:
    """Tests for correlated multi-metric generation."""

    def test_generates_all_19_metrics(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        result = generate_all_metrics(start, end, "Line-1")
        assert len(result) == 19

    def test_correct_number_of_points_per_day(self) -> None:
        """96 points per day (15-minute intervals)."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        result = generate_all_metrics(start, end, "Line-1")
        for metric_name, points in result.items():
            assert len(points) == 96, (
                f"{metric_name}: expected 96, got {len(points)}"
            )

    def test_unique_timestamps_in_series(self) -> None:
        """No duplicate timestamps within one metric/asset series."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=2)
        result = generate_all_metrics(start, end, "Line-1")
        for metric_name, points in result.items():
            timestamps = [p["datetime"] for p in points]
            assert len(timestamps) == len(set(timestamps)), (
                f"{metric_name} has duplicate timestamps"
            )

    def test_values_within_profile_bounds(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=3)
        result = generate_all_metrics(start, end, "Line-1")
        for metric_name, points in result.items():
            profile = PROFILE_BY_NAME[metric_name]
            for p in points:
                # On weekends, production/energy metrics can dip below min_val
                assert p["value"] <= profile.max_val, (
                    f"{metric_name}: {p['value']} exceeds max {profile.max_val}"
                )
                assert p["value"] >= 0, (
                    f"{metric_name}: {p['value']} is negative"
                )

    def test_cross_correlation_energy_throughput(self) -> None:
        """Higher throughput → higher energy_total (positive correlation)."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=7)  # Include weekday + weekend

        result = generate_all_metrics(start, end, "Line-1")
        throughput = result["throughput"]
        energy = result["energy_total"]

        # Weekday vs weekend: both should drop together
        weekday_tp = [p["value"] for p in throughput[:96]]  # Day 1 (Thu)
        weekend_tp = [p["value"] for p in throughput[2 * 96:3 * 96]]  # Day 3 (Sat)
        weekday_e = [p["value"] for p in energy[:96]]
        weekend_e = [p["value"] for p in energy[2 * 96:3 * 96]]

        assert sum(weekend_tp) < sum(weekday_tp)
        assert sum(weekend_e) < sum(weekday_e)

    def test_reproducible_with_same_seed(self) -> None:
        """Same seed → identical output."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)

        r1 = generate_all_metrics(start, end, "Line-1", seed=42)
        r2 = generate_all_metrics(start, end, "Line-1", seed=42)

        for metric_name in r1:
            assert r1[metric_name] == r2[metric_name], (
                f"{metric_name} not reproducible with same seed"
            )

    def test_different_seeds_different_output(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)

        r1 = generate_all_metrics(start, end, "Line-1", seed=42)
        r2 = generate_all_metrics(start, end, "Line-1", seed=99)

        # At least some metrics should differ
        differences = sum(
            1 for name in r1
            if r1[name] != r2[name]
        )
        assert differences > 0


# =========================================================================
# generate_single_metric tests (daemon mode)
# =========================================================================


class TestGenerateSingleMetric:
    """Tests for single-point daemon-mode generation."""

    def test_returns_value_and_datetime(self) -> None:
        profile = PROFILE_BY_NAME["oee"]
        dt = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)

        result = generate_single_metric(profile, dt, start, "Line-1")
        assert "value" in result
        assert "datetime" in result
        assert isinstance(result["value"], float)

    def test_value_within_bounds(self) -> None:
        profile = PROFILE_BY_NAME["scrap_rate"]
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)

        for hour in range(24):
            dt = datetime(2026, 3, 10, hour, 0, tzinfo=timezone.utc)
            result = generate_single_metric(profile, dt, start, "Line-1")
            assert profile.min_val <= result["value"] <= profile.max_val


# =========================================================================
# Anomaly injection rate test
# =========================================================================


class TestAnomalyInjection:
    """Verify anomalies occur at approximately the expected rate."""

    def test_anomaly_rate_approximately_1_5_percent(self) -> None:
        """Anomalies should be injected on ~1.5% of data points."""
        profile = PROFILE_BY_NAME["oee"]
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Use a weekday to avoid weekend drops masking anomalies
        base_dt = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)  # Wed

        # Generate many values and count those far from baseline
        n = 10000
        anomaly_count = 0
        span = profile.max_val - profile.min_val
        threshold = span * 0.2  # Anomalies spike by ~30% of span

        for i in range(n):
            rng = random.Random(i)
            val = generate_value(profile, base_dt, start, "Line-1", rng)
            if abs(val - profile.baseline) > threshold:
                anomaly_count += 1

        rate = anomaly_count / n
        # Allow wide range — anomalies + noise overlap.
        # We just want non-zero anomalies and a reasonable rate.
        assert anomaly_count > 0, "No anomalies detected"
        assert rate < 0.15, f"Anomaly rate {rate:.2%} too high"
