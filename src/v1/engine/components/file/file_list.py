"""Engine component for FileList (tFileList).

Iterates over files (or directories) matching configured masks in a directory.
Implements all 16 tFileList _java.xml parameters and 5 RETURN globalMap variables
for Talend production parity.

Config keys consumed (16 total):
  DIRECTORY              (str, required)         -- directory to walk
  FILES                  (list[dict], default [])-- list of {"FILEMASK": pattern} entries (OR-wise)
  GLOBEXPRESSIONS        (str/bool, default "false") -- true=glob, false=regex matching
  CASE_SENSITIVE         (str/bool, default "YES") -- YES/NO/true/false/bool
  INCLUDSUBDIR           (str/bool, default "false") -- walk recursively (misspelling preserved)
  USE_GLOB               (str/bool, default "false") -- alias of GLOBEXPRESSIONS in some exports
  LIST_MODE              (str, default "FILES")   -- FILES / DIRECTORIES / BOTH
  ORDER_BY               (str, default "ORDER_BY_NOTHING") -- ORDER_BY_NOTHING / ORDER_BY_FILENAME /
                                                           ORDER_BY_FILESIZE / ORDER_BY_MODIFIEDDATE
  ORDER_ACTION           (str, default "ORDER_ACTION_ASC") -- ORDER_ACTION_ASC / ORDER_ACTION_DESC
  ERROR                  (str/bool, default "false") -- true raises on 0 matches (Talend parity)
  IFEXCLUDE              (str/bool, default "false") -- enable EXCLUDEFILEMASK
  EXCLUDEFILEMASK        (str, default "")        -- single exclusion pattern (TEXT not TABLE)
  FORMAT_FILEPATH_TO_SLASH (str/bool, default "false") -- replace backslashes with forward slashes
  die_on_error           (bool, default False)    -- framework: halt on component error
  tstatcatcher_stats     (bool, default False)    -- framework: stat collection
  component_type         (str, default "FileList") -- framework: component type identifier

GlobalMap variables (Talend parity, per Talaxie tFileList_java.xml):
    {id}_CURRENT_FILE          (str) - filename only (no path prefix)
    {id}_CURRENT_FILEPATH      (str) - absolute file path
    {id}_CURRENT_FILEDIRECTORY (str) - parent directory path
    {id}_CURRENT_FILEEXTENSION (str) - extension WITHOUT leading dot (e.g., "java" not ".java")
    {id}_NB_FILE               (int) - 1-based iteration counter; equals total at end

Statistics:
    NB_LINE         = matched file count (set by finalize())
    NB_LINE_OK      = matched file count
    NB_LINE_REJECT  = 0 (tFileList has no REJECT flow)
    NB_FILE         = matched file count (Talend convention alias for NB_LINE)

Parity notes:
    CURRENT_FILEEXTENSION: extracted via path.suffix.lstrip('.') so "report.java" -> "java".
    This matches Java File.getName / lastIndexOf('.') convention (confirmed in Phase 10 research).
    FILES masks: OR-wise. EXCLUDEFILEMASK: single TEXT pattern (not a TABLE), applied AFTER inclusion.
    ERROR=true with 0 matches: raises ComponentExecutionError matching Talend RuntimeException message.
    ORDER_BY_NOTHING: preserves OS-default order (non-deterministic, Talend parity).
"""
import fnmatch
import logging
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

from ...base_iterate_component import BaseIterateComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Module-level constants
# ------------------------------------------------------------------

_LIST_MODES = frozenset({"FILES", "DIRECTORIES", "BOTH"})
_ORDER_BY_VALUES = frozenset({
    "ORDER_BY_NOTHING",
    "ORDER_BY_FILENAME",
    "ORDER_BY_FILESIZE",
    "ORDER_BY_MODIFIEDDATE",
})
_ORDER_ACTIONS = frozenset({"ORDER_ACTION_ASC", "ORDER_ACTION_DESC"})

