import httpx
import pytest
import respx

from sherpa import fleet

V5 = '<script src="https://www.paypal.com/sdk/js?client-id=x&disable-funding=venmo"></script>'
V6 = '<script src="https://www.paypal.com/web-sdk/v6/core"></script><venmo-button></venmo-button><paypal-message>'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8080", "http://169.254.169.254/computeMetadata", "file:///etc/passwd"]
)
async def test_non_public_targets_are_refused(url):
    h = await fleet.check_store(url)
    assert h.error and not h.reachable and h.score == 0


@pytest.fixture
def public(monkeypatch):
    async def allow(url: str) -> None:
        return None

    monkeypatch.setattr(fleet, "_assert_public", allow)


def _store(mock: respx.MockRouter, base: str, html: str, feed: bool = False, cart: bool = False) -> None:
    mock.get(f"{base}/").respond(200, html=html)
    mock.get(f"{base}/cart").respond(404)
    mock.get(f"{base}/checkout").respond(404)
    for path in fleet.FEED_PATHS:
        if feed and path == "/catalog.json":
            mock.get(f"{base}{path}").respond(200, json={"items": [{"id": "a"}, {"id": "b"}]})
        else:
            mock.get(f"{base}{path}").respond(404)
    if cart:
        mock.post(f"{base}/merchant-cart").respond(200, json={"validation_status": "INVALID"})
    else:
        mock.post(f"{base}/merchant-cart").respond(404)


@pytest.mark.asyncio
async def test_scan_ranks_worst_first(public):
    with respx.mock(assert_all_called=False) as mock:
        _store(mock, "https://legacy.example", V5)
        _store(mock, "https://modern.example", V6, feed=True, cart=True)
        rows = await fleet.scan(
            ["https://modern.example", "https://legacy.example/", "https://legacy.example"]
        )
    assert [r["url"] for r in rows] == ["https://legacy.example", "https://modern.example"]
    legacy, modern = rows
    assert legacy["sdk"] == "v5" and not legacy["venmo"] and legacy["score"] == 30
    assert "Legacy JS SDK (v5)" in legacy["issues"]
    assert modern["score"] == 100 and modern["catalog_items"] == 2 and modern["issues"] == []


@pytest.mark.asyncio
async def test_unreachable_store_is_reported(public):
    with respx.mock() as mock:
        mock.get("https://down.example/").mock(side_effect=httpx.ConnectError("boom"))
        h = await fleet.check_store("https://down.example")
    assert not h.reachable and h.error and h.issues[0] == h.error


@pytest.mark.asyncio
async def test_sdk_loaded_from_own_script_is_found(public):
    page = '<script src="/_next/app.js"></script><script src="https://cdn.other/x.js"></script>'
    with respx.mock(assert_all_called=False) as mock:
        _store(mock, "https://spa.example", page)
        mock.get("https://spa.example/_next/app.js").respond(
            200, text='s.src="https://www.paypal.com/sdk/js?client-id="+id+"&currency=USD"'
        )
        h = await fleet.check_store("https://spa.example")
    assert h.paypal and h.sdk == "v5"
