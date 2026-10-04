"""
Trigger evaluation for V2 engine orchestration.

Provides a safe expression evaluator for conditional triggers.
No eval() — uses a simple recursive descent parser.
"""
import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List

from ..config.job_config import TriggerConnection, TriggerType
from .stage import StageStatus

logger = logging.getLogger(__name__)


class TriggerEvaluator:
    """Evaluates trigger conditions to determine if a stage should run."""

    @classmethod
    def evaluate(
        cls,
        trigger: TriggerConnection,
        source_status: StageStatus,
        context_vars: Dict[str, Any],
    ) -> bool:
        """Evaluate a trigger against source stage status and context.

        Args:
            trigger: The trigger connection to evaluate.
            source_status: Status of the source stage.
            context_vars: Current context variables.

        Returns:
            True if the trigger is satisfied and target stage should run.
        """
        if trigger.type == TriggerType.ON_SUCCESS:
            return source_status == StageStatus.SUCCESS

        if trigger.type == TriggerType.ON_FAILURE:
            return source_status == StageStatus.FAILED

        if trigger.type == TriggerType.CONDITIONAL:
            # Conditional triggers don't fire if source was skipped
            if source_status == StageStatus.SKIPPED:
                return False
            return cls._evaluate_condition(trigger.condition, context_vars)

        return False

    @classmethod
    def _evaluate_condition(
        cls, condition: str, context_vars: Dict[str, Any]
    ) -> bool:
        """Evaluate a conditional expression safely.

        Process:
        1. Resolve ${context.var} references to Python values
        2. Tokenize the expression
        3. Parse into AST (recursive descent)
        4. Evaluate AST to boolean
        """
        if not condition:
            return False

        resolved = cls._resolve_context_refs(condition, context_vars)
        tokens = _Tokenizer(resolved).tokenize()
        ast = _Parser(tokens).parse()
        result = _evaluate(ast)
        return bool(result)

    @classmethod
    def _resolve_context_refs(
        cls, condition: str, context_vars: Dict[str, Any]
    ) -> str:
        """Replace ${context.var} with actual values, properly formatted."""
        def _replace(match):
            var_name = match.group(1)
            if var_name not in context_vars:
                raise ValueError(
                    f"Unresolved context variable in condition: "
                    f"'${{{f'context.{var_name}'}}}'"
                )
            value = context_vars[var_name]
            if isinstance(value, str):
                escaped = value.replace("'", "\\'")
                return f"'{escaped}'"
            if isinstance(value, bool):
                return "true" if value else "false"
            if value is None:
                return "null"
            return str(value)

        return re.sub(r'\$\{context\.(\w+)\}', _replace, condition)


# ── Tokenizer ────────────────────────────────────────────────────────

class _TokenType(Enum):
    NUMBER = auto()
    STRING = auto()
    BOOLEAN = auto()
    NULL = auto()
    IDENTIFIER = auto()
    EQ = auto()       # ==
    NEQ = auto()      # !=
    GT = auto()       # >
    GTE = auto()      # >=
    LT = auto()       # <
    LTE = auto()      # <=
    AND = auto()
    OR = auto()
    NOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    EOF = auto()


@dataclass
class _Token:
    type: _TokenType
    value: Any


class _Tokenizer:
    """Simple tokenizer for condition expressions."""

    def __init__(self, text: str):
        self._text = text
        self._pos = 0

    def tokenize(self) -> List[_Token]:
        tokens = []
        while self._pos < len(self._text):
            ch = self._text[self._pos]

            if ch.isspace():
                self._pos += 1
                continue

            if ch == '(':
                tokens.append(_Token(_TokenType.LPAREN, '('))
                self._pos += 1
            elif ch == ')':
                tokens.append(_Token(_TokenType.RPAREN, ')'))
                self._pos += 1
            elif ch == '=' and self._peek(1) == '=':
                tokens.append(_Token(_TokenType.EQ, '=='))
                self._pos += 2
            elif ch == '!' and self._peek(1) == '=':
                tokens.append(_Token(_TokenType.NEQ, '!='))
                self._pos += 2
            elif ch == '>' and self._peek(1) == '=':
                tokens.append(_Token(_TokenType.GTE, '>='))
                self._pos += 2
            elif ch == '<' and self._peek(1) == '=':
                tokens.append(_Token(_TokenType.LTE, '<='))
                self._pos += 2
            elif ch == '>':
                tokens.append(_Token(_TokenType.GT, '>'))
                self._pos += 1
            elif ch == '<':
                tokens.append(_Token(_TokenType.LT, '<'))
                self._pos += 1
            elif ch in ("'", '"'):
                tokens.append(self._read_string(ch))
            elif ch.isdigit() or (ch == '-' and self._peek(1).isdigit()):
                tokens.append(self._read_number())
            elif ch.isalpha() or ch == '_':
                tokens.append(self._read_keyword_or_identifier())
            else:
                raise ValueError(f"Unexpected character in condition: '{ch}' at position {self._pos}")

        tokens.append(_Token(_TokenType.EOF, None))
        return tokens

    def _peek(self, offset: int = 0) -> str:
        pos = self._pos + offset
        if pos < len(self._text):
            return self._text[pos]
        return ''

    def _read_string(self, quote: str) -> _Token:
        self._pos += 1  # skip opening quote
        start = self._pos
        while self._pos < len(self._text) and self._text[self._pos] != quote:
            if self._text[self._pos] == '\\':
                self._pos += 1  # skip escaped char
            self._pos += 1
        value = self._text[start:self._pos]
        self._pos += 1  # skip closing quote
        return _Token(_TokenType.STRING, value)

    def _read_number(self) -> _Token:
        start = self._pos
        if self._text[self._pos] == '-':
            self._pos += 1
        while self._pos < len(self._text) and (self._text[self._pos].isdigit() or self._text[self._pos] == '.'):
            self._pos += 1
        text = self._text[start:self._pos]
        value = float(text) if '.' in text else int(text)
        return _Token(_TokenType.NUMBER, value)

    def _read_keyword_or_identifier(self) -> _Token:
        start = self._pos
        while self._pos < len(self._text) and (self._text[self._pos].isalnum() or self._text[self._pos] == '_'):
            self._pos += 1
        word = self._text[start:self._pos]
        if word == 'true':
            return _Token(_TokenType.BOOLEAN, True)
        if word == 'false':
            return _Token(_TokenType.BOOLEAN, False)
        if word == 'null':
            return _Token(_TokenType.NULL, None)
        if word == 'and':
            return _Token(_TokenType.AND, 'and')
        if word == 'or':
            return _Token(_TokenType.OR, 'or')
        if word == 'not':
            return _Token(_TokenType.NOT, 'not')
        return _Token(_TokenType.IDENTIFIER, word)


