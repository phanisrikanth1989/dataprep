"""tFileOutputXML engine component (simple/flat XML output).

Writes a DataFrame to an XML file with one ROW_TAG element per row. Sub-elements
or attributes per column according to MAPPING.AS_ATTRIBUTE. Optional ROOT_TAGS
wrapper. Streaming-write via etree.xmlfile (NEVER buffer the full tree per
Pitfall P-2). Sink contract (S-5): passthrough main; globalMap puts file name +
line count.

Per D-D5: hand-authored Job_tFileOutputXML_0.1.item fixture exercises the
end-to-end pipeline.

Config keys consumed:
  filename            (str, required)        -- output file path
  input_is_document   (bool, default False)  -- each row's doc col is XML to pass through
  document_col        (str, default "")      -- column name when input_is_document=True
  row_tag             (str, default "row")   -- wrapper element per row
  root_tags           (list, default [])     -- outer wrapper elements (list of {name: str})
  mapping             (list, default [])     -- [{column, as_attribute}] per output column
  use_dynamic_grouping(bool, default False)  -- [DEFERRED] dynamic grouping
  group_by            (list, default [])     -- [DEFERRED] grouping columns
  flushonrow          (bool, default False)  -- flush xmlfile context after each row
  flushonrow_num      (str, default "1")     -- flush every N rows (reserved)
  encoding            (str, default "ISO-8859-15") -- output file encoding
  split               (bool, default False)  -- split output into multiple files
  split_every         (str, default "1000")  -- rows per split file
  create              (bool, default True)   -- overwrite existing file
  trim                (bool, default False)  -- strip whitespace from document_col in doc mode
  advanced_separator  (bool, default False)  -- [DEFERRED] numeric separator config
  thousands_separator (str, default ",")     -- [DEFERRED] thousands grouping char
  decimal_separator   (str, default ".")     -- [DEFERRED] decimal point char
  delete_empty_file   (bool, default False)  -- delete file if no rows written
  tstatcatcher_stats  (bool, default False)  -- stat catcher integration flag
  label               (str, default "")     -- display label
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from lxml import etree

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError
from . import _xml_io

logger = logging.getLogger(__name__)

# Module-level helper for safe int coercion (mirrors file_output_delimited)
def _safe_int(value: Any, default: int) -> int:
    """Safely parse a value to int with a default fallback."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _split_filename(filepath: str, index: int) -> str:
    """Generate split filename: {stem}{index}{suffix}."""
    p = Path(filepath)
    return str(p.with_name(f"{p.stem}{index}{p.suffix}"))


