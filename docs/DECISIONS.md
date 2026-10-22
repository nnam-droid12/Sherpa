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
