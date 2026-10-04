"""
Tests for Python Routine Support in v2 Engine.

Tests:
- RoutineManager loading and registry
- Routine function calls in expressions
- Tokenizer/Parser/Compiler integration
"""
import pytest
import polars as pl
from pathlib import Path

from src.v2.routines import RoutineManager, RoutineRegistry
from src.v2.expressions.tokenizer import Tokenizer, TokenType
from src.v2.expressions.parser import Parser, RoutineCall
from src.v2.expressions.compiler import ExpressionCompiler, compile_expression


class TestRoutineRegistry:
    """Tests for RoutineRegistry."""

    def test_register_and_get(self):
        """Test registering and retrieving functions."""
        registry = RoutineRegistry()

        def greet(name):
            return f"Hello, {name}!"

        registry.register("DemoRoutine", "greet", greet)

        # Get by separate args
        func = registry.get("DemoRoutine", "greet")
        assert func is not None
        assert func("World") == "Hello, World!"

        # Get by key
        func = registry.get_by_key("DemoRoutine.greet")
        assert func is not None
        assert func("Test") == "Hello, Test!"

    def test_has_routine(self):
        """Test checking routine existence."""
        registry = RoutineRegistry()
        registry.register("MyRoutine", "func1", lambda: None)

        assert registry.has_routine("MyRoutine")
        assert not registry.has_routine("OtherRoutine")

    def test_has_function(self):
        """Test checking function existence."""
        registry = RoutineRegistry()
        registry.register("MyRoutine", "func1", lambda: None)

        assert registry.has_function("MyRoutine", "func1")
        assert not registry.has_function("MyRoutine", "func2")

    def test_list_routines(self):
        """Test listing all routines."""
        registry = RoutineRegistry()
        registry.register("Alpha", "func1", lambda: None)
        registry.register("Beta", "func1", lambda: None)

        routines = registry.list_routines()
        assert "Alpha" in routines
        assert "Beta" in routines

    def test_list_functions(self):
        """Test listing functions for a routine."""
        registry = RoutineRegistry()
        registry.register("MyRoutine", "func1", lambda: None)
        registry.register("MyRoutine", "func2", lambda: None)

        functions = registry.list_functions("MyRoutine")
        assert "func1" in functions
        assert "func2" in functions


