"""tFileDelete component - Deletes a file or directory.

Talend equivalent: tFileDelete

Config mapping (Talend XML param -> v1 engine config key):
    FILENAME    -> filename      (str)  default-mode source path
    DIRECTORY   -> directory     (str)  FOLDER mode source path
    PATH        -> path          (str)  FOLDER_FILE mode source path
                  Also accepts a single legacy ``path`` for any mode.
    FAILON      -> failon        (bool, default True)
                  Also accepts legacy ``fail_on_error``.
    FOLDER      -> folder        (bool, default False) - directory mode
                  Also accepts legacy ``is_directory``.
    FOLDER_FILE -> folder_file   (bool, default False) - auto-detect mode
                  Also accepts legacy ``is_folder_file``.

Engine extension (no Talend equivalent):
    recursive   (bool, default True) - recursive directory removal.
                Talend deletes directory trees implicitly; default True
                preserves Talend behaviour.

GlobalMap variables (Talend parity):
    {id}_DELETE_PATH     (string)  - resolved path that was acted on
    {id}_CURRENT_STATUS  (string)  - "deleted" or "not exist"
    {id}_ERROR_MESSAGE   (string)  - error message when deletion fails
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT  via _update_stats()
"""
import os
import shutil
from typing import Any, Dict, Optional
import logging

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileDelete", "tFileDelete")
class FileDelete(BaseComponent):
    """Deletes a file or directory in one of three modes.

    Modes (mutually exclusive, evaluated in order):
        1. ``folder_file`` (auto-detect) - delete whatever exists at ``path``
        2. ``folder``      (directory)   - delete a directory at ``directory``
        3. default         (file)        - delete a file at ``filename``
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_bool(self, *keys: str, default: bool = False) -> bool:
        for k in keys:
            if k in self.config:
                return bool(self.config[k])
        return default

    def _get_failon(self) -> bool:
        return self._get_bool("failon", "fail_on_error", default=True)

    def _get_folder(self) -> bool:
        return self._get_bool("folder", "is_directory", default=False)

    def _get_folder_file(self) -> bool:
        return self._get_bool("folder_file", "is_folder_file", default=False)

    def _get_recursive(self) -> bool:
        # Default True to mirror Talend's implicit recursive directory delete.
        return bool(self.config.get("recursive", True))

    def _resolve_path(self) -> str:
        """Pick the path key that matches the active mode, with fallbacks."""
        if self._get_folder_file():
            return self.config.get("path") or self.config.get("PATH") or ""
        if self._get_folder():
            return (
                self.config.get("directory")
                or self.config.get("DIRECTORY")
                or self.config.get("path")
                or ""
            )
        return (
            self.config.get("filename")
            or self.config.get("FILENAME")
            or self.config.get("path")
            or ""
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        path = self._resolve_path()
        if not isinstance(path, str) or not path.strip():
            raise ConfigurationError(
                f"[{self.id}] Missing required path config "
                "('filename', 'directory', or 'path' depending on mode)"
            )
        for key in (
            "failon", "fail_on_error", "folder", "is_directory",
            "folder_file", "is_folder_file", "recursive",
        ):
            if key in self.config and not isinstance(self.config[key], bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{key}' must be a boolean"
                )

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        path = self._resolve_path()
        failon = self._get_failon()
        folder = self._get_folder()
        folder_file = self._get_folder_file()
        recursive = self._get_recursive()

        logger.info("[%s] Delete operation started: %s", self.id, path)
        deleted = False
        status = "not exist"
        error_msg: Optional[str] = None

        try:
            if folder_file:
                if os.path.isfile(path):
                    os.remove(path)
                    deleted = True
                elif os.path.isdir(path):
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        os.rmdir(path)
                    deleted = True
            elif folder:
                if os.path.isdir(path):
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        os.rmdir(path)
                    deleted = True
            else:
                if os.path.isfile(path):
                    os.remove(path)
                    deleted = True

            if deleted:
                status = "deleted"
                logger.info("[%s] Deleted: %s", self.id, path)
            else:
                logger.warning("[%s] Path does not exist: %s", self.id, path)

        except OSError as exc:
            error_msg = str(exc)
            logger.error("[%s] Error deleting %s: %s", self.id, path, error_msg)
            self._update_stats(rows_read=1, rows_ok=0, rows_reject=1)
            if self.global_map is not None:
                self.global_map.put(f"{self.id}_DELETE_PATH", path)
                self.global_map.put(f"{self.id}_CURRENT_STATUS", "error")
                self.global_map.put(f"{self.id}_ERROR_MESSAGE", error_msg)
            if failon:
                raise FileOperationError(
                    f"[{self.id}] Failed to delete '{path}': {error_msg}"
                ) from exc
            return {
                "main": {"status": "error", "path": path, "message": error_msg},
                "reject": None,
            }

        rows_ok = 1 if deleted else 0
        rows_reject = 0 if deleted else 1
        self._update_stats(rows_read=1, rows_ok=rows_ok, rows_reject=rows_reject)
        if self.global_map is not None:
            self.global_map.put(f"{self.id}_DELETE_PATH", path)
            self.global_map.put(f"{self.id}_CURRENT_STATUS", status)

        return {
            "main": {"status": status, "path": path, "deleted": deleted},
            "reject": None,
        }
