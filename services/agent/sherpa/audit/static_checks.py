"""Deterministic checks that complement the visual shopper.

Every function here is pure or does plain HTTP/Playwright work, so results are reproducible.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

LEGACY_SDK_RE = re.compile(r"""https://www\.(?:sandbox\.)?paypal\.com/sdk/js\?[^"'\s>`]*""", re.I)
V6_SDK_RE = re.compile(r"""https://www\.(?:sandbox\.)?paypal\.com/web-sdk/v6/core""", re.I)
PAY_LATER_RE = re.compile(
    r"""(paypal-message|data-pp-message|paypal\.Messages|createPayPalMessages|PayLaterMessage)"""
)
VENMO_V6_RE = re.compile(r"""(venmo-button|createVenmoOneTimePaymentSession|VenmoButton)""", re.I)
AMOUNT_FROM_CLIENT_RE = re.compile(r"""req\.body\b[^\n]*\btotal\b|\{\s*total\s*\}\s*=\s*req\.body""")
VERIFY_SIG_RE = re.compile(r"""verify-webhook-signature|verifyWebhookSignature""")
PAYMENT_GATE_RE = re.compile(r"""(Choose|Select) (a )?payment method""", re.I)
BLANK_PAGE_RE = re.compile(r"""document\.body\.innerHTML\s*=\s*["']{2}""")
WEBHOOK_PATHS = ("/api/webhooks/paypal", "/api/paypal/webhook", "/webhooks/paypal", "/api/webhook")
FEED_PATHS = (
    "/catalog.json",
    "/api/catalog",
    "/products.json",
    "/.well-known/catalog.json",
    "/api/catalog/feed",
)
CART_API_PATH = "/merchant-cart"
# Tests often quote the very code they guard against, so they never count as the store's behaviour.
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|e2e|spec)/|\.(test|spec)\.[cm]?[jt]sx?$", re.I)


@dataclass
class SdkInfo:
    version: str = "none"  # "v6", "v5", "none"
    script_urls: list[str] = field(default_factory=list)
    disable_funding: list[str] = field(default_factory=list)
    enable_funding: list[str] = field(default_factory=list)


def detect_sdk(html: str) -> SdkInfo:
    info = SdkInfo()
    v6 = V6_SDK_RE.findall(html)
    legacy = LEGACY_SDK_RE.findall(html)
    if v6:
        info.version = "v6"
        info.script_urls = v6
    elif legacy:
        info.version = "v5"
        info.script_urls = legacy
    for url in legacy:
        qs = parse_qs(urlparse(url.replace("&amp;", "&")).query)
        for key, target in (
            ("disable-funding", info.disable_funding),
            ("enable-funding", info.enable_funding),
        ):
            for value in qs.get(key, []):
                target.extend(v.strip() for v in value.split(",") if v.strip())
    return info


def detect_sdk_in_source(files: dict[str, str]) -> SdkInfo:
    """Same detection over source files; finds SDKs injected by JS loaders (e.g. useEffect)."""
    joined = "\n".join(files.values())
    info = detect_sdk(joined)
    if info.version == "none" and re.search(r"paypal\.com/sdk/js\?", joined):
        info.version = "v5"
    return info


def has_pay_later(text: str) -> bool:
    return bool(PAY_LATER_RE.search(text))


def has_venmo(sdk: SdkInfo, text: str) -> bool:
    if "venmo" in sdk.disable_funding:
        return False
    if "venmo" in sdk.enable_funding:
        return True
    return sdk.version == "v6" and bool(VENMO_V6_RE.search(text))


@dataclass
class ServerSignals:
    amount_from_client: bool | None = None
    webhook_signature_verified: bool | None = None
    blank_page_on_error: bool | None = None
    graceful_errors: bool | None = None
    payment_gated: bool | None = None
    evidence: dict[str, str] = field(default_factory=dict)


