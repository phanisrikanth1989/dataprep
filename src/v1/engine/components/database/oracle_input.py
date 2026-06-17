"""Engine component for OracleInput (tOracleInput).

Reads rows from Oracle via a SELECT query and emits them as the ``main`` FLOW
DataFrame. Acquires either a shared connection (USE_EXISTING_CONNECTION +
CONNECTION ref) or an ad-hoc connection (mirrors oracle_row.py acquisition).

Column names for the resulting DataFrame come from ``output_schema`` (the
authoritative converter-emitted schema); if absent, they fall back to
``cursor.description``. BaseComponent step 7c then coerces the frame to the
declared output schema types.

Config keys consumed (mirrors the converter at
src/converters/talend_to_v1/components/database/oracle_input.py):
    use_existing_connection (bool, default False)
    connection            (str, default "")       -- shared-connection cid ref
    connection_type, host, port, dbname,          -- ad-hoc connection params
    local_service_name, rac_url, user, password      (mirror oracle_connection.py)
    query                 (str, REQUIRED)         -- SELECT statement
    use_cursor            (bool, default False)    -- server-side array fetch
    cursor_size           (int, default 1000)      -- cursor.arraysize when
                                                     use_cursor=True
    trim_all_column       (bool, default False)    -- strip all string columns
    trim_column           (list[dict], default []) -- per-column trim settings
    no_null_values        (bool, default False)    -- NULL string cols -> ""
    is_convert_xmltype    (bool, default False)    -- DEFERRED (WARNING)
    support_nls           (bool, default False)    -- DEFERRED (WARNING)
    ... + framework params

Returns: {"main": df, "reject": None}.
Side effects: publishes f"{cid}_NB_LINE" (row count) to globalMap (D-C8 parity).

Security: never logs credentials or row values (T-11-02). ASCII-only (D-H7).
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("OracleInput", "tOracleInput")
class OracleInput(BaseComponent):
    """tOracleInput engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``oracle_manager`` is injected by ETLEngine
        ``_initialize_components``."""
        super().__init__(*args, **kwargs)
        self.oracle_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only -- require the ``query`` key."""
        if "query" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'query'"
            )

    # ------------------------------------------------------------------
    # Process: acquire connection, run SELECT, build DataFrame
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Run the SELECT and return its rows as the ``main`` DataFrame.

        Returns:
            ``{"main": df, "reject": None}``.
        """
        if self.oracle_manager is None:
            raise ConfigurationError(
                f"[{self.id}] OracleConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.oracle_manager."
            )

        # Deferred-feature warnings for parameters not yet honored.
        for deferred_flag in ("is_convert_xmltype", "support_nls"):
            if self.config.get(deferred_flag, False):
                logger.warning(
                    "[%s] Config %r=True but not honored (deferred)",
                    self.id, deferred_flag,
                )

        # Acquire connection (shared via manager.get / ad-hoc via open_ad_hoc).
        use_existing = self.config.get("use_existing_connection", False)
        if use_existing:
            connection_ref = self.config.get("connection", "")
            conn = self.oracle_manager.get(connection_ref)
            owns_connection = False
        else:
            conn = self.oracle_manager.open_ad_hoc(self.id, self.config)
            owns_connection = True

        query = self.config["query"]
        cursor = conn.cursor()
        try:
            if self.config.get("use_cursor", False):
                # Server-side array fetch tuning (D-B). arraysize controls how
                # many rows oracledb buffers per round trip.
                cursor.arraysize = int(self.config.get("cursor_size") or 1000)

            cursor.execute(query)
            rows = cursor.fetchall()
            columns = self._resolve_columns(cursor)
            df = self._build_dataframe(rows, columns)
            df = self._apply_trim(df)
            df = self._apply_no_null_values(df)

            # D-C8 parity: publish resolved query + row count to globalMap.
            if self.global_map is not None:
                self.global_map.put(f"{self.id}_QUERY", query)
                self.global_map.put(f"{self.id}_NB_LINE", len(df))

            logger.info("[%s] Read %d row(s) from Oracle", self.id, len(df))
        finally:
            # WR-02: cleanup must NEVER mask the original exception.
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

        return {"main": df, "reject": None}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_columns(self, cursor: Any) -> List[str]:
        """Return DataFrame column names: output_schema first, else cursor.description."""
        schema = getattr(self, "output_schema", None) or []
        if schema:
            return [col["name"] for col in schema]
        description = getattr(cursor, "description", None) or []
        return [d[0] for d in description]

    @staticmethod
    def _build_dataframe(rows: List[Any], columns: List[str]) -> pd.DataFrame:
        """Build a DataFrame from fetched rows + resolved column names.

        Falls back to positional columns when the declared column count does
        not match the row width (defensive: a SELECT * against a wider table
        than the schema declares).
        """
        if columns and rows and len(columns) != len(rows[0]):
            logger.warning(
                "Column count (%d) does not match row width (%d); "
                "using positional columns",
                len(columns), len(rows[0]),
            )
            return pd.DataFrame(rows)
        if columns:
            return pd.DataFrame(rows, columns=columns)
        return pd.DataFrame(rows)

    def _apply_trim(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace from string columns per TRIM_ALL_COLUMN / TRIM_COLUMN."""
        if df.empty:
            return df
        if self.config.get("trim_all_column", False):
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].map(
                        lambda v: v.strip() if isinstance(v, str) else v
                    )
            return df

        trim_cols = self._trim_column_names()
        for col in trim_cols:
            if col in df.columns and df[col].dtype == object:
                df[col] = df[col].map(
                    lambda v: v.strip() if isinstance(v, str) else v
                )
        return df

    def _trim_column_names(self) -> List[str]:
        """Extract column names flagged for trimming from the trim_column table."""
        entries = self.config.get("trim_column", []) or []
        names: List[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("column") or entry.get("schema_column")
            if name:
                names.append(name)
        return names

    def _apply_no_null_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replace NULL string-column values with '' when NO_NULL_VALUES is set."""
        if df.empty or not self.config.get("no_null_values", False):
            return df
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].map(lambda v: "" if v is None else v)
        return df
