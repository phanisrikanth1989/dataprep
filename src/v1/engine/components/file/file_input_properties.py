"""FileInputProperties engine component.

Talend equivalent: tFileInputProperties

Reads a Java .properties file (key=value pairs) or .ini file (sections with
key=value pairs) and maps property values to output schema columns by key name.

Config keys (all resolved by BaseComponent before _process is called):
    filename     (str, required)                      -- path to the file
    file_format  (str, default "PROPERTIES_FORMAT")   -- PROPERTIES_FORMAT or INI_FORMAT
    retrive_mode (str, default "RETRIVE_BY_SECTION")  -- RETRIVE_BY_SECTION or RETRIVE_ALL
    section_name (str, default "section")             -- INI section to read
    encoding     (str, default "ISO-8859-15")         -- file encoding
    tstatcatcher_stats (bool, default False)          -- framework
    label        (str, default "")                   -- framework

GlobalMap variables set:
    NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
"""
import configparser
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

_PROPERTIES_FORMAT = "PROPERTIES_FORMAT"
_INI_FORMAT = "INI_FORMAT"
_RETRIVE_BY_SECTION = "RETRIVE_BY_SECTION"
_RETRIVE_ALL = "RETRIVE_ALL"


@REGISTRY.register("FileInputProperties", "tFileInputProperties")
class FileInputProperties(BaseComponent):
    """Reads a .properties or .ini file and maps key/value pairs to output columns.

    For ``PROPERTIES_FORMAT`` files each non-comment, non-blank ``key=value``
    line is parsed into a property.  For ``INI_FORMAT`` files
    ``configparser`` is used.

    When ``retrive_mode=RETRIVE_BY_SECTION``, only the specified ``section_name``
    is read and one output row is produced.  When ``retrive_mode=RETRIVE_ALL``,
    all sections are read and each section produces one output row.

    Output schema column names are matched to property keys (case-sensitive).
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

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Read properties/ini file and produce output rows.

        Args:
            input_data: Not used -- this is a file source component.

        Returns:
            Dict with ``main`` (key/value rows DataFrame) and ``reject`` None.
        """
        filepath = str(self.config.get("filename", "")).strip()
        file_format = self.config.get("file_format", _PROPERTIES_FORMAT)
        retrive_mode = self.config.get("retrive_mode", _RETRIVE_BY_SECTION)
        section_name = self.config.get("section_name", "section")
        encoding = str(self.config.get("encoding", "ISO-8859-15")).strip() or "ISO-8859-15"

        # Content checks (Rule 12: deferred to _process)
        if not filepath:
            raise FileOperationError(
                f"[{self.id}] Config 'filename' is empty"
            )
        if not os.path.exists(filepath):
            raise FileOperationError(
                f"[{self.id}] File not found: {filepath!r}"
            )

        output_schema = getattr(self, "output_schema", None) or []
        col_names = [c["name"] for c in output_schema]

        try:
            if file_format == _INI_FORMAT:
                prop_rows = self._read_ini(filepath, encoding, retrive_mode, section_name)
            else:
                prop_rows = self._read_properties(filepath, encoding)
        except Exception as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to read properties file {filepath!r}: {exc}"
            ) from exc

        output_rows: list = []
        for prop_dict in prop_rows:
            out_row: dict = {}
            for col_name in col_names:
                out_row[col_name] = prop_dict.get(col_name, None)
            output_rows.append(out_row)

        main_df = (
            pd.DataFrame(output_rows, columns=col_names)
            if output_rows
            else pd.DataFrame(columns=col_names)
        )
        rows_ok = len(main_df)
        self._update_stats(rows_ok, rows_ok, 0)
        logger.info("[%s] done: file=%r rows=%d", self.id, filepath, rows_ok)
        return {"main": main_df, "reject": None}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_properties(filepath: str, encoding: str) -> List[Dict[str, str]]:
        """Parse a Java .properties file into a list containing one dict.

        Handles ``key=value`` and ``key: value`` syntax.  Lines starting with
        ``#`` or ``!`` are comments.  Line continuation via trailing ``\\`` is
        supported.
        """
        props: Dict[str, str] = {}
        continued = ""
        with open(filepath, encoding=encoding, errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n").rstrip("\r")
                if continued:
                    line = continued + line.lstrip()
                    continued = ""
                if line.endswith("\\"):
                    continued = line[:-1]
                    continue
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("!"):
                    continue
                if "=" in stripped:
                    key, _, value = stripped.partition("=")
                elif ":" in stripped:
                    key, _, value = stripped.partition(":")
                else:
                    continue
                props[key.strip()] = value.strip()
        return [props]

    @staticmethod
    def _read_ini(
        filepath: str,
        encoding: str,
        retrive_mode: str,
        section_name: str,
    ) -> List[Dict[str, str]]:
        """Parse an .ini file using configparser.

        Returns a list of dicts -- one per section (RETRIVE_ALL) or one for
        the specified section (RETRIVE_BY_SECTION).
        """
        parser = configparser.ConfigParser()
        with open(filepath, encoding=encoding, errors="replace") as fh:
            parser.read_file(fh)

        if retrive_mode == _RETRIVE_ALL:
            rows: List[Dict[str, str]] = []
            for section in parser.sections():
                row = dict(parser.items(section))
                row["__section__"] = section
                rows.append(row)
            return rows

        # RETRIVE_BY_SECTION
        if not parser.has_section(section_name):
            return [{}]
        return [dict(parser.items(section_name))]
