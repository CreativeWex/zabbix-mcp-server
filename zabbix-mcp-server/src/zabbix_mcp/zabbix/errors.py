"""Custom exception hierarchy for Zabbix MCP Server.

All public exceptions inherit from ZabbixMCPError, ensuring every domain
error carries a human-readable message that can be safely returned to the
LLM without exposing raw Zabbix JSON payloads.
"""

from __future__ import annotations


class ZabbixMCPError(Exception):
    """Base exception for all Zabbix MCP domain errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class ZabbixAPIError(ZabbixMCPError):
    """Raised when the Zabbix API returns an application-level error response."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class ZabbixConnectionError(ZabbixMCPError):
    """Raised when network connectivity to the Zabbix server fails."""


class ZabbixAuthError(ZabbixMCPError):
    """Raised when Zabbix rejects the API token or denies permission."""


class ZabbixNotFoundError(ZabbixMCPError):
    """Raised when a requested Zabbix object does not exist."""


class ZabbixValidationError(ZabbixMCPError):
    """Raised when tool input validation fails before reaching the Zabbix API."""


def map_api_error(error: dict[str, object]) -> ZabbixMCPError:
    """Convert a Zabbix JSON-RPC error object into a typed exception.

    Args:
        error: The ``error`` dict from a Zabbix JSON-RPC error response.

    Returns:
        A ZabbixMCPError subclass with a human-readable message.
    """
    code = int(str(error.get("code", 0)))
    message = str(error.get("message", "Unknown error"))
    data = str(error.get("data", ""))

    detail = f"{message}: {data}" if data else message

    auth_keywords = ("not authoris", "not authorized", "no permissions", "auth")
    if any(kw in detail.lower() for kw in auth_keywords):
        return ZabbixAuthError(
            "Authentication failed. Verify your ZABBIX_API_TOKEN environment variable."
        )

    not_found_keywords = (
        "not found",
        "does not exist",
        "no such",
        "no triggers found",
    )
    if any(kw in detail.lower() for kw in not_found_keywords):
        return ZabbixNotFoundError(f"Object not found: {data or message}")

    return ZabbixAPIError(
        f"Zabbix API error [{code}]: {detail}",
        code=code,
    )
