"""Engine component for OracleRow (tOracleRow).

Executes arbitrary SQL/DDL/DML against either a shared connection
(USE_EXISTING_CONNECTION + CONNECTION ref) or an ad-hoc connection.
Supports prepared statements with full PARAMETER_TYPE coverage per D-C3.

Talaxie tOracleRow_java.xml PARAMETER_TYPE enum (verified 2026-05-07):
  BigDecimal, Blob, Boolean, Byte, Bytes, Clob, Date, Double, Float,
  Int, Long, Object, Short, String, Time, Null

Source: https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleRow/tOracleRow_java.xml
(see lines 333-352 of the XML for the SET_PREPAREDSTATEMENT_PARAMETERS table.)

Open Question 2 resolution (RESEARCH.md): The Talaxie enum is 16 values.
Differences from the original RESEARCH.md "16-Type Coercion Table":
  - Talaxie HAS:    Blob, Clob, Null  (three additional values)
  - Talaxie LACKS:  Integer, BigInteger, Timestamp
                     (these were inferred from Talend documentation but are
                      not present in the actual Talaxie XML enum)

For maximum safety and Talend feature parity we map ALL of these:
  Talaxie's 16 verified values + the 3 RESEARCH.md inferred values
  (Integer / BigInteger / Timestamp) as defensive aliases.
This protects against converter emitting any of the 19 names; unknown values
still raise ConfigurationError per D-C3.

PROPAGATE_RECORD_SET=true is refused per D-C4 (Talend's live ResultSet-as-FLOW
pattern doesn't translate cleanly to DataFrame semantics; rewrite as
tOracleInput -> downstream component when this is needed).

Config keys consumed (~28 total; the converter at
src/converters/talend_to_v1/components/database/oracle_row.py emits these):
    use_existing_connection (bool, default False) -- shared vs ad-hoc connection
    connection            (str, default "")       -- cid ref of upstream
                                                     tOracleConnection (when
                                                     use_existing_connection=True)
    connection_type, host, port, dbname,          -- ad-hoc connection params
    user, password, ...                              (mirror oracle_connection.py)
    query                 (str, REQUIRED)         -- SQL/DDL/DML; goes through
                                                     engine resolution before
                                                     _process runs (BaseComponent
                                                     _resolve_expressions)
    use_nb_line           (str enum, default      -- one of NONE / NB_LINE_INSERTED
                          "NONE")                  / NB_LINE_UPDATED / NB_LINE_DELETED
    use_preparedstatement (bool, default False)
    set_preparedstatement_parameters (list[dict]) -- each entry:
                                                       {parameter_index,
                                                        parameter_type,
                                                        parameter_value}
    propagate_record_set  (bool, default False)   -- True raises
                                                     ConfigurationError per D-C4
    commit_every          (int, default 10000)    -- relevant only for
                                                     prepared-statement loops
    die_on_error          (bool, default False)   -- handled by BaseComponent
    ... + framework params

Returns: {"main": input_data, "reject": None} -- passthrough.
Side effects:
    - optionally writes f"{cid}_NB_LINE_*" globalMap key per use_nb_line (D-C5)
    - always writes f"{cid}_QUERY" (the resolved SQL) (D-C8)

Security note (T-11-01):
    The QUERY field MAY contain user-controlled SQL. The SAFE channel for
    parameter values is the prepared-statement path -- positional binds via
    cursor.execute(query, [vals]). The 19-type coercion table converts each
    bind value to a typed Python value before binding. When
    use_preparedstatement=False, the raw QUERY string is executed verbatim;
    BaseComponent._resolve_expressions has already substituted context.var
    values BEFORE _process runs. Trust boundary is internal Citi job authors.
    The component DOES NOT itself interpolate context values into SQL strings;
    that responsibility lives in BaseComponent._resolve_expressions (step 3 of
    execute()).

Logging note (T-11-02):
    logger.info logs the cid, rowcount, and use_nb_line enum -- it does NOT
    log the bound parameter values. Bound values may carry PII; the SAFE
    pattern is to log the SQL TEMPLATE only.
"""
import datetime
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# PARAMETER_TYPE coercion helpers (D-C3, RESEARCH "USE_PREPAREDSTATEMENT
# Coercion Table" updated per Talaxie XML inspection 2026-05-07)
# ----------------------------------------------------------------------

