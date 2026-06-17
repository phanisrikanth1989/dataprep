"""Engine component for MSSqlInput (tMSSqlInput).

Reads rows from SQL Server via a SELECT query and emits them as the ``main``
FLOW DataFrame. Acquires either a shared connection (USE_EXISTING_CONNECTION +
CONNECTION ref) or an ad-hoc connection via the MSSqlConnectionManager.

Column names for the resulting DataFrame come from ``output_schema`` (the
authoritative converter-emitted schema); if absent, they fall back to
``cursor.description``.

Config keys consumed (mirrors the converter at
src/converters/talend_to_v1/components/database/mssql_input.py):
    use_existing_connection (bool, default False)
    connection            (str, default "")        -- shared-connection cid ref
    host, port, dbname, user, password             -- ad-hoc connection params
    query                 (str, REQUIRED)          -- SELECT statement
    set_query_timeout     (bool, default False)    -- apply query timeout
    query_timeout_in_seconds (int, default 30)     -- conn.timeout seconds
    trim_all_column       (bool, default False)    -- strip all string columns
    trim_column           (list[dict], default []) -- per-column trim settings
    ... + framework params

Returns: {"main": df, "reject": None}.
Side effects: publishes f"{cid}_NB_LINE" (row count) to globalMap.

Security: never logs credentials or row values (T-11-02). ASCII-only (D-H7).
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("MSSqlInput", "tMSSqlInput")
class MSSqlInput(BaseComponent):
    """tMSSqlInput engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``mssql_manager`` is injected by ETLEngine
        ``_initialize_components``."""
        super().__init__(*args, **kwargs)
        self.mssql_manager = None  # type: ignore  # set by engine

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
        if self.mssql_manager is None:
            raise ConfigurationError(
                f"[{self.id}] MSSqlConnectionManager not wired into component. "
                f"This is an engine integration error -- ETLEngine."
                f"_initialize_components must inject self.mssql_manager."
            )

        # Acquire connection (shared via manager.get / ad-hoc via open_ad_hoc).
        use_existing = self.config.get("use_existing_connection", False)
        if use_existing:
            conn = self.mssql_manager.get(self.config.get("connection", ""))
            owns_connection = False
        else:
            conn = self.mssql_manager.open_ad_hoc(self.id, self.config)
            owns_connection = True

        if self.config.get("set_query_timeout", False):
            # pyodbc applies query timeout at the connection level.
            conn.timeout = int(self.config.get("query_timeout_in_seconds") or 30)

        query = self.config["query"]
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = self._resolve_columns(cursor)
            df = self._build_dataframe(rows, columns)
            df = self._apply_trim(df)

            if self.global_map is not None:
                self.global_map.put(f"{self.id}_QUERY", query)
                self.global_map.put(f"{self.id}_NB_LINE", len(df))
            logger.info("[%s] Read %d row(s) from SQL Server", self.id, len(df))
        finally:
            try:
                cursor.close()
            except Exception:  # noqa: BLE001 -- cleanup must not mask original
                logger.warning("[%s] cursor.close() raised; ignoring", self.id)
            if owns_connection:
                try:
                    self.mssql_manager.close(self.id)
                except Exception:  # noqa: BLE001 -- cleanup must not mask original
                    logger.warning(
                        "[%s] mssql_manager.close() raised; ignoring", self.id
                    )

        return {"main": df, "reject": None}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_columns(self, cursor: Any) -> List[str]:
        """Return DataFrame column names: output_schema first, else description."""
        schema = getattr(self, "output_schema", None) or []
        if schema:
            return [col["name"] for col in schema]
        description = getattr(cursor, "description", None) or []
        return [d[0] for d in description]

    @staticmethod
    def _build_dataframe(rows: List[Any], columns: List[str]) -> pd.DataFrame:
        """Build a DataFrame from fetched rows + resolved column names.

        pyodbc returns Row objects; coerce each to a tuple so pandas builds a
        plain frame. Falls back to positional columns when widths mismatch.
        """
        plain = [tuple(r) for r in rows]
        if columns and plain and len(columns) != len(plain[0]):
            logger.warning(
                "Column count (%d) does not match row width (%d); "
                "using positional columns",
                len(columns), len(plain[0]),
            )
            return pd.DataFrame(plain)
        if columns:
            return pd.DataFrame(plain, columns=columns)
        return pd.DataFrame(plain)

    def _apply_trim(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace from string columns per TRIM_ALL_COLUMN / TRIM_COLUMN."""
        if df.empty:
            return df
        if self.config.get("trim_all_column", False):
            cols = list(df.columns)
        else:
            cols = [c for c in self._trim_column_names() if c in df.columns]
        for col in cols:
            if df[col].dtype == object:
                df[col] = df[col].map(
                    lambda v: v.strip() if isinstance(v, str) else v
                )
        return df

    def _trim_column_names(self) -> List[str]:
        """Extract column names flagged for trimming from the trim_column table."""
        entries = self.config.get("trim_column", []) or []
        names: List[str] = []
        for entry in entries:
            if isinstance(entry, dict):
                name = entry.get("column") or entry.get("schema_column")
                if name:
                    names.append(name)
        return names
