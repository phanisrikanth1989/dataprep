# Knowledge Layer (curated config schemas + validator) Implementation Plan

> **SUPERSEDED IN PART (2026-07-03) -- see `docs/superpowers/specs/2026-07-03-enrichment-scope-correction.md`.**
> This plan is historical in part. The curated-schema / config-key validator / drift-checker / landmine-registry machinery it builds SHIPPED and is live; but the roadmap in "Next plans" at the foot predates the 1.122 native-platform pivot and the enrichment correction -- the `reference_matcher` and the standalone MCP-server plan it names were DROPPED. See the corrected 4-plan set in that section. Do not rewrite the body.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the code-verified knowledge layer for the recon slice — curated per-component config schemas, a config-key validator that catches hallucinated/invalid config *before* the engine runs, a drift-checker that keeps the schemas honest against the engine source, and a landmine registry.

**Architecture:** Per-component config schemas are hand-curated JSON (authored from the committed `agents/schemas/config-surfaces.md` ground truth), each declaring keys with type/default/required/required_when/enum/enum_ref/nested-item rules. `agents/tools/component_schema.py` loads them and resolves `enum_ref`s (a `module:CONSTANT` pointing at a live engine module constant, so enum values never drift). `agents/tools/validate_config.py` validates a component `config` dict against its schema. `agents/tools/check_schema_drift.py` asserts every enum_ref resolves, every schema `type` is a registered component, and every real fixture still validates. A landmine registry (`agents/knowledge/landmines.py`) records the code-verified gotchas.

**Tech Stack:** Python 3.12, stdlib `json`/`importlib`, `pytest`. Imports engine modules (for `enum_ref` resolution + drift checks) — runs in the engine's env.

## Global Constraints

- **Python 3.12+.** ASCII-only in all code and logs.
- **No new third-party dependency** — stdlib + the engine's existing env only.
- **`agents/schemas/config-surfaces.md` is the ground truth** for every schema's keys/types/defaults/required/enums; do not invent keys not in it, and do not copy from `ui_registry.json`.
- **Enums that live in an engine module constant MUST use `enum_ref`** (never a hardcoded copy), so they track the live value: FilterRows operator -> `_OPERATOR_MAP`, AggregateRow function -> `_SUPPORTED_FUNCTIONS`, SortRow sort_type/order -> `_VALID_SORT_TYPES`/`_VALID_ORDERS`, FileOutputDelimited csvrowseparator -> `_CSV_ROW_SEPARATORS`. Hand-sourced enums (tMap modes, UniqueRow `keep`) use a literal `enum`.
- Public functions/classes carry docstrings (CLAUDE.md).
- Per-module logger `logging.getLogger(__name__)`.

## File Structure

- `agents/schemas/config-surfaces.md` — EXISTS (committed ground truth).
- `agents/schemas/<component>.json` — one curated schema per component (8 files).
- `agents/schemas/_index.json` — maps every registered type/alias -> its schema filename.
- `agents/tools/component_schema.py` — `load_schema`, `resolve_enum_ref`, `BASE_KEYS`, `IGNORED_KEYS`.
- `agents/tools/validate_config.py` — `validate_config(component_type, config, strict=True) -> list[str]`.
- `agents/tools/check_schema_drift.py` — `check_drift() -> list[str]` + `__main__` CLI.
- `agents/knowledge/landmines.py` — `LANDMINES` registry + `landmines_for(component_type)`.
- `agents/knowledge/__init__.py`, tests under `tests/agents/tools/` and `tests/agents/knowledge/`.

