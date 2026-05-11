# Gold Standard: Engine Test Pattern

*Last updated: 2026-05-11*

> Reference: test_global_map.py (best example -- one-class-per-concern, fresh fixtures, comprehensive coverage)

Every engine component test file MUST follow this structure and cover these categories.

---

## File Structure

```python
"""Tests for {ComponentName} ({tComponentName} engine implementation)."""
import pytest
import pandas as pd

from src.v1.engine.components.{category}.{module} import {ComponentName}
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, DataValidationError


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "{ComponentName}",
    "required_key": "value",
    # ... all required config keys with valid defaults
}


def _make_component(config=None, global_map=None, context_manager=None):
    """Create a {ComponentName} with test defaults.

    Always creates fresh GlobalMap and ContextManager instances
    unless explicitly provided.
    """
    gm = global_map or GlobalMap()
    cm = context_manager or ContextManager()
    return {ComponentName}(
        component_id="{abbrev}_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_input_df(rows=None):
    """Create test input DataFrame with realistic data."""
    if rows is None:
        rows = [
            {"id": 1, "name": "Alice", "amount": 100.50},
            {"id": 2, "name": "Bob", "amount": 200.75},
            {"id": 3, "name": "Charlie", "amount": 0.0},
        ]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for missing/invalid keys."""

    def test_missing_required_key_raises(self):
        config = dict(_DEFAULT_CONFIG)
        del config["required_key"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="required_key"):
            comp.execute()

    def test_invalid_enum_value_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["mode"] = "INVALID"
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="mode"):
            comp.execute()

    def test_valid_config_does_not_raise(self):
        comp = _make_component()
        # Should not raise -- use execute() with appropriate input
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


@pytest.mark.unit
class TestDefaults:
    """Default config produces expected behavior."""

    def test_default_config_processes_data(self):
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert "main" in result

    def test_default_mode_value(self):
        comp = _make_component()
        # Verify default mode is applied correctly
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


@pytest.mark.unit
class TestMainFlow:
    """Core _process logic with various inputs."""

    def test_basic_processing(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)

    def test_output_has_expected_columns(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        # Verify expected output columns
        assert "id" in result["main"].columns

    def test_row_count_matches_expectation(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        assert len(result["main"]) == len(df)  # or expected count

    def test_data_values_correct(self):
        comp = _make_component()
        df = _make_input_df([{"id": 1, "name": "Test"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["id"] == 1


@pytest.mark.unit
class TestRejectFlow:
    """Reject output produced correctly for invalid/filtered rows."""

    def test_reject_none_when_all_rows_pass(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        # If component filters, verify no rejects on clean data
        assert result.get("reject") is None or result["reject"].empty

    def test_reject_contains_filtered_rows(self):
        comp = _make_component(config={
            **_DEFAULT_CONFIG,
            "filter_condition": "some condition that rejects rows",
        })
        df = _make_input_df()
        result = comp.execute(df)
        reject = result.get("reject")
        if reject is not None:
            assert isinstance(reject, pd.DataFrame)

    def test_main_plus_reject_equals_input(self):
        """Main + reject row counts must equal input row count."""
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        main_count = len(result["main"]) if result["main"] is not None else 0
        reject_count = (
            len(result["reject"])
            if result.get("reject") is not None
            and isinstance(result["reject"], pd.DataFrame)
            else 0
        )
        assert main_count + reject_count == len(df)


@pytest.mark.unit
class TestEdgeCases:
    """Empty DataFrame, None input, single row, special values."""

    def test_empty_dataframe_input(self):
        comp = _make_component()
        df = pd.DataFrame()
        result = comp.execute(df)
        assert result["main"] is not None

    def test_none_input_for_source_component(self):
        """Source components receive None as input_data."""
        comp = _make_component()
        result = comp.execute(None)
        assert "main" in result

    def test_single_row_input(self):
        comp = _make_component()
        df = _make_input_df([{"id": 1, "name": "Only"}])
        result = comp.execute(df)
        assert len(result["main"]) >= 0  # Depends on component logic

    def test_nan_values_in_input(self):
        comp = _make_component()
        df = pd.DataFrame([
            {"id": 1, "name": None},
            {"id": 2, "name": "Bob"},
        ])
        result = comp.execute(df)
        assert "main" in result

    def test_large_dataset(self):
        """Verify component handles larger-than-trivial input."""
        comp = _make_component()
        rows = [{"id": i, "name": f"user_{i}"} for i in range(1000)]
        df = pd.DataFrame(rows)
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)


@pytest.mark.unit
class TestGlobalMapVariables:
    """Component-specific globalMap vars set correctly."""

    def test_stats_pushed_to_global_map(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_input_df())
        # BaseComponent pushes NB_LINE, NB_LINE_OK, NB_LINE_REJECT
        assert gm.get_component_stat("{abbrev}_1", "NB_LINE") >= 0

    def test_component_specific_vars_set(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_input_df())
        # Verify component-specific variables (e.g., {id}_FILENAME)
        # assert gm.get("{abbrev}_1_FILENAME") == expected_path

    def test_stats_without_global_map(self):
        """Component works without GlobalMap (for isolated testing)."""
        comp = _make_component(global_map=None)
        # Manually set global_map to None after construction
        comp.global_map = None
        result = comp.execute(_make_input_df())
        assert "main" in result


@pytest.mark.unit
class TestSchemaHandling:
    """Type coercion, nullable columns, schema mismatch."""

    def test_output_matches_schema_types(self):
        config = dict(_DEFAULT_CONFIG)
        config["schema"] = {
            "output": [
                {"name": "id", "type": "id_Integer", "nullable": False},
                {"name": "name", "type": "id_String", "nullable": True},
            ]
        }
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        # Verify types after schema validation
        assert result["main"] is not None

    def test_nullable_column_allows_nan(self):
        config = dict(_DEFAULT_CONFIG)
        config["schema"] = {
            "output": [
                {"name": "name", "type": "id_String", "nullable": True},
            ]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"name": None}, {"name": "Bob"}])
        result = comp.execute(df)
        assert result["main"] is not None

    def test_non_nullable_column_with_nan_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["schema"] = {
            "output": [
                {"name": "id", "type": "id_Integer", "nullable": False},
            ]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame([{"id": None}])
        # Component that applies schema validation should raise
        # DataValidationError for non-nullable column with NaN


@pytest.mark.unit
class TestIterateReexecution:
    """execute() twice gives correct results both times (config not stale)."""

    def test_second_execute_produces_correct_results(self):
        comp = _make_component()
        df = _make_input_df()

        result1 = comp.execute(df)
        comp.reset()
        result2 = comp.execute(df)

        assert len(result1["main"]) == len(result2["main"])

    def test_stats_reset_between_executions(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_input_df()

        comp.execute(df)
        first_nb_line = gm.get_component_stat("{abbrev}_1", "NB_LINE")

        comp.reset()
        comp.execute(df)
        second_nb_line = gm.get_component_stat("{abbrev}_1", "NB_LINE")

        # Stats should reflect only the second execution, not accumulated
        assert second_nb_line == first_nb_line

    def test_config_not_mutated_across_executions(self):
        comp = _make_component()
        df = _make_input_df()

        comp.execute(df)
        original_config_snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(df)

        # _original_config must not have changed
        assert comp._original_config == original_config_snapshot
```

