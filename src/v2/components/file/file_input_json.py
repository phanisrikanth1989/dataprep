"""JSON file input: read the records a JSONPath finds in a document as rows.

A document is read whole: a JSONPath can ask for any part of it, so there is
no reading it lazily. Every value is handed on as the text v1 would write
for it, and the engine turns that text into the type the schema declares, as
it does for every component.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...rows import hidden, visible
from ..base import Source
from ..registry import REGISTRY
from .file_input_delimited import encoding

logger = logging.getLogger(__name__)

_NO_SCHEMA = "Acted on by v1 only with a `schema` inside the config, which the converter does not write."
# A working column: what the log says of a record that is turned away, missing for the others.
_TOLD = "__json_told"


def _unquoted(value: str) -> str:
    """A path as written, less the double quotes Talend may put around it."""
    return value[1:-1] if len(value) > 1 and value.startswith('"') and value.endswith('"') else value


def _loop(value: str) -> str:
    return value.strip('"')


_MAPPING = (
    Key("column", required=True, doc="The column the value goes to."),
    Key("jsonpath", default="", convert=_unquoted, doc="The JSONPath of the value, from the record."),
    Key("nodecheck", kind=Kind.IGNORED, type=object, doc="Talend's XPath mode; never read by v1."),
)


@REGISTRY.register
class FileInputJSON(Source):
    """Read a JSON document and hand on one row for each record a JSONPath finds in it.

    `json_loop_query` finds the records; each `mapping` entry finds one
    column's value inside a record. A path that finds one value gives that
    value. A path that finds several, or holds `[*]` or `.*`, gives them as
    a JSON list, and so does a path that finds nothing: an empty one. A list
    or an object is handed on as JSON text.

    Values are text until the engine fits them to the declared schema: a
    number written as text is read as a number, and what cannot be read as
    its column's type goes missing.

    A row's number is the place of its record among the records found, from
    1; a failure names the record by that number and by its path in the
    document.
    """

    names = ("file_input_json", "FileInputJSON", "tFileInputJSON")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("path", required=True, aliases=("filename",), doc="The JSON file to read."),
        Key("json_loop_query", required=True, convert=_loop, doc="The JSONPath that finds the records."),
        Key("mapping", type=list, default=[], items=_MAPPING, doc="Which value of a record goes to which column."),
        Key("encoding", default="UTF-8", convert=encoding, doc="The file's character encoding."),
        Key("use_loop_as_root", type=bool, default=False,
            doc="Whether a loop that finds one list is gone through item by item."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a file that is not there or is not JSON, and a missing value in a column that may not "
                "hold one, fail the job. When off, such a file reads as no rows and such a row is dropped."),
        Key("useurl", kind=Kind.REFUSED, type=bool, reason="v2 reads files, not URLs; fetch the document first",
            doc="Read the document from `urlpath`."),
        Key("urlpath", kind=Kind.IGNORED, type=object, doc="Only read with `useurl`."),
        Key("schema", kind=Kind.REFUSED, type=object,
            reason="types are declared in the component's schema, not inside its config",
            doc="v1's older way of naming column types."),
        Key("read_by", kind=Kind.IGNORED, type=object, doc="v1 reads by JSONPath whatever this says."),
        Key("loop_query", kind=Kind.IGNORED, type=object, doc="The loop of Talend's XPath mode, which v1 does not have."),
        Key("json_path_version", kind=Kind.IGNORED, type=object, doc="Never read by v1."),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc=_NO_SCHEMA),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc=_NO_SCHEMA),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc=_NO_SCHEMA),
        Key("check_date", kind=Kind.IGNORED, type=object, doc=_NO_SCHEMA),
    )

    def problems(self) -> List[str]:
        paths = [("json_loop_query", self.config["json_loop_query"])]
        paths += [(f"mapping[{index}].jsonpath", entry["jsonpath"]) for index, entry in enumerate(self.config["mapping"])]
        found = []
        for key, path in paths:
            try:
                _parsed(path)
            except ConfigurationError as exc:
                # The library is not there: said once, and no path is at fault.
                return [f"config: {exc}"]
            except Exception as exc:  # noqa: BLE001 -- the parser raises its own kinds
                found.append(f"{key}: not a JSONPath ({_said(exc)})")
        return found

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        """The columns the paths give, as text, with the declared ones that have no path."""
        names = list(dict.fromkeys(entry["column"] for entry in self.config["mapping"]))
        main = pl.LazyFrame(schema={name: pl.String for name in names})
        return {"main": main, "reject": _no_rejects(main)}

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        config = self.config
        path = config["path"]
        self._paths: List[str] = []
        try:
            with open(path, encoding=config["encoding"]) as handle:
                document = json.load(handle)
        except (OSError, ValueError) as exc:
            why = f"File not found: '{path}'" if not os.path.isfile(path) else f"'{path}' is not JSON: {_said(exc)}"
            if config["die_on_error"]:
                raise ConfigurationError(why) from None
            logger.warning(f"[{self.id}] {why}; no rows are read")
            return self.declared_outputs()
        self.global_map[f"{self.id}_FILENAME"] = path

        records = self._records(document)
        mapping = [(entry["column"], entry["jsonpath"], _parsed(entry["jsonpath"])) for entry in config["mapping"]]
        cells: Dict[str, List[Optional[str]]] = {column: [] for column, _, _ in mapping}
        turned_away: List[Optional[str]] = []
        told: List[Optional[str]] = []
        for where, record in records:
            self._paths.append(where)
            row, why, wrong = _row(record, mapping)
            turned_away.append(why)
            told.append(wrong)
            for column, cell in cells.items():
                cell.append(row.get(column))
        if not cells:
            # No path, so no column, and a table without columns has no rows: v1 writes none either.
            return self.declared_outputs()
        rows = pl.DataFrame(cells, schema={column: pl.String for column in cells})
        rows = rows.with_row_index(self.row_number, offset=1)
        present = [copy for column, copy in zip([c for c in self.schema if c.key], self.key_copies())
                   if column.name in cells]
        rows = rows.with_columns(present)
        rows = rows.select(visible(rows.columns) + hidden(rows.columns))
        why = pl.Series(turned_away, dtype=pl.String)
        reject = rows.filter(why.is_not_null()).with_columns(
            pl.lit("PARSE_ERROR").alias("errorCode"), why.drop_nulls().alias("errorMessage")
        )
        # Turned away whatever die_on_error says, so told whatever it says.
        marked = rows.with_columns(pl.Series(_TOLD, told, dtype=pl.String)).lazy()
        main = self.tell_dropped(marked, pl.col(_TOLD).is_not_null(), pl.col(_TOLD))
        return {"main": main.filter(pl.col(_TOLD).is_null()).drop(_TOLD), "reject": reject.lazy()}

    def _records(self, document: Any) -> List[Tuple[str, Any]]:
        """The records the loop finds, each with its path in the document."""
        found = [(_path(match.full_path), match.value) for match in _parsed(self.config["json_loop_query"]).find(document)]
        if self.config["use_loop_as_root"] and len(found) == 1 and isinstance(found[0][1], list):
            (where, items), = found
            return [(f"{where}[{index}]", item) for index, item in enumerate(items)]
        return found

    def locate(self, number: int) -> str:
        """Where a row's record is: its place among the records, and its path in the document."""
        return f"record {number} ({self._paths[number - 1]}) of {self.config['path']}"


