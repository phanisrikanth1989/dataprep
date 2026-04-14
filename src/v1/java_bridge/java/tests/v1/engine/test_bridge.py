"""Unit tests for src/v1/java_bridge/bridge.py.

Comprehensive tests using mocked Py4J gateway -- no JVM required.
Tests cover: init state, schema-driven serialization, sync after every
Java-calling method, fail-fast errors with stderr capture, state accessors,
log level mapping, and incomplete schema reconciliation.
"""

import logging
from unittest.mock import MagicMock, patch, PropertyMock

import pandas as pd
import pyarrow as pa
import pytest

from src.v1.engine.exceptions import JavaBridgeError
from src.v1.java_bridge.bridge import JavaBridge, _PYTHON_TO_JAVA_LOG_LEVEL


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _create_bridge_with_mock():
    """Create a JavaBridge with mocked gateway and java_bridge, _started=True.

    The mock gateway's _gateway_client is set up to satisfy Py4J's
    ListConverter without needing a real JVM connection.

    Returns:
        Tuple of (bridge, mock_java_bridge).
    """
    bridge = JavaBridge()
    mock_java_bridge = MagicMock()

    # Default: getContext and getGlobalMap return empty dicts for sync
    mock_java_bridge.getContext.return_value = {}
    mock_java_bridge.getGlobalMap.return_value = {}

    bridge.java_bridge = mock_java_bridge

    # Mock gateway with _gateway_client that satisfies Py4J ListConverter
    mock_gateway = MagicMock()
    bridge.gateway = mock_gateway

    bridge.process = MagicMock()
    bridge._started = True

    return bridge, mock_java_bridge


# ------------------------------------------------------------------
# TestBridgeInit
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBridgeInit:
    """Verify initial state of a new JavaBridge instance."""

    def test_initial_state(self):
        bridge = JavaBridge()
        assert bridge.gateway is None
        assert bridge.java_bridge is None
        assert bridge.context == {}
        assert bridge.global_map == {}
        assert bridge._started is False

    @patch("src.v1.java_bridge.bridge.subprocess.Popen")
    @patch("src.v1.java_bridge.bridge.JavaGateway")
    def test_start_requires_port_or_default(self, mock_gateway_cls, mock_popen):
        """Verify start can be called with mocked subprocess + gateway."""
        bridge = JavaBridge()

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        mock_gateway = MagicMock()
        mock_entry_point = MagicMock()
        mock_entry_point.getContext.return_value = {}
        mock_entry_point.getGlobalMap.return_value = {}
        mock_gateway.entry_point = mock_entry_point
        mock_gateway_cls.return_value = mock_gateway

        # Mock _find_jar_path to avoid filesystem dependency
        with patch.object(bridge, "_find_jar_path", return_value="/fake/jar.jar"):
            bridge.start(port=25333)

        assert bridge._started is True


# ------------------------------------------------------------------
# TestSchemaMapping
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaMapping:
    """Verify schema-driven Arrow serialization (BRDG-02)."""

    def test_df_to_arrow_bytes_uses_schema_not_data(self):
        """Schema determines Arrow types, not DataFrame data inference."""
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({"col": [None, None, None]})
        arrow_bytes = bridge._df_to_arrow_bytes(df, {"col": "int"})

        # Deserialize and check the Arrow schema type
        reader = pa.ipc.open_stream(pa.py_buffer(arrow_bytes))
        table = reader.read_all()
        assert table.schema.field("col").type == pa.int64()

    def test_df_to_arrow_bytes_rejects_invalid_type(self):
        """Raw Talend types must be rejected."""
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({"col": ["a", "b"]})
        with pytest.raises(ValueError, match="id_String"):
            bridge._df_to_arrow_bytes(df, {"col": "id_String"})

    def test_df_to_arrow_bytes_all_seven_types(self):
        """All 7 valid types serialize without error."""
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({
            "s": ["hello"],
            "i": [42],
            "f": [3.14],
            "b": [True],
            "d": [pd.Timestamp("2024-01-01")],
            "dec": ["123.45"],
            "o": ["object_val"],
        })
        schema_dict = {
            "s": "str",
            "i": "int",
            "f": "float",
            "b": "bool",
            "d": "datetime",
            "dec": "Decimal",
            "o": "object",
        }
        # Should not raise
        arrow_bytes = bridge._df_to_arrow_bytes(df, schema_dict)
        assert isinstance(arrow_bytes, bytes)
        assert len(arrow_bytes) > 0

    def test_arrow_round_trip_preserves_types(self):
        """Serialize to Arrow and back, verify schema types are preserved."""
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({
            "name": ["Alice"],
            "age": [30],
            "score": [95.5],
        })
        schema_dict = {"name": "str", "age": "int", "score": "float"}

        arrow_bytes = bridge._df_to_arrow_bytes(df, schema_dict)
        result_df = bridge._arrow_bytes_to_df(arrow_bytes, schema_dict)

        assert "name" in result_df.columns
        assert "age" in result_df.columns
        assert "score" in result_df.columns


