"""Extract JSON fields: paths into the JSON document one column holds become columns."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...column_types import held_frame
from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...rows import hidden, shown, visible
from ..base import Transform, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


def _read_by(value: str) -> str:
    return value.upper()


def _mapping(value: List[Any]) -> List[Any]:
    if not value:
        raise ValueError("names no column to fill")
    return value


def _parsed(path: str) -> Any:
    """A JSONPath as the library reads it: plain jsonpath-ng, which is what v1 reads paths with here."""
    from jsonpath_ng import parse  # late: only this component and the JSON reader need the library

    return parse(path)


def _unreadable(path: str) -> Optional[str]:
    try:
        _parsed(path)
    except Exception as exc:  # noqa: BLE001 -- the library raises what it likes for a path it cannot read
        return " ".join(str(exc).split())[:160] or type(exc).__name__
    return None


def _taken(frame: pl.DataFrame, places: List[int]) -> pl.DataFrame:
    return frame[places] if places else frame.clear()


_ENTRY = (
    Key("schema_column", required=True, aliases=("column",), doc="The column to fill."),
    Key("query", default="", nullable=True,
        doc="The JSONPath of its value, from the item. With none, the input column of the same name is taken."),
)


@REGISTRY.register
class ExtractJSONFields(Transform):
    """Read the JSON document in the column `jsonfield` and fill columns from paths into it.

    `json_loop_query` finds the items of a document: each gives a row, and
    a document it finds none in gives no row. Without it the document is
    the one item. Each entry of `mapping_4_jsonpath` fills a column from
    its path, followed from the item (or from the whole document with
    `use_loop_as_root` off). A path that finds nothing gives empty text;
    one value gives that value; several give them as a JSON list; an
    object or a list is written as JSON. An entry with no path takes the
    input column of the same name. Only the columns of the mapping are
    filled: every other output column is missing.

    A row whose source is missing (`NO_JSON`) or is no JSON (`PARSE_ERROR`,
    an empty text too) leaves by the reject output with the text in
    `errorJSONField`, or fails the job under `die_on_error`.

    A document is read out of every row in Python, so this component holds
    its rows in memory, as in v1.
    """

    names = ("extract_json_fields", "ExtractJSONFields", "tExtractJSONFields")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    may_need_rows = True
    keys = (
        Key("read_by", default="JSONPATH", convert=_read_by, doc="How paths are written: JSONPATH. (XPATH is not built.)"),
        Key("jsonfield", default="", doc="The column that holds the document; the first column when none is named."),
        Key("json_loop_query", default="", nullable=True, doc="The JSONPath of the items; none for the document itself."),
        Key("mapping_4_jsonpath", type=list, required=True, items=_ENTRY, convert=_mapping,
            doc="The columns to fill, each with its path."),
        Key("use_loop_as_root", type=bool, default=True,
            doc="Whether a column's path is followed from the item; when off, from the whole document."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether a source that is missing or no JSON, or a missing value in a column the schema declares "
                "not nullable, fails the job; when off, the row leaves by the reject output."),
        Key("loop_query", kind=Kind.IGNORED, type=object, doc="Read only with `read_by` XPATH, which is not built."),
        Key("mapping", kind=Kind.IGNORED, type=object, doc="Read only with `read_by` XPATH, which is not built."),
        Key("json_path_version", kind=Kind.IGNORED, type=object, doc="Never read by v1."),
        Key("encoding", kind=Kind.IGNORED, type=object, doc="Never read by v1."),
    )

    def needs_rows(self) -> bool:
        return True

    def problems(self) -> List[str]:
        config, found = self.config, []
        if config["read_by"] != "JSONPATH":
            found.append(
                f"read_by: '{config['read_by']}' is not built: v2 follows JSONPath only (v1 tries XPath as JSONPath, "
                "which it is not, and fills nothing)"
            )
        if not self.schema:
            found.append("schema: extract JSON fields needs its output columns declared")
        names = [column.name for column in self.input_schema]
        if names and config["jsonfield"] and config["jsonfield"] not in names:
            found.append(f"jsonfield: there is no column '{config['jsonfield']}' ({', '.join(names)})")
        paths = [("json_loop_query", config["json_loop_query"] or "")]
        paths += [(f"mapping_4_jsonpath[{at}].query", entry["query"] or "") for at, entry in enumerate(config["mapping_4_jsonpath"])]
        for key, path in paths:
            wrong = _unreadable(path) if path else None
            if wrong:
                found.append(f"{key}: '{path}' is no JSONPath: {wrong}")
        return found

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        (frame,) = inputs.values()
        config = self.config
        names, carried = visible(frame.columns), hidden(frame.columns)
        field = config["jsonfield"] or (names[0] if names else "")
        if field not in names:
            raise ConfigurationError(f"jsonfield: there is no column '{field}' ({', '.join(names)})")
        loop = _parsed(config["json_loop_query"]) if config["json_loop_query"] else None
        paths = [(entry["schema_column"], entry["query"], _parsed(entry["query"]) if entry["query"] else None)
                 for entry in config["mapping_4_jsonpath"]]

        rows: List[Dict[str, Any]] = []
        origin: List[int] = []
        turned: List[Tuple[int, str, str, str]] = []
        lost: Dict[str, int] = {}
        for at, row in enumerate(frame.select(names).iter_rows(named=True)):
            raw = row[field]
            if raw is None:
                turned.append((at, "", "NO_JSON", f"column '{field}' is null"))
                continue
            text = raw if isinstance(raw, str) else str(raw)
            try:
                document = json.loads(text)
                items = [document] if loop is None else [match.value for match in loop.find(document)]
            except ValueError as exc:
                turned.append((at, text, "PARSE_ERROR", str(exc)))
                continue
            for item in items:
                root = item if config["use_loop_as_root"] else document
                filled: Dict[str, Any] = {}
                for column, written, path in paths:
                    if path is None:
                        filled[column] = row.get(column)
                        continue
                    try:
                        found = [match.value for match in path.find(root)]
                    except Exception:  # noqa: BLE001 -- as v1: a path that cannot be followed here finds nothing
                        lost[written] = lost.get(written, 0) + 1
                        found = []
                    filled[column] = self._value(found)
                rows.append(filled)
                origin.append(at)

        for written, times in lost.items():
            logger.warning(one_line(f"[{self.id}] the path {written} could not be followed on {times} item(s); it found nothing there"))
        places = [at for at, _, _, _ in turned]
        if turned and config["die_on_error"]:
            _, _, code, why = turned[0]
            more = "" if len(turned) == 1 else f" (the first of {len(turned)} such rows)"
            raise ConfigurationError(f"{code}: {shown(why)}{more}{self.where(frame[places[:1]].select(carried))}")
        if turned and "reject" not in self.wired:
            self._tell(len(turned), turned[0][3], frame[places[:1]].select(carried))

        main = held_frame(self.schema, rows, usual_dates=False).hstack(_taken(frame.select(carried), origin))
        reject = _taken(frame.select(names), places).with_columns(
            pl.Series("errorJSONField", [text for _, text, _, _ in turned], dtype=pl.String),
            pl.Series("errorCode", [code for _, _, code, _ in turned], dtype=pl.String),
            pl.Series("errorMessage", [why for _, _, _, why in turned], dtype=pl.String),
        ).hstack(_taken(frame.select(carried), places))
        return {"main": main, "reject": reject}

    @staticmethod
    def _value(found: List[Any]) -> Any:
        """What a path gives for one item, by v1's rule."""
        if not found:
            return ""
        value = found[0] if len(found) == 1 else found
        return json.dumps(value) if isinstance(value, (list, dict)) else value

    def _tell(self, rows: int, why: str, first: pl.DataFrame) -> None:
        """Have the log say, once the subjob has run, that rows were dropped with no flow to take them."""
        start = "1 row was dropped" if rows == 1 else f"{rows} rows were dropped"
        middle = ": " if rows == 1 else "; the first: "
        said = f"[{self.id}] {start} (no flow takes this component's rejects){middle}{shown(why)}{self.where(first)}"
        self.tap(pl.LazyFrame({"rows": [rows]}), lambda _: logger.warning(one_line(said)))
