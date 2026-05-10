---
phase: 14
slug: coverage-push-to-95-per-module-floor
status: locked
measured: 2026-05-11
gate_exit_code: 0
in_scope_modules: 181
overall_percent: 98.3
---

# Phase 14 -- Verification & Acceptance Evidence

> Captured at closeout per Plan 14-12 Task 14-12-007.
> Cross-references: `14-COVERAGE.md` (final per-module table), `14-coverage.json` (machine-readable artifact), `14-PHASE-SUMMARY.md` (retrospective), Phase 13 `13-VERIFICATION.md` (format reference).

---

## Acceptance Criteria

### TEST-11: Per-module line coverage >=95% across `src/v1/engine/` and `src/converters/` (excl. `complex_converter/`)

- **Evidence:** `14-COVERAGE.md` per-module table shows all 181 in-scope modules at >=95.0% line coverage; `14-coverage.json` `files[*].summary.percent_covered` parsed by `scripts/check_per_module_coverage.py --floor 95` exits 0 with `PASS: all 181 in-scope modules at >= 95.0% line coverage`.
- **No-regression guard:** all Phase 13 PASS modules still PASS (see No-Regression Check below).
- **D-C3 enforcement:** zero inline `# pragma: no cover` annotations in scope (`grep -rn "pragma: no cover" src/v1/engine src/converters/talend_to_v1` returns nothing); narrow allowlist (`__main__`, `@abstractmethod`, `raise NotImplementedError`) enforced via `[tool.coverage.report] exclude_also` regexes in `pyproject.toml`.
- **Status:** PASS.

### TEST-12: Paste-runnable gate command + `scripts/check_per_module_coverage.py` + final `14-COVERAGE.md`

- **Evidence:** Gate command documented in `CLAUDE.md` §Coverage (locked Q4/Q5 form) and `14-COVERAGE.md`; `scripts/check_per_module_coverage.py` parses `coverage.json` and exits non-zero on any module below 95% (stdlib-only, ~150 LOC per Plan 14-01); `14-COVERAGE.md` replaces `13-COVERAGE-BASELINE.md` per D-E3.
- **Status:** PASS.

### Roadmap Success Criteria

1. **SC#1 -- Per-module coverage report shows >=95% for every in-scope module:** PASS (181/181 modules, overall 98.3%).
2. **SC#2 (D-E1 amended) -- Paste-runnable gate command in `14-COVERAGE.md` and CLAUDE.md verifies the 95% floor:** PASS. Operational CI explicitly deferred to a future phase.
3. **SC#3 -- Real-behavior tests (no pragma coverage gaming):** PASS (zero inline pragmas in scope; D-C3 allowlist via pyproject `exclude_also`).
4. **SC#4 -- `14-COVERAGE.md` replaces `13-COVERAGE-BASELINE.md`:** PASS (Phase 13 baseline archived in its own phase dir per D-E3).

---

## Final Gate Command + Output

Command (Phase 14 locked form):

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Run context:
- **Measured:** 2026-05-11
- **Branch:** `feature/engine-restructure`
- **HEAD at measurement:** `d661c1f` (commit immediately preceding closeout)
- **Python:** 3.10+ / pandas 3.0.1 (CoW)
- **pytest:** 8.x / pytest-cov 7.0.0 / pytest-xdist 3.8.0
- **Java:** JVM 11+ on PATH (required for `-m java` tests per D-A3)

Final stdout line:

```
PASS: all 181 in-scope modules at >= 95.0% line coverage
```

Gate exit code: `0`. Overall coverage from `14-coverage.json` totals: 16746 covered / 17033 statements = 98.3% line coverage. 100 modules at 100.0%; zero modules below 95.0%.

(Pytest summary line and per-module term-missing output captured into the ephemeral run log `tests/_artifacts/14-final-gate-run.log` per Plan 14-12 Task 14-12-001; not committed.)

---

## No-Regression Check (Task 14-12-002)

Programmatic diff against Phase 13 baseline (PASS modules from `13-COVERAGE-BASELINE.md`):

- Phase 13 PASS modules sampled: 49 (engine + converter core + components)
- Modules with regression below 95% in current `14-coverage.json`: **0**
- Modules missing from current report (omitted by `[tool.coverage.run] omit`): 0

