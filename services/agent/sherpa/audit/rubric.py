"""Deterministic 0–100 checkout score. Weights are documented in docs/SCORECARD.md."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sherpa.audit.static_checks import ProbeResult, SdkInfo, ServerSignals

WEIGHTS = {
    "presentment": 20,
    "payment_options": 15,
    "sdk_modernity": 10,
    "mobile_completion": 15,
    "steps_to_pay": 10,
    "server_correctness": 20,
    "agent_readiness": 10,
}

CATEGORY_LABELS = {
    "presentment": "Presentment",
    "payment_options": "Payment options",
    "sdk_modernity": "SDK modernity",
    "mobile_completion": "Mobile checkout completion",
    "steps_to_pay": "Steps to pay",
    "server_correctness": "Server-side correctness",
    "agent_readiness": "Agent readiness",
}


@dataclass
class DeviceEvidence:
    """What the visual shopper (plus in-page probes) observed on one device."""

    reached_payment: bool = False
    payment_completed: bool = False
    paypal_present: bool = False
    paypal_above_fold: bool = False
    paypal_hidden: bool = False  # in the DOM but clipped or invisible
    payment_gate: bool = False
    crashed: bool = False
    blank_page: bool = False
    order_id: str | None = None
    evidence_shot: str | None = None
    ran: bool = True


@dataclass
class AuditEvidence:
    sdk: SdkInfo
    pay_later: bool
    venmo: bool
    probes: ProbeResult
    desktop: DeviceEvidence
    mobile: DeviceEvidence
    server: ServerSignals | None = None


@dataclass
class Finding:
    code: str
    category: str
    severity: str  # critical | high | medium | low
    title: str
    evidence: dict[str, Any] = field(default_factory=dict)
    impact: str = ""
    fix: str = ""


@dataclass
class Score:
    total: int
    categories: dict[str, dict[str, int]]
    findings: list[Finding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "categories": self.categories,
            "findings": [asdict(f) for f in self.findings],
        }


def device_evidence_from_probes(
    probes: list[dict[str, Any]], *, reached: bool, completed: bool, **kw: Any
) -> DeviceEvidence:
    d = DeviceEvidence(reached_payment=reached, payment_completed=completed, **kw)
    for p in probes:
        if "error" in p:
            continue
        if p.get("paypal_present"):
            d.paypal_present = True
            if p.get("paypal_visible"):
                d.paypal_above_fold = d.paypal_above_fold or bool(p.get("above_fold"))
            else:
                d.paypal_hidden = True
        if p.get("payment_gate") and not p.get("paypal_present"):
            d.payment_gate = True
        d.crashed = d.crashed or bool(p.get("crashed"))
        d.blank_page = d.blank_page or bool(p.get("blank"))
    # Hidden only counts if the button was never visible on that device.
    if d.paypal_hidden and any(p.get("paypal_visible") for p in probes):
        d.paypal_hidden = False
    return d


def score(ev: AuditEvidence) -> Score:
    cats: dict[str, dict[str, int]] = {k: {"score": 0, "max": v} for k, v in WEIGHTS.items()}
    findings: list[Finding] = []

    def add(cat: str, pts: int) -> None:
        cats[cat]["score"] = min(cats[cat]["max"], cats[cat]["score"] + pts)

    def find(finding_code: str, cat: str, sev: str, title: str, **evidence: Any) -> None:
        findings.append(
            Finding(finding_code, cat, sev, title, {k: v for k, v in evidence.items() if v is not None})
        )

    d, m = ev.desktop, ev.mobile

    # Presentment
    if d.paypal_above_fold:
        add("presentment", 10)
    elif d.paypal_present or d.reached_payment:
        find(
            "BUTTON_BELOW_FOLD_DESKTOP",
            "presentment",
            "high",
            "PayPal button sits below the fold on desktop",
            screenshot=d.evidence_shot,
        )
    if m.paypal_above_fold:
        add("presentment", 10)
    elif m.paypal_present and not m.paypal_hidden:
        find(
            "BUTTON_BELOW_FOLD_MOBILE",
            "presentment",
            "high",
            "PayPal button sits below the fold on mobile",
            screenshot=m.evidence_shot,
        )

    # Payment options
    if ev.sdk.version != "none" or d.reached_payment or m.reached_payment:
        add("payment_options", 5)
    else:
        find("NO_PAYPAL", "payment_options", "critical", "PayPal is not offered at checkout")
    if ev.venmo:
        add("payment_options", 5)
    else:
        find(
            "NO_VENMO",
            "payment_options",
            "medium",
            "Venmo is not offered to US shoppers",
            script=", ".join(ev.sdk.script_urls[:1]) or None,
            disabled="venmo" in ev.sdk.disable_funding,
        )
    if ev.pay_later:
        add("payment_options", 5)
    else:
        find(
            "NO_PAY_LATER",
            "payment_options",
            "medium",
            "No Pay Later messaging on eligible items",
            disabled="paylater" in ev.sdk.disable_funding,
        )

    # SDK modernity
    if ev.sdk.version == "v6":
        add("sdk_modernity", 10)
    elif ev.sdk.version == "v5":
        find(
            "SDK_LEGACY",
            "sdk_modernity",
            "high",
            "Checkout uses the legacy PayPal JS SDK (v5)",
            script=ev.sdk.script_urls[0] if ev.sdk.script_urls else None,
        )

    # Mobile checkout completion
    if m.reached_payment:
        add("mobile_completion", 7)
    if m.payment_completed:
        add("mobile_completion", 8)
    if m.ran and m.paypal_hidden:
        find(
            "BUTTON_HIDDEN_MOBILE",
            "mobile_completion",
            "critical",
            "The PayPal button is hidden on phone-sized screens",
            screenshot=m.evidence_shot,
        )
    elif m.ran and not m.payment_completed and not m.crashed:
        find(
            "MOBILE_PAYMENT_FAILED",
            "mobile_completion",
            "high",
            "A shopper could not finish paying on mobile",
            screenshot=m.evidence_shot,
        )

    # Steps to pay
    gated = d.payment_gate or m.payment_gate or bool(ev.server and ev.server.payment_gated)
    crashed = d.crashed or m.crashed
    if crashed:
        find(
            "CHECKOUT_CRASH",
            "steps_to_pay",
            "critical",
            "Checkout crashes before the shopper can pay",
            screenshot=(m if m.crashed else d).evidence_shot,
        )
    else:
        add("steps_to_pay", 10 - (5 if gated else 0))
    if gated:
        find(
            "EXTRA_CLICK",
            "steps_to_pay",
            "high",
            "PayPal is hidden behind an extra 'choose payment method' click",
            code=ev.server.evidence.get("payment_gated") if ev.server else None,
        )

    # Server-side correctness
    s = ev.server
    if s is not None:
        if s.amount_from_client:
            find(
                "AMOUNT_FROM_CLIENT",
                "server_correctness",
                "critical",
                "Order amount is taken from the browser and never verified",
                code=s.evidence.get("amount_from_client"),
            )
        else:
            add("server_correctness", 8)
        if s.webhook_signature_verified:
            add("server_correctness", 7)
        elif "webhook_unverified" in s.evidence:
            find(
                "WEBHOOK_UNVERIFIED",
                "server_correctness",
                "high",
                "Webhook events are accepted without verifying PayPal's signature",
                code=s.evidence["webhook_unverified"],
            )
        else:
            find("WEBHOOK_MISSING", "server_correctness", "high", "No PayPal webhook endpoint")
        if s.blank_page_on_error:
            find(
                "BLANK_PAGE_ON_ERROR",
                "server_correctness",
                "high",
                "A failed payment leaves the shopper on a blank page",
                code=s.evidence.get("blank_page_on_error"),
            )
        elif s.graceful_errors:
            add("server_correctness", 5)
        else:
            find(
                "NO_ERROR_HANDLING",
                "server_correctness",
                "medium",
                "Payment errors are not shown to the shopper",
            )
    else:
        if ev.probes.webhook_endpoint:
            add("server_correctness", 3)
        else:
            find("WEBHOOK_MISSING", "server_correctness", "high", "No PayPal webhook endpoint")
        if d.payment_completed:
            add("server_correctness", 5)

    # Agent readiness
    if ev.probes.catalog_feed:
        add("agent_readiness", 4)
    else:
        find("NO_CATALOG_FEED", "agent_readiness", "medium", "No machine-readable product catalog feed")
    if ev.probes.cart_api.get("present"):
        add("agent_readiness", 6)
    else:
        find(
            "NO_CART_API", "agent_readiness", "medium", "No PayPal Cart API endpoints for AI shopping agents"
        )

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (order[f.severity], f.category))
    total = sum(c["score"] for c in cats.values())
    return Score(total=total, categories=cats, findings=findings)
