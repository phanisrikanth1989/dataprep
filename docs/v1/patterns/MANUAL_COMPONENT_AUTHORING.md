# Manual Component Authoring Guide

*Last updated: 2026-05-11 (Phase 14 lessons folded in)*

> For contributors writing engine components outside the GSD workflow.
> Last updated: 2026-05-11 (Phase 14 lessons folded in)

---

## Why This Document Exists

Phase 7.1 discovered six components calling `self.validate_schema()` inside `_process()`,
and four test files calibrated to a pre-7.1 double-counting bug in `_update_stats`. Both
sets of violations came from manual authoring without reference to the established contract.

This guide exists to prevent recurrence. If you are writing or modifying an engine component
outside the GSD workflow, read this document before writing a single line of code.

---

## Required Reading

Before authoring any component, read these documents in order:

1. `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` -- the 12 rules, file structure, anti-patterns
2. `docs/v1/patterns/ENGINE_TEST_PATTERN.md` -- test structure, required coverage classes, TDD gate, Phase 14 pipeline-test pattern
3. `CLAUDE.md` (project root) -- naming conventions, error handling, logging rules, import style

The converter side has its own pattern (`docs/v1/patterns/CONVERTER_PATTERN.md`) -- it is a
different system and its rules do not apply to engine components.

---

## The 12 Rules of BaseComponent Subclassing

These are hard rules, not guidelines. Each violation breaks the execution contract.

**Rule 1: Extend BaseComponent (or BaseIterateComponent)**
Every component class MUST extend `BaseComponent`. For iterate-producing components
(tFileList, tFlowToIterate, tForeach), extend `BaseIterateComponent` instead. Never
extend a sibling component class.

**Rule 2: _validate_config() is Required**
Every component MUST implement `_validate_config()`. Check ALL config keys the component
depends on. Raise `ConfigurationError` with a message that includes `self.id`. This method
runs on the UNRESOLVED config (context variables not yet substituted) -- validate structural
correctness only, not resolved values.

**Rule 3: _process() Returns Dict with 'main' Key**
`_process()` MUST return a dict with at least a `'main'` key containing a `pd.DataFrame`
or `None`. Use `'reject'` for rejected rows. Use named flow keys for multi-output components.
Never return a bare DataFrame.

**Rule 4: NEVER Override execute()**
The `execute()` method implements the Template Method lifecycle: config deepcopy,
`_validate_config()`, expression resolution, mode selection, `_process()`, stats update,
globalMap sync. Override ONLY `_validate_config()` and `_process()`. Any other override
breaks config immutability, expression resolution, stats, and error wrapping.

**Rule 5: Read Config in `_process()`, Not `__init__()`**
Config values are resolved by BaseComponent between `_validate_config()` and `_process()`.
Context variables (`${context.var}`) and Java expressions (`{{java}}...`) are NOT available
until `_process()` is called. Reading config in `__init__()` produces stale values on
re-execute and misses context substitution entirely.

**Rule 6: Use GlobalMap for Inter-Component Communication**
Use `self.global_map.put()` to set component-specific variables. Use `self.global_map.get()`
to read variables from upstream components. Stats (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) are
handled automatically by BaseComponent. Always guard with `if self.global_map:` -- components
must work without one in tests.

**Rule 7: Use Custom Exceptions**
Use the hierarchy in `src/v1/engine/exceptions.py`. Never raise generic `Exception`,
`RuntimeError`, or `ValueError`. Always include `self.id` in the message.

| Exception | When |
| --------- | ---- |
| `ConfigurationError` | Missing/invalid config keys, bad enum values |
| `DataValidationError` | Schema mismatch, constraint violations |
| `FileOperationError` | File not found, permission denied, encoding errors |
| `ExpressionError` | Invalid filter/condition expressions |

**Rule 8: Use Logger, Not print()**
Every module gets `logger = logging.getLogger(__name__)` at module level. Prefix log messages
with `[{self.id}]`. Never use `print()` in component code.

**Rule 9: Register via @REGISTRY.register() Decorator**
Use the decorator from `component_registry.py`. Pass both the V1 name (PascalCase) and the
Talend alias (with `t` prefix). Import the module from the package `__init__.py` to activate
the decorator on import.

**Rule 10: Component MUST Work After reset()**
Components are re-executed during iterate loops. Do NOT store mutable processing state on
`self` that persists across `execute()` calls. All processing state MUST be local to
`_process()`.