---

## Rules

### Rule 1: One Test Class Per Concern

Every test file MUST have separate classes for each concern:

| Class | Purpose | Required? |
|-------|---------|-----------|
| `TestValidation` | ConfigurationError on missing/invalid config | YES |
| `TestDefaults` | Default config produces expected behavior | YES |
| `TestMainFlow` | Core processing logic with various inputs | YES |
| `TestRejectFlow` | Reject output for filtered/invalid rows | YES (if component filters) |
| `TestEdgeCases` | Empty DataFrame, None, single row, NaN, large | YES |
| `TestGlobalMapVariables` | Component-specific globalMap vars | YES |
| `TestSchemaHandling` | Type coercion, nullable, schema mismatch | YES (if component validates schema) |
| `TestIterateReexecution` | execute() twice with reset() between | YES |

### Rule 2: Fixture Helpers at Module Level

Every test file defines `_make_component()` and `_make_input_df()` at module level. These create fresh instances for each test -- no shared mutable state.

```python
def _make_component(config=None, global_map=None, context_manager=None):
    gm = global_map or GlobalMap()
    cm = context_manager or ContextManager()
    return ComponentName(
        component_id="comp_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
```

### Rule 3: In-Memory DataFrames (with tmp_path Exception for File Components)

Test data MUST be created as in-memory `pd.DataFrame` objects. No reading from external fixtures files.

