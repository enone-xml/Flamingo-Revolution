#!/usr/bin/env bash
# Upload the static site to Cloudflare Pages whenever the news changed,
# and at least once an hour so "Updated X min ago" stays honest.
# Needs CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID and CF_PAGES_PROJECT (see .env).
set -uo pipefail

SITE=/export/site
MAX_QUIET=${PUBLISH_MAX_QUIET_SECONDS:-3600}
last_hash=""
last_deploy=0

: "${CLOUDFLARE_API_TOKEN:?set CLOUDFLARE_API_TOKEN in .env}"
: "${CLOUDFLARE_ACCOUNT_ID:?set CLOUDFLARE_ACCOUNT_ID in .env}"
: "${CF_PAGES_PROJECT:?set CF_PAGES_PROJECT in .env}"

echo "publisher: watching $SITE for project $CF_PAGES_PROJECT"
while true; do
  if [ -f "$SITE/data/version.json" ]; then
    hash=$(grep -o '"content_hash": *"[^"]*"' "$SITE/data/version.json" | cut -d'"' -f4)
    now=$(date +%s)
    if [ "$hash" != "$last_hash" ] || [ $((now - last_deploy)) -ge "$MAX_QUIET" ]; then
      # Copy first, so the next export can't change files mid-upload.
      rm -rf /tmp/site && cp -r "$SITE" /tmp/site
      echo "publisher: deploying (content $hash)"
      if wrangler pages deploy /tmp/site --project-name "$CF_PAGES_PROJECT" --branch main --commit-dirty=true >/tmp/deploy.log 2>&1; then
        last_hash=$hash
        last_deploy=$now
        echo "publisher: deployed OK at $(date -u +%H:%M:%SZ)"
        # Optional: tell healthchecks.io we're alive; it emails you if pings stop.
        [ -n "${HEALTHCHECK_URL:-}" ] && curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" >/dev/null
      else
        echo "publisher: deploy FAILED, retrying in 10 minutes:"
        tail -n 15 /tmp/deploy.log
        sleep 540
      fi
    fi
  else
    echo "publisher: no export yet, waiting"
  fi
  sleep 60
done