def analyze_source(files: dict[str, str]) -> ServerSignals:
    """Static code checks over the store's repo (paths relative to the store root)."""
    s = ServerSignals()
    s.amount_from_client = False
    s.webhook_signature_verified = False
    s.blank_page_on_error = False
    s.payment_gated = False
    has_webhook_handler = False
    has_error_ui = False
    for path, text in files.items():
        if TEST_PATH_RE.search(path):
            continue
        if AMOUNT_FROM_CLIENT_RE.search(text):
            s.amount_from_client = True
            s.evidence.setdefault("amount_from_client", path)
        if re.search(r"webhook", path, re.I) or re.search(r"""['"]/api/webhooks?/""", text):
            has_webhook_handler = True
            if VERIFY_SIG_RE.search(text):
                s.webhook_signature_verified = True
                s.evidence["webhook_signature_verified"] = path
            else:
                s.evidence.setdefault("webhook_unverified", path)
        if BLANK_PAGE_RE.search(text):
            s.blank_page_on_error = True
            s.evidence.setdefault("blank_page_on_error", path)
        if PAYMENT_GATE_RE.search(text):
            s.payment_gated = True
            s.evidence.setdefault("payment_gated", path)
        if re.search(r"""(role=["']alert["']|onError|try again|retry)""", text, re.I):
            has_error_ui = True
    if not has_webhook_handler:
        s.evidence["webhook_missing"] = "no webhook handler found"
    s.graceful_errors = has_error_ui and not s.blank_page_on_error
    return s


def read_source_tree(root: Path, max_bytes: int = 400_000) -> dict[str, str]:
    """Collect text source files under root, skipping dependencies and build output."""
    skip = {"node_modules", ".next", ".git", "dist", "build", "coverage", "public"}
    exts = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".json"}
    files: dict[str, str] = {}
    total = 0
    for p in sorted(root.rglob("*")):
        if any(part in skip for part in p.relative_to(root).parts) or not p.is_file():
            continue
        if p.suffix not in exts or p.name == "package-lock.json":
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        total += len(text)
        if total > max_bytes:
            break
        files[p.relative_to(root).as_posix()] = text
    return files


@dataclass
class ProbeResult:
    webhook_endpoint: str | None = None
    catalog_feed: str | None = None
    catalog_items: int = 0
    cart_api: dict[str, Any] = field(default_factory=dict)


async def probe_endpoints(base_url: str, client: httpx.AsyncClient | None = None) -> ProbeResult:
    """Probe the live store for webhook, catalog feed and Cart API endpoints."""
    own = client is None
    client = client or httpx.AsyncClient(timeout=15, follow_redirects=True)
    result = ProbeResult()
    try:
        for path in WEBHOOK_PATHS:
            r = await client.post(
                urljoin(base_url, path), json={}, headers={"content-type": "application/json"}
            )
            if r.status_code not in (404, 405):
                result.webhook_endpoint = path
                break
        for path in FEED_PATHS:
            r = await client.get(urljoin(base_url, path))
            if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                data = r.json()
                items = data.get("items") or data.get("products") if isinstance(data, dict) else data
                if isinstance(items, list) and items and isinstance(items[0], dict):
                    result.catalog_feed = path
                    result.catalog_items = len(items)
                    break
        result.cart_api = await probe_cart_api(base_url, client)
    finally:
        if own:
            await client.aclose()
    return result


async def probe_cart_api(base_url: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """Light contract probe: POST /merchant-cart with an empty cart should return a structured response."""
    url = urljoin(base_url, CART_API_PATH)
    try:
        r = await client.post(url, json={"items": []})
    except httpx.HTTPError as exc:
        return {"present": False, "error": str(exc)}
    present = r.status_code not in (404, 405) and "json" in r.headers.get("content-type", "")
    body: Any = None
    if present:
        try:
            body = r.json()
        except ValueError:
            present = False
    structured = isinstance(body, dict) and any(
        k in body for k in ("validation_status", "validation_issues", "name")
    )
    return {"present": present and structured, "status": r.status_code}


def as_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)
