# Progress

_Last updated: 2026-11-02_

## Live

- Console: https://sherpa-web-854441956422.us-east1.run.app (landing page, `/dashboard`, `/runs`)
- Agent: Cloud Run `sherpa-agent`, a single always-on instance in `us-east1`
- Demo stores, redesigned with openly licensed product photography:
  - https://store-ember-oak-4j2p5vomta-ue.a.run.app
  - https://store-lumen-bakehouse-4j2p5vomta-ue.a.run.app

## Verified live

- **Audit:** every planted flaw is detected on both stores (9/9 and 7/7). Ember & Oak scored 15 on five consecutive runs; Lumen scored between 18 and 23.
- **Fix:** Ember & Oak [PR #1](https://github.com/nnam-droid12/sherpa-demo-ember-oak/pull/1) has a passing build and no unresolved self-checks.
- **Verify:** Ember & Oak went from 15 to 86 on the preview, with sandbox order `2FX73165U33387701` `COMPLETED` and a scorecard comment on the PR.
- **Sandbox login:** works on both of PayPal's entry pages (guest-first and direct login).

## In progress

- Agent-ready on Ember & Oak (first live run).
- The Lumen Bakehouse fix → verify → agent-ready flow on the new faster fixer.

## Next

- Re-verify Ember & Oak after the mobile popup fix, so the mobile payment also completes and the score exceeds 90.
- A Playwright smoke test of the console in CI, and an accessibility pass.
- Make the Sherpa repo public before submission.
- Record the demo video, following `docs/DEVPOST.md`.

## Known issues

- Vertex AI can return `429 RESOURCE_EXHAUSTED` when several heavy stages run at once; calls retry with backoff of up to a minute.
- The brief's quote about PayPal management and integration support is still unsourced, so the README leaves it out.
