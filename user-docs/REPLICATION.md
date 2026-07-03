# Replicating AVAROS at another SME

Use this sequence for a new manufacturing site.

## 1. Confirm the use case

Select a small set of operator questions and KPIs with clear owners. Begin with read-only decisions.

## 2. Confirm data availability

For each KPI record:

- source system and API owner
- asset identifiers
- timestamp and unit
- authentication method
- expected update frequency
- acceptable data latency

## 3. Deploy an isolated evaluation

Install AVAROS on a non-production host and use the demo platform first. Confirm Docker operations, login, voice access, and backups.

## 4. Create a site profile

Configure the real platform endpoint, register site assets, link resources, map metrics, and test each intent.

## 5. Validate with operators

Use representative questions and compare AVAROS responses with the source system. Record:

- correctness
- response time
- misunderstood asset names
- missing data
- preferred terminology

## 6. Introduce optional analytics

Enable PREVENTION only after base KPI queries are stable and the analytics owner confirms the data and authentication contract.

## 7. Production hardening

- HTTPS and firewall
- read-only service account
- credential rotation
- backups and recovery test
- monitoring and disk alerts
- operator and administrator training
- documented support owner

## 8. Acceptance

Accept the deployment only when installation can be repeated from the release package, all enabled intents have validated data, and rollback has been tested.
