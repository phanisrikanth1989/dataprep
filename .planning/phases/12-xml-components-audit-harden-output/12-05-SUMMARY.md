---
phase: 12
plan: 05
subsystem: xml-components
tags: [xml, xml-map, audit-fix, registry, reject-flow, tdd, per-row-loop]
dependency_graph:
  requires: [12-01, 12-02]
  provides: [tXMLMap-engine-hardened, tXMLMap-conditional-needs-review, test_xml_map]
  affects: [src/v1/engine/components/transform/xml_map.py, src/converters/talend_to_v1/components/transform/xml_map.py]
tech_stack:
  added: []
  patterns:
    - "per-row iterrows() loop pattern (BUG-XMP-003 fix)"
    - "_make_reject_row static helper (S-3 pattern, mirrors ExtractXMLField)"
    - "conditional warn-and-ignore for D-E1 sub-features"
    - "bracket-balanced split_steps() for XPath predicate preservation"
key_files:
  created:
    - tests/v1/engine/components/transform/test_xml_map.py
  modified:
    - src/v1/engine/components/transform/xml_map.py
    - src/converters/talend_to_v1/components/transform/xml_map.py
    - tests/converters/talend_to_v1/components/transform/test_xml_map.py
decisions:
  - "Surgical fix approach (not full rewrite): existing XML tree-walking logic preserved; only audit-cited sites modified"
  - "D-E1 conditional needs_review: 3 new entries emitted only when flags active (expression_filter / lookup / allInOne)"
  - "_evaluate_xml_for_row helper extracted to allow per-row dispatch from _process"
  - "BUG-XMP-013 (global_map.py default param) found to be already fixed in current HEAD; not re-fixed"
metrics:
  duration: "~30 minutes"
  completed: "2026-05-08"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 3
  tests_added: 63
---

# Phase 12 Plan 05: tXMLMap Engine Harden + Conditional needs_review Summary

**One-liner:** Heavy audit-driven fix for tXMLMap engine: per-row iterrows() loop (P0 data-loss), 46 print()->logger replacements, bracket-aware split_steps(), REJECT flow, die_on_error, secure parser delegation, D-E1 conditional warn-and-ignore; 55 new engine tests + 8 converter conditional-needs-review tests.

---

## Audit Items Closed

### BUG-XMP-003 (P0) -- Per-row loop replaces iloc[0, 0]

**Before (line 506):**
```python
xml_string = str(input_data.iloc[0, 0] or "")
```

**After:**
```python
for _, row in input_data.iterrows():
    xml_string = row.get(xml_col, None)
    # ... per-row parse + evaluate ...
```

Impact: 5-row input now produces 5*N output rows instead of silently dropping rows 2-5. Verified by TestMultiRowInput (3 tests).

### BUG-XMP-004 (P1) -- self.id overwritten mid-execute

**Before (line 498):**
```python
self.id = config.get("id", self.DEFAULT_COMPONENT_ID)
```

**After:** Removed. `component_id = self.id` (read-only local variable used throughout _process). self.id now immutable after construction.

### BUG-XMP-006 (P1) -- Ancestor fallback (broadened search)

**Before (line 281):**
```python
broadened = "./ancestor::*//" + tail.lstrip("/")
```

**After (in _broaden_ancestor_if_empty docstring note + actual engine code):**
```python
broadened = "./ancestor::*//" + tail.removeprefix("/")
```

The `choose_context` function debug prints also converted to `logger.debug`.

### BUG-XMP-014 (P1) -- split_steps preserves XPath predicates

**Before:** The original `split_steps` function split on `/` inside `[predicate]` brackets, destroying expressions like `/a/b[@id='x']/c`.

**After:** New bracket-balanced implementation tracks `depth` counter, splits on `/` only at depth==0. Tested by TestSplitSteps (4 tests including nested predicate case).

### ENG-XMP-003 (P1) -- REJECT flow added

**New code:**
```python
reject_rows.append(
    self._make_reject_row(row, xml_string, _ERR_PARSE, str(exc))
)
```

`_make_reject_row` static method mirrors ExtractXMLField (S-3 pattern). Returns `reject_df` in addition to `main_df`. Tested by TestProcessReject + TestRejectRowSchema.

### ENG-XMP-006 (P1) -- die_on_error honored

