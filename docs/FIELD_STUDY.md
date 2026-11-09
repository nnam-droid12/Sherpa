# Field study: PayPal checkouts on real stores

**Date:** 9 November 2026 · **Script:** [`services/agent/scripts/field_study.py`](../services/agent/scripts/field_study.py) ·
**Totals:** [`field-study-2026-11-09.json`](field-study-2026-11-09.json)

We wanted to know whether the problems Sherpa fixes on its demo stores also show up on real stores. So we ran
Sherpa's fleet checks on retailers found through Channel3 product search.

## Method

1. **Find stores.** 30 Channel3 searches across everyday categories (running shoes, coffee beans, dog food, board
   games, cast iron skillets and so on) returned **186 retailer websites**.
2. **Read public pages only.** For each store Sherpa fetched the home, `/cart` and `/checkout` pages, up to 12 of
   the store's own scripts, and the common catalog paths, using GET requests and at most 6 stores at a time.
   The Cart API probe, which is a POST, was switched off for these third-party stores.
3. **Report totals only.** No store is named here or in the JSON file.

## Results

| | |
|---|---|
| Stores found | 186 |
| Reachable (HTTP 200) | 118 |
| Refused automated visits (HTTP 403/429) or timed out | 68 |
| **PayPal loaded on public pages** | **16** |
| … of those, on the legacy JS SDK v5 | **16 of 16 (100%)** |
| … of those, on JS SDK v6 | **0 of 16** |
| … of those, with no Pay Later messaging found | **14 of 16 (87.5%)** |
| Reachable stores with a public product JSON | 55 of 118 (46.6%), all Shopify's built-in `/products.json` |

**What it shows:** every store that loads PayPal on its public pages still uses the legacy SDK, which is exactly
the first thing Sherpa's fix moves to v6. Most also show no Pay Later messaging where shoppers decide to buy.

## Limits, stated plainly

- **PayPal often loads later.** Many stores load PayPal only inside a hosted or signed-in checkout, so "PayPal not
  seen on public pages" does not mean a store doesn't accept PayPal. The SDK and Pay Later numbers only describe
  the 16 stores where PayPal was visible.
- **Venmo isn't measured.** With the v5 SDK, Venmo can appear for eligible buyers without being named in the script,
  so public pages can't show whether Venmo is offered. We left it out.
- **Product JSON isn't an agent feed.** Shopify publishes `/products.json` automatically. None of the 118
  reachable stores had a feed at `/catalog.json` or `/api/catalog` (checked before `/products.json`), and the PayPal
  Cart API was not probed.
- **Small sample.** 186 stores from one product search engine on one day is a snapshot, not a census.
