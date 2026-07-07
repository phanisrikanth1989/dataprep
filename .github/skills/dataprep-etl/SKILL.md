---
name: dataprep-etl
description: >-
  Code-verified knowledge for building DataPrep ETL jobs on the Python engine: per-component
  config keys and allowed values, config landmines, the job.json envelope contract, and the
  join/lookup and transform patterns. Use when interpreting an ETL requirement, designing the
  flow, configuring components, or assembling/repairing a job.json.
---
# DataPrep ETL knowledge

Code-verified knowledge for building DataPrep ETL jobs (sources -> transformations -> outputs) on the Python engine that replaces Talend.

Load the resource that fits the task:

- `config-reference.md` - every allowed component config key + its resolved allowed values.
- `landmines.md` - config traps that silently produce wrong output; respect each.
- `job-envelope.md` - the exact job.json wiring shape the engine requires.

Validate any component config with `python -m agents.tools.validate_config --type T --config c.json` and test a whole job with `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR` before claiming it is correct.
