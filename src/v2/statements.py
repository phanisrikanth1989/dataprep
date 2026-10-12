"""A statement as a job writes it, and what a database is given.

A statement may name context variables and entries of globalMap, as text
with `${context.name}` in it or as Talend joins it
(`"... where d = '" + context.d + "'"`). What such a reference holds is a
value, and no value may change what a statement does:

- A value that stands in quotes is bound. The database is handed the
  statement with a name in the value's place, and the value beside it.
- A value that stands outside quotes is written into the statement, and
  has to be a name, a number, or a list of names, numbers and texts in
  quotes. That is what a table, a column to sort by or the list of an
  `IN` are, and none of them can be bound.
- A statement that defines (`CREATE`, `ALTER`...) takes no bound value.
  There a value in quotes is written as text with its quotes doubled,
  which a database reads as that text and nothing else.

A statement that is nothing but one reference is what the reference
holds, as it is: the job says "run what this holds".

A statement that is run for each row of a flow may name the row's columns
where it is joined (`"... where id = " + row1.id`). A value of a row is
always bound, in quotes or out of them: the statement is one, and the rows
are its values. A prepared statement has a mark (`?`) for each value it
is given.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .engine.references import parsed
from .errors import ConfigurationError

_REFERENCE = re.compile(r"\$\{context\.(\w+)\}|\bcontext\.(\w+)\b")
# A double quote next to a plus, as Java joins text. (One written \\" is a quote of the statement's own.)
_JAVA_JOIN = re.compile(r'(?<!\\)"\s*\+|\+\s*"')
_JAVA = ("the statement is joined as Java joins text, and holds more than text, context variables and entries of "
         "globalMap: v2 runs no Java. Write it as one text, with ${context.name} where a value goes")
_NUMBER = r"[+-]?(?:\d+\.?\d*|\.\d+)"
_NAME = r"[A-Za-z][\w$#]*(?:\.[A-Za-z][\w$#]*)*"
_TEXT = r"'(?:[^']|'')*'"
_ITEM = rf"(?:{_NUMBER}|{_NAME}|{_TEXT})"
# What a value may be where no quotes stand round it.
_OUTSIDE = re.compile(rf"\s*{_ITEM}(?:\s*,\s*{_ITEM})*\s*")
# What a value may be between the quotes of a name.
_IN_A_NAME = re.compile(r"[\w$# .\-]+")
# The first word of a statement, past blanks and remarks.
_FIRST = re.compile(r"(?:\s+|--[^\n]*\n?|/\*.*?\*/)*([A-Za-z]+)", re.DOTALL)
# The first words of the statements that define: a database stores what was pending before one, and binds no value in one.
DEFINES = frozenset((
    "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "GRANT", "REVOKE", "COMMENT", "ANALYZE", "AUDIT", "NOAUDIT",
    "PURGE", "FLASHBACK", "ASSOCIATE", "DISASSOCIATE",
))
# The longest name a value is bound under: what every Oracle still in use takes.
_LONGEST = 30
_PAIRS = {"[": "]", "{": "}", "(": ")", "<": ">"}
# The name a column of the row goes by, as a context variable of that name, while a joined statement is read.
_ROW = "v2_row_column_"
_JAVA_TEXT = r'"(?:[^"\\]|\\.)*"'


@dataclass(frozen=True)
class Bound:
    """A value a database is handed beside its statement.

    Attributes:
        name: The name that stands for it in the statement.
        value: The value; None for one that each row brings.
        column: For a value of the row the statement is run for: the
            column it is.
    """

    name: str
    value: Any
    column: Optional[str] = None


@dataclass(frozen=True)
class Given:
    """What a mark (`?`) of a prepared statement stands for: a value, or a column of the row."""

    value: Any = None
    column: Optional[str] = None


@dataclass(frozen=True)
class _Value:
    """A value met while a statement is taken apart: the words that name it, and what it holds or which column
    of the row it is."""

    label: str
    held: Any = None
    column: Optional[str] = None


class _Join:
    """Where a database joins two texts: `||` for one, `+` for another."""


_JOIN = _Join()


@dataclass
class Statement:
    """A statement ready for a database.

    Attributes:
        parts: Its text, the values bound in it, and where two texts are
            joined, in order.
        defines: Whether it is a statement that defines.
        pasted: For one that defines: its text with every value written in.
    """

    parts: List[Any]
    defines: bool = False
    pasted: Optional[str] = None

    def named(self) -> Tuple[str, Dict[str, str]]:
        """The statement with each value under its name (`:name`), and the values by name. Oracle's way."""
        if self.pasted is not None:
            return self.pasted, {}
        return self.shown(), {part.name: part.value for part in self.parts if isinstance(part, Bound)}

    def by_place(self) -> Tuple[str, List[Bound]]:
        """The statement with a place of its own for each value (`:1`, `:2`...), and what stands at each: for a
        statement run once for each row of a batch."""
        bound = [part for part in self.parts if isinstance(part, Bound)]
        places = iter(range(1, len(bound) + 1))
        text = "".join(f":{next(places)}" if isinstance(part, Bound) else " || " if part is _JOIN else part
                       for part in self.parts)
        return text, bound

    def placed(self) -> Tuple[str, List[str]]:
        """The statement with a `?` for each value, and the values in order; texts are joined with `+`."""
        text = "".join("?" if isinstance(part, Bound) else " + " if part is _JOIN else part for part in self.parts)
        return text, [part.value for part in self.parts if isinstance(part, Bound)]

    def shown(self) -> str:
        """The statement as a log may show it: the names of its values, and never a value."""
        return "".join(f":{part.name}" if isinstance(part, Bound) else " || " if part is _JOIN else part
                       for part in self.parts)


