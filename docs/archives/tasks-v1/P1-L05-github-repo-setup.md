# Task P1-L05: Create GitHub Repo for Team

## 🎯 Objective
Push AVAROS codebase to GitHub so Emre can clone, branch, and submit PRs.
Set up branch protection and basic CI.

## 📋 Requirements

### Functional
- [ ] Public or private GitHub repo created
- [ ] `main` branch protected (no direct push)
- [ ] Emre added as collaborator
- [ ] `.gitignore` covers Python, Docker, OVOS artifacts

### Technical
- [ ] Push existing code from `/home/ubuntu/avaros-ovos-skill`
- [ ] Branch protection: require PR + 1 approval for `main`
- [ ] Add GitHub Actions CI (optional, can be minimal):
  - `pytest` on push/PR
  - Python lint check
- [ ] Verify Emre can clone and run `docker compose up`

## ✅ Acceptance Criteria
- Emre can `git clone`, create branch, push, open PR
- Direct push to `main` is blocked
- README or GETTING-STARTED.md has clone + run instructions

## 📦 Deliverables
1. GitHub repository URL
2. Emre's invite sent
3. Branch protection rules configured
4. Updated `GETTING-STARTED.md` with clone instructions

## 📚 Resources
- GitHub branch protection docs
- Current `.gitignore` in repo
- [GETTING-STARTED.md](../../GETTING-STARTED.md)

## 🎯 Success Criteria
- [ ] Emre clones repo successfully
- [ ] PR workflow works (create branch → push → PR → review)
- [ ] Ready for P1-E00 (Emre's codebase onboarding)

**Points:** 3  
**Dependencies:** P1-L04 ✅ (system proven working before sharing)  
**Owner:** Lead
