#!/usr/bin/env bash
# Daily database backup. Cron runs this at 03:00 (see DEPLOY.md).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T web python -m app.backup
