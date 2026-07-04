"""Engine component for OracleBulkExec (tOracleBulkExec).

Bulk-loads the incoming FLOW into an Oracle table via SQL*Loader (``sqlldr``).
The component:
  1. Materializes the input DataFrame to a delimited data file (unless DATA
     already points at a prepared file with no FLOW in).
  2. Generates a SQL*Loader control (.ctl) file from the input schema + config
     (unless USE_EXISTING_CLT_FILE points at a hand-written CLT_FILE).
  3. Shells out to ``sqlldr`` with a userid built from the connection params and
     NLS environment derived from the NLS_* settings.
  4. Parses the sqlldr log for rows loaded / rejected, publishes stats, and (when
     DIE_ON_ERROR) raises on a non-zero sqlldr exit.

``sqlldr`` is an external Oracle Instant Client binary; it is invoked via
subprocess and is therefore exercised by @pytest.mark.oracle integration tests
only. Unit tests mock ``subprocess.run`` and assert the generated control file
and argv (the deterministic, host-independent surface).

DATA_ACTION drives the control-file load keyword (INSERT / APPEND / REPLACE /
TRUNCATE). TABLE_ACTION DDL beyond NONE / TRUNCATE is deferred (raise
ConfigurationError) -- create/drop the table upstream with tOracleRow.

Security: the sqlldr userid embeds the password and is NEVER logged (T-11-02).
ASCII-only logging (D-H7).
"""
import csv
import logging
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# FIELDS_TERMINATOR enum -> literal delimiter character.
_TERMINATOR_CHARS = {
    "TAB": "\t",
    "COMMA": ",",
    "SEMICOLON": ";",
    "SPACE": " ",
    "PIPE": "|",
    "DOUBLE_QUOTE": '"',
}

# DATA_ACTION -> SQL*Loader load-mode keyword.
_VALID_DATA_ACTIONS = frozenset({"INSERT", "APPEND", "REPLACE", "TRUNCATE"})

# TABLE_ACTION values handled without schema-DDL generation.
_TABLE_ACTION_NONE = "NONE"
_TABLE_ACTION_TRUNCATE = "TRUNCATE"

# Regexes for parsing the sqlldr log summary.
_RE_LOADED = re.compile(r"(\d+)\s+Rows?\s+successfully\s+loaded", re.IGNORECASE)
_RE_NOT_LOADED = re.compile(r"(\d+)\s+Rows?\s+not\s+loaded", re.IGNORECASE)


