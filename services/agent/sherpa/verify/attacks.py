"""Attack replay: prove the security fixes by trying the attacks, before and after the pull request.

Two attacks a real fraudster would try against a PayPal checkout:

- price tampering: ask the store's order endpoint to create a PayPal order for $1.00 instead of the
  real price, then read the order back from PayPal's Orders API to see what amount was really set;
- forged webhook: send a fake PAYMENT.CAPTURE.COMPLETED notification with made-up PayPal signature
  headers and see whether the store accepts it.

Only sandbox stores are attacked: Sherpa's own preview revisions (deployed with sandbox credentials)
and the demo stores. Orders created by the price attack are never captured, so nothing is charged.
"""

from __future__ import annotations

import re
import uuid
from typing import Any
from urllib.parse import urljoin

import httpx

from sherpa.audit.static_checks import FEED_PATHS, WEBHOOK_PATHS
from sherpa.paypal.client import PayPalClient

FAKE_PRICE = "1.00"
ORDER_PATHS = ("/api/orders", "/api/paypal/orders", "/api/checkout/orders", "/api/create-order")
PRODUCT_PATHS = ("/api/products", *FEED_PATHS)
PRODUCT_LINK_RE = re.compile(r"""href=["']/(?:products?|p|shop|cakes?|items?)/([\w-]+)["']""", re.I)

VULNERABLE, BLOCKED, MISSING, UNKNOWN, SKIPPED = "vulnerable", "blocked", "missing", "unknown", "skipped"


def _price(p: dict[str, Any]) -> float | None:
    raw = p.get("price")
    raw = raw.get("value") if isinstance(raw, dict) else raw
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


async def find_product(c: httpx.AsyncClient, base: str) -> dict[str, Any] | None:
    """A real product id (and its price when the store publishes one) to put in the attacker's cart."""
    for path in PRODUCT_PATHS:
        try:
            r = await c.get(urljoin(base, path))
            data = r.json() if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            continue
        items = (data.get("items") or data.get("products")) if isinstance(data, dict) else data
        if isinstance(items, list):
            for p in items:
                if isinstance(p, dict) and p.get("id"):
                    return {"id": str(p["id"]), "title": p.get("title") or p.get("name"), "price": _price(p)}
    try:
        r = await c.get(base)
        m = PRODUCT_LINK_RE.search(r.text)
    except httpx.HTTPError:
        m = None
    return {"id": m.group(1), "title": None, "price": None} if m else None


def _order_amount(order: dict[str, Any] | None) -> str | None:
    try:
        return str(order["purchase_units"][0]["amount"]["value"]) if order else None
    except (KeyError, IndexError, TypeError):
        return None


async def price_tamper(
    c: httpx.AsyncClient, base: str, product: dict[str, Any] | None, paypal: PayPalClient
) -> dict:
    # A store without a product list (a single-item or fixed-amount checkout) still gets the tampered request:
    # a server that sets its own amount ignores the placeholder, and a vulnerable one charges $1.00.
    product = product or {"id": "sherpa-probe-item", "title": None, "price": None}
    line = {"id": product["id"], "qty": 1, "quantity": 1, "price": FAKE_PRICE, "unit_price": FAKE_PRICE}
    payload = {"items": [line], "total": FAKE_PRICE, "amount": FAKE_PRICE, "currency": "USD"}
    for path in ORDER_PATHS:
        try:
            r = await c.post(urljoin(base, path), json=payload)
        except httpx.HTTPError as exc:
            return {"verdict": UNKNOWN, "detail": f"Request failed: {type(exc).__name__}"}
        if r.status_code in (404, 405):
            continue
        request = f"POST {path} with the price set to ${FAKE_PRICE}"
        if r.status_code >= 400:
            return {
                "verdict": BLOCKED,
                "request": request,
                "status": r.status_code,
                "detail": f"The store refused the order (HTTP {r.status_code}).",
            }
        try:
            body = r.json()
        except ValueError:
            body = {}
        order_id = body.get("id") if isinstance(body, dict) else None
        order = await paypal.get_order(order_id) if order_id and paypal.configured else None
        amount = _order_amount(order) or _order_amount(body)
        real = f"${product['price']:.2f}" if product.get("price") else "the real price"
        if amount is None:
            return {
                "verdict": UNKNOWN,
                "request": request,
                "status": r.status_code,
                "order_id": order_id,
                "detail": "An order was created but its amount could not be read from PayPal.",
            }
        if float(amount) == float(FAKE_PRICE) and (product.get("price") or 0) != float(FAKE_PRICE):
            return {
                "verdict": VULNERABLE,
                "request": request,
                "status": r.status_code,
                "order_id": order_id,
                "amount": amount,
                "detail": f"PayPal order {order_id} was created for ${amount} instead of {real}.",
            }
        return {
            "verdict": BLOCKED,
            "request": request,
            "status": r.status_code,
            "order_id": order_id,
            "amount": amount,
            "detail": f"The server ignored the browser's price: PayPal order {order_id} is for ${amount}.",
        }
    return {"verdict": MISSING, "detail": "No order endpoint found."}


