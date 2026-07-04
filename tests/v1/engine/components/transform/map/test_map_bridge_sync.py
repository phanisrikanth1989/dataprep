"""Type-safe context + globalMap push to Java bridge."""
import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.components.transform.map.map_bridge_sync import (
    push_runtime_state_to_bridge,
)


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.context = {}
    bridge.global_map = {}
    bridge.gateway = MagicMock()
    return bridge


def test_push_basic_types(mock_bridge):
    cm = ContextManager()
    cm.set("name", "hello", "id_String")
    cm.set("count", 42, "id_Integer")
    cm.set("active", True, "id_Boolean")
    cm.set("amount", Decimal("3.14"), "id_BigDecimal")
    gm = GlobalMap()
    gm.put("session_id", "abc123")

    push_runtime_state_to_bridge(cm, gm, mock_bridge)

    assert mock_bridge.context["name"] == "hello"
    assert mock_bridge.context["count"] == 42
    assert mock_bridge.context["active"] is True
    assert mock_bridge.context["amount"] == Decimal("3.14")
    assert mock_bridge.global_map["session_id"] == "abc123"


def test_push_date_types(mock_bridge):
    cm = ContextManager()
    cm.set("batch_date", datetime.date(2025, 6, 1), "id_Date")
    cm.set("ts", datetime.datetime(2025, 6, 1, 14, 30), "id_Date")
    push_runtime_state_to_bridge(cm, None, mock_bridge)
    assert mock_bridge.context["batch_date"] == datetime.date(2025, 6, 1)
    assert mock_bridge.context["ts"] == datetime.datetime(2025, 6, 1, 14, 30)


def test_push_id_float_wraps_in_java_lang_float(mock_bridge):
    """id_Float must reach Java as java.lang.Float, not java.lang.Double.

    Py4J's native protocol serializes Python float as Java Double; this
    helper wraps via gateway.jvm.java.lang.Float(v) to force Float.
    """
    cm = ContextManager()
    cm.set("rate", 1.5, "id_Float")
    sentinel = object()
    mock_bridge.gateway.jvm.java.lang.Float.return_value = sentinel

    push_runtime_state_to_bridge(cm, None, mock_bridge)

    mock_bridge.gateway.jvm.java.lang.Float.assert_called_once_with(1.5)
    assert mock_bridge.context["rate"] is sentinel


def test_push_handles_none_bridge_gracefully():
    """No-op when bridge is None (e.g. java not enabled)."""
    cm = ContextManager()
    cm.set("x", "y", "id_String")
    push_runtime_state_to_bridge(cm, None, None)  # must not raise


def test_push_handles_none_managers(mock_bridge):
    push_runtime_state_to_bridge(None, None, mock_bridge)
    assert mock_bridge.context == {}
    assert mock_bridge.global_map == {}
