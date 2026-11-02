#!/usr/bin/env bash
# Idempotent deploy of Sherpa services to Cloud Run.
# Usage: infra/deploy.sh [agent|web|stores|all]
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-nixora-project}"
REGION="${REGION:-us-east1}"
SA="sherpa-runtime@${PROJECT}.iam.gserviceaccount.com"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-all}"

gcloud config set project "$PROJECT" >/dev/null

ensure_registry() {
  gcloud artifacts repositories describe sherpa --location "$REGION" >/dev/null 2>&1 ||
    gcloud artifacts repositories create sherpa --repository-format docker --location "$REGION" --quiet
}

ensure_service_account() {
  if ! gcloud iam service-accounts describe "$SA" >/dev/null 2>&1; then
    gcloud iam service-accounts create sherpa-runtime --display-name "Sherpa runtime"
  fi
  # Only touch the project policy for roles that are missing, so parallel deploys don't race on it.
  local have
  have="$(gcloud projects get-iam-policy "$PROJECT" --flatten 'bindings[].members' \
    --filter "bindings.members:serviceAccount:$SA" --format 'value(bindings.role)')"
  for role in roles/aiplatform.user roles/secretmanager.secretAccessor roles/datastore.user \
              roles/run.developer roles/cloudbuild.builds.editor roles/storage.admin \
              roles/artifactregistry.writer roles/logging.logWriter; do
    grep -qx "$role" <<<"$have" && continue
    gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" \
      --role "$role" --condition None >/dev/null
  done
  # Preview deploys run Cloud Run revisions as the runtime SA.
  if ! gcloud iam service-accounts get-iam-policy "$SA" --format 'value(bindings.role)' \
      | grep -q roles/iam.serviceAccountUser; then
    gcloud iam service-accounts add-iam-policy-binding "$SA" --member "serviceAccount:$SA" \
      --role roles/iam.serviceAccountUser >/dev/null
  fi
}

secret_flags() {
  local flags=""
  for name in "$@"; do
    if gcloud secrets describe "$name" >/dev/null 2>&1; then
      flags+="${name}=${name}:latest,"
    fi
  done
  echo "${flags%,}"
}

url_of() {
  gcloud run services describe "$1" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true
}

deploy_agent() {
  local secrets demo_env
  demo_env="DEMO_EMBER_OAK_URL=$(url_of store-ember-oak),DEMO_LUMEN_URL=$(url_of store-lumen-bakehouse)"
  demo_env+=",SHERPA_PUBLIC_URL=$(url_of sherpa-agent)"
  secrets="$(secret_flags SHERPA_API_KEY KERNEL_API_KEY PAYPAL_CLIENT_ID PAYPAL_CLIENT_SECRET \
    PAYPAL_WEBHOOK_ID PAYPAL_SANDBOX_BUYER_EMAIL PAYPAL_SANDBOX_BUYER_PASSWORD GITHUB_TOKEN)"
  gcloud run deploy sherpa-agent --source "$ROOT/services/agent" --region "$REGION" \
    --service-account "$SA" --allow-unauthenticated --memory 2Gi --cpu 2 --timeout 3600 \
    --concurrency 40 --min-instances 1 --max-instances 1 --no-cpu-throttling \
    --set-env-vars "SHERPA_ENV=cloud,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},GCP_REGION=$REGION,$demo_env" \
    ${secrets:+--set-secrets "$secrets"} --quiet
}

deploy_web() {
  local agent_url secrets
  agent_url="$(gcloud run services describe sherpa-agent --region "$REGION" --format 'value(status.url)')"
  secrets="$(secret_flags SHERPA_API_KEY)"
  gcloud run deploy sherpa-web --source "$ROOT/apps/web" --region "$REGION" \
    --service-account "$SA" --allow-unauthenticated --memory 512Mi \
    --set-env-vars "SHERPA_AGENT_URL=$agent_url" \
    ${secrets:+--set-secrets "$secrets"} --quiet
}

deploy_stores() {
  local secrets
  secrets="$(secret_flags PAYPAL_CLIENT_ID PAYPAL_CLIENT_SECRET PAYPAL_WEBHOOK_ID)"
  for store in ember-oak lumen-bakehouse; do
    [ -d "$ROOT/demo-stores/$store" ] || continue
    # One instance: demo carts for the Cart API live in memory.
    gcloud run deploy "store-$store" --source "$ROOT/demo-stores/$store" --region "$REGION" \
      --service-account "$SA" --allow-unauthenticated --memory 512Mi --max-instances 1 \
      ${secrets:+--set-secrets "$secrets"} --quiet
  done
}

# IAM and registry setup only need to run once per project; re-run with SETUP=1 to repair them.
if [ "${SETUP:-0}" = "1" ] || ! gcloud iam service-accounts describe "$SA" >/dev/null 2>&1; then
  ensure_service_account
  ensure_registry
fi
case "$TARGET" in
  agent) deploy_agent ;;
  web) deploy_web ;;
  stores) deploy_stores ;;
  all)
    deploy_stores
    deploy_agent
    # The agent's own URL is only known after its first deploy, so refresh it afterwards.
    gcloud run services update sherpa-agent --region "$REGION" \
      --update-env-vars "SHERPA_PUBLIC_URL=$(url_of sherpa-agent)" --quiet >/dev/null
    deploy_web
    ;;
  *) echo "unknown target $TARGET" >&2; exit 1 ;;
esac
