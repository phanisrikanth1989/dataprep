"""tAdvancedFileOutputXML engine component (hierarchical XML output).

ROOT/GROUP/LOOP TABLE-driven nesting; emits via etree.xmlfile incremental
write (Pitfall P-2: NEVER buffer the full tree). Streaming-aware: nested
context managers held on self.

D-E1 conditional warn-and-ignore: dtd_valid+file_valid, xsl_valid+file_valid,
output_as_xsd, add_document_as_node, add_unmapped_attribute, merge each emit
a runtime warning when set, but the engine does NOT raise -- falls back to
plain hierarchical write per scope. The converter emits a needs_review entry
per active flag.

Config keys consumed:
  filename              (str, required)             -- output file path
  root                  (list, default [])          -- ROOT TABLE rows (stride-5 dicts)
  group                 (list, default [])          -- GROUP TABLE rows (stride-5 dicts)
  loop                  (list, default [])          -- LOOP TABLE rows (stride-5 dicts)
  encoding              (str, default ISO-8859-15)  -- output file encoding
  create                (bool, default True)        -- overwrite existing file
  file_valid            (bool, default False)       -- file validation flag (D-E1 guard)
  dtd_valid             (bool, default True)        -- DTD validation flag (D-E1 guard)
  xsl_valid             (bool, default False)       -- XSL validation flag (D-E1 guard)
  output_as_xsd         (bool, default False)       -- emit XSD (D-E1 guard)
  add_document_as_node  (bool, default False)       -- embed XML doc (D-E1 guard)
  add_unmapped_attribute(bool, default False)       -- pass-through unmapped attrs (D-E1)
  merge                 (bool, default False)       -- merge mode (D-E1 guard)
  split                 (bool, default False)       -- split output into multiple files
  split_every           (str, default "1000")       -- rows per split file
  trim                  (bool, default False)       -- strip whitespace
  delete_empty_file     (bool, default False)       -- delete output if empty
  generation_mode       (str, default DOM4J)        -- generation mode
  advanced_separator    (bool, default False)       -- [DEFERRED] advanced separator
  thousands_separator   (str, default ",")          -- [DEFERRED] thousands char
  decimal_separator     (str, default ".")          -- [DEFERRED] decimal char
  tstatcatcher_stats    (bool, default False)       -- stat catcher integration
  label                 (str, default "")           -- display label
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

logger = logging.getLogger(__name__)


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


@REGISTRY.register("AdvancedFileOutputXML", "tAdvancedFileOutputXML")
class AdvancedFileOutputXML(BaseComponent):
    """Write DataFrame to hierarchical XML file (tAdvancedFileOutputXML).

    ROOT/GROUP/LOOP TABLE-driven nesting. Hierarchical write uses nested
    etree.xmlfile context managers per lxml incremental API (Pitfall P-2:
    NEVER buffers the full tree -- no etree.tostring or etree.SubElement).

    Streaming-aware (S-6): first chunk opens etree.xmlfile contexts and enters
    ROOT; subsequent chunks reuse open state; reset() closes contexts from
    innermost to outermost on iterate re-execution.

    Sink contract (S-5): returns {'main': input_data, 'reject': None}.
    globalMap puts {id}_FILE_NAME and {id}_NB_LINE after each chunk.

    D-E1 conditional warn-and-ignore: 6 deferred sub-features each emit a
    logger.warning when set in config; the engine does NOT raise and falls back
    to plain hierarchical write.
    """

    # ------------------------------------------------------------------
    # D-E1 deferred sub-features (RESEARCH.md / 12-01-AUDIT lock-in)
    # These are warned at runtime and ignored -- converter emits needs_review.
    # ------------------------------------------------------------------
    _DEFERRED_FLAGS = (
        ("dtd_valid_combined", "DTD validation (file_valid=true, dtd_valid=true)"),
        ("xsl_valid_combined", "XSL validation (file_valid=true, xsl_valid=true)"),
        ("output_as_xsd", "XSD generation (output_as_xsd=true)"),
        ("add_document_as_node", "Document column passthrough (add_document_as_node=true)"),
        ("add_unmapped_attribute", "Unmapped-attribute pass-through (add_unmapped_attribute=true)"),
        ("merge", "Merge mode (merge=true) -- falls back to overwrite"),
    )

    # ------------------------------------------------------------------
    # Streaming-write state (S-6) -- nested contexts held on self
    # ------------------------------------------------------------------

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Active etree.xmlfile() context manager entry point
        self._streaming_xmlfile_ctx = None
        # The entered xmlfile incremental writer object
        self._streaming_xf = None
        # Active root-element context (xf.element(root_path)) held across chunks
        self._streaming_root_ctx = None
        # The underlying file handle (kept open across chunks)
        self._streaming_filehandle = None
        # Whether _process() has opened the xmlfile context for the first time
        self._streaming_write_started: bool = False
        # Cumulative rows written across all chunks
        self._streaming_total_written: int = 0
        # Active group context (used internally per chunk; fully closed per group)
        self._streaming_group_ctx = None

    def reset(self) -> None:
        """Reset streaming state for re-execution (iterate support).

        Closes contexts from innermost to outermost so the XML file is properly
        terminated. Per S-6: reset() is called by BaseComponent finalize and by
        the iterate loop between runs.
        """
        super().reset()
        # Close innermost group context first (if left open unexpectedly)
        if self._streaming_group_ctx is not None:
            try:
                self._streaming_group_ctx.__exit__(None, None, None)
            except Exception:
                pass
        self._streaming_group_ctx = None
        # Close root element context
        if self._streaming_root_ctx is not None:
            try:
                self._streaming_root_ctx.__exit__(None, None, None)
            except Exception:
                pass
        self._streaming_root_ctx = None
        # Close xmlfile context (flushes pending bytes)
        if self._streaming_xmlfile_ctx is not None:
            try:
                self._streaming_xmlfile_ctx.__exit__(None, None, None)
            except Exception:
                pass
        self._streaming_xmlfile_ctx = None
        # Close file handle
        if self._streaming_filehandle is not None:
            try:
                self._streaming_filehandle.close()
            except Exception:
                pass
        self._streaming_filehandle = None
        self._streaming_xf = None
        self._streaming_write_started = False
        self._streaming_total_written = 0

    # ------------------------------------------------------------------
    # Bool-coerce helper
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
    # Configuration validation (Rule 12 -- presence/type checks only)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Presence and type checks only (Rule 12).

        Content checks (file existence, encoding validity) are deferred to
        _process() so context variable references resolve first.

        Raises:
            ConfigurationError: If 'filename' is missing.
        """
        if not self.config.get("filename"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filename'"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Write DataFrame chunk to hierarchical XML file and passthrough input.

        Sink contract (S-5): input_data is returned unchanged as 'main'.
        Streaming hook (S-6): first call opens etree.xmlfile context and ROOT
        element; subsequent calls reuse the held context. Contexts closed by reset().

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
        root_table = self.config.get("root", []) or []
        group_table = self.config.get("group", []) or []
        loop_table = self.config.get("loop", []) or []
        encoding = self.config.get("encoding", "ISO-8859-15") or "ISO-8859-15"
        create = self._bool(self.config.get("create", True))
        file_valid = self._bool(self.config.get("file_valid", False))
        dtd_valid = self._bool(self.config.get("dtd_valid", True))
        xsl_valid = self._bool(self.config.get("xsl_valid", False))
        delete_empty_file = self._bool(self.config.get("delete_empty_file", False))
        split = self._bool(self.config.get("split", False))
        split_every = _safe_int(self.config.get("split_every", "1000"), 1000)

        # ---- 2. D-E1 warn-and-ignore for 6 deferred sub-features ----
        if file_valid and dtd_valid:
            logger.warning(
                "[%s] DTD validation (file_valid=true, dtd_valid=true) is not implemented "
                "in this engine; ignoring (Phase 12 needs_review entry).", self.id,
            )
        if file_valid and xsl_valid:
            logger.warning(
                "[%s] XSL validation (file_valid=true, xsl_valid=true) is not implemented "
                "in this engine; ignoring (Phase 12 needs_review entry).", self.id,
            )
        if self._bool(self.config.get("output_as_xsd", False)):
            logger.warning(
                "[%s] OUTPUT_AS_XSD is not implemented in this engine; ignoring "
                "(Phase 12 needs_review entry).", self.id,
            )
        if self._bool(self.config.get("add_document_as_node", False)):
            logger.warning(
                "[%s] ADD_DOCUMENT_AS_NODE is not implemented in this engine; ignoring "
                "(Phase 12 needs_review entry).", self.id,
            )
        if self._bool(self.config.get("add_unmapped_attribute", False)):
            logger.warning(
                "[%s] ADD_UNMAPPED_ATTRIBUTE is not implemented in this engine; ignoring "
                "(Phase 12 needs_review entry).", self.id,
            )
        if self._bool(self.config.get("merge", False)):
            logger.warning(
                "[%s] MERGE mode is not implemented in this engine; falling back to "
                "overwrite (Phase 12 needs_review entry).", self.id,
            )

        # ---- 3. Resolve filepath ----
        filepath = Path(filename)

        # ---- 4. CREATE check (only on first chunk) ----
        if not create and filepath.exists() and not self._streaming_write_started:
            raise FileOperationError(
                f"[{self.id}] File exists and create=False: {filename!r}"
            )

        # ---- 5. Empty input handling ----
        if input_data is None or len(input_data) == 0:
            if delete_empty_file and filepath.exists():
                filepath.unlink()
                logger.info("[%s] Deleted empty file: %r", self.id, str(filepath))
            self._update_stats(0, 0, 0)
            if self.global_map:
                self.global_map.put(f"{self.id}_FILE_NAME", str(filepath))
                self.global_map.put(f"{self.id}_NB_LINE", 0)
            return {"main": input_data, "reject": None}

        # ---- 6. SPLIT mode ----
        if split and not self._streaming_write_started:
            written = self._write_split(
                input_data, filepath, split_every, root_table, group_table,
                loop_table, encoding,
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

        # ---- 7. Open xmlfile context if first chunk (S-6 streaming hook) ----
        if not self._streaming_write_started:
            if filepath.parent and str(filepath.parent) != ".":
                filepath.parent.mkdir(parents=True, exist_ok=True)
            self._streaming_filehandle = open(filepath, "wb")
            self._streaming_xmlfile_ctx = etree.xmlfile(
                self._streaming_filehandle, encoding=encoding
            )
            self._streaming_xf = self._streaming_xmlfile_ctx.__enter__()
            self._streaming_xf.write_declaration()
            # Open ROOT element context (held across all chunks)
            if root_table:
                root_path = root_table[0].get("path", "root") if isinstance(root_table[0], dict) else "root"
                root_attrs = self._collect_static_attrs(root_table[0])
                self._streaming_root_ctx = self._streaming_xf.element(root_path, **root_attrs)
                self._streaming_root_ctx.__enter__()
                # Emit static sub-entries of root_table (root_table[1:])
                self._emit_static_entries(self._streaming_xf, root_table[1:])
            else:
                # Default root element when no ROOT TABLE configured
                self._streaming_root_ctx = self._streaming_xf.element("root")
                self._streaming_root_ctx.__enter__()
            self._streaming_write_started = True

        # ---- 8. Hierarchical emission per chunk ----
        xf = self._streaming_xf
        written = 0

        if group_table:
            # GROUP_TABLE: emit per-group wrapper elements, then LOOP rows inside
            group_cols = self._extract_group_columns(group_table)
            if group_cols:
                try:
                    group_iter = list(input_data.groupby(group_cols, dropna=False))
                except Exception:
                    # Fallback: treat entire chunk as one group if groupby fails
                    group_iter = [(None, input_data)]
            else:
                # No group-by columns -> single group for entire chunk
                group_iter = [(None, input_data)]

            for _group_key, group_df in group_iter:
                group_path = (
                    group_table[0].get("path", "group")
                    if isinstance(group_table[0], dict) else "group"
                )
                group_attrs = self._collect_static_attrs(group_table[0])
                with xf.element(group_path, **group_attrs):
                    self._emit_static_entries(xf, group_table[1:])
                    for _, row in group_df.iterrows():
                        written += 1
                        self._emit_loop_row(xf, row, loop_table)
                    xf.flush()
        else:
            # No GROUP TABLE -> emit LOOP rows directly under ROOT
            for _, row in input_data.iterrows():
                written += 1
                self._emit_loop_row(xf, row, loop_table)
            xf.flush()

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
    # Loop-row emission helpers
    # ------------------------------------------------------------------

    def _emit_loop_row(self, xf, row: pd.Series, loop_table: List[Dict[str, Any]]) -> None:
        """Emit one LOOP element with sub-elements/attributes per loop_table entry.

        The first loop_table entry defines the wrapper element name (and any
        static attrs from ATTRIBUTE=true + VALUE entries). Subsequent entries
        define either child elements (attribute=false) or attributes on the
        wrapper (attribute=true with column reference).

        Args:
            xf: Entered etree.xmlfile incremental writer.
            row: Current DataFrame row (pd.Series).
            loop_table: LOOP TABLE rows (stride-5 dicts from converter).
        """
        if not loop_table:
            # No LOOP TABLE: emit row as <row> element with each column as a child
            with xf.element("row"):
                for col in row.index:
                    val = row[col]
                    text = "" if pd.isna(val) else str(val)
                    with xf.element(col):
                        xf.write(text)
            return

        loop_path = loop_table[0].get("path", "row") if isinstance(loop_table[0], dict) else "row"

        # Collect attributes from subsequent entries with attribute=true
        loop_attrs: Dict[str, str] = {}
        for entry in loop_table[1:]:
            if not isinstance(entry, dict):
                continue
            if self._bool(entry.get("attribute", False)):
                attr_name = entry.get("path", entry.get("column", ""))
                val = self._resolve_value(entry, row)
                loop_attrs[attr_name] = "" if val is None else str(val)

        with xf.element(loop_path, **loop_attrs):
            for entry in loop_table[1:]:
                if not isinstance(entry, dict):
                    continue
                if self._bool(entry.get("attribute", False)):
                    continue  # already emitted as XML attribute above
                name = entry.get("path", entry.get("column", "field"))
                val = self._resolve_value(entry, row)
                text = "" if val is None else str(val)
                with xf.element(name):
                    xf.write(text)

    def _resolve_value(self, entry: Dict[str, Any], row: pd.Series) -> Any:
        """Pick the correct value for a TABLE entry: column-based or static value.

        Args:
            entry: A single TABLE row dict with 'column', 'value', 'path' keys.
            row: Current DataFrame row.

        Returns:
            The resolved value (str / numeric), or None for NaN/empty.
        """
        col = entry.get("column", "")
        if col and col in row.index:
            v = row[col]
            return None if pd.isna(v) else v
        return entry.get("value", "") or None

    def _extract_group_columns(self, group_table: List[Dict[str, Any]]) -> List[str]:
        """Determine which columns drive the group_by from group_table entries.

        Column-driven entries (column key non-empty) form the pandas groupby key.

        Args:
            group_table: GROUP TABLE rows.

        Returns:
            List of column names for groupby (may be empty).
        """
        cols = []
        for entry in group_table:
            if isinstance(entry, dict):
                col = entry.get("column", "")
                if col:
                    cols.append(col)
        return cols

    def _collect_static_attrs(self, entry: Any) -> Dict[str, str]:
        """Collect static XML attributes from a TABLE entry.

        A TABLE entry contributes an XML attribute on its wrapper element when
        attribute=true AND value is non-empty AND column is empty (static value).

        Args:
            entry: A single TABLE row dict.

        Returns:
            Dict of {attr_name: attr_value} (empty if not applicable).
        """
        if not isinstance(entry, dict):
            return {}
        if self._bool(entry.get("attribute", False)) and entry.get("value") and not entry.get("column"):
            return {entry.get("path", "attr"): str(entry["value"])}
        return {}

    def _emit_static_entries(self, xf, entries: List[Any]) -> None:
        """Emit static (no-column, value-only) elements under the current context.

        Used to emit ROOT TABLE[1:] or GROUP TABLE[1:] static sub-elements.
        Column-driven entries and attribute entries are skipped (they belong to
        the LOOP TABLE row emission).

        Args:
            xf: Entered etree.xmlfile incremental writer.
            entries: TABLE rows to scan for static elements.
        """
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("column"):
                continue  # column-driven entries belong to LOOP rows
            if self._bool(entry.get("attribute", False)):
                continue  # attributes already collected by parent caller
            path = entry.get("path", "static")
            val = entry.get("value", "") or ""
            with xf.element(path):
                xf.write(str(val))

    # ------------------------------------------------------------------
    # Split-mode write helper
    # ------------------------------------------------------------------

    def _write_split(
        self,
        df: pd.DataFrame,
        base_filepath: Path,
        rows_per_file: int,
        root_table: List[Dict[str, Any]],
        group_table: List[Dict[str, Any]],
        loop_table: List[Dict[str, Any]],
        encoding: str,
    ) -> int:
        """Write DataFrame split across numbered output files.

        Files are named: {stem}{index}{suffix}. Each split file is self-contained
        with its own XML declaration, ROOT, and GROUP/LOOP structure. This is a
        stateless method -- does not modify streaming-hook state.

        Args:
            df: DataFrame to write.
            base_filepath: Base output Path.
            rows_per_file: Maximum rows per split file.
            root_table: ROOT TABLE rows.
            group_table: GROUP TABLE rows.
            loop_table: LOOP TABLE rows.
            encoding: Output file encoding.

        Returns:
            Total number of rows written across all split files.
        """
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
                    # Open ROOT element
                    if root_table:
                        root_path = (
                            root_table[0].get("path", "root")
                            if isinstance(root_table[0], dict) else "root"
                        )
                        root_attrs = self._collect_static_attrs(root_table[0])
                    else:
                        root_path = "root"
                        root_attrs = {}

                    with xf.element(root_path, **root_attrs):
                        if root_table:
                            self._emit_static_entries(xf, root_table[1:])
                        chunk_written = self._write_chunk_to_xf(
                            xf, chunk, group_table, loop_table
                        )
                        total_written += chunk_written

            logger.info(
                "[%s] Split file %d: %d rows to %r",
                self.id, chunk_index, chunk_written, split_path,
            )
            chunk_index += 1

        return total_written

    def _write_chunk_to_xf(
        self,
        xf,
        chunk: pd.DataFrame,
        group_table: List[Dict[str, Any]],
        loop_table: List[Dict[str, Any]],
    ) -> int:
        """Write one chunk of rows to an open etree.xmlfile writer.

        Args:
            xf: Entered etree.xmlfile incremental writer.
            chunk: DataFrame rows to write.
            group_table: GROUP TABLE rows.
            loop_table: LOOP TABLE rows.

        Returns:
            Number of rows written.
        """
        written = 0
        if group_table:
            group_cols = self._extract_group_columns(group_table)
            if group_cols:
                try:
                    group_iter = list(chunk.groupby(group_cols, dropna=False))
                except Exception:
                    group_iter = [(None, chunk)]
            else:
                group_iter = [(None, chunk)]

            for _group_key, group_df in group_iter:
                group_path = (
                    group_table[0].get("path", "group")
                    if isinstance(group_table[0], dict) else "group"
                )
                group_attrs = self._collect_static_attrs(group_table[0])
                with xf.element(group_path, **group_attrs):
                    self._emit_static_entries(xf, group_table[1:])
                    for _, row in group_df.iterrows():
                        written += 1
                        self._emit_loop_row(xf, row, loop_table)
                    xf.flush()
        else:
            for _, row in chunk.iterrows():
                written += 1
                self._emit_loop_row(xf, row, loop_table)
            xf.flush()

        return written
