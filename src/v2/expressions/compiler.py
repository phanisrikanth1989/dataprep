"""
Expression Compiler for v2 Engine.

Compiles AST nodes into Polars expressions.
"""
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

import polars as pl

from .parser import (
    ASTNode, Literal, ColumnRef, ContextRef, FunctionCall, RoutineCall,
    BinaryOp, UnaryOp, Conditional, Parser
)

if TYPE_CHECKING:
    from ..routines import RoutineRegistry


class CompileError(Exception):
    """Error during compilation."""
    pass


class ExpressionCompiler:
    """
    Compiles expression AST into Polars expressions.

    Supports:
    - Built-in functions (UPPER, LOWER, etc.)
    - Routine calls (RoutineName.function)
    - Context variables (context.var)
    - Column references (row.column or bare column)

    Usage:
        compiler = ExpressionCompiler(context={'tax_rate': 0.08})
        expr = compiler.compile("UPPER(name)")
        # Returns: pl.col("name").str.to_uppercase()

        # With routine support:
        from v2.routines import RoutineManager
        manager = RoutineManager()
        compiler = ExpressionCompiler(
            context={'tax_rate': 0.08},
            routine_registry=manager.get_registry()
        )
        expr = compiler.compile("DemoRoutine.greet(name)")
    """

    def __init__(
        self,
        context: Dict[str, Any] = None,
        routine_registry: Optional["RoutineRegistry"] = None,
        safe: bool = False
    ):
        """
        Initialize compiler.

        Args:
            context: Context variables for resolving context.var references
            routine_registry: Optional routine registry for RoutineName.function calls
            safe: If True, type cast functions use strict=False so invalid
                  values produce null instead of raising errors
        """
        self.context = context or {}
        self.routine_registry = routine_registry
        self.safe = safe
        self._functions = self._build_function_registry()

    def compile(self, expression: str) -> pl.Expr:
        """Compile an expression string to a Polars expression."""
        ast = Parser.parse(expression)
        return self._compile_node(ast)

    def _compile_node(self, node: ASTNode) -> pl.Expr:
        """Compile an AST node to a Polars expression."""
        if isinstance(node, Literal):
            return self._compile_literal(node)
        elif isinstance(node, ColumnRef):
            return self._compile_column_ref(node)
        elif isinstance(node, ContextRef):
            return self._compile_context_ref(node)
        elif isinstance(node, FunctionCall):
            return self._compile_function_call(node)
        elif isinstance(node, RoutineCall):
            return self._compile_routine_call(node)
        elif isinstance(node, BinaryOp):
            return self._compile_binary_op(node)
        elif isinstance(node, UnaryOp):
            return self._compile_unary_op(node)
        elif isinstance(node, Conditional):
            return self._compile_conditional(node)
        else:
            raise CompileError(f"Unknown node type: {type(node)}")

    def _compile_literal(self, node: Literal) -> pl.Expr:
        """Compile a literal value."""
        return pl.lit(node.value)

    def _compile_column_ref(self, node: ColumnRef) -> pl.Expr:
        """Compile a column reference."""
        return pl.col(node.column)

    def _compile_context_ref(self, node: ContextRef) -> pl.Expr:
        """Compile a context variable reference."""
        if node.variable not in self.context:
            raise CompileError(f"Unknown context variable: {node.variable}")
        return pl.lit(self.context[node.variable])

    def _compile_function_call(self, node: FunctionCall) -> pl.Expr:
        """Compile a function call."""
        func_name = node.name.lower()

        if func_name not in self._functions:
            raise CompileError(f"Unknown function: {node.name}")

        # Compile arguments
        compiled_args = [self._compile_node(arg) for arg in node.args]

        # Call the function implementation
        return self._functions[func_name](compiled_args)

    def _compile_routine_call(self, node: RoutineCall) -> pl.Expr:
        """
        Compile a routine call (RoutineName.function).

        Uses a tiered approach:
        - Tier 1 (Vectorized): If func._vectorized is True, use map_batches.
          The function receives pl.Series args and returns pl.Series.
          Near-native speed since it operates on entire columns.
        - Tier 2 (Scalar fallback): Use map_elements for row-by-row execution.
          The function receives individual values and returns individual values.
          Slower but works for any Python logic.

        For multi-argument functions, both tiers use struct packing to bundle
        columns together.
        """
        if self.routine_registry is None:
            raise CompileError(
                f"Cannot call routine {node.routine}.{node.function}: "
                "no routine registry configured"
            )

        # O(1) lookup of the function
        func = self.routine_registry.get(node.routine, node.function)
        if func is None:
            raise CompileError(
                f"Unknown routine function: {node.routine}.{node.function}"
            )

        # Compile arguments
        compiled_args = [self._compile_node(arg) for arg in node.args]

        # Check if function is marked as vectorized
        is_vectorized = getattr(func, '_vectorized', False)
        return_dtype = getattr(func, '_return_dtype', None)

        if len(compiled_args) == 0:
            # No arguments - call function directly and return literal
            try:
                result = func()
                return pl.lit(result)
            except Exception as e:
                raise CompileError(
                    f"Error calling {node.routine}.{node.function}(): {e}"
                )

        if is_vectorized and len(compiled_args) == 1:
            # Tier 1: Vectorized single-arg — use map_batches (column in, column out)
            return compiled_args[0].map_batches(func, return_dtype=return_dtype)

        if is_vectorized and len(compiled_args) > 1:
            # Tier 1 multi-arg: pack into struct, unpack Series in wrapper
            struct_fields = [
                arg.alias(f"__arg_{i}") for i, arg in enumerate(compiled_args)
            ]

            def call_vectorized(s: pl.Series) -> pl.Series:
                df = s.struct.unnest()
                args = [df[f"__arg_{i}"] for i in range(len(compiled_args))]
                return func(*args)

            return pl.struct(struct_fields).map_batches(
                call_vectorized, return_dtype=return_dtype
            )

        # Tier 2: Scalar fallback
        if len(compiled_args) == 1:
            # Single argument - use map_elements directly
            return compiled_args[0].map_elements(
                func,
                return_dtype=pl.Object,
                skip_nulls=False,
            )
        else:
            # Multiple arguments - use struct + map_elements
            struct_fields = [
                arg.alias(f"__arg_{i}") for i, arg in enumerate(compiled_args)
            ]

            def call_with_struct(row):
                # Extract arguments from struct
                args = [row[f"__arg_{i}"] for i in range(len(compiled_args))]
                return func(*args)

            return pl.struct(struct_fields).map_elements(
                call_with_struct,
                return_dtype=pl.Object,
                skip_nulls=False,
            )

    def _compile_binary_op(self, node: BinaryOp) -> pl.Expr:
        """Compile a binary operation."""
        left = self._compile_node(node.left)
        right = self._compile_node(node.right)

        op_map = {
            '+': lambda l, r: l + r,
            '-': lambda l, r: l - r,
            '*': lambda l, r: l * r,
            '/': lambda l, r: l / r,
            '%': lambda l, r: l % r,
            '==': lambda l, r: l == r,
            '=': lambda l, r: l == r,
            '!=': lambda l, r: l != r,
            '<': lambda l, r: l < r,
            '<=': lambda l, r: l <= r,
            '>': lambda l, r: l > r,
            '>=': lambda l, r: l >= r,
            '&&': lambda l, r: l & r,
            'and': lambda l, r: l & r,
            '||': lambda l, r: l | r,
            'or': lambda l, r: l | r,
        }

        op = node.op.lower() if node.op.isalpha() else node.op
        if op not in op_map:
            raise CompileError(f"Unknown operator: {node.op}")

        return op_map[op](left, right)

    def _compile_unary_op(self, node: UnaryOp) -> pl.Expr:
        """Compile a unary operation."""
        operand = self._compile_node(node.operand)

        if node.op in ('!', 'not'):
            return ~operand
        elif node.op == '-':
            return -operand
        else:
            raise CompileError(f"Unknown unary operator: {node.op}")

    def _compile_conditional(self, node: Conditional) -> pl.Expr:
        """Compile a conditional (ternary) expression."""
        condition = self._compile_node(node.condition)
        then_expr = self._compile_node(node.then_expr)
        else_expr = self._compile_node(node.else_expr)

        return pl.when(condition).then(then_expr).otherwise(else_expr)

    @staticmethod
    def _extract_literal(expr: pl.Expr) -> Any:
        """
        Extract a Python literal value from a pl.lit() expression.

        Some Polars APIs (e.g., str.pad_start, round) require native Python
        values rather than pl.Expr. This evaluates a literal expression on a
        dummy frame to extract its value.
        """
        try:
            result = pl.DataFrame({"_d": [0]}).select(expr.alias("_v"))["_v"][0]
            return result
        except Exception:
            return None

    def _build_function_registry(self) -> Dict[str, Callable]:
        """Build the registry of supported functions."""
        # When safe mode is enabled, type cast functions use strict=False
        # so invalid values produce null instead of raising errors
        cast_strict = not self.safe

        return {
            # String functions
            'upper': lambda args: args[0].str.to_uppercase(),
            'lower': lambda args: args[0].str.to_lowercase(),
            'trim': lambda args: args[0].str.strip_chars(),
            'ltrim': lambda args: args[0].str.strip_chars_start(),
            'rtrim': lambda args: args[0].str.strip_chars_end(),
            'length': lambda args: args[0].str.len_chars(),
            'concat': self._fn_concat,
            'substring': self._fn_substring,
            'replace': lambda args: args[0].str.replace_all(args[1], args[2]),
            'left': lambda args: args[0].str.head(args[1]),
            'right': lambda args: args[0].str.tail(args[1]),
            'lpad': self._fn_lpad,
            'rpad': self._fn_rpad,
            'contains': lambda args: args[0].str.contains(args[1]),
            'starts_with': lambda args: args[0].str.starts_with(args[1]),
            'ends_with': lambda args: args[0].str.ends_with(args[1]),
            'regex_match': lambda args: args[0].str.contains(args[1]),
            'regex_extract': self._fn_regex_extract,
            'split': lambda args: args[0].str.split(args[1]),

            # Numeric functions
            'abs': lambda args: args[0].abs(),
            'round': self._fn_round,
            'floor': lambda args: args[0].floor(),
            'ceil': lambda args: args[0].ceil(),
            'sqrt': lambda args: args[0].sqrt(),
            'pow': lambda args: args[0].pow(args[1]),
            'power': lambda args: args[0].pow(args[1]),
            'mod': lambda args: args[0] % args[1],
            'log': lambda args: args[0].log() if len(args) == 1 else args[0].log(args[1]),
            'exp': lambda args: args[0].exp(),
            'sign': lambda args: args[0].sign(),

            # Null handling (treating NULL as empty string for strings)
            'coalesce': self._fn_coalesce,
            'ifnull': lambda args: args[0].fill_null(args[1]),
            'nvl': lambda args: args[0].fill_null(args[1]),
            'isnull': lambda args: args[0].is_null(),
            'isnotnull': lambda args: args[0].is_not_null(),
            'nullif': lambda args: pl.when(args[0] == args[1]).then(None).otherwise(args[0]),

            # Conditional
            'if': lambda args: pl.when(args[0]).then(args[1]).otherwise(args[2] if len(args) > 2 else None),

            # Type conversion
            'to_string': lambda args: args[0].cast(pl.Utf8).fill_null(""),
            'to_integer': lambda args: args[0].cast(pl.Int64, strict=cast_strict),
            'to_float': lambda args: args[0].cast(pl.Float64, strict=cast_strict),
            'to_boolean': lambda args: args[0].cast(pl.Boolean, strict=cast_strict),
            'to_decimal': lambda args: args[0].cast(pl.Float64, strict=cast_strict),

            # Date functions
            'year': lambda args: args[0].dt.year(),
            'month': lambda args: args[0].dt.month(),
            'day': lambda args: args[0].dt.day(),
            'hour': lambda args: args[0].dt.hour(),
            'minute': lambda args: args[0].dt.minute(),
            'second': lambda args: args[0].dt.second(),
            'to_date': self._fn_to_date,
            'parse_date': self._fn_parse_date,
            'format_date': self._fn_format_date,
            'date_add': self._fn_date_add,
            'date_diff': self._fn_date_diff,
            'now': lambda args: pl.lit(datetime.now()),

            # Aggregate functions (for aggregate component)
            'sum': lambda args: args[0].sum(),
            'count': lambda args: args[0].count(),
            'avg': lambda args: args[0].mean(),
            'min': lambda args: args[0].min(),
            'max': lambda args: args[0].max(),
            'first': lambda args: args[0].first(),
            'last': lambda args: args[0].last(),
        }

    def _fn_concat(self, args) -> pl.Expr:
        """CONCAT function - concatenate strings, treating NULL as empty."""
        if len(args) < 2:
            raise CompileError("CONCAT requires at least 2 arguments")
        # Fill nulls with empty string for concatenation
        result = args[0].fill_null("")
        for arg in args[1:]:
            result = result + arg.fill_null("")
        return result

    def _fn_substring(self, args) -> pl.Expr:
        """SUBSTRING function - extract substring."""
        if len(args) < 2:
            raise CompileError("SUBSTRING requires at least 2 arguments")
        # SUBSTRING(str, start, length) or SUBSTRING(str, start)
        if len(args) == 2:
            return args[0].str.slice(args[1])
        return args[0].str.slice(args[1], args[2])

    def _fn_lpad(self, args) -> pl.Expr:
        """LPAD function - pad string on left to specified length."""
        if len(args) < 2:
            raise CompileError("LPAD requires at least 2 arguments")
        length = self._extract_literal(args[1])
        fill_char = self._extract_literal(args[2]) if len(args) > 2 else " "
        return args[0].str.pad_start(length, fill_char)

    def _fn_rpad(self, args) -> pl.Expr:
        """RPAD function - pad string on right to specified length."""
        if len(args) < 2:
            raise CompileError("RPAD requires at least 2 arguments")
        length = self._extract_literal(args[1])
        fill_char = self._extract_literal(args[2]) if len(args) > 2 else " "
        return args[0].str.pad_end(length, fill_char)

    def _fn_regex_extract(self, args) -> pl.Expr:
        """REGEX_EXTRACT function - extract first regex group match."""
        if len(args) < 2:
            raise CompileError("REGEX_EXTRACT requires at least 2 arguments")
        group_index = self._extract_literal(args[2]) if len(args) > 2 else 1
        return args[0].str.extract(args[1], group_index=group_index)

    def _fn_round(self, args) -> pl.Expr:
        """ROUND function with optional decimal places."""
        if len(args) == 1:
            return args[0].round(0)
        decimals = self._extract_literal(args[1])
        return args[0].round(decimals)

    def _fn_coalesce(self, args) -> pl.Expr:
        """COALESCE - return first non-null value."""
        if len(args) < 1:
            raise CompileError("COALESCE requires at least 1 argument")
        result = args[0]
        for arg in args[1:]:
            result = result.fill_null(arg)
        return result

    def _fn_to_date(self, args) -> pl.Expr:
        """TO_DATE function - convert string to date."""
        if len(args) == 1:
            return args[0].str.to_date()
        fmt = self._extract_literal(args[1])
        return args[0].str.to_date(fmt)

    def _fn_parse_date(self, args) -> pl.Expr:
        """PARSE_DATE function - parse string to date with format."""
        if len(args) < 2:
            raise CompileError("PARSE_DATE requires format argument")
        fmt = self._extract_literal(args[1])
        return args[0].str.to_date(fmt)

    def _fn_format_date(self, args) -> pl.Expr:
        """FORMAT_DATE function - format date/datetime to string."""
        if len(args) < 2:
            raise CompileError("FORMAT_DATE requires format argument")
        fmt = self._extract_literal(args[1])
        return args[0].dt.to_string(fmt)

    def _fn_date_add(self, args) -> pl.Expr:
        """DATE_ADD function - add days to a date."""
        if len(args) < 2:
            raise CompileError("DATE_ADD requires 2 arguments")
        return args[0] + pl.duration(days=args[1])

    def _fn_date_diff(self, args) -> pl.Expr:
        """DATE_DIFF function - difference between two dates in days."""
        if len(args) < 2:
            raise CompileError("DATE_DIFF requires 2 arguments")
        return (args[0] - args[1]).dt.total_days()


def compile_expression(
    expression: str,
    context: Dict[str, Any] = None,
    routine_registry: Optional["RoutineRegistry"] = None,
    safe: bool = False
) -> pl.Expr:
    """
    Convenience function to compile an expression.

    Args:
        expression: Expression string
        context: Context variables
        routine_registry: Optional routine registry for RoutineName.function calls
        safe: If True, type cast functions use strict=False so invalid
              values produce null instead of raising errors

    Returns:
        Polars expression
    """
    compiler = ExpressionCompiler(context, routine_registry, safe=safe)
    return compiler.compile(expression)
