"""Re-export the session-scoped ``java_bridge`` fixture into this test subtree.

``java_bridge`` is defined in ``tests/v1/engine/conftest.py``, whose fixtures
only cover ``tests/v1/engine/`` via pytest's parent-walk. The live-bridge golden
Phase-A e2e (``test_golden_phase_a_e2e.py``) lives here, outside that subtree, so
it cannot see that fixture. Importing the fixture into this conftest registers it
for ``tests/agents/tools/`` (the standard pytest fixture-reuse pattern), giving
the same skip-if-unavailable JVM gate without duplicating the JAR-discovery and
bridge-start logic. Additive only -- it does not shadow the engine conftest,
which covers a different subtree.
"""
from tests.v1.engine.conftest import java_bridge  # noqa: F401
