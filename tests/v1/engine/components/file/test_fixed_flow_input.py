"""Tests for FixedFlowInputComponent (tFixedFlowInput engine implementation).

Group B verdict (Phase 07.2): KEEP. The converter at
``src/converters/talend_to_v1/components/file/fixed_flow_input.py:106``
emits ``nb_rows`` as a Python int via ``_get_int(node, "NB_ROWS", 1)``, so
the engine can rely on receiving an int. The tests below pin that contract:

- A string ``nb_rows`` (e.g. an unresolved ``${context.X}``) must produce a
  validation error at _validate_config time -- this is the engine's
  documented expectation, and the converter is responsible for upstream
  coercion.
- An int ``nb_rows`` must validate cleanly.
"""
import pytest

from src.v1.engine.components.file.fixed_flow_input import FixedFlowInputComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


_BASE_CONFIG = {
    "component_type": "FixedFlowInputComponent",
    "use_singlemode": True,
    "schema": [{"name": "id", "type": "id_Integer"}],
    "values_config": {"id": 1},
}


def _make_component(config):
    """Create a FixedFlowInputComponent and populate self.config.

    BaseComponent only assigns ``self.config`` from ``_original_config`` at
    the start of ``execute()``; for direct ``_validate_config()`` calls in
    unit tests we populate it manually to mirror that lifecycle step.
    """
    comp = FixedFlowInputComponent(
        component_id="tFFI_1",
        config=config,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    # Mirror execute() Step 1: populate working config from original.
    comp.config = dict(config)
    return comp


@pytest.mark.unit
class TestNbRowsContract:
    """Pin the contract that nb_rows is always a Python int post-conversion."""

    def test_validate_config_rejects_string_nb_rows(self):
        """A string nb_rows (unresolved context var) must produce an error.

        The converter never emits a string here -- it always coerces to int
        via _get_int. If the engine ever sees a string, that is a contract
        violation upstream and must be flagged.
        """
        config = dict(_BASE_CONFIG)
        config["nb_rows"] = "${context.X}"
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("nb_rows" in err for err in errors), (
            f"Expected nb_rows validation error, got: {errors}"
        )

    def test_validate_config_accepts_int_nb_rows(self):
        """An int nb_rows must validate cleanly."""
        config = dict(_BASE_CONFIG)
        config["nb_rows"] = 5
        comp = _make_component(config)
        errors = comp._validate_config()
        assert errors == [], f"Expected no errors, got: {errors}"
