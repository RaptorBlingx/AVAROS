"""KPI objective API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class KPIObjectiveRequest(BaseModel):
    metric: str
    asset_id: str = "all"
    mode: Literal["threshold", "improvement_from_baseline"] = "threshold"
    comparator: Literal["at_least", "at_most"] = "at_least"
    target_value: float | None = None
    baseline_value: float | None = None
    improvement_percent: float | None = Field(default=None, gt=0)
    unit: str = ""


class KPIObjectiveResponse(KPIObjectiveRequest):
    pass
