"""
AVAROS Domain Layer - Canonical Manufacturing Data Models

This module contains the core domain models that represent universal
manufacturing concepts. These models are platform-agnostic and form
the contract between the skill layer and adapters.

Key Components:
    - CanonicalMetric: Enum of all supported manufacturing metrics
    - TimePeriod: Value object for time ranges
    - Result types: KPIResult, ComparisonResult, TrendResult, etc.
    - Exceptions: Domain-specific error types

Golden Rule:
    Domain models NEVER import from infrastructure (adapters, APIs).
    Adapters convert platform responses INTO these canonical types.
"""

from skill.domain.models import (
    CanonicalMetric,
    TimePeriod,
    DataPoint,
    WhatIfScenario,
    ScenarioParameter,
    Anomaly,
)
from skill.domain.results import (
    KPIResult,
    ComparisonResult,
    ComparisonItem,
    TrendResult,
    AnomalyResult,
    WhatIfResult,
)
from skill.domain.exceptions import (
    AVAROSError,
    AdapterError,
    ValidationError,
    MetricNotSupportedError,
    AssetNotFoundError,
)

__all__ = [
    # Enums and Value Objects
    "CanonicalMetric",
    "TimePeriod",
    "DataPoint",
    "WhatIfScenario",
    "ScenarioParameter",
    "Anomaly",
    # Result Types
    "KPIResult",
    "ComparisonResult",
    "ComparisonItem",
    "TrendResult",
    "AnomalyResult",
    "WhatIfResult",
    # Exceptions
    "AVAROSError",
    "AdapterError",
    "ValidationError",
    "MetricNotSupportedError",
    "AssetNotFoundError",
]
