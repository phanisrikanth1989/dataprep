"""Engine component for Replace (tReplace).

Performs search-and-replace operations on column values.  Two modes
are supported: simple (substitution list) and advanced (per-row lookup
columns).

Config keys consumed (7 total):
    simple_mode    (bool, default True)    -- use substitutions list; False = advanced_subst
    substitutions  (list[dict], default []) -- simple-mode rules:
                     [{input_column, search_pattern, replace_string,
                       whole_word, case_sensitive, use_glob, comment}]
    strict_match   (bool, default True)    -- True = replace only when entire value matches;
                                             False = replace all occurrences (substring)
    advanced_mode  (bool, default False)   -- ignored when simple_mode=True
    advanced_subst (list[dict], default []) -- advanced-mode rules:
                     [{input_column, search_column, replace_column, comment}]
    tstatcatcher_stats (bool, default False) -- framework
    label              (str, default "")   -- framework
"""
import logging
import re
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _glob_to_regex(pattern: str) -> str:
    """Convert a glob pattern to a regex pattern string.

    Escapes all regex metacharacters first, then restores glob wildcards:
    ``*`` -> ``.*``  and  ``?`` -> ``.``

    Args:
        pattern: Glob-style pattern (e.g. ``foo*bar``).

    Returns:
        Equivalent regex pattern string.
    """
    escaped = re.escape(pattern)
    # re.escape turns * -> \\* and ? -> \\? -- restore as regex wildcards
    escaped = escaped.replace(r"\*", ".*").replace(r"\?", ".")
    return escaped


def _build_regex(
    search_pattern: str,
    whole_word: bool,
    case_sensitive: bool,
    use_glob: bool,
    strict_match: bool,
) -> re.Pattern:
    """Compile a regex from tReplace substitution parameters.

    Args:
        search_pattern: Literal string or glob pattern to search for.
        whole_word: Wrap pattern in word-boundary anchors ``\\b``.
        case_sensitive: Whether matching is case-sensitive.
        use_glob: Treat search_pattern as a glob (``*`` / ``?`` wildcards).
        strict_match: Anchor pattern to full string (``^...$``).

    Returns:
        Compiled ``re.Pattern`` object.

    Raises:
        ConfigurationError: If the resulting pattern is an invalid regex.
    """
    core = _glob_to_regex(search_pattern) if use_glob else re.escape(search_pattern)
    if whole_word:
        core = rf"\b{core}\b"
    if strict_match:
        core = rf"^{core}$"
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(core, flags)
    except re.error as exc:
        raise ConfigurationError(
            f"Invalid search pattern {search_pattern!r} (compiled regex: {core!r}): {exc}"
        ) from exc


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------

_REQUIRED_SUBST_KEYS = {"input_column", "search_pattern", "replace_string"}
_REQUIRED_ADV_KEYS = {"input_column", "search_column", "replace_column"}


def _validate_substitution_row(row: object, idx: int, component_id: str) -> None:
    """Raise ConfigurationError if a substitution dict is missing required keys.

    Args:
        row: Object expected to be a dict.
        idx: Zero-based row index (for error messages).
        component_id: Component ID for error prefix.

    Raises:
        ConfigurationError: On type mismatch or missing required key.
    """
    if not isinstance(row, dict):
        raise ConfigurationError(
            f"[{component_id}] substitutions[{idx}] must be a dict, "
            f"got {type(row).__name__}"
        )
    for key in _REQUIRED_SUBST_KEYS:
        if key not in row:
            raise ConfigurationError(
                f"[{component_id}] substitutions[{idx}] missing required key '{key}'"
            )


def _validate_adv_subst_row(row: object, idx: int, component_id: str) -> None:
    """Raise ConfigurationError if an advanced_subst dict is missing required keys.

    Args:
        row: Object expected to be a dict.
        idx: Zero-based row index (for error messages).
        component_id: Component ID for error prefix.

    Raises:
        ConfigurationError: On type mismatch or missing required key.
    """
    if not isinstance(row, dict):
        raise ConfigurationError(
            f"[{component_id}] advanced_subst[{idx}] must be a dict, "
            f"got {type(row).__name__}"
        )
    for key in _REQUIRED_ADV_KEYS:
        if key not in row:
            raise ConfigurationError(
                f"[{component_id}] advanced_subst[{idx}] missing required key '{key}'"
            )


