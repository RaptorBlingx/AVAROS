# Task P1-L02: Create AVAROS Docker Integration

## 🎯 Objective
Create `docker-compose.avaros.yml` and `Dockerfile` so AVAROS runs as a separate
container that joins the WASABI `ovos` network (per DEC-010).

## 📋 Requirements

### Functional
- [ ] AVAROS container starts and connects to OVOS message bus
- [ ] Skill code is mounted (hot-reload friendly for dev)
- [ ] MockAdapter used by default (DEC-005: zero-config)

### Technical
- [ ] `docker/docker-compose.avaros.yml` — joins `ovos` external network
- [ ] `docker/Dockerfile` — Python 3.10, installs requirements, runs as `ovos` user
- [ ] Mounts `wasabi-ovos/ovos/config` (read-only) and `ovos/tmp`
- [ ] Environment: `ADAPTER_TYPE=mock`, `LOG_LEVEL=INFO`
- [ ] Skill registers on OVOS bus (check with bus monitor)

## 📐 Relevant DECs
- **DEC-005:** Zero-Config First Run (MockAdapter default)
- **DEC-010:** AVAROS as Separate Docker Service

## ✅ Acceptance Criteria
- `docker compose -f docker/docker-compose.avaros.yml up` starts without errors
- Container joins `ovos` network (verify with `docker network inspect ovos`)
- AVAROS logs show "Skill loaded" or equivalent

## 📦 Deliverables
1. `docker/docker-compose.avaros.yml`
2. Updated `docker/Dockerfile`
3. Brief notes on any env vars needed

## 📚 Resources
- [WASABI-DEPLOYMENT.md](../WASABI-DEPLOYMENT.md) — Step 2 (sections 2.1–2.5)
- [DECISIONS.md](../DECISIONS.md) — DEC-010
- Current `docker/Dockerfile` (update in place)

## 🎯 Success Criteria
- [ ] Container runs, no crash loop
- [ ] Shows on `ovos` network alongside WASABI containers
- [ ] Ready for P1-L03 (skill load test)

**Points:** 5  
**Dependencies:** P1-L01 ✅  
**Owner:** Lead
