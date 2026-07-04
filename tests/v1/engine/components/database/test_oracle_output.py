"""Unit tests for OracleOutput engine component (Phase 11-04).

Mock-based tests cover registration, validation, all 8 TABLE_ACTIONs (DDL
emission), INSERT/UPDATE/DELETE batch DML, REJECT flow with
[errorCode, errorMessage, *input cols], FIELD_OPTIONS-aware key handling,
USE_TIMESTAMP_FOR_DATE_TYPE binding, identifier quoting (T-11-04), 5 stat
keys (D-C8), die_on_error rewrap, deferred upserts.

Real-DB DDL/DML validation deferred to plan 11-07 per D-D3.
"""
import re
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, DataValidationError
from src.v1.engine.global_map import GlobalMap


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _make_component(config, output_schema=None, oracle_manager=None, global_map=None):
    """Build an OracleOutput with config seeded directly (skip execute() lifecycle)."""
    from src.v1.engine.components.database.oracle_output import OracleOutput

    gm = global_map if global_map is not None else GlobalMap()
    comp = OracleOutput(
        component_id="tOracleOutput_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    # BaseComponent.execute() repopulates self.config; in unit tests we skip
    # execute() and seed it directly.
    comp.config = dict(config)
    comp.output_schema = output_schema if output_schema is not None else [
        {"name": "id", "type": "int", "key": True, "nullable": False},
        {"name": "name", "type": "str", "length": 50, "nullable": True},
    ]
    comp.oracle_manager = oracle_manager if oracle_manager is not None else MagicMock()
    return comp


def _shared_conn_config(**overrides):
    cfg = {
        "use_existing_connection": True,
        "connection": "tOracleConnection_1",
        "table": "EMP",
        "schema_db": "HR",
        "table_action": "NONE",
        "data_action": "INSERT",
    }
    cfg.update(overrides)
    return cfg


def _make_mock_oracle_manager(autocommit=False, batch_errors=None):
    """Build a MagicMock manager + cursor with sane defaults for _process tests."""
    mgr = MagicMock()
    mock_conn = MagicMock(autocommit=autocommit)
    mock_cursor = MagicMock()
    mock_cursor.getbatcherrors.return_value = batch_errors or []
    mock_conn.cursor.return_value = mock_cursor
    mgr.get.return_value = mock_conn
    mgr.open_ad_hoc.return_value = mock_conn
    return mgr, mock_conn, mock_cursor


# ----------------------------------------------------------------------
# Task 1 RED gate: module docstring documents Talaxie inspection findings
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestModuleDocstring:
    """Verify Open Q 1 + 3 are resolved in code: DDL conventions documented."""

    def test_docstring_has_talaxie_attribution(self):
        from src.v1.engine.components.database import oracle_output

        with open(oracle_output.__file__, encoding="utf-8") as f:
            src = f.read()
        assert "Talaxie _tableActionForOutput.javajet" in src

    def test_docstring_has_fetch_evidence(self):
        from src.v1.engine.components.database import oracle_output

        with open(oracle_output.__file__, encoding="utf-8") as f:
            src = f.read()
        fetch_evidence = re.search(
            r"https?://raw\.githubusercontent\.com/[^\s\"']+", src
        )
        fallback_evidence = re.search(r"\b404\b", src)
        assert fetch_evidence or fallback_evidence

    def test_docstring_lists_type_decisions(self):
        from src.v1.engine.components.database import oracle_output

        with open(oracle_output.__file__, encoding="utf-8") as f:
            src = f.read()
        for kw in ("Float", "Double", "VARCHAR2", "CREATE_IF_NOT_EXISTS"):
            assert kw in src, f"missing decision keyword: {kw}"


# ----------------------------------------------------------------------
# TestRegistration -- both aliases resolve
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.oracle_output import OracleOutput

        assert REGISTRY.get("OracleOutput") is OracleOutput
        assert REGISTRY.get("tOracleOutput") is OracleOutput


# ----------------------------------------------------------------------
# TestValidateConfig -- structural checks only (Rule 12 / D-F3)
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_table_raises(self):
        cfg = _shared_conn_config()
        del cfg["table"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_empty_table_raises(self):
        comp = _make_component(_shared_conn_config(table=""))
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_invalid_table_action_raises(self):
        comp = _make_component(_shared_conn_config(table_action="BOGUS"))
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_invalid_data_action_raises(self):
        comp = _make_component(_shared_conn_config(data_action="BOGUS"))
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_valid_defaults_pass(self):
        comp = _make_component(_shared_conn_config())
        # Should not raise
        comp._validate_config()


# ----------------------------------------------------------------------
# TestIdentifierQuotingPolicy (T-11-04)
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestIdentifierQuotingPolicy:
    def test_invalid_column_name_with_metachars_raises(self):
        from src.v1.engine.components.database.oracle_output import _quote_ident

        with pytest.raises(ConfigurationError) as exc:
            _quote_ident("drop;--")
        assert "drop;--" in str(exc.value)

    def test_column_starting_with_digit_raises(self):
        from src.v1.engine.components.database.oracle_output import _quote_ident

        with pytest.raises(ConfigurationError):
            _quote_ident("1abc")

    def test_column_with_space_raises(self):
        from src.v1.engine.components.database.oracle_output import _quote_ident

        with pytest.raises(ConfigurationError):
            _quote_ident("a b")

    def test_column_with_quote_raises(self):
        from src.v1.engine.components.database.oracle_output import _quote_ident

        with pytest.raises(ConfigurationError):
            _quote_ident('a"b')

    def test_empty_string_raises(self):
        from src.v1.engine.components.database.oracle_output import _quote_ident

        with pytest.raises(ConfigurationError):
            _quote_ident("")

    def test_valid_column_name_quoted(self):
        from src.v1.engine.components.database.oracle_output import _quote_ident

        assert _quote_ident("emp_id") == '"emp_id"'
        assert _quote_ident("FIRST_NAME") == '"FIRST_NAME"'

    def test_legacy_oracle_dollar_hash_column_accepted(self):
        from src.v1.engine.components.database.oracle_output import _quote_ident

        # Talend parity: legacy Oracle column names with $ / # accepted
        assert _quote_ident("EMP$DATA") == '"EMP$DATA"'
        assert _quote_ident("COL#1") == '"COL#1"'

    def test_create_with_invalid_column_name_raises(self):
        comp = _make_component(
            _shared_conn_config(table_action="CREATE"),
            output_schema=[{"name": "drop;--", "type": "str", "length": 10}],
        )
        with pytest.raises(ConfigurationError):
            comp._build_create_sql()


# ----------------------------------------------------------------------
# TestQualifiedTableName
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestQualifiedTableName:
    def test_schema_plus_table(self):
        comp = _make_component(_shared_conn_config())
        assert comp._qualified_table() == '"HR"."EMP"'

    def test_table_only_when_no_schema(self):
        cfg = _shared_conn_config()
        del cfg["schema_db"]
        comp = _make_component(cfg)
        assert comp._qualified_table() == '"EMP"'

    def test_dbschema_alias_honored(self):
        cfg = _shared_conn_config()
        del cfg["schema_db"]
        cfg["dbschema"] = "FINANCE"
        comp = _make_component(cfg)
        assert comp._qualified_table() == '"FINANCE"."EMP"'

    def test_invalid_schema_raises(self):
        comp = _make_component(_shared_conn_config(schema_db="bad-name"))
        with pytest.raises(ConfigurationError):
            comp._qualified_table()


# ----------------------------------------------------------------------
# TestTableActions: parametrized across the 8 actions
# ----------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "action, expected_substring",
    [
        ("CREATE", "CREATE TABLE"),
        ("CREATE_IF_NOT_EXISTS", "EXECUTE IMMEDIATE"),
        ("CREATE_IF_NOT_EXISTS", "SQLCODE != -955"),
        ("DROP_CREATE", "DROP TABLE"),
        ("DROP_IF_EXISTS_AND_CREATE", "SQLCODE != -942"),
        ("CLEAR", "DELETE FROM"),
        ("TRUNCATE", "TRUNCATE TABLE"),
        ("TRUNCATE_REUSE_STORAGE", "REUSE STORAGE"),
    ],
)
class TestTableActions:
    def test_emits_expected_sql(self, action, expected_substring):
        mock_cursor = MagicMock()
        comp = _make_component(_shared_conn_config(table_action=action))
        comp._execute_table_action(mock_cursor, action)
        executed = "\n".join(
            call.args[0] for call in mock_cursor.execute.call_args_list
        )
        assert expected_substring in executed


@pytest.mark.unit
class TestTableActionDispatch:
    def test_none_emits_nothing(self):
        mock_cursor = MagicMock()
        comp = _make_component(_shared_conn_config(table_action="NONE"))
        comp._execute_table_action(mock_cursor, "NONE")
        mock_cursor.execute.assert_not_called()

    def test_drop_create_emits_two_statements(self):
        mock_cursor = MagicMock()
        comp = _make_component(_shared_conn_config(table_action="DROP_CREATE"))
        comp._execute_table_action(mock_cursor, "DROP_CREATE")
        assert mock_cursor.execute.call_count == 2

    def test_drop_if_exists_and_create_emits_two_statements(self):
        mock_cursor = MagicMock()
        comp = _make_component(
            _shared_conn_config(table_action="DROP_IF_EXISTS_AND_CREATE")
        )
        comp._execute_table_action(mock_cursor, "DROP_IF_EXISTS_AND_CREATE")
        # First the PL/SQL DROP guard, then the CREATE
        assert mock_cursor.execute.call_count == 2

    def test_create_if_not_exists_uses_plsql_block(self):
        mock_cursor = MagicMock()
        comp = _make_component(_shared_conn_config(table_action="CREATE_IF_NOT_EXISTS"))
        comp._execute_table_action(mock_cursor, "CREATE_IF_NOT_EXISTS")
        sql = mock_cursor.execute.call_args_list[0].args[0]
        assert "BEGIN" in sql
        assert "EXCEPTION" in sql
        assert "END" in sql

    def test_unknown_action_raises(self):
        mock_cursor = MagicMock()
        comp = _make_component(_shared_conn_config(table_action="NONE"))
        with pytest.raises(ConfigurationError):
            comp._execute_table_action(mock_cursor, "BOGUS")


# ----------------------------------------------------------------------
# TestDdlTypeMapping
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestDdlTypeMapping:
    def test_int_maps_to_number_10(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "int"}, True) == "NUMBER(10)"

    def test_long_maps_to_number_19(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "long"}, True) == "NUMBER(19)"

    def test_short_maps_to_number_5(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "short"}, True) == "NUMBER(5)"

    def test_bigint_maps_to_number_38(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "BigInteger"}, True) == "NUMBER(38)"

    def test_decimal_with_precision(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert (
            _column_to_oracle_type(
                {"type": "Decimal", "length": 10, "precision": 2}, True
            )
            == "NUMBER(10,2)"
        )

    def test_decimal_without_length_falls_back_to_number(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "Decimal"}, True) == "NUMBER"

    def test_str_with_length(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert (
            _column_to_oracle_type({"type": "str", "length": 50}, True)
            == "VARCHAR2(50 CHAR)"
        )

    def test_str_long_maps_to_clob(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "str", "length": 4001}, True) == "CLOB"

    def test_str_no_length_maps_to_clob(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "str"}, True) == "CLOB"

    def test_datetime_with_timestamp_default(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "datetime"}, True) == "TIMESTAMP"

    def test_datetime_with_use_timestamp_false(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "datetime"}, False) == "DATE"

    def test_bool_maps_to_number_1(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "bool"}, True) == "NUMBER(1)"

    def test_bytes_short_maps_to_raw(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert (
            _column_to_oracle_type({"type": "bytes", "length": 100}, True)
            == "RAW(100)"
        )

    def test_bytes_long_maps_to_blob(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "bytes"}, True) == "BLOB"

    def test_float_maps_to_binary_float(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        # Per Task 1 decision; if Talaxie uses NUMBER, update both code and test
        assert _column_to_oracle_type({"type": "float"}, True) in (
            "BINARY_FLOAT",
            "NUMBER",
        )

    def test_double_maps_to_binary_double(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert _column_to_oracle_type({"type": "double"}, True) in (
            "BINARY_DOUBLE",
            "NUMBER",
        )

    def test_unknown_type_falls_back_to_varchar2_4000(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )

        assert (
            _column_to_oracle_type({"type": "unknown_type"}, True)
            == "VARCHAR2(4000)"
        )


# ----------------------------------------------------------------------
# TestNullableNotNull + TestPrimaryKey
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestNullableNotNull:
    def test_nullable_true_emits_null(self):
        schema = [{"name": "x", "type": "int", "nullable": True}]
        comp = _make_component(_shared_conn_config(table_action="CREATE"), output_schema=schema)
        sql = comp._build_create_sql()
        assert '"x" NUMBER(10) NULL' in sql

    def test_nullable_false_emits_not_null(self):
        schema = [{"name": "x", "type": "int", "nullable": False}]
        comp = _make_component(_shared_conn_config(table_action="CREATE"), output_schema=schema)
        sql = comp._build_create_sql()
        assert '"x" NUMBER(10) NOT NULL' in sql


@pytest.mark.unit
class TestPrimaryKey:
    def test_pk_constraint_emitted_when_keys_present(self):
        comp = _make_component(_shared_conn_config(table_action="CREATE"))
        sql = comp._build_create_sql()
        assert "PRIMARY KEY" in sql
        assert "PK_EMP" in sql

    def test_pk_constraint_with_multiple_key_columns(self):
        schema = [
            {"name": "a", "type": "int", "key": True, "nullable": False},
            {"name": "b", "type": "int", "key": True, "nullable": False},
            {"name": "c", "type": "str", "length": 10},
        ]
        comp = _make_component(_shared_conn_config(table_action="CREATE"), output_schema=schema)
        sql = comp._build_create_sql()
        assert '"a"' in sql and '"b"' in sql
        # Both key columns appear in the PRIMARY KEY clause
        assert re.search(r'PRIMARY KEY \("a", "b"\)', sql)

    def test_no_pk_constraint_when_no_key_column(self):
        schema = [{"name": "x", "type": "int", "key": False}]
        comp = _make_component(
            _shared_conn_config(table_action="CREATE"), output_schema=schema
        )
        sql = comp._build_create_sql()
        assert "PRIMARY KEY" not in sql


# ----------------------------------------------------------------------
# TestInsertSql / TestUpdateSql / TestDeleteSql
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestInsertSql:
    def test_shape_and_placeholders(self):
        comp = _make_component(_shared_conn_config())
        sql = comp._build_insert_sql()
        assert sql.startswith('INSERT INTO "HR"."EMP"')
        assert ":1" in sql and ":2" in sql
        assert '"id"' in sql and '"name"' in sql

    def test_insertable_columns_quoted(self):
        comp = _make_component(_shared_conn_config())
        sql = comp._build_insert_sql()
        # Both columns appear in the INSERT column list
        assert re.search(r'\("id", "name"\)', sql)


@pytest.mark.unit
class TestUpdateSql:
    def test_basic_update_uses_key_in_where(self):
        comp = _make_component(_shared_conn_config())
        sql = comp._build_update_sql()
        assert sql.startswith('UPDATE "HR"."EMP"')
        # 'name' is updatable, 'id' is the key
        assert '"name" = :1' in sql
        assert '"id" = :2' in sql
        assert "WHERE" in sql

    def test_update_without_key_raises(self):
        schema = [{"name": "a", "type": "int", "key": False}]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        with pytest.raises(ConfigurationError):
            comp._build_update_sql()


@pytest.mark.unit
class TestDeleteSql:
    def test_basic_delete_uses_key_in_where(self):
        comp = _make_component(_shared_conn_config())
        sql = comp._build_delete_sql()
        assert sql.startswith('DELETE FROM "HR"."EMP"')
        assert '"id" = :1' in sql

    def test_delete_without_key_raises(self):
        schema = [{"name": "a", "type": "int", "key": False}]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        with pytest.raises(ConfigurationError):
            comp._build_delete_sql()


# ----------------------------------------------------------------------
# TestFieldOptions: per-column UPDATE_KEY / UPDATABLE / INSERTABLE
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestFieldOptionsUpdateKey:
    def test_field_options_drives_where_clause(self):
        cfg = _shared_conn_config(
            data_action="UPDATE",
            use_field_options=True,
            field_options=[
                {"column": "id", "update_key": False, "updatable": True, "insertable": True},
                {"column": "name", "update_key": True, "updatable": False, "insertable": True},
            ],
        )
        # output_schema 'key' attr is now ignored in favor of field_options
        comp = _make_component(cfg)
        sql = comp._build_update_sql()
        # 'name' is the UPDATE_KEY -> in WHERE; 'id' is updatable -> in SET
        assert '"id" = :1' in sql  # SET
        assert "WHERE" in sql
        assert '"name" = :2' in sql  # WHERE

    def test_field_options_without_update_key_falls_to_schema_key(self):
        # use_field_options=False -> falls back to schema 'key' attribute
        comp = _make_component(_shared_conn_config(data_action="UPDATE"))
        sql = comp._build_update_sql()
        # 'id' has key=True in default schema; 'name' is updatable
        assert '"name" = :1' in sql
        assert '"id" = :2' in sql


@pytest.mark.unit
class TestFieldOptionsUpdatable:
    def test_updatable_false_omitted_from_set(self):
        cfg = _shared_conn_config(
            data_action="UPDATE",
            use_field_options=True,
            field_options=[
                {"column": "id", "update_key": True, "updatable": False, "insertable": True},
                {"column": "name", "update_key": False, "updatable": False, "insertable": True},
                {"column": "age", "update_key": False, "updatable": True, "insertable": True},
            ],
        )
        schema = [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "str", "length": 50},
            {"name": "age", "type": "int"},
        ]
        comp = _make_component(cfg, output_schema=schema)
        sql = comp._build_update_sql()
        assert '"age"' in sql
        # 'name' updatable=False -> NOT in SET
        # check 'name' only appears as nothing (it's not in updatable, not key)
        assert '"name" = ' not in sql


@pytest.mark.unit
class TestFieldOptionsInsertable:
    def test_insertable_false_omitted_from_insert_cols(self):
        cfg = _shared_conn_config(
            data_action="INSERT",
            use_field_options=True,
            field_options=[
                {"column": "id", "update_key": False, "updatable": True, "insertable": True},
                {"column": "name", "update_key": False, "updatable": True, "insertable": False},
                {"column": "age", "update_key": False, "updatable": True, "insertable": True},
            ],
        )
        schema = [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "str", "length": 50},
            {"name": "age", "type": "int"},
        ]
        comp = _make_component(cfg, output_schema=schema)
        sql = comp._build_insert_sql()
        assert '"id"' in sql and '"age"' in sql
        # 'name' insertable=False -> NOT in INSERT col list
        assert '"name"' not in sql


