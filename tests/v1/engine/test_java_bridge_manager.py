"""Tests for JavaBridgeManager (Plan 14-10).

Per project memory `feedback_test_real_bridge` and Phase 14 D-A3:
- The 95% line-coverage gate for `java_bridge_manager.py` is measured WITH
  `@pytest.mark.java` real-bridge tests.
- Mock-only tests are insufficient -- the bridge manages a real JVM lifecycle
  (Py4J subprocess, port retry loop, library validation, routine loading,
  stop idempotency) that mocks alone do not exercise.

JVM 11+ MUST be available in the executing environment. We assert this at
test collection time via shutil.which("java"); tests skip with a clear
message when JVM is absent.

Coverage targets:
- Port retry loop on "Address already in use" (lines 65-78)
- Required-library validation -> RuntimeError (92-99)
- Routine load failures -> JavaBridgeError (102-117)
- stop() idempotency (121-130)
- get_bridge() / is_available() before/after start/stop (132-138)
- _find_free_port (147-151)
- __enter__ / __exit__ context manager (153-161)
- __repr__ (163-166)
"""
from __future__ import annotations

import shutil
from unittest.mock import MagicMock, patch

import pytest

from src.v1.engine.exceptions import JavaBridgeError
from src.v1.engine.java_bridge_manager import JavaBridgeManager


# ---------------------------------------------------------------------------
# JVM availability gate (RESEARCH §Pitfall 5)
# ---------------------------------------------------------------------------


pytestmark = pytest.mark.java


@pytest.fixture(autouse=True)
def _require_java():
    """Skip the entire module when JVM 11+ is not on PATH."""
    if shutil.which("java") is None:
        pytest.skip("JVM 11+ required for -m java tests (java not on PATH)")


# ---------------------------------------------------------------------------
# Disabled-mode short-circuit (line 45-47)
# ---------------------------------------------------------------------------


class TestDisabledMode:
    """When enable=False, start() returns immediately without subprocess."""

    def test_disabled_start_is_noop(self, caplog):
        mgr = JavaBridgeManager(enable=False)
        with caplog.at_level("INFO"):
            mgr.start()
        assert "Java execution disabled" in caplog.text
        assert mgr.is_running is False
        assert mgr.bridge is None


# ---------------------------------------------------------------------------
# Real-bridge basic lifecycle
# ---------------------------------------------------------------------------


class TestRealBridgeStartStop:
    """Real JVM start/stop -- exercises the happy path of start()."""

    def test_start_then_stop(self, caplog):
        mgr = JavaBridgeManager(enable=True)
        with caplog.at_level("INFO"):
            mgr.start()
        assert mgr.is_running is True
        assert mgr.bridge is not None
        assert mgr.port is not None
        # is_available + get_bridge after start
        assert mgr.is_available() is True
        assert mgr.get_bridge() is mgr.bridge

        mgr.stop()
        assert mgr.is_running is False
        assert mgr.bridge is None
        # is_available + get_bridge after stop
        assert mgr.is_available() is False
        assert mgr.get_bridge() is None

    def test_repr_running_and_stopped(self):
        mgr = JavaBridgeManager(enable=True)
        # Before start
        repr_before = repr(mgr)
        assert "stopped" in repr_before
        assert "no port" in repr_before

        mgr.start()
        try:
            repr_running = repr(mgr)
            assert "running" in repr_running
            assert "port=" in repr_running
        finally:
            mgr.stop()


# ---------------------------------------------------------------------------
# Stop idempotency
# ---------------------------------------------------------------------------


class TestStopIdempotency:
    """Calling stop() multiple times is safe (lines 121-130)."""

    def test_stop_twice_no_error(self):
        mgr = JavaBridgeManager(enable=True)
        mgr.start()
        mgr.stop()
        # Second stop is a no-op (is_running=False / bridge=None already)
        mgr.stop()
        assert mgr.is_running is False

    def test_stop_before_start_no_error(self):
        mgr = JavaBridgeManager(enable=True)
        mgr.stop()  # never started; just falls through
        assert mgr.is_running is False
        assert mgr.bridge is None


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    """__enter__ / __exit__ wraps start() / stop() (153-161)."""

    def test_with_block_runs_start_and_stop(self):
        with JavaBridgeManager(enable=True) as mgr:
            assert mgr.is_running is True
            assert mgr.is_available() is True
        # After exit
        assert mgr.is_running is False


# ---------------------------------------------------------------------------
# Library validation
# ---------------------------------------------------------------------------


