"""FileUnarchive engine component.

Talend equivalent: tFileUnarchive

Extracts a ZIP archive to a target directory. This component performs a
file-system operation and does not participate in row-based data flow --
input_data is ignored and the output is always an empty DataFrame.

Config keys (resolved by BaseComponent before _process is called):
    zipfile         (str, required)  -- path to the ZIP archive to extract
    directory       (str, required)  -- destination directory for extracted files
    extractpath     (bool, default True) -- preserve directory structure inside archive
    checkpassword   (bool, default False) -- use password protection
    password        (str, default "")    -- password for protected archives
    rootname        (str, default "")    -- optional root folder name prefix to strip
    printout        (bool, default False) -- log each extracted filename at DEBUG level
    die_on_error    (bool, default True) -- raise on failure vs. return empty result

GlobalMap variables set:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
    {id}_CURRENT_FILE -- last file extracted (set per-file during extraction)
    {id}_ERROR_MESSAGE -- error message if extraction fails
"""
import logging
import os
import zipfile
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileUnarchive", "FileUnarchiveComponent", "tFileUnarchive")
class FileUnarchive(BaseComponent):
    """Extracts files from a ZIP archive to a target directory.

    Validates member paths against the target directory to prevent zip-slip
    attacks before any file is written to disk.
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
        if not self.config.get("zipfile"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'zipfile'"
            )
        if not self.config.get("directory"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'directory'"
            )
        for bool_key in ("extractpath", "checkpassword", "printout"):
            val = self.config.get(bool_key)
            if val is not None and not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean, "
                    f"got {type(val).__name__!r}"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Extract a ZIP archive to the target directory.

        Performs zip-slip validation: each member's resolved absolute path
        must start with the target directory's absolute path, preventing
        directory traversal attacks via malicious archives.

        Args:
            input_data: Ignored -- this is a file utility with no data flow.

        Returns:
            Dict with 'main' key containing an empty DataFrame and 'reject' None.

        Raises:
            FileOperationError: If the archive does not exist, extraction path
                is unsafe (zip-slip), or the zip cannot be read.
        """
        zipfile_path = str(self.config["zipfile"]).strip()
        output_directory = str(self.config["directory"]).strip()
        extractpath = bool(self.config.get("extractpath", True))
        checkpassword = bool(self.config.get("checkpassword", False))
        password_raw = self.config.get("password", "")
        password = str(password_raw).encode() if password_raw else None
        rootname = str(self.config.get("rootname", "") or "").strip()
        printout = bool(self.config.get("printout", False))

        logger.info(
            "[%s] Extracting: %s -> %s (preserve_paths=%s)",
            self.id, zipfile_path, output_directory, extractpath,
        )

        # Validate archive exists
        if not os.path.exists(zipfile_path):
            raise FileOperationError(
                f"[{self.id}] Archive file does not exist: {zipfile_path!r}"
            )

        # Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)

        abs_output = os.path.abspath(output_directory)
        files_extracted = 0

        try:
            with zipfile.ZipFile(zipfile_path, "r") as zf:
                if checkpassword and password:
                    zf.setpassword(password)

                for member in zf.infolist():
                    member_name = member.filename

                    # Strip optional rootname prefix
                    if rootname and member_name.startswith(rootname + "/"):
                        member_name = member_name[len(rootname) + 1:]

                    if extractpath:
                        target_path = os.path.abspath(
                            os.path.join(abs_output, member_name)
                        )
                    else:
                        # Flatten: use only the basename, no directory structure
                        target_path = os.path.abspath(
                            os.path.join(abs_output, os.path.basename(member_name))
                        )

                    # ---- ZIP-SLIP PROTECTION ----
                    if not target_path.startswith(abs_output + os.sep) and target_path != abs_output:
                        raise FileOperationError(
                            f"[{self.id}] Zip-slip detected: member {member.filename!r} "
                            f"would extract outside target directory"
                        )

                    # Skip directory entries
                    if member.filename.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                        continue

                    # Ensure parent directory exists
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)

                    # Extract to the (safe) target path
                    with zf.open(member) as src, open(target_path, "wb") as dst:
                        dst.write(src.read())

                    files_extracted += 1
                    self.global_map.put(f"{self.id}_CURRENT_FILE", target_path)

                    if printout:
                        logger.debug("[%s] Extracted: %s", self.id, target_path)

        except zipfile.BadZipFile as exc:
            raise FileOperationError(
                f"[{self.id}] Bad or corrupt ZIP file {zipfile_path!r}: {exc}"
            ) from exc
        except OSError as exc:
            raise FileOperationError(
                f"[{self.id}] I/O error during extraction from {zipfile_path!r}: {exc}"
            ) from exc

        logger.info(
            "[%s] Extraction complete: %d file(s) extracted to %s",
            self.id, files_extracted, abs_output,
        )

        # File utility -- no row data processed
        self._update_stats(0, 0, 0)
        return {"main": pd.DataFrame(), "reject": None}

