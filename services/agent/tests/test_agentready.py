import datetime as dt
import json

import httpx

from sherpa.agentready.spec import cart_api_reference, run_contract_tests
from sherpa.buyer.agent import Persona, next_weekday


def fake_store():
    carts = {}

    def validate(body):
        issues = []
        if not body.get("shipping_address"):
            issues.append({"code": "SHIPPING_ERROR", "type": "MISSING_FIELD", "message": "address required"})
        return issues

    def cart(cid, body, status="CREATED"):
        issues = validate(body)
        return {
            "id": cid,
            "status": status,
            "validation_status": "INVALID" if issues else "VALID",
            "validation_issues": issues,
            "items": body.get("items", []),
            "totals": {"total": {"currency_code": "USD", "value": "78.00"}},
            "payment_method": {"type": "paypal", "token": "5O190127TN364715T"},
        }

    def handler(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        body = json.loads(request.content or b"{}")
        if path == "/catalog.json":
            return httpx.Response(200, json={"items": [{"id": "cake"}]})
        if path == "/merchant-cart" and method == "POST":
            carts["c1"] = cart("c1", body)
            return httpx.Response(201, json=carts["c1"])
        cid = path.split("/")[2]
        if cid not in carts:
            return httpx.Response(404, json={"name": "CART_NOT_FOUND", "message": "no cart"})
        if path.endswith("/checkout"):
            return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY", "message": "approve first"})
        if method == "PUT":
            carts[cid] = cart(cid, body)
        return httpx.Response(200, json=carts[cid])

    return httpx.MockTransport(handler)


async def test_contract_suite_passes_on_compliant_store():
    results = await run_contract_tests("https://store.test", "cake", transport=fake_store())
    assert results and all(r["ok"] for r in results), results


async def test_contract_suite_fails_without_cart_api():
    transport = httpx.MockTransport(lambda r: httpx.Response(404, json={}))
    results = await run_contract_tests("https://store.test", "cake", transport=transport)
    assert not any(r["ok"] for r in results)


def test_next_saturday_respects_lead_time():
    wed = dt.date(2026, 11, 4)
    assert next_weekday(5, min_days=2, today=wed) == dt.date(2026, 11, 7)
    fri = dt.date(2026, 11, 6)
    assert next_weekday(5, min_days=2, today=fri) == dt.date(2026, 11, 14)


def test_persona_answers_delivery_and_address():
    p = Persona("cake")
    assert "Saturday" in p.answer("Which delivery date works?")
    assert "94105" in p.answer("What is the shipping address?")


def test_reference_ships_with_package():
    ref = cart_api_reference()
    assert "/merchant-cart/{id}/checkout" in ref and "validation_issues" in ref


def test_describe_call_summarises_cart_and_order_calls():
    from sherpa.buyer.agent import describe_call

    ep, text, tone = describe_call(
        "create_cart",
        {},
        {
            "http_status": 201,
            "status": "CREATED",
            "validation_status": "INVALID",
            "totals": {"total": {"value": "78.00"}},
            "validation_issues": [{"code": "DATA_ERROR", "message": "A delivery date is required"}],
        },
    )
    assert ep == "POST /merchant-cart" and tone == "warn"
    assert "INVALID" in text and "$78.00" in text and "delivery date" in text
    _, text, tone = describe_call(
        "check_paypal_order", {}, {"id": "5O1", "status": "COMPLETED", "amount": "USD 78.00"}
    )
    assert tone == "good" and "COMPLETED" in text
    _, _, tone = describe_call("checkout_cart", {}, {"error": "boom"})
    assert tone == "bad"


def test_persona_answers_address_questions_with_the_address():
    p = Persona("cake")
    a = p.answer("Could you share your delivery address and your name/email for the delivery?")
    assert "94105" in a and "Saturday" not in a and "Alex Rivera" in a
    both = p.answer("What delivery date and shipping address should we use?")
    assert "94105" in both and "Saturday" in both
