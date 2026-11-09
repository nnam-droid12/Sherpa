import pytest

from sherpa.audit import runner, shopper
from sherpa.audit.shopper import BrowserGone, ShopperResult


class FakePage:
    def __init__(self, name, closed=False, fails=False):
        self.name, self.closed, self.fails = name, closed, fails

    def is_closed(self):
        return self.closed

    def locator(self, _sel):
        return None

    async def screenshot(self, **_kw):
        if self.fails:
            raise RuntimeError("Target page, context or browser has been closed")
        return self.name.encode()


class FakeBrowser:
    def __init__(self, page, main, pages):
        self.page, self.main = page, main
        self.session = type("S", (), {"context": type("C", (), {"pages": pages})()})()


@pytest.mark.asyncio
async def test_screenshot_falls_back_to_any_open_page():
    popup = FakePage("popup", closed=True)
    main = FakePage("main", fails=True)
    other = FakePage("store-tab")
    b = FakeBrowser(popup, main, [main, other])
    assert await shopper._active_screenshot(b) == b"store-tab"
    assert b.page is other


@pytest.mark.asyncio
async def test_screenshot_reports_browser_gone_when_every_page_closed():
    main = FakePage("main", closed=True)
    with pytest.raises(BrowserGone):
        await shopper._active_screenshot(FakeBrowser(main, main, [main]))


def test_infra_errors_are_told_apart_from_store_errors():
    assert shopper.is_infra_error(BrowserGone("gone"))
    assert shopper.is_infra_error(
        RuntimeError("Page.screenshot: Target page, context or browser has been closed")
    )
    assert not shopper.is_infra_error(ValueError("checkout returned 500"))


@pytest.mark.asyncio
async def test_only_browser_failures_without_payment_are_retried_once():
    events, reruns = [], []

    async def emit(kind, **data):
        events.append(data.get("message"))

    async def rerun(device):
        reruns.append(device)
        return ShopperResult(device=device, payment_completed=True)

    by_device = {
        "desktop": ShopperResult(device="desktop", error="checkout crashed"),
        "mobile": ShopperResult(device="mobile", error="TargetClosedError", infra_error=True),
    }
    paid_anyway = ShopperResult(device="desktop", infra_error=True, payment_completed=True)
    await runner.retry_browser_failures(by_device, rerun, emit)
    assert reruns == ["mobile"] and by_device["mobile"].payment_completed
    assert "retrying the mobile shopper once" in events[0]
    reruns.clear()
    await runner.retry_browser_failures({"desktop": paid_anyway}, rerun, emit)
    assert reruns == []
