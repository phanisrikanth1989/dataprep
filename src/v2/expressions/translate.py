"""Translate a Python expression into a Polars expression.

An expression in a job config is Python to read and Polars to run: it is
parsed once, when the job loads, and every node of its syntax tree is mapped
to a native Polars expression. Nothing is evaluated row by row. Python that
has no Polars form is refused with a message naming the part that cannot be
translated.

Where Polars and row-by-row Python disagree, the choice made here is:

- A missing value does not raise. Arithmetic, text operations and ordering
  comparisons on a missing value give a missing value.
- ``==`` and ``!=`` treat a missing value as a value, as Python does with
  ``None``: ``x == None`` is true for a missing ``x``.
- ``and``, ``or``, ``not`` and any value used as a condition follow Python's
  truthiness for the operand's type (zero, empty text and missing are false).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, NoReturn, Optional

import polars as pl

from ..errors import ExpressionError

NOT_CONSTANT = object()

_JAVA_HINTS = (
    ("&&", "write `and` instead of `&&`"),
    ("||", "write `or` instead of `||`"),
    ("?", "write `a if condition else b` instead of `condition ? a : b`"),
    ("!", "write `not` instead of `!`"),
)
_NAME_HINTS = {
    "null": "write None",
    "NULL": "write None",
    "true": "write True",
    "false": "write False",
}


@dataclass
class Fallible:
    """A conversion in an expression that can fail on a row.

    Polars would raise on the first such row and say only which value it
    was. The conversion is built so that it gives nothing where it fails,
    and this says which rows those are, for the component that asked for
    the translation to check: it then holds the row and can name it.

    Attributes:
        failed: True for a row on which the conversion is worked out and
            cannot be made. Never missing.
        what: The conversion as a message names it: ``int()``.
        value: What the conversion was handed, on every row.
        source: The expression it is written in.
        where: The config key that holds the expression, for the message;
            set by the component that asked for the translation.
    """

    failed: pl.Expr
    what: str
    value: pl.Expr
    source: str
    where: str = "expression"


@dataclass
class Scope:
    """What an expression may refer to.

    Attributes:
        columns: The columns of the frame the expression runs on, with types.
        rows: Row name to its columns, each mapped to the frame column that
            holds it. ``row1.price`` is looked up here.
        bare: A row whose columns may also be written without the row name.
        variables: Already translated variables, read as ``Var.name``.
        context: Context values, read as ``context.name``.
        global_map: globalMap entries, read as ``globalMap.get("name")``.
        routines: Routine modules, each a mapping of function name to a
            function that takes and returns Polars expressions.
        failures: The conversions that can fail on a row, noted by every
            translation made with this scope. The component that asked
            checks them on the rows the expressions run on.
    """

    columns: Dict[str, pl.DataType]
    rows: Dict[str, Dict[str, str]]
    bare: Optional[str] = None
    variables: Dict[str, pl.Expr] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)
    global_map: Mapping[str, Any] = field(default_factory=dict)
    routines: Mapping[str, Mapping[str, Callable[..., pl.Expr]]] = field(default_factory=dict)
    failures: List[Fallible] = field(default_factory=list)

    @classmethod
    def for_rows(
        cls,
        rows: Mapping[str, Mapping[str, pl.DataType]],
        bare: Optional[str] = None,
        **more: Any,
    ) -> "Scope":
        """Build a scope from named rows.

        The first row's columns keep their names in the frame. Columns of any
        further row are held as ``<row>.<column>``, the way a joined lookup's
        columns are named.
        """
        columns: Dict[str, pl.DataType] = {}
        mapping: Dict[str, Dict[str, str]] = {}
        for position, (row, row_columns) in enumerate(rows.items()):
            mapping[row] = {}
            for name, dtype in row_columns.items():
                physical = name if position == 0 else f"{row}.{name}"
                columns[physical] = dtype
                mapping[row][name] = physical
        return cls(columns=columns, rows=mapping, bare=bare, **more)


def _kind(dtype: pl.DataType) -> str:
    """The broad kind of a type, for telling whether two values can mix."""
    if dtype == pl.Null:
        return "missing"
    if dtype == pl.String:
        return "text"
    if dtype == pl.Boolean:
        return "true/false value"
    if dtype.is_numeric():
        return "number"
    if isinstance(dtype, pl.Duration):
        return "duration"
    if dtype.is_temporal():
        return "date"
    return str(dtype)


def translate(text: str, scope: Scope) -> pl.Expr:
    """Translate one Python expression into a Polars expression.

    Raises:
        ExpressionError: When the text is not a Python expression, or holds
            something that has no Polars form.
    """
    return Translator(text, scope).run()


def translate_condition(text: str, scope: Scope) -> pl.Expr:
    """Translate a Python expression used as a condition.

    The result is true or false by Python's rules of truth (zero, empty text
    and a missing value are false) and is never missing, so it can filter
    rows as it is.

    Raises:
        ExpressionError: As ``translate``.
    """
    translator = Translator(text, scope)
    return translator.truth(translator.parse())


class Translator:
    """Walks one expression's syntax tree. See ``translate``."""

    def __init__(self, text: str, scope: Scope) -> None:
        self.source = text.strip()
        self.scope = scope
        self._probe = pl.LazyFrame(schema=dict(scope.columns))
        # The conditions under which the part being translated is worked out at all, outermost first.
        self._guards: List[pl.Expr] = []

    def run(self) -> pl.Expr:
        """Parse the text and translate it."""
        return self.value(self.parse())

    def parse(self) -> ast.AST:
        """The expression's syntax tree, or a refusal saying why the text is not a Python expression."""
        if self.source.startswith("{{java}}"):
            raise ExpressionError(self.source, "Java expressions are not run by v2; rewrite it in Python")
        try:
            return ast.parse(self.source, mode="eval").body
        except SyntaxError as exc:
            hints = [hint for token, hint in _JAVA_HINTS if token in self.source.replace("!=", "")]
            reason = f"not a valid Python expression ({exc.msg})"
            if hints:
                reason += "; " + "; ".join(hints)
            raise ExpressionError(self.source, reason) from None

    # ------------------------------------------------------------------
    # Helpers used by the function tables
    # ------------------------------------------------------------------

    def fallible(self, what: str, value: pl.Expr, made: pl.Expr) -> pl.Expr:
        """Note a conversion that gives nothing where it fails, and hand its result on.

        A row fails when the conversion was handed a value and made nothing
        of it, and only where Python would have worked the conversion out
        at all: not behind an ``and`` that was already false or an ``or``
        that was already true, and not in the branch of an ``if`` that was
        not taken. A missing value is not a failure: it stays missing.

        Args:
            what: The conversion, as a message names it: ``int()``.
            value: What it was handed.
            made: Its result, missing where it failed.
        """
        failed = value.is_not_null() & made.is_null()
        for guard in self._guards:
            failed = guard & failed
        self.scope.failures.append(Fallible(failed, what, value, self.source))
        return made

    def fail(self, node: ast.AST, reason: str) -> NoReturn:
        """Refuse the expression, quoting the part that cannot be translated."""
        segment = ast.get_source_segment(self.source, node) or self.source
        raise ExpressionError(self.source, f"`{segment}`: {reason}")

    def dtype(self, expr: pl.Expr, node: ast.AST) -> pl.DataType:
        """The type Polars gives an expression on this scope's frame."""
        try:
            return self._probe.select(expr.alias("_")).collect_schema()["_"]
        except Exception as exc:  # noqa: BLE001 -- any Polars complaint is a refusal
            self.fail(node, str(exc).strip().splitlines()[0])

    def const(self, node: ast.AST) -> Any:
        """The Python value of a node known when the job loads, or NOT_CONSTANT."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            inner = self.const(node.operand)
            if isinstance(inner, (int, float)) and not isinstance(inner, bool):
                return -inner if isinstance(node.op, ast.USub) else inner
            return NOT_CONSTANT
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            items = [self.const(item) for item in node.elts]
            return NOT_CONSTANT if any(item is NOT_CONSTANT for item in items) else items
        owner, name = self._owner_and_name(node)
        if owner == "context":
            return self._lookup(node, self.scope.context, name, "context has no variable")
        if owner == "globalMap":
            return self._lookup(node, self.scope.global_map, name, "globalMap has no entry")
        return NOT_CONSTANT

    def need_const(self, node: ast.AST, what: str) -> Any:
        """A constant, or a refusal saying what had to be one."""
        found = self.const(node)
        if found is NOT_CONSTANT:
            self.fail(node, f"{what} must be a constant, not a value that changes per row")
        return found

    def truthy(self, expr: pl.Expr, node: ast.AST) -> pl.Expr:
        """Python's truth of a value, as a Boolean that is never missing."""
        dtype = self.dtype(expr, node)
        if dtype == pl.Boolean:
            return expr.fill_null(False)
        if dtype == pl.Null:
            return pl.lit(False)
        if dtype == pl.String:
            return (expr != "").fill_null(False)
        if dtype.is_numeric():
            return (expr != 0).fill_null(False)
        if dtype.is_temporal():
            return expr.is_not_null()
        self.fail(node, f"a {dtype} value cannot be used as a condition")

    def truth(self, node: ast.AST) -> pl.Expr:
        """Translate a node used as a condition."""
        if isinstance(node, ast.BoolOp):
            both = isinstance(node.op, ast.And)
            held = len(self._guards)
            combined: Optional[pl.Expr] = None
            for value in node.values:
                part = self.truth(value)
                if combined is None:
                    combined = part
                else:
                    combined = (combined & part) if both else (combined | part)
                # Python goes on to the next part only after a true part of an `and`, a false part of an `or`.
                self._guards.append(part if both else ~part)
            del self._guards[held:]
            return combined
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return ~self.truth(node.operand)
        return self.truthy(self.value(node), node)

    def value(self, node: ast.AST) -> pl.Expr:
        """Translate a node used as a value."""
        handler = getattr(self, "_" + type(node).__name__, None)
        if handler is None:
            self.fail(node, "this kind of Python has no Polars form")
        return handler(node)

    def args(self, node: ast.Call, low: int, high: int) -> List[ast.AST]:
        """A call's positional arguments, refused when their number is wrong."""
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            self.fail(node, "keyword and starred arguments are not supported here")
        if not low <= len(node.args) <= high:
            wanted = str(low) if low == high else f"{low} to {high}"
            self.fail(node, f"takes {wanted} argument(s), got {len(node.args)}")
        return list(node.args)

    # ------------------------------------------------------------------
    # Names and constants
    # ------------------------------------------------------------------

    def _Constant(self, node: ast.Constant) -> pl.Expr:
        if node.value is None or isinstance(node.value, (bool, int, float, str)):
            return pl.lit(node.value)
        self.fail(node, "this kind of constant is not supported")

    def _Name(self, node: ast.Name) -> pl.Expr:
        name = node.id
        if self.scope.bare is not None and name in self.scope.rows[self.scope.bare]:
            return pl.col(self.scope.rows[self.scope.bare][name])
        if name in self.scope.rows:
            self.fail(node, f"a row is not a value; name one of its columns, as in {name}.column")
        if name in _NAME_HINTS:
            self.fail(node, f"unknown name '{name}'; {_NAME_HINTS[name]}")
        rows = ", ".join(self.scope.rows) or "none"
        self.fail(node, f"unknown name '{name}'; rows here: {rows}")

    def _Attribute(self, node: ast.Attribute) -> pl.Expr:
        named = self._named(node)
        if named is not None:
            return named
        from .functions import ATTRIBUTES, CONSTANTS, dotted  # late: the tables use this class

        name = dotted(node)
        if name in CONSTANTS and not self._owns_columns(name.split(".")[0]):
            return pl.lit(CONSTANTS[name])
        target = self.value(node.value)
        handler = ATTRIBUTES.get(node.attr)
        if handler is None:
            self.fail(node, f"unknown attribute '.{node.attr}'")
        return handler(self, node, target)

    def _Subscript(self, node: ast.Subscript) -> pl.Expr:
        named = self._named(node)
        if named is not None:
            return named
        from .functions import subscript

        return subscript(self, node)

    def _owner_and_name(self, node: ast.AST):
        """Split ``owner.name`` or ``owner['name']`` when owner is a plain name."""
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return node.value.id, node.attr
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            return node.value.id, node.slice.value
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "globalMap"
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            return "globalMap", node.args[0].value
        return None, None

    def _lookup(self, node: ast.AST, values: Mapping[str, Any], name: str, missing: str) -> Any:
        if name in values:
            return values[name]
        if isinstance(node, ast.Call) and len(node.args) == 2:
            return self.need_const(node.args[1], "the default")
        self.fail(node, f"{missing} '{name}'")

    def _named(self, node: ast.AST) -> Optional[pl.Expr]:
        """Translate a reference to a column, variable, context or globalMap value."""
        owner, name = self._owner_and_name(node)
        if owner is None:
            return None
        if owner in self.scope.rows:
            columns = self.scope.rows[owner]
            if name not in columns:
                self.fail(node, f"{owner} has no column '{name}'; it has: {', '.join(columns) or 'none'}")
            return pl.col(columns[name])
        if owner == "Var":
            if name not in self.scope.variables:
                self.fail(node, f"no variable '{name}' is defined before this expression")
            return self.scope.variables[name]
        if owner in ("context", "globalMap"):
            return pl.lit(self.const(node))
        return None

    # ------------------------------------------------------------------
    # Operators
    # ------------------------------------------------------------------

    def _BinOp(self, node: ast.BinOp) -> pl.Expr:
        left, right = self.value(node.left), self.value(node.right)
        left_type, right_type = self.dtype(left, node.left), self.dtype(right, node.right)
        texts = (left_type == pl.String) + (right_type == pl.String)
        if isinstance(node.op, ast.Add):
            if texts == 1 and pl.Null not in (left_type, right_type):
                self.fail(node, "cannot add text and a number; wrap the number in str(...)")
            return self._checked(left + right, node)
        if texts:
            self.fail(node, "this operator does not work on text")
        if isinstance(node.op, ast.Sub):
            return self._checked(left - right, node)
        if isinstance(node.op, ast.Mult):
            return self._checked(left * right, node)
        if isinstance(node.op, ast.Div):
            return self._checked(self._divided(left, left_type, right), node)
        if isinstance(node.op, ast.FloorDiv):
            return self._checked(left // right, node)
        if isinstance(node.op, ast.Mod):
            return self._checked(left % right, node)
        if isinstance(node.op, ast.Pow):
            return self._checked(left.pow(right), node)
        self.fail(node, "this operator is not supported")

    @staticmethod
    def _divided(left: pl.Expr, left_type: pl.DataType, right: pl.Expr) -> pl.Expr:
        """Python's ``/`` on floats and whole numbers.

        Polars divides by a value that is the same for every row by
        multiplying with its reciprocal, which differs from a true division
        in the last digit for many values (35 / 100 comes out as
        0.35000000000000003). A divisor that is a column is divided by
        exactly, so a constant divisor is spread over the rows first.
        """
        per_row = bool(right.meta.root_names())
        if per_row or not left.meta.root_names() or not (left_type.is_integer() or left_type.is_float()):
            return left / right
        return left / (left.is_null().cast(pl.Float64) * 0 + right)

    def _checked(self, expr: pl.Expr, node: ast.AST) -> pl.Expr:
        self.dtype(expr, node)
        return expr

    def _UnaryOp(self, node: ast.UnaryOp) -> pl.Expr:
        if isinstance(node.op, ast.Not):
            return ~self.truth(node.operand)
        operand = self.value(node.operand)
        if self.dtype(operand, node.operand) == pl.String:
            self.fail(node, "this operator does not work on text")
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        self.fail(node, "this operator is not supported")

    def _BoolOp(self, node: ast.BoolOp) -> pl.Expr:
        # A first translation to learn the types. What can fail in the parts is noted below, by the
        # translation that knows which rows reach each part.
        noted = len(self.scope.failures)
        types = [self.dtype(self.value(item), item) for item in node.values]
        del self.scope.failures[noted:]
        if all(dtype in (pl.Boolean, pl.Null) for dtype in types):
            return self.truth(node)
        both = isinstance(node.op, ast.And)
        held = len(self._guards)
        result, result_node = self.value(node.values[0]), node.values[0]
        for item in node.values[1:]:
            condition = self.truthy(result, result_node)
            self._guards.append(condition if both else ~condition)
            value = self.value(item)
            result, value = self._one_kind(node, result, result_node, value, item)
            if both:
                result = pl.when(condition).then(value).otherwise(result)
            else:
                result = pl.when(condition).then(result).otherwise(value)
            result_node = item
        del self._guards[held:]
        return self._checked(result, node)

    def _Compare(self, node: ast.Compare) -> pl.Expr:
        result: Optional[pl.Expr] = None
        left_node = node.left
        held = len(self._guards)
        for op, right_node in zip(node.ops, node.comparators):
            part = self._compare_pair(node, left_node, op, right_node)
            result = part if result is None else (result & part)
            # As Python, a chain stops at the first comparison that does not hold: what stands
            # further right is worked out only for the rows that got past this one.
            self._guards.append(part)
            left_node = right_node
        del self._guards[held:]
        return result

    def _compare_pair(self, node: ast.Compare, left_node: ast.AST, op: ast.cmpop, right_node: ast.AST) -> pl.Expr:
        if isinstance(op, (ast.In, ast.NotIn)):
            found = self._contains(node, left_node, right_node)
            return ~found if isinstance(op, ast.NotIn) else found

        left_none = isinstance(left_node, ast.Constant) and left_node.value is None
        right_none = isinstance(right_node, ast.Constant) and right_node.value is None
        if isinstance(op, (ast.Is, ast.IsNot)) and not (left_none or right_none):
            self.fail(node, "`is` is only supported against None")
        if (left_none or right_none) and isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
            from .functions import regex_test

            other_node = right_node if left_none else left_node
            matched = regex_test(self, other_node)
            if matched is not None:
                return ~matched if isinstance(op, (ast.Eq, ast.Is)) else matched
            other = self.value(other_node)
            return other.is_null() if isinstance(op, (ast.Eq, ast.Is)) else other.is_not_null()

        left, right = self.value(left_node), self.value(right_node)
        left_type, right_type = self.dtype(left, left_node), self.dtype(right, right_node)
        if (left_type == pl.String) != (right_type == pl.String) and pl.Null not in (left_type, right_type):
            self.fail(node, "cannot compare text with a number; convert one side with str(...) or int(...)")
        if isinstance(op, ast.Eq):
            return self._checked(left.eq_missing(right), node)
        if isinstance(op, ast.NotEq):
            return self._checked(left.ne_missing(right), node)
        if isinstance(op, ast.Lt):
            return self._checked(left < right, node)
        if isinstance(op, ast.LtE):
            return self._checked(left <= right, node)
        if isinstance(op, ast.Gt):
            return self._checked(left > right, node)
        if isinstance(op, ast.GtE):
            return self._checked(left >= right, node)
        self.fail(node, "this comparison is not supported")

    def _contains(self, node: ast.Compare, left_node: ast.AST, right_node: ast.AST) -> pl.Expr:
        left = self.value(left_node)
        choices = self.const(right_node)
        if isinstance(choices, list):
            try:
                return self._checked(left.is_in(choices, nulls_equal=True), node)
            except TypeError:
                self.fail(right_node, "the values in the list must all be of one type")
        right = self.value(right_node)
        if self.dtype(right, right_node) == pl.String and self.dtype(left, left_node) == pl.String:
            return right.str.contains(left, literal=True)
        self.fail(node, "`in` needs a list of constants, or text on both sides")

    def _IfExp(self, node: ast.IfExp) -> pl.Expr:
        test = self.truth(node.test)
        # Each branch is worked out only for the rows that take it.
        self._guards.append(test)
        body = self.value(node.body)
        self._guards[-1] = ~test
        orelse = self.value(node.orelse)
        self._guards.pop()
        return self.either(node, test, body, node.body, orelse, node.orelse)

    def either(
        self, node: ast.AST, test: pl.Expr, body: pl.Expr, body_node: ast.AST, orelse: pl.Expr, orelse_node: ast.AST
    ) -> pl.Expr:
        """One of two values by a condition, the two made to fit one column."""
        then, otherwise = self._one_kind(node, body, body_node, orelse, orelse_node)
        return self._checked(pl.when(test).then(then).otherwise(otherwise), node)

    def _one_kind(self, node: ast.AST, left: pl.Expr, left_node: ast.AST, right: pl.Expr, right_node: ast.AST):
        """Make two alternative values fit one column, or refuse.

        Python would give each row its own type. A column has one, so text
        next to a number makes both text; other mixes are refused.
        """
        kinds = _kind(self.dtype(left, left_node)), _kind(self.dtype(right, right_node))
        if kinds[0] == kinds[1] or "missing" in kinds:
            return left, right
        if set(kinds) == {"text", "number"}:
            if kinds[0] == "number":
                return left.cast(pl.String), right
            return left, right.cast(pl.String)
        self.fail(node, f"one branch gives a {kinds[0]} and the other a {kinds[1]}; they cannot share a column")

    # ------------------------------------------------------------------
    # Calls
    # ------------------------------------------------------------------

    def _Call(self, node: ast.Call) -> pl.Expr:
        from .functions import BUILTINS, FUNCTIONS, METHODS, dotted, method_hint, regex_group

        func = node.func
        name = dotted(func)
        if name is not None and not self._owns_columns(name.split(".")[0]):
            if name == "globalMap.get":
                return pl.lit(self.const(node))
            handler = BUILTINS.get(name) or FUNCTIONS.get(name)
            if handler is not None:
                return handler(self, node)
            routine = self._routine(node, name)
            if routine is not None:
                return routine
            if isinstance(func, ast.Name):
                self.fail(node, f"unknown function '{name}'")
        if not isinstance(func, ast.Attribute):
            self.fail(node, "only named functions and methods can be called")

        if func.attr == "group":
            grouped = regex_group(self, node)
            if grouped is not None:
                return grouped
        target = self.value(func.value)
        handler = METHODS.get(func.attr)
        if handler is None:
            self.fail(node, f"unknown method '.{func.attr}()'{method_hint(func.attr)}")
        return handler(self, node, target)

    def _owns_columns(self, name: str) -> bool:
        """Whether a plain name refers to a row, a bare column or the variables."""
        if name in self.scope.rows or name == "Var":
            return True
        return self.scope.bare is not None and name in self.scope.rows[self.scope.bare]

    def _routine(self, node: ast.Call, name: str) -> Optional[pl.Expr]:
        """Call a routine: a function that takes and returns Polars expressions."""
        parts = name.split(".")
        if parts[0] == "routines":
            parts = parts[1:]
        if len(parts) != 2 or parts[0] not in self.scope.routines:
            return None
        module, function = parts
        functions = self.scope.routines[module]
        if function not in functions:
            self.fail(node, f"routine '{module}' has no function '{function}'")
        if any(isinstance(arg, ast.Starred) for arg in node.args) or any(k.arg is None for k in node.keywords):
            self.fail(node, "starred arguments are not supported")

        def argument(arg: ast.AST) -> Any:
            found = self.const(arg)
            return self.value(arg) if found is NOT_CONSTANT else found

        args = [argument(arg) for arg in node.args]
        kwargs = {keyword.arg: argument(keyword.value) for keyword in node.keywords}
        try:
            result = functions[function](*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- a routine may fail in any way
            self.fail(node, f"routine {module}.{function} raised {type(exc).__name__}: {exc}")
        if not isinstance(result, pl.Expr):
            self.fail(
                node,
                f"routine {module}.{function} must return a Polars expression, got {type(result).__name__}",
            )
        if "python_udf" in str(result):
            self.fail(
                node,
                f"routine {module}.{function} runs Python row by row; build it from Polars expressions only",
            )
        return self._checked(result, node)

    def _JoinedStr(self, node: ast.JoinedStr) -> pl.Expr:
        from .functions import as_text

        parts: List[pl.Expr] = []
        for item in node.values:
            if isinstance(item, ast.Constant):
                parts.append(pl.lit(str(item.value)))
                continue
            if item.format_spec is not None or item.conversion != -1:
                self.fail(node, "format specs inside an f-string are not supported; format the value first")
            parts.append(as_text(self, item.value))
        return pl.concat_str(parts) if parts else pl.lit("")