class TestRoutineManager:
    """Tests for RoutineManager."""

    def test_load_default_routines(self):
        """Test loading routines from default directory."""
        manager = RoutineManager()

        # Should have loaded demo routines
        routines = manager.list_routines()
        assert len(routines) > 0

    def test_load_demo_routine(self):
        """Test that DemoRoutine is loaded correctly."""
        manager = RoutineManager()

        # Check DemoRoutine exists
        assert "DemoRoutine" in manager.list_routines()

        # Check functions
        functions = manager.list_functions("DemoRoutine")
        assert "greet" in functions
        assert "is_senior_male" in functions

    def test_get_function(self):
        """Test getting a specific function."""
        manager = RoutineManager()

        greet = manager.get_function("DemoRoutine", "greet")
        assert greet is not None
        assert greet("World") == "Hello, World!"

    def test_registry_o1_lookup(self):
        """Test that registry provides O(1) lookup."""
        manager = RoutineManager()
        registry = manager.get_registry()

        # Direct key lookup
        func = registry.get_by_key("DemoRoutine.greet")
        assert func is not None
        assert func("Test") == "Hello, Test!"

    def test_aud_rtn_02_bug(self, tmp_path, caplog):
        """
        AUD-RTN-02 regression (Phase 1.1 Tier 1 fix).

        ``RoutineManager.load()`` must log the full traceback (``exc_info=True``)
        when a user routine file fails to load, per PITFALLS #7 observability
        prevention rule ("log with traceback"). Before the fix, only
        ``logger.error(f"...: {e}")`` was called — the exception message
        survived but the traceback was dropped, leaving broken user routines
        diagnosed only by their ``__str__``.

        Scenario: a routine file with a SyntaxError is dropped into a
        tmp_path routines dir. ``manager.load()`` must:
          1. NOT raise (per PITFALLS #6 "log and skip" confirmed clean) —
             other routines in the dir still get a chance to load.
          2. Produce an ERROR-level caplog record whose ``exc_info`` is
             populated (``exc_info[0] is SyntaxError``) AND whose
             ``exc_info[2]`` (traceback) is non-None — proving the traceback
             survived the logging call.
        """
        import logging

        # Build a tmp_path routines dir with one broken routine.
        broken = tmp_path / "broken_routine.py"
        broken.write_text(
            "# Intentionally broken: SyntaxError at module load time\n"
            "def greet(name:\n"  # missing closing paren + body
            "    return name\n"
        )

        caplog.clear()
        with caplog.at_level(logging.ERROR, logger="src.v2.routines.manager"):
            manager = RoutineManager(routines_dir=str(tmp_path), auto_load=False)
            manager.load()  # must NOT raise even though the file is broken

        # Manager should still report as loaded (partial load is OK per PITFALLS #6)
        assert manager._loaded is True

        # Locate the ERROR record that mentions the broken file
        matching = [
            rec for rec in caplog.records
            if rec.levelno == logging.ERROR
            and "broken_routine.py" in rec.getMessage()
        ]
        assert matching, (
            "expected an ERROR log record mentioning 'broken_routine.py' — "
            f"got {[(r.levelname, r.getMessage()) for r in caplog.records]}"
        )

        rec = matching[0]
        # The critical assertion: exc_info MUST be populated (the fix)
        assert rec.exc_info is not None, (
            "AUD-RTN-02: logger.error(...) was called without exc_info=True — "
            "the traceback was dropped. PITFALLS #7 observability prevention "
            "rule requires traceback capture for loader failures."
        )
        exc_type, exc_val, exc_tb = rec.exc_info
        assert exc_type is SyntaxError, (
            f"expected SyntaxError in exc_info[0], got {exc_type}"
        )
        assert exc_tb is not None, "exc_info[2] (traceback) must be non-None"

    def test_aud_rtn_02_happy_path_unaffected(self, tmp_path, caplog):
        """
        AUD-RTN-02 non-regression: a valid routine must still load cleanly
        with no ERROR log record emitted. The fix must not introduce
        spurious error logging on the happy path.
        """
        import logging

        good = tmp_path / "good_routine.py"
        good.write_text(
            "def greet(name):\n"
            "    return f'Hello, {name}!'\n"
        )

        caplog.clear()
        with caplog.at_level(logging.ERROR, logger="src.v2.routines.manager"):
            manager = RoutineManager(routines_dir=str(tmp_path), auto_load=False)
            manager.load()

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records == [], (
            f"happy-path load must not emit ERROR records; got {error_records}"
        )
        # And the routine loaded
        assert "GoodRoutine" in manager.list_routines()


class TestTokenizerRoutineCall:
    """Tests for tokenizer routine call recognition."""

    def test_recognize_routine_call(self):
        """Test tokenizer recognizes RoutineName.function() pattern."""
        tokenizer = Tokenizer("DemoRoutine.greet(name)")
        tokens = tokenizer.tokenize()

        assert len(tokens) >= 4
        assert tokens[0].type == TokenType.ROUTINE_CALL
        assert tokens[0].value == "DemoRoutine.greet"
        assert tokens[1].type == TokenType.LPAREN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[3].type == TokenType.RPAREN

    def test_routine_call_with_string_arg(self):
        """Test routine call with string argument."""
        tokenizer = Tokenizer('DemoRoutine.greet("World")')
        tokens = tokenizer.tokenize()

        assert tokens[0].type == TokenType.ROUTINE_CALL
        assert tokens[0].value == "DemoRoutine.greet"
        assert tokens[2].type == TokenType.STRING
        assert tokens[2].value == "World"

    def test_routine_call_multiple_args(self):
        """Test routine call with multiple arguments."""
        tokenizer = Tokenizer("StringUtils.mask_string(text, 2, 4)")
        tokens = tokenizer.tokenize()

        assert tokens[0].type == TokenType.ROUTINE_CALL
        assert tokens[0].value == "StringUtils.mask_string"

    def test_not_routine_call_without_parens(self):
        """Test PascalCase without () is not a routine call."""
        tokenizer = Tokenizer("MyConstant + 1")
        tokens = tokenizer.tokenize()

        # Should be identifier, not routine call
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "MyConstant"


