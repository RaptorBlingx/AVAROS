# 🚨 IMPORTANT: Port Change & Security Note for Emre

**Date:** 2026-02-11  
**From:** Lead Developer (Mohamad)  
**For:** Emre  

---

## 🔄 Port Change: Web UI Now on 8081

**Old Port:** `8080`  
**New Port:** `8081`  

### Why?
Port 8080 was already in use by Keycloak in the WASABI environment. To avoid conflicts during deployment, we changed the Web UI to port 8081.

### What Changed?
1. **`docker/docker-compose.avaros.yml`** — Port mapping changed from `8080:8080` → `8081:8080`
2. **`web-ui/config.py`** — Added `http://localhost:8081` to `CORS_ORIGINS`

### Action Required
- Access Web UI at: **`http://localhost:8081`** (not 8080)
- Update any documentation or scripts that reference port 8080
- Frontend dev server (Vite) still runs on 5173 — no change needed

---

## 🔒 Security Best Practices (DEC-006 Compliance)

### ✅ CORRECT: Environment Variables via .env

**DO THIS:**
```yaml
# docker-compose.avaros.yml
services:
  avaros-web-ui:
    env_file:
      - ../.env  # ✅ Reference .env file
    environment:
      - AVAROS_DATABASE_URL=postgresql://...  # ✅ Non-sensitive config OK
```

**`.env` file (gitignored):**
```bash
AVAROS_WEB_API_KEY=your-secure-key-here  # ✅ Sensitive data in .env only
```

---

### ❌ NEVER DO THIS: Hardcoded Credentials

**DON'T DO THIS:**
```yaml
# docker-compose.avaros.yml
services:
  avaros-web-ui:
    environment:
      - AVAROS_WEB_API_KEY=emre-strong-key-123  # ❌ SECURITY VIOLATION!
```

**Why?**
- Docker Compose files are committed to version control
- Credentials would be visible in git history forever
- Violates DEC-006 (all credentials via SettingsService/env vars)
- Creates security risk for production deployments

---

## 📋 Security Checklist for Your Work

When working with Web UI or Docker:

- [ ] Never hardcode API keys, passwords, or tokens in any committed file
- [ ] Always use `.env` file for secrets (it's gitignored)
- [ ] Use `.env.example` as a template (committed, but no real secrets)
- [ ] Check `git status` before committing to ensure `.env` is not staged
- [ ] Generate strong keys with: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Test locally with `.env` before pushing to avoid "missing key" errors

---

## 📚 References

- **DEC-006:** All credentials via SettingsService, never hardcoded ([DEVELOPMENT.md L18-L251](../DEVELOPMENT.md))
- **Security Checklist:** See [docs/SECURITY-CHECKLIST.md](SECURITY-CHECKLIST.md)
- **Docker Setup:** See [docs/DEPLOYMENT-SETUP.md](DEPLOYMENT-SETUP.md)
- **`.env.example`:** Template with required/optional variables ([.env.example](../.env.example))

---

## ✅ Current Status

**All services running healthy on port 8081:**
- ✅ Web UI: `http://localhost:8081` (updated CORS)
- ✅ Mock RENERYO: `http://localhost:8090`
- ✅ PostgreSQL: Internal port 5432
- ✅ AVAROS Skill: Listener on messagebus

**Security verification:**
- ✅ No hardcoded credentials in `docker-compose.avaros.yml`
- ✅ `AVAROS_WEB_API_KEY` loaded from `.env` file
- ✅ `.env` file gitignored (line 53 in `.gitignore`)
- ✅ Web UI startup logs show no "key missing" warnings

---

## 🤝 Questions?

If you're unsure about environment variables or Docker configuration, ask the Lead before committing. Security issues are easier to prevent than to fix after they're in git history.

**Good job on the UI polish (ThemeProvider, logos) — keep it up!** 🎨