**New code at per-row error sites:**
```python
if die_on_error:
    raise DataValidationError(f"[{component_id}] XML parse failed: {exc}")
reject_rows.append(self._make_reject_row(...))
```

Default die_on_error=True per Talaxie javajet. Tested by TestDieOnError (2 tests).

### STD-XMP-001 (P1) -- print() -> logger

**Count:** 46 `print(` calls replaced with `logger.info/warning/debug/error`.

Replacement pattern:
```python
# Before: print(f"[XMLMap] Processing started")
# After:
logger.info("[%s] Processing started", component_id)
```

ASCII-only %-style formatting per S-1 / CLAUDE.md memory rule. Verified by TestNoPrintCalls.

### SEC-XMP-001 (P2) -- Secure parser delegation

**Before:** Direct `ET.fromstring(xml_string.encode("utf-8"))` with no security flags.

**After:**
```python
parser = _xml_io.secure_xml_parser()
root = etree.fromstring(xml_string.encode("utf-8"), parser=parser)
```

3 calls to `_xml_io.secure_xml_parser()` in the file. Verified by TestSecureParserDelegation.

### BUG-XMP-015 (P2) -- lstrip -> removeprefix (Pitfall P-7)

**Before (line 281):**
```python
broadened = "./ancestor::*//" + tail.lstrip("/")
```

**After:**
```python
broadened = "./ancestor::*//" + tail.removeprefix("/")
```

All 5 uses of `removeprefix` now present; zero multi-char `lstrip` calls. Verified by TestNoLstripStringArg.

### REGISTRY decorator (S-7)

**Added:**
```python
@REGISTRY.register("XMLMap", "tXMLMap")
class XMLMap(BaseComponent):
```

Both V1 PascalCase and Talend alias registered. Verified by TestRegistry.

---

## D-E1 Conditional needs_review Wiring

### Converter side (3 entries added)

| Feature | Trigger | Entry key |
|---|---|---|
| expression_filter | `activate_expression_filter=True` on first output_tree | `feature: "expression_filter"` |
| lookup_join | any input_tree with `lookup=True` | `feature: "lookup_join"` |
| all_in_one_document_output | any output_tree with `allInOne=True` | `feature: "all_in_one_document_output"` |

3 conditional `needs_review.append` calls added to `src/converters/talend_to_v1/components/transform/xml_map.py` (in addition to the 2 existing blanket output-shape loops = 5 total appends).

### Engine side (3 warn-and-ignore lines)

```python
if config.get("activate_expression_filter"):
    logger.warning("[%s] expression_filter (Java) is not implemented; ignoring ...", component_id)
if self._has_lookup_connection():
    logger.warning("[%s] tXMLMap lookup/join is not implemented; ignoring ...", component_id)
if self._has_all_in_one_output():
    logger.warning("[%s] tXMLMap Document output (allInOne) is not implemented; falling back ...", component_id)
```

No exception raised. Tested by TestConditionalWarn* classes (6 tests total).

---

## D-E2 Contract (Zero Java Bridge Calls)

`grep -E "from .*java_bridge|JavaBridgeManager|execute_one_time_expression" src/v1/engine/components/transform/xml_map.py | grep -v "^#"` == 0 lines.

TestNoBridgeImports (3 tests) locks this in as a regression guard.

---

## Test Count Breakdown

| Test class | Count | Coverage target |
|---|---|---|
| TestRegistry | 3 | REGISTRY decorator |
| TestBaseComponent | 2 | Lifecycle |
| TestValidateConfig | 4 | Rule 12 structural checks |
| TestProcessHappyPath | 5 | Core path |
| TestMultiRowInput | 3 | BUG-XMP-003 regression |
| TestProcessReject | 4 | ENG-XMP-003 REJECT flow |
| TestDieOnError | 2 | ENG-XMP-006 |
| TestNoIlocZeroZero | 1 | BUG-XMP-003 grep guard |
| TestNoPrintCalls | 1 | STD-XMP-001 grep guard |
| TestNoLstripStringArg | 2 | P-7 grep guard |
| TestNoBridgeImports | 3 | D-E2 grep guard |
| TestSecureParserDelegation | 1 | SEC-XMP-001 |
| TestConditionalWarnExpressionFilter | 2 | D-E1 |
| TestConditionalWarnLookup | 2 | D-E1 |
| TestConditionalWarnAllInOne | 2 | D-E1 |
| TestParamMap | 2 | MAP param |
| TestParamDieOnError | 2 | DIE_ON_ERROR param |
| TestParamKeepOrderForDocument | 2 | KEEP_ORDER param |
| TestRejectRowSchema | 4 | S-3 reject schema |
| TestSplitSteps | 4 | BUG-XMP-014 |
| TestStats | 2 | Stats tracking |
| TestE2eFixture | 2 | E2E convert |
| **Total engine tests** | **55** | |
| TestConditionalNeedsReview (converter) | 8 | D-E1 converter |
| **Grand total** | **63** | |

