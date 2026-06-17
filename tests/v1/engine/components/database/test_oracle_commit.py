"""Unit tests for OracleCommit engine component.

Mock-based: registration, structural validation, commit + optional close,
manager-wiring guard. Real-DB validation lives in @pytest.mark.oracle
integration tests (mocks lie).
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, oracle_manager=None, global_map=None):
    from src.v1.engine.components.database.oracle_commit import OracleCommit

    gm = global_map if global_map is not None else GlobalMap()
    comp = OracleCommit(
        component_id="tOracleCommit_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    comp.oracle_manager = (
        oracle_manager if oracle_manager is not None else MagicMock()
    )
    return comp


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.oracle_commit import OracleCommit

        assert REGISTRY.get("OracleCommit") is OracleCommit
        assert REGISTRY.get("tOracleCommit") is OracleCommit


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_connection_raises(self):
        comp = _make_component({"close": True})
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "connection" in str(exc.value)

    def test_empty_connection_raises(self):
        comp = _make_component({"connection": "", "close": True})
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_valid_connection_passes(self):
        comp = _make_component({"connection": "tOracleConnection_1"})
        comp._validate_config()


@pytest.mark.unit
class TestProcess:
    def test_commit_and_close_by_default(self):
        mock_mgr = MagicMock()
        comp = _make_component(
            {"connection": "tOracleConnection_1"}, oracle_manager=mock_mgr
        )
        result = comp._process(None)
        mock_mgr.commit.assert_called_once_with("tOracleConnection_1")
        mock_mgr.close.assert_called_once_with("tOracleConnection_1")
        assert result == {"main": None, "reject": None}

    def test_commit_without_close(self):
        mock_mgr = MagicMock()
        comp = _make_component(
            {"connection": "tOracleConnection_1", "close": False},
            oracle_manager=mock_mgr,
        )
        comp._process(None)
        mock_mgr.commit.assert_called_once_with("tOracleConnection_1")
        mock_mgr.close.assert_not_called()

    def test_passthrough_input(self):
        df = pd.DataFrame({"a": [1, 2]})
        comp = _make_component(
            {"connection": "tOracleConnection_1", "close": False},
            oracle_manager=MagicMock(),
        )
        result = comp._process(df)
        assert result["main"] is df

    def test_manager_wiring_required(self):
        comp = _make_component({"connection": "tOracleConnection_1"})
        comp.oracle_manager = None
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "OracleConnectionManager" in str(exc.value)

    def test_commit_failure_propagates(self):
        mock_mgr = MagicMock()
        mock_mgr.commit.side_effect = ConfigurationError("no such connection")
        comp = _make_component(
            {"connection": "bogus"}, oracle_manager=mock_mgr
        )
        with pytest.raises(ConfigurationError):
            comp._process(None)
        mock_mgr.close.assert_not_called()
