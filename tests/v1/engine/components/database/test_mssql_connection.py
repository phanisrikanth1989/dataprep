"""Unit tests for MSSqlConnection engine component.

Mock-based: registration, structural validation, open + register via the
manager, metadata publish (never credential), manager-wiring guard.
"""
from unittest.mock import MagicMock

import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, mssql_manager=None, global_map=None):
    from src.v1.engine.components.database.mssql_connection import MSSqlConnection

    gm = global_map if global_map is not None else GlobalMap()
    comp = MSSqlConnection(
        component_id="tMSSqlConnection_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    comp.mssql_manager = (
        mssql_manager if mssql_manager is not None else MagicMock()
    )
    return comp


def _config(**overrides):
    cfg = {
        "host": "dbhost",
        "port": "1433",
        "dbname": "sales",
        "schema_db": "dbo",
        "user": "sa",
        "password": "secret",
    }
    cfg.update(overrides)
    return cfg


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.mssql_connection import (
            MSSqlConnection,
        )

        assert REGISTRY.get("MSSqlConnection") is MSSqlConnection
        assert REGISTRY.get("tMSSqlConnection") is MSSqlConnection


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_host_raises(self):
        cfg = _config(host="")
        with pytest.raises(ConfigurationError) as exc:
            _make_component(cfg)._validate_config()
        assert "host" in str(exc.value)

    def test_valid_passes(self):
        _make_component(_config())._validate_config()


@pytest.mark.unit
class TestProcess:
    def test_opens_and_registers(self):
        mgr = MagicMock()
        comp = _make_component(_config(), mssql_manager=mgr)
        result = comp._process(None)
        mgr.open_ad_hoc.assert_called_once_with("tMSSqlConnection_1", comp.config)
        assert result == {"main": None, "reject": None}

    def test_publishes_metadata_not_password(self):
        gm = GlobalMap()
        comp = _make_component(_config(), mssql_manager=MagicMock(), global_map=gm)
        comp._process(None)
        assert gm.get("connectionType_tMSSqlConnection_1") == "MSSQL"
        assert gm.get("dbschema_tMSSqlConnection_1") == "dbo"
        assert gm.get("username_tMSSqlConnection_1") == "sa"
        # Credential must never be published under any key.
        assert all(
            "secret" not in str(v) for v in gm.get_all().values()
        )

    def test_manager_wiring_required(self):
        comp = _make_component(_config())
        comp.mssql_manager = None
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "MSSqlConnectionManager" in str(exc.value)
