import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.api.endpoints.mcp_proxy import (
    STREAM_BRIDGE_READY_DELAY,
    StreamBridgeSession,
    _send_via_stream_bridge,
)


def _make_request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode("utf-8"), value.encode("utf-8"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/mcp",
            "query_string": b"",
            "headers": raw_headers,
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
            "http_version": "1.1",
        }
    )


@pytest.mark.asyncio
async def test_send_via_stream_bridge_returns_session_header(monkeypatch):
    request = _make_request()
    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
    }

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=202, text="", headers={}))

    session = StreamBridgeSession(
        public_session_id="public-session",
        backend_session_id="backend-session",
        client=mock_client,
        stream_context=MagicMock(),
        stream_response=MagicMock(),
        response_queue=asyncio.Queue(),
    )
    await session.response_queue.put({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}})

    async def mock_get_or_create(_request, *, create):
        assert create is True
        return session

    monkeypatch.setattr(
        "app.api.endpoints.mcp_proxy._get_or_create_stream_bridge_session",
        mock_get_or_create,
    )

    response = await _send_via_stream_bridge(request, rpc_request)

    assert response.status_code == 200
    assert response.headers["mcp-session-id"] == "public-session"
    assert json.loads(response.body)["id"] == 1


@pytest.mark.asyncio
async def test_send_via_stream_bridge_rejects_unknown_session(monkeypatch):
    request = _make_request({"Mcp-Session-Id": "missing-session"})
    rpc_request = {"jsonrpc": "2.0", "id": 9, "method": "tools/list", "params": {}}

    async def mock_get_or_create(_request, *, create):
        assert create is False
        return None

    monkeypatch.setattr(
        "app.api.endpoints.mcp_proxy._get_or_create_stream_bridge_session",
        mock_get_or_create,
    )

    response = await _send_via_stream_bridge(request, rpc_request)

    assert response.status_code == 400
    assert json.loads(response.body)["error"]["message"] == "Unknown or expired MCP session"


@pytest.mark.asyncio
async def test_send_via_stream_bridge_waits_for_new_backend_session(monkeypatch):
    request = _make_request()
    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
    }

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=202, text="", headers={}))

    session = StreamBridgeSession(
        public_session_id="public-session",
        backend_session_id="backend-session",
        client=mock_client,
        stream_context=MagicMock(),
        stream_response=MagicMock(),
        response_queue=asyncio.Queue(),
        created_at=time.monotonic(),
    )
    await session.response_queue.put({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}})

    sleep_calls: list[float] = []

    async def mock_sleep(delay: float):
        sleep_calls.append(delay)

    async def mock_get_or_create(_request, *, create):
        assert create is True
        return session

    monkeypatch.setattr(
        "app.api.endpoints.mcp_proxy._get_or_create_stream_bridge_session",
        mock_get_or_create,
    )
    monkeypatch.setattr("app.api.endpoints.mcp_proxy.asyncio.sleep", mock_sleep)

    response = await _send_via_stream_bridge(request, rpc_request)

    assert response.status_code == 200
    assert sleep_calls
    assert sleep_calls[0] == pytest.approx(STREAM_BRIDGE_READY_DELAY, abs=0.05)


@pytest.mark.asyncio
async def test_send_via_stream_bridge_skips_wait_for_existing_backend_session(monkeypatch):
    request = _make_request({"Mcp-Session-Id": "public-session"})
    rpc_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=202, text="", headers={}))

    session = StreamBridgeSession(
        public_session_id="public-session",
        backend_session_id="backend-session",
        client=mock_client,
        stream_context=MagicMock(),
        stream_response=MagicMock(),
        response_queue=asyncio.Queue(),
        created_at=time.monotonic() - (STREAM_BRIDGE_READY_DELAY + 1.0),
    )
    await session.response_queue.put({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}})

    sleep_calls: list[float] = []

    async def mock_sleep(delay: float):
        sleep_calls.append(delay)

    async def mock_get_or_create(_request, *, create):
        assert create is False
        return session

    monkeypatch.setattr(
        "app.api.endpoints.mcp_proxy._get_or_create_stream_bridge_session",
        mock_get_or_create,
    )
    monkeypatch.setattr("app.api.endpoints.mcp_proxy.asyncio.sleep", mock_sleep)

    response = await _send_via_stream_bridge(request, rpc_request)

    assert response.status_code == 200
    assert sleep_calls == []
