# DataPrep -- Codebase Understanding

A durable, whole-repo understanding of the DataPrep project (a Talend -> Python ETL
migration engine). Produced by a 16-agent parallel deep-read of the entire repository,
synthesized into the documents below, and audited by an adversarial critic against the
real source. Every high-severity claim here was verified against HEAD, not inferred.

> Snapshot taken at branch `claude/peaceful-gates-f1e530` == `feature/sync_repo_latest`
> (commit `bafc8e7`). Line numbers may drift; the prose and file references are accurate
> as of this commit.

## Read in this order

| # | Document | What it covers |
|---|----------|----------------|
| 00 | [System Overview](00-system-overview.md) | The big picture: converter -> JSON -> engine pipeline, tech stack, entry points, cross-cutting concepts, glossary. **Start here.** |
| 01 | [Converter Layer](01-converter-layer.md) | Talend `.item` XML -> JSON: the 12-step pipeline, XML parsing, ComponentConverter ABC + registry, expression/`{{java}}` marking, trigger mapping, validation, component catalog. |
| 02 | [Engine Core & Services](02-engine-core.md) | `ETLEngine`, execution plan/executor, output routing, `BaseComponent`/`BaseIterateComponent` template methods, GlobalMap, ContextManager, TriggerManager, 3-phase expression resolution. |
| 03 | [Engine Components Catalog](03-engine-components-catalog.md) | Table-driven catalog of every engine component by category (file in/out, transform, aggregate, context, control, iterate) with Talend equivalents and parity notes. |
| 04 | [tMap Engine & Java/Groovy Bridge](04-tmap-and-java-bridge.md) | The two trickiest subsystems: the tMap engine (lookups, compiled scripts, reject routing) and the Py4J + Apache Arrow Java bridge. |
| 05 | [Database Layer (Oracle/MSSQL)](05-database-layer.md) | The newest code: Oracle/MSSQL connection managers + all DB components, SQL emission, identifier handling (ORA-00942), transactions, reliability. |
| 06 | [API, Tooling & Coverage](06-api-tooling-coverage.md) | The HTTP API, Python routines, build/config, and the **95% per-module coverage gate** (how it works, what is in/out of scope). |
| 07 | [Findings, Risks & Improvements](07-findings-and-risks.md) | The actionable punch-list: all 163 findings prioritized by severity, plus strengths to preserve and open questions. |

## State of the branch (must read)

Phase 1 surfaced that **the engine package did not import** on this branch. Three
regressions from the post-lock commits blocked everything downstream (including any
coverage measurement, because the test `conftest` imports `ETLEngine`):

| Blocker | File | Cause | Introduced by | Status |
|---------|------|-------|---------------|--------|
| `SyntaxError` (package will not import) | `src/v1/engine/engine.py:225` | Missing comma before `output_id=` in the second `add_trigger(...)` call | commit `0ad1ee0` | **FIXED** -- comma restored; package imports, 8424 tests collect |
| Trigger subsystem non-functional | `src/v1/engine/trigger_manager.py:142` | `def add_trigger` dedented to module level; all other `TriggerManager` methods became nested closures | commit `0ad1ee0` | **FIXED** -- `add_trigger` re-indented; all 13 `TriggerManager` methods restored |
| `tOracleOutput` fully broken | `src/v1/engine/components/database/oracle_output.py` | `IDENTIFIER_RE` NameError (constant is `_IDENTIFIER_RE`); `qualified_table()` defined but called as `self._qualified_table()`; undefined `schema` local | Oracle refactor | **OPEN** -- out of scope for the import-unblock; tracked in doc 05 / doc 07 |

The two import-blockers were fixed to unblock coverage measurement (Phase 2). The
`oracle_output.py` runtime breakage remains open and is a candidate for the Phase 3
stabilization/coverage work. See [05-database-layer.md](05-database-layer.md) and
[07-findings-and-risks.md](07-findings-and-risks.md) for details.

## Findings at a glance

163 findings total: **17 high, 47 medium, 99 low** -- broken down as
29 bugs, 25 risks, 54 smells, 17 improvements, and 38 "good" (strengths to preserve).

## How these docs were produced

16 parallel reader agents (one per subsystem, whole repo) -> 8 synthesis writers ->
1 adversarial critic that audited the docs against source. The critic's verdict: the
factual claims are "unusually high-quality and trustworthy ... every high-severity bug
and contract-mismatch claim spot-checked against source was accurate, often down to the
exact line number." Treat the prose as reliable and re-verify exact line numbers before
editing, since the tree moves.
