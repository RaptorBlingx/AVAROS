---
description: Prepare AVAROS for WASABI White-Label Shop publication
agent: agent
---
# WASABI Shop Publication Checklist

## 🎯 Proposal Commitment (WP4, M11-M12)
"Produce a portable release and replication assets; publish to the WASABI White-Label Shop"

## Deliverables for Shop Listing

### 1. Dockerized Release
- [ ] \`docker-compose.yml\` - complete stack (OVOS + DocuBoT + PREVENTION)
- [ ] \`Dockerfile\` - pinned versions, multi-stage build
- [ ] \`.env.example\` - all required environment variables
- [ ] Health checks for all services
- [ ] Resource limits defined

### 2. Installation Checklist (\`INSTALL.md\`)
\`\`\`markdown
## Prerequisites
- [ ] Docker Engine 24.0+
- [ ] Docker Compose v2.20+
- [ ] 4GB RAM minimum
- [ ] Network access to backend API

## Quick Start
1. Clone repository
2. Copy \`.env.example\` to \`.env\`
3. Configure backend URL and API key
4. Run \`docker compose up -d\`
5. Verify health: \`docker compose ps\`

## Configuration
- AVAROS_BACKEND_TYPE: reneryo | mock | custom
- AVAROS_BACKEND_URL: https://your-api.example.com
- ...
\`\`\`

### 3. Sample Configuration
- [ ] \`config/backends/reneryo.yaml.example\`
- [ ] \`config/backends/mock.yaml\` (works without backend)
- [ ] Pre-configured intents for demo

### 4. Getting-Started Dataset
- [ ] \`data/sample/machines.json\` - 5 sample assets
- [ ] \`data/sample/energy_history.csv\` - 30 days mock data
- [ ] \`data/sample/suppliers.csv\` - 3 sample suppliers

### 5. Screenshots & Metadata
- [ ] Screenshot: voice query example
- [ ] Screenshot: KPI response
- [ ] Screenshot: anomaly alert
- [ ] \`shop-metadata.json\`:
  \`\`\`json
  {
      "name": "AVAROS",
      "version": "1.0.0",
      "category": "manufacturing",
      "tags": ["energy", "supply-chain", "sustainability"],
      "wasabi_components": ["ovos", "docubot", "prevention"]
  }
  \`\`\`

### 6. Documentation
- [ ] README.md - overview, architecture, quick start
- [ ] CONTRIBUTING.md - how to extend
- [ ] LICENSE - permissive (Apache 2.0 or MIT)
- [ ] CHANGELOG.md - version history

## Shop Listing Verification
- [ ] All containers start cleanly
- [ ] Mock mode works without external dependencies
- [ ] Basic intent responds correctly
- [ ] Logs are clean (no errors on startup)

## Post-Publication
- Track downloads via Shop analytics
- Monitor GitHub issues for adopter feedback
- Update based on pilot learnings
