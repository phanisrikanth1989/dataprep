# DataPrep Deployment & Job-Management Architecture

**Document status:** Draft v1.1 (decisions folded in)
**Date:** 2026-06-30
**Owner:** Phani Srikanth
**Audience:** Engineering, DevOps, Release Management

---

## 1. Purpose & Scope

This document describes how Talend-replacement ETL jobs are authored, versioned,
generated, promoted, and run across DEV, UAT, and PROD on Unix (RHEL) servers
using Autosys for scheduling.

It covers three independently-versioned concerns:

1. **DataPrep** - the Python execution engine (the runtime).
2. **DataPrepUI** - the web authoring tool (dev-only).
3. **RecTran** - the artifacts repository (job JSONs, config, scripts, JIL).

Out of scope: internal engine design, converter internals, Talend conversion.

---

## 2. Design Principles

1. **Separate the runtime from the artifacts.** The engine is software released
   on its own cadence; jobs are data promoted continuously. They version
   independently.
2. **One job definition, many environments.** A job's JSON is identical in
   DEV/UAT/PROD. Only environment config (values) changes.
3. **Version everything; copy only deltas.** The full snapshot is always in git;
   git moves only changed files to the server.
4. **Generate structure, never secrets.** Tooling scaffolds config/JIL keys;
   humans/vault supply environment-specific and secret values.
5. **Promote a frozen snapshot forward.** The exact tag approved in UAT is the
   tag deployed to PROD - never rebuilt in between.
6. **ASCII-only artifacts.** Scripts, logs, and JIL stay ASCII for RHEL.

---

## 3. System Overview

```
                         AUTHORING (DEV)
   +------------------+        commit JSON        +-------------------+
   |   DataPrepUI     | ------------------------> |   RecTran (git)   |
   | (login, build    |   only writes <lob>/json/ |  job artifacts    |
   |  job, Generate)  | <-----------------------  |                   |
   +------------------+   reads <lob>/json/*.json  +-------------------+
            |                                              |
            | Generate (templates)                         | promote (tag)
            v                                              v
   writes <lob>/config, <lob>/jil, <lob>/scripts   +-------------------+
                                                   |  UAT / PROD       |
                                                   |  Unix servers     |
                                                   |  engine + git     |
                                                   |  checkout + Autosys|
                                                   +-------------------+
```

Three artifacts travel on two tracks:

- **Engine** (DataPrep): slow track. Tagged release installed per server,
  upgraded deliberately.
- **Job artifacts** (RecTran): fast track. Tagged snapshot promoted
  DEV -> UAT -> PROD continuously.

DataPrepUI is **not** deployed to UAT/PROD - jobs run headless under Autosys.

---

## 4. Repository: RecTran

### 4.1 Layout

```
RecTran/                         (single git repo - "Option B")
  fcc/                           Line of Business
    json/                        job definitions  (UI-managed)
      customer_load.json
      kyc_refresh.json
    config/                      env values        (ops-managed)
      config.dev.json
      config.uat.json
      config.prod.json
    scripts/                     job-specific scripts if any (ops-managed)
    jil/                         Autosys job defs  (generated + ops-tuned)
      fcc_customer_load.jil
  eqmo/                          Line of Business
    json/
    config/
    scripts/
    jil/
  templates/                     shared generation templates (ops-managed)
    config.template.json
    job.template.jil
    run.template.sh
  scripts/                       shared, env-agnostic runtime scripts
    run_job.sh                   one generic runner for all jobs
    deploy.sh                    server-side delta deploy
  release.txt                    pins engine version for this snapshot
  CODEOWNERS
```

Rationale for a single repo (Option B): atomic versioning - one tag captures
jobs + config + scripts + JIL together, so "what is in PROD" is one commit hash.

### 4.2 Folder ownership

| Path               | Owner      | Written by         |
|--------------------|------------|--------------------|
| `*/json/`          | data team  | DataPrepUI         |
| `*/config/`        | ops        | Generate + ops     |
| `*/jil/`           | ops        | Generate + ops     |
| `*/scripts/`       | ops        | ops                |
| `templates/`       | ops        | ops                |
| `scripts/`, root   | ops        | ops                |

---

## 5. DataPrepUI Behaviour

### 5.1 Scope: show only JSONs, across all LOBs

The UI lists and edits **only** job JSONs. It surfaces every LOB's jobs in one
combined view.

