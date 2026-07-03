---
name: dataprep-recon
description: >-
  Code-verified knowledge for building DataPrep recon ETL jobs: per-component config keys and
  allowed values, config landmines, the job.json envelope contract, and the tMap match/break
  patterns. Use when interpreting a recon requirement, designing the flow, configuring components,
  or assembling/repairing a recon job.json.
---
# DataPrep recon knowledge

Load the resource that fits the task:

- `config-reference.md` - every allowed component config key + its resolved allowed values.
- `landmines.md` - config traps that silently produce wrong output; respect each.
- `job-envelope.md` - the exact job.json wiring shape the engine requires.

Validate any component config with `python -m agents.tools.validate_config --type T --config c.json` and test a whole job with `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR` before claiming it is correct.
