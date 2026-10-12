"""Foreach: a loop over values written in the job config."""
from __future__ import annotations

from typing import Any, List

from ...job.keys import Key, Kind
from ..base import MAX_ITEMS, Action
from ..registry import REGISTRY


def _texts(values: List[Any]) -> List[str]:
    wrong = [value for value in values if not isinstance(value, (str, int, float)) or isinstance(value, bool)]
    if wrong:
        raise ValueError(f"every value is text; {wrong} is not")
    return [str(value) for value in values]


@REGISTRY.register
class Foreach(Action):
    """Start a loop over `values`: what its iterate link leads to runs once for each, in the order written.

    In a pass the value is in globalMap as `<id>_CURRENT_VALUE`, as text,
    and the number of the pass as `<id>_CURRENT_ITERATION`. A value may
    name a context variable; it is put in when the component runs, before
    the first pass. No value, no pass. `<id>_NB_LINE` is how many values
    there are. No flow comes to it or leaves it.
    """

    names = ("foreach", "Foreach", "tForeach")
    loops = True
    keys = (
        Key("values", type=list, default=[], convert=_texts, doc="The values, in the order their passes run."),
        MAX_ITEMS,
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="Nothing here can fail; v1 reads it on every component."),
    )

    def act(self) -> None:
        values = self.config["values"]
        self.loop_over([(value, {f"{self.id}_CURRENT_VALUE": value}) for value in values])
        self.global_map.update({
            f"{self.id}_NB_LINE": len(values), f"{self.id}_NB_LINE_OK": len(values), f"{self.id}_NB_LINE_REJECT": 0,
        })