```python
def _make_input_df(rows=None):
    if rows is None:
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    return pd.DataFrame(rows)
```

**Exception: File I/O components** (FileInputDelimited, FileOutputDelimited, etc.) inherently
need real files. These tests use pytest's `tmp_path` fixture to create files programmatically.
All paths use `pathlib.Path` for cross-OS compatibility. A small fixture directory at
`tests/v1/engine/fixtures/file/` may hold pre-built files for complex cases (specific encodings).

```python
def test_reads_csv_with_semicolon_delimiter(self, tmp_path):
    f = tmp_path / "input.csv"
    f.write_text("a;b;c\n1;2;3\n", encoding="iso-8859-15")
    config = {**_DEFAULT_CONFIG, "filepath": str(f), "fieldseparator": ";"}
    comp = _make_component(config=config)
    result = comp.execute(None)
    assert len(result["main"]) == 1
```

### Rule 4: Fresh GlobalMap and ContextManager Per Test

Every test creates its own GlobalMap and ContextManager instances. Never share mutable instances between tests.

```python
def test_stats_pushed(self):
    gm = GlobalMap()  # Fresh per test
    comp = _make_component(global_map=gm)
    comp.execute(_make_input_df())
    assert gm.get_component_stat("comp_1", "NB_LINE") > 0
```

### Rule 5: Test Through execute() Lifecycle

Test component behavior through the `execute()` method, NOT by calling `_process()` directly. The `execute()` lifecycle handles config resolution, validation, stats, and error wrapping -- skipping it means testing incomplete behavior.

```python
# WRONG -- skips config resolution, validation, stats
def test_process_directly(self):
    comp = _make_component()
    comp.config = comp._original_config.copy()
    result = comp._process(df)

# CORRECT -- tests full lifecycle
def test_via_execute(self):
    comp = _make_component()
    result = comp.execute(df)
```

Exception: Testing `_validate_config()` in isolation is acceptable via `execute()` (it raises before `_process()`).

### Rule 6: Mark All Tests with @pytest.mark.unit

Every test class MUST be decorated with `@pytest.mark.unit`:

```python
@pytest.mark.unit
class TestMainFlow:
    ...
```

### Rule 7: Test File Naming

Test files MUST match the source module name with `test_` prefix:

| Source | Test |
|--------|------|
| `src/v1/engine/components/file/file_input_delimited.py` | `tests/v1/engine/components/file/test_file_input_delimited.py` |
| `src/v1/engine/components/transform/filter_rows.py` | `tests/v1/engine/components/transform/test_filter_rows.py` |

### Rule 8: Each Test File Creates Own Fixtures

No shared conftest.py fixtures for component tests. Each test file defines its own `_make_component()`, `_make_input_df()`, and `_DEFAULT_CONFIG`. This keeps tests self-contained and makes it easy to understand what each test is doing.

### Rule 9: Test Both Happy Path and Error Cases

Every test class MUST include both successful and failing scenarios:

```python
class TestValidation:
    def test_valid_config_accepted(self):     # Happy path
        ...
    def test_missing_key_raises(self):        # Error case
        ...
    def test_invalid_value_raises(self):      # Error case
        ...
```

### Rule 10: Verify Stats After Execution

After calling `execute()`, verify that stats (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) reflect the actual processing:

