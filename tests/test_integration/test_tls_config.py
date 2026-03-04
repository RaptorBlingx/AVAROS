"""Tests for HTTPS/TLS infrastructure configuration (P4-L05).

Validates that Nginx configuration files, certificate generation script,
and Docker Compose changes are present and well-formed. These are static
configuration validation tests — no live Docker required.
"""

import stat
from pathlib import Path

import pytest

# All paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_DIR = REPO_ROOT / "docker"
NGINX_DIR = DOCKER_DIR / "nginx"


class TestNginxConfig:
    """Validate Nginx configuration files exist and are well-formed."""

    def test_nginx_config_exists(self) -> None:
        """Nginx config file is present."""
        assert (NGINX_DIR / "nginx.conf").exists()

    def test_nginx_config_has_tls_protocols(self) -> None:
        """Config includes TLS protocol restrictions."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "TLSv1.2" in content
        assert "TLSv1.3" in content

    def test_nginx_config_has_ssl_certificate_directives(self) -> None:
        """Config includes ssl_certificate directives."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "ssl_certificate" in content
        assert "ssl_certificate_key" in content

    def test_nginx_config_has_security_headers(self) -> None:
        """Config includes all required security headers."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "Strict-Transport-Security" in content
        assert "X-Frame-Options" in content
        assert "X-Content-Type-Options" in content
        assert "X-XSS-Protection" in content
        assert "Referrer-Policy" in content

    def test_nginx_config_has_http_to_https_redirect(self) -> None:
        """Config redirects HTTP to HTTPS."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "return 301 https://" in content

    def test_nginx_config_has_proxy_pass(self) -> None:
        """Config proxies to the Web UI upstream."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "proxy_pass http://web_ui" in content
        assert "upstream web_ui" in content

    def test_nginx_config_has_websocket_support(self) -> None:
        """Config includes WebSocket upgrade headers."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "Upgrade" in content
        assert "proxy_http_version 1.1" in content

    def test_nginx_config_has_forwarded_headers(self) -> None:
        """Config passes X-Forwarded-For and X-Forwarded-Proto."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "X-Forwarded-For" in content
        assert "X-Forwarded-Proto" in content

    def test_nginx_config_disallows_old_tls(self) -> None:
        """Config does not allow TLS 1.0 or 1.1."""
        content = (NGINX_DIR / "nginx.conf").read_text()
        assert "TLSv1.0" not in content
        assert "TLSv1.1" not in content
        assert "SSLv3" not in content


class TestNginxProductionConfig:
    """Validate production Nginx configuration template."""

    def test_production_config_exists(self) -> None:
        """Production Nginx config template is present."""
        assert (NGINX_DIR / "nginx-production.conf").exists()

    def test_production_config_uses_letsencrypt_paths(self) -> None:
        """Production config references Let's Encrypt cert paths."""
        content = (NGINX_DIR / "nginx-production.conf").read_text()
        assert "/etc/letsencrypt/" in content


class TestCertificateScript:
    """Validate the dev certificate generation script."""

    def test_generate_cert_script_exists(self) -> None:
        """Dev certificate generation script is present."""
        script = NGINX_DIR / "generate-dev-cert.sh"
        assert script.exists()

    def test_generate_cert_script_is_executable(self) -> None:
        """Dev certificate generation script is executable."""
        script = NGINX_DIR / "generate-dev-cert.sh"
        file_stat = script.stat()
        assert file_stat.st_mode & stat.S_IXUSR

    def test_generate_cert_script_uses_openssl(self) -> None:
        """Script uses openssl for certificate generation."""
        content = (NGINX_DIR / "generate-dev-cert.sh").read_text()
        assert "openssl req" in content

    def test_generate_cert_script_sets_san(self) -> None:
        """Script sets Subject Alternative Names for localhost."""
        content = (NGINX_DIR / "generate-dev-cert.sh").read_text()
        assert "subjectAltName" in content
        assert "localhost" in content


class TestCertbotRenewalScript:
    """Validate the Let's Encrypt renewal script."""

    def test_certbot_renew_script_exists(self) -> None:
        """Certbot renewal script is present."""
        assert (DOCKER_DIR / "certbot-renew.sh").exists()

    def test_certbot_renew_script_is_executable(self) -> None:
        """Certbot renewal script is executable."""
        script = DOCKER_DIR / "certbot-renew.sh"
        file_stat = script.stat()
        assert file_stat.st_mode & stat.S_IXUSR

    def test_certbot_renew_script_reloads_nginx(self) -> None:
        """Renewal script reloads Nginx after renewal."""
        content = (DOCKER_DIR / "certbot-renew.sh").read_text()
        assert "nginx -s reload" in content


