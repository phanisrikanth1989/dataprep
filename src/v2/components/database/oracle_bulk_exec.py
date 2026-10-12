"""Oracle bulk exec: the rows of a file, or of a flow, stored in a table."""
from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, List, Tuple

import polars as pl

from ... import oracle
from ...errors import ConfigurationError, DatabaseError
from ...files import codec_name
from ...job.keys import Key, Kind, normalize_config
from ...sessions import Session
from ..base import DIE_ON_ERROR
from ..file.file_input_delimited import FileInputDelimited
from ..registry import REGISTRY
from .oracle_output import _DEFINING, CLEAR, INSERT, NONE, OracleOutput, _rows

logger = logging.getLogger(__name__)

APPEND, REPLACE, TRUNCATE = "APPEND", "REPLACE", "TRUNCATE"
# Oracle's names for the encodings a load file is most often in, as Python calls them.
_ENCODINGS = {"UTF8": "UTF-8", "AL32UTF8": "UTF-8", "WE8ISO8859P1": "ISO-8859-1", "WE8ISO8859P15": "ISO-8859-15",
              "WE8MSWIN1252": "cp1252", "US7ASCII": "ascii"}
# The options of SQL*Loader that mean something here; every other only tunes a loader that is not run.
_READ = ("ROWS", "ERRORS", "SKIP", "LOAD")


def _options(value: List[Any]) -> Dict[str, str]:
    """The load options by name, from the list as the converter writes it: a name, then its value."""
    if len(value) % 2:
        raise ValueError("the options are a name and then its value, and the list has an odd number of entries")
    made = {str(name).strip().upper(): str(held).strip() for name, held in zip(value[::2], value[1::2])}
    for name in _READ:
        if name in made and not made[name].isdigit():
            raise ValueError(f"{name} is to be a whole number")
    return made


def _encoding(value: str) -> str:
    named = _ENCODINGS.get(value.strip().upper(), value.strip())
    try:
        codec_name(named)
    except ConfigurationError:
        raise ValueError(f"'{value}' is no encoding v2 knows: give Oracle's name (UTF8, WE8ISO8859P15, WE8MSWIN1252) "
                         "or Python's") from None
    return named


