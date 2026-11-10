import json
from pathlib import Path

from sherpa.agentready.spec import grounded_check, invented_prices
from sherpa.audit import static_checks as sc
from sherpa.fixer.tools import Workspace

STORES = Path(__file__).resolve().parents[3] / "demo-stores"
SAMPLE_SERVER = """
const createOrder = async (cart) => {
  const collect = { body: { intent: CheckoutPaymentIntent.Capture,
    purchaseUnits: [{ amount: { currencyCode: "USD", value: "100.00" } }] } };
};
"""


def test_invented_cakes_are_flagged_on_a_store_that_sells_one_fixed_order():
    # What Sherpa's agent once published for PayPal's sample, which only ever charges $100.00.
    feed = [
        {
            "id": "vanilla-bean-celebration",
            "title": "Vanilla Bean Celebration Cake",
            "price": {"value": "78.00"},
        },
        {"id": "order", "title": "Order", "price": {"value": "100.00"}},
    ]
    assert invented_prices(SAMPLE_SERVER, feed) == ["Vanilla Bean Celebration Cake ($78.00)"]


def test_a_real_catalog_is_not_flagged():
    root = STORES / "ember-oak"
    original = "\n".join(sc.read_source_tree(root).values())
    products = json.loads((root / "products.json").read_text(encoding="utf-8"))
    items = products if isinstance(products, list) else products.get("items") or products.get("products")
    feed = [{"id": p["id"], "title": p.get("title") or p.get("name"), "price": p.get("price")} for p in items]
    assert feed and invented_prices(original, feed) == []


def test_grounded_check_rejects_new_prices_but_not_tolerances(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "server.js").write_text(SAMPLE_SERVER)
    original = "\n".join(sc.read_source_tree(tmp_path).values())
    check = grounded_check(original)
    (tmp_path / "server.js").write_text(
        SAMPLE_SERVER + "\nif (Math.abs(diff) > 0.01) throw new Error('mismatch');"
    )
    assert not any("New prices" in p for p in check(Workspace(tmp_path)))
    (tmp_path / "catalog.js").write_text('export const items = [{ id: "cake", price: "78.00" }];')
    assert any("78.00" in p for p in check(Workspace(tmp_path)))


def test_a_bare_number_elsewhere_in_the_code_is_not_a_known_price():
    # "50" appears in ordinary code (timeouts, sizes); it must not make an invented $50 item look real.
    original = SAMPLE_SERVER + "\nsetTimeout(retry, 50); const width = 50;"
    feed = [{"id": "item-2", "title": "Sample Item 2", "price": {"value": "50.00"}}]
    assert invented_prices(original, feed) == ["Sample Item 2 ($50.00)"]


def test_whole_number_prices_next_to_a_price_key_are_known():
    assert invented_prices('{ "id": "a", "price": 50 }', [{"id": "a", "price": 50}]) == []


def test_an_invented_item_at_a_real_price_is_still_flagged():
    sample = SAMPLE_SERVER + '\nbody: JSON.stringify({ cart: [{ id: "YOUR_PRODUCT_ID", quantity: "1" }] })'
    feed = [
        {"id": "YOUR_PRODUCT_ID", "title": "Sample Item", "price": {"value": "100.00"}},
        {"id": "item-1", "title": "Sample Item 1", "price": {"value": "100.00"}},
    ]
    assert invented_prices(sample, feed) == ["Sample Item 1 ($100.00)"]
