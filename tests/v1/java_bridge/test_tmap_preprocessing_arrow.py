"""tMap/FilterRows preprocessing results must come back in ONE Arrow payload.

``execute_tmap_preprocessing`` evaluates Groovy expressions on every row
(tFilterRow advanced conditions, tMap main/lookup filters, computed join keys,
FILTER_AS_MATCH). The legacy Java method returned ``Map<String, Object[]>``;
Python then read each Java array element-by-element over the Py4J socket --
two round trips per row, ~112s for a 1M-row tFilterRow.

The fast path returns one tagged Arrow payload for every expression whose
results are Py4J-native scalars, and keeps the legacy ``Object[]`` for any
expression that produced another Java type (Date, BigInteger, GString, List),
so those keep their exact previous behavior (live JavaObject proxies).

Contract under test: the numpy arrays returned are IDENTICAL to what the
legacy path produced -- same dtype, same element types, same values.
"""
import math
from decimal import Decimal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc
import pytest

from src.v1.java_bridge import bridge as bridge_mod


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _arrow_bytes(columns: dict) -> bytes:
    """Serialize {name: pyarrow.Array} as the Java side does (one IPC stream)."""
    table = pa.table(columns)
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _same_element(a, b) -> bool:
    """Element equality that also pins the Python type (NaN / -0.0 aware)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, np.ndarray):
        return np.array_equal(a, b)
    if isinstance(a, (float, np.floating)):
        if math.isnan(a):
            return math.isnan(b)
        return a == b and math.copysign(1.0, a) == math.copysign(1.0, b)
    if type(a).__name__ in ("JavaObject", "JavaList", "JavaMap", "JavaArray"):
        return str(a) == str(b)
    return a == b


def _assert_identical(new: np.ndarray, legacy: np.ndarray, label: str) -> None:
    assert new.dtype == legacy.dtype, f"{label}: dtype {new.dtype} != {legacy.dtype}"
    assert new.shape == legacy.shape, f"{label}: shape {new.shape} != {legacy.shape}"
    for i, (x, y) in enumerate(zip(new.tolist() if new.dtype != object else list(new),
                                   legacy.tolist() if legacy.dtype != object else list(legacy))):
        assert _same_element(x, y), f"{label}[{i}]: {x!r} ({type(x).__name__}) != {y!r} ({type(y).__name__})"


# ------------------------------------------------------------------
# Unit tests -- Python decoder of the tagged Arrow layout (no JVM)
# ------------------------------------------------------------------

T = bridge_mod


@pytest.mark.unit
class TestDecodePreprocessingArrow:
    """``_decode_preprocessing_arrow`` rebuilds the exact Py4J-converted values."""

    def test_homogeneous_string_with_nulls(self):
        payload = _arrow_bytes({
            "e#tag": pa.array([T._PREPROC_TAG_STRING, T._PREPROC_TAG_NULL, T._PREPROC_TAG_STRING], pa.int8()),
            "e#str": pa.array(["a", None, "c"], pa.string()),
        })
        assert T._decode_preprocessing_arrow(payload, ["e"]) == {"e": ["a", None, "c"]}

    def test_each_scalar_kind_round_trips_python_type(self):
        tags = [T._PREPROC_TAG_LONG, T._PREPROC_TAG_DOUBLE, T._PREPROC_TAG_BOOLEAN,
                T._PREPROC_TAG_DECIMAL, T._PREPROC_TAG_STRING, T._PREPROC_TAG_NULL]
        payload = _arrow_bytes({
            "m#tag": pa.array(tags, pa.int8()),
            "m#long": pa.array([3000000000, None, None, None, None, None], pa.int64()),
            "m#dbl": pa.array([None, -0.0, None, None, None, None], pa.float64()),
            "m#bool": pa.array([None, None, True, None, None, None], pa.bool_()),
            "m#dec": pa.array([None, None, None, "1.50", None, None], pa.string()),
            "m#str": pa.array([None, None, None, None, "x", None], pa.string()),
        })
        values = T._decode_preprocessing_arrow(payload, ["m"])["m"]
        assert [type(v).__name__ for v in values] == ["int", "float", "bool", "Decimal", "str", "NoneType"]
        assert values[0] == 3000000000
        assert math.copysign(1.0, values[1]) == -1.0
        assert values[2] is True
        assert values[3] == Decimal("1.50") and str(values[3]) == "1.50"
        assert values[4] == "x"

    def test_multiple_expressions_are_independent(self):
        payload = _arrow_bytes({
            "a#tag": pa.array([T._PREPROC_TAG_BOOLEAN] * 2, pa.int8()),
            "a#bool": pa.array([True, False], pa.bool_()),
            "b#tag": pa.array([T._PREPROC_TAG_NULL] * 2, pa.int8()),
        })
        assert T._decode_preprocessing_arrow(payload, ["a", "b"]) == {
            "a": [True, False], "b": [None, None],
        }

    def test_expression_absent_from_payload_is_not_returned(self):
        payload = _arrow_bytes({"a#tag": pa.array([T._PREPROC_TAG_NULL], pa.int8())})
        assert T._decode_preprocessing_arrow(payload, ["a", "fallback_only"]) == {"a": [None]}

    def test_zero_rows(self):
        payload = _arrow_bytes({"a#tag": pa.array([], pa.int8())})
        assert T._decode_preprocessing_arrow(payload, ["a"]) == {"a": []}


# ------------------------------------------------------------------
# Live-bridge tests (real JVM)
# ------------------------------------------------------------------

# Every result kind the legacy path can produce, including the ones that stay
# on the legacy Object[] path (Date, BigInteger, GString, List).
_TYPE_MATRIX = {
    "string": "row1.s",
    "concat": 'row1.s + "_x"',
    "int": "row1.i",
    "long_big": "3000000000L",
    "short": "(short) 7",
    "byte": "(byte) 7",
    "char": "(char) 65",
    "double": "row1.d",
    "double_lit": "1.5d",
    "float": "1.1f",
    "float_nan": "Float.NaN",
    "bool": "row1.i > 1",
    "bool_nullable": "row1.s == null ? null : row1.s.equals(\"a\")",
    "bigdec_lit": "1.50",
    "bigdec_exp": "1e3",
    "bigdec_neg0": 'new BigDecimal("-0.00")',
    "bigint": 'new BigInteger("12345678901234567890")',
    "gstring": '"v${row1.i}"',
    "date": "new Date(0L)",
    "null": "null",
    "mixed": 'row1.i > 1 ? "big" : row1.i',
    "nan": "Double.NaN",
    "list": "[1, 2]",
    "runtime_error": "row1.s.substring(99)",
    "compile_error": "row1.s +* )",
}

_SCHEMA = {"s": "str", "i": "int", "d": "float"}


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"s": ["a", None, "c"], "i": [1, 2, 3], "d": [1.25, None, -0.0]})


def _legacy_preprocess(bridge, df, expressions, schema):
    """What execute_tmap_preprocessing returned before the fast path."""
    from py4j.java_collections import ListConverter

    arrow_bytes = bridge._df_to_arrow_bytes(df, schema)
    java_lookup_names = ListConverter().convert([], bridge.gateway._gateway_client)
    result_map = bridge.java_bridge.executeTMapPreprocessing(
        arrow_bytes, expressions, "row1", java_lookup_names,
        bridge.context, bridge_mod._coerce_global_map_for_java(bridge.global_map),
    )
    return {k: np.array(list(v) if v else []) for k, v in result_map.items()}


@pytest.mark.java
class TestPreprocessingFastPathParity:
    """New path == legacy path, value for value, on the live JVM."""

    def test_type_matrix_identical_to_legacy(self, java_bridge):
        df = _frame()
        legacy = _legacy_preprocess(java_bridge, df, _TYPE_MATRIX, _SCHEMA)
        new = java_bridge.execute_tmap_preprocessing(df, _TYPE_MATRIX, "row1", [], schema=_SCHEMA)
        assert set(new) == set(legacy) == set(_TYPE_MATRIX)
        for expr_id in _TYPE_MATRIX:
            _assert_identical(new[expr_id], legacy[expr_id], expr_id)

    def test_zero_rows_identical_to_legacy(self, java_bridge):
        df = _frame().iloc[0:0]
        exprs = {"b": "row1.i > 1", "s": "row1.s"}
        legacy = _legacy_preprocess(java_bridge, df, exprs, _SCHEMA)
        new = java_bridge.execute_tmap_preprocessing(df, exprs, "row1", [], schema=_SCHEMA)
        for expr_id in exprs:
            _assert_identical(new[expr_id], legacy[expr_id], expr_id)

    def test_lookup_row_binding_identical_to_legacy(self, java_bridge):
        """Expressions over a joined frame reference lookup columns as row2.col."""
        df = pd.DataFrame({"k": ["x", "y"], "row2.v": [10, 20]})
        schema = {"k": "str", "row2.v": "int"}
        exprs = {"sum": "row2.v + 1", "key": "row1.k"}
        from py4j.java_collections import ListConverter

        arrow_bytes = java_bridge._df_to_arrow_bytes(df, schema)
        names = ListConverter().convert(["row2"], java_bridge.gateway._gateway_client)
        legacy_map = java_bridge.java_bridge.executeTMapPreprocessing(
            arrow_bytes, exprs, "row1", names, java_bridge.context,
            bridge_mod._coerce_global_map_for_java(java_bridge.global_map),
        )
        legacy = {k: np.array(list(v) if v else []) for k, v in legacy_map.items()}
        new = java_bridge.execute_tmap_preprocessing(df, exprs, "row1", ["row2"], schema=schema)
        for expr_id in exprs:
            _assert_identical(new[expr_id], legacy[expr_id], expr_id)


@pytest.mark.java
class TestPreprocessingRoundTrips:
    """The number of Py4J round trips no longer grows with the row count."""

    def test_round_trips_independent_of_row_count(self, java_bridge):
        client = java_bridge.gateway._gateway_client
        calls = {"n": 0}
        original = client.send_command

        def counting_send_command(*args, **kwargs):
            calls["n"] += 1
            return original(*args, **kwargs)

        exprs = {"flag": "row1.i % 2 == 0", "key": 'row1.s + "_k"'}
        counts = {}
        for rows in (10, 5000):
            df = pd.DataFrame({"s": [f"v{i}" for i in range(rows)], "i": list(range(rows))})
            calls["n"] = 0
            client.send_command = counting_send_command
            try:
                result = java_bridge.execute_tmap_preprocessing(
                    df, exprs, "row1", [], schema={"s": "str", "i": "int"},
                )
            finally:
                client.send_command = original
            assert len(result["flag"]) == rows
            counts[rows] = calls["n"]
        assert counts[5000] == counts[10], f"round trips grew with rows: {counts}"
