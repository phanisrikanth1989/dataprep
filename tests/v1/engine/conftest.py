"""Pytest configuration for v1 engine tests.

Provides StubComponent and helper functions for Phase 3 execution tests.
StubComponent enables testing execution orchestration without real component
implementations (per D-17).
"""
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
