# Task P1-L01: Deploy WASABI OVOS Locally

## 🎯 Objective
Get the WASABI OVOS stack running on the development server (`/home/ubuntu/wasabi-ovos`).
This is the foundation — AVAROS skill deploys INTO this infrastructure.

## 📋 Requirements

### Functional
- [ ] All WASABI containers start and stay healthy
- [ ] OVOS message bus is reachable
- [ ] Dozzle log viewer accessible at http://localhost:8888
- [ ] Hivemind client created for AVAROS

### Technical
- [ ] Copy all `.sample` → `.env` files
- [ ] Create `ovos` Docker network
- [ ] Pull all images (use `--ignore-pull-failures` for optional ones)
- [ ] Start full stack with all compose files
- [ ] Verify `ovos_core`, `ovos_messagebus` logs show no errors

## ✅ Acceptance Criteria
- `docker ps` shows all WASABI containers running
- `ovos_messagebus` log shows "Message bus service started"
- Hivemind client `avaros-client` exists
- Credentials saved securely for Step 2

## 📦 Deliverables
1. Running WASABI stack
2. Saved Hivemind client credentials (access-key + password)
3. Screenshot or log snippet confirming healthy state

## 📚 Resources
- [WASABI-DEPLOYMENT.md](../WASABI-DEPLOYMENT.md) — Step 1 (sections 1.1–1.8)
- WASABI OVOS repo README at `/home/ubuntu/wasabi-ovos/README.md`

## 🎯 Success Criteria
- [ ] `docker compose ps` — all services "Up"
- [ ] No crash loops in any container (check with `docker compose logs`)
- [ ] Ready for P1-L02 (AVAROS integration)

**Points:** 3  
**Dependencies:** None  
**Owner:** Lead
