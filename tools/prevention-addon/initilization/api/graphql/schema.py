"""
AVAROS addon GraphQL schema instantiation.

Creates the GraphQL schema used by the AVAROS addon in PREVENTION.
"""

from __future__ import annotations

import graphene

try:
    from prevention.api.graphql.types import (
        Analysis,
        AnalysisResults,
        AnalyticsGoal,
        Dataset,
        Deployment,
        DeploymentConf,
        Model,
    )
    from prevention.api.graphql.mutations import Mutation

    from .queries.addon_query import CustomQuery

    addon_schema = graphene.Schema(
        query=CustomQuery,
        types=[
            Analysis,
            AnalysisResults,
            Dataset,
            DeploymentConf,
            Deployment,
            Model,
            AnalyticsGoal,
        ],
        mutation=Mutation,
    )
except ImportError:
    # Standalone testing — PREVENTION framework not available
    addon_schema = None
