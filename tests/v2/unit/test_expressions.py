"""
Unit tests for v2 Expression DSL.
"""
import pytest
import polars as pl

from v2.expressions import Tokenizer, Token, TokenType, TokenizerError
from v2.expressions import Parser, ParseError
from v2.expressions.parser import ColumnRef, BinaryOp
from v2.expressions import ExpressionCompiler, compile_expression


class TestTokenizer:
    """Test expression tokenizer."""

    def test_simple_identifier(self):
        tokenizer = Tokenizer("name")
        tokens = tokenizer.tokenize()
        assert len(tokens) == 2  # identifier + EOF
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "name"

    def test_function_call(self):
        tokenizer = Tokenizer("UPPER(name)")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.FUNCTION
        assert tokens[0].value == "UPPER"
        assert tokens[1].type == TokenType.LPAREN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[3].type == TokenType.RPAREN

    def test_string_literal(self):
        tokenizer = Tokenizer('"hello world"')
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_number(self):
        tokenizer = Tokenizer("123.45")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "123.45"

    def test_operators(self):
        tokenizer = Tokenizer("a + b * c")
        tokens = tokenizer.tokenize()
        assert tokens[1].type == TokenType.PLUS
        assert tokens[3].type == TokenType.STAR

    def test_comparison(self):
        tokenizer = Tokenizer("a >= 10")
        tokens = tokenizer.tokenize()
        assert tokens[1].type == TokenType.GREATER_EQ

    def test_boolean(self):
        tokenizer = Tokenizer("true && false")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.BOOLEAN
        assert tokens[0].value == "true"
        assert tokens[1].type == TokenType.AND

    def test_column_ref(self):
        tokenizer = Tokenizer("row.column_name")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.COLUMN_REF
        assert tokens[0].value == "row.column_name"

    def test_context_ref(self):
        tokenizer = Tokenizer("context.tax_rate")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.CONTEXT_REF
        assert tokens[0].value == "context.tax_rate"


class TestParser:
    """Test expression parser."""

    def test_simple_column(self):
        ast = Parser.parse("name")
        assert ast.column == "name"

    def test_function_call(self):
        ast = Parser.parse("UPPER(name)")
        assert ast.name == "UPPER"
        assert len(ast.args) == 1

    def test_binary_operation(self):
        ast = Parser.parse("a + b")
        assert ast.op == "+"
        assert ast.left.column == "a"
        assert ast.right.column == "b"

    def test_operator_precedence(self):
        ast = Parser.parse("a + b * c")
        # Should be: a + (b * c)
        assert ast.op == "+"
        assert ast.right.op == "*"

    def test_nested_function(self):
        ast = Parser.parse("UPPER(TRIM(name))")
        assert ast.name == "UPPER"
        assert ast.args[0].name == "TRIM"

    def test_conditional(self):
        ast = Parser.parse("a > 0 ? a : 0")
        assert hasattr(ast, 'condition')
        assert hasattr(ast, 'then_expr')
        assert hasattr(ast, 'else_expr')


