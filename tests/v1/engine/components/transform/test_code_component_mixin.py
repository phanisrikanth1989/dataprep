# Phase 8 D-09 + D-11 / PYCO-03 -- mixin and namespace-constants tests
"""Unit tests for CodeComponentMixin and module-level safe-namespace constants.

Covers Phase 8 Plan 01 Task 1 (D-09 mixin + D-11 / revision-1 Warning 7
whitelist constants). The mixin class itself only carries
``_get_context_dict``; the namespace constants live at module scope and are
imported by the Python code components directly.

No real ``ContextManager`` is needed -- the mixin simply reads
``self.context_manager.get_all()``. We use ``unittest.mock.MagicMock`` to
simulate the context manager.
"""
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.v1.engine.components.transform._code_component_mixin import (
    CodeComponentMixin,
    _SAFE_BUILTIN_NAMES,
    _SAFE_NAMESPACE_GLOBALS,
    _build_safe_builtins,
)


# ----------------------------------------------------------------
# Test probe (lightweight class to exercise the mixin)
# ----------------------------------------------------------------


class _Probe(CodeComponentMixin):
    """Bare consumer of the mixin -- no BaseComponent needed for unit tests."""

    def __init__(self, context_manager: Any) -> None:
        self.context_manager = context_manager


def _make_cm(get_all_return: Any) -> MagicMock:
    """Build a MagicMock context_manager whose get_all() returns the given value."""
    cm = MagicMock()
    cm.get_all.return_value = get_all_return
    return cm


# ----------------------------------------------------------------
# Tests 1-5: _get_context_dict behavior (D-09)
# ----------------------------------------------------------------


def test_get_context_dict_empty_when_no_manager():
    """Test 1: ``self.context_manager=None`` returns ``{}`` (no AttributeError)."""
    probe = _Probe(context_manager=None)
    assert probe._get_context_dict() == {}


def test_get_context_dict_flattens_nested_value_type_shape():
    """Test 2: nested {Default: {var: {value, type}}} flattens to {var: value}."""
    cm = _make_cm({"Default": {"VAR1": {"value": "x", "type": "id_String"}}})
    probe = _Probe(context_manager=cm)
    assert probe._get_context_dict() == {"VAR1": "x"}


def test_get_context_dict_flattens_flat_shape():
    """Test 3: nested {Default: {var: V}} flattens to {var: V} when var_info is not a dict-with-value."""
    cm = _make_cm({"Default": {"VAR1": "y"}})
    probe = _Probe(context_manager=cm)
    assert probe._get_context_dict() == {"VAR1": "y"}


def test_get_context_dict_handles_top_level_scalar():
    """Test 4: top-level {var: V} (no Default wrapping) returns {var: V}."""
    cm = _make_cm({"VAR1": "z"})
    probe = _Probe(context_manager=cm)
    assert probe._get_context_dict() == {"VAR1": "z"}


def test_class_only_exposes_get_context_dict():
    """Test 5: the mixin class has exactly one public/protected method (scope-creep guard)."""
    methods = [
        name
        for name in vars(CodeComponentMixin)
        if callable(vars(CodeComponentMixin)[name]) and not name.startswith("__")
    ]
    assert methods == ["_get_context_dict"], (
        f"CodeComponentMixin should expose exactly one method, found: {methods}"
    )


# ----------------------------------------------------------------
# Tests 6-9: module-level namespace constants (D-11 / revision-1 Warning 7)
# ----------------------------------------------------------------


def test_safe_builtin_names_locked_set():
    """Test 6: _SAFE_BUILTIN_NAMES exposes exactly the D-11 allow list."""
    expected = {
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "frozenset", "int", "isinstance", "len", "list", "map", "max", "min",
        "print", "range", "repr", "round", "set", "sorted", "str", "sum",
        "tuple", "type", "zip",
    }
    assert set(_SAFE_BUILTIN_NAMES) == expected
    # Also assert no duplicates / stable ordering as a tuple
    assert isinstance(_SAFE_BUILTIN_NAMES, tuple)
    assert len(_SAFE_BUILTIN_NAMES) == len(expected)


def test_safe_namespace_globals_keys():
    """Test 7: _SAFE_NAMESPACE_GLOBALS exposes exactly the D-11 module/class set."""
    expected = {"pd", "np", "datetime", "json", "re", "math", "Decimal"}
    assert set(_SAFE_NAMESPACE_GLOBALS.keys()) == expected


def test_build_safe_builtins_returns_only_allow_list():
    """Test 8: _build_safe_builtins() returns a dict whose keys exactly equal _SAFE_BUILTIN_NAMES."""
    builtins_dict = _build_safe_builtins()
    assert set(builtins_dict.keys()) == set(_SAFE_BUILTIN_NAMES)
    # Every value is the actual callable from the builtins module
    import builtins as _b
    for name in _SAFE_BUILTIN_NAMES:
        assert builtins_dict[name] is getattr(_b, name)


@pytest.mark.parametrize(
    "dangerous_name",
    ["os", "sys", "subprocess", "__import__", "open", "exec", "eval", "compile"],
)
def test_safe_builtins_blocks_dangerous_names(dangerous_name: str):
    """Test 9: D-11/D-12 negative check -- dangerous names are NOT in the safe builtins dict."""
    builtins_dict = _build_safe_builtins()
    assert dangerous_name not in builtins_dict, (
        f"{dangerous_name!r} must not appear in _build_safe_builtins() (D-11/D-12)"
    )
