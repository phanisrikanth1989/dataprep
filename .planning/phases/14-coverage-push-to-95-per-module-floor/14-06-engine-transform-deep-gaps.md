---
phase: 14
plan: 06
slug: engine-transform-deep-gaps
type: execute
wave: 2
depends_on: [14-01]
files_modified:
  - tests/v1/engine/components/transform/test_map.py
  - tests/v1/engine/components/transform/test_join.py
  - tests/v1/engine/components/transform/test_python_dataframe_component.py
  - tests/fixtures/jobs/transform/map_with_lookup.json
  - tests/fixtures/jobs/transform/join_with_reject.json
  - src/v1/engine/components/transform/map.py                    # only if BUG surfaces
  - src/v1/engine/components/transform/join.py                   # only if BUG surfaces
  - src/v1/engine/components/transform/python_dataframe_component.py  # only if BUG surfaces
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "src/v1/engine/components/transform/map.py >= 95% line coverage"
    - "src/v1/engine/components/transform/join.py >= 95% line coverage"
    - "src/v1/engine/components/transform/python_dataframe_component.py >= 95% line coverage"
    - "Pipeline tests for map.py exercise full ETLEngine.execute() lifecycle (D-C1)"
  artifacts:
    - path: tests/v1/engine/components/transform/test_map.py
      provides: extended unit + pipeline coverage of enable_auto_convert_type, RELOAD_AT_EACH_ROW edges, inner-join reject schema, catch-output reject
    - path: tests/v1/engine/components/transform/test_join.py
      provides: case-insensitive joins + null-key + reject-schema + INCLUDE_LOOKUP toggle edges
    - path: tests/v1/engine/components/transform/test_python_dataframe_component.py
      provides: output_columns filter + routines availability + error branches
    - path: tests/fixtures/jobs/transform/map_with_lookup.json
      provides: pipeline-test fixture for tMap with lookup flow
    - path: tests/fixtures/jobs/transform/join_with_reject.json
      provides: pipeline-test fixture for tJoin with reject flow
  key_links:
    - from: tests/v1/engine/components/transform/test_map.py
      to: src/v1/engine/components/transform/map.py
      via: direct _process() unit tests + run_job_fixture pipeline tests
---

<objective>
Lift the three deep-gap non-SWIFT transform modules: `map.py` (77%, 198 missed, 868 stmts -- the largest single module by stmts), `join.py` (69%, 45 missed), `python_dataframe_component.py` (20%, 37 missed, 46 stmts -- small file but deep gap). Mix of unit tests (direct `_process()`) and pipeline tests (via `run_job_fixture` from Plan 14-01) per D-C1. Pipeline tests required for `map.py` since lifecycle / globalMap / reject-routing semantics matter.
</objective>

<scope>
- MODIFIED: `tests/v1/engine/components/transform/test_map.py` -- extend to cover:
    - `enable_auto_convert_type` per-key branches (MAP-06)
    - RELOAD_AT_EACH_ROW edges (Phase 5.2 fixed 4 bugs; ensure all branches covered)
    - inner-join reject schema (MAP-02 -- `rejectInnerJoin` flow vs generic reject)
    - `activateCondensedTool` catch-output reject (MAP-05)
    - UNIQUE_MATCH first-row vs last-row semantics
    - null-key handling in joins (MAP-03)
    - `{id}_NB_LINE` globalMap variable assertions (verify in pipeline tests)
- MODIFIED: `tests/v1/engine/components/transform/test_join.py` -- extend for:
    - case-insensitive join branch (JOIN-01) -- verify original data NOT mutated
    - null-key handling (JOIN-08)
    - reject schema population (JOIN-03)
    - INCLUDE_LOOKUP toggle (JOIN-04)
    - ERROR_MESSAGE globalMap (JOIN-05)
    - LEFT/RIGHT/INNER outer-join reject paths
- MODIFIED: `tests/v1/engine/components/transform/test_python_dataframe_component.py` -- extend for:
    - `output_columns` filter (subset of input cols)
    - routines availability in execution namespace
    - error branches (exec failure -> ComponentExecutionError)
    - D-11 secure namespace (no os/sys access)
    - empty input DataFrame handling
