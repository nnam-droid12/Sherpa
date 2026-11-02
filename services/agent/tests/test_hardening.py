import pytest
from fastapi import HTTPException

from sherpa.pipeline import add_usage
from sherpa.ratelimit import RateLimiter


def test_rate_limiter_blocks_after_limit_and_recovers():
    rl = RateLimiter(limit=2, window_s=60)
    rl.check("ip", now=0)
    rl.check("ip", now=1)
    with pytest.raises(HTTPException) as exc:
        rl.check("ip", now=2)
    assert exc.value.status_code == 429
    rl.check("other-ip", now=2)
    rl.check("ip", now=70)


def test_usage_accumulates_across_stages():
    shoppers = {
        "desktop": {"steps": 10, "model_calls": 11, "seconds": 120},
        "mobile": {"steps": 5, "model_calls": 6, "seconds": 60},
    }
    first = add_usage(None, {"audit": {"shoppers": shoppers}}, 200)
    assert first == {"steps": 15, "browser_minutes": 3.0, "model_calls": 17, "seconds": 200.0}
    second = add_usage(first, {"fix": {"model_calls": 30}}, 100)
    assert second["model_calls"] == 47 and second["steps"] == 15 and second["seconds"] == 300.0


async def test_preview_api_merges_extra_headers(monkeypatch):
    import httpx

    from sherpa.verify import preview

    seen = {}

    async def fake_request(self, method, url, headers=None, **kw):
        seen.update(headers or {})
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(preview, "_token", lambda: "tok")
    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    out = await preview._api(
        "POST", "https://storage.example/upload", content=b"x", headers={"Content-Type": "application/gzip"}
    )
    assert out == {"ok": True}
    assert seen == {"Authorization": "Bearer tok", "Content-Type": "application/gzip"}


async def test_screenshot_falls_back_to_store_when_paypal_popup_closed():
    from types import SimpleNamespace

    from sherpa.audit import shopper

    class FakePage:
        def __init__(self, closed, data):
            self.closed, self.data = closed, data

        def is_closed(self):
            return self.closed

        def locator(self, _):
            return None

        async def screenshot(self, **_):
            if self.closed:
                raise RuntimeError("Target page, context or browser has been closed")
            return self.data

    main = FakePage(False, b"store")
    b = SimpleNamespace(main=main, page=FakePage(True, b"popup"))
    assert await shopper._active_screenshot(b) == b"store"
    assert b.page is main


async def test_stop_request_cancels_a_running_stage(monkeypatch):
    import asyncio

    from sherpa import pipeline
    from sherpa.store.runs import RunStore

    monkeypatch.setattr(pipeline, "STOP_POLL_SECONDS", 0.05)
    store = RunStore(use_firestore=False)
    run = await store.create_run({"store_url": "https://store.example"})
    cleaned = asyncio.Event()

    async def slow_job():
        try:
            await asyncio.sleep(30)
        finally:
            cleaned.set()  # stages release browsers and clones in finally blocks
        return {}

    pipeline.spawn(store, run["id"], "fix", slow_job)
    await asyncio.sleep(0.1)
    assert (await store.get_run(run["id"]))["status"] == "fix:running"
    await store.update_run(run["id"], stop_requested=True)
    for _ in range(50):
        await asyncio.sleep(0.05)
        if (await store.get_run(run["id"]))["status"] != "fix:running":
            break
    final = await store.get_run(run["id"])
    assert final["status"] == "fix:failed" and final["error"] == "Stopped by the user."
    assert cleaned.is_set()
