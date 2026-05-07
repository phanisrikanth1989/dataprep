"""Engine component for OracleOutput (tOracleOutput).

Writes a DataFrame to an Oracle table using cursor.executemany with
batcherrors=True (D-B2, single code path). Supports the full 8 TABLE_ACTION
x 5 DATA_ACTION matrix per D-C1, with INSERT_OR_UPDATE / UPDATE_OR_INSERT
deferred to plan 11-05 (this plan stubs them to raise NotImplementedError).

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
_DATA_ACTIONS_THIS_PLAN = frozenset({"INSERT", "UPDATE", "DELETE"})
_DATA_ACTIONS_DEFERRED_TO_11_05 = frozenset({"INSERT_OR_UPDATE", "UPDATE_OR_INSERT"})


def _quote_ident(name: str) -> str:
    """Wrap an Oracle identifier in double quotes (T-11-04).

    Validates ``name`` against the Oracle non-quoted identifier pattern
    (letter start, then letters/digits/_/$/#) before quoting. Oracle treats
    double-quoted identifiers as case-sensitive, so we preserve case and
    rely on the regex to reject SQL metachars / spaces / punctuation.

    Args:
        name: The identifier (column / table / schema name) to quote.

    Returns:
        ``'"<name>"'`` -- double-quoted identifier ready for SQL emission.

    Raises:
        ConfigurationError: If ``name`` does not match the safe-pattern.
    """
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise ConfigurationError(
            f"Invalid Oracle identifier {name!r}. "
            f"Must match /^[A-Za-z][A-Za-z0-9_$#]*$/ "
            f"(letter start, then letters/digits/_/$/#)."
        )
    return f'"{name}"'


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

    def _qualified_table(self) -> str:
        """Return the double-quoted qualified table name (T-11-04).

        Returns:
            ``'"<schema>"."<table>"'`` when schema_db is set; otherwise
            ``'"<table>"'``.

        Raises:
            ConfigurationError: If the table or schema_db identifier fails
                _quote_ident validation.
        """
        schema = (self.config.get("schema_db") or self.config.get("dbschema") or "").strip()
        table = self.config["table"].strip()
        if schema:
            return f"{_quote_ident(schema)}.{_quote_ident(table)}"
        return _quote_ident(table)

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
        for col in self.output_schema:
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

    def _key_columns(self) -> List[str]:
        """Return primary key column names.

        Honors FIELD_OPTIONS UPDATE_KEY when use_field_options=True (D-C6);
        otherwise falls back to the schema 'key' attribute.
        """
        if self.config.get("use_field_options", False):
            fo = self.config.get("field_options", []) or []
            return [r["column"] for r in fo if r.get("update_key", False)]
        return [c["name"] for c in self.output_schema if c.get("key", False)]

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
        return [c["name"] for c in self.output_schema if not c.get("key", False)]

    def _insertable_columns(self) -> List[str]:
        """Return columns that go in the INSERT column list.

        Honors FIELD_OPTIONS INSERTABLE when use_field_options=True (D-C6);
        otherwise all schema columns are insertable.
        """
        if self.config.get("use_field_options", False):
            fo = self.config.get("field_options", []) or []
            return [r["column"] for r in fo if r.get("insertable", True)]
        return [c["name"] for c in self.output_schema]

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
        if data_action == "INSERT":
            cols = self._insertable_columns()
        elif data_action == "UPDATE":
            cols = self._updatable_columns() + self._key_columns()
        elif data_action == "DELETE":
            cols = self._key_columns()
        else:
            raise NotImplementedError(
                f"data_action {data_action} not handled in plan 11-04"
            )
        return [
            tuple(row[c] if pd.notna(row[c]) else None for c in cols)
            for _, row in df.iterrows()
        ]

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
        schema_by_name = {c["name"]: c for c in self.output_schema}
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
            elif ctype == "str":
                if clength and int(clength) <= 4000:
                    sizes.append(int(clength))
                else:
                    sizes.append(oracledb.DB_TYPE_CLOB)
            elif ctype == "datetime":
                sizes.append(
                    oracledb.DB_TYPE_TIMESTAMP if use_ts else oracledb.DB_TYPE_DATE
                )
            elif ctype == "bytes":
                if clength and int(clength) <= 2000:
                    sizes.append(oracledb.DB_TYPE_RAW)
                else:
                    sizes.append(oracledb.DB_TYPE_BLOB)
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
            ConfigurationError: If oracle_manager is not wired.
            NotImplementedError: If data_action is INSERT_OR_UPDATE or
                UPDATE_OR_INSERT (deferred to plan 11-05).
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
        if data_action in _DATA_ACTIONS_DEFERRED_TO_11_05:
            # Plan 11-05 lands the upsert logic
            raise NotImplementedError(
                f"[{self.id}] data_action {data_action!r} deferred to plan 11-05"
            )

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
                if data_action == "INSERT":
                    sql = self._build_insert_sql()
                elif data_action == "UPDATE":
                    sql = self._build_update_sql()
                elif data_action == "DELETE":
                    sql = self._build_delete_sql()
                else:
                    raise NotImplementedError(
                        f"data_action {data_action} not handled"
                    )

                rows = self._dataframe_to_param_list(input_data, data_action)
                input_sizes = self._build_input_sizes(data_action)

                since_commit = 0
                for chunk_start in range(0, len(rows), batch_size):
                    chunk = rows[chunk_start:chunk_start + batch_size]
                    chunk_df = input_data.iloc[
                        chunk_start:chunk_start + len(chunk)
                    ]

                    if input_sizes:
                        cursor.setinputsizes(*input_sizes)
                    cursor.executemany(sql, chunk, batcherrors=True)
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

                    # Commit cycle (D-B2 + Pitfall 7: explicit commit when
                    # batcherrors=True; auto-commit DOES NOT fire when
                    # batcherrors flag is set on a single-row batch failure).
                    since_commit += len(chunk)
                    if since_commit >= commit_every:
                        conn.commit()
                        since_commit = 0

                if since_commit > 0:
                    conn.commit()

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
            die_on_error = self.config.get("die_on_error", False)
            if die_on_error and reject_df is not None and len(reject_df) > 0:
                first_err = reject_df.iloc[0].get("errorMessage", "unknown")
                raise DataValidationError(
                    f"[{self.id}] {len(reject_df)} row(s) rejected with "
                    f"die_on_error=True; first error: {first_err}"
                )

            logger.info(
                "[%s] Wrote (inserted=%d, updated=%d, deleted=%d, rejected=%d) to %s",
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

        # Sink: main is empty; reject carries the error rows
        return {"main": pd.DataFrame(), "reject": reject_df}