@REGISTRY.register("OracleBulkExec", "tOracleBulkExec")
class OracleBulkExec(BaseComponent):
    """tOracleBulkExec engine component. See module docstring."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize. ``oracle_manager`` is injected by ETLEngine
        ``_initialize_components``."""
        super().__init__(*args, **kwargs)
        self.oracle_manager = None  # type: ignore  # set by engine

    # ------------------------------------------------------------------
    # Validation (structural only per Rule 12 / D-F3)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Structural validation only.

        Verifies ``table`` is present and DATA_ACTION is in the closed set.
        TABLE_ACTION DDL refusal is a CONTENT check in ``_process``.
        """
        if not self.config.get("table"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'table'"
            )
        data_action = self.config.get("data_action", "INSERT").upper()
        if data_action not in _VALID_DATA_ACTIONS:
            raise ConfigurationError(
                f"[{self.id}] Invalid data_action {data_action!r}. "
                f"Must be one of: {sorted(_VALID_DATA_ACTIONS)}"
            )

    # ------------------------------------------------------------------
    # Process
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Run the SQL*Loader bulk load.

        Returns:
            ``{"main": None, "reject": None}`` -- tOracleBulkExec is a sink.
        """
        self._refuse_unsupported_table_action()

        tmp_paths: List[str] = []
        try:
            data_file = self._resolve_data_file(input_data, tmp_paths)
            control_file = self._resolve_control_file(input_data, data_file, tmp_paths)
            log_file = self._make_tmp(".log", tmp_paths)
            bad_file = self._make_tmp(".bad", tmp_paths)

            argv = self._build_sqlldr_argv(control_file, data_file, log_file, bad_file)
            env = self._build_nls_env()

            logger.info(
                "[%s] Invoking sqlldr (table=%s, action=%s)",
                self.id, self.config.get("table"),
                self.config.get("data_action", "INSERT").upper(),
            )
            # T-11-02: argv[1] is the userid (embeds password); never logged.
            completed = subprocess.run(
                argv, capture_output=True, text=True, env=env, check=False
            )
            loaded, rejected = self._parse_log(log_file)
            self._publish_stats(loaded, rejected, input_data)
            self._handle_exit(completed.returncode, completed.stderr, rejected)
        finally:
            self._cleanup_tmp(tmp_paths)

        return {"main": None, "reject": None}

    # ------------------------------------------------------------------
    # TABLE_ACTION
    # ------------------------------------------------------------------

    def _refuse_unsupported_table_action(self) -> None:
        """Refuse CREATE/DROP-family TABLE_ACTION (deferred to upstream DDL)."""
        action = self.config.get("table_action", _TABLE_ACTION_NONE).upper()
        if action not in (_TABLE_ACTION_NONE, _TABLE_ACTION_TRUNCATE):
            raise ConfigurationError(
                f"[{self.id}] table_action {action!r} requires schema DDL "
                f"generation; not supported for bulk load. Create/drop the "
                f"target table upstream (e.g. tOracleRow). Tracked in deferred "
                f"items. (NONE and TRUNCATE are supported.)"
            )

    # ------------------------------------------------------------------
    # Data file
    # ------------------------------------------------------------------

    def _resolve_data_file(
        self, input_data: Optional[pd.DataFrame], tmp_paths: List[str]
    ) -> str:
        """Return the data file path, writing the input DataFrame to it.

        When DATA is set, the rows are written there (a stable path the operator
        can inspect); otherwise a temp file is used and cleaned up afterwards.
        When there is no input FLOW, DATA must already point at a prepared file.
        """
        data_path = self.config.get("data", "")
        if input_data is None or input_data.empty:
            if not data_path:
                raise ConfigurationError(
                    f"[{self.id}] No input FLOW and no 'data' file configured; "
                    f"nothing to load"
                )
            return data_path

        if not data_path:
            data_path = self._make_tmp(".dat", tmp_paths)
        delimiter = self._resolve_delimiter()
        quoting = (
            csv.QUOTE_ALL
            if self.config.get("use_fields_enclosure", False)
            else csv.QUOTE_MINIMAL
        )
        try:
            input_data.to_csv(
                data_path,
                sep=delimiter,
                header=False,
                index=False,
                quoting=quoting,
            )
        except OSError as e:
            raise FileOperationError(
                f"[{self.id}] Failed to write data file {data_path!r}: {e}"
            ) from e
        return data_path

    def _resolve_delimiter(self) -> str:
        """Return the literal field delimiter from FIELDS_TERMINATOR config."""
        terminator = self.config.get("fields_terminator", "OTHER").upper()
        if terminator == "OTHER":
            return self.config.get("terminator_value", ";")
        return _TERMINATOR_CHARS.get(terminator, ";")

    # ------------------------------------------------------------------
    # Control file
    # ------------------------------------------------------------------

    def _resolve_control_file(
        self,
        input_data: Optional[pd.DataFrame],
        data_file: str,
        tmp_paths: List[str],
    ) -> str:
        """Return the control file path -- existing CLT_FILE or a generated one."""
        if self.config.get("use_existing_clt_file", False):
            clt_file = self.config.get("clt_file", "")
            if not clt_file:
                raise ConfigurationError(
                    f"[{self.id}] use_existing_clt_file=True but 'clt_file' is empty"
                )
            return clt_file

        control_file = self._make_tmp(".ctl", tmp_paths)
        content = self._generate_control_file(data_file)
        try:
            with open(control_file, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as e:
            raise FileOperationError(
                f"[{self.id}] Failed to write control file {control_file!r}: {e}"
            ) from e
        return control_file

    def _generate_control_file(self, data_file: str) -> str:
        """Build the SQL*Loader control-file text from input schema + config."""
        data_action = self.config.get("data_action", "INSERT").upper()
        table = self.config.get("table")
        delimiter = self._resolve_delimiter()

        lines: List[str] = ["LOAD DATA"]
        encoding = self.config.get("encoding", "UTF8")
        if encoding:
            lines.append(f"CHARACTERSET {encoding}")
        lines.append(f"INFILE '{data_file}'")
        lines.append(data_action)
        lines.append(f"INTO TABLE {table}")

        fields_clause = f"FIELDS TERMINATED BY '{self._escape_delim(delimiter)}'"
        if self.config.get("use_fields_enclosure", False):
            fields_clause += ' OPTIONALLY ENCLOSED BY \'"\''
        lines.append(fields_clause)

        if self.config.get("preserve_blanks", False):
            lines.append("PRESERVE BLANKS")
        if self.config.get("trailing_nullcols", False):
            lines.append("TRAILING NULLCOLS")

        lines.append("(")
        lines.append(self._column_specs())
        lines.append(")")
        return "\n".join(lines) + "\n"

    def _column_specs(self) -> str:
        """Render the column list, applying DATE masks when USE_DATE_PATTERN set."""
        schema = getattr(self, "input_schema", None) or []
        use_date = self.config.get("use_date_pattern", False)
        upper = self.config.get("convert_column_table_to_uppercase", False)
        specs: List[str] = []
        for col in schema:
            name = col.get("name", "")
            if upper:
                name = name.upper()
            spec = f"  {name}"
            if use_date and self._is_date_column(col) and col.get("date_pattern"):
                mask = self._oracle_date_mask(col["date_pattern"])
                spec += f' DATE "{mask}"'
            specs.append(spec)
        return ",\n".join(specs)

    @staticmethod
    def _is_date_column(col: Dict[str, Any]) -> bool:
        """Return True for date/timestamp-typed schema columns."""
        return str(col.get("type", "")).lower() in ("date", "datetime", "timestamp")

    @staticmethod
    def _oracle_date_mask(java_pattern: str) -> str:
        """Translate a common Java date pattern to an Oracle date mask.

        Handles the frequent tokens; unknown patterns pass through unchanged so
        the operator can correct them in the generated control file.
        """
        mask = java_pattern
        for java_tok, ora_tok in (
            ("yyyy", "YYYY"), ("yy", "YY"),
            ("MM", "MM"), ("dd", "DD"),
            ("HH", "HH24"), ("mm", "MI"), ("ss", "SS"),
        ):
            mask = mask.replace(java_tok, ora_tok)
        return mask

    @staticmethod
    def _escape_delim(delimiter: str) -> str:
        """Render TAB as the sqlldr ``X'09'`` form is overkill; use literal tab.

        For the common single-char delimiters a literal is fine inside the
        single-quoted FIELDS TERMINATED BY clause. A tab is emitted as a real
        tab character which sqlldr accepts.
        """
        return delimiter

    # ------------------------------------------------------------------
    # sqlldr invocation
    # ------------------------------------------------------------------

    def _build_sqlldr_argv(
        self, control_file: str, data_file: str, log_file: str, bad_file: str
    ) -> List[str]:
        """Build the sqlldr argument vector (userid first; never logged)."""
        argv = [
            "sqlldr",
            self._build_userid(),
            f"control={control_file}",
            f"data={data_file}",
            f"log={log_file}",
            f"bad={bad_file}",
        ]
        if self.config.get("output", "OUTPUT_TO_CONSOLE") == "OUTPUT_TO_CONSOLE":
            argv.append("silent=(header)")
        for option in self.config.get("options", []) or []:
            argv.append(option)
        return argv

    def _build_userid(self) -> str:
        """Build the sqlldr ``user/password@dsn`` userid from connection params.

        T-11-02: the return value embeds the password and MUST NOT be logged.
        """
        user = self.config.get("user", "")
        password = self.config.get("password", "")
        dsn = self._build_dsn()
        return f"{user}/{password}@{dsn}" if dsn else f"{user}/{password}"

    def _build_dsn(self) -> str:
        """Build an Easy Connect dsn from connection_type / host / port / dbname."""
        ct = self.config.get("connection_type", "ORACLE_SID")
        if ct == "ORACLE_RAC":
            return (self.config.get("rac_url") or "").strip()
        host = self.config.get("host", "")
        port = self.config.get("port", "1521")
        dbname = self.config.get("dbname", "") or self.config.get(
            "local_service_name", ""
        )
        if not host:
            return ""
        return f"//{host}:{port}/{dbname}"

    def _build_nls_env(self) -> Dict[str, str]:
        """Return the subprocess environment with NLS_LANG when NLS is set."""
        env = dict(os.environ)
        language = self.config.get("nls_language", "DEFAULT")
        territory = self.config.get("nls_territory", "DEFAULT")
        charset = self.config.get("encoding", "UTF8")
        if language != "DEFAULT" or territory != "DEFAULT":
            lang = language if language != "DEFAULT" else "AMERICAN"
            terr = territory if territory != "DEFAULT" else "AMERICA"
            env["NLS_LANG"] = f"{lang}_{terr}.{charset}"
        return env

    # ------------------------------------------------------------------
    # Result handling
    # ------------------------------------------------------------------

    def _parse_log(self, log_file: str) -> tuple:
        """Parse rows-loaded / rows-not-loaded from the sqlldr log.

        Returns (loaded, rejected); 0/0 if the log is missing or unparseable.
        """
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            logger.warning("[%s] sqlldr log not readable; stats default to 0", self.id)
            return 0, 0
        loaded = self._first_int(_RE_LOADED, text)
        rejected = self._first_int(_RE_NOT_LOADED, text)
        return loaded, rejected

    @staticmethod
    def _first_int(pattern: re.Pattern, text: str) -> int:
        """Return the first integer matched by ``pattern`` in ``text`` (or 0)."""
        match = pattern.search(text)
        return int(match.group(1)) if match else 0

    def _publish_stats(
        self, loaded: int, rejected: int, input_data: Optional[pd.DataFrame]
    ) -> None:
        """Publish row-count stats to globalMap and the component stats dict."""
        total = len(input_data) if input_data is not None else loaded + rejected
        self._update_stats(rows_read=total, rows_ok=loaded, rows_reject=rejected)
        if self.global_map is not None:
            self.global_map.put(f"{self.id}_NB_LINE", total)
            self.global_map.put(f"{self.id}_NB_LINE_INSERTED", loaded)
            self.global_map.put(f"{self.id}_NB_LINE_REJECTED", rejected)
        logger.info(
            "[%s] sqlldr loaded=%d rejected=%d", self.id, loaded, rejected
        )

    def _handle_exit(self, return_code: int, stderr: str, rejected: int) -> None:
        """Raise on a fatal sqlldr exit, or when rows were rejected with die_on_error."""
        # sqlldr exit codes: 0 OK, 1 OK with warnings, 2 fatal/discontinued, 3 error.
        if return_code >= 2:
            raise FileOperationError(
                f"[{self.id}] sqlldr failed (exit {return_code}): "
                f"{(stderr or '').strip()[:500]}"
            )
        if rejected > 0 and self.config.get("die_on_error", False):
            raise ConfigurationError(
                f"[{self.id}] {rejected} row(s) rejected by sqlldr with "
                f"die_on_error=True"
            )

    # ------------------------------------------------------------------
    # Temp-file helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_tmp(suffix: str, tmp_paths: List[str]) -> str:
        """Create a tracked temp file path, returning it (closed, empty)."""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="bulkexec_")
        os.close(fd)
        tmp_paths.append(path)
        return path

    def _cleanup_tmp(self, tmp_paths: List[str]) -> None:
        """Remove tracked temp files, swallowing per-file errors."""
        for path in tmp_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:  # noqa: BLE001 -- cleanup must not mask original
                logger.warning("[%s] Could not remove temp file %s", self.id, path)
