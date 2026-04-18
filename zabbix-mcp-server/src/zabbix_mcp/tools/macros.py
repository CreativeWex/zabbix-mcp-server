"""Tool: bulk_update_macro — update a macro across many hosts at once."""

from __future__ import annotations

import json
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixValidationError

_BATCH_SIZE = 50  # hosts processed per usermacro API call


async def _find_hosts(
    client: ZabbixClient,
    name_pattern: str | None,
    tag: str | None,
) -> list[dict[str, Any]]:
    """Return hosts matching *name_pattern* and/or *tag*."""
    kwargs: dict[str, Any] = {}
    if name_pattern:
        search_name = name_pattern.replace("*", "").replace("%", "")
        kwargs["search"] = {"name": search_name}
        kwargs["searchWildcardsEnabled"] = True
    if tag:
        parts = tag.split(":", 1)
        tag_filter: dict[str, Any] = {"tag": parts[0]}
        if len(parts) > 1:
            tag_filter["value"] = parts[1]
            tag_filter["operator"] = 1
        kwargs["tags"] = [tag_filter]
    return await client.host_get(**kwargs)


async def _update_macro_on_hosts(
    client: ZabbixClient,
    host_ids: list[str],
    macro: str,
    value: str,
) -> int:
    """Update *macro* to *value* on each of *host_ids*; returns update count."""
    updated = 0
    for i in range(0, len(host_ids), _BATCH_SIZE):
        batch = host_ids[i : i + _BATCH_SIZE]
        existing_macros = await client.usermacro_get(hostids=batch)

        to_update: list[dict[str, Any]] = []
        to_create: list[dict[str, Any]] = []

        existing_by_host: dict[str, dict[str, Any]] = {}
        for m in existing_macros:
            if m.get("macro", "").upper() == macro.upper():
                existing_by_host[str(m["hostid"])] = m

        for hid in batch:
            if hid in existing_by_host:
                to_update.append(
                    {
                        "hostmacroid": existing_by_host[hid]["hostmacroid"],
                        "value": value,
                    }
                )
            else:
                to_create.append(
                    {"hostid": hid, "macro": macro, "value": value}
                )

        if to_update:
            await client.usermacro_update(to_update)
            updated += len(to_update)
        if to_create:
            await client.usermacro_create(to_create)
            updated += len(to_create)

    return updated


async def bulk_update_macro(
    client: ZabbixClient,
    macro: str,
    value: str,
    name_pattern: str | None = None,
    tag: str | None = None,
) -> str:
    """Update a named macro value across all matching hosts.

    At least one of *name_pattern* or *tag* must be supplied to scope
    the update. The macro is created on hosts where it does not yet exist.

    Args:
        client: Authenticated ZabbixClient instance.
        macro: Zabbix macro name including braces, e.g. ``{$LOG_LEVEL}``.
        value: New macro value to set.
        name_pattern: Host name pattern (wildcards ``*`` supported).
        tag: Tag filter in ``"key:value"`` or ``"key"`` format.

    Returns:
        JSON summary with number of updated hosts.

    Raises:
        ZabbixValidationError: If neither name_pattern nor tag is provided.
    """
    if not name_pattern and not tag:
        raise ZabbixValidationError(
            "Provide at least one of 'name_pattern' or 'tag' to scope the update."
        )
    if not macro or not macro.strip():
        raise ZabbixValidationError("macro name must not be empty.")

    hosts = await _find_hosts(client, name_pattern, tag)
    if not hosts:
        pattern_desc = name_pattern or tag or ""
        return json.dumps(
            {
                "updated_count": 0,
                "message": f"No hosts matched pattern '{pattern_desc}'.",
            },
            indent=2,
        )

    host_ids = [str(h["hostid"]) for h in hosts]
    updated = await _update_macro_on_hosts(client, host_ids, macro, value)

    return json.dumps(
        {
            "updated_count": updated,
            "total_matched_hosts": len(hosts),
            "macro": macro,
            "new_value": value,
        },
        indent=2,
    )
