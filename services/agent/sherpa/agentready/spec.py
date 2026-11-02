"""Agent-ready task for the coding agent, its acceptance check and a live contract test suite."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from sherpa.audit import static_checks as sc
from sherpa.fixer.agent import self_check
from sherpa.fixer.tools import Workspace

CART_API_DOC = Path(__file__).with_name("cart_api.md")


def cart_api_reference() -> str:
    return CART_API_DOC.read_text(encoding="utf-8")


AGENT_READY_TASK = """Make this store ready for AI shopping agents. Add, in the store's own stack:

1. A catalog feed at `GET /catalog.json` returning `{ "items": [...] }` built from the store's real product data, \
each item with id, title, description, price {currency_code, value}, availability ("in_stock" or "preorder"), \
image_url (absolute URL), url and variants (may be empty). Include extra product facts an agent needs (for example \
serves / lead time) as additional fields.
2. The PayPal Cart API v1 merchant endpoints exactly as specified in the reference below: `POST /merchant-cart`, \
`GET /merchant-cart/{id}`, `PUT /merchant-cart/{id}` (full replace) and `POST /merchant-cart/{id}/checkout`, at those \
exact paths (not under /api). Keep carts in an in-memory Map keyed by id. Price items only from the server-side catalog. \
Validate every cart and return validation_issues in the documented shape, for example an unknown item_id \
(INVENTORY_ISSUE), a missing shipping_address (SHIPPING_ERROR / MISSING_FIELD) and, for products that must be ordered \
ahead, a missing or too-early DELIVERY_DATE_PREFERENCE checkout field (DATA_ERROR / MISSING_FIELD with \
resolution_options [{"action": "PROVIDE_MISSING_FIELD"}]).
3. Wire carts to PayPal Orders v2 on the sandbox: when a cart has items, create (or, on PUT, recreate) a PayPal order \
for the server-computed total with `payment_source.paypal.experience_context` containing return_url \
(`<origin>/thank-you`), cancel_url (`<origin>/cart`) and user_action "PAY_NOW"; put the order id in \
`payment_method.token`. On checkout: if validation_status is INVALID return 200 with the cart and its issues; \
otherwise fetch the PayPal order, and if it is APPROVED capture it, verify the captured amount equals the cart total, \
set status COMPLETED and add payment_confirmation {merchant_order_number, order_review_page}; if it is not yet \
approved return 422 with name "UNPROCESSABLE_ENTITY" and a message telling the caller the buyer must approve the \
PayPal payment first. Errors use {name, message, debug_id}.
4. A contract test suite for these endpoints that runs with `npm test` without network access (mock the PayPal \
calls), covering create, get, 404, update (full replace), validation issues and checkout before approval.
Keep all existing checkout fixes working. Do not add dependencies unless unavoidable; Node's built-in test runner \
(`node --test`) is fine. Run run_build (which also runs npm test) before finish.

PayPal Cart API v1 reference:
"""


def agent_ready_task() -> str:
    return AGENT_READY_TASK + cart_api_reference()


def agent_ready_check(ws: Workspace) -> list[str]:
    files = sc.read_source_tree(ws.root)
    corpus = "\n".join(files.values())
    problems = []
    if "catalog.json" not in corpus:
        problems.append("No /catalog.json route found.")
    if "merchant-cart" not in corpus:
        problems.append("No /merchant-cart routes found.")
    for needle in ("validation_status", "validation_issues", "payment_method", "experience_context"):
        if needle not in corpus:
            problems.append(f"`{needle}` is missing from the Cart API implementation.")
    if not re.search(r"checkout", corpus):
        problems.append("No /merchant-cart/{id}/checkout handler found.")
    pkg = files.get("package.json", "")
    if '"test"' not in pkg:
        problems.append("Add an npm test script that runs the Cart API contract tests.")
    problems += self_check(ws)
    return problems


SAMPLE_ADDRESS = {
    "address_line_1": "500 Market St",
    "admin_area_2": "San Francisco",
    "admin_area_1": "CA",
    "postal_code": "94105",
    "country_code": "US",
}


async def run_contract_tests(
    base_url: str,
    item_id: str,
    extra_fields: list[dict] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    on_result: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
) -> list[dict[str, Any]]:
    """Live contract checks against a deployed store. Never approves or captures a payment."""
    base = base_url.rstrip("/")
    results: list[dict[str, Any]] = []

    async def record(method: str, path: str, ok: bool, detail: str = "") -> None:
        results.append({"method": method, "path": path, "ok": bool(ok), "detail": detail[:200]})
        if on_result:
            await on_result(results[-1])  # stream each check to the console as it completes

    async with httpx.AsyncClient(timeout=30, transport=transport) as c:
        r = await c.get(f"{base}/catalog.json")
        feed_ok = (
            r.status_code == 200 and isinstance(r.json().get("items"), list) and len(r.json()["items"]) > 0
        )
        await record("GET", "/catalog.json", feed_ok, f"{r.status_code}")

        body = {"items": [{"item_id": item_id, "quantity": 1}], "payment_method": {"type": "paypal"}}
        r = await c.post(f"{base}/merchant-cart", json=body)
        cart = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        created = r.status_code in (200, 201) and bool(cart.get("id")) and "validation_status" in cart
        await record("POST", "/merchant-cart", created, f"{r.status_code} {cart.get('validation_status')}")
        if not created:
            return results
        cid = cart["id"]
        issues_ok = cart.get("validation_status") == "INVALID" and all(
            {"code", "type", "message"} <= set(i) for i in cart.get("validation_issues", [])
        )
        await record("POST", "/merchant-cart (validation issues)", issues_ok, "missing address is reported")

        r = await c.get(f"{base}/merchant-cart/{cid}")
        await record(
            "GET",
            "/merchant-cart/{id}",
            r.status_code == 200 and r.json().get("id") == cid,
            f"{r.status_code}",
        )
        r = await c.get(f"{base}/merchant-cart/does-not-exist")
        not_found = r.status_code == 404 and r.json().get("name") == "CART_NOT_FOUND"
        await record("GET", "/merchant-cart/{id} (404)", not_found, f"{r.status_code}")

        full = {**body, "shipping_address": SAMPLE_ADDRESS, "checkout_fields": extra_fields or []}
        r = await c.put(f"{base}/merchant-cart/{cid}", json=full)
        updated = r.json() if r.status_code == 200 else {}
        token = (updated.get("payment_method") or {}).get("token")
        put_ok = updated.get("validation_status") == "VALID" and bool(token)
        await record(
            "PUT", "/merchant-cart/{id}", put_ok, f"{r.status_code} {updated.get('validation_status')}"
        )

        total = ((updated.get("totals") or {}).get("total") or {}).get("value")
        await record("PUT", "/merchant-cart/{id} (server pricing)", bool(total), f"total {total}")

        r = await c.post(f"{base}/merchant-cart/{cid}/checkout", json=full)
        early = r.status_code == 422 or (r.status_code == 200 and r.json().get("status") != "COMPLETED")
        await record("POST", "/merchant-cart/{id}/checkout (before approval)", early, f"{r.status_code}")
    return results
