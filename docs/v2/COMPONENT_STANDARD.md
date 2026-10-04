# v2 Component Standard

Reference specification for building, testing, documenting, and benchmarking
v2 Polars ETL engine components. Every component that ships in the v2 engine
follows this contract exactly -- no exceptions, no "we'll clean it up later."

This document was written **last** (after all infrastructure and the
FilterColumns prover landed) so that every section cites real, working
artifacts. If a code example appears here, the underlying file exists on disk
and passes tests.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Code Layout](#2-code-layout)
3. [SUPPORTED_FEATURES Declaration](#3-supported_features-declaration)
4. [Registry Registration](#4-registry-registration)
5. [Documentation](#5-documentation)
6. [Test Conventions](#6-test-conventions)
7. [Benchmark Harness](#7-benchmark-harness)
8. [talend_to_v2 Converter](#8-talend_to_v2-converter)
9. [Enforcement Gates](#9-enforcement-gates)
10. [Python Component Exemption](#10-python-component-exemption)

**Appendices**

- [A. tFilterColumn Walkthrough](#appendix-a-tfiltercolumn-walkthrough)
- [B. Onboarding Checklist](#appendix-b-onboarding-checklist)

---

## 1. Overview

### What Is the v2 Component Standard?

The v2 Component Standard is the contract every component in the v2 Polars ETL
engine must satisfy before it is considered "done." It defines file layout,
class structure, feature declarations, test patterns, benchmark gates, documentation
headings, and converter integration.

### Core Value

**Performance first, capability second.** Every v2 component runs at Polars
speed. Every Talend feature that cannot be expressed as a lazy `pl.Expr`
operation or a vectorized Polars transformation is explicitly out -- documented
in the component's unsupported-features table and reported by the
`talend_to_v2` converter at conversion time.

### Five Deliverables per Component

Each component produces exactly five artifacts:

| # | Deliverable | Location |
|---|-------------|----------|
| 1 | **Runtime** | `src/v2/components/<category>/<name>.py` |
| 2 | **Converter** | `src/converters/talend_to_v2/components/<category>/<name>_converter.py` |
| 3 | **Documentation** | `docs/v2/components/<category>/<name>.md` |
| 4 | **Tests** | `tests/v2/components/<category>/test_<name>.py` |
| 5 | **Benchmark baseline** | `tests/v2/benchmark/baselines/<name>.json` |

No component is "done" until all five exist, pass CI, and are cited in the
registry-completeness gate.

---

## 2. Code Layout

### File Location

```
src/v2/components/<category>/<name>.py
```

Each component lives in its own file (one class per file). This was established
when FilterColumns was split from the shared `transform.py` into
`src/v2/components/transform/filter_columns.py`.

### Class Hierarchy

All v2 components inherit from the abstract base class
`Component` in `src/v2/components/base.py`:

```
Component(ABC)                 -- abstract root
  SourceComponent              -- _read() -> LazyFrame; produce() with schema validation
  SinkComponent                -- consume(inputs) -> None  (is_barrier=True)
  TransformComponent           -- pass-through (override apply())
  PythonComponent              -- Python UDF wrapper (is_barrier=True)
  UtilityComponent             -- side-effect components (is_barrier=True)
```

Choose the subclass that matches the component's role:

| Subclass | When to use | `is_barrier` |
|----------|-------------|--------------|
| `SourceComponent` | Reads data from files, databases, or external systems | No (unless schema validation) |
| `TransformComponent` | Transforms data lazily (select, filter, rename, join) | No |
| `SinkComponent` | Writes data to files, databases, or external targets | Yes |
| `PythonComponent` | Runs Python UDFs that require materialization | Yes |
| `UtilityComponent` | Side-effect operations (context loading, logging) | Yes |

### Constructor Pattern

Components override `_post_init()`, **not** `__init__()`. The base class
constructor handles `component_id`, `config`, `context`, `routine_registry`,
`streaming`, and `_collect_kwargs` setup, then calls `_post_init()`:

```python
class MyComponent(TransformComponent):
    def _post_init(self):
        """Initialize component-specific state."""
        self.threshold = self.config.get("threshold", 0.5)
```

This ensures base class constructor changes never break subclasses.

### `_collect_kwargs` Pattern

When a component needs to materialize (barrier components), use
`self._collect_kwargs` in the `.collect()` call. This dict is `{}` normally
and `{"engine": "streaming"}` when the engine runs in streaming mode:

```python
df = lf.collect(**self._collect_kwargs)
```

### `validate() -> List[str]`

Every component implements `validate()` to check its configuration. The method
returns a list of error strings (empty list means valid). It **never raises**
exceptions -- the engine collects errors and reports them:

```python
def validate(self) -> List[str]:
    errors = []
    if "columns" not in self.config:
        errors.append("FilterColumns requires 'columns' in config")
    return errors
```

### `apply(inputs) -> Dict[str, pl.LazyFrame]`

The core processing method. Takes a dict of named `LazyFrame` inputs and
returns a dict of named `LazyFrame` outputs. Components **never** call
`.collect()` inside `apply()` -- the engine handles materialization at barriers:

```python
def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
    data = inputs.get("main")
    if data is None:
        return {}
    return {"main": data.select([pl.col("id"), pl.col("name")])}
```

---

## 3. SUPPORTED_FEATURES Declaration

Every component declares which Talend features it supports, partially supports,
or excludes. This declaration powers converter warnings, documentation tables,
and registry-completeness tests.

### Infrastructure

The types live in `src/v2/components/capabilities.py`:

- **`Support`** -- an enum with four levels: `FULL`, `PARTIAL`, `UNSUPPORTED`,
  `NOT_PLANNED`.
- **`FeatureSupport`** -- a frozen dataclass with `support: Support` and
  `note: str`.
- **`get_supported_features(cls)`** -- returns `cls.SUPPORTED_FEATURES`
  directly (no MRO merging; each component's dict is authoritative for itself).

### Per-Component Feature Enum

Each component file defines its own `StrEnum` listing the Talend parameter
names it maps:

```python
from enum import Enum

class FilterColumnsFeature(str, Enum):
    """Talend tFilterColumns features mapped to v2 support levels."""
    columns = "columns"
    mode = "mode"
    tstatcatcher_stats = "tstatcatcher_stats"
    label = "label"
```

Feature keys use **snake_case** derived from the Talend XML parameter name
(e.g., `REMOVE_OR_KEEP` becomes `mode` when the semantic mapping is clearer).

### SUPPORTED_FEATURES Class Variable

The component class declares a `ClassVar[Dict[str, FeatureSupport]]` mapping
each feature enum value to its support level:

```python
from typing import ClassVar, Dict
from ..capabilities import FeatureSupport, Support

class FilterColumns(TransformComponent):
    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        FilterColumnsFeature.columns: FeatureSupport(
            support=Support.FULL,
            note="Column list with optional source->name rename mapping",
        ),
        FilterColumnsFeature.mode: FeatureSupport(
            support=Support.FULL,
            note="'keep' (default) selects listed columns; 'remove' drops them",
        ),
        FilterColumnsFeature.tstatcatcher_stats: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="tStatCatcher is a v1/Talend concept; use Python logging instead",
        ),
        FilterColumnsFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
    }
```

### Support Levels

| Level | Meaning | Converter behavior |
|-------|---------|-------------------|
| `FULL` | Feature fully supported in v2 | No warning |
| `PARTIAL` | Feature supported with caveats | `needs_review` entry emitted |
| `UNSUPPORTED` | Feature exists in Talend but cannot be implemented in Polars | Warning emitted |
| `NOT_PLANNED` | Feature is a Talend-specific concept with no v2 equivalent | Warning emitted (with advice) |

The `note` field is required for `PARTIAL`, `UNSUPPORTED`, and `NOT_PLANNED`.
It appears in converter output and generated documentation tables.

---

## 4. Registry Registration

### Decorator Pattern

Components register with the global `REGISTRY` via decorator in
`src/v2/components/registry.py`:

```python
from ..registry import REGISTRY

@REGISTRY.register("filter_columns")
class FilterColumns(TransformComponent):
    ...
```

Multiple aliases can be registered:

```python
@REGISTRY.register("file_input", "file_input_delimited")
class FileInputDelimited(SourceComponent):
    ...
```

### Case-Insensitive Lookup

Names are stored in lowercase. `REGISTRY.get("Filter_Columns")` resolves the
same class as `REGISTRY.get("filter_columns")`.

### Duplicate Registration Guard

Registering a **different** class under an existing name raises `ValueError`
(AUD-REG-01 regression guard). Re-registering the **same** class under the
same name is a no-op for import-side-effect idempotency.

### Side-Effect Import Requirement

Each component category's `__init__.py` must import the component module to
trigger the `@REGISTRY.register()` decorator. For example,
`src/v2/components/transform/__init__.py` must contain:

```python
from .filter_columns import FilterColumns  # noqa: F401
```

Without this import, the component will not appear in the registry and the
engine cannot resolve it from job configs.

---

## 5. Documentation

### File Location

```
docs/v2/components/<category>/<name>.md
```

Example: `docs/v2/components/transform/filter_columns.md`.

### Required Headings (8)

Every component doc must contain these headings in order:

1. **Purpose** -- one-sentence description of what the component does
2. **When to Use** -- bullet list of use cases
3. **Configuration** -- parameter table (`Parameter | Type | Default | Description`)
4. **Example** -- JSON config snippet(s)
5. **Supported Features** -- generated feature table
6. **Unsupported Features** -- manual table of excluded features with advice
7. **Performance** -- generated benchmark table + prose
8. **Talend Differences** -- comparison table with Talend equivalent

### GENERATED Markers

Two blocks in each doc are auto-populated from code introspection:

```markdown
<!-- GENERATED: features -->
...feature table from SUPPORTED_FEATURES...
<!-- /GENERATED: features -->

<!-- GENERATED: benchmarks -->
...benchmark table from baseline JSON...
<!-- /GENERATED: benchmarks -->
```

### Doc Generator

`scripts/gen_component_doc.py` populates the GENERATED blocks:

```bash
# Update a single doc:
python scripts/gen_component_doc.py docs/v2/components/transform/filter_columns.md

# Validate all docs (no-write):
python scripts/gen_component_doc.py --validate-only --all

# Update all docs:
python scripts/gen_component_doc.py --all
```

The `--validate-only` mode checks for:
- Missing required headings
- Stale GENERATED blocks (content differs from current introspection)

### Pre-commit and CI Enforcement

The `gen-component-doc` pre-commit hook runs `--validate-only --all` on every
commit that touches markdown files. This catches stale feature tables and
missing headings before they reach the remote. CI runs the same check as a
gate.

---

## 6. Test Conventions

### File Location

```
tests/v2/components/<category>/test_<name>.py
```

Test files mirror the `src/` layout. Each file contains one test class.

### ComponentTestCase Base Class

Every component test class subclasses `ComponentTestCase` from
`tests/v2/_harness/component_test_case.py`:

```python
from tests.v2._harness.component_test_case import ComponentTestCase
from src.v2.components.transform.filter_columns import FilterColumns

class TestFilterColumns(ComponentTestCase):
    component_type = "filter_columns"
    component_class = FilterColumns
    golden_dir = "filter_columns_cases"
```

### Class Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| `component_type` | `str` | Registry name for resolution |
| `component_class` | `Type[Component]` | Direct class reference (alternative to registry) |
| `golden_dir` | `str` | Subdirectory name for golden-case JSON files |
| `default_config` | `dict` | Default config merged into every `run_component()` call |

### `run_component()` -- Validate Before Apply

The harness method `run_component()` creates the component, calls `validate()`
before `apply()`, and returns the output dict. This gate ensures no component
skips configuration validation at test time:

```python
result = self.run_component(
    config={"columns": ["id", "name"]},
    inputs={"main": pl.DataFrame({"id": [1], "name": ["a"], "extra": [True]}).lazy()},
)
assert result["main"].collect().columns == ["id", "name"]
```

To test that invalid config is caught:

```python
result = self.run_component(
    config={},
    expect_validation_errors=True,
)
assert "_validation_errors" in result
```

### Golden-Case JSON Format

Golden-case files use column-oriented dicts:

```json
{
    "config": {"columns": ["id", "name"]},
    "inputs": {
        "main": {"id": [1, 2], "name": ["Alice", "Bob"], "extra": [true, false]}
    },
    "expected": {
        "main": {"id": [1, 2], "name": ["Alice", "Bob"]}
    }
}
```

Files live in `tests/v2/components/<category>/<name>_cases/` and are
discovered by `load_golden_cases()` which sorts by filename for deterministic
ordering.

### Integration Tests

Integration tests run a full job through `PyETLEngine.execute()` via the
`run_integration()` method. This verifies registry resolution, DAG building,
and the full execution pipeline -- not just the isolated component:

```python
def test_integration_pipeline(self):
    from src.v2.components.registry import REGISTRY
    cls = REGISTRY.get("filter_columns")
    assert cls is FilterColumns
    comp = cls("fc", {"columns": ["id", "name"]})
    assert comp.validate() == []
```

### Deleting Legacy Tests

When a component is onboarded to the standard, any old free-function tests for
that component are deleted and replaced by the `ComponentTestCase` subclass.
The new class inherits all harness guarantees (validate-before-apply, golden
cases, integration, benchmarks).

---

## 7. Benchmark Harness

### Purpose

Every v2 component must run within approximately 10% overhead compared to a
hand-written raw Polars script doing the same operation. This is enforced by
a benchmark test pair and a committed baseline.

### Benchmark Marker

Benchmark tests are marked with `@pytest.mark.benchmark` and quarantined
from the default test run via `addopts = "-m 'not benchmark'"` in
`pyproject.toml`. To run benchmarks explicitly:

```bash
# Run all benchmarks:
pytest tests/v2 -m benchmark

# Run benchmarks for a specific component:
pytest tests/v2 -m benchmark -k filter_columns
```

### Benchmark Test Pair

Each component provides two benchmark methods in its test class:

1. **`test_benchmark_ratio`** -- runs the v2 component and raw Polars
   side by side, asserts `ratio <= 1.10`.

The benchmark method warms up both paths, then times N runs of each,
compares medians:

```python
@pytest.mark.benchmark
def test_benchmark_ratio(self):
    # ... warmup both paths ...
    ratio = v2_median / raw_median
    assert ratio <= 1.10, f"Component is {ratio:.2f}x slower than raw Polars"
```

### Baseline JSON

Baselines are committed at `tests/v2/benchmark/baselines/<name>.json`:

```json
{
    "component": "filter_columns",
    "polars_version": "1.38.1",
    "python_version": "3.12.12",
    "raw_polars_median_ns": 8584,
    "v2_median_ns": 8667,
    "n_runs": 5,
    "ratio": 1.0097,
    "timestamp": "2026-04-12T10:28:32+0530",
    "machine_hash": "34b94d555643"
}
```

### Re-baseline Script

Baselines are captured via `scripts/rebaseline.py`. Re-baselining is a
deliberate act -- baselines are never updated automatically:

```bash
python scripts/rebaseline.py filter_columns
```

The script calls `write_baseline()` with benchmark parameters:
- `WARMUP = 1000` (warmup iterations before timing)
- `N_RUNS = 5` (timed iterations)
- `DISABLE_GC = True` (garbage collection disabled during timing)
- Polars version recorded for reproducibility

### The 10% Gate

The ratio assertion `ratio <= 1.10` is the hard gate. If a component
consistently exceeds 1.10x overhead, the implementation must be optimized
before it can ship. The raw Polars comparison is against a hand-written
equivalent using the same Polars API the component wraps.

---

## 8. talend_to_v2 Converter

### Purpose

The `talend_to_v2` converter is user-facing tooling that transforms Talend
`.item` XML files into v2 JSON job configs. Each v2 component has a
corresponding converter that maps Talend parameters to v2 config.

### File Location

```
src/converters/talend_to_v2/components/<category>/<name>_converter.py
```

Example: `src/converters/talend_to_v2/components/transform/filter_columns_converter.py`.

### Converter Base Class

Converters subclass `ComponentConverter` from
`src/converters/talend_to_v2/components/base.py`:

```python
from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
```

Key types:
- **`TalendNode`** -- parsed representation of a Talend component
  (`component_id`, `component_type`, `params`, `schema`, `raw_xml`)
- **`TalendConnection`** -- edge between components
  (`name`, `source`, `target`, `connector_type`)
- **`ComponentResult`** -- output of conversion
  (`component`, `flows`, `warnings`, `needs_review`)

### Converter Registration

Converters register with their own `CONVERTER_REGISTRY` using the **Talend
type name** (case-sensitive, PascalCase):

```python
from ..registry import REGISTRY as CONVERTER_REGISTRY

@CONVERTER_REGISTRY.register("tFilterColumns")
class FilterColumnsConverter(ComponentConverter):
    ...
```

### Feature Introspection

Converters introspect the runtime component's `SUPPORTED_FEATURES` to emit
appropriate warnings:

- **`UNSUPPORTED`** features with non-empty Talend values: emit a `warnings`
  entry
- **`PARTIAL`** features: emit a `needs_review` entry with severity
  `"engine_gap"`
- **`NOT_PLANNED`** features: emit a `warnings` entry with skip advice

```python
from src.v2.components.capabilities import Support, get_supported_features
from src.v2.components.transform.filter_columns import FilterColumns

features = get_supported_features(FilterColumns)
for feat_key, feat_support in features.items():
    if feat_support.support == Support.UNSUPPORTED:
        # Emit warning if Talend config uses this feature
        ...
```

### XML Fixtures

Test fixtures for converters are hand-crafted minimal XML files placed in:

```
tests/converters/talend_to_v2/fixtures/
```

These represent the minimal Talend XML needed to exercise each conversion path.

---

## 9. Enforcement Gates

Three automated gates enforce the standard across the project.

### Gate 1: Registry Completeness (`tests/v2/test_registry_completeness.py`)

A hardcoded `TARGET_COMPONENTS` frozenset lists every component that must be
registered. Each onboarding phase adds its component name to this set.

Two parametrized tests run against every entry:

1. **Registration gate** -- `REGISTRY.get(name)` returns a non-None class.
2. **SUPPORTED_FEATURES gate** -- `get_supported_features(cls)` returns a
   non-empty dict.

The `TARGET_COMPONENTS` frozenset is intentionally hardcoded (not
auto-discovered from disk) so that adding a new target component requires a
deliberate test-file edit:

```python
TARGET_COMPONENTS: frozenset = frozenset({
    "filter_columns",        # Phase 2
    # "filter",              # Phase 4 -- uncomment when onboarded
    # "union",               # Phase 5 -- uncomment when onboarded
    # ...
})
```

### Gate 2: Python-Callback Ban (`tests/v2/test_no_python_callbacks.py`)

Scans all `.py` files under `src/v2/components/` (excluding the `python/`
subdirectory) for banned patterns:

- `map_elements(`
- `.apply(lambda`
- `map_batches(`

Any match is a test failure. These patterns force row-by-row Python execution
and destroy Polars performance. The `python/` directory is excluded because
`python_row`, `python_code`, and `python_dataframe` are explicitly designed to
run Python code.

### Gate 3: Doc Validation (`scripts/gen_component_doc.py --validate-only`)

Runs as a pre-commit hook (`gen-component-doc` in `.pre-commit-config.yaml`)
and as a CI gate. Checks every component doc for:

- All 8 required headings present
- GENERATED blocks match current introspection output (not stale)

---

## 10. Python Component Exemption

Three components are exempted from the Python-callback ban:

- `python_row`
- `python_code`
- `python_dataframe`

These components exist specifically to run user-supplied Python code. They are
barrier components (`is_barrier = True`) because Python UDFs require
materialization.

### Benchmark Baseline Difference

Python components benchmark against a **raw Python loop** (or equivalent
non-Polars baseline), not against raw Polars. This is because the component's
purpose *is* to run Python -- comparing it to a lazy Polars expression would
be meaningless.

Their docs and benchmark baselines must clearly state this difference.

### Where the Exemption Is Enforced

- **`test_no_python_callbacks.py`** excludes `src/v2/components/python/` from
  its scan via the `EXCLUDED_DIRS` set.
- **Each Python component's doc** states the exemption in its Performance
  section.
- **This standard** (Section 10) documents the exemption rationale.

---

## Appendix A: tFilterColumn Walkthrough

This appendix walks through the complete end-to-end for FilterColumns -- the
component that proved the standard works. Every file path below exists on disk
and passes tests.

### A.1 Runtime: `src/v2/components/transform/filter_columns.py`

The runtime file contains three things:

**1. Feature Enum**

```python
class FilterColumnsFeature(str, Enum):
    columns = "columns"
    mode = "mode"
    tstatcatcher_stats = "tstatcatcher_stats"
    label = "label"
```

**2. SUPPORTED_FEATURES Declaration**

A four-entry dict mapping each feature to its support level. `columns` and
`mode` are `FULL`, `tstatcatcher_stats` is `NOT_PLANNED`, `label` is `FULL`.

**3. Component Class**

```python
@REGISTRY.register("filter_columns")
class FilterColumns(TransformComponent):
    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = { ... }

    def validate(self) -> List[str]:
        # Checks "columns" key exists and mode is valid
        ...

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        # mode="keep": data.select([...])
        # mode="remove": data.drop([...])
        ...
```

Key properties:
- Subclasses `TransformComponent` (not a barrier)
- `validate()` returns errors, never raises
- `apply()` never calls `.collect()` -- stays fully lazy
- Handles both string column names and `{"name": "target", "source": "original"}` rename dicts

### A.2 Converter: `src/converters/talend_to_v2/components/transform/filter_columns_converter.py`

```python
@CONVERTER_REGISTRY.register("tFilterColumns")
class FilterColumnsConverter(ComponentConverter):
    def convert(self, node, connections, context) -> ComponentResult:
        # 1. Extract mode from REMOVE_OR_KEEP param
        # 2. Extract columns from schema
        # 3. Build v2 config dict
        # 4. Introspect SUPPORTED_FEATURES for warnings
        # 5. Build component dict with type="filter_columns"
        # 6. Build flows via _build_simple_flows()
        return ComponentResult(component=..., flows=..., warnings=..., needs_review=...)
```

The converter introspects `FilterColumns.SUPPORTED_FEATURES` at conversion
time. If the Talend config uses a `NOT_PLANNED` or `UNSUPPORTED` feature,
the converter emits appropriate warnings.

### A.3 Documentation: `docs/v2/components/transform/filter_columns.md`

The doc contains all 8 required headings:

1. Purpose
2. When to Use
3. Configuration (parameter table)
4. Example (keep + remove mode JSON)
5. Supported Features (`<!-- GENERATED: features -->` block)
6. Unsupported Features (manual table)
7. Performance (`<!-- GENERATED: benchmarks -->` block + prose)
8. Talend Differences (comparison table)

The GENERATED blocks are populated by `gen_component_doc.py` from
`FilterColumns.SUPPORTED_FEATURES` and the committed baseline JSON.

### A.4 Tests: `tests/v2/components/transform/test_filter_columns.py`

```python
class TestFilterColumns(ComponentTestCase):
    component_type = "filter_columns"
    component_class = FilterColumns
    golden_dir = "filter_columns_cases"
```

Test methods:
- `test_golden_cases()` -- loads `filter_columns_cases/*.json`, runs each
  through `run_component()`, asserts outputs match expected
- `test_validate_missing_columns()` -- expects validation error
- `test_validate_invalid_mode()` -- expects validation error
- `test_keep_mode_default()` -- verifies default mode
- `test_remove_mode()` -- verifies remove mode drops columns
- `test_no_main_input()` -- verifies empty dict on missing input
- `test_not_barrier()` -- verifies `is_barrier is False`
- `test_integration_pipeline()` -- verifies REGISTRY resolution + full apply
- `test_benchmark_ratio()` -- benchmark with `@pytest.mark.benchmark`, asserts
  `ratio <= 1.10`

### A.5 Benchmark Baseline: `tests/v2/benchmark/baselines/filter_columns.json`

```json
{
    "component": "filter_columns",
    "polars_version": "1.38.1",
    "python_version": "3.12.12",
    "raw_polars_median_ns": 8584,
    "v2_median_ns": 8667,
    "n_runs": 5,
    "ratio": 1.0097
}
```

Ratio of 1.0097x confirms FilterColumns adds negligible overhead over raw
`pl.LazyFrame.select()`. This is expected -- FilterColumns is a pure lazy
transform that composes into the Polars query plan.

---

## Appendix B: Onboarding Checklist

Use this checklist when onboarding each new component to the standard. Replace
`<cat>` with the category (e.g., `transform`, `file`, `aggregate`) and
`<name>` with the component name (e.g., `filter_columns`, `sort`).

### Runtime

- [ ] Create `src/v2/components/<cat>/<name>.py`
- [ ] Define `<Name>Feature(str, Enum)` with Talend parameter keys
- [ ] Declare `SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]]`
- [ ] Subclass the appropriate base (`TransformComponent`, `SourceComponent`, etc.)
- [ ] Implement `validate() -> List[str]` (return errors, never raise)
- [ ] Implement `apply(inputs) -> Dict[str, pl.LazyFrame]` (never `.collect()`)
- [ ] Register with `@REGISTRY.register("<name>")`
- [ ] Import in `src/v2/components/<cat>/__init__.py` for side-effect registration

### Converter

- [ ] Create `src/converters/talend_to_v2/components/<cat>/<name>_converter.py`
- [ ] Subclass `ComponentConverter`
- [ ] Register with `@CONVERTER_REGISTRY.register("tTalendName")`
- [ ] Introspect `SUPPORTED_FEATURES` for `UNSUPPORTED`/`PARTIAL` warnings
- [ ] Create XML fixtures in `tests/converters/talend_to_v2/fixtures/`

### Tests

- [ ] Create `tests/v2/components/<cat>/test_<name>.py`
- [ ] Subclass `ComponentTestCase`
- [ ] Set `component_type`, `component_class`, `golden_dir` class attributes
- [ ] Create golden-case JSON files in `tests/v2/components/<cat>/<name>_cases/`
- [ ] Add validation error tests
- [ ] Add behavior tests
- [ ] Add integration test (REGISTRY resolution + full pipeline)
- [ ] Add `@pytest.mark.benchmark` test pair (`test_benchmark_ratio`)
- [ ] Delete any legacy free-function tests for this component

### Benchmark

- [ ] Run benchmark: `pytest tests/v2 -m benchmark -k <name>`
- [ ] Capture baseline: `python scripts/rebaseline.py <name>`
- [ ] Verify baseline exists at `tests/v2/benchmark/baselines/<name>.json`
- [ ] Verify `ratio <= 1.10`

### Documentation

- [ ] Create `docs/v2/components/<cat>/<name>.md` with all 8 required headings
- [ ] Add `<!-- GENERATED: features -->` and `<!-- GENERATED: benchmarks -->` markers
- [ ] Run `python scripts/gen_component_doc.py docs/v2/components/<cat>/<name>.md`
- [ ] Verify `python scripts/gen_component_doc.py --validate-only --all` passes

### Gates

- [ ] Add `"<name>"` to `TARGET_COMPONENTS` in `tests/v2/test_registry_completeness.py`
- [ ] Verify: `pytest tests/v2 -x -q -m "not benchmark"` passes
- [ ] Verify: `pytest tests/v2 -m benchmark -k <name>` passes
- [ ] Verify: `python scripts/gen_component_doc.py --validate-only --all` passes