**Rule 11 -- DO NOT call `self.validate_schema()` inside `_process()`**

> **CRITICAL: This is the most commonly violated rule.**

BaseComponent runs schema validation automatically in step 7c (`_apply_output_schema_validation`)
AFTER `_process()` returns. Step 7b (`_enforce_schema_column_order`) also fills in any
missing schema columns with type-appropriate null values before validation runs.

Calling `self.validate_schema()` inside `_process()` causes two problems:

1. **Double-validation**: schema coercion runs twice, which can cause type errors on already-
   coerced columns.
2. **Race with missing-column fill**: `_process()` sees only the columns it produced; the base
   class fills missing columns in step 7b. If you call `validate_schema()` before 7b runs,
   missing columns are not present yet and the validation is incomplete.

```python
# WRONG -- Rule 11 violation
def _process(self, input_data=None) -> dict:
    output_df = _build_output(input_data)
    if self.output_schema:
        output_df = self.validate_schema(output_df, self.output_schema)  # DO NOT DO THIS
    return {"main": output_df, "reject": None}

# CORRECT -- BaseComponent handles it automatically in step 7c
def _process(self, input_data=None) -> dict:
    output_df = _build_output(input_data)
    return {"main": output_df, "reject": None}
```

---

## Rule 12: `_validate_config` may only check key presence and container shape -- never content

> **CRITICAL: This rule complements Rule 2 and was elevated to its own
> section after Phase 07.2 swept 11 components for violations.**

BaseComponent.execute() runs validation in this order
(`src/v1/engine/base_component.py:204-260`):

1. **Step 1**: `self.config = copy.deepcopy(self._original_config)` -- raw config restored
2. **Step 2**: `self._validate_config()` -- runs on UNRESOLVED config
3. **Step 3**: `self._resolve_expressions()` -- context vars (`${context.X}`,
   `context.X`) and Java `{{java}}` markers resolved
4. **Step 7**: `self._process()` -- `self.config` is now fully resolved

**The bug class:** Any `_validate_config()` that inspects the *content*
of a config field (length, regex, type coercion, enum membership for
non-closed-lists, file-exists, numeric range) -- when that field can
hold a context-var reference -- will spuriously reject or crash on
valid configs because it measures the unresolved literal, not the
runtime value.

Phase 07.2 fixed 6+ instances of this bug across file_archive,
file_input_positional, log_row, pivot_to_columns_delimited,
file_input_excel, file_output_delimited (CR-06), and send_mail. The
rule below codifies the contract.

### Allowed in `_validate_config`

- **Key presence**: `if not self.config.get("X"): raise ConfigurationError(...)`
- **Container shape**: `isinstance(value, list)`, `isinstance(value, dict)`, `isinstance(value, bool)`
- **Structural validity of immutable config**: e.g. schema list shape,
  number of rows in a fixed-shape config table.
- **Closed-list enum membership** ONLY when the converter is proven to
  emit a literal closed-list value (never a `${context.X}` string).
  Example: `tContextLoad.LOAD_NEW_VARIABLE` is one of WARNING / ERROR /
  NO_WARNING -- emitted as a literal -- so `if value not in {...}` is
  allowed. Document the converter evidence in a code comment when
  relying on this carve-out.

### Disallowed in `_validate_config`

- **Length checks**: `len(x) != 1`, `len(x) < N` -- defer to `_process`
- **Regex / pattern checks**: `re.match(...)`, `.startswith(...)` for
  content shape -- defer to `_process`
- **Numeric coercion**: `int(value)`, `float(value)`, `.isdigit()` --
  defer to `_process`
- **Numeric range**: `value < 0`, `value < 1 or value > 65535` -- defer
  to `_process`
- **File-exists / path checks**: `os.path.exists(value)` -- defer to
  `_process` (path may be `${context.X}`)
- **Enum membership for fields the converter emits as `_get_str`**:
  the field can hold a context var -- defer to `_process`

### Where deferred checks belong

Move the check verbatim into `_process()` at the earliest point after
`self.config` is the resolved dict. (BaseComponent has already run
Step 3 by the time `_process` is called -- no manual call needed.)

Preserve the **same exception type** and **same error message** so
behavior at the new check site is identical.

### Side-by-side example

**WRONG -- Rule 12 violation (rejects valid `${context.SEP}`):**