def read(
    written: str,
    context: Mapping[str, Any],
    global_map: Mapping[str, Any],
    row: Optional[Tuple[str, List[str]]] = None,
    parameters: Optional[List[Given]] = None,
) -> Statement:
    """Read a statement as a job config has it.

    Args:
        written: The statement.
        context: The run's context variables.
        global_map: The run's globalMap entries.
        row: For a statement run for each row of a flow: the flow's name
            and the columns of its rows.
        parameters: For a prepared statement: what each of its marks
            (`?`) stands for, in their order.

    Raises:
        ConfigurationError: When it names what is not there, holds Java
            that is more than joining, or a value stands where it could
            change what the statement does. No message shows a value.
    """
    pieces = _pieces(written, context, global_map, row)
    if len(pieces) == 1 and isinstance(pieces[0], _Value) and pieces[0].column is None:
        if not isinstance(pieces[0].held, str):
            raise ConfigurationError(f"what {pieces[0].label} holds is no statement: it is no text")
        return Statement([pieces[0].held], defines=_defines(pieces[0].held))
    defines = _defines("".join(piece for piece in pieces if isinstance(piece, str)))
    bound = _Writer(False, parameters).written(pieces)
    pasted = "".join(_Writer(True, parameters).written(pieces)) if defines else None
    return Statement(bound, defines, pasted)


def unreadable(written: str, row: Optional[Tuple[str, List[str]]] = None) -> Optional[str]:
    """Why a statement cannot be read whatever the context holds; None when it can. For the check at load."""
    if parsed(_with_row(written, row)) is None and _joined(written, row) is None and _JAVA_JOIN.search(written):
        return _JAVA
    return None


# ------------------------------------------------------------------
# Taking a statement apart
# ------------------------------------------------------------------

def _joined(written: str, row: Optional[Tuple[str, List[str]]] = None) -> Optional[List[Any]]:
    """The terms of a statement the converter took the outermost quotes off; None when it is no joined text."""
    joined = parsed(_with_row(f'"{written}"', row))
    return joined if joined is not None and len(joined) > 1 else None


def _with_row(written: str, row: Optional[Tuple[str, List[str]]]) -> str:
    """A joined statement with each column of the row it names (`row1.id`) written as a term that can be read.

    Only where Java joins: between Java's quotes such a name is the statement's own (a table given that name).
    """
    if row is None:
        return written
    named = re.compile(rf'{_JAVA_TEXT}|(?<![\w.]){re.escape(row[0])}\.(\w+)\b')
    return named.sub(lambda found: found.group(0) if found.group(1) is None else f"context.{_ROW}{found.group(1)}", written)


