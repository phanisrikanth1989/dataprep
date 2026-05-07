"""Unit tests for OracleRow engine component (Phase 11-03).

Mock-based tests cover registration, structural validation, both connection
acquisition paths (shared via manager.get / ad-hoc via open_ad_hoc), all
PARAMETER_TYPE coercions (Talaxie's 16 verified + RESEARCH.md inferred 3
aliases), USE_NB_LINE counter (D-C5), PROPAGATE_RECORD_SET refusal (D-C4),
and resolved-query globalMap publish (D-C8).

Real-DB validation lives in plan 11-07's @pytest.mark.oracle integration
tests (D-D3, D-F4 -- mocks lie).
"""
import datetime
import logging as _lg
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, oracle_manager=None, global_map=None):
    """Build an OracleRow with config already populated as the working
    ``self.config`` (skipping the BaseComponent.execute() lifecycle).
    """
    from src.v1.engine.components.database.oracle_row import OracleRow

    gm = global_map if global_map is not None else GlobalMap()
    comp = OracleRow(
        component_id="tOracleRow_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    # BaseComponent.execute() repopulates self.config; in unit tests we skip
    # execute() and seed it directly.
    comp.config = dict(config)
    comp.oracle_manager = (
        oracle_manager if oracle_manager is not None else MagicMock()
    )
    return comp


def _shared_conn_config(**overrides):
    cfg = {
        "use_existing_connection": True,
        "connection": "tOracleConnection_1",
        "query": "SELECT 1 FROM DUAL",
        "use_nb_line": "NONE",
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
        "password": "secret_hunter2",
        "query": "SELECT 1 FROM DUAL",
        "use_nb_line": "NONE",
    }
    cfg.update(overrides)
    return cfg


# ----------------------------------------------------------------------
# TestRegistration -- both aliases resolve
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.oracle_row import OracleRow

        assert REGISTRY.get("OracleRow") is OracleRow
        assert REGISTRY.get("tOracleRow") is OracleRow


# ----------------------------------------------------------------------
# TestValidateConfig -- structural checks only (Rule 12 / D-F3)
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_query_raises(self):
        cfg = _shared_conn_config()
        del cfg["query"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "query" in str(exc.value)

    def test_invalid_use_nb_line_raises(self):
        comp = _make_component(_shared_conn_config(use_nb_line="BOGUS"))
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "BOGUS" in str(exc.value)

    def test_set_preparedstatement_parameters_not_list_raises(self):
        comp = _make_component(_shared_conn_config(
            use_preparedstatement=True,
            set_preparedstatement_parameters="not_a_list",
        ))
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "must be a list" in str(exc.value)

    def test_set_preparedstatement_parameters_entry_not_dict_raises(self):
        comp = _make_component(_shared_conn_config(
            use_preparedstatement=True,
            set_preparedstatement_parameters=["not_a_dict"],
        ))
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "must be a dict" in str(exc.value)

    def test_unsupported_parameter_type_raises(self):
        comp = _make_component(_shared_conn_config(
            use_preparedstatement=True,
            set_preparedstatement_parameters=[
                {"parameter_index": "1", "parameter_type": "BogusType",
                 "parameter_value": "x"}
            ],
        ))
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "BogusType" in str(exc.value)

    def test_propagate_record_set_passes_validate_config(self):
        # Per Rule 12 / D-F3, PROPAGATE_RECORD_SET refusal is a CONTENT check
        # in _process, not _validate_config.
        comp = _make_component(_shared_conn_config(propagate_record_set=True))
        # Should not raise
        comp._validate_config()


# ----------------------------------------------------------------------
# TestPropagateRecordSetRefusal -- D-C4 content check in _process
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestPropagateRecordSetRefusal:
    def test_propagate_record_set_true_raises_with_d_c4_message(self):
        mock_mgr = MagicMock()
        comp = _make_component(
            _shared_conn_config(propagate_record_set=True),
            oracle_manager=mock_mgr,
        )
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        msg = str(exc.value)
        assert "PROPAGATE_RECORD_SET" in msg
        assert "ResultSet" in msg
        assert "tOracleInput" in msg
        # Manager should not have been touched -- refusal happens before
        # connection acquisition.
        mock_mgr.get.assert_not_called()
        mock_mgr.open_ad_hoc.assert_not_called()


# ----------------------------------------------------------------------
# TestConnectionAcquisition -- shared vs ad-hoc paths
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestConnectionAcquisition:
    def test_use_existing_connection_calls_get(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=1)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn

        comp = _make_component(_shared_conn_config(), oracle_manager=mock_mgr)
        comp._process(None)

        mock_mgr.get.assert_called_once_with("tOracleConnection_1")
        mock_mgr.open_ad_hoc.assert_not_called()
        mock_mgr.close.assert_not_called()  # owns_connection=False

    def test_ad_hoc_connection_calls_open_ad_hoc_and_closes(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=1)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.open_ad_hoc.return_value = mock_conn

        comp = _make_component(_ad_hoc_config(), oracle_manager=mock_mgr)
        comp._process(None)

        mock_mgr.open_ad_hoc.assert_called_once()
        # First positional arg is self.id; second arg is the config dict
        args, kwargs = mock_mgr.open_ad_hoc.call_args
        assert args[0] == "tOracleRow_1"
        mock_mgr.close.assert_called_once_with("tOracleRow_1")

    def test_manager_wiring_required(self):
        # If oracle_manager is None, _process raises ConfigurationError
        comp = _make_component(_shared_conn_config())
        comp.oracle_manager = None
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "OracleConnectionManager" in str(exc.value)


# ----------------------------------------------------------------------
# TestAdHocCloseInFinally -- T-11-03 mitigation regression
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestAdHocCloseInFinally:
    def test_ad_hoc_closed_when_execute_raises(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("boom")
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.open_ad_hoc.return_value = mock_conn

        comp = _make_component(
            _ad_hoc_config(query="BAD SQL"),
            oracle_manager=mock_mgr,
        )
        with pytest.raises(RuntimeError):
            comp._process(None)
        mock_mgr.close.assert_called_once_with("tOracleRow_1")
        mock_cursor.close.assert_called_once()

    def test_shared_connection_not_closed_when_execute_raises(self):
        # Shared connections are owned by upstream tOracleConnection; we
        # MUST NOT close them on exception.
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("boom")
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn

        comp = _make_component(_shared_conn_config(), oracle_manager=mock_mgr)
        with pytest.raises(RuntimeError):
            comp._process(None)
        mock_mgr.close.assert_not_called()  # owns_connection=False
        mock_cursor.close.assert_called_once()  # cursor closed in finally


# ----------------------------------------------------------------------
# TestSimpleExecute / TestPreparedStatementBindOrder
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestSimpleExecute:
    def test_no_prepared_statement_calls_execute_without_binds(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=0)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn
        comp = _make_component(
            _shared_conn_config(query="DELETE FROM emp"),
            oracle_manager=mock_mgr,
        )
        comp._process(None)
        mock_cursor.execute.assert_called_once_with("DELETE FROM emp")


@pytest.mark.unit
class TestPreparedStatementBindOrder:
    def test_binds_in_parameter_index_order_when_shuffled(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=1)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn
        cfg = _shared_conn_config(
            use_preparedstatement=True,
            set_preparedstatement_parameters=[
                {"parameter_index": "3", "parameter_type": "String",
                 "parameter_value": "third"},
                {"parameter_index": "1", "parameter_type": "Int",
                 "parameter_value": 1},
                {"parameter_index": "2", "parameter_type": "Float",
                 "parameter_value": 2.5},
            ],
        )
        comp = _make_component(cfg, oracle_manager=mock_mgr)
        comp._process(None)
        args, kwargs = mock_cursor.execute.call_args
        assert args[0] == "SELECT 1 FROM DUAL"
        assert args[1] == [1, 2.5, "third"]


# ----------------------------------------------------------------------
# TestParameterTypeCoercion -- 16 Talaxie + 3 RESEARCH inferred = 19 entries
# ----------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "ptype, value, expected",
    [
        # Talaxie verified (16)
        ("BigDecimal", "3.14", Decimal("3.14")),
        ("Blob",       "abc",  b"abc"),
        ("Boolean",    1,      True),
        ("Byte",       "127",  127),
        ("Bytes",      "abc",  b"abc"),
        ("Clob",       42,     "42"),
        ("Date",       "2026-05-07", datetime.date(2026, 5, 7)),
        ("Double",     "2.5",  2.5),
        ("Float",      "1.5",  1.5),
        ("Int",        "5",    5),
        ("Long",       "9999999999", 9999999999),
        ("Object",     {"any": "thing"}, {"any": "thing"}),
        ("Short",      "10",   10),
        ("String",     42,     "42"),
        ("Time",       "12:34:56", datetime.time(12, 34, 56)),
        ("Null",       "ignored_value", None),
        # RESEARCH.md inferred aliases (3)
        ("Integer",    "5",    5),
        ("BigInteger", "12345678901234567890", 12345678901234567890),
        ("Timestamp",  "2026-05-07T12:34:56",
         datetime.datetime(2026, 5, 7, 12, 34, 56)),
    ],
)
class TestParameterTypeCoercion:
    def test_each_type_coerces_correctly(self, ptype, value, expected):
        from src.v1.engine.components.database.oracle_row import (
            _coerce_prepared_param,
        )
        result = _coerce_prepared_param({
            "parameter_index": "1",
            "parameter_type": ptype,
            "parameter_value": value,
        })
        assert result == expected
        # Type assertion -- exact same Python type, not just equality
        if expected is not None:
            assert type(result) is type(expected), (
                f"{ptype}: expected type {type(expected).__name__}, "
                f"got {type(result).__name__}"
            )


@pytest.mark.unit
class TestParameterTypeNullPassthrough:
    def test_each_coercer_returns_none_for_none(self):
        from src.v1.engine.components.database.oracle_row import (
            _PARAM_TYPE_COERCERS,
        )
        for ptype, coercer in _PARAM_TYPE_COERCERS.items():
            assert coercer(None) is None, (
                f"{ptype} coercer did not return None for None input"
            )


@pytest.mark.unit
class TestUnknownParameterType:
    def test_raises_with_supported_list(self):
        from src.v1.engine.components.database.oracle_row import (
            _coerce_prepared_param,
        )
        with pytest.raises(ConfigurationError) as exc:
            _coerce_prepared_param({
                "parameter_index": "1",
                "parameter_type": "Bogus",
                "parameter_value": "x",
            })
        msg = str(exc.value)
        assert "Bogus" in msg
        assert "Supported" in msg


# ----------------------------------------------------------------------
# TestUseNbLineCounter -- D-C5
# ----------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "nb_choice", ["NB_LINE_INSERTED", "NB_LINE_UPDATED", "NB_LINE_DELETED"]
)
class TestUseNbLineCounter:
    def test_writes_globalmap_key(self, nb_choice):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=42)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn
        gm = GlobalMap()
        comp = _make_component(
            _shared_conn_config(use_nb_line=nb_choice),
            oracle_manager=mock_mgr,
            global_map=gm,
        )
        comp._process(None)
        assert gm.get(f"tOracleRow_1_{nb_choice}") == 42