@REGISTRY.register("Replace", "tReplace")
class Replace(BaseComponent):
    """tReplace engine implementation.

    Performs search-and-replace operations on specified column values.

    **Simple mode** (``simple_mode=True``): iterates a ``substitutions``
    list; each rule defines the column, pattern, replacement, and match
    options (whole-word, case, glob).  ``strict_match=True`` replaces
    only cells whose entire value equals the pattern; ``strict_match=False``
    replaces all in-string occurrences.

    **Advanced mode** (``simple_mode=False``): iterates ``advanced_subst``;
    for each row the search and replacement strings are taken from sibling
    columns in that row.

    Config keys:
        simple_mode: Toggle between simple (True) and advanced (False) mode.
        substitutions: Simple-mode substitution rules.
        strict_match: Strict full-value match vs. substring match (simple mode).
        advanced_mode: Mirrors simple_mode=False; both flags are respected.
        advanced_subst: Advanced-mode substitution rules.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Called before every execute(). ``self.config`` contains a fresh
        deepcopy (context variables NOT yet resolved). Validates structural
        correctness: key types and required sub-keys in list items.

        Raises:
            ConfigurationError: If any required key or sub-key is missing
                or has the wrong type.
        """
        simple_mode = self.config.get("simple_mode", True)
        if not isinstance(simple_mode, bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'simple_mode' must be a bool, "
                f"got {type(simple_mode).__name__}"
            )

        if simple_mode:
            substitutions = self.config.get("substitutions", [])
            if not isinstance(substitutions, list):
                raise ConfigurationError(
                    f"[{self.id}] Config 'substitutions' must be a list, "
                    f"got {type(substitutions).__name__}"
                )
            for idx, row in enumerate(substitutions):
                _validate_substitution_row(row, idx, self.id)
        else:
            advanced_subst = self.config.get("advanced_subst", [])
            if not isinstance(advanced_subst, list):
                raise ConfigurationError(
                    f"[{self.id}] Config 'advanced_subst' must be a list, "
                    f"got {type(advanced_subst).__name__}"
                )
            for idx, row in enumerate(advanced_subst):
                _validate_adv_subst_row(row, idx, self.id)

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Apply search-and-replace rules to input data.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with keys:
                - ``main``: transformed DataFrame (or empty DataFrame)
                - ``reject``: ``None`` (tReplace does not filter rows)
        """
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty or None input received")
            return {"main": pd.DataFrame(), "reject": None}

        simple_mode = self.config.get("simple_mode", True)
        df = input_data.copy()

        if simple_mode:
            df = self._apply_simple_mode(df)
        else:
            df = self._apply_advanced_mode(df)

        logger.info(f"[{self.id}] Processed {len(df)} rows")
        return {"main": df, "reject": None}

    # ------------------------------------------------------------------
    # Simple mode
    # ------------------------------------------------------------------

    def _apply_simple_mode(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply substitutions list to the DataFrame.

        Args:
            df: Input DataFrame (already a copy).

        Returns:
            DataFrame with replacements applied.
        """
        substitutions = self.config.get("substitutions", [])
        strict_match = self.config.get("strict_match", True)

        for rule in substitutions:
            col = rule["input_column"]
            if col not in df.columns:
                logger.warning(
                    f"[{self.id}] Column '{col}' not found in input; skipping substitution"
                )
                continue

            pattern = _build_regex(
                search_pattern=rule.get("search_pattern", ""),
                whole_word=rule.get("whole_word", False),
                case_sensitive=rule.get("case_sensitive", False),
                use_glob=rule.get("use_glob", False),
                strict_match=strict_match,
            )
            replace_str = rule.get("replace_string", "")

            logger.debug(
                f"[{self.id}] Applying rule on '{col}': "
                f"pattern={pattern.pattern!r} -> replace={replace_str!r}"
            )
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(pattern, replace_str, regex=True)
            )

        return df

    # ------------------------------------------------------------------
    # Advanced mode
    # ------------------------------------------------------------------

    def _apply_advanced_mode(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply advanced_subst rules (per-row column lookup) to the DataFrame.

        For each rule, replaces occurrences of the value in ``search_column``
        within ``input_column`` with the value from ``replace_column``,
        evaluated per row.  Talend parity: uses literal string replacement
        (no regex), case-sensitive.

        Args:
            df: Input DataFrame (already a copy).

        Returns:
            DataFrame with replacements applied.
        """
        advanced_subst = self.config.get("advanced_subst", [])

        for rule in advanced_subst:
            input_col = rule["input_column"]
            search_col = rule["search_column"]
            replace_col = rule["replace_column"]

            missing = [c for c in (input_col, search_col, replace_col) if c not in df.columns]
            if missing:
                logger.warning(
                    f"[{self.id}] Advanced subst: column(s) {missing} not found; skipping rule"
                )
                continue

            logger.debug(
                f"[{self.id}] Advanced subst: replace in '{input_col}' "
                f"using search='{search_col}', replace='{replace_col}'"
            )
            # Per-row literal replacement -- Talend does not apply regex here
            df[input_col] = df.apply(
                lambda row: str(row[input_col]).replace(
                    str(row[search_col]), str(row[replace_col])
                ),
                axis=1,
            )

        return df