**Schema JSON format** (illustrative — the real files hold strict JSON, no comments):
```
{
  "type": "FilterRows",
  "aliases": ["FilterRow", "tFilterRow", "tFilterRows"],
  "source": "src/v1/engine/components/transform/filter_rows.py",
  "keys": {
    "use_advanced": {"type": "bool", "default": false},
    "advanced_cond": {"type": "str", "default": "", "required_when": {"use_advanced": true}},
    "logical_op": {"type": "str", "default": "&&", "enum": ["&&", "||", "AND", "OR"]},
    "conditions": {"type": "list", "default": [], "item_keys": {
      "column":   {"type": "str", "required": true},
      "operator": {"type": "str", "required": true,
                   "enum_ref": "src.v1.engine.components.transform.filter_rows:_OPERATOR_MAP"},
      "function": {"type": "str"},
      "value":    {"type": "str"}
    }}
  }
}
```
Key-spec fields: `type` (one of str/int/float/bool/list/dict), `default`, `required` (bool), `required_when` ({other_key: value}), `enum` (literal list), `enum_ref` ("module:CONST" whose dict-keys or set-members are the valid values), `item_keys` (nested schema for each dict in a list).

---

### Task 1: Schema format, loader, and the FilterRows exemplar schema

**Files:**
- Create: `agents/schemas/filter_rows.json`, `agents/schemas/_index.json`
- Create: `agents/tools/component_schema.py`
- Test: `tests/agents/tools/test_component_schema.py`

**Interfaces:**
- Produces:
  - `BASE_KEYS: frozenset[str]` = `{"die_on_error", "execution_mode", "chunk_size", "tstatcatcher_stats", "label", "component_type"}` (accepted on any component).
  - `IGNORED_KEYS: frozenset[str]` = `{"original_type", "position", "id", "type", "schema", "inputs", "outputs", "subjob_id", "is_subjob_start", "connector"}` (job-envelope/passthrough keys accepted-but-not-config).
  - `load_schema(component_type: str) -> dict` — resolves via `_index.json` (by type OR alias), loads and returns the schema dict; raises `KeyError` if the type is unknown.
  - `resolve_enum_ref(ref: str) -> set[str]` — `"module.path:CONST"`; imports the module, gets `CONST`; returns `set(CONST.keys())` if it's a dict/Mapping else `set(CONST)` (set/frozenset/list). Raises `ValueError` with a clear message if the module/attr is missing.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_component_schema.py
from agents.tools.component_schema import BASE_KEYS, load_schema, resolve_enum_ref


def test_load_schema_by_type_and_alias():
    by_type = load_schema("FilterRows")
    assert by_type["type"] == "FilterRows"
    assert by_type["keys"]["logical_op"]["enum"] == ["&&", "||", "AND", "OR"]
    by_alias = load_schema("tFilterRow")           # alias resolves to same schema
    assert by_alias["type"] == "FilterRows"


def test_resolve_enum_ref_reads_live_operator_map():
    values = resolve_enum_ref("src.v1.engine.components.transform.filter_rows:_OPERATOR_MAP")
    assert "==" in values and "IS_NULL" in values      # live keys of _OPERATOR_MAP
    assert isinstance(values, set)


def test_base_keys_present():
    assert "die_on_error" in BASE_KEYS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_component_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.component_schema'`

- [ ] **Step 3: Write minimal implementation**

Create `agents/schemas/filter_rows.json` (strict JSON, matching the format block above — the exemplar). Create `agents/schemas/_index.json`:
```json
{"FilterRows": "filter_rows.json", "FilterRow": "filter_rows.json", "tFilterRow": "filter_rows.json", "tFilterRows": "filter_rows.json"}
```
Create `agents/tools/component_schema.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_component_schema.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/schemas/filter_rows.json agents/schemas/_index.json agents/tools/component_schema.py tests/agents/tools/test_component_schema.py
git commit -m "feat(agents): curated schema format, loader, enum_ref resolver + FilterRows schema"
```

---

### Task 2: The config-key validator

**Files:**
- Create: `agents/tools/validate_config.py`
- Test: `tests/agents/tools/test_validate_config.py`