def _pieces(written: str, context: Mapping[str, Any], global_map: Mapping[str, Any],
            row: Optional[Tuple[str, List[str]]] = None) -> List[Any]:
    """A statement as its texts and, between them, each value with the words that name it."""
    terms = parsed(_with_row(written, row))
    if terms is None:
        # The converter takes the outermost quotes off what Talend wrote as one joined text.
        terms = _joined(written, row)
    pieces: List[Any] = []
    if terms is None:
        if _JAVA_JOIN.search(written):
            raise ConfigurationError(_JAVA)
        at = 0
        for found in _REFERENCE.finditer(written):
            name = found.group(1) or found.group(2)
            if name not in context:
                if found.group(1) is None:
                    # Written bare, and no variable: it may be a column of a table called context.
                    continue
                raise ConfigurationError(f"context has no variable '{name}'")
            pieces += [written[at:found.start()], _Value(f"context.{name}", context[name])]
            at = found.end()
        pieces.append(written[at:])
    else:
        for kind, name in terms:
            if kind == "text":
                pieces.append(name)
            elif kind == "variable" and name.startswith(_ROW):
                flow, columns = row
                column = name[len(_ROW):]
                if column not in columns:
                    raise ConfigurationError(f"the rows of {flow} have no column '{column}'; they have: {', '.join(columns)}")
                pieces.append(_Value(f"{flow}.{column}", column=column))
            elif kind == "variable":
                if name not in context:
                    raise ConfigurationError(f"context has no variable '{name}'")
                pieces.append(_Value(f"context.{name}", context[name]))
            else:
                if name not in global_map:
                    raise ConfigurationError(f"globalMap has no entry '{name}'")
                pieces.append(_Value(f"the entry '{name}' of globalMap", global_map[name]))
    # Texts that stand side by side are one text: a quote that ends one may be half of a pair.
    merged: List[Any] = []
    for piece in pieces:
        if isinstance(piece, str) and merged and isinstance(merged[-1], str):
            merged[-1] += piece
        elif piece != "":
            merged.append(piece)
    return merged


def _defines(text: str) -> bool:
    first = _FIRST.match(text)
    return first is not None and first.group(1).upper() in DEFINES


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


