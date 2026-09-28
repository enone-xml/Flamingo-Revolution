#!/usr/bin/env bash
# Deploy the latest version from GitHub. Run on the server from /opt/flamingo.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build
docker image prune -f >/dev/null
sleep 5
curl -fsS "https://$(grep ^DOMAIN= .env | cut -d= -f2)/health" && echo && echo "Deployed OK"