class TestDevComposeOverride:
    """Validate the dev Docker Compose override."""

    def test_dev_override_exists(self) -> None:
        """Dev compose override file exists."""
        assert (DOCKER_DIR / "docker-compose.dev.yml").exists()

    def test_dev_override_exposes_port_8081(self) -> None:
        """Dev override re-exposes Web UI on port 8081."""
        content = (DOCKER_DIR / "docker-compose.dev.yml").read_text()
        assert "8081:8080" in content


class TestDockerComposeProxy:
    """Validate avaros-proxy service in docker-compose.avaros.yml."""

    @pytest.fixture()
    def compose_content(self) -> str:
        """Read docker-compose.avaros.yml content."""
        return (DOCKER_DIR / "docker-compose.avaros.yml").read_text()

    def test_proxy_service_defined(self, compose_content: str) -> None:
        """Docker Compose includes avaros-proxy service."""
        assert "avaros-proxy:" in compose_content

    def test_proxy_uses_nginx_image(self, compose_content: str) -> None:
        """Proxy service uses nginx alpine image."""
        assert "nginx:" in compose_content
        assert "alpine" in compose_content

    def test_proxy_mounts_nginx_config(self, compose_content: str) -> None:
        """Proxy service mounts nginx.conf."""
        assert "nginx.conf:/etc/nginx/conf.d/default.conf" in compose_content

    def test_proxy_mounts_ssl_certs(self, compose_content: str) -> None:
        """Proxy service mounts SSL directory."""
        assert "nginx/ssl:/etc/nginx/ssl" in compose_content

    def test_proxy_mounts_letsencrypt_volume(self, compose_content: str) -> None:
        """Proxy service mounts Let's Encrypt certificates volume."""
        assert "letsencrypt_certs:/etc/letsencrypt" in compose_content

    def test_web_ui_not_directly_exposed(self, compose_content: str) -> None:
        """Web UI no longer exposes port 8081 directly."""
        # The compose file should use 'expose' not 'ports' for web-ui
        # Find the web-ui section and check it doesn't have ports: 8081
        lines = compose_content.split("\n")
        in_web_ui = False
        in_proxy = False
        for line in lines:
            if "avaros-web-ui:" in line and "container_name" not in line:
                in_web_ui = True
                in_proxy = False
            elif "avaros-proxy:" in line and "container_name" not in line:
                in_web_ui = False
                in_proxy = True
            elif (
                line.strip()
                and not line.startswith(" ")
                and not line.startswith("\t")
            ):
                in_web_ui = False
                in_proxy = False

            if in_web_ui and "8081:8080" in line:
                pytest.fail(
                    "Web UI should not directly expose port 8081 "
                    "in production compose"
                )


class TestDockerComposeCertbot:
    """Validate certbot service wiring in docker-compose.avaros.yml."""

    @pytest.fixture()
    def compose_content(self) -> str:
        """Read docker-compose.avaros.yml content."""
        return (DOCKER_DIR / "docker-compose.avaros.yml").read_text()

    def test_certbot_service_defined(self, compose_content: str) -> None:
        """Docker Compose includes certbot service."""
        assert "certbot:" in compose_content
        assert "certbot/certbot" in compose_content

    def test_certbot_conditional_domain_check(self, compose_content: str) -> None:
        """Certbot command checks LETSENCRYPT_DOMAIN before requesting cert."""
        assert "LETSENCRYPT_DOMAIN not set; skipping certificate acquisition" in compose_content

    def test_certbot_and_proxy_share_letsencrypt_volume(
        self, compose_content: str,
    ) -> None:
        """Certbot and proxy share /etc/letsencrypt persisted volume."""
        assert "letsencrypt_certs:/etc/letsencrypt" in compose_content
        assert "letsencrypt_certs:" in compose_content


class TestSkillHealthcheck:
    """Validate runtime health check semantics for avaros_skill service."""

    def test_skill_healthcheck_uses_http_endpoint(self) -> None:
        """Skill health check probes Web UI /health endpoint over HTTP."""
        content = (DOCKER_DIR / "docker-compose.avaros.yml").read_text()
        assert "urllib.request.urlopen('http://avaros-web-ui:8080/health')" in content
        assert "from skill import AVAROSSkill" not in content


class TestSslDirectory:
    """Validate the SSL directory structure."""

    def test_ssl_directory_exists(self) -> None:
        """SSL directory exists with .gitkeep."""
        assert (NGINX_DIR / "ssl").is_dir()
        assert (NGINX_DIR / "ssl" / ".gitkeep").exists()


class TestGitignore:
    """Validate .gitignore includes TLS certificate exclusions."""

    def test_gitignore_excludes_pem_files(self) -> None:
        """Gitignore prevents committing generated certificates."""
        content = (REPO_ROOT / ".gitignore").read_text()
        assert "docker/nginx/ssl/*.pem" in content