# ------------------------------------------------------------------
# Paths and values
# ------------------------------------------------------------------

def _parsed(path: str) -> Any:
    """A JSONPath, read by the library v1 reads it with."""
    try:
        # Imported here: a job without JSON input runs on a machine without the library.
        from jsonpath_ng.ext import parse
    except ImportError:
        raise ConfigurationError(
            "reading JSON files needs the jsonpath-ng package (pip install 'dataprep[v2]')"
        ) from None
    return parse(path)


def _said(error: BaseException) -> str:
    """An error's first line, for a message."""
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


def _row(
    record: Any, mapping: List[Tuple[str, str, Any]]
) -> Tuple[Dict[str, Optional[str]], Optional[str], Optional[str]]:
    """One record's values as text, by column; and why the record is turned away, when it is.

    Asked for an item of something that is no list, the library raises where
    it could find nothing. v1 turns such a record away with what the library
    said, keeping the values read before that path; so does this.

    Returns:
        The values; then, for a record that is turned away, what the
        library said (the reject output's ``errorMessage``, as in v1) and
        what the log says of it, which names the column and its path too.
    """
    row: Dict[str, Optional[str]] = {}
    for column, written, query in mapping:
        try:
            found = query.find(record)
        except Exception as exc:  # noqa: BLE001 -- whatever the library raises, as v1 has it
            said = str(exc)
            return row, said, f"Column '{column}': the path {written} could not be followed on the record ({said})"
        row[column] = _as_text(_value(written, found))
    return row, None, None


def _value(written: str, matches: List[Any]) -> Any:
    """What a path gives for one record, by v1's rule: one value alone, else all of them as a list."""
    values = [match.value for match in matches]
    if "[*]" in written or ".*" in written:
        return values
    return values[0] if len(values) == 1 else values


def _as_text(value: Any) -> Optional[str]:
    """A JSON value as the text v1 writes for it."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    # True and False, and numbers as Python prints them: 1, 1.5, 1e+30.
    return str(value)


def _path(full: Any) -> str:
    """The path of a match as a JSONPath a person can follow: ``$.items[2]``."""
    return "$" + _steps(full)


def _steps(node: Any) -> str:
    """One part of a match's path, written out: the library's own text for it differs between its versions."""
    kind = type(node).__name__
    if kind == "Child":
        return _steps(node.left) + _steps(node.right)
    if kind == "Fields":
        return "".join(f".{name}" for name in node.fields)
    if kind == "Index":
        indices = getattr(node, "indices", None) or (node.index,)
        return "".join(f"[{index}]" for index in indices)
    # What is left is the document itself, which the leading `$` stands for.
    return ""


def _no_rejects(main: pl.LazyFrame) -> pl.LazyFrame:
    """The reject output of a reader that turns no record away: the columns of main and v1's two, no rows."""
    return main.clear().with_columns(
        pl.lit(None, dtype=pl.String).alias("errorCode"), pl.lit(None, dtype=pl.String).alias("errorMessage")
    )
