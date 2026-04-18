"""Tests for tools/hosts.py — TC-032 through TC-037, TC-046–TC-050, TC-071–TC-073."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import SAMPLE_HOST
from zabbix_mcp.tools.hosts import add_host, check_host_availability, search_hosts
from zabbix_mcp.zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ TC-032

@pytest.mark.asyncio
async def test_add_host_success_full_params(mock_client: object) -> None:
    """TC-032: Add new host with all params returns host_id."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.hostgroup_get = AsyncMock(return_value=[{"groupid": "10", "name": "Linux Servers"}])  # type: ignore[attr-defined]
    mock_client.template_get = AsyncMock(  # type: ignore[attr-defined]
        return_value=[{"templateid": "50001", "name": "Template OS Linux by Zabbix agent"}]
    )
    mock_client.host_create = AsyncMock(return_value="9001")  # type: ignore[attr-defined]

    result = await add_host(
        mock_client,  # type: ignore[arg-type]
        name="new-server-42",
        ip="192.168.1.42",
        host_groups=["Linux Servers"],
        templates=["Template OS Linux by Zabbix agent"],
    )
    data = json.loads(result)
    assert data["host_id"] == "9001"
    assert data["status"] == "created"


# ------------------------------------------------------------------ TC-033

@pytest.mark.asyncio
async def test_add_host_idempotent_returns_existing_id(mock_client: object) -> None:
    """TC-033: Existing host returns its ID without creating a duplicate."""
    mock_client.host_get = AsyncMock(return_value=[{**SAMPLE_HOST, "hostid": "1001"}])  # type: ignore[attr-defined]

    result = await add_host(
        mock_client,  # type: ignore[arg-type]
        name="existing-server-01",
        ip="10.0.0.1",
        host_groups=["Linux Servers"],
    )
    data = json.loads(result)
    assert data["host_id"] == "1001"
    assert data["status"] == "already_exists"
    mock_client.host_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-034

@pytest.mark.asyncio
async def test_add_host_missing_groups_raises(mock_client: object) -> None:
    """TC-034: Empty host_groups raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="host_groups"):
        await add_host(mock_client, name="x", ip="10.0.0.1", host_groups=[])  # type: ignore[arg-type]
    mock_client.host_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-035

@pytest.mark.asyncio
async def test_add_host_invalid_ip_raises(mock_client: object) -> None:
    """TC-035: Invalid IP address format raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="[Ii]nvalid"):
        await add_host(
            mock_client,  # type: ignore[arg-type]
            name="new-host",
            ip="999.999.999.999",
            host_groups=["Linux Servers"],
        )
    mock_client.host_create.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-036

@pytest.mark.asyncio
async def test_add_host_nonexistent_template_raises(mock_client: object) -> None:
    """TC-036: Non-existent template raises ZabbixNotFoundError."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.hostgroup_get = AsyncMock(return_value=[{"groupid": "10", "name": "Linux Servers"}])  # type: ignore[attr-defined]
    mock_client.template_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    with pytest.raises(ZabbixNotFoundError, match="Non-Existent Template"):
        await add_host(
            mock_client,  # type: ignore[arg-type]
            name="new-host",
            ip="10.0.0.1",
            host_groups=["Linux Servers"],
            templates=["Non-Existent Template"],
        )


# ------------------------------------------------------------------ TC-037

@pytest.mark.asyncio
async def test_add_host_single_char_name(mock_client: object) -> None:
    """TC-037: Single-character host name creates host if Zabbix accepts it."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.hostgroup_get = AsyncMock(return_value=[{"groupid": "10", "name": "Linux Servers"}])  # type: ignore[attr-defined]
    mock_client.template_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.host_create = AsyncMock(return_value="9999")  # type: ignore[attr-defined]

    result = await add_host(
        mock_client,  # type: ignore[arg-type]
        name="X",
        ip="10.0.0.1",
        host_groups=["Linux Servers"],
    )
    data = json.loads(result)
    assert data["status"] == "created"


