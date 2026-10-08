"""Loader for curated per-component config schemas + live enum_ref resolution.

Vendored from agents/tools/component_schema.py (ticket 17; map invariant:
never import from agents/). Deltas: the schema dir is the studio's vendored
copy (demo/etl_studio/knowledge/schemas), and enum_ref resolution puts the
repo root on sys.path first so ``src.v1...`` imports resolve when the core
runs with demo/etl_studio as its working directory. The engine is imported
READ-ONLY -- resolution only reads module constants.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "schemas"
_REPO_ROOT = Path(__file__).resolve().parents[4]

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
    """Return True iff the component type (or alias) has a curated schema."""
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
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    try:
        module_path, const_name = ref.split(":", 1)
        module = importlib.import_module(module_path)
        const = getattr(module, const_name)
    except (ValueError, ImportError, AttributeError) as exc:
        raise ValueError(f"cannot resolve enum_ref {ref!r}: {exc}") from exc
    if hasattr(const, "keys"):
        return set(const.keys())
    return set(const)
