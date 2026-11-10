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


def test_playwright_driver_crash_is_an_infra_error():
    assert shopper.is_infra_error(Exception("Connection closed while reading from the driver"))


@pytest.mark.parametrize(
    ("typed", "iso"),
    [
        ("11/20/2026", "2026-11-20"),
        ("11202026", "2026-11-20"),  # typed into a phone's segmented mm/dd/yyyy field
        ("20261120", "2026-11-20"),
        ("2026-11-20", "2026-11-20"),
        ("November 20, 2026", "2026-11-20"),
        ("20 Nov 2026", "2026-11-20"),
    ],
)
def test_typed_dates_become_iso(typed, iso):
    assert shopper.to_iso_date(typed) == iso


@pytest.mark.parametrize("typed", ["Alex Rivera", "500 Market St", "94105", "13/45/2026"])
def test_non_dates_are_left_alone(typed):
    assert shopper.to_iso_date(typed) is None


class SlowCapturePayPal:
    """APPROVED for the first checks, then COMPLETED, like a store whose capture lands after the popup closes."""

    def __init__(self, approved_checks):
        self.left = approved_checks

    async def get_order(self, order_id):
        if self.left > 0:
            self.left -= 1
            return {"id": order_id, "status": "APPROVED"}
        return {
            "id": order_id,
            "status": "COMPLETED",
            "purchase_units": [{"payments": {"captures": [{"status": "COMPLETED"}]}}],
        }


@pytest.mark.asyncio
async def test_a_capture_that_lands_late_is_still_confirmed():
    done = await shopper.confirm_payment(SlowCapturePayPal(2), ["ORDER1"], wait_s=5, poll_s=0.01)
    assert done == {"id": "ORDER1", "status": "COMPLETED"}


@pytest.mark.asyncio
async def test_an_order_that_never_completes_is_not_confirmed():
    assert (
        await shopper.confirm_payment(SlowCapturePayPal(10_000), ["ORDER1"], wait_s=0.05, poll_s=0.01) is None
    )
