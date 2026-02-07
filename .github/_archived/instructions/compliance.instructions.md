---
applyTo: "**"
---
# Compliance & Trustworthy AI Rules (GDPR + AI Act + ISO 27001)

## 🎯 Proposal Commitments
From Section 1.3: "Trustworthy-AI practices will be embedded from day one"
- GDPR compliance by design
- EU AI Act (limited-risk decision support)
- ISO/IEC 27001-aligned ISMS

## GDPR Compliance

### Data Minimization
- Collect ONLY data necessary for function
- NO user personal data unless authentication requires it
- Pseudonymize user IDs in logs where feasible

### Audit Logging (Immutable)
\`\`\`python
@dataclass(frozen=True)
class AuditLogEntry:
    timestamp: datetime
    query_id: str           # Unique ID for traceability
    user_role: str          # NOT personal identifier
    intent: str
    data_accessed: list[str]  # Which data sources queried
    recommendation_id: str | None
    response_summary: str
\`\`\`

### Data Retention
- Operational logs: 90 days rolling
- Audit logs: 1 year minimum
- Personal data: delete on user request

### Access Control (RBAC)
| Role | Permissions |
|------|-------------|
| Operator | Query KPIs, view trends |
| Planner | + What-if simulations |
| Engineer | + Anomaly investigation |
| Admin | + Configuration, audit review |

## AI Act Compliance (Limited Risk)

### Human Oversight
- User ALWAYS makes final decision
- Recommendations include confidence + evidence
- Clear escalation paths documented

### Transparency
- Explain WHY recommendation was made
- Link to DocuBoT sources
- Show input features used

### Risk Management
- Log model versions for every prediction
- Track recommendation outcomes when available
- Flag high-uncertainty outputs

## Security Controls

### Authentication & Authorization
- TLS 1.2+ for all API calls
- API keys via environment variables
- JWT tokens with expiry

### Secrets Management
- NEVER commit credentials
- Use Docker secrets or env vars
- Rotate keys periodically

### Encryption
- At rest: encrypted volumes
- In transit: TLS everywhere
- Backups: encrypted

## Code Implementation Rules
1. Add \`@audit_log\` decorator to handlers accessing sensitive data
2. Include \`user_role\` in all API requests
3. Return \`recommendation_id\` with every suggestion
4. Log but NEVER expose raw credentials in errors
5. Implement graceful degradation on auth failures
