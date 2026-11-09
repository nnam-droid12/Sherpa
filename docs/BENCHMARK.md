# Sherpa benchmark

Two measurements: a **detection benchmark** that anyone can rerun in seconds, and the **live run history**,
reported as it is.

## 1. Detection benchmark

**Script:** [`services/agent/bench/detection.py`](../services/agent/bench/detection.py) · **Guarded by:**
`tests/test_benchmark.py` (a change that weakens detection fails the test suite).

**Base:** real code written by Sherpa's own fixer for Ember & Oak (pull request #4), which passes every check.
**Method:** 11 flaw operators each reintroduce one real-world PayPal problem with a small code change. Sherpa then
runs its source checks on every single flaw, every pair of flaws and 60 random mixes of 3 to 6 flaws. A variant passes
only when Sherpa reports exactly the planted flaws: nothing missed and nothing extra.

- Variants: **126** (11 single flaws, every pair, and random mixes of 3–6)
- Exactly the planted flaws reported: **126 / 126**
- Variants with a false alarm: **0**
- Recall over all planted flaws: **100.0%**
- Findings on the unmodified base: none

| Flaw | What changes | Planted | Found |
|---|---|---|---|
| `SDK_LEGACY` | Load the legacy v5 SDK (with Venmo enabled) instead of v6 | 35 | 35 |
| `NO_VENMO` | Remove the Venmo button (and turn Venmo off in a v5 script) | 38 | 38 |
| `NO_PAY_LATER` | Remove Pay Later messaging | 32 | 32 |
| `AMOUNT_FROM_CLIENT` | Trust a total sent by the browser | 33 | 33 |
| `WEBHOOK_UNVERIFIED` | Stop verifying webhook signatures | 29 | 29 |
| `BLANK_PAGE_ON_ERROR` | Blank the page when payment fails | 36 | 36 |
| `EXTRA_CLICK` | Hide PayPal behind a 'Choose payment method' click | 38 | 38 |
| `DECLINED_NOT_RECOVERED` | Drop INSTRUMENT_DECLINED recovery | 38 | 38 |
| `REQUESTS_NOT_IDEMPOTENT` | Drop PayPal-Request-Id headers | 38 | 38 |
| `PENDING_TREATED_AS_PAID` | Treat PENDING captures as paid | 34 | 34 |
| `WEBHOOK_NOT_DEDUPED` | Process repeated webhook deliveries again | 33 | 33 |

**Scope:** the deterministic source checks. Checks that need a real shopper, such as whether the PayPal button is
visible on a phone, are measured by the live runs below.

### What the benchmark caught

The first run scored **88 of 126**, with no false alarms. It exposed two real detection bugs in Sherpa, both now fixed:

- **Removed Pay Later went unnoticed.** The v5 pattern `message: { amount }` also matched unrelated JavaScript
  objects, and the word `PayLaterMessage` matched a leftover function name. Both now require PayPal's actual
  markup: the `message` option inside `paypal.Buttons({...})`, or a `<PayLaterMessage>` tag.
- **Flaws combined inconsistently.** The benchmark's own legacy-SDK operator turned Venmo on, hiding a removed
  Venmo button. Operators now apply in a fixed order and compose correctly.

## 2. Live run history (Ember & Oak and Lumen Bakehouse)

Every run that reached Verify, as stored on the live system. Scores from different days used the rubric of that day
(the PayPal production checks were added on 9 November), so they are not directly comparable.

| Run | Store | Before → after | PayPal sandbox payment | Notes |
|---|---|---|---|---|
| `c95caeb6056d` | Ember & Oak | 15 → 100 | COMPLETED | All four stages |
| `3cafdd0bfbc9` | Ember & Oak | 15 → 85 | COMPLETED | Sherpa's checker flagged a fixer-written test that quoted the old blank-page code. Fixed: tests are no longer read as store code |
| `823477e9b5a3` | Ember & Oak | 15 → 82 | COMPLETED (desktop) | First run with the PayPal production checks: server-side correctness 20/20, both attacks blocked. The phone browser disconnected mid-checkout. Fixed: Sherpa now keeps the PayPal orders it saw and retries a device once after a cloud-browser failure |
| `03cde58b09e9` | Ember & Oak | 15 → 50 | none | The cloud-browser API key had expired, so no shopper could open a browser |
| `06eebdce06ea` | Lumen Bakehouse | 18 → 82 | none | Recorded before the KERNEL key and browser fixes |

Every failure above was traced to a cause in Sherpa or its infrastructure, and each has a fix and a test.
