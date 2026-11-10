import httpx
import pytest
import respx

from sherpa.verify import attacks

BEFORE = "https://before.example"
AFTER = "https://after.example"


class FakePayPal:
    configured = True

    def __init__(self, amounts: dict[str, str]):
        self.amounts = amounts

    async def get_order(self, order_id):
        value = self.amounts.get(order_id)
        return {"purchase_units": [{"amount": {"value": value}}]} if value else None


def store(mock, base, *, order_status=201, order_id="O1", webhook_status=200, webhook=True, products=True):
    mock.get(f"{base}/api/products").respond(
        200, json=[{"id": "tent", "price": "349.00"}] if products else []
    )
    mock.post(f"{base}/api/orders").respond(order_status, json={"id": order_id})
    if webhook:
        mock.post(f"{base}/api/webhooks/paypal").respond(webhook_status)
    mock.route(host=base.removeprefix("https://")).respond(404)


@pytest.mark.asyncio
async def test_attacks_succeed_before_and_are_stopped_after():
    paypal = FakePayPal({"BAD": "1.00", "GOOD": "349.00"})
    with respx.mock(assert_all_called=False) as mock:
        store(mock, BEFORE, order_id="BAD", webhook_status=200)
        store(mock, AFTER, order_id="GOOD", webhook_status=400)
        result = await attacks.replay(BEFORE, AFTER, paypal)
    price, webhook = result
    assert price["before"]["verdict"] == "vulnerable" and price["before"]["amount"] == "1.00"
    assert "$349.00" in price["before"]["detail"]
    assert price["after"]["verdict"] == "blocked" and price["after"]["amount"] == "349.00"
    assert webhook["before"]["verdict"] == "vulnerable"
    assert webhook["after"]["verdict"] == "blocked" and webhook["after"]["status"] == 400
    assert attacks.proven(result)


@pytest.mark.asyncio
async def test_forged_webhook_carries_fake_signature_headers():
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{AFTER}/api/webhooks/paypal").respond(400)
        mock.route(host="after.example").respond(404)
        async with httpx.AsyncClient() as c:
            await attacks.forged_webhook(c, AFTER + "/")
    sent = route.calls.last.request
    assert sent.headers["paypal-transmission-sig"] == attacks.FORGED_HEADERS["paypal-transmission-sig"]
    assert b"PAYMENT.CAPTURE.COMPLETED" in sent.content


@pytest.mark.asyncio
async def test_rejected_order_counts_as_blocked_and_missing_routes_are_reported():
    with respx.mock(assert_all_called=False) as mock:
        store(mock, AFTER, order_status=422, webhook=False)
        result = await attacks.replay(None, AFTER, FakePayPal({}))
    price, webhook = result
    assert price["after"]["verdict"] == "blocked" and price["after"]["status"] == 422
    assert webhook["after"]["verdict"] == "missing"
    assert price["before"]["verdict"] == "skipped"
    assert attacks.proven(result)


@pytest.mark.asyncio
async def test_unreadable_order_amount_is_unknown_not_safe():
    with respx.mock(assert_all_called=False) as mock:
        store(mock, AFTER, order_id="NOPE")
        result = await attacks.replay(None, AFTER, FakePayPal({}))
    assert result[0]["after"]["verdict"] == "unknown"
    assert not attacks.proven(result)


@pytest.mark.asyncio
async def test_product_found_from_homepage_links_when_no_feed():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{AFTER}/").respond(200, text='<a href="/cakes/vanilla-bean">Vanilla</a>')
        mock.route(host="after.example").respond(404)
        async with httpx.AsyncClient() as c:
            product = await attacks.find_product(c, AFTER + "/")
    assert product == {"id": "vanilla-bean", "title": None, "price": None}


def test_proven_requires_every_attack_stopped():
    stopped = {"verdict": "blocked"}
    assert attacks.proven([{"after": stopped}, {"after": {"verdict": "missing"}}])
    assert not attacks.proven([{"after": stopped}, {"after": {"verdict": "vulnerable"}}])
    assert not attacks.proven([])


def test_pr_comment_lists_attack_results():
    from sherpa.fixer.pr import scorecard_comment

    rows = [
        {
            "title": "Price tampering",
            "before": {"detail": "PayPal order A was created for $1.00 instead of $349.00."},
            "after": {"detail": "The server ignored the browser's price: PayPal order B is for $349.00."},
        }
    ]
    text = scorecard_comment({"total": 15}, {"total": 100}, "https://pr-1.example", None, rows)
    assert "### Attack replay" in text
    assert "| Price tampering | PayPal order A was created for $1.00" in text


@pytest.mark.asyncio
async def test_price_tampering_runs_on_a_store_without_a_product_list():
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{AFTER}/api/orders").respond(201, json={"id": "SAMPLE"})
        mock.route(host="after.example").respond(404)
        async with httpx.AsyncClient() as c:
            result = await attacks.price_tamper(c, AFTER + "/", None, FakePayPal({"SAMPLE": "100.00"}))
    assert result["verdict"] == "blocked" and result["amount"] == "100.00"