# ----------------------------------------------------------------------
# TestExecuteMany + RejectFlow + DieOnError + StatKeys
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestExecuteManyAndRejectFlow:
    def test_executemany_called_with_batcherrors_true(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr)
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        comp._process(df)
        args, kwargs = mock_cursor.executemany.call_args
        assert kwargs.get("batcherrors") is True

    def test_no_executemany_when_input_empty(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr)
        df = pd.DataFrame({"id": [], "name": []})
        comp._process(df)
        mock_cursor.executemany.assert_not_called()

    def test_no_executemany_when_input_none(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr)
        comp._process(None)
        mock_cursor.executemany.assert_not_called()

    def test_reject_chunk_schema_and_format(self):
        err1 = MagicMock()
        err1.code = 1
        err1.message = "ORA-00001: unique constraint violated"
        err1.offset = 2
        err2 = MagicMock()
        err2.code = 2291
        err2.message = "parent key not found"
        err2.offset = 3
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(
            batch_errors=[err1, err2]
        )
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr)
        df = pd.DataFrame({"id": [10, 11, 12, 13], "name": ["a", "b", "c", "d"]})
        result = comp._process(df)
        reject = result["reject"]
        assert reject is not None
        assert list(reject.columns)[:2] == ["errorCode", "errorMessage"]
        assert "id" in reject.columns
        assert "name" in reject.columns
        assert reject.iloc[0]["errorCode"] == "1"
        assert "Line: 2" in reject.iloc[0]["errorMessage"]
        assert reject.iloc[1]["errorCode"] == "2291"

    def test_no_reject_when_no_batch_errors(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(batch_errors=[])
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr)
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        result = comp._process(df)
        assert result["reject"] is None


