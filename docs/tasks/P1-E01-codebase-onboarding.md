## Task: [P1-E01] AVAROS Codebase Onboarding — Clone, Run, Verify

**Story Points:** 2
**Dependencies:** P1-L05 (repo access), P1-L06 (onboarding doc)
**Branch:** `feature/emre-P1-E01-onboarding`

### Objective
Clone the AVAROS repository, set up the development environment, run the skill inside the OVOS Docker stack, and verify that all existing tests pass. This is your first hands-on task with the AVAROS codebase — by the end you should be able to develop, test, and run the skill locally.

### Requirements
- [ ] Clone the AVAROS repo from Forgejo using the URL in the onboarding doc
- [ ] Follow the onboarding doc to start the WASABI OVOS Docker stack
- [ ] Verify the AVAROS skill container starts and connects to the message bus
- [ ] Run the full test suite locally (`pytest tests/ -v`) — all tests must pass
- [ ] Read through the project structure and understand the layer separation (domain → adapters → use_cases → skill handlers)
- [ ] Document any issues or deviations from the onboarding doc in a short `docs/P1-E01-onboarding-notes.md`

### Acceptance Criteria
- [ ] AVAROS skill registers in OVOS and responds to at least one voice command via MockAdapter
- [ ] `pytest tests/ -v` passes with 0 failures on your local machine
- [ ] You can explain the purpose of: `CanonicalMetric`, `QueryDispatcher`, `ManufacturingAdapter`, `MockAdapter`, `ResponseBuilder`
- [ ] Short onboarding notes file committed (any issues, questions, or environment quirks)
- [ ] No changes to existing production code in this PR — this is read/verify only

### Files to Create/Modify
- `docs/P1-E01-onboarding-notes.md` — Your notes from the onboarding process (create new)
- No production code changes expected

### Testing Requirements
- Run `pytest tests/ -v` and confirm all tests pass
- Run `pytest tests/test_domain/ -v` and confirm domain tests pass
- Manually verify skill loads by checking Docker logs for "AVAROS skill initialized with adapter: MockAdapter"

### Reference
- Onboarding doc (created by Lead in P1-L06) — your starting guide
- `DEVELOPMENT.md` L18–L251 for architecture decisions (DEC-001–007)
- `DEVELOPMENT.md` L779–L983 for testing standards
- `skill/__init__.py` — main skill class, read all handlers
- `skill/domain/` — domain layer (models, exceptions, results)
- `skill/adapters/` — adapter interface and MockAdapter
- `skill/use_cases/query_dispatcher.py` — orchestration layer
- `skill/services/response_builder.py` — voice formatting (currently unused, will be wired later)

### Notes
- The onboarding doc from Lead will have the exact Docker commands. Follow it step by step.
- If something in the doc is wrong or unclear, that's valuable feedback — write it in your notes file.
- Do NOT modify any existing code in this task. The goal is understanding and verification only.
- The `tests/test_exceptions.py` and `tests/test_result_types.py` files contain known bad tests (they test locally-defined fakes, not real code). Lead is rewriting them in P1-L08. Don't be confused by their structure.
- Ask Lead if you get stuck on Docker networking or message bus connection issues.
