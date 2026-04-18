"""Tools: add_host, search_hosts, check_host_availability."""

from __future__ import annotations

import ipaddress
import json
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ helpers

def _validate_ip(ip: str) -> None:
    """Raise ZabbixValidationError if *ip* is not a valid IPv4/IPv6 address."""
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise ZabbixValidationError(
            f"Invalid IP address format: '{ip}'. "
            "Provide a valid IPv4 or IPv6 address."
        ) from None


async def _resolve_group_ids(
    client: ZabbixClient, group_names: list[str]
) -> list[str]:
    """Resolve a list of group names to group IDs."""
    ids: list[str] = []
    for name in group_names:
        groups = await client.hostgroup_get(filter={"name": name})
        if not groups:
            raise ZabbixNotFoundError(f"Host group '{name}' not found.")
        ids.append(str(groups[0]["groupid"]))
    return ids


async def _resolve_template_ids(
    client: ZabbixClient, template_names: list[str]
) -> list[str]:
    """Resolve template names to template IDs."""
    ids: list[str] = []
    for name in template_names:
        templates = await client.template_get(filter={"name": name})
        if not templates:
            raise ZabbixNotFoundError(f"Template '{name}' not found.")
        ids.append(str(templates[0]["templateid"]))
    return ids


def _availability_status(available: str | int) -> str:
    mapping = {"0": "Unknown", "1": "Available", "2": "Unavailable"}
    return mapping.get(str(available), "Unknown")


def _format_host(host: dict[str, Any]) -> dict[str, Any]:
    interfaces = host.get("interfaces", [])
    main_iface = next((i for i in interfaces if str(i.get("main")) == "1"), {})
    groups = [g["name"] for g in host.get("groups", [])]
    available = host.get("available", "0")
    return {
        "host_id": host.get("hostid", ""),
        "name": host.get("name", host.get("host", "")),
        "technical_name": host.get("host", ""),
        "status": "Monitored" if str(host.get("status")) == "0" else "Not monitored",
        "availability": _availability_status(available),
        "ip": main_iface.get("ip", ""),
        "groups": groups,
    }


# ------------------------------------------------------------------ tools

async def add_host(
    client: ZabbixClient,
    name: str,
    ip: str,
    host_groups: list[str],
    templates: list[str] | None = None,
    dns: str = "",
    port: str = "10050",
) -> str:
    """Add a Zabbix host with agent interface, groups, and templates (idempotent).

    If a host with *name* already exists, its existing ID is returned
    without creating a duplicate.

    Args:
        client: Authenticated ZabbixClient instance.
        name: Unique host name (technical name in Zabbix).
        ip: IPv4 or IPv6 address of the agent interface.
        host_groups: List of host group names (at least one required).
        templates: Optional list of template names to link.
        dns: Optional DNS name (leave blank to use IP).
        port: Zabbix agent port (default ``"10050"``).

    Returns:
        JSON with host_id and status (created / already_exists).

    Raises:
        ZabbixValidationError: If host_groups is empty or IP is invalid.
        ZabbixNotFoundError: If a specified group or template does not exist.
    """
    if not host_groups:
        raise ZabbixValidationError("host_groups is required and must not be empty.")
    _validate_ip(ip)

    existing = await client.host_get(filter={"host": name})
    if existing:
        return json.dumps(
            {"host_id": str(existing[0]["hostid"]), "status": "already_exists"},
            indent=2,
        )

    group_ids = await _resolve_group_ids(client, host_groups)
    template_ids = await _resolve_template_ids(client, templates or [])

    payload: dict[str, Any] = {
        "host": name,
        "name": name,
        "interfaces": [
            {
                "type": 1, "main": 1, "useip": 1 if not dns else 0,
                "ip": ip, "dns": dns, "port": port,
            }
        ],
        "groups": [{"groupid": gid} for gid in group_ids],
    }
    if template_ids:
        payload["templates"] = [{"templateid": tid} for tid in template_ids]

    host_id = await client.host_create(payload)
    return json.dumps({"host_id": host_id, "status": "created"}, indent=2)


async def search_hosts(
    client: ZabbixClient,
    name_substring: str | None = None,
    host_group: str | None = None,
    template: str | None = None,
    tag: str | None = None,
) -> str:
    """Search Zabbix hosts by name, group, template, or tag.

    Args:
        client: Authenticated ZabbixClient instance.
        name_substring: Substring to match against the host visible name.
        host_group: Filter to hosts belonging to this group name.
        template: Filter to hosts linked to this template name.
        tag: Filter by tag in ``"key:value"`` or ``"key"`` format.

    Returns:
        JSON list of matching host objects, or a message if none found.
    """
    kwargs: dict[str, Any] = {}

    if name_substring:
        kwargs["search"] = {"name": name_substring}
        kwargs["searchWildcardsEnabled"] = True

    if host_group:
        groups = await client.hostgroup_get(filter={"name": host_group})
        if groups:
            kwargs["groupids"] = [str(g["groupid"]) for g in groups]

    if template:
        templates = await client.template_get(filter={"name": template})
        if templates:
            kwargs["templateids"] = [str(t["templateid"]) for t in templates]

    if tag:
        parts = tag.split(":", 1)
        tag_filter: dict[str, Any] = {"tag": parts[0]}
        if len(parts) > 1:
            tag_filter["value"] = parts[1]
            tag_filter["operator"] = 1  # CONTAINS
        kwargs["tags"] = [tag_filter]

    hosts = await client.host_get(**kwargs)
    if not hosts:
        return "[]"
    return json.dumps([_format_host(h) for h in hosts], indent=2)


async def check_host_availability(
    client: ZabbixClient,
    host: str,
) -> str:
    """Check whether the Zabbix agent on *host* is reachable.

    Args:
        client: Authenticated ZabbixClient instance.
        host: Host name or technical name.

    Returns:
        JSON with available (bool), status string, and last check info.

    Raises:
        ZabbixNotFoundError: If the host is not found in Zabbix.
    """
    hosts = await client.host_get(filter={"host": host})
    if not hosts:
        hosts = await client.host_get(search={"name": host})
    if not hosts:
        raise ZabbixNotFoundError(f"Host '{host}' not found.")

    h = hosts[0]
    interfaces = h.get("interfaces", [])
    main_iface = next((i for i in interfaces if str(i.get("main")) == "1"), {})

    iface_available = main_iface.get("available", h.get("available", "0"))
    iface_error = main_iface.get("error", h.get("error", ""))
    status_str = _availability_status(iface_available)
    is_available = str(iface_available) == "1"

    result: dict[str, Any] = {
        "host": h.get("name", host),
        "available": is_available,
        "status": status_str,
        "ip": main_iface.get("ip", ""),
    }
    if iface_error:
        result["last_error"] = iface_error
    return json.dumps(result, indent=2)
