"""Tests for tools/metrics.py — TC-038 through TC-045, TC-074–TC-077."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import SAMPLE_HOST, SAMPLE_ITEM
from zabbix_mcp.tools.metrics import export_metrics, get_metric_history, get_metric_value
from zabbix_mcp.zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ TC-038

@pytest.mark.asyncio
async def test_get_metric_value_by_host_name(mock_client: object) -> None:
    """TC-038: Correct key + host returns value, units, and last_updated."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]

    result = await get_metric_value(
        mock_client, item_key="system.cpu.util", host="web-server-01"  # type: ignore[arg-type]
    )
    data = json.loads(result)
    assert data["value"] == "23.5"
    assert data["units"] == "%"
    assert data["last_updated"] is not None


# ------------------------------------------------------------------ TC-039

@pytest.mark.asyncio
async def test_get_metric_value_by_host_id(mock_client: object) -> None:
    """TC-039: host_id parameter works as alternative to host name."""
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]

    result = await get_metric_value(
        mock_client, item_key="agent.ping", host_id="1001"  # type: ignore[arg-type]
    )
    data = json.loads(result)
    assert "value" in data


# ------------------------------------------------------------------ TC-040

@pytest.mark.asyncio
async def test_get_metric_value_nonexistent_key_raises(mock_client: object) -> None:
    """TC-040: Non-existent item_key raises ZabbixNotFoundError."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    with pytest.raises(ZabbixNotFoundError, match="non.existent.key"):
        await get_metric_value(
            mock_client, item_key="non.existent.key", host="web-server-01"  # type: ignore[arg-type]
        )


# ------------------------------------------------------------------ TC-041

@pytest.mark.asyncio
async def test_get_metric_value_no_data_returns_message(mock_client: object) -> None:
    """TC-041: Item with no history returns informative message, not error."""
    stale_item = {**SAMPLE_ITEM, "lastvalue": "", "lastclock": "0"}
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[stale_item])  # type: ignore[attr-defined]

    result = await get_metric_value(
        mock_client, item_key="custom.stale.counter", host="web-server-01"  # type: ignore[arg-type]
    )
    data = json.loads(result)
    assert "message" in data
    assert data["last_updated"] is None


# ------------------------------------------------------------------ TC-042

@pytest.mark.asyncio
async def test_get_metric_history_one_hour(mock_client: object) -> None:
    """TC-042: History request for 1 hour returns data points in range."""
    history_points = [
        {"itemid": "201", "clock": "1713350400", "value": "10.5", "ns": "0"},
        {"itemid": "201", "clock": "1713350460", "value": "12.3", "ns": "0"},
    ]
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]
    mock_client.history_get = AsyncMock(return_value=history_points)  # type: ignore[attr-defined]

    result = await get_metric_history(
        mock_client,  # type: ignore[arg-type]
        item_key="system.cpu.util",
        time_from="2026-04-17T10:00:00",
        time_to="2026-04-17T11:00:00",
        host="db-01",
    )
    data = json.loads(result)
    assert len(data) == 2
    assert "clock" in data[0]
    assert "value" in data[0]


# ------------------------------------------------------------------ TC-043

@pytest.mark.asyncio
async def test_get_metric_history_reversed_range_raises(mock_client: object) -> None:
    """TC-043: time_from > time_to raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="time_from"):
        await get_metric_history(
            mock_client,  # type: ignore[arg-type]
            item_key="system.cpu.util",
            time_from="2026-04-17T12:00:00",
            time_to="2026-04-17T10:00:00",
            host="db-01",
        )
    mock_client.history_get.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-044

@pytest.mark.asyncio
async def test_get_metric_history_one_second_range(mock_client: object) -> None:
    """TC-044: 1-second range returns 0 or 1 data points without error."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]
    mock_client.history_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await get_metric_history(
        mock_client,  # type: ignore[arg-type]
        item_key="system.cpu.util",
        time_from="2026-04-17T10:00:00",
        time_to="2026-04-17T10:00:01",
        host="db-01",
    )
    data = json.loads(result)
    assert isinstance(data, list)


# ------------------------------------------------------------------ TC-074

@pytest.mark.asyncio
async def test_export_metrics_json_format(mock_client: object) -> None:
    """TC-074: export_metrics with format=json returns valid JSON array."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]
    mock_client.history_get = AsyncMock(  # type: ignore[attr-defined]
        return_value=[{"itemid": "201", "clock": "1713350400", "value": "10.5", "ns": "0"}]
    )

    result = await export_metrics(
        mock_client,  # type: ignore[arg-type]
        hosts=["app-01"],
        items=["system.cpu.util"],
        time_from="2026-04-16T00:00:00",
        time_to="2026-04-17T00:00:00",
        format="json",
    )
    data = json.loads(result)
    assert isinstance(data, list)
    assert data[0]["host"] == "app-01"
    assert "clock" in data[0]
    assert "value" in data[0]


# ------------------------------------------------------------------ TC-075

@pytest.mark.asyncio
async def test_export_metrics_csv_format(mock_client: object) -> None:
    """TC-075: export_metrics with format=csv returns CSV with header row."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]
    mock_client.history_get = AsyncMock(  # type: ignore[attr-defined]
        return_value=[{"itemid": "201", "clock": "1713350400", "value": "10.5", "ns": "0"}]
    )

    result = await export_metrics(
        mock_client,  # type: ignore[arg-type]
        hosts=["app-01"],
        items=["system.cpu.util"],
        time_from="2026-04-16T00:00:00",
        time_to="2026-04-17T00:00:00",
        format="csv",
    )
    first_line = result.strip().split("\n")[0]
    assert "host" in first_line
    assert "item_key" in first_line
    assert "clock" in first_line
    assert "value" in first_line


# ------------------------------------------------------------------ TC-076

@pytest.mark.asyncio
async def test_export_metrics_invalid_format_raises(mock_client: object) -> None:
    """TC-076: format='xml' raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="xml"):
        await export_metrics(
            mock_client,  # type: ignore[arg-type]
            hosts=["app-01"],
            items=["system.cpu.util"],
            time_from="2026-04-16T00:00:00",
            time_to="2026-04-17T00:00:00",
            format="xml",
        )
    mock_client.history_get.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-077

@pytest.mark.asyncio
async def test_export_metrics_empty_period_returns_empty_array(mock_client: object) -> None:
    """TC-077: Period with no data returns empty array, not error."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]
    mock_client.history_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await export_metrics(
        mock_client,  # type: ignore[arg-type]
        hosts=["app-01"],
        items=["system.cpu.util"],
        time_from="2020-01-01T00:00:00",
        time_to="2020-01-02T00:00:00",
        format="json",
    )
    data = json.loads(result)
    assert data == []


# ------------------------------------------------------------------ extra

@pytest.mark.asyncio
async def test_get_metric_value_no_host_or_id_raises(mock_client: object) -> None:
    """Neither host nor host_id raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError):
        await get_metric_value(mock_client, item_key="system.cpu.util")  # type: ignore[arg-type]
