"""KERNEL cloud browser sessions driven by Playwright over CDP."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

from kernel import AsyncKernel
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from sherpa.config import get_settings

log = logging.getLogger(__name__)

Device = Literal["desktop", "mobile"]

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
)


@dataclass(frozen=True)
class DeviceProfile:
    name: Device
    width: int
    height: int
    user_agent: str | None = None
    is_mobile: bool = False


PROFILES: dict[Device, DeviceProfile] = {
    "desktop": DeviceProfile("desktop", 1440, 900),
    "mobile": DeviceProfile("mobile", 390, 844, MOBILE_UA, True),
}

# PayPal sandbox checkout and SDK hosts the shopper may visit besides the store itself.
PAYPAL_HOST_SUFFIXES = (".paypal.com", ".paypalobjects.com", ".venmo.com")


def host_allowed(url: str, allowed_hosts: set[str]) -> bool:
    """True if the URL's host is a store/preview host or a PayPal-owned host."""
    parsed = urlparse(url)
    if parsed.scheme in {"about", "data", "blob"}:
        return True
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in allowed_hosts:
        return True
    return host == "paypal.com" or host.endswith(PAYPAL_HOST_SUFFIXES)


@dataclass
class BrowserSession:
    session_id: str
    device: DeviceProfile
    page: Page
    context: BrowserContext
    live_view_url: str | None
    replay_id: str | None = None
    replay_url: str | None = None
    blocked: list[str] = field(default_factory=list)


@asynccontextmanager
async def open_session(
    device: Device, allowed_hosts: set[str], *, timeout_seconds: int = 900
) -> AsyncIterator[BrowserSession]:
    """Create a KERNEL browser, attach Playwright, record a replay, and always clean up."""
    settings = get_settings()
    kernel = AsyncKernel(api_key=settings.kernel_api_key)
    profile = PROFILES[device]
    kb = await kernel.browsers.create(
        stealth=True,
        timeout_seconds=timeout_seconds,
        viewport={"width": profile.width, "height": profile.height},
        kiosk_mode=True,
    )
    pw: Playwright | None = None
    browser: Browser | None = None
    session: BrowserSession | None = None
    try:
        try:
            replay = await kernel.browsers.replays.start(kb.session_id)
            replay_id, replay_url = replay.replay_id, getattr(replay, "replay_view_url", None)
        except Exception:  # replays are a nice-to-have; never fail the audit over them
            log.warning("replay start failed", exc_info=True)
            replay_id = replay_url = None

        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
        if profile.is_mobile:
            context = await browser.new_context(
                viewport={"width": profile.width, "height": profile.height},
                user_agent=profile.user_agent,
                is_mobile=True,
                has_touch=True,
                device_scale_factor=2,
            )
        else:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        await page.set_viewport_size({"width": profile.width, "height": profile.height})

        session = BrowserSession(
            session_id=kb.session_id,
            device=profile,
            page=page,
            context=context,
            live_view_url=getattr(kb, "browser_live_view_url", None),
            replay_id=replay_id,
            replay_url=replay_url,
        )

        async def guard(route):
            url = route.request.url
            if route.request.is_navigation_request() and not host_allowed(url, allowed_hosts):
                session.blocked.append(url)
                await route.abort("blockedbyclient")
            else:
                await route.continue_()

        await context.route("**/*", guard)
        yield session
    finally:
        if session and session.replay_id:
            try:
                await kernel.browsers.replays.stop(session.replay_id, id_or_name=kb.session_id)
                if not session.replay_url:
                    for r in await kernel.browsers.replays.list(kb.session_id):
                        if r.replay_id == session.replay_id:
                            session.replay_url = r.replay_view_url
            except Exception:
                log.warning("replay stop failed", exc_info=True)
        for closer in (browser.close if browser else None, pw.stop if pw else None):
            if closer:
                try:
                    await asyncio.wait_for(closer(), timeout=15)
                except Exception:
                    log.debug("close failed", exc_info=True)
        try:
            await kernel.browsers.delete_by_id(kb.session_id)
        except Exception:
            log.warning("kernel browser delete failed", exc_info=True)
