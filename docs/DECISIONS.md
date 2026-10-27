# Decisions

A running log of technical choices and where the live docs differed from the original plan.

| # | Date | Decision | Why |
|---|------|----------|-----|
| 1 | 2026-10-22 | Gemini runs on Gemini Enterprise Agent Platform (Vertex AI) via the `google-genai` SDK in Vertex mode, authenticated with Application Default Credentials. No API keys. | Keyless auth with a least-privilege service account on Cloud Run. |
| 2 | 2026-10-22 | Model `gemini-3.8-flash`, location `global`. | The Vertex computer-use docs list Gemini 3.8 Flash as supported and show REST endpoints under `locations/global`. |
| 3 | 2026-10-22 | Computer use also runs on `gemini-3.8-flash` (`ENVIRONMENT_BROWSER`). | Listed as supported in the Vertex computer-use docs. Coordinates are on a 0–999 grid and are scaled to the viewport. The model id is configurable via `SHERPA_COMPUTER_USE_MODEL`. |
| 4 | 2026-10-22 | Web → agent auth uses a shared `X-Sherpa-Key` header stored in Secret Manager. | Simpler than IAM-authenticated calls from a Next.js server, and the key never reaches the browser because the console proxies through its own server routes. |
| 5 | 2026-10-22 | Demo stores live in their own public repos (`sherpa-demo-ember-oak`, `sherpa-demo-lumen-bakehouse`), with source mirrored in `demo-stores/`. | Cleaner pull requests and a GitHub token scoped to just those repos. |
| 6 | 2026-10-22 | Next.js 15.5.28. | Earlier 15.5.x releases carry a published security advisory. |
| 7 | 2026-10-27 | Cloud Run services run in `us-east1`. Firestore (`sherpa` database) and the artifacts bucket stay in `us-central1`. | Cloud Run in `us-central1` rejected every deploy in this project, even a stock hello-world image ("Deletion in progress"), while `us-east1` deployed normally. |
| 8 | 2026-10-27 | JS SDK v6 is detected by `https://www.sandbox.paypal.com/web-sdk/v6/core` (or the live host); legacy v5 by `paypal.com/sdk/js?`. | Matches the current JS SDK v6 setup docs. |
| 9 | 2026-10-27 | The shopper never sends sandbox credentials to the model. Sherpa detects PayPal's login page and fills the sandbox buyer itself, masking those fields in screenshots. | Keeps credentials out of prompts, logs and stored screenshots. |
| 10 | 2026-10-27 | Payment confirmations from the computer-use safety system are acknowledged only while the active page is on the allowlist (the store, its preview or PayPal). Anything else stops the run. | Sherpa only ever shops its own sandbox stores with a sandbox buyer; everything else is refused. |
| 11 | 2026-10-27 | Screenshots are stored in Cloud Storage and served through the authenticated agent API, not a public bucket. | Keeps evidence private to the console. |
