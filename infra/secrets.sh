#!/usr/bin/env bash
# Push secret values from the local .env into Secret Manager without printing them.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-nixora-project}"
ENV_FILE="${1:-$(cd "$(dirname "$0")/.." && pwd)/.env}"
NAMES=(SHERPA_API_KEY KERNEL_API_KEY PAYPAL_CLIENT_ID PAYPAL_CLIENT_SECRET PAYPAL_WEBHOOK_ID
       PAYPAL_SANDBOX_BUYER_EMAIL PAYPAL_SANDBOX_BUYER_PASSWORD GITHUB_TOKEN)

[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE" >&2; exit 1; }

for name in "${NAMES[@]}"; do
  value="$(grep -E "^${name}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
  if [ -z "$value" ] || [[ "$value" == your-* ]] || [[ "$value" == *xxx ]] || [ "$value" = "change-me" ]; then
    echo "skip   $name (empty or placeholder)"
    continue
  fi
  if ! gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1; then
    gcloud secrets create "$name" --project "$PROJECT" --replication-policy automatic >/dev/null
  fi
  printf '%s' "$value" | gcloud secrets versions add "$name" --project "$PROJECT" --data-file=- >/dev/null
  echo "update $name"
done
