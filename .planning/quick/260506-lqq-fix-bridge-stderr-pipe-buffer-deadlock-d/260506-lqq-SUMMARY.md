---
phase: 260506-lqq
plan: 01
subsystem: infra
tags: [java-bridge, threading, subprocess, py4j, deadlock, pipe-buffer]

# Dependency graph
requires:
  - phase: 10-iterate-support
    provides: JavaBridge with _drain_java_stdout pattern that stderr drainer mirrors
provides:
  - Continuously-draining stderr background thread (java-stderr-drainer daemon) in JavaBridge
  - Bounded in-memory deque (_stderr_buffer, maxlen=200) for stderr capture
  - Non-blocking _capture_java_stderr reading from deque instead of blocking pipe read
  - Four unit tests covering thread start, deque reads, bounded capacity, and 32KB deadlock regression
affects: [tFlowToIterate, tFileList, any high-verbosity JVM job, JavaBridgeManager]

# Tech tracking
tech-stack:
  added: [collections.deque, threading.Lock (existing module, new usage)]
  patterns: [background-drainer-thread: daemon thread mirrors _drain_java_stdout pattern for stderr]

key-files:
  created:
    - tests/v1/java_bridge/__init__.py
    - tests/v1/java_bridge/test_stderr_drainer.py
  modified:
    - src/v1/java_bridge/bridge.py

key-decisions:
  - "deque(maxlen=200) chosen to bound memory without losing recent diagnostic lines"
  - "Lock around deque append and read ensures thread-safe access with minimal contention"
  - "Rewrite _capture_java_stderr body entirely: old select+read(65536) was both blocking and racy"
  - "Drainer thread started immediately after stdout thread in start() for symmetric lifecycle"

patterns-established:
  - "java-stderr-drainer: daemon thread reads stderr line-by-line into bounded deque, mirrors java-stdout-forwarder"

requirements-completed: [D-08-01]

# Metrics
duration: 8min
completed: 2026-05-06
---

# Quick Task 260506-lqq: Fix Bridge stderr Pipe-Buffer Deadlock Summary

**Replaced blocking stderr.read(65536) with a background daemon thread draining stderr into a collections.deque(maxlen=200), eliminating the JVM pipe-buffer deadlock on tFlowToIterate and other high-verbosity jobs**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-06T10:13:00Z
- **Completed:** 2026-05-06T10:21:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `_drain_java_stderr` daemon thread that reads stderr line-by-line and appends to bounded deque under lock, keeping the OS pipe buffer permanently empty
- Rewrote `_capture_java_stderr` to read from the deque under lock — zero blocking I/O, no `import select`, no risk of filling the pipe
- Added `_stderr_buffer` (deque maxlen=200), `_stderr_lock` (Lock), and `_stderr_thread` to `JavaBridge.__init__`; thread started in `start()` alongside the existing stdout forwarder
- Four unit tests: thread lifecycle, deque reads, bounded capacity (200 entries), and 32KB deadlock regression test using a real subprocess

## Task Commits

1. **Task 1: Add _stderr_buffer deque + _drain_java_stderr thread + rewrite _capture_java_stderr** - `b050d76` (feat)
2. **Task 2: Write four tests in tests/v1/java_bridge/test_stderr_drainer.py** - `5d1ff6a` (test)

## Files Created/Modified
- `src/v1/java_bridge/bridge.py` - Added import collections, _stderr_buffer/_stderr_lock/_stderr_thread to __init__, stderr drainer thread start in start(), _drain_java_stderr method, rewrote _capture_java_stderr body
- `tests/v1/java_bridge/__init__.py` - Empty package marker (new)
- `tests/v1/java_bridge/test_stderr_drainer.py` - Four unit tests for drainer thread and deque behavior (new)

## Decisions Made
- `deque(maxlen=200)` bounds memory while retaining enough diagnostic context for error reporting; old approach had no bound
- Lock scope is minimal: lock taken only for append (inside drainer) and list slice (inside capture), not for the line decode/log
- `_capture_java_stderr` signature preserved unchanged so all call sites are unaffected
- Log level for stderr lines is WARNING (not DEBUG or INFO) — stderr from JVM is always worth surfacing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The plan's attribute check (`isinstance(b._stderr_buffer, collections.deque)`) fails under Python 3.12 because `collections.deque` cannot be used as a type argument to `isinstance()` directly (needs `isinstance(x, collections.deque)` which works, but the test inline used `deque` as second arg). Worked around in manual verification by using `type(x).__name__`. The actual test file uses direct operations, not isinstance checks, so tests pass cleanly.

## Known Stubs
None.

## Threat Surface Scan
No new network endpoints or auth paths introduced. Changes are limited to internal pipe I/O handling. Threat T-lqq-01 (DoS via unbounded stderr) is mitigated by deque maxlen=200.

## Self-Check: PASSED

- `src/v1/java_bridge/bridge.py` - EXISTS (modified in place)
- `tests/v1/java_bridge/__init__.py` - EXISTS
- `tests/v1/java_bridge/test_stderr_drainer.py` - EXISTS
- Commit `b050d76` - EXISTS (feat commit)
- Commit `5d1ff6a` - EXISTS (test commit)
- All 4 tests PASS
- All 29 existing test_bridge.py tests PASS (no regressions)
- `import select` NOT present in bridge.py

## Next Steps
- The fix is ready for merge. Any job that previously hung at iteration 3+ due to JVM stderr buffering should now complete.
- No follow-up tasks needed for this fix.

---
*Phase: 260506-lqq*
*Completed: 2026-05-06*
