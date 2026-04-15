"""Engine component for ContextLoad (tContextLoad).

Loads context variables from an incoming DataFrame flow at runtime.
All incoming key-value pairs are loaded unconditionally -- policies
only control validation messages (warnings/errors), not whether
variables are actually assigned.

Config keys consumed (9 total):
  print_operations       (bool, default False)  -- log each loaded key-value pair
  die_on_error           (bool, default False)  -- raise on unsuppressed ERROR message
  disable_error          (bool, default False)  -- suppress ERROR-level messages
  disable_warnings       (bool, default True)   -- suppress WARNING-level messages
  disable_info           (bool, default True)   -- suppress INFO-level messages
  load_new_variable      (str,  default "WARNING")  -- policy for keys not in existing context
  not_load_old_variable  (str,  default "WARNING")  -- policy for context keys absent from flow
  tstatcatcher_stats     (bool, default False)  -- enable tStatCatcher statistics
  label                  (str,  default "")     -- component label for logging
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    DataValidationError,
)

logger = logging.getLogger(__name__)

# Valid values for closed-list policy config keys
_VALID_POLICIES = {"ERROR", "WARNING", "INFO", "NO_WARNING"}


@REGISTRY.register("ContextLoad", "tContextLoad")
class ContextLoad(BaseComponent):
    """tContextLoad engine implementation.

    Loads context variables from an incoming DataFrame with key/value
    columns. Supports optional type column for type preservation.
    Implements LOAD_NEW_VARIABLE and NOT_LOAD_OLD_VARIABLE validation
    policies with DISABLE_* suppression flags and die_on_error
    integration.

    Config keys:
        print_operations: Log each loaded key-value pair.
        die_on_error: Raise ComponentExecutionError on unsuppressed ERROR.
        disable_error: Suppress ERROR-level validation messages.
        disable_warnings: Suppress WARNING-level validation messages.
        disable_info: Suppress INFO-level validation messages.
        load_new_variable: Policy for keys not in existing context.
        not_load_old_variable: Policy for context keys absent from flow.
        tstatcatcher_stats: Enable tStatCatcher statistics.
        label: Component label for logging.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Checks that load_new_variable and not_load_old_variable are
        valid policy strings. All config keys have defaults so no
        required-key checks are needed.

        Raises:
            ConfigurationError: If a policy value is not in the allowed set.
        """
        load_new = str(self.config.get("load_new_variable", "WARNING")).upper()
        if load_new not in _VALID_POLICIES:
            raise ConfigurationError(
                f"[{self.id}] Invalid load_new_variable '{load_new}'. "
                f"Must be one of: {sorted(_VALID_POLICIES)}"
            )
        self.config["load_new_variable"] = load_new

        not_load_old = str(self.config.get("not_load_old_variable", "WARNING")).upper()
        if not_load_old not in _VALID_POLICIES:
            raise ConfigurationError(
                f"[{self.id}] Invalid not_load_old_variable '{not_load_old}'. "
                f"Must be one of: {sorted(_VALID_POLICIES)}"
            )
        self.config["not_load_old_variable"] = not_load_old

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Load context variables from input DataFrame.

        Three-phase model:
          A. Setup -- snapshot existing context keys.
          B. Row processing -- load each key-value pair unconditionally.
          C. Post-processing -- emit validation messages, set globalMap.

        Args:
            input_data: DataFrame with 'key' and 'value' columns,
                and optionally a 'type' column.

        Returns:
            dict with 'main' key containing an empty DataFrame.

        Raises:
            DataValidationError: If input DataFrame lacks required columns.
        """
        print_operations = self.config.get("print_operations", False)

        # Phase A -- Setup
        assigned_keys: set[str] = set()
        new_keys: set[str] = set()
        existing_context_keys = (
            set(self.context_manager.context.keys())
            if self.context_manager
            else set()
        )

        # Phase B -- Row Processing
        if input_data is not None and not input_data.empty:
            # Validate required columns
            if "key" not in input_data.columns or "value" not in input_data.columns:
                raise DataValidationError(
                    f"[{self.id}] Input DataFrame must have 'key' and 'value' "
                    f"columns, got: {list(input_data.columns)}"
                )

            # Vectorized extraction -- fillna before astype to avoid
            # pandas NaN propagation through str operations
            keys = input_data["key"].fillna("").astype(str).str.strip()
            values = input_data["value"]
            has_type = "type" in input_data.columns
            if has_type:
                types = input_data["type"]

            for i in range(len(input_data)):
                key = str(keys.iloc[i]).strip()

                # Skip empty keys
                if not key:
                    continue

                # NaN safety: convert NaN/NaT to None
                val = values.iloc[i]
                if pd.isna(val):
                    val = None

                # Determine type: type column > existing type > default
                value_type = self._determine_type(
                    key,
                    types.iloc[i] if has_type else None,
                    has_type,
                )

                # Categorize key
                if key in existing_context_keys:
                    assigned_keys.add(key)
                else:
                    new_keys.add(key)

                # Unconditionally assign to context
                if self.context_manager:
                    self.context_manager.set(key, val, value_type)

                # Log operation if requested
                if print_operations:
                    logger.info(
                        "[%s] Context loaded: %s = %s (type: %s)",
                        self.id, key, val, value_type,
                    )

        # Phase C -- Post-Processing Validation
        unloaded_keys = existing_context_keys - assigned_keys - new_keys
        self._emit_validation_messages(new_keys, unloaded_keys)

        loaded_count = len(assigned_keys) + len(new_keys)

        # Set globalMap variables
        if self.global_map:
            self.global_map.put(f"{self.id}_NB_LINE", loaded_count)
            self.global_map.put(f"{self.id}_NB_CONTEXT_LOADED", loaded_count)
            new_keys_str = ",".join(sorted(new_keys)) if new_keys else ""
            unloaded_keys_str = ",".join(sorted(unloaded_keys)) if unloaded_keys else ""
            self.global_map.put(f"{self.id}_KEY_NOT_INCONTEXT", new_keys_str)
            self.global_map.put(f"{self.id}_KEY_NOT_LOADED", unloaded_keys_str)

        # Update base stats
        self._update_stats(loaded_count, loaded_count, 0)

        logger.info(
            "[%s] Loaded %d context variables (%d new, %d updated, %d unloaded)",
            self.id, loaded_count, len(new_keys), len(assigned_keys),
            len(unloaded_keys),
        )

        return {"main": pd.DataFrame()}

    # ------------------------------------------------------------------
    # Type Determination
    # ------------------------------------------------------------------

    def _determine_type(
        self,
        key: str,
        type_val: Any,
        has_type_column: bool,
    ) -> str:
        """Determine the appropriate type for a context variable.

        Priority:
          1. Type column value (if present and not NaN).
          2. Existing type from ContextManager.
          3. Default: id_String.

        Args:
            key: Context variable key.
            type_val: Value from the type column (or None).
            has_type_column: Whether the DataFrame has a type column.

        Returns:
            Type identifier string.
        """
        # 1. Type column value
        if has_type_column and type_val is not None and not pd.isna(type_val):
            return str(type_val)

        # 2. Existing type from ContextManager
        if self.context_manager:
            existing_type = self.context_manager.get_type(key)
            if existing_type:
                return existing_type

        # 3. Default
        return "id_String"

    # ------------------------------------------------------------------
    # Validation Message Emission
    # ------------------------------------------------------------------

    def _emit_validation_messages(
        self,
        new_keys: set[str],
        unloaded_keys: set[str],
    ) -> None:
        """Emit validation messages for new and unloaded keys.

        Args:
            new_keys: Keys in the flow that were not in the existing context.
            unloaded_keys: Keys in the existing context not present in the flow.
        """
        load_new_policy = self.config.get("load_new_variable", "WARNING")
        not_load_old_policy = self.config.get("not_load_old_variable", "WARNING")

        for key in sorted(new_keys):
            message = f"New context variable '{key}' not in original job context"
            self._emit_message(message, load_new_policy)

        for key in sorted(unloaded_keys):
            message = f"Context variable '{key}' not loaded from incoming flow"
            self._emit_message(message, not_load_old_policy)

    def _emit_message(self, message: str, level: str) -> None:
        """Emit a validation message at the specified severity level.

        Respects DISABLE_* flags and die_on_error configuration.

        Args:
            message: The validation message text.
            level: Policy level -- "ERROR", "WARNING", "INFO", or "NO_WARNING".

        Raises:
            ComponentExecutionError: If level is ERROR, not suppressed,
                and die_on_error is True.
        """
        # NO_WARNING means no message at all
        if level == "NO_WARNING":
            return

        # Check DISABLE flags
        disable_error = self.config.get("disable_error", False)
        disable_warnings = self.config.get("disable_warnings", True)
        disable_info = self.config.get("disable_info", True)

        if level == "ERROR" and disable_error:
            return
        if level == "WARNING" and disable_warnings:
            return
        if level == "INFO" and disable_info:
            return

        # Emit the message at the appropriate log level
        prefixed = f"[{self.id}] {message}"
        if level == "ERROR":
            logger.error(prefixed)
        elif level == "WARNING":
            logger.warning(prefixed)
        elif level == "INFO":
            logger.info(prefixed)

        # die_on_error: raise if ERROR-level message was emitted (not suppressed)
        if level == "ERROR" and self.config.get("die_on_error", False):
            raise ComponentExecutionError(self.id, message)