```python
def _validate_config(self) -> None:
    if not self.config.get("filepath"):
        raise ConfigurationError(f"[{self.id}] Missing required config 'filepath'")
    # WRONG: this measures the unresolved literal "${context.SEP}" as 14 chars
    sep = self.config.get("fieldseparator", ";")
    if len(sep) != 1:
        raise ConfigurationError(f"[{self.id}] fieldseparator must be single char")

def _process(self, input_data=None) -> dict:
    sep = self.config["fieldseparator"]  # already resolved here
    ...
```

**CORRECT -- check moved to `_process` (Phase 07.2 / commit 43762c8):**

```python
def _validate_config(self) -> None:
    """Validate component configuration.

    Note:
        Multi-character fieldseparator validation is intentionally
        deferred to _process() after context variable resolution.
        Validating here would incorrectly measure unresolved context
        references such as ${context.SEP} as multi-character strings.
    """
    if not self.config.get("filepath"):
        raise ConfigurationError(f"[{self.id}] Missing required config 'filepath'")

def _process(self, input_data=None) -> dict:
    sep = self.config.get("fieldseparator", ";")
    if len(sep) != 1:
        raise ConfigurationError(f"[{self.id}] fieldseparator must be single char")
    ...
```

### Cross-references

- `src/v1/engine/base_component.py:204-260` -- Template Method
  lifecycle showing Step 2 vs Step 3 vs Step 7 ordering.
- `src/v1/engine/components/file/file_output_delimited.py:130-145` --
  canonical post-fix `_validate_config` with the docstring note.
- `.planning/phases/07.2-validate-config-bug-sweep-move-pre-resolution-content-checks/`
  -- the sweep that elevated this rule.
