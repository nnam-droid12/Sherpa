"""Minimal PayPal sandbox REST client: OAuth, Orders v2 and webhook signature verification."""

from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sherpa.config import PAYPAL_SANDBOX_BASE, get_settings

_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


class PayPalClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None) -> None:
        s = get_settings()
        self.client_id = client_id or s.paypal_client_id
        self.client_secret = client_secret or s.paypal_client_secret
        self.base = PAYPAL_SANDBOX_BASE
        self._token: str | None = None
        self._token_exp = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @_retry
    async def token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{self.base}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
            )
            r.raise_for_status()
            data = r.json()
        self._token = data["access_token"]
        self._token_exp = time.time() + int(data.get("expires_in", 300))
        return self._token

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {await self.token()}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as c:
            return await c.request(method, f"{self.base}{path}", headers=headers, **kw)

    @_retry
    async def get_order(self, order_id: str) -> dict[str, Any] | None:
        r = await self._request("GET", f"/v2/checkout/orders/{order_id}")
        if r.status_code == 404:
            return None
        if r.status_code >= 500:
            r.raise_for_status()
        return r.json() if r.status_code < 400 else None

    async def create_order(self, amount: str, currency: str = "USD", **extra: Any) -> dict[str, Any]:
        body = {
            "intent": "CAPTURE",
            "purchase_units": [{"amount": {"currency_code": currency, "value": amount}}],
        }
        body.update(extra)
        r = await self._request("POST", "/v2/checkout/orders", json=body)
        r.raise_for_status()
        return r.json()

    async def capture_order(self, order_id: str) -> dict[str, Any]:
        r = await self._request("POST", f"/v2/checkout/orders/{order_id}/capture")
        return r.json()

    async def verify_webhook_signature(
        self, headers: dict[str, str], event: dict[str, Any], webhook_id: str
    ) -> bool:
        h = {k.lower(): v for k, v in headers.items()}
        body = {
            "auth_algo": h.get("paypal-auth-algo"),
            "cert_url": h.get("paypal-cert-url"),
            "transmission_id": h.get("paypal-transmission-id"),
            "transmission_sig": h.get("paypal-transmission-sig"),
            "transmission_time": h.get("paypal-transmission-time"),
            "webhook_id": webhook_id,
            "webhook_event": event,
        }
        if not all(body.values()):
            return False
        r = await self._request("POST", "/v1/notifications/verify-webhook-signature", json=body)
        return r.status_code == 200 and r.json().get("verification_status") == "SUCCESS"


def order_completed(order: dict[str, Any] | None) -> bool:
    """An order counts as paid when it is COMPLETED and has a completed capture."""
    if not order or order.get("status") != "COMPLETED":
        return False
    for unit in order.get("purchase_units", []):
        for cap in unit.get("payments", {}).get("captures", []):
            if cap.get("status") == "COMPLETED":
                return True
    return False
