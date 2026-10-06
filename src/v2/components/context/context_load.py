"""Context load: set context variables from the rows of a key/value flow."""
from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from typing import Any, Callable, ClassVar, Dict, List, Set, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key
from ..base import CheckFailed, Eager
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_POLICIES = ("ERROR", "WARNING", "INFO", "NO_WARNING")
# The log level of each policy, and the key that keeps its messages quiet.
_LEVELS = {
    "ERROR": (logging.ERROR, "disable_error"),
    "WARNING": (logging.WARNING, "disable_warnings"),
    "INFO": (logging.INFO, "disable_info"),
}
_DATE_PATTERNS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y %H:%M")


def _truth(value: Any) -> bool:
    return str(value).lower() in ("true", "1", "yes")


def _first_character(value: Any) -> str:
    return str(value)[0] if value else ""


def _date(value: Any) -> Any:
    """A date read by the first of v1's four patterns that fits; the value itself when none does."""
    if not isinstance(value, str):
        return value
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.datetime.strptime(value, pattern)
        except ValueError:
            continue
    return value


# How v1 turns a value into each type a context variable may have, by the type's v1 name.
_CONVERTERS: Dict[str, Callable[[Any], Any]] = {
    "id_String": str, "id_Object": str, "str": str, "object": str, "datetime": str,
    "id_Integer": int, "id_Long": int, "id_Short": int, "id_Byte": int, "int": int,
    "id_Float": float, "id_Double": float, "float": float,
    "id_Boolean": _truth, "bool": _truth,
    "id_BigDecimal": Decimal, "Decimal": Decimal,
    "id_Character": _first_character,
    "id_Date": _date,
}


@REGISTRY.register
class ContextLoad(Eager):
    """Set context variables from the rows of a flow with ``key`` and ``value`` columns.

    Every row sets its variable, whether the job declares it or not, and the
    value takes the variable's type. A ``type`` column, when the flow has
    one, names the type of its row instead (v1's names: ``int``,
    ``id_Integer``, ``id_Date``...). Components built after this one read
    the new values. The two policy keys decide only what is said about keys
    that are new and variables the flow leaves alone.

    globalMap is given ``<id>_NB_CONTEXT_LOADED``, ``<id>_KEY_NOT_INCONTEXT``
    and ``<id>_KEY_NOT_LOADED`` (names, sorted and joined by commas).
    """

    names = ("context_load", "ContextLoad", "tContextLoad")
    outputs: ClassVar[Dict[str, Tuple[str, ...]]] = {}
    min_inputs = 1
    sets_context = True
    # The variables the flow set, by name.
    _loaded: Tuple[str, ...] = ()
    keys = (
        Key("print_operations", type=bool, default=False, doc="Whether each variable set is logged."),
        Key("load_new_variable", default="WARNING", convert=str.upper, choices=_POLICIES,
            doc="How a key that is not a context variable yet is reported: ERROR, WARNING, INFO or NO_WARNING."),
        Key("not_load_old_variable", default="WARNING", convert=str.upper, choices=_POLICIES,
            doc="How a context variable the flow does not set is reported: ERROR, WARNING, INFO or NO_WARNING."),
        Key("disable_error", type=bool, default=False,
            doc="Whether ERROR reports are kept quiet. A quiet report never fails the component."),
        Key("disable_warnings", type=bool, default=True, doc="Whether WARNING reports are kept quiet."),
        Key("disable_info", type=bool, default=True, doc="Whether INFO reports are kept quiet."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether an ERROR report fails the component. The variables have been set by then."),
    )

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        (frame,) = inputs.values()
        known = set(self.context)
        new: Set[str] = set()
        updated: Set[str] = set()
        if "key" not in frame.columns or "value" not in frame.columns:
            raise ConfigurationError(f"Input must have 'key' and 'value' columns, got: {frame.columns}")
        for row in frame.iter_rows(named=True):
            key = "" if row["key"] is None else str(row["key"]).strip()
            if key:
                (updated if key in known else new).add(key)
                self._set(key, row["value"], row.get("type"))

        unloaded = known - updated
        for key in sorted(new):
            self._report(f"New context variable '{key}' not in original job context", "load_new_variable")
        for key in sorted(unloaded):
            self._report(f"Context variable '{key}' not loaded from incoming flow", "not_load_old_variable")

        self._loaded = tuple(sorted(new | updated))
        loaded = len(self._loaded)
        self.global_map[f"{self.id}_NB_CONTEXT_LOADED"] = loaded
        self.global_map[f"{self.id}_KEY_NOT_INCONTEXT"] = ",".join(sorted(new))
        self.global_map[f"{self.id}_KEY_NOT_LOADED"] = ",".join(sorted(unloaded))
        logger.info(
            f"[{self.id}] Loaded {loaded} context variables "
            f"({len(new)} new, {len(updated)} updated, {len(unloaded)} unloaded)"
        )
        return {}

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """v1 counts the variables loaded, not the rows that set them."""
        loaded = [pl.LazyFrame({"key": list(self._loaded)}, schema={"key": pl.String})]
        return {"NB_LINE": loaded, "NB_LINE_OK": loaded, "NB_LINE_REJECT": []}

    # ------------------------------------------------------------------
    # One variable
    # ------------------------------------------------------------------

    def _set(self, key: str, value: Any, row_type: Any) -> None:
        kind = self._declared_type(key) if row_type is None else str(row_type)
        self.context[key] = self._converted(key, value, kind)
        if kind:
            # The type stays with the variable, so a later load reads its values the same way, as in v1.
            self.run_context.context_types[key] = kind
        if self.config["print_operations"]:
            logger.info(f"[{self.id}] Context loaded: {key} = {value} (type: {kind})")

    def _declared_type(self, key: str) -> str:
        """The type of a context variable, by v1's name for it: the declared one, or text."""
        return self.run_context.context_types.get(key) or "id_String"

    def _converted(self, key: str, value: Any, kind: str) -> Any:
        """A value as its type, by v1's rules: nothing, empty text and what does not fit stay as they are."""
        if value is None or value == "" or not kind:
            return value
        convert = _CONVERTERS.get(kind)
        if convert is None:
            logger.warning(f"[{self.id}] context variable '{key}': unknown type '{kind}', value kept as it is")
            return value
        try:
            return convert(value)
        except (ValueError, TypeError, ArithmeticError):
            logger.warning(f"[{self.id}] context variable '{key}': {value!r} is not a valid {kind}, kept as it is")
            return value

    # ------------------------------------------------------------------
    # What is said about keys
    # ------------------------------------------------------------------

    def _report(self, message: str, policy_key: str) -> None:
        policy = self.config[policy_key]
        if policy == "NO_WARNING":
            return
        level, quiet_key = _LEVELS[policy]
        if self.config[quiet_key]:
            return
        logger.log(level, f"[{self.id}] {message}")
        if policy == "ERROR" and self.config["die_on_error"]:
            raise CheckFailed(message)