Iterate / context modules (locked Q2 merge -- Plan 14-04 absorbed into 14-12 no-regression):

| Module | Phase 13 | Phase 14 | Status |
|--------|---------:|---------:|--------|
| `src/v1/engine/components/iterate/flow_to_iterate.py` | 97% | 96.9% | PASS |
| `src/v1/engine/components/context/context_load.py` | 98% | 98.0% | PASS |

Result: `no regressions` (verified via the inline diff script documented in Plan 14-12 Task 14-12-002).

---

## D-C3 Pragma Audit

Command: `grep -rn "pragma: no cover" src/v1/engine src/converters/talend_to_v1`

Result: zero matches. The D-C3 narrow allowlist (`__main__`, `@abstractmethod`, `raise NotImplementedError`) is enforced via `[tool.coverage.report] exclude_also` regexes, NOT inline annotations. This means:
- No source files contain `# pragma: no cover` -- the policy is centralized.
- Future PRs that add an inline pragma will pop a single visible diff line that reviewers can reject (the regex allowlist would not exclude such a line; only the regex-matched code patterns are excluded).
- The Phase 13 baseline file (`file_output_delimited.py:364` -- a single pre-existing pragma noted in research) was resolved by deletion of the unreachable `except Exception` wrapper (STALE-FOD-001 D-C5 deletion in Plan 14-08).

---

## D-C5 Dead-Code Deletions Log

