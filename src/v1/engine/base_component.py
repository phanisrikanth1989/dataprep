"""Base component class for all ETL engine components.

Provides the template method lifecycle: validate -> snapshot -> resolve -> process -> stats -> restore.
Subclasses MUST implement _validate_config() and _process().

Fixes applied:
- ENG-03: Array resolution via ContextManager.resolve_dict (eliminates old replace_in_config [i] bug)
- ENG-07/ENG-20: Streaming mode collects BOTH main and reject data
- ENG-08: _validate_config is abstract -- every subclass must implement (per D-13)
- ENG-09/ENG-21: Config immutability -- _original_config is deepcopied at construction, config
  re-derived from _original_config at start of each execute()
- ENG-16: Standardized template method lifecycle (per D-11)
- ENG-17: Named flow routing -- _process() returns dict with arbitrary keys
- ENG-19: validate_schema nullable logic corrected (nullable=True allows NaN, not fills with 0)
- NEW-03: Fixed __repr__ missing opening paren

Phase 7.1 fixes:
- CR-01: Reject schema validated with relaxed nullability (deepcopy + force nullable=True)
- CR-02: _apply_decimal_precision coerces string precision to int before use
- WR-01/G-01: Missing datetime columns filled with pd.NaT (nullable) or pd.Timestamp(0) (non-nullable)
- WR-02: Missing columns use pd.Series construction to preserve dtype on empty DataFrames
- WR-03: Removed empty-DataFrame early-exit guards in _enforce_schema_column_order and
  _apply_output_schema_validation so empty results still get column order + schema validation
- G-02: Decimal columns without precision coerced to Decimal objects in _coerce_column_type
- G-03: Float columns with declared precision get rounded to that precision
- G-04: date_pattern attribute used for datetime parsing; Talend default chain -> ISO 8601 -> inference
- G-05/D-11: die_on_error=False routes schema-violating rows to reject with errorCode=SCHEMA_VIOLATION
- G-10/D-12: _execute_streaming runs schema validation per chunk, not after concatenation
- G-12/D-10: treat_empty_as_null per-column attribute (default True for numeric/datetime/Decimal,
  False for str) controls empty-string-to-null coercion
- D-21: User columns named errorMessage or errorCode renamed to *_user with warning log
"""
import copy
import logging
import time
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from typing import Any, Optional

import numpy as np
import pandas as pd

from .exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    DataValidationError,
    SchemaError,
)

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes for components."""
    BATCH = "batch"         # Process entire dataframe at once
    STREAMING = "streaming"  # Process in chunks
    HYBRID = "hybrid"        # Auto-switch based on data size


class ComponentStatus(Enum):
    """Component execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


# Java-style date pattern tokens -> strptime tokens
_JAVA_DATE_TOKENS = {
    "yyyy": "%Y",
    "yy": "%y",
    "MM": "%m",
    "dd": "%d",
    "HH": "%H",
    "hh": "%I",
    "mm": "%M",
    "ss": "%S",
    "SSS": "%f",
}

# Talend default datetime parse chain (tried in order when no date_pattern specified)
_TALEND_DEFAULT_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
]

# Column types that default treat_empty_as_null=True
_NUMERIC_LIKE_TYPES = {"int", "float", "bool", "datetime", "Decimal"}

# Reserved reject-flow column names
_RESERVED_REJECT_COLS = {"errorCode", "errorMessage"}


def _java_pattern_to_strptime(java_pattern: str) -> str:
    """Convert a Java SimpleDateFormat pattern to a Python strptime format string.

    Handles the tokens used in Talend schemas: yyyy, MM, dd, HH, hh, mm, ss, SSS.

    Args:
        java_pattern: Java date pattern (e.g. "dd/MM/yyyy HH:mm:ss").

    Returns:
        Python strptime format string (e.g. "%d/%m/%Y %H:%M:%S").
    """
    result = java_pattern
    # Replace longest tokens first to avoid partial replacement (e.g. MM before M)
    for token in sorted(_JAVA_DATE_TOKENS, key=len, reverse=True):
        result = result.replace(token, _JAVA_DATE_TOKENS[token])
    return result


