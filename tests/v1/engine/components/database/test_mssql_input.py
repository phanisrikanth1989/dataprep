"""Unit tests for MSSqlInput engine component.

Mock-based: registration, structural validation, both connection acquisition
paths, fetch -> DataFrame (pyodbc Row -> tuple), trim flags, query timeout,
NB_LINE publish, and finally-block cleanup.
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, mssql_manager=None, global_map=None, output_schema=None):
    from src.v1.engine.components.database.mssql_input import MSSqlInput

    gm = global_map if global_map is not None else GlobalMap()
    comp = MSSqlInput(
        component_id="tMSSqlInput_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    comp.output_schema = output_schema or []
    comp.mssql_manager = (
        mssql_manager if mssql_manager is not None else MagicMock()
    )
    return comp


def _shared(**overrides):
    cfg = {
        "use_existing_connection": True,
        "connection": "tMSSqlConnection_1",
        "query": "SELECT id, name FROM emp",
    }
    cfg.update(overrides)
    return cfg


def _ad_hoc(**overrides):
    cfg = {
        "use_existing_connection": False,
        "host": "h", "port": "1433", "dbname": "db",
        "user": "u", "password": "p",
        "query": "SELECT id, name FROM emp",
    }
    cfg.update(overrides)
    return cfg


def _mgr_with_rows(rows, description=None):
    mgr = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.description = description
    conn.cursor.return_value = cursor
    mgr.get.return_value = conn
    mgr.open_ad_hoc.return_value = conn
    return mgr, conn, cursor


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.mssql_input import MSSqlInput

        assert REGISTRY.get("MSSqlInput") is MSSqlInput
        assert REGISTRY.get("tMSSqlInput") is MSSqlInput


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_query_raises(self):
        cfg = _shared()
        del cfg["query"]
        with pytest.raises(ConfigurationError) as exc:
            _make_component(cfg)._validate_config()
        assert "query" in str(exc.value)

    def test_valid_passes(self):
        _make_component(_shared())._validate_config()


@pytest.mark.unit
class TestConnectionAcquisition:
    def test_shared_calls_get(self):
        mgr, _, _ = _mgr_with_rows([(1, "a")])
        comp = _make_component(
            _shared(), mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        mgr.get.assert_called_once_with("tMSSqlConnection_1")
        mgr.close.assert_not_called()

    def test_ad_hoc_opens_and_closes(self):
        mgr, _, _ = _mgr_with_rows([(1, "a")])
        comp = _make_component(
            _ad_hoc(), mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        mgr.open_ad_hoc.assert_called_once()
        mgr.close.assert_called_once_with("tMSSqlInput_1")

    def test_manager_wiring_required(self):
        comp = _make_component(_shared())
        comp.mssql_manager = None
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "MSSqlConnectionManager" in str(exc.value)


@pytest.mark.unit
class TestDataFrameBuild:
    def test_columns_from_schema(self):
        mgr, _, _ = _mgr_with_rows([(1, "alice"), (2, "bob")])
        comp = _make_component(
            _shared(), mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        df = comp._process(None)["main"]
        assert list(df.columns) == ["id", "name"]
        assert df.iloc[1]["name"] == "bob"

    def test_columns_from_description(self):
        desc = [("ID", None), ("NAME", None)]
        mgr, _, _ = _mgr_with_rows([(1, "a")], description=desc)
        comp = _make_component(_shared(), mssql_manager=mgr)
        df = comp._process(None)["main"]
        assert list(df.columns) == ["ID", "NAME"]

    def test_width_mismatch_positional(self):
        mgr, _, _ = _mgr_with_rows([(1, "a", "x")])
        comp = _make_component(
            _shared(), mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        df = comp._process(None)["main"]
        assert df.shape == (1, 3)

    def test_no_columns_positional(self):
        mgr, _, _ = _mgr_with_rows([(1, "a")], description=None)
        comp = _make_component(_shared(), mssql_manager=mgr)
        df = comp._process(None)["main"]
        assert df.shape == (1, 2)

    def test_empty(self):
        mgr, _, _ = _mgr_with_rows([])
        comp = _make_component(
            _shared(), mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        assert comp._process(None)["main"].empty


@pytest.mark.unit
class TestTrim:
    def test_trim_all(self):
        mgr, _, _ = _mgr_with_rows([("  a  ", "  b  ")])
        comp = _make_component(
            _shared(trim_all_column=True), mssql_manager=mgr,
            output_schema=[{"name": "c1"}, {"name": "c2"}],
        )
        df = comp._process(None)["main"]
        assert df.iloc[0]["c1"] == "a"
        assert df.iloc[0]["c2"] == "b"

    def test_trim_specific(self):
        mgr, _, _ = _mgr_with_rows([("  a  ", "  b  ")])
        comp = _make_component(
            _shared(trim_column=["bad", {"column": "c1"}]), mssql_manager=mgr,
            output_schema=[{"name": "c1"}, {"name": "c2"}],
        )
        df = comp._process(None)["main"]
        assert df.iloc[0]["c1"] == "a"
        assert df.iloc[0]["c2"] == "  b  "


@pytest.mark.unit
class TestQueryTimeout:
    def test_timeout_set_on_connection(self):
        mgr, conn, _ = _mgr_with_rows([(1, "a")])
        comp = _make_component(
            _shared(set_query_timeout=True, query_timeout_in_seconds=45),
            mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        assert conn.timeout == 45


@pytest.mark.unit
class TestStatsAndCleanup:
    def test_nb_line_published(self):
        gm = GlobalMap()
        mgr, _, _ = _mgr_with_rows([(1, "a"), (2, "b")])
        comp = _make_component(
            _shared(), mssql_manager=mgr, global_map=gm,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        assert gm.get("tMSSqlInput_1_NB_LINE") == 2
        assert gm.get("tMSSqlInput_1_QUERY") == "SELECT id, name FROM emp"

    def test_ad_hoc_closed_on_error(self):
        mgr, _, cur = _mgr_with_rows([(1, "a")])
        cur.execute.side_effect = RuntimeError("boom")
        comp = _make_component(_ad_hoc(), mssql_manager=mgr)
        with pytest.raises(RuntimeError):
            comp._process(None)
        cur.close.assert_called_once()
        mgr.close.assert_called_once_with("tMSSqlInput_1")

    def test_cursor_close_failure_swallowed(self, caplog):
        mgr, _, cur = _mgr_with_rows([(1, "a")])
        cur.close.side_effect = RuntimeError("close boom")
        comp = _make_component(
            _shared(), mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        assert any(
            "cursor.close() raised" in r.getMessage() for r in caplog.records
        )

    def test_adhoc_manager_close_failure_swallowed(self, caplog):
        mgr, _, _ = _mgr_with_rows([(1, "a")])
        mgr.close.side_effect = RuntimeError("mgr boom")
        comp = _make_component(
            _ad_hoc(), mssql_manager=mgr,
            output_schema=[{"name": "id"}, {"name": "name"}],
        )
        comp._process(None)
        assert any(
            "mssql_manager.close() raised" in r.getMessage()
            for r in caplog.records
        )
