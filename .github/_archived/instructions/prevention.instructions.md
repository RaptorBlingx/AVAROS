---
applyTo: "**/prevention/**,**/anomaly/**"
---
# PREVENTION Integration Rules (Anomaly/Drift Detection)

## 🎯 Purpose
PREVENTION provides **early detection of anomalies and risks** in:
- Energy consumption patterns
- Material quality deviations
- Supplier performance drift
- Production KPI anomalies
- CO₂-eq baseline deviations

## Architecture
\`\`\`
Time-Series Data → PREVENTION Service
                        ↓
              Anomaly Detection Models
                        ↓
              Drift Alerts + Severity
                        ↓
              AVAROS Skill (proactive alerts)
\`\`\`

## Integration Points

### PREVENTION API Endpoints
\`\`\`python
# Check for anomalies
POST /prevention/check
{
    "metric": "energy_per_unit",
    "asset_id": "compressor-1",
    "lookback_hours": 24,
    "threshold_sigma": 2.0
}

# Response
{
    "is_anomalous": true,
    "anomalies": [
        {"timestamp": "2026-01-29T10:00:00Z", "value": 45.2, "expected": 32.1, "deviation_sigma": 3.2}
    ],
    "severity": "WARNING",
    "recommendation": "Check compressor load pattern"
}

# Subscribe to alerts (webhook)
POST /prevention/subscribe
{
    "metrics": ["energy_per_unit", "scrap_rate"],
    "callback_url": "http://avaros-skill:8080/alerts"
}
\`\`\`

### Alert Severity Levels
| Level | Sigma | Action |
|-------|-------|--------|
| INFO | 1-2σ | Log only |
| WARNING | 2-3σ | Notify user proactively |
| CRITICAL | >3σ | Interrupt with urgent alert |

### Skill Integration Pattern
\`\`\`python
# Reactive: User asks "Any unusual patterns?"
@intent_handler('anomaly.production.check.intent')
async def handle_anomaly_check(self, message: Message):
    result: AnomalyResult = await self.dispatcher.check_anomaly(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id=message.data.get('asset')
    )
    if result.is_anomalous:
        self.speak_dialog('anomaly.detected', {...})
    else:
        self.speak_dialog('anomaly.none', {...})

# Proactive: PREVENTION pushes alert
async def on_prevention_alert(self, alert: dict):
    if alert["severity"] == "CRITICAL":
        self.speak(f"Urgent: {alert['message']}")
\`\`\`

## Drift Detection for KPIs
Monitor baseline drift for proposal targets:
- ≥8% electricity/unit improvement
- ≥5% material efficiency
- ≥10% CO₂-eq reduction

## Rules
1. Log all anomaly checks for audit
2. Don't alert fatigue - batch low-severity
3. Link anomalies to likely causes when possible
4. Track false positive rates for tuning
