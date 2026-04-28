"""Playwright E2E tests for the AVAROS Web UI configuration wizard.

Tests the full wizard flow end-to-end in a real browser:
  - Login with API key
  - Step 1: Platform Setup (RENERYO cookie auth)
  - Step 2: Asset Registration
  - Step 3: Metric Mapping
  - Step 4: Intent Activation
  - Step 5: Success Screen

Requires:
  - AVAROS web-ui running on http://localhost:8081
  - AVAROS_WEB_API_KEY set (default: raptorblingx)
  - For RENERYO tests: live RENERYO at deploys.int.arti.ac:30377 + valid session cookie

Run:
  source .venv-playwright/bin/activate
  pytest tests/test_e2e/test_wizard_playwright.py -v --headed  # with browser
  pytest tests/test_e2e/test_wizard_playwright.py -v            # headless
"""

from __future__ import annotations

import os
import re

import pytest
import requests

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("AVAROS_WEB_URL", "http://localhost:8081")
API_KEY = os.environ.get("AVAROS_WEB_API_KEY", "raptorblingx")
RENERYO_API_URL = os.environ.get(
    "RENERYO_API_URL", "http://deploys.int.arti.ac:30377"
)
RENERYO_SESSION_COOKIE = os.environ.get(
    "RENERYO_SESSION_COOKIE",
    "50e2a9a7-a030-4356-9b47-3db126c17c8d"
    ".azDOYokXB9DNsm9xBPb3SRJ5N36HQ6E5ehmH1RdyWyI%3D",
)
# Timeouts (ms)
NAV_TIMEOUT = 15_000
ACTION_TIMEOUT = 20_000
LONG_TIMEOUT = 30_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _reset_platform_config() -> None:
    """Reset AVAROS to unconfigured state via API."""
    resp = requests.delete(
        f"{BASE_URL}/api/v1/config/platform",
        headers={"X-API-Key": API_KEY},
        timeout=10,
    )
    # 200 = reset, 404 = already unconfigured — both are fine
    assert resp.status_code in (200, 404), (
        f"Failed to reset config: {resp.status_code} {resp.text}"
    )


def _login(page: Page) -> None:
    """Navigate to the app and enter the API key on the login screen."""
    page.goto(BASE_URL, wait_until="networkidle", timeout=NAV_TIMEOUT)

    # If we land on the login page, authenticate
    api_key_input = page.locator("input#api-key")
    if api_key_input.is_visible(timeout=3_000):
        api_key_input.fill(API_KEY)
        page.locator("button[type='submit']").click()
        # Wait for navigation away from login
        page.wait_for_url(re.compile(r"/(wizard|$)"), timeout=NAV_TIMEOUT)


def _navigate_to_wizard(page: Page) -> None:
    """Navigate to the wizard page with force=1 to bypass redirect."""
    page.goto(
        f"{BASE_URL}/wizard?force=1",
        wait_until="networkidle",
        timeout=NAV_TIMEOUT,
    )
    # Dismiss onboarding overlay if present
    _dismiss_onboarding(page)
    # Verify we're on step 1
    expect(page.get_by_text("Platform Setup", exact=False).first).to_be_visible(
        timeout=ACTION_TIMEOUT,
    )


def _dismiss_onboarding(page: Page) -> None:
    """Dismiss the onboarding overlay if it appears."""
    close_btn = page.locator("[data-onboarding-close], button:has-text('Got it'), button:has-text('Close')")
    if close_btn.first.is_visible(timeout=2_000):
        close_btn.first.click()
        page.wait_for_timeout(500)


def _wait_for_step(page: Page, step_text: str) -> None:
    """Wait until the wizard shows the expected step."""
    expect(page.get_by_text(step_text, exact=False).first).to_be_visible(
        timeout=ACTION_TIMEOUT,
    )


def _click_button(page: Page, text: str, *, timeout: int = ACTION_TIMEOUT) -> None:
    """Click a button by its visible text, scrolling into view if needed."""
    btn = page.get_by_role("button", name=text, exact=False).first
    btn.scroll_into_view_if_needed(timeout=timeout)
    expect(btn).to_be_visible(timeout=timeout)
    btn.click()


def _take_screenshot(page: Page, name: str) -> None:
    """Save a screenshot for debugging."""
    os.makedirs("test-results/screenshots", exist_ok=True)
    page.screenshot(path=f"test-results/screenshots/{name}.png")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def _check_services() -> None:
    """Verify Web UI is reachable before running tests."""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
    except Exception as exc:
        pytest.skip(f"AVAROS Web UI not reachable at {BASE_URL}: {exc}")