@pytest.mark.unit
class TestStatKeys:
    def test_all_five_keys_present_for_insert(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        gm = GlobalMap()
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr, global_map=gm)
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        comp._process(df)
        assert gm.get("tOracleOutput_1_NB_LINE") == 3
        assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 3
        assert gm.get("tOracleOutput_1_NB_LINE_UPDATED") == 0
        assert gm.get("tOracleOutput_1_NB_LINE_DELETED") == 0
        assert gm.get("tOracleOutput_1_NB_LINE_REJECTED") == 0

    def test_stat_keys_for_update(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        gm = GlobalMap()
        comp = _make_component(
            _shared_conn_config(data_action="UPDATE"),
            oracle_manager=mgr, global_map=gm,
        )
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        comp._process(df)
        assert gm.get("tOracleOutput_1_NB_LINE_UPDATED") == 2
        assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 0

    def test_stat_keys_for_delete(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        gm = GlobalMap()
        comp = _make_component(
            _shared_conn_config(data_action="DELETE"),
            oracle_manager=mgr, global_map=gm,
        )
        df = pd.DataFrame({"id": [1, 2]})
        comp._process(df)
        assert gm.get("tOracleOutput_1_NB_LINE_DELETED") == 2
        assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 0

    def test_rejected_count_in_stats(self):
        err = MagicMock()
        err.code = 1
        err.message = "dup"
        err.offset = 0
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(batch_errors=[err])
        gm = GlobalMap()
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr, global_map=gm)
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        comp._process(df)
        # 1 reject, 1 ok
        assert gm.get("tOracleOutput_1_NB_LINE_REJECTED") == 1
        assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 1

    def test_zero_stats_when_input_empty(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        gm = GlobalMap()
        comp = _make_component(_shared_conn_config(), oracle_manager=mgr, global_map=gm)
        comp._process(None)
        assert gm.get("tOracleOutput_1_NB_LINE") == 0
        assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 0


@pytest.mark.unit
class TestCommitCycle:
    def test_commit_called_per_commit_every_threshold(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(
            _shared_conn_config(commit_every=2, batch_size=2),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2, 3, 4], "name": ["a", "b", "c", "d"]})
        comp._process(df)
        # 4 rows / batch_size=2 = 2 chunks; commit_every=2 -> commit after each
        # plus a trailing commit if there's leftover (here none) -- so at least
        # 2 commits during loop. NONE table_action means no pre-commit.
        assert mock_conn.commit.call_count >= 2

    def test_trailing_partial_batch_committed(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(
            _shared_conn_config(commit_every=10, batch_size=2),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        comp._process(df)
        # 3 rows < commit_every=10, but trailing partial commit fires in finally
        assert mock_conn.commit.call_count >= 1


@pytest.mark.unit
class TestDieOnErrorRewrap:
    def test_die_on_error_with_rejects_raises(self):
        err = MagicMock()
        err.code = 1
        err.message = "dup"
        err.offset = 0
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(batch_errors=[err])
        comp = _make_component(
            _shared_conn_config(die_on_error=True), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with pytest.raises(DataValidationError):
            comp._process(df)

    def test_die_on_error_false_does_not_raise(self):
        err = MagicMock()
        err.code = 1
        err.message = "dup"
        err.offset = 0
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(batch_errors=[err])
        comp = _make_component(
            _shared_conn_config(die_on_error=False), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        # No raise; result has reject DataFrame
        result = comp._process(df)
        assert result["reject"] is not None

    def test_die_on_error_does_not_rollback_prior_commits(self):
        """WR-01 regression: die_on_error fires AFTER the commit cycle.

        Talend tOracleOutput parity: prior batches that completed successfully
        within the COMMIT_EVERY cycle have already been committed to the DB.
        die_on_error then aborts the job, but does NOT issue conn.rollback()
        -- those committed rows stay in the table. This locks behavior so a
        future "fix" that adds rollback() doesn't silently diverge from
        Talend semantics.
        """
        err = MagicMock()
        err.code = 1
        err.message = "dup"
        err.offset = 0
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(batch_errors=[err])
        comp = _make_component(
            _shared_conn_config(die_on_error=True), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with pytest.raises(DataValidationError):
            comp._process(df)
        # Talend-parity: do NOT auto-rollback; operator's COMMIT_EVERY choice
        # is the all-or-nothing knob.
        assert mock_conn.rollback.call_count == 0


# ----------------------------------------------------------------------
# Plan 11-05: Upsert (INSERT_OR_UPDATE / UPDATE_OR_INSERT) test classes
# Supersedes plan 11-04's deferred-upsert placeholder class (NotImplementedError stubs).
# Strategy per D-C2: SELECT pk_cols WHERE pk IN (batch_keys) ->
# partition matched/unmatched -> executemany UPDATE on matched +
# executemany INSERT on unmatched.
# ----------------------------------------------------------------------


def _make_upsert_mock_manager(matched_keys=None, update_errors=None,
                              insert_errors=None, autocommit=False):
    """Build a manager + cursor for upsert tests.

    Sequencing (per _execute_upsert_batch):
      1. cursor.execute(SELECT pk_cols ...)  <- matched_keys returned by fetchall()
      2. cursor.executemany(UPDATE, matched) [optional]
      3. cursor.executemany(INSERT, unmatched) [optional]

    For getbatcherrors side_effect ordering:
      - call 1 -> update_errors (after UPDATE executemany)
      - call 2 -> insert_errors (after INSERT executemany)
    Defaults to no errors on either branch.
    """
    mgr = MagicMock()
    mock_conn = MagicMock(autocommit=autocommit)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = list(matched_keys or [])
    upd = list(update_errors or [])
    ins = list(insert_errors or [])
    mock_cursor.getbatcherrors.side_effect = [upd, ins]
    mock_conn.cursor.return_value = mock_cursor
    mgr.get.return_value = mock_conn
    mgr.open_ad_hoc.return_value = mock_conn
    return mgr, mock_conn, mock_cursor


@pytest.mark.unit
class TestUpsertBatched:
    def test_5_rows_2_matched_3_unmatched_stats_split(self):
        # 2 matched (ids 2 and 4), 3 unmatched
        mgr, _, _ = _make_upsert_mock_manager(matched_keys=[(2,), (4,)])
        gm = GlobalMap()
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"),
            oracle_manager=mgr, global_map=gm,
        )
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]})
        comp._process(df)
        assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 3
        assert gm.get("tOracleOutput_1_NB_LINE_UPDATED") == 2
        assert gm.get("tOracleOutput_1_NB_LINE_REJECTED") == 0
        assert gm.get("tOracleOutput_1_NB_LINE") == 5


@pytest.mark.unit
class TestUpsertSingleSelect:
    def test_select_executed_once_per_batch(self):
        mgr, _, mock_cursor = _make_upsert_mock_manager(matched_keys=[])
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        comp._process(df)
        # Exactly ONE cursor.execute -- the SELECT-existing query
        assert mock_cursor.execute.call_count == 1
        sql = mock_cursor.execute.call_args.args[0]
        assert sql.startswith("SELECT")
        assert "IN (" in sql

    def test_select_uses_parameterized_binds_not_concat(self):
        """T-11-01 mitigation regression: malicious-looking PK string must
        flow through binds, never inline in the SQL string."""
        mgr, _, mock_cursor = _make_upsert_mock_manager(matched_keys=[])
        # Schema with str id (so the malicious payload is a valid input)
        schema = [
            {"name": "id", "type": "str", "length": 50, "key": True, "nullable": False},
            {"name": "name", "type": "str", "length": 50, "nullable": True},
        ]
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"),
            oracle_manager=mgr, output_schema=schema,
        )
        df = pd.DataFrame({"id": ["1; DROP TABLE EMP", "2"], "name": ["a", "b"]})
        comp._process(df)
        sql = mock_cursor.execute.call_args.args[0]
        # SQL string must NOT contain the payload literally
        assert "DROP TABLE" not in sql
        # Binds list must contain it
        binds = mock_cursor.execute.call_args.args[1]
        assert "1; DROP TABLE EMP" in binds


@pytest.mark.unit
class TestUpsertExecuteManyOnce:
    def test_update_and_insert_each_called_once(self):
        # 1 matched, 2 unmatched -> 1 UPDATE executemany + 1 INSERT executemany
        mgr, _, mock_cursor = _make_upsert_mock_manager(matched_keys=[(2,)])
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        comp._process(df)
        assert mock_cursor.executemany.call_count == 2


@pytest.mark.unit
class TestUpsertSinglePk:
    def test_select_sql_uses_in_list(self):
        mgr, _, mock_cursor = _make_upsert_mock_manager(matched_keys=[])
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        comp._process(df)
        sql = mock_cursor.execute.call_args.args[0]
        assert '"id" IN (' in sql
        assert ":1" in sql and ":2" in sql and ":3" in sql


@pytest.mark.unit
class TestUpsertCompositePk:
    def test_select_sql_uses_or_chain(self):
        mgr, _, mock_cursor = _make_upsert_mock_manager(matched_keys=[])
        schema = [
            {"name": "pk1", "type": "int", "key": True, "nullable": False},
            {"name": "pk2", "type": "str", "length": 10, "key": True, "nullable": False},
            {"name": "v", "type": "str", "length": 50, "nullable": True},
        ]
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"),
            oracle_manager=mgr, output_schema=schema,
        )
        df = pd.DataFrame({"pk1": [1, 2], "pk2": ["a", "b"], "v": ["x", "y"]})
        comp._process(df)
        sql = mock_cursor.execute.call_args.args[0]
        assert " OR " in sql
        assert '"pk1" = :' in sql
        assert '"pk2" = :' in sql


