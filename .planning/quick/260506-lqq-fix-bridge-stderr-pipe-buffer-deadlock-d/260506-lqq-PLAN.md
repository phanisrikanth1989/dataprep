---
phase: 260506-lqq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/v1/java_bridge/bridge.py
files_created:
  - tests/v1/java_bridge/__init__.py
  - tests/v1/java_bridge/test_stderr_drainer.py
autonomous: true
requirements:
  - D-08-01
must_haves:
  truths:
    - "JVM stderr is continuously drained by a background thread — the OS pipe buffer never fills"
    - "_capture_java_stderr returns the last 20 lines from the in-memory deque, not from a blocking read"
    - "The stderr drainer thread is a daemon thread named 'java-stderr-drainer' started alongside the stdout forwarder"
    - "The deque holds at most 200 lines regardless of how much stderr the JVM emits"
    - "No deadlock occurs when the JVM writes 32KB+ of stderr without an explicit reader"
  artifacts:
    - path: "src/v1/java_bridge/bridge.py"
      provides: "_drain_java_stderr method + _stderr_buffer deque + _stderr_lock"
      contains: "_stderr_buffer"
    - path: "tests/v1/java_bridge/test_stderr_drainer.py"
      provides: "Four focused tests covering thread start, deque reads, bounded deque, and deadlock regression"
      exports: []
  key_links:
    - from: "JavaBridge.__init__"
      to: "self._stderr_buffer / self._stderr_lock"
      via: "collections.deque(maxlen=200) + threading.Lock()"
      pattern: "_stderr_buffer"
    - from: "JavaBridge.start"
      to: "_drain_java_stderr thread"
      via: "threading.Thread(...).start() immediately after stdout thread"
      pattern: "java-stderr-drainer"
    - from: "JavaBridge._capture_java_stderr"
      to: "self._stderr_buffer"
      via: "deque slice under self._stderr_lock"
      pattern: "_stderr_lock"
---

<objective>
Fix the JVM stderr pipe-buffer deadlock in the Java bridge by replacing the blocking
`process.stderr.read(65536)` pattern with a continuously-draining background thread
that stores stderr lines in a bounded in-memory deque.

Purpose: On Windows the OS stderr pipe buffer is 4-8KB; on macOS/Linux it is 64KB.
When the JVM writes more stderr than the buffer holds (common during tFlowToIterate
jobs at iteration 3+), it blocks on the next write. Because nothing drains the buffer
until an error is detected, Py4J calls freeze. The fix mirrors the existing
`_drain_java_stdout` pattern: a daemon thread drains stderr continuously so the buffer
never fills.

Output: Modified `src/v1/java_bridge/bridge.py` + new test file
`tests/v1/java_bridge/test_stderr_drainer.py` with four tests.
</objective>

<execution_context>
@/Users/aarun/Workspace/Projects/dataprep/.claude/get-shit-done/workflows/execute-plan.md
@/Users/aarun/Workspace/Projects/dataprep/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/aarun/Workspace/Projects/dataprep/.planning/STATE.md
@/Users/aarun/Workspace/Projects/dataprep/src/v1/java_bridge/bridge.py

<interfaces>
<!-- Key signatures in bridge.py the executor must match. -->

Current __init__ attributes (lines 81-87):
```python
self.gateway: Optional[JavaGateway] = None
self.java_bridge: Any = None
self.process: Optional[subprocess.Popen] = None
self.context: dict[str, Any] = {}
self.global_map: dict[str, Any] = {}
self._started: bool = False
self._stdout_thread: Optional[threading.Thread] = None
```

Popen call (lines 148-163) — stdout drainer starts here; stderr drainer goes immediately after:
```python
self.process = subprocess.Popen(cmd, cwd=java_dir, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=False)
self._stdout_thread = threading.Thread(
    target=self._drain_java_stdout, daemon=True, name="java-stdout-forwarder")
self._stdout_thread.start()
# << INSERT stderr drainer thread here >>
```

Existing _drain_java_stdout (lines 976-992) — mirror this for stderr:
```python
def _drain_java_stdout(self) -> None:
    if not self.process or not self.process.stdout:
        return
    try:
        for raw_line in self.process.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line:
                logger.info("[Java] %s", line)
    except Exception:
        pass
```

