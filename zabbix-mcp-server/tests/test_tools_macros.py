"""Tests for tools/macros.py — TC-060 through TC-063."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, call

import pytest

from tests.conftest import SAMPLE_HOST
from zabbix_mcp.tools.macros import bulk_update_macro
from zabbix_mcp.zabbix.errors import ZabbixValidationError


# ------------------------------------------------------------------ TC-060

@pytest.mark.asyncio
async def test_bulk_update_macro_by_name_pattern(mock_client: object) -> None:
    """TC-060: Update macro on 3 hosts matched by name pattern."""
    app_hosts = [
        {**SAMPLE_HOST, "hostid": str(i), "name": f"app-server-0{i}"}
        for i in range(1, 4)
    ]
    mock_client.host_get = AsyncMock(return_value=app_hosts)  # type: ignore[attr-defined]
    existing_macros = [
        {"hostmacroid": f"m{i}", "hostid": str(i), "macro": "{$LOG_LEVEL}", "value": "INFO"}
        for i in range(1, 4)
    ]
    mock_client.usermacro_get = AsyncMock(return_value=existing_macros)  # type: ignore[attr-defined]
    mock_client.usermacro_update = AsyncMock(return_value=None)  # type: ignore[attr-defined]

    result = await bulk_update_macro(
        mock_client,  # type: ignore[arg-type]
        macro="{$LOG_LEVEL}",
        value="DEBUG",
        name_pattern="app-server-*",
    )
    data = json.loads(result)
    assert data["updated_count"] == 3
    assert data["macro"] == "{$LOG_LEVEL}"
    assert data["new_value"] == "DEBUG"


# ------------------------------------------------------------------ TC-061

@pytest.mark.asyncio
async def test_bulk_update_macro_by_tag(mock_client: object) -> None:
    """TC-061: Tag filter limits update to 2 hosts."""
    staging_hosts = [
        {**SAMPLE_HOST, "hostid": str(i)} for i in range(1, 3)
    ]
    mock_client.host_get = AsyncMock(return_value=staging_hosts)  # type: ignore[attr-defined]
    mock_client.usermacro_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.usermacro_create = AsyncMock(return_value=None)  # type: ignore[attr-defined]

    result = await bulk_update_macro(
        mock_client,  # type: ignore[arg-type]
        macro="{$TIMEOUT}",
        value="30",
        tag="env:staging",
    )
    data = json.loads(result)
    assert data["updated_count"] == 2
    assert data["total_matched_hosts"] == 2

    kwargs = mock_client.host_get.call_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["tags"][0]["tag"] == "env"
    assert kwargs["tags"][0]["value"] == "staging"


# ------------------------------------------------------------------ TC-062

@pytest.mark.asyncio
async def test_bulk_update_macro_no_match_returns_message(mock_client: object) -> None:
    """TC-062: Pattern with no matching hosts returns informational message."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await bulk_update_macro(
        mock_client,  # type: ignore[arg-type]
        macro="{$TEST}",
        value="X",
        name_pattern="zzz-no-match-*",
    )
    data = json.loads(result)
    assert data["updated_count"] == 0
    assert "zzz-no-match-*" in data["message"]
    mock_client.usermacro_update.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-063

@pytest.mark.asyncio
async def test_bulk_update_macro_500_hosts_uses_batches(mock_client: object) -> None:
    """TC-063: 500 hosts are processed in batches; all updated."""
    bulk_hosts = [
        {**SAMPLE_HOST, "hostid": str(i), "name": f"bulk-host-{i}"}
        for i in range(500)
    ]
    mock_client.host_get = AsyncMock(return_value=bulk_hosts)  # type: ignore[attr-defined]
    mock_client.usermacro_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.usermacro_create = AsyncMock(return_value=None)  # type: ignore[attr-defined]

    result = await bulk_update_macro(
        mock_client,  # type: ignore[arg-type]
        macro="{$PARAM}",
        value="new_value",
        name_pattern="bulk-host-*",
    )
    data = json.loads(result)
    assert data["updated_count"] == 500
    # usermacro_get should be called in batches (500 / 50 = 10 batches)
    assert mock_client.usermacro_get.call_count == 10  # type: ignore[attr-defined]


# ------------------------------------------------------------------ extra

@pytest.mark.asyncio
async def test_bulk_update_macro_no_scope_raises(mock_client: object) -> None:
    """Neither name_pattern nor tag provided raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError):
        await bulk_update_macro(mock_client, macro="{$X}", value="v")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bulk_update_macro_empty_macro_raises(mock_client: object) -> None:
    """Empty macro name raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError):
        await bulk_update_macro(mock_client, macro="", value="v", name_pattern="h*")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bulk_update_macro_creates_when_not_exists(mock_client: object) -> None:
    """Macro is created on hosts where it does not yet exist."""
    host = {**SAMPLE_HOST, "hostid": "42"}
    mock_client.host_get = AsyncMock(return_value=[host])  # type: ignore[attr-defined]
    mock_client.usermacro_get = AsyncMock(return_value=[])  # no existing macros
    mock_client.usermacro_create = AsyncMock(return_value=None)  # type: ignore[attr-defined]

    result = await bulk_update_macro(
        mock_client,  # type: ignore[arg-type]
        macro="{$NEW_MACRO}",
        value="hello",
        name_pattern="some-host",
    )
    data = json.loads(result)
    assert data["updated_count"] == 1
    mock_client.usermacro_create.assert_called_once()  # type: ignore[attr-defined]
