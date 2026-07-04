#!/bin/bash
# run_job.sh <lob> <job_name> <env>
# Shared, env-agnostic runner. Called by Autosys (via JIL) for every job.
# See RecTran-Deployment-Design.md section 9.4.
set -euo pipefail

LOB="$1"; JOB="$2"; ENV="$3"
ROOT="/app/dataprep"
JSON="$ROOT/artifacts/$LOB/json/$JOB.json"
CONFIG="$ROOT/artifacts/$LOB/config/config.$ENV.json"

cd "$ROOT/engine"

# Expand the flat config file (key:value JSON) into repeated --context_param
# overrides. Each key and value becomes a separate argv element, so values may
# contain spaces safely.
mapfile -t CTX < <(python -c '
import json, sys
with open(sys.argv[1]) as f:
    for k, v in json.load(f).items():
        print("--context_param"); print(f"{k}={v}")
' "$CONFIG")

# Secrets come from server env vars (set by uDeploy), injected as additional
# overrides so nothing secret is ever written to the repo.
python src/v1/engine/engine.py "$JSON" \
    "${CTX[@]}" \
    --context_param db_password="${DB_PASSWORD:-}"
