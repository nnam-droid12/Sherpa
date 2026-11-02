"""Background jobs for each run stage. Each stage updates the run document and streams events."""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from sherpa.agentready.spec import agent_ready_check, agent_ready_task, run_contract_tests
from sherpa.audit.runner import run_audit
from sherpa.buyer.agent import next_weekday, run_buyer
from sherpa.fixer import github
from sherpa.fixer.agent import run_fixer
from sherpa.fixer.pr import pr_body, scorecard_comment
from sherpa.fixer.tools import Workspace
from sherpa.gitrepo import clone, parse_repo
from sherpa.store.runs import RunStore
from sherpa.verify.preview import deploy_preview

log = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()
MAX_DIFF = 150_000
STOP_POLL_SECONDS = 8
HEARTBEAT_SECONDS = 45


def add_usage(usage: dict[str, float] | None, patch: dict[str, Any], seconds: float) -> dict[str, float]:
    """Accumulate browser steps, browser minutes and model calls for the run's cost display."""
    total = {"steps": 0, "browser_minutes": 0.0, "model_calls": 0, "seconds": 0.0, **(usage or {})}
    audits = [patch.get("audit"), (patch.get("verify") or {}).get("audit")]
    for audit in filter(None, audits):
        for s in audit.get("shoppers", {}).values():
            total["steps"] += s.get("steps") or 0
            total["model_calls"] += s.get("model_calls") or 0
            total["browser_minutes"] += (s.get("seconds") or 0) / 60
    for key in ("fix", "agent_ready"):
        total["model_calls"] += (patch.get(key) or {}).get("model_calls") or 0
    total["seconds"] += seconds
    total["browser_minutes"] = round(total["browser_minutes"], 1)
    total["seconds"] = round(total["seconds"], 1)
    return total


