"""Tools: get_metric_value, get_metric_history, export_metrics."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixNotFoundError, ZabbixValidationError

# Zabbix item value_type → history table type
_VALUE_TYPE_TO_HISTORY: dict[str, int] = {
    "0": 0,  # float
    "1": 1,  # char
    "2": 2,  # log
    "3": 3,  # uint
    "4": 4,  # text
}


async def _get_item(
    client: ZabbixClient,
    host: str | None,
    host_id: str | None,
    item_key: str,
) -> dict[str, Any]:
    """Fetch a single item by host + item_key combination."""
    kwargs: dict[str, Any] = {"filter": {"key_": item_key}}
    if host_id:
        kwargs["hostids"] = [host_id]
    elif host:
        hosts = await client.host_get(filter={"host": host})
        if not hosts:
            hosts = await client.host_get(search={"name": host})
        if not hosts:
            raise ZabbixNotFoundError(f"Host '{host}' not found.")
        kwargs["hostids"] = [str(hosts[0]["hostid"])]

    items = await client.item_get(**kwargs)
    if not items:
        label = host or host_id or "unknown"
        raise ZabbixNotFoundError(
            f"Item '{item_key}' not found on host '{label}'."
        )
    return items[0]


async def get_metric_value(
    client: ZabbixClient,
    item_key: str,
    host: str | None = None,
    host_id: str | None = None,
) -> str:
    """Get the latest value of a Zabbix metric.

    Provide either *host* (name) or *host_id*.

    Args:
        client: Authenticated ZabbixClient instance.
        item_key: Zabbix item key (e.g. ``system.cpu.util``).
        host: Host name or technical name.
        host_id: Numeric host ID (alternative to *host*).

    Returns:
        JSON with value, units, item_key, host, and last_updated timestamp.

    Raises:
        ZabbixNotFoundError: If host or item is not found.
        ZabbixValidationError: If neither host nor host_id is provided.
    """
    if not host and not host_id:
        raise ZabbixValidationError("Provide either 'host' or 'host_id'.")

    item = await _get_item(client, host, host_id, item_key)
    last_clock = int(item.get("lastclock", 0) or 0)
    last_updated = (
        datetime.fromtimestamp(last_clock, tz=timezone.utc).isoformat()
        if last_clock
        else None
    )
    last_value = item.get("lastvalue", "")
    host_info = item.get("hosts", [{}])
    host_name = host_info[0].get("name", host or host_id or "")

    if not last_value and last_clock == 0:
        return json.dumps(
            {
                "item_key": item_key,
                "host": host_name,
                "message": f"No recent data available for item '{item_key}'.",
                "last_updated": None,
            },
            indent=2,
        )

    return json.dumps(
        {
            "item_key": item_key,
            "host": host_name,
            "value": last_value,
            "units": item.get("units", ""),
            "last_updated": last_updated,
        },
        indent=2,
    )


async def get_metric_history(
    client: ZabbixClient,
    item_key: str,
    time_from: str,
    time_to: str,
    host: str | None = None,
    host_id: str | None = None,
) -> str:
    """Return metric history within a time range as a JSON list.

    Args:
        client: Authenticated ZabbixClient instance.
        item_key: Zabbix item key.
        time_from: ISO-8601 start of the range.
        time_to: ISO-8601 end of the range.
        host: Host name (optional if host_id provided).
        host_id: Numeric host ID (optional if host provided).

    Returns:
        JSON list of ``{clock, value}`` data points.

    Raises:
        ZabbixValidationError: If time_from >= time_to.
        ZabbixNotFoundError: If host or item is not found.
    """
    from dateutil import parser as dateparser

    if not host and not host_id:
        raise ZabbixValidationError("Provide either 'host' or 'host_id'.")

    tf = int(dateparser.parse(time_from).timestamp())
    tt = int(dateparser.parse(time_to).timestamp())
    if tf >= tt:
        raise ZabbixValidationError("time_from must be earlier than time_to.")

    item = await _get_item(client, host, host_id, item_key)
    history_type = _VALUE_TYPE_TO_HISTORY.get(str(item.get("value_type", "0")), 0)

    points = await client.history_get(
        itemids=[str(item["itemid"])],
        history=history_type,
        time_from=tf,
        time_till=tt,
    )
    formatted = [
        {
            "clock": int(p["clock"]),
            "timestamp": datetime.fromtimestamp(int(p["clock"]), tz=timezone.utc).isoformat(),
            "value": p["value"],
        }
        for p in points
    ]
    return json.dumps(formatted, indent=2)


async def _collect_export_data(
    client: ZabbixClient,
    hosts: list[str],
    items: list[str],
    tf: int,
    tt: int,
) -> list[dict[str, Any]]:
    """Gather history rows for all host/item combinations."""
    rows: list[dict[str, Any]] = []
    for host_name in hosts:
        host_list = await client.host_get(filter={"host": host_name})
        if not host_list:
            host_list = await client.host_get(search={"name": host_name})
        if not host_list:
            continue
        host_id = str(host_list[0]["hostid"])
        for item_key in items:
            item_list = await client.item_get(
                hostids=[host_id], filter={"key_": item_key}
            )
            if not item_list:
                continue
            item = item_list[0]
            history_type = _VALUE_TYPE_TO_HISTORY.get(
                str(item.get("value_type", "0")), 0
            )
            points = await client.history_get(
                itemids=[str(item["itemid"])],
                history=history_type,
                time_from=tf,
                time_till=tt,
            )
            for p in points:
                rows.append(
                    {
                        "host": host_name,
                        "item_key": item_key,
                        "clock": int(p["clock"]),
                        "value": p["value"],
                    }
                )
    return rows


async def export_metrics(
    client: ZabbixClient,
    hosts: list[str],
    items: list[str],
    time_from: str,
    time_to: str,
    format: str = "json",
) -> str:
    """Export metric history for multiple hosts/items as JSON or CSV.

    Args:
        client: Authenticated ZabbixClient instance.
        hosts: List of host names.
        items: List of item keys.
        time_from: ISO-8601 start of the export range.
        time_to: ISO-8601 end of the export range.
        format: Output format — ``"json"`` or ``"csv"``.

    Returns:
        JSON array or CSV string of metric data points.

    Raises:
        ZabbixValidationError: If format is unsupported or time range is invalid.
    """
    from dateutil import parser as dateparser

    if format not in ("json", "csv"):
        raise ZabbixValidationError(
            f"Unsupported format '{format}'. Allowed: json, csv"
        )

    tf = int(dateparser.parse(time_from).timestamp())
    tt = int(dateparser.parse(time_to).timestamp())
    if tf >= tt:
        raise ZabbixValidationError("time_from must be earlier than time_to.")

    rows = await _collect_export_data(client, hosts, items, tf, tt)

    if format == "json":
        return json.dumps(rows, indent=2)

    # CSV format
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["host", "item_key", "clock", "value"]
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
