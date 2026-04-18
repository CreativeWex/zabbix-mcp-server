"""Configuration module — loads and validates all environment variables at startup."""

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded exclusively from environment variables.

    Required:
        ZABBIX_URL: Base URL of the Zabbix server.
        ZABBIX_API_TOKEN: Zabbix API token (never logged).

    Optional:
        ZABBIX_TIMEOUT_SECONDS: HTTP timeout (default 10).
        ZABBIX_PAGE_LIMIT: Max objects per API page (default 100).
        LOG_LEVEL: Logging verbosity (default INFO).
    """

    model_config = SettingsConfigDict(
        env_prefix="ZABBIX_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    url: AnyHttpUrl
    api_token: str
    timeout_seconds: int = Field(default=10, ge=1)
    page_limit: int = Field(default=100, ge=1)
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("api_token")
    @classmethod
    def token_must_not_be_empty(cls, v: str) -> str:
        """Ensure the API token is not blank."""
        if not v.strip():
            raise ValueError("ZABBIX_API_TOKEN must not be empty")
        return v

    @field_validator("log_level")
    @classmethod
    def log_level_must_be_valid(cls, v: str) -> str:
        """Ensure log level is a recognised Python logging level."""
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}, got '{v}'")
        return upper

    def zabbix_url(self) -> str:
        """Return the Zabbix base URL as a plain string without trailing slash."""
        return str(self.url).rstrip("/")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the application settings, loading them on first call.

    Returns:
        A validated Settings instance.

    Raises:
        pydantic_settings.ValidationError: If required env vars are missing or invalid.
    """
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings


def reset_settings() -> None:
    """Reset cached settings — intended for use in tests only."""
    global _settings
    _settings = None
