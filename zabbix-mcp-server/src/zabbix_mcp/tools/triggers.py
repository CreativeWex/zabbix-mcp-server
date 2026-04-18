"""Tools: get_triggers, create_trigger."""

from __future__ import annotations

import json
import re
from typing import Any

from ..zabbix.client import ZabbixClient
from ..zabbix.errors import ZabbixNotFoundError, ZabbixValidationError

# Basic Zabbix trigger expression pattern: func(/host/key) op value
# Host segment may contain spaces (e.g. ``/Zabbix server/agent.ping``).
_EXPRESSION_PATTERN = re.compile(
    r"\w+\s*\(\s*/[\w.\- ]+/[\w.\[\]<>,\s]+\s*\)"
)


def _validate_expression_syntax(expression: str) -> None:
    """Raise ZabbixValidationError for obviously malformed expressions.

    Args:
        expression: Trigger expression string to validate.

    Raises:
        ZabbixValidationError: If the expression does not contain at least
            one valid Zabbix function call pattern.
    """
    if not expression or not expression.strip():
        raise ZabbixValidationError("Trigger expression must not be empty.")
    if not _EXPRESSION_PATTERN.search(expression):
        raise ZabbixValidationError(
            f"Invalid trigger expression: '{expression}'. "
            "Expected at least one Zabbix function call, "
            "e.g. last(/hostname/item.key)>90"
        )


def _format_trigger(t: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Zabbix trigger dict to the MCP response format."""
    return {
        "trigger_id": t.get("triggerid", ""),
        "description": t.get("description", ""),
        "expression": t.get("expression", ""),
        "state": int(t.get("state", 0)),  # 0=OK, 1=Problem
        "status": "Enabled" if str(t.get("status")) == "0" else "Disabled",
        "priority": int(t.get("priority", 0)),
        "last_change": int(t.get("lastchange", 0)),
    }


async def get_triggers(
    client: ZabbixClient,
    host: str,
) -> str:
    """Return all triggers configured on a Zabbix host.

    Args:
        client: Authenticated ZabbixClient instance.
        host: Host name to retrieve triggers for.

    Returns:
        JSON list of trigger objects with expression, state, and priority.

    Raises:
        ZabbixNotFoundError: If the host does not exist in Zabbix.
    """
    hosts = await client.host_get(filter={"host": host})
    if not hosts:
        hosts = await client.host_get(search={"name": host})
    if not hosts:
        raise ZabbixNotFoundError(f"Host '{host}' not found.")

    host_id = str(hosts[0]["hostid"])
    triggers = await client.trigger_get(hostids=[host_id])
    if not triggers:
        return "[]"
    return json.dumps([_format_trigger(t) for t in triggers], indent=2)


async def create_trigger(
    client: ZabbixClient,
    name: str,
    expression: str,
    priority: int = 3,
    description: str = "",
) -> str:
    """Create a Zabbix trigger after validating expression syntax.

    The expression is validated locally for obvious syntax errors before
    being sent to Zabbix. Any remaining API-level errors are mapped to
    human-readable messages.

    Args:
        client: Authenticated ZabbixClient instance.
        name: Trigger description / display name (must not be empty).
        expression: Zabbix trigger expression (new format for 6.4+).
        priority: Severity level 0–5 (default 3=Average).
        description: Optional long description.

    Returns:
        JSON with trigger_id and status.

    Raises:
        ZabbixValidationError: If name is empty or expression is malformed.
    """
    if not name or not name.strip():
        raise ZabbixValidationError("name is required and must not be empty.")
    if not (0 <= priority <= 5):
        raise ZabbixValidationError("priority must be between 0 and 5.")

    _validate_expression_syntax(expression)

    payload: dict[str, Any] = {
        "description": name,
        "expression": expression,
        "priority": priority,
    }
    if description:
        payload["comments"] = description

    trigger_id = await client.trigger_create(payload)
    return json.dumps({"trigger_id": trigger_id, "status": "created"}, indent=2)