@pytest.mark.unit
class TestUpsertEmptyMatched:
    def test_no_update_call_when_no_matches(self):
        mgr, _, mock_cursor = _make_upsert_mock_manager(matched_keys=[])
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        comp._process(df)
        # All rows go to INSERT only
        assert mock_cursor.executemany.call_count == 1


@pytest.mark.unit
class TestUpsertEmptyUnmatched:
    def test_no_insert_call_when_all_match(self):
        mgr, _, mock_cursor = _make_upsert_mock_manager(matched_keys=[(1,), (2,)])
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        comp._process(df)
        # All rows go to UPDATE only
        assert mock_cursor.executemany.call_count == 1


@pytest.mark.unit
class TestUpsertNullPk:
    def test_null_pk_forced_to_insert_with_warning(self, caplog):
        mgr, _, _ = _make_upsert_mock_manager(matched_keys=[])
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"), oracle_manager=mgr,
        )
        # id schema is non-nullable but the test values include None for one row;
        # use a nullable-id schema to permit the test scenario.
        comp.output_schema = [
            {"name": "id", "type": "int", "key": True, "nullable": True},
            {"name": "name", "type": "str", "length": 50, "nullable": True},
        ]
        df = pd.DataFrame({"id": [None, 1], "name": ["null_pk", "ok"]})
        import logging as _lg
        with caplog.at_level(_lg.WARNING):
            comp._process(df)
        assert any("NULL primary key" in rec.getMessage() for rec in caplog.records)


