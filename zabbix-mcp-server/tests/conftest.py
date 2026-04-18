"""Shared pytest fixtures for Zabbix MCP Server tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from zabbix_mcp.config import Settings


# ------------------------------------------------------------------ settings

@pytest.fixture
def zabbix_url() -> str:
    return "https://zabbix.test"


@pytest.fixture
def settings(zabbix_url: str) -> Settings:
    """A minimal Settings instance for unit tests."""
    return Settings(
        url=zabbix_url,  # type: ignore[arg-type]
        api_token="test_token_abc123",
        timeout_seconds=10,
        page_limit=100,
    )


# ------------------------------------------------------------------ mock client

@pytest.fixture
def mock_client() -> MagicMock:
    """Mock ZabbixClient with all methods as AsyncMock."""
    client = MagicMock()
    client.problem_get = AsyncMock(return_value=[])
    client.event_acknowledge = AsyncMock(return_value={"eventids": ["1"]})
    client.host_get = AsyncMock(return_value=[])
    client.host_create = AsyncMock(return_value="9001")
    client.host_update = AsyncMock(return_value=None)
    client.hostgroup_get = AsyncMock(return_value=[])
    client.template_get = AsyncMock(return_value=[])
    client.item_get = AsyncMock(return_value=[])
    client.history_get = AsyncMock(return_value=[])
    client.trigger_get = AsyncMock(return_value=[])
    client.trigger_create = AsyncMock(return_value="5001")
    client.maintenance_get = AsyncMock(return_value=[])
    client.maintenance_create = AsyncMock(return_value="2001")
    client.usermacro_get = AsyncMock(return_value=[])
    client.usermacro_update = AsyncMock(return_value=None)
    client.usermacro_create = AsyncMock(return_value=None)
    client.api_version = AsyncMock(return_value="7.0.0")
    return client


# ------------------------------------------------------------------ sample data

SAMPLE_PROBLEM: dict[str, Any] = {
    "eventid": "555",
    "objectid": "101",
    "name": "High CPU utilization",
    "severity": "4",
    "clock": "1713350400",
    "r_clock": "0",
    "acknowledged": "0",
    "hosts": [{"hostid": "1001", "name": "db-01", "host": "db-01"}],
}

SAMPLE_HOST: dict[str, Any] = {
    "hostid": "1001",
    "host": "web-server-01",
    "name": "web-server-01",
    "status": "0",
    "available": "1",
    "error": "",
    "interfaces": [
        {
            "ip": "10.0.0.1",
            "port": "10050",
            "type": "1",
            "main": "1",
            "available": "1",
            "error": "",
        }
    ],
    "groups": [{"groupid": "10", "name": "Linux Servers"}],
    "parentTemplates": [],
    "tags": [],
}

SAMPLE_ITEM: dict[str, Any] = {
    "itemid": "201",
    "name": "CPU utilization",
    "key_": "system.cpu.util",
    "lastvalue": "23.5",
    "lastclock": "1713350400",
    "units": "%",
    "value_type": "0",
    "description": "CPU utilization percentage",
    "hosts": [{"hostid": "1001", "name": "web-server-01"}],
}

SAMPLE_TRIGGER: dict[str, Any] = {
    "triggerid": "301",
    "description": "High CPU",
    "expression": "last(/web-server-01/system.cpu.util)>90",
    "status": "0",
    "priority": "3",
    "lastchange": "1713350000",
    "state": "0",
}

SAMPLE_MAINTENANCE: dict[str, Any] = {
    "maintenanceid": "2001",
    "name": "maint-2026-04-17-db",
    "active_since": "1713350400",
    "active_till": "1713354000",
}

SAMPLE_GROUP: dict[str, Any] = {"groupid": "10", "name": "Linux Servers"}
SAMPLE_TEMPLATE: dict[str, Any] = {
    "templateid": "50001",
    "name": "Template OS Linux by Zabbix agent",
}