@pytest.fixture()
def wizard_page(page: Page, _check_services: None) -> Page:
    """Provide a logged-in page navigated to a fresh wizard."""
    page.set_default_timeout(ACTION_TIMEOUT)
    _reset_platform_config()
    _login(page)
    _navigate_to_wizard(page)
    return page


# ---------------------------------------------------------------------------
# Test: RENERYO Cookie Auth Wizard Flow
# ---------------------------------------------------------------------------
class TestReneryoWizardFlow:
    """Wizard walkthrough using live RENERYO with cookie authentication."""

    @pytest.fixture(autouse=True)
    def _check_reneryo(self) -> None:
        """Skip if RENERYO is not reachable."""
        try:
            resp = requests.get(
                f"{RENERYO_API_URL}/api/ui",
                timeout=5,
            )
            if resp.status_code != 200:
                pytest.skip(f"RENERYO not reachable: HTTP {resp.status_code}")
        except Exception as exc:
            pytest.skip(f"RENERYO not reachable at {RENERYO_API_URL}: {exc}")

    def test_step1_reneryo_cookie_auth(self, wizard_page: Page) -> None:
        """Step 1: Configure RENERYO with cookie auth, test connection, and save."""
        page = wizard_page

        _take_screenshot(page, "reneryo-step1-initial")

        # Click "Use API" to ensure we're in API mode (not mock)
        _click_button(page, "Use API")

        # Fill API URL
        url_input = page.locator("input[type='url']")
        expect(url_input).to_be_visible(timeout=ACTION_TIMEOUT)
        url_input.fill(RENERYO_API_URL)

        # Select "Session Cookie" auth type
        auth_select = page.locator("select")
        auth_select.select_option("cookie")

        # Fill session cookie value
        cookie_input = page.locator("input[type='password']")
        expect(cookie_input).to_be_visible(timeout=ACTION_TIMEOUT)
        cookie_input.fill(RENERYO_SESSION_COOKIE)

        _take_screenshot(page, "reneryo-step1-filled")

        # Test Connection
        _click_button(page, "Test Connection")

        # Wait for the test to complete (can take a few seconds)
        page.wait_for_timeout(3_000)
        _take_screenshot(page, "reneryo-step1-test-result")

        # Save & Continue
        _click_button(page, "Save & Continue")

        # Wait for step 2 - allow extra time for save
        _wait_for_step(page, "Asset Registration")
        _take_screenshot(page, "reneryo-step2")

    def test_full_reneryo_wizard_flow(self, wizard_page: Page) -> None:
        """Complete wizard with RENERYO cookie auth: Steps 1-5."""
        page = wizard_page

        # --- Step 1: Platform Setup (RENERYO) ---
        _click_button(page, "Use API")
        page.locator("input[type='url']").fill(RENERYO_API_URL)
        page.locator("select").select_option("cookie")
        page.locator("input[type='password']").fill(RENERYO_SESSION_COOKIE)
        _take_screenshot(page, "reneryo-full-step1")
        _click_button(page, "Save & Continue")
        _wait_for_step(page, "Asset Registration")

        # --- Step 2: Asset Registration (Skip for now) ---
        _take_screenshot(page, "reneryo-full-step2")
        _click_button(page, "Skip")
        _wait_for_step(page, "Metric Mapping")

        # --- Step 3: Metric Mapping (Skip for now) ---
        _take_screenshot(page, "reneryo-full-step3")
        _click_button(page, "Skip")
        _wait_for_step(page, "Intent Activation")

        # --- Step 4: Intent Activation ---
        page.wait_for_timeout(2_000)
        _take_screenshot(page, "reneryo-full-step4")
        _click_button(page, "Continue to Success")

        # --- Step 5: Success ---
        expect(
            page.get_by_text("AVAROS is now configured", exact=False).first
        ).to_be_visible(timeout=LONG_TIMEOUT)
        _take_screenshot(page, "reneryo-full-step5-success")


