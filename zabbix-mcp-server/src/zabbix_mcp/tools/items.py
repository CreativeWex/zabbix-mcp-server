"""Tool: search_items — search Zabbix items by name, key, or description."""

from __future__ import annotations

import json
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixValidationError


def _format_item(item: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Zabbix item to the MCP response format."""
    hosts = item.get("hosts", [])
    host_name = hosts[0].get("name", "") if hosts else ""
    return {
        "item_id": item.get("itemid", ""),
        "name": item.get("name", ""),
        "key_": item.get("key_", ""),
        "host": host_name,
        "units": item.get("units", ""),
        "description": item.get("description", ""),
        "last_value": item.get("lastvalue", ""),
    }


async def search_items(
    client: ZabbixClient,
    name_substring: str | None = None,
    key_substring: str | None = None,
    description: str | None = None,
    host_id: str | None = None,
) -> str:
    """Search Zabbix items (metrics) by name, key substring, or description.

    At least one of *name_substring*, *key_substring*, or *description*
    must be provided.

    Args:
        client: Authenticated ZabbixClient instance.
        name_substring: Substring to match in the item display name.
        key_substring: Substring to match in the item key.
        description: Substring to match in the item description.
        host_id: Optional host ID to limit the search scope.

    Returns:
        JSON list of matching item objects with host info.

    Raises:
        ZabbixValidationError: If no search parameter is provided.
    """
    if not any([name_substring, key_substring, description]):
        raise ZabbixValidationError(
            "At least one search parameter is required: "
            "name_substring, key_substring, or description."
        )

    search: dict[str, str] = {}
    if name_substring:
        search["name"] = name_substring
    if key_substring:
        search["key_"] = key_substring
    if description:
        search["description"] = description

    kwargs: dict[str, Any] = {
        "search": search,
        "searchWildcardsEnabled": True,
    }
    if host_id:
        kwargs["hostids"] = [host_id]

    items = await client.item_get(**kwargs)
    if not items:
        return "[]"
    return json.dumps([_format_item(i) for i in items], indent=2)
