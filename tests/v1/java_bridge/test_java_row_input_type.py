"""Input-DataFrame serialization must use the INPUT column type, not the output type.

Regression for the tJavaRow null-coercion bug: a column read as ``str`` but
emitted as ``float`` (e.g. ``output_row.b = Float.parseFloat(input_row.b)``)
was serialized to Arrow using the OUTPUT type (``float``). An empty-string
input value (``""``) then became ``pd.to_numeric("") -> NaN -> Arrow null ->
Java null``, so the row body saw ``input_row.b == null`` and crashed with
``Cannot invoke method length() on null object`` /
``Cannot invoke "String.trim()" because "in" is null``.

The input DataFrame holds INPUT-typed values, so ``input_schema`` must win over
``output_schema`` when building the serialization schema. The output type is
applied separately when the result is deserialized.
"""
import pandas as pd
import pytest

from src.v1.java_bridge.bridge import JavaBridge


# ------------------------------------------------------------------
# Fast unit test (no JVM) -- the precedence itself
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSchemaDictPrecedence:
    def test_input_schema_wins_over_output_schema(self):
        """A column declared str on input but float on output serializes as str."""
        b = JavaBridge()
        df = pd.DataFrame([{"a": "sri", "b": "", "c": "kanth"}])
        output_schema = {"a": "str", "b": "float", "c": "str"}
        input_schema = {"a": "str", "b": "str", "c": "str"}
        chosen = b._schema_dict_from_df_and_output(
            df, output_schema, input_schema=input_schema
        )
        assert chosen["b"] == "str", (
            "input column must serialize with its INPUT type, not the output type"
        )
        assert chosen["a"] == "str"
        assert chosen["c"] == "str"

    def test_output_schema_used_when_input_schema_absent(self):
        """With no input_schema, output_schema is the fallback (unchanged behavior)."""
        b = JavaBridge()
        df = pd.DataFrame([{"n": 1}])
        chosen = b._schema_dict_from_df_and_output(df, {"n": "int"}, input_schema=None)
        assert chosen["n"] == "int"

    def test_pandas_inference_when_neither_declares_column(self):
        """A df column in neither schema falls back to pandas dtype inference."""
        b = JavaBridge()
        df = pd.DataFrame([{"x": "hello"}])
        chosen = b._schema_dict_from_df_and_output(df, {}, input_schema={})
        assert chosen["x"] == "str"


# ------------------------------------------------------------------
# Live-bridge tests (real JVM) -- both of the failing expression forms
# ------------------------------------------------------------------

@pytest.mark.java
class TestJavaRowStrInputFloatOutput:
    """Empty string read as str then parsed to float must yield 0.0, not crash."""

    def test_length_guard_empty_value(self, java_bridge):
        """input_row.b.length()==0 ? 0 : parseFloat(b) -- empty b -> 0.0."""
        df = pd.DataFrame([{"a": "sri", "b": "", "c": "kanth"}])
        java = (
            "output_row.a = input_row.a;\n"
            "output_row.b = input_row.b.length()==0"
            "?Float.parseFloat(\"0\"):Float.parseFloat(input_row.b);\n"
            "output_row.c = input_row.c;\n"
        )
        out = java_bridge.execute_java_row(
            df=df,
            java_code=java,
            output_schema={"a": "str", "b": "float", "c": "str"},
            input_schema={"a": "str", "b": "str", "c": "str"},
        )
        row = out.iloc[0].to_dict()
        assert row["a"] == "sri"
        assert row["b"] == 0.0
        assert row["c"] == "kanth"

    def test_equals_guard_empty_value(self, java_bridge):
        """input_row.v.equals("") ? 0 : parseFloat(v) -- empty v -> 0.0."""
        df = pd.DataFrame([{"v": ""}])
        java = (
            "output_row.v = input_row.v.equals(\"\")"
            "?Float.parseFloat(\"0\"):Float.parseFloat(input_row.v);\n"
        )
        out = java_bridge.execute_java_row(
            df=df,
            java_code=java,
            output_schema={"v": "float"},
            input_schema={"v": "str"},
        )
        assert out.iloc[0]["v"] == 0.0

    def test_nonempty_value_still_parses(self, java_bridge):
        """Regression guard: a real numeric string still parses to its float value."""
        df = pd.DataFrame([{"v": "3.5"}])
        java = (
            "output_row.v = input_row.v.length()==0"
            "?Float.parseFloat(\"0\"):Float.parseFloat(input_row.v);\n"
        )
        out = java_bridge.execute_java_row(
            df=df,
            java_code=java,
            output_schema={"v": "float"},
            input_schema={"v": "str"},
        )
        assert out.iloc[0]["v"] == pytest.approx(3.5)
