"""MCP server entry point — registers all 15 Zabbix tools with FastMCP."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncGenerator

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .config import Settings, get_settings
from .logging_config import configure_logging
from .tools import hosts, items, macros, maintenance, metrics, problems, reports, triggers
from .zabbix.client import ZabbixClient
from .zabbix.errors import ZabbixMCPError

logger = structlog.get_logger(__name__)

# Module-level client, set during lifespan startup
_app_state: dict[str, Any] = {}


def _get_client() -> ZabbixClient:
    """Return the shared ZabbixClient; raises RuntimeError if not initialised."""
    client = _app_state.get("client")
    if not isinstance(client, ZabbixClient):
        raise RuntimeError("ZabbixClient is not initialised.")
    return client


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncGenerator[None, None]:
    """Initialise ZabbixClient before serving requests; close on shutdown."""
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    async with ZabbixClient(settings) as client:
        _app_state["client"] = client
        _app_state["settings"] = settings
        logger.info("server_started", zabbix_url=settings.zabbix_url())
        yield
    logger.info("server_stopped")


mcp = FastMCP("zabbix-mcp-server", lifespan=_lifespan)


# ------------------------------------------------------------------ decorator

async def _run_tool(tool_name: str, coro: Any) -> str:
    """Execute *coro*, log structured result, and convert errors to strings."""
    start = time.monotonic()
    try:
        result: str = await coro
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "tool_called",
            tool_name=tool_name,
            outcome="success",
            duration_ms=duration_ms,
        )
        return result
    except ZabbixMCPError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning(
            "tool_called",
            tool_name=tool_name,
            outcome="error",
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        return f"Error: {exc.message}"
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_called",
            tool_name=tool_name,
            outcome="error",
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        return f"Error: {exc}"


# ------------------------------------------------------------------ problems

@mcp.tool()
async def get_active_problems(
    host_name: str | None = None,
    host_group: str | None = None,
    severity: Annotated[int | None, Field(ge=0, le=5)] = None,
    acknowledged: bool | None = None,
) -> str:
    """Return active Zabbix problems as JSON. Filter by host, group, or severity (0–5)."""
    return await _run_tool(
        "get_active_problems",
        problems.get_active_problems(
            _get_client(),
            host_name=host_name,
            host_group=host_group,
            severity=severity,
            acknowledged=acknowledged,
        ),
    )


@mcp.tool()
async def acknowledge_problem(
    problem_id: str,
    comment: str,
    close: bool = False,
) -> str:
    """Acknowledge a Zabbix problem by event ID with a mandatory comment."""
    return await _run_tool(
        "acknowledge_problem",
        problems.acknowledge_problem(
            _get_client(), problem_id=problem_id, comment=comment, close=close
        ),
    )


@mcp.tool()
async def get_incident_summary(
    problem_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
) -> str:
    """Return an incident summary — affected hosts, severity breakdown, event timeline."""
    return await _run_tool(
        "get_incident_summary",
        problems.get_incident_summary(
            _get_client(),
            problem_id=problem_id,
            time_from=time_from,
            time_to=time_to,
        ),
    )


# ------------------------------------------------------------------ maintenance

@mcp.tool()
async def create_maintenance(
    name: str,
    reason: str,
    duration_minutes: Annotated[int, Field(ge=1)],
    host: str | None = None,
    host_group: str | None = None,
) -> str:
    """Create a Zabbix maintenance window. Idempotent — reuses existing window by name."""
    return await _run_tool(
        "create_maintenance",
        maintenance.create_maintenance(
            _get_client(),
            name=name,
            reason=reason,
            duration_minutes=duration_minutes,
            host=host,
            host_group=host_group,
        ),
    )


# ------------------------------------------------------------------ hosts

@mcp.tool()
async def add_host(
    name: str,
    ip: str,
    host_groups: list[str],
    templates: list[str] | None = None,
    dns: str = "",
    port: str = "10050",
) -> str:
    """Add a Zabbix host with agent interface, groups, and templates. Idempotent by name."""
    return await _run_tool(
        "add_host",
        hosts.add_host(
            _get_client(),
            name=name,
            ip=ip,
            host_groups=host_groups,
            templates=templates,
            dns=dns,
            port=port,
        ),
    )


@mcp.tool()
async def search_hosts(
    name_substring: str | None = None,
    host_group: str | None = None,
    template: str | None = None,
    tag: str | None = None,
) -> str:
    """Search Zabbix hosts by name substring, group, linked template, or tag."""
    return await _run_tool(
        "search_hosts",
        hosts.search_hosts(
            _get_client(),
            name_substring=name_substring,
            host_group=host_group,
            template=template,
            tag=tag,
        ),
    )


@mcp.tool()
async def check_host_availability(host: str) -> str:
    """Check whether the Zabbix agent on a host is reachable."""
    return await _run_tool(
        "check_host_availability",
        hosts.check_host_availability(_get_client(), host=host),
    )


# ------------------------------------------------------------------ metrics

@mcp.tool()
async def get_metric_value(
    item_key: str,
    host: str | None = None,
    host_id: str | None = None,
) -> str:
    """Get the latest value of a Zabbix metric by host name/ID and item key."""
    return await _run_tool(
        "get_metric_value",
        metrics.get_metric_value(
            _get_client(), item_key=item_key, host=host, host_id=host_id
        ),
    )


@mcp.tool()
async def get_metric_history(
    item_key: str,
    time_from: str,
    time_to: str,
    host: str | None = None,
    host_id: str | None = None,
) -> str:
    """Fetch metric history for a host/item pair within a time range."""
    return await _run_tool(
        "get_metric_history",
        metrics.get_metric_history(
            _get_client(),
            item_key=item_key,
            time_from=time_from,
            time_to=time_to,
            host=host,
            host_id=host_id,
        ),
    )


@mcp.tool()
async def export_metrics(
    hosts_list: list[str],
    items_list: list[str],
    time_from: str,
    time_to: str,
    format: str = "json",
) -> str:
    """Export metric history for multiple hosts/items as JSON or CSV."""
    return await _run_tool(
        "export_metrics",
        metrics.export_metrics(
            _get_client(),
            hosts=hosts_list,
            items=items_list,
            time_from=time_from,
            time_to=time_to,
            format=format,
        ),
    )


# ------------------------------------------------------------------ triggers

@mcp.tool()
async def get_triggers(host: str) -> str:
    """List all Zabbix triggers configured on a host."""
    return await _run_tool(
        "get_triggers",
        triggers.get_triggers(_get_client(), host=host),
    )


@mcp.tool()
async def create_trigger(
    name: str,
    expression: str,
    priority: Annotated[int, Field(ge=0, le=5)] = 3,
    description: str = "",
) -> str:
    """Create a Zabbix trigger with local expression syntax validation."""
    return await _run_tool(
        "create_trigger",
        triggers.create_trigger(
            _get_client(),
            name=name,
            expression=expression,
            priority=priority,
            description=description,
        ),
    )


# ------------------------------------------------------------------ items / macros / reports

@mcp.tool()
async def search_items(
    name_substring: str | None = None,
    key_substring: str | None = None,
    description: str | None = None,
    host_id: str | None = None,
) -> str:
    """Search Zabbix items (metrics) by name, key, or description substring."""
    return await _run_tool(
        "search_items",
        items.search_items(
            _get_client(),
            name_substring=name_substring,
            key_substring=key_substring,
            description=description,
            host_id=host_id,
        ),
    )


@mcp.tool()
async def bulk_update_macro(
    macro: str,
    value: str,
    name_pattern: str | None = None,
    tag: str | None = None,
) -> str:
    """Update a Zabbix macro value across all hosts matching a pattern or tag."""
    return await _run_tool(
        "bulk_update_macro",
        macros.bulk_update_macro(
            _get_client(),
            macro=macro,
            value=value,
            name_pattern=name_pattern,
            tag=tag,
        ),
    )


@mcp.tool()
async def get_availability_report(
    hosts_list: list[str],
    time_from: str,
    time_to: str,
) -> str:
    """Calculate uptime percentage per host over a calendar period."""
    return await _run_tool(
        "get_availability_report",
        reports.get_availability_report(
            _get_client(),
            hosts=hosts_list,
            time_from=time_from,
            time_to=time_to,
        ),
    )
