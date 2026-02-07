# Task P1-E02: Turkish Locale (tr-tr)

## 🎯 Objective
Add Turkish language support for all existing intents and dialogs.
Copy `locale/en-us/` → `locale/tr-tr/` and translate.

## 📋 Requirements

### Files to Create
- [ ] `skill/locale/tr-tr/*.intent` — All intent files translated
- [ ] `skill/locale/tr-tr/*.dialog` — All dialog files translated
- [ ] Include Turkish manufacturing synonyms (e.g., "enerji", "hurda oranı", "OEE")

### Quality
- [ ] Natural Turkish phrasing (not word-for-word translation)
- [ ] Multiple utterance variations per intent (at least 3)
- [ ] Test with Turkish text input if possible

## 📐 Protocols & Standards
- `.github/instructions/avaros-protocols.instructions.md` — Intent naming
- **DEC-002:** Use canonical metric names in code, Turkish only in locale files

## ✅ Acceptance Criteria
- All `en-us` intents have `tr-tr` equivalents
- Dialogs use proper Turkish grammar
- PR includes side-by-side comparison (EN vs TR)

## 📦 Deliverables
1. `skill/locale/tr-tr/` directory with all files
2. Brief translation notes (any terms that were hard to translate)

**Points:** 3  
**Dependencies:** P1-E00 ✅  
**Owner:** Emre
