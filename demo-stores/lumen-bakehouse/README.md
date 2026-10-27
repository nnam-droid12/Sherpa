# Lumen Bakehouse

A fictional bakery that takes preorders for celebration cakes. It is a demo target for Sherpa, built with Next.js and PayPal Orders v2 in the sandbox.

This baseline is intentionally flawed so Sherpa has something to audit and fix. The list of planted issues lives in the Sherpa repo under `docs/SCORECARD.md`.

## Run locally

```bash
npm install
PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=... npm run dev
```

Sandbox only. Never use live PayPal credentials with this store.
