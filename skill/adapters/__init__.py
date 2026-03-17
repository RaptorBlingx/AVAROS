"""
AVAROS Adapters Layer

Platform-agnostic adapter interfaces and implementations.
Adapters translate platform-specific APIs into canonical manufacturing data.

Components:
    - ManufacturingAdapter: Abstract base class defining the 5 query methods
    - UnconfiguredAdapter: Default when no platform is configured
    - AdapterFactory: Creates adapters based on configuration

Golden Rule:
    Adapters are TRANSLATORS, not business logic holders.
    They convert platform responses INTO canonical types.
"""

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.generic_rest import GenericRestAdapter
from skill.adapters.reneryo import ReneryoAdapter
from skill.adapters.unconfigured import UnconfiguredAdapter
from skill.adapters.factory import AdapterFactory

__all__ = [
    "ManufacturingAdapter",
    "GenericRestAdapter",
    "ReneryoAdapter",
    "UnconfiguredAdapter",
    "AdapterFactory",
]
