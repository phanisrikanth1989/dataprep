"""FileProperties engine component.

Talend equivalent: tFileProperties

Extracts file metadata (path parts, size, modification time, optional MD5)
and emits a single-row DataFrame.

Config keys (all resolved by BaseComponent before _process is called):
    filename           (str, required)       -- path to the file
    md5                (bool, default False) -- calculate MD5 checksum
    tstatcatcher_stats (bool, default False) -- framework
    label              (str, default "")    -- framework

GlobalMap variables set:
    NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()  (always 1/1/0)
"""
import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileProperties", "tFileProperties")
class FileProperties(BaseComponent):
    """Extracts file metadata and emits a one-row DataFrame.

    Reads path parts, size, modification time, and optionally an MD5 checksum
    from the file at ``filename``.  All stat-based metadata is collected from
    a single ``os.stat()`` call to avoid TOCTOU races.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check key presence only (Rule 12)."""
        if "filename" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filename'"
            )
        if not isinstance(self.config.get("md5", False), bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'md5' must be a boolean"
            )

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """Extract file metadata and return as a one-row DataFrame.

        Args:
            input_data: Not used -- utility component with no FLOW input.

        Returns:
            Dict with ``main`` (single-row metadata DataFrame) and ``reject`` None.

        Raises:
            ConfigurationError: If filename is empty after resolution.
            FileOperationError: If the file cannot be accessed.
        """
        filepath = str(self.config.get("filename", "")).strip()
        calculate_md5 = self.config.get("md5", False)

        # Content checks deferred to _process (Rule 12)
        if not filepath:
            raise ConfigurationError(
                f"[{self.id}] Config 'filename' is empty"
            )

        try:
            stat = os.stat(filepath)
        except FileNotFoundError:
            raise FileOperationError(
                f"[{self.id}] File not found: {filepath!r}"
            )
        except OSError as exc:
            raise FileOperationError(
                f"[{self.id}] Cannot stat file {filepath!r}: {exc}"
            ) from exc

        mtime = stat.st_mtime
        props: Dict[str, Any] = {
            "abs_path": os.path.abspath(filepath),
            "dirname": os.path.dirname(filepath),
            "basename": os.path.basename(filepath),
            "mode_string": oct(stat.st_mode),
            "size": stat.st_size,
            "mtime": mtime,
            "mtime_string": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
        }

        if calculate_md5:
            logger.debug("[%s] Calculating MD5 for %r", self.id, filepath)
            props["md5"] = self._calculate_md5(filepath)

        main_df = pd.DataFrame([props])
        self._update_stats(1, 1, 0)
        logger.info("[%s] done: file=%r size=%d", self.id, filepath, stat.st_size)
        return {"main": main_df, "reject": None}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calculate_md5(self, filepath: str) -> str:
        """Return the hex MD5 digest of a file.

        Args:
            filepath: Path to the file.

        Returns:
            Hex MD5 string.

        Raises:
            FileOperationError: If the file cannot be read.
        """
        try:
            h = hashlib.md5()
            with open(filepath, "rb") as fh:
                for chunk in iter(lambda: fh.read(4096), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to calculate MD5 for {filepath!r}: {exc}"
            ) from exc
