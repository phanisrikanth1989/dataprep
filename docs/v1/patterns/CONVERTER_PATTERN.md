# Gold Standard: Converter Code Pattern

*Last updated: 2026-05-11*

> Reference: tSchemaComplianceCheck converter (src/converters/talend_to_v1/components/transform/schema_compliance_check.py -- TABLE parsing, RADIO fields, needs_review, framework params)

Every talend_to_v1 component converter MUST follow this structure.

---

## File Structure

```python
"""Converter for Talend {tComponentName} component.

{1-2 sentence description of what the component does.}

Config mapping ({N} params total):
  {XML_PARAM_1}  -> {config_key_1} ({type}, default {value})
  {XML_PARAM_2}  -> {config_key_2} ({type}, default {value})
  ...
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants (only if component has TABLE params)
# ------------------------------------------------------------------
_TABLE_FIELDS = ("FIELD1", "FIELD2", "FIELD3")
_TABLE_GROUP_SIZE = len(_TABLE_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions (module-level, prefixed with underscore)
# ------------------------------------------------------------------
def _parse_table(raw: Any) -> List[Dict[str, Any]]:
    """Parse {TABLE_NAME} TABLE into list of dicts.

    Each group of {N} consecutive elementRef entries maps to one row:
      {FIELD1}  -> {key1} ({type})
      {FIELD2}  -> {key2} ({type})

    Incomplete trailing groups (< {N} entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _TABLE_GROUP_SIZE):
        group = raw[i : i + _TABLE_GROUP_SIZE]
        if len(group) < _TABLE_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "FIELD1":
                row["key1"] = val.strip('"')
            elif ref == "FIELD2":
                row["key2"] = val.lower() in ("true", "1")
        if row:
            result.append(row)
    return result


@REGISTRY.register("{tComponentName}")
class {ComponentName}Converter(ComponentConverter):
    """Convert Talend {tComponentName} to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["param_one"] = self._get_str(node, "PARAM_ONE", "default")
        config["param_two"] = self._get_bool(node, "PARAM_TWO", False)
        config["param_three"] = self._get_int(node, "PARAM_THREE", 0)

        # ---- 2. CLOSED_LIST / RADIO parameters ----
        config["mode"] = self._get_str(node, "MODE", "DEFAULT_VALUE")

        # ---- 3. TABLE parameters ----
        raw_table = node.params.get("TABLE_NAME", [])
        config["table_data"] = _parse_table(raw_table)

        # ---- 4. Conditional parameters ----
        if config.get("advanced_option"):
            config["advanced_param"] = self._get_str(node, "ADV_PARAM", "")

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        # Source component:
        schema = {"input": [], "output": self._parse_schema(node)}
        # Transform component:
        # schema = {"input": schema_cols, "output": schema_cols}
        # Utility/control (no data flow):
        # schema = {"input": [], "output": []}
        #
        # NOTE: schema.input is auto-propagated by the pipeline
        # (converter.py Step 6b: _propagate_input_schemas) from the
        # upstream component's schema.output.  Component converters
        # only need to set schema.output correctly.

        # ---- 7. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("config_key", "reason engine doesn't read this key"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="{TypeName}",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
```

---

## Rules

1. **Module docstring** lists ALL config keys with XML name -> config key mapping, types, and defaults
2. **Imports** follow project convention: stdlib -> third-party -> local (relative)
3. **TABLE constants** at module level with `_UPPER_SNAKE_CASE` naming
4. **TABLE parser functions** at module level, prefixed with `_`, before the class
5. **Class uses `@REGISTRY.register`** decorator -- one component per class
6. **Parameter extraction order**: core params -> CLOSED_LIST/RADIO -> TABLE -> conditional -> framework params (ALWAYS LAST)
7. **Framework params** (`tstatcatcher_stats`, `label`) are ALWAYS extracted, ALWAYS last, NEVER get needs_review entries
8. **`_get_str`, `_get_bool`, `_get_int`** from base class -- never raw `params.get()` for scalar params (use `_get_param` only for CODE/IMPORT fields per Pitfall 6)
9. **TABLE values must strip quotes** manually: `val.strip('"')` -- XmlParser doesn't strip TABLE entry quotes
10. **needs_review** entries have exactly 3 keys: `issue`, `component`, `severity` (always `"engine_gap"`)
11. **No exception raising** -- return ComponentResult with warnings
12. **Config keys are snake_case** -- converted from UPPER_CASE XML names

---

## Schema Patterns (4 Quadrants)

The `schema.input` / `schema.output` shape depends on whether the component is a source, sink, transform, or utility:

```python
# Source component (produces data): input empty, output from FLOW
schema={"input": [], "output": self._parse_schema(node)}

# Sink/output component (consumes data): input from FLOW, output empty
schema={"input": self._parse_schema(node), "output": []}

# Transform component (passes through): both from FLOW
schema_cols = self._parse_schema(node)
schema={"input": schema_cols, "output": schema_cols}

# Utility component (no data flow): both empty
schema={"input": [], "output": []}
```

> **Note:** The `schema.input` values set by individual component converters are **overwritten** during pipeline Step 6b (`_propagate_input_schemas`). Each target component's `schema.input` is replaced with its upstream component's `schema.output`, derived from the flow connection graph. This means component converters only need to set `schema.output` correctly; the pipeline handles `schema.input` automatically.

---

## Hidden / Design-Time Parameters (NOT Extracted)

Talend components include several parameter categories that are **not** extracted by the converter:

| Category | Examples | Reason for exclusion |
| ---------- | ---------- | ---------------------- |
| Schema optimization | `SCHEMA_OPT_NUM` | Studio-only hint for schema preview sampling; no runtime effect |
| Hidden UI controls | `USE_ITEMS`, `LOOP_QUERY_BASE`, `USE_XML_FIELD`, `XML_TEXT`, `XML_PREFIX`, `LINK_STYLE`, `LKUP_PARALLELIZE`, `ENABLE_AUTO_CONVERT_TYPE`, `LEVENSHTEIN`, `JACCARD`, `HASH_KEY_FROM_INPUT_CONNECTOR` | `show="false"` in component XML; never set by users |
| Phantom parameters | `CONNECTION_FORMAT`, `TEMP_DIR`, `DESTINATION`, `USE_HEADER_AS_IS`, `TEMP_DIRECTORY`, `SPLIT_LIST`, `JDK_VERSION`, `VAR_TABLE_NAME`, `VAR_TABLE_SIZE_STATE` | Present in `.item` XML but absent from `_java.xml` definition or only used at design time |

These parameters were previously extracted and flagged as `engine_gap` entries. They have been removed to reduce noise in the converted JSON output and eliminate false-positive needs_review entries.

---

## TABLE Parameter Parsing

XmlParser stores TABLE params as flat lists of `{elementRef, value}` dicts:

```python
# Example: parse a TABLE with pairs of KEY/VALUE entries
raw = self._get_param(node, "MY_TABLE", [])
entries = []
current_key = None
for entry in raw:
    if not isinstance(entry, dict):
        continue
    ref = entry.get("elementRef", "")
    val = entry.get("value", "").strip('"')
    if ref == "KEY":
        current_key = val
    elif ref == "VALUE" and current_key:
        entries.append({"key": current_key, "value": val})
        current_key = None
```
