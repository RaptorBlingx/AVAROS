"""Single source of truth for active deterministic DIA capabilities."""

from __future__ import annotations

from typing import Any

from skill.domain.models import CanonicalMetric
from skill.services.prevention_runtime import resolve_prevention_config


def build_capability_manifest(settings_service, adapter=None) -> dict[str, Any]:
    """Build a profile-aware, read-only capability manifest."""
    profile = "unconfigured"
    display_name = "Unconfigured"
    if settings_service is not None:
        try:
            profile = settings_service.get_active_profile_name()
            display_name = profile.replace("-", " ").title()
            config = settings_service.get_profile(profile)
            configured_name = str(
                getattr(config, "extra_settings", {}).get("display_name", ""),
            ).strip()
            if configured_name:
                display_name = configured_name
        except Exception:
            pass

    metrics: list[CanonicalMetric] = []
    if adapter is not None:
        try:
            metrics = list(adapter.get_supported_metrics())
        except Exception:
            metrics = []
    elif settings_service is not None:
        names = set(settings_service.list_metric_mappings().keys())
        try:
            for asset in settings_service.get_asset_mappings(profile=profile).values():
                if isinstance(asset, dict):
                    resources = asset.get("metric_resources", {})
                    if isinstance(resources, dict):
                        names.update(resources.keys())
                    native_bindings = asset.get("native_metric_bindings", {})
                    if isinstance(native_bindings, dict):
                        names.update(native_bindings.keys())
        except Exception:
            pass
        for name in sorted(names):
            try:
                metrics.append(CanonicalMetric.from_string(name))
            except ValueError:
                continue

    prevention = resolve_prevention_config(settings_service)
    analytics_available = prevention.mode == "http" and bool(prevention.url)
    operations = [
        "kpi",
        "multi_kpi",
        "summary",
        "comparison",
        "ranking",
        "average",
        "trend",
        "definition",
        "target_gap",
        "evidence_based_diagnosis",
        "advisory_recommendation",
        "bounded_kpi_what_if",
        "status",
        "provenance",
        "freshness",
    ]
    if analytics_available:
        operations.extend(["anomaly", "drift", "forecast", "proactive_alerts"])

    return {
        "profile": profile,
        "display_name": display_name,
        "read_only": True,
        "language": "en",
        "metrics": [
            {"id": metric.value, "label": metric.display_name, "unit": metric.default_unit}
            for metric in metrics
        ],
        "operations": operations,
        "prevention": {
            "available": analytics_available,
            "mode": prevention.mode,
            "reason": prevention.mode_reason,
        },
        "unsupported": ["machine_control", "causal_claims", "unmodelled_process_what_if"],
    }