# ------------------------------------------------------------------ TC-046

@pytest.mark.asyncio
async def test_search_hosts_by_name_substring(mock_client: object) -> None:
    """TC-046: name_substring='web' returns only web hosts."""
    web_hosts = [
        {**SAMPLE_HOST, "hostid": "1", "name": "web-server-01", "host": "web-server-01"},
        {**SAMPLE_HOST, "hostid": "2", "name": "web-server-02", "host": "web-server-02"},
    ]
    mock_client.host_get = AsyncMock(return_value=web_hosts)  # type: ignore[attr-defined]

    result = await search_hosts(mock_client, name_substring="web")  # type: ignore[arg-type]
    data = json.loads(result)
    assert len(data) == 2
    assert all("web" in h["name"] for h in data)


# ------------------------------------------------------------------ TC-047

@pytest.mark.asyncio
async def test_search_hosts_by_template(mock_client: object) -> None:
    """TC-047: template filter returns only hosts using that template."""
    mock_client.template_get = AsyncMock(  # type: ignore[attr-defined]
        return_value=[{"templateid": "50001", "name": "Template OS Linux"}]
    )
    linux_hosts = [{**SAMPLE_HOST, "hostid": str(i)} for i in range(2)]
    mock_client.host_get = AsyncMock(return_value=linux_hosts)  # type: ignore[attr-defined]

    result = await search_hosts(mock_client, template="Template OS Linux")  # type: ignore[arg-type]
    data = json.loads(result)
    assert len(data) == 2


# ------------------------------------------------------------------ TC-048

@pytest.mark.asyncio
async def test_search_hosts_by_tag(mock_client: object) -> None:
    """TC-048: tag filter passes tag dict to host_get."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST] * 3)  # type: ignore[attr-defined]

    result = await search_hosts(mock_client, tag="env:production")  # type: ignore[arg-type]
    data = json.loads(result)
    assert len(data) == 3
    kwargs = mock_client.host_get.call_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["tags"][0]["tag"] == "env"
    assert kwargs["tags"][0]["value"] == "production"


# ------------------------------------------------------------------ TC-049

@pytest.mark.asyncio
async def test_search_hosts_no_matches_returns_empty_list(mock_client: object) -> None:
    """TC-049: No matching hosts returns empty JSON array."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await search_hosts(mock_client, name_substring="zzz-no-match-zzz")  # type: ignore[arg-type]
    assert result == "[]"


# ------------------------------------------------------------------ TC-071

@pytest.mark.asyncio
async def test_check_host_availability_available(mock_client: object) -> None:
    """TC-071: Available host returns available=True."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]

    result = await check_host_availability(mock_client, host="monitored-host")  # type: ignore[arg-type]
    data = json.loads(result)
    assert data["available"] is True
    assert data["status"] == "Available"


# ------------------------------------------------------------------ TC-072

@pytest.mark.asyncio
async def test_check_host_availability_unavailable(mock_client: object) -> None:
    """TC-072: Unavailable host returns available=False."""
    unavail_host = {
        **SAMPLE_HOST,
        "available": "2",
        "error": "Cannot connect to agent",
        "interfaces": [
            {
                "ip": "10.0.0.1", "port": "10050", "type": "1",
                "main": "1", "available": "2", "error": "Cannot connect",
            }
        ],
    }
    mock_client.host_get = AsyncMock(return_value=[unavail_host])  # type: ignore[attr-defined]

    result = await check_host_availability(mock_client, host="unreachable-host")  # type: ignore[arg-type]
    data = json.loads(result)
    assert data["available"] is False
    assert data["status"] == "Unavailable"


# ------------------------------------------------------------------ TC-073

@pytest.mark.asyncio
async def test_check_host_availability_not_found_raises(mock_client: object) -> None:
    """TC-073: Non-existent host raises ZabbixNotFoundError."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    with pytest.raises(ZabbixNotFoundError, match="no-such-host"):
        await check_host_availability(mock_client, host="no-such-host")  # type: ignore[arg-type]
