"""E2E tests for tOracleOutput against gvenzl/oracle-free testcontainer.

Phase 11-07. @pytest.mark.oracle. Covers:
  VR-05: type round-trip across 6 type families (NUMBER/Decimal, DATE/datetime,
         TIMESTAMP/datetime, VARCHAR2/str, CLOB/str>4000 chars, BLOB/bytes)
  VR-06: REJECT path with batcherrors (ORA-00001 unique violation -> reject DF)
  VR-07: INSERT_OR_UPDATE batched 2-statement upsert (NB_LINE_UPDATED + INSERTED)
  VR-08: DDL emission for CREATE-family TABLE_ACTIONs (parametrized over 4
         actions: CREATE / CREATE_IF_NOT_EXISTS / DROP_CREATE /
         DROP_IF_EXISTS_AND_CREATE)
  USE_TIMESTAMP_FOR_DATE_TYPE: True preserves microseconds, False drops them
                               (D-B1)

Reject schema (D-C7): [errorCode, errorMessage, *input cols]
  errorCode    = str(BatchError.code)
  errorMessage = BatchError.message + " - Line: " + offset
"""
import datetime
import secrets
from decimal import Decimal

import pandas as pd
import pytest

from src.v1.engine.components.database.oracle_output import OracleOutput
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.oracle_connection_manager import OracleConnectionManager


