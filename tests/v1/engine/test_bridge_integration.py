"""Integration tests for the Java bridge with a real JVM.

All tests in this file are marked with @pytest.mark.java and
@pytest.mark.integration. They start a real JVM process, send data
through Arrow IPC, execute Groovy scripts, and verify round-trip
correctness.

Requires:
    - Java 11+ installed
    - Built JAR at src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar
    - Run: cd src/v1/java_bridge/java && mvn clean package -q

Run:
    python -m pytest tests/v1/engine/test_bridge_integration.py -x -q -m java
"""

import datetime
from decimal import Decimal

import pandas as pd
import pytest

from src.v1.engine.java_bridge_manager import JavaBridgeManager
from src.v1.java_bridge.bridge import JavaBridge
from src.v1.java_bridge.type_mapping import extract_precision_map


# ------------------------------------------------------------------
# Module-scoped bridge fixture (one JVM per test module -- T-02-12)
#
# Plan 14-01 deferred-issue resolution (Plan 14-10):
# Use JavaBridgeManager (dynamic port via socket.bind('', 0)) instead of
# the bare JavaBridge() default port=25333. Under pytest-xdist -n auto, each
# worker creates its own module-scoped fixture; with the default port every
# worker except one collided on bind() and the entire TestTMapCompiledExpressions
# class failed under parallel collection. Dynamic port allocation eliminates
# the contention; tests now pass under serial AND -n auto.
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def bridge():
    """Start a real Java bridge for the test module via JavaBridgeManager.

    JavaBridgeManager allocates a free port per worker (via socket.bind('', 0)),
    avoiding the port-25333 collision that crashed parallel xdist workers.
    """
    manager = JavaBridgeManager(enable=True)
    manager.start()
    try:
        yield manager.bridge
    finally:
        manager.stop()


