"""Tests for config.py — TC-001 through TC-007."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from zabbix_mcp.config import Settings, reset_settings


@pytest.fixture(autouse=True)
def _clear_settings() -> None:
    """Reset the cached settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


# ------------------------------------------------------------------ TC-001

def test_settings_valid_env_vars() -> None:
    """TC-001: Settings loads successfully with all required variables."""
    s = Settings(url="https://zabbix.example.com", api_token="abc123token")  # type: ignore[call-arg]
    assert str(s.url).startswith("https://zabbix.example.com")
    assert s.api_token == "abc123token"


# ------------------------------------------------------------------ TC-002

def test_settings_missing_url_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """TC-002: ValidationError when ZABBIX_URL is absent."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZABBIX_URL", raising=False)
    monkeypatch.delenv("ZABBIX_API_TOKEN", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(api_token="abc123token")  # type: ignore[call-arg]
    assert "url" in str(exc_info.value).lower()


# ------------------------------------------------------------------ TC-003

def test_settings_missing_token_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """TC-003: ValidationError when ZABBIX_API_TOKEN is absent."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZABBIX_URL", raising=False)
    monkeypatch.delenv("ZABBIX_API_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        Settings(url="https://zabbix.example.com")  # type: ignore[call-arg]


# ------------------------------------------------------------------ TC-004

def test_settings_defaults() -> None:
    """TC-004: Optional variables have correct default values."""
    s = Settings(url="https://zabbix.example.com", api_token="tok")  # type: ignore[call-arg]
    assert s.timeout_seconds == 10
    assert s.page_limit == 100
    assert s.log_level == "INFO"


# ------------------------------------------------------------------ TC-005

def test_settings_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-005: ZABBIX_TIMEOUT_SECONDS is respected."""
    monkeypatch.setenv("ZABBIX_TIMEOUT_SECONDS", "30")
    s = Settings(url="https://zabbix.example.com", api_token="tok")  # type: ignore[call-arg]
    assert s.timeout_seconds == 30


# ------------------------------------------------------------------ TC-006

def test_settings_page_limit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-006: ZABBIX_PAGE_LIMIT=1 is accepted."""
    monkeypatch.setenv("ZABBIX_PAGE_LIMIT", "1")
    s = Settings(url="https://zabbix.example.com", api_token="tok")  # type: ignore[call-arg]
    assert s.page_limit == 1


# ------------------------------------------------------------------ TC-007

def test_settings_invalid_url_raises() -> None:
    """TC-007: A non-HTTP URL raises ValidationError at startup."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(url="not-a-valid-url", api_token="abc123")  # type: ignore[call-arg]
    error_str = str(exc_info.value)
    assert "url" in error_str.lower() or "zabbix_url" in error_str.lower()


# ------------------------------------------------------------------ extra

def test_settings_empty_token_raises() -> None:
    """API token must not be blank."""
    with pytest.raises(ValidationError):
        Settings(url="https://zabbix.example.com", api_token="  ")  # type: ignore[call-arg]


def test_settings_zabbix_url_strips_slash() -> None:
    """zabbix_url() helper strips trailing slash."""
    s = Settings(url="https://zabbix.example.com/", api_token="tok")  # type: ignore[call-arg]
    assert not s.zabbix_url().endswith("/")


def test_settings_log_level_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_LEVEL env var is read and uppercased."""
    monkeypatch.setenv("LOG_LEVEL", "debug")
    s = Settings(url="https://zabbix.example.com", api_token="tok")  # type: ignore[call-arg]
    assert s.log_level == "DEBUG"
