"""Drift/consistency checks keeping the curated schemas honest against the engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from agents.tools.component_schema import _SCHEMA_DIR, load_schema, resolve_enum_ref  # noqa: F401
from agents.tools.validate_config import validate_config

_REPO = Path(__file__).resolve().parents[2]
_FIXTURE_DIRS = [_REPO / "tests" / "fixtures" / "jobs", _REPO / "tests" / "talend_xml_samples" / "converted_jsons"]


def _iter_enum_refs(node):
    if isinstance(node, dict):
        if "enum_ref" in node:
            yield node["enum_ref"]
        for v in node.values():
            yield from _iter_enum_refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_enum_refs(v)


def check_drift() -> list:
    """Return schema-drift / fixture-inconsistency messages (empty = clean)."""
    from src.v1.engine.component_registry import REGISTRY
    problems: list = []
    with (_SCHEMA_DIR / "_index.json").open(encoding="utf-8") as fh:
        index = json.load(fh)
    schema_files = sorted(set(index.values()))
    for filename in schema_files:
        schema = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        ctype = schema["type"]
        if REGISTRY.get(ctype) is None:
            problems.append(f"{filename}: type {ctype!r} not registered in REGISTRY")
        for ref in _iter_enum_refs(schema):
            try:
                resolve_enum_ref(ref)
            except ValueError as exc:
                problems.append(f"{filename}: {exc}")
    # fixture consistency: validate every component instance in every fixture job
    known = set(index)
    for fdir in _FIXTURE_DIRS:
        for jf in fdir.rglob("*.json"):
            try:
                job = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            for comp in job.get("components", []):
                ctype = comp.get("type")
                if ctype in known:
                    for err in validate_config(ctype, comp.get("config", {}), strict=False):
                        problems.append(f"{jf.name}:{comp.get('id')}: {err}")
    return problems


if __name__ == "__main__":
    found = check_drift()
    print("\n".join(found) if found else "schema drift: clean")
    sys.exit(1 if found else 0)
