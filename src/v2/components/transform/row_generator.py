"""Row generator: rows made from expressions written in the job config."""
from __future__ import annotations

import ast
import io
import logging
import random
import re
import tokenize
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import polars as pl

from ...column_types import held_frame
from ...job.keys import Key, Kind, Looked, has_context_reference
from ...rows import hidden, visible
from ..base import Source, one_line
from ..registry import REGISTRY

if TYPE_CHECKING:
    from ...engine.context import RunContext

logger = logging.getLogger(__name__)

# A context variable in an expression: as `${context.x}`, or bare.
_REFERENCE = re.compile(r"\$\{context\.(\w+)\}|\bcontext\.(\w+)\b")
# The name that stands for one in the expression Python is given, and what is added to it for its value as text.
_NAME = "__v2_context_"
_TEXT = "t"
_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
# The text between the names of an f-string, as Python 3.12 and later tell it apart.
_FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", None)

_SPACE = re.compile(r"StringHandling\.SPACE\(([^)]+)\)")
_LEN = re.compile(r"StringHandling\.LEN\(([^)]+)\)")
_QUOTES = ('"', "'")
_WHY = "__row_generator_why"


def _count(value: Any) -> int:
    try:
        rows = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is not a whole number of rows") from None
    if rows < 0:
        raise ValueError(f"{rows} rows cannot be made; give 0 or more")
    return rows


def _length(match: "re.Match[str]") -> str:
    text = match.group(1).strip()
    if text[:1] in _QUOTES and text[-1:] == text[:1]:
        return str(len(text[1:-1]))
    return f"len({text})"


def _as_itself(text: str) -> str:
    """Text that is not Python, as the value it is: without the blanks and the quotes around it."""
    text = text.strip()
    if text[:1] in _QUOTES and text[-1:] == text[:1]:
        return text[1:-1]
    return text


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def _as_python(value: Any) -> Any:
    """What a context variable holds, as an expression has it: text that is a plain number is that number, as when
    v1 writes the text into the expression; any other text is text."""
    if isinstance(value, str) and _NUMBER.fullmatch(value.strip()):
        try:
            return ast.literal_eval(value.strip())
        except (ValueError, SyntaxError):
            # 007 is no number Python reads.
            pass
    return value


class _Expression:
    """One column's expression, read once and worked out for every row.

    A context variable the expression names is the value it holds and
    never text of the expression: each stands in the expression under a
    name of its own, and the value is handed to Python under that name.
    So what a variable holds is never run, whatever it looks like.
    """

    def __init__(self, written: Any, run_context: "RunContext") -> None:
        self.code = None
        # What was looked up while the job runs is the value, whatever it looks like: it is never read as Python.
        self.looked: Optional[Looked] = None
        # What the context variables in the expression hold, under the names that stand for them: as Python has
        # each, and under a second name as text.
        self.names: Dict[str, Any] = {}
        self._held: Dict[str, Any] = {}
        text = str(written)
        if isinstance(written, str) and has_context_reference(written):
            self.looked = run_context.named(written)
            if self.looked is not None:
                return
            text = self._named(written, run_context.context)
            alone = text.strip()
            while alone.startswith("(") and alone.endswith(")"):
                alone = alone[1:-1].strip()
            if alone in self._held:
                # One variable and nothing else: the value itself.
                self.looked = Looked(self._held[alone])
                return
        source = self._quoted(_LEN.sub(_length, _SPACE.sub(self._spaces, text)))
        self.text = self._written(source)
        try:
            # Blanks in front are not Python's business, as for v1's eval.
            self.code = compile(source.lstrip(" \t"), "<expression>", "eval")
        except SyntaxError:
            pass

    def value(self, reach: Dict[str, Any]) -> Any:
        """What the expression comes to for one row. Raises what the expression raises."""
        if self.looked is not None:
            return self.looked.value
        if self.code is None:
            return _as_itself(self.text)
        try:
            return eval(self.code, {**reach, **self.names} if self.names else reach)  # noqa: S307 -- only `random` is in reach, as in v1
        except NameError:
            return _as_itself(self.text)

    def _named(self, text: str, context: Dict[str, Any]) -> str:
        """The expression with a name of its own where each context variable stood."""

        def name(match: "re.Match[str]") -> str:
            variable = match.group(1) or match.group(2)
            if variable not in context:
                # Written bare, and no variable: left as it is, as in v1. (Written with ${}, it has failed the
                # component before this.)
                return match.group(0)
            made = f"{_NAME}{len(self._held)}__"
            self._held[made] = context[variable]
            self.names[made] = _as_python(context[variable])
            self.names[made + _TEXT] = _as_text(context[variable])
            return made

        return _REFERENCE.sub(name, text)

    def _written(self, text: str) -> str:
        """The expression as text, with what each variable holds where its name stands."""
        for name, held in self._held.items():
            text = text.replace(name, _as_text(held))
        return text

    def _spaces(self, match: "re.Match[str]") -> str:
        try:
            # Nothing is in reach but the numbers the context holds.
            return repr(" " * int(eval(match.group(1).strip(), {"__builtins__": {}, **self.names})))  # noqa: S307
        except Exception:  # noqa: BLE001 -- as v1: a count that cannot be worked out is no blanks
            return repr("")

    def _quoted(self, source: str) -> str:
        """The expression with every variable that stands inside quotes made part of that text."""
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (tokenize.TokenError, SyntaxError):
            # No Python: it is taken as itself.
            return source
        starts = [0]
        for line in source.splitlines(keepends=True):
            starts.append(starts[-1] + len(line))
        for token in reversed(tokens):
            if not any(name in token.string for name in self._held):
                continue
            if token.type == tokenize.STRING:
                held = ast.literal_eval(token.string)
                if isinstance(held, bytes):
                    for name, value in self._held.items():
                        held = held.replace(name.encode(), _as_text(value).encode("utf-8"))
                    made = repr(held)
                else:
                    made = repr(self._written(held))
            elif token.type == _FSTRING_MIDDLE:
                # The text of an f-string: the variable is named there, as the text it holds.
                made = token.string
                for name in self._held:
                    made = made.replace(name, "{" + name + _TEXT + "}")
            else:
                continue
            start = starts[token.start[0] - 1] + token.start[1]
            end = starts[token.end[0] - 1] + token.end[1]
            source = source[:start] + made + source[end:]
        return source


