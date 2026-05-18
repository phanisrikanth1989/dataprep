"""Pytest configuration for java_bridge unit/integration tests.

Provides the session-scoped ``java_bridge`` fixture used by
``@pytest.mark.java`` tests that need a real running JVM subprocess.

Mirrors ``tests/v1/engine/conftest.py``'s ``java_bridge`` fixture so that
tests under ``tests/v1/java_bridge/`` can use the same fixture contract
without depending on a sibling conftest directory.
"""
import subprocess
from pathlib import Path

import pytest

_JAR_REL = Path("src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar")


def _find_java_bridge_jar() -> Path:
    """Locate the Java bridge JAR, supporting worktree layouts.

    Mirrors ``tests/v1/engine/conftest.py::_find_java_bridge_jar`` exactly.
    """
    conftest_dir = Path(__file__).resolve().parent
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(conftest_dir),
            text=True,
        ).strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (conftest_dir / common_path).resolve()
        else:
            common_path = common_path.resolve()
        main_repo = common_path.parent
        main_jar = main_repo / _JAR_REL
        if main_jar.exists():
            return main_jar
    except Exception:
        pass
    # conftest.py is at tests/v1/java_bridge/conftest.py, so parents[3] is the
    # repo root (parents[0]=tests/v1/java_bridge, [1]=tests/v1, [2]=tests, [3]=repo).
    return Path(__file__).resolve().parents[3] / _JAR_REL


@pytest.fixture(scope="session")
def java_bridge():
    """Start one real ``JavaBridge`` for the entire test session.

    Used by every ``@pytest.mark.java`` integration test in the java_bridge
    test suite. When the JAR is not built, every test requesting this fixture
    is skipped.

    Per project memory ``feedback_test_real_bridge``: tests that exercise the
    Java bridge MUST use a real JVM -- mock-only tests gave false confidence.
    """
    jar_path = _find_java_bridge_jar()
    if not jar_path.exists():
        pytest.skip(
            f"Java bridge JAR not found at {jar_path}. "
            f"Build with: cd src/v1/java_bridge/java && mvn package -q"
        )

    # In a worktree, ``JavaBridge._find_jar_path`` resolves relative to its
    # own ``__file__``. Build artifacts are gitignored, so the worktree path
    # is empty. Symlink the main-repo JAR into the worktree target dir.
    from src.v1.java_bridge import bridge as bridge_mod
    bridge_base = Path(bridge_mod.__file__).resolve().parent
    worktree_target_dir = bridge_base / "java" / "target"
    worktree_jar = worktree_target_dir / "java-bridge-with-dependencies.jar"
    symlink_created = False
    if not worktree_jar.exists() and jar_path.exists():
        worktree_target_dir.mkdir(parents=True, exist_ok=True)
        worktree_jar.symlink_to(jar_path)
        symlink_created = True

    from src.v1.engine.java_bridge_manager import JavaBridgeManager
    manager = JavaBridgeManager()
    try:
        manager.start()
    except Exception as exc:
        if symlink_created:
            worktree_jar.unlink(missing_ok=True)
        pytest.skip(f"Java bridge failed to start: {exc}")
    try:
        yield manager.bridge
    finally:
        manager.stop()
        if symlink_created:
            worktree_jar.unlink(missing_ok=True)
