"""Validate playbook references against real code and configuration.

These tests ensure the Pilot Deployment Playbook (docs/PILOT-PLAYBOOK.md)
stays accurate as the codebase evolves.  Each test cross-references a
documentation claim against the actual files in the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCALE_DIR = ROOT / "skill" / "locale" / "en-us"
DOCKER_COMPOSE = ROOT / "docker" / "docker-compose.avaros.yml"
PLAYBOOK = ROOT / "docs" / "PILOT-PLAYBOOK.md"
ENV_EXAMPLE = ROOT / ".env.example"
VOICE_COMMANDS = ROOT / "docs" / "VOICE-COMMANDS.md"


class TestIntentFilesExist:
    """Voice commands reference card matches locale files."""

    EXPECTED_INTENTS = [
        "kpi.energy.per_unit.intent",
        "kpi.oee.intent",
        "kpi.scrap_rate.intent",
        "compare.energy.intent",
        "trend.energy.intent",
        "trend.scrap.intent",
        "anomaly.production.check.intent",
        "whatif.temperature.intent",
    ]

    @pytest.mark.parametrize("intent_file", EXPECTED_INTENTS)
    def test_intent_file_exists(self, intent_file: str) -> None:
        """Every intent referenced in the playbook has a locale file."""
        path = LOCALE_DIR / intent_file
        assert path.exists(), f"Intent file missing: {path}"

    def test_no_extra_intents_in_playbook(self) -> None:
        """Playbook does not reference intents that don't exist."""
        actual_intents = {
            f.name for f in LOCALE_DIR.iterdir() if f.name.endswith(".intent")
        }
        referenced = set(self.EXPECTED_INTENTS)
        for intent in referenced:
            assert intent in actual_intents, (
                f"Playbook references {intent} but file not found in locale"
            )


class TestDockerComposeReferences:
    """Docker Compose references in the playbook are accurate."""

    def test_docker_compose_file_exists(self) -> None:
        """The Docker Compose file referenced in the playbook exists."""
        assert DOCKER_COMPOSE.exists()

    def test_services_in_docker_compose(self) -> None:
        """All services mentioned in the playbook exist in Docker Compose."""
        content = DOCKER_COMPOSE.read_text()
        expected_services = [
            "avaros_db",
            "avaros_skill",
            "avaros-web-ui",
            "reneryo-data-generator-api",
            "avaros-proxy",
        ]
        for service in expected_services:
            assert service in content, (
                f"Service '{service}' referenced in playbook "
                f"but not found in docker-compose.avaros.yml"
            )


class TestEnvVariableReferences:
    """Environment variables in .env.example match Docker Compose."""

    def test_env_example_exists(self) -> None:
        """The .env.example template file exists in the repo root."""
        assert ENV_EXAMPLE.exists()

    def test_adapter_type_in_env_example(self) -> None:
        """ADAPTER_TYPE appears in .env.example."""
        content = ENV_EXAMPLE.read_text()
        assert "ADAPTER_TYPE" in content

    def test_database_url_in_env_example(self) -> None:
        """AVAROS_DATABASE_URL appears in .env.example."""
        content = ENV_EXAMPLE.read_text()
        assert "AVAROS_DATABASE_URL" in content

    def test_https_port_in_env_example(self) -> None:
        """AVAROS_HTTPS_PORT appears in .env.example."""
        content = ENV_EXAMPLE.read_text()
        assert "AVAROS_HTTPS_PORT" in content

    def test_adapter_type_in_docker_compose(self) -> None:
        """ADAPTER_TYPE appears in Docker Compose environment."""
        content = DOCKER_COMPOSE.read_text()
        assert "ADAPTER_TYPE" in content


class TestPlaybookStructure:
    """Playbook document has all required sections."""

    REQUIRED_SECTIONS = [
        "Overview",
        "Prerequisites",
        "Installation Procedure",
        "First-Run Configuration",
        "Data Source Mapping",
        "Production Data Setup",
        "Emission Factor Configuration",
        "KPI Baseline Recording",
        "Ongoing Operations",
        "Measurement Schedule",
        "Troubleshooting",
        "Rollback and Recovery",
        "Site-Specific Appendices",
        "Security and Privacy",
    ]

    def test_playbook_exists(self) -> None:
        """The playbook document exists."""
        assert PLAYBOOK.exists()

    @pytest.mark.parametrize("section", REQUIRED_SECTIONS)
    def test_section_present(self, section: str) -> None:
        """Each required section appears in the playbook."""
        content = PLAYBOOK.read_text()
        assert section in content, (
            f"Section '{section}' not found in PILOT-PLAYBOOK.md"
        )

    def test_no_internal_file_references(self) -> None:
        """Playbook does not reference local-only files."""
        content = PLAYBOOK.read_text()
        forbidden = [".github/", "docs/TODO.md", "docs/PROJECT-STATUS.md"]
        for ref in forbidden:
            assert ref not in content, (
                f"Playbook references internal file: {ref}"
            )

    def test_d31_deliverable_mentioned(self) -> None:
        """Playbook references D3.1 deliverable."""
        content = PLAYBOOK.read_text()
        assert "D3.1" in content

    def test_wasabi_kpi_targets_present(self) -> None:
        """Playbook states the three WASABI KPI targets."""
        content = PLAYBOOK.read_text()
        assert "8%" in content, "Missing 8% electricity target"
        assert "5%" in content, "Missing 5% material efficiency target"
        assert "10%" in content, "Missing 10% CO₂ target"


class TestCriticalProceduralClaims:
    """Validate critical operational claims in the playbook."""

    def test_auth_flow_uses_api_key_not_cookie_auth(self) -> None:
        """Wizard auth instructions must match implemented API-key model."""
        content = PLAYBOOK.read_text()
        assert "API key" in content or "API Key" in content
        assert "cookie-based" not in content.lower()

    def test_letsencrypt_is_not_claimed_as_automatic(self) -> None:
        """Playbook must not claim unsupported auto Let's Encrypt flow."""
        content = PLAYBOOK.read_text()
        assert "certificate will be obtained automatically" not in content

    def test_letsencrypt_marked_as_not_yet_available(self) -> None:
        """Playbook should clearly state current Let's Encrypt limitation."""
        content = PLAYBOOK.read_text()
        assert "not yet available in the current stack" in content


class TestVoiceCommandsReference:
    """Voice commands quick reference document is consistent."""

    def test_voice_commands_file_exists(self) -> None:
        """VOICE-COMMANDS.md exists."""
        assert VOICE_COMMANDS.exists()

    def test_all_intent_categories_covered(self) -> None:
        """Voice commands doc covers all intent categories."""
        content = VOICE_COMMANDS.read_text()
        categories = [
            "Energy",
            "OEE",
            "Scrap",
            "Comparison",
            "Trend",
            "Anomaly",
            "What-If",
        ]
        for category in categories:
            assert category.lower() in content.lower(), (
                f"Category '{category}' not found in VOICE-COMMANDS.md"
            )
