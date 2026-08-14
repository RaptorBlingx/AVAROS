# AVAROS Voice Commands — Quick Reference

Printable reference card for site operators.

---

## How to Use

1. Say **"Hey AVAROS"** to wake the assistant
2. Wait for the confirmation sound
3. Speak your query using the phrases below

---

## Available Commands

### Energy

| Say This | You Get |
|----------|---------|
| "What's the energy per unit for Line-1?" | Energy consumption per unit produced |
| "How much energy does Line-1 use per unit?" | Same — alternative phrasing |
| "Energy per unit this week" | Energy per unit for a time period |
| "Show me the energy consumption per unit for Line-1" | Same — alternative phrasing |

### OEE (Overall Equipment Effectiveness)

| Say This | You Get |
|----------|---------|
| "What's the OEE for Line-1?" | OEE percentage for an asset |
| "How is Line-1 performing?" | Same — alternative phrasing |
| "What's the overall equipment effectiveness on Line-1?" | Same — alternative phrasing |

### Scrap Rate

| Say This | You Get |
|----------|---------|
| "What's the scrap rate?" | Current scrap percentage |
| "What is the waste rate for Line-1?" | Scrap rate for a specific asset |
| "How much scrap are we producing?" | Same — alternative phrasing |

### Energy Comparison

| Say This | You Get |
|----------|---------|
| "Compare energy between Line-1 and Line-2" | Side-by-side energy comparison |
| "Which uses more energy, Line-1 or Line-2?" | Identifies the more efficient asset |
| "Compare Line-1 and Line-2 energy" | Same — alternative phrasing |

### Energy Trend

| Say This | You Get |
|----------|---------|
| "Show the energy trend for last week" | Rising, falling, or stable trend |
| "How has energy changed this month?" | Energy trend over a period |
| "What's the energy trend?" | General energy trend |

### Scrap Trend

| Say This | You Get |
|----------|---------|
| "What's the scrap rate trend?" | Rising, falling, or stable scrap trend |
| "Show the scrap trend for last month" | Scrap trend over a period |
| "How has scrap rate changed this week?" | Scrap trend over a period |

### Anomaly Detection

| Say This | You Get |
|----------|---------|
| "Are there any anomalies in production?" | PREVENTION-backed anomaly result, or an explicit unavailable message |
| "Check for anomalies" | Same — shorter phrasing |
| "Any unusual patterns?" | Same — alternative phrasing |
| "Any spikes or issues?" | Same — alternative phrasing |

Anomaly, drift, and forecast commands are advertised only when PREVENTION is configured and available.

### What-If Simulation

| Say This | You Get |
|----------|---------|
| "What if scrap rate drops by 10 percent on Line-1?" | Direct bounded KPI percentage scenario |
| "What if energy per unit reaches 2 kWh per unit on Line-2?" | Direct KPI target scenario |

Process parameters such as temperature or pressure require a configured sensitivity model. AVAROS rejects them when no model is configured. It also rejects physically impossible KPI changes.

### Summaries, Meaning, and Follow-ups

| Say This | You Get |
|----------|---------|
| "Give me a factory summary for all lines last month" | Core KPI evidence for every line |
| "Rank all lines by OEE last month" | Complete ranking with values and period |
| "What does OEE mean?" | Definition, formula, direction, and data requirements |
| "Is OEE good on Line-1?" | Objective-based judgment, or an explicit no-objective message |
| "Why did OEE change?" | Evidence and possible contributors without a causal claim |
| "What about Line-2?" | Reuses the previous metric and period in the same session |

---

## Tips

- Replace **Line-1** with your actual asset name
- Time periods include **today**, **yesterday**, **last week**, **last month**, **past 30 days**, named months, and explicit date ranges
- **Last month** means the previous calendar month; **past 30 days** is rolling
- AVAROS is advisory and read-only; machine-control requests are refused
- If the assistant doesn't understand, try using the exact phrases above
- Commands only work for intents that are **enabled** in Settings → Intent Activation
