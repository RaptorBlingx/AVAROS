"""Authenticated client for explainable MDSP findings."""

from __future__ import annotations

import os
import ssl
from datetime import datetime, timezone
from typing import Any

import aiohttp

from skill.domain.exceptions import AdapterError
from skill.domain.reneryo_models import LocalizedText, MdspFinding, MdspFindingList


def _datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class MdspClient:
    """Read findings from MDSP with server-side credentials."""

    def __init__(
        self,
        base_url: str,
        service_token: str,
        timeout: int = 30,
        tls_ca_path: str | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._timeout = timeout
        self._tls_ca_path = tls_ca_path

    @classmethod
    def from_environment(cls) -> MdspClient:
        base_url = os.environ.get("MDSP_BASE_URL", "").strip()
        token = os.environ.get("MDSP_SERVICE_TOKEN", "").strip()
        if not base_url or not token:
            raise AdapterError(
                message="MDSP client is not configured",
                code="MDSP_NOT_CONFIGURED",
                platform="mdsp",
                user_message="Decision-support findings are not configured in AVAROS.",
            )
        return cls(
            base_url,
            token,
            tls_ca_path=os.environ.get("MDSP_TLS_CA_PATH", "").strip() or None,
        )

    async def list_findings(
        self,
        organization_id: str,
        *,
        status: str = "ACTIVE",
    ) -> MdspFindingList:
        payload = await self._get(
            "/v1/findings",
            organization_id,
            {"status": status},
        )
        records = payload.get("records", [])
        summary = payload.get("summary", {})
        severity = summary.get("bySeverity", {}) if isinstance(summary, dict) else {}
        return MdspFindingList(
            findings=(
                tuple(self._finding(row) for row in records if isinstance(row, dict))
                if isinstance(records, list)
                else ()
            ),
            active_count=(
                int(summary.get("active", 0)) if isinstance(summary, dict) else 0
            ),
            resolved_count=(
                int(summary.get("resolved", 0)) if isinstance(summary, dict) else 0
            ),
            severity_counts=(
                {
                    key.upper(): int(value)
                    for key, value in severity.items()
                    if isinstance(value, (int, float))
                }
                if isinstance(severity, dict)
                else {}
            ),
        )

    async def get_finding(self, organization_id: str, finding_id: str) -> MdspFinding:
        return self._finding(
            await self._get(f"/v1/findings/{finding_id}", organization_id)
        )

    async def _get(
        self,
        path: str,
        organization_id: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "X-Organization-Id": organization_id,
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        connector = None
        if self._tls_ca_path:
            connector = aiohttp.TCPConnector(
                ssl=ssl.create_default_context(cafile=self._tls_ca_path)
            )
        async with aiohttp.ClientSession(
            timeout=timeout, headers=headers, connector=connector
        ) as session:
            try:
                async with session.get(
                    f"{self._base_url}{path}", params=params
                ) as response:
                    if response.status == 404:
                        raise AdapterError(
                            message=f"MDSP finding not found: {path}",
                            code="MDSP_FINDING_NOT_FOUND",
                            platform="mdsp",
                            status_code=404,
                            user_message="That decision-support finding is no longer available.",
                        )
                    if response.status < 200 or response.status >= 300:
                        raise AdapterError(
                            message=f"MDSP returned HTTP {response.status} for {path}",
                            code="MDSP_REQUEST_FAILED",
                            platform="mdsp",
                            status_code=response.status,
                            user_message="Decision-support findings are temporarily unavailable.",
                        )
                    payload = await response.json()
            except (aiohttp.ClientError, TimeoutError) as exc:
                raise AdapterError(
                    message=f"MDSP request failed for {path}: {exc}",
                    code="MDSP_REQUEST_FAILED",
                    platform="mdsp",
                    user_message="Decision-support findings are temporarily unavailable.",
                ) from exc
        if not isinstance(payload, dict):
            raise AdapterError(
                message=f"Unexpected MDSP response for {path}",
                code="MDSP_INVALID_RESPONSE",
                platform="mdsp",
            )
        return payload

    @staticmethod
    def _finding(row: dict[str, Any]) -> MdspFinding:
        title = row.get("title") if isinstance(row.get("title"), dict) else {}
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        window = (
            row.get("evaluationWindow")
            if isinstance(row.get("evaluationWindow"), dict)
            else {}
        )
        assumptions = (
            row.get("assumptions") if isinstance(row.get("assumptions"), list) else []
        )
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        metric_name = str(evidence.get("metricName") or evidence.get("metric") or "")
        return MdspFinding(
            finding_id=str(row.get("id", "")),
            status=str(row.get("status", "")),
            severity=str(row.get("severity", "")),
            domain=str(row.get("domain", "")),
            entity_type=str(row.get("entityType", "")),
            entity_id=str(row.get("entityId", "")),
            title=LocalizedText(
                en=str(title.get("en", "")), tr=str(title.get("tr", ""))
            ),
            summary=LocalizedText(
                en=str(summary.get("en", "")), tr=str(summary.get("tr", ""))
            ),
            evidence=dict(evidence),
            assumptions=tuple(
                LocalizedText(en=str(item.get("en", "")), tr=str(item.get("tr", "")))
                for item in assumptions
                if isinstance(item, dict)
            ),
            evaluation_start=_datetime(window.get("start"))
            or datetime.min.replace(tzinfo=timezone.utc),
            evaluation_end=_datetime(window.get("end"))
            or datetime.min.replace(tzinfo=timezone.utc),
            source_watermark=_datetime(row.get("sourceWatermark")),
            deep_link=str(row.get("deepLink")) if row.get("deepLink") else None,
            provisional=bool(row.get("provisional")),
            metric_name=metric_name,
        )