**Interfaces:**
- Consumes: `load_schema`, `resolve_enum_ref`, `BASE_KEYS`, `IGNORED_KEYS` (Task 1).
- Produces: `validate_config(component_type: str, config: dict, strict: bool = True) -> list[str]` — returns a list of human-readable error strings (empty = valid). `strict=True` flags unknown keys (for AI-generated configs); `strict=False` skips the unknown-key check (for validating real fixtures that carry ignored passthrough keys). Checks, in order: unknown keys (strict only, excluding BASE_KEYS/IGNORED_KEYS), missing required (incl. `required_when`), wrong python type, out-of-enum / out-of-enum_ref, and nested `item_keys` for each dict in a list-typed key.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_validate_config.py
from agents.tools.validate_config import validate_config


def test_valid_filter_config_passes():
    cfg = {"conditions": [{"column": "amt", "operator": ">", "value": "0"}], "logical_op": "&&"}
    assert validate_config("FilterRows", cfg) == []


def test_unknown_key_flagged_strict_only():
    cfg = {"bogus_key": 1, "conditions": []}
    errs = validate_config("FilterRows", cfg, strict=True)
    assert any("bogus_key" in e for e in errs)
    assert validate_config("FilterRows", cfg, strict=False) == []   # ignored when not strict


def test_missing_required_when():
    cfg = {"use_advanced": True}          # advanced_cond required when use_advanced
    errs = validate_config("FilterRows", cfg)
    assert any("advanced_cond" in e for e in errs)


def test_wrong_type_flagged():
    cfg = {"conditions": "not a list"}
    assert any("conditions" in e and "list" in e for e in validate_config("FilterRows", cfg))


def test_out_of_enum_operator_flagged():
    cfg = {"conditions": [{"column": "amt", "operator": "<=>"}]}  # <=> not in _OPERATOR_MAP
    assert any("operator" in e for e in validate_config("FilterRows", cfg))


def test_nested_missing_required_column():
    cfg = {"conditions": [{"operator": "=="}]}   # column required per item
    assert any("column" in e for e in validate_config("FilterRows", cfg))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_validate_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.validate_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# agents/tools/validate_config.py
"""Validate a component config dict against its curated schema (pre-engine gate)."""
from __future__ import annotations

from agents.tools.component_schema import BASE_KEYS, IGNORED_KEYS, load_schema, resolve_enum_ref

_PY_TYPES = {"str": str, "int": int, "float": (int, float), "bool": bool, "list": list, "dict": dict}


def _valid_values(spec: dict) -> set | None:
    if "enum" in spec:
        return set(spec["enum"])
    if "enum_ref" in spec:
        return resolve_enum_ref(spec["enum_ref"])
    return None


def _check_key(name: str, value, spec: dict, errors: list) -> None:
    expected = spec.get("type")
    if expected and not isinstance(value, _PY_TYPES[expected]):
        errors.append(f"key {name!r}: expected {expected}, got {type(value).__name__}")
        return
    allowed = _valid_values(spec)
    if allowed is not None and value not in allowed:
        errors.append(f"key {name!r}: value {value!r} not in allowed {sorted(allowed)}")
    if spec.get("type") == "list" and "item_keys" in spec:
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                errors.append(f"key {name!r}[{i}]: expected dict item")
                continue
            for sub, subspec in spec["item_keys"].items():
                if subspec.get("required") and sub not in item:
                    errors.append(f"key {name!r}[{i}]: missing required {sub!r}")
                elif sub in item:
                    _check_key(f"{name}[{i}].{sub}", item[sub], subspec, errors)


def _required(name: str, spec: dict, config: dict) -> bool:
    if spec.get("required"):
        return True
    cond = spec.get("required_when")
    return bool(cond) and all(config.get(k) == v for k, v in cond.items())


def validate_config(component_type: str, config: dict, strict: bool = True) -> list:
    """Return a list of config errors (empty = valid). strict flags unknown keys."""
    schema = load_schema(component_type)
    keys = schema["keys"]
    errors: list = []
    if strict:
        for name in config:
            if name not in keys and name not in BASE_KEYS and name not in IGNORED_KEYS:
                errors.append(f"unknown config key {name!r} for {component_type}")
    for name, spec in keys.items():
        if _required(name, spec, config) and name not in config:
            errors.append(f"missing required config key {name!r}")
        elif name in config:
            _check_key(name, config[name], spec, errors)
    return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_validate_config.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/validate_config.py tests/agents/tools/test_validate_config.py
