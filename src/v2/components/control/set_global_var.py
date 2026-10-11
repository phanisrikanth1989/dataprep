"""Set global var: entries are put in globalMap."""
from __future__ import annotations

import re
from typing import Any, Dict, List

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...rows import visible
from ..base import Action, Transform
from ..registry import REGISTRY

_OF_ROW = re.compile(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)")


def _named(value: str) -> str:
    if not value:
        raise ValueError("an entry needs a key to be put under")
    return value


_VARIABLE = (
    Key("key", required=True, aliases=("name",), convert=_named, doc="The key of the entry."),
    Key("value", type=object, default=None, nullable=True, aliases=("VALUE",),
        doc="What is put under it. In a flow, `<flow>.<column>` is that column of the row."),
)


@REGISTRY.register
class SetGlobalVar(Action, Transform):
    """Put the entries of `variables` in globalMap.

    Set off by a trigger, it puts each value under its key when its turn
    comes. With a flow leading to it, it hands the rows on as they came,
    and a value written `<flow>.<column>` (`row1.name`) is that column of
    the last row; nothing is put when no row arrives, as in Talend.

    In a flow the entries are put when the subjob is done, not row by row:
    v2 runs a subjob in one pass. A later subjob reads them, as does a
    trigger's condition. A component of the same subjob that reads one of
    them would read what was there before, so such a job fails before
    anything is written.
    """

    names = ("set_global_var", "SetGlobalVar", "tSetGlobalVar")
    outputs = {"main": ("flow", "main")}
    min_inputs = 0
    max_inputs = 1
    keys = (
        Key("variables", type=list, required=True, aliases=("VARIABLES",), items=_VARIABLE,
            doc="The entries: each a key and its value."),
        Key("die_on_error", type=bool, default=True, doc="Nothing here can fail on a row; v1 reads it on every component."),
        Key("requires_java_bridge", kind=Kind.IGNORED, type=object,
            doc="The converter's note that a value was Java; a value that still is refuses the job."),
    )

    def problems(self) -> List[str]:
        if self.config["variables"] is None:
            return ["variables: names no entry to put"]
        found = [f"variables[{at}].key: an entry needs a key to be put under"
                 for at, entry in enumerate(self.config["variables"]) if not entry["key"]]
        return found + self.unfed()

    def act(self) -> None:
        for entry in self.config["variables"]:
            self._put(entry["key"], entry["value"])

    def _put(self, key: str, value: Any) -> None:
        self.global_map[key] = value
        # The key does not say whose it is; a trigger judged before this component is done must not see it.
        self.run_context.put_by[key] = self.id

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        ((flow, frame),) = inputs.items()
        self._unserved()
        names = visible(frame.collect_schema().names())
        # A value that names a column of the flow is that column of the last row; any other is itself.
        of_row: Dict[int, str] = {}
        for at, entry in enumerate(self.config["variables"]):
            named = _OF_ROW.fullmatch(entry["value"].strip()) if isinstance(entry["value"], str) else None
            if named and named.group(1) == flow and named.group(2) in names:
                of_row[at] = named.group(2)
        asked = [pl.len().alias("__rows")] + [pl.col(name).last().alias(f"__{at}") for at, name in of_row.items()]

        def put(found: pl.DataFrame) -> None:
            if not found["__rows"].item():
                return
            for at, entry in enumerate(self.config["variables"]):
                self._put(entry["key"], found[f"__{at}"].item() if at in of_row else entry["value"])

        self.tap(frame.select(asked), put)
        return {"main": frame}

    def line_counts(self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]) -> Dict[str, List[Any]]:
        # As v1 counts: it sets entries, and counts no rows.
        return {"NB_LINE": [], "NB_LINE_OK": [], "NB_LINE_REJECT": []}

    def _unserved(self) -> None:
        """Fail when a component of the same subjob reads an entry this one puts only when the subjob is done."""
        for other, text in self.run_context.subjob_texts.items():
            if other == self.id:
                continue
            for entry in self.config["variables"]:
                # Read as globalMap.get("key") or globalMap["key"], in either kind of quotes.
                read = r"globalMap\s*(?:\.\s*get\s*\(|\[)\s*[\"']" + re.escape(entry["key"]) + r"[\"']"
                if re.search(read, text):
                    raise ConfigurationError(
                        f"'{other}' reads the globalMap entry '{entry['key']}' in the same subjob: v2 puts it when the "
                        "subjob is done, not row by row as v1 does; read it in a subjob that follows"
                    )