Existing _capture_java_stderr (lines 994-1021) — replace body, keep signature:
```python
def _capture_java_stderr(self) -> str:
    """Non-blocking read of available Java stderr output.
    Returns the last 20 lines for error diagnostics."""
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add _stderr_buffer deque + _drain_java_stderr thread + rewrite _capture_java_stderr</name>
  <files>src/v1/java_bridge/bridge.py</files>
  <action>
Make four targeted changes to bridge.py:

**1. Add `import collections` to the top-level imports** (alongside existing `import threading`).

**2. In `JavaBridge.__init__` (after the `self._stdout_thread` declaration, ~line 87)**, add:
```python
self._stderr_buffer: collections.deque[str] = collections.deque(maxlen=200)
self._stderr_lock: threading.Lock = threading.Lock()
self._stderr_thread: Optional[threading.Thread] = None
```

**3. In `JavaBridge.start`, immediately after `self._stdout_thread.start()` (~line 163)**, add:
```python
self._stderr_thread = threading.Thread(
    target=self._drain_java_stderr,
    daemon=True,
    name="java-stderr-drainer",
)
self._stderr_thread.start()
```

**4. Add `_drain_java_stderr` method** directly after `_drain_java_stdout` (~line 993):
```python
def _drain_java_stderr(self) -> None:
    """Background thread: read JVM stderr line-by-line into bounded deque.

    Runs until the JVM process exits.  Keeps the OS pipe buffer empty so
    the JVM never blocks on a stderr write (prevents pipe-buffer deadlock
    on tFlowToIterate and other high-verbosity jobs).

    Each non-empty line is appended to ``self._stderr_buffer`` (capped at
    200 lines) and logged at WARNING level for visibility.
    """
    if not self.process or not self.process.stderr:
        return
    try:
        for raw_line in self.process.stderr:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line:
                with self._stderr_lock:
                    self._stderr_buffer.append(line)
                logger.warning("[Java stderr] %s", line)
    except Exception:
        pass
```

**5. Rewrite `_capture_java_stderr`** (replace the entire body, keep the method signature and docstring):
```python
def _capture_java_stderr(self) -> str:
    """Return the last 20 lines of JVM stderr captured by the drainer thread.

    The stderr pipe is continuously drained by ``_drain_java_stderr``; this
    method reads from the in-memory deque so it never blocks.

    Returns:
        String of up to 20 most-recent stderr lines, or empty string.
    """
    with self._stderr_lock:
        lines = list(self._stderr_buffer)[-20:]
    return "\n".join(lines)
