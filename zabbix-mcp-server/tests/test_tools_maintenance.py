"""Tests for tools/maintenance.py — TC-026 through TC-031."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import SAMPLE_HOST, SAMPLE_MAINTENANCE
from zabbix_mcp.tools.maintenance import create_maintenance
from zabbix_mcp.zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ TC-026

@pytest.mark.asyncio
async def test_create_maintenance_for_single_host(mock_client: object) -> None:
    """TC-026: Create maintenance for one host returns maintenance_id."""
    mock_client.maintenance_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.maintenance_create = AsyncMock(return_value="2001")  # type: ignore[attr-defined]

    result = await create_maintenance(
        mock_client,  # type: ignore[arg-type]
        name="test-maint-01",
        reason="Planned OS upgrade",
        duration_minutes=60,
        host="app-server-01",
    )
    data = json.loads(result)
    assert data["maintenance_id"] == "2001"
    assert data["status"] == "created"


# ------------------------------------------------------------------ TC-027

@pytest.mark.asyncio
async def test_create_maintenance_for_host_group(mock_client: object) -> None:
    """TC-027: Create maintenance scoped to a host group."""
    mock_client.maintenance_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.hostgroup_get = AsyncMock(  # type: ignore[attr-defined]
        return_value=[{"groupid": "10", "name": "Database Servers"}]
    )
    mock_client.maintenance_create = AsyncMock(return_value="2002")  # type: ignore[attr-defined]

    result = await create_maintenance(
        mock_client,  # type: ignore[arg-type]
        name="db-maint",
        reason="DB patching",
        duration_minutes=30,
        host_group="Database Servers",
    )
    data = json.loads(result)
    assert data["maintenance_id"] == "2002"


# ------------------------------------------------------------------ TC-028

@pytest.mark.asyncio
async def test_create_maintenance_minimum_duration(mock_client: object) -> None:
    """TC-028: duration_minutes=1 is accepted."""
    mock_client.maintenance_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.maintenance_create = AsyncMock(return_value="2003")  # type: ignore[attr-defined]

    result = await create_maintenance(
        mock_client,  # type: ignore[arg-type]
        name="quick-test",
        reason="Quick test",
        duration_minutes=1,
        host="test-host-01",
    )
    data = json.loads(result)
    assert data["status"] == "created"


# ------------------------------------------------------------------ TC-029

@pytest.mark.asyncio
async def test_create_maintenance_missing_reason_raises(mock_client: object) -> None:
    """TC-029: Empty reason raises ZabbixValidationError without calling Zabbix."""
    with pytest.raises(ZabbixValidationError, match="reason"):
        await create_maintenance(
            mock_client,  # type: ignore[arg-type]
            name="bad",
            reason="",
            duration_minutes=60,
            host="test-host",
        )
    mock_client.maintenance_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-030

@pytest.mark.asyncio
async def test_create_maintenance_nonexistent_host_raises(mock_client: object) -> None:
    """TC-030: Non-existent host name raises ZabbixNotFoundError."""
    mock_client.maintenance_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    with pytest.raises(ZabbixNotFoundError, match="phantom-host-999"):
        await create_maintenance(
            mock_client,  # type: ignore[arg-type]
            name="bad-maint",
            reason="Test",
            duration_minutes=60,
            host="phantom-host-999",
        )
    mock_client.maintenance_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-031

@pytest.mark.asyncio
async def test_create_maintenance_idempotent(mock_client: object) -> None:
    """TC-031: Second call with same name returns existing ID without creating."""
    mock_client.maintenance_get = AsyncMock(return_value=[SAMPLE_MAINTENANCE])  # type: ignore[attr-defined]

    result = await create_maintenance(
        mock_client,  # type: ignore[arg-type]
        name="maint-2026-04-17-db",
        reason="Planned OS upgrade",
        duration_minutes=60,
        host="app-server-01",
    )
    data = json.loads(result)
    assert data["maintenance_id"] == "2001"
    assert data["status"] == "already_exists"
    mock_client.maintenance_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ extra

@pytest.mark.asyncio
async def test_create_maintenance_no_target_raises(mock_client: object) -> None:
    """Neither host nor host_group provided raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError):
        await create_maintenance(
            mock_client,  # type: ignore[arg-type]
            name="bad",
            reason="Test",
            duration_minutes=30,
        )


@pytest.mark.asyncio
async def test_create_maintenance_zero_duration_raises(mock_client: object) -> None:
    """duration_minutes=0 raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError):
        await create_maintenance(
            mock_client,  # type: ignore[arg-type]
            name="bad",
            reason="Test",
            duration_minutes=0,
            host="some-host",
        )
