"""Async Zabbix JSON-RPC 2.0 client with pagination, auth, and error mapping."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings
from .errors import ZabbixConnectionError, ZabbixMCPError, map_api_error

_REQUEST_ID = 1


class ZabbixClient:
    """Async HTTP client for the Zabbix JSON-RPC 2.0 API.

    Use as an async context manager to ensure the underlying
    ``httpx.AsyncClient`` is properly closed:

        async with ZabbixClient(settings) as client:
            problems = await client.problem_get()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http: httpx.AsyncClient | None = None
        self._api_url = f"{settings.zabbix_url()}/api_jsonrpc.php"

    async def __aenter__(self) -> "ZabbixClient":
        self._http = httpx.AsyncClient(
            timeout=float(self._settings.timeout_seconds),
            headers={
                "Authorization": f"Bearer {self._settings.api_token}",
                "Content-Type": "application/json",
            },
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("ZabbixClient must be used as an async context manager.")
        return self._http

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        """Execute a single Zabbix JSON-RPC request.

        Args:
            method: Zabbix API method (e.g. ``problem.get``).
            params: Method parameters dict.

        Returns:
            The ``result`` field from the JSON-RPC response.

        Raises:
            ZabbixConnectionError: On network timeouts or HTTP errors.
            ZabbixMCPError: On Zabbix API-level errors.
        """
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": _REQUEST_ID,
        }
        try:
            response = await self._client.post(self._api_url, json=payload)
            response.raise_for_status()
        except httpx.TimeoutException:
            timeout = self._settings.timeout_seconds
            raise ZabbixConnectionError(
                f"Request timed out after {timeout}s. "
                "Check ZABBIX_URL and network connectivity."
            ) from None
        except httpx.HTTPError as exc:
            raise ZabbixConnectionError(
                f"HTTP error communicating with Zabbix: {exc}"
            ) from exc

        data: dict[str, Any] = response.json()
        if "error" in data:
            raise map_api_error(data["error"])
        return data.get("result")

    async def _paginated_get(
        self,
        method: str,
        params: dict[str, Any],
        *,
        paginate: bool = True,
    ) -> list[Any]:
        """Fetch all pages of a Zabbix list API method.

        Sends repeated requests with increasing ``offset`` until the
        number of results returned is below ``page_limit``.

        Args:
            method: Zabbix API method name.
            params: Base request parameters (without ``limit``/``offset``).
            paginate: If False, send a single request with ``limit`` only
                (Zabbix 7 ``problem.get`` does not support ``offset``).

        Returns:
            Concatenated list of all result objects.
        """
        results: list[Any] = []
        offset = 0
        limit = self._settings.page_limit

        while True:
            page_params: dict[str, Any] = {**params, "limit": limit}
            if paginate:
                page_params["offset"] = offset
            page: list[Any] = await self._request(method, page_params)
            if not isinstance(page, list):
                return results
            results.extend(page)
            if len(page) < limit:
                break
            if not paginate:
                break
            offset += limit

        return results

    # ------------------------------------------------------------------ #
    # Problem / Event methods                                             #
    # ------------------------------------------------------------------ #

    async def _enrich_problems_with_trigger_hosts(
        self, problems: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Attach ``hosts`` to trigger problems (Zabbix 7+ omits ``selectHosts`` on problem.get)."""
        need: dict[str, list[dict[str, Any]]] = {}
        for p in problems:
            if p.get("hosts"):
                continue
            if int(p.get("object", 0)) != 0:
                continue
            tid = str(p.get("objectid", ""))
            if not tid:
                continue
            need.setdefault(tid, [])
        if not need:
            return problems
        triggers = await self.trigger_get(
            triggerids=list(need.keys()),
            selectHosts=["hostid", "name", "host"],
        )
        by_tid: dict[str, list[dict[str, Any]]] = {}
        for t in triggers:
            tid = str(t.get("triggerid", ""))
            hosts = t.get("hosts") or []
            if tid:
                by_tid[tid] = hosts if isinstance(hosts, list) else []
        for p in problems:
            if p.get("hosts"):
                continue
            if int(p.get("object", 0)) != 0:
                continue
            tid = str(p.get("objectid", ""))
            if tid in by_tid:
                p["hosts"] = by_tid[tid]
        return problems

    async def problem_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch active problems; host names come from trigger.get (Zabbix 7 problem.get has no selectHosts)."""
        params: dict[str, Any] = {
            "output": "extend",
            "selectAcknowledges": "count",
            "recent": True,
            **kwargs,
        }
        rows = await self._paginated_get("problem.get", params, paginate=False)
        return await self._enrich_problems_with_trigger_hosts(rows)

    async def event_acknowledge(
        self,
        event_ids: list[str],
        message: str,
        action: int = 6,
    ) -> dict[str, Any]:
        """Acknowledge one or more Zabbix events.

        Args:
            event_ids: List of event IDs to acknowledge.
            message: Human-readable acknowledgement comment.
            action: Bitmask — 2=acknowledge, 4=add message, 1=close. Default 6.

        Returns:
            Zabbix ``event.acknowledge`` result dict.
        """
        return await self._request(  # type: ignore[return-value]
            "event.acknowledge",
            {"eventids": event_ids, "message": message, "action": action},
        )

    # ------------------------------------------------------------------ #
    # Host methods                                                        #
    # ------------------------------------------------------------------ #

    async def host_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Search or retrieve hosts."""
        params: dict[str, Any] = {
            "output": ["hostid", "host", "name", "status", "available", "error"],
            "selectInterfaces": ["ip", "port", "type", "available", "error", "main"],
            "selectGroups": ["groupid", "name"],
            "selectParentTemplates": ["templateid", "name"],
            "selectTags": ["tag", "value"],
            **kwargs,
        }
        return await self._paginated_get("host.get", params)

    async def host_create(self, payload: dict[str, Any]) -> str:
        """Create a new host; returns the new ``hostid``."""
        result: dict[str, Any] = await self._request("host.create", payload)
        return str(result["hostids"][0])

    async def host_update(self, payload: dict[str, Any]) -> None:
        """Update an existing host (e.g. macros)."""
        await self._request("host.update", payload)

    async def hostgroup_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve host groups."""
        params: dict[str, Any] = {"output": ["groupid", "name"], **kwargs}
        return await self._paginated_get("hostgroup.get", params, paginate=False)

    async def template_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve templates."""
        params: dict[str, Any] = {"output": ["templateid", "name"], **kwargs}
        return await self._paginated_get("template.get", params, paginate=False)

    # ------------------------------------------------------------------ #
    # Item / Metric methods                                               #
    # ------------------------------------------------------------------ #

    async def item_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve items (metrics)."""
        params: dict[str, Any] = {
            "output": [
                "itemid", "name", "key_", "lastvalue", "lastclock",
                "units", "value_type", "description",
            ],
            "selectHosts": ["hostid", "name"],
            **kwargs,
        }
        return await self._paginated_get("item.get", params)

    async def history_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve metric history points."""
        params: dict[str, Any] = {
            "output": "extend",
            "sortfield": "clock",
            "sortorder": "ASC",
            **kwargs,
        }
        # Zabbix 7 history.get rejects ``offset``; use a single limited page.
        return await self._paginated_get("history.get", params, paginate=False)

    # ------------------------------------------------------------------ #
    # Trigger methods                                                     #
    # ------------------------------------------------------------------ #

    async def trigger_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve triggers."""
        params: dict[str, Any] = {
            "output": [
                "triggerid", "description", "expression",
                "status", "priority", "lastchange", "state",
            ],
            **kwargs,
        }
        return await self._paginated_get("trigger.get", params)

    async def trigger_create(self, payload: dict[str, Any]) -> str:
        """Create a trigger; returns the new ``triggerid``."""
        result: dict[str, Any] = await self._request("trigger.create", payload)
        return str(result["triggerids"][0])

    # ------------------------------------------------------------------ #
    # Maintenance methods                                                 #
    # ------------------------------------------------------------------ #

    async def maintenance_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve maintenance periods."""
        params: dict[str, Any] = {
            "output": ["maintenanceid", "name", "active_since", "active_till"],
            **kwargs,
        }
        return await self._paginated_get("maintenance.get", params)

    async def maintenance_create(self, payload: dict[str, Any]) -> str:
        """Create a maintenance period; returns the new ``maintenanceid``."""
        result: dict[str, Any] = await self._request("maintenance.create", payload)
        return str(result["maintenanceids"][0])

    # ------------------------------------------------------------------ #
    # Macro (usermacro) methods                                          #
    # ------------------------------------------------------------------ #

    async def usermacro_get(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve user macros defined on hosts."""
        params: dict[str, Any] = {
            "output": ["hostmacroid", "hostid", "macro", "value"],
            **kwargs,
        }
        return await self._paginated_get("usermacro.get", params)

    async def usermacro_update(self, macros: list[dict[str, Any]]) -> None:
        """Update existing user macros."""
        await self._request("usermacro.update", macros)

    async def usermacro_create(self, macros: list[dict[str, Any]]) -> None:
        """Create new user macros on hosts."""
        await self._request("usermacro.create", macros)

    # ------------------------------------------------------------------ #
    # Version / info                                                      #
    # ------------------------------------------------------------------ #

    async def api_version(self) -> str:
        """Return the Zabbix API version string (e.g. ``'7.0.0'``)."""
        result: str = await self._request("apiinfo.version", {})
        return result
