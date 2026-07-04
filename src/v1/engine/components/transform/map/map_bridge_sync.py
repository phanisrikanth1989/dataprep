"""Type-safe push of ContextManager + GlobalMap state to the Java bridge.

This is the ONLY module in the map package that touches the bridge's
internal context / global_map dicts directly. Writes are direct
(``bridge.context[k] = v``) rather than via ``bridge.set_context(k, v)``
to bypass any setter-side coercion and preserve Python value types
end-to-end. (As of Task 0.4 the setter no longer str-coerces, but direct
write keeps this module independent of setter implementation details.)

Type-aware: id_Float values are explicitly wrapped via
``gateway.jvm.java.lang.Float(v)`` because Py4J's native protocol always
sends Python ``float`` as Java ``Double``.
"""
from __future__ import annotations

from typing import Any


def push_runtime_state_to_bridge(
    context_manager: Any | None,
    global_map: Any | None,
    java_bridge: Any | None,
) -> None:
    """Flush ContextManager + GlobalMap state into the Java bridge.

    Must be called immediately before any bridge invocation that runs
    per-row Groovy. No-op when java_bridge is None.

    Args:
        context_manager: ContextManager instance, or None.
        global_map: GlobalMap instance, or None.
        java_bridge: JavaBridge wrapper, or None.
    """
    if java_bridge is None:
        return

    if context_manager is not None:
        types = getattr(context_manager, "context_types", {})
        for key, value in context_manager.get_all().items():
            value_type = types.get(key)
            if value_type == "id_Float" and isinstance(value, float):
                # Py4J protocol always emits Python float as Java Double.
                # Force Java Float via explicit JVM construction.
                java_bridge.context[key] = (
                    java_bridge.gateway.jvm.java.lang.Float(value)
                )
            else:
                # All other types: native Py4J protocol + registered date
                # converters handle serialization correctly.
                java_bridge.context[key] = value

    if global_map is not None:
        for key, value in global_map.get_all().items():
            java_bridge.global_map[key] = value
