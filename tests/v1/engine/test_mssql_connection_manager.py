"""Unit tests for MSSqlConnectionManager.

pyodbc is not installed in this environment, so a fake ``pyodbc`` module is
injected into sys.modules for the paths that import it (start / open_ad_hoc).
Real SQL Server validation lives in @pytest.mark.mssql integration tests.
"""
import sys
from unittest.mock import MagicMock

import pytest

from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.mssql_connection_manager import MSSqlConnectionManager


@pytest.fixture
def fake_pyodbc(monkeypatch):
    mod = MagicMock(name="pyodbc")
    monkeypatch.setitem(sys.modules, "pyodbc", mod)
    return mod


def _config(**overrides):
    cfg = {
        "host": "dbhost",
        "port": "1433",
        "dbname": "sales",
        "user": "sa",
        "password": "p@ss",
    }
    cfg.update(overrides)
    return cfg


@pytest.mark.unit
class TestLifecycle:
    def test_start_is_idempotent(self, fake_pyodbc):
        mgr = MSSqlConnectionManager()
        mgr.start()
        mgr.start()
        assert mgr.is_running is True
        assert mgr.is_available() is True

    def test_stop_closes_all_connections(self, fake_pyodbc):
        mgr = MSSqlConnectionManager()
        mgr.start()
        conn = MagicMock()
        mgr.register("c1", conn)
        mgr.stop()
        conn.close.assert_called_once()
        assert mgr.connections == {}
        assert mgr.is_running is False

    def test_stop_idempotent_when_never_started(self):
        mgr = MSSqlConnectionManager()
        mgr.stop()  # no-op, no raise

    def test_stop_swallows_close_error(self, fake_pyodbc):
        mgr = MSSqlConnectionManager()
        mgr.start()
        conn = MagicMock()
        conn.close.side_effect = RuntimeError("boom")
        mgr.register("c1", conn)
        mgr.stop()  # must not raise
        assert mgr.connections == {}


@pytest.mark.unit
class TestRegistry:
    def test_register_and_get(self):
        mgr = MSSqlConnectionManager()
        conn = MagicMock()
        mgr.register("c1", conn)
        assert mgr.get("c1") is conn

    def test_register_duplicate_raises(self):
        mgr = MSSqlConnectionManager()
        mgr.register("c1", MagicMock())
        with pytest.raises(ValueError):
            mgr.register("c1", MagicMock())

    def test_get_unknown_raises(self):
        mgr = MSSqlConnectionManager()
        with pytest.raises(ConfigurationError) as exc:
            mgr.get("missing")
        assert "missing" in str(exc.value)


@pytest.mark.unit
class TestAdHoc:
    def test_open_ad_hoc_connects_and_stores(self, fake_pyodbc):
        mgr = MSSqlConnectionManager()
        mgr.start()
        conn = MagicMock()
        fake_pyodbc.connect.return_value = conn
        result = mgr.open_ad_hoc("c1", _config(auto_commit=True))
        assert result is conn
        assert mgr.connections["c1"] is conn
        # autocommit passed through.
        _, kwargs = fake_pyodbc.connect.call_args
        assert kwargs["autocommit"] is True

    def test_open_ad_hoc_duplicate_raises(self, fake_pyodbc):
        mgr = MSSqlConnectionManager()
        mgr.start()
        fake_pyodbc.connect.return_value = MagicMock()
        mgr.open_ad_hoc("c1", _config())
        with pytest.raises(ValueError):
            mgr.open_ad_hoc("c1", _config())


@pytest.mark.unit
class TestConnectionString:
    def test_basic_sql_auth(self):
        cs = MSSqlConnectionManager._build_connection_string(_config())
        assert "DRIVER={ODBC Driver 17 for SQL Server}" in cs
        assert "SERVER=dbhost,1433" in cs
        assert "DATABASE=sales" in cs
        assert "UID=sa" in cs
        assert "PWD=p@ss" in cs

    def test_custom_driver_override(self):
        cs = MSSqlConnectionManager._build_connection_string(
            _config(odbc_driver="ODBC Driver 18 for SQL Server")
        )
        assert "DRIVER={ODBC Driver 18 for SQL Server}" in cs

    def test_active_directory_auth(self):
        cs = MSSqlConnectionManager._build_connection_string(
            _config(active_dir_auth=True)
        )
        assert "Authentication=ActiveDirectoryPassword" in cs

    def test_no_port_uses_host_only(self):
        cs = MSSqlConnectionManager._build_connection_string(_config(port=""))
        assert "SERVER=dbhost;" in cs


@pytest.mark.unit
class TestPerConnectionControl:
    def test_close_pops_and_closes(self):
        mgr = MSSqlConnectionManager()
        conn = MagicMock()
        mgr.register("c1", conn)
        mgr.close("c1")
        conn.close.assert_called_once()
        assert "c1" not in mgr.connections

    def test_close_missing_is_noop(self):
        MSSqlConnectionManager().close("nope")  # no raise

    def test_close_swallows_error(self):
        mgr = MSSqlConnectionManager()
        conn = MagicMock()
        conn.close.side_effect = RuntimeError("boom")
        mgr.register("c1", conn)
        mgr.close("c1")  # must not raise

    def test_commit_and_rollback(self):
        mgr = MSSqlConnectionManager()
        conn = MagicMock()
        mgr.register("c1", conn)
        mgr.commit("c1")
        mgr.rollback("c1")
        conn.commit.assert_called_once()
        conn.rollback.assert_called_once()

    def test_commit_unknown_raises(self):
        with pytest.raises(ConfigurationError):
            MSSqlConnectionManager().commit("missing")


@pytest.mark.unit
class TestContextManagerAndRepr:
    def test_context_manager(self, fake_pyodbc):
        with MSSqlConnectionManager() as mgr:
            assert mgr.is_running is True
        assert mgr.is_running is False

    def test_repr_hides_details(self):
        mgr = MSSqlConnectionManager()
        mgr.register("c1", MagicMock())
        text = repr(mgr)
        assert "connections=1" in text
        assert "stopped" in text
