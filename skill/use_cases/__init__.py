"""
AVAROS Use Cases Layer

Application-level orchestration of business logic.
Use cases coordinate between the presentation layer (OVOS intents)
and the infrastructure layer (adapters).

Components:
    - QueryDispatcher: Routes queries to adapter methods
    - Handlers for complex multi-step operations
"""

from skill.use_cases.query_dispatcher import QueryDispatcher

__all__ = ["QueryDispatcher"]