```

Remove the `import select` inside the old `_capture_java_stderr` body (it was a local import — it disappears automatically when the body is replaced).

Do NOT change any call sites of `_capture_java_stderr` — callers are unaffected.
ASCII-only strings in all log calls (no emojis/unicode).
  </action>
  <verify>
    <automated>cd /Users/aarun/Workspace/Projects/dataprep && python -c "
import collections, threading
from src.v1.java_bridge.bridge import JavaBridge
b = JavaBridge()
assert isinstance(b._stderr_buffer, collections.deque), 'missing _stderr_buffer'
assert b._stderr_buffer.maxlen == 200, 'wrong maxlen'
assert isinstance(b._stderr_lock, threading.Lock), 'missing _stderr_lock'
assert hasattr(b, '_drain_java_stderr'), 'missing _drain_java_stderr'
print('Task 1 attribute checks: PASS')
"
    </automated>
  </verify>
  <done>
    - `self._stderr_buffer` is a `collections.deque(maxlen=200)` on every new `JavaBridge()` instance
    - `self._stderr_lock` is a `threading.Lock` on every new instance
    - `_drain_java_stderr` method exists, is a daemon thread named "java-stderr-drainer" when started
    - `_capture_java_stderr` reads from the deque under the lock, returns `"\n".join(lines[-20:])`
    - No `import select` remains inside `_capture_java_stderr`
    - All log strings are ASCII-only
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write four tests in tests/v1/java_bridge/test_stderr_drainer.py</name>
  <files>
    tests/v1/java_bridge/__init__.py
    tests/v1/java_bridge/test_stderr_drainer.py
  </files>
  <behavior>
    - test_drainer_thread_starts: after bridge._stderr_thread is manually started with a stub process whose stderr is an io.BytesIO, the thread is alive (or was alive) and named "java-stderr-drainer"
    - test_capture_returns_recent_lines: push 5 lines directly into bridge._stderr_buffer, call _capture_java_stderr, confirm the 5 lines appear in the result
    - test_deque_bounded_at_200: push 500 strings directly into bridge._stderr_buffer, confirm len(bridge._stderr_buffer) == 200 and the last entry equals the 500th item
    - test_stderr_does_not_deadlock_under_load: launch a stub subprocess that writes 32KB of stderr (320 lines x 100 bytes), wait up to 5 seconds for the drainer thread to drain it, assert the thread exits cleanly without hanging — this proves the OS pipe buffer is never full
  </behavior>
  <action>
Create `tests/v1/java_bridge/__init__.py` as an empty file (marks it as a package).

Create `tests/v1/java_bridge/test_stderr_drainer.py` with these four tests. Use `@pytest.mark.unit` on all tests. No real JVM required — use `subprocess.Popen` with a Python one-liner as the stub process for the deadlock test.

```python
"""Tests for JavaBridge stderr drainer (D-08-01 fix).

Verifies that:
- The stderr drainer thread starts correctly.
- _capture_java_stderr reads from the in-memory deque.
- The deque is bounded at 200 entries.
- A stub process writing 32KB of stderr does not deadlock.

No real JVM required -- stub subprocesses and direct deque access used throughout.
"""

import collections
import io
import sys
import threading
import time

import pytest

from src.v1.java_bridge.bridge import JavaBridge


