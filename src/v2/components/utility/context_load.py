"""
Context Load Component for V2 Engine.

Reads key/value configuration from external files and injects them
into the execution context at runtime.

Config options:
    path: str - File path (supports ${context.var} placeholders)
    format: str - "delimited", "json", or "yaml" (auto-detected from extension if omitted)
    delimiter: str - Key/value separator for delimited format (default "=")
    encoding: str - File encoding (default "utf-8")
    comment_char: str - Skip lines starting with this character (default "#")
    print_operations: bool - Log each loaded variable (default false)
    die_on_error: bool - Fail on errors vs skip and continue (default true)
    types: dict - Explicit type declarations for new variables

Example config:
    {
        "path": "${context.config_dir}/db.properties",
        "format": "delimited",
        "delimiter": "=",
        "print_operations": true,
        "types": {
            "port": {"type": "int"},
            "start_date": {"type": "date", "format": "%Y-%m-%d"}
        }
    }
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from ..base import UtilityComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = ("password", "secret", "token", "key", "credential")


@REGISTRY.register("context_load")
class ContextLoad(UtilityComponent):
    """Load context variables from an external file.

    Reads key/value pairs from delimited, JSON, or YAML files and returns
    them as ``__context_updates__`` for the engine to apply to the execution
    context.  Supports type casting via existing context types, explicit
    type declarations, JSON/YAML native types, and smart auto-detection.
    """

    def _post_init(self):
        self._path = self.resolve_context(self.config.get("path", ""))
        self._format = self.config.get("format", None)
        self._delimiter = self.config.get("delimiter", "=")
        self._encoding = self.config.get("encoding", "utf-8")
        self._comment_char = self.config.get("comment_char", "#")
        self._print_ops = self.config.get("print_operations", False)
        self._die_on_error = self.config.get("die_on_error", True)
        self._types = self.config.get("types", {})

    def validate(self) -> List[str]:
        errors = []
        if not self._path:
            errors.append("ContextLoad requires a 'path' config field")
        if self._format and self._format not in ("delimited", "json", "yaml"):
            errors.append(
                f"Unsupported format: {self._format}. "
                "Use 'delimited', 'json', or 'yaml'"
            )
        return errors

    def apply(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        fmt = self._detect_format()
        raw_pairs = self._read_file(fmt)
        updates, stats = self._cast_and_collect(raw_pairs)
        return {
            "__context_updates__": updates,
            "__context_load_stats__": stats,
        }

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

    def _detect_format(self) -> str:
        if self._format:
            return self._format
        ext = Path(self._path).suffix.lower()
        if ext == ".json":
            return "json"
        if ext in (".yaml", ".yml"):
            return "yaml"
        return "delimited"

    # ------------------------------------------------------------------
    # File readers
    # ------------------------------------------------------------------

    def _read_file(self, fmt: str) -> Dict[str, Any]:
        path = Path(self._path)
        if not path.exists():
            if self._die_on_error:
                raise FileNotFoundError(
                    f"Context file not found: {self._path}"
                )
            logger.error("Context file not found: %s", self._path)
            return {}

        if fmt == "json":
            return self._read_json(path)
        elif fmt == "yaml":
            return self._read_yaml(path)
        else:
            return self._read_delimited(path)

    def _read_delimited(self, path: Path) -> Dict[str, str]:
        pairs: Dict[str, str] = {}
        with open(path, encoding=self._encoding) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(self._comment_char):
                    continue
                if self._delimiter not in line:
                    logger.warning(
                        "Skipping malformed line (no delimiter): %s", line
                    )
                    continue
                key, value = line.split(self._delimiter, 1)
                pairs[key.strip()] = value.strip()
        return pairs

    def _read_json(self, path: Path) -> Dict[str, Any]:
        with open(path, encoding=self._encoding) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(
                f"JSON context file must contain a flat object, "
                f"got {type(data).__name__}"
            )
        self._check_flat(data, "JSON")
        return data

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        import yaml

        with open(path, encoding=self._encoding) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(
                f"YAML context file must contain a flat mapping, "
                f"got {type(data).__name__}"
            )
        self._check_flat(data, "YAML")
        return data

    @staticmethod
    def _check_flat(data: Dict[str, Any], fmt: str) -> None:
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                raise ValueError(
                    f"{fmt} context file must be flat, but key '{k}' "
                    f"contains a nested {type(v).__name__}"
                )

    # ------------------------------------------------------------------
    # Type casting
    # ------------------------------------------------------------------

    def _cast_and_collect(
        self, raw_pairs: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        updates: Dict[str, Any] = {}
        nb_loaded = 0
        nb_skipped = 0
        skipped_keys: List[str] = []

        for key, value in raw_pairs.items():
            try:
                typed_value = self._cast_value(key, value)
                updates[key] = typed_value
                nb_loaded += 1
                if self._print_ops:
                    self._log_variable(key, typed_value)
            except Exception as e:
                if self._die_on_error:
                    raise ValueError(
                        f"Failed to cast context variable '{key}': {e}"
                    ) from e
                logger.warning("Skipping context variable '%s': %s", key, e)
                nb_skipped += 1
                skipped_keys.append(key)

        stats = {
            "nb_loaded": nb_loaded,
            "nb_skipped": nb_skipped,
            "skipped_keys": skipped_keys,
        }
        return updates, stats

    def _cast_value(self, key: str, value: Any) -> Any:
        # Priority 1: Existing context variable -- match its type
        if self.context and key in self.context:
            existing = self.context[key]
            return self._cast_to_type(value, type(existing))

        # Priority 2: Explicit types config
        if key in self._types:
            type_spec = self._types[key]
            return self._cast_from_spec(value, type_spec)

        # Priority 3: JSON/YAML native types (already typed, pass through)
        if not isinstance(value, str):
            return value

        # Priority 4: Smart auto-detection for strings
        return self._auto_detect(value)

    def _cast_to_type(self, value: Any, target_type: type) -> Any:
        if isinstance(value, target_type):
            return value
        s = str(value)
        if target_type == int:
            return int(s)
        if target_type == float:
            return float(s)
        if target_type == bool:
            if s.lower() in ("true", "1", "yes"):
                return True
            if s.lower() in ("false", "0", "no"):
                return False
            raise ValueError(f"Cannot cast '{s}' to bool")
        if target_type in (date, datetime):
            if target_type == date:
                return date.fromisoformat(s)
            return datetime.fromisoformat(s)
        return s

    def _cast_from_spec(self, value: Any, spec: Dict[str, str]) -> Any:
        type_name = spec.get("type", "str")
        fmt = spec.get("format")
        s = str(value)
        if type_name == "int":
            return int(s)
        if type_name == "float":
            return float(s)
        if type_name == "bool":
            return s.lower() in ("true", "1", "yes")
        if type_name == "date":
            if fmt:
                return datetime.strptime(s, fmt).date()
            return date.fromisoformat(s)
        if type_name == "datetime":
            if fmt:
                return datetime.strptime(s, fmt)
            return datetime.fromisoformat(s)
        return s

    def _auto_detect(self, value: str) -> Any:
        """Auto-detect type from string value: int -> float -> bool -> str."""
        # Try int
        try:
            return int(value)
        except ValueError:
            pass
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        # Try bool
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        # Default to string
        return value

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_variable(self, key: str, value: Any) -> None:
        if any(p in key.lower() for p in _SENSITIVE_PATTERNS):
            display = "********"
        else:
            display = value
        logger.info(
            "[context_load:%s] %s = %s", self.component_id, key, display
        )
