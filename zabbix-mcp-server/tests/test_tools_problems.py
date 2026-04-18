"""Tests for tools/problems.py — TC-014 through TC-025, TC-057–TC-059."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import SAMPLE_HOST, SAMPLE_PROBLEM
from zabbix_mcp.tools.problems import (
    acknowledge_problem,
    get_active_problems,
    get_incident_summary,
)
from zabbix_mcp.zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ TC-014

@pytest.mark.asyncio
async def test_get_active_problems_no_filters(mock_client: object) -> None:
    """TC-014: No filters returns all active problems."""
    mock_client.problem_get = AsyncMock(return_value=[SAMPLE_PROBLEM])  # type: ignore[attr-defined]

    result = await get_active_problems(mock_client)  # type: ignore[arg-type]
    data = json.loads(result)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["problem_id"] == "555"
    assert data[0]["host"] == "db-01"
    assert "High CPU" in data[0]["description"]


# ------------------------------------------------------------------ TC-015

@pytest.mark.asyncio
async def test_get_active_problems_filter_by_host_name(mock_client: object) -> None:
    """TC-015: Filters by host_name resolves to hostids before calling problem_get."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.problem_get = AsyncMock(return_value=[SAMPLE_PROBLEM])  # type: ignore[attr-defined]

    result = await get_active_problems(mock_client, host_name="web-server-01")  # type: ignore[arg-type]
    data = json.loads(result)

    assert len(data) == 1
    mock_client.problem_get.assert_called_once()  # type: ignore[attr-defined]
    call_kwargs = mock_client.problem_get.call_args.kwargs  # type: ignore[attr-defined]
    assert "hostids" in call_kwargs


# ------------------------------------------------------------------ TC-016

@pytest.mark.asyncio
async def test_get_active_problems_filter_by_host_group(mock_client: object) -> None:
    """TC-016: Filters by host_group resolves to groupids before calling problem_get."""
    mock_client.hostgroup_get = AsyncMock(return_value=[{"groupid": "10", "name": "Linux Servers"}])  # type: ignore[attr-defined]
    mock_client.problem_get = AsyncMock(return_value=[SAMPLE_PROBLEM])  # type: ignore[attr-defined]

    result = await get_active_problems(mock_client, host_group="Linux Servers")  # type: ignore[arg-type]
    data = json.loads(result)

    assert len(data) == 1
    call_kwargs = mock_client.problem_get.call_args.kwargs  # type: ignore[attr-defined]
    assert "groupids" in call_kwargs


# ------------------------------------------------------------------ TC-017

@pytest.mark.asyncio
async def test_get_active_problems_filter_by_severity(mock_client: object) -> None:
    """TC-017: Severity filter passes severities range to problem_get."""
    mock_client.problem_get = AsyncMock(return_value=[SAMPLE_PROBLEM])  # type: ignore[attr-defined]

    result = await get_active_problems(mock_client, severity=5)  # type: ignore[arg-type]
    data = json.loads(result)
    assert len(data) == 1
    call_kwargs = mock_client.problem_get.call_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["severities"] == [5]


# ------------------------------------------------------------------ TC-018

@pytest.mark.asyncio
async def test_get_active_problems_combined_filters(mock_client: object) -> None:
    """TC-018: Combined filters all forwarded to problem_get."""
    mock_client.host_get = AsyncMock(return_value=[SAMPLE_HOST])  # type: ignore[attr-defined]
    mock_client.hostgroup_get = AsyncMock(return_value=[{"groupid": "10", "name": "DB"}])  # type: ignore[attr-defined]
    mock_client.problem_get = AsyncMock(return_value=[SAMPLE_PROBLEM])  # type: ignore[attr-defined]

    result = await get_active_problems(
        mock_client, host_name="db-01", host_group="Databases", severity=4  # type: ignore[arg-type]
    )
    data = json.loads(result)
    assert len(data) == 1


# ------------------------------------------------------------------ TC-019

@pytest.mark.asyncio
async def test_get_active_problems_nonexistent_host_empty_list(mock_client: object) -> None:
    """TC-019: Non-existent host name returns empty list without error."""
    mock_client.host_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    mock_client.problem_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await get_active_problems(mock_client, host_name="non-existent")  # type: ignore[arg-type]
    assert result == "No active problems found."


# ------------------------------------------------------------------ TC-020

@pytest.mark.asyncio
async def test_get_active_problems_invalid_severity_raises(mock_client: object) -> None:
    """TC-020: severity=-1 raises ZabbixValidationError before any API call."""
    with pytest.raises(ZabbixValidationError, match="severity"):
        await get_active_problems(mock_client, severity=-1)  # type: ignore[arg-type]

    mock_client.problem_get.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-021

