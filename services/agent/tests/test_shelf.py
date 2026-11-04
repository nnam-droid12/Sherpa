import pytest
import respx

from sherpa import shelf


def product(pid: str, title: str, price: float, category: str = "Tents", stock: str = "InStock") -> dict:
    return {
        "id": pid,
        "title": title,
        "brands": [{"id": "b", "name": "Brand"}],
        "category": {"slug": category.lower(), "title": category},
        "images": [{"url": f"https://img/{pid}", "cleaned_url": None, "is_main_image": True}],
        "offers": [
            {
                "url": f"https://buy/{pid}",
                "domain": "shop.example",
                "price": {"price": price, "currency": "USD"},
                "availability": stock,
            }
        ],
        "ratings": None,
    }


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("CHANNEL3_API_KEY", "test")
    shelf.get_settings.cache_clear()
    shelf._cache.clear()

    async def queries(items):
        return {i["id"]: f"q {i['id']}" for i in items}

    async def comparables(items, candidates):
        # The relevance check drops the candle that only shares a word with the product.
        return {i["id"]: {c["id"] for c in candidates[i["id"]] if "Candle" not in c["title"]} for i in items}

    monkeypatch.setattr(shelf, "shopper_queries", queries)
    monkeypatch.setattr(shelf, "pick_comparables", comparables)
    yield
    shelf.get_settings.cache_clear()


def test_position_bands():
    assert shelf.position(349, [760, 800, 1050]) == ("below", pytest.approx((349 - 800) / 800))
    assert shelf.position(100, [95, 100, 108])[0] == "in_line"
    assert shelf.position(200, [100, 110])[0] == "above"
    assert shelf.position(50, []) == ("no_match", None)


@pytest.mark.asyncio
async def test_shelf_compares_only_real_alternatives(configured):
    tent = {"id": "tent", "title": "Ridgeline 2P", "price": {"value": "349.00"}, "category": "Shelter"}
    cake = {"id": "cake", "title": "Vanilla Bean Cake", "price": {"value": "78.00"}}
    with respx.mock() as mock:
        mock.post(f"{shelf.API}/search", json__query="q tent").respond(
            200,
            json={
                "products": [
                    product("a", "Trango 2", 1050),
                    product("b", "Mountain 25", 760),
                    product("c", "Advance Pro 2", 800),
                    product("d", "Sold out tent", 10, stock="OutOfStock"),
                ]
            },
        )
        mock.post(f"{shelf.API}/search", json__query="q cake").respond(
            200, json={"products": [product("e", "Vanilla Cake Candle", 30, "Candles")]}
        )
        result = await shelf.build_shelf([tent, cake])
    assert result["available"] and result["searches"] == 2
    tent_row, cake_row = result["items"]
    assert tent_row["position"] == "below"
    assert tent_row["market"] == {
        "count": 3,
        "min": 760,
        "median": 800,
        "max": 1050,
        "retailers": ["shop.example"],
    }
    assert [c["id"] for c in tent_row["comparables"]] == ["a", "b", "c"]
    assert cake_row["position"] == "no_match" and cake_row["comparables"] == []


@pytest.mark.asyncio
async def test_shelf_without_key_is_unavailable(monkeypatch):
    monkeypatch.setenv("CHANNEL3_API_KEY", "")
    shelf.get_settings.cache_clear()
    try:
        result = await shelf.build_shelf([{"id": "x", "title": "X"}])
    finally:
        shelf.get_settings.cache_clear()
    assert result["available"] is False
