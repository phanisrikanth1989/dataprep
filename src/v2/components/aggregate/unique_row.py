"""Unique row: send the first row of each key one way and its duplicates another."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...rows import visible
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_DUPLICATE = "__duplicate"


def _column(value: str) -> str:
    if not value:
        raise ValueError("must not be empty")
    return value


def _named(item: Any) -> Any:
    """A key column written as a bare name, as the object it stands for."""
    return {"column": item} if isinstance(item, str) else item


def _keep(value: Any) -> Any:
    if value is False or value in ("first", "last"):
        return value
    raise ValueError(f"{value!r} is not allowed; use 'first', 'last' or false")


_KEY_COLUMN = (
    Key("column", required=True, convert=_column, doc="The column."),
    Key("case_sensitive", type=bool, nullable=True,
        doc="Whether upper and lower case differ in this column; the component's `case_sensitive` when left out."),
)


@REGISTRY.register
class UniqueRow(Transform):
    """Send the first row of each key to the unique output and the others to the duplicate output.

    Rows keep their input order on both outputs. Missing values are equal to
    each other as keys. The numbers of unique and duplicate rows are put in
    the globalMap as ``<id>_NB_UNIQUES`` and ``<id>_NB_DUPLICATES`` when
    something in the job reads them.
    """

    names = ("unique_row", "UniqueRow", "tUniqRow", "tUniqueRow", "tUnqRow")
    outputs = {"main": ("flow", "main", "unique"), "reject": ("duplicate", "reject")}
    keys = (
        Key("key_columns", type=list, default=[], items=_KEY_COLUMN, item_convert=_named,
            doc="The columns that make a row's key, as names or objects; every column when empty."),
        Key("keep", type=object, default="first", convert=_keep,
            doc="Which row of a key is the unique one: `first`, `last`, or false for no row of a repeated key."),
        Key("case_sensitive", type=bool, default=True,
            doc="Whether upper and lower case differ in the text key columns that do not say so themselves."),
        Key("only_once_each_duplicated_key", type=bool, default=False,
            doc="Whether only the first duplicate of each key leaves by the duplicate output."),
        Key("output_duplicates", type=bool, default=True,
            doc="Whether duplicate rows leave by the duplicate output at all."),
        Key("is_reject_duplicate", type=bool, default=True,
            doc="Whether the duplicate rows count as rejected rows (`<id>_NB_LINE_REJECT`)."),
        Key("is_virtual_component", kind=Kind.IGNORED, type=object,
            doc="Talend's work-on-disk switch; Polars decides."),
        Key("buffer_size", kind=Kind.IGNORED, type=object, doc="Talend's work-on-disk buffer."),
        Key("temp_directory", kind=Kind.IGNORED, type=object, doc="Talend's work-on-disk folder."),
        Key("change_hash_and_equals_for_bigdecimal", kind=Kind.IGNORED, type=object,
            doc="Decimals of equal value are always one key."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        config = self.config
        key = self._key(frame.collect_schema())
        if config["keep"] == "first":
            duplicate = ~key.is_first_distinct()
        elif config["keep"] == "last":
            duplicate = ~key.is_last_distinct()
        else:
            duplicate = key.is_duplicated()

        flagged = frame.with_columns(duplicate.alias(_DUPLICATE))
        self._every_duplicate = flagged.filter(pl.col(_DUPLICATE))
        if any(self.run_context.reads(f"{self.id}_{name}") for name in ("NB_UNIQUES", "NB_DUPLICATES")):
            self.tap(
                flagged.select(pl.len().alias("rows"), pl.col(_DUPLICATE).sum().alias("duplicates")), self._count
            )
        if not config["output_duplicates"]:
            duplicates = frame.clear()
        elif config["only_once_each_duplicated_key"]:
            first_of_key = pl.struct(key.alias("__key"), pl.col(_DUPLICATE)).is_first_distinct()
            duplicates = flagged.filter(pl.col(_DUPLICATE) & first_of_key).drop(_DUPLICATE)
        else:
            duplicates = flagged.filter(pl.col(_DUPLICATE)).drop(_DUPLICATE)
        return {"main": flagged.filter(~pl.col(_DUPLICATE)).drop(_DUPLICATE), "reject": duplicates}

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """As v1: every duplicate is a rejected row, whether or not it leaves by the duplicate output."""
        counts = super().line_counts(inputs, outputs)
        counts["NB_LINE_REJECT"] = [self._every_duplicate] if self.config["is_reject_duplicate"] else []
        return counts

    def _key(self, types: pl.Schema) -> pl.Expr:
        """What two rows must have in common to be duplicates of each other."""
        config = self.config
        # Without key columns two rows are duplicates when all their own columns agree; the hidden ones never do.
        sensitive = {name: config["case_sensitive"] for name in visible(types.names())}
        if config["key_columns"]:
            sensitive = {}
            for entry in config["key_columns"]:
                if entry["column"] not in types:
                    raise ConfigurationError(f"key_columns: there is no column '{entry['column']}'")
                own = entry["case_sensitive"]
                sensitive[entry["column"]] = config["case_sensitive"] if own is None else own

        parts: List[pl.Expr] = []
        for name, case_sensitive in sensitive.items():
            part = pl.col(name)
            if types[name] == pl.String and not case_sensitive:
                part = part.str.to_lowercase()
            elif types[name].is_float():
                part = part.fill_nan(None)
            parts.append(part)
        if len(parts) == 1:
            return parts[0]
        return pl.struct([part.alias(f"k{index}") for index, part in enumerate(parts)])

    def _count(self, found: pl.DataFrame) -> None:
        duplicates = int(found["duplicates"].item() or 0)
        uniques = int(found["rows"].item()) - duplicates
        self.global_map[f"{self.id}_NB_UNIQUES"] = uniques
        self.global_map[f"{self.id}_NB_DUPLICATES"] = duplicates
        logger.info(f"[{self.id}] unique={uniques} duplicate={duplicates}")
