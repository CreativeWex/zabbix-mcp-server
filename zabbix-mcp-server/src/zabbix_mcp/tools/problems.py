"""Tools: get_active_problems, acknowledge_problem, get_incident_summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixMCPError, ZabbixNotFoundError, ZabbixValidationError


# ------------------------------------------------------------------ helpers

async def _resolve_hostids(
    client: ZabbixClient, host_name: str | None
) -> list[str] | None:
    """Return [hostid] for *host_name*, or None if no filter needed."""
    if not host_name:
        return None
    hosts = await client.host_get(filter={"host": host_name})
    if not hosts:
        hosts = await client.host_get(search={"name": host_name})
    return [str(h["hostid"]) for h in hosts] if hosts else []


async def _resolve_groupids(
    client: ZabbixClient, host_group: str | None
) -> list[str] | None:
    """Return [groupid] for *host_group*, or None if no filter needed."""
    if not host_group:
        return None
    groups = await client.hostgroup_get(filter={"name": host_group})
    return [str(g["groupid"]) for g in groups] if groups else []


def _severity_label(severity: str | int) -> str:
    labels = {
        "0": "Not classified", "1": "Information", "2": "Warning",
        "3": "Average", "4": "High", "5": "Disaster",
    }
    return labels.get(str(severity), str(severity))


def _format_problem(p: dict[str, Any]) -> dict[str, Any]:
    hosts = p.get("hosts", [])
    host_name = hosts[0]["name"] if hosts else "unknown"
    ts = int(p.get("clock", 0))
    since = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "unknown"
    return {
        "problem_id": p.get("eventid", ""),
        "host": host_name,
        "description": p.get("name", ""),
        "severity": _severity_label(p.get("severity", "0")),
        "severity_level": int(p.get("severity", 0)),
        "since": since,
        "acknowledged": p.get("acknowledges", "0") not in ("0", 0),
    }


# ------------------------------------------------------------------ tools

async def get_active_problems(
    client: ZabbixClient,
    host_name: str | None = None,
    host_group: str | None = None,
    severity: int | None = None,
    acknowledged: bool | None = None,
) -> str:
    """Return active Zabbix problems as a JSON list, with optional filters.

    Args:
        client: Authenticated ZabbixClient instance.
        host_name: Filter to a specific host name.
        host_group: Filter to a specific host group name.
        severity: Minimum severity level 0–5 (0=Not classified, 5=Disaster).
        acknowledged: If True/False, filter by acknowledgement status.

    Returns:
        JSON-serialised list of problem objects, or a plain message if empty.
    """
    if severity is not None and not (0 <= severity <= 5):
        raise ZabbixValidationError(
            f"severity must be between 0 and 5, got {severity}"
        )

    hostids = await _resolve_hostids(client, host_name)
    groupids = await _resolve_groupids(client, host_group)

    kwargs: dict[str, Any] = {}
    if hostids is not None:
        kwargs["hostids"] = hostids
    if groupids is not None:
        kwargs["groupids"] = groupids
    if severity is not None:
        kwargs["severities"] = list(range(severity, 6))
    if acknowledged is not None:
        kwargs["acknowledged"] = 1 if acknowledged else 0

    problems = await client.problem_get(**kwargs)
    if not problems:
        return "No active problems found."
    return json.dumps([_format_problem(p) for p in problems], indent=2)


async def acknowledge_problem(
    client: ZabbixClient,
    problem_id: str,
    comment: str,
    close: bool = False,
) -> str:
    """Acknowledge a Zabbix problem and optionally close it.

    Args:
        client: Authenticated ZabbixClient instance.
        problem_id: The event ID of the problem to acknowledge.
        comment: Mandatory human-readable comment (must not be empty).
        close: If True, also close the problem (action bitmask includes 1).

    Returns:
        Confirmation message string.

    Raises:
        ZabbixValidationError: If comment is empty.
        ZabbixNotFoundError: If the problem does not exist.
    """
    if not comment.strip():
        raise ZabbixValidationError("comment is required and must not be empty")

    # action: 2=acknowledge + 4=add message = 6; add 1 if closing
    action = 7 if close else 6
    try:
        await client.event_acknowledge([problem_id], message=comment, action=action)
    except ZabbixMCPError:
        raise
    return f"Problem {problem_id} acknowledged successfully."


def _build_summary(problems: list[dict[str, Any]], time_from: int, time_to: int) -> dict[str, Any]:
    """Aggregate problem list into an incident summary dict."""
    affected_hosts: set[str] = set()
    by_severity: dict[str, int] = {}
    timeline: list[dict[str, str]] = []

    for p in problems:
        hosts = p.get("hosts", [])
        for h in hosts:
            affected_hosts.add(h.get("name", "unknown"))
        sev = _severity_label(p.get("severity", "0"))
        by_severity[sev] = by_severity.get(sev, 0) + 1
        clock = int(p.get("clock", 0))
        r_clock = int(p.get("r_clock", 0))
        timeline.append({
            "problem_id": p.get("eventid", ""),
            "description": p.get("name", ""),
            "started": datetime.fromtimestamp(clock, tz=timezone.utc).isoformat(),
            "resolved": (
                datetime.fromtimestamp(r_clock, tz=timezone.utc).isoformat()
                if r_clock else "still active"
            ),
        })

    return {
        "total_problems": len(problems),
        "affected_hosts": sorted(affected_hosts),
        "problems_by_severity": by_severity,
        "event_timeline": timeline,
        "period": {
            "from": datetime.fromtimestamp(time_from, tz=timezone.utc).isoformat(),
            "to": datetime.fromtimestamp(time_to, tz=timezone.utc).isoformat(),
        },
    }


async def get_incident_summary(
    client: ZabbixClient,
    problem_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
) -> str:
    """Return a summary of one incident or all incidents in a time window.

    Provide either *problem_id* OR a *time_from*/*time_to* window.

    Args:
        client: Authenticated ZabbixClient instance.
        problem_id: Specific event ID to summarise.
        time_from: ISO-8601 start of the time window.
        time_to: ISO-8601 end of the time window.

    Returns:
        JSON summary with affected hosts, severity breakdown, and timeline.

    Raises:
        ZabbixValidationError: If neither problem_id nor time window is provided.
    """
    import time as _time
    from dateutil import parser as dateparser

    kwargs: dict[str, Any] = {}
    now = int(_time.time())

    if problem_id:
        kwargs["eventids"] = [problem_id]
        tf, tt = now - 86400 * 7, now
    elif time_from and time_to:
        tf = int(dateparser.parse(time_from).timestamp())
        tt = int(dateparser.parse(time_to).timestamp())
        kwargs["time_from"] = tf
        kwargs["time_till"] = tt
    else:
        raise ZabbixValidationError(
            "Provide either problem_id or both time_from and time_to."
        )

    problems = await client.problem_get(**kwargs)
    if problem_id and not problems:
        raise ZabbixNotFoundError(f"Problem {problem_id} not found.")

    summary = _build_summary(problems, tf, tt)
    return json.dumps(summary, indent=2)