# ── Parser ───────────────────────────────────────────────────────────

class _Parser:
    """Recursive descent parser for condition expressions.

    Grammar (lowest to highest precedence):
        expr     -> or_expr
        or_expr  -> and_expr ('or' and_expr)*
        and_expr -> not_expr ('and' not_expr)*
        not_expr -> 'not' not_expr | comparison
        comparison -> primary (('==' | '!=' | '>' | '>=' | '<' | '<=') primary)?
        primary  -> literal | '(' expr ')'
        literal  -> NUMBER | STRING | BOOLEAN | NULL | IDENTIFIER
    """

    def __init__(self, tokens: List[_Token]):
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> dict:
        node = self._parse_or()
        if self._current().type != _TokenType.EOF:
            raise ValueError(
                f"Unexpected token after expression: {self._current()}"
            )
        return node

    def _current(self) -> _Token:
        return self._tokens[self._pos]

    def _advance(self) -> _Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _parse_or(self) -> dict:
        left = self._parse_and()
        while self._current().type == _TokenType.OR:
            self._advance()
            right = self._parse_and()
            left = {"type": "binary", "op": "or", "left": left, "right": right}
        return left

    def _parse_and(self) -> dict:
        left = self._parse_not()
        while self._current().type == _TokenType.AND:
            self._advance()
            right = self._parse_not()
            left = {"type": "binary", "op": "and", "left": left, "right": right}
        return left

    def _parse_not(self) -> dict:
        if self._current().type == _TokenType.NOT:
            self._advance()
            operand = self._parse_not()
            return {"type": "unary", "op": "not", "operand": operand}
        return self._parse_comparison()

    def _parse_comparison(self) -> dict:
        left = self._parse_primary()
        comp_types = {
            _TokenType.EQ: "==",
            _TokenType.NEQ: "!=",
            _TokenType.GT: ">",
            _TokenType.GTE: ">=",
            _TokenType.LT: "<",
            _TokenType.LTE: "<=",
        }
        if self._current().type in comp_types:
            op = comp_types[self._current().type]
            self._advance()
            right = self._parse_primary()
            return {"type": "binary", "op": op, "left": left, "right": right}
        return left

    def _parse_primary(self) -> dict:
        token = self._current()
        if token.type == _TokenType.LPAREN:
            self._advance()  # skip (
            node = self._parse_or()
            if self._current().type != _TokenType.RPAREN:
                raise ValueError("Expected closing ')'")
            self._advance()  # skip )
            return node
        if token.type in (_TokenType.NUMBER, _TokenType.STRING,
                          _TokenType.BOOLEAN, _TokenType.NULL,
                          _TokenType.IDENTIFIER):
            self._advance()
            return {"type": "literal", "value": token.value}
        raise ValueError(f"Unexpected token: {token}")


# ── Evaluator ────────────────────────────────────────────────────────

def _evaluate(node: dict) -> Any:
    """Evaluate an AST node to a Python value."""
    if node["type"] == "literal":
        return node["value"]

    if node["type"] == "unary":
        operand = _evaluate(node["operand"])
        if node["op"] == "not":
            return not operand
        raise ValueError(f"Unknown unary op: {node['op']}")

    if node["type"] == "binary":
        left = _evaluate(node["left"])
        right = _evaluate(node["right"])
        op = node["op"]

        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == "and":
            return bool(left) and bool(right)
        if op == "or":
            return bool(left) or bool(right)
        raise ValueError(f"Unknown binary op: {op}")

    raise ValueError(f"Unknown AST node type: {node['type']}")
