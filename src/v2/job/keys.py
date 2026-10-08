"""Config-key declarations.

Every component declares the config keys it knows, and one function checks a
raw config dict against that declaration: v1 spellings become v2 names,
omitted keys take their defaults, values are checked, and everything v2 will
not run with is collected as refusals instead of being silently ignored.
"""
from __future__ import annotations

import copy
import difflib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .refusal import Refusal

# Value types beyond plain Python types. An expression or a block of code is
# text that is never searched for context references here: its own reader
# understands them.
EXPRESSION = "expression"
CODE = "code"

_TEXT_TYPES = (str, EXPRESSION, CODE)
_BASE_OFF: Tuple[Any, ...] = (None, False, "", 0, [], {})
_CONTEXT_REF = re.compile(r"\$\{context\.\w+\}|(?<![\w.])context\.\w+|(?<![\w.])globalMap\b")


class Kind(str, Enum):
    """What v2 does with a config key."""

    SUPPORTED = "supported"
    IGNORED = "ignored"
    REFUSED = "refused"


@dataclass(frozen=True)
class Key:
    """One declared config key.

    Attributes:
        name: v2's spelling, the documented one.
        kind: Supported, ignored (accepted, no effect) or refused.
        type: ``str``, ``int``, ``float``, ``bool``, ``list``, ``dict``,
            ``EXPRESSION``, ``CODE``, or ``object`` for anything.
        default: The value an omitted key takes.
        required: Whether leaving the key out is refused.
        aliases: v1 spellings accepted in place of ``name``.
        choices: The allowed values, when the key is an enumeration.
        reason: For a refused key, why. Shown in the refusal report.
        doc: One line saying what the key does, for the generated doc page.
        convert: Called with the checked value; returns the value the
            component sees. Raising ``ValueError`` refuses the value.
        nullable: Whether an explicit null is a value in its own right.
        off: For a refused key, values that mean "not used" and are accepted,
            in addition to null, false, zero and empty.
        items: Declared keys of each object in a list value.
        fields: Declared keys of an object value.
        item_convert: Called with each list item before it is checked, so a
            shorthand form can be expanded.
    """

    name: str
    kind: Kind = Kind.SUPPORTED
    type: Any = str
    default: Any = None
    required: bool = False
    aliases: Tuple[str, ...] = ()
    choices: Optional[Tuple[Any, ...]] = None
    reason: str = ""
    doc: str = ""
    convert: Optional[Callable[[Any], Any]] = None
    nullable: bool = False
    off: Tuple[Any, ...] = ()
    items: Optional[Tuple["Key", ...]] = None
    fields: Optional[Tuple["Key", ...]] = None
    item_convert: Optional[Callable[[Any], Any]] = None

    @property
    def spellings(self) -> Tuple[str, ...]:
        """Every spelling a job config may use for this key."""
        return (self.name,) + tuple(self.aliases)


def has_context_reference(value: Any) -> bool:
    """Whether a config value names a context or globalMap entry."""
    return isinstance(value, str) and bool(_CONTEXT_REF.search(value))


def normalize_config(
    raw: Optional[Dict[str, Any]],
    keys: Sequence[Key],
    where: str,
    resolve: Optional[Callable[[str], Any]] = None,
    _prefix: str = "",
) -> Tuple[Dict[str, Any], List[Refusal]]:
    """Check a raw config dict against declared keys.

    Args:
        raw: The config as written in the job config.
        keys: The declaration to check it against.
        where: The owner of the config, for refusal messages.
        resolve: Turns a string holding context references into its value.
            Without it such strings are passed through unchecked, which is
            what a load-time check wants; with it they are resolved and then
            checked like any other value.

    Returns:
        The config under v2 names, with defaults filled in, and the refusals.
    """
    raw = raw or {}
    refusals: List[Refusal] = []
    config: Dict[str, Any] = {}

    by_spelling: Dict[str, Key] = {}
    for key in keys:
        for spelling in key.spellings:
            by_spelling[spelling] = key

    written: Dict[str, List[str]] = {}
    for raw_name in raw:
        key = by_spelling.get(raw_name)
        if key is None:
            refusals.append(Refusal(where, _prefix + raw_name, _unknown_reason(raw_name, by_spelling)))
            continue
        written.setdefault(key.name, []).append(raw_name)

    for key in keys:
        names = written.get(key.name, [])
        if len(names) > 1:
            kept = key.name if key.name in names else names[0]
            for extra in names:
                if extra != kept:
                    refusals.append(
                        Refusal(where, _prefix + extra, f"also given as '{kept}'; use one spelling")
                    )
            names = [kept]

        if not names:
            if key.kind is not Kind.SUPPORTED:
                continue
            if key.required:
                refusals.append(Refusal(where, _prefix + key.name, "required config key is missing"))
                config[key.name] = None
            else:
                config[key.name] = copy.deepcopy(key.default)
            continue

        raw_name = names[0]
        path = _prefix + raw_name
        value = raw[raw_name]

        if key.kind is Kind.IGNORED:
            continue
        if key.kind is Kind.REFUSED:
            if not _is_off(value, key.off):
                refusals.append(Refusal(where, path, key.reason or "not supported in v2"))
            continue

        config[key.name] = _check_value(key, value, where, path, resolve, refusals)

    return config, refusals


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _unknown_reason(raw_name: str, by_spelling: Dict[str, Key]) -> str:
    close = difflib.get_close_matches(raw_name, list(by_spelling), n=1, cutoff=0.75)
    if close:
        return f"unknown config key; did you mean '{close[0]}'?"
    return "unknown config key"


