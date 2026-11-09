"""Interoperability check: drive a store's Sherpa MCP endpoint with the official MCP Python SDK client.

It does what an AI assistant would: connect, list the tools, search the catalog, build a PayPal cart with a shipping
address and fetch the PayPal approval link for the shopper. It stops before approval, which is the shopper's job.

Run: python scripts/mcp_interop.py https://<console>/api/agent/mcp/<run_id>
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ADDRESS = {
    "address_line_1": "500 Market St",
    "admin_area_2": "San Francisco",
    "admin_area_1": "CA",
    "postal_code": "94105",
    "country_code": "US",
}
CUSTOMER = {"email_address": "shopper@example.com", "name": {"given_name": "Alex", "surname": "Rivera"}}


def data(result) -> dict:
    if result.is_error:
        raise RuntimeError(result.content[0].text)
    return result.structured_content or json.loads(result.content[0].text)


async def main(url: str) -> None:
    async with streamable_http_client(url) as (read, write, *_), ClientSession(read, write) as session:
        init = await session.initialize()
        print(f"connected: {init.server_info.title} · protocol {init.protocol_version}")
        tools = (await session.list_tools()).tools
        print(f"tools ({len(tools)}): {', '.join(t.name for t in tools)}")

        found = data(await session.call_tool("search_products", {}))
        product = next(
            p for p in found["products"] if p.get("availability", "in_stock").lower() != "out_of_stock"
        )
        print(
            f"search_products: {found['total']} products, picked {product['title']} (${product['price']['value']})"
        )

        cart = data(
            await session.call_tool(
                "create_cart",
                {
                    "items": [{"item_id": product["id"], "quantity": 1}],
                    "shipping_address": ADDRESS,
                    "customer": CUSTOMER,
                },
            )
        )
        print(
            f"create_cart: {cart['id']} · {cart.get('validation_status')} · issues {cart.get('validation_issues')}"
        )

        link = data(await session.call_tool("get_payment_link", {"cart_id": cart["id"]}))
        print(f"get_payment_link: PayPal order {link['order_id']} -> {link['approve_url']}")
        status = data(await session.call_tool("get_order_status", {"order_id": link["order_id"]}))
        print(f"get_order_status: {status['status']} (waiting for the shopper to approve on PayPal)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
