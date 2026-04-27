"""Tests for PREVENTION runtime manifest and data freshness helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from skill.services.prevention_runtime import resolve_prevention_data_status


def test_resolve_prevention_data_status_uses_env_manifest_path(
    monkeypatch,
    tmp_path,
) -> None:
    """Manifest path can be injected for container-safe runtime checks."""
    manifest_path = tmp_path / "export_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "exported_at": datetime.now(tz=timezone.utc).isoformat(),
                "platform": "mock",
                "days": 7,
                "total_records": 42,
                "files": {},
            },
        ),
    )
    monkeypatch.setenv("PREVENTION_EXPORT_MANIFEST_PATH", str(manifest_path))

    status = resolve_prevention_data_status(settings_service=None)

    assert status.state == "fresh"
    assert status.record_count == 42
    assert "42 records" in status.message