---

## Deviations from Plan

### Auto-discovered: BUG-XMP-013 Already Fixed

**Found during:** Task 1 read of global_map.py
**Issue:** 12-01-AUDIT.md flagged BUG-XMP-013 (global_map.py `get()` undefined `default` param) as OPEN and noted Plan 12-05 should fix it.
**Verification:** `global_map.py:26`: `def get(self, key: str, default: Any = None) -> Optional[Any]:` -- `default` param is already present in current HEAD.
**Resolution:** No fix needed. Noted in summary only.

### Minor Adaptation: _evaluate_xml_for_row Helper

**Scope:** The plan's `<action>` specified refactoring per-doc evaluation into `_evaluate_xml_for_row`. Implemented as a method taking `(root, output_schema, expressions, looping_element, ns_prefix, nsmap, component_id)` rather than the exact `(doc, current_row)` signature shown in the plan pseudocode. This is a cleaner extraction since `current_row` from the outer loop is not needed inside the per-document evaluation (the row context is only needed for the reject path, which lives in `_process`).

### Minor Adaptation: _has_lookup_connection inspects input_trees

The plan suggested checking `connections` list for `connector_name == "LOOKUP"`. In the actual Talend converter output, the LOOKUP flag is on `input_trees[i].lookup=True` (not the connections list). The engine helper `_has_lookup_connection()` was implemented to check both `input_trees` and `connections` dicts to be maximally compatible.

---

## Known Stubs

None. All audit items closed with real implementation or documented as D-E1 warn-and-ignore (intentional, tracked to Phase 13).

---

## Threat Flags

No new security surface introduced. The T-12-01 and T-12-02 mitigations (XXE / DTD bombs via `_xml_io.secure_xml_parser()`) are now active in xml_map.py. T-12-05 (verbose error in reject) is mitigated: `errorMessage` contains only the exception string; raw XML appears only in `errorXMLField` of the reject row (not logged at INFO level).

---

## Commits

| Task | Commit | Description |
|---|---|---|
| Task 1 | 33f6a5d | feat(12-05): heavy audit fix for tXMLMap engine component |
| Task 2 | 78ccfee | feat(12-05): add D-E1 conditional needs_review to tXMLMap converter |
| Task 3 | 1b76e81 | test(12-05): add 55 engine tests for tXMLMap component |

## Self-Check: PASSED

- [x] src/v1/engine/components/transform/xml_map.py exists (931 LOC, >500 min)
- [x] @REGISTRY.register("XMLMap", "tXMLMap") present
- [x] iloc[0, 0] eradicated (0 matches)
- [x] print() eradicated (0 non-comment matches)
- [x] lstrip() eradicated (0 matches)
- [x] removeprefix() present (5 matches)
- [x] _xml_io.secure_xml_parser present (3 calls)
- [x] errorCode present (3 matches)
- [x] D-E2: 0 java_bridge imports
- [x] D-E1: 3 logger.warning lines for expression_filter/lookup/allInOne
- [x] Converter: needs_review.append >= 3 (5 total, 3 conditional D-E1)
- [x] Converter: expression_filter/lookup_join/all_in_one_document_output keywords present
- [x] tests/v1/engine/components/transform/test_xml_map.py exists (55 tests)
- [x] TestMultiRowInput present
- [x] TestNoIlocZeroZero present
- [x] TestNoPrintCalls present
- [x] TestNoLstripStringArg present
- [x] TestNoBridgeImports present
- [x] No lxml.etree mocks (D-D4)
- [x] All files ASCII-clean
- [x] All 87 tests (55 engine + 32 converter) pass