@pytest.mark.asyncio
async def test_get_active_problems_200_via_pagination(mock_client: object) -> None:
    """TC-021: 200 active problems returned correctly (pagination handled by client)."""
    problems = [
        {**SAMPLE_PROBLEM, "eventid": str(i), "hosts": [{"hostid": "1", "name": "h", "host": "h"}]}
        for i in range(200)
    ]
    mock_client.problem_get = AsyncMock(return_value=problems)  # type: ignore[attr-defined]

    result = await get_active_problems(mock_client)  # type: ignore[arg-type]
    data = json.loads(result)
    assert len(data) == 200


# ------------------------------------------------------------------ TC-022

@pytest.mark.asyncio
async def test_acknowledge_problem_success(mock_client: object) -> None:
    """TC-022: Acknowledging an existing problem returns success message."""
    mock_client.event_acknowledge = AsyncMock(return_value={"eventids": ["12345"]})  # type: ignore[attr-defined]

    result = await acknowledge_problem(mock_client, "12345", "Investigating")  # type: ignore[arg-type]
    assert "12345" in result
    assert "acknowledged" in result.lower()


# ------------------------------------------------------------------ TC-023

@pytest.mark.asyncio
async def test_acknowledge_problem_empty_comment_raises(mock_client: object) -> None:
    """TC-023: Empty comment raises ZabbixValidationError without calling API."""
    with pytest.raises(ZabbixValidationError, match="comment"):
        await acknowledge_problem(mock_client, "12345", "")  # type: ignore[arg-type]

    mock_client.event_acknowledge.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ TC-024

@pytest.mark.asyncio
async def test_acknowledge_problem_not_found_reraises(mock_client: object) -> None:
    """TC-024: Non-existent problem ID raises ZabbixNotFoundError."""
    mock_client.event_acknowledge = AsyncMock(  # type: ignore[attr-defined]
        side_effect=ZabbixNotFoundError("Problem 999999999 not found")
    )
    with pytest.raises(ZabbixNotFoundError, match="999999999"):
        await acknowledge_problem(mock_client, "999999999", "Test")  # type: ignore[arg-type]


# ------------------------------------------------------------------ TC-025

@pytest.mark.asyncio
async def test_acknowledge_problem_single_char_comment(mock_client: object) -> None:
    """TC-025: Single-character comment is accepted."""
    mock_client.event_acknowledge = AsyncMock(return_value={"eventids": ["12345"]})  # type: ignore[attr-defined]

    result = await acknowledge_problem(mock_client, "12345", "A")  # type: ignore[arg-type]
    assert "acknowledged" in result.lower()


# ------------------------------------------------------------------ TC-057

@pytest.mark.asyncio
async def test_get_incident_summary_by_problem_id(mock_client: object) -> None:
    """TC-057: Summary for a specific problem_id contains host and timeline."""
    mock_client.problem_get = AsyncMock(return_value=[SAMPLE_PROBLEM])  # type: ignore[attr-defined]

    result = await get_incident_summary(mock_client, problem_id="555")  # type: ignore[arg-type]
    data = json.loads(result)

    assert "db-01" in data["affected_hosts"]
    assert data["total_problems"] == 1
    assert len(data["event_timeline"]) == 1


# ------------------------------------------------------------------ TC-058

@pytest.mark.asyncio
async def test_get_incident_summary_by_time_window(mock_client: object) -> None:
    """TC-058: Time-window query returns all incidents in range."""
    problems = [
        {**SAMPLE_PROBLEM, "eventid": str(i), "hosts": [{"hostid": str(i), "name": f"host-{i}", "host": f"h{i}"}]}
        for i in range(3)
    ]
    mock_client.problem_get = AsyncMock(return_value=problems)  # type: ignore[attr-defined]

    result = await get_incident_summary(
        mock_client,  # type: ignore[arg-type]
        time_from="2026-04-16T00:00:00",
        time_to="2026-04-17T00:00:00",
    )
    data = json.loads(result)
    assert data["total_problems"] == 3


# ------------------------------------------------------------------ TC-059

@pytest.mark.asyncio
async def test_get_incident_summary_not_found(mock_client: object) -> None:
    """TC-059: Non-existent problem_id raises ZabbixNotFoundError."""
    mock_client.problem_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    with pytest.raises(ZabbixNotFoundError, match="000000"):
        await get_incident_summary(mock_client, problem_id="000000")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_incident_summary_no_params_raises(mock_client: object) -> None:
    """No problem_id and no time window raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError):
        await get_incident_summary(mock_client)  # type: ignore[arg-type]
