"""Tests for tools/reports.py — TC-064 through TC-067."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import SAMPLE_HOST, SAMPLE_PROBLEM
from zabbix_mcp.tools.reports import get_availability_report
from zabbix_mcp.zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ TC-064

@pytest.mark.asyncio
async def test_get_availability_report_30_days(mock_client: object) -> None:
    """TC-064: 30-day report for 3 hosts returns uptime_percent for each."""
    hosts_data = [
        {**SAMPLE_HOST, "hostid": str(i), "name": f"app-0{i}", "host": f"app-0{i}"}
        for i in range(1, 4)
    ]

    def _host_get(**kwargs: object) -> list:
        name = kwargs.get("filter", {}).get("host")  # type: ignore[attr-defined]
        if name:
            return [h for h in hosts_data if h["host"] == name]
        return []

    mock_client.host_get = AsyncMock(side_effect=_host_get)  # type: ignore[attr-defined]
    mock_client.problem_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await get_availability_report(
        mock_client,  # type: ignore[arg-type]
        hosts=["app-01", "app-02", "app-03"],
        time_from="2026-03-01",
        time_to="2026-03-31",
    )
    data = json.loads(result)
    assert len(data) == 3
    for entry in data:
        assert "uptime_percent" in entry
        assert 0.0 <= entry["uptime_percent"] <= 100.0
        assert "downtime_seconds" in entry


# ------------------------------------------------------------------ TC-065

@pytest.mark.asyncio
async def test_get_availability_report_reversed_range_raises(mock_client: object) -> None:
    """TC-065: from > to raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="from"):
        await get_availability_report(
            mock_client,  # type: ignore[arg-type]
            hosts=["app-01"],
            time_from="2026-04-17",
            time_to="2026-04-01",
        )
    mock_client.problem_get.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-066

@pytest.mark.asyncio
async def test_get_availability_report_nonexistent_host_raises(mock_client: object) -> None:
    """TC-066: Non-existent host raises ZabbixNotFoundError."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    with pytest.raises(ZabbixNotFoundError, match="ghost-host"):
        await get_availability_report(
            mock_client,  # type: ignore[arg-type]
            hosts=["ghost-host"],
            time_from="2026-03-01",
            time_to="2026-03-31",
        )


# ------------------------------------------------------------------ TC-067

@pytest.mark.asyncio
async def test_get_availability_report_full_year(mock_client: object) -> None:
    """TC-067: Yearly report produces uptime_percent in [0, 100] range."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    # Simulate 1 problem (1 hour downtime in a year)
    downtime_problem = {
        **SAMPLE_PROBLEM,
        "clock": "1735689600",   # 2025-01-01T00:00:00Z
        "r_clock": "1735693200",  # +1 hour
    }
    mock_client.problem_get = AsyncMock(return_value=[downtime_problem])  # type: ignore[attr-defined]

    result = await get_availability_report(
        mock_client,  # type: ignore[arg-type]
        hosts=["app-01"],
        time_from="2025-01-01",
        time_to="2025-12-31",
    )
    data = json.loads(result)
    assert len(data) == 1
    assert 0.0 <= data[0]["uptime_percent"] <= 100.0
    assert data[0]["downtime_seconds"] > 0


# ------------------------------------------------------------------ extra

@pytest.mark.asyncio
async def test_get_availability_report_100_percent_no_problems(mock_client: object) -> None:
    """No problems in period results in 100% uptime."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.problem_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await get_availability_report(
        mock_client,  # type: ignore[arg-type]
        hosts=["app-01"],
        time_from="2026-03-01",
        time_to="2026-03-31",
    )
    data = json.loads(result)
    assert data[0]["uptime_percent"] == 100.0
    assert data[0]["downtime_seconds"] == 0