```python
def test_stats_reflect_processing(self):
    comp = _make_component()
    df = _make_input_df()  # 3 rows
    result = comp.execute(df)
    assert result["stats"]["NB_LINE"] == 3
    assert result["stats"]["NB_LINE_OK"] == 3
    assert result["stats"]["NB_LINE_REJECT"] == 0
```

### Rule 11: Iterate Re-Execution Tests Are Mandatory

Every component MUST have `TestIterateReexecution` verifying that `execute()` works correctly after `reset()`:

```python
def test_second_execute_after_reset(self):
    comp = _make_component()
    result1 = comp.execute(df)
    comp.reset()
    result2 = comp.execute(df)
    assert len(result1["main"]) == len(result2["main"])
```

This catches state leaks (ENG-09) where config mutation or accumulated state breaks re-execution.

---

## Anti-Patterns

### Do NOT test private methods directly

```python
# WRONG -- tests internal implementation, breaks on refactor
def test_parse_encoding(self):
    result = FileInputDelimited._parse_encoding("UTF-8")
    assert result == "utf-8"

# CORRECT -- test through execute() which uses the private method
def test_encoding_applied(self):
    comp = _make_component(config={**_DEFAULT_CONFIG, "encoding": "UTF-8"})
    result = comp.execute(None)
    assert result["main"] is not None
```

### Do NOT use shared mutable fixtures

```python
# WRONG -- mutation in one test affects another
_SHARED_GM = GlobalMap()

class TestComponent:
    def test_one(self):
        comp = _make_component(global_map=_SHARED_GM)
        ...
    def test_two(self):
        comp = _make_component(global_map=_SHARED_GM)  # DIRTY state from test_one!
        ...

# CORRECT -- fresh per test
class TestComponent:
    def test_one(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        ...
```

### Do NOT skip edge cases

```python
# WRONG -- only tests happy path
class TestMainFlow:
    def test_basic(self):
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert result["main"] is not None
    # No empty df, no None, no NaN, no single row tests!

# CORRECT -- TestEdgeCases class covers all boundaries
```

### Do NOT test only the happy path

```python
# WRONG -- no error cases tested
class TestValidation:
    def test_valid_config(self):
        comp = _make_component()
        result = comp.execute(df)  # Only tests success

# CORRECT -- both success and failure
class TestValidation:
    def test_valid_config_accepted(self):
        comp = _make_component()
        result = comp.execute(df)
    def test_missing_key_raises(self):
        comp = _make_component(config={})
        with pytest.raises(ConfigurationError):
            comp.execute(df)
```

### Do NOT mock the component under test

```python
# WRONG -- mocking _process() tests nothing real
from unittest.mock import patch

def test_with_mock(self):
    with patch.object(MyComponent, "_process", return_value={"main": df}):
        comp = _make_component()
        result = comp.execute(df)

# CORRECT -- test the real _process() through execute()
def test_real(self):
    comp = _make_component()
    result = comp.execute(df)
```

### Do NOT use file I/O in non-file-component unit tests

```python
# WRONG -- depends on filesystem, slow, fragile
def test_reads_file(self):
    comp = _make_component(config={"file_path": "/tmp/test.csv"})
    with open("/tmp/test.csv", "w") as f:
        f.write("id,name\n1,Alice\n")
    result = comp.execute(None)

# CORRECT for non-file components -- use in-memory data
def test_processes_data(self):
    comp = _make_component()
    df = _make_input_df()
    result = comp.execute(df)
```

File I/O components use `tmp_path` instead -- see Rule 3 for the pattern.

---

## Test Directory Structure

```
tests/
  v1/
    engine/
      __init__.py
      test_global_map.py
      test_context_manager.py
      test_trigger_manager.py
      test_base_component.py
      components/
        __init__.py
        file/
          __init__.py
          test_file_input_delimited.py
          test_file_output_delimited.py
        transform/
          __init__.py
          test_filter_rows.py
          test_sort_row.py
          test_filter_columns.py
        aggregate/
          __init__.py
          test_aggregate_row.py
        context/
          __init__.py
          test_context_load.py
```

