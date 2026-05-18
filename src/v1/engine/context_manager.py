"""Context Manager for handling job context variables.

Manages context variables for ETL jobs with proper type conversion, safe
resolution that skips code fields, and recursive resolution into nested
data structures.

Fixes applied:
- ENG-05: Type conversion uses actual callables, not string literals
- ENG-18: resolve_dict skips python_code/java_code/imports fields
- NEW-01: No dead imports (os, sys removed)
- NEW-02: resolve_dict recurses into dicts inside lists
"""
import datetime
import re
import logging
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _parse_talend_date(value):
    """Parse a Talend id_Date value into datetime.date / datetime.datetime.

    Accepts already-typed date/datetime objects (pass-through) and strings in
    the four Talend-standard formats:
      - ISO datetime: "yyyy-MM-dd HH:mm:ss"
      - ISO date:     "yyyy-MM-dd"
      - US:           "MM/dd/yyyy"
      - European:     "dd/MM/yyyy HH:mm"

    Returns the original value if parsing fails (matches the error-tolerance
    contract of the existing type converter map).
    """
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value
    if not isinstance(value, str) or not value:
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y %H:%M"):
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return value


class ContextManager:
    """Manages context variables for ETL jobs.

    Handles variable resolution, type conversion, and context loading.
    Resolution patterns:
      - ``${context.varname}`` -- dollar-brace syntax (resolved everywhere except code fields)
      - ``context.varname`` -- bare reference (resolved everywhere except code fields)

    Code fields (python_code, java_code, imports) are never resolved -- they
    reference context variables at runtime through the Java bridge or Python exec.

    Note: Java Bridge lifecycle is managed separately by JavaBridgeManager.
    """

    # Fields that must NOT be resolved -- they contain code that references
    # context variables at runtime, not at config-resolution time.
    SKIP_RESOLUTION_KEYS: frozenset[str] = frozenset({
        "java_code",
        "imports",
        "python_code",
    })

    # Type converters mapping Talend type IDs and Python type names to actual
    # callable functions. ENG-05 fix: the old code had string literals like
    # 'int' instead of the builtin int, causing converter(value) to fail.
    _TYPE_CONVERTERS: dict[str, Callable] = {
        # Talend types
        "id_String": str,
        "id_Integer": int,
        "id_Long": int,
        "id_Short": int,
        "id_Byte": int,
        "id_Float": float,
        "id_Double": float,
        "id_Boolean": lambda v: str(v).lower() in ("true", "1", "yes"),
        "id_Character": lambda v: str(v)[0] if v else "",
        # id_Date: Parse to datetime.date / datetime.datetime at storage time so
        # that downstream tMap expressions doing (Date) context.batch_date receive
        # a real Date object rather than a String. _parse_talend_date handles the
        # four Talend-standard formats and passes through already-typed objects.
        "id_Date": _parse_talend_date,
        "id_BigDecimal": Decimal,
        "id_Object": str,
        # Python types
        "str": str,
        "int": int,
        "float": float,
        "bool": lambda v: str(v).lower() in ("true", "1", "yes"),
        "Decimal": Decimal,
        "datetime": str,
        "object": str,
    }

    # Compiled regex patterns for context variable resolution
    _PATTERN_DOLLAR_BRACE = re.compile(r"\$\{context\.(\w+)\}")
    _PATTERN_BARE_CONTEXT = re.compile(r"\bcontext\.(\w+)\b")

    def __init__(
        self,
        initial_context: Optional[Dict[str, Dict[str, Any]]] = None,
        default_context: str = "Default",
        java_bridge_manager=None,
    ):
        """Initialize the ContextManager.

        Args:
            initial_context: Optional dict of context groups, keyed by context name.
                Each group is a dict of {var_name: {value: ..., type: ...}}.
            default_context: Name of the default context group to load from
                initial_context.
            java_bridge_manager: Reference to JavaBridgeManager (not owned).
        """
        self.context: Dict[str, Any] = {}
        self.context_types: Dict[str, str] = {}
        self.java_bridge_manager = java_bridge_manager

        if initial_context:
            context_dict_to_load = initial_context.get(default_context, initial_context)
            self.load_context(context_dict_to_load)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_context(self, context_dict: Dict[str, Any]) -> None:
        """Load context variables from a dictionary (from JSON config).

        Args:
            context_dict: Dict where each key maps to either a dict with
                ``value`` and ``type`` keys, or a plain value.
        """
        for key, value_dict in context_dict.items():
            if isinstance(value_dict, dict):
                self.set(key, value_dict.get("value"), value_dict.get("type"))
            else:
                self.set(key, value_dict)

    def load_from_file(self, file_path: str, delimiter: str = "=") -> None:
        """Load context variables from a key=value file.

        Used by tContextLoad component. Lines starting with ``#`` are ignored.

        Args:
            file_path: Path to the context file.
            delimiter: Key-value delimiter (default ``=``).

        Raises:
            FileNotFoundError: If file_path does not exist.
            IOError: On other file read errors.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if delimiter in line:
                            key, value = line.split(delimiter, 1)
                            self.set(key.strip(), value.strip())

            logger.info(f"Loaded context from file: {file_path}: {len(self.context)} variables")
        except Exception as e:
            logger.error(f"Error loading context from file {file_path}: {e}")
            raise

    # ------------------------------------------------------------------
    # Get / Set
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any, value_type: Optional[str] = None) -> None:
        """Set a context variable with optional type conversion.

        Args:
            key: Variable name.
            value: Variable value (will be converted if value_type given).
            value_type: Talend type ID (e.g. ``id_Integer``) or Python type name.
        """
        if value_type:
            value = self._convert_type(value, value_type)
            self.context_types[key] = value_type

        self.context[key] = value
        logger.debug(f"Context: Set {key} = {value} (type: {value_type})")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a context variable.

        Args:
            key: Variable name.
            default: Value to return if key is not found.

        Returns:
            The variable value, or default if not found.
        """
        return self.context.get(key, default)

    def get_type(self, key: str) -> Optional[str]:
        """Get the type string of a context variable.

        Args:
            key: Variable name.

        Returns:
            The type string (e.g. ``id_Integer``), or None if not set.
        """
        return self.context_types.get(key)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve_string(self, value: str) -> str:
        """Resolve context variables in a string.

        Replaces ``${context.variable}`` and bare ``context.variable`` references
        with their actual values. Strings starting with ``{{java}}`` are passed
        through unchanged (they are resolved by the Java bridge at runtime).

        Args:
            value: String potentially containing context variable references.

        Returns:
            String with context variables resolved.
        """
        if not isinstance(value, str):
            return value

        # Skip Java code markers -- resolved by Java bridge at runtime
        if value.startswith("{{java}}"):
            return value

        # Pattern 1: ${context.variable}
        def _replace_dollar_brace(match):
            var_name = match.group(1)
            var_value = self.get(var_name)
            return str(var_value) if var_value is not None else match.group(0)

        value = self._PATTERN_DOLLAR_BRACE.sub(_replace_dollar_brace, value)

        # Pattern 2: context.variable (bare reference with word boundaries)
        def _replace_bare(match):
            var_name = match.group(1)
            var_value = self.get(var_name)
            return str(var_value) if var_value is not None else match.group(0)

        value = self._PATTERN_BARE_CONTEXT.sub(_replace_bare, value)

        return value

    def resolve_dict(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve context variables in a configuration dictionary.

        Returns a NEW dictionary -- never mutates the input. Code fields
        (python_code, java_code, imports) are passed through unchanged.

        Args:
            config: Configuration dictionary potentially containing context
                variable references in string values.

        Returns:
            New dictionary with context variables resolved in all string values,
            recursing into nested dicts and lists.
        """
        resolved = {}
        for key, value in config.items():
            if key in self.SKIP_RESOLUTION_KEYS:
                # ENG-18 fix: code fields pass through unchanged
                resolved[key] = value
            elif isinstance(value, str):
                resolved[key] = self.resolve_string(value)
            elif isinstance(value, dict):
                resolved[key] = self.resolve_dict(value)
            elif isinstance(value, list):
                # NEW-02 fix: recurse into lists (including dicts inside lists)
                resolved[key] = self._resolve_list(value)
            else:
                resolved[key] = value
        return resolved

    def _resolve_list(self, items: list) -> list:
        """Resolve context variables in list elements, including nested dicts.

        Args:
            items: List of values that may contain context variable references.

        Returns:
            New list with context variables resolved in string, dict, and list
            elements.
        """
        result = []
        for item in items:
            if isinstance(item, str):
                result.append(self.resolve_string(item))
            elif isinstance(item, dict):
                result.append(self.resolve_dict(item))
            elif isinstance(item, list):
                result.append(self._resolve_list(item))
            else:
                result.append(item)
        return result

    # ------------------------------------------------------------------
    # Type Conversion
    # ------------------------------------------------------------------

    def _convert_type(self, value: Any, value_type: str) -> Any:
        """Convert a value to the specified type.

        Uses actual callable functions (not string literals) from
        ``_TYPE_CONVERTERS``. Falls back to returning the original value
        with a warning if conversion fails.

        Args:
            value: The value to convert.
            value_type: Talend type ID (e.g. ``id_Integer``) or Python type name.

        Returns:
            The converted value, or the original value if conversion fails
            or value is None/empty string.
        """
        if value is None or value == "":
            return value

        converter = self._TYPE_CONVERTERS.get(value_type)
        if converter is None:
            logger.warning(
                f"ContextManager: Unknown type '{value_type}' for value '{value}', returning as-is"
            )
            return value

        try:
            return converter(value)
        except (ValueError, TypeError, ArithmeticError) as e:
            logger.warning(
                f"ContextManager: Failed to convert value '{value}' to type '{value_type}': {e}"
            )
            return value

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def contains(self, key: str) -> bool:
        """Check if a context variable exists.

        Args:
            key: Variable name.

        Returns:
            True if the variable exists.
        """
        return key in self.context

    def remove(self, key: str) -> None:
        """Remove a context variable.

        Args:
            key: Variable name to remove.
        """
        if key in self.context:
            del self.context[key]
            if key in self.context_types:
                del self.context_types[key]

    def clear(self) -> None:
        """Clear all context variables."""
        self.context.clear()
        self.context_types.clear()

    def get_all(self) -> Dict[str, Any]:
        """Get all context variables.

        Returns:
            A copy of the context variables dictionary.
        """
        return self.context.copy()

    # ------------------------------------------------------------------
    # Java Bridge Integration (Delegated to Manager)
    # ------------------------------------------------------------------

    def get_java_bridge(self):
        """Get the Java Bridge instance from the manager.

        Returns:
            The JavaBridge instance, or None if not available.
        """
        if self.java_bridge_manager:
            return self.java_bridge_manager.get_bridge()
        return None

    def is_java_enabled(self) -> bool:
        """Check if Java Bridge is enabled.

        Returns:
            True if the Java bridge manager reports availability.
        """
        if self.java_bridge_manager:
            return self.java_bridge_manager.is_available()
        return False

    def __repr__(self) -> str:
        java_status = "enabled" if self.is_java_enabled() else "disabled"
        return f"ContextManager(variables={len(self.context)}, java_bridge={java_status})"
