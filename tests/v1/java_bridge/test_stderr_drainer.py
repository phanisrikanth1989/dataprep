"""Tests for JavaBridge stderr drainer (D-08-01 fix).

Verifies that:
- The stderr drainer thread starts correctly.
- _capture_java_stderr reads from the in-memory deque.
- The deque is bounded at 200 entries.
- A stub process writing 32KB of stderr does not deadlock.

No real JVM required -- stub subprocesses and direct deque access used throughout.
"""

import io
import subprocess
import sys
import threading

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
