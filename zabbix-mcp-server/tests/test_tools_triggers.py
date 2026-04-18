"""Tests for tools/triggers.py — TC-051 through TC-056."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import SAMPLE_HOST, SAMPLE_TRIGGER
from zabbix_mcp.tools.triggers import create_trigger, get_triggers
from zabbix_mcp.zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ TC-051

@pytest.mark.asyncio
async def test_get_triggers_with_triggers(mock_client: object) -> None:
    """TC-051: Host with triggers returns list with expression and state."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.trigger_get = AsyncMock(return_value=[SAMPLE_TRIGGER])  # type: ignore[attr-defined]

    result = await get_triggers(mock_client, host="db-01")  # type: ignore[arg-type]
    data = json.loads(result)

    assert len(data) == 1
    assert data[0]["trigger_id"] == "301"
    assert "expression" in data[0]
    assert "state" in data[0]
    assert "priority" in data[0]


# ------------------------------------------------------------------ TC-052

@pytest.mark.asyncio
async def test_get_triggers_no_triggers_returns_empty_list(mock_client: object) -> None:
    """TC-052: Host without triggers returns empty JSON array."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.trigger_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await get_triggers(mock_client, host="untriggered-host")  # type: ignore[arg-type]
    assert result == "[]"


# ------------------------------------------------------------------ TC-053

@pytest.mark.asyncio
async def test_get_triggers_nonexistent_host_raises(mock_client: object) -> None:
    """TC-053: Non-existent host raises ZabbixNotFoundError."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    with pytest.raises(ZabbixNotFoundError, match="ghost-host-xyz"):
        await get_triggers(mock_client, host="ghost-host-xyz")  # type: ignore[arg-type]


# ------------------------------------------------------------------ TC-054

@pytest.mark.asyncio
async def test_create_trigger_valid_expression(mock_client: object) -> None:
    """TC-054: Valid Zabbix 7.0 expression creates trigger and returns trigger_id."""
    mock_client.trigger_create = AsyncMock(return_value="5001")  # type: ignore[attr-defined]

    result = await create_trigger(
        mock_client,  # type: ignore[arg-type]
        name="High CPU",
        expression="last(/web-server-01/system.cpu.util)>90",
        priority=3,
    )
    data = json.loads(result)
    assert data["trigger_id"] == "5001"
    assert data["status"] == "created"


# ------------------------------------------------------------------ TC-055

@pytest.mark.asyncio
async def test_create_trigger_invalid_expression_raises(mock_client: object) -> None:
    """TC-055: Invalid expression syntax raises ZabbixValidationError before Zabbix call."""
    with pytest.raises(ZabbixValidationError, match="[Ii]nvalid"):
        await create_trigger(
            mock_client,  # type: ignore[arg-type]
            name="Bad Trigger",
            expression="INVALID EXPRESSION SYNTAX !!!",
        )
    mock_client.trigger_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-056

@pytest.mark.asyncio
async def test_create_trigger_missing_name_raises(mock_client: object) -> None:
    """TC-056: Empty name raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="name"):
        await create_trigger(
            mock_client,  # type: ignore[arg-type]
            name="",
            expression="last(/h/k)>0",
        )
    mock_client.trigger_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ extra

@pytest.mark.asyncio
async def test_create_trigger_invalid_priority_raises(mock_client: object) -> None:
    """Priority outside 0–5 raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="priority"):
        await create_trigger(
            mock_client,  # type: ignore[arg-type]
            name="High CPU",
            expression="last(/h/k)>90",
            priority=10,
        )


@pytest.mark.asyncio
async def test_create_trigger_empty_expression_raises(mock_client: object) -> None:
    """Empty expression raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError):
        await create_trigger(
            mock_client,  # type: ignore[arg-type]
            name="High CPU",
            expression="",
        )
