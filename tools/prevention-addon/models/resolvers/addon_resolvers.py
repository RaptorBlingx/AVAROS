"""
AVAROS addon resolver.

Uses PREVENTION's built-in AddonDescriptiveResolver for all
descriptive analytics. No custom resolver needed for the current
z-score and linear drift algorithms.
"""

from __future__ import annotations

try:
    from prevention.models.resolvers.base import AddonDescriptiveResolver
except ImportError:
    # Standalone testing stub
    class AddonDescriptiveResolver:
        pass