def _is_off(value: Any, extra: Tuple[Any, ...]) -> bool:
    return any(type(value) is type(off) and value == off for off in _BASE_OFF + tuple(extra))


def _check_value(
    key: Key,
    value: Any,
    where: str,
    path: str,
    resolve: Optional[Callable[[str], Any]],
    refusals: List[Refusal],
) -> Any:
    """Return the value a component sees for one supported key."""
    if key.type not in (EXPRESSION, CODE) and has_context_reference(value):
        if resolve is None:
            return value
        value = resolve(value)

    if value is None:
        return None if key.nullable else copy.deepcopy(key.default)

    try:
        value = _coerce(key, value)
    except ValueError as exc:
        refusals.append(Refusal(where, path, str(exc)))
        return copy.deepcopy(key.default)
    if value is None:
        return copy.deepcopy(key.default)

    if key.type is list:
        value = _check_items(key, value, where, path, resolve, refusals)
    elif key.type is dict and key.fields is not None:
        value, nested = normalize_config(value, key.fields, where, resolve, _prefix=path + ".")
        refusals.extend(nested)

    if key.convert is not None:
        try:
            value = key.convert(value)
        except ValueError as exc:
            refusals.append(Refusal(where, path, str(exc)))
            return copy.deepcopy(key.default)

    if key.choices is not None and value not in key.choices:
        allowed = ", ".join(repr(choice) for choice in key.choices)
        refusals.append(Refusal(where, path, f"{value!r} is not allowed; use one of {allowed}"))
        return copy.deepcopy(key.default)
    return value


def _check_items(
    key: Key,
    value: List[Any],
    where: str,
    path: str,
    resolve: Optional[Callable[[str], Any]],
    refusals: List[Refusal],
) -> List[Any]:
    items: List[Any] = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if key.item_convert is not None:
            item = key.item_convert(item)
        if key.items is None:
            if resolve is not None and has_context_reference(item):
                item = resolve(item)
            items.append(item)
            continue
        if not isinstance(item, dict):
            refusals.append(Refusal(where, item_path, "expected an object"))
            continue
        checked, nested = normalize_config(item, key.items, where, resolve, _prefix=item_path + ".")
        refusals.extend(nested)
        items.append(checked)
    return items


def _coerce(key: Key, value: Any) -> Any:
    """Bring a JSON value to the declared type, or raise ``ValueError``.

    Returns ``None`` when the value means "omitted" (an empty string for a
    number), so the caller falls back to the default.
    """
    kind = key.type
    if kind is object:
        return value
    if kind is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        raise ValueError(f"expected true or false, got {value!r}")
    if kind is int:
        if isinstance(value, bool):
            raise ValueError(f"expected a whole number, got {value!r}")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            text = value.strip()
            if text == "":
                return None
            if re.fullmatch(r"[+-]?\d+", text):
                return int(text)
        raise ValueError(f"expected a whole number, got {value!r}")
    if kind is float:
        if isinstance(value, bool):
            raise ValueError(f"expected a number, got {value!r}")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if text == "":
                return None
            try:
                return float(text)
            except ValueError:
                pass
        raise ValueError(f"expected a number, got {value!r}")
    if kind in _TEXT_TYPES:
        if isinstance(value, str):
            return value
        raise ValueError(f"expected text, got {value!r}")
    if kind is list:
        if isinstance(value, list):
            return value
        raise ValueError(f"expected a list, got {value!r}")
    if kind is dict:
        if isinstance(value, dict):
            return value
        raise ValueError(f"expected an object, got {value!r}")
    raise ValueError(f"key '{key.name}' declares an unknown type {kind!r}")
