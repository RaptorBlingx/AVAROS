---
applyTo: "**"
---
# Zero-Config / Zero-Touch Development Rules

## 🎯 Core Principle
> **Clone → Docker Compose Up → Working System**
> 
> Users should NEVER edit code files or YAML configs to run AVAROS.
> All configuration happens via Web UI or API.

## User Experience Target
\`\`\`bash
git clone https://github.com/artibilim/avaros-ovos-skill.git
cd avaros-ovos-skill
docker compose up -d
# Open http://localhost:8080 → First-run wizard guides setup
\`\`\`

## Architecture for Zero-Config

### 1. Default Mock Mode (Works Out-of-Box)
- On first run, AVAROS starts with \`MockAdapter\`
- All intents work with sample data
- No external API required
- User can explore full functionality immediately

### 2. Configuration via Web UI (NOT Files)
\`\`\`
┌─────────────────────────────────────────┐
│           AVAROS Web Console            │
├─────────────────────────────────────────┤
│  🔧 Settings                            │
│  ├── Platform Connection                │
│  │   ├── Type: [RENERYO ▼]             │
│  │   ├── API URL: [________________]    │
│  │   ├── API Key: [________________]    │
│  │   └── [Test Connection] [Save]       │
│  ├── Data Sources                       │
│  ├── Alert Thresholds                   │
│  └── User Management                    │
└─────────────────────────────────────────┘
\`\`\`

### 3. Settings Persistence
\`\`\`python
# Settings stored in database, NOT in YAML files
class SettingsService:
    """Runtime configuration via database"""
    
    def get_platform_config(self) -> PlatformConfig:
        return self.db.query(Settings).filter_by(category="platform").first()
    
    def update_platform_config(self, config: PlatformConfig) -> None:
        # Validates, saves to DB, hot-reloads adapter
        self.db.merge(Settings(category="platform", data=config.dict()))
        self.adapter_factory.reload()  # No restart required
\`\`\`

### 4. Environment Variables (Minimal, with Defaults)
\`\`\`bash
# .env.example - ALL have sensible defaults
AVAROS_PORT=8080                    # Default: 8080
AVAROS_LOG_LEVEL=INFO               # Default: INFO
AVAROS_DB_PATH=/data/avaros.db      # Default: SQLite in container
# NO platform credentials here - those go via Web UI
\`\`\`

## Implementation Rules

### ❌ NEVER DO THIS
\`\`\`python
# BAD: Hardcoded config file path
config = yaml.load(open("config/backends/reneryo.yaml"))

# BAD: Require user to edit files
# "Edit config/settings.yaml and set your API key"
\`\`\`

### ✅ ALWAYS DO THIS
\`\`\`python
# GOOD: Config from settings service (backed by DB)
config = self.settings_service.get_platform_config()

# GOOD: First-run detection with setup wizard
if not self.settings_service.is_configured():
    return RedirectResponse("/setup")
\`\`\`

## First-Run Wizard Flow
1. Welcome screen → explains AVAROS
2. Platform selection → RENERYO, Mock, Custom
3. If external platform: enter credentials (stored encrypted in DB)
4. Test connection → validate API access
5. Optional: import sample data
6. Done → redirect to dashboard

## Hot-Reload on Config Change
- Settings changes apply WITHOUT container restart
- Adapter factory watches settings DB
- New adapter instance created on config change
- Zero downtime configuration

## File Structure
\`\`\`
avaros-ovos-skill/
├── docker-compose.yml       # Just works with defaults
├── .env.example             # Minimal, all optional
├── data/                    # Mounted volume for persistence
│   └── avaros.db           # SQLite (settings, audit logs)
└── NO config/*.yaml files for user editing!
\`\`\`
