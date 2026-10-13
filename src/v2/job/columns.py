"""The columns of a schema, as a job config declares them."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .keys import Key, Kind
from .model import TYPE_NAMES, Column


def not_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


def _places(value: int) -> Optional[int]:
    """Declared decimal places; a negative number is Talend's way to say none are declared."""
    return value if value >= 0 else None


COLUMN_KEYS: Tuple[Key, ...] = (
    Key("name", required=True, convert=not_empty, doc="The column name."),
    Key("type", default="str", choices=tuple(TYPE_NAMES), doc="The column type."),
    Key("nullable", type=bool, default=True, doc="Whether missing values are allowed."),
    Key("key", type=bool, default=False, doc="Whether the column is part of the key."),
    Key("length", type=int, doc="Declared length."),
    Key("precision", type=int, convert=_places,
        doc="Declared number of decimal places. A negative number, as Talend writes for none, means none."),
    Key("date_pattern", aliases=("pattern",), doc="strftime pattern for dates."),
    Key("default", kind=Kind.IGNORED, type=object, doc="Talend default value."),
    Key("comment", kind=Kind.IGNORED, type=object, doc="Free-form comment."),
    Key("original_type", kind=Kind.IGNORED, type=object, doc="The Talend type."),
)


def column_of(fields: Dict[str, Any]) -> Column:
    """A column from what `COLUMN_KEYS` made of its declaration."""
    return Column(
        name=fields["name"],
        type=TYPE_NAMES[fields["type"]],
        nullable=fields["nullable"],
        key=fields["key"],
        length=fields["length"],
        precision=fields["precision"],
        date_pattern=fields["date_pattern"] or None,
    )
