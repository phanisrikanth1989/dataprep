"""Pytest configuration for integration tests.

Provides the ``java_bridge`` fixture used by ``@pytest.mark.java`` integration
tests that invoke the full ETL engine with Java expressions (tMap, tJava, etc.).

The ``java_bridge`` fixture mirrors the session-scoped fixture in
``tests/v1/engine/conftest.py`` but is scoped to integration tests only.
When the JAR is not built, every test that requests this fixture is skipped.
"""
from pathlib import Path

import pytest

_JAR_REL = "src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar"


def _find_java_bridge_jar() -> Path:
    """Resolve the JAR path, accounting for git worktrees."""
    conftest_dir = Path(__file__).resolve().parent
    # Walk up to find the repo root (conftest at tests/integration/conftest.py,
    # so parents[0]=tests/integration, [1]=tests, [2]=repo root).
    repo_root = conftest_dir.parents[1]
    local_jar = repo_root / _JAR_REL
    if local_jar.exists():
        return local_jar

    # Worktree: build artifacts are gitignored; resolve main repo via git.
    import subprocess
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

    return local_jar


@pytest.fixture(scope="session")
def java_bridge():
    """Skip if JAR is not built; otherwise yield the JAR path as a sentinel.

    Integration tests that use this fixture need the Java bridge JAR to be
    present. The ETLEngine starts its own JavaBridgeManager when a job config
    has ``java_config.enabled=True``; this fixture only acts as a gate.

    Build the JAR with:
        cd src/v1/java_bridge/java && mvn package -q
    """
    jar_path = _find_java_bridge_jar()
    if not jar_path.exists():
        pytest.skip(
            f"Java bridge JAR not found at {jar_path}. "
            f"Build with: cd src/v1/java_bridge/java && mvn package -q"
        )

    # In a worktree, ETLEngine resolves the JAR relative to bridge.py's
    # __file__. Build artifacts are gitignored, so the worktree path is empty.
    # Symlink the main-repo JAR into the worktree target dir so the engine finds it.
    from src.v1.java_bridge import bridge as bridge_mod
    bridge_base = Path(bridge_mod.__file__).resolve().parent
    worktree_target_dir = bridge_base / "java" / "target"
    worktree_jar = worktree_target_dir / "java-bridge-with-dependencies.jar"
    symlink_created = False
    if not worktree_jar.exists() and jar_path.exists():
        worktree_target_dir.mkdir(parents=True, exist_ok=True)
        worktree_jar.symlink_to(jar_path)
        symlink_created = True

    try:
        yield jar_path
    finally:
        if symlink_created:
            worktree_jar.unlink(missing_ok=True)