Source-level deletions accumulated during the lift (each documented in the responsible plan's SUMMARY):

| Plan | Module | Deletion |
|------|--------|----------|
| 14-02 | `aggregate_row.py` | `_build_agg_func` unknown-function silent-default fallback -> explicit `ConfigurationError`; `_process` column-ordering safety loop |
| 14-05 | `extract_positional_fields.py` | unreachable `pd.isna` try/except for non-scalar containers |
| 14-05 | `extract_regex_fields.py` | unreachable `pd.isna` try/except for non-scalar containers |
| 14-05 | `extract_delimited_fields.py` | 2 unreachable main_df backfill loops (columns guaranteed present by construction) + pd.isna try/except |
| 14-06 | `transform/join.py` | 3 sets of unreachable defensive branches (post-keep_cols merge / lookup-key drops; lk_col + '_lookup' / out_col-passthrough; ConfigurationError/DataValidationError re-raise) |
| 14-07 | `swift_transformer.py` | duplicate `_load_lookup_files` definition (first one orphaned stub shadowed by second def) |
| 14-08 | `file_output_delimited.py` | STALE-FOD-001 unreachable `except Exception` catch-all wrapping `pd.to_datetime(errors='coerce')` (pandas contracts NEVER to raise with errors='coerce') -- resolves Phase 13 baseline's single pre-existing pragma |

Total D-C5 deletions: 7 source-level cleanups across 5 plans.

Note: Plans 14-07, 14-09, and 14-11 each documented additional defensive unreachable branches that were left in source (12 in `swift_block_formatter.py`, 15 in `file_input_excel.py`, 4 in expression_converter / foreach / xml_map). The 95% floor was cleared without further source-level cleanup; a future cosmetic phase can revisit these as D-C5 candidates.

---

## Bug-Fix Log (root-cause source patches during the lift)

Project rule (`feedback_fix_source_no_fallbacks`): when tests surface real bugs, patch the source root-cause; do NOT add defensive shims downstream. Bugs surfaced during Phase 14:

| Bug | Plan | Module | Root cause | Fix |
|-----|------|--------|-----------|-----|
| BUG-AGG-001 | 14-02 | `aggregate_row.py` | `list`/`list_object`/`union` under `ignore_null=False` crashed on null-bearing input | `Series.fillna("null")` + Java `String.valueOf` parity |
| BUG-MAIL-001 | 14-03 | `send_mail.py` | attachment `FileOperationError` swallowed by outer `except Exception` block (rewrapped to `ComponentExecutionError`) | `except ETLError: raise` guard between attachment loop and SMTP-failure catch |
| BUG-EJF-001 | 14-05 | `extract_json_fields.py` | `_is_null()` only caught `TypeError` from `bool(pd.isna(v))`; multi-element list raises `ValueError` | Widened except to `(TypeError, ValueError)` |
| BUG-PDC-001 | 14-06 | `python_dataframe_component.py` | Component unregistered with REGISTRY -- engine silently dropped tPythonDataFrame as 'Unknown component type' in production | `@REGISTRY.register('PythonDataFrameComponent', 'tPythonDataFrame')` |
| BUG-PDC-002 | 14-06 | `python_dataframe_component.py` | Missing abstract `_validate_config` (instantiable only because no test exercised the contract) | Added Rule-12 minimal validator |
| BUG-SWIFT-001/002/003 | 14-07 | swift_transformer / swift_block_formatter / file_input_raw | Same triple pattern: unregistered + missing abstract + `ValueError`/`RuntimeError` instead of ETLError | Decorators + ConfigurationError-raising `_validate_config` + ETLError raises |
| BUG-SWIFT-004 | 14-07 | swift_* `__init__` | Read `self.config` (left empty by BaseComponent until `execute()`) | Switched to `self._original_config` per ENG-09/ENG-21 |
| BUG-SWIFT-005 | 14-07 | swift JSON fixtures | Unsupported `\${VAR}` ctx-var syntax (ContextManager resolves only `\${context.VAR}`) | Fixture rewrite (3 swift JSON + 1 YAML) |
| BUG-FIJ-001 | 14-09 | `file_input_json.py` | Unregistered with REGISTRY (same dual-bug pattern as BUG-SWIFT-001/002) | `@REGISTRY.register('FileInputJSON', 'tFileInputJSON')` |
| BUG-FIJ-002 | 14-09 | `file_input_json.py` | Missing abstract `_validate_config` | Rule-12 validator |
| BUG-JVM-001 | 14-10 | `test_bridge_integration.py` | Module-scoped `bridge` fixture used `JavaBridge()` with default port=25333; under `-n auto` every xdist worker except first failed on bind() | Switched to `JavaBridgeManager()` (dynamic free port via `socket.bind('', 0)`) -- closes Plan 14-01 deferred JVM contention |

Plan-checker observation for the future: 4 of these (BUG-PDC-001/002, BUG-SWIFT-001/002, BUG-FIJ-001/002) share the same dual-pattern -- `BaseComponent` subclass missing both `@REGISTRY.register` and abstract `_validate_config`. A plan-checker grep for `class .+\(BaseComponent\):` subclasses missing either invariant would catch this systematically in future phases.

---

## STALE Deletions Log

| ID | Plan | File | Reason |
|----|------|------|--------|
| STALE-INT-001 | 14-11 | `tests/converters/talend_to_v1/test_integration.py` | 378 lines importing absent `src.converters.complex_converter`; broke `-n auto` collection. Originally deferred from 14-01; absorbed into 14-11. |
| STALE-FOD-001 | 14-08 | source-level: `file_output_delimited._apply_date_patterns` `except Exception` wrapping `pd.to_datetime(errors='coerce')` | Unreachable -- pandas contracts NEVER to raise with `errors='coerce'`. Resolves the single pre-existing `# pragma: no cover` from Phase 13 baseline. |

---

## Pipeline-Fixture Inventory (Plan 14-01 + per-subsystem additions)

Path: `tests/fixtures/jobs/`. Total: 14 JSON pipeline-job fixtures.

| Subsystem | Fixture | Plan | Behavior |
|-----------|---------|------|----------|
| core | `multi_subjob.json` | 14-10 | OnSubjobOk multi-subjob orchestration |
| core | `reject_routing.json` | 14-10 | reject-flow routing to downstream component |
| core | `trigger_runif.json` | 14-10 | RunIf trigger branching |
| file | `csv_split_output.json` | 14-08 | FileOutputDelimited SPLIT_EVERY |
| file | `csv_with_header.json` | 14-08 | FileInputDelimited with header + simple downstream |
| file | `csv_with_reject.json` | 14-08 | FILE reject routing with CHECK_FIELDS_NUM |
| file | `excel_simple.json` | 14-09 | FileInputExcel deep-gap pipeline |
| file | `json_jsonpath.json` | 14-09 | FileInputJSON with JSONPath extraction |
| file | `raw_text.json` | 14-09 | FileInputRaw deep-gap pipeline |
| swift | `mt103_basic.json` | 14-07 | SwiftTransformer MT103 happy path |
| swift | `mt202_with_lookup.json` | 14-07 | SwiftTransformer + lookup YAML config |
| swift | `mt940_block_formatter.json` | 14-07 | SwiftBlockFormatter end-to-end |
| transform | `join_with_reject.json` | 14-06 | tJoin reject routing |
| transform | `map_with_lookup.json` | 14-06 | tMap LOAD_ONCE lookup |

All fixtures load through `run_job_fixture` from `tests/conftest.py` (Plan 14-01). Path resolved via `FIXTURE_JOBS_ROOT`. JSON format mirrors converter output (D-C2).

Companion data fixtures under `tests/fixtures/data/`:
- `sample_basic.xlsx`, `sample_multisheet.xlsx`, `sample_legacy.xls` (Excel inputs for 14-09)
- `sample_data.json`, `sample_jsonpath.json` (JSON inputs for 14-09)
- `sample_raw_utf8.txt`, `sample_raw_iso8859.txt` (raw text inputs for 14-09)

---

## SWIFT Generator Inventory (Plan 14-07)

Path: `tests/fixtures/swift/synthetic.py`. Public functions exposed for test composition:

- `build_block_1(...)` -- Block 1 basic header
- `build_block_2(...)` -- Block 2 application header (input or output)
- `build_block_3(...)` -- Block 3 user header (optional)
- `build_block_4(fields: Iterable[MTBlock4Field]) -> str` -- Block 4 text block (the message body)
- `build_block_5(checksum: str = "1234567890AB") -> str` -- Block 5 trailer
- `build_mt_message(...)` -- compose full MT envelope from blocks 1-5
- `mt103_minimum()` -- MT103 single customer credit transfer happy path
- `mt202_cov()` -- MT202 COV financial-institution transfer
- `mt940_with_balance()` -- MT940 customer statement with closing balance
- `malformed_missing_block_4()` -- intentionally malformed for error-path coverage

Plus YAML lookup / config / layout fixtures under `tests/fixtures/swift/configs/`, `tests/fixtures/swift/layouts/`, `tests/fixtures/swift/lookups/`.

The generator is test-only (D-A5 synthetic per SWIFT user-handbook spec); no production samples required. Reusable for Phase 15 if real Talend SWIFT job parity tests are added.

---

## Manager / Contributor Notes

- **`14-coverage.json` is committed per phase** (locked Q4 deviation from researcher recommendation). Future operational CI phase will re-emit on every PR; per-phase artifact lives in the phase dir so historical floors are diffable.
- **`htmlcov/index.html` is gitignored.** Regenerate locally via the gate command. Always available after a fresh run.
- **`rm -f .coverage*` prefix is non-optional** (locked Q5). Stale `.coverage.*` shards from interrupted xdist runs otherwise pollute the JSON report and produce mysteriously-different per-module numbers.
- **JVM 11+ on PATH is required** for `-m java` tests (D-A3). Running the gate without JVM will skip `@pytest.mark.java` tests and the gate will FAIL on `java_bridge_manager.py` and `transform/map.py` (both bridge-driven). Future operational CI must provision JVM 11+.
- **Oracle modules use mocked `oracledb`** (D-A6). The Phase 11 testcontainer suite stays opt-in via `-m oracle`; running it requires Docker + testcontainers, and is NOT part of the Phase 14 gate.

---

## Threat Flags

No new security-relevant surface introduced. Test infrastructure only.

---

## Self-Check

- [x] `14-COVERAGE.md` exists at `.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md`
- [x] `14-coverage.json` committed
- [x] `scripts/check_per_module_coverage.py coverage.json --floor 95` exits 0
- [x] `grep -rn "pragma: no cover" src/v1/engine src/converters/talend_to_v1` returns nothing
- [x] No-regression check vs Phase 13 baseline passes
- [x] Iterate / context modules (locked Q2 merge) explicitly verified >=95%
- [x] All 4 SC entries marked DONE in ROADMAP.md
- [x] TEST-11 / TEST-12 marked Complete in REQUIREMENTS.md + traceability table
- [x] CLAUDE.md §Coverage reflects locked gate command form

---

*Phase 14 verification evidence -- captured 2026-05-11 -- closeout sign-off pending manual checkpoint*