@pytest.mark.unit
class TestUpsertRejectMerging:
    def test_reject_df_consolidates_update_and_insert_errors(self):
        # 2 matched, 3 unmatched. UPDATE produces 1 BatchError; INSERT
        # produces 1 BatchError. Reject DataFrame should have 2 rows total.
        update_err = MagicMock()
        update_err.code = 2291
        update_err.message = "parent key not found"
        update_err.offset = 0
        insert_err = MagicMock()
        insert_err.code = 1
        insert_err.message = "unique constraint violated"
        insert_err.offset = 1
        mgr, _, _ = _make_upsert_mock_manager(
            matched_keys=[(2,), (4,)],
            update_errors=[update_err],
            insert_errors=[insert_err],
        )
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"), oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]})
        result = comp._process(df)
        reject = result["reject"]
        assert reject is not None
        assert len(reject) == 2
        assert "errorCode" in reject.columns
        assert "errorMessage" in reject.columns
        assert "id" in reject.columns
        codes = sorted(reject["errorCode"].tolist())
        assert codes == ["1", "2291"]


@pytest.mark.unit
class TestUpsertNoPkRaises:
    def test_no_key_column_raises_configuration_error(self):
        mgr, _, _ = _make_upsert_mock_manager(matched_keys=[])
        schema = [
            {"name": "x", "type": "int", "key": False, "nullable": True},
            {"name": "y", "type": "str", "length": 10, "nullable": True},
        ]
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"),
            oracle_manager=mgr, output_schema=schema,
        )
        with pytest.raises(ConfigurationError) as exc:
            comp._process(pd.DataFrame({"x": [1], "y": ["a"]}))
        assert "primary key" in str(exc.value).lower()


