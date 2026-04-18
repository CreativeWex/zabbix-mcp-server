#!/usr/bin/env python3
"""Run all MCP tool implementations once and print JSON lines for mcp-description.md (stdout)."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# Ensure .env is found
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zabbix_mcp.config import get_settings, reset_settings
from zabbix_mcp.tools import (
    hosts,
    items,
    macros,
    maintenance,
    metrics,
    problems,
    reports,
    triggers,
)
from zabbix_mcp.zabbix.client import ZabbixClient


def emit(name: str, request: dict[str, Any], response: str) -> None:
    line = json.dumps(
        {"tool": name, "request": request, "response": response},
        ensure_ascii=False,
    )
    print(line, flush=True)


async def run_all() -> None:
    reset_settings()
    get_settings()
    async with ZabbixClient(get_settings()) as client:
        ts = int(time.time())

        # 1 get_active_problems
        req = {}
        out = await problems.get_active_problems(client)
        emit("get_active_problems", req, out)

        # 2 search_hosts — no filters returns first page via host.get
        req = {}
        out = await hosts.search_hosts(client)
        emit("search_hosts", req, out)

        hosts_json = json.loads(out) if out.startswith("[") else []
        host_label = "Zabbix server"
        if hosts_json and isinstance(hosts_json, list):
            for h in hosts_json:
                if h.get("name") == "Zabbix server" or h.get("technical_name") == "Zabbix server":
                    host_label = str(h.get("name") or "Zabbix server")
                    break
            else:
                host_label = str(hosts_json[0].get("name") or "Zabbix server")

        # 3 search_items — pick a key for metrics on that host
        req = {"key_substring": "agent.ping"}
        out = await items.search_items(client, key_substring="agent.ping")
        emit("search_items", req, out)

        items_json = json.loads(out) if out.startswith("[") else []
        item_key = "agent.ping"
        if items_json and isinstance(items_json, list):
            for row in items_json:
                if row.get("host") == host_label and row.get("key_"):
                    item_key = str(row["key_"])
                    break
            if item_key == "agent.ping" and items_json[0].get("key_"):
                item_key = str(items_json[0]["key_"])

        # 4 get_metric_value
        req = {"item_key": item_key, "host": host_label}
        out = await metrics.get_metric_value(
            client, item_key=item_key, host=host_label
        )
        emit("get_metric_value", req, out)

        now = datetime.now(tz=timezone.utc)
        tf = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        tt = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        req = {
            "item_key": item_key,
            "time_from": tf,
            "time_to": tt,
            "host": host_label,
        }
        out = await metrics.get_metric_history(
            client,
            item_key=item_key,
            time_from=tf,
            time_to=tt,
            host=host_label,
        )
        emit("get_metric_history", req, out)

        req = {
            "hosts_list": [host_label],
            "items_list": [item_key],
            "time_from": tf,
            "time_to": tt,
            "format": "json",
        }
        out = await metrics.export_metrics(
            client,
            hosts=[host_label],
            items=[item_key],
            time_from=tf,
            time_to=tt,
            format="json",
        )
        emit("export_metrics", req, out)

        req = {"host": host_label}
        out = await hosts.check_host_availability(client, host=host_label)
        emit("check_host_availability", req, out)

        req = {"host": host_label}
        out = await triggers.get_triggers(client, host=host_label)
        emit("get_triggers", req, out)

        day = now.strftime("%Y-%m-%d")
        prev = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        req = {"hosts_list": [host_label], "time_from": prev, "time_to": day}
        out = await reports.get_availability_report(
            client, hosts=[host_label], time_from=prev, time_to=day
        )
        emit("get_availability_report", req, out)

        # get_incident_summary — time window
        req = {
            "problem_id": None,
            "time_from": prev + "T00:00:00Z",
            "time_to": day + "T23:59:59Z",
        }
        out = await problems.get_incident_summary(
            client,
            problem_id=None,
            time_from=prev + "T00:00:00Z",
            time_to=day + "T23:59:59Z",
        )
        emit("get_incident_summary", req, out)

        # create_maintenance
        mname = f"mcp-doc-maint-{ts}"
        req = {
            "name": mname,
            "reason": "MCP documentation sample",
            "duration_minutes": 30,
            "host": host_label,
            "host_group": None,
        }
        out = await maintenance.create_maintenance(
            client,
            name=mname,
            reason="MCP documentation sample",
            duration_minutes=30,
            host=host_label,
            host_group=None,
        )
        emit("create_maintenance", req, out)

        # add_host — unique technical name
        hname = f"mcp_doc_host_{ts}"
        req = {
            "name": hname,
            "ip": "127.0.0.1",
            "host_groups": ["Zabbix servers"],
            "templates": None,
            "dns": "",
            "port": "10050",
        }
        try:
            out = await hosts.add_host(
                client,
                name=hname,
                ip="127.0.0.1",
                host_groups=["Zabbix servers"],
                templates=None,
                dns="",
                port="10050",
            )
        except Exception as exc:
            out = f"Error: {exc}"
        emit("add_host", req, out)

        # create_trigger — expression on Zabbix server item
        expr = f"last(/{host_label}/agent.ping)>0"
        tname = f"MCP doc trigger {ts}"
        req = {
            "name": tname,
            "expression": expr,
            "priority": 1,
            "description": "Sample from MCP docs collector",
        }
        try:
            out = await triggers.create_trigger(
                client,
                name=tname,
                expression=expr,
                priority=1,
                description="Sample from MCP docs collector",
            )
        except Exception as exc:
            out = f"Error: {exc}"
        emit("create_trigger", req, out)

        # bulk_update_macro — narrow pattern
        req = {
            "macro": "{$MCP_DOC_MACRO}",
            "value": "1",
            "name_pattern": hname,
            "tag": None,
        }
        try:
            out = await macros.bulk_update_macro(
                client,
                macro="{$MCP_DOC_MACRO}",
                value="1",
                name_pattern=hname,
                tag=None,
            )
        except Exception as exc:
            out = f"Error: {exc}"
        emit("bulk_update_macro", req, out)

        # acknowledge_problem — only if we have an active problem
        probs_raw = await problems.get_active_problems(client)
        ack_req = {
            "problem_id": "0",
            "comment": "doc sample",
            "close": False,
        }
        ack_out = "No active problems to acknowledge."
        if probs_raw.startswith("["):
            plist = json.loads(probs_raw)
            if plist and isinstance(plist, list) and plist[0].get("problem_id"):
                pid = str(plist[0]["problem_id"])
                ack_req = {"problem_id": pid, "comment": "MCP mcp-description.md sample ack", "close": False}
                try:
                    ack_out = await problems.acknowledge_problem(
                        client,
                        problem_id=pid,
                        comment="MCP mcp-description.md sample ack",
                        close=False,
                    )
                except Exception as exc:
                    ack_out = f"Error: {exc}"
        emit("acknowledge_problem", ack_req, ack_out)


def main() -> None:
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
