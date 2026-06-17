"""Engine component for OracleSP (tOracleSP).

Calls an Oracle stored procedure or function, binding IN parameters from the
incoming FLOW row and writing OUT / IN OUT parameters (and a function's return
value) back into the output row. Executes once per input row (Talend
per-row-call semantics); when there is no input FLOW it executes a single time.

Acquires either a shared connection (USE_EXISTING_CONNECTION + CONNECTION ref)
or an ad-hoc connection (mirrors oracle_row.py acquisition).

SP_ARGS entries (converter emits column / type / dbtype / is_custom /
custom_type / custom_name):
    type   -- parameter direction: IN, OUT, IN OUT (INOUT), or RECORDSET
    column -- schema column the IN value is read from / OUT value written to
    dbtype -- Oracle type name used to allocate the OUT/INOUT bind variable

Deferred (raise ConfigurationError, mirroring the OCI/Wallet deferral in
oracle_connection.py):
    is_custom=True (STRUCT/ARRAY object types) -- needs thick-mode type handles
    type=RECORDSET (ref-cursor OUT)            -- live ResultSet -> FLOW column

Config keys consumed (mirrors the converter at
src/converters/talend_to_v1/components/database/oracle_sp.py):
    use_existing_connection, connection, connection_type, host, port, dbname,
    local_service_name, rac_url, user, password   -- connection acquisition
    sp_name        (str, REQUIRED)                -- procedure / function name
    is_function    (bool, default False)          -- callfunc vs callproc
    return_column  (str)                          -- output column for a
                                                    function's return value
    return_bdtype  (str, default "AUTOMAPPING")   -- function return Oracle type
    sp_args        (list[dict], default [])       -- parameter table
    support_nls    (bool, default False)          -- DEFERRED (WARNING)

Returns: {"main": df, "reject": None}.
Side effects: publishes f"{cid}_NB_LINE" (output row count) to globalMap.

Security: never logs credentials or bound values (T-11-02). ASCII-only (D-H7).
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Parameter direction tokens (normalized: upper-cased, spaces/underscores stripped).
_DIRECTION_IN = "IN"
_DIRECTION_OUT = "OUT"
_DIRECTION_INOUT = "INOUT"
_DIRECTION_RECORDSET = "RECORDSET"


def _normalize_direction(raw: str) -> str:
    """Normalize a SP_ARGS 'type' value to a canonical direction token.

    Talend emits "IN", "OUT", "IN OUT", or "RECORDSET". We fold whitespace and
    underscores so "IN OUT" / "IN_OUT" / "INOUT" all map to INOUT.
    """
    return (raw or "").upper().replace(" ", "").replace("_", "")


def _oracle_var_type(dbtype: str) -> Any:
    """Map an Oracle DBTYPE name to an oracledb type for cursor.var allocation.

    Unknown / unmapped types fall back to DB_TYPE_VARCHAR (string), which binds
    safely for the common case. oracledb is imported lazily so the ``oracle``
    extra stays optional for non-Oracle jobs.
    """
    import oracledb

    mapping = {
        "VARCHAR2": oracledb.DB_TYPE_VARCHAR,
        "VARCHAR": oracledb.DB_TYPE_VARCHAR,
        "CHAR": oracledb.DB_TYPE_CHAR,
        "NCHAR": oracledb.DB_TYPE_NCHAR,
        "NVARCHAR2": oracledb.DB_TYPE_NVARCHAR,
        "NUMBER": oracledb.DB_TYPE_NUMBER,
        "INTEGER": oracledb.DB_TYPE_NUMBER,
        "INT": oracledb.DB_TYPE_NUMBER,
        "FLOAT": oracledb.DB_TYPE_NUMBER,
        "BINARY_FLOAT": oracledb.DB_TYPE_BINARY_FLOAT,
        "BINARY_DOUBLE": oracledb.DB_TYPE_BINARY_DOUBLE,
        "DATE": oracledb.DB_TYPE_DATE,
        "TIMESTAMP": oracledb.DB_TYPE_TIMESTAMP,
        "CLOB": oracledb.DB_TYPE_CLOB,
        "BLOB": oracledb.DB_TYPE_BLOB,
    }
    return mapping.get((dbtype or "").upper(), oracledb.DB_TYPE_VARCHAR)


@REGISTRY.register("OracleSP", "tOracleSP")
class OracleSP(BaseComponent):
    """tOracleSP engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``oracle_manager`` is injected by ETLEngine
        ``_initialize_components``."""
        super().__init__(*args, **kwargs)
        self.oracle_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only.

        Verifies ``sp_name`` is present and ``sp_args`` is a list of dicts.
        Custom-type / RECORDSET refusal is a CONTENT check that lives in
        ``_process`` (after context resolution).
        """
        if not self.config.get("sp_name"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'sp_name'"
            )
        sp_args = self.config.get("sp_args", [])
        if not isinstance(sp_args, list):
            raise ConfigurationError(
                f"[{self.id}] sp_args must be a list, got "
                f"{type(sp_args).__name__}"
            )
        for i, arg in enumerate(sp_args):
            if not isinstance(arg, dict):
                raise ConfigurationError(
                    f"[{self.id}] sp_args[{i}] must be a dict, got "
                    f"{type(arg).__name__}"
                )

    # ------------------------------------------------------------------
    # Process
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Call the procedure/function per input row, collect OUT params.

        Returns:
            ``{"main": df, "reject": None}`` -- one output row per input row.
        """
        if self.oracle_manager is None:
            raise ConfigurationError(
                f"[{self.id}] OracleConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.oracle_manager."
            )

        sp_args = self.config.get("sp_args", [])
        self._refuse_unsupported_args(sp_args)

        if self.config.get("support_nls", False):
            logger.warning(
                "[%s] Config 'support_nls'=True but not honored (deferred)",
                self.id,
            )

        # Acquire connection (shared via manager.get / ad-hoc via open_ad_hoc).
        use_existing = self.config.get("use_existing_connection", False)
        if use_existing:
            conn = self.oracle_manager.get(self.config.get("connection", ""))
            owns_connection = False
        else:
            conn = self.oracle_manager.open_ad_hoc(self.id, self.config)
            owns_connection = True

        cursor = conn.cursor()
        try:
            input_rows = self._iter_input_rows(input_data)
            out_rows = [
                self._call_once(cursor, sp_args, row) for row in input_rows
            ]
            if not getattr(conn, "autocommit", False):
                conn.commit()
        finally:
            try:
                cursor.close()
            except Exception:  # noqa: BLE001 -- cleanup must not mask original
                logger.warning("[%s] cursor.close() raised; ignoring", self.id)
            if owns_connection:
                try:
                    self.oracle_manager.close(self.id)
                except Exception:  # noqa: BLE001 -- cleanup must not mask original
                    logger.warning(
                        "[%s] oracle_manager.close() raised; ignoring", self.id
                    )

        df = pd.DataFrame(out_rows)
        if self.global_map is not None:
            self.global_map.put(f"{self.id}_NB_LINE", len(df))
        logger.info(
            "[%s] Called %s %r for %d row(s)",
            self.id,
            "function" if self.config.get("is_function") else "procedure",
            self.config.get("sp_name"),
            len(df),
        )
        return {"main": df, "reject": None}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refuse_unsupported_args(self, sp_args: List[Dict[str, Any]]) -> None:
        """Refuse custom STRUCT/ARRAY types and RECORDSET ref-cursor params."""
        for arg in sp_args:
            if arg.get("is_custom"):
                raise ConfigurationError(
                    f"[{self.id}] tOracleSP custom Oracle types (STRUCT/ARRAY) "
                    f"require oracledb thick mode + type handles; not yet "
                    f"supported. Tracked in deferred items."
                )
            if _normalize_direction(arg.get("type", "")) == _DIRECTION_RECORDSET:
                raise ConfigurationError(
                    f"[{self.id}] tOracleSP RECORDSET (ref-cursor) parameters "
                    f"emit a live ResultSet to a FLOW column; this Talend "
                    f"pattern is not yet supported. Tracked in deferred items."
                )

    @staticmethod
    def _iter_input_rows(
        input_data: Optional[pd.DataFrame],
    ) -> List[Optional[Dict[str, Any]]]:
        """Yield one dict per input row, or a single ``None`` when no FLOW in."""
        if input_data is None or input_data.empty:
            return [None]
        return [row.to_dict() for _, row in input_data.iterrows()]

    def _call_once(
        self,
        cursor: Any,
        sp_args: List[Dict[str, Any]],
        row: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute one SP call, returning the assembled output row."""
        bind_args: List[Any] = []
        out_targets: List[Dict[str, Any]] = []  # {column, var}

        for arg in sp_args:
            direction = _normalize_direction(arg.get("type", _DIRECTION_IN))
            column = arg.get("column", "")
            if direction == _DIRECTION_IN:
                bind_args.append(row.get(column) if row else None)
            elif direction in (_DIRECTION_OUT, _DIRECTION_INOUT):
                var = cursor.var(_oracle_var_type(arg.get("dbtype", "")))
                if direction == _DIRECTION_INOUT and row is not None:
                    var.setvalue(0, row.get(column))
                bind_args.append(var)
                out_targets.append({"column": column, "var": var})
            else:
                # Defensive: unknown direction binds as IN value.
                bind_args.append(row.get(column) if row else None)

        return_value = None
        if self.config.get("is_function", False):
            ret_type = _oracle_var_type(self.config.get("return_bdtype", ""))
            return_value = cursor.callfunc(
                self.config["sp_name"], ret_type, bind_args
            )
        else:
            cursor.callproc(self.config["sp_name"], bind_args)

        # Assemble output row: input columns first, then OUT params, then return.
        out_row: Dict[str, Any] = dict(row) if row else {}
        for target in out_targets:
            out_row[target["column"]] = target["var"].getvalue()
        return_column = self.config.get("return_column", "")
        if self.config.get("is_function", False) and return_column:
            out_row[return_column] = return_value
        return out_row
