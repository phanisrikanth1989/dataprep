"""Unit tests for OracleSP engine component.

Mock-based: registration, structural validation, IN/OUT/INOUT binding,
function vs procedure calls, custom-type + RECORDSET refusal, per-row
iteration, stats, and cleanup. Real-DB validation lives in @pytest.mark.oracle
integration tests (mocks lie).
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, oracle_manager=None, global_map=None, output_schema=None):
    from src.v1.engine.components.database.oracle_sp import OracleSP

    gm = global_map if global_map is not None else GlobalMap()
    comp = OracleSP(
        component_id="tOracleSP_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    comp.output_schema = output_schema or []
    comp.oracle_manager = (
        oracle_manager if oracle_manager is not None else MagicMock()
    )
    return comp


def _base_config(**overrides):
    cfg = {
        "use_existing_connection": True,
        "connection": "tOracleConnection_1",
        "sp_name": "my_proc",
        "is_function": False,
        "sp_args": [],
    }
    cfg.update(overrides)
    return cfg


def _mock_mgr(autocommit=False):
    mgr = MagicMock()
    conn = MagicMock(autocommit=autocommit)
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    mgr.get.return_value = conn
    mgr.open_ad_hoc.return_value = conn
    return mgr, conn, cursor


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.oracle_sp import OracleSP

        assert REGISTRY.get("OracleSP") is OracleSP
        assert REGISTRY.get("tOracleSP") is OracleSP


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_sp_name_raises(self):
        cfg = _base_config()
        del cfg["sp_name"]
        with pytest.raises(ConfigurationError) as exc:
            _make_component(cfg)._validate_config()
        assert "sp_name" in str(exc.value)

    def test_sp_args_not_list_raises(self):
        with pytest.raises(ConfigurationError) as exc:
            _make_component(_base_config(sp_args="x"))._validate_config()
        assert "must be a list" in str(exc.value)

    def test_sp_args_entry_not_dict_raises(self):
        with pytest.raises(ConfigurationError) as exc:
            _make_component(_base_config(sp_args=["x"]))._validate_config()
        assert "must be a dict" in str(exc.value)

    def test_valid_passes(self):
        _make_component(_base_config())._validate_config()


@pytest.mark.unit
class TestUnsupportedRefusal:
    def test_custom_type_refused(self):
        mgr, _, _ = _mock_mgr()
        comp = _make_component(
            _base_config(sp_args=[{"column": "c", "type": "IN", "is_custom": True}]),
            oracle_manager=mgr,
        )
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "custom" in str(exc.value).lower()
        mgr.get.assert_not_called()  # refusal before connection acquisition

    def test_recordset_refused(self):
        mgr, _, _ = _mock_mgr()
        comp = _make_component(
            _base_config(sp_args=[{"column": "rc", "type": "RECORDSET"}]),
            oracle_manager=mgr,
        )
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "RECORDSET" in str(exc.value)


@pytest.mark.unit
class TestProcedureCall:
    def test_callproc_with_in_params(self):
        mgr, conn, cursor = _mock_mgr()
        df_in = pd.DataFrame({"a": [10], "b": ["x"]})
        comp = _make_component(
            _base_config(sp_args=[
                {"column": "a", "type": "IN", "dbtype": "NUMBER"},
                {"column": "b", "type": "IN", "dbtype": "VARCHAR2"},
            ]),
            oracle_manager=mgr,
        )
        comp._process(df_in)
        cursor.callproc.assert_called_once()
        name, args = cursor.callproc.call_args.args
        assert name == "my_proc"
        assert args == [10, "x"]

    def test_out_param_written_to_output(self):
        mgr, conn, cursor = _mock_mgr()
        out_var = MagicMock()
        out_var.getvalue.return_value = 42
        cursor.var.return_value = out_var
        comp = _make_component(
            _base_config(sp_args=[
                {"column": "result", "type": "OUT", "dbtype": "NUMBER"},
            ]),
            oracle_manager=mgr,
        )
        df = comp._process(None)["main"]
        assert df.iloc[0]["result"] == 42

    def test_inout_param_sets_and_reads(self):
        mgr, conn, cursor = _mock_mgr()
        io_var = MagicMock()
        io_var.getvalue.return_value = 99
        cursor.var.return_value = io_var
        df_in = pd.DataFrame({"counter": [1]})
        comp = _make_component(
            _base_config(sp_args=[
                {"column": "counter", "type": "IN OUT", "dbtype": "NUMBER"},
            ]),
            oracle_manager=mgr,
        )
        df = comp._process(df_in)["main"]
        io_var.setvalue.assert_called_once_with(0, 1)
        assert df.iloc[0]["counter"] == 99


@pytest.mark.unit
class TestFunctionCall:
    def test_callfunc_return_written(self):
        mgr, conn, cursor = _mock_mgr()
        cursor.callfunc.return_value = "RESULT"
        comp = _make_component(
            _base_config(
                is_function=True,
                sp_name="my_func",
                return_column="ret",
                return_bdtype="VARCHAR2",
                sp_args=[{"column": "a", "type": "IN", "dbtype": "NUMBER"}],
            ),
            oracle_manager=mgr,
        )
        df_in = pd.DataFrame({"a": [5]})
        df = comp._process(df_in)["main"]
        cursor.callfunc.assert_called_once()
        assert df.iloc[0]["ret"] == "RESULT"


@pytest.mark.unit
class TestPerRowIteration:
    def test_called_once_per_input_row(self):
        mgr, conn, cursor = _mock_mgr()
        df_in = pd.DataFrame({"a": [1, 2, 3]})
        comp = _make_component(
            _base_config(sp_args=[{"column": "a", "type": "IN", "dbtype": "NUMBER"}]),
            oracle_manager=mgr,
        )
        result = comp._process(df_in)
        assert cursor.callproc.call_count == 3
        assert len(result["main"]) == 3

    def test_no_input_calls_once(self):
        mgr, conn, cursor = _mock_mgr()
        comp = _make_component(_base_config(), oracle_manager=mgr)
        comp._process(None)
        assert cursor.callproc.call_count == 1


@pytest.mark.unit
class TestCommitAndStats:
    def test_commit_when_not_autocommit(self):
        mgr, conn, cursor = _mock_mgr(autocommit=False)
        comp = _make_component(_base_config(), oracle_manager=mgr)
        comp._process(None)
        conn.commit.assert_called_once()

    def test_no_commit_when_autocommit(self):
        mgr, conn, cursor = _mock_mgr(autocommit=True)
        comp = _make_component(_base_config(), oracle_manager=mgr)
        comp._process(None)
        conn.commit.assert_not_called()

    def test_nb_line_published(self):
        gm = GlobalMap()
        mgr, conn, cursor = _mock_mgr()
        df_in = pd.DataFrame({"a": [1, 2]})
        comp = _make_component(
            _base_config(sp_args=[{"column": "a", "type": "IN"}]),
            oracle_manager=mgr,
            global_map=gm,
        )
        comp._process(df_in)
        assert gm.get("tOracleSP_1_NB_LINE") == 2


@pytest.mark.unit
class TestCleanup:
    def test_ad_hoc_closed_on_error(self):
        mgr, conn, cursor = _mock_mgr()
        cursor.callproc.side_effect = RuntimeError("boom")
        comp = _make_component(
            {
                "use_existing_connection": False,
                "connection_type": "ORACLE_SID",
                "host": "h", "port": "1521", "dbname": "ORCL",
                "user": "u", "password": "p",
                "sp_name": "my_proc", "sp_args": [],
            },
            oracle_manager=mgr,
        )
        with pytest.raises(RuntimeError):
            comp._process(None)
        cursor.close.assert_called_once()
        mgr.close.assert_called_once_with("tOracleSP_1")

    def test_manager_wiring_required(self):
        comp = _make_component(_base_config())
        comp.oracle_manager = None
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "OracleConnectionManager" in str(exc.value)

    def test_cursor_close_failure_swallowed(self, caplog):
        mgr, conn, cursor = _mock_mgr()
        cursor.close.side_effect = RuntimeError("close boom")
        comp = _make_component(_base_config(), oracle_manager=mgr)
        comp._process(None)  # must not raise
        assert any(
            "cursor.close() raised" in r.getMessage() for r in caplog.records
        )

    def test_adhoc_manager_close_failure_swallowed(self, caplog):
        mgr, conn, cursor = _mock_mgr()
        mgr.close.side_effect = RuntimeError("mgr boom")
        comp = _make_component(
            {
                "use_existing_connection": False,
                "connection_type": "ORACLE_SID",
                "host": "h", "port": "1521", "dbname": "ORCL",
                "user": "u", "password": "p",
                "sp_name": "my_proc", "sp_args": [],
            },
            oracle_manager=mgr,
        )
        comp._process(None)
        assert any(
            "oracle_manager.close() raised" in r.getMessage()
            for r in caplog.records
        )


@pytest.mark.unit
class TestHelpers:
    def test_normalize_direction_variants(self):
        from src.v1.engine.components.database.oracle_sp import (
            _normalize_direction,
        )
        assert _normalize_direction("IN OUT") == "INOUT"
        assert _normalize_direction("in_out") == "INOUT"
        assert _normalize_direction("OUT") == "OUT"
        assert _normalize_direction("") == ""

    def test_oracle_var_type_known_and_unknown(self):
        import oracledb
        from src.v1.engine.components.database.oracle_sp import _oracle_var_type

        assert _oracle_var_type("NUMBER") is oracledb.DB_TYPE_NUMBER
        assert _oracle_var_type("DATE") is oracledb.DB_TYPE_DATE
        # Unknown falls back to VARCHAR.
        assert _oracle_var_type("WEIRDTYPE") is oracledb.DB_TYPE_VARCHAR

    def test_support_nls_warns(self, caplog):
        import logging
        mgr, conn, cursor = _mock_mgr()
        comp = _make_component(
            _base_config(support_nls=True), oracle_manager=mgr
        )
        with caplog.at_level(logging.WARNING):
            comp._process(None)
        assert any("support_nls" in r.getMessage() for r in caplog.records)

    def test_unknown_direction_binds_as_in(self):
        mgr, conn, cursor = _mock_mgr()
        df_in = pd.DataFrame({"a": [7]})
        comp = _make_component(
            _base_config(sp_args=[{"column": "a", "type": "WEIRD"}]),
            oracle_manager=mgr,
        )
        comp._process(df_in)
        _, args = cursor.callproc.call_args.args
        assert args == [7]