@pytest.mark.unit
class TestStderrDrainer:
    """Verify the JavaBridge stderr drainer thread and deque behavior."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_bridge_with_stub_stderr(stderr_bytes: bytes) -> JavaBridge:
        """Return a JavaBridge with process.stderr backed by a BytesIO stub."""
        bridge = JavaBridge()
        mock_proc = type("FakeProc", (), {})()
        mock_proc.stderr = io.BytesIO(stderr_bytes)
        mock_proc.stdout = io.BytesIO(b"")
        bridge.process = mock_proc
        return bridge

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_drainer_thread_starts(self):
        """Drainer thread is a daemon named 'java-stderr-drainer'."""
        stderr_data = b"line one\nline two\n"
        bridge = self._make_bridge_with_stub_stderr(stderr_data)

        t = threading.Thread(
            target=bridge._drain_java_stderr,
            daemon=True,
            name="java-stderr-drainer",
        )
        bridge._stderr_thread = t
        t.start()
        t.join(timeout=2)

        assert t.name == "java-stderr-drainer"
        assert t.daemon is True
        # Thread should have finished (BytesIO is finite)
        assert not t.is_alive()

    def test_capture_returns_recent_lines(self):
        """_capture_java_stderr returns lines from the deque."""
        bridge = JavaBridge()
        test_lines = ["alpha", "beta", "gamma", "delta", "epsilon"]
        with bridge._stderr_lock:
            bridge._stderr_buffer.extend(test_lines)

        result = bridge._capture_java_stderr()

        for line in test_lines:
            assert line in result

    def test_deque_bounded_at_200(self):
        """Deque retains only the last 200 entries when overfilled."""
        bridge = JavaBridge()
        for i in range(500):
            bridge._stderr_buffer.append(f"line-{i}")

        assert len(bridge._stderr_buffer) == 200
        # Last entry is line-499 (the 500th item, 0-indexed)
        assert bridge._stderr_buffer[-1] == "line-499"

    def test_stderr_does_not_deadlock_under_load(self):
        """Drainer keeps the OS pipe buffer empty so JVM never blocks.

        Launches a real Python subprocess that writes 32KB to stderr (320 lines
        of 100 bytes each).  The drainer thread must drain all output within
        5 seconds -- if it deadlocks, the join() timeout fires and the assert
        fails, proving the fix is needed/working.
        """
        # 320 lines * (100 chars + newline) = ~32 KB
        write_script = (
            "import sys\n"
            "for _ in range(320):\n"
            "    sys.stderr.write('X' * 100 + '\\n')\n"
            "sys.stderr.flush()\n"
        )
        import subprocess
        proc = subprocess.Popen(
            [sys.executable, "-c", write_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )

        bridge = JavaBridge()
        bridge.process = proc

        drainer = threading.Thread(
            target=bridge._drain_java_stderr,
            daemon=True,
            name="java-stderr-drainer",
        )
        drainer.start()

        # The subprocess should complete quickly once stderr is drained
        proc.wait(timeout=10)
        drainer.join(timeout=5)

        assert not drainer.is_alive(), (
            "Drainer thread is still alive -- stderr pipe may be blocked (deadlock!)"
        )
        # Deque should have captured the lines
        assert len(bridge._stderr_buffer) > 0
```
  </action>
  <verify>
    <automated>cd /Users/aarun/Workspace/Projects/dataprep && python -m pytest tests/v1/java_bridge/test_stderr_drainer.py -v --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - `tests/v1/java_bridge/__init__.py` exists (empty)
    - `tests/v1/java_bridge/test_stderr_drainer.py` exists with four `@pytest.mark.unit` tests
    - All four tests pass: `test_drainer_thread_starts`, `test_capture_returns_recent_lines`, `test_deque_bounded_at_200`, `test_stderr_does_not_deadlock_under_load`
    - No test uses a real JVM (BytesIO and Python subprocess stubs only)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| JVM process -> Python | Untrusted text arrives on stderr pipe; decoded with errors="replace" |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-lqq-01 | Denial of Service | _drain_java_stderr | mitigate | deque maxlen=200 bounds memory; logging at WARNING prevents log flooding from swamping disk |
| T-lqq-02 | Information Disclosure | _stderr_buffer | accept | stderr is internal JVM diagnostic output; deque holds last 200 lines only, not sensitive data |
</threat_model>

<verification>
```bash
# 1. Attribute presence
cd /Users/aarun/Workspace/Projects/dataprep && python -c "
import collections, threading
from src.v1.java_bridge.bridge import JavaBridge
b = JavaBridge()
assert isinstance(b._stderr_buffer, collections.deque)
assert b._stderr_buffer.maxlen == 200
assert isinstance(b._stderr_lock, threading.Lock)
print('Attribute checks: PASS')
"

# 2. Unit tests
cd /Users/aarun/Workspace/Projects/dataprep && python -m pytest tests/v1/java_bridge/test_stderr_drainer.py -v

# 3. Confirm no import select remains in _capture_java_stderr
grep -n "import select" src/v1/java_bridge/bridge.py && echo "FAIL: select still present" || echo "PASS: select removed"

# 4. Confirm ASCII-only log strings
grep -n "Java stderr" src/v1/java_bridge/bridge.py
```
</verification>

<success_criteria>
- `JavaBridge()` has `_stderr_buffer` (deque, maxlen=200), `_stderr_lock` (Lock), `_stderr_thread` (None at init)
- `_drain_java_stderr` method exists; when started it reads stderr line-by-line, appends to deque under lock, logs WARNING `[Java stderr] <line>`
- Thread is daemon=True, name="java-stderr-drainer", started immediately after stdout thread in `start()`
- `_capture_java_stderr` reads deque under lock, returns `"\n".join(last_20_lines)`, no blocking I/O
- No `import select` inside `_capture_java_stderr`
- All four tests in `test_stderr_drainer.py` pass, including the 32KB deadlock regression test
- Existing bridge tests (`tests/v1/engine/test_bridge.py`) still pass (no regressions)
</success_criteria>

<output>
After completion, create `.planning/quick/260506-lqq-fix-bridge-stderr-pipe-buffer-deadlock-d/260506-lqq-SUMMARY.md`
using the summary template at `/Users/aarun/Workspace/Projects/dataprep/.claude/get-shit-done/templates/summary.md`.
</output>