# ---------------------------------------------------------------------------
# Test: Wizard Navigation
# ---------------------------------------------------------------------------
class TestWizardNavigation:
    """Test wizard navigation controls (Back/Next buttons)."""

    def test_back_button_disabled_on_step1(self, wizard_page: Page) -> None:
        """Back button should be disabled on step 1."""
        page = wizard_page
        back_btn = page.get_by_role("button", name="Back", exact=True)
        expect(back_btn.first).to_be_disabled()

    def test_next_button_blocked_without_completing_step(
        self, wizard_page: Page
    ) -> None:
        """Next button should show a warning when step is not completed."""
        page = wizard_page
        _click_button(page, "Next")
        # Should show a warning message
        expect(
            page.get_by_text("Complete platform setup", exact=False).first
        ).to_be_visible(timeout=ACTION_TIMEOUT)

    def test_step_indicator_shows_progress(self, wizard_page: Page) -> None:
        """Step indicator should show 1 / 5 on first step."""
        page = wizard_page
        expect(page.get_by_text("1 / 5").first).to_be_visible(timeout=ACTION_TIMEOUT)


# ---------------------------------------------------------------------------
# Test: Platform Setup Step Details
# ---------------------------------------------------------------------------
class TestPlatformSetupStep:
    """Detailed tests for Step 1 — Platform Setup."""

    def test_status_cards_visible(self, wizard_page: Page) -> None:
        """System status cards (Configured, Database) should be visible."""
        page = wizard_page
        expect(page.get_by_text("Configured", exact=False).first).to_be_visible()
        expect(page.get_by_text("Database", exact=False).first).to_be_visible()

    def test_auth_type_shows_cookie_field(self, wizard_page: Page) -> None:
        """Selecting 'Session Cookie' auth type shows the cookie input."""
        page = wizard_page

        # Ensure we're in API mode
        _click_button(page, "Use API")

        # Select cookie auth
        page.locator("select").select_option("cookie")

        # Should see "Session Cookie Value" label
        expect(
            page.get_by_text("Session Cookie Value", exact=False).first
        ).to_be_visible(timeout=ACTION_TIMEOUT)

    def test_auth_type_none_hides_key_field(self, wizard_page: Page) -> None:
        """Selecting 'No Authentication' hides the key/cookie input."""
        page = wizard_page
        _click_button(page, "Use API")

        page.locator("select").select_option("none")

        # Password field should not be visible
        expect(page.locator("input[type='password']")).not_to_be_visible()

    def test_validation_requires_url(self, wizard_page: Page) -> None:
        """Save & Continue without URL shows validation error."""
        page = wizard_page
        _click_button(page, "Use API")

        # Clear URL if any
        url_input = page.locator("input[type='url']")
        url_input.fill("")

        # Try to save
        _click_button(page, "Save & Continue")

        # Should show validation error
        expect(
            page.get_by_text("URL is required", exact=False).first
        ).to_be_visible(timeout=ACTION_TIMEOUT)


# ---------------------------------------------------------------------------
# Test: Login Flow
# ---------------------------------------------------------------------------
class TestLogin:
    """Test the login / API key entry flow."""

    @pytest.fixture()
    def fresh_page(self, page: Page, _check_services: None) -> Page:
        """Provide a fresh page (not logged in)."""
        page.set_default_timeout(ACTION_TIMEOUT)
        # Clear localStorage to force login
        page.goto(BASE_URL, wait_until="networkidle", timeout=NAV_TIMEOUT)
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle", timeout=NAV_TIMEOUT)
        return page

    def test_login_page_shows_api_key_input(self, fresh_page: Page) -> None:
        """Login page should show API key input field."""
        page = fresh_page
        expect(page.locator("input#api-key")).to_be_visible(timeout=ACTION_TIMEOUT)
        expect(page.get_by_text("API Key", exact=False).first).to_be_visible()

    def test_login_with_valid_key(self, fresh_page: Page) -> None:
        """Valid API key should authenticate and redirect."""
        page = fresh_page
        page.locator("input#api-key").fill(API_KEY)
        page.locator("button[type='submit']").click()
        # Should navigate away from login
        page.wait_for_url(re.compile(r"/(wizard|$)"), timeout=NAV_TIMEOUT)
        _take_screenshot(page, "login-success")

    def test_login_with_invalid_key(self, fresh_page: Page) -> None:
        """Invalid API key should show error message."""
        page = fresh_page
        page.locator("input#api-key").fill("wrong-key-12345")
        page.locator("button[type='submit']").click()
        expect(
            page.get_by_text("Invalid API key", exact=False).first
        ).to_be_visible(timeout=ACTION_TIMEOUT)