Test directory structure mirrors the source directory structure under `src/v1/engine/`.

---

## Coverage Categories Checklist

Before submitting a component test file, verify these categories are covered:

- [ ] **TestValidation** -- ConfigurationError for every required config key
- [ ] **TestDefaults** -- Default config produces valid output
- [ ] **TestMainFlow** -- Core logic with 3+ test methods
- [ ] **TestRejectFlow** -- Reject output (or verify no reject for non-filtering components)
- [ ] **TestEdgeCases** -- Empty DataFrame, None input, single row, NaN values, large dataset
- [ ] **TestGlobalMapVariables** -- Stats pushed, component-specific vars set, works without GlobalMap
- [ ] **TestSchemaHandling** -- Type coercion, nullable, non-nullable with NaN
- [ ] **TestIterateReexecution** -- execute() after reset() produces correct results, stats reset, config unchanged

---

## Phase 14 Pipeline-Test Pattern (lifecycle-sensitive modules)

Component unit tests built around `_make_component()` exercise the BaseComponent
lifecycle, but they do NOT exercise the full engine REGISTRY lookup, trigger
orchestration, schema-attachment, or context-resolution pipeline. For lifecycle-
sensitive modules (executor, base_component, iterate, file I/O, trigger flow),
unit tests MUST be augmented with pipeline tests that drive the full engine.

### Pipeline-test fixtures

Two pytest fixtures in `tests/conftest.py` carry this pattern:

- `run_job_fixture` -- callable that loads a fixture JSON from
  `tests/fixtures/jobs/{subsystem}/{behavior}.json` (format mirrors the
  converter's JSON output), applies optional config mutations + context
  overrides, invokes `ETLEngine.run_job(...)`, and returns a structured
  result for assertion.
- `assert_ascii_logs` -- captures DEBUG-level log records during a test and
  asserts no Unicode characters appear in caplog output. Enforces ASCII
  discipline (Rule 1: ASCII-only logging) at test time, not just at code
  review time.

### Why pipeline tests are mandatory (not optional)

Mock-only / `_make_component()`-only tests PASS even when the class is
unregistered with `@REGISTRY.register`. The engine's runtime lookup path
silently drops unregistered classes with `WARNING [engine] Unknown component
type: <type>`; the job continues without the component. Unit tests with
direct instantiation bypass that lookup entirely.

Phase 14 closed 4 dual-bug instances of exactly this failure mode in
already-shipped code. Each was caught precisely BECAUSE pipeline tests
exercised the full engine REGISTRY lookup path:

- **BUG-PDC-001** / **BUG-PDC-002**: `PythonDataFrameComponent`
  (`src/v1/engine/components/transform/python_dataframe_component.py`) was
  missing both `@REGISTRY.register` and `_validate_config()` implementation.
- **BUG-SWIFT-001** / **BUG-SWIFT-002**: `SwiftTransformer` and
  `SwiftBlockFormatter` (`src/v1/engine/components/transform/swift_*.py`)
  same dual gap.
- **BUG-FIJ-001** / **BUG-FIJ-002**: `FileInputJSON`
  (`src/v1/engine/components/file/file_input_json.py`) same dual gap.

See `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` Rule 13 for the
authoring-side invariant; this section is the test-side enforcement.

### Coverage gate

Every test surface (unit + pipeline) contributes to the 95% per-module line-
coverage floor enforced by `scripts/check_per_module_coverage.py` against the
`coverage.json` report. The Phase 14 gate command is in `docs/CONTRIBUTING.md`
Rule 6 (paste-runnable from the project root). The script exits non-zero with
a per-module table if any in-scope module drops below 95% lines.

### Fixture-authoring format

Pipeline-test fixture jobs live under `tests/fixtures/jobs/{subsystem}/`
(currently: `core/`, `file/`, `swift/`, `transform/`). The JSON format mirrors
the converter's output so the same fixture exercises both converter-to-engine
parity and the engine's full pipeline. See `tests/fixtures/jobs/README.md` for
the canonical format + mutation conventions used by `run_job_fixture`.
