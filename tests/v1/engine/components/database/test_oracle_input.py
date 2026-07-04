"""Unit tests for OracleInput engine component.

Mock-based: registration, structural validation, both connection acquisition
paths, fetch -> DataFrame with schema/description columns, trim flags,
no_null_values, cursor sizing, NB_LINE publish, and finally-block cleanup.
Real-DB validation lives in @pytest.mark.oracle integration tests (mocks lie).
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, oracle_manager=None, global_map=None, output_schema=None):
    from src.v1.engine.components.database.oracle_input import OracleInput

    gm = global_map if global_map is not None else GlobalMap()
    comp = OracleInput(
        component_id="tOracleInput_1",
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


def _shared_config(**overrides):
    cfg = {
        "use_existing_connection": True,
        "connection": "tOracleConnection_1",
        "query": "SELECT id, name FROM emp",
    }
    cfg.update(overrides)
    return cfg


def _ad_hoc_config(**overrides):
    cfg = {
        "use_existing_connection": False,
        "connection_type": "ORACLE_SID",
        "host": "h",
        "port": "1521",
        "dbname": "ORCL",
        "user": "u",
        "password": "secret",
        "query": "SELECT id, name FROM emp",
    }
    cfg.update(overrides)
    return cfg


def _mock_mgr_with_rows(rows, description=None, autocommit=False):
    mock_mgr = MagicMock()
    mock_conn = MagicMock(autocommit=autocommit)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_cursor.description = description
    mock_conn.cursor.return_value = mock_cursor
    mock_mgr.get.return_value = mock_conn
    mock_mgr.open_ad_hoc.return_value = mock_conn
    return mock_mgr, mock_conn, mock_cursor


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.oracle_input import OracleInput

        assert REGISTRY.get("OracleInput") is OracleInput
        assert REGISTRY.get("tOracleInput") is OracleInput


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_query_raises(self):
        cfg = _shared_config()
        del cfg["query"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "query" in str(exc.value)

    def test_valid_passes(self):
        _make_component(_shared_config())._validate_config()


@pytest.mark.unit
class TestConnectionAcquisition:
    def test_shared_calls_get(self):
        mgr, _, _ = _mock_mgr_with_rows([(1, "a")])
        comp = _make_component(
            _shared_config(),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        mgr.get.assert_called_once_with("tOracleConnection_1")
        mgr.open_ad_hoc.assert_not_called()
        mgr.close.assert_not_called()  # shared connection not owned

    def test_ad_hoc_opens_and_closes(self):
        mgr, _, _ = _mock_mgr_with_rows([(1, "a")])
        comp = _make_component(
            _ad_hoc_config(),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        mgr.open_ad_hoc.assert_called_once()
        assert mgr.open_ad_hoc.call_args.args[0] == "tOracleInput_1"
        mgr.close.assert_called_once_with("tOracleInput_1")

    def test_manager_wiring_required(self):
        comp = _make_component(_shared_config())
        comp.oracle_manager = None
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "OracleConnectionManager" in str(exc.value)


@pytest.mark.unit
class TestDataFrameBuild:
    def test_columns_from_output_schema(self):
        mgr, _, _ = _mock_mgr_with_rows([(1, "alice"), (2, "bob")])
        comp = _make_component(
            _shared_config(),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        df = comp._process(None)["main"]
        assert list(df.columns) == ["id", "name"]
        assert df.shape == (2, 2)
        assert df.iloc[1]["name"] == "bob"

    def test_columns_from_description_when_no_schema(self):
        desc = [("ID", None), ("NAME", None)]
        mgr, _, _ = _mock_mgr_with_rows([(1, "alice")], description=desc)
        comp = _make_component(_shared_config(), oracle_manager=mgr)
        df = comp._process(None)["main"]
        assert list(df.columns) == ["ID", "NAME"]

    def test_column_count_mismatch_falls_back_to_positional(self, caplog):
        # 3-wide rows but 2-col schema -> positional columns + warning.
        mgr, _, _ = _mock_mgr_with_rows([(1, "a", "x")])
        comp = _make_component(
            _shared_config(),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        df = comp._process(None)["main"]
        assert df.shape == (1, 3)

    def test_empty_result(self):
        mgr, _, _ = _mock_mgr_with_rows([])
        comp = _make_component(
            _shared_config(),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        df = comp._process(None)["main"]
        assert df.empty

    def test_no_columns_at_all_builds_positional(self):
        # No output_schema and no cursor.description -> positional DataFrame.
        mgr, _, _ = _mock_mgr_with_rows([(1, "a")], description=None)
        comp = _make_component(_shared_config(), oracle_manager=mgr)
        df = comp._process(None)["main"]
        assert df.shape == (1, 2)


@pytest.mark.unit
class TestTrim:
    def test_trim_all_column_strips_strings(self):
        mgr, _, _ = _mock_mgr_with_rows([(1, "  alice  ")])
        comp = _make_component(
            _shared_config(trim_all_column=True),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        df = comp._process(None)["main"]
        assert df.iloc[0]["name"] == "alice"

    def test_trim_specific_column(self):
        mgr, _, _ = _mock_mgr_with_rows([("  a  ", "  b  ")])
        comp = _make_component(
            _shared_config(trim_column=[{"column": "c1"}]),
            oracle_manager=mgr,
            output_schema=[{"name": "c1"}, {"name": "c2"}],
        )
        df = comp._process(None)["main"]
        assert df.iloc[0]["c1"] == "a"
        assert df.iloc[0]["c2"] == "  b  "  # untrimmed

    def test_trim_column_ignores_non_dict_entries(self):
        # Defensive: malformed trim_column entries are skipped, no crash.
        mgr, _, _ = _mock_mgr_with_rows([("  a  ", "  b  ")])
        comp = _make_component(
            _shared_config(trim_column=["not_a_dict", {"column": "c1"}]),
            oracle_manager=mgr,
            output_schema=[{"name": "c1"}, {"name": "c2"}],
        )
        df = comp._process(None)["main"]
        assert df.iloc[0]["c1"] == "a"


@pytest.mark.unit
class TestNoNullValues:
    def test_none_replaced_with_empty_string(self):
        mgr, _, _ = _mock_mgr_with_rows([(1, None)])
        comp = _make_component(
            _shared_config(no_null_values=True),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        df = comp._process(None)["main"]
        assert df.iloc[0]["name"] == ""


@pytest.mark.unit
class TestCursorSizing:
    def test_use_cursor_sets_arraysize(self):
        mgr, _, cur = _mock_mgr_with_rows([(1, "a")])
        comp = _make_component(
            _shared_config(use_cursor=True, cursor_size=500),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        assert cur.arraysize == 500


@pytest.mark.unit
class TestStats:
    def test_nb_line_published(self):
        gm = GlobalMap()
        mgr, _, _ = _mock_mgr_with_rows([(1, "a"), (2, "b"), (3, "c")])
        comp = _make_component(
            _shared_config(),
            oracle_manager=mgr,
            global_map=gm,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        assert gm.get("tOracleInput_1_NB_LINE") == 3
        assert gm.get("tOracleInput_1_QUERY") == "SELECT id, name FROM emp"


@pytest.mark.unit
class TestCleanup:
    def test_ad_hoc_closed_when_execute_raises(self):
        mgr, _, cur = _mock_mgr_with_rows([(1, "a")])
        cur.execute.side_effect = RuntimeError("boom")
        comp = _make_component(_ad_hoc_config(), oracle_manager=mgr)
        with pytest.raises(RuntimeError):
            comp._process(None)
        cur.close.assert_called_once()
        mgr.close.assert_called_once_with("tOracleInput_1")

    def test_ad_hoc_manager_close_failure_swallowed(self, caplog):
        mgr, _, _ = _mock_mgr_with_rows([(1, "a")])
        mgr.close.side_effect = RuntimeError("mgr close boom")
        comp = _make_component(
            _ad_hoc_config(),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)  # must not raise
        assert any(
            "oracle_manager.close() raised" in r.getMessage()
            for r in caplog.records
        )

    def test_cursor_close_failure_swallowed(self, caplog):
        mgr, _, cur = _mock_mgr_with_rows([(1, "a")])
        cur.close.side_effect = RuntimeError("close boom")
        comp = _make_component(
            _shared_config(),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)  # must not raise
        assert any(
            "cursor.close() raised" in r.getMessage() for r in caplog.records
        )

    def test_deferred_flags_warn(self, caplog):
        import logging
        mgr, _, _ = _mock_mgr_with_rows([(1, "a")])
        comp = _make_component(
            _shared_config(is_convert_xmltype=True, support_nls=True),
            oracle_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        with caplog.at_level(logging.WARNING):
            comp._process(None)
        msgs = " ".join(r.getMessage() for r in caplog.records)
        assert "is_convert_xmltype" in msgs
        assert "support_nls" in msgs
