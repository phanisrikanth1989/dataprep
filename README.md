# DataPrep
*Last updated: 2026-05-11*

DataPrep is a Python-based ETL execution engine that replaces Talend Open
Studio for 1200+ production jobs. The system has two layers: a converter
that transforms Talend `.item` XML job definitions into JSON configurations,
and an engine that executes those JSON configs. Talend feature parity is
non-negotiable -- any Talend job using the target components must produce
identical results when run through the Python engine.

## Quickstart

Convert a Talend `.item` file to a JSON job config:

```bash
python -m src.converters.talend_to_v1.converter path/to/job.item path/to/job.json
```

Execute a JSON job config:

```bash
python src/v1/engine/engine.py path/to/job.json
```

Jobs using Java expressions (tMap, tJava, tJavaRow) require JVM 11+ on PATH
and the Java bridge JAR built via `mvn package` under
`src/v1/java_bridge/java/`. See `docs/DEPLOYMENT.md` for the full setup.

## Documentation

- `docs/ARCHITECTURE.md` -- system overview, layers, data flow, registry discipline
- `docs/COMPONENT_REFERENCE.md` -- registry-driven inventory of every engine component
- `docs/CONTRIBUTING.md` -- contributor rules (registry+abstract discipline, 95% coverage floor, ASCII-only, atomic commits)
- `docs/DEPLOYMENT.md` -- validated runtime (Linux + JVM 11+), build, run, test gate
- `CLAUDE.md` -- Claude-specific project instructions; takes precedence for Claude-driven work

Detailed authoring patterns live under `docs/v1/patterns/` (engine component
pattern, converter pattern, test patterns, manual component authoring,
BaseComponent reference card).

## License

License details TBD -- internal.
