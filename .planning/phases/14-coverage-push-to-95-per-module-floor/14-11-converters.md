---
phase: 14
plan: 11
slug: converters
type: execute
wave: 1
depends_on: [14-01]
files_modified:
  - tests/converters/talend_to_v1/test_converter.py
  - tests/converters/talend_to_v1/test_expression_converter.py
  - tests/converters/talend_to_v1/components/transform/test_xml_map.py
  - tests/converters/talend_to_v1/components/transform/test_replace.py
  - tests/converters/talend_to_v1/components/aggregate/test_aggregate_row.py
  - tests/converters/talend_to_v1/components/iterate/test_foreach.py
  - tests/converters/talend_to_v1/components/file/test_file_input_excel.py
  - tests/converters/talend_to_v1/components/database/test_mssql_input.py
  - src/converters/talend_to_v1/*.py  # only if BUGs surface
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "All 8 converter modules in scope reach >= 95% line coverage"
    - "Existing converter tests continue to pass"
    - "ETLError subclasses asserted in raises (ConfigurationError, etc.) where converter raises typed exceptions"
  artifacts:
    - path: tests/converters/talend_to_v1/test_<module>.py
      provides: extension of converter-side tests for missed-line clusters
  key_links:
    - from: each converter test file
      to: matching src/converters/talend_to_v1/<module>.py
      via: TalendNode-based converter unit tests (existing pattern)
---

<objective>
Lift the 8 converter-side modules below 95%: `converter.py` (94%, 13 missed), `expression_converter.py` (78%, 20 missed), and 6 component-converters: `transform/xml_map.py` (93%, 15), `transform/replace.py` (94%, 6), `aggregate/aggregate_row.py` (91%, 11), `iterate/foreach.py` (94%, 2), `file/file_input_excel.py` (94%, 7), `database/mssql_input.py` (81%, 12 -- in scope per locked Q3). All are converter-side: TalendNode -> JSON dict transformations. Pure unit tests; no pipeline tests required (D-C1 -- the engine layer is what consumes the JSON).
</objective>

<scope>
- MODIFIED: `tests/converters/talend_to_v1/test_converter.py` -- cover orchestrator edge cases: malformed `.item`, missing components, validator error propagation, dump-mode option flags.
- MODIFIED: `tests/converters/talend_to_v1/test_expression_converter.py` -- cover Java->Python translation edge cases: `detect_java_expression` patterns, string-method translations, null-check translations, operator translations, `{{java}}` marker emission for unhandled patterns.
- MODIFIED: `tests/converters/talend_to_v1/components/transform/test_xml_map.py` -- cover the conditional needs_review edge cases per Phase 12 D-E1 (12 deferred sub-features); ensure all parameter shapes covered.
- MODIFIED: `tests/converters/talend_to_v1/components/transform/test_replace.py` -- cover regex/literal mode emission + REPLACE_TABLE row count edges.
- MODIFIED: `tests/converters/talend_to_v1/components/aggregate/test_aggregate_row.py` -- cover remaining corner cases (Phase 13 already updated NeedsReview count).
- MODIFIED: `tests/converters/talend_to_v1/components/iterate/test_foreach.py` -- 2 missed lines, trivial.
- MODIFIED: `tests/converters/talend_to_v1/components/file/test_file_input_excel.py` -- cover converter parameter-handling edges.
- MODIFIED: `tests/converters/talend_to_v1/components/database/test_mssql_input.py` -- cover error branches (12 missed lines). MSSQL converter is in scope per locked Q3 even though MSSQL engine is v2.
- POSSIBLY MODIFIED: source files only if real bugs surface. No new product features.
</scope>

<out_of_scope>
- Already-at-95% converter modules (the vast majority of converter components -- see baseline).
- `complex_converter` legacy modules (D-D1 / D-E4 / `[tool.coverage.run] omit`).
- MSSQL **engine** components (v2 territory; only the converter is in scope).
- Pipeline tests via `run_job_fixture` (converter is upstream of engine; no pipeline-test relevance for the converter side).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Module Triage converters core + components
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` (locked Q3: mssql_input in scope)
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-06-PLAN.md` (TEST-CHANGE sweep, regex storage convention reference)
- `.planning/phases/12-xml-components-audit-harden-output/12-05-PLAN.md` (xml_map D-E1 conditional needs_review pattern)
- `src/converters/talend_to_v1/converter.py`, `expression_converter.py`, `components/transform/xml_map.py`, `components/transform/replace.py`, `components/aggregate/aggregate_row.py`, `components/iterate/foreach.py`, `components/file/file_input_excel.py`, `components/database/mssql_input.py` (lift targets)
- existing test files under `tests/converters/talend_to_v1/`
- `src/v1/engine/exceptions.py` (where converter raises typed exceptions)
- `src/converters/talend_to_v1/components/base.py` (TalendNode, ComponentResult, helpers)
</canonical_refs>

<waves>

## Wave 1 -- Module-by-module test extensions

Standard pattern per task: inventory missed lines via `--cov-report=term-missing`, add targeted tests, verify >= 95% before commit. Apply D-C5 if needed and document.

### Task 14-11-001 -- Lift converter.py to 95%
- **Files:** `tests/converters/talend_to_v1/test_converter.py`
- **Description:** Cover malformed `.item` -> graceful handling, missing components -> `_unsupported` placeholder + warning, validator error propagation in step 11, dump-mode toggles.
- **Verification:** `python -m pytest tests/converters/talend_to_v1/test_converter.py --cov=src/converters/talend_to_v1/converter --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-11-002 -- Lift expression_converter.py to 95%
- **Files:** `tests/converters/talend_to_v1/test_expression_converter.py`
- **Description:** Cover Java->Python translation edge cases. Inventory the patterns in `convert()` and `detect_java_expression()`. Add tests for: string-method translations (`.toUpperCase()` -> `.upper()`, etc.), null-check translations (`==null` -> `is None`), operator translations (`||` -> `or`, `&&` -> `and`), `{{java}}` marker emission for patterns the converter declines to translate.
- **Verification:** `python -m pytest tests/converters/talend_to_v1/test_expression_converter.py --cov=src/converters/talend_to_v1/expression_converter --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-11-003 -- Lift components/transform/xml_map.py converter to 95%
- **Files:** `tests/converters/talend_to_v1/components/transform/test_xml_map.py`
- **Description:** Cover the 15 missed lines. Phase 12 added rich tests; remaining gap likely in conditional-needs_review edge cases (12 deferred sub-features per D-E1 of Phase 12).
- **Verification:** `python -m pytest tests/converters/talend_to_v1/components/transform/test_xml_map.py --cov=src/converters/talend_to_v1/components/transform/xml_map --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-11-004 -- Lift components/transform/replace.py converter to 95%
- **Files:** `tests/converters/talend_to_v1/components/transform/test_replace.py`
- **Description:** Cover regex/literal mode emission and REPLACE_TABLE row count edges (6 missed lines).
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-11-005 -- Lift components/aggregate/aggregate_row.py converter to 95%
- **Files:** `tests/converters/talend_to_v1/components/aggregate/test_aggregate_row.py`
- **Description:** Cover the 11 missed lines (Phase 13 already updated NeedsReview count). Likely in remaining corner cases of grouped vs ungrouped emission, output_column handling.
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-11-006 -- Lift components/iterate/foreach.py converter to 95%
- **Files:** `tests/converters/talend_to_v1/components/iterate/test_foreach.py`
- **Description:** 2 missed lines -- trivial. Inventory + add 1-2 targeted tests.
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-11-007 -- Lift components/file/file_input_excel.py converter to 95%
- **Files:** `tests/converters/talend_to_v1/components/file/test_file_input_excel.py`
- **Description:** 7 missed lines. Cover converter parameter-handling edges (date_pattern, encoding, advanced separator emission).
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-11-008 -- Lift components/database/mssql_input.py converter to 95% (locked Q3)
- **Files:** `tests/converters/talend_to_v1/components/database/test_mssql_input.py`
- **Description:** Cover the 12 missed lines. Branch-handling, parameter type emission, error branches. Note: MSSQL **engine** is v2 territory; this is the **converter** only.
- **Verification:** `python -m pytest tests/converters/talend_to_v1/components/database/test_mssql_input.py --cov=src/converters/talend_to_v1/components/database/mssql_input --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-11-009 -- Per-plan gate verification
- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/converters/ -m "not oracle" -n auto \
      --cov=src/converters --cov-report=json:cov_14_11.json -q
    python scripts/check_per_module_coverage.py cov_14_11.json --floor 95
    ```
- **Expected:** PASS for all 8 modules in scope. `complex_converter` modules excluded by `[tool.coverage.run] omit`.

</waves>

<verification_gate>

Plan 14-11 is GREEN when:
1. All 8 converter modules >= 95% line coverage.
2. ETLError subclasses (or converter-specific exceptions where applicable) in `raises` assertions.
3. No new pragmas outside D-C3 allowlist.
4. Per-module gate exits 0 for `src/converters/` (excl. omit list).

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `test(14-11): COV-CV-001 lift converter.py to 95% (malformed item + missing components + validator propagation)` | `tests/converters/talend_to_v1/test_converter.py` |
| 2 | `test(14-11): COV-EXC-001 lift expression_converter.py to 95% (Java->Python translation edges + {{java}} marker)` | `tests/converters/talend_to_v1/test_expression_converter.py` |
| 3 | `test(14-11): COV-XMC-001 lift transform/xml_map converter to 95% (D-E1 conditional needs_review edges)` | `tests/converters/talend_to_v1/components/transform/test_xml_map.py` |
| 4 | `test(14-11): COV-RPC-001 lift transform/replace converter to 95% (regex/literal + REPLACE_TABLE edges)` | `tests/converters/talend_to_v1/components/transform/test_replace.py` |
| 5 | `test(14-11): COV-AGC-001 lift aggregate/aggregate_row converter to 95% (grouped/ungrouped + output_column edges)` | `tests/converters/talend_to_v1/components/aggregate/test_aggregate_row.py` |
| 6 | `test(14-11): COV-FEC-001 lift iterate/foreach converter to 95%` | `tests/converters/talend_to_v1/components/iterate/test_foreach.py` |
| 7 | `test(14-11): COV-FIEC-001 lift file/file_input_excel converter to 95% (param-handling edges)` | `tests/converters/talend_to_v1/components/file/test_file_input_excel.py` |
| 8 | `test(14-11): COV-MSC-001 lift database/mssql_input converter to 95% (per locked Q3 -- converter only, engine is v2)` | `tests/converters/talend_to_v1/components/database/test_mssql_input.py` |
| 9+ (conditional) | `fix(14-11): BUG-CONV-NN <description>` -- only if bug surfaces | source files |

(Total: 8 + optional bug commits.)

</commit_map>