- **Read:** fetch the repo tree and keep only paths matching
  `^[^/]+/json/.+\.json$`. This shows all LOBs' jobs and auto-discovers new LOBs
  (e.g. `risk/json/...`) with no code change. config/scripts/jil never match, so
  they are never displayed.
- **Display:** group by first path segment (the LOB).

```
DataPrep - All Jobs
  fcc
    customer_load.json
    kyc_refresh.json
  eqmo
    daily_recon.json
```

- **Write:** path is always `<lob>/json/<name>.json`. The UI has no code path
  that writes outside `*/json/`, so a user cannot touch config/scripts.
  LOB is known on edit (from the path) and chosen on create (dropdown).

### 5.2 Generate feature

After a JSON is saved, a **Generate** action scaffolds the supporting artifacts
from templates.

```
[Generate] for fcc/json/customer_load.json
   1. read the JSON
   2. extract metadata:
        - job name, LOB
        - every context.* / ${context.*} reference  -> config keys
        - I/O hints
   3. collect extra inputs not present in the JSON, via the UI Generate form:
        - schedule (run time / days)
        - dependencies (upstream jobs)
        - target machine
   4. render templates/config.template.json -> fcc/config/config.<env>.json
                templates/job.template.jil   -> fcc/jil/fcc_customer_load.jil
   5. commit onto the current working branch (no separate approval ceremony) so
      the JSON + generated config/JIL travel together in one PR
```

**What Generate produces vs. what humans supply**

- *Config:* the correct **keys** (every context var the job uses), with empty
  placeholder values. Ops (or vault at runtime) fills real per-environment
  values. The UI never writes secrets.
- *JIL:* job name and command derived from the JSON; schedule/machine/
  dependencies from the Generate form or template defaults.
- *Script:* normally none - all jobs share `scripts/run_job.sh`.

**Regeneration is a merge, not an overwrite.** On re-Generate (after a JSON
edit), the generator adds new context keys and preserves existing filled-in
values and hand-tuned JIL schedule/dependencies.

### 5.3 Commit & review flow

All authoring happens on a short-lived **working branch**, never directly on
`main`:

```
1. UI creates/uses a working branch        e.g. ui/fcc/customer_load
2. Save JSON      -> commit to that branch  (fcc/json/customer_load.json)
3. Generate       -> commit to the SAME branch, straight (no own approval):
                       fcc/config/config.<env>.json
                       fcc/jil/fcc_customer_load.jil
4. UI opens ONE pull request from the working branch -> main
5. PR review (CODEOWNERS): data team approves json/, ops approves config/ + jil/
6. Merge to main
```

This reconciles the two commit decisions:

- **JSON authoring goes through a PR** (decision: via PR) - nothing reaches
  `main` unreviewed.
- **Generate commits straight** (decision: commit straight) - it does *not* raise
  its own separate PR; it commits onto the working branch so its output is
  reviewed inside the *same* PR as the JSON.

Net effect: JSON + config + JIL for a change are always one reviewable,
atomically-merged unit. `main` is protected; the only path in is a reviewed PR.

> Confirmed: Generate output is **PR-reviewed**. It commits to the working
> branch (not directly to `main`), so config/JIL land in the same PR as the JSON
> and go through CODEOWNERS review before merge.

---

## 6. Configuration Management

**Engine contract (verified against `engine.py`):** the engine takes default
context from the job JSON's own `context` block, and the *only* external override
is `--context_param KEY=VALUE` (repeatable). There is no separate config-file
load. So context resolves in three layers, last-wins:

```
JSON "context" block        (defaults, committed in the job JSON)
  < config.<env>.json       (per-environment non-secret values)
  < server env vars         (secrets)
```

- `config.<env>.json` is therefore a **flat key->value map**, not a job config.
  `run_job.sh` reads it and expands each entry into a `--context_param` override
  (section 9.4). All three env files share the same keys; only values differ.
- **Versioning is orthogonal to environment.** One snapshot/tag contains
  dev+uat+prod config together. The environment is selected at *run time*
  (`run_job.sh <job> prod`), not by making separate versions.
- **Secrets are never committed - they come from server environment variables.**
  Each UAT/PROD server sets secret values (DB passwords, etc.) as OS env vars,
  managed by the deployment tooling (uDeploy) outside git. Committed config holds
  only non-secret values and references.
