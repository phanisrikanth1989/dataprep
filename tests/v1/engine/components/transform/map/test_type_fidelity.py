"""Type round-trip across Python/Java for context/globalMap.

For each Talend type, verify the value arrives in Groovy as the
expected Java class (via .getClass().getName()).

Row-data type fidelity (DataFrame columns) is exercised by the
existing TestPhase055TypeMatrix in test_map_bridge.py; this file
focuses on the context / globalMap setter path that Phase 0 / Task 1.1
locked down.

Test design note
----------------
``bridge.execute_one_time_expression`` always passes ``self.context``
(Python dict) via ``executeOneTimeExpression(..., contextVars, globalMapVars)``
which calls ``this.context.putAll(contextVars)`` on the Java side -- that
would overwrite whatever ``setContext`` stored, making the test insensitive to
the str-coercion bug. Each test therefore calls
``java_bridge.java_bridge.executeOneTimeExpression(expr, {}, {})`` directly on
the Py4J proxy, passing EMPTY context / globalMap dicts so ``putAll`` is a
no-op and the setter-stored type is preserved.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest


TYPE_CASES = [
    # (talend_type, python_value, expected_java_class)
    ("id_String",     "hello",                           "java.lang.String"),
    ("id_Integer",    42,                                "java.lang.Integer"),
    ("id_Long",       9_999_999_999,                     "java.lang.Long"),
    ("id_Boolean",    True,                              "java.lang.Boolean"),
    ("id_BigDecimal", Decimal("3.14"),                   "java.math.BigDecimal"),
    ("id_Date",       datetime.date(2025, 6, 1),         "java.util.Date"),
    ("id_DateTime",   datetime.datetime(2025, 6, 1),     "java.util.Date"),
    ("id_Double",     1.5,                               "java.lang.Double"),
]


@pytest.mark.java
@pytest.mark.parametrize("talend_type,py_value,expected_class", TYPE_CASES,
                         ids=[t[0] for t in TYPE_CASES])
def test_context_round_trip(java_bridge, talend_type, py_value, expected_class):
    """context.X arrives in Groovy as the correct Java class.

    Validates Phase 0 type-fidelity work end-to-end (str-coercion drop +
    id_Date converter + DateConverter JavaClass fix).
    """
    java_bridge.set_context("the_val", py_value)
    # Pass empty dicts so putAll is a no-op; reads the setContext-stored value.
    result = java_bridge.java_bridge.executeOneTimeExpression(
        "context.get(\"the_val\").getClass().getName()",
        {},
        {},
    )
    assert result == expected_class, (
        f"{talend_type}: expected {expected_class}, got {result}"
    )


@pytest.mark.java
@pytest.mark.parametrize("talend_type,py_value,expected_class", TYPE_CASES,
                         ids=[t[0] for t in TYPE_CASES])
def test_global_map_round_trip(java_bridge, talend_type, py_value, expected_class):
    """globalMap.get(key) returns the correct Java class.

    Validates Phase 0 type-fidelity work end-to-end (str-coercion drop +
    id_Date converter + DateConverter JavaClass fix).
    """
    java_bridge.set_global_map("the_val", py_value)
    # Pass empty dicts so putAll is a no-op; reads the setGlobalMap-stored value.
    result = java_bridge.java_bridge.executeOneTimeExpression(
        "globalMap.get(\"the_val\").getClass().getName()",
        {},
        {},
    )
    assert result == expected_class, (
        f"{talend_type}: expected {expected_class}, got {result}"
    )
