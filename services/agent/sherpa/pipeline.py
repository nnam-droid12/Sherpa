"""Background jobs for each run stage. Each stage updates the run document and streams events."""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sherpa.audit.runner import run_audit
from sherpa.fixer import github
from sherpa.fixer.agent import run_fixer
from sherpa.fixer.pr import pr_body
from sherpa.fixer.tools import Workspace
from sherpa.gitrepo import clone, parse_repo
from sherpa.store.runs import RunStore

log = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()
MAX_DIFF = 150_000


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


def emitter(store: RunStore, run_id: str, phase: str):
    async def emit(kind: str, **data: Any) -> None:
        await store.add_event(run_id, kind, phase=phase, **data)

    return emit


async def audit_job(store: RunStore, run: dict[str, Any]) -> dict[str, Any]:
    audit = await run_audit(store, run["id"], run["store_url"], repo=run.get("repo"), label="before")
    return {"audit": audit}


async def fix_job(store: RunStore, run: dict[str, Any]) -> dict[str, Any]:
    run_id, repo = run["id"], run["repo"]
    emit = emitter(store, run_id, "fix")
    _, name = parse_repo(repo)
    await emit("log", message=f"Cloning {repo}")
    root = await clone(repo)
    try:
        base = await github.default_branch(repo)
        ws = Workspace(root)
        outcome = await run_fixer(
            ws, run["audit"]["findings"], emit, store_type=run.get("store_type", "auto")
        )
        if not ws.changed:
            raise RuntimeError("The fixer made no changes.")
        if not outcome.build_ok:
            raise RuntimeError(
                "The build does not pass after the fixer's changes; no pull request was opened."
            )
        branch = f"sherpa/fix-{name.removeprefix('sherpa-demo-')}-{run_id}"
        await emit("log", message=f"Committing {len(outcome.files_changed)} files to {branch}")
        sha = await github.commit_and_push(
            root, branch, "fix(checkout): upgrade PayPal to JS SDK v6 and harden payments"
        )
        diff = await github.git(root, "show", "--format=", "--no-color", "HEAD")
        pr = await github.open_pr(
            repo,
            head=branch,
            base=base,
            title="Upgrade PayPal checkout: JS SDK v6, Venmo, Pay Later and safer payments",
            body=pr_body(run["audit"], outcome, run["store_url"]),
        )
        await emit("log", message=f"Opened pull request #{pr['number']}")
        return {
            "fix": {
                "pr_url": pr["html_url"],
                "pr_number": pr["number"],
                "branch": branch,
                "base": base,
                "sha": sha,
                "summary": outcome.summary,
                "changes": outcome.changes,
                "files_changed": outcome.files_changed,
                "diff": diff[:MAX_DIFF],
                "build_ok": outcome.build_ok,
                "tool_calls": outcome.tool_calls,
                "model_calls": outcome.model_calls,
                "unresolved": outcome.unresolved,
                "seconds": outcome.seconds,
            }
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


@dataclass(frozen=True)
class Stage:
    name: str
    requires: tuple[str, ...]
    job: Callable[[RunStore, dict[str, Any]], Awaitable[dict[str, Any]]]


STAGES: dict[str, Stage] = {
    "fix": Stage("fix", ("audit", "repo"), fix_job),
}
