"""Detection benchmark: plant known PayPal flaws in a fixed store and check Sherpa reports exactly those.

The base is real code written by Sherpa's own fixer (bench/ember_fixed.json), which passes every check. Each flaw
operator reintroduces one real-world problem with a small text change. A variant passes when the findings from
Sherpa's source checks equal the planted flaws: nothing missed (recall) and nothing extra (precision).

Scope: the deterministic source checks (SDK version, Venmo, Pay Later, server pricing, webhooks, error handling,
payment gate and the PayPal production practices). Browser-only checks, such as button placement on a phone, need
real shoppers and are measured by the live runs instead.

Run: python bench/detection.py   (prints a Markdown table; no network, no model calls)
"""

from __future__ import annotations

import itertools
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sherpa.audit import static_checks as sc
from sherpa.audit.rubric import AuditEvidence, DeviceEvidence, score

BASE = json.loads((Path(__file__).parent / "ember_fixed.json").read_text(encoding="utf-8"))["files"]
DEVICE_CODES = {"NO_CATALOG_FEED", "NO_CART_API"}  # agent readiness is probed over HTTP, not read from source


@dataclass(frozen=True)
class Flaw:
    code: str
    what: str
    edits: tuple[tuple[str, str], ...]  # (regex, replacement) applied to every file
    insert: tuple[str, str, str] | None = None  # (file, anchor regex, text inserted after the anchor)


FLAWS = [
    Flaw(
        "SDK_LEGACY",
        "Load the legacy v5 SDK (with Venmo enabled) instead of v6",
        (
            (
                r"https://www\.sandbox\.paypal\.com/web-sdk/v6/core",
                "https://www.paypal.com/sdk/js?client-id=sb&currency=USD&enable-funding=venmo",
            ),
            (r"web-sdk/v6/core", "sdk/js?client-id=sb&enable-funding=venmo"),
        ),
    ),
    Flaw(
        "NO_VENMO",
        "Remove the Venmo button (and turn Venmo off in a v5 script)",
        (
            (r"(?i)venmo-button|createVenmoOneTimePaymentSession|VenmoButton", "removed-x"),
            (r"enable-funding=venmo", "disable-funding=venmo"),
        ),
    ),
    Flaw(
        "NO_PAY_LATER",
        "Remove Pay Later messaging",
        ((r"(?i)paypal-message|createPayPalMessages|data-pp-message", "removed-msg"),),
    ),
    Flaw(
        "AMOUNT_FROM_CLIENT",
        "Trust a total sent by the browser",
        (),
        ("server.js", r"const \{ items \} = req\.body \|\| \{\};", "\n    const { total } = req.body;"),
    ),
    Flaw(
        "WEBHOOK_UNVERIFIED",
        "Stop verifying webhook signatures",
        ((r"verify-webhook-signature", "verify-nothing"), (r"verifyWebhookSignature", "skipCheck")),
    ),
    Flaw(
        "BLANK_PAGE_ON_ERROR",
        "Blank the page when payment fails",
        (),
        (
            "views/cart.html",
            r"<script>",
            '\n  window.onPaymentError = () => { document.body.innerHTML = ""; };',
        ),
    ),
    Flaw(
        "EXTRA_CLICK",
        "Hide PayPal behind a 'Choose payment method' click",
        (),
        ("views/cart.html", r"<body[^>]*>", '\n<button id="gate">Choose payment method</button>'),
    ),
    Flaw(
        "DECLINED_NOT_RECOVERED",
        "Drop INSTRUMENT_DECLINED recovery",
        ((r"INSTRUMENT_DECLINED", "SOME_ERROR"),),
    ),
    Flaw(
        "REQUESTS_NOT_IDEMPOTENT",
        "Drop PayPal-Request-Id headers",
        ((r"(?i)PayPal-Request-Id|paypalRequestId", "X-Trace-Id"),),
    ),
    Flaw(
        "PENDING_TREATED_AS_PAID", "Treat PENDING captures as paid", ((r"([\"'`])PENDING\1", r"\1ON_HOLD\1"),)
    ),
    Flaw(
        "WEBHOOK_NOT_DEDUPED",
        "Process repeated webhook deliveries again",
        (
            (r"processedEvents", "eventLog"),
            (r"(?i)duplicate", "repeat"),
            (r"(?i)already\s+(processed|handled|seen)", "done before"),
        ),
    ),
]