def _coerce_string(v: Any) -> Optional[str]:
    """Coerce to str. None -> None."""
    return str(v) if v is not None else None


def _coerce_int(v: Any) -> Optional[int]:
    """Coerce to int. Used for Int / Integer / Long / Short / Byte / BigInteger.
    None -> None."""
    return int(v) if v is not None else None


def _coerce_decimal(v: Any) -> Optional[Decimal]:
    """Coerce to Decimal via str (avoids float roundtrip). None -> None."""
    return Decimal(str(v)) if v is not None else None


def _coerce_bool(v: Any) -> Optional[bool]:
    """Coerce to bool. None -> None."""
    return bool(v) if v is not None else None


def _coerce_float(v: Any) -> Optional[float]:
    """Coerce to float. Used for Float and Double. None -> None."""
    return float(v) if v is not None else None


def _coerce_date(v: Any) -> Optional[datetime.date]:
    """Coerce to datetime.date. Accepts datetime / date / ISO-format str.
    None -> None.

    Raises:
        ValueError: If v is a non-None / non-date / non-str value (e.g. int).
    """
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        return datetime.date.fromisoformat(v)
    raise ValueError(f"Cannot coerce {v!r} to date")


def _coerce_timestamp(v: Any) -> Optional[datetime.datetime]:
    """Coerce to datetime.datetime. Accepts datetime / ISO-format str.
    None -> None.

    Raises:
        ValueError: If v is a non-None / non-datetime / non-str value.
    """
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v
    if isinstance(v, str):
        return datetime.datetime.fromisoformat(v)
    raise ValueError(f"Cannot coerce {v!r} to timestamp")


def _coerce_time(v: Any) -> Optional[datetime.time]:
    """Coerce to datetime.time. Accepts time / ISO-format str. None -> None.

    Raises:
        ValueError: If v is a non-None / non-time / non-str value.
    """
    if v is None:
        return None
    if isinstance(v, datetime.time):
        return v
    if isinstance(v, str):
        return datetime.time.fromisoformat(v)
    raise ValueError(f"Cannot coerce {v!r} to time")


def _coerce_bytes(v: Any) -> Optional[bytes]:
    """Coerce to bytes. Accepts bytes / str (utf-8 encoded). Used for Bytes
    and Blob (Talaxie). None -> None.

    Raises:
        ValueError: If v is a non-None / non-bytes / non-str value.
    """
    if v is None:
        return None
    if isinstance(v, bytes):
        return v
    if isinstance(v, str):
        return v.encode("utf-8")
    raise ValueError(f"Cannot coerce {v!r} to bytes")


def _coerce_clob(v: Any) -> Optional[str]:
    """Coerce to str for Clob (character LOB). Talaxie-specific.

    oracledb thin mode handles long string binds natively; we just ensure the
    payload is a str. None -> None.
    """
    return str(v) if v is not None else None


def _coerce_null(v: Any) -> None:
    """Always None -- Talaxie's PARAMETER_TYPE='Null' explicitly binds SQL NULL
    regardless of the PARAMETER_VALUE expression result.

    oracledb maps Python None to SQL NULL.
    """
    return None


def _passthrough(v: Any) -> Any:
    """Identity coercer. Used for Object (no Python -> SQL coercion needed)."""
    return v


