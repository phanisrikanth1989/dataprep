---
name: dataprep-recon
description: >-
  Code-verified knowledge for building the recon team's DataPrep ENRICHMENT ETL jobs: per-component
  config keys and allowed values, config landmines, the job.json envelope contract, and the tMap
  lookup-join enrichment pattern. Use when interpreting an enrichment requirement, designing the
  flow, configuring components, or assembling/repairing a job.json.
---
# DataPrep recon knowledge

recon = the recon TEAM; this tool does data ENRICHMENT/prep, not the reconciliation (SmartStream TLM reconciles).

Load the resource that fits the task:

- `config-reference.md` - every allowed component config key + its resolved allowed values.
- `landmines.md` - config traps that silently produce wrong output; respect each.
- `job-envelope.md` - the exact job.json wiring shape the engine requires.

Validate any component config with `python -m agents.tools.validate_config --type T --config c.json` and test a whole job with `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR` before claiming it is correct.
