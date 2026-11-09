"""Fleet scan: a fast, browser-free health check of PayPal checkout across many stores.

Only public pages are fetched and nothing is posted except the empty Cart API probe, so a scan costs
no browser minutes or model calls. The score is a triage signal, not the full audit rubric.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from sherpa.audit.runner import HTML_PATHS
from sherpa.audit.static_checks import (
    FEED_PATHS,
    detect_sdk_in_source,
    has_pay_later,
    has_venmo,
    probe_cart_api,
)

MAX_STORES = 25
CONCURRENCY = 6
STORE_TIMEOUT_S = 30
MAX_SCRIPTS = 12
MAX_SCRIPT_BYTES = 1_500_000
SCRIPT_SRC_RE = re.compile(r"""<script[^>]+src=["']([^"']+)["']""", re.I)

# Points per signal, out of 100.
POINTS = {"paypal": 30, "sdk_v6": 20, "venmo": 10, "pay_later": 10, "catalog_feed": 15, "cart_api": 15}


class BlockedHost(Exception):
    pass


async def _assert_public(url: str) -> None:
    """Refuse non-public targets (loopback, private ranges, cloud metadata) to avoid SSRF."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BlockedHost("only http(s) URLs can be scanned")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise BlockedHost(f"could not resolve {parts.hostname}") from exc
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise BlockedHost(f"{parts.hostname} is not a public address")


async def _guard(request: httpx.Request) -> None:
    # Redirects are checked too, so a public URL can't bounce the scanner inward.
    await _assert_public(str(request.url))


@dataclass
class StoreHealth:
    url: str
    reachable: bool = False
    status: int | None = None
    ms: int | None = None
    sdk: str = "none"
    paypal: bool = False
    venmo: bool = False
    pay_later: bool = False
    catalog_feed: str | None = None
    catalog_items: int = 0
    cart_api: bool = False
    score: int = 0
    issues: list[str] = field(default_factory=list)
    error: str | None = None


def grade(h: StoreHealth) -> None:
    signals = {
        "paypal": h.paypal,
        "sdk_v6": h.sdk == "v6",
        "venmo": h.venmo,
        "pay_later": h.pay_later,
        "catalog_feed": bool(h.catalog_feed),
        "cart_api": h.cart_api,
    }
    h.score = sum(POINTS[k] for k, ok in signals.items() if ok)
    h.issues = []
    if not h.paypal:
        h.issues.append("PayPal not seen on public pages")
    elif h.sdk == "v5":
        h.issues.append("Legacy JS SDK (v5)")
    if h.paypal and not h.venmo:
        h.issues.append("No Venmo")
    if h.paypal and not h.pay_later:
        h.issues.append("No Pay Later messaging")
    if not h.catalog_feed:
        h.issues.append("No catalog feed for AI agents")
    if not h.cart_api:
        h.issues.append("No Cart API for AI agents")


async def _own_scripts(c: httpx.AsyncClient, base: str, html: str) -> list[str]:
    """Same-origin scripts, where SPAs and Next.js stores load the PayPal SDK after the page renders."""
    host = urlparse(base).netloc
    out: list[str] = []
    for src in dict.fromkeys(SCRIPT_SRC_RE.findall(html)):
        url = urljoin(base, src)
        if urlparse(url).netloc != host:
            continue
        try:
            r = await c.get(url)
        except httpx.HTTPError:
            continue
        if r.status_code == 200 and len(r.content) <= MAX_SCRIPT_BYTES:
            out.append(r.text)
        if len(out) >= MAX_SCRIPTS:
            break
    return out


async def check_store(url: str, probe_cart: bool = True) -> StoreHealth:
    h = StoreHealth(url=url.rstrip("/"))
    base = h.url + "/"
    try:
        await _assert_public(base)
        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            max_redirects=5,
            event_hooks={"request": [_guard]},
            headers={"user-agent": "SherpaFleetScan/1.0 (+checkout health check)"},
        ) as c:
            async with asyncio.timeout(STORE_TIMEOUT_S):
                pages: list[str] = []
                for i, path in enumerate(HTML_PATHS):
                    t0 = time.perf_counter()
                    try:
                        r = await c.get(urljoin(base, path))
                    except httpx.HTTPError:
                        if i == 0:
                            raise
                        continue
                    if i == 0:
                        h.status, h.ms = r.status_code, int((time.perf_counter() - t0) * 1000)
                        h.reachable = r.status_code < 400
                    if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                        pages.append(r.text)
                html = "\n".join(pages)
                html += "\n" + "\n".join(await _own_scripts(c, base, html))
                sdk = detect_sdk_in_source({"pages": html})
                h.sdk = sdk.version
                h.paypal = sdk.version != "none"
                h.venmo = h.paypal and has_venmo(sdk, html)
                h.pay_later = h.paypal and has_pay_later(html)
                for path in FEED_PATHS:
                    try:
                        r = await c.get(urljoin(base, path))
                        data = (
                            r.json()
                            if r.status_code == 200 and "json" in r.headers.get("content-type", "")
                            else None
                        )
                    except (httpx.HTTPError, ValueError):
                        continue
                    items = (data.get("items") or data.get("products")) if isinstance(data, dict) else data
                    if isinstance(items, list) and items and isinstance(items[0], dict):
                        h.catalog_feed, h.catalog_items = path, len(items)
                        break
                # The Cart API probe is an empty POST; read-only studies of third-party stores skip it.
                if probe_cart:
                    h.cart_api = bool((await probe_cart_api(base, c)).get("present"))
    except BlockedHost as exc:
        h.error = str(exc)
    except TimeoutError:
        h.error = f"timed out after {STORE_TIMEOUT_S}s"
    except httpx.HTTPError as exc:
        h.error = f"could not load the store ({type(exc).__name__})"
    grade(h)
    if h.error:
        h.issues.insert(0, h.error)
    return h


async def scan(urls: list[str]) -> list[dict[str, Any]]:
    unique = list(dict.fromkeys(u.strip().rstrip("/") for u in urls if u.strip()))[:MAX_STORES]
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(u: str) -> StoreHealth:
        async with sem:
            return await check_store(u)

    results = await asyncio.gather(*(one(u) for u in unique))
    return sorted((asdict(r) for r in results), key=lambda r: r["score"])
