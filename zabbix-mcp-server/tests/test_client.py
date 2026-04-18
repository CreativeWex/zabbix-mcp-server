"""Tests for ZabbixClient — TC-008 through TC-013."""

from __future__ import annotations

import json

import pytest
import httpx
import respx

from zabbix_mcp.config import Settings
from zabbix_mcp.zabbix.client import ZabbixClient
from zabbix_mcp.zabbix.errors import (
    ZabbixAPIError,
    ZabbixAuthError,
    ZabbixConnectionError,
    ZabbixNotFoundError,
)


def _rpc_ok(result: object) -> dict:
    return {"jsonrpc": "2.0", "result": result, "id": 1}


def _rpc_error(code: int, message: str, data: str = "") -> dict:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message, "data": data}, "id": 1}


@pytest.fixture
def settings() -> Settings:
    return Settings(url="https://zabbix.test", api_token="valid_token")  # type: ignore[call-arg]


# ------------------------------------------------------------------ TC-008

@pytest.mark.asyncio
async def test_bearer_token_in_request_header(settings: Settings) -> None:
    """TC-008: Client sends Authorization: Bearer <token> on every request."""
    with respx.mock(base_url="https://zabbix.test") as mock:
        mock.post("/api_jsonrpc.php").mock(
            return_value=httpx.Response(200, json=_rpc_ok([]))
        )
        async with ZabbixClient(settings) as client:
            await client.problem_get()

        request = mock.calls[0].request
        assert request.headers["Authorization"] == "Bearer valid_token"


# ------------------------------------------------------------------ TC-009

@pytest.mark.asyncio
async def test_auth_failed_maps_to_readable_error(settings: Settings) -> None:
    """TC-009: AUTH_FAILED error code maps to ZabbixAuthError with readable message."""
    with respx.mock(base_url="https://zabbix.test") as mock:
        mock.post("/api_jsonrpc.php").mock(
            return_value=httpx.Response(
                200,
                json=_rpc_error(-32602, "Not authorised.", ""),
            )
        )
        async with ZabbixClient(settings) as client:
            with pytest.raises(ZabbixAuthError) as exc_info:
                await client.problem_get()

    assert "ZABBIX_API_TOKEN" in exc_info.value.message
    assert "Not authorised" not in exc_info.value.message  # raw message hidden


# ------------------------------------------------------------------ TC-010

@pytest.mark.asyncio
async def test_object_not_found_maps_to_readable_error(settings: Settings) -> None:
    """TC-010: OBJECT_NOT_FOUND error maps to ZabbixNotFoundError."""
    with respx.mock(base_url="https://zabbix.test") as mock:
        mock.post("/api_jsonrpc.php").mock(
            return_value=httpx.Response(
                200,
                json=_rpc_error(-32500, "Application error.", "No triggers found."),
            )
        )
        async with ZabbixClient(settings) as client:
            with pytest.raises(ZabbixNotFoundError) as exc_info:
                await client.trigger_get()

    assert "not found" in exc_info.value.message.lower()


# ------------------------------------------------------------------ TC-011

@pytest.mark.asyncio
async def test_network_timeout_maps_to_readable_error(settings: Settings) -> None:
    """TC-011: Network timeout raises ZabbixConnectionError with readable message."""
    with respx.mock(base_url="https://zabbix.test") as mock:
        mock.post("/api_jsonrpc.php").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        async with ZabbixClient(settings) as client:
            with pytest.raises(ZabbixConnectionError) as exc_info:
                await client.problem_get()

    assert "timed out" in exc_info.value.message.lower()
    assert "10s" in exc_info.value.message  # timeout value included


# ------------------------------------------------------------------ TC-012

