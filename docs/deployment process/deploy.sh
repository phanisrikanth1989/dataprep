#!/bin/bash
# deploy.sh <new_tag> <env>
# Server-side delta deploy, invoked by uDeploy on each target server.
# See RecTran-Deployment-Design.md section 9.3.
set -euo pipefail

NEW_TAG="$1"; ENV="$2"
REPO_DIR="/app/dataprep/artifacts"
STATE_FILE="/app/dataprep/CURRENT_RELEASE"

cd "$REPO_DIR"
OLD_TAG="$(cat "$STATE_FILE" 2>/dev/null || echo "")"

# Git transfers only changed files.
git fetch --tags --prune
git checkout -q "tags/$NEW_TAG"

# Apply only the JILs that changed since the last deploy.
if [ -n "$OLD_TAG" ]; then
    CHANGED="$(git diff --name-only "$OLD_TAG" "$NEW_TAG" -- '*/jil/' | grep '\.jil$' || true)"
    DELETED="$(git diff --name-only --diff-filter=D "$OLD_TAG" "$NEW_TAG" -- '*/jil/' | grep '\.jil$' || true)"
else
    CHANGED="$(git ls-files '*/jil/' | grep '\.jil$' || true)"   # first deploy
    DELETED=""
fi

for f in $CHANGED; do
    echo "load JIL: $f"
    jil < "$f"
done

for f in $DELETED; do
    job="$(basename "$f" .jil)"
    echo "delete JIL job: $job"
    echo "delete_job: $job" | jil
done

echo "$NEW_TAG" > "$STATE_FILE"
echo "Deployed $NEW_TAG to $ENV (previous: ${OLD_TAG:-none})"
