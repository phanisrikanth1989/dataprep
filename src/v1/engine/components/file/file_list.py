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

    def _validate_config(self) -> None:
        """Validate component configuration (structural checks only).

        Called before every execute() on unresolved config. Validates key
        presence and enum membership; does NOT check directory existence or
        mask validity (those are content checks belonging in prepare_iterations).

        Raises:
            ConfigurationError: If required keys are missing or enum values are invalid.
        """
        # DIRECTORY: required
        if "DIRECTORY" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'DIRECTORY'"
            )

        # LIST_MODE: must be in known set
        list_mode = self.config.get("LIST_MODE", "FILES")
        if list_mode not in _LIST_MODES:
            raise ConfigurationError(
                f"[{self.id}] Invalid LIST_MODE '{list_mode}'. "
                f"Must be one of: {sorted(_LIST_MODES)}"
            )

        # ORDER_BY: must be in known set
        order_by = self.config.get("ORDER_BY", "ORDER_BY_NOTHING")
        if order_by not in _ORDER_BY_VALUES:
            raise ConfigurationError(
                f"[{self.id}] Invalid ORDER_BY '{order_by}'. "
                f"Must be one of: {sorted(_ORDER_BY_VALUES)}"
            )

        # ORDER_ACTION: must be in known set
        order_action = self.config.get("ORDER_ACTION", "ORDER_ACTION_ASC")
        if order_action not in _ORDER_ACTIONS:
            raise ConfigurationError(
                f"[{self.id}] Invalid ORDER_ACTION '{order_action}'. "
                f"Must be one of: {sorted(_ORDER_ACTIONS)}"
            )

        # CASE_SENSITIVE: normalize; raises ConfigurationError if invalid
        case_sensitive_raw = self.config.get("CASE_SENSITIVE", "YES")
        FileList._normalize_case_sensitive(self.id, case_sensitive_raw)

        # FILES: must be a list; each entry must be a dict with FILEMASK key
        files_list = self.config.get("FILES", [])
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
        # -- Read config -------------------------------------------------
        directory_str: str = self.config["DIRECTORY"]
        files_cfg: List[Dict[str, Any]] = self.config.get("FILES", [])
        # GLOBEXPRESSIONS or USE_GLOB (alias used by some converter exports)
        use_glob_raw = self.config.get(
            "GLOBEXPRESSIONS", self.config.get("USE_GLOB", "false")
        )
        use_glob: bool = _truthy(use_glob_raw)
        case_sensitive_raw = self.config.get("CASE_SENSITIVE", "YES")
        case_sensitive: bool = FileList._normalize_case_sensitive(
            self.id, case_sensitive_raw
        )
        recursive: bool = _truthy(self.config.get("INCLUDSUBDIR", "false"))
        list_mode: str = self.config.get("LIST_MODE", "FILES")
        order_by: str = self.config.get("ORDER_BY", "ORDER_BY_NOTHING")
        order_action: str = self.config.get("ORDER_ACTION", "ORDER_ACTION_ASC")
        error_on_empty: bool = _truthy(self.config.get("ERROR", "false"))
        if_exclude: bool = _truthy(self.config.get("IFEXCLUDE", "false"))
        exclude_mask: str = self.config.get("EXCLUDEFILEMASK", "")
        fmt_slash: bool = _truthy(self.config.get("FORMAT_FILEPATH_TO_SLASH", "false"))

        # Extract FILEMASK strings from FILES list
        masks: List[str] = [
            entry["FILEMASK"]
            for entry in files_cfg
            if isinstance(entry, dict) and entry.get("FILEMASK")
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
            # Preserve OS-default (no sort); DESC reversal is a no-op for
            # unordered sequences, but apply it anyway for consistency.
            if reverse:
                paths = list(reversed(paths))
            return paths

        if order_by == "ORDER_BY_FILENAME":
            paths = sorted(paths, key=lambda p: p.name, reverse=reverse)
        elif order_by == "ORDER_BY_FILESIZE":
            paths = sorted(
                paths,
                key=lambda p: p.stat().st_size if p.exists() else 0,
                reverse=reverse,
            )
        elif order_by == "ORDER_BY_MODIFIEDDATE":
            paths = sorted(
                paths,
                key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
                reverse=reverse,
            )

        return paths

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
