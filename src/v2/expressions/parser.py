"""
Expression Parser for v2 Engine.

Parses tokens into an Abstract Syntax Tree (AST).
"""
from dataclasses import dataclass
from typing import Any, List, Union

from .tokenizer import Token, TokenType, Tokenizer


class ParseError(Exception):
    """Error during parsing."""
    pass


# AST Node Types
@dataclass
class Literal:
    """A literal value (string, number, boolean, null)."""
    value: Any
    dtype: str  # 'string', 'number', 'boolean', 'null'


@dataclass
class ColumnRef:
    """Reference to a column: row.column_name."""
    column: str
    source: str = "row"  # 'row' or 'input'


@dataclass
class ContextRef:
    """Reference to a context variable: context.var_name."""
    variable: str


@dataclass
class FunctionCall:
    """A function call: FUNC(arg1, arg2, ...)."""
    name: str
    args: List[Any]  # List of AST nodes


@dataclass
class RoutineCall:
    """A routine function call: RoutineName.function(arg1, arg2, ...)."""
    routine: str    # Routine name (e.g., "DemoRoutine")
    function: str   # Function name (e.g., "greet")
    args: List[Any] # List of AST nodes


@dataclass
class BinaryOp:
    """Binary operation: left op right."""
    op: str
    left: Any
    right: Any


@dataclass
class UnaryOp:
    """Unary operation: op expr."""
    op: str
    operand: Any


@dataclass
class Conditional:
    """Conditional: condition ? then_expr : else_expr."""
    condition: Any
    then_expr: Any
    else_expr: Any


ASTNode = Union[Literal, ColumnRef, ContextRef, FunctionCall, RoutineCall, BinaryOp, UnaryOp, Conditional]