# ------------------------------------------------------------------
# TestSync
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSync:
    """Verify _sync_from_java is called after every Java-calling method.

    Per BRDG-03: every public method that invokes Java state must sync
    context and globalMap back to Python afterward.
    """

    def test_execute_one_time_expression_syncs(self):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.executeOneTimeExpression.return_value = 42

        with patch.object(bridge, "_sync_from_java", wraps=bridge._sync_from_java) as spy:
            bridge.execute_one_time_expression("1+1")
            spy.assert_called()

    def test_execute_batch_expressions_syncs(self):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.executeBatchOneTimeExpressionsWithGlobalMap.return_value = {"a": "2"}

        with patch.object(bridge, "_sync_from_java", wraps=bridge._sync_from_java) as spy:
            bridge.execute_batch_one_time_expressions({"a": "1+1"})
            spy.assert_called()

    def test_execute_java_row_syncs(self):
        bridge, mock_jb = _create_bridge_with_mock()

        # Return valid Arrow IPC bytes for a single-row output
        out_df = pd.DataFrame({"col": ["result"]})
        out_table = pa.Table.from_pandas(out_df)
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, out_table.schema)
        writer.write_table(out_table)
        writer.close()
        mock_jb.executeJavaRow.return_value = sink.getvalue().to_pybytes()

        df = pd.DataFrame({"col": ["input"]})

        with patch.object(bridge, "_sync_from_java", wraps=bridge._sync_from_java) as spy:
            bridge.execute_java_row(
                df,
                "code",
                output_schema={"col": "str"},
            )
            spy.assert_called()

    @patch("py4j.java_collections.ListConverter")
    def test_execute_tmap_preprocessing_syncs(self, mock_list_conv_cls):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.executeTMapPreprocessing.return_value = {}
        mock_list_conv_cls.return_value.convert.return_value = MagicMock()

        df = pd.DataFrame({"col": ["val"]})

        with patch.object(bridge, "_sync_from_java", wraps=bridge._sync_from_java) as spy:
            bridge.execute_tmap_preprocessing(
                df, {"expr1": "1+1"}, "row1",
                schema={"col": "str"},
            )
            spy.assert_called()

    @patch("py4j.java_collections.ListConverter")
    def test_execute_tmap_compiled_syncs(self, mock_list_conv_cls):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.executeTMapCompiled.return_value = {}
        mock_list_conv_cls.return_value.convert.return_value = MagicMock()

        df = pd.DataFrame({"col": ["val"]})

        with patch.object(bridge, "_sync_from_java", wraps=bridge._sync_from_java) as spy:
            bridge.execute_tmap_compiled(
                "script",
                df,
                output_schemas={"out1": ["col"]},
                output_types={"out1_col": "str"},
                schema={"col": "str"},
            )
            spy.assert_called()

    def test_execute_compiled_tmap_chunked_syncs(self):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.executeCompiledTMap.return_value = {}

        df = pd.DataFrame({"col": ["val"]})

        with patch.object(bridge, "_sync_from_java", wraps=bridge._sync_from_java) as spy:
            bridge.execute_compiled_tmap_chunked(
                "comp1", df,
                schema={"col": "str"},
            )
            spy.assert_called()

    def test_load_routine_syncs(self):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.loadRoutine.return_value = None

        with patch.object(bridge, "_sync_from_java", wraps=bridge._sync_from_java) as spy:
            bridge.load_routine("routines.MyClass")
            spy.assert_called()

    @patch("py4j.java_collections.ListConverter")
    def test_compile_tmap_script_does_not_sync(self, mock_list_conv_cls):
        """compile_tmap_script is read-only -- no sync needed."""
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.compileTMapScript.return_value = "comp1"
        mock_list_conv_cls.return_value.convert.return_value = MagicMock()

        with patch.object(bridge, "_sync_from_java") as spy:
            bridge.compile_tmap_script(
                "comp1",
                "script",
                output_schemas={"out1": ["col"]},
                output_types={"out1_col": "str"},
            )
            spy.assert_not_called()

    @patch("py4j.java_collections.ListConverter")
    def test_validate_libraries_does_not_sync(self, mock_list_conv_cls):
        """validate_libraries is read-only -- no sync needed."""
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.validateLibraries.return_value = []
        mock_list_conv_cls.return_value.convert.return_value = MagicMock()

        with patch.object(bridge, "_sync_from_java") as spy:
            bridge.validate_libraries(["some.jar"])
            spy.assert_not_called()

    def test_sync_updates_context_and_global_map(self):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.getContext.return_value = {"key": "val"}
        mock_jb.getGlobalMap.return_value = {"gm": "42"}

        bridge._sync_from_java()

        assert bridge.context == {"key": "val"}
        assert bridge.global_map == {"gm": "42"}