@pytest.mark.unit
class TestUpsertPreferUpdateVsInsert:
    def test_same_partition_for_both_data_actions(self):
        """INSERT_OR_UPDATE and UPDATE_OR_INSERT produce identical
        matched/unmatched stats; only the prefer_update flag differs and
        only affects log wording."""
        for da in ("INSERT_OR_UPDATE", "UPDATE_OR_INSERT"):
            mgr, _, _ = _make_upsert_mock_manager(matched_keys=[(2,)])
            gm = GlobalMap()
            comp = _make_component(
                _shared_conn_config(data_action=da),
                oracle_manager=mgr, global_map=gm,
            )
            df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
            comp._process(df)
            assert gm.get("tOracleOutput_1_NB_LINE_UPDATED") == 1
            assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 2


# ----------------------------------------------------------------------
# TestConnectionAcquisition: shared (manager.get) vs ad-hoc (open_ad_hoc)
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestConnectionAcquisition:
    def test_shared_uses_manager_get(self):
        mgr, mock_conn, _ = _make_mock_oracle_manager()
        comp = _make_component(
            _shared_conn_config(use_existing_connection=True),
            oracle_manager=mgr,
        )
        comp._process(pd.DataFrame({"id": [1], "name": ["a"]}))
        mgr.get.assert_called_once_with("tOracleConnection_1")
        mgr.open_ad_hoc.assert_not_called()
        mgr.close.assert_not_called()  # shared conn is NOT owned

    def test_adhoc_uses_open_ad_hoc_and_closes(self):
        mgr, _, _ = _make_mock_oracle_manager()
        comp = _make_component(
            _shared_conn_config(use_existing_connection=False),
            oracle_manager=mgr,
        )
        comp._process(pd.DataFrame({"id": [1], "name": ["a"]}))
        mgr.open_ad_hoc.assert_called_once()
        mgr.close.assert_called_once_with("tOracleOutput_1")

    def test_oracle_manager_not_wired_raises(self):
        comp = _make_component(_shared_conn_config())
        comp.oracle_manager = None
        with pytest.raises(ConfigurationError):
            comp._process(pd.DataFrame({"id": [1]}))


# ----------------------------------------------------------------------
# TestUseTimestampForDateType (D-B1)
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestUseTimestampForDateType:
    def test_default_true_emits_timestamp_in_ddl(self):
        schema = [{"name": "ts", "type": "datetime"}]
        comp = _make_component(_shared_conn_config(table_action="CREATE"), output_schema=schema)
        sql = comp._build_create_sql()
        assert "TIMESTAMP" in sql
        assert " DATE " not in sql

    def test_false_emits_date_in_ddl(self):
        schema = [{"name": "ts", "type": "datetime"}]
        comp = _make_component(
            _shared_conn_config(table_action="CREATE", use_timestamp_for_date_type=False),
            output_schema=schema,
        )
        sql = comp._build_create_sql()
        assert "DATE" in sql
        assert "TIMESTAMP" not in sql


# ----------------------------------------------------------------------
# TestRejectChunkBuilder: schema preservation and offset edge cases
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestRejectChunkBuilder:
    def test_reject_columns_match_input_plus_error_cols(self):
        err = MagicMock()
        err.code = 1
        err.message = "x"
        err.offset = 0
        comp = _make_component(_shared_conn_config())
        df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        out = comp._build_reject_chunk(df, [err])
        assert list(out.columns) == ["errorCode", "errorMessage", "a", "b", "c"]

    def test_reject_offset_out_of_range_does_not_raise(self):
        err = MagicMock()
        err.code = 1
        err.message = "x"
        err.offset = 99  # out of range
        comp = _make_component(_shared_conn_config())
        df = pd.DataFrame({"a": [1]})
        # Should not raise even with bogus offset; defensive fallback
        out = comp._build_reject_chunk(df, [err])
        assert len(out) == 1
        assert out.iloc[0]["errorCode"] == "1"

    def test_empty_batch_errors_returns_empty_df_with_columns(self):
        comp = _make_component(_shared_conn_config())
        df = pd.DataFrame({"a": [1], "b": [2]})
        out = comp._build_reject_chunk(df, [])
        assert len(out) == 0
        assert "errorCode" in out.columns
        assert "errorMessage" in out.columns


# ----------------------------------------------------------------------
# CR-02: Upsert refuses cleanly when PK column is marked insertable=False
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestUpsertNonInsertablePkRefused:
    """CR-02 regression: PK marked insertable=False under FIELD_OPTIONS used
    to crash with a confusing ``ValueError: 'pk' is not in list`` from
    list.index(); we now raise ConfigurationError up front with a clear
    remediation message.
    """

    def test_pk_not_insertable_raises_configuration_error(self):
        cfg = _shared_conn_config(
            data_action="INSERT_OR_UPDATE",
            use_field_options=True,
            field_options=[
                # 'id' is the PK (update_key=True) but insertable=False
                # (e.g. sequence-populated PK pattern)
                {"column": "id", "update_key": True, "updatable": False, "insertable": False},
                {"column": "name", "update_key": False, "updatable": True, "insertable": True},
            ],
        )
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "name", "type": "str", "length": 50, "nullable": True},
        ]
        mgr, _, _ = _make_upsert_mock_manager(matched_keys=[])
        comp = _make_component(cfg, output_schema=schema, oracle_manager=mgr)
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        with pytest.raises(ConfigurationError) as excinfo:
            comp._process(df)
        # Sanity: error mentions the offending column AND the remediation
        msg = str(excinfo.value)
        assert "id" in msg
        assert "insertable" in msg.lower()

    def test_update_or_insert_also_refused(self):
        cfg = _shared_conn_config(
            data_action="UPDATE_OR_INSERT",
            use_field_options=True,
            field_options=[
                {"column": "id", "update_key": True, "updatable": False, "insertable": False},
                {"column": "name", "update_key": False, "updatable": True, "insertable": True},
            ],
        )
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "name", "type": "str", "length": 50, "nullable": True},
        ]
        mgr, _, _ = _make_upsert_mock_manager(matched_keys=[])
        comp = _make_component(cfg, output_schema=schema, oracle_manager=mgr)
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with pytest.raises(ConfigurationError):
            comp._process(df)


