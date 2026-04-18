"""Tool: get_availability_report — uptime percentage per host over a period."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixNotFoundError, ZabbixValidationError


async def _get_host_id(client: ZabbixClient, host_name: str) -> str:
    """Resolve host name to ID, raising ZabbixNotFoundError if absent."""
    hosts = await client.host_get(filter={"host": host_name})
    if not hosts:
        hosts = await client.host_get(search={"name": host_name})
    if not hosts:
        raise ZabbixNotFoundError(f"Host '{host_name}' not found.")
    return str(hosts[0]["hostid"])


def _calculate_downtime(
    problems: list[dict[str, Any]],
    time_from: int,
    time_to: int,
) -> int:
    """Return total downtime seconds within [time_from, time_to].

    Overlapping problem periods are not merged (conservative estimate).
    """
    downtime = 0
    for p in problems:
        start = max(int(p.get("clock", time_from)), time_from)
        r_clock = int(p.get("r_clock", 0))
        end = min(r_clock if r_clock > 0 else time_to, time_to)
        if end > start:
            downtime += end - start
    return downtime


def _host_availability_entry(
    host_name: str,
    problems: list[dict[str, Any]],
    time_from: int,
    time_to: int,
) -> dict[str, Any]:
    """Build the availability report dict for one host."""
    period = time_to - time_from
    downtime = _calculate_downtime(problems, time_from, time_to)
    uptime = max(0, period - downtime)
    uptime_pct = round(uptime / period * 100, 4) if period > 0 else 100.0
    return {
        "host": host_name,
        "uptime_percent": uptime_pct,
        "downtime_seconds": downtime,
        "uptime_seconds": uptime,
        "period_seconds": period,
        "period": {
            "from": datetime.fromtimestamp(time_from, tz=timezone.utc).isoformat(),
            "to": datetime.fromtimestamp(time_to, tz=timezone.utc).isoformat(),
        },
    }


async def get_availability_report(
    client: ZabbixClient,
    hosts: list[str],
    time_from: str,
    time_to: str,
) -> str:
    """Calculate uptime percentage for a list of hosts over a time period.

    Uses Zabbix problem history to estimate downtime. Problems with an open
    ``r_clock`` (still active at report time) count until ``time_to``.

    Args:
        client: Authenticated ZabbixClient instance.
        hosts: List of host names to include in the report.
        time_from: ISO-8601 or ``YYYY-MM-DD`` start of the period.
        time_to: ISO-8601 or ``YYYY-MM-DD`` end of the period.

    Returns:
        JSON list with uptime_percent and downtime_seconds per host.

    Raises:
        ZabbixValidationError: If time_from >= time_to.
        ZabbixNotFoundError: If any host is not found.
    """
    from dateutil import parser as dateparser

    tf = int(dateparser.parse(time_from).timestamp())
    tt = int(dateparser.parse(time_to).timestamp())
    if tf >= tt:
        raise ZabbixValidationError("from must be earlier than to.")

    report: list[dict[str, Any]] = []
    for host_name in hosts:
        host_id = await _get_host_id(client, host_name)
        problems = await client.problem_get(
            hostids=[host_id],
            time_from=tf,
            time_till=tt,
        )
        entry = _host_availability_entry(host_name, problems, tf, tt)
        report.append(entry)

    return json.dumps(report, indent=2)
