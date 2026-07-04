"""tFileTouch component - Creates an empty file or updates its timestamp.

Talend equivalent: tFileTouch

Config mapping (Talend XML param -> v1 engine config key):
    FILENAME   -> filename       (str, required)
    CREATEDIR  -> createdir      (bool, default False) -- preferred per _java.xml
                  also accepts legacy ``create_directory``

Engine-only:
    die_on_error (bool, default True) -- inherited from BaseComponent.
                  When False, errors are logged and reported in the result
                  dict but the component does not raise.

GlobalMap variables:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT  via _update_stats()
    {id}_ERROR_MESSAGE  (string) -- set when the operation fails
"""
import os
from typing import Any, Dict, Optional
import logging

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileTouch", "tFileTouch")
class FileTouch(BaseComponent):
    """Creates or refreshes the modification time of a file (Unix ``touch``)."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_filename(self) -> str:
        return self.config.get("filename") or self.config.get("FILENAME") or ""

    def _get_createdir(self) -> bool:
        # CREATEDIR is the _java.xml param name; accept legacy
        # ``create_directory`` for backward compatibility.
        if "createdir" in self.config:
            return bool(self.config["createdir"])
        return bool(self.config.get("create_directory", False))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        filename = self._get_filename()
        if not isinstance(filename, str) or not filename.strip():
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filename'"
            )
        for key in ("createdir", "create_directory"):
            if key in self.config and not isinstance(self.config[key], bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{key}' must be a boolean"
                )

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        filename = self._get_filename()
        createdir = self._get_createdir()

        logger.info("[%s] Touch operation started: %s", self.id, filename)

        try:
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                if createdir:
                    logger.debug("[%s] Creating directory: %s", self.id, directory)
                    os.makedirs(directory, exist_ok=True)
                else:
                    raise FileOperationError(
                        f"[{self.id}] Parent directory does not exist: {directory} "
                        "(set createdir=true to auto-create)"
                    )

            with open(filename, "a", encoding="utf-8"):
                os.utime(filename, None)

            self._update_stats(rows_read=1, rows_ok=1, rows_reject=0)
            logger.info("[%s] Touch operation complete: %s", self.id, filename)
            return {
                "main": {"status": "success", "filename": filename},
                "reject": None,
            }

        except FileOperationError:
            self._update_stats(rows_read=1, rows_ok=0, rows_reject=1)
            if self.global_map is not None:
                self.global_map.put(f"{self.id}_ERROR_MESSAGE", "directory missing")
            raise

        except OSError as exc:
            self._update_stats(rows_read=1, rows_ok=0, rows_reject=1)
            error_msg = str(exc)
            if self.global_map is not None:
                self.global_map.put(f"{self.id}_ERROR_MESSAGE", error_msg)
            logger.error("[%s] Touch operation failed: %s", self.id, error_msg)
            if self.die_on_error:
                raise FileOperationError(
                    f"[{self.id}] Failed to touch file '{filename}': {error_msg}"
                ) from exc
            return {
                "main": {"status": "error", "filename": filename, "message": error_msg},
                "reject": None,
            }