- **How env-var secrets reach the engine:** `run_job.sh` maps the required env
  vars into engine context parameters at launch, e.g.
  `--context_param db_password="$FCC_DB_PASSWORD"`. The config file supplies the
  non-secret keys; env vars supply the secret ones. Nothing secret is ever
  written to disk in the repo.

---

## 7. Version Control Strategy

- **`main`** = DEV / integration. UI commits land here (into `*/json/`).
- **Tags = deployed snapshots.** The **release manager** cuts a tag on `main`
  after the relevant PRs merge, named `release-YYYY.MM.DD.NN` (e.g.
  `release-2026.06.30.01`; `NN` = sequence within a day). Tags are immutable -
  the auditable record of "what ran."
- **The same tag flows UAT -> PROD.** UAT checks out the tag, tests, signs off;
  PROD checks out the *same* tag. Never retag between UAT and PROD.
- **`release.txt`** pins the engine version tested with this snapshot:

  ```
  engine: v3.2
  ```

- **Access control via CODEOWNERS** (enforced on PRs with branch protection):

  ```
  /*/config/    @ops-team
  /*/jil/       @ops-team
  /*/scripts/   @ops-team
  /templates/   @ops-team
  /*/json/      @data-team
  ```

  Because all changes flow through PRs into a protected `main` (section 5.3),
  CODEOWNERS is enforced: a PR touching `*/config/` or `*/jil/` cannot merge
  without ops approval, and `*/json/` needs data-team approval. The UI's path
  scoping plus CODEOWNERS together control who can change what.

---

## 8. Promotion Flow

```
  DataPrepUI commits JSON
          |
          v
  main (DEV)  --- tag release-2026.06.30 --->  UAT server checks out tag
                                                     |
                                               test + sign-off
                                                     |
                                                     v
                                          PROD server checks out SAME tag
                                                     |
                                               Autosys runs run_job.sh
```

Engine upgrades run on a parallel, slower track: tag engine vX -> deploy to UAT
-> soak -> deploy to PROD -> bump `release.txt`.

---

## 9. Server Layout & Deployment

### 9.0 CI/CD pipeline (Lightspeed / TeamCity / uDeploy)

The promotion in section 8 is driven by the enterprise toolchain, not by hand:

```
PR merged to main
      |
   [TeamCity]  CI: validate JSON, lint scripts/JIL, package the snapshot,
      |        cut/record the release tag (release-YYYY.MM.DD)
      v
   [uDeploy]   CD to UAT: on the UAT server, checkout the tag (delta),
      |                   apply only changed/deleted JILs, set CURRENT_RELEASE
      v
   UAT test + sign-off gate (approval in uDeploy)
      |
   [uDeploy]   CD to PROD: deploy the SAME tag to the PROD server
      |                    (identical steps; no rebuild)
      v
   Lightspeed orchestrates the pipeline definition and gates end to end.
```

Responsibilities:

- **TeamCity (CI):** triggered on merge to `main`. Runs validation (e.g. the
  converter's JSON validator, shell/JIL lint), produces the immutable snapshot,
  and records the release tag. No deployment.
- **uDeploy (CD):** performs the actual deployment on each target server -
  effectively running `deploy.sh` (section 9.3): git checkout of the tag, apply
  changed JILs to Autosys, update `CURRENT_RELEASE`. Holds the UAT->PROD approval
  gate and sets the per-server secret env vars (section 6).
- **Lightspeed:** the pipeline-as-definition / orchestration layer that wires
  TeamCity and uDeploy together and enforces the promotion gates.

`deploy.sh` (9.3) and `run_job.sh` (9.4) are the scripts uDeploy invokes on the
target; they remain the source of truth for *what* happens on the box, while
uDeploy controls *when* and *with which approvals*.

### 9.1 On-server layout

```
/app/dataprep/
  engine/                 tagged engine release (matches release.txt)
  artifacts/              git checkout of a RecTran tag
    fcc/   eqmo/   scripts/   templates/
  logs/
  CURRENT_RELEASE         records the live tag (for delta deploy)
```

### 9.2 Delta deployment

Principle: the **tag** is the full snapshot, but only the **diff** is acted on.

- **Files (json/config/scripts):** `git checkout <tag>` updates only changed
  files; unchanged jobs are untouched. A new JSON is simply present on disk and
  read by the engine at the job's next run - no extra action.
- **JIL:** unlike files, JIL must be actively loaded into Autosys
  (`jil < file`). Loading 1200 JILs every release is wrong - apply only the
  changed ones, found via `git diff`.

### 9.3 deploy.sh

```bash
#!/bin/bash
# deploy.sh <new_tag> <env>
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
```

The `git diff` output doubles as the change report for a release ticket.

### 9.4 run_job.sh (shared runner)

```bash
#!/bin/bash
# run_job.sh <lob> <job_name> <env>
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
```

This matches the verified engine contract (section 6): the JSON carries default
context, `config.<env>.json` overrides per environment, env vars override
secrets - all via `--context_param`, last-wins.

---

## 10. Autosys / JIL

- One `templates/job.template.jil`; Generate stamps one JIL per job.
- JIL command always calls the shared runner:
  `command: /app/dataprep/artifacts/scripts/run_job.sh fcc customer_load $ENV`
- Standardize `std_out_file` / `std_err_file` under `/app/dataprep/logs/`.
- Schedule, machine, and dependencies are JIL inputs the JSON does not carry -
  captured in the Generate form or defaulted in the template.
- Deploy applies only changed/deleted JILs (section 9).

---

## 11. Rollback

- Redeploy the previous tag: `deploy.sh release-2026.06.29 prod`. Git applies the
  reverse delta; only changed JILs reload.
- Because tags are immutable full snapshots, rollback is deterministic.
- Engine rollback is independent: reinstall the prior engine release and restore
  `release.txt`.

---

## 12. Edge Cases & Rules

- **Job deletion:** removing JSON+JIL deletes files on checkout, but the Autosys
  job persists - handled by the `--diff-filter=D` delete loop in deploy.sh.
- **Regeneration:** merge, never clobber filled config values or tuned JIL.
- **New LOB:** add `risk/{json,config,scripts,jil}/`; UI auto-discovers it via
  the tree filter; no UI change.
- **Line endings:** enforce LF on `*.sh` via `.gitattributes` (Windows authoring,
  RHEL execution).
- **Dependency pinning:** pin engine Python deps so UAT/PROD match DEV.
- **Java bridge:** if jobs use `{{java}}`/tMap, the bridge JAR must be present and
  JVM 11+ on PATH on the server.

---

## 13. Resolved Decisions

1. **Commit flow:** UI authoring goes through a **PR** into protected `main`;
   CODEOWNERS enforced. (Section 5.3)
2. **Generate output:** **PR-reviewed** - commits onto the working branch (not
   direct-to-main), so config/JIL are reviewed inside the JSON's PR. (Section 5.3)
3. **Deployment mechanism:** **Lightspeed / TeamCity / uDeploy** - TeamCity for
   CI + packaging, uDeploy for gated deployment, Lightspeed for orchestration.
   (Section 9.0)
4. **Secrets source:** **server environment variables**, set per server by
   uDeploy and mapped into engine context by `run_job.sh`. (Section 6)
5. **JIL inputs** (schedule/machine/dependencies): captured in the **UI Generate
   form**. (Section 5.2)
6. **Engine context contract:** the **`--context_param` way** - verified the
   engine has no config-file load; `config.<env>.json` is a flat key->value map
   expanded into `--context_param` overrides. (Sections 6, 9.4)
7. **Tag cutting & naming:** the **release manager** cuts the tag on `main` after
   PRs merge. Naming: **`release-YYYY.MM.DD.NN`** (`NN` = 2-digit sequence for
   multiple releases in a day), e.g. `release-2026.06.30.01`. The same tag flows
   UAT -> PROD. (Sections 7, 8)

### Remaining to confirm

- Branch-protection specifics on `main` (required reviewers, required status
  checks - e.g. the TeamCity validation build must pass before merge).
- Names of the actual secret env vars per LOB (e.g. `FCC_DB_PASSWORD`) so
  `run_job.sh` injects the right ones.

---

## 14. Glossary

- **LOB** - Line of Business (fcc, eqmo).
- **Artifact** - a versioned file produced for a job (JSON, config, script, JIL).
- **Snapshot / tag** - an immutable, complete state of RecTran.
- **Engine** - the DataPrep Python runtime that executes a job JSON.
- **JIL** - Autosys Job Information Language; the scheduler's job definition.
```