def spawn(store: RunStore, run_id: str, stage: str, job: Callable[[], Awaitable[dict[str, Any]]]) -> None:
    """Run a stage in the background; failures are recorded on the run instead of being lost."""

    async def watch_for_stop(work: asyncio.Task) -> None:
        # A stop can be requested on any agent instance, so poll the shared run document.
        # The same loop writes a heartbeat, so a stage orphaned by a server restart can be detected.
        last_beat = 0.0
        while not work.done():
            await asyncio.sleep(STOP_POLL_SECONDS)
            if time.monotonic() - last_beat > HEARTBEAT_SECONDS:
                await store.heartbeat(run_id)
                last_beat = time.monotonic()
            fresh = await store.fresh_run(run_id)
            if fresh and fresh.get("stop_requested"):
                work.cancel()
                return

    async def wrapper() -> None:
        await store.update_run(
            run_id,
            status=f"{stage}:running",
            stage=stage,
            error=None,
            stop_requested=False,
            heartbeat=time.time(),
        )
        started = time.monotonic()
        work = asyncio.create_task(job())
        watcher = asyncio.create_task(watch_for_stop(work))
        try:
            patch = await work
            run = await store.get_run(run_id) or {}
            patch["usage"] = add_usage(run.get("usage"), patch, time.monotonic() - started)
            await store.update_run(run_id, status=f"{stage}:done", **patch)
        except asyncio.CancelledError:
            # Cloud browsers and clones are released by each stage's finally blocks.
            await store.add_event(run_id, "warning", phase=stage, message="Stopped by the user.")
            await store.update_run(
                run_id, status=f"{stage}:failed", error="Stopped by the user.", stop_requested=False
            )
        except Exception as exc:
            log.exception("stage %s failed", stage, extra={"run_id": run_id})
            await store.add_event(run_id, "error", phase=stage, message=str(exc)[:500])
            await store.update_run(run_id, status=f"{stage}:failed", error=str(exc)[:500])
        finally:
            watcher.cancel()

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
        # Agent-readiness (catalog feed, Cart API) is its own stage; keep the checkout PR focused.
        checkout_audit = {
            **run["audit"],
            "findings": [f for f in run["audit"]["findings"] if f.get("category") != "agent_readiness"],
        }
        outcome = await run_fixer(
            ws, checkout_audit["findings"], emit, store_type=run.get("store_type", "auto")
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
            root,
            branch,
            "fix(checkout): upgrade PayPal to JS SDK v6 and harden payments",
            paths=outcome.files_changed,
        )
        diff = await github.git(root, "show", "--format=", "--no-color", "HEAD")
        pr = await github.open_pr(
            repo,
            head=branch,
            base=base,
            title="Upgrade PayPal checkout: JS SDK v6, Venmo, Pay Later and safer payments",
            body=pr_body(checkout_audit, outcome, run["store_url"]),
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


async def verify_job(store: RunStore, run: dict[str, Any]) -> dict[str, Any]:
    run_id, repo, fix = run["id"], run["repo"], run["fix"]
    emit = emitter(store, run_id, "verify")
    service = f"store-{parse_repo(repo)[1].removeprefix('sherpa-demo-')}"
    tag = f"pr-{fix['pr_number']}"
    preview_url = (await deploy_preview(repo, fix["branch"], service, tag, emit)).rstrip("/")
    await emit("log", message="Re-running the shopper on desktop and mobile against the preview")
    after = await run_audit(store, run_id, preview_url, repo=repo, branch=fix["branch"], label="after")

    shoppers = after.get("shoppers", {})
    order = (shoppers.get("mobile") or {}).get("order") or (shoppers.get("desktop") or {}).get("order")
    comment_url = ""
    try:
        comment_url = await github.comment(
            repo, fix["pr_number"], scorecard_comment(run["audit"], after, preview_url, order)
        )
    except Exception as exc:
        await emit("warning", message=f"Could not comment on the PR: {exc}")
    return {
        "verify": {"preview_url": preview_url, "audit": after, "order": order, "comment_url": comment_url}
    }


BUYER_REQUESTS = {
    "lumen-bakehouse": "I need a birthday cake for 12 people delivered Saturday, under $90.",
    "ember-oak": "I need a two-person tent for a fall backpacking trip, under $400.",
}


async def agent_ready_job(store: RunStore, run: dict[str, Any]) -> dict[str, Any]:
    run_id, repo, fix = run["id"], run["repo"], run["fix"]
    emit = emitter(store, run_id, "agent_ready")
    slug = parse_repo(repo)[1].removeprefix("sherpa-demo-")
    await emit("log", message="Adding a catalog feed and PayPal Cart API v1 endpoints")
    root = await clone(repo, fix["branch"])
    try:
        ws = Workspace(root)
        outcome = await run_fixer(
            ws,
            run["audit"]["findings"],
            emit,
            store_type=run.get("store_type", "auto"),
            task=agent_ready_task(),
            checker=agent_ready_check,
        )
        if not ws.changed or not outcome.build_ok:
            raise RuntimeError("The agent-ready changes did not build; nothing was pushed.")
        sha = await github.commit_and_push(
            root,
            fix["branch"],
            "feat(agent-ready): add catalog feed and PayPal Cart API v1 endpoints",
            paths=outcome.files_changed,
        )
        diff = await github.git(root, "show", "--format=", "--no-color", "HEAD")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    await github.comment(
        repo,
        fix["pr_number"],
        "## Agent-ready\n\nAdded a catalog feed (`/catalog.json`) and PayPal Cart API v1 endpoints "
        "(`/merchant-cart`) in a separate commit, with contract tests.\n\n"
        f"{outcome.summary}\n\nOpened by Sherpa.",
    )

    service = f"store-{slug}"
    preview_url = (await deploy_preview(repo, fix["branch"], service, f"pr-{fix['pr_number']}", emit)).rstrip(
        "/"
    )
    feed = []
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            feed = (await c.get(f"{preview_url}/catalog.json")).json().get("items", [])
    except Exception as exc:
        await emit("warning", message=f"Catalog feed unreadable: {exc}")
    await emit("catalog", url=f"{preview_url}/catalog.json", count=len(feed), items=feed[:6])
    item_id = feed[0]["id"] if feed else ""
    date = next_weekday(5, min_days=7).isoformat()

    async def on_contract(result: dict[str, Any]) -> None:
        await emit("contract", **result)

    endpoints = await run_contract_tests(
        preview_url,
        item_id,
        [{"type": "DELIVERY_DATE_PREFERENCE", "value": date}],
        on_result=on_contract,
    )
    await emit("log", message=f"Contract tests: {sum(e['ok'] for e in endpoints)}/{len(endpoints)} passed")

    buyer = await run_buyer(preview_url, BUYER_REQUESTS.get(slug, "Buy your best-selling item."), emit)
    return {
        "agent_ready": {
            "preview_url": preview_url,
            "sha": sha,
            "diff": diff[:MAX_DIFF],
            "files_changed": outcome.files_changed,
            "summary": outcome.summary,
            "catalog_preview": feed[:3],
            "endpoints": endpoints,
            "transcript": buyer["transcript"],
            "order": buyer["order"],
            "pr_url": fix["pr_url"],
        }
    }


@dataclass(frozen=True)
class Stage:
    name: str
    requires: tuple[str, ...]
    job: Callable[[RunStore, dict[str, Any]], Awaitable[dict[str, Any]]]


STAGES: dict[str, Stage] = {
    "audit": Stage("audit", (), audit_job),
    "fix": Stage("fix", ("audit", "repo"), fix_job),
    "verify": Stage("verify", ("fix",), verify_job),
    "agent-ready": Stage("agent_ready", ("fix",), agent_ready_job),
}
