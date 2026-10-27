# Audit scorecard

Sherpa scores a store's PayPal checkout from 0 to 100. **Scores come from deterministic code** in `services/agent/sherpa/audit/rubric.py`, built from two kinds of evidence:

- **Visual evidence** from the computer-use shopper, which shops the live store in a KERNEL cloud browser on desktop (1440×900) and mobile (390×844).
- **Static evidence** from `static_checks.py`: page HTML, measured button positions, endpoint probes and, when a repo is linked, the source code.

Gemini only writes the plain-English wording of each finding (impact and recommended fix). It never decides a score.

## Categories and weights

| Category | Weight | Checks (points) |
|---|---:|---|
| Presentment | 20 | PayPal button above the fold on desktop cart/checkout (10) · above the fold on mobile (10) |
| Payment options | 15 | PayPal offered (5) · Venmo enabled (5) · Pay Later messaging shown for eligible amounts (5) |
| SDK modernity | 10 | JS SDK v6 (10) · legacy v5 `paypal.com/sdk/js` (0) |
| Mobile checkout completion | 15 | Shopper reaches a visible PayPal button on mobile (7) · mobile sandbox payment completes (8) |
| Steps to pay | 10 | No extra clicks between checkout and PayPal (10), −5 per extra click; a crash on the way scores 0 |
| Server-side correctness | 20 | Order amount computed or verified server-side (8) · webhook endpoint with signature verification (7) · graceful payment errors with a retry path (5) |
| Agent readiness | 10 | Product catalog feed (4) · PayPal Cart API v1 endpoints respond to the contract (6) |

Each finding carries a **severity** (critical, high, medium, low), **evidence** (a screenshot step or a code reference), the **business impact** in plain English, and the **recommended fix**.

Targets: a flawed baseline scores **below 45**; after Sherpa's fix the preview scores **above 85**.

## Planted flaws (ground truth)

These are deliberate. The audit must detect every one, and the fixer must fix every one.

### Ember & Oak (outdoor gear, HTML/JS + Express)

| ID | Flaw | Where | Category | Severity |
|---|---|---|---|---|
| EO-1 | Legacy JS SDK v5 script tag (`www.paypal.com/sdk/js?client-id=…`) | `views/cart.html` | SDK modernity | high |
| EO-2 | PayPal button at the bottom of a long cart page, below the fold on desktop and mobile | `views/cart.html` | Presentment | high |
| EO-3 | No Pay Later messaging, even on items over $200 (`disable-funding=…paylater`) | `views/cart.html`, `views/product.html` | Payment options | medium |
| EO-4 | Venmo not offered (`disable-funding=venmo`) | `views/cart.html` | Payment options | medium |
| EO-5 | CSS collapses `.checkout-actions` to zero height at widths ≤ 414px, hiding the pay button on phones | `public/styles.css` | Mobile completion | critical |
| EO-6 | Server creates the order from the browser-supplied `total` and captures without checking it | `server.js` `/api/orders` | Server-side correctness | critical |
| EO-7 | Webhook endpoint accepts events without verifying the PayPal signature | `server.js` `/api/webhooks/paypal` | Server-side correctness | high |
| EO-8 | A failed capture wipes the page (`document.body.innerHTML = ""`) with no message or retry | `views/cart.html` | Server-side correctness | high |
| EO-9 | No catalog feed and no Cart API endpoints | — | Agent readiness | medium |

### Lumen Bakehouse (preorder cakes, Next.js)

| ID | Flaw | Where | Category | Severity |
|---|---|---|---|---|
| LB-1 | Legacy JS SDK v5 injected by a `useEffect` script loader | `src/components/paypal-button.tsx` | SDK modernity | high |
| LB-2 | PayPal only renders after an extra "Choose payment method" click | `src/components/checkout.tsx` | Steps to pay, Presentment | high |
| LB-3 | Review step crashes when the optional delivery notes field is left empty (`notes` is `undefined`) | `src/components/checkout.tsx` | Mobile completion, Steps to pay | critical |
| LB-4 | No catalog feed | — | Agent readiness | medium |
| LB-5 | No PayPal Cart API v1 endpoints | — | Agent readiness | medium |
| LB-6 | No webhook endpoint | — | Server-side correctness | high |
| LB-7 | Venmo and Pay Later messaging not configured | `src/components/paypal-button.tsx` | Payment options | medium |

Notes on reproducing the flaws by hand:

- **Ember & Oak** can be bought on desktop by scrolling to the bottom of `/cart`. On a phone-width window (≤ 414px) the pay button is hidden.
- **Lumen Bakehouse** can be bought by typing something in "Delivery notes", then clicking "Choose payment method". Leaving the notes empty crashes the review step.
