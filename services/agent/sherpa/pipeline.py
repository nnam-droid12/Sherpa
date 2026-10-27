"""Background jobs for each run stage. Each stage updates the run document and streams events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sherpa.audit.runner import run_audit
from sherpa.store.runs import RunStore

log = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()


def spawn(store: RunStore, run_id: str, stage: str, job: Callable[[], Awaitable[dict[str, Any]]]) -> None:
    """Run a stage in the background; failures are recorded on the run instead of being lost."""

    async def wrapper() -> None:
        await store.update_run(run_id, status=f"{stage}:running", stage=stage, error=None)
        try:
            patch = await job()
            await store.update_run(run_id, status=f"{stage}:done", **patch)
        except Exception as exc:
            log.exception("stage %s failed", stage, extra={"run_id": run_id})
            await store.add_event(run_id, "error", phase=stage, message=str(exc)[:500])
            await store.update_run(run_id, status=f"{stage}:failed", error=str(exc)[:500])

    task = asyncio.create_task(wrapper())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def audit_job(store: RunStore, run: dict[str, Any]) -> dict[str, Any]:
    audit = await run_audit(store, run["id"], run["store_url"], repo=run.get("repo"), label="before")
    return {"audit": audit}
