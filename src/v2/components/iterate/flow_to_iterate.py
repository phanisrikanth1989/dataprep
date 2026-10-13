"""Flow to iterate: a loop over the rows of a flow."""
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Iterator, List, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ..base import MAX_ITEMS, Sink, Write
from ..registry import REGISTRY

# How many rows are taken from the scratch file at a time.
_PIECE = 10_000


def _key(value: str) -> str:
    if not value.strip():
        raise ValueError("an entry of globalMap needs a name")
    return value


@REGISTRY.register
class FlowToIterate(Sink):
    """Start a loop over the rows that reach it: what its iterate link leads to runs once for each row.

    In a pass the row is in globalMap, each value with the type it has.
    With `default_map` on, every column is there as `<flow>.<column>`,
    `<flow>` being the name of the flow that leads to the component
    (`row1.filepath`). With it off, `map_entries` says which columns, and
    under which names. `<id>_NB_LINE` is how many rows there were.

    The rows are not held in memory. They go to a scratch file in the one
    pass of the subjob they come from, and when that subjob has finished,
    with its own files in place, the passes are fed from the file a piece
    at a time. The file is removed when the loop is over.
    """

    names = ("flow_to_iterate", "FlowToIterate", "tFlowToIterate")
    loops = True
    keys = (
        Key("default_map", type=bool, default=True,
            doc="Whether every column is put in globalMap, as `<flow>.<column>`; off, `map_entries` says which."),
        Key("map_entries", type=list, default=[], doc="For `default_map` off: the entries of globalMap a pass has.",
            items=(Key("key", required=True, convert=_key, doc="The name of the entry."),
                   Key("value", required=True, doc="The column whose value it holds."))),
        MAX_ITEMS,
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="Nothing here can fail; v1 reads it on every component."),
    )

    def problems(self) -> List[str]:
        config = self.config
        if config["default_map"]:
            return []
        if not config["map_entries"]:
            return ["map_entries: `default_map` is off and no entry is given: a pass would have nothing"]
        declared = [column.name for column in self.input_schema]
        return [
            f"map_entries[{at}].value: there is no column '{entry['value']}'; the columns are: {', '.join(declared)}"
            for at, entry in enumerate(config["map_entries"]) if declared and entry["value"] not in declared
        ]

    def write(self, frame: pl.LazyFrame) -> Write:
        names = frame.collect_schema().names()
        if self.config["default_map"]:
            flow = self.arriving[0]
            entries = {f"{flow}.{name}": name for name in names}
        else:
            entries = {entry["key"]: entry["value"] for entry in self.config["map_entries"]}
            missing = [column for column in entries.values() if column not in names]
            if missing:
                raise ConfigurationError(f"map_entries: there is no column '{missing[0]}'; the columns are: {', '.join(names)}")
        wanted = list(dict.fromkeys(entries.values()))
        folder = os.environ.get("V2_TEMP_DIR") or tempfile.gettempdir()

        def place(written: str, rows: int) -> None:
            # The file the rows were written to is what the passes are fed from; it goes when the loop is over.
            self.loop_over(_rows(written, entries), count=rows, done=lambda: _removed(written))

        return Write(
            path=os.path.join(folder, f"v2_{self.run_context.token}_{self.id}.rows"),
            sink=lambda target: frame.select(wanted).sink_ipc(target, lazy=True),
            place=place,
        )


def _rows(path: str, entries: Dict[str, str]) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """The rows of the scratch file one after another, each as the entries of its pass; a piece is held at a time."""
    taken = 0
    while True:
        piece = pl.scan_ipc(path).slice(taken, _PIECE).collect()
        if piece.is_empty():
            return
        for number, row in enumerate(piece.iter_rows(named=True), start=taken + 1):
            yield f"row {number}", {key: row[column] for key, column in entries.items()}
        taken += piece.height


def _removed(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
