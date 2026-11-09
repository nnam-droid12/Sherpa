from pathlib import Path

from sherpa.audit import static_checks as sc
from sherpa.audit.findings import apply_defaults
from sherpa.audit.rubric import WEIGHTS, AuditEvidence, DeviceEvidence, device_evidence_from_probes, score

STORES = Path(__file__).resolve().parents[3] / "demo-stores"

EMBER_OAK_CODES = {
    "SDK_LEGACY",  # EO-1
    "BUTTON_BELOW_FOLD_DESKTOP",  # EO-2
    "NO_PAY_LATER",  # EO-3
    "NO_VENMO",  # EO-4
    "BUTTON_HIDDEN_MOBILE",  # EO-5
    "AMOUNT_FROM_CLIENT",  # EO-6
    "WEBHOOK_UNVERIFIED",  # EO-7
    "BLANK_PAGE_ON_ERROR",  # EO-8
    "NO_CATALOG_FEED",  # EO-9
    "NO_CART_API",  # EO-9
}
LUMEN_CODES = {
    "SDK_LEGACY",  # LB-1
    "EXTRA_CLICK",  # LB-2
    "CHECKOUT_CRASH",  # LB-3
    "NO_CATALOG_FEED",  # LB-4
    "NO_CART_API",  # LB-5
    "WEBHOOK_MISSING",  # LB-6
    "NO_VENMO",  # LB-7
    "NO_PAY_LATER",  # LB-7
}


def _probe(**kw):
    base = {
        "url": "https://x/cart",
        "viewport_height": 900,
        "candidates": [],
        "crashed": False,
        "blank": False,
        "payment_gate": False,
        "pay_later_message": False,
        "paypal_present": False,
        "paypal_visible": False,
        "above_fold": False,
    }
    base.update(kw)
    return base


def _evidence(store, desktop, mobile):
    files = sc.read_source_tree(STORES / store)
    sdk = sc.detect_sdk_in_source(files)
    corpus = "\n".join(files.values())
    return AuditEvidence(
        sdk=sdk,
        pay_later=sc.has_pay_later(corpus),
        venmo=sc.has_venmo(sdk, corpus),
        probes=sc.ProbeResult(),
        desktop=desktop,
        mobile=mobile,
        server=sc.analyze_source(files),
    )


def test_ember_oak_baseline_finds_every_planted_flaw():
    desktop = device_evidence_from_probes(
        [_probe(paypal_present=True, paypal_visible=True, above_fold=False)], reached=True, completed=True
    )
    mobile = device_evidence_from_probes(
        [_probe(paypal_present=True, paypal_visible=False)], reached=False, completed=False
    )
    result = score(_evidence("ember-oak", desktop, mobile))
    codes = {f.code for f in result.findings}
    assert EMBER_OAK_CODES <= codes
    assert result.total < 45


def test_lumen_baseline_finds_every_planted_flaw():
    desktop = device_evidence_from_probes(
        [_probe(payment_gate=True), _probe(paypal_present=True, paypal_visible=True, above_fold=True)],
        reached=True,
        completed=True,
    )
    mobile = device_evidence_from_probes([_probe(crashed=True)], reached=False, completed=False)
    result = score(_evidence("lumen-bakehouse", desktop, mobile))
    codes = {f.code for f in result.findings}
    assert LUMEN_CODES <= codes
    assert result.total < 45


def test_fixed_store_scores_high():
    sdk = sc.SdkInfo(version="v6", script_urls=["https://www.sandbox.paypal.com/web-sdk/v6/core"])
    good = DeviceEvidence(
        reached_payment=True, payment_completed=True, paypal_present=True, paypal_above_fold=True
    )
    server = sc.ServerSignals(
        amount_from_client=False,
        webhook_signature_verified=True,
        blank_page_on_error=False,
        graceful_errors=True,
        payment_gated=False,
    )
    probes = sc.ProbeResult(catalog_feed="/catalog.json", catalog_items=6, cart_api={"present": True})
    result = score(
        AuditEvidence(
            sdk=sdk, pay_later=True, venmo=True, probes=probes, desktop=good, mobile=good, server=server
        )
    )
    assert result.total == sum(WEIGHTS.values()) == 100
    assert result.findings == []


def test_score_is_deterministic():
    desktop = device_evidence_from_probes(
        [_probe(paypal_present=True, paypal_visible=True)], reached=True, completed=False
    )
    mobile = DeviceEvidence(ran=False)
    totals = {score(_evidence("ember-oak", desktop, mobile)).total for _ in range(3)}
    assert len(totals) == 1


def test_every_code_has_default_wording():
    desktop = device_evidence_from_probes(
        [_probe(paypal_present=True, paypal_visible=True)], reached=True, completed=True
    )
    mobile = device_evidence_from_probes([_probe(paypal_present=True)], reached=False, completed=False)
    result = score(_evidence("ember-oak", desktop, mobile))
    apply_defaults(result.findings)
    assert all(f.impact and f.fix for f in result.findings)


RESILIENCE_CODES = {"DECLINED_NOT_RECOVERED", "REQUESTS_NOT_IDEMPOTENT", "PENDING_TREATED_AS_PAID"}


def _fixed(**server_kw):
    sdk = sc.SdkInfo(version="v6", script_urls=["https://www.sandbox.paypal.com/web-sdk/v6/core"])
    good = DeviceEvidence(
        reached_payment=True, payment_completed=True, paypal_present=True, paypal_above_fold=True
    )
    server = sc.ServerSignals(
        amount_from_client=False,
        webhook_signature_verified=True,
        blank_page_on_error=False,
        graceful_errors=True,
        payment_gated=False,
        calls_orders_api=True,
        evidence={"orders_api": "server.js", "webhook_signature_verified": "server.js"},
        **server_kw,
    )
    probes = sc.ProbeResult(catalog_feed="/catalog.json", catalog_items=6, cart_api={"present": True})
    return score(
        AuditEvidence(
            sdk=sdk, pay_later=True, venmo=True, probes=probes, desktop=good, mobile=good, server=server
        )
    )


def test_resilient_orders_integration_scores_full_marks():
    result = _fixed(
        declined_recovery=True, idempotent_requests=True, pending_handled=True, webhook_deduped=True
    )
    assert result.total == 100 and result.findings == []
    assert result.categories["server_correctness"]["score"] == 20


def test_missing_paypal_practices_cost_six_points():
    result = _fixed(
        declined_recovery=False, idempotent_requests=False, pending_handled=False, webhook_deduped=False
    )
    assert result.total == 94
    assert {f.code for f in result.findings} == RESILIENCE_CODES | {"WEBHOOK_NOT_DEDUPED"}
    apply_defaults(result.findings)
    assert all(f.impact and f.fix for f in result.findings)


def test_broken_demo_stores_lack_paypal_practices():
    desktop = device_evidence_from_probes(
        [_probe(paypal_present=True, paypal_visible=True)], reached=True, completed=True
    )
    mobile = DeviceEvidence(ran=False)
    ember = {f.code for f in score(_evidence("ember-oak", desktop, mobile)).findings}
    lumen = {f.code for f in score(_evidence("lumen-bakehouse", desktop, mobile)).findings}
    assert RESILIENCE_CODES | {"WEBHOOK_NOT_DEDUPED"} <= ember
    # Lumen has no webhook at all, so only WEBHOOK_MISSING is reported, not the dedupe finding.
    assert RESILIENCE_CODES <= lumen and "WEBHOOK_NOT_DEDUPED" not in lumen
