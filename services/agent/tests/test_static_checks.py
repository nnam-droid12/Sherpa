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


def test_tests_that_quote_old_code_are_not_store_behaviour():
    # A fixer-written regression test names the blank-page code it guards against.
    files = {
        "views/cart.html": '<div role="alert">Payment failed, try again</div>',
        "test/store.test.js": "assert.ok(!html.includes('document.body.innerHTML = \"\"'));",
        "src/cart.spec.ts": "const { total } = req.body;",
    }
    s = sc.analyze_source(files)
    assert s.blank_page_on_error is False
    assert s.amount_from_client is False
    assert s.graceful_errors is True


def test_paypal_resilience_signals():
    server = {
        "server.js": (
            'await fetch(`${base}/v2/checkout/orders/${id}/capture`, {headers: {"PayPal-Request-Id": randomUUID()}});\n'
            'if (issue === "INSTRUMENT_DECLINED") return res.status(422).json({ retry: true });\n'
            'if (capture.status === "PENDING") return res.json({ pending: true });'
        ),
        "routes/webhooks.js": (
            "await verifyWebhookSignature(req);\n"
            "if (processedEvents.has(event.id)) return res.sendStatus(200);\n"
            "processedEvents.add(event.id);"
        ),
    }
    s = sc.analyze_source(server)
    assert s.calls_orders_api and s.declined_recovery and s.idempotent_requests and s.pending_handled
    assert s.webhook_deduped


def test_logging_an_event_id_is_not_deduplication():
    s = sc.analyze_source({"routes/webhooks.js": "verifyWebhookSignature(); console.log(event.id);"})
    assert s.webhook_deduped is False


def test_resilience_needs_server_orders_calls():
    s = sc.analyze_source({"public/app.js": "paypal.Buttons({ onApprove: (d, a) => a.order.capture() })"})
    assert s.calls_orders_api is False


def test_official_server_sdk_counts_as_orders_calls():
    # PayPal's own standard-integration sample uses @paypal/paypal-server-sdk, not raw REST URLs.
    s = sc.analyze_source(
        {
            "server.js": "const ordersController = new OrdersController(client);\nawait ordersController.createOrder(collect);"
        }
    )
    assert s.calls_orders_api and not s.idempotent_requests
    s = sc.analyze_source(
        {"server.js": "await ordersController.captureOrder({ id, paypalRequestId: randomUUID() });"}
    )
    assert s.calls_orders_api and s.idempotent_requests


def test_v5_buttons_message_option_is_pay_later():
    assert sc.has_pay_later("paypal.Buttons({ style: {}, message: { amount: 100 }, createOrder() {} })")
    assert not sc.has_pay_later("resultMessage(`Sorry, your transaction could not be processed`)")


def test_paypal_sample_error_message_counts_as_error_ui():
    s = sc.analyze_source({"app.js": "resultMessage(`Sorry, your transaction could not be processed...`)"})
    assert s.graceful_errors is True


def test_message_objects_outside_paypal_buttons_are_not_pay_later():
    assert not sc.has_pay_later('showToast({ message: { text: "Saved", amount: 3 } })')
    sample = (
        'window.paypal.Buttons({ style: { shape: "rect", layout: "vertical" }, message: { amount: 100 } })'
    )
    assert sc.has_pay_later(sample)