def forged_event() -> dict[str, Any]:
    return {
        "id": f"WH-SHERPA-FORGED-{uuid.uuid4().hex[:12]}",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "summary": "Forged by Sherpa's attack replay",
        "resource": {
            "id": "SHERPA-FORGED",
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": "349.00"},
        },
    }


FORGED_HEADERS = {
    "paypal-transmission-id": "forged-transmission",
    "paypal-transmission-time": "2026-01-01T00:00:00Z",
    "paypal-transmission-sig": "Zm9yZ2Vk",
    "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-forged",
    "paypal-auth-algo": "SHA256withRSA",
}


async def forged_webhook(c: httpx.AsyncClient, base: str) -> dict:
    for path in WEBHOOK_PATHS:
        try:
            r = await c.post(urljoin(base, path), json=forged_event(), headers=FORGED_HEADERS)
        except httpx.HTTPError as exc:
            return {"verdict": UNKNOWN, "detail": f"Request failed: {type(exc).__name__}"}
        if r.status_code in (404, 405):
            continue
        request = f"POST {path} with a fake PAYMENT.CAPTURE.COMPLETED event"
        if r.status_code < 300:
            return {
                "verdict": VULNERABLE,
                "request": request,
                "status": r.status_code,
                "detail": f"The store accepted a forged payment notification (HTTP {r.status_code}).",
            }
        if r.status_code < 500:
            return {
                "verdict": BLOCKED,
                "request": request,
                "status": r.status_code,
                "detail": f"The forged notification was rejected (HTTP {r.status_code}).",
            }
        return {
            "verdict": UNKNOWN,
            "request": request,
            "status": r.status_code,
            "detail": f"The store errored (HTTP {r.status_code}).",
        }
    return {"verdict": MISSING, "detail": "No PayPal webhook endpoint found."}


ATTACKS = (
    ("price_tamper", "Price tampering", "A shopper edits the price to $1.00 before paying."),
    ("forged_webhook", "Forged payment notification", 'Someone fakes PayPal\'s "payment completed" message.'),
)


async def attack(base: str, paypal: PayPalClient) -> dict[str, dict]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        product = await find_product(c, base.rstrip("/") + "/")
        return {
            "price_tamper": await price_tamper(c, base.rstrip("/") + "/", product, paypal),
            "forged_webhook": await forged_webhook(c, base.rstrip("/") + "/"),
        }


async def replay(before_url: str | None, after_url: str, paypal: PayPalClient | None = None) -> list[dict]:
    """Run every attack against the store before the fix (when it is a sandbox store) and after it."""
    paypal = paypal or PayPalClient()
    skipped = {"verdict": SKIPPED, "detail": "Sherpa only attacks stores it knows run in the PayPal sandbox."}
    before = await attack(before_url, paypal) if before_url else {k: skipped for k, *_ in ATTACKS}
    after = await attack(after_url, paypal)
    return [
        {"id": key, "title": title, "threat": threat, "before": before[key], "after": after[key]}
        for key, title, threat in ATTACKS
    ]


def proven(attacks: list[dict]) -> bool:
    """True when every attack is stopped after the fix."""
    return bool(attacks) and all(a["after"]["verdict"] in (BLOCKED, MISSING) for a in attacks)
