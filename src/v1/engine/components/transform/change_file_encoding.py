"""ChangeFileEncoding engine component.

Talend equivalent: tChangeFileEncoding

Re-encodes a file from one character encoding to another. Operates entirely
at the OS file level -- does NOT participate in row-based data flow. Has no
FLOW input/output connectors, so input_data is ignored and the output is
always an empty DataFrame.

Config keys (all resolved by BaseComponent before _process is called):
    infile_name     (str, required) -- source file path
    outfile_name    (str, required) -- destination file path
    use_inencoding  (bool, default False) -- when True, use inencoding for reading
    inencoding      (str, default "ISO-8859-15") -- source file charset
    encoding        (str, default "ISO-8859-15") -- target file charset
    buffersize      (str, default "8192") -- read/write buffer size in bytes
                    stored as TEXT in Talend to allow context-var expressions
    create          (bool, default True) -- create output file if it does not exist

GlobalMap variables set:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
    (always 0 -- file utility, no rows processed)
"""
import locale
import logging
import os
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("ChangeFileEncoding", "tChangeFileEncoding")
class ChangeFileEncoding(BaseComponent):
    """Re-encodes a file from one character encoding to another.

    Reads the source file using the specified (or system default) encoding
    and writes the output file in the target encoding using a configurable
    buffer size. Optionally creates the output file if it does not exist.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check structural config -- key presence and container types only (Rule 12)."""
        if not self.config.get("infile_name"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'infile_name'"
            )
        if not self.config.get("outfile_name"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'outfile_name'"
            )
        if not isinstance(self.config.get("use_inencoding", False), bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'use_inencoding' must be a boolean"
            )
        if not isinstance(self.config.get("create", True), bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'create' must be a boolean"
            )

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """Re-encode the source file and write to the destination file.

        Args:
            input_data: Ignored -- this is a file utility with no data flow.

        Returns:
            Dict with 'main' key containing an empty DataFrame and 'reject' None.
        """
        infile = str(self.config["infile_name"]).strip()
        outfile = str(self.config["outfile_name"]).strip()
        use_inencoding = bool(self.config.get("use_inencoding", False))
        inencoding = str(self.config.get("inencoding", "ISO-8859-15")).strip() or "ISO-8859-15"
        outencoding = str(self.config.get("encoding", "ISO-8859-15")).strip() or "ISO-8859-15"
        create = bool(self.config.get("create", True))

        # buffersize is TEXT type (may be context var) -- coerce to int here in _process
        raw_buffersize = self.config.get("buffersize", "8192")
        try:
            buffersize = int(raw_buffersize)
            if buffersize < 1:
                raise ValueError
        except (ValueError, TypeError):
            raise FileOperationError(
                f"[{self.id}] buffersize must be a positive integer, got: {raw_buffersize!r}"
            )

        # Resolve source encoding
        src_encoding = inencoding if use_inencoding else locale.getpreferredencoding(False)

        logger.info(
            "[%s] Re-encoding: %s (%s) -> %s (%s), buffer=%d bytes",
            self.id, infile, src_encoding, outfile, outencoding, buffersize,
        )

        # Validate source exists
        if not os.path.exists(infile):
            raise FileOperationError(
                f"[{self.id}] Source file does not exist: {infile}"
            )

        # Handle create=False: fail if output does not exist
        if not create and not os.path.exists(outfile):
            raise FileOperationError(
                f"[{self.id}] Output file does not exist and create=False: {outfile}"
            )

        # Ensure output directory exists
        outdir = os.path.dirname(outfile)
        if outdir and not os.path.exists(outdir):
            os.makedirs(outdir, exist_ok=True)

        # Perform chunked re-encoding
        try:
            with (
                open(infile, mode="r", encoding=src_encoding, errors="replace") as src,
                open(outfile, mode="w", encoding=outencoding, errors="replace") as dst,
            ):
                while True:
                    chunk = src.read(buffersize)
                    if not chunk:
                        break
                    dst.write(chunk)
        except (OSError, LookupError) as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to re-encode {infile!r}: {exc}"
            ) from exc

        logger.info("[%s] Re-encoding complete: %s", self.id, outfile)

        # File utility -- no rows produced
        self._update_stats(0, 0, 0)
        return {"main": pd.DataFrame(), "reject": None}
