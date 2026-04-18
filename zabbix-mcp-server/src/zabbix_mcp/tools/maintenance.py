"""Tool: create_maintenance — idempotent maintenance window creation."""

from __future__ import annotations

import json
import time
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


async def _find_existing_maintenance(
    client: ZabbixClient, name: str
) -> str | None:
    """Return maintenanceid if a maintenance with *name* already exists."""
    existing = await client.maintenance_get(filter={"name": name})
    return str(existing[0]["maintenanceid"]) if existing else None


async def _resolve_host_for_maintenance(
    client: ZabbixClient, host: str
) -> str:
    """Resolve host name to hostid, raising ZabbixNotFoundError if absent."""
    hosts = await client.host_get(filter={"host": host})
    if not hosts:
        hosts = await client.host_get(search={"name": host})
    if not hosts:
        raise ZabbixNotFoundError(f"Host '{host}' not found.")
    return str(hosts[0]["hostid"])


async def _resolve_group_for_maintenance(
    client: ZabbixClient, group: str
) -> str:
    """Resolve group name to groupid, raising ZabbixNotFoundError if absent."""
    groups = await client.hostgroup_get(filter={"name": group})
    if not groups:
        raise ZabbixNotFoundError(f"Host group '{group}' not found.")
    return str(groups[0]["groupid"])


def _build_maintenance_payload(
    name: str,
    reason: str,
    active_since: int,
    active_till: int,
    hostids: list[str],
    groupids: list[str],
) -> dict[str, Any]:
    """Assemble the Zabbix maintenance.create payload."""
    duration_secs = active_till - active_since
    payload: dict[str, Any] = {
        "name": name,
        "active_since": active_since,
        "active_till": active_till,
        "description": reason,
        "timeperiods": [
            {
                "timeperiod_type": 0,  # ONE_TIME_ONLY
                "start_date": active_since,
                "period": duration_secs,
            }
        ],
    }
    if hostids:
        payload["hostids"] = hostids
    if groupids:
        payload["groupids"] = groupids
    return payload


async def create_maintenance(
    client: ZabbixClient,
    name: str,
    reason: str,
    duration_minutes: int,
    host: str | None = None,
    host_group: str | None = None,
) -> str:
    """Create a Zabbix maintenance window (idempotent by *name*).

    Provide either *host* or *host_group* (or both). If a maintenance with
    the same *name* already exists, its ID is returned without creating a
    duplicate.

    Args:
        client: Authenticated ZabbixClient instance.
        name: Unique maintenance name used for idempotency checks.
        reason: Human-readable description of why maintenance is needed.
        duration_minutes: Length of the maintenance window (minimum 1).
        host: Target host name (optional).
        host_group: Target host group name (optional).

    Returns:
        JSON with maintenance_id and status message.

    Raises:
        ZabbixValidationError: If neither host nor host_group is provided,
            or if duration_minutes < 1.
        ZabbixNotFoundError: If the specified host or group does not exist.
    """
    if not host and not host_group:
        raise ZabbixValidationError(
            "Provide at least one of 'host' or 'host_group'."
        )
    if duration_minutes < 1:
        raise ZabbixValidationError("duration_minutes must be at least 1.")
    if not reason or not reason.strip():
        raise ZabbixValidationError("reason is required and must not be empty.")

    existing_id = await _find_existing_maintenance(client, name)
    if existing_id:
        return json.dumps(
            {"maintenance_id": existing_id, "status": "already_exists"},
            indent=2,
        )

    hostids: list[str] = []
    groupids: list[str] = []
    if host:
        hostids.append(await _resolve_host_for_maintenance(client, host))
    if host_group:
        groupids.append(await _resolve_group_for_maintenance(client, host_group))

    now = int(time.time())
    active_till = now + duration_minutes * 60
    payload = _build_maintenance_payload(
        name, reason, now, active_till, hostids, groupids
    )
    maintenance_id = await client.maintenance_create(payload)
    return json.dumps(
        {"maintenance_id": maintenance_id, "status": "created"},
        indent=2,
    )