@pytest.mark.unit
class TestUseNbLineNone:
    def test_use_nb_line_none_writes_no_nb_line_key(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=5)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn
        gm = GlobalMap()
        comp = _make_component(
            _shared_conn_config(use_nb_line="NONE"),
            oracle_manager=mock_mgr,
            global_map=gm,
        )
        comp._process(None)
        # No NB_LINE_* key written (only QUERY + maybe stats)
        all_keys = list(gm.get_all().keys())
        nb_line_keys = [
            k for k in all_keys
            if "NB_LINE_INSERTED" in k or "NB_LINE_UPDATED" in k
            or "NB_LINE_DELETED" in k
        ]
        assert nb_line_keys == [], (
            f"use_nb_line=NONE should not write NB_LINE_* but found: "
            f"{nb_line_keys}"
        )


@pytest.mark.unit
class TestUseNbLineWithDdl:
    def test_rowcount_negative_writes_zero_and_warns(self, caplog):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=-1)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn
        gm = GlobalMap()
        with caplog.at_level(_lg.WARNING):
            comp = _make_component(
                _shared_conn_config(
                    query="CREATE TABLE x(a INT)",
                    use_nb_line="NB_LINE_INSERTED",
                ),
                oracle_manager=mock_mgr,
                global_map=gm,
            )
            comp._process(None)
        assert gm.get("tOracleRow_1_NB_LINE_INSERTED") == 0
        assert any(
            "DDL or unknown" in rec.getMessage() for rec in caplog.records
        ), f"Expected DDL warning; got: {[r.getMessage() for r in caplog.records]}"

    def test_rowcount_none_writes_zero(self, caplog):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock(rowcount=None)
        mock_conn.cursor.return_value = mock_cursor
        mock_mgr.get.return_value = mock_conn
        gm = GlobalMap()
        with caplog.at_level(_lg.WARNING):
            comp = _make_component(
                _shared_conn_config(
                    query="CREATE TABLE y(a INT)",
                    use_nb_line="NB_LINE_INSERTED",
                ),
                oracle_manager=mock_mgr,
                global_map=gm,
            )
            comp._process(None)
        assert gm.get("tOracleRow_1_NB_LINE_INSERTED") == 0
        assert any(
            "DDL or unknown" in rec.getMessage() for rec in caplog.records
        )


