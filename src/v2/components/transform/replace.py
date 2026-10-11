"""Replace: search and replace in the values of columns."""
from __future__ import annotations

import logging
import re
import warnings
from typing import Any, Dict, List, Optional

import polars as pl

from ...column_types import plain_text
from ...job.keys import Key, Kind, has_context_reference
from ...job.model import Column
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# What a pattern takes for more than itself.
_SPECIAL = re.compile(r"[\\.+*?()|\[\]{}^$#&\-~]")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "\\": "\\"}


def _literal(text: str, glob: bool) -> str:
    """Text as a pattern that finds exactly it; with ``glob``, `*` is any run of characters and `?` any one."""
    escaped = _SPECIAL.sub(lambda found: "\\" + found.group(0), text)
    return escaped.replace("\\*", ".*").replace("\\?", ".") if glob else escaped


def _template(written: str) -> str:
    """A replacement Python's ``re.sub`` takes, written the way Polars wants it."""
    made, at = [], 0
    while at < len(written):
        char = written[at]
        at += 1
        if char == "$":
            made.append("$$")
        elif char != "\\":
            made.append(char)
        else:
            after = written[at]
            at += 1
            if after == "g":
                named = re.match(r"<(\w+)>", written[at:])
                made.append("${" + named.group(1) + "}")
                at += named.end()
            elif after in "0123456789":
                # Python's own reading: \0 and three octal digits are a character, one or two digits a group.
                more = re.match(r"[0-7]{1,2}" if after == "0" else r"[0-9]", written[at:])
                digits = after + (more.group(0) if more else "")
                third = written[at + 1:at + 2] if len(digits) == 2 and after != "0" else ""
                if after == "0" or (after in "0123" and digits[1:] and digits[1] in "01234567" and third and third in "01234567"):
                    digits += third if after != "0" else ""
                    made.append(chr(int(digits, 8)).replace("$", "$$"))
                else:
                    made.append("${" + str(int(digits)) + "}")
                at += len(digits) - 1
            elif after in _ESCAPES:
                made.append(_ESCAPES[after])
            else:
                made.append("\\" + after)
    return "".join(made)


def _compiles(pattern: str, replacement: str) -> None:
    """Raise ValueError when Polars cannot work with a pattern and its replacement."""
    try:
        pl.Series([""]).str.replace_all(pattern, replacement)
    except Exception as exc:  # noqa: BLE001 -- Polars reports a bad pattern in its own kinds
        raise ValueError(f"v2 cannot use the pattern {pattern!r}: {' '.join(str(exc).split())[:200]}") from None


