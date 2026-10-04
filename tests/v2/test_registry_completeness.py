"""Registry completeness and SUPPORTED_FEATURES assertion (HARN-05).

Asserts all 15 target v2 components are registered in REGISTRY and
each declares non-empty SUPPORTED_FEATURES.

The TARGET_COMPONENTS frozenset is intentionally hardcoded: changing
the target set requires a deliberate test-file edit. Each onboarding
phase adds its name to this set.

Per D-23: hardcoded frozenset, not auto-discovered.
Per D-24: two gates -- registration + non-empty SUPPORTED_FEATURES.
"""

import pytest

from src.v2.components.capabilities import get_supported_features
from src.v2.components.registry import REGISTRY

# Side-effect imports to ensure all component modules register with REGISTRY.
# Each component package's __init__.py re-exports its classes, triggering
# the @REGISTRY.register() decorators.
import src.v2.components.transform  # noqa: F401
import src.v2.components.file  # noqa: F401
import src.v2.components.aggregate  # noqa: F401
import src.v2.components.python  # noqa: F401
import src.v2.components.utility  # noqa: F401

# ------------------------------------------------------------------
# Hardcoded target set (D-23).
# Add each component name as its phase onboards it to the standard.
# Phase 2 starts with filter_columns only.
# ------------------------------------------------------------------
TARGET_COMPONENTS: frozenset = frozenset(
    {
        # Phase 2 (COMP-01):
        "filter_columns",
        # Phase 4 (COMP-02):
        "filter_rows",
        # Phase 5 (COMP-03):
        "unite",
        # Phase 6 (COMP-04):
        "uniq_row",
        # Phase 7 (COMP-05):
        "file_input_delimited",
        # Phase 8 (COMP-06):
        "file_output_delimited",
        # Phase 9 (COMP-07):
        "sort_row",
        # Phase 10 (COMP-08): "aggregate",  -- uncomment when onboarded
        # Phase 11 (COMP-13): "python_row",  -- uncomment when onboarded
        # Phase 12 (COMP-14): "python_code",  -- uncomment when onboarded
        # Phase 13 (COMP-15): "python_dataframe",  -- uncomment when onboarded
        # Phase 14 (COMP-09): "file_input_positional",  -- uncomment when onboarded
        # Phase 15 (COMP-10): "schema_compliance_check",  -- uncomment when onboarded
        # Phase 16 (COMP-11): "context_load",  -- uncomment when onboarded
        # Phase 17 (COMP-12): "map",  -- uncomment when onboarded
    }
)

# How many we expect to reach (the full 15)
TOTAL_TARGET = 15


class TestRegistryCompleteness:
    """Gate 1 (D-24): all target components are registered."""

    @pytest.mark.parametrize("name", sorted(TARGET_COMPONENTS))
    def test_component_registered(self, name: str):
        """Component must be resolvable via REGISTRY.get()."""
        cls = REGISTRY.get(name)
        assert cls is not None, (
            f"Component {name!r} not found in REGISTRY. "
            f"Check that the component module is imported (side-effect registration) "
            f"and the @REGISTRY.register() decorator includes {name!r}."
        )

    @pytest.mark.parametrize("name", sorted(TARGET_COMPONENTS))
    def test_supported_features_declared(self, name: str):
        """Component must have non-empty SUPPORTED_FEATURES (D-24 Gate 2)."""
        cls = REGISTRY.get(name)
        if cls is None:
            pytest.skip(f"{name} not registered yet -- Gate 1 must pass first")
        features = get_supported_features(cls)
        assert len(features) > 0, (
            f"Component {cls.__name__} has empty SUPPORTED_FEATURES. "
            f"Every onboarded component must declare its feature support dict."
        )

    def test_target_count_reminder(self):
        """TARGET_COMPONENTS should grow to TOTAL_TARGET as phases complete."""
        current = len(TARGET_COMPONENTS)
        if current < TOTAL_TARGET:
            # This is informational, not a failure -- but it surfaces progress
            pass
        assert current <= TOTAL_TARGET, (
            f"TARGET_COMPONENTS has {current} entries but only {TOTAL_TARGET} "
            f"components are in scope. Remove extras or update TOTAL_TARGET."
        )
