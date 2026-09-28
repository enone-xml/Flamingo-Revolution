#!/bin/sh
# Auto-updater: every few minutes, check GitHub for new commits on main.
# When one has passed the "tests" workflow, pull it and rebuild the site.
# Runs in the "updater" container (see docker-compose.yml, profile "autoupdate").
set -u

REPO=${GITHUB_REPO:-enone-xml/Flamingo-Revolution}
BRANCH=${UPDATE_BRANCH:-main}
INTERVAL=${UPDATE_INTERVAL_SECONDS:-300}
PROJECT=${COMPOSE_PROJECT:-flamingo_revolution}
cd /repo || exit 1
git config --global --add safe.directory /repo

log() { echo "updater: $*"; }
log "watching $REPO@$BRANCH every ${INTERVAL}s"

while true; do
  if ! git fetch -q https://github.com/$REPO.git "$BRANCH" 2>/tmp/fetch.err; then
    log "git fetch failed (repo private or offline?): $(tail -n1 /tmp/fetch.err)"
  else
    local_sha=$(git rev-parse HEAD)
    remote_sha=$(git rev-parse FETCH_HEAD)
    if [ "$local_sha" != "$remote_sha" ]; then
      # Only deploy commits whose tests passed on GitHub.
      conclusion=$(wget -qO- "https://api.github.com/repos/$REPO/commits/$remote_sha/check-runs?check_name=test" 2>/dev/null \
        | tr ',' '\n' | grep '"conclusion"' | head -n1 | cut -d'"' -f4)
      if [ "$conclusion" != "success" ]; then
        log "new commit ${remote_sha%${remote_sha#???????}} waiting for tests (status: ${conclusion:-pending})"
      elif ! git merge-base --is-ancestor "$local_sha" "$remote_sha"; then
        log "local branch has commits that aren't on GitHub; not updating automatically"
      elif [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        log "local files were edited by hand; not updating automatically (commit or discard them)"
      else
        log "updating ${local_sha%${local_sha#???????}} -> ${remote_sha%${remote_sha#???????}}"
        if [ -n "${UPDATE_DRY_RUN:-}" ]; then
          git merge -q --ff-only "$remote_sha" && log "dry run: would rebuild now"
          sleep "$INTERVAL"; continue
        fi
        git merge -q --ff-only "$remote_sha" \
          && docker compose -p "$PROJECT" up -d --build web publisher \
          && log "update deployed OK" \
          || log "update FAILED, will retry next round"
      fi
    fi
  fi
  sleep "$INTERVAL"
done
