import asyncio

import pytest

from sherpa import pipeline
from sherpa.config import get_settings
from sherpa.store.runs import RunStore, take_daily_quota


@pytest.fixture
def cap_of_two(monkeypatch):
    monkeypatch.setenv("SHERPA_DAILY_CODING_RUNS", "2")
    monkeypatch.setenv("SHERPA_DEMO_MODE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def finish(store, run_id):
    for _ in range(100):
        await asyncio.sleep(0.02)
        status = (await store.get_run(run_id))["status"]
        if not status.endswith(":running"):
            return await store.get_run(run_id)
    raise AssertionError("stage never finished")


@pytest.mark.asyncio
async def test_coding_stages_stop_at_the_daily_cap(cap_of_two):
    store = RunStore(use_firestore=False)
    results = []
    for _ in range(3):
        run = await store.create_run({"store_url": "https://store.example"})

        async def job():
            return {}

        pipeline.spawn(store, run["id"], "fix", job)
        results.append(await finish(store, run["id"]))
    assert [r["status"] for r in results] == ["fix:done", "fix:done", "fix:failed"]
    assert "today's demo limit of 2" in results[2]["error"]


@pytest.mark.asyncio
async def test_other_stages_are_not_capped(cap_of_two):
    store = RunStore(use_firestore=False)
    for _ in range(3):
        run = await store.create_run({"store_url": "https://store.example"})

        async def job():
            return {}

        pipeline.spawn(store, run["id"], "verify", job)
        assert (await finish(store, run["id"]))["status"] == "verify:done"


@pytest.mark.asyncio
async def test_quota_counts_per_key_and_refuses_without_counting():
    store = RunStore(use_firestore=False)
    assert await take_daily_quota(store, "a", 1) is True
    assert await take_daily_quota(store, "a", 1) is False
    assert await take_daily_quota(store, "b", 1) is True


@pytest.mark.asyncio
async def test_a_cap_of_zero_pauses_coding_stages_with_a_clear_message(monkeypatch):
    monkeypatch.setenv("SHERPA_DAILY_CODING_RUNS", "0")
    monkeypatch.setenv("SHERPA_DEMO_MODE", "true")
    get_settings.cache_clear()
    try:
        store = RunStore(use_firestore=False)
        run = await store.create_run({"store_url": "https://store.example"})

        async def job():
            raise AssertionError("a paused stage must never run")

        pipeline.spawn(store, run["id"], "agent_ready", job)
        final = await finish(store, run["id"])
    finally:
        get_settings.cache_clear()
    assert final["status"] == "agent_ready:failed"
    assert final["error"].startswith("Fix and Agent-ready are paused on the public demo")


@pytest.mark.asyncio
async def test_audits_have_their_own_daily_cap(monkeypatch):
    monkeypatch.setenv("SHERPA_DAILY_AUDIT_RUNS", "1")
    monkeypatch.setenv("SHERPA_DEMO_MODE", "true")
    get_settings.cache_clear()
    try:
        store = RunStore(use_firestore=False)
        statuses = []
        for _ in range(2):
            run = await store.create_run({"store_url": "https://store.example"})

            async def job():
                return {}

            pipeline.spawn(store, run["id"], "audit", job)
            statuses.append((await finish(store, run["id"]))["status"])
    finally:
        get_settings.cache_clear()
    assert statuses == ["audit:done", "audit:failed"]
