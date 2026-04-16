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
"""
import copy
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

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
        7. _update_stats_from_result() + _update_global_map()

    Config Immutability (ENG-09/ENG-21):
        ``_original_config`` is deepcopied at construction and NEVER mutated.
        ``config`` is re-derived from ``_original_config`` at the start of every
        ``execute()`` call, so iterate re-execution always starts clean.
    """

    # Memory threshold for auto-switching to streaming mode (in MB)
    MEMORY_THRESHOLD_MB = 3072

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
                result = self._execute_streaming(input_data)
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
        """Process data in chunks. Collects ALL named flow outputs.

        Fixes ENG-07/ENG-20: The old implementation only collected main chunks,
        silently dropping all reject data from streaming execution.
        Updated to collect arbitrary named flows (not just main/reject) so
        multi-output components like tMap work correctly in streaming mode.

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
            chunk = input_data.iloc[start : start + chunk_size]
            chunk_result = self._process(chunk)

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
        """Reorder output DataFrame columns to match the output schema.

        The output schema is the authoritative source for column order.
        Components may produce columns in any order internally; this method
        ensures the final output matches the schema contract.

        Applies to the 'main' key in the result dict. Only reorders if
        output_schema is defined and the DataFrame has columns.

        Args:
            result: The dict returned by _process().

        Returns:
            The same dict with 'main' DataFrame columns reordered.
        """
        output_schema = getattr(self, "output_schema", None)
        if not output_schema:
            return result

        main_df = result.get("main")
        if main_df is None or not isinstance(main_df, pd.DataFrame) or main_df.empty:
            return result

        # Build ordered column list from schema
        schema_cols = [
            col["name"] for col in output_schema
            if isinstance(col, dict) and "name" in col
        ]
        if not schema_cols:
            return result

        # Add any schema columns missing from DataFrame as empty/default
        # (Talend always outputs all schema columns, even if empty).
        # Use type-appropriate defaults for non-nullable columns to avoid
        # validation errors downstream.
        missing = [c for c in schema_cols if c not in main_df.columns]
        if missing:
            schema_by_name = {
                col["name"]: col for col in output_schema
                if isinstance(col, dict) and "name" in col
            }
            for col in missing:
                col_def = schema_by_name.get(col, {})
                col_type = col_def.get("type", "str")
                nullable = col_def.get("nullable", True)
                if nullable:
                    main_df[col] = pd.NA
                elif col_type == "str":
                    main_df[col] = ""
                elif col_type in ("int", "float", "Decimal"):
                    main_df[col] = 0
                elif col_type == "bool":
                    main_df[col] = False
                else:
                    main_df[col] = ""

        # Reorder: schema columns first, then any extras not in schema (safety).
        ordered = [c for c in schema_cols if c in main_df.columns]
        extra = [c for c in main_df.columns if c not in ordered]
        final_order = ordered + extra

        if final_order != list(main_df.columns):
            result["main"] = main_df[final_order]

        return result

    # ------------------------------------------------------------------
    # Output Schema Validation (applied automatically by execute())
    # ------------------------------------------------------------------

    def _apply_output_schema_validation(self, result: dict) -> dict:
        """Apply validate_schema to the 'main' DataFrame using output_schema.

        Called automatically by execute() after _process(). This ensures
        type coercion and precision formatting are applied consistently
        for all components without requiring each to call validate_schema
        manually.

        Args:
            result: The dict returned by _process().

        Returns:
            The same dict with 'main' DataFrame validated against output_schema.
        """
        output_schema = getattr(self, "output_schema", None)
        if not output_schema:
            return result

        main_df = result.get("main")
        if main_df is None or not isinstance(main_df, pd.DataFrame) or main_df.empty:
            return result

        result["main"] = self.validate_schema(main_df, output_schema)
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

        Args:
            df: Input DataFrame.
            schema: List of column defs with keys: name, type, nullable,
                length, precision, key.

        Returns:
            DataFrame with validated/coerced types.

        Raises:
            DataValidationError: If a non-nullable column contains NULL values.
        """
        if not schema or df is None or df.empty:
            return df

        result = df.copy()
        for col_def in schema:
            col_name = col_def.get("name")
            if col_name not in result.columns:
                continue

            col_type = col_def.get("type", "str")
            nullable = col_def.get("nullable", True)

            # Check nullable constraint CORRECTLY (FIX ENG-19)
            if not nullable and result[col_name].isna().any():
                raise DataValidationError(
                    f"Column '{col_name}' has NULL values but is not nullable"
                )

            # Type coercion
            result = self._coerce_column_type(result, col_name, col_type, nullable)

            # Apply precision for Decimal columns
            precision = col_def.get("precision")
            if precision is not None and col_type == "Decimal":
                result = self._apply_decimal_precision(result, col_name, precision)

        return result

    @staticmethod
    def _apply_decimal_precision(
        df: pd.DataFrame,
        col_name: str,
        precision: int,
    ) -> pd.DataFrame:
        """Round Decimal column values to the specified number of decimal places.

        Args:
            df: DataFrame containing the column.
            col_name: Name of the Decimal column.
            precision: Number of decimal places.

        Returns:
            DataFrame with the column values quantized.
        """
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

        quantize_str = Decimal(10) ** -precision  # e.g. Decimal('0.0001') for precision=4

        def _quantize(val):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return val
            try:
                d = val if isinstance(val, Decimal) else Decimal(str(val))
                return d.quantize(quantize_str, rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError):
                return val

        df[col_name] = df[col_name].apply(_quantize)
        return df

    def _coerce_column_type(
        self,
        df: pd.DataFrame,
        col_name: str,
        col_type: str,
        nullable: bool,
    ) -> pd.DataFrame:
        """Coerce a single column to the target pandas type.

        Args:
            df: DataFrame containing the column.
            col_name: Name of the column to coerce.
            col_type: Python type string (e.g. 'int', 'str', 'Decimal').
            nullable: Whether the column allows NULL values.

        Returns:
            DataFrame with the column coerced (modified in place on the copy).
        """
        pandas_type = self._TYPE_MAPPING.get(col_type, "object")

        try:
            if pandas_type == "datetime64[ns]":
                df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
            elif pandas_type == "int64":
                df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
                if nullable and df[col_name].isna().any():
                    # Use nullable integer type to preserve NaN
                    df[col_name] = df[col_name].astype(pd.Int64Dtype())
                else:
                    df[col_name] = df[col_name].astype("int64")
            elif pandas_type == "float64":
                df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
            elif pandas_type == "bool":
                df[col_name] = df[col_name].astype("bool")
            # object type: no conversion needed
        except Exception as e:
            logger.warning(
                f"[{self.id}] Failed to convert column '{col_name}' "
                f"to type '{pandas_type}': {e}"
            )

        return df

    # ------------------------------------------------------------------
    # Reset (Iterate Support)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset component state for iterate re-execution.

        Clears stats, resets status to PENDING. Config is re-derived from
        _original_config at next execute() call automatically.
        Clears component stats in globalMap.
        """
        self.stats = self._default_stats()
        self.status = ComponentStatus.PENDING
        if self.global_map:
            self.global_map.reset_component(self.id)

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
