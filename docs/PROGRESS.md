# Progress

_Last updated: 2026-10-27_

## Done (code complete, unit-tested)

- **Phase 1:** monorepo, FastAPI agent (`/health`, sandbox-only guard, API-key auth), Next.js console, Dockerfiles, `infra/deploy.sh`, `infra/secrets.sh`, CI. Agent deployed to Cloud Run (`us-east1`).
- **Phase 2:** both flawed demo stores (`demo-stores/`), mirrored to public repos `nnam-droid12/sherpa-demo-ember-oak` and `nnam-droid12/sherpa-demo-lumen-bakehouse` with a `baseline` tag. `infra/reset-demo.sh` restores them. Planted flaws documented in `docs/SCORECARD.md`.
- **Phase 3:** KERNEL browser sessions over CDP (desktop/mobile, live view, replays, host allowlist), Gemini computer-use shopper, deterministic static checks and page probes, rubric, Gemini structured-output findings. Tests prove every planted flaw maps to a finding and both baselines score under 45.
- **Phase 4:** console with streaming live audit (KERNEL live view, timeline, score dial), scorecard with HTML report download, fix, verify and agent-ready panels, and run history.
- **Phase 5:** fixer agent (Gemini 3.8 Flash, thinking high) with sandboxed tools, build gate, deterministic self-checks, best-practice grounding from `paypal/AI-Toolkit`, branch and PR flow.
- **Phase 6:** preview deploys as tagged no-traffic revisions via the Cloud Build API, re-audit, and a scorecard comment on the PR.
- **Phase 7:** Cart API v1 contract (`services/agent/sherpa/agentready/cart_api.md`), agent-ready task for the fixer, live contract test suite, and AI buyer agent (function calling, persona, computer-use approval, PayPal Agent Toolkit order checks).

## Blocked: live end-to-end testing

Nothing that touches PayPal, KERNEL or GitHub has run live yet. Needed in the local `.env`, which `infra/secrets.sh` then syncs to Secret Manager:

- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` (sandbox REST app)
- `PAYPAL_SANDBOX_BUYER_EMAIL`, `PAYPAL_SANDBOX_BUYER_PASSWORD` (sandbox personal account)
- `KERNEL_API_KEY`
- `GITHUB_TOKEN` (fine-grained, limited to the two demo repos)

`PAYPAL_WEBHOOK_ID` gets created through the API once the stores are deployed.

## Next

1. Deploy both stores and the console, and register sandbox webhooks.
2. Run live audits on both stores, then tune the shopper prompt and probes until every planted flaw is detected reliably (±5 across three runs).
3. Run fix → verify → agent-ready end to end on both stores and tune until before < 45, after > 85, mobile payment completes, and the buyer agent completes an order.
4. Phase 8: hardening (rate limiting and demo mode, cached replay, usage display, Playwright smoke test, accessibility pass).
5. Phase 9: README, DEVPOST.md, architecture details.

## Known issues / risks

- Cloud Run in `us-central1` rejects deploys in this project; everything runs in `us-east1`.
- The Sherpa repo is private and must be made public before submission.
- Computer use is in preview; the shopper prompt will need tuning against the real stores.