def plant(flaws: list[Flaw]) -> dict[str, str]:
    files = dict(BASE)
    for f in sorted(flaws, key=FLAWS.index):  # a fixed order, so flaws compose the same way every time
        if f.insert:
            path, anchor, text = f.insert
            new, n = re.subn(anchor, lambda m, t=text: m.group(0) + t, files[path], count=1)
            if not n:
                raise ValueError(f"{f.code}: anchor not found in {path}")
            files[path] = new
        hits = 0
        for pattern, repl in f.edits:
            hits += sum(len(re.findall(pattern, t)) for t in files.values())
            files = {k: re.sub(pattern, repl, t) for k, t in files.items()}
        if f.edits and not hits:
            raise ValueError(f"{f.code}: none of its patterns are in the base, so nothing was planted")
    return files


def findings(files: dict[str, str]) -> set[str]:
    """Score source evidence only: devices are perfect, so every finding comes from the code."""
    sdk = sc.detect_sdk_in_source(files)
    corpus = "\n".join(files.values())
    good = DeviceEvidence(
        reached_payment=True, payment_completed=True, paypal_present=True, paypal_above_fold=True
    )
    ev = AuditEvidence(
        sdk=sdk,
        pay_later=sc.has_pay_later(corpus),
        venmo=sc.has_venmo(sdk, corpus),
        probes=sc.ProbeResult(),
        desktop=good,
        mobile=good,
        server=sc.analyze_source(files),
    )
    return {f.code for f in score(ev).findings} - DEVICE_CODES


def variants(seed: int = 7, random_count: int = 60) -> list[list[Flaw]]:
    singles = [[f] for f in FLAWS]
    pairs = [list(p) for p in itertools.combinations(FLAWS, 2)]
    rng = random.Random(seed)
    mixes = [rng.sample(FLAWS, rng.randint(3, 6)) for _ in range(random_count)]
    return singles + pairs + mixes


def run() -> dict:
    base = findings(dict(BASE))
    per_flaw = defaultdict(lambda: {"planted": 0, "found": 0})
    exact = extra = 0
    rows = variants()
    for flaws in rows:
        expected = {f.code for f in flaws}
        got = findings(plant(flaws))
        exact += got == expected
        extra += bool(got - expected)
        for f in flaws:
            per_flaw[f.code]["planted"] += 1
            per_flaw[f.code]["found"] += f.code in got
    planted = sum(v["planted"] for v in per_flaw.values())
    found = sum(v["found"] for v in per_flaw.values())
    return {
        "base_findings": sorted(base),
        "variants": len(rows),
        "exact_match": exact,
        "variants_with_false_alarms": extra,
        "recall": round(found / planted, 4),
        "per_flaw": {k: dict(v) for k, v in per_flaw.items()},
    }


def markdown(r: dict) -> str:
    lines = [
        f"- Variants: **{r['variants']}** ({len(FLAWS)} single flaws, every pair, and random mixes of 3–6)",
        f"- Exactly the planted flaws reported: **{r['exact_match']} / {r['variants']}**",
        f"- Variants with a false alarm: **{r['variants_with_false_alarms']}**",
        f"- Recall over all planted flaws: **{r['recall']:.1%}**",
        f"- Findings on the unmodified base: {r['base_findings'] or 'none'}",
        "",
        "| Flaw | What changes | Planted | Found |",
        "|---|---|---|---|",
    ]
    for f in FLAWS:
        v = r["per_flaw"][f.code]
        lines.append(f"| `{f.code}` | {f.what} | {v['planted']} | {v['found']} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(markdown(run()))
