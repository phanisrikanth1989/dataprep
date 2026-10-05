# Context Map

## Contexts

- [ETL Studio](./CONTEXT.md) — the VS Code extension where agents turn a request or a BRD into a verified job
- [v2 Engine](./src/v2/CONTEXT.md) — the pure-Python, Polars-based engine that runs v1 job configs

## Relationships

- **v2 Engine → v1 engine**: v2 runs v1 job configs; v1's output for the same job is v2's answer key. The v1 engine (`src/v1/`) has no glossary of its own.
- **ETL Studio → v1 engine**: ETL Studio builds and verifies jobs against the v1 engine. It does not use v2.
