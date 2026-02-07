---
description: Create a new platform adapter for AVAROS
---
# New Adapter Request

Create adapter for platform: {{platform_name}}

## Platform Details
- API Base URL: {{api_base_url}}
- Auth Method: {{auth_method}}
- Documentation: {{docs_url}}

## Implementation Tasks
1. Create \`adapters/{{platform_name}}_adapter.py\`
2. Extend \`ManufacturingAdapter\` ABC
3. Implement all 5 query methods:
   - \`get_kpi(metric, equipment_id, timeframe)\`
   - \`compare(metric, equipment_ids, timeframe)\`
   - \`get_trend(metric, equipment_id, start, end, granularity)\`
   - \`check_anomaly(metric, equipment_id)\`
   - \`simulate_whatif(scenario)\`
4. Map platform-specific fields to canonical metrics
5. Add to adapter registry
6. Create unit tests with mocked responses
7. Add integration test (skipped by default)