class TestLibraryValidation:
    """libraries=['nonexistent.jar'] -> RuntimeError (92-99)."""

    def test_missing_library_raises_runtime_error(self):
        mgr = JavaBridgeManager(
            enable=True, libraries=["nonexistent_definitely_not_real.jar"]
        )
        # Validation runs inside start() AFTER bridge starts; raised exception
        # is caught and rewrapped as JavaBridgeError ("Java bridge failed to start")
        with pytest.raises(JavaBridgeError, match="Java bridge failed to start"):
            mgr.start()


# ---------------------------------------------------------------------------
# Routine loading
# ---------------------------------------------------------------------------


class TestRoutineLoadFailures:
    """Mix of valid + invalid routine class names -> JavaBridgeError (102-117)."""

    def test_invalid_routine_raises_java_bridge_error(self):
        mgr = JavaBridgeManager(
            enable=True,
            routines=["routines.NonExistentRoutineClass"],
        )
        with pytest.raises(JavaBridgeError, match="Java bridge failed to start"):
            mgr.start()


# ---------------------------------------------------------------------------
# Port retry loop
# ---------------------------------------------------------------------------


class TestPortRetry:
    """Port retry loop catches 'Address already in use' (lines 65-78).

    We monkeypatch JavaBridge.start to raise the magic substring on the first
    two attempts then succeed -- the retry loop should consume both retries
    and return on attempt 3.
    """

    def test_port_retry_on_address_in_use(self, monkeypatch):
        mgr = JavaBridgeManager(enable=True)

        # Patch the JavaBridge class import to wrap start with a counter
        import src.v1.java_bridge as bridge_pkg
        from src.v1.java_bridge import bridge as bridge_mod

        real_bridge_cls = bridge_mod.JavaBridge
        attempt_counter = {"n": 0}

        class _RetryingJavaBridge(real_bridge_cls):
            def start(self, *a, **kw):
                attempt_counter["n"] += 1
                if attempt_counter["n"] < 3:
                    raise RuntimeError(
                        "Java gateway start failed: Address already in use"
                    )
                return super().start(*a, **kw)

        monkeypatch.setattr(bridge_mod, "JavaBridge", _RetryingJavaBridge)
        monkeypatch.setattr(bridge_pkg, "JavaBridge", _RetryingJavaBridge)
        try:
            mgr.start()
            assert attempt_counter["n"] == 3
            assert mgr.is_running is True
        finally:
            mgr.stop()

    def test_port_retry_exhaustion_raises_java_bridge_error(self, monkeypatch):
        """All 3 attempts hit 'Address already in use' -> JavaBridgeError."""
        mgr = JavaBridgeManager(enable=True)
        import src.v1.java_bridge as bridge_pkg
        from src.v1.java_bridge import bridge as bridge_mod

        real_bridge_cls = bridge_mod.JavaBridge

        class _AlwaysFailingBridge(real_bridge_cls):
            def start(self, *a, **kw):
                raise RuntimeError(
                    "Java gateway start failed: Address already in use"
                )

        monkeypatch.setattr(bridge_mod, "JavaBridge", _AlwaysFailingBridge)
        monkeypatch.setattr(bridge_pkg, "JavaBridge", _AlwaysFailingBridge)
        # The retry loop will exhaust 3 attempts; the final iteration falls
        # through the `raise` (line 78), so caller sees the underlying RuntimeError.
        with pytest.raises(RuntimeError, match="Address already in use"):
            mgr.start()

    def test_non_port_error_raises_immediately(self, monkeypatch):
        """A non-port error (no 'Address already in use' string) re-raises on
        first attempt without retry (line 78 path)."""
        mgr = JavaBridgeManager(enable=True)
        import src.v1.java_bridge as bridge_pkg
        from src.v1.java_bridge import bridge as bridge_mod

        real_bridge_cls = bridge_mod.JavaBridge
        call_counter = {"n": 0}

        class _NonPortErrorBridge(real_bridge_cls):
            def start(self, *a, **kw):
                call_counter["n"] += 1
                raise RuntimeError("Some other unrelated failure")

        monkeypatch.setattr(bridge_mod, "JavaBridge", _NonPortErrorBridge)
        monkeypatch.setattr(bridge_pkg, "JavaBridge", _NonPortErrorBridge)
        with pytest.raises(RuntimeError, match="Some other unrelated"):
            mgr.start()
        # Should have been called exactly once -- no retry on non-port error
        assert call_counter["n"] == 1


# ---------------------------------------------------------------------------
# _find_free_port
# ---------------------------------------------------------------------------


class TestFindFreePort:
    """_find_free_port returns a positive integer in the ephemeral range (147-151)."""

    def test_find_free_port_returns_int(self):
        mgr = JavaBridgeManager(enable=True)
        port = mgr._find_free_port()
        assert isinstance(port, int)
        assert port > 0
        assert port <= 65535


