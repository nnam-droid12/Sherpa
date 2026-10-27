#!/usr/bin/env bash
# Reset the demo store repos to their flawed baseline so the demo can be run again.
# Closes open Sherpa PRs, deletes sherpa/* branches and force-resets main to the `baseline` tag.
# Usage: infra/reset-demo.sh [ember-oak|lumen-bakehouse|all]
set -euo pipefail

OWNER="${DEMO_OWNER:-nnam-droid12}"
TARGET="${1:-all}"
PROJECT="${GOOGLE_CLOUD_PROJECT:-nixora-project}"
REGION="${REGION:-us-east1}"

reset_store() {
  local store="$1" repo="$OWNER/sherpa-demo-$1"
  echo "resetting $repo"
  for pr in $(gh pr list -R "$repo" --state open --json number,headRefName \
      -q '.[] | select(.headRefName | startswith("sherpa/")) | .number'); do
    gh pr close "$pr" -R "$repo" --comment "Closed by demo reset." >/dev/null
  done
  for ref in $(gh api "repos/$repo/git/matching-refs/heads/sherpa/" -q '.[].ref'); do
    gh api -X DELETE "repos/$repo/git/$ref" >/dev/null
  done
  local sha
  sha="$(gh api "repos/$repo/git/ref/tags/baseline" -q .object.sha)"
  gh api -X PATCH "repos/$repo/git/refs/heads/main" -f sha="$sha" -F force=true >/dev/null
  # Drop preview tags from the store's Cloud Run service so old preview URLs stop resolving.
  local tags
  tags="$(gcloud run services describe "store-$store" --project "$PROJECT" --region "$REGION" \
    --format 'value(spec.traffic[].tag)' 2>/dev/null | tr ';,' '\n\n' | grep '^pr-' || true)"
  if [ -n "$tags" ]; then
    gcloud run services update-traffic "store-$store" --project "$PROJECT" --region "$REGION" \
      --remove-tags "$(echo "$tags" | paste -sd, -)" --quiet >/dev/null
  fi
}

case "$TARGET" in
  all) reset_store ember-oak; reset_store lumen-bakehouse ;;
  ember-oak|lumen-bakehouse) reset_store "$TARGET" ;;
  *) echo "unknown store $TARGET" >&2; exit 1 ;;
esac
echo "done"