# NOTE: do NOT use a frozenset mixing bool and string for CASE_SENSITIVE because
# Python evaluates True == 1 and False == 0, which causes false positives
# (e.g., 1 in {True, "yes", ...} -> True). _normalize_case_sensitive uses
# explicit isinstance checks instead.
_CASE_SENSITIVE_TRUE_STRINGS = frozenset({"YES", "yes", "true", "True"})
_CASE_SENSITIVE_FALSE_STRINGS = frozenset({"NO", "no", "false", "False"})


# ------------------------------------------------------------------
# Typed iteration item (D-A4)
# ------------------------------------------------------------------

@dataclass
class FileListItem:
    """Typed item produced by FileList per iteration (D-A4).

    All path-string attributes have FORMAT_FILEPATH_TO_SLASH already applied
    (if configured), so set_iteration_globalmap can write them directly.
    """

    path: pathlib.Path   # full absolute path
    name: str            # filename only (path.name)
    parent: pathlib.Path # parent directory (path.parent)
    ext: str             # extension without leading dot (path.suffix.lstrip('.'))
    index: int           # 1-based iteration counter


# ------------------------------------------------------------------
# Component
# ------------------------------------------------------------------

@REGISTRY.register("FileList", "tFileList")
class FileList(BaseIterateComponent):
    """tFileList engine component (Phase 10).

    Iterates files in a directory matching configured masks. Per Talaxie
    tFileList_java.xml: 16 params, 5 RETURN globalMap vars.

    Config keys: see module docstring.
    """

    # ------------------------------------------------------------------
    # Configuration Validation (structural only, D-L4 / Phase 7.1 Rule 12)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Config key helpers (converter produces lowercase; accept both)
    # ------------------------------------------------------------------

    def _cfg(self, key_upper: str, key_lower: str, default: Any = None) -> Any:
        """Read a config value by uppercase key with lowercase fallback.

        The talend_to_v1 converter produces lowercase snake_case config keys
        (e.g. 'directory', 'list_mode') while the original engine contract used
        uppercase Talend-style keys (e.g. 'DIRECTORY', 'LIST_MODE'). This helper
        checks the uppercase key first (backward compat), then falls back to the
        lowercase key, then to default.

        Args:
            key_upper: Uppercase Talend-style key (e.g. 'DIRECTORY').
            key_lower: Lowercase converter-output key (e.g. 'directory').
            default: Default value if neither key is present.

        Returns:
            Config value or default.
        """
        if key_upper in self.config:
            return self.config[key_upper]
        if key_lower in self.config:
            return self.config[key_lower]
        return default

    def _validate_config(self) -> None:
        """Validate component configuration (structural checks only).

        Called before every execute() on unresolved config. Validates key
        presence and enum membership; does NOT check directory existence or
        mask validity (those are content checks belonging in prepare_iterations).

        Accepts both uppercase Talend-style keys (e.g. 'DIRECTORY') and lowercase
        converter-output keys (e.g. 'directory').

        Raises:
            ConfigurationError: If required keys are missing or enum values are invalid.
        """
        # DIRECTORY: required (accepts both 'DIRECTORY' and lowercase 'directory')
        if "DIRECTORY" not in self.config and "directory" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'DIRECTORY'"
            )

        # LIST_MODE: must be in known set
        list_mode = self._cfg("LIST_MODE", "list_mode", "FILES")
        if list_mode not in _LIST_MODES:
            raise ConfigurationError(
                f"[{self.id}] Invalid LIST_MODE '{list_mode}'. "
                f"Must be one of: {sorted(_LIST_MODES)}"
            )

        # ORDER_BY: optional explicit key; RADIO flags are validated by presence only
        order_by = self._cfg("ORDER_BY", "order_by", None)
        if order_by is not None and order_by not in _ORDER_BY_VALUES:
            raise ConfigurationError(
                f"[{self.id}] Invalid ORDER_BY '{order_by}'. "
                f"Must be one of: {sorted(_ORDER_BY_VALUES)}"
            )

        # ORDER_ACTION: optional explicit key
        order_action = self._cfg("ORDER_ACTION", "order_action", None)
        if order_action is not None and order_action not in _ORDER_ACTIONS:
            raise ConfigurationError(
                f"[{self.id}] Invalid ORDER_ACTION '{order_action}'. "
                f"Must be one of: {sorted(_ORDER_ACTIONS)}"
            )

        # CASE_SENSITIVE: normalize; raises ConfigurationError if invalid
        case_sensitive_raw = self._cfg("CASE_SENSITIVE", "case_sensitive", "YES")
        FileList._normalize_case_sensitive(self.id, case_sensitive_raw)

        # FILES: must be a list; each entry must be a dict (FILEMASK or filemask key)
        files_list = self._cfg("FILES", "files", [])
        if not isinstance(files_list, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'FILES' must be a list, "
                f"got {type(files_list).__name__}"
            )
        for i, entry in enumerate(files_list):
            if not isinstance(entry, dict):
                raise ConfigurationError(
                    f"[{self.id}] Config 'FILES[{i}]' must be a dict with 'FILEMASK' key, "
                    f"got {type(entry).__name__}"
                )

    # ------------------------------------------------------------------
    # Iterate Lifecycle (abstract implementations)
    # ------------------------------------------------------------------

    def prepare_iterations(
        self, input_data: Optional[pd.DataFrame] = None
    ) -> Iterator[FileListItem]:
        """Walk directory and yield FileListItem per matched path.

        Reads all 16 config keys (post-resolution), walks the directory with
        pathlib, applies LIST_MODE filter, glob/regex inclusion masks, exclusion
        mask, sorting, and yields FileListItem instances.

        Raises:
            ComponentExecutionError: If ERROR=true and 0 files match.
        """
        # -- Read config (accepts both uppercase Talend keys and lowercase converter keys) --
        directory_str: str = self._cfg("DIRECTORY", "directory", "")
        files_cfg: List[Dict[str, Any]] = self._cfg("FILES", "files", [])
        # GLOBEXPRESSIONS or USE_GLOB (alias) or glob_expressions (converter output)
        use_glob_raw = self._cfg(
            "GLOBEXPRESSIONS",
            "glob_expressions",
            self.config.get("USE_GLOB", "false"),
        )
        use_glob: bool = _truthy(use_glob_raw)
        case_sensitive_raw = self._cfg("CASE_SENSITIVE", "case_sensitive", "YES")
        case_sensitive: bool = FileList._normalize_case_sensitive(
            self.id, case_sensitive_raw
        )
        recursive: bool = _truthy(self._cfg("INCLUDSUBDIR", "include_subdirs", "false"))
        list_mode: str = self._cfg("LIST_MODE", "list_mode", "FILES")

        # ORDER_BY: either explicit ORDER_BY key or derived from ORDER_BY_* RADIO flags
        order_by_direct = self._cfg("ORDER_BY", "order_by", None)
        if order_by_direct is not None:
            order_by = order_by_direct
        elif _truthy(self._cfg("ORDER_BY_FILENAME", "order_by_filename", False)):
            order_by = "ORDER_BY_FILENAME"
        elif _truthy(self._cfg("ORDER_BY_FILESIZE", "order_by_filesize", False)):
            order_by = "ORDER_BY_FILESIZE"
        elif _truthy(self._cfg("ORDER_BY_MODIFIEDDATE", "order_by_modifieddate", False)):
            order_by = "ORDER_BY_MODIFIEDDATE"
        else:
            order_by = "ORDER_BY_NOTHING"

        # ORDER_ACTION: either explicit ORDER_ACTION key or derived from RADIO flags
        order_action_direct = self._cfg("ORDER_ACTION", "order_action", None)
        if order_action_direct is not None:
            order_action = order_action_direct
        elif _truthy(self._cfg("ORDER_ACTION_DESC", "order_action_desc", False)):
            order_action = "ORDER_ACTION_DESC"
        else:
            order_action = "ORDER_ACTION_ASC"

        error_on_empty: bool = _truthy(self._cfg("ERROR", "error", "false"))
        if_exclude: bool = _truthy(self._cfg("IFEXCLUDE", "exclude_file", "false"))
        exclude_mask: str = self._cfg("EXCLUDEFILEMASK", "exclude_filemask", "")
        fmt_slash: bool = _truthy(
            self._cfg("FORMAT_FILEPATH_TO_SLASH", "format_filepath_to_slash", "false")
        )

        # Extract FILEMASK strings from FILES list -- accept both 'FILEMASK' and 'filemask' keys
        masks: List[str] = [
            entry.get("FILEMASK") or entry.get("filemask", "")
            for entry in files_cfg
            if isinstance(entry, dict) and (entry.get("FILEMASK") or entry.get("filemask"))
        ]

        directory = pathlib.Path(directory_str)

        logger.info(
            "[%s] tFileList walking %s (mode=%s, recursive=%s)",
            self.id, directory, list_mode, recursive,
        )

        # -- Walk directory ----------------------------------------------
        # On missing directory with ERROR=false: treat as 0-match (no iterations).
        # On missing directory with ERROR=true: the 0-match path below handles it
        # (no entries produced when directory missing, matched = [], ERROR=true -> raise).
        if not directory.exists():
            raw_paths: List[pathlib.Path] = []
        elif recursive:
            raw_paths = list(directory.rglob("*"))
        else:
            raw_paths = list(directory.iterdir())

        # -- Apply LIST_MODE filter -------------------------------------
        if list_mode == "FILES":
            raw_paths = [p for p in raw_paths if p.is_file()]
        elif list_mode == "DIRECTORIES":
            raw_paths = [p for p in raw_paths if p.is_dir()]
        # else BOTH: no filter

        # -- Apply inclusion masks (OR-wise) ----------------------------
        if masks:
            raw_paths = [
                p for p in raw_paths
                if FileList._match_path(p.name, masks, use_glob, case_sensitive)
            ]

        # -- Apply exclusion mask (after inclusion, same mode + sensitivity)
        if if_exclude and exclude_mask:
            raw_paths = [
                p for p in raw_paths
                if not FileList._match_path(
                    p.name, [exclude_mask], use_glob, case_sensitive
                )
            ]

        # -- Sort -------------------------------------------------------
        raw_paths = FileList._sort_paths(raw_paths, order_by, order_action)

        # -- 0-match handling (D-G8 / D-E4) ----------------------------
        if len(raw_paths) == 0:
            if error_on_empty:
                raise ComponentExecutionError(
                    self.id,
                    f"No file found in directory: {directory}",
                )
            else:
                logger.warning(
                    "[%s] tFileList: no files matched in %s; ERROR=false, no iterations",
                    self.id, directory,
                )
                self.total_iterations = 0
                self.stats["NB_FILE"] = 0
                return iter([])

        # -- Set total and yield items ----------------------------------
        self.total_iterations = len(raw_paths)

        def _item_iter() -> Iterator[FileListItem]:
            for idx, p in enumerate(raw_paths, start=1):
                abs_path = p.resolve()
                # Apply FORMAT_FILEPATH_TO_SLASH before yielding (D-G10)
                abs_path = FileList._apply_format_filepath_to_slash(abs_path, fmt_slash)
                parent = abs_path.parent
                parent = FileList._apply_format_filepath_to_slash(parent, fmt_slash)
                yield FileListItem(
                    path=abs_path,
                    name=abs_path.name,
                    parent=parent,
                    ext=abs_path.suffix.lstrip("."),
                    index=idx,
                )

        return _item_iter()

    def set_iteration_globalmap(self, item: FileListItem) -> None:  # type: ignore[override]
        """Set the 5 Talend-parity RETURN globalMap variables for one file.

        Args:
            item: FileListItem produced by prepare_iterations().
        """
        if self.global_map is None:
            return
        path_str = str(item.path)
        parent_str = str(item.parent)
        # FORMAT_FILEPATH_TO_SLASH already applied in prepare_iterations
        self.global_map.put(f"{self.id}_CURRENT_FILE", item.name)
        self.global_map.put(f"{self.id}_CURRENT_FILEPATH", path_str)
        self.global_map.put(f"{self.id}_CURRENT_FILEDIRECTORY", parent_str)
        self.global_map.put(f"{self.id}_CURRENT_FILEEXTENSION", item.ext)
        self.global_map.put(f"{self.id}_NB_FILE", item.index)

    def get_iter_key_info(self, item: "FileListItem", index: int) -> str:
        """Return component-specific key info for per-iteration log lines (D-H3).

        Args:
            item: FileListItem for the current iteration.
            index: 1-based iteration index.

        Returns:
            "file=<absolute path>" string for use in iteration log lines.
        """
        return f"file={item.path}"

    def finalize(self) -> None:
        """Set final statistics after all iterations complete.

        NB_FILE = total matched files. NB_LINE / NB_LINE_OK mirror NB_FILE.
        NB_LINE_REJECT = 0 (tFileList has no REJECT flow).
        """
        total = self.total_iterations if self.total_iterations >= 0 else 0
        self.stats["NB_LINE"] = total
        self.stats["NB_LINE_OK"] = total
        self.stats["NB_LINE_REJECT"] = 0
        self.stats["NB_FILE"] = total  # Talend alias (D-D1)

    # ------------------------------------------------------------------
    # Static Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_case_sensitive(component_id: str, value: Any) -> bool:
        """Normalize CASE_SENSITIVE config value to bool.

        Accepts Talaxie strings ("YES"/"NO"), boolean-like strings
        ("true"/"false"), and Python booleans.

        Args:
            component_id: Component ID for error messages.
            value: Raw config value.

        Returns:
            True if case-sensitive matching, False otherwise.

        Raises:
            ConfigurationError: If value cannot be normalized.
        """
        # bool first -- Python's True == 1 / False == 0 means a frozenset
        # containing both bool and string would alias ints; explicit isinstance
        # prevents the collision.
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value in _CASE_SENSITIVE_TRUE_STRINGS:
                return True
            if value in _CASE_SENSITIVE_FALSE_STRINGS:
                return False
        raise ConfigurationError(
            f"[{component_id}] Invalid CASE_SENSITIVE: {value!r}. "
            f"Must be one of: YES, NO, true, false or a Python bool."
        )

    @staticmethod
    def _compile_mask(
        mask: str, use_glob: bool, case_sensitive: bool
    ) -> "re.Pattern[str]":
        """Compile a single mask pattern into a regex.

        Args:
            mask: Glob or regex pattern string.
            use_glob: True = translate via fnmatch, False = use directly.
            case_sensitive: True = no IGNORECASE flag.

        Returns:
            Compiled regex pattern.
        """
        if use_glob:
            pattern = fnmatch.translate(mask)
        else:
            pattern = mask  # regex used directly (D-G5: fullmatch parity with Java)
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.compile(pattern, flags)

    @staticmethod
    def _match_path(
        path_name: str,
        masks: List[str],
        use_glob: bool,
        case_sensitive: bool,
    ) -> bool:
        """Check if a filename matches any of the given masks (OR-wise).

        Uses re.fullmatch to match the filename. This mirrors Java's
        Pattern.matcher(s).matches() semantics (D-G4, D-G5).

        Args:
            path_name: Filename only (no directory prefix).
            masks: List of glob or regex pattern strings.
            use_glob: True = fnmatch.translate(mask) for each mask.
            case_sensitive: True = exact case; False = IGNORECASE.

        Returns:
            True if any mask matches (OR-wise).
        """
        for mask in masks:
            compiled = FileList._compile_mask(mask, use_glob, case_sensitive)
            if compiled.fullmatch(path_name):
                return True
        return False

    @staticmethod
    def _sort_paths(
        paths: List[pathlib.Path],
        order_by: str,
        order_action: str,
    ) -> List[pathlib.Path]:
        """Sort paths per ORDER_BY and ORDER_ACTION config.

        ORDER_BY_NOTHING: preserves OS-default order (non-deterministic --
        Talend parity, accept as the parity choice per D-G6).
        ORDER_BY_FILENAME: stable sort by path.name.
        ORDER_BY_FILESIZE: stable sort by path.stat().st_size.
        ORDER_BY_MODIFIEDDATE: stable sort by path.stat().st_mtime.
        ORDER_ACTION_DESC: reverses any sort.

        Args:
            paths: List of paths to sort (mutated in-place for efficiency,
                then returned).
            order_by: Sort key enum string.
            order_action: Direction enum string.

        Returns:
            Sorted list of paths.
        """
        reverse = (order_action == "ORDER_ACTION_DESC")

        if order_by == "ORDER_BY_NOTHING":
            # Preserve OS-default (non-deterministic). Talend does NOT reverse
            # on ORDER_BY_NOTHING+DESC; reversing a non-deterministic sequence
            # is meaningless and only adds an O(n) allocation. Skip it. (WR-04)
            return paths

        if order_by == "ORDER_BY_FILENAME":
            paths = sorted(paths, key=lambda p: p.name, reverse=reverse)
        elif order_by == "ORDER_BY_FILESIZE":
            paths = sorted(
                paths,
                key=FileList._safe_stat_size,
                reverse=reverse,
            )
        elif order_by == "ORDER_BY_MODIFIEDDATE":
            paths = sorted(
                paths,
                key=FileList._safe_stat_mtime,
                reverse=reverse,
            )

        return paths

    @staticmethod
    def _safe_stat_size(p: pathlib.Path) -> int:
        """Return file size in bytes, or 0 if the file is unavailable.

        Uses try/except OSError to handle files deleted between directory walk
        and sort (TOCTOU race). Returns 0 as a sort-stable default on error.
        Logs a WARNING (ASCII-only) to aid debugging of busy-directory races.
        """
        try:
            return p.stat().st_size
        except OSError:
            logger.warning("[FileList] File unavailable during FILESIZE sort (skipping): %s", p)
            return 0

    @staticmethod
    def _safe_stat_mtime(p: pathlib.Path) -> float:
        """Return file modification time as float, or 0.0 if the file is unavailable.

        Uses try/except OSError to handle files deleted between directory walk
        and sort (TOCTOU race). Returns 0.0 as a sort-stable default on error.
        Logs a WARNING (ASCII-only) to aid debugging of busy-directory races.
        """
        try:
            return p.stat().st_mtime
        except OSError:
            logger.warning("[FileList] File unavailable during MODIFIEDDATE sort (skipping): %s", p)
            return 0.0

    @staticmethod
    def _apply_format_filepath_to_slash(
        path: pathlib.Path, enabled: bool
    ) -> pathlib.Path:
        """Replace backslashes with forward slashes in path when enabled.

        On POSIX systems pathlib never produces backslashes, so this is a
        no-op unless the path was constructed from a Windows-style string.
        On Windows this normalises the separators.

        Args:
            path: Path object to normalise.
            enabled: If False, return path unchanged.

        Returns:
            Path with backslashes replaced by forward slashes (if enabled).
        """
        if not enabled:
            return path
        normalised = str(path).replace("\\", "/")
        return pathlib.Path(normalised)


# ------------------------------------------------------------------
# Module-level helpers (private)
# ------------------------------------------------------------------

def _truthy(value: Any) -> bool:
    """Normalise bool-like config values to Python bool.

    Accepts bool, "true"/"false", "yes"/"no" strings (case-insensitive),
    and numeric values. Returns False for empty string and None.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False
