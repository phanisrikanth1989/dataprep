"""Die: the job is stopped with a message."""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, Optional

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...rows import first_of
from ..base import Action, Transform, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# `((Integer)globalMap.get("key"))`, as a converted job writes an entry of globalMap into a message.
_ENTRY = re.compile(r'\(\(\w+\)globalMap\.get\("(\w+)"\)\)')
# Talend's priorities, 1 trace to 6 fatal, as the levels v1 logs them at.
_LEVELS = {1: logging.DEBUG, 2: logging.DEBUG, 3: logging.INFO, 4: logging.WARNING, 5: logging.ERROR, 6: logging.CRITICAL}


def whole(what: str) -> Callable[[Any], int]:
    def convert(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{value!r} is no {what}: give a whole number") from None
    return convert


def priority(value: Any) -> int:
    level = whole("priority")(value)
    if level not in _LEVELS:
        raise ValueError(f"{level} is no priority: give 1 (trace) to 6 (fatal)")
    return level


def with_entries(message: str, global_map: Dict[str, Any]) -> str:
    """A message with each `((Type)globalMap.get("key"))` in it as that entry, 0 where there is none."""
    return _ENTRY.sub(lambda match: str(global_map.get(match.group(1), 0)), message)


def said(component_id: str, code: int, message: str, level: int) -> None:
    """Log a message with its code at the level of its priority, as v1 words it."""
    logger.log(_LEVELS[level], one_line(f"[{component_id}] Code {code}: {message}"))


@REGISTRY.register
class Die(Action, Transform):
    """Stop the job with `message`: nothing runs after it, and no trigger fires.

    Set off by a trigger, it stops the job when its turn comes. With a
    flow leading to it, it stops the job when a row arrives and not
    otherwise, as in Talend; the failure then names the first such row.

    The message is logged with its `code` at the level of `priority` (1
    and 2 debug, 3 info, 4 warning, 5 error, 6 critical), and left in
    globalMap with the code, the priority and `exit_code`, under v1's
    names (`<id>_MESSAGE`, `_CODE`, `_PRIORITY`, `_EXIT_CODE`,
    `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE`) and Talend's (`<id>_DIE_MESSAGE`,
    `_DIE_MESSAGES`, `_DIE_CODE`, `_DIE_PRIORITY`). A
    `((Integer)globalMap.get("key"))` in the message is that entry.
    """

    names = ("die", "Die", "tDie")
    stops_job = True
    min_inputs = 0
    max_inputs = 1
    keys = (
        Key("message", default="the end is near", doc="What the job stops with."),
        Key("code", type=object, default=4, convert=whole("code"), doc="The message's code."),
        Key("priority", type=object, default=5, convert=priority, doc="How grave it is: 1 (trace) to 6 (fatal)."),
        Key("exit_code", type=object, default=1, convert=whole("exit code"),
            doc="The exit code the message names. (The command line ends with 1 for any job that failed.)"),
        Key("exit_jvm", kind=Kind.REFUSED, type=object, reason="there is no JVM to exit; the job stops either way"),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="It stops the job whatever this says; v1 reads it on every component."),
    )

    def act(self) -> None:
        raise ConfigurationError(self._stopped())

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()

        def problem(found: pl.DataFrame) -> Optional[str]:
            rows = found["rows"].item()
            if not rows:
                return None
            more = "" if rows == 1 else f" (the first of {rows} rows that came to it)"
            return f"{self._stopped()}{more}{self.where(found)}"

        self.check(frame.select(pl.len().alias("rows"), *first_of(frame)), problem)
        return {}

    def _stopped(self) -> str:
        """Say the message, leave it in globalMap, and give the words the job fails with."""
        config, held = self.config, self.global_map
        message = with_entries(config["message"], held)
        said(self.id, config["code"], message, config["priority"])
        held.update({
            f"{self.id}_MESSAGE": message, f"{self.id}_CODE": config["code"], f"{self.id}_PRIORITY": config["priority"],
            f"{self.id}_EXIT_CODE": config["exit_code"],
            f"{self.id}_DIE_MESSAGE": message, f"{self.id}_DIE_MESSAGES": message, f"{self.id}_DIE_CODE": config["code"],
            f"{self.id}_DIE_PRIORITY": config["priority"],
            "JOB_ERROR_MESSAGE": message, "JOB_EXIT_CODE": config["exit_code"],
        })
        return f"Job terminated by tDie: {message} (exit code: {config['exit_code']})"