# ----------------------------------------------------------------------
# TestQueryGlobalMapPublish -- D-C8
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestQueryGlobalMapPublish:
    def test_resolved_query_published(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_conn.cursor.return_value = MagicMock(rowcount=1)
        mock_mgr.get.return_value = mock_conn
        gm = GlobalMap()
        comp = _make_component(
            _shared_conn_config(query="SELECT * FROM dual"),
            oracle_manager=mock_mgr,
            global_map=gm,
        )
        comp._process(None)
        assert gm.get("tOracleRow_1_QUERY") == "SELECT * FROM dual"


# ----------------------------------------------------------------------
# TestCommitBehavior
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestCommitBehavior:
    def test_commit_called_when_autocommit_false(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_conn.cursor.return_value = MagicMock(rowcount=1)
        mock_mgr.get.return_value = mock_conn
        comp = _make_component(_shared_conn_config(), oracle_manager=mock_mgr)
        comp._process(None)
        mock_conn.commit.assert_called_once()

    def test_commit_not_called_when_autocommit_true(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=True)
        mock_conn.cursor.return_value = MagicMock(rowcount=1)
        mock_mgr.get.return_value = mock_conn
        comp = _make_component(_shared_conn_config(), oracle_manager=mock_mgr)
        comp._process(None)
        mock_conn.commit.assert_not_called()


# ----------------------------------------------------------------------
# TestPassthrough
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestPassthrough:
    def test_input_dataframe_returned_as_main(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_conn.cursor.return_value = MagicMock(rowcount=1)
        mock_mgr.get.return_value = mock_conn
        df = pd.DataFrame({"a": [1, 2, 3]})
        comp = _make_component(_shared_conn_config(), oracle_manager=mock_mgr)
        result = comp._process(df)
        assert result["main"] is df
        assert result["reject"] is None

    def test_none_input_passes_through_as_none(self):
        mock_mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_conn.cursor.return_value = MagicMock(rowcount=1)
        mock_mgr.get.return_value = mock_conn
        comp = _make_component(_shared_conn_config(), oracle_manager=mock_mgr)
        result = comp._process(None)
        assert result["main"] is None
        assert result["reject"] is None