class TestParserRoutineCall:
    """Tests for parser routine call handling."""

    def test_parse_routine_call(self):
        """Test parsing a routine call."""
        ast = Parser.parse("DemoRoutine.greet(name)")

        assert isinstance(ast, RoutineCall)
        assert ast.routine == "DemoRoutine"
        assert ast.function == "greet"
        assert len(ast.args) == 1

    def test_parse_routine_call_multiple_args(self):
        """Test parsing routine call with multiple args."""
        ast = Parser.parse("DemoRoutine.is_senior_male(age, gender)")

        assert isinstance(ast, RoutineCall)
        assert ast.routine == "DemoRoutine"
        assert ast.function == "is_senior_male"
        assert len(ast.args) == 2

    def test_parse_routine_call_no_args(self):
        """Test parsing routine call with no args."""
        ast = Parser.parse("MyRoutine.get_value()")

        assert isinstance(ast, RoutineCall)
        assert ast.routine == "MyRoutine"
        assert ast.function == "get_value"
        assert len(ast.args) == 0


class TestCompilerRoutineCall:
    """Tests for compiler routine call handling."""

    def test_compile_routine_call_single_arg(self):
        """Test compiling a routine call with single argument."""
        manager = RoutineManager()
        registry = manager.get_registry()

        compiler = ExpressionCompiler(routine_registry=registry)
        expr = compiler.compile("DemoRoutine.greet(name)")

        # Apply to DataFrame
        df = pl.DataFrame({"name": ["Alice", "Bob", "Charlie"]})
        result = df.select(expr.alias("greeting"))

        assert result["greeting"][0] == "Hello, Alice!"
        assert result["greeting"][1] == "Hello, Bob!"
        assert result["greeting"][2] == "Hello, Charlie!"

    def test_compile_routine_call_multiple_args(self):
        """Test compiling routine call with multiple arguments."""
        manager = RoutineManager()
        registry = manager.get_registry()

        compiler = ExpressionCompiler(routine_registry=registry)
        expr = compiler.compile("DemoRoutine.is_senior_male(age, gender)")

        # Apply to DataFrame
        df = pl.DataFrame({
            "age": [65, 55, 70, 65],
            "gender": ["Male", "Male", "Female", "Male"]
        })
        result = df.select(expr.alias("is_senior"))

        # 65 Male -> True, 55 Male -> False, 70 Female -> False, 65 Male -> True
        assert result["is_senior"][0] == True
        assert result["is_senior"][1] == False
        assert result["is_senior"][2] == False
        assert result["is_senior"][3] == True

    def test_compile_routine_call_no_registry(self):
        """Test that routine call fails without registry."""
        compiler = ExpressionCompiler()

        with pytest.raises(Exception) as exc_info:
            compiler.compile("DemoRoutine.greet(name)")

        assert "no routine registry" in str(exc_info.value).lower()

    def test_compile_unknown_routine(self):
        """Test that unknown routine raises error."""
        manager = RoutineManager()
        registry = manager.get_registry()

        compiler = ExpressionCompiler(routine_registry=registry)

        with pytest.raises(Exception) as exc_info:
            compiler.compile("UnknownRoutine.func(x)")

        assert "unknown" in str(exc_info.value).lower()


class TestRoutineIntegration:
    """Integration tests for routine support."""

    def test_routine_with_context(self):
        """Test routine calls combined with context variables."""
        manager = RoutineManager()
        registry = manager.get_registry()

        compiler = ExpressionCompiler(
            context={"prefix": "Hello"},
            routine_registry=registry
        )

        # Use context + routine
        expr = compiler.compile("DemoRoutine.greet(name)")

        df = pl.DataFrame({"name": ["World"]})
        result = df.select(expr.alias("result"))

        assert result["result"][0] == "Hello, World!"

    def test_routine_in_larger_expression(self):
        """Test routine as part of larger expression."""
        manager = RoutineManager()
        registry = manager.get_registry()

        compiler = ExpressionCompiler(routine_registry=registry)

        # Concatenate routine result with literal
        # Note: This tests that routine result can be used in expressions
        df = pl.DataFrame({"name": ["World"]})

        # First compile just the routine call
        greeting_expr = compiler.compile("DemoRoutine.greet(name)")
        result = df.select(greeting_expr.alias("greeting"))

        assert "Hello, World!" in result["greeting"][0]
