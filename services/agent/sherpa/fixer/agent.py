"""Gemini coding agent that fixes a store's PayPal integration inside a temp clone."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from google.genai import types

from sherpa.audit import static_checks as sc
from sherpa.config import get_settings
from sherpa.fixer.tools import ToolError, Workspace, declarations
from sherpa.llm import generate

log = logging.getLogger(__name__)

Emit = Callable[..., Awaitable[Any]]

REFERENCES_URL = (
    "https://raw.githubusercontent.com/paypal/AI-Toolkit/main/skills/paypal-best-practices/references/{}.md"
)
REFERENCE_FILES = ("js-sdk-v6", "checkout", "venmo", "bnpl", "webhooks")
_reference_cache: dict[str, str] = {}

SYSTEM = """You are Sherpa, a senior PayPal integration engineer. You fix a merchant's checkout by editing their \
repository with the tools provided. You work carefully: read before you write, keep the store's look and structure, \
and make the smallest set of changes that fully fixes each problem. Never touch secrets or .env files, never hardcode \
credentials, and keep everything on the PayPal sandbox (https://api-m.sandbox.paypal.com and \
https://www.sandbox.paypal.com/web-sdk/v6/core). Do not add new npm dependencies unless there is no other way. Run \
run_build after your changes and fix any failures. Call finish only when every required fix is done and the build \
passes."""

REQUIRED_FIXES = """Required fixes (each one will be checked):
1. Migrate to PayPal JS SDK v6. Load `<script async src="https://www.sandbox.paypal.com/web-sdk/v6/core">`, create \
the instance with `window.paypal.createInstance({ clientId, components: ["paypal-payments", "venmo-payments", \
"paypal-messages"], pageType: "checkout" })`, call `findEligibleMethods({ currencyCode: "USD" })`, render \
`<paypal-button>` / `<venmo-button>` web components and start sessions with \
`createPayPalOneTimePaymentSession` / `createVenmoOneTimePaymentSession` using `session.start({ presentationMode: \
"auto" }, createOrder())` where createOrder() returns a Promise of `{ orderId }`. Remove every legacy \
`paypal.com/sdk/js` script and `paypal.Buttons` call. Use the client ID the server already exposes to the page \
(clientId mode, not clientToken).
2. Render the PayPal and Venmo buttons above the fold on the cart/checkout page, right next to the order total. If \
PayPal is hidden behind an extra click (for example "Choose payment method"), remove that gate so the buttons render \
immediately on that step.
3. Offer Venmo for eligible US buyers and show Pay Later messaging with `<paypal-message auto-bootstrap amount="..." \
currency-code="USD">` on product and cart/checkout pages (after `sdkInstance.createPayPalMessages()`).
4. Fix mobile and checkout bugs: payment buttons must be visible at 390px wide, and no step may crash when optional \
fields are empty.
5. Compute the order amount on the server from the server-side catalog (product ids and quantities only) before \
creating the order, and never trust a total sent by the browser. Verify the captured amount matches.
6. Add `POST /api/webhooks/paypal` that verifies every event with PayPal's \
`POST /v1/notifications/verify-webhook-signature` (using the PAYPAL_WEBHOOK_ID env var and the PAYPAL-* headers), \
rejects unverified events with 400, and handles PAYMENT.CAPTURE.COMPLETED, PAYMENT.CAPTURE.DENIED and \
CHECKOUT.ORDER.APPROVED.
7. Handle failures gracefully: on a declined or failed payment (including INSTRUMENT_DECLINED) show a visible message \
in an element with role="alert" and a "Try again" path; never blank the page.
8. Recover from declined funding: when the capture response from PayPal is INSTRUMENT_DECLINED (check the error's details[].issue), return a clear response so the page shows a role="alert" message and lets the buyer choose another payment method (start a new payment session), instead of ending the checkout.
9. Make PayPal calls retry-safe: send a unique `PayPal-Request-Id` header (crypto.randomUUID()) on every POST to /v2/checkout/orders and /v2/checkout/orders/{id}/capture.
10. Treat a capture whose status is "PENDING" as not yet paid: only mark the order paid for a "COMPLETED" capture and tell the buyer a PENDING payment is being reviewed.
11. Deduplicate webhooks: keep a `processedEvents` Set of event ids, and when `processedEvents.has(event.id)` return 200 without processing the event again.
Do not add a catalog feed or Cart API endpoints in this change; a separate agent-ready step does that."""


@dataclass
class FixOutcome:
    summary: str = ""
    changes: list[dict[str, Any]] = field(default_factory=list)
    build_ok: bool = False
    tool_calls: int = 0
    model_calls: int = 0
    files_changed: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    seconds: float = 0.0


MAX_FILE_EVENT = 30_000
PRELOAD_BYTES = 150_000


async def emit_file(emit: Emit, ws: Workspace, path: str, action: str, before: str | None) -> None:
    """Stream the file the agent is working on so the console can show its code, or a diff of an edit."""
    after = ws.peek(path)
    if after is None:
        return
    rel = path.replace("\\", "/").lstrip("/")
    diff = ""
    if action != "read":
        lines = difflib.unified_diff(
            (before or "").splitlines(), after.splitlines(), f"a/{rel}", f"b/{rel}", lineterm="", n=3
        )
        diff = f"diff --git a/{rel} b/{rel}\n" + "\n".join(lines)
    await emit(
        "file",
        path=rel,
        action=action,
        content=after[:MAX_FILE_EVENT],
        truncated=len(after) > MAX_FILE_EVENT,
        diff=diff[:MAX_FILE_EVENT],
    )


async def load_references() -> str:
    if not _reference_cache:
        async with httpx.AsyncClient(timeout=20) as c:
            for name in REFERENCE_FILES:
                try:
                    r = await c.get(REFERENCES_URL.format(name))
                    if r.status_code == 200:
                        _reference_cache[name] = r.text
                except httpx.HTTPError:
                    log.warning("could not fetch reference %s", name)
    return "\n\n".join(f"### Reference: {k}.md\n{v}" for k, v in _reference_cache.items())


def self_check(ws: Workspace) -> list[str]:
    """Deterministic acceptance checks on the edited source. Returns problems still present."""
    files = sc.read_source_tree(ws.root)
    corpus = "\n".join(files.values())
    sdk = sc.detect_sdk_in_source(files)
    server = sc.analyze_source(files)
    problems = []
    if sdk.version != "v6" or sc.LEGACY_SDK_RE.search(corpus):
        problems.append("The legacy SDK is still referenced; every page must use web-sdk/v6/core only.")
    if not sc.has_venmo(sdk, corpus):
        problems.append(
            "Venmo is not offered (expected a <venmo-button> and createVenmoOneTimePaymentSession)."
        )
    if not sc.has_pay_later(corpus):
        problems.append("Pay Later messaging (<paypal-message>) is missing.")
    if server.amount_from_client:
        problems.append(
            f"The server still uses a client-supplied total ({server.evidence.get('amount_from_client')})."
        )
    if not server.webhook_signature_verified:
        problems.append("No webhook handler calls /v1/notifications/verify-webhook-signature.")
    if server.blank_page_on_error or not server.graceful_errors:
        problems.append(
            'Payment errors must show a role="alert" message with a retry path, never a blank page.'
        )
    if server.payment_gated:
        problems.append("PayPal is still behind a 'Choose payment method' click.")
    if server.calls_orders_api:
        if not server.declined_recovery:
            problems.append(
                "INSTRUMENT_DECLINED from capture is not handled with a choose-another-method path."
            )
        if not server.idempotent_requests:
            problems.append("PayPal order create/capture calls do not send a PayPal-Request-Id header.")
        if not server.pending_handled:
            problems.append('A "PENDING" capture status is not distinguished from "COMPLETED".')
    if server.webhook_signature_verified and not server.webhook_deduped:
        problems.append("The webhook handler does not skip event ids it has already processed.")
    return problems


async def run_fixer(
    ws: Workspace,
    findings: list[dict[str, Any]],
    emit: Emit,
    *,
    store_type: str = "auto",
    task: str | None = None,
    checker: Callable[[Workspace], list[str]] | None = self_check,
    max_tool_calls: int = 80,
    max_seconds: int = 2700,
) -> FixOutcome:
    settings = get_settings()
    started = time.monotonic()
    outcome = FixOutcome()
    if settings.env != "test":
        ws.prewarm()  # npm install runs while the agent plans, so the first build doesn't wait for it
    references = await load_references()
    tree = ws.list_dir(".")
    # Hand the agent the whole (small) store up front: reading files one call at a time, each with
    # high thinking, was most of the fixer's wall-clock time.
    sources = sc.read_source_tree(ws.root, max_bytes=PRELOAD_BYTES)
    sources.pop("package-lock.json", None)
    preloaded = "\n\n".join(f"### {path}\n```\n{text}\n```" for path, text in sources.items())
    for path in sources:
        await emit_file(emit, ws, path, "read", None)
    prompt = (
        f"{task or REQUIRED_FIXES}\n\n"
        f"Store type hint: {store_type}. Files in the store directory:\n{tree}\n\n"
        "The current contents of every source file are included below, so you do not need to read them "
        "again; make several edits per turn where you can.\n\n"
        f"{preloaded}\n\n"
        f"Audit findings (JSON):\n{json.dumps(findings, indent=1)[:12000]}\n\n"
        f"PayPal best-practice references (authoritative):\n{references[:60000]}"
    )
    history: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        tools=[types.Tool(function_declarations=declarations())],
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    nudges = 0
    rejections = 0
    await emit(
        "log",
        message=f"Fixer started on {len(findings)} findings with {len(_reference_cache)} PayPal references.",
    )

    while outcome.tool_calls < max_tool_calls and time.monotonic() - started < max_seconds:
        response = await generate(settings.gemini_model, history, config)
        outcome.model_calls += 1
        cand = response.candidates[0] if response.candidates else None
        if not cand or not cand.content or not cand.content.parts:
            nudges += 1
            if nudges > 3:
                break
            history.append(types.Content(role="user", parts=[types.Part(text="Continue using the tools.")]))
            continue
        history.append(cand.content)
        text = " ".join(p.text for p in cand.content.parts if p.text and not p.thought).strip()
        if text:
            await emit("log", message=text[:600])
        calls = [p.function_call for p in cand.content.parts if p.function_call]
        if not calls:
            nudges += 1
            if nudges > 3:
                break
            history.append(
                types.Content(
                    role="user", parts=[types.Part(text="Continue with tool calls; call finish when done.")]
                )
            )
            continue

        replies: list[types.Part] = []
        finished = False
        for call in calls:
            outcome.tool_calls += 1
            args = dict(call.args or {})
            target = args.get("path") or args.get("pattern") or ""
            await emit("tool", tool=call.name, target=str(target)[:120])
            try:
                if call.name == "list_dir":
                    result = ws.list_dir(args.get("path", "."))
                elif call.name == "read_file":
                    result = ws.read_file(args["path"], args.get("start_line"), args.get("end_line"))
                    await emit_file(emit, ws, args["path"], "read", None)
                elif call.name == "search_code":
                    result = ws.search_code(args["pattern"], args.get("path_glob"))
                elif call.name == "write_file":
                    before = ws.peek(args["path"])
                    result = ws.write_file(args["path"], args["content"])
                    await emit_file(emit, ws, args["path"], "create" if before is None else "edit", before)
                elif call.name == "apply_patch":
                    before = ws.peek(args["path"])
                    result = ws.apply_patch(args["path"], args["old"], args["new"])
                    await emit_file(emit, ws, args["path"], "edit", before)
                elif call.name == "run_build":
                    result = await ws.run_build()
                    await emit(
                        "log", message="Build passed." if ws.last_build_ok else "Build failed; fixing."
                    )
                elif call.name == "finish":
                    problems = []
                    if ws.last_build_ok is not True:
                        problems.append("Run run_build after your last change; it must pass before finish.")
                    if checker and not problems:
                        problems = checker(ws)
                    if problems and rejections < 3:
                        rejections += 1
                        await emit(
                            "log", message=f"Self-check found {len(problems)} open item(s); continuing."
                        )
                        result = "Not finished yet:\n- " + "\n- ".join(problems)
                    else:
                        outcome.summary = str(args.get("summary", ""))
                        outcome.changes = list(args.get("changes") or [])
                        outcome.unresolved = problems
                        finished = True
                        result = "ok"
                else:
                    result = f"unknown tool {call.name}"
            except ToolError as exc:
                result = f"error: {exc}"
            except KeyError as exc:
                result = f"error: missing argument {exc}"
            replies.append(
                types.Part(
                    function_response=types.FunctionResponse(name=call.name, response={"result": result})
                )
            )
        history.append(types.Content(role="user", parts=replies))
        if finished:
            break
        await asyncio.sleep(0)

    outcome.build_ok = ws.last_build_ok is True
    outcome.files_changed = sorted(ws.changed)
    outcome.seconds = round(time.monotonic() - started, 1)
    if not outcome.summary:
        outcome.summary = "Sherpa stopped before calling finish; review the changes carefully."
    return outcome
