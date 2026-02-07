---
description: Add a new voice intent to AVAROS skill
---
# New Intent Request

Add a new intent called: {{intent_name}}

## Query Type
This intent belongs to query type: {{query_type}}

(Options: get_kpi, compare, get_trend, check_anomaly, simulate_whatif)

## Sample Utterances
- "{{utterance_1}}"
- "{{utterance_2}}"
- "{{utterance_3}}"

## Expected Slot Extraction
- metric: {{metric}}
- equipment_id: {{equipment}}
- timeframe: {{timeframe}}

## Tasks
1. Create vocab file: \`locale/en-us/{{intent_name}}.voc\`
2. Create dialog file: \`locale/en-us/{{intent_name}}.dialog\`
3. Add intent handler in \`__init__.py\`
4. Route to correct adapter method based on query type
5. Add unit test in \`tests/\`
