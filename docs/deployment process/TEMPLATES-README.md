# RecTran templates & tooling - draft starter kit

Drafts that implement the design in `RecTran-Deployment-Design.md`. Drop the
templates into `RecTran/templates/`, the runtime scripts into `RecTran/scripts/`,
and wire `generate.py` into the DataPrepUI "Generate" action.

## Files

| File                   | Goes to               | Purpose                                            |
|------------------------|-----------------------|----------------------------------------------------|
| `config.template.json` | `templates/`          | Jinja template -> flat key:value config skeleton   |
| `job.template.jil`     | `templates/`          | Jinja template -> one Autosys JIL per job          |
| `run.template.sh`      | `templates/`          | Jinja template -> optional per-job wrapper script  |
| `generate.py`          | UI backend / `tools/` | Scans a job JSON, renders the templates            |
| `run_job.sh`           | `scripts/`            | Shared runner Autosys calls for every job          |
| `deploy.sh`            | `scripts/`            | Server-side delta deploy (uDeploy invokes it)      |

## How generate.py works (design section 5.2)

1. Reads the job JSON and extracts every `context.*` / `${context.*}` reference.
2. Writes `config.<env>.json` for each env with those keys (values empty).
   **Merge-safe:** re-running adds new keys and keeps already-filled values.
3. Writes `<lob>/jil/<lob>_<job>.jil` from the JIL template + form inputs
   (machine, owner, schedule, dependencies). **Does not overwrite an existing
   JIL** unless `--force-jil`, so hand-tuned schedules survive.
4. Optionally writes a per-job wrapper script with `--with-script`.

Example:

```
python generate.py fcc/json/customer_load.json --lob fcc \
    --machine batch01 --owner etluser \
    --days-of-week "mo,tu,we,th,fr" --start-times "02:00" \
    --depends fcc_upstream_a
```

Requires Jinja2 (`pip install jinja2`).

## Key conventions baked in

- **Secrets never land in the repo.** Config holds only non-secret values; secret
  values come from server env vars, injected by `run_job.sh` at run time
  (section 6).
- **One JIL works in UAT and PROD.** The JIL command passes `$ENV`, a box-level
  variable (`uat` on the UAT server, `prod` on the PROD server). The same tag
  deploys to both (section 5.3 / 7).
- **ASCII + LF.** All generated files are ASCII and written with LF newlines for
  RHEL (sections 2, 12).

## Still to fill in before use

- Real `--machine` / `--owner` values per environment (defaults are `REPLACE_ME`).
- The actual secret env-var names (e.g. `FCC_DB_PASSWORD`) in `run_job.sh`.
- Confirm the engine path in `run_job.sh` matches the deployed engine location.