_VALUE = (
    Key("schema_column", required=True, doc="The column."),
    Key("array", type=object, default="", nullable=True, reads_references=True,
        doc="The expression every row's value comes from."),
)


@REGISTRY.register
class RowGenerator(Source):
    """Make `nb_rows` rows, each column from the expression `values` gives it.

    An expression is Python with no name to call on but the `random`
    module: `1 + 2`, `'ann'`, `random.randint(1, 100)`. (That is what v1
    gives it. It is no fence: Python code can reach anything from there,
    and a job config is trusted as code is.) As in v1, text that is not
    Python (`hello world`, `2024-01-31`, `007`), or that names something
    not in reach (`len('abc')`), is the value itself, as text, without the
    quotes around it. `StringHandling.SPACE(3)` is three blanks and
    `StringHandling.LEN("ab")` is 2. A column with no expression is missing.

    A value that is looked up while the job runs is the value itself and
    never an expression: the name of a file or what another job handed
    over is data, whatever it looks like. That holds for an entry of
    globalMap (`globalMap.get("KEY")`, alone or joined to text) and for a
    context variable. A context variable that stands alone (`context.x`,
    `${context.x}`) is what it holds, as it is. Inside an expression it
    is that value too: text is text, and text that is a plain number is
    the number (`${context.n} + 1`). Inside quotes it is part of that
    text. What a variable holds is never run as Python.

    A row with an expression that fails (`1/0`) leaves by the reject output
    with that column missing (false, in a true/false column) and nothing
    added, as in v1; the log says how
    many such rows there are and what failed in the first. With no flow on
    the reject output they are dropped, and the log warns of it.

    The rows are worked out row by row, column after column, and held in
    memory. They are made once in a run, however often the engine reads
    the source. A failure names a row as `row 3 of <id>`.
    """

    names = ("row_generator", "RowGenerator", "tRowGenerator")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("nb_rows", type=object, default=100, convert=_count, doc="How many rows are made."),
        Key("values", type=list, required=True, items=_VALUE, doc="Each column with its expression."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
        Key("requires_java_bridge", kind=Kind.IGNORED, type=object,
            doc="The converter's note that the expressions were Java; an expression that still is refuses the job."),
    )

    def problems(self) -> List[str]:
        if not self.schema:
            return ["schema: a row generator needs its columns declared"]
        names = [column.name for column in self.schema]
        found, seen = [], {}
        for at, entry in enumerate(self.config["values"]):
            name = entry["schema_column"]
            if name not in names:
                found.append(f"values[{at}].schema_column: '{name}' is not a column of the schema ({', '.join(names)})")
            elif name in seen:
                found.append(f"values[{at}].schema_column: '{name}' already has an expression (values[{seen[name]}])")
            seen.setdefault(name, at)
        return found

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        made = self.run_context.made
        if self.id not in made:
            made[self.id] = self._made()
        frame = self.picked(made[self.id]).with_columns(self.key_copies())
        flagged = frame.select(visible(frame.columns) + hidden(frame.columns)).lazy()
        failed = pl.col(_WHY).is_not_null()
        flagged = self.tell_dropped(flagged, failed, pl.col(_WHY))
        return {"main": flagged.filter(~failed).drop(_WHY), "reject": flagged.filter(failed).drop(_WHY)}

    def locate(self, number: int) -> str:
        return f"row {number} of {self.id}"

    @property
    def place_kind(self) -> str:
        return "rows"

    @property
    def place_why(self) -> str:
        return "makes its rows itself"

    def _made(self) -> pl.DataFrame:
        """Every row, numbered, with what failed in it where something did."""
        expressions: List[Tuple[str, _Expression]] = [
            (entry["schema_column"], _Expression(entry["array"], self.run_context)) for entry in self.config["values"]
        ]
        reach = {"__builtins__": {}, "random": random}
        # True or false with no expression at all is false, as in v1, also where it may not be missing.
        given = {name for name, _ in expressions}
        unsaid = {column.name: "" for column in self.schema if column.type == "bool" and column.name not in given}
        rows: List[Dict[str, Any]] = []
        why: List[Optional[str]] = []
        for _ in range(self.config["nb_rows"]):
            row: Dict[str, Any] = dict(unsaid)
            failures: List[str] = []
            for name, expression in expressions:
                try:
                    row[name] = expression.value(reach)
                except Exception as exc:  # noqa: BLE001 -- whatever the expression raises rejects the row
                    failures.append(f"{name}: {exc}")
            rows.append(row)
            why.append("; ".join(failures) if failures else None)
        failed = [at for at, said in enumerate(why) if said is not None]
        if failed:
            logger.info(one_line(
                f"[{self.id}] an expression failed in {len(failed)} of {len(rows)} rows; "
                f"the first is row {failed[0] + 1}: {why[failed[0]]}"
            ))
        return held_frame(self.schema, rows).with_columns(
            pl.Series(_WHY, why, dtype=pl.String),
            pl.Series(self.row_number, range(1, len(rows) + 1), dtype=pl.UInt32),
        )
