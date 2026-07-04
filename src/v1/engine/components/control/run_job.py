"""Engine component for tRunJob -- run another whole job in-process.

See docs/superpowers/specs/2026-06-30-trunjob-component-design.md.
"""
import logging
import re
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)

# Full-match anchored patterns for all supported forms:
#   ((Type)globalMap.get("KEY"))   -- Java double-paren cast wrapper (FQN, array, generic ok)
#   (Type)globalMap.get("KEY")     -- single-paren cast (e.g. (String)globalMap.get("K"))
#   globalMap.get("KEY")           -- bare form
# Composed expressions (e.g. "/data/" + globalMap.get("F")) do NOT match and trigger an error.
_GLOBALMAP_PURE = re.compile(
    r'\(\s*\(\s*[^)]+\s*\)\s*globalMap\.get\(\s*"([^"]+)"\s*\)\s*\)'  # ((Type)globalMap.get("KEY"))
    r'|\(\s*[^)]+\s*\)\s*globalMap\.get\(\s*"([^"]+)"\s*\)'           # (Type)globalMap.get("KEY")
    r'|globalMap\.get\(\s*"([^"]+)"\s*\)'                             # globalMap.get("KEY")
)

# Keys that mean nothing in the Python engine; warn once if set to a non-default truthy value.
_IGNORED_IF_SET = (
    "use_independent_process", "print_parameter", "propagate_child_result",
    "use_custom_jvm_setting", "use_extra_classpath", "load_context_from_file",
)


@REGISTRY.register("RunJob", "tRunJob")
class RunJob(BaseComponent):
    """tRunJob -- orchestration component that runs a child job to completion."""

    def _validate_config(self) -> None:
        if self.config.get("use_dynamic_job"):
            raise ConfigurationError(f"[{self.id}] tRunJob: dynamic job (use_dynamic_job) not supported")
        if self.config.get("use_dynamic_context"):
            raise ConfigurationError(f"[{self.id}] tRunJob: dynamic context not supported")
        if not str(self.config.get("process", "")).strip():
            raise ConfigurationError(f"[{self.id}] tRunJob: no child job 'process' configured")
        for key in _IGNORED_IF_SET:
            if self.config.get(key):
                logger.warning("[%s] tRunJob: '%s' is set but not supported by the Python engine; ignored",
                               self.id, key)

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        runner = getattr(self, "child_job_runner", None)
        if runner is None:
            raise ConfigurationError(f"[{self.id}] tRunJob: child_job_runner not available")

        process = self.config["process"]
        whole_context = (dict(self.context_manager.context)
                         if self.config.get("transmit_whole_context") else {})
        param_overrides = self._build_param_overrides()
        context_name = self.config.get("context_name", "Default")

        result = runner.run(process, whole_context, param_overrides, context_name)

        # Persist BEFORE any raise (base post-_process steps are skipped after a raise).
        self.global_map.put(f"{self.id}_CHILD_RETURN_CODE", int(result.return_code))
        if result.stacktrace:
            self.global_map.put(f"{self.id}_CHILD_EXCEPTION_STACKTRACE", result.stacktrace)

        if result.return_code != 0 and self.config.get("die_on_child_error", True):
            logger.error("[%s] child job '%s' failed (rc=%s); terminating parent",
                         self.id, process, result.return_code)
            err = ComponentExecutionError(
                self.id, f"tRunJob child '{process}' failed (rc={result.return_code})")
            err.exit_code = result.return_code      # dynamic attr AFTER construction -> kills parent
            raise err

        logger.info("[%s] child job '%s' completed (rc=%s)", self.id, process, result.return_code)
        return {"main": None, "reject": None}

    def _build_param_overrides(self) -> Dict[str, Any]:
        overrides: Dict[str, Any] = {}
        for row in self.config.get("context_params", []) or []:
            name = row.get("param_name")
            if not name:
                continue
            overrides[name] = self._resolve_globalmap(row.get("param_value"))
        return overrides

    def _resolve_globalmap(self, raw: Any) -> Any:
        # context.X / ${context.X} already resolved by execute() before _process.
        if not isinstance(raw, str):
            return raw
        m = _GLOBALMAP_PURE.fullmatch(raw.strip())
        if m:
            return self.global_map.get(m.group(1) or m.group(2) or m.group(3))
        if "globalMap.get(" in raw:
            raise ConfigurationError(
                f"[{self.id}] tRunJob: unsupported composed context_param expression {raw!r}; "
                f"only a bare globalMap.get(\"KEY\") (optionally cast-wrapped) is supported"
            )
        return raw