- NEW: `tests/fixtures/jobs/transform/map_with_lookup.json` -- 3-component pipeline fixture (input -> tMap with lookup -> output) for pipeline tests
- NEW: `tests/fixtures/jobs/transform/join_with_reject.json` -- 4-component pipeline fixture (main + lookup -> tJoin -> output + reject) for pipeline tests
</scope>

<out_of_scope>
- SWIFT (Plan 14-07).
- Quick-win + medium transform lifts (Plan 14-05).
- BaseComponent / executor.py / engine.py core lifts (Plan 14-10).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Module Triage transform deep gaps; §Pipeline-Test Infrastructure
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-C1, D-C2, D-C4
- `.planning/REQUIREMENTS.md` MAP-01..08, JOIN-01..08
- `.planning/phases/05.2-tmap-reload-at-each-row-fix/` (RELOAD_AT_EACH_ROW context)
- `src/v1/engine/components/transform/map.py` (lift target, 868 stmts)
- `src/v1/engine/components/transform/join.py` (lift target)
- `src/v1/engine/components/transform/python_dataframe_component.py` (lift target)
- `tests/v1/engine/components/transform/test_map.py`, `test_map_integration.py`, `test_map_method_size.py` (existing tests)
- `tests/v1/engine/components/transform/test_join.py` (existing)
- `tests/integration/test_iterate_e2e.py` (pipeline-test pattern reference)
- `tests/conftest.py` (run_job_fixture from Plan 14-01)
</canonical_refs>

<waves>

## Wave 0 -- Pipeline-test fixtures (prerequisite for unit-tests-with-pipeline component)

### Task 14-06-001 -- Generate map_with_lookup.json pipeline fixture

- **Type:** fixture
- **Description:** Use a real `.item` from `tests/talend_xml_samples/` (the tMap+lookup samples used in Phase 5.2) and run `python -m src.converters.talend_to_v1.converter <item> tests/fixtures/jobs/transform/map_with_lookup.json`. Trim to the minimum 3-component shape: tFileInputDelimited (main) + tFileInputDelimited (lookup) + tMap + tFileOutputDelimited. Use placeholder paths (`"filepath": "TBD_via_mutations"`).
- **Files:** `tests/fixtures/jobs/transform/map_with_lookup.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/transform/map_with_lookup.json')); assert any(x['type']=='tMap' or x['type']=='Map' for x in c['components']); print('ok')"`
- **Expected:** `ok`.

### Task 14-06-002 -- Generate join_with_reject.json pipeline fixture

- **Type:** fixture
- **Description:** Generate a 4-component pipeline (main input + lookup input + tJoin + tFileOutputDelimited main + tFileOutputDelimited reject). Same approach as 14-06-001.
- **Files:** `tests/fixtures/jobs/transform/join_with_reject.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/transform/join_with_reject.json')); assert any('Join' in x['type'] for x in c['components']); print('ok')"`
- **Expected:** `ok`.

## Wave 1 -- Unit + pipeline test extensions

### Task 14-06-003 -- Lift map.py to 95% (unit + pipeline)

- **Type:** test
- **Description:**
    1. Inventory: `pytest tests/v1/engine/components/transform/test_map.py tests/v1/engine/components/transform/test_map_integration.py --cov=src/v1/engine/components/transform/map --cov-report=term-missing -q`.
    2. Add unit tests to `test_map.py` for missed branches in: enable_auto_convert_type per-key paths, UNIQUE_MATCH first-row vs last-row, null-key join, RELOAD_AT_EACH_ROW (covering Phase 5.2 fix paths), inner-join reject schema, catch-output reject (activateCondensedTool).
    3. Add pipeline tests using `run_job_fixture("transform/map_with_lookup", mutations={...})` -- assert `result.stats["status"] == "success"`, `result.global_map["tMap_1_NB_LINE"]` matches expected, output flow content is correct.
    4. Per D-C4: realistic dtypes (Int64, Decimal, datetime64, StringDtype) in test fixtures.
- **Files:** `tests/v1/engine/components/transform/test_map.py`
- **Verification:** `python -m pytest tests/v1/engine/components/transform/test_map.py tests/v1/engine/components/transform/test_map_integration.py --cov=src/v1/engine/components/transform/map --cov-report=term-missing -q`
- **Expected:** Coverage >= 95% for `map.py`; tests green.

