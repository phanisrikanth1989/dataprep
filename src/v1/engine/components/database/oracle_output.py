"""Engine component for OracleOutput (tOracleOutput).

Writes a DataFrame to an Oracle table using cursor.executemany with
batcherrors=True (D-B2, single code path). Supports the full 8 TABLE_ACTION
x 5 DATA_ACTION matrix per D-C1. INSERT_OR_UPDATE / UPDATE_OR_INSERT use
the batched 2-statement upsert per D-C2 (plan 11-05): per chunk, SELECT
existing PKs once, partition matched/unmatched in Python, then executemany
UPDATE on matched + executemany INSERT on unmatched. Stats split correctly
(NB_LINE_UPDATED += matched_ok; NB_LINE_INSERTED += unmatched_ok); reject
DataFrame consolidates errors from both calls.

Talaxie _tableActionForOutput.javajet (verified 2026-05-07):
  Source: https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/templates/_tableActionForOutput.javajet
  Note: The Talaxie templates use JDBC DatabaseMetaData.getTables() to test
        for table existence in ORACLE codepaths (line 176-190). The DDL
        type-mapping itself is delegated to a per-DBMS sql_helper that is
        not exposed in the templates fetched (404 on per-component override
        path /tOracleOutput/_tableActionForOutput.javajet). Standard Oracle
        SQL grammar applies; we do not require JDBC because oracledb thin
        mode is the python-side driver. We therefore use PL/SQL
        EXECUTE IMMEDIATE + ORA-00955/ORA-00942 catch for the conditional
        CREATE / DROP variants (the Oracle-idiomatic "if not exists" form
        for SQL prior to 23ai).

Decisions for this plan (per CONTEXT.md Discretion + RESEARCH.md type table):
  Float    -> BINARY_FLOAT       (IEEE 754 round-trip; better than NUMBER)
  Double   -> BINARY_DOUBLE      (IEEE 754 round-trip; better than NUMBER)
  String   -> VARCHAR2(n CHAR)   (CHAR semantics; n counts characters not bytes)
  CREATE_IF_NOT_EXISTS -> PL/SQL EXECUTE IMMEDIATE + ORA-00955 catch
  DROP_IF_EXISTS_AND_CREATE -> PL/SQL EXECUTE IMMEDIATE + ORA-00942 catch
                                followed by CREATE TABLE

Reject schema (D-C7): [errorCode, errorMessage, <input columns>]
  errorCode    = str(BatchError.code)
  errorMessage = BatchError.message + " - Line: " + offset

Stat globalMap keys (D-C8):
  {cid}_NB_LINE             -- input row count
  {cid}_NB_LINE_INSERTED    -- per data_action
  {cid}_NB_LINE_UPDATED     -- per data_action
  {cid}_NB_LINE_DELETED     -- per data_action
  {cid}_NB_LINE_REJECTED    -- sum across batches

Identifier quoting (T-11-04 mitigation): column names validated against
/^[A-Za-z][A-Za-z0-9_$#]*$/ (Oracle non-quoted identifier rules: letter
start, followed by letters/digits/_/$/#) before DDL emission. Non-conforming
names raise ConfigurationError with the offending column name. Table
identifiers are wrapped in double quotes for Oracle (e.g. "HR"."EMP").
Legacy Oracle columns like EMP$DATA / COL#1 are accepted for Talend parity.

Config keys consumed (~26 + framework). See module-level _VALID_TABLE_ACTIONS
/ _VALID_DATA_ACTIONS for the closed enums.
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


# T-11-04: identifier safe-pattern. Oracle non-quoted identifier rules:
# letter start, then letters/digits/_/$/#. Accepts legacy column names like
# EMP$DATA / COL#1 for Talend parity; rejects spaces, punctuation, SQL metachars.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")

_VALID_TABLE_ACTIONS = frozenset({
    "NONE",
    "CREATE",
    "CREATE_IF_NOT_EXISTS",
    "DROP_CREATE",
    "DROP_IF_EXISTS_AND_CREATE",
    "CLEAR",
    "TRUNCATE",
    "TRUNCATE_REUSE_STORAGE",
})
_VALID_DATA_ACTIONS = frozenset({
    "INSERT",
    "UPDATE",
    "INSERT_OR_UPDATE",
    "UPDATE_OR_INSERT",
    "DELETE",
})
# Per D-C1: 3 single-statement DATA_ACTIONs (plan 11-04) + 2 upsert
# DATA_ACTIONs (plan 11-05). _DATA_ACTIONS_UPSERT routes to
# _execute_upsert_batch (D-C2 batched 2-statement strategy).
_DATA_ACTIONS_SIMPLE = frozenset({"INSERT", "UPDATE", "DELETE"})
_DATA_ACTIONS_UPSERT = frozenset({"INSERT_OR_UPDATE", "UPDATE_OR_INSERT"})


def _quote_ident(name: str) -> str:
    """
    Validate an Oracle identifier and return it ready for SQL emission (T-11-04).

    Validates ``name`` against the Oracle non-quoted identifier pattern
    (letter start, then letters/digits/_/$/#) and returns it **without**
    quotes. Oracle stores unquoted identifiers at create time and runtime,
    which emits identifiers unquoted so Oracle's default lookup rules
    (auto-uppercase) finds tables / columns that were created with the
    standard unquoted DDL.

    Why no quotes:
        Oracle treats ``"foo"`` as a case-sensitive literal lookup of
        lowercase ``foo``. Job configs (and Talend ``context.*`` variables)
        originated from human-maintained ``.cfg`` files while the actual
        table on disk is stored uppercase (``CITI_BSER_RUN_DETAILS``)
        because the DDL was unquoted. Wrapping in quotes therefore caused
        spurious ORA-00942 failures. Talend never quotes; we now mirror that.

    Safety:
        SQL-injection protection is preserved by ``IDENTIFIER_RE`` --
        only ``[A-Za-z][A-Za-z0-9_$#]*`` survives, so semicolons, dashes,
        spaces, embedded quotes, and other metachars still raise
        ``ConfigurationError`` before the identifier is interpolated into
        the SQL string.

    Args:
        name: The identifier (column / table / schema name) to validate.

    Returns:
        The validated identifier verbatim (no surrounding quotes).

    Raises:
        ConfigurationError: If ``name`` does not match the safe pattern.
    """
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise ConfigurationError(
            f"Invalid Oracle identifier {name!r}. "
            "Must match ^[A-Za-z][A-Za-z0-9_$#]*$ "
            "(letter start, then letters/digits/_/$/#)."
        )

    return name


def _column_to_oracle_type(col: Dict[str, Any], use_timestamp_for_date: bool) -> str:
    """Map an engine schema column dict to its Oracle DDL type.

    Per Task 1 resolution + RESEARCH.md "Oracle DDL Emission From Engine
    Schema". Decisions:
        int / long / short / byte / BigInteger -> NUMBER(p)
        float    -> BINARY_FLOAT
        double   -> BINARY_DOUBLE
        Decimal  -> NUMBER(length, precision)  (fallback NUMBER if length unset)
        str      -> VARCHAR2(length CHAR) when length<=4000 else CLOB
        bool     -> NUMBER(1)
        datetime -> TIMESTAMP (or DATE when use_timestamp_for_date=False)
        bytes    -> RAW(length) when length<=2000 else BLOB

    Args:
        col: Engine schema column dict with keys 'name', 'type', optional
            'length' and 'precision'.
        use_timestamp_for_date: If True (default), datetime columns map to
            TIMESTAMP; if False, map to DATE (D-B1).

    Returns:
        The Oracle DDL type string (e.g. ``"NUMBER(10)"``).
    """
    ctype = col.get("type", "str")
    clength = col.get("length")
    cprecision = col.get("precision")  # Decimal scale

    if ctype == "int":
        return "NUMBER(10)"
    if ctype == "long":
        return "NUMBER(19)"
    if ctype == "short":
        return "NUMBER(5)"
    if ctype == "byte":
        return "NUMBER(3)"
    if ctype == "BigInteger":
        return "NUMBER(38)"
    if ctype == "float":
        return "BINARY_FLOAT"
    if ctype == "double":
        return "BINARY_DOUBLE"
    if ctype == "Decimal":
        if clength is not None:
            p = int(clength)
            s = int(cprecision or 0)
            return f"NUMBER({p},{s})"
        return "NUMBER"
    if ctype == "str":
        if clength is not None and int(clength) <= 4000:
            return f"VARCHAR2({int(clength)} CHAR)"
        return "CLOB"
    if ctype == "bool":
        return "NUMBER(1)"
    if ctype == "datetime":
        return "TIMESTAMP" if use_timestamp_for_date else "DATE"
    if ctype == "bytes":
        if clength is not None and int(clength) <= 2000:
            return f"RAW({int(clength)})"
        return "BLOB"
    # Fallback (per RESEARCH.md "Oracle DDL Emission" -- log WARNING)
    logger.warning(
        "Schema column %r has unknown type %r; defaulting to VARCHAR2(4000)",
        col.get("name", "?"), ctype,
    )
    return "VARCHAR2(4000)"


@REGISTRY.register("OracleOutput", "tOracleOutput")
class OracleOutput(BaseComponent):
    """tOracleOutput engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``oracle_manager`` is injected by ETLEngine
        ``_initialize_components`` (plan 11-01 wiring).
        """
        super().__init__(*args, **kwargs)
        self.oracle_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Phase 7.1 Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only. Content checks live in ``_process``.

        Raises:
            ConfigurationError: If required keys are missing or enum values
                are not in the closed sets.
        """
        if not self.config.get("table"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'table'"
            )
        ta = self.config.get("table_action", "NONE")
        if ta not in _VALID_TABLE_ACTIONS:
            raise ConfigurationError(
                f"[{self.id}] Invalid table_action {ta!r}. "
                f"Must be one of: {sorted(_VALID_TABLE_ACTIONS)}"
            )
        da = self.config.get("data_action", "INSERT")
        if da not in _VALID_DATA_ACTIONS:
            raise ConfigurationError(
                f"[{self.id}] Invalid data_action {da!r}. "
                f"Must be one of: {sorted(_VALID_DATA_ACTIONS)}"
            )

    # ------------------------------------------------------------------
    # DDL helpers
    # ------------------------------------------------------------------

    def qualified_table(self) -> str:
        """Return the qualified table name for SQL emission (T-11-04).

        Identifiers are validated by ``_quote_ident`` (rejects SQL metachars)
        and emitted unquoted so Oracle auto-uppercase lookup matches
        Talend's runtime, which never wraps identifiers in double
        quotes. This avoids ``ORA-00942`` when a job config carries a
        lowercase table name (e.g. ``citi_bser_run_details``) while the
        actual table is stored uppercase (``CITI_BSER_RUN_DETAILS``).

        Returns:
            ``<schema>.<table>`` when schema_db is set and
            ``use_existing_connection`` is False; otherwise ``<table>``.

        Raises:
            ConfigurationError: If the table or schema_db identifier fails
            ``_quote_ident`` validation.
        """
        
        # When reusing an upstream connection (use_existing_connection=True),
        # schema_db is not applicable - Oracle resolves the table against the
        # connection user's default schema. Talend's generated code leaves
        # schema blank in this mode, and preserving that behaviour prevents
        # FQN mismatches when multiple contexts share the same value for both
        # schema_db and table.
        use_existing = self.config.get("use_existing_connection", False)
        table = self._quote_ident(
            self.config.get("table") or self.config.get("dbschema") or ""
        ).strip()
        logger.debug(
            "%s qualified_table: use_existing=%s schema_db=%r table=%r",
            self.id, use_existing, schema, table
        )
        if schema:
            qualified = f"{_quote_ident(schema)}.{_quote_ident(table)}"
            logger.info("[%s] target table: %s", self.id, qualified)
            return qualified
        qualified = _quote_ident(table)
        logger.info("[%s] target table: %s", self.id, qualified)
        return qualified

    def _build_create_sql(self) -> str:
        """Build a CREATE TABLE statement from output_schema.

        Honors per-column nullable flag and emits a PRIMARY KEY constraint
        when one or more schema columns have ``key=True``.

        Returns:
            The CREATE TABLE SQL string.

        Raises:
            ConfigurationError: If any column name fails _quote_ident.
        """
        use_ts = self.config.get("use_timestamp_for_date_type", True)
        cols_sql: List[str] = []
        pk_cols: List[str] = []
        for col in self._schema_cols():
            name = col["name"]
            quoted = _quote_ident(name)  # T-11-04: validates before quoting
            otype = _column_to_oracle_type(col, use_ts)
            nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
            cols_sql.append(f"  {quoted} {otype} {nullable}")
            if col.get("key", False):
                pk_cols.append(quoted)
        body = ",\n".join(cols_sql)
        if pk_cols:
            table_unq = self.config["table"].strip()
            pk_name = _quote_ident(f"PK_{table_unq}")
            body += f",\n  CONSTRAINT {pk_name} PRIMARY KEY ({', '.join(pk_cols)})"
        return f"CREATE TABLE {self._qualified_table()} (\n{body}\n)"

    # ------------------------------------------------------------------
    # 8 TABLE_ACTION emitters (one method each per Discretion D-C1)
    # ------------------------------------------------------------------

    def _emit_none(self, cursor) -> None:
        """NONE: explicit no-op."""
        return None

    def _emit_create(self, cursor) -> None:
        """CREATE: unconditional CREATE TABLE."""
        cursor.execute(self._build_create_sql())

    def _emit_create_if_not_exists(self, cursor) -> None:
        """CREATE_IF_NOT_EXISTS: PL/SQL EXECUTE IMMEDIATE + ORA-00955 catch.

        ORA-00955 is "name is already used by an existing object" -- the
        Oracle-idiomatic guard for conditional CREATE prior to 23ai.
        """
        create_sql = self._build_create_sql()
        # Escape single quotes in the inner SQL for PL/SQL string literal
        escaped = create_sql.replace("'", "''")
        plsql = (
            "BEGIN\n"
            f"  EXECUTE IMMEDIATE '{escaped}';\n"
            "EXCEPTION\n"
            "  WHEN OTHERS THEN\n"
            "    IF SQLCODE != -955 THEN\n"
            "      RAISE;\n"
            "    END IF;\n"
            "END;"
        )
        cursor.execute(plsql)

    def _emit_drop_create(self, cursor) -> None:
        """DROP_CREATE: DROP TABLE then CREATE TABLE. Fails if table absent."""
        cursor.execute(f"DROP TABLE {self._qualified_table()} PURGE")
        cursor.execute(self._build_create_sql())

    def _emit_drop_if_exists_and_create(self, cursor) -> None:
        """DROP_IF_EXISTS_AND_CREATE: PL/SQL DROP guard (ORA-00942 catch) + CREATE.

        ORA-00942 is "table or view does not exist" -- the Oracle-idiomatic
        guard for conditional DROP.
        """
        drop_sql = f"DROP TABLE {self._qualified_table()} PURGE"
        escaped = drop_sql.replace("'", "''")
        plsql = (
            "BEGIN\n"
            f"  EXECUTE IMMEDIATE '{escaped}';\n"
            "EXCEPTION\n"
            "  WHEN OTHERS THEN\n"
            "    IF SQLCODE != -942 THEN\n"
            "      RAISE;\n"
            "    END IF;\n"
            "END;"
        )
        cursor.execute(plsql)
        cursor.execute(self._build_create_sql())

    def _emit_clear(self, cursor) -> None:
        """CLEAR: DELETE FROM table. Slow but transactional + index-preserving."""
        cursor.execute(f"DELETE FROM {self._qualified_table()}")

    def _emit_truncate(self, cursor) -> None:
        """TRUNCATE: TRUNCATE TABLE. Fast but DDL (auto-commits)."""
        cursor.execute(f"TRUNCATE TABLE {self._qualified_table()}")

    def _emit_truncate_reuse_storage(self, cursor) -> None:
        """TRUNCATE_REUSE_STORAGE: TRUNCATE TABLE ... REUSE STORAGE.

        Keeps the segment storage allocated; useful when the table will be
        repopulated immediately.
        """
        cursor.execute(f"TRUNCATE TABLE {self._qualified_table()} REUSE STORAGE")

    def _execute_table_action(self, cursor, action: str) -> None:
        """Dispatch to the right emitter based on the action name.

        Args:
            cursor: An open oracledb cursor.
            action: One of _VALID_TABLE_ACTIONS.

        Raises:
            ConfigurationError: If ``action`` is not a valid TABLE_ACTION.
        """
        dispatch = {
            "NONE": self._emit_none,
            "CREATE": self._emit_create,
            "CREATE_IF_NOT_EXISTS": self._emit_create_if_not_exists,
            "DROP_CREATE": self._emit_drop_create,
            "DROP_IF_EXISTS_AND_CREATE": self._emit_drop_if_exists_and_create,
            "CLEAR": self._emit_clear,
            "TRUNCATE": self._emit_truncate,
            "TRUNCATE_REUSE_STORAGE": self._emit_truncate_reuse_storage,
        }
        emitter = dispatch.get(action)
        if emitter is None:
            raise ConfigurationError(
                f"[{self.id}] Invalid table_action {action!r}. "
                f"Must be one of: {sorted(_VALID_TABLE_ACTIONS)}"
            )
        emitter(cursor)

    # ------------------------------------------------------------------
    # DML helpers
    # ------------------------------------------------------------------

    def _schema_cols(self) -> List[Dict[str, Any]]:
        """Return the per-column schema metadata for this sink.
        Talend ``tOracleOutput`` is a sink; data flows IN, nothing flows
        OUT. The converter therefore writes the parsed schema to
        ``schema["input"]`` (see
        ``src/converters/talend_to_v1/components/database/oracle_output.py``)
        and the engine wires it onto ``self.input_schema``
        (``engine.py``). ``self.output_schema`` is intentionally
        ``[]`` for sinks.
        Earlier engine code read ``self.output_schema`` directly which
        always returned ``[]`` at runtime, causing
        ``_insertable_columns()`` to be empty and the INSERT path to
        raise ``INSERT requires at least one insertable column`` even
        though the upstream map delivered 304 columns.
        This helper mirrors the correct pattern already used by the
        sister sink ``oracle_bulk_exec.py:261`` (``self.input_schema``)
        while preserving backward compatibility with unit tests that
        wire the schema via ``component.schema``. If neither path
        contains schema metadata, the helper gracefully
        falls back to ``output_schema``.

        Returns:
            List of column-metadata dicts (``name``, ``type``, nullable, key,
            length, ...). Empty list when neither side is populated.
        """

        # ``getattr`` with default mirrors ``oracle_bulk_exec.py:261`` and
        # tolerates legacy unit-test fixtures that build the component
        # without going through the engine wiring which would normally
        # set both attributes.
        in_schema = (
            getattr(self, "input_schema", None) or []
            or getattr(self, "output_schema", None) or []
        )
        return in_schema or out_schema

    def _key_columns(self) -> List[str]:
        """Return primary key column names.

        Honors FIELD_OPTIONS UPDATE_KEY when use_field_options=True (D-C6);
        otherwise falls back to the schema 'key' attribute.
        """
        if self.config.get("use_field_options", False):
            fo = self.config.get("field_options", []) or []
            return [r["column"] for r in fo if r.get("update_key", False)]
        return [c["name"] for c in self._schema_cols if c.get("key", False)]

    def _updatable_columns(self) -> List[str]:
        """Return columns that go in the SET clause of UPDATE.

        Honors FIELD_OPTIONS UPDATABLE when use_field_options=True (D-C6);
        otherwise all non-key schema columns are updatable.
        """
        if self.config.get("use_field_options", False):
            fo = self.config.get("field_options", []) or []
            return [
                r["column"] for r in fo
                if r.get("updatable", True) and not r.get("update_key", False)
            ]
        return [c["name"] for c in self._schema_cols if not c.get("key", False)]

    def _insertable_columns(self) -> List[str]:
        """Return columns that go in the INSERT column list.

        Honors FIELD_OPTIONS INSERTABLE when use_field_options=True (D-C6);
        otherwise all schema columns are insertable.
        """
        if self.config.get("use_field_options", False):
            fo = self.config.get("field_options", []) or []
            return [r["column"] for r in fo if r.get("insertable", True)]
        return [c["name"] for c in self._schema_cols]

    def _build_insert_sql(self) -> str:
        """Build the INSERT INTO ... VALUES (:1, :2, ...) SQL."""
        cols = self._insertable_columns()
        if not cols:
            raise ConfigurationError(
                f"[{self.id}] INSERT requires at least one insertable column"
            )
        quoted_cols = [_quote_ident(c) for c in cols]
        placeholders = ", ".join(f":{i}" for i in range(1, len(cols) + 1))
        return (
            f"INSERT INTO {self._qualified_table()} "
            f"({', '.join(quoted_cols)}) VALUES ({placeholders})"
        )

    def _build_update_sql(self) -> str:
        """Build the UPDATE ... SET ... WHERE key = :n SQL.

        Raises:
            ConfigurationError: If no key column is declared (UPDATE without
                a key would silently rewrite every row).
        """
        keys = self._key_columns()
        if not keys:
            raise ConfigurationError(
                f"[{self.id}] UPDATE requires at least one primary key column "
                f"(schema 'key' attribute or field_options UPDATE_KEY)"
            )
        updatable = self._updatable_columns()
        if not updatable:
            raise ConfigurationError(
                f"[{self.id}] UPDATE requires at least one updatable column"
            )
        set_clause = ", ".join(
            f"{_quote_ident(c)} = :{i}" for i, c in enumerate(updatable, start=1)
        )
        where_clause = " AND ".join(
            f"{_quote_ident(k)} = :{i}"
            for i, k in enumerate(keys, start=len(updatable) + 1)
        )
        return (
            f"UPDATE {self._qualified_table()} SET {set_clause} "
            f"WHERE {where_clause}"
        )

    def _build_delete_sql(self) -> str:
        """Build the DELETE FROM ... WHERE key = :n SQL.

        Raises:
            ConfigurationError: If no key column is declared (DELETE without
                a key would silently empty the table).
        """
        keys = self._key_columns()
        if not keys:
            raise ConfigurationError(
                f"[{self.id}] DELETE requires at least one primary key column"
            )
        where_clause = " AND ".join(
            f"{_quote_ident(k)} = :{i}" for i, k in enumerate(keys, start=1)
        )
        return f"DELETE FROM {self._qualified_table()} WHERE {where_clause}"

    # ---- Upsert support (D-C2) ------------------------------------------

    def _build_pk_select_sql(self, pk_cols: List[str], n_keys: int) -> str:
        """Build SELECT pk_cols FROM table WHERE pk IN (batch_keys) (D-C2).

        Single-PK uses ``WHERE pk IN (:1, :2, ..., :N)``.
        Composite PK uses an OR-chain
        ``(pk1=:1 AND pk2=:2) OR (pk1=:3 AND pk2=:4) OR ...`` per
        RESEARCH.md Open Q 4 (acceptable for batch_size <= 10000).

        Args:
            pk_cols: List of primary-key column names. Validated identifiers.
            n_keys: Number of input rows in the batch.

        Returns:
            The SELECT SQL string with positional :N placeholders.

        Raises:
            ConfigurationError: If pk_cols is empty.
        """
        if not pk_cols:
            raise ConfigurationError(
                f"[{self.id}] upsert requires at least one primary key column "
                f"(schema 'key' attribute or field_options UPDATE_KEY)"
            )
        quoted_cols = [_quote_ident(c) for c in pk_cols]
        if len(pk_cols) == 1:
            placeholders = ", ".join(f":{i}" for i in range(1, n_keys + 1))
            return (
                f"SELECT {quoted_cols[0]} FROM {self._qualified_table()} "
                f"WHERE {quoted_cols[0]} IN ({placeholders})"
            )
        # Composite PK -- OR-chain
        clauses: List[str] = []
        bind_idx = 1
        for _ in range(n_keys):
            tuple_clauses = []
            for col in quoted_cols:
                tuple_clauses.append(f"{col} = :{bind_idx}")
                bind_idx += 1
            clauses.append("(" + " AND ".join(tuple_clauses) + ")")
        return (
            f"SELECT {', '.join(quoted_cols)} FROM {self._qualified_table()} "
            f"WHERE " + " OR ".join(clauses)
        )

    def _flatten_pk_binds(
        self, chunk: List[Tuple], pk_cols: List[str], col_order: List[str],
    ) -> List[Any]:
        """Flatten chunk rows into a positional bind list for the SELECT.

        Args:
            chunk: List of param tuples in ``col_order`` layout.
            pk_cols: Primary-key column names.
            col_order: Column order matching the chunk tuples (INSERT order).

        Returns:
            Flat list of bind values. Single-PK: one value per row. Composite-PK:
            len(pk_cols) values per row, row by row.
        """
        pk_indices = [col_order.index(c) for c in pk_cols]
        flat: List[Any] = []
        if len(pk_cols) == 1:
            for row in chunk:
                flat.append(row[pk_indices[0]])
        else:
            for row in chunk:
                for idx in pk_indices:
                    flat.append(row[idx])
        return flat

    def _split_matched_unmatched(
        self,
        chunk: List[Tuple],
        chunk_df: pd.DataFrame,
        pk_cols: List[str],
        col_order: List[str],
        matched_keys: set,
    ) -> Tuple[List[Tuple], pd.DataFrame, List[Tuple], pd.DataFrame, int]:
        """Partition the chunk into matched / unmatched. NULL-PK rows go to INSERT.

        NULL primary key handling (Pitfall 6 in RESEARCH.md): Oracle's
        ``NULL = NULL`` is UNKNOWN, so the SELECT cannot match a NULL key.
        Force such rows into the INSERT path and emit a WARNING per row count.

        Returns:
            (matched_chunk, matched_df, unmatched_chunk, unmatched_df, null_pk_count).
        """
        pk_indices = [col_order.index(c) for c in pk_cols]
        matched_chunk: List[Tuple] = []
        unmatched_chunk: List[Tuple] = []
        matched_idx: List[int] = []
        unmatched_idx: List[int] = []
        null_pk_count = 0
        for i, row in enumerate(chunk):
            key = tuple(row[idx] for idx in pk_indices)
            has_null_pk = any(v is None for v in key)
            if has_null_pk:
                null_pk_count += 1
                unmatched_chunk.append(row)
                unmatched_idx.append(i)
            elif key in matched_keys:
                matched_chunk.append(row)
                matched_idx.append(i)
            else:
                unmatched_chunk.append(row)
                unmatched_idx.append(i)
        matched_df = chunk_df.iloc[matched_idx].reset_index(drop=True)
        unmatched_df = chunk_df.iloc[unmatched_idx].reset_index(drop=True)
        return matched_chunk, matched_df, unmatched_chunk, unmatched_df, null_pk_count

    def _execute_upsert_batch(
        self,
        cursor,
        chunk: List[Tuple],
        chunk_df: pd.DataFrame,
        prefer_update: bool,
    ) -> Tuple[int, int, Optional[pd.DataFrame]]:
        """Run the batched 2-statement upsert per D-C2.

        Per batch of N rows:
          1. SELECT pk_cols WHERE pk IN (batch_keys) -- one round trip.
          2. Partition input rows into matched / unmatched (NULL PK -> unmatched).
          3. executemany UPDATE on matched_chunk.
          4. executemany INSERT on unmatched_chunk.
          5. Combine batcherrors from both calls into a single reject DataFrame.

        ``prefer_update`` only affects log wording; matched rows always go
        to UPDATE and unmatched rows always go to INSERT. Talend's per-row
        try-update-first vs try-insert-first distinction collapses to
        identical batched behavior here.

        Args:
            cursor: An open oracledb cursor.
            chunk: Pre-built INSERT-order parameter tuples for the chunk.
            chunk_df: The original input DataFrame slice for this chunk.
            prefer_update: True for UPDATE_OR_INSERT; False for INSERT_OR_UPDATE.

        Returns:
            Tuple of (inserted_count, updated_count, reject_df_or_None).

        Raises:
            ConfigurationError: If there are no key columns to upsert against.
        """
        pk_cols = self._key_columns()
        if not pk_cols:
            raise ConfigurationError(
                f"[{self.id}] upsert requires at least one primary key column "
                f"(schema 'key' attribute or field_options UPDATE_KEY)"
            )

        # The chunk param tuples are in INSERT-column order (built by
        # _dataframe_to_param_list with data_action="INSERT_OR_UPDATE").
        insert_cols = self._insertable_columns()

        # CR-02: PK columns MUST be in the insertable set for upsert. The
        # chunk tuples / SELECT binds / UPDATE bind reorder all assume the
        # PK lives at a known offset within insert_cols. If FIELD_OPTIONS
        # marks a key column as insertable=False (a legitimate Talend
        # pattern for sequence-populated PKs on plain INSERT), upsert is
        # incompatible -- refuse cleanly here rather than crashing later
        # with a confusing ValueError from list.index().
        missing_pk_in_insert = [c for c in pk_cols if c not in insert_cols]
        if missing_pk_in_insert:
            raise ConfigurationError(
                f"[{self.id}] upsert (data_action="
                f"{self.config.get('data_action', '')!r}) requires PK columns "
                f"{missing_pk_in_insert!r} to also be insertable, but "
                f"FIELD_OPTIONS marks them insertable=False. Either remove the "
                f"non-insertable flag for these PK columns, or use a non-upsert "
                f"data_action."
            )

        # 1. SELECT existing PKs
        select_sql = self._build_pk_select_sql(pk_cols, len(chunk))
        select_binds = self._flatten_pk_binds(chunk, pk_cols, insert_cols)
        cursor.execute(select_sql, select_binds)
        matched_keys: set = set()
        for row in cursor.fetchall():
            if isinstance(row, (list, tuple)):
                matched_keys.add(tuple(row))
            else:
                matched_keys.add((row,))

        # 2. Partition
        (
            matched_chunk, matched_df,
            unmatched_chunk, unmatched_df,
            null_pk_count,
        ) = self._split_matched_unmatched(
            chunk, chunk_df, pk_cols, insert_cols, matched_keys,
        )
        if null_pk_count > 0:
            logger.warning(
                "[%s] %d row(s) have NULL primary key; forced into INSERT path "
                "(Oracle NULL=NULL is UNKNOWN -- SELECT cannot match)",
                self.id, null_pk_count,
            )

        # Build matched-row binds in UPDATE order (updatable cols + key cols)
        updatable_cols = self._updatable_columns()
        update_col_order = updatable_cols + pk_cols
        update_indices_in_insert = [insert_cols.index(c) for c in update_col_order]
        update_chunk: List[Tuple] = []
        for row in matched_chunk:
            update_chunk.append(tuple(row[idx] for idx in update_indices_in_insert))

        update_errors: List[Any] = []
        insert_errors: List[Any] = []

        # 3. executemany UPDATE
        if update_chunk:
            update_sql = self._build_update_sql()
            input_sizes_update = self._build_input_sizes("UPDATE")
            if input_sizes_update:
                cursor.setinputsizes(*input_sizes_update)
            cursor.executemany(update_sql, update_chunk, batcherrors=True)
            update_errors = list(cursor.getbatcherrors() or [])

        # 4. executemany INSERT
        if unmatched_chunk:
            insert_sql = self._build_insert_sql()
            input_sizes_insert = self._build_input_sizes("INSERT")
            if input_sizes_insert:
                cursor.setinputsizes(*input_sizes_insert)
            cursor.executemany(insert_sql, unmatched_chunk, batcherrors=True)
            insert_errors = list(cursor.getbatcherrors() or [])

        # 5. Stats
        updated = len(matched_chunk) - len(update_errors)
        inserted = len(unmatched_chunk) - len(insert_errors)

        # 6. Reject DataFrame -- merge errors from both calls
        reject_dfs: List[pd.DataFrame] = []
        if update_errors:
            reject_dfs.append(self._build_reject_chunk(matched_df, update_errors))
        if insert_errors:
            reject_dfs.append(self._build_reject_chunk(unmatched_df, insert_errors))
        reject_df = pd.concat(reject_dfs, ignore_index=True) if reject_dfs else None

        logger.debug(
            "[%s] upsert batch (prefer_update=%s): matched=%d unmatched=%d "
            "null_pk=%d update_errors=%d insert_errors=%d",
            self.id, prefer_update, len(matched_chunk), len(unmatched_chunk),
            null_pk_count, len(update_errors), len(insert_errors),
        )

        return inserted, updated, reject_df

    def _dataframe_to_param_list(
        self, df: pd.DataFrame, data_action: str,
    ) -> List[Tuple]:
        """Convert DataFrame rows to parameter tuples in SQL bind order.

        Args:
            df: Input DataFrame (a chunk slice or the full input).
            data_action: One of INSERT / UPDATE / DELETE.

        Returns:
            List of tuples; each tuple is one row's bound values in the
            order matching the SQL placeholders. NaN/NA -> None.

        Raises:
            NotImplementedError: For data_action values not in this plan.
        """
        if data_action == "INSERT" or data_action in (
            "INSERT_OR_UPDATE", "UPDATE_OR_INSERT",
        ):
            # Upsert chunks use INSERT-column order; _execute_upsert_batch
            # reorders for UPDATE binds.
            cols = self._insertable_columns()
        elif data_action == "UPDATE":
            cols = self._updatable_columns() + self._key_columns()
        elif data_action == "DELETE":
            cols = self._key_columns()
        else:
            raise NotImplementedError(
                f"data_action {data_action} not handled"
            )
        # Vectorized NA→None. iterrows() creates a pd.Series per row and
        # calls pd.notna() per cell → ~1.24M Python-level calls for 36k×34
        # frame. where(pd.notna(df), df, None) does the work in
        # one C-level pass and materializes a single pandas/NumPy array with
        # Python None (unlike df.where().to_numpy() which keeps np.nan for
        # float-dtype columns).
        sub = df[cols]
        return [tuple(row) for row in sub.to_numpy(dtype=object, na_value=None)]

    def _build_input_sizes(self, data_action: str) -> List[Any]:
        """Build cursor.setinputsizes args list per the SQL bind order (D-B1).

        For datetime columns, binds DB_TYPE_TIMESTAMP when
        use_timestamp_for_date_type=True (default) so sub-second precision is
        preserved; otherwise binds DB_TYPE_DATE.

        Args:
            data_action: One of INSERT / UPDATE / DELETE.

        Returns:
            List of oracledb type constants / lengths / None entries in the
            same order as the SQL bind parameters. ``[]`` if oracledb is not
            importable (lazy import keeps the [oracle] extra optional).
        """
        try:
            import oracledb  # noqa: WPS433 -- lazy import; keeps extra optional
        except ImportError:
            return []
        use_ts = self.config.get("use_timestamp_for_date_type", True)
        if data_action == "INSERT":
            cols_in_order = self._insertable_columns()
        elif data_action == "UPDATE":
            cols_in_order = self._updatable_columns() + self._key_columns()
        elif data_action == "DELETE":
            cols_in_order = self._key_columns()
        else:
            return []
        schema_by_name = {c["name"]: c for c in self._schema_cols()}
        sizes: List[Any] = []
        for cname in cols_in_order:
            col = schema_by_name.get(cname, {"type": "str"})
            ctype = col.get("type", "str")
            clength = col.get("length")
            if ctype in (
                "int", "long", "short", "byte", "BigInteger",
                "Decimal", "float", "double", "bool",
            ):
                sizes.append(oracledb.NUMBER)
            elif cType == "str":
                # Always None, including for CLOB (length > 4000 / no length).
                # Passing DB_TYPE_CLOB triggers oracledb LOB streaming protocol
                # which opens a SEPARATE ROUND TRIP PER VALUE PER ROW (36k
                # rows × N_CLOB_columns ⇒ tens of thousands of round-trips).
                # With None, oracledb uses inline/deferred LOB write inside the
                # executemany batch (same single round trip for the whole chunk).
                sizes.append(None)
            elif cType == "datetime":
                # Must hint: Python datetime is ambiguous between Oracle DATE and
                # TIMESTAMP. This is the only type that genuinely needs a hint.
                sizes.append(
                    oracledb.DB_TYPE_TIMESTAMP if use_ts else oracledb.DB_TYPE_DATE
                )
            elif cType == "bytes":
                if cLength and int(cLength) <= 2000:
                    # Hint RAW to distinguish from BLOB for small byte columns.
                    sizes.append(oracledb.DB_TYPE_RAW)
                else:
                    # Same as CLOB: None avoids per-value BLOB streaming overhead.
                    sizes.append(None)
            else:
                sizes.append(None)
        return sizes

    def _build_reject_chunk(self, chunk_df: pd.DataFrame, batch_errors) -> pd.DataFrame:
        """Build a reject DataFrame from a list of oracledb BatchError objects.

        Reject schema (D-C7): [errorCode, errorMessage, <input cols>]
            errorCode    = str(err.code)
            errorMessage = err.message + " - Line: " + offset

        Args:
            chunk_df: The input DataFrame slice that produced the errors.
            batch_errors: List of oracledb BatchError objects with .code,
                .message, .offset attributes.

        Returns:
            DataFrame with ``errorCode`` / ``errorMessage`` columns first,
            followed by the original input columns for the rejected rows.
        """
        rows: List[Dict[str, Any]] = []
        for err in batch_errors:
            try:
                src_row = chunk_df.iloc[err.offset].to_dict()
            except IndexError:
                # Defensive: oracledb BatchError offset out of range
                src_row = {}
            row: Dict[str, Any] = {
                "errorCode": str(err.code),
                "errorMessage": f"{err.message} - Line: {err.offset}",
            }
            row.update(src_row)
            rows.append(row)
        # Construct columns in the canonical order: errorCode, errorMessage, *input cols
        if not rows:
            return pd.DataFrame(columns=["errorCode", "errorMessage", *list(chunk_df.columns)])
        ordered_cols = ["errorCode", "errorMessage", *[c for c in chunk_df.columns if c not in {"errorCode", "errorMessage"}]]
        return pd.DataFrame(rows, columns=ordered_cols)

    # ------------------------------------------------------------------
    # Process: TABLE_ACTION + DATA_ACTION
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Acquire connection, run TABLE_ACTION + DATA_ACTION, publish stats.

        Args:
            input_data: Upstream FLOW DataFrame. May be None for jobs that
                only need the TABLE_ACTION (e.g. CREATE without rows).

        Returns:
            ``{"main": pd.DataFrame(), "reject": <reject_df or None>}``.
            tOracleOutput is a sink; ``main`` is always empty.

        Raises:
            ConfigurationError: If oracle_manager is not wired, or if
                data_action requires a primary key column and none is
                declared (UPDATE / DELETE / upsert).
            DataValidationError: If die_on_error=True and the reject DataFrame
                is non-empty (mirror file_input_delimited.py:253-258).
        """
        if self.oracle_manager is None:
            raise ConfigurationError(
                f"[{self.id}] OracleConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.oracle_manager."
            )

        data_action = self.config.get("data_action", "INSERT")
        # Plan 11-05: INSERT_OR_UPDATE / UPDATE_OR_INSERT now handled via
        # _execute_upsert_batch (D-C2 batched 2-statement upsert).

        # Acquire connection (shared via manager.get / ad-hoc via open_ad_hoc)
        use_existing = self.config.get("use_existing_connection", False)
        if use_existing:
            conn = self.oracle_manager.get(self.config.get("connection", ""))
            owns_connection = False
        else:
            conn = self.oracle_manager.open_ad_hoc(self.id, self.config)
            owns_connection = True

        cursor = conn.cursor()
        inserted = updated = deleted = rejected = 0
        all_reject_dfs: List[pd.DataFrame] = []
        commit_every = int(self.config.get("commit_every", 10000) or 10000)
        # batch_size respects use_batch_size flag (default True). When False,
        # treat the entire DataFrame as a single batch.
        if self.config.get("use_batch_size", True):
            batch_size = int(self.config.get("batch_size", 10000) or 10000)
        else:
            batch_size = len(input_data) if input_data is not None else 10000
            if batch_size <= 0:
                batch_size = 10000

        try:
            # 1. TABLE_ACTION
            table_action = self.config.get("table_action", "NONE")
            self._execute_table_action(cursor, table_action)
            if table_action != "NONE" and not getattr(conn, "autocommit", False):
                conn.commit()

            # 2. DATA_ACTION via executemany + batcherrors
            if input_data is not None and len(input_data) > 0:
                is_upsert = data_action in (
                    "INSERT_OR_UPDATE", "UPDATE_OR_INSERT",
                )
                if data_action == "INSERT":
                    sql = self._build_insert_sql()
                elif data_action == "UPDATE":
                    sql = self._build_update_sql()
                elif data_action == "DELETE":
                    sql = self._build_delete_sql()
                elif is_upsert:
                    # Upsert builds SQL internally per chunk
                    # (_build_pk_select_sql + _build_update_sql + _build_insert_sql).
                    sql = None
                else:
                    raise NotImplementedError(
                        f"data_action {data_action} not handled"
                    )
                
                _t0 = time.monotonic()
                rows = self._dataframe_to_param_list(input_data, data_action)
                _t1 = time.monotonic()
                logger.info(
                    "[%s] param prep: %.2fs for %d rows",
                self.id, _t1 - _t0, len(rows),
                )

                input_sizes = (
                    self._build_input_sizes(data_action) if not is_upsert else []
                )
                # setinputsizes persists for the cursor lifetime - call once
                # before the first executemany, NOT once per chunk.
                # Skip entirely when every entry is None (pure numeric/varchar/str
                # workloads) because it is redundant.
                if input_sizes and any(s is not None for s in input_sizes):
                    cursor.setinputsizes(*input_sizes)

                _t_exec_total = 0.0
                _t_commit_total = 0.0
                since_commit = 0
                for chunk_start in range(0, len(rows), batch_size):
                    chunk = rows[chunk_start:chunk_start + batch_size]
                    chunk_df = input_data.iloc[
                        chunk_start:chunk_start + len(chunk)
                    ]

                    if is_upsert:
                        prefer_update = (data_action == "UPDATE_OR_INSERT")
                        chunk_inserted, chunk_updated, chunk_reject = (
                            self._execute_upsert_batch(
                                cursor, chunk, chunk_df,
                                prefer_update=prefer_update,
                            )
                        )
                        inserted += chunk_inserted
                        updated += chunk_updated
                        if chunk_reject is not None and len(chunk_reject) > 0:
                            rejected += len(chunk_reject)
                            all_reject_dfs.append(chunk_reject)
                    else:
                        _te = time.monotonic()
                        cursor.executemany(sql, chunk, batcherrors=True)
                        _t_exec_total += time.monotonic() - _te

                        batch_errors = cursor.getbatcherrors() or []

                        ok = len(chunk) - len(batch_errors)
                        if data_action == "INSERT":
                            inserted += ok
                        elif data_action == "UPDATE":
                            updated += ok
                        elif data_action == "DELETE":
                            deleted += ok
                        rejected += len(batch_errors)
                        if batch_errors:
                            all_reject_dfs.append(
                                self._build_reject_chunk(chunk_df, batch_errors)
                            )

                    # Commit cycle (D-B2 + Pitfall 7; explicit commit when
                    # batcherrors=True; auto-commit DOES NOT fire when
                    # batcherrors flag is set on a single-row batch failure).
                    since_commit += len(chunk)
                    if since_commit >= commit_every:
                        _tc = time.monotonic()
                        conn.commit()
                        _t_commit_total += time.monotonic() - _tc
                        since_commit = 0

                if since_commit > 0:
                    _tc = time.monotonic()
                    conn.commit()
                    _t_commit_total += time.monotonic() - _tc

                logger.info(
                        "[%s] timing breakdown — param prep=%.2fs executemany=%.2fs "
                        "commits=%.2fs total_rows=%d",
                        self.id, t1 - t0, _t_exec_total, _t_commit_total, len(rows),
                )
            # 3. globalMap stat keys (D-C8)
            if self.global_map is not None:
                    n = len(input_data) if input_data is not None else 0
                    self.global_map.put(f"{self.id}_NB_LINE", n)
                    self.global_map.put(f"{self.id}_NB_LINE_INSERTED", inserted)
                    self.global_map.put(f"{self.id}_NB_LINE_UPDATED", updated)
                    self.global_map.put(f"{self.id}_NB_LINE_DELETED", deleted)
                    self.global_map.put(f"{self.id}_NB_LINE_REJECTED", rejected)

            reject_df = (
                pd.concat(all_reject_dfs, ignore_index=True)
                if all_reject_dfs else None
            )

            # die_on_error rewrap (mirror file_input_delimited.py:253-258)
            #
            # WR-01 (Talend-parity, intentional): die_on_error fires AFTER
            # the per-batch commit cycle has run. Successfully-inserted rows
            # from earlier chunks (and from the same chunk before a non-rejectable
            # failure) remain committed in the target table. This mirrors
            # Talend tOracleOutput's behavior. Talend's main-javajet commits
            # at COMMIT_EVERY thresholds and the job-abort path only sees NOT
            # yet-committed work. We deliberately DO NOT call
            # conn.rollback() here -- that would diverge from Talend semantics
            # and surprise jobs that depend on committed-up-to-failure-point
            # behavior.
            # Jobs requiring strict all-or-nothing semantics
            # should set commit_every very high (e.g. > input row count)
            # so only one commit fires at the end of a successful run.
            die_on_error = self.config.get("die_on_error", False)
            if die_on_error and reject_df is not None and len(reject_df) > 0:
                first_err = reject_df.iloc[0].get("errorMessage", "unknown")
                raise DataValidationError(
                    f"[{self.id}] {len(reject_df)} row(s) rejected with "
                    f"die_on_error=True; first error: {first_err}"
                )

            logger.info(
                    "[%s] wrote (inserted=%d updated=%d deleted=%d rejected=%d) to %s",
                    self.id, inserted, updated, deleted, rejected,
                    self._qualified_table(),
            )
        finally:
            try:
                cursor.close()
            except Exception:  # noqa: BLE001 -- cleanup must not mask original
                logger.warning("[%s] cursor.close() raised; ignoring", self.id)

                if owns_connection:
                    try:
                        self.oracle_manager.close(self.id)
                    except Exception:  # noqa: BLE001
                        logger.warning(
                            "[%s] oracle_manager.close() raised; ignoring", self.id
                        )
            # Sink; main is empty; reject carries the error rows
            return {"main": pd.DataFrame(), "reject": reject_df}
