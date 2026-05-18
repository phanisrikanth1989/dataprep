"""Type fidelity for set_context / set_global_map (drop str-coercion).

Verifies the bridge passes Python value types through to Java without
coercing to str. The Java side (Task 0.2) accepts Object, so any Py4J-
serializable Python type should arrive as the corresponding Java class.

Test design note
----------------
``bridge.execute_one_time_expression`` always passes ``self.context``
(Python dict) via ``executeOneTimeExpression(..., contextVars, globalMapVars)``
which calls ``this.context.putAll(contextVars)`` on the Java side -- that
would overwrite whatever ``setContext`` stored, making the test insensitive to
the str-coercion bug. Instead, each test:

1. Calls ``set_context``/``set_global_map`` to write the value via the setter
   under test.
2. Reads the Java-side stored value back by calling
   ``java_bridge.java_bridge.executeOneTimeExpression(expr, {}, {})``
   directly on the Py4J proxy, passing EMPTY context / globalMap dicts so
   ``putAll`` is a no-op and the stored type is preserved.

Before Task 0.4 fix (str-coercion present):
    ``set_context("x", 42)`` -> ``setContext("x", "42")`` -> stored as String
    -> ``context.get("x").getClass().getName()`` returns ``java.lang.String``
    -> tests FAIL

After Task 0.4 fix (no str-coercion):
    ``set_context("x", 42)`` -> ``setContext("x", 42)`` -> stored as Integer
    -> ``context.get("x").getClass().getName()`` returns ``java.lang.Integer``
    -> tests PASS
"""
import datetime
from decimal import Decimal

import pytest


@pytest.mark.java
class TestSetContextTypeFidelity:
    """Values stored via set_context must arrive in Java with the correct type."""

    def test_int_stays_int(self, java_bridge):
        java_bridge.set_context("the_int", 42)
        # Pass empty dicts so putAll is a no-op; reads the setContext-stored value.
        result = java_bridge.java_bridge.executeOneTimeExpression(
            "context.get(\"the_int\").getClass().getName()",
            {},
            {},
        )
        # Py4J sends small ints as Integer, large ints as Long
        assert result in ("java.lang.Integer", "java.lang.Long"), result

    def test_decimal_stays_bigdecimal(self, java_bridge):
        java_bridge.set_context("the_dec", Decimal("3.14"))
        result = java_bridge.java_bridge.executeOneTimeExpression(
            "context.get(\"the_dec\").getClass().getName()",
            {},
            {},
        )
        assert result == "java.math.BigDecimal"

    def test_date_stays_date(self, java_bridge):
        java_bridge.set_context("the_date", datetime.date(2025, 6, 1))
        result = java_bridge.java_bridge.executeOneTimeExpression(
            "context.get(\"the_date\").getClass().getName()",
            {},
            {},
        )
        assert result == "java.util.Date"

    def test_global_map_int_stays_int(self, java_bridge):
        java_bridge.set_global_map("gm_int", 100)
        result = java_bridge.java_bridge.executeOneTimeExpression(
            "globalMap.get(\"gm_int\").getClass().getName()",
            {},
            {},
        )
        assert result in ("java.lang.Integer", "java.lang.Long"), result