### Task 14-06-004 -- Lift join.py to 95% (unit, pipeline optional)

- **Type:** test
- **Description:**
    1. Inventory missed lines.
    2. Add unit tests for: case-insensitive join (verify original DataFrame NOT mutated -- important Phase 7 JOIN-01 invariant), null-key handling, reject schema, INCLUDE_LOOKUP toggle, ERROR_MESSAGE globalMap, LEFT/RIGHT/INNER outer-join reject paths.
    3. Optional: pipeline test via `run_job_fixture("transform/join_with_reject", ...)` to verify reject-flow routing end-to-end.
- **Files:** `tests/v1/engine/components/transform/test_join.py`
- **Verification:** `python -m pytest tests/v1/engine/components/transform/test_join.py --cov=src/v1/engine/components/transform/join --cov-report=term-missing -q`
- **Expected:** Coverage >= 95%.

### Task 14-06-005 -- Lift python_dataframe_component.py to 95% (unit only)

- **Type:** test
- **Description:** RESEARCH §Open Q2 recommends "existing patterns scale up" -- hand-rolled `pd.DataFrame` fixtures with mixed dtypes are sufficient. 46-stmt module wrapping `exec(python_code, namespace)`. Cover:
    1. `output_columns=["a","b"]` with input having `["a","b","c","d"]` -- verify only a,b in output
    2. Routines availability in namespace (StringHandling, TalendDate, Numeric routines callable from python_code)
    3. Error branches: malformed `python_code` -> `ComponentExecutionError`; exec raises during run -> wrap in ComponentExecutionError with component_id
    4. D-11 secure namespace: assert `os` and `sys` NOT in execution namespace (likely same enforcement as python_component.py per PYCO-02)
    5. Empty DataFrame input handling
- **Files:** `tests/v1/engine/components/transform/test_python_dataframe_component.py`
- **Verification:** `python -m pytest tests/v1/engine/components/transform/test_python_dataframe_component.py --cov=src/v1/engine/components/transform/python_dataframe_component --cov-report=term-missing -q`
- **Expected:** Coverage >= 95%.

### Task 14-06-006 -- Per-plan gate verification

- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/transform/ -m "not oracle" -n auto \
      --cov=src/v1/engine/components/transform --cov-report=json:cov_14_06.json -q
    python scripts/check_per_module_coverage.py cov_14_06.json --floor 95
    ```
    Filter expected: `map.py`, `join.py`, `python_dataframe_component.py` all PASS. SWIFT modules will still fail at this point (Plan 14-07).
- **Expected:** PASS for the 3 modules in this plan's scope.

</waves>

<verification_gate>

Plan 14-06 is GREEN when:
1. All three modules >= 95% line coverage.
2. Pipeline tests for map.py exist and pass via `run_job_fixture`.
3. ETLError-subclass exceptions in all `raises`.
4. No new pragmas outside D-C3 allowlist.
5. `assert_ascii_logs` fixture clean for any pipeline tests added.
6. Per-module gate exits 0 for `map.py`, `join.py`, `python_dataframe_component.py`.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(14-06): INFRA-FIX-001 add transform/map_with_lookup pipeline fixture` | `tests/fixtures/jobs/transform/map_with_lookup.json` |
| 2 | `chore(14-06): INFRA-FIX-002 add transform/join_with_reject pipeline fixture` | `tests/fixtures/jobs/transform/join_with_reject.json` |
| 3 | `test(14-06): COV-MAP-001 lift transform/map.py to 95% (auto-convert + RELOAD + reject + UNIQUE_MATCH branches)` | `tests/v1/engine/components/transform/test_map.py` |
| 4 | `test(14-06): COV-JOIN-001 lift transform/join.py to 95% (case-insensitive + null-key + reject schema + INCLUDE_LOOKUP)` | `tests/v1/engine/components/transform/test_join.py` |
| 5 | `test(14-06): COV-PDC-001 lift transform/python_dataframe_component.py to 95% (output_columns + routines + secure namespace)` | `tests/v1/engine/components/transform/test_python_dataframe_component.py` |
| 6+ (conditional) | `fix(14-06): BUG-XXX-NN <description>` -- only if bugs surface | source files |

(Total: 5 + optional bug commits.)

</commit_map>
