"""Loader for curated per-component config schemas + live enum_ref resolution."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"

BASE_KEYS = frozenset({
    "die_on_error", "execution_mode", "chunk_size",
    "tstatcatcher_stats", "label", "component_type",
})
IGNORED_KEYS = frozenset({
    "original_type", "position", "id", "type", "schema",
    "inputs", "outputs", "subjob_id", "is_subjob_start", "connector",
})


def _index() -> dict:
    with (_SCHEMA_DIR / "_index.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def is_curated(component_type: str) -> bool:
    """Return True iff the component type (or alias) has a curated schema.

    Curated types are the keys of the ``_index.json`` index. Only curated types
    get strict, enum_ref-backed validation; every other registered engine
    component is validated advisory-only (correctness falls to the engine's own
    ``_validate_config`` plus the oracle).

    Args:
        component_type: Engine component type or one of its aliases.

    Returns:
        True if a curated schema exists for the type, False otherwise.
    """
    return component_type in _index()


def load_schema(component_type: str) -> dict:
    """Load the curated schema for a component type or alias."""
    filename = _index().get(component_type)
    if filename is None:
        raise KeyError(f"no curated schema for component type {component_type!r}")
    with (_SCHEMA_DIR / filename).open(encoding="utf-8") as fh:
        return json.load(fh)


def resolve_enum_ref(ref: str) -> set:
    """Resolve 'module.path:CONST' to the live set of valid values (dict keys or members)."""
    try:
        module_path, const_name = ref.split(":", 1)
        module = importlib.import_module(module_path)
        const = getattr(module, const_name)
    except (ValueError, ImportError, AttributeError) as exc:
        raise ValueError(f"cannot resolve enum_ref {ref!r}: {exc}") from exc
    if hasattr(const, "keys"):
        return set(const.keys())
    return set(const)
