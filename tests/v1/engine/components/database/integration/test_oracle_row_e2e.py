"""E2E tests for tOracleRow against gvenzl/oracle-free testcontainer.

Phase 11-07. @pytest.mark.oracle. Covers:
  VR-04 (in-scope CT works against real DB)
  VR-05 partial (prepared-statement type round-trip subset; full 16-type matrix
                 lives in test_oracle_output_e2e.py for economy)
  USE_NB_LINE counter against real cursor.rowcount (D-C5)
  PROPAGATE_RECORD_SET refusal (D-C4)
"""
import datetime
from decimal import Decimal

import pytest

from src.v1.engine.components.database.oracle_row import OracleRow
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.oracle_connection_manager import OracleConnectionManager


pytestmark = pytest.mark.oracle


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _make_row_component(
    query,
    oracle_manager,
    *,
    use_nb_line="NONE",
    connection_ref=None,
    prepared_params=None,
    extra_cfg=None,
):
    """Build an OracleRow seeded with config (skip BaseComponent.execute lifecycle)."""
    cfg = {
        "use_existing_connection": connection_ref is not None,
        "connection": connection_ref or "",
        "query": query,
        "use_nb_line": use_nb_line,
    }
    if prepared_params is not None:
        cfg["use_preparedstatement"] = True
        cfg["set_preparedstatement_parameters"] = prepared_params
    if extra_cfg:
        cfg.update(extra_cfg)
    comp = OracleRow(
        component_id="tOracleRow_1",
        config=cfg,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    comp.config = dict(cfg)
    comp.oracle_manager = oracle_manager
    return comp


# ----------------------------------------------------------------------
# DDL + DML real-cursor.rowcount validation
# ----------------------------------------------------------------------


class TestRealDdlAndDml:
    """VR-04 + USE_NB_LINE counter behaviour against real cursor.rowcount."""

    def test_ddl_create_table(self, oracle_connection, temp_table, caplog):
        """DDL emits cursor.rowcount<0; counter writes 0 and a WARNING is logged."""
        import logging as _lg

        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            comp = _make_row_component(
                f'CREATE TABLE "{temp_table}" (id NUMBER(10) PRIMARY KEY, '
                f'name VARCHAR2(50 CHAR))',
                mgr,
                connection_ref="c1",
                use_nb_line="NB_LINE_INSERTED",
            )
            with caplog.at_level(_lg.WARNING):
                comp._process(None)

            # Verify table exists (DDL ran).
            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{temp_table}"')
                assert cur.fetchone()[0] == 0
            finally:
                cur.close()

            # DDL rowcount<0 -> counter is 0 + WARNING logged.
            assert comp.global_map.get("tOracleRow_1_NB_LINE_INSERTED") == 0
            assert any(
                "DDL or unknown" in rec.getMessage() for rec in caplog.records
            )
        finally:
            mgr.stop()

    def test_dml_insert_increments_counter(self, oracle_connection, temp_table):
        cur = oracle_connection.cursor()
        cur.execute(
            f'CREATE TABLE "{temp_table}" (id NUMBER(10), name VARCHAR2(50 CHAR))'
        )
        oracle_connection.commit()
        cur.close()

        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            comp = _make_row_component(
                f'INSERT INTO "{temp_table}" (id, name) VALUES (1, \'a\')',
                mgr,
                connection_ref="c1",
                use_nb_line="NB_LINE_INSERTED",
            )
            comp._process(None)
            assert comp.global_map.get("tOracleRow_1_NB_LINE_INSERTED") == 1
        finally:
            mgr.stop()

    def test_dml_update_increments_counter(self, oracle_connection, temp_table):
        cur = oracle_connection.cursor()
        cur.execute(
            f'CREATE TABLE "{temp_table}" (id NUMBER(10), name VARCHAR2(50 CHAR))'
        )
        cur.execute(f'INSERT INTO "{temp_table}" VALUES (1, \'old\')')
        cur.execute(f'INSERT INTO "{temp_table}" VALUES (2, \'old\')')
        oracle_connection.commit()
        cur.close()

        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            comp = _make_row_component(
                f'UPDATE "{temp_table}" SET name = \'new\' WHERE id IN (1, 2)',
                mgr,
                connection_ref="c1",
                use_nb_line="NB_LINE_UPDATED",
            )
            comp._process(None)
            assert comp.global_map.get("tOracleRow_1_NB_LINE_UPDATED") == 2
        finally:
            mgr.stop()

    def test_dml_delete_increments_counter(self, oracle_connection, temp_table):
        cur = oracle_connection.cursor()
        cur.execute(
            f'CREATE TABLE "{temp_table}" (id NUMBER(10), name VARCHAR2(50 CHAR))'
        )
        cur.execute(f'INSERT INTO "{temp_table}" VALUES (1, \'a\')')
        cur.execute(f'INSERT INTO "{temp_table}" VALUES (2, \'b\')')
        cur.execute(f'INSERT INTO "{temp_table}" VALUES (3, \'c\')')
        oracle_connection.commit()
        cur.close()

        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            comp = _make_row_component(
                f'DELETE FROM "{temp_table}" WHERE id < 3',
                mgr,
                connection_ref="c1",
                use_nb_line="NB_LINE_DELETED",
            )
            comp._process(None)
            assert comp.global_map.get("tOracleRow_1_NB_LINE_DELETED") == 2
        finally:
            mgr.stop()


# ----------------------------------------------------------------------
# VR-05 partial: prepared-statement type round-trip
# ----------------------------------------------------------------------


class TestPreparedStatementRoundTrip:
    """VR-05 partial coverage: 4 representative bind types via real DB."""

    def test_prepared_statement_round_trip(self, oracle_connection, temp_table):
        cur = oracle_connection.cursor()
        cur.execute(
            f'CREATE TABLE "{temp_table}" '
            f'(id NUMBER(10), val_str VARCHAR2(50 CHAR), '
            f'val_dec NUMBER(10,2), val_ts TIMESTAMP)'
        )
        oracle_connection.commit()
        cur.close()

        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            params = [
                {"parameter_index": "1", "parameter_type": "Int",
                 "parameter_value": 7},
                {"parameter_index": "2", "parameter_type": "String",
                 "parameter_value": "hello"},
                {"parameter_index": "3", "parameter_type": "BigDecimal",
                 "parameter_value": "3.14"},
                {"parameter_index": "4", "parameter_type": "Timestamp",
                 "parameter_value": "2026-05-07T12:34:56"},
            ]
            comp = _make_row_component(
                f'INSERT INTO "{temp_table}" (id, val_str, val_dec, val_ts) '
                f'VALUES (:1, :2, :3, :4)',
                mgr,
                connection_ref="c1",
                prepared_params=params,
            )
            comp._process(None)

            cur = oracle_connection.cursor()
            try:
                cur.execute(
                    f'SELECT id, val_str, val_dec, val_ts FROM "{temp_table}"'
                )
                row = cur.fetchone()
            finally:
                cur.close()

            assert row[0] == 7
            assert row[1] == "hello"
            assert row[2] == Decimal("3.14")
            assert row[3] == datetime.datetime(2026, 5, 7, 12, 34, 56)
        finally:
            mgr.stop()

    def test_prepared_statement_null_bind(self, oracle_connection, temp_table):
        """PARAMETER_TYPE='Null' binds SQL NULL regardless of supplied value."""
        cur = oracle_connection.cursor()
        cur.execute(
            f'CREATE TABLE "{temp_table}" (id NUMBER(10), label VARCHAR2(50 CHAR))'
        )
        oracle_connection.commit()
        cur.close()

        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            params = [
                {"parameter_index": "1", "parameter_type": "Int",
                 "parameter_value": 9},
                # 'Null' coercer ignores the supplied value and binds SQL NULL.
                {"parameter_index": "2", "parameter_type": "Null",
                 "parameter_value": "ignored"},
            ]
            comp = _make_row_component(
                f'INSERT INTO "{temp_table}" (id, label) VALUES (:1, :2)',
                mgr,
                connection_ref="c1",
                prepared_params=params,
            )
            comp._process(None)

            cur = oracle_connection.cursor()
            try:
                cur.execute(
                    f'SELECT id, label FROM "{temp_table}" WHERE id = 9'
                )
                row = cur.fetchone()
            finally:
                cur.close()
            assert row[0] == 9
            assert row[1] is None
        finally:
            mgr.stop()


# ----------------------------------------------------------------------
# Refusals + shared-connection identity
# ----------------------------------------------------------------------


class TestPropagateRecordSetRefusal:
    """D-C4: PROPAGATE_RECORD_SET emits a live ResultSet to a downstream FLOW
    column; this Talend pattern doesn't translate cleanly to DataFrame
    semantics. tOracleRow refuses it after context resolution.
    """

    def test_propagate_record_set_raises(self, oracle_dsn):
        mgr = OracleConnectionManager()
        mgr.start()
        try:
            comp = OracleRow(
                component_id="tOracleRow_1",
                config={
                    "use_existing_connection": False,
                    "connection_type": "ORACLE_SERVICE_NAME",
                    "host": oracle_dsn["host"],
                    "port": str(oracle_dsn["port"]),
                    "dbname": oracle_dsn["service_name"],
                    "user": oracle_dsn["user"],
                    "password": oracle_dsn["password"],
                    "query": "SELECT 1 FROM dual",
                    "use_nb_line": "NONE",
                    "propagate_record_set": True,
                },
                global_map=GlobalMap(),
                context_manager=ContextManager(),
            )
            comp.config = dict(comp._original_config)
            comp.oracle_manager = mgr
            with pytest.raises(ConfigurationError) as exc:
                comp._process(None)
            # Error message must mention the refused param name.
            assert "PROPAGATE_RECORD_SET" in str(exc.value).upper().replace(" ", "_")
        finally:
            mgr.stop()


class TestUseExistingConnectionShares:
    """Verify use_existing_connection=true reuses the SAME oracledb.Connection
    that tOracleConnection registered.
    """

    def test_use_existing_connection_reuses_shared(self, oracle_connection):
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            # Verify the SESSIONID seen via the shared connection matches the
            # SESSIONID seen via mgr.get('c1') -- same session means same
            # oracledb.Connection.
            cur1 = oracle_connection.cursor()
            cur1.execute("SELECT SYS_CONTEXT('USERENV','SESSIONID') FROM dual")
            sid_direct = cur1.fetchone()[0]
            cur1.close()

            comp = _make_row_component(
                "SELECT 1 FROM dual",
                mgr,
                connection_ref="c1",
                use_nb_line="NONE",
            )
            # Confirm mgr.get returns the same Python object id.
            shared = mgr.get("c1")
            assert shared is oracle_connection

            cur2 = shared.cursor()
            cur2.execute("SELECT SYS_CONTEXT('USERENV','SESSIONID') FROM dual")
            sid_shared = cur2.fetchone()[0]
            cur2.close()
            assert sid_direct == sid_shared

            # Sanity: comp can run a cheap query through that shared conn.
            comp._process(None)
        finally:
            mgr.stop()
