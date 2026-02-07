# Task P1-L03: Test Skill Loads in OVOS

## 🎯 Objective
Verify the AVAROS skill registers correctly with OVOS and responds to at least
one intent via the message bus. This proves the Container→Bus→Skill pipeline works.

## 📋 Requirements

### Functional
- [ ] AVAROS skill appears in OVOS skill list
- [ ] At least one intent (e.g. `kpi.energy.per_unit`) is registered
- [ ] Sending a test utterance via bus returns a dialog response

### Technical
- [ ] Use OVOS bus monitor or CLI to send test message
- [ ] Check skill log for intent match + response builder output
- [ ] MockAdapter returns demo data (no real API needed)
- [ ] Verify locale files loaded (`locale/en-us/*.intent`)

## ✅ Acceptance Criteria
- OVOS logs: "Registered intent: kpi.energy.per_unit"
- Test utterance "What is our energy per unit?" → gets spoken response
- MockAdapter `get_kpi("energy_per_unit")` called (visible in debug log)

## 📦 Deliverables
1. Log snippet showing successful intent registration
2. Log snippet showing test utterance → response
3. List of any fixes needed (if skill didn't load on first try)

## 📚 Resources
- OVOS CLI docs: `ovos-core --help`
- OVOS bus API: send `recognizer_loop:utterance` message
- [skill/__init__.py](../../skill/__init__.py) — intent handlers

## 🎯 Success Criteria
- [ ] Skill loads without import errors
- [ ] At least 1 intent fires and returns dialog
- [ ] Ready for P1-L04 (end-to-end voice)

**Points:** 3  
**Dependencies:** P1-L02 ✅  
**Owner:** Lead
