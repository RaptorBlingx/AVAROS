# Task P1-E03: Docker Dev Environment for Emre

## 🎯 Objective
Set up your own development environment: clone repo, run AVAROS in Docker,
run tests, make a change, submit PR. Proves the full dev workflow works.

## 📋 Requirements

### Setup
- [ ] Clone repo from GitHub
- [ ] `docker compose up` works (DEC-005: zero-config)
- [ ] `bash run_tests.sh` passes
- [ ] Create feature branch, make small change, open PR

### Verify
- [ ] AVAROS container starts and connects to OVOS bus
- [ ] MockAdapter responds to test queries
- [ ] Can see logs via `docker logs avaros_skill`

## ✅ Acceptance Criteria
- Full environment running on Emre's machine
- Tests pass locally
- First PR opened (even if trivial fix/improvement)

## 📦 Deliverables
1. Confirmation: environment running
2. First PR submitted

**Points:** 2  
**Dependencies:** P1-E00 ✅, P1-L02 ✅ (Docker config exists)  
**Owner:** Emre
