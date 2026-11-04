# Sherpa: Devpost submission

## Tagline

The AI integration engineer for PayPal checkout and agentic commerce.

## Inspiration

Where PayPal appears in a checkout, how it looks, and whether it's offered at the right moment decide whether shoppers choose it. In practice, many stores run integrations that quietly lose those shoppers: a legacy SDK, a PayPal button buried below the fold or hidden on phones, no Venmo, no Pay Later, prices trusted from the browser, unverified webhooks. Fixing that takes hands-on integration work that most merchants never get to. Agentic commerce adds a second bottleneck: before an AI agent can buy from a store, the store has to expose a catalog and PayPal Cart API endpoints.

We wanted an engineer that does that work end to end and proves it worked.

## What it does

Give Sherpa a store URL and its GitHub repo.

1. **Audit:** two AI shoppers powered by Gemini computer use open real KERNEL cloud browsers, one desktop and one phone, and try to buy something with PayPal while you watch live. Deterministic checks measure SDK version, button placement, Venmo, Pay Later, server-side correctness and agent readiness. The result is a 0–100 scorecard with screenshots, replays and plain-English findings.
2. **Fix:** a Gemini 3.8 Flash coding agent edits the repo in front of you, in a live code editor with diffs. It upgrades to JS SDK v6, puts PayPal and Venmo above the fold, adds Pay Later messaging, moves pricing to the server, verifies webhook signatures and adds graceful error handling. It can't finish until the build passes and Sherpa's own checks agree. Then it opens a real pull request written for the merchant.
3. **Verify:** Sherpa deploys the PR as a private Cloud Run preview, re-runs the shoppers, completes a real PayPal sandbox payment, confirms it through the Orders API, and posts a before/after scorecard on the PR. On our demo store the score went from **15 to 100** with a `COMPLETED` sandbox order.
4. **Agent-ready:** the coding agent adds a catalog feed and the PayPal Cart API endpoints, contract tests run live, and an AI buyer agent shops the store through the API: *"I need a birthday cake for 12 people delivered Saturday, under $90."* It handles the store's validation questions and checks out through PayPal.

On top of the four stages:

- **⚡ Autopilot** runs all four stages back to back from one click.
- **Revenue at risk** turns findings into an estimated monthly PayPal revenue at risk, from the merchant's own traffic and order value, with every assumption visible and editable, and shows the estimated revenue recovered after Verify.
- **Agent Shelf** uses Channel3 to show what a shopper's AI agent finds elsewhere for the same products, with live retailer prices, and where the store's price sits against the market.
- **Fleet scan** ranks up to 25 stores by checkout health in seconds in an AG Grid table, for platforms and agencies that look after many merchants, with a deep audit one click away.

## How we built it

- **Gemini 3.8 Flash on Gemini Enterprise Agent Platform (Vertex AI):**
  - computer use for the shoppers and PayPal approval
  - structured output for findings
  - a function-calling coding agent with high thinking for fixes
  - function calling for the buyer agent

  All of it authenticates with a service account, with no API keys.
- **KERNEL** cloud browsers over CDP with Playwright, plus live view embedded in the console and session replays.
- **PayPal:** JS SDK v6, Orders v2, Webhooks with `verify-webhook-signature`, Venmo, Pay Later messaging, Cart API v1, the Agent Toolkit, and the official `paypal/AI-Toolkit` best-practice references as grounding.
- **Google Cloud:** Cloud Run (console, agent, stores, tagged preview revisions), Cloud Build, Artifact Registry, Firestore, Cloud Storage and Secret Manager.
- **AG Grid** for the fleet scan table.
- **Channel3** product search for Agent Shelf market data.
- **Next.js 15** console with server-sent events, and **FastAPI** for the agent.

## Challenges

- **PayPal's sandbox checkout varies:** guest-first pages, iframes, hidden duplicate inputs, and popups that close themselves. We sign the sandbox buyer in deterministically, without ever showing credentials to the model.
- **Long-running agents on serverless:** background jobs were being shut down mid-run. We moved to a single always-on instance with heartbeats, stop signals and visible "interrupted" states.
- **Keeping scores honest:** the model writes the explanations, but deterministic code decides every number, and the audit has to find every planted flaw.
- **Speed:** preloading sources, caching installs and stopping shoppers once a crash is captured cut audits and fixes dramatically.

## What we learned

Computer-use agents are most useful when they are paired with deterministic measurement. The agent shows what a shopper experiences, and probes turn that into evidence you can score and reproduce.

## What's next

- Run against real merchant repos through a GitHub App.
- Support more stacks (Shopify themes, WooCommerce).
- Register real Store Sync endpoints, and expand the rubric to Fastlane and card fields.

## Honesty notes

- **Sandbox only:** Sherpa refuses to start against live PayPal.
- **Computer use is in preview.**
- **The buyer agent plays PayPal's role:** in production, PayPal's Commerce Platform calls the merchant's Cart API after Store Sync onboarding. In this build, Sherpa's buyer agent plays that caller against the sandbox.
- **The demo stores are fictional.** Their product photos are real, openly licensed photographs; see each store's `CREDITS.md`.

---

## 3-minute video shot list

| Time | Shot | What to show |
|---|---|---|
| 0:00–0:15 | Landing page | The pitch line, then "Try it live, no sign-up" |
| 0:15–0:45 | Dashboard → Run live audit | Two live KERNEL browsers; the mobile shopper can't find PayPal; the timeline narrates |
| 0:45–1:05 | Scorecard | The 15/100 dial, category bars, critical findings with screenshots |
| 1:05–1:35 | Fix it | The dark code editor filling with files and live diffs; the "Pull request is open" card; the PR on GitHub |
| 1:35–2:05 | Deploy preview & verify | The checklist, the shopper paying on the preview, 15 → 86, the PayPal receipt `COMPLETED`, the PR comment |
| 2:05–2:45 | Make agent-ready | Catalog cards, contract tests ticking green, the buyer agent chat answering the delivery-date question, PayPal approval, the receipt |
| 2:45–3:00 | Close | Before/after, "Opened by Sherpa", the console URL |
