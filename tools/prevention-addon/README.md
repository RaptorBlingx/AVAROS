# AVAROS Addon for PREVENTION Platform
#
# This addon provides anomaly detection and drift monitoring for
# manufacturing KPIs. It is mounted into the PREVENTION platform
# via Docker volume.
#
# Structure follows PREVENTION's addon pattern:
#   data/           — Raw data files (JSON, written by data-sync pipeline)
#   initilization/  — GraphQL schema, queries, init_data
#   models/         — Custom algorithms and resolvers
#   services/       — Helper functions