# ------------------------------------------------------------------
# TestTypeRoundTrip (D-20 -- 12 Talend data types)
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestTypeRoundTrip:
    """Round-trip each of the 12 Talend data types through the bridge.

    For each type, we create a DataFrame, send it through execute_java_row
    with a pass-through Groovy script (output = input), and verify the data
    comes back correct.
    """

    @staticmethod
    def _passthrough_code(col_name: str) -> str:
        """Generate Groovy pass-through code: output_row.set(col, input_row.get(col))."""
        return f'output_row.set("{col_name}", input_row.get("{col_name}"));'

    def test_string_round_trip(self, bridge):
        """String column round-trips correctly."""
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("name"),
            output_schema={"name": "str"},
        )
        assert list(result["name"]) == ["Alice", "Bob", "Charlie"]

    def test_integer_round_trip(self, bridge):
        """Integer (int -> int64) round-trips correctly."""
        df = pd.DataFrame({"val": [1, 42, -100]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("val"),
            output_schema={"val": "int"},
        )
        assert list(result["val"]) == [1, 42, -100]

    def test_long_round_trip(self, bridge):
        """Long (int -> int64) round-trips correctly with large values."""
        df = pd.DataFrame({"val": [2**40, 2**50, -2**40]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("val"),
            output_schema={"val": "int"},
        )
        assert list(result["val"]) == [2**40, 2**50, -2**40]

    def test_float_round_trip(self, bridge):
        """Float (float -> float64) round-trips correctly."""
        df = pd.DataFrame({"val": [1.5, 2.7, -3.14]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("val"),
            output_schema={"val": "float"},
        )
        for actual, expected in zip(result["val"], [1.5, 2.7, -3.14]):
            assert abs(actual - expected) < 1e-10

    def test_double_round_trip(self, bridge):
        """Double (float -> float64) round-trips correctly with high precision."""
        df = pd.DataFrame({"val": [1.23456789012345, -9.87654321098765]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("val"),
            output_schema={"val": "float"},
        )
        for actual, expected in zip(result["val"], [1.23456789012345, -9.87654321098765]):
            assert abs(actual - expected) < 1e-10

    def test_big_decimal_round_trip(self, bridge):
        """BigDecimal with DEFAULT precision (38, 18) round-trips correctly."""
        df = pd.DataFrame({"amount": [Decimal("123.456789"), Decimal("999.111222")]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("amount"),
            output_schema={"amount": "Decimal"},
        )
        # Decimal comes back as Decimal objects from Arrow
        for actual, expected in zip(result["amount"], [Decimal("123.456789"), Decimal("999.111222")]):
            assert Decimal(str(actual)) == expected

    def test_big_decimal_custom_precision_round_trip(self, bridge):
        """BigDecimal with custom precision (10, 2) round-trips correctly.

        Addresses review concern: Decimal precision/scale mapping must flow
        end-to-end from schema config through Python type_mapping through
        Arrow serialization through Java and back.
        """
        schema_columns = [
            {"name": "amount", "type": "Decimal", "length": 10, "precision": 2},
        ]
        precision_map = extract_precision_map(schema_columns)
        assert precision_map == {"amount": (10, 2)}

        df = pd.DataFrame({"amount": [Decimal("123.45"), Decimal("9999.99")]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("amount"),
            output_schema={"amount": "Decimal"},
            schema_columns=schema_columns,
        )
        for actual, expected in zip(result["amount"], [Decimal("123.45"), Decimal("9999.99")]):
            actual_dec = Decimal(str(actual))
            assert actual_dec == expected, f"Expected {expected}, got {actual_dec}"

    def test_date_round_trip(self, bridge):
        """Date (datetime) round-trips correctly."""
        dates = [datetime.datetime(2024, 1, 15), datetime.datetime(2023, 6, 30)]
        df = pd.DataFrame({"dt": pd.to_datetime(dates)})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("dt"),
            output_schema={"dt": "datetime"},
        )
        result_dates = pd.to_datetime(result["dt"])
        for actual, expected in zip(result_dates, dates):
            assert actual.year == expected.year
            assert actual.month == expected.month
            assert actual.day == expected.day

    def test_timestamp_round_trip(self, bridge):
        """Timestamp (datetime with time component) round-trips correctly."""
        timestamps = [
            datetime.datetime(2024, 1, 15, 10, 30, 45),
            datetime.datetime(2023, 6, 30, 23, 59, 59),
        ]
        df = pd.DataFrame({"ts": pd.to_datetime(timestamps)})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("ts"),
            output_schema={"ts": "datetime"},
        )
        result_ts = pd.to_datetime(result["ts"])
        for actual, expected in zip(result_ts, timestamps):
            assert actual.year == expected.year
            assert actual.month == expected.month
            assert actual.day == expected.day
            assert actual.hour == expected.hour
            assert actual.minute == expected.minute

    def test_boolean_round_trip(self, bridge):
        """Boolean round-trips correctly."""
        df = pd.DataFrame({"flag": [True, False, True]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("flag"),
            output_schema={"flag": "bool"},
        )
        assert list(result["flag"]) == [True, False, True]

    def test_byte_round_trip(self, bridge):
        """Byte (small int, maps to int) round-trips correctly."""
        df = pd.DataFrame({"val": [0, 127, -128]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("val"),
            output_schema={"val": "int"},
        )
        assert list(result["val"]) == [0, 127, -128]

    def test_short_round_trip(self, bridge):
        """Short (medium int, maps to int) round-trips correctly."""
        df = pd.DataFrame({"val": [0, 32767, -32768]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("val"),
            output_schema={"val": "int"},
        )
        assert list(result["val"]) == [0, 32767, -32768]

    def test_character_round_trip(self, bridge):
        """Character (single char, maps to str) round-trips correctly."""
        df = pd.DataFrame({"ch": ["A", "Z", "9"]})
        result = bridge.execute_java_row(
            df,
            self._passthrough_code("ch"),
            output_schema={"ch": "str"},
        )
        assert list(result["ch"]) == ["A", "Z", "9"]

    def test_null_values_preserved(self, bridge):
        """None/NaN values survive round-trip for various types."""
        df = pd.DataFrame({
            "name": ["Alice", None, "Charlie"],
            "val": [1.0, float("nan"), 3.0],
        })
        result = bridge.execute_java_row(
            df,
            'output_row.set("name", input_row.get("name")); output_row.set("val", input_row.get("val"));',
            output_schema={"name": "str", "val": "float"},
        )
        # Row with null name should be null
        assert result["name"].iloc[0] == "Alice"
        assert pd.isna(result["name"].iloc[1]) or result["name"].iloc[1] is None
        assert result["name"].iloc[2] == "Charlie"
        # NaN float should stay NaN
        assert pd.notna(result["val"].iloc[0])
        assert pd.isna(result["val"].iloc[1])
        assert pd.notna(result["val"].iloc[2])

    def test_multi_column_mixed_types(self, bridge):
        """Multiple columns with different types in a single DataFrame."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "age": [30, 25],
            "score": [95.5, 87.3],
            "active": [True, False],
            "created": pd.to_datetime(["2024-01-01", "2024-06-15"]),
        })
        code = (
            'output_row.set("name", input_row.get("name")); '
            'output_row.set("age", input_row.get("age")); '
            'output_row.set("score", input_row.get("score")); '
            'output_row.set("active", input_row.get("active")); '
            'output_row.set("created", input_row.get("created"));'
        )
        result = bridge.execute_java_row(
            df,
            code,
            output_schema={
                "name": "str",
                "age": "int",
                "score": "float",
                "active": "bool",
                "created": "datetime",
            },
        )
        assert list(result["name"]) == ["Alice", "Bob"]
        assert list(result["age"]) == [30, 25]
        assert abs(result["score"].iloc[0] - 95.5) < 0.01
        assert list(result["active"]) == [True, False]


# ------------------------------------------------------------------
# TestCompiledScripts (BRDG-06)
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestCompiledScripts:
    """Test compiled script caching and execution."""

    def test_compile_and_execute(self, bridge):
        """Compile a tMap script and execute it, verify output."""
        # Script must return {outputName: {data: Object[][], count: int}}
        # where data is row-oriented and columns match outputSchemas order
        script = """
def results = [:]
def out1Data = new Object[rowCount][1]  // 1 column: upper_name
for (int i = 0; i < rowCount; i++) {
    def name = inputRoot.getVector("name").getObject(i)?.toString()
    out1Data[i][0] = name?.toUpperCase()
}
results["out1"] = ["data": out1Data, "count": rowCount]
return results
"""
        component_id = bridge.compile_tmap_script(
            "test_comp_1",
            script,
            output_schemas={"out1": ["upper_name"]},
            output_types={"out1_upper_name": "str"},
        )
        assert component_id == "test_comp_1"

        df = pd.DataFrame({"name": ["alice", "bob", "charlie"]})
        result = bridge.execute_compiled_tmap_chunked(
            "test_comp_1",
            df,
            schema={"name": "str"},
        )
        assert "out1" in result
        assert list(result["out1"]["upper_name"]) == ["ALICE", "BOB", "CHARLIE"]

    def test_compiled_script_reuse_across_chunks(self, bridge):
        """Compile once, execute 3 times with different data -- no state leakage."""
        script = """
def results = [:]
def out1Data = new Object[rowCount][1]  // 1 column: doubled
for (int i = 0; i < rowCount; i++) {
    def val = inputRoot.getVector("val").getObject(i)
    out1Data[i][0] = val != null ? ((Number)val).longValue() * 2 : null
}
results["out1"] = ["data": out1Data, "count": rowCount]
return results
"""
        bridge.compile_tmap_script(
            "test_comp_chunks",
            script,
            output_schemas={"out1": ["doubled"]},
            output_types={"out1_doubled": "Long"},
        )

        # Chunk 1
        df1 = pd.DataFrame({"val": [1, 2, 3]})
        result1 = bridge.execute_compiled_tmap_chunked(
            "test_comp_chunks", df1, schema={"val": "int"},
        )
        assert list(result1["out1"]["doubled"]) == [2, 4, 6]

        # Chunk 2
        df2 = pd.DataFrame({"val": [10, 20]})
        result2 = bridge.execute_compiled_tmap_chunked(
            "test_comp_chunks", df2, schema={"val": "int"},
        )
        assert list(result2["out1"]["doubled"]) == [20, 40]

        # Chunk 3
        df3 = pd.DataFrame({"val": [100]})
        result3 = bridge.execute_compiled_tmap_chunked(
            "test_comp_chunks", df3, schema={"val": "int"},
        )
        assert list(result3["out1"]["doubled"]) == [200]

    def test_multiple_compiled_scripts(self, bridge):
        """Compile 2 different scripts, execute each -- no cross-contamination."""
        script_add = """
def results = [:]
def out1Data = new Object[rowCount][1]
for (int i = 0; i < rowCount; i++) {
    def x = inputRoot.getVector("x").getObject(i)
    out1Data[i][0] = x != null ? ((Number)x).longValue() + 10 : null
}
results["out1"] = ["data": out1Data, "count": rowCount]
return results
"""
        script_mul = """
def results = [:]
def out1Data = new Object[rowCount][1]
for (int i = 0; i < rowCount; i++) {
    def x = inputRoot.getVector("x").getObject(i)
    out1Data[i][0] = x != null ? ((Number)x).longValue() * 3 : null
}
results["out1"] = ["data": out1Data, "count": rowCount]
return results
"""
        bridge.compile_tmap_script(
            "test_add_10",
            script_add,
            output_schemas={"out1": ["result"]},
            output_types={"out1_result": "Long"},
        )
        bridge.compile_tmap_script(
            "test_mul_3",
            script_mul,
            output_schemas={"out1": ["result"]},
            output_types={"out1_result": "Long"},
        )

        df = pd.DataFrame({"x": [5, 10]})

        result_add = bridge.execute_compiled_tmap_chunked(
            "test_add_10", df, schema={"x": "int"},
        )
        result_mul = bridge.execute_compiled_tmap_chunked(
            "test_mul_3", df, schema={"x": "int"},
        )

        assert list(result_add["out1"]["result"]) == [15, 20]
        assert list(result_mul["out1"]["result"]) == [15, 30]


# ------------------------------------------------------------------
# TestBatchExpressions (BRDG-03 sync)
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestBatchExpressions:
    """Test batch expression execution and state synchronization."""

    def test_batch_expressions_return_values(self, bridge):
        """Batch execute expressions and verify return values."""
        result = bridge.execute_batch_one_time_expressions({
            "a": "1+1",
            "b": "'hello'.toUpperCase()",
        })
        assert str(result["a"]) == "2"
        assert str(result["b"]) == "HELLO"

    def test_globalmap_sync_after_batch(self, bridge):
        """Set globalMap, execute expression that reads it, verify sync."""
        bridge.set_global_map("test_key", "test_value")

        result = bridge.execute_batch_one_time_expressions({
            "check": "globalMap.get('test_key')",
        })
        assert str(result["check"]) == "test_value"

    def test_context_sync_after_expression(self, bridge):
        """Set context, execute expression accessing it, verify."""
        bridge.set_context("my_param", "42")

        result = bridge.execute_one_time_expression("context.get('my_param')")
        assert str(result) == "42"


# ------------------------------------------------------------------
# TestLibraryValidation (BRDG-04)
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestLibraryValidation:
    """Test library validation against real classpath."""

    def test_validate_existing_libraries(self, bridge):
        """Validate a class that's known to be on the classpath."""
        # The bridge JAR itself contains com.citi.gru.etl.JavaBridge
        missing = bridge.validate_libraries(["com.citi.gru.etl.JavaBridge"])
        assert missing == [], f"Expected no missing libraries, got: {missing}"

    def test_validate_missing_library(self, bridge):
        """Non-existent path should appear in missing list."""
        missing = bridge.validate_libraries(["/nonexistent/fake-library-42.jar"])
        assert len(missing) == 1
        assert "/nonexistent/fake-library-42.jar" in missing


# ------------------------------------------------------------------
# TestPy4JVersion (BRDG-05)
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestPy4JVersion:
    """Verify Py4J version compatibility on both sides."""

    def test_py4j_python_version(self):
        """Python-side Py4J is 0.10.9.9."""
        import py4j
        # py4j.__version__ may not exist in all builds, check for it
        if hasattr(py4j, "__version__"):
            assert py4j.__version__.startswith("0.10.9")
        # If no __version__, the import itself confirms compatibility

    def test_bridge_connects_successfully(self, bridge):
        """Bridge start + connectivity confirms Py4J compatibility."""
        assert bridge._started is True
        # If we get here, the Python Py4J client and Java Py4J server
        # connected successfully, confirming version compatibility
        result = bridge.execute_one_time_expression("42")
        assert str(result) == "42"


# ------------------------------------------------------------------
# TestLifecycle
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestLifecycle:
    """Test bridge lifecycle management."""

    def test_start_stop_cycle(self):
        """Start bridge, verify running, stop, verify stopped."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]

        b = JavaBridge()
        b.start(port=port)
        assert b._started is True
        assert b.gateway is not None
        assert b.java_bridge is not None

        b.stop()
        assert b._started is False
        assert b.gateway is None
        assert b.java_bridge is None

    def test_double_stop_no_error(self):
        """Stopping an already-stopped bridge should not raise."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]

        b = JavaBridge()
        b.start(port=port)
        b.stop()
        # Second stop should be a no-op
        b.stop()
        assert b._started is False


# ------------------------------------------------------------------
# TestTMapCompiledExpressions (Phase 5.1 -- Arrow type extraction fix)
# ------------------------------------------------------------------


@pytest.mark.java
@pytest.mark.integration
class TestTMapCompiledExpressions:
    """Test compiled tMap scripts with expressions that require proper Java types.

    These tests exercise the extractTypedValue fix in JavaBridge.buildArrowRowWrapper().
    Before the fix, VarChar columns returned Arrow Text objects instead of Java Strings,
    causing Groovy's + operator to hang indefinitely.
    """

    def test_string_concatenation(self, bridge):
        """String concat via compiled tMap -- the exact bug scenario (D-01).

        Before fix: row1.first_name + " " + row1.last_name causes infinite hang
        because VarCharVector.getObject() returns Arrow Text, not java.lang.String.
        After fix: extractTypedValue converts to String, concat works normally.
        """
        script = """
import java.util.*;
import com.citi.gru.etl.RowWrapper;
Object[][] out1_data = new Object[rowCount][1];
int out1_count = 0;
for (int i = 0; i < rowCount; i++) {
    RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1");
    out1_data[out1_count] = new Object[]{ row1.first_name + " " + row1.last_name };
    out1_count++;
}
Map<String, Map<String, Object>> results = new HashMap<>();
Map<String, Object> out1_result = new HashMap<>();
out1_result.put("data", out1_data);
out1_result.put("count", out1_count);
results.put("out1", out1_result);
return results;
"""
        bridge.compile_tmap_script(
            "test_string_concat",
            script,
            output_schemas={"out1": ["full_name"]},
            output_types={"out1_full_name": "str"},
            main_table_name="row1",
            lookup_names=[],
        )

        df = pd.DataFrame({
            "row1.first_name": ["John", "Jane"],
            "row1.last_name": ["Smith", "Doe"],
        })
        result = bridge.execute_compiled_tmap_chunked(
            "test_string_concat", df,
            schema={"row1.first_name": "str", "row1.last_name": "str"},
        )
        assert "out1" in result
        assert list(result["out1"]["full_name"]) == ["John Smith", "Jane Doe"]

    def test_ternary_expression(self, bridge):
        """Ternary conditional -- salary grade from numeric comparison.

        Tests that numeric values from Arrow (Float8Vector -> double) work
        correctly in Groovy ternary expressions with Number casting.
        """
        script = """
import java.util.*;
import com.citi.gru.etl.RowWrapper;
Object[][] out1_data = new Object[rowCount][1];
int out1_count = 0;
for (int i = 0; i < rowCount; i++) {
    RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1");
    Object salary = row1.salary;
    out1_data[out1_count] = new Object[]{
        ((Number)salary).doubleValue() >= 75000 ? "Senior" : "Junior"
    };
    out1_count++;
}
Map<String, Map<String, Object>> results = new HashMap<>();
Map<String, Object> out1_result = new HashMap<>();
out1_result.put("data", out1_data);
out1_result.put("count", out1_count);
results.put("out1", out1_result);
return results;
"""
        bridge.compile_tmap_script(
            "test_ternary",
            script,
            output_schemas={"out1": ["grade"]},
            output_types={"out1_grade": "str"},
            main_table_name="row1",
            lookup_names=[],
        )

        df = pd.DataFrame({"row1.salary": [85000.0, 65000.0, 90000.0]})
        result = bridge.execute_compiled_tmap_chunked(
            "test_ternary", df,
            schema={"row1.salary": "float"},
        )
        assert "out1" in result
        assert list(result["out1"]["grade"]) == ["Senior", "Junior", "Senior"]

    def test_cross_table_lookup_expression(self, bridge):
        """Cross-table column access combining main + lookup table values.

        Tests that buildRowWrapper correctly creates separate RowWrappers
        for main and lookup tables, both with proper String type extraction.
        """
        script = """
import java.util.*;
import com.citi.gru.etl.RowWrapper;
Object[][] out1_data = new Object[rowCount][1];
int out1_count = 0;
for (int i = 0; i < rowCount; i++) {
    RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1");
    RowWrapper countries = buildRowWrapper(inputRoot, i, "countries");
    out1_data[out1_count] = new Object[]{
        row1.first_name + " from " + countries.country_name
    };
    out1_count++;
}
Map<String, Map<String, Object>> results = new HashMap<>();
Map<String, Object> out1_result = new HashMap<>();
out1_result.put("data", out1_data);
out1_result.put("count", out1_count);
results.put("out1", out1_result);
return results;
"""
        bridge.compile_tmap_script(
            "test_cross_table",
            script,
            output_schemas={"out1": ["description"]},
            output_types={"out1_description": "str"},
            main_table_name="row1",
            lookup_names=["countries"],
        )

        df = pd.DataFrame({
            "row1.first_name": ["John", "Jane"],
            "countries.country_name": ["USA", "UK"],
        })
        result = bridge.execute_compiled_tmap_chunked(
            "test_cross_table", df,
            schema={
                "row1.first_name": "str",
                "countries.country_name": "str",
            },
        )
        assert "out1" in result
        assert list(result["out1"]["description"]) == [
            "John from USA", "Jane from UK"
        ]

    def test_null_handling_in_expressions(self, bridge):
        """Null-safe string concatenation with null check in Groovy.

        Tests that null values from Arrow (isNull check in extractTypedValue)
        are properly handled in Groovy null-safe expressions.
        """
        script = """
import java.util.*;
import com.citi.gru.etl.RowWrapper;
Object[][] out1_data = new Object[rowCount][1];
int out1_count = 0;
for (int i = 0; i < rowCount; i++) {
    RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1");
    String firstName = row1.first_name != null ? (String)row1.first_name : "Unknown";
    out1_data[out1_count] = new Object[]{ firstName + " " + row1.last_name };
    out1_count++;
}
Map<String, Map<String, Object>> results = new HashMap<>();
Map<String, Object> out1_result = new HashMap<>();
out1_result.put("data", out1_data);
out1_result.put("count", out1_count);
results.put("out1", out1_result);
return results;
"""
        bridge.compile_tmap_script(
            "test_null_handling",
            script,
            output_schemas={"out1": ["full_name"]},
            output_types={"out1_full_name": "str"},
            main_table_name="row1",
            lookup_names=[],
        )

        df = pd.DataFrame({
            "row1.first_name": ["John", None],
            "row1.last_name": ["Smith", "Doe"],
        })
        result = bridge.execute_compiled_tmap_chunked(
            "test_null_handling", df,
            schema={"row1.first_name": "str", "row1.last_name": "str"},
        )
        assert "out1" in result
        assert list(result["out1"]["full_name"]) == ["John Smith", "Unknown Doe"]
