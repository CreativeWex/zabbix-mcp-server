"""Shared logging utilities for tool call instrumentation."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def tool_span(
    tool_name: str,
    params: dict[str, Any],
) -> AsyncGenerator[None, None]:
    """Async context manager that emits a structured log entry for a tool call.

    Logs ``outcome="success"`` on clean exit and ``outcome="error"`` on
    exception. Sensitive fields (tokens, passwords) must be removed from
    ``params`` by the caller before passing them here.

    Args:
        tool_name: Name of the MCP tool being invoked.
        params: Sanitized input parameters for the log entry.

    Yields:
        Control to the caller.
    """
    start = time.monotonic()
    try:
        yield
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "tool_call",
            tool_name=tool_name,
            params=params,
            duration_ms=duration_ms,
            outcome="success",
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_call",
            tool_name=tool_name,
            params=params,
            duration_ms=duration_ms,
            outcome="error",
            error_message=str(exc),
        )
        raise