# Mapping of PARAMETER_TYPE name (Talaxie verified + RESEARCH inferred aliases)
# -> coercer function. Unknown names raise ConfigurationError in
# _coerce_prepared_param() (D-C3 contract: closed-list enum).
_PARAM_TYPE_COERCERS: Dict[str, Any] = {
    # --- Talaxie tOracleRow_java.xml verified values (16, lines 336-352) ---
    "BigDecimal":  _coerce_decimal,
    "Blob":        _coerce_bytes,    # Talaxie-only; binary LOB binds as bytes
    "Boolean":     _coerce_bool,
    "Byte":        _coerce_int,
    "Bytes":       _coerce_bytes,
    "Clob":        _coerce_clob,     # Talaxie-only; character LOB binds as str
    "Date":        _coerce_date,
    "Double":      _coerce_float,
    "Float":       _coerce_float,
    "Int":         _coerce_int,
    "Long":        _coerce_int,
    "Object":      _passthrough,
    "Short":       _coerce_int,
    "String":      _coerce_string,
    "Time":        _coerce_time,
    "Null":        _coerce_null,     # Talaxie-only; explicit SQL NULL bind
    # --- RESEARCH.md inferred aliases (defensive; not in Talaxie XML enum but
    #     may appear if a Talend variant or custom palette emits them) ---
    "Integer":     _coerce_int,
    "BigInteger":  _coerce_int,
    "Timestamp":   _coerce_timestamp,
}


def _coerce_prepared_param(param: Dict[str, Any]) -> Any:
    """Apply the right coercer for a single SET_PREPAREDSTATEMENT_PARAMETERS row.

    Args:
        param: Dict with keys parameter_index, parameter_type, parameter_value.

    Returns:
        The coerced bind value (or None for SQL NULL).

    Raises:
        ConfigurationError: If parameter_type is not in _PARAM_TYPE_COERCERS.
    """
    p_type = param.get("parameter_type", "Object")
    p_value = param.get("parameter_value", None)
    coercer = _PARAM_TYPE_COERCERS.get(p_type)
    if coercer is None:
        raise ConfigurationError(
            f"Unknown PARAMETER_TYPE {p_type!r}. "
            f"Supported: {sorted(_PARAM_TYPE_COERCERS.keys())}"
        )
    return coercer(p_value)


# ----------------------------------------------------------------------
# OracleRow component
# ----------------------------------------------------------------------

_VALID_USE_NB_LINE = frozenset(
    {"NONE", "NB_LINE_INSERTED", "NB_LINE_UPDATED", "NB_LINE_DELETED"}
)