# ----------------------------------------------------------------------
# Plan 14-04 Coverage Lift: rare matrix corners + ConfigurationError branches.
# Targets oracle_output.py missed lines: 156, 426, 451, 504, 665, 794, 810-821,
# 910-912, 919, 1042-1048. (Lines 784-785 are the optional-import shim, allowed
# pragma per D-C3 but not currently tagged; we cover via direct invocation.)
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestDdlTypeMappingByteAndBlob:
    """Cover line 156 (byte -> NUMBER(3)) and the DEFAULT-fallback path."""

    def test_byte_maps_to_number_3(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )
        assert _column_to_oracle_type({"type": "byte"}, True) == "NUMBER(3)"

    def test_bytes_blob_when_no_length(self):
        from src.v1.engine.components.database.oracle_output import (
            _column_to_oracle_type,
        )
        # No length -> BLOB (covers the bytes branch fallback for line 180)
        assert _column_to_oracle_type({"type": "bytes"}, True) == "BLOB"


@pytest.mark.unit
class TestEmptyInsertableUpdatable:
    """Cover lines 426 (no insertable cols) and 451 (no updatable cols)."""

    def test_insert_with_no_insertable_columns_raises(self):
        cfg = _shared_conn_config(
            data_action="INSERT",
            use_field_options=True,
            field_options=[
                {"column": "id", "update_key": False, "updatable": False, "insertable": False},
                {"column": "name", "update_key": False, "updatable": False, "insertable": False},
            ],
        )
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError) as exc:
            comp._build_insert_sql()
        assert "insertable" in str(exc.value).lower()

    def test_update_with_no_updatable_columns_raises(self):
        # All schema columns are keys; nothing updatable.
        schema = [
            {"name": "a", "type": "int", "key": True, "nullable": False},
            {"name": "b", "type": "int", "key": True, "nullable": False},
        ]
        comp = _make_component(
            _shared_conn_config(data_action="UPDATE"), output_schema=schema,
        )
        with pytest.raises(ConfigurationError) as exc:
            comp._build_update_sql()
        assert "updatable" in str(exc.value).lower()

    def test_pk_select_empty_pk_raises(self):
        """Cover line 504: _build_pk_select_sql with empty pk_cols."""
        comp = _make_component(_shared_conn_config())
        with pytest.raises(ConfigurationError) as exc:
            comp._build_pk_select_sql([], 5)
        assert "primary key" in str(exc.value).lower()


@pytest.mark.unit
class TestUpsertScalarFetchallRow:
    """Cover line 665: matched_keys.add((row,)) when fetchall returns scalars
    (some drivers / configurations return raw scalar values for single-column
    SELECTs instead of tuples)."""

    def test_scalar_fetchall_rows_wrapped_into_singleton_tuples(self):
        mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock()
        # Return scalars rather than (val,) tuples -- drivers vary on this.
        mock_cursor.fetchall.return_value = [2, 4]
        # getbatcherrors is called once for UPDATE then once for INSERT.
        mock_cursor.getbatcherrors.side_effect = [[], []]
        mock_conn.cursor.return_value = mock_cursor
        mgr.get.return_value = mock_conn
        gm = GlobalMap()
        comp = _make_component(
            _shared_conn_config(data_action="INSERT_OR_UPDATE"),
            oracle_manager=mgr, global_map=gm,
        )
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]})
        comp._process(df)
        # 2 matched (ids 2 and 4) via the scalar wrapping path.
        assert gm.get("tOracleOutput_1_NB_LINE_UPDATED") == 2
        assert gm.get("tOracleOutput_1_NB_LINE_INSERTED") == 3


@pytest.mark.unit
class TestBuildInputSizes:
    """Cover lines 794, 810-821 in _build_input_sizes type-mapping branches.

    Each oracledb constant is asserted via attribute lookup so the test is
    resilient to the actual oracledb module's type-class identities.
    """

    def test_unknown_data_action_returns_empty(self):
        # Line 794: data_action not in (INSERT/UPDATE/DELETE) -> []
        comp = _make_component(_shared_conn_config())
        assert comp._build_input_sizes("BOGUS") == []

    def test_str_long_maps_to_db_type_clob(self):
        # Line 810: str length > 4000 -> oracledb.DB_TYPE_CLOB
        import oracledb
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "big", "type": "str", "length": 8000, "nullable": True},
        ]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        sizes = comp._build_input_sizes("INSERT")
        assert sizes[1] is oracledb.DB_TYPE_CLOB

    def test_str_no_length_maps_to_db_type_clob(self):
        # Line 810: str without length -> CLOB
        import oracledb
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "txt", "type": "str", "nullable": True},
        ]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        sizes = comp._build_input_sizes("INSERT")
        assert sizes[1] is oracledb.DB_TYPE_CLOB

    def test_datetime_maps_to_timestamp_when_use_ts(self):
        # Line 812: datetime with use_timestamp_for_date_type=True
        import oracledb
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "ts", "type": "datetime", "nullable": True},
        ]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        sizes = comp._build_input_sizes("INSERT")
        assert sizes[1] is oracledb.DB_TYPE_TIMESTAMP

    def test_datetime_maps_to_date_when_use_ts_false(self):
        # Line 812: datetime with use_timestamp_for_date_type=False
        import oracledb
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "d", "type": "datetime", "nullable": True},
        ]
        cfg = _shared_conn_config(use_timestamp_for_date_type=False)
        comp = _make_component(cfg, output_schema=schema)
        sizes = comp._build_input_sizes("INSERT")
        assert sizes[1] is oracledb.DB_TYPE_DATE

    def test_bytes_short_maps_to_db_type_raw(self):
        # Line 815-817: bytes with small length -> DB_TYPE_RAW
        import oracledb
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "blob", "type": "bytes", "length": 200, "nullable": True},
        ]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        sizes = comp._build_input_sizes("INSERT")
        assert sizes[1] is oracledb.DB_TYPE_RAW

    def test_bytes_long_maps_to_db_type_blob(self):
        # Line 819: bytes without length / length > 2000 -> DB_TYPE_BLOB
        import oracledb
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "lob", "type": "bytes", "nullable": True},
        ]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        sizes = comp._build_input_sizes("INSERT")
        assert sizes[1] is oracledb.DB_TYPE_BLOB

    def test_unknown_type_appends_none(self):
        # Line 821: unknown ctype -> None placeholder
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "weird", "type": "mystery", "nullable": True},
        ]
        comp = _make_component(_shared_conn_config(), output_schema=schema)
        sizes = comp._build_input_sizes("INSERT")
        assert sizes[1] is None