@REGISTRY.register("FileOutputXML", "tFileOutputXML")
class FileOutputXML(BaseComponent):
    """Write DataFrame to XML file (simple/flat tFileOutputXML).

    Streaming-aware: first chunk opens etree.xmlfile context; subsequent
    chunks reuse the open context; reset() closes contexts on iterate
    re-execution. Per Pitfall P-2: NEVER buffers the full tree.

    Sink contract (S-5): returns {'main': input_data, 'reject': None}.
    globalMap puts {id}_FILE_NAME and {id}_NB_LINE after each chunk.
    """

    # ------------------------------------------------------------------
    # Streaming-write state (S-6)
    # ------------------------------------------------------------------

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Active etree.xmlfile() context manager (held across chunks)
        self._streaming_xmlfile_ctx = None
        # Active root-element context (xf.element(root_tag)) (held across chunks)
        self._streaming_xmlfile_root_ctx = None
        # Whether _process() has opened the xmlfile context for the first time
        self._streaming_write_started: bool = False
        # The entered xf object (xmlfile incremental writer)
        self._streaming_xf = None
        # The underlying file handle (kept open across chunks)
        self._streaming_filehandle = None
        # Cumulative rows written across all chunks
        self._streaming_total_written: int = 0
        # Resolved filepath for the current execution
        self._streaming_filepath: Optional[str] = None

    def reset(self) -> None:
        """Reset streaming state for re-execution (iterate support).

        Closes any leftover etree.xmlfile context managers before clearing
        state so that the XML file is properly terminated on forced close.
        Per S-6: reset() is called by BaseComponent finalize and by the
        iterate loop between runs.
        """
        super().reset()
        # Close root-element context first (inner), then xmlfile context (outer)
        if self._streaming_xmlfile_root_ctx is not None:
            try:
                self._streaming_xmlfile_root_ctx.__exit__(None, None, None)
            except Exception:
                pass
        if self._streaming_xmlfile_ctx is not None:
            try:
                self._streaming_xmlfile_ctx.__exit__(None, None, None)
            except Exception:
                pass
        if self._streaming_filehandle is not None:
            try:
                self._streaming_filehandle.close()
            except Exception:
                pass
        self._streaming_xmlfile_ctx = None
        self._streaming_xmlfile_root_ctx = None
        self._streaming_write_started = False
        self._streaming_xf = None
        self._streaming_filehandle = None
        self._streaming_total_written = 0
        self._streaming_filepath = None

    # ------------------------------------------------------------------
    # Bool-coerce helper (ENG-WR-11 analog)
    # ------------------------------------------------------------------

    @staticmethod
    def _bool(v: Any) -> bool:
        """Coerce config value to bool, handling JSON string 'true'/'false'.

        Args:
            v: Config value -- may be bool, int, or string.

        Returns:
            True if v is truthy and not the string literal 'false'/'0'/'no'.
        """
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes")
        return bool(v)

    # ------------------------------------------------------------------
    # Configuration Validation (Rule 12)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Presence and type checks only (Rule 12).

        Content checks (file existence, encoding validity) are deferred to
        _process() so context variable references resolve first.

        Raises:
            ConfigurationError: If 'filename' is missing or a bool-typed
                config key holds a value that cannot be coerced to bool.
        """
        if not self.config.get("filename"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filename'"
            )
        bool_keys = (
            "input_is_document", "use_dynamic_grouping", "flushonrow",
            "split", "create", "trim", "advanced_separator",
            "delete_empty_file", "tstatcatcher_stats",
        )
        for key in bool_keys:
            if key in self.config:
                val = self.config[key]
                if not isinstance(val, (bool, str, int)):
                    raise ConfigurationError(
                        f"[{self.id}] Config '{key}' must be coercible to bool, "
                        f"got {type(val).__name__!r}"
                    )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Write DataFrame chunk to XML file and passthrough original input.

        Sink contract (S-5): input_data is returned unchanged as 'main'.
        Streaming hook (S-6): first call opens etree.xmlfile context; subsequent
        calls reuse the held context. Contexts are closed by reset().

        Per Pitfall P-2: NEVER buffers the full tree. Uses only
        etree.xmlfile() incremental API (no tostring, no SubElement).

        Args:
            input_data: Input DataFrame from upstream component, or None.

        Returns:
            dict with 'main' == input_data (passthrough identity, S-5)
            and 'reject' == None.

        Raises:
            FileOperationError: If create=False and the file already exists,
                or if the file write fails.
        """
        # ---- 1. Read and coerce config ----
        filename = self.config["filename"]
        input_is_document = self._bool(self.config.get("input_is_document", False))
        document_col = self.config.get("document_col", "") or ""
        row_tag = self.config.get("row_tag", "row") or "row"
        root_tags = self.config.get("root_tags", []) or []
        mapping = self.config.get("mapping", []) or []
        encoding = self.config.get("encoding", "ISO-8859-15") or "ISO-8859-15"
        create = self._bool(self.config.get("create", True))
        flushonrow = self._bool(self.config.get("flushonrow", False))
        trim = self._bool(self.config.get("trim", False))
        delete_empty_file = self._bool(self.config.get("delete_empty_file", False))
        split = self._bool(self.config.get("split", False))
        split_every = _safe_int(self.config.get("split_every", "1000"), 1000)

        # ---- 2. Resolve filepath ----
        filepath = Path(filename)

        # ---- 3. CREATE check (only on first chunk) ----
        if not create and filepath.exists() and not self._streaming_write_started:
            raise FileOperationError(
                f"[{self.id}] File exists and create=False: {filename!r}"
            )

        # ---- 4. Empty input handling ----
        if input_data is None or len(input_data) == 0:
            if delete_empty_file and filepath.exists():
                filepath.unlink()
                logger.info("[%s] Deleted empty file: %r", self.id, str(filepath))
            self._update_stats(0, 0, 0)
            if self.global_map:
                self.global_map.put(f"{self.id}_FILE_NAME", str(filepath))
                self.global_map.put(f"{self.id}_NB_LINE", 0)
            return {"main": input_data, "reject": None}

        # ---- 5. SPLIT mode (simpler approach: write per chunk range) ----
        if split and not self._streaming_write_started:
            written = self._write_split(
                input_data, filepath, split_every, row_tag, root_tags,
                mapping, encoding, flushonrow, trim, input_is_document,
                document_col,
            )
            self._streaming_total_written += written
            self._update_stats(written, written, 0)
            if self.global_map:
                self.global_map.put(f"{self.id}_FILE_NAME", str(filepath))
                self.global_map.put(f"{self.id}_NB_LINE", self._streaming_total_written)
            logger.info(
                "[%s] Split write complete: %d rows to %r",
                self.id, written, str(filepath),
            )
            return {"main": input_data, "reject": None}

        # ---- 6. Compute attribute columns from MAPPING ----
        attr_cols: set = {
            m["column"] for m in mapping if self._bool(m.get("as_attribute", False))
        }

        # ---- 7. Open xmlfile context if first chunk (S-6 streaming hook) ----
        if not self._streaming_write_started:
            # Ensure parent directory exists
            if filepath.parent and str(filepath.parent) != ".":
                filepath.parent.mkdir(parents=True, exist_ok=True)
            self._streaming_filehandle = open(filepath, "wb")
            self._streaming_xmlfile_ctx = etree.xmlfile(
                self._streaming_filehandle, encoding=encoding
            )
            self._streaming_xf = self._streaming_xmlfile_ctx.__enter__()
            self._streaming_xf.write_declaration()
            # Open root wrapper element.  An XML document MUST have exactly one root;
            # use the first ROOT_TAGS entry if provided, otherwise default to "root".
            if root_tags:
                outer = root_tags[0]
                outer_name = outer.get("name") if isinstance(outer, dict) else str(outer)
            else:
                outer_name = "root"
            self._streaming_xmlfile_root_ctx = self._streaming_xf.element(outer_name)
            self._streaming_xmlfile_root_ctx.__enter__()
            self._streaming_write_started = True
            self._streaming_filepath = str(filepath)

        # ---- 8. Write rows using etree.xmlfile incremental API ----
        xf = self._streaming_xf
        written = 0

        for _, row in input_data.iterrows():
            if input_is_document:
                # Passthrough mode: each row holds a complete XML document string
                doc = row.get(document_col, "") if document_col else ""
                if trim and isinstance(doc, str):
                    doc = doc.strip()
                if doc:
                    try:
                        # T-12-01 mitigation: parse with secure parser before re-emitting
                        parser = _xml_io.secure_xml_parser(recover=False)
                        doc_bytes = (
                            doc.encode("utf-8") if isinstance(doc, str) else doc
                        )
                        sub_root = etree.fromstring(doc_bytes, parser=parser)
                        xf.write(sub_root)
                    except etree.XMLSyntaxError as exc:
                        logger.warning(
                            "[%s] Skipping malformed XML doc row: %s", self.id, exc
                        )
                        continue
            else:
                # Standard mode: one <row_tag> element per row
                attrs: Dict[str, str] = {}
                for col in attr_cols:
                    if col in row.index:
                        val = row[col]
                        attrs[col] = "" if pd.isna(val) else str(val)

                with xf.element(row_tag, **attrs):
                    if mapping:
                        # Emit only mapping-declared columns as sub-elements
                        for m in mapping:
                            col = m["column"]
                            if col in attr_cols:
                                continue  # already an attribute
                            if col in row.index:
                                val = row[col]
                                text = "" if pd.isna(val) else str(val)
                                with xf.element(col):
                                    xf.write(text)
                    else:
                        # No mapping: emit all non-attribute columns as sub-elements
                        for col in row.index:
                            if col in attr_cols:
                                continue
                            val = row[col]
                            text = "" if pd.isna(val) else str(val)
                            with xf.element(col):
                                xf.write(text)

            if flushonrow:
                xf.flush()
            written += 1

        self._streaming_total_written += written

        # ---- 9. GlobalMap puts (S-5 requirement) ----
        if self.global_map:
            self.global_map.put(f"{self.id}_FILE_NAME", str(filepath))
            self.global_map.put(f"{self.id}_NB_LINE", self._streaming_total_written)

        # ---- 10. Stats ----
        self._update_stats(written, written, 0)

        logger.info(
            "[%s] Wrote %d rows to %r (total=%d)",
            self.id, written, str(filepath), self._streaming_total_written,
        )

        # NOTE: xmlfile context NOT closed here -- streaming hook holds it open.
        # Closure happens in reset() which BaseComponent finalize calls after
        # the last chunk (or on iterate re-execution start).

        return {"main": input_data, "reject": None}

    # ------------------------------------------------------------------
    # Split-mode write helper
    # ------------------------------------------------------------------

    def _write_split(
        self,
        df: pd.DataFrame,
        base_filepath: Path,
        rows_per_file: int,
        row_tag: str,
        root_tags: List[Dict[str, Any]],
        mapping: List[Dict[str, Any]],
        encoding: str,
        flushonrow: bool,
        trim: bool,
        input_is_document: bool,
        document_col: str,
    ) -> int:
        """Write DataFrame split across numbered output files.

        Files are named: {stem}{index}{suffix}. Each split file gets its own
        XML declaration and root wrapper (if ROOT_TAGS specified). This is a
        stateless method -- does not modify streaming-hook state.

        Args:
            df: DataFrame to write.
            base_filepath: Base output Path.
            rows_per_file: Maximum rows per split file.
            row_tag: XML element name for each row.
            root_tags: Root wrapper element list.
            mapping: Column-to-attribute mapping list.
            encoding: Output file encoding.
            flushonrow: Whether to flush after each row.
            trim: Whether to strip whitespace from document col.
            input_is_document: Whether each row is a full XML doc.
            document_col: Column name holding XML doc in doc mode.

        Returns:
            Total number of rows written across all split files.
        """
        attr_cols: set = {
            m["column"] for m in mapping if self._bool(m.get("as_attribute", False))
        }
        total_written = 0
        chunk_index = 0

        for start in range(0, len(df), rows_per_file):
            chunk = df.iloc[start: start + rows_per_file]
            split_path = _split_filename(str(base_filepath), chunk_index)

            split_fp = Path(split_path)
            if split_fp.parent and str(split_fp.parent) != ".":
                split_fp.parent.mkdir(parents=True, exist_ok=True)

            with open(split_path, "wb") as fh:
                with etree.xmlfile(fh, encoding=encoding) as xf:
                    xf.write_declaration()
                    # Always wrap in a root element for valid XML
                    if root_tags:
                        outer = root_tags[0]
                        outer_name = (
                            outer.get("name") if isinstance(outer, dict) else str(outer)
                        )
                    else:
                        outer_name = "root"
                    with xf.element(outer_name):
                        # WR-02 fix: use returned count (not len(chunk)) so that
                        # rows skipped due to XMLSyntaxError in input_is_document
                        # mode are not counted in NB_LINE stats.
                        chunk_written = self._write_rows_to_xf(
                            xf, chunk, row_tag, attr_cols, mapping,
                            flushonrow, trim, input_is_document, document_col,
                        )

            total_written += chunk_written
            logger.info(
                "[%s] Split file %d: %d rows to %r",
                self.id, chunk_index, chunk_written, split_path,
            )
            chunk_index += 1

        return total_written

    def _write_rows_to_xf(
        self,
        xf,
        df: pd.DataFrame,
        row_tag: str,
        attr_cols: set,
        mapping: List[Dict[str, Any]],
        flushonrow: bool,
        trim: bool,
        input_is_document: bool,
        document_col: str,
    ) -> int:
        """Write DataFrame rows to an open etree.xmlfile incremental writer.

        This helper is shared between streaming and split write paths to avoid
        code duplication. It does NOT touch streaming-hook state.

        WR-02 fix: now returns the actual number of rows successfully written
        (previously returned None). In input_is_document mode, rows with
        malformed XML are skipped via continue -- the caller must use the
        returned count, not len(df), to avoid overcounting in NB_LINE stats.

        Args:
            xf: Entered etree.xmlfile incremental writer object.
            df: DataFrame rows to write.
            row_tag: XML element name per row.
            attr_cols: Set of column names to emit as XML attributes.
            mapping: Column-to-attribute mapping list.
            flushonrow: Whether to flush after each row.
            trim: Whether to strip whitespace in doc mode.
            input_is_document: Whether each row is a full XML doc.
            document_col: Column name for doc mode.

        Returns:
            Number of rows actually written (skipped rows not counted).
        """
        written = 0
        for _, row in df.iterrows():
            if input_is_document:
                doc = row.get(document_col, "") if document_col else ""
                if trim and isinstance(doc, str):
                    doc = doc.strip()
                if doc:
                    try:
                        parser = _xml_io.secure_xml_parser(recover=False)
                        doc_bytes = (
                            doc.encode("utf-8") if isinstance(doc, str) else doc
                        )
                        sub_root = etree.fromstring(doc_bytes, parser=parser)
                        xf.write(sub_root)
                        written += 1
                    except etree.XMLSyntaxError as exc:
                        logger.warning(
                            "[%s] Skipping malformed XML doc row: %s", self.id, exc
                        )
                        continue
            else:
                attrs: Dict[str, str] = {}
                for col in attr_cols:
                    if col in row.index:
                        val = row[col]
                        attrs[col] = "" if pd.isna(val) else str(val)

                with xf.element(row_tag, **attrs):
                    if mapping:
                        for m in mapping:
                            col = m["column"]
                            if col in attr_cols:
                                continue
                            if col in row.index:
                                val = row[col]
                                text = "" if pd.isna(val) else str(val)
                                with xf.element(col):
                                    xf.write(text)
                    else:
                        for col in row.index:
                            if col in attr_cols:
                                continue
                            val = row[col]
                            text = "" if pd.isna(val) else str(val)
                            with xf.element(col):
                                xf.write(text)
                written += 1

            if flushonrow:
                xf.flush()
        return written