def _rules(value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for entry in value:
        written = entry.get("replace_string")
        if not isinstance(written, str):
            raise ValueError(f"replace_string: text is needed, and {written!r} is none")
        if not has_context_reference(written):
            # What is searched for is plain text, so the replacement has no group but the whole match.
            entry["replacement"] = _replacement("replace_string", written, "")
    return value


def _replacement(key: str, written: str, pattern: str) -> str:
    """A replacement in Polars' spelling. Raises ValueError where Python would not take it for the pattern."""
    try:
        re.compile(pattern).sub(written, "")
    except (re.error, IndexError) as exc:
        raise ValueError(f"{key} {written!r}: {exc}") from None
    return _template(written)


def _advanced(value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for entry in value:
        pattern, replace = entry.get("search_column"), entry.get("replace_column")
        if not isinstance(pattern, str) or not isinstance(replace, str):
            raise ValueError("search_column and replace_column: text is needed for both")
        if has_context_reference(pattern) or has_context_reference(replace):
            # Read once the context value is in: the run reads the config again.
            continue
        try:
            with warnings.catch_warnings():
                # As v1: a doubled backslash of the Talend job is one. An escape Python does not know stays.
                warnings.simplefilter("ignore")
                pattern = pattern.encode("utf-8").decode("unicode_escape")
        except (UnicodeDecodeError, ValueError):
            pass
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"search_column {pattern!r} is not a pattern: {exc}") from None
        entry["pattern"], entry["replacement"] = pattern, _replacement("replace_column", replace, pattern)
        try:
            _compiles(pattern, entry["replacement"])
        except ValueError as exc:
            raise ValueError(f"search_column: {exc}") from None
    return value


_RULE = (
    Key("input_column", required=True, doc="The column whose values are changed."),
    Key("search_pattern", required=True, doc="The text to find, taken as it is written."),
    Key("replace_string", required=True, doc="What it is replaced by; `\\1` or `\\g<1>` puts a group of the match back."),
    Key("whole_word", type=bool, default=False, doc="Whether it is only found as a whole word."),
    Key("case_sensitive", type=bool, default=False, doc="Whether upper and lower case differ."),
    Key("use_glob", type=bool, default=False, doc="Whether `*` stands for any run of characters and `?` for any one."),
    Key("comment", kind=Kind.IGNORED, type=object, doc="A note."),
)
_ADVANCED = (
    Key("input_column", required=True, doc="The column whose values are changed."),
    Key("search_column", required=True, doc="A regular expression, in spite of the name v1 gives it."),
    Key("replace_column", required=True, doc="What a match is replaced by, in spite of the name."),
    Key("comment", kind=Kind.IGNORED, type=object, doc="A note."),
)


@REGISTRY.register
class Replace(Transform):
    """Search and replace in the values of columns, rule after rule.

    In simple mode a rule finds text as it is written, whatever its case
    unless `case_sensitive`. With `strict_match` (the default) only a value
    that is the text and nothing else is replaced; without it, every
    occurrence inside a value. In advanced mode a rule is a regular
    expression and its replacement.

    A column that is not text is searched as the text it is written as,
    and the engine reads the result back as the declared type. A missing
    value stays missing. A rule for a column the input does not have is
    passed over, as in v1.

    Patterns run on Polars' regular expressions, which have no look-around
    and no back-reference inside a pattern: an advanced rule that needs one
    is refused at load.
    """

    names = ("replace", "Replace", "tReplace")
    keys = (
        Key("simple_mode", type=bool, default=True, doc="Whether `substitutions` are used; off, `advanced_subst` are."),
        Key("substitutions", type=list, default=[], items=_RULE, convert=_rules, doc="The rules of simple mode."),
        Key("strict_match", type=bool, default=True,
            doc="Simple mode: whether only a value that is the searched text and nothing else is replaced."),
        Key("advanced_subst", type=list, default=[], items=_ADVANCED, convert=_advanced, doc="The rules of advanced mode."),
        Key("advanced_mode", kind=Kind.IGNORED, type=object, doc="Never read by v1: `simple_mode` decides."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
    )

    def _pattern(self, rule: Dict[str, Any]) -> str:
        core = _literal(rule["search_pattern"], rule["use_glob"])
        if rule["whole_word"]:
            core = rf"\b{core}\b"
        if self.config["strict_match"]:
            core = rf"^{core}$"
        return core if rule["case_sensitive"] else "(?i)" + core

    def _searched(self, name: str, dtype: pl.DataType) -> pl.Expr:
        """A column as the text a rule searches.

        A date is its text by the pattern its column declares, so that the
        engine can read the result back by the same pattern. Without a
        pattern a day with no time of day is the day alone, as v1 has it.
        """
        declared: Optional[Column] = next(
            (column for column in list(self.schema) + list(self.input_schema)
             if column.name == name and column.date_pattern), None)
        return plain_text(pl.col(name), dtype, declared)

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        types = frame.collect_schema()
        simple = self.config["simple_mode"]
        rules = self.config["substitutions"] if simple else self.config["advanced_subst"]
        changed: Dict[str, pl.Expr] = {}
        for rule in rules:
            name = rule["input_column"]
            if name not in types:
                logger.warning(f"[{self.id}] there is no column '{name}'; its rule is passed over")
                continue
            value = changed.get(name)
            if value is None:
                value = self._searched(name, types[name])
            pattern = self._pattern(rule) if simple else rule["pattern"]
            changed[name] = value.str.replace_all(pattern, rule["replacement"])
        return {"main": frame.with_columns([value.alias(name) for name, value in changed.items()])}
