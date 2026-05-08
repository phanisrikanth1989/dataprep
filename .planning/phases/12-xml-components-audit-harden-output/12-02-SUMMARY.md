---
phase: 12
plan: 02
slug: xml-io-shared-helper
subsystem: engine/components/file
tags: [xml, infrastructure, secure-parser, streaming, lxml, xxe, memory]
requires: [12-01]
provides: [_xml_io, secure_xml_parser, parse_xml_strategy, iterparse_loop_query, log_strategy, synthetic_60mb_xml]
affects: [12-03, 12-04, 12-05, 12-06, 12-07]
tech_stack:
  added: []
  patterns: [threshold-switched-dom-stream, secure-xmlparser-factory, iterparse-element-clearing]
key_files:
  created:
    - src/v1/engine/components/file/_xml_io.py
    - tests/v1/engine/components/file/test__xml_io.py
    - tests/v1/engine/components/file/conftest.py
    - tests/v1/__init__.py
    - tests/v1/engine/__init__.py
    - tests/v1/engine/components/__init__.py
    - tests/v1/engine/components/file/__init__.py
  modified: []
decisions:
  - "Billion-laughs test asserts output length < 10KB (not XMLSyntaxError): lxml with load_dtd=False suppresses entity expansion silently; entity references are left unexpanded (text=None), no error raised"
  - "tests/v1/ hierarchy created from scratch: worktree branched off main (pre-feature/engine-restructure), so tests/v1/ did not exist yet; created all __init__.py files"
metrics:
  duration_minutes: 5
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 0
  completed_date: "2026-05-08"
---

# Phase 12 Plan 02: Shared XML I/O Helper Module (_xml_io) Summary

Builds `src/v1/engine/components/file/_xml_io.py` -- the secure-parser factory and threshold-switched streaming helpers that Plans 12-03..12-07 all consume. Replaces the deprecated `defusedxml.lxml` pattern (RESEARCH P-1) with the existing repo pattern of `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)`. All 26 tests pass; XXE and billion-laughs negative tests use real XML payloads; streaming-memory test asserts tracemalloc peak < 100 MB on a 60 MB synthetic file.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: _xml_io.py helper module | e3124ab | src/v1/engine/components/file/_xml_io.py |
| Task 2: Tests + conftest fixture | f8e9f8e | tests/v1/ (6 files: __init__.py x4, conftest.py, test__xml_io.py) |

## Public API (4 helpers)

### `secure_xml_parser(*, recover: bool = False) -> etree.XMLParser`

Hardened XMLParser factory. Returns an `etree.XMLParser` with the three secure flags:
- `resolve_entities=False` -- disables XXE external entity resolution
- `no_network=True` -- blocks external URI fetching (DTD, schema, entity refs)
- `load_dtd=False` -- prevents DTD loading (kills billion-laughs expansion vector)
- `recover=False` -- strict mode by default; callers pass `recover=True` for partial-tree recovery

Replaces the deprecated `defusedxml.lxml` per RESEARCH P-1. The pattern was already used by `extract_xml_fields.py:153-159` and `file_input_msxml.py:107-113`; this centralizes it.

### `parse_xml_strategy(filename: str, threshold_mb: int) -> tuple[str, object]`

Threshold-switched parse strategy (D-C2). Uses `os.stat(filename).st_size / (1024 * 1024)` for size measurement.

- Returns `('dom', etree._ElementTree)` when `size_mb < threshold_mb` (full DOM parse with `secure_xml_parser()`)
- Returns `('stream', filename)` when `size_mb >= threshold_mb` (caller invokes `iterparse_loop_query`)
- Propagates `FileNotFoundError`/`OSError` from `os.stat` -- caller decides REJECT vs raise
- Does NOT log; logging is the caller's responsibility via `log_strategy()`

### `iterparse_loop_query(filename: str, loop_tag: str) -> Iterator[etree._Element]`

Memory-correct streaming generator (Pitfall P-3 mitigation).

- Yields each `loop_tag` end-event element via `etree.iterparse`
- Immediately after yield: calls `element.clear(keep_tail=True)` to free subtree
- Walks back via `element.getprevious()` / `del element.getparent()[0]` to release prefix siblings
- Secure flags forwarded as iterparse kwargs (`resolve_entities=False, no_network=True, load_dtd=False, recover=False`) -- lxml iterparse cannot accept an XMLParser instance directly
- Callers must consume child data BEFORE continuing the generator (elements are cleared immediately after yield)

### `log_strategy(component_id: str, strategy: str, size_mb: float, threshold_mb: int) -> None`

ASCII-only INFO log emitter (Pitfall P-4 mitigation). Emits one log record per call:

```
[<component_id>] XML strategy=<dom|stream> size=<N.NN>MB threshold=<M>MB
```

Uses `%`-style deferred formatting. Plan 12-07 E2E tests spy on this line via `caplog` to confirm which branch executed.

## Test Coverage (26 tests)

