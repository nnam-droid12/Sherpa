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
