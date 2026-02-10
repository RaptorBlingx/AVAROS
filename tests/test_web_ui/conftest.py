"""
Shared fixtures for Web UI backend tests.

Provides FastAPI TestClient with an in-memory SettingsService
dependency override.  Uses SQLAlchemy ``StaticPool`` so that the
single in-memory SQLite connection is shared across threads
(TestClient dispatches requests on a background thread).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure the web-ui package is importable by adding it to sys.path.
_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from main import app  # noqa: E402 — path must be inserted first
from config import WEB_API_KEY  # noqa: E402
from dependencies import get_settings_service  # noqa: E402
from skill.services.settings import Base, SettingsService  # noqa: E402

# Re-export so test modules can import from conftest if needed.
TEST_API_KEY = WEB_API_KEY


def _create_test_settings_service() -> SettingsService:
    """Build a SettingsService backed by a thread-safe in-memory SQLite.

    The default ``sqlite:///:memory:`` engine uses per-thread
    connections, so tables created on the main thread are invisible
    to the TestClient request thread.  ``StaticPool`` forces a single
    shared connection, solving this problem.
    """
    svc = SettingsService()
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    svc._engine = engine
    svc._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    svc._initialized = True
    return svc


@pytest.fixture()
def settings_service() -> Generator[SettingsService, None, None]:
    """In-memory SettingsService, initialised and ready for one test."""
    svc = _create_test_settings_service()
    yield svc
    svc.close()


@pytest.fixture()
def api_key_header() -> dict[str, str]:
    """Return auth header dict for authenticated test requests."""
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture()
def client(settings_service: SettingsService) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with SettingsService override and auth header.

    The ``X-API-Key`` header is injected automatically so that all
    ``/api/v1/`` requests pass the auth middleware.  Tests that
    explicitly need to omit the key should use ``client_no_auth``.
    """

    def _override() -> SettingsService:
        return settings_service

    app.dependency_overrides[get_settings_service] = _override
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture()
def client_no_auth(
    settings_service: SettingsService,
) -> Generator[TestClient, None, None]:
    """TestClient **without** the API-key header — for auth rejection tests."""

    def _override() -> SettingsService:
        return settings_service

    app.dependency_overrides[get_settings_service] = _override
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()
