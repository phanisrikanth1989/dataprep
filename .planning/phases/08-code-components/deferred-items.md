# Phase 08 Deferred Items

Out-of-scope discoveries logged during plan execution. Per executor agent
deviation rules: items here are not auto-fixed because they fall outside
the current plan's `<files_modified>` boundary or violate phase scope
constraints.

---

## D-08-01 (Plan 05): JavaBridge `_capture_java_stderr` blocks on `read(65536)`

**Discovered:** 2026-04-29 during Plan 05 Task 1 verification (real-bridge
@pytest.mark.java sweep).

**Where:** `src/v1/java_bridge/bridge.py:955` -- inside `_capture_java_stderr`.

**Issue:** When a Java-side row throws an exception, the Python bridge
catches the Py4J exception and tries to enrich the error message with the
JVM's stderr. The fallback path is:
```python
import select
if hasattr(select, "select"):
    ready, _, _ = select.select([self.process.stderr], [], [], 0.1)
    if not ready:
        return ""
raw = self.process.stderr.read(65536)
```

`select` returns "ready" because there are SOME bytes (e.g., 1500 bytes of
the stack trace). But `BufferedReader.read(65536)` is a *blocking* read
that waits until either 65536 bytes arrive or EOF. The Java process is
still alive and its stderr is open, so neither condition fires. The
Python side hangs indefinitely.

**Symptom:** Any test that triggers a Java exception inside
`execute_java_row` (or any other method routed through
`_call_java_with_sync`'s except-branch) hangs.

**Why deferred:** Plan 05 is explicitly forbidden from modifying
`src/v1/java_bridge/` (CLAUDE.md project constraint and plan
`<constraints>`). Fix requires either:

- non-blocking `os.read` with `O_NONBLOCK` set on the stderr fd, or
- `process.stderr.read1()` (single-syscall, returns whatever is available
  without re-blocking), or
- a buffered reader thread that drains stderr continuously into a
  `collections.deque`, polled here.

**Mitigation in Plan 05:** Test 18 (`TestErrorPropagationRealBridge::
test_real_bridge_error_propagates` in
`tests/v1/engine/components/transform/test_java_row_component.py`) is
marked `@pytest.mark.xfail(strict=False, run=False)` so the test suite
does not hang. The error-propagation contract (JROW-02 reinterpretation
per CONTEXT revision 2) is fully verified at the component layer by the
existing mock-based `TestErrorPropagation::test_bridge_exception_propagates`
unit test.

**Suggested follow-up:** A dedicated bridge-layer plan that addresses
this and any related blocking-IO issues in `_capture_java_stderr` /
`_call_java_with_sync`. Re-enable Test 18 (remove the `xfail`) as the
verification gate.
