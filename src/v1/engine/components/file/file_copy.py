"""tFileCopy component - Copies a file or directory.

Talend equivalent: tFileCopy

Config mapping (Talend XML param -> v1 engine config key):
    FILENAME                    -> filename                   (str, required for file mode)
                                   Also accepts legacy ``source``.
    ENABLE_COPY_DIRECTORY       -> enable_copy_directory      (bool, default False)
    SOURCE_DERECTORY            -> source_derectory           (str)  -- Talend typo preserved
                                   Also accepts ``source_directory``.
    DESTINATION                 -> destination                (str, required)
    RENAME                      -> rename                     (bool, default False)
    DESTINATION_RENAME          -> destination_rename         (str, default 'NewName.temp')
                                   Also accepts legacy ``new_name``.
    REMOVE_FILE                 -> remove_file                (bool, default False)
                                   When True, deletes source after successful copy.
    REPLACE_FILE                -> replace_file               (bool, default True)
    CREATE_DIRECTORY            -> create_directory           (bool, default True)
    FAILON                      -> failon                     (bool, default False)
                                   Also accepts legacy ``fail_on_error``.
    FORCE_COPY_DELETE           -> force_copy_delete          (bool, default False)
                                   Used with REMOVE_FILE to force delete of source.
    PRESERVE_LAST_MODIFIED_TIME -> preserve_last_modified_time (bool, default False)
                                   Also accepts legacy ``preserve_last_modified``.

GlobalMap variables:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
    {id}_ERROR_MESSAGE  (string) -- set when the copy operation fails
"""
import os
import shutil
from typing import Any, Dict, Optional
import logging

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileCopy", "tFileCopy")
class FileCopy(BaseComponent):
    """Copies a file or directory from source to destination.

    Supports rename, replace, directory-tree copy, source-removal (move
    semantics), timestamp preservation, and FAILON error policy per Talend.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_bool(self, *keys: str, default: bool = False) -> bool:
        for k in keys:
            if k in self.config:
                return bool(self.config[k])
        return default

    def _get_str(self, *keys: str, default: str = "") -> str:
        for k in keys:
            if k in self.config and self.config[k] is not None:
                return str(self.config[k])
        return default

    def _resolve_source(self) -> str:
        if self._get_bool("enable_copy_directory", default=False):
            return self._get_str(
                "source_derectory", "source_directory", "filename", "source"
            )
        return self._get_str("filename", "source")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        source = self._resolve_source()
        destination = self._get_str("destination")
        if not source.strip():
            raise ConfigurationError(
                f"[{self.id}] Missing required source config "
                "('filename' or 'source_derectory' when enable_copy_directory=true)"
            )
        if not destination.strip():
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'destination'"
            )
        bool_keys = (
            "enable_copy_directory", "rename", "remove_file", "replace_file",
            "create_directory", "failon", "fail_on_error", "force_copy_delete",
            "preserve_last_modified_time", "preserve_last_modified",
        )
        for key in bool_keys:
            if key in self.config and not isinstance(self.config[key], bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{key}' must be a boolean"
                )

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        source = self._resolve_source()
        destination = self._get_str("destination")
        rename = self._get_bool("rename", default=False)
        new_name = self._get_str("destination_rename", "new_name", default="")
        replace_file = self._get_bool("replace_file", default=True)
        create_directory = self._get_bool("create_directory", default=True)
        preserve_last_modified = self._get_bool(
            "preserve_last_modified_time", "preserve_last_modified", default=False
        )
        remove_file = self._get_bool("remove_file", default=False)
        failon = self._get_bool("failon", "fail_on_error", default=False)
        force_copy_delete = self._get_bool("force_copy_delete", default=False)
        enable_copy_directory = self._get_bool("enable_copy_directory", default=False)

        logger.info(
            "[%s] Copy operation started: %s -> %s", self.id, source, destination,
        )

        copied = False
        error_msg: Optional[str] = None

        try:
            if not os.path.exists(source):
                raise FileOperationError(
                    f"[{self.id}] Source path does not exist: {source}"
                )

            is_directory_copy = enable_copy_directory or os.path.isdir(source)

            # Decide final destination path.
            if is_directory_copy:
                final_destination = destination
                if create_directory:
                    parent = os.path.dirname(destination.rstrip(os.sep))
                    if parent and not os.path.exists(parent):
                        os.makedirs(parent, exist_ok=True)
            else:
                # File-mode copy: ensure dest directory exists, then place file.
                if create_directory and not os.path.exists(destination):
                    os.makedirs(destination, exist_ok=True)
                target_filename = new_name if (rename and new_name) else os.path.basename(source)
                if os.path.isdir(destination):
                    final_destination = os.path.join(destination, target_filename)
                else:
                    final_destination = destination

            if (
                os.path.exists(final_destination)
                and not replace_file
                and not is_directory_copy
            ):
                raise FileOperationError(
                    f"[{self.id}] Destination already exists and replace_file=False: "
                    f"{final_destination}"
                )

            if is_directory_copy:
                shutil.copytree(source, final_destination, dirs_exist_ok=replace_file)
            else:
                shutil.copy2(source, final_destination)

            if preserve_last_modified:
                shutil.copystat(source, final_destination)

            copied = True
            logger.info(
                "[%s] Copy complete: %s -> %s", self.id, source, final_destination,
            )

            # Move semantics: REMOVE_FILE deletes source after successful copy.
            if remove_file and (copied or force_copy_delete):
                try:
                    if os.path.isdir(source):
                        shutil.rmtree(source)
                    else:
                        os.remove(source)
                    logger.info("[%s] Source removed after copy: %s", self.id, source)
                except OSError as rm_exc:
                    if force_copy_delete:
                        logger.warning(
                            "[%s] Forced source removal failed: %s",
                            self.id, rm_exc,
                        )
                    else:
                        raise

        except (OSError, FileOperationError) as exc:
            error_msg = str(exc)
            logger.error("[%s] Copy operation failed: %s", self.id, error_msg)
            self._update_stats(rows_read=1, rows_ok=0, rows_reject=1)
            if self.global_map is not None:
                self.global_map.put(f"{self.id}_ERROR_MESSAGE", error_msg)
            if failon or self.die_on_error:
                if isinstance(exc, FileOperationError):
                    raise
                raise FileOperationError(
                    f"[{self.id}] Copy failed ({source} -> {destination}): {error_msg}"
                ) from exc
            return {
                "main": {
                    "status": "error",
                    "source": source,
                    "destination": destination,
                    "message": error_msg,
                },
                "reject": None,
            }

        self._update_stats(rows_read=1, rows_ok=1, rows_reject=0)
        return {
            "main": {
                "status": "success",
                "source": source,
                "destination": final_destination,
            },
            "reject": None,
        }