| Class | Tests | Key Scenarios |
|-------|-------|--------------|
| `TestSecureXmlParser` | 8 | Returns XMLParser instance; recover=False raises on malformed; recover=True does not raise; XXE entity not resolved (real _XXE_DOC payload); billion-laughs output < 10KB (real _BILLION_LAUGHS_DOC payload); DOCTYPE allowed but entities unresolved; load_dtd confirmation; multiple parsers all strict |
| `TestParseXmlStrategy` | 6 | DOM for small file returns `etree._ElementTree`; stream for large (synthetic_60mb_xml) returns filename; threshold=0 always streams (boundary inclusive); missing file propagates OSError; DOM result supports XPath; no log emitted |
| `TestIterparseLoopQuery` | 6 | Yields correct elements; filters by tag only; elements cleared after yield; tracemalloc peak < 100 MB on 60 MB file (P-3 guard); XXE secure flags forwarded; generator is lazy (`types.GeneratorType`) |
| `TestLogStrategy` | 4 | Expected format `[comp_1] XML strategy=dom size=12.34MB threshold=50MB`; ASCII round-trip; exactly one record per call; 'stream' label |
| `TestModuleImport` | 2 | 4 callables present; no `import defusedxml` statement in source |

**Total: 26 tests (all pass)**

No mocks of `lxml.etree` per D-D4. All XML inputs are real strings or files.

## synthetic_60mb_xml Fixture (conftest.py)

Session-scoped pytest fixture in `tests/v1/engine/components/file/conftest.py`.

**Structure:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <item><id>0</id><payload>xxx...xxx (1000 chars)</payload></item>
  <item><id>1</id><payload>xxx...xxx</payload></item>
  ...  (60,000 items total)
</root>
```

**Contract:**
- Size: 55-65 MB (asserted in fixture; ~60 MB actual)
- Item count: 60,000 (`<item>` elements)
- Payload: 1000-char "x" string per item (1 KB per element)
- Scope: `session` -- built once per pytest session, reused across all plans
- Location: `tmp_path_factory.mktemp("xml_streaming")` -- never committed to repo

**Downstream consumption (Plans 12-03..12-07):**
Plans that need streaming-path tests request this fixture by name. Any test file under `tests/v1/engine/components/file/` can use it via pytest fixture autodiscovery (conftest.py in same directory). The fixture exercises `iterparse_loop_query` under realistic memory pressure and validates `parse_xml_strategy` returns `('stream', ...)` for files >= 50 MB.

## How Plans 12-03..12-07 Consume the Helpers

```python
from . import _xml_io  # relative import within same package

# In _process():
size_mb = os.stat(filepath).st_size / (1024 * 1024)
strategy, result = _xml_io.parse_xml_strategy(filepath, threshold_mb=threshold)
_xml_io.log_strategy(self.id, strategy, size_mb, threshold)

if strategy == "dom":
    root = result.getroot()
    # ... XPath / element traversal
else:
    for element in _xml_io.iterparse_loop_query(filepath, loop_tag):
        # ... process element BEFORE the generator clears it
```

No plan needs to re-derive the secure-flag triplet -- they call `secure_xml_parser()` or rely on it being embedded in `parse_xml_strategy` / `iterparse_loop_query`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Billion-laughs test expectation corrected**
- **Found during:** Task 2 test execution
- **Issue:** Test expected `etree.XMLSyntaxError` from billion-laughs payload when `load_dtd=False`. Actual behavior: lxml silently leaves entity references unexpanded (text=None) rather than raising. The attack is neutralized (no expansion) but no error is raised.
- **Fix:** Changed assertion from `pytest.raises(etree.XMLSyntaxError)` to `assert len(serialized) < 10_000` -- confirms no expansion occurred (expanded content would be megabytes)
- **Files modified:** `tests/v1/engine/components/file/test__xml_io.py`
- **Commit:** f8e9f8e

**2. [Rule 3 - Blocking] `test_module_has_no_defusedxml_dependency` over-matched docstring mentions**
- **Found during:** Task 2 test execution
- **Issue:** Original test scanned full source for string "defusedxml" but the module docstring legitimately mentions "defusedxml.lxml" in a historical context comment (explaining what it replaces). The test should only check for import statements.
- **Fix:** Scoped the check to only lines beginning with `import ` or `from `, excluding docstrings and comments
- **Files modified:** `tests/v1/engine/components/file/test__xml_io.py`
- **Commit:** f8e9f8e

**3. [Rule 3 - Blocking] tests/v1/ directory hierarchy absent in worktree**
- **Found during:** Task 2 (pre-test)
- **Issue:** This worktree was branched off from the main branch (commit `464d2f9`) before the `tests/v1/` structure was added on `feature/engine-restructure`. The directory and all its `__init__.py` files did not exist in the worktree.
- **Fix:** Created `tests/v1/__init__.py`, `tests/v1/engine/__init__.py`, `tests/v1/engine/components/__init__.py`, `tests/v1/engine/components/file/__init__.py`
- **Files created:** 4 `__init__.py` files
- **Commit:** f8e9f8e

## Known Stubs

None. All 4 helpers are fully implemented with real behavior.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond those in the plan's threat model. The module handles untrusted XML byte streams at the parse boundary, which is explicitly modeled in the plan's STRIDE register (T-12-01, T-12-02, T-12-04 all mitigated).

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `src/v1/engine/components/file/_xml_io.py` | FOUND |
| `tests/v1/engine/components/file/test__xml_io.py` | FOUND |
| `tests/v1/engine/components/file/conftest.py` | FOUND |
| commit e3124ab (feat 12-02 _xml_io) | FOUND |
| commit f8e9f8e (test 12-02 tests + fixture) | FOUND |