class _Writer:
    """Goes through a statement and writes what a database is given: each value by where it stands.

    Args:
        paste: Whether a value in quotes is written into its text, quotes
            doubled, and not bound: for a statement that defines.
        parameters: What each mark (`?`) stands for; None when the
            statement is not a prepared one, and a mark is left as it is.
    """

    def __init__(self, paste: bool, parameters: Optional[List[Given]] = None) -> None:
        self.paste = paste
        self.parameters = parameters
        self.marks = 0
        self.out: List[Any] = []
        # Where it stands: in the statement itself (code), in a text in quotes, in the quotes of a name, in a
        # remark to the end of the line or between its marks, or in a text written q'...'.
        self.state = "code"
        # In a text in quotes: whether nothing stands in it yet, and whether a value stands before where it is at.
        self.fresh = False
        self.joined = False
        # The two characters that end a text written q'...'.
        self.ends = ""
        self.names: Dict[str, Tuple[str, str]] = {}
        self.made = 0

    def written(self, pieces: List[Any]) -> List[Any]:
        for piece in pieces:
            if isinstance(piece, str):
                self._text(piece)
            else:
                self._value(piece)
        if self.parameters is not None and self.marks != len(self.parameters):
            raise ConfigurationError(
                f"the statement has {self.marks} marks (?) and {len(self.parameters)} value(s) are given for them")
        return self.out

    # ------------------------------------------------------------------

    def _text(self, piece: str) -> None:
        at, size = 0, len(piece)
        while at < size:
            char, pair = piece[at], piece[at:at + 2]
            step = 1
            if self.state == "code":
                if char == "'":
                    if self._opens_other_quotes(piece, at):
                        opener = piece[at + 1:at + 2]
                        self.state, self.ends = "other", _PAIRS.get(opener, opener) + "'"
                    else:
                        self.state, self.fresh, self.joined = "text", True, False
                elif char == '"':
                    self.state = "name"
                elif pair == "--":
                    self.state, step = "line", 2
                elif pair == "/*":
                    self.state, step = "block", 2
                elif char == "?" and self.parameters is not None:
                    self._mark()
                    at += 1
                    continue
            elif self.state == "text":
                if pair == "''":
                    step, self.fresh = 2, False
                elif char == "'":
                    self.state = "code"
                    if self.fresh and self.joined:
                        # A value ended the text: the text that was opened after it holds nothing, and goes.
                        del self.out[-2:]
                        at += 1
                        continue
                else:
                    self.fresh = False
            elif self.state == "name":
                if char == '"':
                    self.state = "code"
            elif self.state == "line":
                if char == "\n":
                    self.state = "code"
            elif self.state == "block":
                if pair == "*/":
                    self.state, step = "code", 2
            elif pair == self.ends:
                self.state, step = "code", 2
            self.out.append(piece[at:at + step])
            at += step

    def _opens_other_quotes(self, piece: str, at: int) -> bool:
        """Whether a quote opens a text written q'[...]': a q stands before it, and is no end of a name."""
        before = ("".join(part for part in self.out[-3:] if isinstance(part, str)) + piece[:at])[-3:]
        if before[-1:] not in ("q", "Q"):
            return False
        rest = before[:-1]
        if rest[-1:] in ("n", "N"):
            rest = rest[:-1]
        return not re.search(r"[\w$#]$", rest)

    def _mark(self) -> None:
        """A mark of a prepared statement: the value given for its place is bound there."""
        self.marks += 1
        if self.paste:
            raise ConfigurationError("a statement that defines takes no bound value, and this one has a mark (?)")
        if self.marks <= len(self.parameters or []):
            given = self.parameters[self.marks - 1]
            self.out.append(Bound(f"p{self.marks}", given.value, given.column))

    def _of_the_row(self, value: _Value) -> None:
        """A value of the row the statement is run for: bound where it stands, in quotes or out of them."""
        if self.paste:
            raise ConfigurationError("a statement that defines takes no bound value, and a value of a row can only "
                                     f"be bound: {value.label} cannot stand in this one")
        if self.state not in ("code", "text"):
            raise ConfigurationError(f"{value.label} stands where no value can be bound: in a remark, or between "
                                     "the quotes of a name")
        bound = Bound(re.sub(r"\W", "_", value.label), None, value.column)
        if self.state == "code":
            self.out.append(bound)
        else:
            self._joined_in(bound)

    def _joined_in(self, bound: Bound) -> None:
        """A bound value in a text in quotes: all of the text, or joined to the rest of it by the database."""
        if self.fresh:
            # Nothing stands in the text yet: its opening quote goes, and the value takes its place.
            del self.out[-1]
        else:
            self.out += ["'", _JOIN]
        self.out += [bound, _JOIN, "'"]
        self.fresh, self.joined = True, True

    def _value(self, value: _Value) -> None:
        if value.column is not None:
            self._of_the_row(value)
            return
        label, text = value.label, _as_text(value.held)
        if self.state == "other":
            raise ConfigurationError(
                f"{label} stands inside a text written q'...': write that text with plain quotes, so that the value "
                "can be bound")
        if self.state == "name":
            if not _IN_A_NAME.fullmatch(text):
                raise ConfigurationError(
                    f"what {label} holds is written between the quotes of a name, and there it has to be a name: "
                    "letters, digits, blanks, and `_`, `$`, `#`, `.`, `-`; it is not")
            self.out.append(text)
        elif self.state != "text":
            if not _OUTSIDE.fullmatch(text):
                raise ConfigurationError(
                    f"what {label} holds is written into the statement, since no quotes stand round it, and there it "
                    "has to be a name, a number, or a list of names, numbers and texts in quotes; it is none of "
                    "these. A value in quotes is bound, whatever it holds")
            self.out.append(text.strip())
        elif self.paste:
            self.out.append(text.replace("'", "''"))
            self.fresh = False
        else:
            self._joined_in(Bound(self._name(label), text))

    def _name(self, label: str) -> str:
        """The name a value is bound under: one for each thing that is named, and never the same for two."""
        if label in self.names:
            return self.names[label][0]
        kind = "context_" if label.startswith("context.") else "entry_"
        said = label[len("context."):] if kind == "context_" else label.split("'")[1]
        name = kind + re.sub(r"\W", "_", said)
        if len(name) > _LONGEST:
            self.made += 1
            name = f"v2_{self.made}"
        taken = {made for made, _ in self.names.values()}
        number = 2
        while name in taken:
            name = f"{kind}{re.sub(chr(92) + 'W', '_', said)}_{number}"
            number += 1
        self.names[label] = (name, label)
        return name