@pytest.mark.asyncio
async def test_pagination_triggers_second_request_when_full_page(
    settings: Settings,
) -> None:
    """TC-012: Client fetches next page when result count equals page_limit."""
    page1 = [{"hostid": str(i), "host": f"h{i}", "name": f"H{i}"} for i in range(100)]
    page2 = [
        {"hostid": str(i + 100), "host": f"h{i + 100}", "name": f"H{i + 100}"}
        for i in range(50)
    ]

    call_count = 0

    with respx.mock(base_url="https://zabbix.test") as mock:
        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            body = json.loads(request.content.decode())
            assert body["method"] == "host.get"
            call_count += 1
            return httpx.Response(200, json=_rpc_ok(page1 if call_count == 1 else page2))

        mock.post("/api_jsonrpc.php").mock(side_effect=_handler)

        async with ZabbixClient(settings) as client:
            result = await client.host_get()

    assert len(result) == 150
    assert call_count == 2


# ------------------------------------------------------------------ TC-013

@pytest.mark.asyncio
async def test_no_pagination_when_below_page_limit(settings: Settings) -> None:
    """TC-013: Exactly one request when result count is below page_limit."""
    page = [{"hostid": str(i), "host": f"h{i}", "name": f"H{i}"} for i in range(99)]

    call_count = 0

    with respx.mock(base_url="https://zabbix.test") as mock:
        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            body = json.loads(request.content.decode())
            assert body["method"] == "host.get"
            call_count += 1
            return httpx.Response(200, json=_rpc_ok(page))

        mock.post("/api_jsonrpc.php").mock(side_effect=_handler)

        async with ZabbixClient(settings) as client:
            result = await client.host_get()

    assert len(result) == 99
    assert call_count == 1


# ------------------------------------------------------------------ extra

@pytest.mark.asyncio
async def test_http_error_raises_connection_error(settings: Settings) -> None:
    """Non-2xx HTTP response raises ZabbixConnectionError."""
    with respx.mock(base_url="https://zabbix.test") as mock:
        mock.post("/api_jsonrpc.php").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        async with ZabbixClient(settings) as client:
            with pytest.raises(ZabbixConnectionError):
                await client.problem_get()


@pytest.mark.asyncio
async def test_request_without_context_manager_raises() -> None:
    """Calling _request without entering context manager raises RuntimeError."""
    settings = Settings(url="https://zabbix.test", api_token="tok")  # type: ignore[call-arg]
    client = ZabbixClient(settings)
    with pytest.raises(RuntimeError, match="context manager"):
        await client.problem_get()


@pytest.mark.asyncio
async def test_api_version_returns_string(settings: Settings) -> None:
    """api_version() returns the Zabbix version string."""
    with respx.mock(base_url="https://zabbix.test") as mock:
        mock.post("/api_jsonrpc.php").mock(
            return_value=httpx.Response(200, json=_rpc_ok("7.0.0"))
        )
        async with ZabbixClient(settings) as client:
            version = await client.api_version()

    assert version == "7.0.0"


@pytest.mark.asyncio
async def test_problem_get_enriches_hosts_via_trigger_get(settings: Settings) -> None:
    """Zabbix 7: problem.get has no selectHosts; client merges hosts from trigger.get."""
    problem_row = {
        "eventid": "7001",
        "object": "0",
        "objectid": "15112",
        "name": "Test problem",
        "severity": "3",
        "clock": "1713350400",
        "acknowledges": "0",
    }
    trigger_row = {
        "triggerid": "15112",
        "hosts": [{"hostid": "10084", "name": "Zabbix server", "host": "Zabbix server"}],
    }

    def _route(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        if body["method"] == "problem.get":
            return httpx.Response(200, json=_rpc_ok([problem_row]))
        if body["method"] == "trigger.get":
            return httpx.Response(200, json=_rpc_ok([trigger_row]))
        return httpx.Response(200, json=_rpc_ok([]))

    with respx.mock(base_url="https://zabbix.test") as mock:
        mock.post("/api_jsonrpc.php").mock(side_effect=_route)
        async with ZabbixClient(settings) as client:
            out = await client.problem_get()

    assert len(out) == 1
    assert out[0]["hosts"] == trigger_row["hosts"]