class TestCompiler:
    """Test expression compiler."""

    def test_compile_column(self):
        expr = compile_expression("name")
        # Should produce pl.col("name")
        assert expr is not None

    def test_compile_upper(self):
        expr = compile_expression("UPPER(name)")
        df = pl.DataFrame({"name": ["hello", "world"]})
        result = df.select(expr.alias("result"))
        assert result["result"].to_list() == ["HELLO", "WORLD"]

    def test_compile_concat(self):
        expr = compile_expression('CONCAT(first, " ", last)')
        df = pl.DataFrame({"first": ["John"], "last": ["Doe"]})
        result = df.select(expr.alias("result"))
        assert result["result"][0] == "John Doe"

    def test_compile_arithmetic(self):
        expr = compile_expression("price * quantity")
        df = pl.DataFrame({"price": [10.0], "quantity": [5]})
        result = df.select(expr.alias("total"))
        assert result["total"][0] == 50.0

    def test_compile_comparison(self):
        expr = compile_expression("amount > 100")
        df = pl.DataFrame({"amount": [50, 150, 100]})
        result = df.select(expr.alias("result"))
        assert result["result"].to_list() == [False, True, False]

    def test_compile_conditional(self):
        expr = compile_expression("amount > 100 ? 'high' : 'low'")
        df = pl.DataFrame({"amount": [50, 150]})
        result = df.select(expr.alias("result"))
        assert result["result"].to_list() == ["low", "high"]

    def test_compile_with_context(self):
        expr = compile_expression("amount * context.tax_rate", {"tax_rate": 0.1})
        df = pl.DataFrame({"amount": [100.0]})
        result = df.select(expr.alias("result"))
        assert result["result"][0] == 10.0

    def test_null_handling_concat(self):
        """Test that NULL is treated as empty string in CONCAT."""
        expr = compile_expression('CONCAT(first, " ", last)')
        df = pl.DataFrame({"first": ["John", None], "last": ["Doe", "Smith"]})
        result = df.select(expr.alias("result"))
        # NULL should become empty string
        assert result["result"][0] == "John Doe"
        assert result["result"][1] == " Smith"

    def test_coalesce(self):
        expr = compile_expression("COALESCE(value, 0)")
        df = pl.DataFrame({"value": [1, None, 3]})
        result = df.select(expr.alias("result"))
        assert result["result"].to_list() == [1, 0, 3]


class TestTokenizerLookupRefs:
    """Test tokenizer support for lookup column and variable references."""

    def test_lookup_column_ref(self):
        """customers.name should tokenize as COLUMN_REF"""
        tokens = Tokenizer("customers.name").tokenize()
        # "customers" is lowercase, not PascalCase, so NOT a routine call
        # Should be treated as a dotted column reference
        assert tokens[0].type == TokenType.COLUMN_REF
        assert tokens[0].value == "customers.name"

    def test_var_ref(self):
        """var.total should tokenize as COLUMN_REF with source='var'"""
        tokens = Tokenizer("var.total").tokenize()
        assert tokens[0].type == TokenType.COLUMN_REF
        assert tokens[0].value == "var.total"

    def test_lookup_in_expression(self):
        """quantity * products.unit_price"""
        tokens = Tokenizer("quantity * products.unit_price").tokenize()
        assert tokens[0].type == TokenType.IDENTIFIER  # quantity
        assert tokens[1].type == TokenType.STAR
        assert tokens[2].type == TokenType.COLUMN_REF  # products.unit_price

    def test_routine_call_still_works(self):
        """PascalCase.func() is still ROUTINE_CALL"""
        tokens = Tokenizer("StringUtils.clean(name)").tokenize()
        assert tokens[0].type == TokenType.ROUTINE_CALL


class TestParserLookupRefs:
    """Test parser support for lookup column and variable references."""

    def test_parse_lookup_column(self):
        ast = Parser.parse("customers.name")
        assert isinstance(ast, ColumnRef)
        assert ast.column == "customers.name"

    def test_parse_var_ref(self):
        ast = Parser.parse("var.total")
        assert isinstance(ast, ColumnRef)
        assert ast.column == "var.total"

    def test_parse_expression_with_lookup(self):
        ast = Parser.parse("quantity * products.unit_price")
        assert isinstance(ast, BinaryOp)
        assert isinstance(ast.right, ColumnRef)
        assert ast.right.column == "products.unit_price"


class TestCompilerLookupRefs:
    """Test compiler support for lookup column and variable references."""

    def test_compile_lookup_column(self):
        expr = compile_expression("customers.name")
        df = pl.DataFrame({"customers.name": ["Alice", "Bob"]}).lazy()
        result = df.select(expr).collect()
        assert result["customers.name"].to_list() == ["Alice", "Bob"]

    def test_compile_var_ref(self):
        expr = compile_expression("var.total")
        df = pl.DataFrame({"var.total": [100.0, 200.0]}).lazy()
        result = df.select(expr).collect()
        assert result["var.total"].to_list() == [100.0, 200.0]
