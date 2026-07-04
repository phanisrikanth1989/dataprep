"""tFileExist component - Checks if a file or directory exists.

Talend equivalent: tFileExist

Config mapping (Talend XML param -> v1 engine config key):
    FILE_NAME           -> file_name (preferred); also accepts ``file_path``
                          and legacy ``FILE_NAME`` for backward compatibility
    (engine extension)  -> check_directory  (bool, default False)
                          When True, only directories satisfy the check.

GlobalMap variables (Talend parity):
    {id}_EXISTS    (bool)   - whether the path exists at check time
    {id}_FILENAME  (string) - resolved file path that was checked

Statistics:
    NB_LINE         = 1 (one existence check)
    NB_LINE_OK      = 1 (the check itself always succeeds as an operation)
    NB_LINE_REJECT  = 0
"""
import os
from typing import Any, Dict, Optional
import logging

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileExistComponent", "FileExist", "tFileExist")
class FileExistComponent(BaseComponent):
    """Checks whether a file (or directory) exists at the configured path.

    Trigger-only component -- emits no row data. Sets ``{id}_EXISTS`` and
    ``{id}_FILENAME`` in globalMap so downstream RUN_IF triggers can branch
    on the result, matching Talend's tFileExist behaviour.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_file_path(self) -> str:
        """Return the configured path, accepting all converter aliases."""
        return (
            self.config.get("file_name")
            or self.config.get("file_path")
            or self.config.get("FILE_NAME")
            or ""
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        path = self._resolve_file_path()
        if not isinstance(path, str) or not path.strip():
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'file_name' "
                "(also accepts 'file_path' or legacy 'FILE_NAME')"
            )
        check_directory = self.config.get("check_directory", False)
        if not isinstance(check_directory, bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'check_directory' must be a boolean"
            )

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        file_path = self._resolve_file_path()
        check_directory = self.config.get("check_directory", False)

        logger.info("[%s] File existence check started: %s", self.id, file_path)

        if check_directory:
            file_exists = os.path.isdir(file_path)
            check_type = "directory"
        else:
            file_exists = os.path.exists(file_path)
            check_type = "file/directory"

        # The check itself is an operation -- always OK.
        self._update_stats(rows_read=1, rows_ok=1, rows_reject=0)

        # Talend-parity globalMap variables.
        if self.global_map is not None:
            self.global_map.put(f"{self.id}_EXISTS", bool(file_exists))
            self.global_map.put(f"{self.id}_FILENAME", file_path)

        logger.info(
            "[%s] File existence check complete: %s '%s' exists=%s",
            self.id, check_type, file_path, file_exists,
        )

        return {
            "main": {"file_exists": bool(file_exists), "file_path": file_path},
            "reject": None,
        }