@REGISTRY.register
class OracleBulkExec(OracleOutput):
    """Store the rows of a file in a table of an Oracle database.

    With no flow leading to it, as in Talend, it reads the file `data`
    itself: delimited text with `terminator_value` between the fields,
    read as every delimited file is, by the declared columns and their
    patterns. With a flow leading to it, it stores that flow's rows.

    Talend's component runs SQL*Loader. Nothing of Oracle's is run here:
    the rows are stored as the Oracle output stores them, in batches
    inside a transaction, when the whole subjob has succeeded. A row
    that cannot be read as its declared type fails the job and names its
    line.

    `data_action` has SQL*Loader's meanings: `INSERT` needs the table to
    be empty, `APPEND` adds to what it holds, `REPLACE` deletes every row
    first (taken back with the rows when the subjob fails), `TRUNCATE`
    truncates first (not taken back).

    Of the load options, `ROWS` is the rows a round trip takes, `SKIP`
    the lines left out at the file's start, `LOAD` the most rows read,
    and `ERRORS` how many rows the database may refuse before the job
    fails; without it, the first refused row fails the job.

    It leaves `<id>_NB_LINE_DATA` (the rows it was handed),
    `_NB_LINE_BAD` (those the database refused), `_NB_LINE_INSERTED` and
    `_RETURN_CODE` (0, or 2 when rows were refused) in globalMap.
    """

    names = ("oracle_bulk_exec", "OracleBulkExec", "tOracleBulkExec")
    min_inputs = 0
    keys = (
        Key("table", default="", doc="The table."),
        Key("table_action", default=NONE, choices=(NONE, CLEAR) + tuple(action for action in _DEFINING if "REUSE" not in action),
            doc="What is done to the table first, as for the Oracle output."),
        Key("data_action", default=INSERT, choices=(INSERT, APPEND, REPLACE, TRUNCATE, "UPDATE"),
            doc="What the load does to the rows the table holds."),
        Key("data", default="", doc="The file to load, when no flow leads to it."),
        Key("fields_terminator", default="OTHER", doc="How a field ends: `OTHER`, by `terminator_value`."),
        Key("terminator_value", default=";", doc="What stands between the fields."),
        Key("use_fields_enclosure", type=bool, default=False,
            doc="Whether a field may be enclosed in double quotes, so that it can hold the terminator or a line end."),
        Key("encoding", default="UTF8", convert=_encoding, doc="The file's encoding, by Oracle's name or Python's."),
        Key("options", type=list, default=[], convert=_options,
            doc="The load options, a name and then its value: `ROWS`, `ERRORS`, `SKIP` and `LOAD` are read."),
        DIE_ON_ERROR,
        Key("advanced_separator", kind=Kind.REFUSED, type=object,
            reason="numbers are read with a point and no thousands separator; write the file so, or read it with a "
                   "delimited file input"),
        Key("use_existing_clt_file", kind=Kind.REFUSED, type=object,
            reason="a control file of SQL*Loader's is not read: no loader is run"),
        Key("input_into_table_clause", kind=Kind.REFUSED, type=object,
            reason="a clause of SQL*Loader's control file is not read: no loader is run"),
        Key("record_format", kind=Kind.REFUSED, type=object, off=("DEFAULT",),
            reason="only the default record format is read: a line a record"),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="See `advanced_separator`."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="See `advanced_separator`."),
        Key("clt_file", kind=Kind.IGNORED, type=object, doc="See `use_existing_clt_file`."),
        Key("use_date_pattern", kind=Kind.IGNORED, type=object, doc="A date is always read by its column's pattern."),
        Key("preserve_blanks", kind=Kind.IGNORED, type=object, doc="A value is stored as the file holds it."),
        Key("trailing_nullcols", kind=Kind.IGNORED, type=object, doc="A field a line lacks at its end is missing."),
        Key("nls_language", kind=Kind.IGNORED, type=object, doc="The engine reads the file; no loader's language matters."),
        Key("nls_date_language", kind=Kind.IGNORED, type=object, doc="See `nls_language`."),
        Key("nls_territory", kind=Kind.IGNORED, type=object, doc="See `nls_language`."),
        Key("set_nls_territory", kind=Kind.IGNORED, type=object, doc="See `nls_language`."),
        Key("output", kind=Kind.IGNORED, type=object, doc="Where SQL*Loader's own output goes; there is none."),
        Key("convert_column_table_to_uppercase", kind=Kind.IGNORED, type=object,
            doc="Names are written without quotes, and Oracle reads those in capitals."),
    ) + oracle.WORKING_KEYS + oracle.CONNECTION_KEYS

    def __init__(self, *given: Any) -> None:
        super().__init__(*given)
        # The load as the output it is: every row is inserted, in batches of the size the options say.
        options = self.config["options"] or {}
        self._action = self.config["data_action"]
        self._errors = int(options["ERRORS"]) if "ERRORS" in options else None
        self.config.update(data_action=INSERT, use_batch_size=True, batch_size=_rows(options.get("ROWS", 10000)))

    def problems(self) -> List[str]:
        config = self.config
        found = super().problems()
        if self._action == "UPDATE":
            found.append("data_action: a load updates no rows; use an Oracle output with `data_action` UPDATE")
        if self.fed:
            return found
        if not config["data"].strip():
            found.append("data: names no file, and no flow leads to it: it has no rows to store")
        if config["fields_terminator"] != "OTHER":
            found.append(f"fields_terminator: {config['fields_terminator']} is not read; fields end at `terminator_value` "
                         "(`OTHER`)")
        return found + [f"data: the file cannot be read as the keys say: {wrong}" for wrong in self._reader()[1]]

    def _reader(self) -> Tuple[FileInputDelimited, List[str]]:
        """The reader of the file `data`, a delimited file input set by this component's keys; and what is wrong
        with it as they set it."""
        config, options = self.config, self.config["options"] or {}
        asked = {"filepath": config["data"], "fieldseparator": config["terminator_value"], "row_separator": "\\n",
                 "header_rows": int(options.get("SKIP", 0)), "limit": options.get("LOAD"), "encoding": config["encoding"],
                 "csv_option": config["use_fields_enclosure"], "die_on_error": True}
        made, refusals = normalize_config(asked, FileInputDelimited.all_keys(), self.spec.where)
        reader = FileInputDelimited(dataclasses.replace(self.spec, cls=FileInputDelimited, schema=self.input_schema), made,
                                    self.run_context)
        reader.wired = {"main"}
        return reader, [f"{refusal.key}: {refusal.reason}" for refusal in refusals] + reader.problems()

    def rows(self) -> pl.LazyFrame:
        """The rows of the file `data`, read as a delimited file input reads them."""
        reader, _ = self._reader()
        read = reader.read()["main"]
        # What the reader asked to know of the rows is this component's to hear, and a row's place is the file's.
        self.taps += reader.taps
        self.noticed += reader.noticed
        self.run_context.sources[self.id] = reader
        return read

    # ------------------------------------------------------------------

    def _table_action(self) -> str:
        action = self.config["table_action"]
        if action != NONE:
            return action
        return {REPLACE: CLEAR, TRUNCATE: "TRUNCATE"}.get(self._action, NONE)

    def _defined(self, session: Session, table: str) -> None:
        super()._defined(session, table)
        if self._action == INSERT and self._table_action() in (NONE, "CREATE_IF_NOT_EXISTS"):
            import pyarrow

            held = next(iter(session.batches(f"select count(*) from {table}", {}, [pyarrow.int64()], 1)))
            if held.column(0)[0].as_py():
                raise DatabaseError("`data_action` INSERT has SQL*Loader's meaning: the table has to be empty, and it "
                                    "holds rows. APPEND adds to them, REPLACE deletes them first")

    def _gives_up(self, refused: int) -> bool:
        if self._errors is None:
            return self.config["die_on_error"]
        return refused > self._errors

    def _stored(self, scratch: str, rows: int) -> int:
        kept = super()._stored(scratch, rows)
        held = self.global_map
        held[f"{self.id}_NB_LINE_DATA"] = rows
        held[f"{self.id}_NB_LINE_BAD"] = rows - kept
        held[f"{self.id}_RETURN_CODE"] = 2 if kept < rows else 0
        return kept