pytestmark = pytest.mark.oracle


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _make_output(
    table,
    output_schema,
    oracle_manager,
    *,
    table_action="NONE",
    data_action="INSERT",
    connection_ref="c1",
    **extra_cfg,
):
    """Build an OracleOutput with config seeded directly (skip execute lifecycle).

    Mirror of tests/v1/engine/components/database/test_oracle_output.py:_make_component.
    """
    cfg = {
        "use_existing_connection": True,
        "connection": connection_ref,
        "table": table,
        "table_action": table_action,
        "data_action": data_action,
        "use_timestamp_for_date_type": True,
    }
    cfg.update(extra_cfg)
    comp = OracleOutput(
        component_id="tOracleOutput_1",
        config=cfg,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    comp.config = dict(cfg)
    comp.output_schema = output_schema
    comp.oracle_manager = oracle_manager
    return comp


# ----------------------------------------------------------------------
# VR-05: Type round-trip (6 type families)
# ----------------------------------------------------------------------


class TestTypeRoundTrip:
    """VR-05: each Talend type maps to an Oracle column type and round-trips
    losslessly through cursor.executemany insert + SELECT read-back.
    """

    def test_decimal_round_trip(self, oracle_connection, temp_table):
        """Decimal/NUMBER(p,s) preserves scale exactly via str-bridge coercion."""
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "v", "type": "Decimal", "length": 10, "precision": 2,
                 "key": True, "nullable": False},
            ]
            cur = oracle_connection.cursor()
            cur.execute(f'CREATE TABLE "{temp_table}" ("v" NUMBER(10,2) PRIMARY KEY)')
            oracle_connection.commit()
            cur.close()

            comp = _make_output(temp_table, schema, mgr, data_action="INSERT")
            df = pd.DataFrame({"v": [Decimal("3.14"), Decimal("2.71")]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "v" FROM "{temp_table}" ORDER BY "v"')
                rows = [r[0] for r in cur.fetchall()]
            finally:
                cur.close()
            assert rows == [Decimal("2.71"), Decimal("3.14")]
        finally:
            mgr.stop()

    def test_timestamp_round_trip(self, oracle_connection, temp_table):
        """datetime / TIMESTAMP preserves microsecond precision."""
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "ts", "type": "datetime", "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "ts" TIMESTAMP)'
            )
            oracle_connection.commit()
            cur.close()

            comp = _make_output(
                temp_table, schema, mgr, data_action="INSERT",
                use_timestamp_for_date_type=True,
            )
            ts_in = datetime.datetime(2026, 5, 7, 12, 34, 56, 123456)
            df = pd.DataFrame({"id": [1], "ts": [ts_in]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "ts" FROM "{temp_table}"')
                got = cur.fetchone()[0]
            finally:
                cur.close()
            assert got == ts_in

        finally:
            mgr.stop()

    def test_date_round_trip(self, oracle_connection, temp_table):
        """datetime / DATE drops sub-second precision (D-B1).

        With use_timestamp_for_date_type=False, the bind type is DB_TYPE_DATE
        and sub-second precision is dropped on insert.
        """
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "d", "type": "datetime", "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "d" DATE)'
            )
            oracle_connection.commit()
            cur.close()

            comp = _make_output(
                temp_table, schema, mgr, data_action="INSERT",
                use_timestamp_for_date_type=False,
            )
            ts_in = datetime.datetime(2026, 5, 7, 12, 34, 56, 999999)
            df = pd.DataFrame({"id": [1], "d": [ts_in]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "d" FROM "{temp_table}"')
                got = cur.fetchone()[0]
            finally:
                cur.close()
            # DATE type stores second-level precision; microseconds are dropped.
            assert got.microsecond == 0
            assert got.replace(microsecond=0) == ts_in.replace(microsecond=0)
        finally:
            mgr.stop()

    def test_varchar2_round_trip(self, oracle_connection, temp_table):
        """str / VARCHAR2(n CHAR) preserves Unicode content within length."""
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "s", "type": "str", "length": 50, "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "s" VARCHAR2(50 CHAR))'
            )
            oracle_connection.commit()
            cur.close()

            comp = _make_output(temp_table, schema, mgr, data_action="INSERT")
            df = pd.DataFrame({"id": [1, 2], "s": ["hello", "world"]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "s" FROM "{temp_table}" ORDER BY "id"')
                rows = [r[0] for r in cur.fetchall()]
            finally:
                cur.close()
            assert rows == ["hello", "world"]
        finally:
            mgr.stop()

    def test_clob_round_trip(self, oracle_connection, temp_table):
        """str / CLOB preserves payloads >4000 chars (oracledb thin mode).

        D-B1: oracledb.defaults.fetch_lobs = False is set by the manager so
        SELECT returns str (not Lob).
        """
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            # length omitted -> column maps to CLOB per _column_to_oracle_type.
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "doc", "type": "str", "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "doc" CLOB)'
            )
            oracle_connection.commit()
            cur.close()

            big = "x" * 8000
            comp = _make_output(temp_table, schema, mgr, data_action="INSERT")
            df = pd.DataFrame({"id": [1], "doc": [big]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "doc" FROM "{temp_table}"')
                got = cur.fetchone()[0]
            finally:
                cur.close()
            # fetch_lobs=False (D-B1) -> SELECT returns str, not Lob.
            assert isinstance(got, str)
            assert len(got) == 8000
            assert got == big
        finally:
            mgr.stop()

    def test_blob_round_trip(self, oracle_connection, temp_table):
        """bytes / BLOB preserves binary content."""
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            # length omitted -> column maps to BLOB per _column_to_oracle_type.
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "payload", "type": "bytes", "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "payload" BLOB)'
            )
            oracle_connection.commit()
            cur.close()

            payload = bytes(range(256))
            comp = _make_output(temp_table, schema, mgr, data_action="INSERT")
            df = pd.DataFrame({"id": [1], "payload": [payload]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "payload" FROM "{temp_table}"')
                got = cur.fetchone()[0]
            finally:
                cur.close()
            assert isinstance(got, bytes)
            assert got == payload
        finally:
            mgr.stop()


# ----------------------------------------------------------------------
# VR-06: REJECT path via batcherrors
# ----------------------------------------------------------------------


class TestRejectBatcherrors:
    """VR-06: 3 valid + 1 dup PK -> NB_LINE_INSERTED=3, NB_LINE_REJECTED=1.

    Reject DataFrame errorCode='1' (ORA-00001 unique violation), errorMessage
    ends with " - Line: <offset>" per D-C7.
    """

    def test_reject_on_unique_violation(self, oracle_connection, temp_table):
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "name", "type": "str", "length": 50, "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "name" VARCHAR2(50 CHAR))'
            )
            cur.execute(f'INSERT INTO "{temp_table}" VALUES (2, \'pre-existing\')')
            oracle_connection.commit()
            cur.close()

            comp = _make_output(temp_table, schema, mgr, data_action="INSERT")
            df = pd.DataFrame({"id": [1, 2, 3, 4], "name": ["a", "b", "c", "d"]})
            # id=2 will fail with ORA-00001 (unique constraint).
            result = comp._process(df)

            assert comp.global_map.get("tOracleOutput_1_NB_LINE_INSERTED") == 3
            assert comp.global_map.get("tOracleOutput_1_NB_LINE_REJECTED") == 1

            reject = result["reject"]
            assert reject is not None
            assert len(reject) == 1
            assert reject.iloc[0]["errorCode"] == "1"
            # errorMessage ends with " - Line: <offset>"; offset for id=2 is 1
            # (zero-based index in the executemany batch).
            err_msg = reject.iloc[0]["errorMessage"]
            assert "Line: 1" in err_msg
            assert reject.iloc[0]["id"] == 2
            assert reject.iloc[0]["name"] == "b"
        finally:
            mgr.stop()


# ----------------------------------------------------------------------
# VR-07: INSERT_OR_UPDATE batched 2-statement upsert
# ----------------------------------------------------------------------


class TestUpsertBatched:
    """VR-07: 5 input rows where 2 keys exist -> 2 UPDATED + 3 INSERTED."""

    def test_insert_or_update_batched(self, oracle_connection, temp_table):
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "name", "type": "str", "length": 50, "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "name" VARCHAR2(50 CHAR))'
            )
            cur.execute(f'INSERT INTO "{temp_table}" VALUES (2, \'old\')')
            cur.execute(f'INSERT INTO "{temp_table}" VALUES (4, \'old\')')
            oracle_connection.commit()
            cur.close()

            comp = _make_output(
                temp_table, schema, mgr, data_action="INSERT_OR_UPDATE",
            )
            df = pd.DataFrame({
                "id": [1, 2, 3, 4, 5],
                "name": ["new1", "new2", "new3", "new4", "new5"],
            })
            comp._process(df)

            assert comp.global_map.get("tOracleOutput_1_NB_LINE_UPDATED") == 2
            assert comp.global_map.get("tOracleOutput_1_NB_LINE_INSERTED") == 3

            cur = oracle_connection.cursor()
            try:
                cur.execute(
                    f'SELECT "id", "name" FROM "{temp_table}" ORDER BY "id"'
                )
                rows = list(cur.fetchall())
            finally:
                cur.close()
            assert rows == [
                (1, "new1"), (2, "new2"), (3, "new3"),
                (4, "new4"), (5, "new5"),
            ]
        finally:
            mgr.stop()

    def test_update_or_insert_batched_prefers_update(
        self, oracle_connection, temp_table,
    ):
        """UPDATE_OR_INSERT mirrors INSERT_OR_UPDATE for the matched/unmatched
        row counts -- semantically the difference is ordering, not the final
        table state in the batched 2-statement strategy.
        """
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "name", "type": "str", "length": 50, "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "name" VARCHAR2(50 CHAR))'
            )
            cur.execute(f'INSERT INTO "{temp_table}" VALUES (1, \'old1\')')
            oracle_connection.commit()
            cur.close()

            comp = _make_output(
                temp_table, schema, mgr, data_action="UPDATE_OR_INSERT",
            )
            df = pd.DataFrame({"id": [1, 2], "name": ["new1", "new2"]})
            comp._process(df)

            assert comp.global_map.get("tOracleOutput_1_NB_LINE_UPDATED") == 1
            assert comp.global_map.get("tOracleOutput_1_NB_LINE_INSERTED") == 1

            cur = oracle_connection.cursor()
            try:
                cur.execute(
                    f'SELECT "id", "name" FROM "{temp_table}" ORDER BY "id"'
                )
                rows = list(cur.fetchall())
            finally:
                cur.close()
            assert rows == [(1, "new1"), (2, "new2")]
        finally:
            mgr.stop()


# ----------------------------------------------------------------------
# VR-08: DDL emission for the 4 CREATE-family TABLE_ACTIONs
# ----------------------------------------------------------------------


class TestDdlEmission:
    """VR-08: each CREATE-family TABLE_ACTION emits valid Oracle DDL.

    Parametrized across the 4 CREATE-family actions. Each test verifies that
    after the action runs, the table exists with the expected columns.
    """

    @pytest.mark.parametrize("table_action", [
        "CREATE",
        "CREATE_IF_NOT_EXISTS",
        "DROP_CREATE",
        "DROP_IF_EXISTS_AND_CREATE",
    ])
    def test_create_family_emits_valid_ddl(
        self, oracle_connection, table_action,
    ):
        # Identifier validation (T-11-04) requires letter start + letters/digits/_/$/#.
        # token_hex(3) returns 6 hex chars; uppercase per Oracle convention.
        tname = f"DDL_{table_action}_{secrets.token_hex(3).upper()}"
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "amount", "type": "Decimal", "length": 10, "precision": 2,
                 "nullable": True},
                {"name": "name", "type": "str", "length": 50, "nullable": True},
                {"name": "created_at", "type": "datetime", "nullable": True},
            ]
            # DROP_CREATE requires a table to drop; pre-create one for that path.
            cur = oracle_connection.cursor()
            try:
                if table_action == "DROP_CREATE":
                    cur.execute(f'CREATE TABLE "{tname}" (dummy NUMBER)')
                    oracle_connection.commit()
            finally:
                cur.close()

            comp = _make_output(
                tname, schema, mgr,
                table_action=table_action, data_action="INSERT",
            )
            df = pd.DataFrame({
                "id": [1],
                "amount": [Decimal("99.99")],
                "name": ["x"],
                "created_at": [datetime.datetime(2026, 1, 1, 0, 0, 0)],
            })
            comp._process(df)

            # Verify the resulting table has 4 columns of the expected types.
            cur = oracle_connection.cursor()
            try:
                cur.execute(
                    "SELECT column_name, data_type FROM user_tab_columns "
                    f"WHERE table_name = '{tname}' ORDER BY column_id"
                )
                cols = [(r[0], r[1]) for r in cur.fetchall()]
                cur.execute(f'DROP TABLE "{tname}" PURGE')
                oracle_connection.commit()
            finally:
                cur.close()

            # Identifiers were quoted so case matches the schema names exactly.
            col_names = [c[0] for c in cols]
            col_types = [c[1] for c in cols]
            assert col_names == ["id", "amount", "name", "created_at"]
            assert "NUMBER" in col_types[0]
            assert "NUMBER" in col_types[1]
            assert "VARCHAR2" in col_types[2]
            assert "TIMESTAMP" in col_types[3]
        finally:
            mgr.stop()


# ----------------------------------------------------------------------
# USE_TIMESTAMP_FOR_DATE_TYPE bind precision (D-B1)
# ----------------------------------------------------------------------


class TestUseTimestampForDateType:
    """D-B1: USE_TIMESTAMP_FOR_DATE_TYPE controls the cursor.setinputsizes bind
    type for datetime columns. True (default) -> DB_TYPE_TIMESTAMP preserves
    sub-second precision; False -> DB_TYPE_DATE strips it.
    """

    def test_default_true_preserves_subsecond(
        self, oracle_connection, temp_table,
    ):
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "ts", "type": "datetime", "nullable": True},
            ]
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "ts" TIMESTAMP)'
            )
            oracle_connection.commit()
            cur.close()

            comp = _make_output(
                temp_table, schema, mgr, data_action="INSERT",
                use_timestamp_for_date_type=True,
            )
            ts_in = datetime.datetime(2026, 5, 7, 12, 34, 56, 654321)
            df = pd.DataFrame({"id": [1], "ts": [ts_in]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "ts" FROM "{temp_table}"')
                got = cur.fetchone()[0]
            finally:
                cur.close()
            assert got == ts_in
            assert got.microsecond == 654321
        finally:
            mgr.stop()

    def test_false_drops_subsecond(self, oracle_connection, temp_table):
        mgr = OracleConnectionManager()
        mgr.start()
        mgr.register("c1", oracle_connection)
        try:
            schema = [
                {"name": "id", "type": "int", "key": True, "nullable": False},
                {"name": "ts", "type": "datetime", "nullable": True},
            ]
            # Storage column is TIMESTAMP so the precision difference is purely
            # bind-side; if the bind drops microseconds, the stored value loses
            # them too.
            cur = oracle_connection.cursor()
            cur.execute(
                f'CREATE TABLE "{temp_table}" '
                f'("id" NUMBER(10) PRIMARY KEY, "ts" TIMESTAMP)'
            )
            oracle_connection.commit()
            cur.close()

            comp = _make_output(
                temp_table, schema, mgr, data_action="INSERT",
                use_timestamp_for_date_type=False,
            )
            ts_in = datetime.datetime(2026, 5, 7, 12, 34, 56, 654321)
            df = pd.DataFrame({"id": [1], "ts": [ts_in]})
            comp._process(df)

            cur = oracle_connection.cursor()
            try:
                cur.execute(f'SELECT "ts" FROM "{temp_table}"')
                got = cur.fetchone()[0]
            finally:
                cur.close()
            # DB_TYPE_DATE bind strips microseconds before sending to the server.
            assert got.microsecond == 0
            assert got.replace(microsecond=0) == ts_in.replace(microsecond=0)
        finally:
            mgr.stop()
