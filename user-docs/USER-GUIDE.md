# AVAROS user guide

## Sign in

Open the AVAROS URL and enter the API key supplied by your administrator.

## Complete the setup wizard

1. Select or create a platform profile.
2. Enter the platform API endpoint and authentication.
3. Test the connection.
4. Register assets and spoken aliases.
5. Link assets to platform resource identifiers.
6. Map platform fields to canonical metrics.
7. Test mappings.
8. Enable the intents that have valid data.
9. Configure PREVENTION only if your administrator provides it.

## Ask a question

Use the voice control or text interface. Include an asset and period when relevant:

- “What is the energy per unit for Line-1 this week?”
- “Compare Line-1 and Line-2 on OEE.”
- “Show the scrap rate trend for last month.”
- “List the configured assets.”
- “Are there any production anomalies?”

Anomaly and drift questions require a healthy PREVENTION connection and fresh exported data.

## Add production data

Open **Production Data**, upload a CSV, review the validation summary, and import accepted rows. Asset identifiers must match configured AVAROS assets.

## Review system status

Use **System Info** to review:

- active platform profile
- platform reachability
- configured assets and metrics
- PREVENTION reachability and data freshness
- voice and wake-word status

Report unavailable or stale dependencies to the system administrator rather than treating the result as a manufacturing conclusion.

## Change profiles

Use profiles to separate sites, tenants, or test environments. Confirm the active profile before interpreting KPI results.
