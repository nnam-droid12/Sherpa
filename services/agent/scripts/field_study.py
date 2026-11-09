"""Field study: how real online stores present PayPal today, measured with Sherpa's fleet checks.

1. Collect retailer websites from Channel3 product searches across everyday categories.
2. Scan each store's public pages (home, cart, checkout and the store's own scripts) and its catalog paths
   with GET requests only; the Cart API probe (a POST) is skipped for third-party stores.
3. Report totals only. Individual stores are never named in the report.

Run: python scripts/field_study.py --out study.json   (needs CHANNEL3_API_KEY; about 1 credit per query)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict

import httpx

from sherpa.fleet import CONCURRENCY, check_store
from sherpa.shelf import search

QUERIES = [
    "running shoes",
    "yoga mat",
    "coffee beans",
    "dog food",
    "face serum",
    "phone case",
    "wireless earbuds",
    "wooden toys",
    "board game",
    "scented candle",
    "loose leaf tea",
    "hiking backpack",
    "sunglasses",
    "mechanical watch",
    "silver necklace",
    "graphic t-shirt",
    "hoodie",
    "chef knife",
    "cast iron skillet",
    "linen bed sheets",
    "desk lamp",
    "ceramic plant pot",
    "bike light",
    "camping tent",
    "fishing lure",
    "golf balls",
    "multivitamin",
    "protein powder",
    "watercolor paint set",
    "leather wallet",
]


async def collect_domains(queries: list[str]) -> list[str]:
    domains: dict[str, None] = {}
    async with httpx.AsyncClient(timeout=30) as c:
        for q in queries:
            try:
                for p in await search(c, q):
                    for o in p.get("offers", []):
                        d = (o.get("domain") or "").lower().removeprefix("www.")
                        if d and "." in d:
                            domains.setdefault(d)
            except httpx.HTTPError as exc:
                print(f"search failed for {q!r}: {exc}")
    return list(domains)


async def scan(domains: list[str]) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(d: str) -> dict:
        async with sem:
            return asdict(await check_store(f"https://{d}", probe_cart=False))

    return await asyncio.gather(*(one(d) for d in domains))


def summarise(stores: list[dict]) -> dict:
    reached = [s for s in stores if s["reachable"]]
    paypal = [s for s in reached if s["paypal"]]

    def pct(part: list, whole: list) -> float:
        return round(100 * len(part) / len(whole), 1) if whole else 0.0

    return {
        "stores_found": len(stores),
        "stores_reachable": len(reached),
        "paypal_seen_on_public_pages": len(paypal),
        "of_paypal_stores": {
            "legacy_v5_sdk_pct": pct([s for s in paypal if s["sdk"] == "v5"], paypal),
            "v6_sdk_pct": pct([s for s in paypal if s["sdk"] == "v6"], paypal),
            "no_venmo_pct": pct([s for s in paypal if not s["venmo"]], paypal),
            "no_pay_later_messaging_pct": pct([s for s in paypal if not s["pay_later"]], paypal),
        },
        "of_all_reachable_stores": {
            "catalog_feed_at_common_paths_pct": pct([s for s in reached if s["catalog_feed"]], reached),
        },
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="study.json")
    ap.add_argument("--limit", type=int, default=400)
    args = ap.parse_args()
    t0 = time.time()
    domains = (await collect_domains(QUERIES))[: args.limit]
    print(f"{len(domains)} stores from {len(QUERIES)} searches")
    stores = await scan(domains)
    summary = summarise(stores)
    summary["seconds"] = round(time.time() - t0)
    summary["queries"] = QUERIES
    json.dump({"summary": summary, "stores": stores}, open(args.out, "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