class Parser:
    """
    Recursive descent parser for expressions.

    Operator precedence (lowest to highest):
    1. OR (||)
    2. AND (&&)
    3. Equality (==, !=)
    4. Comparison (<, <=, >, >=)
    5. Addition (+, -)
    6. Multiplication (*, /, %)
    7. Unary (!, -)
    8. Primary (literals, identifiers, function calls)
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    @classmethod
    def parse(cls, expression: str) -> ASTNode:
        """Parse an expression string into an AST."""
        tokenizer = Tokenizer(expression)
        tokens = tokenizer.tokenize()
        parser = cls(tokens)
        return parser.parse_expression()

    def parse_expression(self) -> ASTNode:
        """Parse a complete expression."""
        return self._parse_ternary()

    def _current(self) -> Token:
        """Get current token."""
        return self.tokens[self.pos]

    def _peek(self, offset: int = 0) -> Token:
        """Peek at token at current position + offset."""
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def _advance(self) -> Token:
        """Advance to next token and return current."""
        token = self._current()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        """Expect current token to be of given type."""
        token = self._current()
        if token.type != token_type:
            raise ParseError(f"Expected {token_type.name}, got {token.type.name}")
        return self._advance()

    def _match(self, *types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        return self._current().type in types

    def _parse_ternary(self) -> ASTNode:
        """Parse ternary conditional: expr ? then : else."""
        expr = self._parse_or()

        if self._match(TokenType.QUESTION):
            self._advance()
            then_expr = self.parse_expression()
            self._expect(TokenType.COLON)
            else_expr = self.parse_expression()
            return Conditional(expr, then_expr, else_expr)

        return expr

    def _parse_or(self) -> ASTNode:
        """Parse OR expressions."""
        left = self._parse_and()

        while self._match(TokenType.OR):
            op = self._advance().value
            right = self._parse_and()
            left = BinaryOp(op, left, right)

        return left

    def _parse_and(self) -> ASTNode:
        """Parse AND expressions."""
        left = self._parse_equality()

        while self._match(TokenType.AND):
            op = self._advance().value
            right = self._parse_equality()
            left = BinaryOp(op, left, right)

        return left

    def _parse_equality(self) -> ASTNode:
        """Parse equality expressions (==, !=)."""
        left = self._parse_comparison()

        while self._match(TokenType.EQUALS, TokenType.NOT_EQUALS):
            op = self._advance().value
            right = self._parse_comparison()
            left = BinaryOp(op, left, right)

        return left

    def _parse_comparison(self) -> ASTNode:
        """Parse comparison expressions (<, <=, >, >=)."""
        left = self._parse_additive()

        while self._match(TokenType.LESS, TokenType.LESS_EQ, TokenType.GREATER, TokenType.GREATER_EQ):
            op = self._advance().value
            right = self._parse_additive()
            left = BinaryOp(op, left, right)

        return left

    def _parse_additive(self) -> ASTNode:
        """Parse additive expressions (+, -)."""
        left = self._parse_multiplicative()

        while self._match(TokenType.PLUS, TokenType.MINUS):
            op = self._advance().value
            right = self._parse_multiplicative()
            left = BinaryOp(op, left, right)

        return left

    def _parse_multiplicative(self) -> ASTNode:
        """Parse multiplicative expressions (*, /, %)."""
        left = self._parse_unary()

        while self._match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._advance().value
            right = self._parse_unary()
            left = BinaryOp(op, left, right)

        return left

    def _parse_unary(self) -> ASTNode:
        """Parse unary expressions (!, -)."""
        if self._match(TokenType.NOT, TokenType.MINUS):
            op = self._advance().value
            operand = self._parse_unary()
            return UnaryOp(op, operand)

        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        """Parse primary expressions."""
        token = self._current()

        # Literals
        if token.type == TokenType.NUMBER:
            self._advance()
            if '.' in token.value:
                return Literal(float(token.value), 'number')
            return Literal(int(token.value), 'number')

        if token.type == TokenType.STRING:
            self._advance()
            return Literal(token.value, 'string')

        if token.type == TokenType.BOOLEAN:
            self._advance()
            return Literal(token.value.lower() == 'true', 'boolean')

        if token.type == TokenType.NULL:
            self._advance()
            return Literal(None, 'null')

        # Column reference
        if token.type == TokenType.COLUMN_REF:
            self._advance()
            parts = token.value.split('.', 1)
            # For row/input prefixes, strip the prefix (e.g., row.name -> name)
            # For lookup/var prefixes, keep the full dotted name (e.g., customers.name)
            if parts[0] in ('row', 'input'):
                return ColumnRef(parts[1], parts[0])
            return ColumnRef(token.value, parts[0])

        # Context reference
        if token.type == TokenType.CONTEXT_REF:
            self._advance()
            parts = token.value.split('.', 1)
            return ContextRef(parts[1])

        # Function call
        if token.type == TokenType.FUNCTION:
            return self._parse_function_call()

        # Routine call (RoutineName.function)
        if token.type == TokenType.ROUTINE_CALL:
            return self._parse_routine_call()

        # Identifier (bare column name)
        if token.type == TokenType.IDENTIFIER:
            self._advance()
            return ColumnRef(token.value)

        # Parenthesized expression
        if token.type == TokenType.LPAREN:
            self._advance()
            expr = self.parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        raise ParseError(f"Unexpected token: {token}")

    def _parse_function_call(self) -> FunctionCall:
        """Parse a function call."""
        name_token = self._expect(TokenType.FUNCTION)
        self._expect(TokenType.LPAREN)

        args = []
        if not self._match(TokenType.RPAREN):
            args.append(self.parse_expression())
            while self._match(TokenType.COMMA):
                self._advance()
                args.append(self.parse_expression())

        self._expect(TokenType.RPAREN)
        return FunctionCall(name_token.value, args)

    def _parse_routine_call(self) -> RoutineCall:
        """Parse a routine function call (RoutineName.function)."""
        name_token = self._expect(TokenType.ROUTINE_CALL)

        # Parse "RoutineName.function" from token value
        parts = name_token.value.split('.', 1)
        routine_name = parts[0]
        func_name = parts[1] if len(parts) > 1 else ""

        self._expect(TokenType.LPAREN)

        args = []
        if not self._match(TokenType.RPAREN):
            args.append(self.parse_expression())
            while self._match(TokenType.COMMA):
                self._advance()
                args.append(self.parse_expression())

        self._expect(TokenType.RPAREN)
        return RoutineCall(routine_name, func_name, args)
