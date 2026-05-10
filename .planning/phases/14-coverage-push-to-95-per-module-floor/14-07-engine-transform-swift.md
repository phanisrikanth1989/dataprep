---
phase: 14
plan: 07
slug: engine-transform-swift
type: execute
wave: 2
depends_on: [14-01]
files_modified:
  - tests/fixtures/swift/__init__.py
  - tests/fixtures/swift/synthetic.py
  - tests/fixtures/swift/layouts/mt_basic.yaml
  - tests/fixtures/swift/layouts/mt_with_block3.yaml
  - tests/fixtures/swift/configs/transform_minimum.yaml
  - tests/fixtures/swift/configs/transform_with_lookup.yaml
  - tests/fixtures/swift/lookups/bic_country.csv
  - tests/v1/engine/components/transform/test_swift_block_formatter.py  # NEW
  - tests/v1/engine/components/transform/test_swift_transformer.py      # NEW
  - tests/fixtures/jobs/swift/mt103_basic.json
  - tests/fixtures/jobs/swift/mt202_with_lookup.json
  - tests/fixtures/jobs/swift/mt940_block_formatter.json
  - src/v1/engine/components/transform/swift_transformer.py     # only if BUG surfaces or D-C5 dead-code deletion
  - src/v1/engine/components/transform/swift_block_formatter.py # only if BUG surfaces or D-C5 dead-code deletion
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "src/v1/engine/components/transform/swift_transformer.py >= 95% line coverage"
    - "src/v1/engine/components/transform/swift_block_formatter.py >= 95% line coverage"
    - "tests/fixtures/swift/synthetic.py exposes mt103_minimum, mt202_cov, mt940_with_balance, malformed_missing_block_4 generators"
    - "Synthetic MT messages exercise every reachable branch in both modules; unreachable branches are deleted per D-C5"
    - "ASCII-only test output -- no SWIFT special characters surface in logs"
  artifacts:
    - path: tests/fixtures/swift/synthetic.py
      provides: build_block_1..5, build_mt_message, mt103_minimum, mt202_cov, mt940_with_balance, malformed_missing_block_4
    - path: tests/fixtures/swift/layouts/*.yaml
      provides: layout configs for swift_block_formatter
    - path: tests/fixtures/swift/configs/*.yaml
      provides: transform configs for swift_transformer
    - path: tests/fixtures/swift/lookups/bic_country.csv
      provides: lookup CSV for transform_with_lookup config
    - path: tests/v1/engine/components/transform/test_swift_block_formatter.py
      provides: full unit + pipeline coverage of swift_block_formatter
    - path: tests/v1/engine/components/transform/test_swift_transformer.py
      provides: full unit + pipeline coverage of swift_transformer
  key_links:
    - from: tests/v1/engine/components/transform/test_swift_block_formatter.py
      to: src/v1/engine/components/transform/swift_block_formatter.py
      via: synthetic MT messages from tests/fixtures/swift/synthetic.py + layout YAML
    - from: tests/v1/engine/components/transform/test_swift_transformer.py
      to: src/v1/engine/components/transform/swift_transformer.py
      via: synthetic MT + transform_config YAML + optional lookup CSV
---

<objective>
The largest single Phase 14 plan -- 851 stmts at 7% combined. Build the synthetic SWIFT MT generator (`tests/fixtures/swift/synthetic.py`), generate YAML layouts and transform configs covering every reachable branch in both modules, and write the unit + pipeline tests that drive both `swift_transformer.py` (441 stmts, 7%) and `swift_block_formatter.py` (410 stmts, 7%) to >= 95%. Per D-A5, fixtures are synthetic-per-handbook; if a code branch can't be hit by any realistic MT input, apply D-C5 (delete dead code -- preferred). Per RESEARCH §Pipeline-Test JSON job synthesis, generate the JSON job fixtures by running `convert_job()` on real `.item` SWIFT samples if available, else hand-construct mirroring converter output shape.
</objective>

<scope>
- NEW: `tests/fixtures/swift/__init__.py` -- empty package marker
- NEW: `tests/fixtures/swift/synthetic.py` -- per RESEARCH §SWIFT Synthetic Generator section: `MTBlock4Field` dataclass, `build_block_1`, `build_block_2`, `build_block_3`, `build_block_4`, `build_block_5`, `build_mt_message`, plus convenience templates `mt103_minimum`, `mt202_cov`, `mt940_with_balance`, `malformed_missing_block_4`.
- NEW: `tests/fixtures/swift/layouts/mt_basic.yaml` -- block parsing layout (block 1, block 2, block 4 with field-tag pattern), `pipe_fields` simple + dict forms, `processing.strip_whitespace`.
- NEW: `tests/fixtures/swift/layouts/mt_with_block3.yaml` -- adds block 3 user-header parsing.
- NEW: `tests/fixtures/swift/configs/transform_minimum.yaml` -- `input_fields`, `output_fields`, `output_layout`, `field_mappings` with `condition` and `source/transform` rule shapes, `transformations.trim` (regex_replace).
- NEW: `tests/fixtures/swift/configs/transform_with_lookup.yaml` -- adds `lookups` referencing `bic_country.csv`.
- NEW: `tests/fixtures/swift/lookups/bic_country.csv` -- BIC -> country mapping CSV.
- NEW: `tests/v1/engine/components/transform/test_swift_block_formatter.py` -- unit + pipeline tests covering: 5-block parsing, optional block 3 path, block 4 field-tag dispatch, multi-line tag values (e.g. `:50K:`, `:86:`), missing optional fields, malformed input -> ConfigurationError / DataValidationError, `pipe_fields` simple form vs dict form, `processing.strip_whitespace` toggle, all branches in `_init_swift_parser` (lines 33-79 per RESEARCH).
- NEW: `tests/v1/engine/components/transform/test_swift_transformer.py` -- unit + pipeline tests covering: input-field type coercion, output-field defaults, condition-rule branches (`when`/`then`/`else`), `source/transform` rule shapes, all `transformations` types (regex_replace, lookup, format), missing lookup file -> FileOperationError, lookup miss with default, output_layout ordering, all branches in `_init_transformer_config` (lines 43-77 per RESEARCH).
- NEW: `tests/fixtures/jobs/swift/mt103_basic.json` -- pipeline job: tFileInputRaw -> SwiftBlockFormatter -> tFileOutputDelimited (or similar minimum).
- NEW: `tests/fixtures/jobs/swift/mt202_with_lookup.json` -- pipeline job: tFileInputRaw -> SwiftBlockFormatter -> SwiftTransformer (with lookup) -> tFileOutputDelimited.
- NEW: `tests/fixtures/jobs/swift/mt940_block_formatter.json` -- pipeline job exercising MT940 statement-line parsing.
- POSSIBLY MODIFIED: `swift_transformer.py` / `swift_block_formatter.py` -- only if D-C5 dead-code deletion is needed or a real bug surfaces.
</scope>

<out_of_scope>
- Real production SWIFT samples (D-A5: synthetic only).
- Hypothesis property-based tests (CONTEXT.md Deferred Ideas).
- ISO 20022 message types.
- Converter-side `swift_transformer.py` (already at 100% per baseline; covered by existing converter test).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §SWIFT Synthetic Generator (full section), §Pitfall 6 (SWIFT MT format edge cases)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-A1, D-A5, D-C5
- `src/v1/engine/components/transform/swift_transformer.py` (lift target, 441 stmts at 7%, lines 43-77 = `_init_transformer_config`)
- `src/v1/engine/components/transform/swift_block_formatter.py` (lift target, 410 stmts at 7%, lines 33-79 = `_init_swift_parser`)
- `tests/converters/talend_to_v1/components/transform/test_swift_transformer.py` (existing converter test -- shares YAML key vocabulary; cross-check synth shape)
- `tests/conftest.py` (`run_job_fixture`, `assert_ascii_logs`)
- `src/v1/engine/exceptions.py`
- SWIFT MT user-handbook field tags reference (RESEARCH §SWIFT Synthetic Generator table)
</canonical_refs>

<waves>

## Wave 0 -- Synthetic generator + layout + config fixtures

### Task 14-07-001 -- Build synthetic.py MT message generator

- **Type:** fixture
- **Description:** Implement `tests/fixtures/swift/synthetic.py` per RESEARCH §SWIFT Synthetic Generator. Functions: `build_block_1`, `build_block_2` (direction/message_type/receiver/priority), `build_block_3` (UETR + validation_flag, both optional), `build_block_4` (list of `MTBlock4Field`), `build_block_5` (CHK trailer), `build_mt_message` (composer). Templates: `mt103_minimum`, `mt202_cov` (with block 3 validation flag "COV"), `mt940_with_balance`, `malformed_missing_block_4` (reject-path fixture). All ASCII; explicit dataclass `MTBlock4Field(tag: str, value: str)`.
- **Files:** `tests/fixtures/swift/__init__.py`, `tests/fixtures/swift/synthetic.py`
- **Verification:**
    ```bash
    python -c "
    from tests.fixtures.swift.synthetic import mt103_minimum, mt202_cov, mt940_with_balance, malformed_missing_block_4
    msg = mt103_minimum(); assert '{1:' in msg and '{2:I103' in msg and ':20:' in msg and '{5:' in msg
    msg = mt202_cov(); assert '{2:I202' in msg and '{3:' in msg and '119:COV' in msg
    msg = mt940_with_balance(); assert '{2:I940' in msg and ':60F:' in msg and ':86:' in msg
    msg = malformed_missing_block_4(); assert '{4:' not in msg
    print('ok')
    "
    ```
- **Expected:** `ok`.

### Task 14-07-002 -- Generate YAML layouts (mt_basic, mt_with_block3)

- **Type:** fixture
- **Description:** Create the two YAML layout files per RESEARCH §SWIFT YAML config / layout shapes. Cover both `pipe_fields` shapes (simple string + dict form), `processing.strip_whitespace`, block 1/2/4 always parsed; `mt_with_block3.yaml` adds block 3.
- **Files:** `tests/fixtures/swift/layouts/mt_basic.yaml`, `tests/fixtures/swift/layouts/mt_with_block3.yaml`
- **Verification:** `python -c "import yaml; [yaml.safe_load(open(f)) for f in ['tests/fixtures/swift/layouts/mt_basic.yaml','tests/fixtures/swift/layouts/mt_with_block3.yaml']]; print('ok')"`
- **Expected:** `ok`.

### Task 14-07-003 -- Generate transform configs + lookup CSV

- **Type:** fixture
- **Description:** Create `tests/fixtures/swift/configs/transform_minimum.yaml` and `transform_with_lookup.yaml` per RESEARCH §SWIFT YAML config. Cover `field_mappings` rule shapes: `rule: condition` (`when`/`then`/`else`), `source` + `transform` shape. `transformations.trim` (regex_replace). `lookups` block in the with_lookup config.
    Create `tests/fixtures/swift/lookups/bic_country.csv` -- minimum 5 BIC -> country rows; ASCII only.
- **Files:** `tests/fixtures/swift/configs/transform_minimum.yaml`, `tests/fixtures/swift/configs/transform_with_lookup.yaml`, `tests/fixtures/swift/lookups/bic_country.csv`
- **Verification:** `python -c "import yaml; yaml.safe_load(open('tests/fixtures/swift/configs/transform_minimum.yaml')); yaml.safe_load(open('tests/fixtures/swift/configs/transform_with_lookup.yaml')); import csv; list(csv.reader(open('tests/fixtures/swift/lookups/bic_country.csv'))); print('ok')"`
- **Expected:** `ok`.

### Task 14-07-004 -- Generate pipeline-job JSON fixtures

- **Type:** fixture
- **Description:** Create the three JSON job configs under `tests/fixtures/jobs/swift/`. Mirror converter output shape. Use placeholder paths via `mutations`. Component lineup:
    - `mt103_basic.json`: tFileInputRaw -> SwiftBlockFormatter -> tFileOutputDelimited (3 components)
    - `mt202_with_lookup.json`: tFileInputRaw -> SwiftBlockFormatter -> SwiftTransformer (with lookup) -> tFileOutputDelimited (4 components)
    - `mt940_block_formatter.json`: tFileInputRaw -> SwiftBlockFormatter -> tFileOutputDelimited (3 components)
- **Files:** `tests/fixtures/jobs/swift/mt103_basic.json`, `tests/fixtures/jobs/swift/mt202_with_lookup.json`, `tests/fixtures/jobs/swift/mt940_block_formatter.json`
- **Verification:** `python -c "import json; [json.load(open(f)) for f in ['tests/fixtures/jobs/swift/mt103_basic.json','tests/fixtures/jobs/swift/mt202_with_lookup.json','tests/fixtures/jobs/swift/mt940_block_formatter.json']]; print('ok')"`
- **Expected:** `ok`.

## Wave 1 -- Tests for swift_block_formatter

### Task 14-07-005 -- Unit + pipeline tests for swift_block_formatter (NEW test file)

- **Type:** test
- **Description:** Create `tests/v1/engine/components/transform/test_swift_block_formatter.py`. Use synthetic generator + YAML layouts. Cover:
    1. `_init_swift_parser` happy path (lines 33-79 from RESEARCH gap analysis)
    2. Block 1/2/4 parsing -> output DataFrame columns derived from `pipe_fields`
    3. Block 3 optional path: present (mt_with_block3.yaml + mt202_cov input) and absent (mt_basic.yaml + mt103_minimum)
    4. Block 4 field-tag dispatch: every tag in synthesizer (`:20:`, `:23B:`, `:32A:`, `:50K:`, `:59:`, `:70:`, `:71A:`, `:25:`, `:60F:`, `:62F:`, `:61:`, `:86:`, `:28C:`, `:21:`, `:52A:`, `:58A:`)
    5. Multi-line field values (`:86:` with `\n`)
    6. Malformed input (`malformed_missing_block_4`) -> raises `ConfigurationError` or `DataValidationError`; assert specific subclass
    7. `pipe_fields` simple-string form + dict form (default value applied when missing source)
    8. `processing.strip_whitespace=true` vs `false` branches
    9. Pipeline test via `run_job_fixture("swift/mt103_basic", mutations={...})` writing a synthetic MT to a tmp file and verifying parsed columns flow to output
    10. ASCII-only logs via `assert_ascii_logs`
- **Files:** `tests/v1/engine/components/transform/test_swift_block_formatter.py`
- **Verification:** `python -m pytest tests/v1/engine/components/transform/test_swift_block_formatter.py --cov=src/v1/engine/components/transform/swift_block_formatter --cov-report=term-missing -q`
- **Expected:** Coverage >= 95% for `swift_block_formatter.py`; tests green.
- **Notes:** Use `@pytest.mark.slow` if any test exceeds 5s wall time (RESEARCH §D-D4). Apply D-C5 if a missed line cannot be hit with any realistic synthetic input (delete dead branch; document in plan summary). When uncovered, READ the engine code at the missed line to identify the field-presence trigger and add a synthetic variant (RESEARCH §Pitfall 6).

## Wave 2 -- Tests for swift_transformer

### Task 14-07-006 -- Unit + pipeline tests for swift_transformer (NEW test file)

- **Type:** test
- **Description:** Create `tests/v1/engine/components/transform/test_swift_transformer.py`. Cover:
    1. `_init_transformer_config` (lines 43-77 from RESEARCH gap analysis)
    2. `input_fields` type coercion (string, int, decimal, date)
    3. `output_fields` defaults applied when source missing
    4. `field_mappings` rule shapes:
        - `rule: condition` with `when`/`then`/`else` -- both branches taken
        - `source: <name>` + `transform: <name>` -- transform applied (regex_replace `trim`)
    5. `transformations` types: `regex_replace`, `lookup` (CSV-backed), `format` (if engine supports it -- read source to confirm)
    6. `lookups`: hit + miss + missing CSV file -> `FileOperationError`
    7. `output_layout` ordering preserved
    8. Pipeline test via `run_job_fixture("swift/mt202_with_lookup", mutations={...})` -- assert specific output columns + globalMap stats
    9. Specific exception types in all `raises`
- **Files:** `tests/v1/engine/components/transform/test_swift_transformer.py`
- **Verification:** `python -m pytest tests/v1/engine/components/transform/test_swift_transformer.py --cov=src/v1/engine/components/transform/swift_transformer --cov-report=term-missing -q`
- **Expected:** Coverage >= 95% for `swift_transformer.py`; tests green.

## Wave 3 -- Per-plan gate verification

### Task 14-07-007 -- Per-plan gate verification

- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/transform/ -m "not oracle" -n auto \
      --cov=src/v1/engine/components/transform --cov-report=json:cov_14_07.json -q
    python scripts/check_per_module_coverage.py cov_14_07.json --floor 95
    ```
- **Expected:** PASS for `swift_transformer.py` and `swift_block_formatter.py`. (Other transform modules covered by 14-05 / 14-06 should already be PASS.)

</waves>

<verification_gate>

Plan 14-07 is GREEN when:
1. `swift_transformer.py` >= 95%.
2. `swift_block_formatter.py` >= 95%.
3. Synthetic generator produces ASCII-only output (verified via `synthetic.py` self-test in 14-07-001).
4. ETLError subclasses in all `raises`.
5. No new `# pragma: no cover` outside D-C3 allowlist; any D-C5 deletions are documented in plan summary.
6. Pipeline tests via `run_job_fixture` succeed.
7. `assert_ascii_logs` clean.
8. Per-module gate exits 0 for both SWIFT modules.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(14-07): INFRA-SWIFT-001 add synthetic.py MT message generator + __init__.py` | `tests/fixtures/swift/__init__.py`, `tests/fixtures/swift/synthetic.py` |
| 2 | `chore(14-07): INFRA-SWIFT-002 add YAML layout fixtures (mt_basic, mt_with_block3)` | `tests/fixtures/swift/layouts/*.yaml` |
| 3 | `chore(14-07): INFRA-SWIFT-003 add transform configs + bic_country lookup CSV` | `tests/fixtures/swift/configs/*.yaml`, `tests/fixtures/swift/lookups/bic_country.csv` |
| 4 | `chore(14-07): INFRA-SWIFT-004 add pipeline-job JSON fixtures (mt103/mt202/mt940)` | `tests/fixtures/jobs/swift/*.json` |
| 5 | `test(14-07): COV-SBF-001 swift_block_formatter to 95% (5-block parsing, field-tag dispatch, multi-line, malformed, pipeline tests)` | `tests/v1/engine/components/transform/test_swift_block_formatter.py` |
| 6 | `test(14-07): COV-SWT-001 swift_transformer to 95% (rule shapes, transformations, lookups, output_layout, pipeline tests)` | `tests/v1/engine/components/transform/test_swift_transformer.py` |
| 7+ (conditional) | `chore(14-07): STALE-SWIFT-NN delete dead branch in <module> per D-C5` -- only if D-C5 deletions surface | source files |
| 8+ (conditional) | `fix(14-07): BUG-SWIFT-NN <description>` -- only if real bugs surface | source files |

(Total: 6 + optional D-C5 / bug commits.)

</commit_map>
