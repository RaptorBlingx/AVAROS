"""
AVAROS addon GraphQL query definitions.

Extends PREVENTION's BaseQuery with custom queries for
manufacturing KPI anomaly detection and drift monitoring.
"""

from __future__ import annotations

import graphene

try:
    from prevention.api.graphql.queries.base_query import BaseQuery
except ImportError:
    # Standalone testing — BaseQuery not available
    BaseQuery = graphene.ObjectType


class CustomQuery(BaseQuery, graphene.ObjectType):
    """AVAROS custom GraphQL queries (extends PREVENTION BaseQuery)."""
    pass
