"""The protocol over HTTP, not just the handlers underneath it.

The tool tests call the server in process. These speak the wire: a real
JSON-RPC initialize, then tools/list, then tools/call, over the Streamable
HTTP transport. Every bug that has ever made an MCP server unusable lives
here rather than in the handlers — a wrong Accept header, a session the
gateway drops, a transport that refuses a Host it was never told about.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from mcp.server.transport_security import TransportSecuritySettings

HEADERS = {
    # Both are required: the transport picks between a JSON body and an SSE
    # stream per call, so a client must say it can read either.
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def rpc(method: str, params: dict | None = None, ident: int = 1) -> dict:
    body = {"jsonrpc": "2.0", "id": ident, "method": method}
    if params is not None:
        body["params"] = params
    return body


@asynccontextmanager
async def connected(server):
    """A client talking to the server over a real ASGI round trip.

    Deliberately not a fixture. The transport holds a task group for the life
    of the app, and anyio refuses to close one in a different task than opened
    it — which is exactly what a yielding fixture does when pytest runs the
    finaliser. Entering and leaving inside the test keeps both in one task.
    """
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
            yield client


async def test_healthz_is_not_the_protocol(server) -> None:
    async with connected(server) as client:
        response = await client.get("/healthz")
    assert response.status_code == 200


async def test_initialize_announces_the_server_and_its_tools(server) -> None:
    async with connected(server) as client:
        response = await client.post(
            "/mcp",
            json=rpc(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "poshra-tests", "version": "0"},
                },
            ),
            headers=HEADERS,
        )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["serverInfo"]["name"] == "poshra-storefront"
    assert "tools" in result["capabilities"]
    # Shipped with the server, so an agent learns how to shop Poshra without
    # anything being written into the agent.
    assert "nakshi kantha" in result["instructions"]


async def test_tools_list_over_the_wire(server) -> None:
    async with connected(server) as client:
        response = await client.post("/mcp", json=rpc("tools/list", ident=2), headers=HEADERS)
    assert response.status_code == 200
    names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert sorted(names) == ["get_product", "list_crafts", "search_products"]


async def test_tools_call_over_the_wire(server) -> None:
    async with connected(server) as client:
        response = await client.post(
            "/mcp",
            json=rpc("tools/call", {"name": "search_products", "arguments": {"query": "saree"}}, 3),
            headers=HEADERS,
        )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["pieces"][0]["slug"] == "indigo-jamdani-saree"


async def test_a_failing_tool_is_a_result_not_a_transport_error(server) -> None:
    """isError, not HTTP 500: the model is meant to read it and correct itself."""
    async with connected(server) as client:
        response = await client.post(
            "/mcp",
            json=rpc("tools/call", {"name": "get_product", "arguments": {"slug": "nope"}}, 4),
            headers=HEADERS,
        )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert "no piece with the slug" in result["content"][0]["text"]
