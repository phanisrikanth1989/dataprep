# Phase 14 -- Plan-Check / Execution Notes

> Recorded during execution. Each entry is dated and tagged with the plan + task that surfaced it.

---

## 14-01-005 (smoke: serial vs xdist coverage equivalence) -- 2026-05-10

**Result: SMOKE OK -- no drift.**

Measurement: `tests/v1/engine/test_executor.py --cov=src/v1/engine`

| Mode | percent_covered for src/v1/engine/executor.py |
|------|----------------------------------------------:|
| Serial | 59.58% |
| `-n auto` (10 workers) | 59.58% |
| Delta | 0.00% |

Conclusion: pytest-xdist 3.8.0 + pytest-cov 7.0.0 combine cleanly on this codebase
under `-n auto`. The Phase 14 gate command's parallel mode is safe for coverage
measurement. The `[tool.coverage.run] parallel = true` setting in pyproject.toml is
a defense-in-depth choice; pytest-cov's combine step works the same with or without
that flag for the project layout.

No fix required.

---

## 14-01-006 (gate command on current tree) -- 2026-05-10

**Result: gate command runs to completion; per-module floor script reports 52
modules below 95% (Phase 13 baseline expected ~53; the off-by-one is the
`__init__.py` omit pattern, not a regression).**

Pre-existing test infrastructure noise surfaced by `-n auto` on the FULL suite
(not present in Phase 13's serial baseline run):

1. **`tests/v1/engine/test_bridge_integration.py::TestTMapCompiledExpressions`** --
   4 of 4 tests in this class FAIL when the full suite runs under `-n auto -p 10
   workers`, but PASS when the same class runs in isolation under `-n auto`. Root
   cause is JVM-resource contention under high parallelism (Java bridge subprocess
   per-worker collision). This is pre-existing under the new gate-command shape;
   Phase 13 measured serially so the issue was masked.
   - **Disposition:** Surface to a future Phase 14-11 (engine core) plan, which
     touches `java_bridge_manager.py`. Plan 14-11 must either:
       (a) Mark these tests `@pytest.mark.serial` (custom marker, not yet defined)
           and exclude them from `-n auto` via xdist `--dist=loadgroup` or
           `--dist=no` for the marker, OR
       (b) Stabilize the bridge-fixture lifecycle so per-worker JVMs do not
           collide on Py4J ports.
   - **Plan-check stance:** NOT a Plan 14-01 blocker. Plan 14-01 ships
     infrastructure; the failures are a pre-existing issue in the test layout
     amplified by the new parallel gate.
   - **RESOLUTION (2026-05-11, Plan 14-10 BUG-JVM-001 / commit `bb2a81d`):**
     Applied option (b). The module-scoped `bridge` fixture in
     `tests/v1/engine/test_bridge_integration.py` was using `JavaBridge()` with
     the default port=25333. Each xdist worker created its own fixture instance
     and competed for the same port; only the first worker bound successfully.
     Fix: switched the fixture to `JavaBridgeManager(enable=True)` which calls
     `socket.bind(('', 0))` to allocate a free port per invocation. Each worker
     now gets a unique port. Verified by running
     `python -m pytest tests/v1/engine/test_bridge_integration.py -m java -n auto`
     with 10 workers -- all 31 tests pass under parallel collection. No new
     marker required; existing `-m "not oracle"` gate command stays clean.

2. **`tests/converters/talend_to_v1/test_integration.py`** -- ImportError on
   collection: `ModuleNotFoundError: No module named 'src.converters.complex_converter'`.
   The complex_converter directory is not present in the working tree (project's
   "legacy converter" -- see ROADMAP "leave legacy complex_converter" decision in
   PROJECT.md). This file has been broken since at least commit `90d56be` and
   was not surfaced because Phase 13 ran with `-q` and the error landed at
   collection, not as a recorded test failure.
   - **Disposition:** Either (a) delete `tests/converters/talend_to_v1/test_integration.py`
     as STALE (legacy import; no value), or (b) guard the import behind
     `pytest.importorskip("src.converters.complex_converter")`. Defer to Plan
     14-12 (converter-core lift) which already touches `converter.py` and
     `expression_converter.py`.
   - **Plan-check stance:** NOT a Plan 14-01 blocker.

**Per-module floor script output:** 52 modules below 95.0%. Top failures match
the Phase 13 baseline (`13-COVERAGE-BASELINE.md`):

```
   6.8%  src/v1/engine/components/transform/swift_block_formatter.py
   7.3%  src/v1/engine/components/transform/swift_transformer.py
   9.3%  src/v1/engine/components/file/file_input_json.py
  15.0%  src/v1/engine/components/file/file_input_raw.py
  19.6%  src/v1/engine/components/transform/python_dataframe_component.py
  28.7%  src/v1/engine/components/file/file_input_excel.py
  59.4%  src/v1/engine/java_bridge_manager.py
  60.2%  src/v1/engine/components/control/send_mail.py
  ... (44 more rows; full list elided)
```

Infrastructure verified: gate command pipeline (pytest -> coverage.json ->
check_per_module_coverage.py) operates as designed.

---

## .gitignore update -- 2026-05-10 (incidental to 14-01-006)

The Phase 14 gate command produces three artifacts that must NOT be committed:

- `coverage.json` -- already covered by the project-wide `*.json` rule.
- `htmlcov/` -- not previously ignored. ADDED.
- `.coverage` (and any `.coverage.<worker>` parallel files) -- not previously
  ignored. ADDED.

`.gitignore` now has a "Coverage artifacts" section. `git status --ignored` after
a gate run confirms all three are ignored.