- Rule 2 above (which states "validate structural correctness only,
  not resolved values") -- this rule operationalises Rule 2.

---

## Rule 13: Registry Membership AND Abstract Methods (dual invariant)

> **CRITICAL: Both halves of this rule must hold; either alone leaves
> the component silently broken in production.**

Every `BaseComponent` (or `BaseIterateComponent`) subclass MUST honour
the dual invariant:

1. **REGISTRY membership.** The class MUST be decorated with
   `@REGISTRY.register("PascalCaseName", "tTalendName")`. Import
   `REGISTRY` from `src.v1.engine.component_registry`. The decorator
   activates on import, so the module MUST also be imported from its
   package `__init__.py` (otherwise the decorator never runs and the
   class is invisible to the engine).
2. **Abstract method satisfaction.** The class MUST implement
   `_validate_config()` (raise `ConfigurationError` for missing/invalid
   required keys) and `_process()` (return `dict` with at least a
   `'main'` key). `BaseComponent` declares these abstract; Python's ABC
   machinery refuses to instantiate a subclass that omits either.

### Why this is a hard rule, not a guideline

Phase 14 closed **four dual-bug instances** of THIS rule being violated
in already-shipped code:

| Bug ID | Component class | Source path |
|--------|-----------------|-------------|
| BUG-PDC-001 / BUG-PDC-002 | `PythonDataFrameComponent` | `src/v1/engine/components/transform/python_dataframe_component.py` |
| BUG-SWIFT-001 / BUG-SWIFT-002 | `SwiftTransformer`, `SwiftBlockFormatter` | `src/v1/engine/components/transform/swift_transformer.py`, `.../swift_block_formatter.py` |
| BUG-FIJ-001 / BUG-FIJ-002 | `FileInputJSON` | `src/v1/engine/components/file/file_input_json.py` |

Each component had BOTH defects at the same time: missing
`@REGISTRY.register` AND a `_validate_config()` /
`_process()` gap. The components shipped with green unit tests.

### Failure mode at runtime

The engine looks up components via `REGISTRY.get(comp_type)`. An
unregistered class is silently dropped with:

```
WARNING [engine] Unknown component type: <type>
```

The job continues without that component. Downstream components see
an empty DataFrame (or no upstream at all) and either error
mysteriously or produce wrong-but-plausible output. Production data
pipelines have shipped quietly broken because of this.

### Why mock-only tests miss the bug

Tests that instantiate the class directly via a helper such as
`_make_component()` bypass the engine REGISTRY lookup entirely and
thus pass even when `@REGISTRY.register` is missing. This is the
specific failure mode that Phase 14 attributed to the four BUG IDs
above.

### Enforcement at test time

Use the pipeline-test pattern documented in
`docs/v1/patterns/ENGINE_TEST_PATTERN.md` ("Phase 14 Pipeline-Test
Pattern" section). The `tests/conftest.py:run_job_fixture` fixture
runs a fixture JSON through the full engine, exercising the REGISTRY
lookup path. If a class is unregistered, the pipeline test fails
loudly with `Unknown component type: <type>` -- which is the
intended catch.

### Cross-references

- `src/v1/engine/component_registry.py` -- the `REGISTRY` singleton
  and `register(*aliases)` decorator.
- `src/v1/engine/base_component.py` -- declares `_validate_config()`
  and `_process()` as abstract methods.
- `docs/v1/patterns/ENGINE_TEST_PATTERN.md` -- "Phase 14 Pipeline-Test
  Pattern" section; how to author pipeline tests that catch this.
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md`
  -- BUG-PDC-001/002, BUG-SWIFT-001/002, BUG-FIJ-001/002 evidence.

---

## Stats Lifecycle

BaseComponent owns stats. The lifecycle is:

1. `_process()` runs and returns a result dict.
2. If `_process()` called `self._update_stats(rows_read, rows_ok, rows_reject)`, the flag
   `_stats_set_by_component` is set to `True`.
3. `_update_stats_from_result()` runs: if `_stats_set_by_component` is `True`, it is a no-op.
   If `False`, it counts rows from the result dict automatically.

### Double-Count Anti-Pattern

If a component calls `_update_stats()` manually AND the base class also counts from the result,
NB_LINE is doubled. This was the pre-7.1 bug.

```python
# WRONG -- double-count: _update_stats sets the flag,
# but _update_stats_from_result was previously ignoring it
def _process(self, input_data=None) -> dict:
    result_df = _transform(input_data)
    self._update_stats(len(input_data), len(result_df), 0)  # sets flag
    # Old base class bug: _update_stats_from_result ran anyway -> NB_LINE doubled
    return {"main": result_df, "reject": None}
```

Post-7.1 contract: `_update_stats_from_result()` is a strict no-op when
`_stats_set_by_component=True`. Tests that assert double-counted values are wrong and
must be corrected when found.

When to call `_update_stats()` manually:

- When your component has a specific definition of "rows read" that differs from `len(main) + len(reject)`.
- Example: a source component that reads 1000 rows but produces 500 main + 500 reject should
  call `_update_stats(1000, 500, 500)` to record the actual read count.

When NOT to call it:

- When your transform simply passes rows through or filters them. The base class auto-count
  from `len(main) + len(reject)` is correct.

---

## treat_empty_as_null Per-Column Behavior

Schema columns carry a `treat_empty_as_null` attribute (Phase 7.1 D-10). It controls how
empty string `""` values are handled during schema validation.

Default values (if not set in schema):

- `True` for: `int`, `float`, `bool`, `datetime`, `Decimal` columns
- `False` for: `str` columns

Effect:

- `treat_empty_as_null=True`: `""` is coerced to `pd.NA` / `NaN` / `NaT`.
- `treat_empty_as_null=False` (str default): `""` stays as `""`.

Talend parity: Talend reads `""` as `""` for string columns by default, and as null/NaN
for numeric/datetime/Decimal columns. This matches.

Schema example:

```json
{
  "name": "description",
  "type": "str",
  "nullable": true,
  "treat_empty_as_null": false
}
```

Components do not need to implement this -- `validate_schema()` handles it. Do not replicate
this logic in `_process()`.

---

## die_on_error Reject Routing

When `die_on_error=False` is set in the component config (default is `True`), schema
violations route rows to the reject flow instead of raising an exception.

Reject rows receive two extra columns added by the base class:

- `errorCode`: `"SCHEMA_VIOLATION"`
- `errorMessage`: `"Column '<name>': <reason>"`

Violation reasons include:

- `"non-nullable column has null"`
- `"type coercion failed: <value>"`
- `"length exceeded: <actual> > <schema_length>"`

Components MUST NOT add user columns named `errorMessage` or `errorCode`. If such columns
exist on input, the base class renames them to `*_user` with a warning before attaching its
own diagnostic columns.

Components do not need to implement this routing -- the base class handles it in
`_apply_output_schema_validation`. Set `die_on_error` in the job config JSON, not in
component code.

---

## Per-Chunk Streaming

BaseComponent auto-selects execution mode (BATCH / STREAMING / HYBRID) based on data size.
In STREAMING mode, `_process()` is called once per chunk, not once per full DataFrame.

What `_process()` MUST NOT assume:

- That `input_data` contains all rows. In STREAMING mode it is one chunk.
- That it can accumulate state across calls (Rule 10 prohibits this).
- That it can call `_update_stats()` with the total input size -- it only has the chunk.

What the base class handles automatically:

- Chunk splitting and reassembly.
- Stats aggregation across chunks.
- Schema enforcement per chunk.

If your component's algorithm requires the full DataFrame (e.g., SortRow, which must see all
rows to produce a globally sorted result), set the execution mode to BATCH-only by overriding
nothing -- instead, document in the component's docstring that it requires full-DataFrame
processing. The engine will handle mode selection based on the configured threshold.

---

## Java/Groovy Expressions

Expressions containing Java or Groovy logic are marked with `{{java}}` prefix during
conversion (by the converter's `ExpressionConverter`). The engine resolves them before
`_process()` runs, in step 3 of the `execute()` lifecycle.

Timing:

- `_validate_config()`: `{{java}}` markers are NOT yet resolved. Do not validate resolved values.
- `_process()`: all `{{java}}` expressions in `self.config` are fully evaluated.

Components that receive expressions in config values (e.g., filter conditions, field mappings)
do not need to call the Java bridge directly. The base class calls `_resolve_expressions()`
automatically. If a component needs to evaluate a row-level Java expression (not a config
expression), it must use `self.java_bridge` directly and handle `JavaBridgeError`.

GlobalMap and context are synced bidirectionally with the Java bridge after each expression
batch via `_sync_from_java()`. Components do not need to trigger this sync manually.

---

## Talend Parity is Non-Negotiable

From the project's core value statement (CLAUDE.md):

> Any Talend job using the target components must produce identical results when run through
> the Python engine -- feature parity with Talend is non-negotiable.

This means:

- If Talend outputs `""` for a missing string field, the engine must output `""`.
- If Talend silently drops rows with type errors, the engine must do the same (use reject flow).
- If Talend preserves column order from the schema definition, the engine must too.

Before implementing any behavior that differs from Talend's documented behavior, verify
against Talend documentation (<https://help.talend.com>) and add a comment
citing the specific Talend behavior being matched.

---

## Test Patterns

Engine component tests follow the RED-before-GREEN TDD gate. Before implementing a component,
write failing tests. Before merging, all tests must pass.

Required test coverage classes (from `ENGINE_TEST_PATTERN.md`):

| Class | Purpose |
| ----- | ------- |
| `TestRegistration` | Both V1 and Talend alias registered in REGISTRY |
| `TestValidation` | All `_validate_config()` error paths |
| `TestCore*` | Happy-path behavior covering each requirement |
| `TestEdgeCases` | Empty input, None input, stats, boundary conditions |

Stats tests: after calling `_update_stats()` manually in `_process()`, test that
`gm.get_nb_line()` equals the manual value (not double). Post-7.1 contract:
`_update_stats_from_result()` is a no-op when the component sets stats manually.

```python
def test_stats_updated(self):
    gm = GlobalMap()
    comp = _make_component(global_map=gm)
    comp.execute(input_df)
    # Component calls _update_stats(N, N, 0) -- base class does NOT add again
    assert gm.get_nb_line("tMyComponent_1") == N
    assert gm.get_nb_line_ok("tMyComponent_1") == N
```

Real Java bridge tests: if the component evaluates `{{java}}` expressions, add
`@pytest.mark.java` tests that run the actual bridge, not mocks. Mock-only tests gave
false confidence pre-7.1 (see `project_java_bridge_tmap_bug.md` in memory).

---

## PR Checklist

Before opening a pull request for a new or modified engine component:

- [ ] Full engine test suite ran locally: `python -m pytest tests/v1/engine/ -q`
- [ ] Zero new failures (pre-existing failures in out-of-scope files are acceptable)
- [ ] Regression test added for the behavior introduced or changed
- [ ] `grep -r "self.validate_schema" src/v1/engine/components/` returns no hits in new files
- [ ] Component does NOT call `_update_stats()` unless it has a specific reason to override
      the auto-count (document the reason in a comment)
- [ ] No `print()` calls in component code (`grep -n "print(" <file>`)
- [ ] Module-level docstring lists ALL config keys consumed with type and default
- [ ] `_validate_config()` implemented and raises `ConfigurationError` with `self.id`
- [ ] `@REGISTRY.register()` decorator present with both V1 and Talend names
- [ ] New module imported in the package `__init__.py` to activate the decorator
- [ ] If Java tests required: `cd src/v1/java_bridge/java && mvn test -q` passes
