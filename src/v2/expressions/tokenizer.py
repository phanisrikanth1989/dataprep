"""
Expression Tokenizer for v2 Engine.

Converts expression strings into tokens for parsing.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, List


class TokenType(Enum):
    """Types of tokens in expressions."""
    # Literals
    NUMBER = auto()         # 123, 45.67
    STRING = auto()         # "hello", 'world'
    BOOLEAN = auto()        # true, false
    NULL = auto()           # null, NULL

    # Identifiers
    IDENTIFIER = auto()     # column_name, variable
    FUNCTION = auto()       # UPPER, CONCAT (followed by '(')

    # Operators
    PLUS = auto()           # +
    MINUS = auto()          # -
    STAR = auto()           # *
    SLASH = auto()          # /
    PERCENT = auto()        # %
    EQUALS = auto()         # ==
    NOT_EQUALS = auto()     # !=
    LESS = auto()           # <
    LESS_EQ = auto()        # <=
    GREATER = auto()        # >
    GREATER_EQ = auto()     # >=
    AND = auto()            # && or AND
    OR = auto()             # || or OR
    NOT = auto()            # ! or NOT

    # Punctuation
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    COMMA = auto()          # ,
    DOT = auto()            # .
    COLON = auto()          # :
    QUESTION = auto()       # ?

    # Special
    COLUMN_REF = auto()     # row.column or input.column
    CONTEXT_REF = auto()    # context.var
    ROUTINE_CALL = auto()   # RoutineName.function (PascalCase.function)

    EOF = auto()


@dataclass
class Token:
    """A token from the expression."""
    type: TokenType
    value: str
    position: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r})"


class TokenizerError(Exception):
    """Error during tokenization."""
    def __init__(self, message: str, position: int):
        super().__init__(f"{message} at position {position}")
        self.position = position


class Tokenizer:
    """
    Tokenizes expression strings.

    Example:
        tokenizer = Tokenizer("UPPER(name)")
        tokens = tokenizer.tokenize()
        # [Token(FUNCTION, 'UPPER'), Token(LPAREN, '('),
        #  Token(IDENTIFIER, 'name'), Token(RPAREN, ')'), Token(EOF, '')]
    """

    # Keywords that are treated specially
    KEYWORDS = {
        'true': TokenType.BOOLEAN,
        'false': TokenType.BOOLEAN,
        'null': TokenType.NULL,
        'and': TokenType.AND,
        'or': TokenType.OR,
        'not': TokenType.NOT,
    }

    # Known function names (case-insensitive)
    FUNCTIONS = {
        # String functions
        'upper', 'lower', 'trim', 'ltrim', 'rtrim', 'concat', 'substring',
        'length', 'replace', 'left', 'right', 'pad_left', 'pad_right',
        'lpad', 'rpad',
        'split', 'contains', 'starts_with', 'ends_with',
        'regexp_match', 'regex_match', 'regex_extract',

        # Numeric functions
        'abs', 'round', 'floor', 'ceil', 'mod', 'pow', 'power',
        'sqrt', 'log', 'exp',
        'min', 'max', 'sign',

        # Date/Time functions
        'parse_date', 'parse_datetime', 'format_date', 'year', 'month', 'day',
        'hour', 'minute', 'second', 'date_add', 'date_diff', 'now', 'today',
        'to_date',

        # Null handling
        'coalesce', 'ifnull', 'nullif', 'isnull', 'isnotnull', 'nvl',

        # Conditional
        'if', 'case', 'when', 'decode',

        # Type conversion
        'to_string', 'to_integer', 'to_float', 'to_boolean',
        'to_decimal', 'cast',

        # Aggregate (for aggregate component)
        'sum', 'count', 'avg', 'min', 'max', 'first', 'last',
        'count_distinct', 'collect_list', 'collect_set',
    }

    def __init__(self, expression: str):
        self.expression = expression
        self.pos = 0
        self.length = len(expression)

    def tokenize(self) -> List[Token]:
        """Tokenize the entire expression."""
        tokens = list(self._tokenize_iter())
        tokens.append(Token(TokenType.EOF, '', self.pos))
        return tokens

    def _tokenize_iter(self) -> Iterator[Token]:
        """Generate tokens from the expression."""
        while self.pos < self.length:
            self._skip_whitespace()
            if self.pos >= self.length:
                break

            char = self.expression[self.pos]

            # String literal
            if char in ('"', "'"):
                yield self._read_string()

            # Number
            elif char.isdigit() or (char == '.' and self._peek(1).isdigit()):
                yield self._read_number()

            # Identifier or keyword
            elif char.isalpha() or char == '_':
                yield self._read_identifier()

            # Operators and punctuation
            elif char == '+':
                yield Token(TokenType.PLUS, '+', self.pos)
                self.pos += 1

            elif char == '-':
                yield Token(TokenType.MINUS, '-', self.pos)
                self.pos += 1

            elif char == '*':
                yield Token(TokenType.STAR, '*', self.pos)
                self.pos += 1

            elif char == '/':
                yield Token(TokenType.SLASH, '/', self.pos)
                self.pos += 1

            elif char == '%':
                yield Token(TokenType.PERCENT, '%', self.pos)
                self.pos += 1

            elif char == '(':
                yield Token(TokenType.LPAREN, '(', self.pos)
                self.pos += 1

            elif char == ')':
                yield Token(TokenType.RPAREN, ')', self.pos)
                self.pos += 1

            elif char == '[':
                yield Token(TokenType.LBRACKET, '[', self.pos)
                self.pos += 1

            elif char == ']':
                yield Token(TokenType.RBRACKET, ']', self.pos)
                self.pos += 1

            elif char == ',':
                yield Token(TokenType.COMMA, ',', self.pos)
                self.pos += 1

            elif char == '.':
                yield Token(TokenType.DOT, '.', self.pos)
                self.pos += 1

            elif char == ':':
                yield Token(TokenType.COLON, ':', self.pos)
                self.pos += 1

            elif char == '?':
                yield Token(TokenType.QUESTION, '?', self.pos)
                self.pos += 1

            elif char == '=':
                if self._peek(1) == '=':
                    yield Token(TokenType.EQUALS, '==', self.pos)
                    self.pos += 2
                else:
                    yield Token(TokenType.EQUALS, '=', self.pos)
                    self.pos += 1

            elif char == '!':
                if self._peek(1) == '=':
                    yield Token(TokenType.NOT_EQUALS, '!=', self.pos)
                    self.pos += 2
                else:
                    yield Token(TokenType.NOT, '!', self.pos)
                    self.pos += 1

            elif char == '<':
                if self._peek(1) == '=':
                    yield Token(TokenType.LESS_EQ, '<=', self.pos)
                    self.pos += 2
                else:
                    yield Token(TokenType.LESS, '<', self.pos)
                    self.pos += 1

            elif char == '>':
                if self._peek(1) == '=':
                    yield Token(TokenType.GREATER_EQ, '>=', self.pos)
                    self.pos += 2
                else:
                    yield Token(TokenType.GREATER, '>', self.pos)
                    self.pos += 1

            elif char == '&':
                if self._peek(1) == '&':
                    yield Token(TokenType.AND, '&&', self.pos)
                    self.pos += 2
                else:
                    raise TokenizerError(f"Unexpected character: {char}", self.pos)

            elif char == '|':
                if self._peek(1) == '|':
                    yield Token(TokenType.OR, '||', self.pos)
                    self.pos += 2
                else:
                    raise TokenizerError(f"Unexpected character: {char}", self.pos)

            else:
                raise TokenizerError(f"Unexpected character: {char}", self.pos)

    def _skip_whitespace(self):
        """Skip whitespace characters."""
        while self.pos < self.length and self.expression[self.pos].isspace():
            self.pos += 1

    def _peek(self, offset: int = 0) -> str:
        """Peek at character at current position + offset."""
        idx = self.pos + offset
        if idx < self.length:
            return self.expression[idx]
        return ''

    def _read_string(self) -> Token:
        """Read a string literal."""
        start_pos = self.pos
        quote = self.expression[self.pos]
        self.pos += 1
        value = []

        while self.pos < self.length:
            char = self.expression[self.pos]
            if char == quote:
                self.pos += 1
                return Token(TokenType.STRING, ''.join(value), start_pos)
            elif char == '\\':
                # Handle escape sequences
                self.pos += 1
                if self.pos < self.length:
                    escaped = self.expression[self.pos]
                    escape_map = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\'}
                    value.append(escape_map.get(escaped, escaped))
                    self.pos += 1
            else:
                value.append(char)
                self.pos += 1

        raise TokenizerError("Unterminated string literal", start_pos)

    def _read_number(self) -> Token:
        """Read a numeric literal."""
        start_pos = self.pos
        value = []
        has_dot = False

        while self.pos < self.length:
            char = self.expression[self.pos]
            if char.isdigit():
                value.append(char)
                self.pos += 1
            elif char == '.' and not has_dot:
                value.append(char)
                has_dot = True
                self.pos += 1
            else:
                break

        return Token(TokenType.NUMBER, ''.join(value), start_pos)

    def _read_identifier(self) -> Token:
        """Read an identifier, keyword, or function name."""
        start_pos = self.pos
        value = []

        while self.pos < self.length:
            char = self.expression[self.pos]
            if char.isalnum() or char == '_':
                value.append(char)
                self.pos += 1
            else:
                break

        name = ''.join(value)
        lower_name = name.lower()

        # Check for keywords
        if lower_name in self.KEYWORDS:
            return Token(self.KEYWORDS[lower_name], name, start_pos)

        # Check for row.column or context.var
        if lower_name in ('row', 'input') and self._peek() == '.':
            return self._read_column_ref(start_pos, name)

        if lower_name == 'context' and self._peek() == '.':
            return self._read_context_ref(start_pos)

        # Check for RoutineName.function pattern (PascalCase.function)
        # PascalCase identifiers start with uppercase letter
        if name[0].isupper() and self._peek() == '.':
            return self._read_routine_call(start_pos, name)

        # Check for dotted column reference: lowercase_name.column
        # This catches lookup refs (customers.name, products.price) and
        # variable refs (var.total). Not PascalCase (handled above) and
        # not keywords (handled above).
        if self._peek() == '.' and not name[0].isupper():
            return self._read_column_ref(start_pos, name)

        # Check if followed by '(' - it's a function
        self._skip_whitespace()
        if self._peek() == '(':
            if lower_name in self.FUNCTIONS:
                return Token(TokenType.FUNCTION, name, start_pos)

        return Token(TokenType.IDENTIFIER, name, start_pos)

    def _read_column_ref(self, start_pos: int, prefix: str) -> Token:
        """Read a column reference like row.column_name."""
        self.pos += 1  # Skip '.'
        col_name = []

        while self.pos < self.length:
            char = self.expression[self.pos]
            if char.isalnum() or char == '_':
                col_name.append(char)
                self.pos += 1
            else:
                break

        return Token(TokenType.COLUMN_REF, f"{prefix}.{''.join(col_name)}", start_pos)

    def _read_context_ref(self, start_pos: int) -> Token:
        """Read a context reference like context.var_name."""
        self.pos += 1  # Skip '.'
        var_name = []

        while self.pos < self.length:
            char = self.expression[self.pos]
            if char.isalnum() or char == '_':
                var_name.append(char)
                self.pos += 1
            else:
                break

        return Token(TokenType.CONTEXT_REF, f"context.{''.join(var_name)}", start_pos)

    def _read_routine_call(self, start_pos: int, routine_name: str) -> Token:
        """
        Read a routine call like RoutineName.function.

        This recognizes PascalCase.function patterns as routine calls.
        The value is stored as "RoutineName.function" for the parser.
        """
        self.pos += 1  # Skip '.'
        func_name = []

        while self.pos < self.length:
            char = self.expression[self.pos]
            if char.isalnum() or char == '_':
                func_name.append(char)
                self.pos += 1
            else:
                break

        # Must be followed by '(' to be a routine call
        self._skip_whitespace()
        if self._peek() == '(':
            return Token(
                TokenType.ROUTINE_CALL,
                f"{routine_name}.{''.join(func_name)}",
                start_pos
            )

        # Not followed by '(' - treat as regular identifier with dot access
        # Reset and return as identifier (let parser handle it)
        self.pos = start_pos + len(routine_name)
        return Token(TokenType.IDENTIFIER, routine_name, start_pos)
