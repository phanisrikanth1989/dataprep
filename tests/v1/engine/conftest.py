"""Pytest configuration for v1 engine tests.

Provides StubComponent and helper functions for Phase 3 execution tests.
StubComponent enables testing execution orchestration without real component
implementations (per D-17).

Also provides a session-scoped ``java_bridge`` fixture used by every
``@pytest.mark.java`` integration test that needs a real running JVM
subprocess (Phase 8 Plan 05 / TEST-07). Per project memory
``feedback_test_real_bridge``, code-component tests for tJava / tJavaRow
MUST exercise a real bridge -- mock-only is FORBIDDEN.
"""
import subprocess
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import pytest

from src.v1.engine.base_component import BaseComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


class StubComponent(BaseComponent):
    """Configurable test stub for BaseComponent.

    Allows tests to control output data, reject data, and failure behavior
    without depending on real component implementations.

    Config keys:
        output_data (list[dict]): Rows to return as main DataFrame.
        reject_data (list[dict]): Rows to return as reject DataFrame.
        should_fail (bool): If True, _process raises ComponentExecutionError.
        fail_message (str): Custom failure message (default: 'StubComponent failure').
    """

    def _validate_config(self) -> None:
        """No-op validation -- StubComponent accepts any config."""
        pass

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Return configurable output based on config keys.

        Args:
            input_data: Input DataFrame or None.

        Returns:
            dict with 'main' key and optionally 'reject' key.

        Raises:
            ComponentExecutionError: If config['should_fail'] is True.
        """
        if self.config.get("should_fail", False):
            raise ComponentExecutionError(
                self.id, self.config.get("fail_message", "StubComponent failure")
            )

        result: dict[str, Any] = {}

        # Main output
        output_data = self.config.get("output_data")
        if output_data is not None:
            result["main"] = pd.DataFrame(output_data)
        elif input_data is not None:
            result["main"] = input_data
        else:
            result["main"] = pd.DataFrame()

        # Reject output
        reject_data = self.config.get("reject_data")
        if reject_data is not None:
            result["reject"] = pd.DataFrame(reject_data)

        return result


def make_stub_component(
    comp_id: str,
    config: Optional[dict] = None,
    global_map: Optional[GlobalMap] = None,
    context_manager: Optional[ContextManager] = None,
) -> StubComponent:
    """Create a StubComponent with sensible defaults.

    Args:
        comp_id: Component identifier.
        config: Component configuration dict. Defaults to empty dict.
        global_map: GlobalMap instance. Defaults to fresh GlobalMap().
        context_manager: ContextManager instance. Defaults to fresh ContextManager
            with empty context.

    Returns:
        Configured StubComponent instance ready for testing.
    """
    if config is None:
        config = {}
    if global_map is None:
        global_map = GlobalMap()
    if context_manager is None:
        context_manager = ContextManager(initial_context={"Default": {}})
    comp = StubComponent(comp_id, config, global_map, context_manager)
    # Populate self.config so _process() works when called directly in tests.
    # Normally execute() does this via deepcopy of _original_config.
    import copy
    comp.config = copy.deepcopy(comp._original_config)
    return comp


def make_job_config(
    components: list[dict],
    flows: Optional[list[dict]] = None,
    triggers: Optional[list[dict]] = None,
    subjobs: Optional[list[dict]] = None,
) -> dict:
    """Build a valid job config dict for testing.

    Args:
        components: List of component config dicts. Each must have at least
            'id' and 'component_type'.
        flows: List of flow dicts. Defaults to empty list.
        triggers: List of trigger dicts. Defaults to empty list.
        subjobs: List of subjob dicts. Defaults to empty list.

    Returns:
        Job config dict matching the engine's expected format.
    """
    return {
        "job": {
            "name": "test_job",
            "version": "1.0",
        },
        "components": components,
        "flows": flows or [],
        "triggers": triggers or [],
        "subjobs": subjobs or [],
        "context": {"Default": {}},
    }



@pytest.fixture
def stub_component_factory():
    """Fixture providing make_stub_component as a callable factory.

    Usage in tests::

        def test_something(self, stub_component_factory):
            comp = stub_component_factory("comp1", config={...})
    """
    return make_stub_component


# ------------------------------------------------------------------
# Session-scoped real Java bridge fixture (Phase 8 Plan 05 / TEST-07)
# ------------------------------------------------------------------


_JAR_REL = Path("src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar")


def _find_java_bridge_jar() -> Path:
    """Locate the Java bridge JAR, supporting worktree layouts.

    Build artifacts (``target/``) are gitignored, so in a git worktree the
    JAR lives only in the main repo. ``git rev-parse --git-common-dir``
    returns the shared ``.git`` directory whose parent is the main repo
    root; we resolve the JAR there. Falls back to the worktree path when
    the common-dir lookup fails (e.g., not in a git repo).

    Mirrors the pattern in ``test_map_integration.py::_find_jar_path`` so
    Phase 5.1 and Phase 8 share the same JAR-discovery contract.
    """
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(Path(__file__).resolve().parent),
            text=True,
        ).strip()
        main_repo = Path(common_dir).resolve().parent
        main_jar = main_repo / _JAR_REL
        if main_jar.exists():
            return main_jar
    except Exception:
        pass
    return Path(__file__).resolve().parents[2] / _JAR_REL


@pytest.fixture(scope="session")
def java_bridge():
    """Start one real ``JavaBridge`` for the entire test session.

    Used by every ``@pytest.mark.java`` integration test in the engine test
    suite (notably the Phase 8 code-component tests in
    ``test_java_component.py`` and ``test_java_row_component.py``).

    Per project memory ``feedback_test_real_bridge``: code components MUST
    test against the real bridge, not mocks. Mock-only tests gave false
    confidence in the Phase 5.1 audit, so D-21 / D-24 forbid mock-only for
    Java components.

    Threat T-08-19 (test pollution across the shared JVM): tests that
    mutate ``globalMap`` or ``context`` state should clean up after
    themselves -- the fixture itself does not reset between test methods.

    Threat T-08-20 (DoS via hung subprocess): teardown calls
    ``b.stop()``; ``JavaBridgeManager`` already handles SIGTERM and timeout
    on the underlying ``subprocess.Popen``.

    Worktree handling: build artifacts are gitignored, so we resolve the
    JAR to the main repo via ``git rev-parse --git-common-dir`` and
    symlink it into the worktree's expected target path so
    ``JavaBridge._find_jar_path`` (which looks relative to its own
    ``__file__``) succeeds. Symlink is removed on teardown.
    """
    jar_path = _find_java_bridge_jar()
    if not jar_path.exists():
        pytest.skip(
            f"Java bridge JAR not found at {jar_path}. "
            f"Build with: cd src/v1/java_bridge/java && mvn package -q"
        )

    # In a worktree, ``JavaBridge._find_jar_path`` resolves relative to its
    # own ``__file__`` (under the worktree's ``src/v1/java_bridge``). Build
    # artifacts are gitignored, so the worktree path is empty. Symlink the
    # main-repo JAR into the worktree path so the bridge finds it.
    from src.v1.java_bridge import bridge as bridge_mod
    bridge_base = Path(bridge_mod.__file__).resolve().parent
    worktree_target_dir = bridge_base / "java" / "target"
    worktree_jar = worktree_target_dir / "java-bridge-with-dependencies.jar"
    symlink_created = False
    if not worktree_jar.exists() and jar_path.exists():
        worktree_target_dir.mkdir(parents=True, exist_ok=True)
        worktree_jar.symlink_to(jar_path)
        symlink_created = True

    # Use JavaBridgeManager so we get the same dynamic-port allocation +
    # SIGTERM teardown the production engine relies on. This avoids the
    # default 25333 port collision when test_map_integration.py's
    # module-scoped fixture (or another test process) already holds it.
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
