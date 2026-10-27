"""Plain-English wording for findings, written by Gemini with structured output.

The model only phrases impact and fix. Codes, severities and scores stay deterministic.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.genai import types
from pydantic import BaseModel

from sherpa.audit.rubric import Finding
from sherpa.config import get_settings
from sherpa.llm import generate

log = logging.getLogger(__name__)

DEFAULTS: dict[str, tuple[str, str]] = {
    "SDK_LEGACY": (
        "The legacy SDK misses PayPal's current checkout experiences and eligibility logic, so fewer shoppers see the "
        "options they prefer.",
        "Load JS SDK v6 from /web-sdk/v6/core, create an instance with createInstance, and start one-time payment "
        "sessions from PayPal, Venmo and Pay Later buttons.",
    ),
    "BUTTON_BELOW_FOLD_DESKTOP": (
        "Shoppers have to scroll past unrelated content to find PayPal, which lowers selection and conversion.",
        "Render the PayPal buttons next to the order total at the top of the cart and checkout pages.",
    ),
    "BUTTON_BELOW_FOLD_MOBILE": (
        "On phones the PayPal button is several screens down, so many shoppers never see it.",
        "Place the payment buttons directly under the order summary on small screens.",
    ),
    "BUTTON_HIDDEN_MOBILE": (
        "Phone shoppers cannot pay at all, so every mobile checkout is lost.",
        "Remove the CSS rule that collapses the checkout actions at narrow widths and test at 390px.",
    ),
    "NO_VENMO": (
        "US shoppers who prefer Venmo are not offered it and may abandon checkout.",
        "Enable Venmo through the v6 SDK (venmo-payments component) and show the Venmo button when eligible.",
    ),
    "NO_PAY_LATER": (
        "Shoppers buying higher-priced items are not told they can pay over time, which reduces conversion and "
        "basket size.",
        "Add Pay Later messaging on product and cart pages for eligible amounts using the paypal-messages component.",
    ),
    "NO_PAYPAL": ("Shoppers cannot choose PayPal at all.", "Integrate PayPal checkout with JS SDK v6."),
    "MOBILE_PAYMENT_FAILED": (
        "A real shopper on a phone could not complete a payment.",
        "Walk the mobile checkout end to end and fix whatever blocks the PayPal button or the approval flow.",
    ),
    "CHECKOUT_CRASH": (
        "The checkout breaks before payment, so the order is lost and the shopper loses trust.",
        "Guard against missing optional fields and add tests for the empty case.",
    ),
    "EXTRA_CLICK": (
        "Hiding PayPal behind an extra click adds friction at the moment of purchase.",
        "Render the payment buttons directly on the review step without a 'choose payment method' gate.",
    ),
    "AMOUNT_FROM_CLIENT": (
        "Anyone can change the price in the browser and pay less than the real total.",
        "Recalculate the order total on the server from the catalog and cart before creating and capturing the "
        "order.",
    ),
    "WEBHOOK_UNVERIFIED": (
        "Forged webhook events could mark orders paid or refunded.",
        "Verify every event with POST /v1/notifications/verify-webhook-signature before acting on it.",
    ),
    "WEBHOOK_MISSING": (
        "The store never hears about captures that complete, fail or are reversed after checkout.",
        "Add a webhook endpoint for PAYMENT.CAPTURE.COMPLETED, PAYMENT.CAPTURE.DENIED and CHECKOUT.ORDER.APPROVED, "
        "verifying each signature.",
    ),
    "BLANK_PAGE_ON_ERROR": (
        "When a payment fails the shopper sees an empty page with no way forward.",
        "Show a clear error message and let the shopper retry or choose another payment method.",
    ),
    "NO_ERROR_HANDLING": (
        "Failed payments give no feedback, so shoppers are left guessing.",
        "Handle onError and failed captures with a visible message and a retry path.",
    ),
    "NO_CATALOG_FEED": (
        "AI shopping agents cannot discover what the store sells.",
        "Publish a JSON catalog feed with ids, titles, prices, availability and images.",
    ),
    "NO_CART_API": (
        "AI agents cannot build carts or check out through PayPal on the shopper's behalf.",
        "Implement the PayPal Cart API v1 endpoints (/merchant-cart) wired to PayPal Orders.",
    ),
}


class _Wording(BaseModel):
    code: str
    impact: str
    fix: str


class _WordingList(BaseModel):
    findings: list[_Wording]


def apply_defaults(findings: list[Finding]) -> None:
    for f in findings:
        impact, fix = DEFAULTS.get(f.code, ("", ""))
        f.impact = f.impact or impact
        f.fix = f.fix or fix


async def write_findings(findings: list[Finding], context: dict[str, Any]) -> list[Finding]:
    """Ask Gemini for merchant-friendly wording; fall back to defaults on any failure."""
    apply_defaults(findings)
    if not findings:
        return findings
    prompt = (
        "You are writing an audit report for a small online merchant about their PayPal checkout. For each finding, "
        "write a one-sentence business impact in plain English (no jargon) and a one or two sentence recommended fix "
        "that a developer can act on. Keep the meaning of the draft text; make it specific to this store using the "
        "context. Do not invent facts or numbers.\n\n"
        f"Store context: {json.dumps(context)[:4000]}\n\n"
        "Findings (code, title, evidence, draft impact, draft fix):\n"
        + json.dumps(
            [{"code": f.code, "title": f.title, "evidence": f.evidence, "impact": f.impact, "fix": f.fix} for f in findings]
        )
    )
    try:
        resp = await generate(
            get_settings().gemini_model,
            prompt,
            types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_WordingList,
                temperature=0.2,
            ),
        )
        parsed = resp.parsed if isinstance(resp.parsed, _WordingList) else _WordingList.model_validate_json(resp.text)
        by_code = {w.code: w for w in parsed.findings}
        for f in findings:
            w = by_code.get(f.code)
            if w and w.impact.strip() and w.fix.strip():
                f.impact, f.fix = w.impact.strip(), w.fix.strip()
    except Exception:
        log.warning("finding wording fell back to defaults", exc_info=True)
    return findings
