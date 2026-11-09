import json

import httpx
import pytest
import respx

from sherpa.agentready import mcp

STORE = "https://pr-1.store.example"
FEED = {
    "items": [
        {
            "id": "tent",
            "title": "Ridgeline 2P Alpine Tent",
            "price": {"value": "349.00", "currency_code": "USD"},
        },
        {
            "id": "stove",
            "title": "Kindle Canister Stove Kit",
            "price": {"value": "89.00", "currency_code": "USD"},
        },
    ]
}


class FakePayPal:
    async def get_order(self, order_id):
        return {"id": order_id, "status": "APPROVED"} if order_id == "ORDER1" else None


async def call(message, tools=None):
    async with httpx.AsyncClient() as http:
        return await mcp.handle(message, tools or mcp.StoreTools(STORE, http, FakePayPal()), "ember-oak")


def rpc(method, params=None, msg_id=1):
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}


@pytest.mark.asyncio
async def test_initialize_negotiates_version_and_advertises_tools():
    reply = await call(
        rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {}})
    )
    result = reply["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"]["name"] == "sherpa-store"
    old = await call(rpc("initialize", {"protocolVersion": "2024-01-01"}))
    assert old["result"]["protocolVersion"] == mcp.LATEST


@pytest.mark.asyncio
async def test_notifications_get_no_reply_and_bad_requests_are_rejected():
    assert await call({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert (await call({"id": 1, "method": "ping"}))["error"]["code"] == -32600
    assert (await call(rpc("resources/list")))["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_tools_list_matches_the_spec_shape():
    tools = (await call(rpc("tools/list")))["result"]["tools"]
    names = [t["name"] for t in tools]
    assert names == [
        "search_products",
        "create_cart",
        "get_cart",
        "update_cart",
        "get_payment_link",
        "checkout_cart",
        "get_order_status",
    ]
    assert all(t["inputSchema"]["type"] == "object" and t["description"] for t in tools)


@pytest.mark.asyncio
async def test_unknown_tool_and_missing_arguments_are_protocol_errors():
    assert (await call(rpc("tools/call", {"name": "steal"})))["error"]["code"] == -32602
    reply = await call(rpc("tools/call", {"name": "create_cart", "arguments": {}}))
    assert reply["error"]["code"] == -32602 and "items" in reply["error"]["message"]


@pytest.mark.asyncio
async def test_search_filters_by_words_and_price():
    with respx.mock() as mock:
        mock.get(f"{STORE}/catalog.json").respond(200, json=FEED)
        reply = await call(
            rpc("tools/call", {"name": "search_products", "arguments": {"query": "tent", "max_price": 400}})
        )
    result = reply["result"]
    assert result["isError"] is False
    assert [p["id"] for p in result["structuredContent"]["products"]] == ["tent"]
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]


@pytest.mark.asyncio
async def test_create_cart_pays_with_paypal_and_keeps_validation_issues():
    cart = {
        "id": "C1",
        "validation_status": "INVALID",
        "validation_issues": [{"code": "MISSING_SHIPPING_ADDRESS"}],
    }
    with respx.mock() as mock:
        route = mock.post(f"{STORE}/merchant-cart").respond(201, json=cart)
        reply = await call(
            rpc(
                "tools/call",
                {"name": "create_cart", "arguments": {"items": [{"item_id": "tent", "quantity": 1}]}},
            )
        )
    sent = json.loads(route.calls.last.request.content)
    assert sent["payment_method"] == {"type": "paypal"}
    assert reply["result"]["structuredContent"]["validation_status"] == "INVALID"


@pytest.mark.asyncio
async def test_payment_link_goes_to_paypal_for_the_human_to_approve():
    with respx.mock() as mock:
        mock.get(f"{STORE}/merchant-cart/C1").respond(
            200, json={"id": "C1", "payment_method": {"token": "ORDER1"}}
        )
        reply = await call(rpc("tools/call", {"name": "get_payment_link", "arguments": {"cart_id": "C1"}}))
    assert reply["result"]["structuredContent"] == {
        "order_id": "ORDER1",
        "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER1",
    }


@pytest.mark.asyncio
async def test_checkout_resends_the_stored_cart():
    stored = {
        "id": "C1",
        "items": [{"item_id": "tent", "quantity": 1, "price": {"value": "349.00"}}],
        "shipping_address": {"postal_code": "94105"},
        "payment_method": {"type": "paypal", "token": "ORDER1"},
    }
    with respx.mock() as mock:
        mock.get(f"{STORE}/merchant-cart/C1").respond(200, json=stored)
        route = mock.post(f"{STORE}/merchant-cart/C1/checkout").respond(
            200, json={"id": "C1", "status": "COMPLETED"}
        )
        reply = await call(rpc("tools/call", {"name": "checkout_cart", "arguments": {"cart_id": "C1"}}))
    sent = json.loads(route.calls.last.request.content)
    assert sent["items"] == [{"item_id": "tent", "quantity": 1}]
    assert sent["payment_method"]["token"] == "ORDER1"
    assert reply["result"]["structuredContent"]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_tool_failures_are_reported_with_is_error():
    with respx.mock() as mock:
        mock.get(f"{STORE}/merchant-cart/C9").respond(
            200, json={"id": "C9", "payment_method": {"type": "paypal"}}
        )
        no_token = await call(rpc("tools/call", {"name": "get_payment_link", "arguments": {"cart_id": "C9"}}))
        mock.get(f"{STORE}/merchant-cart/BAD").respond(500, text="boom")
        broken = await call(rpc("tools/call", {"name": "get_cart", "arguments": {"cart_id": "BAD"}}))
    missing = await call(rpc("tools/call", {"name": "get_order_status", "arguments": {"order_id": "NOPE"}}))
    for reply in (no_token, broken, missing):
        assert reply["result"]["isError"] is True and "structuredContent" not in reply["result"]


class _Runs:
    def __init__(self, run):
        self.run = run

    async def get_run(self, run_id):
        return self.run


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient

    from sherpa import main

    def use(run):
        monkeypatch.setattr(main, "get_store", lambda: _Runs(run))
        return TestClient(main.app)

    return use


READY = {"id": "r1", "store_url": STORE, "demo_store": "ember-oak", "agent_ready": {"preview_url": STORE}}


def test_endpoint_answers_json_and_202_for_notifications(api):
    client = api(READY)
    res = client.post("/api/mcp/r1", json=rpc("tools/list"))
    assert res.status_code == 200 and res.headers["content-type"].startswith("application/json")
    assert len(res.json()["result"]["tools"]) == 7
    note = client.post("/api/mcp/r1", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.status_code == 202 and note.content == b""
    assert client.get("/api/mcp/r1").status_code == 405


def test_endpoint_rejects_foreign_origins_and_unready_runs(api):
    assert (
        api(READY)
        .post("/api/mcp/r1", json=rpc("ping"), headers={"Origin": "https://evil.example"})
        .status_code
        == 403
    )
    assert api({"id": "r2", "store_url": STORE}).post("/api/mcp/r2", json=rpc("ping")).status_code == 404
    bad = api(READY).post("/api/mcp/r1", content=b"{not json", headers={"content-type": "application/json"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == -32700