git commit -m "feat(agents): config-key validator (unknown/required/type/enum/nested)"
```

---

### Task 3: The remaining 7 curated schemas + fixture-consistency drift check

**Files:**
- Create: `agents/schemas/file_input_delimited.json`, `file_output_delimited.json`, `aggregate_row.json`, `map.json`, `sort_row.json`, `unique_row.json`, `convert_type.json`; extend `agents/schemas/_index.json` with all their type+alias entries.
- Create: `agents/tools/check_schema_drift.py`
- Test: `tests/agents/tools/test_check_schema_drift.py`

**Interfaces:**
- Consumes: `validate_config`, `load_schema`, `resolve_enum_ref`, the registry (`src.v1.engine.component_registry.REGISTRY`).
- Produces: `check_drift() -> list[str]` — for every schema in `_index.json`: (a) its `type` resolves in `REGISTRY`; (b) every `enum_ref` in it resolves without error; (c) every matching fixture under `tests/fixtures/jobs/**` and `tests/talend_xml_samples/converted_jsons/**` validates with `strict=False` (required present, enums valid, types ok). Returns the list of drift/inconsistency messages (empty = clean). Plus a `__main__` that prints them and exits non-zero if any.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_check_schema_drift.py
from agents.tools.check_schema_drift import check_drift


def test_no_schema_drift():
    problems = check_drift()
    assert problems == [], "schema drift / fixture inconsistency:\n" + "\n".join(problems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_check_schema_drift.py -v`
Expected: FAIL — `ModuleNotFoundError` (drift module absent) and/or the 7 schemas not yet authored.

- [ ] **Step 3: Author the 7 schemas + implement the drift checker**

Author each schema file as strict JSON from `agents/schemas/config-surfaces.md` (the committed ground truth) following the Task-1 FilterRows format. Rules the author MUST honor (from config-surfaces.md):
- **file_input_delimited.json**: `filepath` required; all other keys optional with the exact defaults in the reference; the 5 deferred flags (uncompress/split_record/random/advanced_separator/enable_decode) included as optional bools; `trim_select` a list with `item_keys` `{column:str, trim:bool}`. Do NOT include stale docstring keys (nb_random/decode_cols/tstatcatcher_stats).
- **file_output_delimited.json**: `filepath` required; `csvrowseparator` uses `enum_ref` `src.v1.engine.components.file.file_output_delimited:_CSV_ROW_SEPARATORS`; the 5 deferred flags optional.
- **aggregate_row.json**: `operations` list with `item_keys` function (required, `enum_ref` `src.v1.engine.components.aggregate.aggregate_row:_SUPPORTED_FUNCTIONS`), input_column (required), output_column, ignore_null(bool); `groupbys` list with `item_keys` input_column(required), output_column(required).
- **map.json** (tMap): nested `inputs` (dict with `main` and `lookups`), `outputs`, `variables`, `die_on_error`, `enable_auto_convert_type`, `label`. Use hand-sourced literal `enum`s for join_mode `["LEFT_OUTER_JOIN","INNER_JOIN"]`, matching_mode `["UNIQUE_MATCH","FIRST_MATCH","ALL_MATCHES","ALL_ROWS"]`, lookup_mode `["LOAD_ONCE","RELOAD","CACHE_OR_RELOAD"]`, join_key operator `["="]`. For output columns, accept BOTH `pattern` and `date_pattern` (converter emits `pattern`; dataclass reads `date_pattern` — the documented drift) and column `operator`. tMap's deep nesting is validated loosely (presence of `outputs`, each output has `name`+`columns`); do not over-constrain passthrough keys — set `strict=False`-friendly by allowing extra nested keys (only validate the named sub-keys, ignore others).
- **sort_row.json**: `criteria` required non-empty list with `item_keys` column(required), sort_type(`enum_ref` `...sort_row:_VALID_SORT_TYPES`), order(`enum_ref` `...sort_row:_VALID_ORDERS`).
- **unique_row.json**: `key_columns` list; `keep` literal `enum` `["first","last",false]`; the bool flags with reference defaults; include `only_once_each_duplicated_key`.
- **convert_type.json**: `autocast`/`emptytonull`/`dieonerror` bools; `manualtable` list with `item_keys` input_column, output_column.

Then implement `agents/tools/check_schema_drift.py`:
```python
"""Drift/consistency checks keeping the curated schemas honest against the engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from agents.tools.component_schema import _SCHEMA_DIR, load_schema, resolve_enum_ref
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
```

Iterate: run the drift test, and for each fixture-inconsistency it reports, fix the SCHEMA (a real key/default/enum you missed per config-surfaces.md) — not the fixture — until `check_drift()` returns `[]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_check_schema_drift.py -v`
Expected: PASS — `check_drift()` returns `[]` (all enum_refs resolve, all types registered, all fixtures validate under strict=False).

- [ ] **Step 5: Commit**

```bash
git add agents/schemas/*.json agents/tools/check_schema_drift.py tests/agents/tools/test_check_schema_drift.py
git commit -m "feat(agents): 7 curated component schemas + drift/fixture-consistency checker"
```

---

### Task 4: Landmine registry

**Files:**
- Create: `agents/knowledge/__init__.py` (empty), `agents/knowledge/landmines.py`
- Test: `tests/agents/knowledge/__init__.py` (empty), `tests/agents/knowledge/test_landmines.py`

**Interfaces:**
- Produces:
  - `LANDMINES: list[dict]` — each `{"id": str, "component": str|None, "summary": str, "code_anchor": str, "guidance": str}`, capturing the code-verified gotchas from `config-surfaces.md` and the design spec.
  - `landmines_for(component_type: str) -> list[dict]` — landmines whose `component` is that type (by type or alias) or `None` (global).

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/knowledge/test_landmines.py
from agents.knowledge.landmines import LANDMINES, landmines_for


def test_registry_has_core_landmines():
    ids = {lm["id"] for lm in LANDMINES}
    assert {"tmap-operator-noop", "tmap-matching-mode-drops-dups",
            "tmap-catch-output-reject-error-only", "die-on-error-dual-default",
            "tmap-pattern-vs-date-pattern"} <= ids
    for lm in LANDMINES:                       # every landmine is fully populated
        assert lm["summary"] and lm["code_anchor"] and lm["guidance"]


def test_landmines_for_map_includes_operator_noop():
    ids = {lm["id"] for lm in landmines_for("Map")}
    assert "tmap-operator-noop" in ids
    assert "tmap-operator-noop" in {lm["id"] for lm in landmines_for("tMap")}   # alias
    assert "die-on-error-dual-default" in ids                                   # global included
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/knowledge/test_landmines.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.knowledge.landmines'`

- [ ] **Step 3: Write minimal implementation**

Create the empty `__init__.py` files, then `agents/knowledge/landmines.py`:
```python
"""Code-verified config landmines for the recon slice (from config-surfaces.md + spec)."""
from __future__ import annotations

_MAP_ALIASES = {"Map", "tMap"}

LANDMINES = [
    {"id": "die-on-error-dual-default", "component": None,
     "summary": "die_on_error defaults True in BaseComponent but False in several components' own reads.",
     "code_anchor": "base_component.py:234 vs e.g. file_input_delimited.py:173",
     "guidance": "Always set die_on_error explicitly; do not rely on the default."},
    {"id": "tmap-operator-noop", "component": "Map",
     "summary": "tMap join_key operator is parsed but read by no join path; matching is equality-only.",
     "code_anchor": "map_config.py:38,115; map_joins.py (equality merge)",
     "guidance": "Only operator '=' is meaningful. Model tolerance as exact-join + post-join split, never operator '<='."},
    {"id": "tmap-matching-mode-drops-dups", "component": "Map",
     "summary": "matching_mode default UNIQUE_MATCH silently keeps only the last duplicate lookup row, no break.",
     "code_anchor": "map_joins.py:446-463; map_config.py:46,55",
     "guidance": "For a non-unique lookup key use ALL_MATCHES + explicit duplicate handling; UNIQUE_MATCH hides dups."},
    {"id": "tmap-catch-output-reject-error-only", "component": "Map",
     "summary": "catch_output_reject captures expression ERRORS only, not filter-rejects; it cancels die_on_error propagation.",
     "code_anchor": "map_reject_routing.py:82-153; map_compiled_script.py:405",
     "guidance": "Use is_reject (or complementary output filters) for business/tolerance breaks; never catch_output_reject."},
    {"id": "tmap-pattern-vs-date-pattern", "component": "Map",
     "summary": "tMap output column date format: dataclass reads 'date_pattern' but the converter emits 'pattern' -> date formatting silently unwired.",
     "code_anchor": "map_config.py:149 vs converter transform/map.py:251",
     "guidance": "Emit the column date format under 'pattern' (schema accepts both); do not rely on 'date_pattern'."},
    {"id": "reject-is-a-data-flow", "component": None,
     "summary": "Reject is a data flow (type 'reject'), not a trigger; it routes through flows[], not triggers[].",
     "code_anchor": "output_router.py:22-29",
     "guidance": "Wire rejects as flows with type 'reject', not as OnComponentError triggers."},
]


def landmines_for(component_type: str) -> list:
    """Return landmines whose component matches (by type/alias) or is global (None)."""
    matches = []
    for lm in LANDMINES:
        comp = lm["component"]
        if comp is None:
            matches.append(lm)
        elif comp == component_type or (component_type in _MAP_ALIASES and comp in _MAP_ALIASES):
            matches.append(lm)
    return matches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/knowledge/test_landmines.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Verify the whole knowledge layer, then commit**

Run: `python -m pytest tests/agents/ -v` (all knowledge-layer tests green) and `python -m agents.tools.check_schema_drift` (prints "schema drift: clean", exit 0).

```bash
git add agents/knowledge/__init__.py agents/knowledge/landmines.py tests/agents/knowledge/__init__.py tests/agents/knowledge/test_landmines.py
git commit -m "feat(agents): code-verified landmine registry for the recon slice"
```

---

## Self-Review

**1. Spec coverage:** curated code-verified schemas sourced from `config-surfaces.md` not `ui_registry.json` (spec §6.1) — Tasks 1,3. enum_ref-to-live-constant so enums never drift (§6.1 conflict rule) — Tasks 1,2,3. config-key validator BEFORE the engine (§9) — Task 2. drift-detector as a check tied to source + fixtures (§6.3) — Task 3. landmine registry as machine facts (§6.2) — Task 4. tMap operator/matching_mode/catch_output_reject/pattern landmines (§7, config-surfaces) — Task 4.

**2. Placeholder scan:** no TBD/TODO; complete code in every code step; Task 3's schema authoring is bounded by the committed `config-surfaces.md` + the Task-1 exemplar + the drift test as the acceptance gate.

**3. Type consistency:** `load_schema`, `resolve_enum_ref`, `BASE_KEYS`, `IGNORED_KEYS`, `validate_config(component_type, config, strict)`, `check_drift`, `LANDMINES`, `landmines_for` names/signatures are consistent across tasks.

## Next plans (not built here)
Corrected 4-plan set (post 1.122 pivot / enrichment correction; this is plan 2, already built): 1. `recon-doc-extraction` (`extract_doc`) -- built. 2. `knowledge-layer` (this plan) -- built. 3. `parity-harness` -- multi-signal oracle + run-and-validate (consumes ExtractResult from plan 1 + these schemas). 4. `native-platform` -- roles + deterministic feedback loop on native subagents + Agent Skills. DROPPED at the 1.122 pivot / enrichment correction: the `reference_matcher` (match/break cross-check -- a LEFT-join enrichment keeps all source rows, so there is no independent match) and the standalone MCP-server + sampling-preflight plan (superseded by the native platform).
