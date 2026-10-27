from pathlib import Path

from sherpa.audit import static_checks as sc

STORES = Path(__file__).resolve().parents[3] / "demo-stores"


def test_ember_oak_source_flaws():
    files = sc.read_source_tree(STORES / "ember-oak")
    sdk = sc.detect_sdk_in_source(files)
    assert sdk.version == "v5"
    assert {"venmo", "paylater"} <= set(sdk.disable_funding)
    server = sc.analyze_source(files)
    assert server.amount_from_client is True
    assert server.webhook_signature_verified is False
    assert "webhook_unverified" in server.evidence
    assert server.blank_page_on_error is True
    assert server.graceful_errors is False
    assert not sc.has_pay_later("\n".join(files.values()))
    assert not sc.has_venmo(sdk, "\n".join(files.values()))


def test_lumen_source_flaws():
    files = sc.read_source_tree(STORES / "lumen-bakehouse")
    sdk = sc.detect_sdk_in_source(files)
    assert sdk.version == "v5"
    server = sc.analyze_source(files)
    assert server.payment_gated is True
    assert server.amount_from_client is False
    assert "webhook_missing" in server.evidence
    assert server.graceful_errors is True


def test_v6_detection():
    html = '<script src="https://www.sandbox.paypal.com/web-sdk/v6/core"></script><paypal-messages></paypal-messages>'
    html += "<venmo-button></venmo-button>"
    sdk = sc.detect_sdk(html)
    assert sdk.version == "v6"
    assert sc.has_pay_later(html)
    assert sc.has_venmo(sdk, html)


def test_verified_webhook_source():
    files = {"server/webhooks.js": "await fetch(`${base}/v1/notifications/verify-webhook-signature`)"}
    s = sc.analyze_source(files)
    assert s.webhook_signature_verified is True
