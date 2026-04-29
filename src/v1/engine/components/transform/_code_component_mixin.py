"""Mixin + module-level safe-namespace builders for code-execution components.

Phase 8 anchors:
- D-09: consolidate the four near-duplicate ``_get_context_dict`` methods that
  previously lived in each code component into a single mixin class.
- D-11: define the curated allow-list of safe builtins and standard-library
  globals that the Python code components inject into the user's exec
  namespace; ``os``, ``sys``, ``subprocess``, ``__import__``, ``open``,
  ``exec``, ``eval`` and ``compile`` are intentionally absent.

Consumers (Phase 8 components, all four inherit ``CodeComponentMixin``
mixin-first ahead of ``BaseComponent``):
- ``JavaComponent``       -- one-shot tJava
- ``JavaRowComponent``    -- per-row tJavaRow
- ``PythonComponent``     -- one-shot tPython
- ``PythonRowComponent``  -- per-row tPythonRow

The Java components only need ``_get_context_dict``; the Python components
also import the module-level whitelist constants
(``_SAFE_BUILTIN_NAMES``, ``_SAFE_NAMESPACE_GLOBALS``,
``_build_safe_builtins``).

Why module-level (not class attributes)?
The whitelist constants and the builder helper have no ``self`` dependency
and are not needed by every consumer (the Java variants ignore them).
Keeping them at module scope lets the Python components import them
directly while keeping the mixin class itself minimal. This is a Phase 8
revision-1 Warning 7 fix -- prior plans had each Python component define
its own copy, which was a near-duplicate footgun.

ASCII-only per project memory ``feedback_ascii_logging``.
"""

import datetime as _datetime_module
import decimal as _decimal_module
import json as _json_module
import math as _math_module
import re as _re_module
from typing import Any

import numpy as np
import pandas as pd


# ----------------------------------------------------------------
# Module-level safe namespace (D-11 / revision-1 Warning 7)
# ----------------------------------------------------------------

_SAFE_BUILTIN_NAMES: tuple[str, ...] = (
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
    "frozenset", "int", "isinstance", "len", "list", "map", "max", "min",
    "print", "range", "repr", "round", "set", "sorted", "str", "sum",
    "tuple", "type", "zip",
)
"""Whitelist of safe Python builtins exposed inside user exec namespaces.

Per Phase 8 D-11. Notably absent: ``__import__``, ``open``, ``exec``,
``eval``, ``compile``, ``getattr``, ``setattr``, ``delattr``,
``input``, ``vars``, ``globals``, ``locals``. ``os``, ``sys`` and
``subprocess`` are out of scope (D-12 documents this as a breaking
change vs the legacy partial implementation -- no compatibility shim
per project memory ``feedback_fix_source_no_fallbacks``).
"""


def _build_safe_builtins() -> dict[str, Any]:
    """Return a tight ``__builtins__`` dict containing only D-11 allow-listed names.

    The Python code components assign this dict to the ``__builtins__`` key
    of the user exec namespace so that ``__import__`` (and therefore
    ``import os`` / ``import sys`` etc.) is unavailable. Each call returns
    a fresh dict so callers can mutate freely without affecting subsequent
    invocations.

    Returns:
        Dict mapping each name in :data:`_SAFE_BUILTIN_NAMES` to the
        corresponding callable from the standard ``builtins`` module.
    """
    import builtins as _b  # local import; avoid leaking into module ns
    return {name: getattr(_b, name) for name in _SAFE_BUILTIN_NAMES}


_SAFE_NAMESPACE_GLOBALS: dict[str, Any] = {
    "pd": pd,
    "np": np,
    "datetime": _datetime_module,
    "json": _json_module,
    "re": _re_module,
    "math": _math_module,
    "Decimal": _decimal_module.Decimal,
}
"""Whitelist of safe modules / classes surfaced into user exec namespaces.

Per Phase 8 D-11. The Python code components spread this dict into the
user's exec namespace alongside ``__builtins__`` (built via
:func:`_build_safe_builtins`). Anything outside this dict and the
allow-listed builtins is unreachable from user code without explicit
host-side wiring.
"""


# ----------------------------------------------------------------
# Mixin
# ----------------------------------------------------------------


class CodeComponentMixin:
    """Shared helpers for code-execution components (Phase 8 D-09).

    NOT a ``BaseComponent`` subclass. Provides instance methods that read
    ``self.context_manager`` (set by ``BaseComponent.__init__``). Designed
    for cooperative multiple inheritance -- inherit mixin-first:

        class JavaComponent(CodeComponentMixin, BaseComponent):
            ...

    Has no ``__init__`` so MRO chains naturally to ``BaseComponent.__init__``.
    """

    def _get_context_dict(self) -> dict[str, Any]:
        """Return a flat ``{var_name: value}`` dict view of context variables.

        Walks ``self.context_manager.get_all()`` and flattens both the
        nested shape (``{Default: {var: {value: V, type: T}}}``) and the
        flat shape (``{var: V}``) that ``ContextManager`` may produce.
        Suitable for assignment as ``context`` inside a user-code exec
        namespace.

        Returns ``{}`` when ``self.context_manager`` is ``None`` (guards
        against ``AttributeError`` for components instantiated without a
        ContextManager).
        """
        context_dict: dict[str, Any] = {}
        if self.context_manager:
            context_all = self.context_manager.get_all()
            for context_name, context_vars in context_all.items():
                if isinstance(context_vars, dict):
                    # Nested shape: {Default: {var: {value, type}}}
                    for var_name, var_info in context_vars.items():
                        if isinstance(var_info, dict) and "value" in var_info:
                            context_dict[var_name] = var_info["value"]
                        else:
                            context_dict[var_name] = var_info
                elif context_vars is not None:
                    # Flat shape: {var: V} (top-level scalar)
                    context_dict[context_name] = context_vars
        return context_dict
