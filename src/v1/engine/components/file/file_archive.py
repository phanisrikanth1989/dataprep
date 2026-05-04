"""FileArchive engine component.

Talend equivalent: tFileArchive

Compresses files or directories into a ZIP archive. This component performs a
file-system operation and does not participate in row-based data flow -- input_data
is ignored and the output is always an empty DataFrame.

Config keys (resolved by BaseComponent before _process is called):
    source          (str, required)  -- source file or directory path
    target          (str, required)  -- destination archive file path
    archive_format  (str, default "ZIP") -- archive format; only "ZIP" supported
    sub_directroy   (bool, default True) -- include subdirectories (Talend typo preserved)
    overwrite       (bool, default True) -- overwrite existing target archive
    mkdir           (bool, default True) -- create target directory if it does not exist
    level           (str, default "4") -- compression level 0-9 as TEXT (context-var-safe)
    all_files       (bool, default True) -- include all files; when False apply mask filter
    mask            (str, default "")   -- glob mask for file filtering when all_files=False
    die_on_error    (bool, default True) -- raise on failure vs. return empty result

GlobalMap variables set:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
    {id}_ARCHIVE_FILEPATH -- absolute path to the created archive
    {id}_ARCHIVE_FILENAME -- basename of the created archive
"""
import fnmatch
import logging
import os
import zipfile
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = {"zip", "ZIP"}


@REGISTRY.register("FileArchive", "FileArchiveComponent", "tFileArchive")
class FileArchive(BaseComponent):
    """Compresses files or directories into a ZIP archive.

    Reads the source path and writes a ZIP archive to the target path. Optionally
    creates the target directory, applies a file mask filter, and sets globalMap
    variables with the archive path for downstream components.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check structural config -- key presence and container types only (Rule 12).

        Raises:
            ConfigurationError: If a required key is missing or a boolean field
                has the wrong type.
        """
        if not self.config.get("source"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'source'"
            )
        if not self.config.get("target"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'target'"
            )
        for bool_key in ("sub_directroy", "overwrite", "mkdir", "all_files"):
            val = self.config.get(bool_key)
            if val is not None and not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean, "
                    f"got {type(val).__name__!r}"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Create a ZIP archive from the configured source path.

        Args:
            input_data: Ignored -- this is a file utility with no data flow.

        Returns:
            Dict with 'main' key containing an empty DataFrame and 'reject' None.

        Raises:
            ConfigurationError: If compression level is not a valid integer 0-9.
            FileOperationError: If source does not exist, target exists and
                overwrite=False, mkdir=False and directory missing, or the
                archive cannot be written.
        """
        source = str(self.config["source"]).strip()
        target = str(self.config["target"]).strip()
        archive_format = str(self.config.get("archive_format", "ZIP")).strip().upper()
        sub_directroy = bool(self.config.get("sub_directroy", True))
        overwrite = bool(self.config.get("overwrite", True))
        mkdir = bool(self.config.get("mkdir", True))
        all_files = bool(self.config.get("all_files", True))
        mask = str(self.config.get("mask", "") or "").strip()

        # level is TEXT type in Talend (supports context-var expressions) -- coerce here
        raw_level = self.config.get("level", "4")
        try:
            compression_level = int(raw_level)
            if not 0 <= compression_level <= 9:
                raise ValueError("out of range")
        except (ValueError, TypeError):
            raise ConfigurationError(
                f"[{self.id}] Config 'level' must be an integer 0-9, got: {raw_level!r}"
            )

        if archive_format not in _SUPPORTED_FORMATS:
            raise FileOperationError(
                f"[{self.id}] Unsupported archive format: {archive_format!r}. "
                "Only 'ZIP' is supported."
            )

        logger.info(
            "[%s] Archiving: %s -> %s (level=%d, sub_dirs=%s)",
            self.id, source, target, compression_level, sub_directroy,
        )

        # Validate source exists
        if not os.path.exists(source):
            raise FileOperationError(
                f"[{self.id}] Source path does not exist: {source!r}"
            )

        # Handle target directory
        target_dir = os.path.dirname(target)
        if target_dir and not os.path.exists(target_dir):
            if mkdir:
                os.makedirs(target_dir, exist_ok=True)
                logger.debug("[%s] Created target directory: %s", self.id, target_dir)
            else:
                raise FileOperationError(
                    f"[{self.id}] Target directory does not exist and mkdir=False: "
                    f"{target_dir!r}"
                )

        # Check overwrite
        if os.path.exists(target) and not overwrite:
            raise FileOperationError(
                f"[{self.id}] Target archive already exists and overwrite=False: {target!r}"
            )

        # Determine zipfile compression
        compression = zipfile.ZIP_DEFLATED if compression_level > 0 else zipfile.ZIP_STORED

        files_archived = 0
        try:
            with zipfile.ZipFile(target, "w", compression=compression) as zf:
                if os.path.isdir(source):
                    for root, dirs, files in os.walk(source):
                        if not sub_directroy:
                            dirs.clear()  # prevent os.walk from recursing into subdirs
                        for fname in files:
                            if not all_files and mask and not fnmatch.fnmatch(fname, mask):
                                continue
                            file_path = os.path.join(root, fname)
                            arcname = os.path.relpath(file_path, source)
                            zf.write(file_path, arcname)
                            files_archived += 1
                            logger.debug("[%s] Added: %s", self.id, arcname)
                else:
                    fname = os.path.basename(source)
                    if not all_files and mask and not fnmatch.fnmatch(fname, mask):
                        logger.warning(
                            "[%s] Source file %r does not match mask %r -- "
                            "archive will be empty",
                            self.id, fname, mask,
                        )
                    else:
                        zf.write(source, fname)
                        files_archived = 1
        except (OSError, zipfile.BadZipFile) as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to create archive {target!r}: {exc}"
            ) from exc

        # Publish globalMap variables for downstream components
        abs_target = os.path.abspath(target)
        self.global_map.put(f"{self.id}_ARCHIVE_FILEPATH", abs_target)
        self.global_map.put(f"{self.id}_ARCHIVE_FILENAME", os.path.basename(abs_target))

        logger.info(
            "[%s] Archive created: %s (%d file(s))", self.id, abs_target, files_archived
        )

        # File utility -- no row data processed
        self._update_stats(0, 0, 0)
        return {"main": pd.DataFrame(), "reject": None}