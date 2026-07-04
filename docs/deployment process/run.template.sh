#!/bin/bash
# ------------------------------------------------------------------
# Optional per-job wrapper for {{ lob }}/{{ job_name }}.
# Most jobs call scripts/run_job.sh directly; generate this only when a
# job needs custom pre/post steps. See RecTran-Deployment-Design.md 5.2.
# ------------------------------------------------------------------
set -euo pipefail

ENV="${1:?usage: $(basename "$0") <env>}"
ROOT="/app/dataprep"

# ---- pre-job ----
{{ pre_hook }}

# ---- run the job via the shared runner ----
"$ROOT/artifacts/scripts/run_job.sh" {{ lob }} {{ job_name }} "$ENV"

# ---- post-job ----
{{ post_hook }}
