"""Runs a full audit: static checks, desktop and mobile shoppers, deterministic scoring, findings."""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from sherpa.audit import static_checks as sc
from sherpa.audit.findings import write_findings
from sherpa.audit.rubric import AuditEvidence, DeviceEvidence, device_evidence_from_probes, score
from sherpa.audit.shopper import ShopperResult, run_shopper
from sherpa.gitrepo import clone
from sherpa.store.artifacts import get_artifacts
from sherpa.store.runs import RunStore

log = logging.getLogger(__name__)

HTML_PATHS = ("", "cart", "checkout")


async def retry_browser_failures(
    by_device: dict[str, ShopperResult | None],
    rerun: Callable[[str], Awaitable[ShopperResult]],
    emit: Callable[..., Awaitable[Any]],
) -> None:
    """A cloud-browser failure says nothing about the store, so that device gets exactly one more try."""
    for d, r in list(by_device.items()):
        if r is not None and r.infra_error and not r.payment_completed:
            await emit("log", message=f"The {d} cloud browser disconnected; retrying the {d} shopper once")
            by_device[d] = await rerun(d)


async def fetch_html(store_url: str) -> str:
    pages: list[str] = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        for path in HTML_PATHS:
            try:
                r = await c.get(urljoin(store_url.rstrip("/") + "/", path))
                if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                    pages.append(r.text)
            except httpx.HTTPError:
                continue
    return "\n".join(pages)


def _evidence_shot(result: ShopperResult) -> str | None:
    for step in result.steps:
        p = step.probe
        if p.get("crashed") or p.get("paypal_present") or p.get("payment_gate"):
            return step.shot_id
    return result.steps[-1].shot_id if result.steps else None


def _device(result: ShopperResult | None) -> DeviceEvidence:
    if result is None:
        return DeviceEvidence(ran=False)
    ev = device_evidence_from_probes(
        result.probes,
        reached=result.reached_payment,
        completed=result.payment_completed,
        order_id=(result.completed_order or {}).get("id"),
        evidence_shot=_evidence_shot(result),
    )
    ev.crashed = ev.crashed or result.crashed
    ev.blank_page = ev.blank_page or result.blank_page
    return ev


async def run_audit(
    store: RunStore,
    run_id: str,
    store_url: str,
    *,
    repo: str | None = None,
    branch: str | None = None,
    label: str = "before",
    devices: tuple[str, ...] = ("desktop", "mobile"),
    extra_hosts: set[str] | None = None,
) -> dict[str, Any]:
    artifacts = get_artifacts()

    async def emit(kind: str, **data: Any) -> None:
        await store.add_event(run_id, kind, phase=f"audit:{label}", **data)

    async def save_shot(jpeg: bytes) -> str:
        return await artifacts.put(run_id, jpeg)

    await emit("phase", status="started", store_url=store_url)

    html = await fetch_html(store_url)
    sdk = sc.detect_sdk(html)
    source: dict[str, str] = {}
    server = None
    if repo:
        root = None
        try:
            root = await clone(repo, branch)
            source = sc.read_source_tree(root)
            server = sc.analyze_source(source)
        except Exception as exc:
            await emit("warning", message=f"Could not read the repository: {exc}")
        finally:
            if root:
                shutil.rmtree(root, ignore_errors=True)
    if source and sdk.version == "none":
        # SDKs injected by JS loaders (e.g. in a useEffect) only show up in the source.
        sdk = sc.detect_sdk_in_source(source)
    corpus = html + "\n".join(source.values())
    probes = await sc.probe_endpoints(store_url)
    await emit(
        "static",
        sdk=asdict(sdk),
        probes=asdict(probes),
        server=asdict(server) if server else None,
    )

    results = await asyncio.gather(
        *(run_shopper(store_url, d, emit, extra_hosts=extra_hosts, save_shot=save_shot) for d in devices),  # type: ignore[arg-type]
        return_exceptions=True,
    )
    by_device: dict[str, ShopperResult | None] = {"desktop": None, "mobile": None}
    for d, r in zip(devices, results, strict=True):
        if isinstance(r, BaseException):
            await emit("warning", message=f"{d} shopper failed: {r}")
        else:
            by_device[d] = r
    await retry_browser_failures(
        by_device,
        lambda d: run_shopper(store_url, d, emit, extra_hosts=extra_hosts, save_shot=save_shot),  # type: ignore[arg-type]
        emit,
    )

    probe_pay_later = any(
        p.get("pay_later_message") for r in by_device.values() if r for p in r.probes if "error" not in p
    )
    evidence = AuditEvidence(
        sdk=sdk,
        pay_later=sc.has_pay_later(corpus) or probe_pay_later,
        venmo=sc.has_venmo(sdk, corpus),
        probes=probes,
        desktop=_device(by_device["desktop"]),
        mobile=_device(by_device["mobile"]),
        server=server,
    )
    result = score(evidence)
    await write_findings(
        result.findings, {"store_url": store_url, "host": urlparse(store_url).hostname, "sdk": sdk.version}
    )

    shoppers = {
        d: {
            "reached_payment": r.reached_payment,
            "payment_completed": r.payment_completed,
            "order": r.completed_order,
            "replay_url": r.replay_url,
            "live_view_url": r.live_view_url,
            "summary": r.summary,
            "steps": len(r.steps),
            "model_calls": r.model_calls,
            "seconds": r.seconds,
            "error": r.error,
        }
        for d, r in by_device.items()
        if r
    }
    audit = {
        "label": label,
        "store_url": store_url,
        **result.to_dict(),
        "evidence": {
            "sdk": asdict(sdk),
            "pay_later": evidence.pay_later,
            "venmo": evidence.venmo,
            "desktop": asdict(evidence.desktop),
            "mobile": asdict(evidence.mobile),
            "probes": asdict(probes),
        },
        "shoppers": shoppers,
    }
    await emit("score", total=result.total, categories=result.categories)
    await emit("phase", status="done", total=result.total)
    return audit