@REGISTRY.register("OracleRow", "tOracleRow")
class OracleRow(BaseComponent):
    """tOracleRow engine component. See module docstring."""

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

        Per Phase 7.1 Rule 12 (D-F3), we verify required keys exist and enum
        values are in the closed set; we do NOT inspect resolved values
        (PROPAGATE_RECORD_SET refusal lives in ``_process`` -- it can fire
        only after context resolution has substituted context.var values).
        """
        if "query" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'query'"
            )

        use_nb_line = self.config.get("use_nb_line", "NONE")
        if use_nb_line not in _VALID_USE_NB_LINE:
            raise ConfigurationError(
                f"[{self.id}] Invalid use_nb_line {use_nb_line!r}. "
                f"Must be one of: {sorted(_VALID_USE_NB_LINE)}"
            )

        if self.config.get("use_preparedstatement", False):
            params = self.config.get("set_preparedstatement_parameters", [])
            if not isinstance(params, list):
                raise ConfigurationError(
                    f"[{self.id}] set_preparedstatement_parameters must be "
                    f"a list, got {type(params).__name__}"
                )
            for i, p in enumerate(params):
                if not isinstance(p, dict):
                    raise ConfigurationError(
                        f"[{self.id}] set_preparedstatement_parameters[{i}] "
                        f"must be a dict, got {type(p).__name__}"
                    )
                p_type = p.get("parameter_type", "Object")
                if p_type not in _PARAM_TYPE_COERCERS:
                    raise ConfigurationError(
                        f"[{self.id}] set_preparedstatement_parameters[{i}] "
                        f"has unsupported parameter_type {p_type!r}. "
                        f"Supported: {sorted(_PARAM_TYPE_COERCERS.keys())}"
                    )

    # ------------------------------------------------------------------
    # Process: acquire connection, execute SQL, optionally publish stats
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Acquire connection (shared or ad-hoc), execute query, publish stats.

        Args:
            input_data: Upstream FLOW DataFrame (passthrough -- tOracleRow does
                not transform input rows; it executes a single SQL statement).

        Returns:
            ``{"main": input_data, "reject": None}`` -- input passes through.
        """
        if self.oracle_manager is None:
            raise ConfigurationError(
                f"[{self.id}] OracleConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.oracle_manager."
            )

        # D-C4: PROPAGATE_RECORD_SET is a CONTENT check (Rule 12) -- after
        # context resolution, refuse if True.
        if self.config.get("propagate_record_set", False):
            raise ConfigurationError(
                f"[{self.id}] tOracleRow PROPAGATE_RECORD_SET emits a live "
                f"ResultSet to a downstream FLOW column; this Talend pattern "
                f"doesn't translate cleanly to DataFrame semantics. Tracked in "
                f"deferred items -- rewrite as tOracleInput -> downstream "
                f"component when this is needed."
            )

        # Acquire connection (shared via manager.get / ad-hoc via open_ad_hoc)
        use_existing = self.config.get("use_existing_connection", False)
        if use_existing:
            connection_ref = self.config.get("connection", "")
            conn = self.oracle_manager.get(connection_ref)
            owns_connection = False
        else:
            conn = self.oracle_manager.open_ad_hoc(self.id, self.config)
            owns_connection = True

        query = self.config["query"]
        use_nb_line = self.config.get("use_nb_line", "NONE")
        use_prepared = self.config.get("use_preparedstatement", False)

        cursor = conn.cursor()
        try:
            if use_prepared:
                params = self.config.get("set_preparedstatement_parameters", [])
                # Sort by parameter_index for positional bind. parameter_index
                # may be "1"/"2"/... (str from Talend XML) or 1/2/... (int).
                ordered = sorted(
                    params, key=lambda r: int(r.get("parameter_index", 0))
                )
                bound_values = [_coerce_prepared_param(p) for p in ordered]
                # T-11-02: do NOT log bound_values; they may carry PII.
                cursor.execute(query, bound_values)
            else:
                cursor.execute(query)

            # D-C5: USE_NB_LINE counter
            rowcount = cursor.rowcount
            if rowcount is None or rowcount < 0:
                if use_nb_line != "NONE":
                    logger.warning(
                        "[%s] use_nb_line=%s set but cursor.rowcount=%s "
                        "(DDL or unknown); writing 0",
                        self.id, use_nb_line, rowcount,
                    )
                rowcount = 0

            if use_nb_line != "NONE" and self.global_map is not None:
                self.global_map.put(
                    f"{self.id}_{use_nb_line}", int(rowcount or 0)
                )

            # D-C8: publish resolved query (post-resolution string)
            if self.global_map is not None:
                self.global_map.put(f"{self.id}_QUERY", query)

            # Commit if autocommit not set on the connection (Talend default
            # is auto-commit semantics per statement; for shared connections
            # we honor whatever the upstream tOracleConnection set).
            if not getattr(conn, "autocommit", False):
                conn.commit()

            logger.info(
                "[%s] Executed query (rowcount=%s, use_nb_line=%s)",
                self.id, rowcount, use_nb_line,
            )
        finally:
            # WR-02: cleanup must NEVER mask the original exception. If
            # cursor.execute raised (e.g. ORA-00942) and cursor.close() also
            # raises (some drivers raise on bad-state cursors), Python would
            # replace the meaningful SQL error with the close-time error.
            # Mirror oracle_output.py:1008-1018 -- swallow cleanup errors and
            # log a warning instead.
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

        # Pass through input (tOracleRow has FLOW out as passthrough)
        return {"main": input_data, "reject": None}