# ---------------------------------------------------------------------------
# Stop-during-retry cleanup (lines 73-74)
# ---------------------------------------------------------------------------


class TestRetryCleanupStopFailure:
    """When the previous bridge.stop() raises during retry cleanup, the
    exception is swallowed so the retry can proceed (lines 70-76)."""

    def test_retry_cleanup_stop_exception_swallowed(self, monkeypatch):
        mgr = JavaBridgeManager(enable=True)
        import src.v1.java_bridge as bridge_pkg
        from src.v1.java_bridge import bridge as bridge_mod

        real_bridge_cls = bridge_mod.JavaBridge
        attempts = {"n": 0}

        class _RetryWithStopBoom(real_bridge_cls):
            def start(self, *a, **kw):
                attempts["n"] += 1
                if attempts["n"] == 1:
                    # First attempt: pretend port collision; bridge object
                    # is now non-None and stop() will be called for cleanup
                    raise RuntimeError(
                        "Java gateway start failed: Address already in use"
                    )
                return super().start(*a, **kw)

            def stop(self):
                if attempts["n"] == 1:
                    # Cleanup-time stop fails -- swallowed by 73-74
                    raise RuntimeError("stop during retry cleanup failed")
                return super().stop()

        monkeypatch.setattr(bridge_mod, "JavaBridge", _RetryWithStopBoom)
        monkeypatch.setattr(bridge_pkg, "JavaBridge", _RetryWithStopBoom)
        try:
            mgr.start()
            assert mgr.is_running is True
        finally:
            mgr.stop()


# ---------------------------------------------------------------------------
# Library validation success path (line 99)
# ---------------------------------------------------------------------------


class TestLibraryValidationSuccess:
    """When validate_libraries returns no missing libraries, the success
    log line is emitted (line 99). We mock validate_libraries to return [].
    """

    def test_libraries_all_available(self, monkeypatch, caplog):
        mgr = JavaBridgeManager(enable=True, libraries=["any.jar"])
        # Patch JavaBridge.validate_libraries on the production class
        import src.v1.java_bridge as bridge_pkg
        from src.v1.java_bridge import bridge as bridge_mod

        real_cls = bridge_mod.JavaBridge

        class _OkValidatingBridge(real_cls):
            def validate_libraries(self, libs):
                return []  # all available

        monkeypatch.setattr(bridge_mod, "JavaBridge", _OkValidatingBridge)
        monkeypatch.setattr(bridge_pkg, "JavaBridge", _OkValidatingBridge)
        try:
            with caplog.at_level("INFO"):
                mgr.start()
            assert "All 1 libraries are available on classpath" in caplog.text
        finally:
            mgr.stop()


# ---------------------------------------------------------------------------
# Routine load success path (line 108)
# ---------------------------------------------------------------------------


class TestRoutineLoadSuccess:
    """When load_routine succeeds, the [OK] Loaded log line fires (line 108)."""

    def test_routine_loaded_logs_ok(self, monkeypatch, caplog):
        mgr = JavaBridgeManager(enable=True, routines=["routines.Fake"])
        import src.v1.java_bridge as bridge_pkg
        from src.v1.java_bridge import bridge as bridge_mod

        real_cls = bridge_mod.JavaBridge

        class _RoutineOkBridge(real_cls):
            def load_routine(self, name):
                return None  # silent success

        monkeypatch.setattr(bridge_mod, "JavaBridge", _RoutineOkBridge)
        monkeypatch.setattr(bridge_pkg, "JavaBridge", _RoutineOkBridge)
        try:
            with caplog.at_level("INFO"):
                mgr.start()
            assert "Loaded: routines.Fake" in caplog.text
        finally:
            mgr.stop()


# ---------------------------------------------------------------------------
# stop() exception logged (lines 125-126)
# ---------------------------------------------------------------------------


class TestStopExceptionLogged:
    """When bridge.stop() raises during stop(), the error is logged but the
    finally clause still resets state (lines 121-130)."""

    def test_stop_exception_logged_state_reset(self, monkeypatch, caplog):
        mgr = JavaBridgeManager(enable=True)
        mgr.start()
        # Make the bridge.stop() raise on the next call
        original_stop = mgr.bridge.stop

        def boom_stop():
            raise RuntimeError("stop failure")

        mgr.bridge.stop = boom_stop
        with caplog.at_level("ERROR"):
            mgr.stop()
        assert "Error stopping Java bridge" in caplog.text
        # State still cleared (the finally block ran)
        assert mgr.is_running is False
        assert mgr.bridge is None
        assert mgr.port is None