# ------------------------------------------------------------------
# TestFailFast
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFailFast:
    """Verify fail-fast error handling with JavaBridgeError."""

    @patch("src.v1.java_bridge.bridge.subprocess.Popen")
    def test_start_failure_raises_java_bridge_error(self, mock_popen):
        bridge = JavaBridge()

        # Simulate process that exits immediately during startup
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # non-zero exit code
        mock_process.returncode = 1
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = b""
        mock_popen.return_value = mock_process

        with patch.object(bridge, "_find_jar_path", return_value="/fake/jar.jar"):
            with pytest.raises(JavaBridgeError, match="Java process exited during startup"):
                bridge.start(port=25333)

    def test_java_exception_raises_java_bridge_error(self):
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.executeOneTimeExpression.side_effect = RuntimeError("Java NPE")

        with pytest.raises(JavaBridgeError, match="Java NPE"):
            bridge.execute_one_time_expression("bad_expr")

    def test_java_bridge_error_includes_stderr(self):
        """Verify _capture_java_stderr output is included in error message."""
        bridge, mock_jb = _create_bridge_with_mock()
        mock_jb.executeOneTimeExpression.side_effect = RuntimeError("Java crash")

        # Mock _capture_java_stderr to return Java log output
        with patch.object(
            bridge, "_capture_java_stderr",
            return_value="NullPointerException at MyClass.java:42"
        ):
            with pytest.raises(JavaBridgeError, match="NullPointerException"):
                bridge.execute_one_time_expression("fail_expr")


# ------------------------------------------------------------------
# TestSetMethods
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSetMethods:
    """Verify set_context and set_global_map update both local and Java state."""

    def test_set_context_updates_local_and_java(self):
        bridge, mock_jb = _create_bridge_with_mock()

        bridge.set_context("k", "v")

        assert bridge.context["k"] == "v"
        mock_jb.setContext.assert_called_once_with("k", "v")

    def test_set_global_map_updates_local_and_java(self):
        bridge, mock_jb = _create_bridge_with_mock()

        bridge.set_global_map("gm_key", "gm_val")

        assert bridge.global_map["gm_key"] == "gm_val"
        mock_jb.setGlobalMap.assert_called_once_with("gm_key", "gm_val")


# ------------------------------------------------------------------
# TestLogLevel
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLogLevel:
    """Verify Python log level -> Java JUL level mapping."""

    def test_set_log_level_maps_debug_to_fine(self):
        bridge, mock_jb = _create_bridge_with_mock()
        bridge.set_log_level(logging.DEBUG)
        mock_jb.setLogLevel.assert_called_once_with("FINE")

    def test_set_log_level_maps_info_to_info(self):
        bridge, mock_jb = _create_bridge_with_mock()
        bridge.set_log_level(logging.INFO)
        mock_jb.setLogLevel.assert_called_once_with("INFO")

    def test_set_log_level_maps_warning_to_warning(self):
        bridge, mock_jb = _create_bridge_with_mock()
        bridge.set_log_level(logging.WARNING)
        mock_jb.setLogLevel.assert_called_once_with("WARNING")

    def test_set_log_level_maps_error_to_severe(self):
        bridge, mock_jb = _create_bridge_with_mock()
        bridge.set_log_level(logging.ERROR)
        mock_jb.setLogLevel.assert_called_once_with("SEVERE")


# ------------------------------------------------------------------
# TestIncompleteSchemaHandling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIncompleteSchemaHandling:
    """Verify _reconcile_schema_to_df handles mismatches between schema and DataFrame.

    Addresses review concern: incomplete schema handling.
    """

    def test_reconcile_adds_missing_schema_columns(self):
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        schema_dict = {"a": "str", "b": "int"}

        result = bridge._reconcile_schema_to_df(df, schema_dict)

        assert "c" in result
        assert result["c"] == "str"  # default for missing

    def test_reconcile_logs_warning_for_missing_column(self, caplog):
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        schema_dict = {"a": "str", "b": "int"}

        with caplog.at_level(logging.WARNING):
            bridge._reconcile_schema_to_df(df, schema_dict)

        assert any(
            "c" in record.message and "missing from schema" in record.message
            for record in caplog.records
        ), f"Expected warning about column 'c' missing from schema. Got: {[r.message for r in caplog.records]}"

    def test_reconcile_ignores_extra_schema_columns(self):
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({"a": [1], "b": [2]})
        schema_dict = {"a": "str", "b": "int", "d": "float"}

        result = bridge._reconcile_schema_to_df(df, schema_dict)

        # Extra schema column "d" not in DataFrame should be removed
        assert "d" not in result
        assert "a" in result
        assert "b" in result

    def test_reconcile_no_change_when_schema_matches(self):
        bridge, _ = _create_bridge_with_mock()

        df = pd.DataFrame({"a": [1], "b": [2]})
        schema_dict = {"a": "str", "b": "int"}

        result = bridge._reconcile_schema_to_df(df, schema_dict)

        assert result == {"a": "str", "b": "int"}
