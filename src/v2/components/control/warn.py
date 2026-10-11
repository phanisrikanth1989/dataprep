"""Warn: a message is logged and the job goes on."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...job.keys import Key
from ..base import Action, Transform
from ..registry import REGISTRY
from .die import priority, said, whole, with_entries


@REGISTRY.register
class Warn(Action, Transform):
    """Log `message` and go on.

    Set off by a trigger, it speaks when its turn comes. With a flow
    leading to it, it hands the rows on as they came and speaks once when
    a row arrives, and not at all when none does.

    The message is logged with its `code` at the level of `priority` (1
    and 2 debug, 3 info, 4 warning, 5 error, 6 critical), and left in
    globalMap with the code and the priority, under v1's names
    (`<id>_MESSAGE`, `_CODE`, `_PRIORITY`) and Talend's
    (`<id>_WARN_MESSAGES`, `_WARN_CODE`, `_WARN_PRIORITY`). A
    `((Integer)globalMap.get("key"))` in the message is that entry.
    """

    names = ("warn", "Warn", "tWarn")
    outputs = {"main": ("flow", "main")}
    min_inputs = 0
    max_inputs = 1
    keys = (
        Key("message", default="this is a warning", doc="What is said."),
        Key("code", type=object, default=42, convert=whole("code"), doc="The message's code."),
        Key("priority", type=object, default=4, convert=priority, doc="How grave it is: 1 (trace) to 6 (fatal)."),
    )

    def act(self) -> None:
        config, held = self.config, self.global_map
        message = with_entries(config["message"], held)
        said(self.id, config["code"], message, config["priority"])
        held.update({
            f"{self.id}_MESSAGE": message, f"{self.id}_CODE": config["code"], f"{self.id}_PRIORITY": config["priority"],
            f"{self.id}_WARN_MESSAGES": message, f"{self.id}_WARN_CODE": config["code"],
            f"{self.id}_WARN_PRIORITY": config["priority"],
        })

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        self.tap(frame.select(pl.len().alias("rows")), lambda found: self.act() if found["rows"].item() else None)
        return {"main": frame}