@pytest.mark.unit
class TestUseBatchSizeFalse:
    """Cover lines 910-912: use_batch_size=False treats whole DF as one batch."""

    def test_whole_df_is_single_batch_when_use_batch_size_false(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(
            _shared_conn_config(use_batch_size=False, batch_size=2),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]})
        comp._process(df)
        # batch_size honors len(df) -- one executemany call covers all rows.
        assert mock_cursor.executemany.call_count == 1
        # Verify second positional arg (the rows list) has all 5 rows.
        rows_arg = mock_cursor.executemany.call_args.args[1]
        assert len(rows_arg) == 5

    def test_use_batch_size_false_with_none_input_does_not_error(self):
        # Line 910 fallback -- when input_data is None, batch_size=10000.
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(
            _shared_conn_config(use_batch_size=False),
            oracle_manager=mgr,
        )
        # No raise; no executemany either (None input skips DML).
        comp._process(None)
        mock_cursor.executemany.assert_not_called()

    def test_use_batch_size_false_with_empty_df_falls_back_to_10000(self):
        """Cover line 912: empty DataFrame -> batch_size <= 0 -> reset to 10000.

        Empty DF with use_batch_size=False produces batch_size=0 from len(df);
        the defensive ``if batch_size <= 0`` guard rewrites to 10000 so the
        loop range step is well-defined (even though the loop body never runs
        because len(rows)==0 -> range(0,0,10000) is empty).
        """
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager()
        comp = _make_component(
            _shared_conn_config(use_batch_size=False),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [], "name": []})
        comp._process(df)
        # No DML rows -> no executemany call.
        mock_cursor.executemany.assert_not_called()


@pytest.mark.unit
class TestPreCommitAfterTableAction:
    """Cover line 919: post-table-action commit when action != NONE and
    autocommit is False."""

    def test_commit_after_create_when_autocommit_false(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(autocommit=False)
        comp = _make_component(
            _shared_conn_config(table_action="CREATE", data_action="INSERT"),
            oracle_manager=mgr,
        )
        # Empty DF -> no DML commit cycle -> the only commit is the post-DDL one.
        df = pd.DataFrame({"id": [], "name": []})
        comp._process(df)
        # Must have committed at least once -- the post-DDL commit on line 919.
        assert mock_conn.commit.call_count >= 1

    def test_no_pre_commit_when_table_action_none(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(autocommit=False)
        comp = _make_component(
            _shared_conn_config(table_action="NONE", data_action="INSERT"),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [], "name": []})
        comp._process(df)
        # No DDL, no rows -> NO commits at all (commit is gated on
        # since_commit > 0, which is 0 here).
        assert mock_conn.commit.call_count == 0

    def test_no_pre_commit_when_autocommit_true(self):
        mgr, mock_conn, mock_cursor = _make_mock_oracle_manager(autocommit=True)
        comp = _make_component(
            _shared_conn_config(table_action="CREATE"),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [], "name": []})
        comp._process(df)
        # autocommit=True -> the "and not autocommit" guard skips line 919.
        assert mock_conn.commit.call_count == 0


@pytest.mark.unit
class TestCleanupSwallowsErrors:
    """Cover lines 1042-1043 (cursor.close raise) + 1047-1048 (manager.close raise)."""

    def test_cursor_close_failure_logged_not_raised(self, caplog):
        import logging as _lg
        mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock()
        mock_cursor.close.side_effect = RuntimeError("cursor close exploded")
        mock_cursor.getbatcherrors.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mgr.open_ad_hoc.return_value = mock_conn
        comp = _make_component(
            _shared_conn_config(use_existing_connection=False),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with caplog.at_level(_lg.WARNING):
            # Must NOT raise -- cleanup error swallowed.
            comp._process(df)
        assert any(
            "cursor.close() raised" in rec.getMessage() for rec in caplog.records
        )

    def test_manager_close_failure_logged_not_raised(self, caplog):
        import logging as _lg
        mgr = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_cursor = MagicMock()
        mock_cursor.getbatcherrors.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mgr.open_ad_hoc.return_value = mock_conn
        mgr.close.side_effect = RuntimeError("manager close exploded")
        comp = _make_component(
            _shared_conn_config(use_existing_connection=False),
            oracle_manager=mgr,
        )
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with caplog.at_level(_lg.WARNING):
            comp._process(df)
        assert any(
            "oracle_manager.close() raised" in rec.getMessage()
            for rec in caplog.records
        )


@pytest.mark.unit
class TestReservedWordIdentifierQuoting:
    """T-11-04: reserved-word column names like GROUP must round-trip via the
    double-quote wrapper. Oracle treats double-quoted identifiers as
    case-sensitive so we get correct DDL even for reserved words.
    """

    def test_group_column_name_quoted_in_create_sql(self):
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "GROUP", "type": "str", "length": 50, "nullable": True},
        ]
        comp = _make_component(
            _shared_conn_config(table_action="CREATE"),
            output_schema=schema,
        )
        sql = comp._build_create_sql()
        # Reserved word survives via double-quote wrapping.
        assert '"GROUP"' in sql

    def test_reserved_word_in_insert_sql(self):
        schema = [
            {"name": "id", "type": "int", "key": True, "nullable": False},
            {"name": "ORDER", "type": "str", "length": 50, "nullable": True},
        ]
        comp = _make_component(
            _shared_conn_config(data_action="INSERT"),
            output_schema=schema,
        )
        sql = comp._build_insert_sql()
        assert '"ORDER"' in sql
