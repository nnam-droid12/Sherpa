"""An MCP endpoint for an agent-ready store, so any MCP-capable AI assistant can shop it.

PayPal documents its own MCP server for merchants managing their PayPal account, and the ACP/UCP "Agent Ready"
paths for approved merchants. It does not document a merchant-side MCP server for a store's own catalog, so this
is Sherpa's bridge: every tool is a thin call to the store's catalog feed and its PayPal Cart API endpoints, and
payment approval always goes to the human on PayPal's own page.

Transport: MCP Streamable HTTP (spec 2025-06-18), answering each POST with a single application/json response.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from sherpa.paypal.client import PayPalClient

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2025-11-25", "2026-07-28")
LATEST = "2025-06-18"
APPROVE_URL = "https://www.sandbox.paypal.com/checkoutnow?token={}"

_item = {
    "type": "object",
    "properties": {"item_id": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1}},
    "required": ["item_id", "quantity"],
}
_cart = {
    "items": {"type": "array", "items": _item},
    "shipping_address": {
        "type": "object",
        "description": "address_line_1, admin_area_2 (city), admin_area_1 (state), postal_code, country_code",
    },
    "checkout_fields": {
        "type": "array",
        "description": "Answers to the store's validation questions, e.g. a delivery date.",
        "items": {"type": "object", "properties": {"type": {"type": "string"}, "value": {"type": "string"}}},
    },
    "customer": {"type": "object", "description": "email_address and name {given_name, surname}"},
}
_cart_id = {"cart_id": {"type": "string"}}

TOOLS = [
    {
        "name": "search_products",
        "title": "Search products",
        "description": "Search the store's catalog. Returns ids, titles, prices and availability.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "max_price": {"type": "number"}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "create_cart",
        "title": "Create a cart",
        "description": "Create a cart paid with PayPal. The response lists validation issues the shopper must "
        "resolve (such as a shipping address or delivery date) before checkout.",
        "inputSchema": {"type": "object", "properties": _cart, "required": ["items"]},
    },
    {
        "name": "get_cart",
        "title": "Get a cart",
        "description": "Get a cart's items, totals and validation status.",
        "inputSchema": {"type": "object", "properties": _cart_id, "required": ["cart_id"]},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "update_cart",
        "title": "Update a cart",
        "description": "Replace the whole cart: send every field again, including the answers to validation issues.",
        "inputSchema": {
            "type": "object",
            "properties": {**_cart_id, **_cart},
            "required": ["cart_id", "items"],
        },
    },
    {
        "name": "get_payment_link",
        "title": "Get the PayPal approval link",
        "description": "Returns the PayPal page where the shopper approves the payment themselves. Give this link "
        "to the shopper; never approve a payment on their behalf.",
        "inputSchema": {"type": "object", "properties": _cart_id, "required": ["cart_id"]},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "checkout_cart",
        "title": "Complete checkout",
        "description": "Complete the purchase after the shopper approved the PayPal payment.",
        "inputSchema": {"type": "object", "properties": _cart_id, "required": ["cart_id"]},
    },
    {
        "name": "get_order_status",
        "title": "PayPal order status",
        "description": "Check a PayPal order's status with PayPal's Orders API.",
        "inputSchema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
        "annotations": {"readOnlyHint": True},
    },
]
TOOL_NAMES = {t["name"] for t in TOOLS}


class ToolError(Exception):
    """A tool ran but failed; reported to the assistant with isError, per the MCP spec."""


def _result(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "content": [{"type": "text", "text": json.dumps(data, default=str)}],
        "isError": is_error,
    }
    if isinstance(data, dict) and not is_error:
        out["structuredContent"] = data
    return out


class StoreTools:
    def __init__(self, store_url: str, http: httpx.AsyncClient, paypal: PayPalClient | None = None) -> None:
        self.base = store_url.rstrip("/")
        self.http = http
        self.paypal = paypal or PayPalClient()

    async def _cart(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        r = await self.http.request(method, f"{self.base}{path}", json=body)
        try:
            data = r.json()
        except ValueError:
            raise ToolError(f"The store returned HTTP {r.status_code} without JSON.") from None
        if r.status_code >= 400 and not (isinstance(data, dict) and "validation_status" in data):
            raise ToolError(f"The store returned HTTP {r.status_code}: {json.dumps(data)[:300]}")
        return data if isinstance(data, dict) else {"data": data}

    @staticmethod
    def _body(args: dict[str, Any]) -> dict[str, Any]:
        body = {k: v for k, v in args.items() if k != "cart_id" and v is not None}
        body.setdefault("payment_method", {"type": "paypal"})
        return body

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "search_products":
            feed = (await self.http.get(f"{self.base}/catalog.json")).json().get("items", [])
            words = str(args.get("query") or "").lower().split()
            cap = args.get("max_price")

            def price(i: dict) -> float:
                p = i.get("price")
                return float((p.get("value") if isinstance(p, dict) else p) or 0)

            hits = [
                i
                for i in feed
                if (not words or any(w in json.dumps(i).lower() for w in words))
                and (cap is None or price(i) <= float(cap))
            ]
            return {"products": hits[:10], "total": len(hits)}
        if name == "create_cart":
            return await self._cart("POST", "/merchant-cart", self._body(args))
        if name == "get_cart":
            return await self._cart("GET", f"/merchant-cart/{args['cart_id']}")
        if name == "update_cart":
            return await self._cart("PUT", f"/merchant-cart/{args['cart_id']}", self._body(args))
        if name == "get_payment_link":
            cart = await self._cart("GET", f"/merchant-cart/{args['cart_id']}")
            token = (cart.get("payment_method") or {}).get("token")
            if not token:
                raise ToolError("The cart has no PayPal order yet: resolve its validation issues first.")
            return {"order_id": token, "approve_url": APPROVE_URL.format(token)}
        if name == "checkout_cart":
            cart = await self._cart("GET", f"/merchant-cart/{args['cart_id']}")
            body = {
                k: cart[k]
                for k in ("shipping_address", "checkout_fields", "customer", "payment_method")
                if k in cart
            }
            body["items"] = [
                {"item_id": i["item_id"], "quantity": i["quantity"]} for i in cart.get("items", [])
            ]
            return await self._cart("POST", f"/merchant-cart/{args['cart_id']}/checkout", body)
        if name == "get_order_status":
            order = await self.paypal.get_order(args["order_id"])
            if not order:
                raise ToolError("PayPal has no order with that id in the sandbox.")
            return {"order_id": order.get("id"), "status": order.get("status")}
        raise KeyError(name)


ERROR_PARSE = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


async def handle(message: Any, tools: StoreTools, store_name: str) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Returns the response, or None for notifications (HTTP 202)."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "method" not in message:
        return _error(None, -32600, "Invalid Request")
    msg_id, method, params = message.get("id"), message["method"], message.get("params") or {}
    if "id" not in message:
        return None  # notifications such as notifications/initialized need no answer
    if method == "initialize":
        asked = params.get("protocolVersion")
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": asked if asked in SUPPORTED_VERSIONS else LATEST,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "sherpa-store",
                    "title": f"{store_name} (via Sherpa)",
                    "version": "1.0.0",
                },
                "instructions": "Shop this store for the user. Payments are approved by the user on PayPal's own "
                "page (get_payment_link); never approve on their behalf. PayPal sandbox only.",
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in TOOL_NAMES:
            return _error(msg_id, -32602, f"Unknown tool: {name}")
        missing = [
            k
            for k in next(t for t in TOOLS if t["name"] == name)["inputSchema"].get("required", [])
            if k not in args
        ]
        if missing:
            return _error(msg_id, -32602, f"Missing arguments: {', '.join(missing)}")
        try:
            data = await tools.call(name, args)
        except (ToolError, httpx.HTTPError, ValueError) as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "result": _result({"error": str(exc)}, is_error=True)}
        return {"jsonrpc": "2.0", "id": msg_id, "result": _result(data)}
    return _error(msg_id, -32601, f"Method not found: {method}")
