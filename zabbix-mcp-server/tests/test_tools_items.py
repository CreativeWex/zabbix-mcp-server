"""Tests for tools/items.py — TC-068 through TC-070."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import SAMPLE_ITEM
from zabbix_mcp.tools.items import search_items
from zabbix_mcp.zabbix.errors import ZabbixValidationError


# ------------------------------------------------------------------ TC-068

@pytest.mark.asyncio
async def test_search_items_by_name_substring(mock_client: object) -> None:
    """TC-068: name_substring='CPU' returns items with 'CPU' in name."""
    cpu_items = [
        {**SAMPLE_ITEM, "itemid": "1", "name": "CPU utilization"},
        {**SAMPLE_ITEM, "itemid": "2", "name": "CPU load"},
    ]
    mock_client.item_get = AsyncMock(return_value=cpu_items)  # type: ignore[attr-defined]

    result = await search_items(mock_client, name_substring="CPU")  # type: ignore[arg-type]
    data = json.loads(result)

    assert len(data) == 2
    assert all("CPU" in item["name"] for item in data)
    assert "item_id" in data[0]
    assert "key_" in data[0]
    assert "host" in data[0]


# ------------------------------------------------------------------ TC-069

@pytest.mark.asyncio
async def test_search_items_by_key_substring(mock_client: object) -> None:
    """TC-069: key_substring='system.cpu' returns items with matching key."""
    cpu_items = [
        {**SAMPLE_ITEM, "itemid": "1", "key_": "system.cpu.util"},
        {**SAMPLE_ITEM, "itemid": "2", "key_": "system.cpu.load"},
    ]
    mock_client.item_get = AsyncMock(return_value=cpu_items)  # type: ignore[attr-defined]

    result = await search_items(mock_client, key_substring="system.cpu")  # type: ignore[arg-type]
    data = json.loads(result)

    assert len(data) == 2
    call_kwargs = mock_client.item_get.call_args.kwargs  # type: ignore[attr-defined]
    assert "key_" in call_kwargs["search"]


# ------------------------------------------------------------------ TC-070

@pytest.mark.asyncio
async def test_search_items_no_params_raises(mock_client: object) -> None:
    """TC-070: No search parameter raises ZabbixValidationError."""
    with pytest.raises(ZabbixValidationError, match="[Aa]t least one"):
        await search_items(mock_client)  # type: ignore[arg-type]
    mock_client.item_get.assert_not_called()  # type: ignore[attr-defined]


# ------------------------------------------------------------------ extra

@pytest.mark.asyncio
async def test_search_items_no_results_returns_empty_list(mock_client: object) -> None:
    """No matching items returns empty JSON array."""
    mock_client.item_get = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    result = await search_items(mock_client, name_substring="zzz-no-match")  # type: ignore[arg-type]
    assert result == "[]"


@pytest.mark.asyncio
async def test_search_items_by_description(mock_client: object) -> None:
    """description parameter is included in the search dict."""
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]

    result = await search_items(mock_client, description="utilization")  # type: ignore[arg-type]
    data = json.loads(result)
    assert len(data) == 1
    call_kwargs = mock_client.item_get.call_args.kwargs  # type: ignore[attr-defined]
    assert "description" in call_kwargs["search"]


@pytest.mark.asyncio
async def test_search_items_with_host_id_filter(mock_client: object) -> None:
    """host_id parameter is forwarded to item_get."""
    mock_client.item_get = AsyncMock(return_value=[SAMPLE_ITEM])  # type: ignore[attr-defined]

    await search_items(mock_client, name_substring="CPU", host_id="1001")  # type: ignore[arg-type]
    call_kwargs = mock_client.item_get.call_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["hostids"] == ["1001"]
