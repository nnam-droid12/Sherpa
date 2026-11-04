"""Agent Shelf: what an AI shopping agent finds on the open web when it shops for a store's products.

For each catalog item Sherpa writes the query a shopper's agent would send, searches the Channel3 product
catalog, keeps only truly comparable products and compares the merchant's price with the market.
Every price shown is a live retailer offer returned by Channel3; nothing is estimated.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
from collections import Counter
from typing import Any

import httpx
from google.genai import types
from pydantic import BaseModel

from sherpa.config import get_settings
from sherpa.llm import generate

log = logging.getLogger(__name__)

API = "https://api.trychannel3.com/v1"
MAX_ITEMS = 4  # one search credit per item
RESULTS = 10
SHOWN = 4
BAND = 0.10  # within ±10% of the market median counts as "in line"

_cache: dict[str, list[dict[str, Any]]] = {}


class _Query(BaseModel):
    id: str
    query: str


class _Queries(BaseModel):
    items: list[_Query]


class _Match(BaseModel):
    id: str
    comparable_ids: list[str]


class _Matches(BaseModel):
    items: list[_Match]


def _config(schema: type[BaseModel]) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.1,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
    )


async def _ask[T: BaseModel](prompt: str, schema: type[T]) -> T:
    resp = await generate(get_settings().gemini_model, prompt, _config(schema))
    return resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text)


def _price(item: dict[str, Any]) -> float | None:
    p = item.get("price")
    raw = p.get("value") if isinstance(p, dict) else p
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


async def shopper_queries(items: list[dict[str, Any]]) -> dict[str, str]:
    """The search a shopper's agent would run: the product type and key specs, without the store's brand."""
    prompt = (
        "For each product, write the short search query a shopper's AI agent would send to a product search "
        "engine to find this kind of product from any retailer. Describe the product type and the one or two "
        "specs that matter most. Leave out the store's own brand and product names. At most 8 words.\n\n"
        + json.dumps(
            [
                {
                    "id": i["id"],
                    "title": i.get("title"),
                    "category": i.get("category"),
                    "specs": i.get("specs"),
                }
                for i in items
            ]
        )
    )
    try:
        parsed = await _ask(prompt, _Queries)
        found = {q.id: q.query.strip() for q in parsed.items if q.query.strip()}
    except Exception:
        log.warning("shelf query writing failed", exc_info=True)
        found = {}
    return {i["id"]: found.get(i["id"]) or str(i.get("title", "")) for i in items}


async def search(client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
    if query in _cache:
        return _cache[query]
    r = await client.post(
        f"{API}/search",
        headers={"x-api-key": get_settings().channel3_api_key},
        json={"query": query, "limit": RESULTS},
    )
    r.raise_for_status()
    products = r.json().get("products", [])
    _cache[query] = products
    return products


def _summary(p: dict[str, Any]) -> dict[str, Any] | None:
    """A Channel3 product reduced to its best in-stock USD offer."""
    offers = [
        o
        for o in p.get("offers", [])
        if o.get("availability") == "InStock" and (o.get("price") or {}).get("currency") == "USD"
    ]
    if not offers:
        return None
    best = min(offers, key=lambda o: o["price"]["price"])
    images = p.get("images") or []
    main = next((i for i in images if i.get("is_main_image")), images[0] if images else {})
    ratings = p.get("ratings") or {}
    return {
        "id": p["id"],
        "title": p.get("title", ""),
        "brand": (p.get("brands") or [{}])[0].get("name"),
        "category": (p.get("category") or {}).get("title"),
        "price": round(float(best["price"]["price"]), 2),
        "domain": best.get("domain"),
        "url": best.get("url"),
        "offers": len(offers),
        "image": main.get("cleaned_url") or main.get("url"),
        "rating": ratings.get("value"),
        "reviews": ratings.get("count"),
    }


async def pick_comparables(
    items: list[dict[str, Any]], candidates: dict[str, list[dict[str, Any]]]
) -> dict[str, set[str]]:
    """Keep only results a shopper would accept as the same kind of product."""
    prompt = (
        "A shopper's AI agent searched the web for alternatives to each store product. For each product, return "
        "the ids of the results that are genuinely the same kind of product a shopper could buy instead (same "
        "product type and use, comparable size or capacity). Exclude accessories, unrelated items and products "
        "that merely share a word (a vanilla cake candle is not a cake). It is fine to return none.\n\n"
        + json.dumps(
            [
                {
                    "id": i["id"],
                    "product": {
                        "title": i.get("title"),
                        "category": i.get("category"),
                        "specs": i.get("specs"),
                    },
                    "results": [
                        {"id": c["id"], "title": c["title"], "brand": c["brand"], "category": c["category"]}
                        for c in candidates.get(i["id"], [])
                    ],
                }
                for i in items
            ]
        )
    )
    try:
        parsed = await _ask(prompt, _Matches)
        return {m.id: set(m.comparable_ids) for m in parsed.items}
    except Exception:
        log.warning("shelf relevance check failed; falling back to the dominant category", exc_info=True)
        out: dict[str, set[str]] = {}
        for item_id, cands in candidates.items():
            top = Counter(c["category"] for c in cands[:3] if c["category"]).most_common(1)
            out[item_id] = {c["id"] for c in cands if top and c["category"] == top[0][0]}
        return out


def position(price: float | None, market: list[float]) -> tuple[str, float | None]:
    if price is None or not market:
        return "no_match", None
    median = statistics.median(market)
    delta = (price - median) / median
    if delta < -BAND:
        return "below", delta
    if delta > BAND:
        return "above", delta
    return "in_line", delta


async def build_shelf(items: list[dict[str, Any]]) -> dict[str, Any]:
    items = [i for i in items if i.get("id") and i.get("title")][:MAX_ITEMS]
    if not get_settings().channel3_api_key:
        return {"available": False, "reason": "Channel3 is not configured", "items": []}
    queries = await shopper_queries(items)
    async with httpx.AsyncClient(timeout=30) as client:
        results = await asyncio.gather(
            *(search(client, queries[i["id"]]) for i in items), return_exceptions=True
        )
    candidates: dict[str, list[dict[str, Any]]] = {}
    for item, res in zip(items, results, strict=True):
        if isinstance(res, BaseException):
            log.warning("channel3 search failed for %s: %s", item["id"], res)
            candidates[item["id"]] = []
            continue
        candidates[item["id"]] = [s for s in (_summary(p) for p in res) if s]
    keep = await pick_comparables(items, candidates)

    rows = []
    for item in items:
        comparables = [c for c in candidates[item["id"]] if c["id"] in keep.get(item["id"], set())]
        market = [c["price"] for c in comparables]
        price = _price(item)
        label, delta = position(price, market)
        rows.append(
            {
                "id": item["id"],
                "title": item["title"],
                "image": item.get("image_url"),
                "price": price,
                "query": queries[item["id"]],
                "position": label,
                "delta": None if delta is None else round(delta, 3),
                "market": {
                    "count": len(market),
                    "min": min(market) if market else None,
                    "median": round(statistics.median(market), 2) if market else None,
                    "max": max(market) if market else None,
                    "retailers": sorted({c["domain"] for c in comparables if c["domain"]}),
                },
                # Channel3's own ranking: what the shopper's agent sees first.
                "comparables": comparables[:SHOWN],
            }
        )
    return {"available": True, "source": "Channel3", "searches": len(items), "items": rows}
