# Task P1-L04: End-to-End Voice Test

## 🎯 Objective
Complete voice pipeline test: microphone → STT → OVOS intent → AVAROS skill →
TTS → speaker (or Hivemind client). Proves the full loop works before sharing
with Emre.

## 📋 Requirements

### Functional
- [ ] Voice input recognized (STT transcribes correctly)
- [ ] AVAROS intent matched from spoken query
- [ ] Response spoken aloud (TTS) or returned via Hivemind
- [ ] At least 3 different intents tested:
  - `kpi.energy.per_unit` — "What's our energy per unit?"
  - `kpi.oee` — "What's our OEE?"
  - `kpi.scrap_rate` — "What's the scrap rate?"

### Technical
- [ ] If no mic available: test via Hivemind websocket or bus CLI
- [ ] Verify STT service is running (`ovos_stt` container)
- [ ] Verify TTS service is running (`ovos_tts` container)
- [ ] Log full request→response roundtrip timing

## ✅ Acceptance Criteria
- 3 intents produce correct spoken/text responses
- Roundtrip < 10 seconds per query
- No unhandled exceptions in any container log

## 📦 Deliverables
1. Test results table (intent, utterance, response, time)
2. Fix any issues discovered during testing
3. `TESTING-E2E.md` short summary (optional, can be in PR description)

## 📚 Resources
- Hivemind client credentials from P1-L01
- [WASABI-DEPLOYMENT.md](../WASABI-DEPLOYMENT.md) — Testing section
- OVOS STT/TTS container logs

## 🎯 Success Criteria
- [ ] Full voice loop works (or text-via-bus if no audio hardware)
- [ ] System stable for 10+ queries without restart
- [ ] Ready to share with Emre (P1-L05)

**Points:** 5  
**Dependencies:** P1-L03 ✅  
**Owner:** Lead