class BaseComponent(ABC):
    """Base class for all ETL engine components.

    Implements the Template Method pattern. The ``execute()`` method provides
    a fixed lifecycle that subclasses hook into via ``_validate_config()``
    and ``_process()``. Subclasses MUST NOT override ``execute()``.

    Lifecycle per execute() call:
        1. Fresh config from _original_config (deepcopy)
        2. _validate_config() -- abstract, raises ConfigurationError
        3. _resolve_expressions() -- Java markers + context variable resolution
        4. Read die_on_error from resolved config
        5. _select_mode() -- auto-select BATCH/STREAMING
        6. _execute_batch() or _execute_streaming() -> calls _process()
        7b. _enforce_schema_column_order() -- per-flow column ordering + missing-col fill
        7c. _apply_output_schema_validation() -- type coercion, precision, length, reject routing
        8. _update_stats_from_result() + _update_global_map()

    Config Immutability (ENG-09/ENG-21):
        ``_original_config`` is deepcopied at construction and NEVER mutated.
        ``config`` is re-derived from ``_original_config`` at the start of every
        ``execute()`` call, so iterate re-execution always starts clean.

    Schema Validation Contract (Phase 7.1):
        Subclasses MUST NOT call validate_schema() inside _process(). The base class
        runs validation automatically in step 7c (_apply_output_schema_validation) AFTER
        _process returns. Calling it inside _process double-validates and races with
        _enforce_schema_column_order's missing-column fill.
    """

    # Memory threshold for auto-switching to streaming mode (in MB)
    MEMORY_THRESHOLD_MB = 5120

    # Python type string -> pandas dtype mapping for validate_schema.
    # Only the 7 canonical Python type strings are supported.
    # Talend id_* types are converted to Python types by the converter layer
    # (src/converters/talend_to_v1/type_mapping.py) before reaching the engine.
    _TYPE_MAPPING: dict[str, str] = {
        "str": "object",
        "int": "int64",
        "float": "float64",
        "bool": "bool",
        "datetime": "datetime64[ns]",
        "Decimal": "object",
        "object": "object",
    }

    def __init__(
        self,
        component_id: str,
        config: dict,
        global_map=None,
        context_manager=None,
    ):
        """Initialize a component.

        Args:
            component_id: Unique identifier for this component instance.
            config: Component configuration dictionary. Deepcopied and frozen
                as ``_original_config``. Working ``config`` is empty until
                ``execute()`` is called.
            global_map: GlobalMap instance for stats and variable storage.
            context_manager: ContextManager instance for variable resolution.
        """
        self.id = component_id
        self._original_config = copy.deepcopy(config)
        self.config: dict = {}  # Populated at start of each execute() from _original_config
        self.global_map = global_map
        self.context_manager = context_manager

        # Component metadata
        self.component_type = config.get("component_type", self.__class__.__name__)

        # Execution state
        self.status = ComponentStatus.PENDING
        self.stats = self._default_stats()
        self.execution_mode = ExecutionMode.BATCH
        self.die_on_error = True

        # Java bridge (set by engine if Java is enabled)
        self.java_bridge = None

        # Python routine manager (set by engine if Python is enabled)
        self.python_routine_manager = None

    # ------------------------------------------------------------------
    # Template Method Lifecycle
    # ------------------------------------------------------------------

    def execute(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Template method lifecycle. Override _validate_config() and _process(), not this.

        Args:
            input_data: Input DataFrame from upstream component, or None for
                source components.

        Returns:
            dict with at least a ``main`` key (DataFrame or None), and
            optionally ``reject``, ``stats``, and other named flow keys.

        Raises:
            ConfigurationError: If _validate_config() fails.
            ComponentExecutionError: If _process() or other step fails.
        """
        self.status = ComponentStatus.RUNNING
        self._stats_set_by_component = False
        start_time = time.time()

        try:
            # Step 1: Fresh config from original (addresses ENG-09/ENG-21)
            self.config = copy.deepcopy(self._original_config)

            # Step 2: Validate configuration (addresses ENG-08, per D-13 -- abstract)
            self._validate_config()

            # Step 3: Resolve expressions (Java markers + context variables)
            self._resolve_expressions()

            # Step 4: Read die_on_error from resolved config
            self.die_on_error = self.config.get("die_on_error", True)

            # Step 5: Capture input row count for NB_LINE (Talend convention)
            self._input_row_count = self._count_input_rows(input_data)

            # Step 6: Select execution mode
            mode = self._select_mode(input_data)

            # Step 7: Execute based on mode
            if mode == ExecutionMode.STREAMING:
                result = self._execute_streaming(input_data)  # type: ignore[arg-type]
            else:
                result = self._execute_batch(input_data)
                # Step 7b: Enforce output schema column order
                result = self._enforce_schema_column_order(result)
                # Step 7c: Validate and coerce output against output_schema
                result = self._apply_output_schema_validation(result)

            # Step 8: Update stats and globalMap
            self._update_stats_from_result(result)
            self._update_global_map()

            self.status = ComponentStatus.SUCCESS
            elapsed = time.time() - start_time
            logger.info(
                f"[{self.id}] completed in {elapsed:.2f}s - "
                f"NB_LINE:{self.stats['NB_LINE']} OK:{self.stats['NB_LINE_OK']} "
                f"REJECT:{self.stats['NB_LINE_REJECT']}"
            )

            # Attach stats to result for engine consumption
            result["stats"] = self.stats.copy()
            return result

        except ConfigurationError:
            self.status = ComponentStatus.ERROR
            raise
        except Exception as e:
            self.status = ComponentStatus.ERROR
            logger.error(f"[{self.id}] failed: {e}")
            raise ComponentExecutionError(self.id, str(e), cause=e) from e

    # ------------------------------------------------------------------
    # Abstract Methods -- Subclasses MUST Implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate component configuration. Raise ConfigurationError if invalid.

        Every component MUST implement this. Called before every execute().
        Access ``self.config`` which has been freshly deepcopied from
        ``_original_config`` but NOT yet resolved (context variables still
        present). Validate structural correctness -- required keys, valid
        enum values, etc.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        ...

    @abstractmethod
    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Process data. Return dict with 'main' key and optionally 'reject' and other named flows.

        Args:
            input_data: Input DataFrame, or None for source components.

        Returns:
            dict with keys:
                - ``main``: output DataFrame (or None)
                - ``reject``: rejected rows DataFrame (or None)
                - any other named flow keys for multi-output components

        Note:
            Subclasses MUST NOT call self.validate_schema() inside _process().
            The base class runs validation automatically in step 7c
            (_apply_output_schema_validation) AFTER _process returns.
        """
        ...

    # ------------------------------------------------------------------
    # Expression Resolution
    # ------------------------------------------------------------------

    def _resolve_expressions(self) -> None:
        """Resolve Java markers and context variables in config.

        Resolution order:
            1. Java {{java}} markers (delegated to JavaBridgeManager)
            2. Context variables via ContextManager.resolve_dict()

        The rewritten ContextManager.resolve_dict() handles:
            - SKIP_RESOLUTION_KEYS (python_code, java_code, imports)
            - Nested dict recursion
            - List-of-dict recursion (fixes ENG-03 literal [i] bug)
        """
        # Java expression resolution
        if self.java_bridge:
            self._resolve_java_expressions()

        # Context variable resolution
        if self.context_manager:
            self.config = self.context_manager.resolve_dict(self.config)

    def _resolve_java_expressions(self) -> None:
        """Resolve Java expressions marked with {{java}} prefix in config.

        Uses batch execution for efficiency. Syncs context and globalMap to
        the Java bridge before evaluation.
        """
        # Collect all Java expressions from config
        java_expressions: dict[str, str] = {}

        def _scan_config(obj, path=""):
            """Recursively scan config for {{java}} markers."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    _scan_config(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _scan_config(item, f"{path}[{i}]")
            elif isinstance(obj, str) and obj.startswith("{{java}}"):
                expression = obj[8:]  # Remove marker
                java_expressions[path] = expression

        _scan_config(self.config)

        if not java_expressions:
            return

        if not self.java_bridge:
            logger.warning(
                f"[{self.id}] Java expressions found but no Java bridge available"
            )
            return

        # Sync context to Java bridge before executing
        if self.context_manager:
            current_context = self.context_manager.get_all()
            for key, value in current_context.items():
                self.java_bridge.set_context(key, value)

        # Sync globalMap to Java bridge
        if self.global_map:
            gm_all = self.global_map.get_all()
            logger.debug(
                f"[{self.id}] Syncing {len(gm_all)} globalMap variables to Java"
            )
            for key, value in gm_all.items():
                self.java_bridge.set_global_map(key, value)

        # Execute all Java expressions in batch
        try:
            logger.info(f"[{self.id}] Executing Java expressions: {java_expressions}")
            results = self.java_bridge.execute_batch_one_time_expressions(
                java_expressions
            )
            logger.info(f"[{self.id}] Java expression results: {results}")
        except Exception as e:
            logger.error(f"[{self.id}] Failed to resolve Java expressions: {e}")
            raise

        # Replace marked expressions with resolved values
        def _replace_in_config(obj, path=""):
            """Recursively replace resolved expressions in config."""
            if isinstance(obj, dict):
                for key, value in list(obj.items()):
                    current_path = f"{path}.{key}" if path else key
                    if current_path in results:
                        result_value = results[current_path]
                        if isinstance(result_value, str) and result_value.startswith(
                            "{{ERROR}}"
                        ):
                            error_msg = result_value[9:]
                            raise RuntimeError(
                                f"Error in Java expression at {current_path}: {error_msg}"
                            )
                        logger.info(
                            f"[{self.id}] Replaced {current_path}: "
                            f"'{value}' -> '{result_value}'"
                        )
                        obj[key] = result_value
                    else:
                        _replace_in_config(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]"  # FIX ENG-03: was f"{path}[i]"
                    if current_path in results:
                        result_value = results[current_path]
                        if isinstance(result_value, str) and result_value.startswith(
                            "{{ERROR}}"
                        ):
                            error_msg = result_value[9:]
                            raise RuntimeError(
                                f"Error in Java expression at {current_path}: {error_msg}"
                            )
                        obj[i] = result_value
                    else:
                        _replace_in_config(item, current_path)

        _replace_in_config(self.config)
        logger.debug(
            f"[{self.id}] Resolved {len(java_expressions)} Java expression(s)"
        )

    # ------------------------------------------------------------------
    # Execution Modes
    # ------------------------------------------------------------------

    def _select_mode(self, input_data: Optional[pd.DataFrame]) -> ExecutionMode:
        """Auto-select execution mode based on config and data size.

        Args:
            input_data: Input DataFrame or None.

        Returns:
            ExecutionMode to use for this execution.
        """
        # Respect explicit config
        mode_str = self.config.get("execution_mode", "hybrid")
        if mode_str == "batch":
            return ExecutionMode.BATCH
        if mode_str == "streaming":
            return ExecutionMode.STREAMING

        # Hybrid: auto-select based on data size
        if input_data is None:
            return ExecutionMode.BATCH

        if isinstance(input_data, pd.DataFrame):
            memory_usage_mb = (
                input_data.memory_usage(deep=True).sum() / (1024 * 1024)
            )
            if memory_usage_mb > self.MEMORY_THRESHOLD_MB:
                logger.info(
                    f"[{self.id}] Switching to STREAMING mode "
                    f"(data size: {memory_usage_mb:.2f} MB)"
                )
                return ExecutionMode.STREAMING

        return ExecutionMode.BATCH

    def _execute_batch(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Process entire dataset at once.

        Args:
            input_data: Input DataFrame or None.

        Returns:
            Result dict from _process().
        """
        return self._process(input_data)

    def _execute_streaming(self, input_data: pd.DataFrame) -> dict:
        """Process data in chunks. Runs schema validation per chunk (G-10/D-12).

        Per-chunk validation keeps memory bounded and routes reject rows correctly
        from each chunk. Schema validation (steps 7b/7c) runs inside the chunk loop,
        NOT after the final concat.

        Also collects ALL named flow outputs (ENG-07/ENG-20 fix).

        Args:
            input_data: Input DataFrame to chunk and process.

        Returns:
            dict with 'main' key (always present) and any other named flow
            keys returned by _process(), containing concatenated results.
        """
        if input_data is None:
            return self._process(None)

        chunk_size = self.config.get("chunk_size", 10000)
        flow_chunks: dict[str, list[pd.DataFrame]] = {}
        all_flow_keys: set[str] = set()

        for start in range(0, len(input_data), chunk_size):
            chunk = input_data.iloc[start: start + chunk_size].copy()
            chunk_result = self._process(chunk)

            # Apply schema validation per chunk (G-10/D-12 fix)
            chunk_result = self._enforce_schema_column_order(chunk_result)
            chunk_result = self._apply_output_schema_validation(chunk_result)

            for key, value in chunk_result.items():
                all_flow_keys.add(key)
                if isinstance(value, pd.DataFrame) and len(value) > 0:
                    flow_chunks.setdefault(key, []).append(value)

        result = {}
        for key in all_flow_keys:
            if key in flow_chunks:
                result[key] = pd.concat(flow_chunks[key], ignore_index=True)
            else:
                result[key] = None

        # Ensure 'main' always exists
        if "main" not in result:
            result["main"] = pd.DataFrame()
        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def _default_stats(self) -> dict[str, int]:
        """Return default stats dict with zeroed counters."""
        return {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}

    @staticmethod
    def _count_input_rows(input_data) -> int:
        """Count rows in input_data (DataFrame, dict of DataFrames, or None)."""
        if input_data is None:
            return 0
        if isinstance(input_data, pd.DataFrame):
            return len(input_data)
        if isinstance(input_data, dict):
            # Multiple inputs -- sum all DataFrames
            total = 0
            for v in input_data.values():
                if isinstance(v, pd.DataFrame):
                    total += len(v)
            return total
        return 0

    def _update_stats_from_result(self, result: dict) -> None:
        """Update stats from _process result.

        Talend convention:
          NB_LINE        = rows read (input) for transforms; rows produced for sources
          NB_LINE_OK     = rows produced on main output
          NB_LINE_REJECT = rows produced on reject output

        If a component already set stats via _update_stats() inside _process(),
        this method is a no-op to avoid double-counting.

        Args:
            result: Dict returned by _process() or _execute_streaming().
        """
        # If component already set stats manually, respect those values
        if self._stats_set_by_component:
            return

        main_df = result.get("main")
        reject_df = result.get("reject")
        main_count = (
            len(main_df)
            if main_df is not None and isinstance(main_df, pd.DataFrame) and not main_df.empty
            else 0
        )
        reject_count = (
            len(reject_df)
            if reject_df is not None and isinstance(reject_df, pd.DataFrame) and not reject_df.empty
            else 0
        )
        # Source components (no input) use output count for NB_LINE
        input_rows = getattr(self, "_input_row_count", 0)
        if input_rows > 0:
            self.stats["NB_LINE"] += input_rows
        else:
            self.stats["NB_LINE"] += main_count + reject_count
        self.stats["NB_LINE_OK"] += main_count
        self.stats["NB_LINE_REJECT"] += reject_count

    def _update_stats(self, rows_read: int = 0, rows_ok: int = 0, rows_reject: int = 0) -> None:
        """Helper to manually update statistics.

        When called from _process(), marks stats as component-managed so that
        _update_stats_from_result() will not double-count.

        Args:
            rows_read: Total rows read/processed.
            rows_ok: Rows that passed successfully.
            rows_reject: Rows that were rejected.
        """
        self._stats_set_by_component = True
        self.stats["NB_LINE"] += rows_read
        self.stats["NB_LINE_OK"] += rows_ok
        self.stats["NB_LINE_REJECT"] += rows_reject

    def _update_global_map(self) -> None:
        """Push stats to globalMap."""
        if self.global_map:
            for stat_name, stat_value in self.stats.items():
                self.global_map.put_component_stat(self.id, stat_name, stat_value)

    # ------------------------------------------------------------------
    # Output Column Ordering
    # ------------------------------------------------------------------

    def _enforce_schema_column_order(self, result: dict) -> dict:
        """Reorder output DataFrame columns to match the output/reject schema.

        The output schema is the authoritative source for column order.
        Components may produce columns in any order internally; this method
        ensures the final output matches the schema contract.

        Also enforces column order on the 'reject' DataFrame using reject_schema.
        Applies to empty DataFrames (WR-03 fix: no empty early-exit guard).

        Phase 7.1 fixes (WR-01, WR-02, WR-03):
            - Missing datetime columns: pd.NaT (nullable) or pd.Timestamp(0) (non-nullable)
            - Missing columns use pd.Series construction so dtype is preserved on empty frames
            - No early-exit for empty DataFrames -- ordering applies cheaply to empty

        Args:
            result: The dict returned by _process().

        Returns:
            The same dict with DataFrame columns reordered.
        """
        output_schema = getattr(self, "output_schema", None)
        if not output_schema:
            return result

        main_df = result.get("main")
        # WR-03 fix: removed `or main_df.empty` early-exit so empty DFs get column fill
        if main_df is None or not isinstance(main_df, pd.DataFrame):
            return result

        # Build ordered column list from schema
        schema_cols = [
            col["name"] for col in output_schema
            if isinstance(col, dict) and "name" in col
        ]
        if not schema_cols:
            return result

        # Add any schema columns missing from DataFrame as type-appropriate defaults.
        # WR-01/WR-02: use pd.Series construction so dtype is correct on empty DFs.
        missing = [c for c in schema_cols if c not in main_df.columns]
        if missing:
            schema_by_name = {
                col["name"]: col for col in output_schema
                if isinstance(col, dict) and "name" in col
            }
            for col in missing:
                col_def = schema_by_name.get(col, {})
                main_df[col] = self._make_default_series(col_def, len(main_df))

        # Reorder: schema columns first, then any extras not in schema (safety).
        ordered = [c for c in schema_cols if c in main_df.columns]
        extra = [c for c in main_df.columns if c not in ordered]
        final_order = ordered + extra

        if final_order != list(main_df.columns):
            result["main"] = main_df[final_order]
        else:
            result["main"] = main_df

        # Also enforce column order on reject flow using reject_schema
        reject_schema = getattr(self, "reject_schema", None)
        reject_df = result.get("reject")
        if (
            reject_schema
            and reject_df is not None
            and isinstance(reject_df, pd.DataFrame)
        ):
            # WR-02 fix: take a working copy before any mutation so that CoW
            # column assignments are captured and result["reject"] is always
            # written back with the final state.
            reject_df = reject_df.copy()
            # WR-03 fix: no empty guard -- apply ordering even to empty reject DataFrames
            reject_cols = [
                col["name"] for col in reject_schema
                if isinstance(col, dict) and "name" in col
            ]
            if reject_cols:
                reject_missing = [c for c in reject_cols if c not in reject_df.columns]
                if reject_missing:
                    reject_by_name = {
                        col["name"]: col for col in reject_schema
                        if isinstance(col, dict) and "name" in col
                    }
                    for col in reject_missing:
                        col_def = reject_by_name.get(col, {})
                        reject_df[col] = self._make_default_series(col_def, len(reject_df))

                r_ordered = [c for c in reject_cols if c in reject_df.columns]
                r_extra = [c for c in reject_df.columns if c not in r_ordered]
                r_final = r_ordered + r_extra
                result["reject"] = reject_df[r_final]
            else:
                result["reject"] = reject_df

        return result

    @staticmethod
    def _make_default_series(col_def: dict, length: int) -> pd.Series:
        """Create a type-appropriate default Series for a missing schema column.

        Uses pd.Series construction (not scalar broadcast) so that dtype is
        preserved even on empty DataFrames (WR-02 fix).

        Phase 7.1 WR-01/G-01: datetime columns use pd.NaT (nullable) or
        pd.Timestamp(0) (non-nullable) instead of pd.NA/"".

        Args:
            col_def: Column definition dict with 'type', 'nullable' keys.
            length: Number of rows (0 for empty DataFrames).

        Returns:
            pd.Series with the correct dtype and default values.
        """
        col_type = col_def.get("type", "str")
        nullable = col_def.get("nullable", True)

        if col_type == "datetime":
            if nullable:
                return pd.Series([pd.NaT] * length, dtype="datetime64[ns]")
            else:
                return pd.Series([pd.Timestamp(0)] * length, dtype="datetime64[ns]")
        elif col_type == "int":
            if nullable:
                return pd.Series([pd.NA] * length, dtype="Int64")
            else:
                return pd.Series([0] * length, dtype="int64")
        elif col_type == "float":
            if nullable:
                return pd.Series([np.nan] * length, dtype="float64")
            else:
                return pd.Series([0.0] * length, dtype="float64")
        elif col_type == "bool":
            if nullable:
                return pd.Series([pd.NA] * length, dtype="boolean")
            else:
                return pd.Series([False] * length, dtype="bool")
        elif col_type == "str":
            if nullable:
                return pd.Series([pd.NA] * length, dtype="string")
            else:
                return pd.Series([""] * length, dtype="string")
        elif col_type == "Decimal":
            default_val = pd.NA if nullable else Decimal("0")
            return pd.Series([default_val] * length, dtype="object")
        else:
            # Unknown type: nullable -> NA, non-nullable -> empty string
            if nullable:
                return pd.Series([pd.NA] * length, dtype="object")
            else:
                return pd.Series([""] * length, dtype="object")

    # ------------------------------------------------------------------
    # Output Schema Validation (applied automatically by execute())
    # ------------------------------------------------------------------

    def _apply_output_schema_validation(self, result: dict) -> dict:
        """Apply validate_schema to 'main' and 'reject' DataFrames.

        Called automatically by execute() after _process(). This ensures
        type coercion, string length truncation, and precision formatting
        are applied consistently for all components without requiring each
        to call validate_schema manually.

        Phase 7.1 fixes:
            - CR-01: reject DataFrame validated with all-nullable schema (deepcopy + force True)
            - WR-03: no empty-DataFrame early-exit; validation applies to empty DFs
            - G-05/D-11: when die_on_error=False, schema violations route to reject
              instead of raising DataValidationError
            - D-21: user columns named errorMessage/errorCode renamed to *_user before
              the engine attaches its own reject diagnostic columns

        Args:
            result: The dict returned by _process().

        Returns:
            The same dict with DataFrames validated against their schemas.
        """
        # D-21: rename reserved column names in user data before any validation
        result = self._rename_reserved_reject_columns(result)

        die_on_error = getattr(self, "die_on_error", True)

        # Validate main output
        output_schema = getattr(self, "output_schema", None)
        if output_schema:
            main_df = result.get("main")
            if main_df is not None and isinstance(main_df, pd.DataFrame):
                # WR-03 fix: removed `not main_df.empty` guard
                if die_on_error:
                    result["main"] = self.validate_schema(main_df, output_schema)
                else:
                    # G-05/D-11: route violations to reject instead of raising
                    result = self._validate_with_reject_routing(
                        result, main_df, output_schema
                    )

        # Validate reject output
        # CR-01 fix: deepcopy reject_schema and force all columns nullable=True
        reject_schema = getattr(self, "reject_schema", None)
        if reject_schema:
            reject_df = result.get("reject")
            if reject_df is not None and isinstance(reject_df, pd.DataFrame):
                # WR-03 fix: removed `not reject_df.empty` guard
                # CR-01 fix: relax nullability on reject to avoid crashing on rejected NULLs
                reject_schema_relaxed = copy.deepcopy(reject_schema)
                for col_def in reject_schema_relaxed:
                    col_def["nullable"] = True
                result["reject"] = self.validate_schema(reject_df, reject_schema_relaxed)

        return result

    def _rename_reserved_reject_columns(self, result: dict) -> dict:
        """Rename user-defined columns that collide with engine reject column names.

        D-21: The engine reserves 'errorCode' and 'errorMessage' for reject flow
        diagnostics. If user data contains columns with these names IN THE MAIN FLOW,
        they are renamed to '{name}_user' with a warning log. This prevents silent data
        overwrites when the engine attaches its own reject diagnostic columns.

        Only applies to the 'main' flow. The reject flow is the engine's domain and
        components are expected to add 'errorCode'/'errorMessage' there legitimately.

        Args:
            result: The result dict (modified in-place for main DataFrame).

        Returns:
            The result dict with renamed columns in the main flow.
        """
        main_df = result.get("main")
        if main_df is None or not isinstance(main_df, pd.DataFrame):
            return result

        renames = {}
        for reserved_col in _RESERVED_REJECT_COLS:
            if reserved_col in main_df.columns:
                new_name = f"{reserved_col}_user"
                renames[reserved_col] = new_name
                logger.warning(
                    f"[{self.id}] Input had reserved column '{reserved_col}'; "
                    f"renamed to '{new_name}'"
                )
        if renames:
            result["main"] = main_df.rename(columns=renames)
        return result

    def _validate_with_reject_routing(
        self,
        result: dict,
        main_df: pd.DataFrame,
        output_schema: list[dict],
    ) -> dict:
        """Validate main DataFrame and route violations to reject (die_on_error=False).

        For each schema column, checks nullable constraint and type coercion. Rows
        that violate constraints are removed from main and appended to reject with:
            - errorCode: "SCHEMA_VIOLATION"
            - errorMessage: "Column '<name>': <reason>"

        Violation reasons:
            - "non-nullable column has null"
            - "type coercion failed: <value>"
            - "length exceeded: <actual> > <schema_length>"

        Args:
            result: The result dict (modified in place).
            main_df: The main output DataFrame to validate.
            output_schema: Schema column definitions.

        Returns:
            Updated result dict with valid rows in main, violated rows in reject.
        """
        violation_indices: dict[int, str] = {}  # index -> first violation reason

        working_df = main_df.copy()

        for col_def in output_schema:
            col_name = col_def.get("name")
            if col_name is None or col_name not in working_df.columns:
                continue

            col_type = col_def.get("type", "str")
            nullable = col_def.get("nullable", True)
            col_length = col_def.get("length")
            precision = col_def.get("precision")

            # Check nullable constraint
            if not nullable:
                null_mask = working_df[col_name].isna()
                for idx in working_df.index[null_mask]:
                    if idx not in violation_indices:
                        violation_indices[idx] = (
                            f"Column '{col_name}': non-nullable column has null"
                        )

            # Apply treat_empty_as_null before coercion
            default_treat_empty = col_type in _NUMERIC_LIKE_TYPES
            treat_empty = col_def.get("treat_empty_as_null", default_treat_empty)
            working_df = self._apply_treat_empty(working_df, col_name, col_type, treat_empty)

            # Type coercion (best-effort; record failures)
            working_df = self._coerce_column_type(working_df, col_def)

            # String length: in Talend, 'length' on string columns is purely
            # informational metadata (Talend Studio schema display / code generation).
            # It is NEVER enforced at runtime -- no truncation, no rejection.

            # Float precision rounding
            if precision is not None and col_type == "float":
                try:
                    precision_int = int(precision)
                    working_df[col_name] = working_df[col_name].round(precision_int)
                except (TypeError, ValueError):
                    pass

            # Decimal precision
            if precision is not None and col_type == "Decimal":
                working_df = self._apply_decimal_precision(
                    working_df, col_name, precision
                )

        if not violation_indices:
            result["main"] = working_df
            return result

        # Split valid and violating rows
        bad_idx = set(violation_indices.keys())
        good_mask = ~working_df.index.isin(bad_idx)
        valid_df = working_df[good_mask].reset_index(drop=True)

        # Build reject rows from original data (preserve raw values)
        # WR-01 fix: use sorted order for both row selection and message lookup
        # so errorMessage aligns correctly with each rejected row.
        bad_idx_sorted = sorted(bad_idx)
        rejected_rows = main_df.loc[bad_idx_sorted].copy().reset_index(drop=True)
        rejected_rows["errorCode"] = "SCHEMA_VIOLATION"
        rejected_rows["errorMessage"] = [
            violation_indices[idx] for idx in bad_idx_sorted
        ]

        # Merge with existing reject
        existing_reject = result.get("reject")
        if existing_reject is not None and isinstance(existing_reject, pd.DataFrame) and len(existing_reject) > 0:
            result["reject"] = pd.concat(
                [existing_reject, rejected_rows], ignore_index=True
            )
        else:
            result["reject"] = rejected_rows

        result["main"] = valid_df
        return result

    # ------------------------------------------------------------------
    # Schema Validation
    # ------------------------------------------------------------------

    def validate_schema(self, df: pd.DataFrame, schema: list[dict]) -> pd.DataFrame:
        """Validate and coerce DataFrame columns to match schema.

        Fixes ENG-19: The old code filled NaN with 0 when ``nullable=True``
        (inverted logic). Correct behavior:
            - ``nullable=False`` + column has NaN -> raise DataValidationError
            - ``nullable=True`` -> allow NaN values (do nothing special)

        For integer columns with NaN values and ``nullable=True``, uses
        ``pd.Int64Dtype()`` (nullable integer) instead of ``fillna(0).astype(int64)``.

        Phase 7.1 additions (G-02, G-03, G-04, G-12):
            - Decimal columns without precision coerced to Decimal objects
            - Float columns with precision get rounded
            - date_pattern attribute used for datetime parsing
            - treat_empty_as_null per-column attribute applied before coercion

        Args:
            df: Input DataFrame.
            schema: List of column defs with keys: name, type, nullable,
                length, precision, date_pattern, treat_empty_as_null.

        Returns:
            DataFrame with validated/coerced types.

        Raises:
            DataValidationError: If a non-nullable column contains NULL values
                (only when die_on_error=True or called directly).
        """
        if not schema:
            return df
        if df is None:
            return df

        result = df.copy()

        for col_def in schema:
            col_name = col_def.get("name")
            if col_name is None or col_name not in result.columns:
                continue

            col_type = col_def.get("type", "str")
            nullable = col_def.get("nullable", True)

            # Apply treat_empty_as_null before coercion (G-12/D-10)
            default_treat_empty = col_type in _NUMERIC_LIKE_TYPES
            treat_empty = col_def.get("treat_empty_as_null", default_treat_empty)
            result = self._apply_treat_empty(result, col_name, col_type, treat_empty)

            # Check nullable constraint CORRECTLY (FIX ENG-19)
            if not nullable and result[col_name].isna().any():
                raise DataValidationError(
                    f"Column '{col_name}' has NULL values but is not nullable"
                )

            # Type coercion (G-02, G-04 fixes in _coerce_column_type)
            result = self._coerce_column_type(result, col_def)

            # Apply precision for Decimal columns (CR-02 fix in _apply_decimal_precision)
            precision = col_def.get("precision")
            if precision is not None and col_type == "Decimal":
                result = self._apply_decimal_precision(result, col_name, precision)

            # G-03: Apply precision for float columns
            if precision is not None and col_type == "float":
                try:
                    precision_int = int(precision)
                    result[col_name] = result[col_name].round(precision_int)
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        f"[{self.id}] Invalid precision {precision!r} for float column "
                        f"'{col_name}'; skipping rounding: {exc}"
                    )

        return result

    @staticmethod
    def _apply_treat_empty(
        df: pd.DataFrame,
        col_name: str,
        col_type: str,
        treat_empty: bool,
    ) -> pd.DataFrame:
        """Apply treat_empty_as_null logic for a single column.

        G-12/D-10: Controls whether empty strings are coerced to null before
        type coercion.

        For string columns:
            - treat_empty=True: "" -> pd.NA
            - treat_empty=False (default): "" stays as ""

        For numeric/datetime/Decimal columns:
            - treat_empty=True (default): "" will be coerced to NaN by pd.to_numeric/to_datetime
            - treat_empty=False: DataValidationError raised if "" present
              (non-string type cannot meaningfully represent "")

        Args:
            df: DataFrame containing the column.
            col_name: Column name.
            col_type: Column type string.
            treat_empty: Whether to treat "" as null.

        Returns:
            DataFrame with empty-string handling applied.

        Raises:
            DataValidationError: If treat_empty=False on a numeric column that has "" values.
        """
        if col_name not in df.columns:
            return df

        col = df[col_name]

        # Find cells that are exactly the empty string
        # Use len(col) check first to avoid unnecessary work on empty series
        if len(col) == 0:
            return df

        try:
            has_empty = col.apply(
                lambda v: isinstance(v, str) and v == ""
            ).astype(bool).any()
        except Exception:
            # If apply/any fails (e.g. complex dtype), skip treatment
            return df

        if not has_empty:
            return df

        if col_type == "str":
            if treat_empty:
                df = df.copy()
                col = df[col_name]          # refresh after copy to avoid stale reference
                df[col_name] = col.apply(
                    lambda v: pd.NA if (isinstance(v, str) and v == "") else v
                )
        else:
            # numeric/datetime/Decimal: empty string has no valid representation
            if not treat_empty:
                raise DataValidationError(
                    f"Column '{col_name}' has empty strings but treat_empty_as_null=false "
                    f"on a non-string column (type '{col_type}')"
                )
            # treat_empty=True (default for numeric): leave "" for pd.to_numeric to coerce to NaN

        return df

    @staticmethod
    def _apply_decimal_precision(
        df: pd.DataFrame,
        col_name: str,
        precision,
    ) -> pd.DataFrame:
        """Round Decimal column values to the specified number of decimal places.

        CR-02 fix: coerce string precision to int before use (JSON configs send strings).

        Args:
            df: DataFrame containing the column.
            col_name: Name of the Decimal column.
            precision: Number of decimal places (int or str -- coerced to int).

        Returns:
            DataFrame with the column values quantized.
        """
        # CR-02 fix: coerce string precision to int
        try:
            precision = int(precision)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid precision {precision!r} for column '{col_name}'; "
                f"skipping precision application"
            )
            return df

        quantize_str = Decimal(10) ** -precision  # e.g. Decimal('0.0001') for precision=4

        def _quantize(val):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return val
            try:
                if pd.isna(val):
                    return val
            except (TypeError, ValueError):
                pass
            try:
                d = val if isinstance(val, Decimal) else Decimal(str(val))
                return d.quantize(quantize_str, rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError):
                return val

        df[col_name] = df[col_name].apply(_quantize)  # type: ignore[arg-type]
        return df

    def _coerce_column_type(
        self,
        df: pd.DataFrame,
        col_def: dict,
    ) -> pd.DataFrame:
        """Coerce a single column to the target pandas type.

        Phase 7.1 additions:
            - G-02: Decimal columns get values coerced to Decimal objects (not just object dtype)
            - G-04: date_pattern attribute drives format-aware datetime parsing with Talend
              default chain -> ISO 8601 -> inference fallback

        Datetime parsing chain (G-04):
            1. If date_pattern is set: convert Java pattern to strptime, parse with that format
            2. Else try Talend defaults in order: "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"
            3. Else ISO 8601 / pandas inference via pd.to_datetime(errors="coerce")
               (infer_datetime_format was removed in pandas 2.0+)
            4. Else inference fallback (current behavior, last resort)

        Args:
            df: DataFrame containing the column.
            col_def: Column definition dict with 'name', 'type', 'nullable', 'date_pattern', etc.

        Returns:
            DataFrame with the column coerced (modified in place on the copy).
        """
        col_name = col_def.get("name")
        if col_name not in df.columns:
            return df

        col_type = col_def.get("type", "str")
        nullable = col_def.get("nullable", True)
        date_pattern = col_def.get("date_pattern")

        pandas_type = self._TYPE_MAPPING.get(col_type, "object")

        try:
            if pandas_type == "datetime64[ns]":
                df[col_name] = self._parse_datetime_column(
                    df[col_name], date_pattern
                )

            elif pandas_type == "int64":
                df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
                if nullable:
                    # Always use nullable Int64 for nullable int columns (preserves NaN,
                    # and on empty DataFrames isna().any() is False but dtype must still be Int64)
                    df[col_name] = df[col_name].astype(pd.Int64Dtype())
                else:
                    df[col_name] = df[col_name].astype("int64")

            elif pandas_type == "float64":
                df[col_name] = pd.to_numeric(df[col_name], errors="coerce")

            elif pandas_type == "bool":
                df[col_name] = df[col_name].astype("bool")

            elif col_type == "Decimal":
                # G-02 fix: coerce to Decimal objects (not just leave as object/string)
                def _to_decimal(v):
                    if v is None:
                        return pd.NA
                    try:
                        if pd.isna(v):
                            return pd.NA
                    except (TypeError, ValueError):
                        pass
                    if isinstance(v, Decimal):
                        return v
                    try:
                        return Decimal(str(v))
                    except (InvalidOperation, ValueError):
                        return v

                df[col_name] = df[col_name].apply(_to_decimal)  # type: ignore[arg-type]

            # str type (object) and unknown types: no conversion needed

        except Exception as e:
            logger.warning(
                f"[{self.id}] Failed to convert column '{col_name}' "
                f"to type '{col_type}': {e}"
            )

        return df

    @staticmethod
    def _parse_datetime_column(series: pd.Series, date_pattern: Optional[str]) -> pd.Series:
        """Parse a datetime column using the Talend date parsing chain.

        G-04 fix: date_pattern attribute from schema drives format-aware parsing.

        Parsing chain:
            1. If date_pattern (Java format): convert to strptime, try pd.to_datetime with format
            2. Else try Talend default formats in order (avoid false-NaT results)
            3. Else ISO 8601 with pd.to_datetime inference
            4. Fallback: pd.to_datetime inference (last resort)

        Args:
            series: The column Series to parse.
            date_pattern: Java-style date pattern from schema (e.g. "dd/MM/yyyy"), or None.

        Returns:
            Parsed datetime Series with dtype datetime64[ns].
        """
        # Step 1: Explicit date_pattern from schema
        if date_pattern:
            strptime_fmt = _java_pattern_to_strptime(date_pattern)
            parsed = pd.to_datetime(series, format=strptime_fmt, errors="coerce")
            # If this produced some valid dates, use it
            if parsed.notna().any() or series.isna().all():
                return parsed

        # Step 2: Try Talend default date formats in order
        for fmt in _TALEND_DEFAULT_DATE_FORMATS:
            try:
                parsed = pd.to_datetime(series, format=fmt, errors="coerce")
                # A format wins if it parses all non-null values successfully
                non_null_mask = series.notna() & (series != "")
                if non_null_mask.any() and parsed[non_null_mask].notna().all():
                    return parsed
            except Exception:
                continue

        # Step 3: ISO 8601 / pandas inference (infer_datetime_format removed in pandas 3.x)
        parsed = pd.to_datetime(series, errors="coerce")
        return parsed

    # ------------------------------------------------------------------
    # Reset (Iterate Support)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset component state for iterate re-execution or streaming finalization.

        Clears in-memory stats and resets status to PENDING. Config is
        re-derived from _original_config at next execute() call automatically.

        GlobalMap stats are intentionally NOT cleared here. put_component_stat
        overwrites (does not accumulate), so the next execute/_update_global_map
        call will push fresh values. Clearing GlobalMap stats from reset() would
        silently wipe stats when the executor calls reset() for streaming
        finalization (CR-01), causing get_nb_line_ok/get_nb_line to return 0
        for non-iterate components after job completion.
        """
        self.stats = self._default_stats()
        self.status = ComponentStatus.PENDING

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_status(self) -> ComponentStatus:
        """Get component execution status."""
        return self.status

    def get_stats(self) -> dict[str, int]:
        """Get a copy of component statistics."""
        return self.stats.copy()

    def get_python_routines(self) -> dict[str, Any]:
        """Get loaded python routines for use in expressions.

        Returns:
            Dictionary mapping routine names to routine objects.
            Empty dict if no python routine manager is configured.
        """
        if self.python_routine_manager:
            return self.python_routine_manager.get_all_routines()
        return {}

    def __repr__(self) -> str:
        return f"{self.component_type}(id={self.id}, status={self.status.value})"