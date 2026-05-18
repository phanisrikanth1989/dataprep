"""Bridge must raise on schema/DataFrame mismatch (not WARN + default to str).

Type fidelity end-to-end requires every column crossing the Python/Java
boundary to have a declared type. A DataFrame column without a schema
entry indicates an upstream bug; we want to fail loudly, not paper over
with a 'str' default.
"""
import pandas as pd
import pytest

from src.v1.engine.exceptions import ConfigurationError
from src.v1.java_bridge.bridge import JavaBridge


def test_reconcile_schema_raises_on_missing_column_type():
    bridge = JavaBridge()
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})  # 'b' not declared in schema
    schema = {"a": "int"}
    with pytest.raises(ConfigurationError) as exc_info:
        bridge._reconcile_schema_to_df(df, schema)
    msg = str(exc_info.value)
    assert "b" in msg
    assert "declared types" in msg.lower() or "schema" in msg.lower()


def test_reconcile_schema_passes_when_all_columns_declared():
    bridge = JavaBridge()
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    schema = {"a": "int", "b": "str"}
    result = bridge._reconcile_schema_to_df(df, schema)
    assert result == {"a": "int", "b": "str"}


def test_reconcile_schema_prunes_schema_columns_not_in_df():
    """Schema columns NOT present in the DataFrame are pruned (not an error)."""
    bridge = JavaBridge()
    df = pd.DataFrame({"a": [1, 2]})
    schema = {"a": "int", "extra": "str"}  # 'extra' not in df
    result = bridge._reconcile_schema_to_df(df, schema)
    assert result == {"a": "int"}  # 'extra' pruned, no error
