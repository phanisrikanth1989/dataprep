# Audit Report: tUniqRow / UniqueRow

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tUniqRow` (also `tUniqueRow` in some Talend versions) |
| **V1 Engine Class** | `UniqueRow` |
| **Engine File** | `src/v1/engine/components/aggregate/unique_row.py` (289 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_unique()` (lines 798-858) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `_parse_component()` (lines 240-243): dispatches `tUniqRow` and `tUnqRow` (typo) only; `tUniqueRow` is **missing** from dispatch |
| **Converter Param Mapping** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 207-215): handles `tUniqueRow` via broken generic path |
| **Registry Aliases** | `UniqueRow`, `tUniqueRow`, `tUniqRow` (registered in `src/v1/engine/engine.py` lines 164-166) |
| **Category** | Aggregate / Data Quality |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/aggregate/unique_row.py` | Engine implementation (289 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 798-858) | Dedicated `parse_unique()` XML-level parser for UNIQUE_KEY table |
| `src/converters/complex_converter/component_parser.py` (lines 207-215) | Generic `_map_component_parameters()` fallback for `tUniqueRow` (broken) |
| `src/converters/complex_converter/converter.py` (lines 240-243) | Dispatch -- only `tUniqRow` and `tUnqRow`; `tUniqueRow` missing |
| `src/converters/complex_converter/converter.py` (lines 384-405) | `_parse_flow()` -- lowercases `UNIQUE`/`DUPLICATE` connectorNames to `unique`/`duplicate` |
| `src/converters/complex_converter/converter.py` (lines 566-585) | Engine output routing -- handles `flow`/`reject`/`filter` but NOT `unique`/`duplicate` |
| `src/v1/engine/base_component.py` | Base class: `execute()`, `_update_stats()`, `_update_global_map()`, `validate_schema()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_UNIQUES` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ComponentExecutionError`, `ConfigurationError`) |
| `src/v1/engine/components/aggregate/__init__.py` | Package exports -- `UniqueRow` |
| `src/v1/engine/engine.py` (lines 164-166) | COMPONENT_REGISTRY aliases |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 1 | 4 | 4 | 2 | Dedicated `parse_unique()` parses UNIQUE_KEY table but discards per-column case sensitivity; `tUniqueRow` dispatch missing; `ONLY_ONCE` mapping wrong; Path B broken |
| Engine Feature Parity | **Y** | 1 | 3 | 4 | 1 | UNIQUE/DUPLICATE flow types not routed; `ONLY_ONCE_EACH_DUPLICATED_KEY` not implementable; per-column case sensitivity absent; no disk-based processing |
| Code Quality | **Y** | 1 | 3 | 7 | 4 | Duplicate flow-mapping logic; silent key column filtering; 10+ print() statements; temp column collision; NaN case-insensitive behavior |
| Performance & Memory | **G** | 0 | 1 | 1 | 1 | Full DataFrame copy on every execution; double copy of output DFs; no disk-based fallback |
| Testing | **R** | 1 | 2 | 0 | 0 | Zero v1 unit tests; zero integration tests; zero converter parser tests |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tUniqRow Does

`tUniqRow` (also known as `tUniqueRow`) is a Data Quality component that compares entries in an input flow and separates them into unique records and duplicate records. It is an intermediary component requiring both an input flow and at least one output flow. It belongs to the **Data Quality** family.

The component has **two named output connectors**: `UNIQUE` (for first-seen records) and `DUPLICATE` (for subsequent occurrences of matching keys). This is a **critical distinction** from components like tFilterRow, which use `FLOW`/`REJECT` connectors. The output connectors are created in Talend Studio via the `Main > Uniques` and `Main > Duplicates` context menu options.

**Sources**: [tUniqRow Standard properties (Talend 7.3)](https://help.talend.com/en-US/data-matching/7.3/tuniqrow-standard-properties), [tUniqRow Standard properties (Talend 8.0)](https://help.qlik.com/talend/en-US/data-matching/8.0/tuniqrow-standard-properties), [Component-specific settings (Job Script Reference Guide)](https://help.talend.com/en-US/job-script-reference-guide/7.3/component-specific-settings-for-tuniqrow), [tUniqRow example (Job Script Reference)](https://help.talend.com/en-US/job-script-reference-guide/7.3/tuniqrow-example), [Uniques/Duplicates (Talend Studio Help)](https://help.talend.com/en-US/studio-user-guide/8.0-R2024-08/uniques-duplicates), [Talend Unique Row Tutorial (Tutorial Gateway)](https://www.tutorialgateway.org/talend-unique-row/)

**Component family**: Data Quality (Processing)
**Available in**: All Talend products (Standard). Also available in Apache Spark Batch variant.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Shared identically between UNIQUE and DUPLICATE outputs (parallel schema). |
| 3 | Unique Key Table | `UNIQUE_KEY` | Table (groups of 3 elementValues) | -- | **Core configuration.** Per-column deduplication settings. Each logical row contains three `elementValue` entries: `SCHEMA_COLUMN` (column name), `KEY_ATTRIBUTE` (boolean -- whether this column participates in deduplication), and `CASE_SENSITIVE` (boolean -- whether comparison is case-sensitive for this specific column). |

#### UNIQUE_KEY Table Structure

The `UNIQUE_KEY` parameter is a table stored as groups of three `elementValue` entries in the Talend XML. This is NOT a simple scalar parameter -- it is a **nested table parameter** with child elements.

| elementRef | Type | Description |
|------------|------|-------------|
| `SCHEMA_COLUMN` | String | The column name from the schema (quoted in XML, e.g., `"firstName"`) |
| `KEY_ATTRIBUTE` | Boolean (`"true"`/`"false"`) | Whether this column participates in deduplication. Only columns with `KEY_ATTRIBUTE="true"` are used as key columns. |
| `CASE_SENSITIVE` | Boolean (`"true"`/`"false"`) | Whether comparison is case-sensitive **for this specific column**. Per-column setting, NOT global. |

**Example from Talend Job Script Reference:**
```
UNIQUE_KEY {
    SCHEMA_COLUMN : "id",
    KEY_ATTRIBUTE : "false",
    CASE_SENSITIVE : "false",
    SCHEMA_COLUMN : "firstName",
    KEY_ATTRIBUTE : "true",
    CASE_SENSITIVE : "true",
    SCHEMA_COLUMN : "lastName",
    KEY_ATTRIBUTE : "true",
    CASE_SENSITIVE : "false"
}
```

In this example, `firstName` and `lastName` are key columns. `firstName` is case-sensitive, while `lastName` is case-insensitive. `id` is NOT a key column (KEY_ATTRIBUTE=false) and is passed through unchanged.

**Critical Talend Behavior**: Case sensitivity is configured **per column**, not globally. Column A might be case-sensitive while Column B is case-insensitive, both within the same deduplication check. This is a fundamental design aspect that the v1 implementation does not support.

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 4 | Only once each duplicated key | `ONLY_ONCE_EACH_DUPLICATED_KEY` | Boolean (CHECK) | `false` | When checked, only the FIRST duplicate for each key group is sent to DUPLICATE output; remaining duplicates for that key are **discarded entirely** (not sent to either output). When unchecked (default), ALL subsequent duplicates are sent to DUPLICATE output. Only useful when there are 3+ rows with the same key. |
| 5 | Use of disk (virtual component) | `IS_VIRTUAL_COMPONENT` | Boolean (CHECK) | `false` | Enables temporary file generation for large datasets to prevent memory overflow. When true, the component spills intermediate data to disk. |
| 6 | Buffer size | `BUFFER_SIZE` | Enum (S/M/B) | `M` | Memory buffer rows: S = 500,000 rows, M = 1,000,000 rows, B = 2,000,000 rows. Only visible when `IS_VIRTUAL_COMPONENT=true`. |
| 7 | Temp directory | `TEMP_DIRECTORY` | String | system temp | Location for temporary files when disk-based processing is enabled. Only visible when `IS_VIRTUAL_COMPONENT=true`. |
| 8 | Ignore trailing zeros for BigDecimal | `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` | Boolean (CHECK) | `false` | When true, `1.00` and `1.0` are treated as equal for BigDecimal key columns. Affects the `hashCode()` and `equals()` methods in the generated key comparison struct. |
| 9 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used in production. |
| 10 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | connectorName in XML | Direction | Type | Description |
|-----------|---------------------|-----------|------|-------------|
| **Uniques** | `UNIQUE` | Output | Row > Uniques | Records seen for the first time based on key columns. This is **NOT** `FLOW` or `MAIN`. The first occurrence of each key combination goes here. |
| **Duplicates** | `DUPLICATE` | Output | Row > Duplicates | Subsequent occurrences of matching key combinations. This is **NOT** `REJECT`. Duplicates are normal data quality output, not error rows. Schema is identical to UNIQUE output (no extra errorCode/errorMessage columns). |
| `SUBJOB_OK` | Output (Trigger) | Trigger | -- | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | -- | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | -- | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | -- | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | -- | Conditional trigger with a boolean expression. |

**CRITICAL NOTE**: In Talend Studio, the output connectors are created via `Main > Uniques` and `Main > Duplicates` in the connection context menu. The XML `connectorName` values are `UNIQUE` and `DUPLICATE`, respectively. These are **fundamentally distinct from** the standard `FLOW`/`REJECT` connectors used by most other components. Mapping DUPLICATE to `reject` conflates two entirely different Talend concepts: error rejection (malformed data) and data quality deduplication (legitimate duplicate detection).

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_UNIQUES` | Integer | After execution | Number of unique rows sent to the UNIQUE output. This is the Talend-standard counter for this component. |
| `{id}_NB_DUPLICATES` | Integer | After execution | Number of duplicate rows sent to the DUPLICATE output. This is the Talend-standard counter for this component. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. |

**Note on NB_LINE/NB_LINE_OK/NB_LINE_REJECT**: Talend documentation does **not** list `NB_LINE`, `NB_LINE_OK`, or `NB_LINE_REJECT` as standard globalMap variables for tUniqRow. The Talend-standard statistics are `NB_UNIQUES` and `NB_DUPLICATES`. The v1 engine's use of `NB_LINE`/`NB_LINE_OK`/`NB_LINE_REJECT` is inherited from BaseComponent and is non-standard for this component, though not harmful.

### 3.5 Behavioral Notes

1. **UNIQUE vs FLOW**: The Uniques output connector has `connectorName="UNIQUE"` in Talend XML, **not** `"FLOW"`. Any implementation that assumes the unique rows flow through a `FLOW`-type connector will fail to route data correctly through the engine's primary flow routing logic.

2. **DUPLICATE vs REJECT**: The Duplicates output connector has `connectorName="DUPLICATE"`, **not** `"REJECT"`. Implementations that map duplicates to a `reject` flow must ensure the engine handles `DUPLICATE`-typed flows during output routing. Crucially, DUPLICATE rows do NOT get extra `errorCode`/`errorMessage` columns -- they share the identical schema as UNIQUE output.

3. **ONLY_ONCE_EACH_DUPLICATED_KEY behavior (detailed)**:
   - When `false` (default): First occurrence of each key goes to UNIQUE. ALL subsequent occurrences go to DUPLICATE. For 5 rows with same key: 1 UNIQUE + 4 DUPLICATE = 5 total.
   - When `true`: First occurrence goes to UNIQUE. ONLY the first duplicate (second occurrence) goes to DUPLICATE. Rows 3+ with that key are **silently discarded** (not sent to either output). For 5 rows with same key: 1 UNIQUE + 1 DUPLICATE + 3 discarded = 5 total but only 2 output.
   - This is only useful when there are 3+ rows with the same key combination.

4. **Per-column case sensitivity**: Each column in the UNIQUE_KEY table has its own CASE_SENSITIVE flag. Talend does **NOT** have a single global case_sensitive setting for tUniqRow. Column "Name" might be case-insensitive while column "Code" is case-sensitive, both within the same deduplication operation.

5. **Schema parallelism**: Both UNIQUE and DUPLICATE outputs share the identical schema structure. No extra columns are added to DUPLICATE output. This differs from tFilterRow's REJECT, which adds `errorCode` and `errorMessage` columns.

6. **Processing order**: Talend processes rows one at a time in input order. The FIRST occurrence always goes to UNIQUE. Order is deterministic and depends on input order.

7. **Null handling**: In Talend's generated Java code, `null == null` evaluates to `true` for key comparison purposes. Two rows with null in the same key column are considered duplicates.

8. **Disk-based processing**: For large datasets, Talend supports `IS_VIRTUAL_COMPONENT` mode that spills intermediate data to temporary files on disk to avoid OutOfMemoryError. Buffer sizes range from 500K to 2M rows.

9. **BigDecimal comparison**: The `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` flag changes equality semantics so that `1.00` and `1.0` are treated as equal for BigDecimal key columns. This modifies both `hashCode()` and `equals()` in the generated key struct.

10. **HashSet-based implementation**: Talend generates a `KeyStruct` inner class with `hashCode()` and `equals()` methods reflecting per-column case sensitivity. A `HashSet<KeyStruct>` tracks seen keys. Each input row creates a key struct, and `seenKeys.add(key)` returns `true` for first occurrence (UNIQUE) or `false` for subsequent occurrences (DUPLICATE).

### 3.6 Comparison: tUniqRow vs tFilterRow Output Connectors

Understanding the difference between tUniqRow and tFilterRow output connectors is essential because the v1 engine tends to generalize all components into a `main`/`reject` pattern, which is incorrect for tUniqRow.

| Aspect | tFilterRow | tUniqRow |
|--------|------------|----------|
| Output 1 connector name | `FLOW` (Main) | `UNIQUE` (Uniques) |
| Output 2 connector name | `REJECT` | `DUPLICATE` (Duplicates) |
| Output 1 semantic | Rows matching filter conditions | First-seen rows (by key) |
| Output 2 semantic | Rows failing filter conditions (errors) | Subsequent occurrences (data quality) |
| Output 2 schema | Adds `errorCode`, `errorMessage` columns | Same schema as Output 1 (no extra columns) |
| XML connectorName | `FLOW`, `REJECT` | `UNIQUE`, `DUPLICATE` |
| Engine flow type (after converter) | `flow`, `reject` | `unique`, `duplicate` |
| Engine primary routing support | Yes (`flow` and `reject` matched) | **No** (`unique` and `duplicate` not matched) |

This table makes it clear that mapping tUniqRow's DUPLICATE output to `'reject'` conflates two fundamentally different concepts: error rejection and data quality deduplication.

### 3.7 Comparison: tUniqRow vs tAggregateRow

Both components live in the `aggregate` category in the v1 engine, but they have different output patterns:

| Aspect | tAggregateRow | tUniqRow |
|--------|---------------|----------|
| Output connectors | `FLOW` (single output) | `UNIQUE` + `DUPLICATE` (dual output) |
| Processes groups | Yes (aggregation functions) | Yes (deduplication) |
| Per-column config | Group/Operation per column | Key/CaseSensitive per column |
| Dual output needed | No | Yes |
| Disk-based option | No | Yes (IS_VIRTUAL_COMPONENT) |
| GlobalMap counters | NB_LINE, NB_LINE_OK | NB_UNIQUES, NB_DUPLICATES |

### 3.8 Talend Generated Java Code Pattern

In Talend's generated Java code, tUniqRow uses a `HashSet` or `HashMap` to track seen keys. The basic pattern is:

```java
// Talend-generated code pattern (simplified)
class KeyStruct_tUniqRow_1 {
    String firstName;
    String lastName;

    @Override
    public int hashCode() {
        // Uses case-sensitive or case-insensitive hash based on PER-COLUMN setting
        int hash = 0;
        hash = hash * 31 + (firstName == null ? 0 : firstName.hashCode());          // case-sensitive
        hash = hash * 31 + (lastName == null ? 0 : lastName.toLowerCase().hashCode()); // case-insensitive
        return hash;
    }

    @Override
    public boolean equals(Object obj) {
        // Per-column case sensitivity in equals() too
        KeyStruct_tUniqRow_1 other = (KeyStruct_tUniqRow_1) obj;
        boolean eq = true;
        eq = eq && (firstName == null ? other.firstName == null : firstName.equals(other.firstName));
        eq = eq && (lastName == null ? other.lastName == null : lastName.equalsIgnoreCase(other.lastName));
        return eq;
    }
}

Set<KeyStruct_tUniqRow_1> seenKeys = new HashSet<>();
int nb_uniques = 0;
int nb_duplicates = 0;

// For each input row:
KeyStruct_tUniqRow_1 key = new KeyStruct_tUniqRow_1();
key.firstName = row.firstName;
key.lastName = row.lastName;
if (seenKeys.add(key)) {
    // Send to UNIQUE output
    nb_uniques++;
} else {
    // Send to DUPLICATE output
    nb_duplicates++;
}

// After execution:
globalMap.put("tUniqRow_1_NB_UNIQUES", nb_uniques);
globalMap.put("tUniqRow_1_NB_DUPLICATES", nb_duplicates);
```

This pattern shows that:
1. Talend processes rows **one at a time in order** -- the first occurrence always goes to UNIQUE.
2. Per-column case sensitivity is embedded in `hashCode()` and `equals()`.
3. Null handling is explicit: `null == null` is `true` (two nulls are considered equal/duplicate).
4. The `ONLY_ONCE_EACH_DUPLICATED_KEY` flag would add a secondary `Map<Key, Integer>` tracking how many duplicates have been sent per key, capping at 1.

The pandas `duplicated()` approach used by the v1 engine is functionally equivalent for the basic case but diverges on:
- **Per-column case sensitivity**: Talend supports per-column; v1 has global only.
- **Null semantics**: pandas considers NaN == NaN as True in `duplicated()`, which matches Talend's null == null behavior. However, the case-insensitive `.str.lower()` path converts NaN to NaN differently.
- **ONLY_ONCE behavior**: No direct pandas equivalent exists. The converter's mapping to `keep='last'` is incorrect.
- **Order preservation**: Both pandas and Talend process in input order. This matches.

---

## 4. Converter Audit

### 4.1 Converter Dispatch Path

The converter has **two separate code paths** for tUniqRow configuration, which creates a critical inconsistency:

**Path A: `_parse_component()` dispatch (converter.py, lines 240-243)**

```python
elif component_type == 'tUniqRow':
    component = self.component_parser.parse_unique(node, component)
elif component_type == 'tUnqRow':  # Typo variant -- not a real Talend name
    component = self.component_parser.parse_unique(node, component)
```

This dispatches to `parse_unique()`, which does XML-level parsing of the `UNIQUE_KEY` table parameter by iterating `elementValue` groups of 3.

**Path B: `parse_base_component()` -> `_map_component_parameters()` (component_parser.py, lines 207-215)**

```python
elif component_type == 'tUniqueRow':
    return {
        'key_columns': config_raw.get('UNIQUE_KEY', []),
        'case_sensitive': config_raw.get('CASE_SENSITIVE', True),
        'keep': 'first' if config_raw.get('KEEP_FIRST', True) else 'last',
        'output_duplicates': config_raw.get('OUTPUT_DUPLICATES', True),
        'is_reject_duplicate': config_raw.get('IS_REJECT_DUPLICATE', True)
    }
```

This path is reached when `parse_base_component()` processes raw parameters into `config_raw` and then calls `_map_component_parameters()`. However, `config_raw` is built by iterating `elementParameter` nodes and extracting simple `name`/`value` pairs (lines 434-458 of component_parser.py). The `UNIQUE_KEY` parameter is a **table parameter** with child `elementValue` nodes -- it is NOT a simple scalar value. Therefore `config_raw.get('UNIQUE_KEY', [])` will either return the last `elementValue` child's `value` attribute (a single string like `"true"` or `"false"`), or `[]` (the default), **never** the correctly parsed list of key columns.

**Critical Dispatch Gap: `tUniqueRow` is missing from `_parse_component()` dispatch.** The `_parse_component()` method handles `tUniqRow` and `tUnqRow` but **NOT** `tUniqueRow`. If a Talend job XML uses `componentName="tUniqueRow"`, the component will go through `parse_base_component()` -> `_map_component_parameters()` -> Path B, receiving broken `key_columns` data (empty list), which causes the engine to fall back to deduplicating on ALL columns.

### 4.2 `parse_unique()` Analysis (Path A)

The dedicated `parse_unique()` method (component_parser.py, lines 798-858):

**What it does correctly:**
- Finds `UNIQUE_KEY` elementParameter nodes via XPath: `node.findall('.//elementParameter[@name="UNIQUE_KEY"]')`
- Iterates `elementValue` children in groups of 3 (SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE)
- Checks `elementRef` attribute to identify each element's role (line 826-827)
- Only adds columns where `KEY_ATTRIBUTE == "true"` (line 828)
- Strips quotes from column names via `.strip('"')` (line 830)
- Parses `ONLY_ONCE_EACH_DUPLICATED_KEY` parameter (lines 838-841)
- Parses `CONNECTION_FORMAT` parameter (lines 843-846)

**What it does incorrectly or incompletely:**

1. **Per-column CASE_SENSITIVE is read but discarded.** The parser reads `case_sensitive_elem` (line 818) and prints it to debug output (line 823), but **never stores it per column**. Instead, line 850 sets a single global `case_sensitive` from `component['config'].get('CASE_SENSITIVE', True)`, which comes from the raw parameter extraction. Since Talend has no global `CASE_SENSITIVE` parameter for tUniqRow (it is per-column in the UNIQUE_KEY table), this will always be the default `True`. The per-column case sensitivity information that was correctly parsed from the XML is completely lost.

2. **`ONLY_ONCE_EACH_DUPLICATED_KEY` maps to wrong semantics.** Line 851: `'keep': 'last' if only_once_each_duplicated_key else 'first'`. This is semantically incorrect. See Section 5.3 for full analysis.

3. **Debug `print()` statements left in production code.** Lines 803, 807, 811, 820, 821, 822, 823, 833, 835, 856 all contain `print(f"[DEBUG] ...")` statements that output to stdout in production. These should be `logger.debug()` calls per STANDARDS.md.

4. **Brittle positional parsing.** The parser assumes elements always appear in strict groups of 3 with the order SCHEMA_COLUMN -> KEY_ATTRIBUTE -> CASE_SENSITIVE. If the Talend XML has a different ordering, includes additional element values, or has an unexpected structure, the parser will misalign and produce incorrect results. A more robust approach would build a dictionary by `elementRef` attribute for each group rather than relying on positional indexing.

5. **Boundary check `i + 2 < len(elements)` silently drops trailing elements.** If there are elements that don't form a complete group of 3 (e.g., 7 elements = 2 complete groups + 1 orphan), the last element(s) are silently ignored with no warning logged.

6. **`connection_format` extracted but unused.** Line 854 stores `connection_format` in the config, but the engine component `UniqueRow` never reads it.

### 4.3 `_map_component_parameters()` Analysis (Path B)

The `_map_component_parameters()` method (component_parser.py, lines 207-215) for `tUniqueRow`:

| # | Talend Parameter | Config Key | Extraction | Issue |
|---|------------------|------------|------------|-------|
| 1 | `UNIQUE_KEY` (table) | `key_columns` | `config_raw.get('UNIQUE_KEY', [])` | **BROKEN**: Table parameters are not flat key-value pairs; `config_raw` will not contain the parsed table structure. Will return `[]` or a garbage string, never the correct list of column names. |
| 2 | `CASE_SENSITIVE` (non-existent) | `case_sensitive` | `config_raw.get('CASE_SENSITIVE', True)` | **WRONG**: Talend has no global `CASE_SENSITIVE` param for tUniqRow. Case sensitivity is per-column in the UNIQUE_KEY table. Will always return the default `True`. |
| 3 | `KEEP_FIRST` (non-existent) | `keep` | `'first' if config_raw.get('KEEP_FIRST', True) else 'last'` | **WRONG**: Talend has no `KEEP_FIRST` parameter. The relevant param is `ONLY_ONCE_EACH_DUPLICATED_KEY`, and even that does not map to first/last. Will always return `'first'`. |
| 4 | `OUTPUT_DUPLICATES` (non-existent) | `output_duplicates` | `config_raw.get('OUTPUT_DUPLICATES', True)` | **WRONG**: Talend has no `OUTPUT_DUPLICATES` parameter. Talend always outputs duplicates when the DUPLICATE connector is connected. Will always return `True`. |
| 5 | `IS_REJECT_DUPLICATE` (non-existent) | `is_reject_duplicate` | `config_raw.get('IS_REJECT_DUPLICATE', True)` | **WRONG**: Talend has no `IS_REJECT_DUPLICATE` parameter. This is an invented parameter name that has no correspondence in Talend's component configuration. Will always return `True`. |

**Summary**: Path B references 4 non-existent Talend parameters (`CASE_SENSITIVE`, `KEEP_FIRST`, `OUTPUT_DUPLICATES`, `IS_REJECT_DUPLICATE`) and cannot parse the UNIQUE_KEY table parameter. It produces a config where `key_columns` is always `[]` (empty), causing the engine to deduplicate on ALL columns instead of the intended key columns. This path is fundamentally broken and should be deleted.

### 4.4 Parameter Extraction Summary

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Path | Notes |
|---|----------------------|------------|---------------|----------------|-------|
| 1 | `UNIQUE_KEY` (table structure) | **Partial (Path A only)** | `key_columns` | `parse_unique()` line 806 | Path A parses correctly but discards per-column CASE_SENSITIVE. Path B produces garbage. |
| 2 | `ONLY_ONCE_EACH_DUPLICATED_KEY` | **Yes (Path A)** | `keep` | `parse_unique()` line 839 | Extracted but **mapped to wrong semantics** (`keep='last'`). |
| 3 | `CONNECTION_FORMAT` | Yes (Path A) | `connection_format` | `parse_unique()` line 844 | Extracted but **not used by engine**. |
| 4 | `IS_VIRTUAL_COMPONENT` | **No** | -- | -- | Disk-based processing not supported. |
| 5 | `BUFFER_SIZE` | **No** | -- | -- | Memory buffer configuration not extracted. |
| 6 | `TEMP_DIRECTORY` | **No** | -- | -- | Temp directory for disk mode not extracted. |
| 7 | `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` | **No** | -- | -- | BigDecimal trailing zero comparison not supported. |
| 8 | `TSTATCATCHER_STATS` | **No** | -- | -- | Statistics metadata gathering not supported. |
| 9 | `LABEL` | **No** | -- | -- | Not needed (cosmetic -- no runtime impact). |
| 10 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs). |

**Summary**: 3 of 10 parameters extracted (30%). Of the 3 extracted, one produces wrong semantics (`ONLY_ONCE_EACH_DUPLICATED_KEY`), one discards critical per-column data (`UNIQUE_KEY`), and one is unused by the engine (`CONNECTION_FORMAT`). Only the basic key column list extraction is functionally useful.

### 4.5 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 475-508 of component_parser.py).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes (if present) | Integer conversion, only if attribute present in XML |
| `precision` | Yes (if present) | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes (if present) | Java date pattern converted to Python strftime: `yyyy`->`%Y`, `MM`->`%m`, `dd`->`%d` |
| `default` | **No** | Column default value not extracted from XML |
| `comment` | **No** | Column comment not extracted (cosmetic -- no runtime impact) |

**UNIQUE/DUPLICATE metadata**: The converter parses metadata nodes by the `connector` attribute (lines 504-507). A `connector="UNIQUE"` metadata node matches neither `connector == 'FLOW'` nor `connector == 'REJECT'`. This means the UNIQUE and DUPLICATE schema metadata is **NOT extracted** by the generic `parse_base_component()` method. Only `FLOW` and `REJECT` connector schemas are captured. The `parse_unique()` method does not extract schema metadata either -- it only handles config parameters. This means the component may have no output schema defined, which prevents schema enforcement on output DataFrames.

### 4.6 Expression Handling

**Context variable handling** (component_parser.py lines 449-456):
- Simple `context.var` references in non-CODE/IMPORT fields are detected by checking `'context.' in value`
- If the expression is NOT a Java expression, it is wrapped as `${context.var}` for ContextManager resolution
- If it IS a Java expression, it is left as-is for the Java expression marking step

**Java expression handling** (component_parser.py lines 462-469):
- After raw parameter extraction, the `mark_java_expression()` method scans all non-CODE/IMPORT/UNIQUE_NAME string values
- Values containing Java operators, method calls, routine references, etc. are prefixed with `{{java}}` marker
- The engine's `BaseComponent._resolve_java_expressions()` resolves these at runtime via the Java bridge

**Note for tUniqRow**: Context variables and Java expressions are uncommon in tUniqRow configuration because the UNIQUE_KEY table contains column names and boolean flags, not expressions. However, the `TEMP_DIRECTORY` parameter (when extracted) could contain context variables.

### 4.7 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-UNQ-001 | **P0** | **`tUniqueRow` not dispatched to `parse_unique()`.** `_parse_component()` in converter.py only matches `tUniqRow` (line 240) and `tUnqRow` (line 242, a typo). If a Talend job uses `componentName="tUniqueRow"`, the dedicated parser is bypassed, and `_map_component_parameters()` Path B is used instead, which produces broken `key_columns` (empty list) because `UNIQUE_KEY` is a table parameter that cannot be extracted as a flat value from `config_raw`. The engine will then deduplicate on ALL columns instead of specified keys, producing incorrect results. |
| CONV-UNQ-002 | **P1** | **Per-column case sensitivity parsed then discarded.** `parse_unique()` reads `CASE_SENSITIVE` per column from the UNIQUE_KEY table elements (line 818) and prints them to debug output (line 823), but stores only a single global `case_sensitive` boolean (line 850) sourced from `component['config'].get('CASE_SENSITIVE', True)` -- a parameter that does not exist in Talend's tUniqRow. The per-column case sensitivity data is lost. |
| CONV-UNQ-003 | **P1** | **`ONLY_ONCE_EACH_DUPLICATED_KEY` incorrectly mapped to `keep='last'`.** The converter maps `true` to `keep='last'` (line 851), but pandas `keep='last'` means "keep the LAST occurrence as unique, mark all others as duplicates." This is entirely different from Talend's behavior of "keep only the first duplicate per key group." The mapping produces completely wrong output for both UNIQUE and DUPLICATE flows. See Section 5.3. |
| CONV-UNQ-004 | **P1** | **`_map_component_parameters()` Path B references non-existent Talend parameters.** Path B references `KEEP_FIRST`, `OUTPUT_DUPLICATES`, and `IS_REJECT_DUPLICATE` -- none of which are real Talend tUniqRow parameters. These are invented parameter names that will never match anything in `config_raw`, so the defaults will always be used, masking the broken extraction. |
| CONV-UNQ-005 | **P2** | **`tUnqRow` is a typo variant with no known Talend source.** Line 242 of converter.py dispatches `tUnqRow` (missing 'i') to `parse_unique()`. This typo variant is not a known Talend component name. While harmless as defensive coding, it suggests the dispatch table was modified without careful review and the correct name `tUniqueRow` was not added. |
| CONV-UNQ-006 | **P2** | **`IS_VIRTUAL_COMPONENT` / `BUFFER_SIZE` / `TEMP_DIRECTORY` not extracted.** Talend's disk-based deduplication for large datasets is not supported. Jobs using this feature will silently fall back to in-memory processing, potentially causing OOM errors on large inputs. |
| CONV-UNQ-007 | **P2** | **`CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` not extracted.** BigDecimal trailing zero comparison semantics are lost. `Decimal("1.00")` and `Decimal("1.0")` may be treated as different values during deduplication, whereas Talend with this flag enabled treats them as equal. |
| CONV-UNQ-008 | **P2** | **Debug `print()` statements in production code.** `parse_unique()` contains 10 `print()` calls (lines 803, 807, 811, 820, 821, 822, 823, 833, 835, 856) that write to stdout in production. These should be replaced with `logger.debug()` calls per STANDARDS.md. This is a code quality violation that also produces noise in production logs/output. |
| CONV-UNQ-009 | **P2** | **UNIQUE/DUPLICATE metadata schemas not captured.** The generic `parse_base_component()` only captures `FLOW` and `REJECT` connector schemas (lines 504-507). Metadata with `connector="UNIQUE"` or `connector="DUPLICATE"` is not stored, meaning the component has no output schema for validation. |
| CONV-UNQ-010 | **P3** | **Positional parsing of UNIQUE_KEY elementValues is brittle.** The parser assumes a strict SCHEMA_COLUMN/KEY_ATTRIBUTE/CASE_SENSITIVE ordering in groups of 3. A more robust approach would match by `elementRef` attribute rather than assuming positional order. If Talend ever changes the element order or adds additional attributes, the parser will break. |
| CONV-UNQ-011 | **P3** | **Incomplete group of 3 silently dropped.** If `len(elements) % 3 != 0`, trailing elements are silently ignored with no warning logged. Should log a warning to aid debugging. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|---|----------------|-------------|----------|-----------------|-------|
| 1 | Deduplication by key columns | **Yes** | High | `_remove_duplicates()` line 249 | Uses `pd.DataFrame.duplicated()` -- solid core implementation |
| 2 | Default to all columns when no keys specified | **Yes** | High | `_remove_duplicates()` line 214-215 | Falls back to `list(input_data.columns)` when key_columns is empty |
| 3 | Case-insensitive comparison | **Partial** | Low | `_remove_duplicates()` lines 232-246 | Only global (all string key columns lowered), not per-column as Talend requires |
| 4 | `keep='first'` (default dedup behavior) | **Yes** | High | `_remove_duplicates()` line 249 | Correct default: first occurrence kept as unique, matches Talend |
| 5 | `keep='last'` | **Yes** | Medium | `_remove_duplicates()` line 249 | Available but incorrectly triggered by converter mapping of ONLY_ONCE_EACH_DUPLICATED_KEY |
| 6 | `keep=False` (drop ALL duplicates) | **Yes** | N/A | `_remove_duplicates()` line 249 | Available in engine but NO Talend equivalent; never triggered by converter |
| 7 | UNIQUE output connector routing | **Partial** | Low | `_process()` lines 170-182, `execute()` lines 279-287 | Engine outputs as `'main'` key; primary routing misses `'unique'` flow type; works only via fragile fallback |
| 8 | DUPLICATE output connector routing | **Partial** | Low | `_process()` lines 170-182, `execute()` lines 279-287 | Engine outputs as `'reject'` key; primary routing misses `'duplicate'` flow type; works only via fragile fallback |
| 9 | `ONLY_ONCE_EACH_DUPLICATED_KEY` | **No** | N/A | -- | **Not implemented.** The "send only first duplicate, discard rest" behavior has no equivalent in the engine. The converter's mapping to `keep='last'` is incorrect and produces wrong output. |
| 10 | Per-column case sensitivity | **No** | N/A | -- | **Not implemented.** Engine has single global `case_sensitive` flag applied to all string key columns uniformly |
| 11 | Disk-based processing (IS_VIRTUAL_COMPONENT) | **No** | N/A | -- | **Not implemented.** No spill-to-disk for large datasets |
| 12 | BigDecimal trailing zero comparison | **No** | N/A | -- | **Not implemented.** `Decimal("1.00") != Decimal("1.0")` in Python by default |
| 13 | `{id}_NB_UNIQUES` globalMap | **Yes** | High | `_process()` line 162 | Set via `self.global_map.put()` correctly |
| 14 | `{id}_NB_DUPLICATES` globalMap | **Yes** | High | `_process()` line 163 | Set via `self.global_map.put()` correctly |
| 15 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Not set on error. Exception is raised but globalMap variable not populated. |
| 16 | Schema enforcement on outputs | **No** | N/A | -- | Output DataFrames are not validated against output schema (UNIQUE/DUPLICATE metadata not captured either) |
| 17 | Empty/null input handling | **Yes** | High | `_process()` lines 123-129 | Returns empty DataFrames for both main and reject with stats (0, 0, 0) |
| 18 | Logging with component ID prefix | **Yes** | High | Throughout | All log messages use `[{self.id}]` prefix per STANDARDS.md |
| 19 | Statistics tracking | **Yes** | High | `_process()` lines 155-158 | NB_LINE, NB_LINE_OK, NB_LINE_REJECT updated via `_update_stats()` |
| 20 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 21 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers |

### 5.2 Flow Routing Analysis (CRITICAL)

This is the most important section of the audit. The flow routing chain for tUniqRow involves three layers: converter, engine output storage, and engine input retrieval.

#### Layer 1: Converter Flow Parsing

In `converter.py`, line 74: the converter recognizes `UNIQUE` and `DUPLICATE` as valid connectorNames:
```python
if conn_type in ['FLOW', 'MAIN', 'REJECT', 'FILTER', 'UNIQUE', 'DUPLICATE', 'ITERATE']:
```

In `_parse_flow()` (line 384-405):
```python
connector = connection.get('connectorName', 'FLOW')
return {
    'name': unique_name or label,
    'from': source,
    'to': target,
    'type': connector.lower()   # 'UNIQUE' -> 'unique', 'DUPLICATE' -> 'duplicate'
}
```

The converter correctly recognizes `UNIQUE` and `DUPLICATE` connector types and includes them in the flows list. The `type` field is set to `'unique'` and `'duplicate'` (lowercased).

#### Layer 2: Engine Output Storage

In `engine.py`, `_execute_component()` (lines 566-585):
```python
for flow in self.job_config.get('flows', []):
    if flow['from'] == comp_id:
        if flow['type'] == 'flow' and 'main' in result and result['main'] is not None:
            self.data_flows[flow['name']] = result['main']
        elif flow['type'] == 'reject' and 'reject' in result and result['reject'] is not None:
            self.data_flows[flow['name']] = result['reject']
        elif flow['type'] == 'filter' and 'main' in result and result['main'] is not None:
            self.data_flows[flow['name']] = result['main']
# Other named outputs (secondary fallback loop):
for key, value in result.items():
    if key not in ['main', 'reject', 'stats'] and value is not None:
        if key in component.outputs:
            self.data_flows[key] = value
        else:
            self.data_flows[f"{comp_id}_{key}"] = value
```

**The engine handles `flow['type']` values of `'flow'`, `'reject'`, and `'filter'` ONLY.** There is NO handling for `flow['type'] == 'unique'` or `flow['type'] == 'duplicate'`. This means:
- A flow with `type='unique'` will **not** match any of the three `if/elif` branches.
- A flow with `type='duplicate'` will **not** match any of the three `if/elif` branches.
- The data for UNIQUE and DUPLICATE outputs will **not** be stored in `self.data_flows` via the primary routing logic.

**Fallback mechanism**: The secondary loop (lines 578-585) iterates over all result keys that are not `'main'`, `'reject'`, or `'stats'`. The `UniqueRow.execute()` method override (lines 279-287) adds flow-named entries to the result:

```python
if result and hasattr(self, 'outputs') and self.outputs:
    for i, output_flow_name in enumerate(self.outputs):
        if i == 0 and 'main' in result:
            result[output_flow_name] = result['main']       # Unique data under flow name
        elif i == 1 and 'reject' in result:
            result[output_flow_name] = result['reject']      # Duplicate data under flow name
```

The `self.outputs` list is populated from the converter's `_update_component_connections()` (lines 451-465), which adds the flow's `name` (the unique_name/label from the connection XML). So if the UNIQUE flow is named `"uniques"` and the DUPLICATE flow is named `"duplicates"`, then `self.outputs = ["uniques", "duplicates"]` and the result will contain `result["uniques"] = unique_df` and `result["duplicates"] = duplicate_df`.

The engine's secondary loop then checks:
```python
if key in component.outputs:
    self.data_flows[key] = value
```

This WILL store `self.data_flows["uniques"] = unique_df` and `self.data_flows["duplicates"] = duplicate_df`.

#### Layer 3: Engine Input Retrieval

In `engine.py`, `_get_input_data()` (lines 779-794) retrieves data by flow name from `self.data_flows`. Since the fallback mechanism stores data under the flow name, and the downstream component's `inputs` list contains the same flow name, the data will be found. This layer works correctly assuming Layer 2 stored the data.

#### Verdict

The flow routing works **by accident** through the fallback mechanism in both `UniqueRow.execute()` and the engine's secondary output loop. However, this is fragile for several reasons:

1. **Duplicate flow-mapping logic runs twice.** The `_process()` method ALSO adds flow-named outputs (lines 177-182), and then `execute()` does the same thing again (lines 279-287). The same mapping logic executes twice, creating confusion about responsibility.

2. **Empty `self.outputs` breaks the fallback.** If `self.outputs` is empty or not set (which could happen if the converter fails to populate it, or if the flow connections are not properly parsed), the fallback breaks and no data is routed.

3. **Output order assumption is not guaranteed.** The assumption that `outputs[0]` is the UNIQUE flow and `outputs[1]` is the DUPLICATE flow depends on the order in which `_update_component_connections()` processes flows. If the DUPLICATE connection appears before the UNIQUE connection in the Talend XML, the mapping is reversed: unique data goes to the duplicate target and vice versa.

4. **Primary routing could interfere if flow types change.** If anyone adds `'unique'` or `'duplicate'` handling to the primary routing in the future, and the secondary loop still runs, data could be stored twice under different keys.

### 5.3 `ONLY_ONCE_EACH_DUPLICATED_KEY` Semantic Analysis

This is a nuanced Talend behavior that has no direct pandas equivalent. The converter's mapping to `keep='last'` is fundamentally incorrect.

**Talend behavior with ONLY_ONCE_EACH_DUPLICATED_KEY=true:**

Given input (key column: `name`):
```
Row 1: name="Alice"  -> UNIQUE output (first occurrence)
Row 2: name="Bob"    -> UNIQUE output (first occurrence)
Row 3: name="Alice"  -> DUPLICATE output (first duplicate of "Alice")
Row 4: name="Alice"  -> DISCARDED (second duplicate; only first duplicate sent)
Row 5: name="Bob"    -> DUPLICATE output (first duplicate of "Bob")
Row 6: name="Bob"    -> DISCARDED (second duplicate; only first duplicate sent)
```
Result: UNIQUE = [Row1, Row2] (2 rows), DUPLICATE = [Row3, Row5] (2 rows), Discarded = [Row4, Row6] (2 rows)

**Talend behavior with ONLY_ONCE_EACH_DUPLICATED_KEY=false (default):**
```
Row 1: name="Alice"  -> UNIQUE output
Row 2: name="Bob"    -> UNIQUE output
Row 3: name="Alice"  -> DUPLICATE output
Row 4: name="Alice"  -> DUPLICATE output
Row 5: name="Bob"    -> DUPLICATE output
Row 6: name="Bob"    -> DUPLICATE output
```
Result: UNIQUE = [Row1, Row2] (2 rows), DUPLICATE = [Row3, Row4, Row5, Row6] (4 rows)

**V1 engine behavior with `keep='first'` (current default, ONLY_ONCE_EACH_DUPLICATED_KEY=false):**
```
duplicated(keep='first') marks Row3, Row4, Row5, Row6 as duplicates
unique_df = [Row1, Row2]
duplicate_df = [Row3, Row4, Row5, Row6]
```
This matches Talend's default behavior. **CORRECT for the default case.**

**V1 engine behavior with `keep='last'` (converter sets this when ONLY_ONCE_EACH_DUPLICATED_KEY=true):**
```
duplicated(keep='last') marks Row1, Row3, Row5 as duplicates (keeping LAST occurrence)
unique_df = [Row2, Row4, Row6]  (LAST occurrence of each key -- WRONG)
duplicate_df = [Row1, Row3, Row5]  (includes original first occurrence -- WRONG)
```
This is **COMPLETELY WRONG**. The unique output contains the LAST rows instead of the FIRST, and the duplicate output also contains wrong rows including the original first occurrences.

**Correct implementation for ONLY_ONCE_EACH_DUPLICATED_KEY=true** would require:
1. Use `keep='first'` to identify the first occurrence of each key (same as default).
2. Among the remaining duplicates, keep only the FIRST duplicate per key group.
3. This requires a two-pass approach:
   - First pass: `duplicated(keep='first')` to separate unique from duplicate
   - Second pass: Among duplicates, `drop_duplicates(subset=key_columns, keep='first')` to keep only the first duplicate per key

### 5.4 Case Sensitivity Implementation Analysis

The engine's case-insensitive handling (lines 232-246 of `unique_row.py`):

```python
if not case_sensitive:
    for col in key_columns:
        if df[col].dtype == 'object':
            temp_col = f"_temp_{col}"
            temp_cols[col] = temp_col
            df[temp_col] = df[col].str.lower()
```

**Issues:**

1. **Global case sensitivity only.** When `case_sensitive=False`, ALL string key columns are lowercased uniformly. Talend supports per-column control where column A might be case-insensitive while column B is case-sensitive.

2. **Non-string columns silently skipped.** If a column has `dtype == 'object'` but contains mixed types (some strings, some NaN, some integers), `df[col].str.lower()` will produce NaN for non-string values. The `str` accessor returns NaN for non-string values in an object column.

3. **Temp column name collision.** If the input data already has a column named `_temp_columnName`, the temporary column will overwrite it, corrupting the original data. The temp column is dropped at cleanup (lines 256-261), which would also drop the original column with the same name. No collision check is performed.

4. **Category/string dtype detection too narrow.** The check `df[col].dtype == 'object'` does not catch `pd.CategoricalDtype`, `pd.StringDtype` ("string" dtype), or `pd.ArrowDtype(pa.string())` columns, which may also contain string data requiring case-insensitive comparison.

5. **NaN values change deduplication semantics.** When `str.lower()` encounters NaN, it produces NaN. Two rows with NaN in a case-insensitive key column would then be treated as duplicates via pandas' `duplicated()` (which considers NaN == NaN). While this matches Talend's null == null behavior, the intermediate NaN conversion path is different from the case-sensitive path, which could cause subtle behavioral differences.

### 5.5 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-UNQ-001 | **P0** | **UNIQUE/DUPLICATE flow types not handled by engine routing.** The engine's primary output routing (lines 566-576 of engine.py) only handles `flow['type']` values of `'flow'`, `'reject'`, and `'filter'`. The `'unique'` and `'duplicate'` flow types from tUniqRow are NOT matched. Data routing currently works only through a fragile fallback mechanism that depends on `UniqueRow.execute()` adding named outputs to the result dict, and the engine's secondary loop storing them. If the fallback fails (e.g., `self.outputs` is empty), downstream components receive NO data. |
| ENG-UNQ-002 | **P1** | **`ONLY_ONCE_EACH_DUPLICATED_KEY` semantics incorrect.** Mapped to `keep='last'`, which changes which row is kept as unique (last instead of first), rather than limiting duplicates to one per key group. Produces completely wrong output for both UNIQUE and DUPLICATE flows. See Section 5.3. |
| ENG-UNQ-003 | **P1** | **Per-column case sensitivity not supported.** Engine uses a single global `case_sensitive` boolean. Talend allows independent case sensitivity per key column. Jobs with mixed case sensitivity settings will produce incorrect deduplication results. |
| ENG-UNQ-004 | **P1** | **Output order depends on XML connection order.** The assumption that `outputs[0]` is the UNIQUE flow and `outputs[1]` is the DUPLICATE flow depends on the order in which `_update_component_connections()` processes flows from the XML. If DUPLICATE appears before UNIQUE in the XML, the mapping is reversed and unique data goes to the wrong target. |
| ENG-UNQ-005 | **P2** | **No disk-based processing.** Talend's `IS_VIRTUAL_COMPONENT` mode for large datasets is not implemented. Very large input datasets may cause OutOfMemoryError. |
| ENG-UNQ-006 | **P2** | **No BigDecimal trailing zero handling.** `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` not implemented. `Decimal("1.00")` and `Decimal("1.0")` treated as different values in deduplication. |
| ENG-UNQ-007 | **P2** | **`{id}_ERROR_MESSAGE` globalMap not set.** On error, Talend sets `{id}_ERROR_MESSAGE` in globalMap. The v1 engine raises a `ComponentExecutionError` exception but does not populate this globalMap variable. Downstream error handling flows referencing this variable will get null. |
| ENG-UNQ-008 | **P2** | **UNIQUE/DUPLICATE metadata schemas not captured by converter.** The generic `parse_base_component()` only captures `FLOW` and `REJECT` schemas. Metadata with `connector="UNIQUE"` or `connector="DUPLICATE"` is silently skipped, so the component has no output schema for enforcement. |
| ENG-UNQ-009 | **P3** | **Streaming mode drops duplicate output.** `BaseComponent._execute_streaming()` only collects `result['main']` from each chunk (line 270-271 of base_component.py). The `'reject'` (duplicate) output is discarded. If the engine auto-switches to streaming for a large DataFrame, all duplicate data is lost. |

### 5.6 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_UNIQUES` | Yes (standard) | **Yes** | `_process()` line 162: `self.global_map.put(f"{self.id}_NB_UNIQUES", unique_count)` | Set correctly. Matches Talend naming convention. |
| `{id}_NB_DUPLICATES` | Yes (standard) | **Yes** | `_process()` line 163: `self.global_map.put(f"{self.id}_NB_DUPLICATES", duplicate_count)` | Set correctly. Matches Talend naming convention. |
| `{id}_ERROR_MESSAGE` | Yes (on error) | **No** | -- | Not implemented. Exception is raised but globalMap not populated. |
| `{id}_NB_LINE` | Not standard for tUniqRow | **Yes** | Via `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Non-standard for tUniqRow but harmless. Inherited from BaseComponent. |
| `{id}_NB_LINE_OK` | Not standard for tUniqRow | **Yes** | Same mechanism | Non-standard. Set to unique count when `is_reject_duplicate=True`. |
| `{id}_NB_LINE_REJECT` | Not standard for tUniqRow | **Yes** | Same mechanism | Non-standard. Set to duplicate count when `is_reject_duplicate=True`, else 0. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Via BaseComponent stats | V1-specific, not in Talend. |

**Cross-cutting note**: The `_update_global_map()` method in `base_component.py` (line 304) contains a bug where it references an undefined variable `value` (should be `stat_value`). This will cause `NameError` at runtime when `global_map` is not None. This affects ALL components, not just UniqueRow. See BUG-UNQ-007.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-UNQ-001 | **P0** | `base_component.py:304` | **`_update_global_map()` references undefined variable `value`** (cross-cutting). The log statement uses `{stat_name}: {value}` but the loop variable is `stat_value`. Will cause `NameError` at runtime for ALL components when `global_map` is not None. This prevents any component from completing successfully when globalMap is configured. |
| BUG-UNQ-002 | **P1** | `unique_row.py` lines 177-182 + 279-287 | **Duplicate flow mapping runs twice.** `_process()` adds flow-named outputs (lines 177-182), and then `execute()` does the same thing again (lines 279-287). This means the same DataFrame is stored under the flow name twice in the result dict. While not causing incorrect data currently, it indicates confusion about responsibility and creates a maintenance hazard. If either method is modified independently, behavior becomes inconsistent. |
| BUG-UNQ-003 | **P1** | `unique_row.py` lines 217-218 | **Silent key column filtering.** If the converter provides key column names that do not exist in the input DataFrame, they are silently filtered out: `key_columns = [col for col in key_columns if col in input_data.columns]`. If ALL key columns are missing, the code falls through to the "No valid key columns" branch (lines 220-226) which returns ALL data as unique with no duplicates. This silently produces wrong results instead of raising a `ConfigurationError`. The only indication is a `logger.warning()` message that may be missed. |
| BUG-UNQ-004 | **P1** | `unique_row.py` line 249 | **`keep=False` passed to `pd.DataFrame.duplicated()` is misleading.** The `VALID_KEEP_OPTIONS` includes `False` (boolean). When `keep=False`, `duplicated()` marks ALL occurrences of duplicate rows (including the first). This means `unique_df` will contain only rows with NO duplicates anywhere, and `duplicate_df` will contain ALL rows that have any duplicate. There is no Talend equivalent and no converter path that produces `keep=False`. It exists as unreachable dead code that could be accidentally triggered by manual config. |
| BUG-UNQ-005 | **P2** | `unique_row.py` line 235 | **`df[col].dtype == 'object'` check too narrow for string detection.** Pandas columns with `StringDtype`, `CategoricalDtype` with string categories, or `ArrowDtype(pa.string())` will not be detected as string columns. Case-insensitive comparison will be silently skipped for these column types, producing incorrect deduplication results. |
| BUG-UNQ-006 | **P2** | `unique_row.py` lines 236-237 | **Temp column name collision.** The temp column name `f"_temp_{col}"` does not check for collision with existing columns. If the input DataFrame has a column named `_temp_myColumn`, it will be overwritten, corrupting the original data. When the temp column is dropped at cleanup (lines 256-261), the original column with the same name is also dropped. |
| BUG-UNQ-007 | **P2** | `unique_row.py` line 238 | **`str.lower()` on object column with NaN values.** If a string column contains NaN values, `df[col].str.lower()` produces NaN for those entries. Two rows with NaN in a key column would then be treated as duplicates of each other (since NaN == NaN is True in pandas `duplicated()`). While this matches Talend's null == null behavior, the intermediate transformation path differs from the case-sensitive path. |
| BUG-UNQ-008 | **P2** | `global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter** (cross-cutting). The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. This affects ALL code using `global_map.get()`. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-UNQ-001 | **P2** | **Engine output keys are `'main'`/`'reject'` but Talend connectors are `UNIQUE`/`DUPLICATE`.** The `_process()` method returns `{'main': unique_df, 'reject': duplicate_df}`. Using `'reject'` for duplicates is semantically misleading -- duplicates in tUniqRow are normal output, not errors. Talend's DUPLICATE connector is a legitimate data path, not an error/reject path. This naming causes confusion and led to the flow routing workaround. |
| NAME-UNQ-002 | **P2** | **Component docstring says `reject: Duplicate rows` conflating two different Talend concepts.** In Talend, REJECT (error rows with errorCode/errorMessage) and DUPLICATE (deduplication results with same schema) are entirely different concepts with different connectors and semantics. The docstring and return structure treat them as interchangeable. |
| NAME-UNQ-003 | **P3** | **`is_reject_duplicate` config key has no Talend equivalent.** This appears to be an invented concept. In Talend, the DUPLICATE output either exists (connector is drawn) or doesn't. There is no parameter to toggle whether duplicates are "rejects." |
| NAME-UNQ-004 | **P3** | **`output_duplicates` config key has no Talend equivalent.** Talend always outputs duplicates when the DUPLICATE connector is connected. There is no toggle to suppress duplicate output. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-UNQ-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists and validates basic types, but is never called by any code path. The base class `execute()` does not call it, and the UniqueRow `execute()` override also does not call it. All validation is dead code. |
| STD-UNQ-002 | **P2** | "Every component MUST have its own `parse_*` method" (STANDARDS.md) | The component has `parse_unique()` (Path A) but also has a conflicting `_map_component_parameters()` entry (Path B) for `tUniqueRow`. Two conflicting code paths violate the single-responsibility principle. |
| STD-UNQ-003 | **P2** | "`_validate_config()` should verify column names against schema" (STANDARDS.md) | The validator checks that `key_columns` is a list of strings but does not verify that those strings are valid column names from the component's schema. |
| STD-UNQ-004 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts schema types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format. |
| STD-UNQ-005 | **P3** | "No `print()` statements" (STANDARDS.md) | 10 `print()` statements in `parse_unique()` (component_parser.py lines 803-856). |
| STD-UNQ-006 | **P3** | "`_remove_duplicates` has unused parameter" | The `is_reject_duplicate` parameter is passed to `_remove_duplicates()` but never referenced inside the method. It only affects statistics in `_process()`. The function signature suggests it influences deduplication behavior, which is misleading. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-UNQ-001 | **P2** | **10 `print()` statements in `parse_unique()`.** Lines 803, 807, 811, 820, 821, 822, 823, 833, 835, 856 of component_parser.py contain `print(f"[DEBUG] ...")` statements. These write to stdout in production, not to the logging framework. Per STANDARDS.md, all debug output should use `logger.debug()`. Production deployments will see these messages polluting stdout. |
| DBG-UNQ-002 | **P3** | **INFO-level logging in hot path.** `_process()` logs at INFO level for every execution (lines 132, 165-166). For components in iteration loops (e.g., tFlowToIterate -> tUniqRow), this produces excessive log output. Should be DEBUG level for per-execution messages, with INFO only for summary. |

### 6.5 Structural Issues

| ID | Priority | Issue |
|----|----------|-------|
| STRUCT-UNQ-001 | **P1** | **`execute()` override duplicates `_process()` flow-mapping logic.** Both `_process()` (lines 177-182) and `execute()` (lines 279-287) contain identical logic to map output DataFrames to flow names using `self.outputs`. This violates DRY and creates a maintenance hazard. If one is updated but not the other, behavior becomes inconsistent. The flow-mapping should exist in exactly one place. |
| STRUCT-UNQ-002 | **P2** | **`_remove_duplicates()` has too many parameters (6).** The method accepts `input_data`, `key_columns`, `keep`, `case_sensitive`, `output_duplicates`, and `is_reject_duplicate`. Of these, `output_duplicates` and `is_reject_duplicate` only affect whether the duplicate DataFrame is populated and are better handled in `_process()`. The core deduplication logic only needs `input_data`, `key_columns`, `keep`, and `case_sensitive`. |

### 6.6 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-UNQ-001 | **P3** | **No input data sanitization.** Column names from the converter are used directly to index the DataFrame. If a column name contains special characters, it could potentially cause issues in downstream processing. Low risk since input is from trusted converter output. |

### 6.7 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones (lines 132, 165), WARNING for recoverable issues (lines 124, 222), ERROR for failures (line 187) -- correct pattern but INFO is too verbose for per-execution messages |
| Start/complete logging | `_process()` logs start (line 132) and completion (lines 165-166) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| print statements | 10 `print()` calls in converter `parse_unique()` -- **VIOLATION** |

### 6.8 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ComponentExecutionError` and `ConfigurationError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ComponentExecutionError(..., e) from e` pattern (line 188) -- correct |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and descriptive text -- correct |
| Graceful degradation | Returns empty DataFrames for None/empty input (lines 123-129) -- correct |
| `{id}_ERROR_MESSAGE` | **NOT set** in globalMap on error -- gap |

### 6.9 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_remove_duplicates()`, `execute()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[str]` -- correct |
| Class constants | `VALID_KEEP_OPTIONS`, `DEFAULT_KEEP`, etc. are properly typed by value -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-UNQ-001 | **P1** | **Full DataFrame copy on every execution.** Line 229: `df = input_data.copy()`. The entire input DataFrame is copied even when `case_sensitive=True` (where no temporary columns are needed). For a 10-million-row DataFrame with 50 columns, this doubles memory usage unnecessarily. Should only copy when temporary columns will be created (i.e., when `case_sensitive=False` and there are string key columns). |
| PERF-UNQ-002 | **P2** | **Double copy of unique and duplicate DataFrames.** Lines 252-253: `unique_df = df[~duplicates_mask].copy()` and `duplicate_df = df[duplicates_mask].copy()`. These create full copies of the filtered DataFrames. Combined with the initial copy on line 229, the peak memory usage is approximately 3x the input data size (original + copy + unique copy + duplicate copy, minus the overlap). For large datasets with many duplicates, this can be significant. |
| PERF-UNQ-003 | **P3** | **No disk-based processing.** Talend's `IS_VIRTUAL_COMPONENT` mode with configurable buffer sizes (500K to 2M rows) is not implemented. For datasets larger than available RAM, the component will fail with MemoryError rather than spilling to disk. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Input copy | Full copy on every execution (line 229), even when unnecessary. Peak memory = 2x input. |
| Output copies | `.copy()` on both unique and duplicate slices. Peak memory = 3x input. |
| Temp column cleanup | Temp columns are dropped after deduplication (lines 256-261). Correct cleanup. |
| Streaming mode | Inherited from BaseComponent. Auto-switches for DataFrames > 3GB. But streaming mode drops duplicate output (see ENG-UNQ-009). |
| No disk spill | Talend supports disk-based processing for large datasets. Not implemented. |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| Duplicate output dropped | `BaseComponent._execute_streaming()` only collects `result['main']` from each chunk. The `'reject'` output (containing duplicates) is discarded. All duplicate data is lost in streaming mode. |
| Cross-chunk deduplication | Streaming processes chunks independently. A duplicate that spans two chunks (first occurrence in chunk 1, second in chunk 2) will not be detected. This is a fundamental limitation of chunk-based deduplication. |
| Stats accumulation | `_update_stats()` is called per execution. In streaming mode, stats from multiple chunks would be accumulated correctly by the base class. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `UniqueRow` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests for this component |
| Converter parser tests | **No** | -- | No tests for `parse_unique()` method |
| Converter dispatch tests | **No** | -- | No tests verifying `tUniqueRow` dispatch |

**Key finding**: The v1 engine has ZERO tests for this component. All 289 lines of v1 engine code and 60 lines of converter parser code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|---|-----------|----------|-------------|
| 1 | Basic dedup with single key column | P0 | Input with duplicates on one column. Verify `unique_df` and `duplicate_df` have correct rows and row counts. |
| 2 | Basic dedup with multiple key columns | P0 | Composite key deduplication (e.g., firstName + lastName). Verify that rows must match on ALL key columns to be considered duplicates. |
| 3 | No key columns (use all) | P0 | Empty `key_columns` list. Verify all columns are used for deduplication. |
| 4 | Invalid key columns | P0 | Key columns that don't exist in input. Verify behavior (currently silent fallback; should raise error). |
| 5 | Case-insensitive dedup | P0 | `case_sensitive=False` with string columns. Verify "Alice" and "ALICE" are treated as duplicates. |
| 6 | Empty input DataFrame | P0 | Verify both outputs are empty DataFrames, no errors, stats (0, 0, 0). |
| 7 | None input | P0 | Verify both outputs are empty DataFrames, no errors, stats (0, 0, 0). |
| 8 | Output flow routing | P0 | Verify that outputs are available under both standard keys (`'main'`/`'reject'`) and flow names. |
| 9 | Statistics accuracy | P0 | Verify NB_LINE, NB_LINE_OK, NB_LINE_REJECT match actual row counts after execution. |
| 10 | Converter `parse_unique()` with valid XML | P0 | Full XML fragment with UNIQUE_KEY table, verify key_columns extraction produces correct list. |
| 11 | Converter dispatch for `tUniqueRow` | P0 | Verify `tUniqueRow` component name reaches `parse_unique()`. Currently broken -- should fail this test. |
| 12 | Engine flow routing with `type='unique'` | P0 | Verify engine stores output data for flows with `type='unique'`. Currently fails via primary routing. |
| 13 | Engine flow routing with `type='duplicate'` | P0 | Verify engine stores output data for flows with `type='duplicate'`. Currently fails via primary routing. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|---|-----------|----------|-------------|
| 14 | `keep='first'` vs `keep='last'` | P1 | Verify which specific row is retained in unique output for each mode. |
| 15 | GlobalMap variables | P1 | Verify `{id}_NB_UNIQUES` and `{id}_NB_DUPLICATES` are set correctly in globalMap after execution. |
| 16 | Mixed types in key column | P1 | Object column with strings, ints, NaN. Verify deduplication handles these correctly. |
| 17 | Case-insensitive with NaN values | P1 | String column with NaN and `case_sensitive=False`. Verify NaN handling during `str.lower()`. |
| 18 | Converter `parse_unique()` with mixed KEY_ATTRIBUTE | P1 | Some columns `KEY_ATTRIBUTE=true`, some `false`. Verify only `true` columns extracted. |
| 19 | Converter `parse_unique()` with per-column case | P1 | Different CASE_SENSITIVE per column. Verify per-column extraction (currently fails -- data discarded). |
| 20 | Per-column case sensitivity (future) | P1 | When per-column case is implemented, verify mixed case settings work correctly. |
| 21 | ONLY_ONCE_EACH_DUPLICATED_KEY (future) | P1 | When implemented, verify only first duplicate per key is output, rest discarded. |
| 22 | Integration: tFileInputDelimited -> tUniqRow -> tFileOutputDelimited x2 | P1 | End-to-end test with two output files (uniques and duplicates). Verify both files have correct data. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|---|-----------|----------|-------------|
| 23 | Large DataFrame performance | P2 | Benchmark memory usage for 1M+ rows. Verify no unexpected copies beyond the documented 3x. |
| 24 | Temp column name collision | P2 | Input with `_temp_colname` column. Verify original data is not corrupted. |
| 25 | `output_duplicates=False` | P2 | Verify reject output is empty DataFrame and stats still count duplicates. |
| 26 | Streaming mode behavior | P2 | Verify behavior when auto-switching to streaming. Document that duplicate data is dropped. |
| 27 | All columns are string type with case-insensitive | P2 | Verify all string columns get temp lowercase columns and cleanup works correctly. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| CONV-UNQ-001 | Converter Dispatch | `tUniqueRow` component name not dispatched to `parse_unique()` in converter.py; falls through to broken `_map_component_parameters()` Path B that cannot parse UNIQUE_KEY table parameter. All key columns will be empty, causing deduplication on ALL columns instead of specified keys. |
| ENG-UNQ-001 | Engine Flow Routing | Engine's primary output routing does not handle `flow['type'] == 'unique'` or `flow['type'] == 'duplicate'`. Data routing works only through a fragile fallback mechanism. If fallback fails (e.g., empty `self.outputs`), downstream components receive no data. |
| TEST-UNQ-001 | Testing | Zero unit tests for the UniqueRow engine component. All 289 lines of v1 engine code are completely unverified. No converter parser tests either. |
| BUG-UNQ-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Crashes ALL components when `global_map` is set. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-UNQ-002 | Converter | Per-column case sensitivity from UNIQUE_KEY table is parsed but discarded. Only a single global `case_sensitive` boolean is stored. Jobs with mixed per-column case sensitivity produce wrong results. |
| CONV-UNQ-003 | Converter | `ONLY_ONCE_EACH_DUPLICATED_KEY=true` incorrectly mapped to `keep='last'`. Produces completely wrong output for both unique and duplicate flows. `keep='last'` keeps the LAST occurrence as unique, which is entirely different from Talend's "send only first duplicate" behavior. |
| CONV-UNQ-004 | Converter | `_map_component_parameters()` Path B references non-existent Talend parameters (`KEEP_FIRST`, `OUTPUT_DUPLICATES`, `IS_REJECT_DUPLICATE`). These are invented names that never match anything in the XML. |
| ENG-UNQ-002 | Engine | `ONLY_ONCE_EACH_DUPLICATED_KEY` semantics not implemented. No mechanism to limit duplicate output to one row per key group. Would require two-pass deduplication. |
| ENG-UNQ-003 | Engine | Per-column case sensitivity not supported. Single global boolean applied to all key columns uniformly. |
| ENG-UNQ-004 | Engine | Output order depends on XML connection order. `outputs[0]`=UNIQUE and `outputs[1]`=DUPLICATE is assumed but not guaranteed by the converter. Reversed order causes data to go to wrong targets. |
| BUG-UNQ-002 | Code Quality | Duplicate flow-mapping logic in both `_process()` and `execute()`. DRY violation and maintenance hazard -- if one is modified without the other, behavior diverges. |
| BUG-UNQ-003 | Code Quality | Silent key column filtering drops nonexistent columns without error. All-missing keys silently returns all data as unique with zero duplicates. Should raise `ConfigurationError`. |
| STRUCT-UNQ-001 | Code Quality | `execute()` override duplicates `_process()` flow-mapping logic. Same logic exists in two places. |
| PERF-UNQ-001 | Performance | Full DataFrame copy on every execution, even when no temp columns needed (case_sensitive=True). Doubles memory usage unnecessarily for the common case. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-UNQ-005 | Converter | `tUnqRow` typo variant in dispatch (missing 'i') with no known Talend source. |
| CONV-UNQ-006 | Converter | `IS_VIRTUAL_COMPONENT` / `BUFFER_SIZE` / `TEMP_DIRECTORY` not extracted. Disk-based processing unavailable. |
| CONV-UNQ-007 | Converter | `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` not extracted. BigDecimal trailing zero comparison lost. |
| CONV-UNQ-008 | Converter | 10 `print()` debug statements in production code in `parse_unique()`. Should be `logger.debug()`. |
| CONV-UNQ-009 | Converter | UNIQUE/DUPLICATE metadata schemas not captured by generic `parse_base_component()`. |
| ENG-UNQ-005 | Engine | No disk-based processing for large datasets. OOM risk. |
| ENG-UNQ-006 | Engine | No BigDecimal trailing zero handling. `Decimal("1.00") != Decimal("1.0")`. |
| ENG-UNQ-007 | Engine | `{id}_ERROR_MESSAGE` globalMap not set on error. |
| ENG-UNQ-008 | Engine | UNIQUE/DUPLICATE metadata schemas not captured, preventing output schema enforcement. |
| BUG-UNQ-005 | Code Quality | `dtype == 'object'` check too narrow; misses `StringDtype`, `CategoricalDtype`. |
| BUG-UNQ-006 | Code Quality | Temp column name collision possible with `_temp_` prefix. No collision check. |
| BUG-UNQ-007 | Code Quality | `str.lower()` on NaN values produces NaN, changing deduplication semantics in subtle ways. |
| BUG-UNQ-008 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined `default` parameter. Crashes on any `.get()` call. |
| NAME-UNQ-001 | Naming | Engine uses `'main'`/`'reject'` output keys but Talend uses `UNIQUE`/`DUPLICATE`. Semantically misleading. |
| NAME-UNQ-002 | Naming | Docstring conflates REJECT (error) with DUPLICATE (data quality). |
| STD-UNQ-001 | Standards | `_validate_config()` exists but never called -- dead validation code. |
| STD-UNQ-002 | Standards | Two conflicting code paths (Path A and Path B) for the same component. |
| STD-UNQ-003 | Standards | `_validate_config()` does not check key columns against schema. |
| STD-UNQ-004 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| STRUCT-UNQ-002 | Code Quality | `_remove_duplicates()` has 6 parameters; 2 are unused by the deduplication logic. |
| PERF-UNQ-002 | Performance | Double copy of unique/duplicate DataFrames. Peak memory approximately 3x input. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-UNQ-010 | Converter | Positional parsing of UNIQUE_KEY elementValues is brittle. Should match by `elementRef` attribute. |
| CONV-UNQ-011 | Converter | Incomplete group of 3 elements silently dropped without warning. |
| ENG-UNQ-009 | Engine | Streaming mode drops duplicate output. All duplicate data lost when auto-switching to streaming. |
| BUG-UNQ-004 | Code Quality | `keep=False` in `VALID_KEEP_OPTIONS` is unreachable dead code with no Talend equivalent. |
| NAME-UNQ-003 | Naming | `is_reject_duplicate` config key has no Talend equivalent. |
| NAME-UNQ-004 | Naming | `output_duplicates` config key has no Talend equivalent. |
| STD-UNQ-005 | Standards | `print()` statements in `parse_unique()` -- also covered by CONV-UNQ-008. |
| STD-UNQ-006 | Standards | `_remove_duplicates()` accepts unused `is_reject_duplicate` parameter. Misleading signature. |
| SEC-UNQ-001 | Security | No input data sanitization on column names from converter. Low risk. |
| DBG-UNQ-002 | Debug | INFO-level logging in hot path. Excessive output in iteration loops. |
| PERF-UNQ-003 | Performance | No disk-based processing for very large datasets. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 1 converter dispatch, 1 engine routing, 1 testing, 1 bug (cross-cutting) |
| P1 | 10 | 3 converter, 3 engine, 2 bugs, 1 structural, 1 performance |
| P2 | 21 | 5 converter, 4 engine, 4 bugs (incl. 1 cross-cutting), 2 naming, 4 standards, 1 structural, 1 performance |
| P3 | 11 | 2 converter, 1 engine, 1 bug, 2 naming, 2 standards, 1 security, 1 debug, 1 performance |
| **Total** | **46** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix converter dispatch for `tUniqueRow`** (CONV-UNQ-001). Add `elif component_type == 'tUniqueRow':` to `_parse_component()` in converter.py, dispatching to `self.component_parser.parse_unique(node, component)`. This is a one-line fix that resolves a P0 issue. The existing dispatch on line 240 handles `tUniqRow`; add the equivalent for `tUniqueRow` immediately after.

2. **Add `'unique'` and `'duplicate'` flow type handling to engine** (ENG-UNQ-001). In `engine.py`, `_execute_component()`, add two new branches after the existing `flow`/`reject`/`filter` handling:
   ```python
   elif flow['type'] == 'unique' and 'main' in result and result['main'] is not None:
       self.data_flows[flow['name']] = result['main']
   elif flow['type'] == 'duplicate' and 'reject' in result and result['reject'] is not None:
       self.data_flows[flow['name']] = result['reject']
   ```
   This ensures the primary routing path works for tUniqRow flows, eliminating dependence on the fragile fallback mechanism.

3. **Fix `_update_global_map()` bug** (BUG-UNQ-001). Change `value` to `stat_value` on `base_component.py` line 304. Better yet, simplify the log message to remove the stale reference entirely. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

4. **Fix `GlobalMap.get()` bug** (BUG-UNQ-008). Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL code using `global_map.get()`. **Risk**: Very low.

5. **Create comprehensive unit test suite** (TEST-UNQ-001). Cover all P0 test cases listed in Section 8.2 (items 1-13). At minimum: basic deduplication, empty/null input, case sensitivity, statistics, flow routing, and converter dispatch.

6. **Remove `print()` statements** (CONV-UNQ-008). Replace all `print(f"[DEBUG]...")` in `parse_unique()` with `logger.debug(...)`. 10 occurrences to fix.

### Short-Term (Hardening)

7. **Fix `ONLY_ONCE_EACH_DUPLICATED_KEY` mapping** (CONV-UNQ-003, ENG-UNQ-002). Change the converter to NOT map this to `keep='last'`. Instead, add a new config key like `only_once_duplicated: bool`. Implement a two-pass deduplication in the engine:
   - First pass: `duplicated(keep='first')` to identify all duplicates
   - Second pass: Among duplicates, `drop_duplicates(subset=key_columns, keep='first')` to keep only the first duplicate per key group

8. **Implement per-column case sensitivity** (CONV-UNQ-002, ENG-UNQ-003). Modify `parse_unique()` to store per-column case sensitivity. Change the engine's config from a single `case_sensitive: bool` to `key_columns_config: List[Dict]` where each dict has `{'column': str, 'case_sensitive': bool}`. Update `_remove_duplicates()` to create temp lowercase columns only for columns marked as case-insensitive.

9. **Consolidate flow-mapping logic** (BUG-UNQ-002, STRUCT-UNQ-001). Remove the flow-mapping from `_process()` (lines 177-182) and keep it only in `execute()` (lines 279-287). Or better yet, move all flow-mapping to the engine's output routing as recommended in item #2.

10. **Fix silent key column filtering** (BUG-UNQ-003). Raise `ConfigurationError` if any configured key columns are not present in the input DataFrame, rather than silently filtering them out. Missing key columns indicate a configuration or schema mismatch that should be reported immediately.

11. **Remove Path B from `_map_component_parameters()`** (CONV-UNQ-004). Delete the `elif component_type == 'tUniqueRow':` block from `_map_component_parameters()` (lines 208-215). All tUniqRow/tUniqueRow parsing should go through `parse_unique()`. Having two conflicting code paths is a source of confusion and bugs.

12. **Fix UNIQUE/DUPLICATE metadata schema extraction** (CONV-UNQ-009). In `parse_base_component()`, add handling for `connector="UNIQUE"` and `connector="DUPLICATE"` metadata nodes. Store them as output schemas to enable downstream schema enforcement.

13. **Wire up `_validate_config()`** (STD-UNQ-001). Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` for non-empty results. Alternatively, add validation as a standard lifecycle step in `BaseComponent.execute()`.

14. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-UNQ-007). In the `except` block of `_process()` (line 186-188), before re-raising, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

### Long-Term (Optimization)

15. **Implement disk-based processing** (CONV-UNQ-006, ENG-UNQ-005). For large datasets, support `IS_VIRTUAL_COMPONENT` mode with configurable buffer sizes and temp directory. Could use `dask` or chunked processing with an on-disk hash set.

16. **Optimize memory usage** (PERF-UNQ-001, PERF-UNQ-002). Only copy the DataFrame when temp columns are needed (case_sensitive=False with string columns). Use views instead of copies where possible. Consider using boolean indexing without `.copy()` for final output when the original DataFrame is no longer needed.

17. **Fix streaming mode** (ENG-UNQ-009). The base class streaming mode only collects `result['main']` from chunks. Extend it to also collect and concatenate `result['reject']` (or in this case, duplicate) outputs. Note that cross-chunk deduplication is a fundamental limitation that requires a different approach (e.g., maintaining a global seen-keys set across chunks).

18. **Implement BigDecimal trailing zero handling** (CONV-UNQ-007, ENG-UNQ-006). Normalize BigDecimal columns before comparison to ignore trailing zeros. Can use `Decimal.normalize()` on key column values before deduplication.

19. **Fix temp column collision** (BUG-UNQ-006). Use UUIDs or hash-based temp column names to avoid collisions: `f"__dedup_temp_{uuid.uuid4().hex[:8]}_{col}"`.

20. **Improve string dtype detection** (BUG-UNQ-005). Use `pd.api.types.is_string_dtype(df[col])` instead of `df[col].dtype == 'object'` to properly detect all string column types including `StringDtype` and `ArrowDtype(pa.string())`.

---

## Appendix A: Code Flow Diagram

```
Talend XML (.item file)
    |
    v
converter.py::_parse_component()
    |-- componentName == 'tUniqRow'  --> component_parser.parse_unique(node, component)  [WORKS]
    |-- componentName == 'tUnqRow'   --> component_parser.parse_unique(node, component)  [typo variant]
    |-- componentName == 'tUniqueRow' --> parse_base_component() --> _map_component_parameters()  [BROKEN: Path B]
    |
    v
component_parser.py::parse_unique() [Path A -- only for tUniqRow/tUnqRow]
    |-- Finds UNIQUE_KEY elementParameter
    |-- Iterates elementValue children in groups of 3
    |-- For each group: checks SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE
    |-- Adds column to key_columns if KEY_ATTRIBUTE="true"
    |-- DISCARDS per-column CASE_SENSITIVE (stores global only)
    |-- Parses ONLY_ONCE_EACH_DUPLICATED_KEY (maps to keep='last' -- WRONG)
    |-- Stores config: key_columns, case_sensitive, keep, output_duplicates, is_reject_duplicate
    |-- PRINTS 10 debug statements to stdout
    |
    v
converter.py::_parse_flow()
    |-- connectorName == 'UNIQUE'    --> flow['type'] = 'unique'
    |-- connectorName == 'DUPLICATE' --> flow['type'] = 'duplicate'
    |
    v
converter.py::_update_component_connections()
    |-- Adds flow name to source component's outputs list
    |-- Adds flow name to target component's inputs list
    |-- ORDER DEPENDS ON XML CONNECTION ORDER (not guaranteed)
    |
    v
JSON job config
    |-- components: [{ "id": "tUniqRow_1", "type": "UniqueRow", "config": {...}, "outputs": ["uniques", "duplicates"] }]
    |-- flows: [
    |     { "name": "uniques",    "from": "tUniqRow_1", "to": "tLogRow_1", "type": "unique" },
    |     { "name": "duplicates", "from": "tUniqRow_1", "to": "tLogRow_2", "type": "duplicate" }
    |   ]
    |
    v
engine.py::_initialize_components()
    |-- Looks up 'UniqueRow' in COMPONENT_REGISTRY
    |-- Creates UniqueRow instance with config
    |-- Sets component.outputs = ["uniques", "duplicates"]  (from converter)
    |
    v
engine.py::_execute_component()
    |-- Calls component.execute(input_data)
    |
    |-- UniqueRow.execute() calls super().execute() which calls _process()
    |-- _process() returns:
    |     { 'main': unique_df, 'reject': dup_df, 'uniques': unique_df, 'duplicates': dup_df }
    |-- execute() adds AGAIN:
    |     { ..., 'uniques': unique_df, 'duplicates': dup_df }  (redundant)
    |
    |-- Primary routing: checks flow['type'] against 'flow', 'reject', 'filter'
    |     --> MISSES 'unique' and 'duplicate'  [BUG: ENG-UNQ-001]
    |
    |-- Fallback routing: iterates result keys, finds 'uniques' and 'duplicates' in component.outputs
    |     --> Stores self.data_flows['uniques'] = unique_df    [WORKS by accident]
    |     --> Stores self.data_flows['duplicates'] = dup_df     [WORKS by accident]
    |
    v
Downstream components receive data via _get_input_data()
    |-- Looks up flow name in self.data_flows
    |-- Finds 'uniques' or 'duplicates' data
    |-- Returns to downstream component
```

---

## Appendix B: Talend XML Structure Example

```xml
<node componentName="tUniqRow" componentVersion="0.101"
      offsetLabelX="0" offsetLabelY="0" posX="384" posY="192">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tUniqRow_1"/>

  <!-- UNIQUE_KEY table parameter: groups of 3 elementValue entries -->
  <elementParameter field="TABLE" name="UNIQUE_KEY">
    <!-- Column 1: firstName, IS a key, case-sensitive -->
    <elementValue elementRef="SCHEMA_COLUMN" value="&quot;firstName&quot;"/>
    <elementValue elementRef="KEY_ATTRIBUTE" value="true"/>
    <elementValue elementRef="CASE_SENSITIVE" value="true"/>

    <!-- Column 2: lastName, IS a key, case-INSENSITIVE -->
    <elementValue elementRef="SCHEMA_COLUMN" value="&quot;lastName&quot;"/>
    <elementValue elementRef="KEY_ATTRIBUTE" value="true"/>
    <elementValue elementRef="CASE_SENSITIVE" value="false"/>

    <!-- Column 3: id, NOT a key column -->
    <elementValue elementRef="SCHEMA_COLUMN" value="&quot;id&quot;"/>
    <elementValue elementRef="KEY_ATTRIBUTE" value="false"/>
    <elementValue elementRef="CASE_SENSITIVE" value="false"/>
  </elementParameter>

  <!-- Advanced setting: only send first duplicate per key to DUPLICATE output -->
  <elementParameter field="CHECK" name="ONLY_ONCE_EACH_DUPLICATED_KEY" value="false"/>

  <!-- UNIQUE output schema (connector="UNIQUE", NOT "FLOW") -->
  <metadata connector="UNIQUE" name="tUniqRow_1">
    <column key="false" name="id" nullable="true" type="id_Integer"/>
    <column key="false" name="firstName" nullable="true" type="id_String"/>
    <column key="false" name="lastName" nullable="true" type="id_String"/>
  </metadata>

  <!-- DUPLICATE output schema (connector="DUPLICATE", NOT "REJECT") -->
  <metadata connector="DUPLICATE" name="tUniqRow_1">
    <column key="false" name="id" nullable="true" type="id_Integer"/>
    <column key="false" name="firstName" nullable="true" type="id_String"/>
    <column key="false" name="lastName" nullable="true" type="id_String"/>
  </metadata>
</node>

<!-- UNIQUE output connection (connectorName="UNIQUE") -->
<connection connectorName="UNIQUE" label="uniques" lineStyle="0"
            metaname="tUniqRow_1" offsetLabelX="0" offsetLabelY="0"
            source="tUniqRow_1" target="tLogRow_1">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="uniques"/>
</connection>

<!-- DUPLICATE output connection (connectorName="DUPLICATE") -->
<connection connectorName="DUPLICATE" label="duplicates" lineStyle="0"
            metaname="tUniqRow_1" offsetLabelX="0" offsetLabelY="0"
            source="tUniqRow_1" target="tLogRow_2">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="duplicates"/>
</connection>
```

---

## Appendix C: Converter Parameter Mapping Code

### Path A: `parse_unique()` (component_parser.py lines 798-858)

```python
def parse_unique(self, node, component: Dict) -> Dict:
    """Parse tUniqueRow specific configuration"""
    key_columns = []

    # Add debugging to see what we're parsing
    print(f"[DEBUG] Parsing tUniqueRow component: {component.get('id', 'unknown')}")

    # Parse UNIQUE_KEY table parameter - handle SCHEMA_COLUMN/KEY_ATTRIBUTE pairs
    unique_key_params = node.findall('.//elementParameter[@name="UNIQUE_KEY"]')
    print(f"[DEBUG] Found {len(unique_key_params)} UNIQUE_KEY parameters")

    for param in unique_key_params:
        elements = list(param.findall('./elementValue'))
        print(f"[DEBUG] Found {len(elements)} elementValue entries in UNIQUE_KEY")

# Group elements by sets of 3 (SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE)
    for i in range(0, len(elements), 3):
        if i + 2 < len(elements):
            schema_col_elem = elements[i]
            key_attr_elem = elements[i + 1]
            case_sensitive_elem = elements[i + 2]

            print(f"[DEBUG] Element {i//3 + 1}:")
            print(f"  Schema: ref='{schema_col_elem.get('elementRef')}' value='{schema_col_elem.get('value')}'")
            print(f"  Key Attr: ref='{key_attr_elem.get('elementRef')}' value='{key_attr_elem.get('value')}'")
            print(f"  Case Sens: ref='{case_sensitive_elem.get('elementRef')}' value='{case_sensitive_elem.get('value')}'")

            # Check if this is a key column (KEY_ATTRIBUTE = true)
            if (schema_col_elem.get('elementRef') == 'SCHEMA_COLUMN' and
                key_attr_elem.get('elementRef') == 'KEY_ATTRIBUTE' and
                key_attr_elem.get('value', 'false').lower() == 'true'):

                col_name = schema_col_elem.get('value', '').strip('"')
                if col_name:
                    key_columns.append(col_name)
                    print(f"[DEBUG] Added key column: {col_name}")

    print(f"[DEBUG] Final key_columns list: {key_columns}")

    # Parse other configuration parameters
    only_once_each_duplicated_key = False
    for param in node.findall('.//elementParameter[@name="ONLY_ONCE_EACH_DUPLICATED_KEY"]'):
        only_once_each_duplicated_key = param.get('value', 'false').lower() == 'true'
        break

    connection_format = 'row'
    for param in node.findall('.//elementParameter[@name="CONNECTION_FORMAT"]'):
        connection_format = param.get('value', 'row')
        break

    # Map to component config
    component['config']['key_columns'] = key_columns
    component['config']['case_sensitive'] = component['config'].get('CASE_SENSITIVE', True)  # WRONG: global, not per-column
    component['config']['keep'] = 'last' if only_once_each_duplicated_key else 'first'       # WRONG: see Section 5.3
    component['config']['output_duplicates'] = True
    component['config']['is_reject_duplicate'] = True
    component['config']['connection_format'] = connection_format

    print(f"[DEBUG] Final component config: {component['config']}")

    return component
```

**Issues with this code**:
- Line 803, 807, 811, 820-823, 833, 835, 856: `print()` statements should be `logger.debug()`
- Line 850: `component['config'].get('CASE_SENSITIVE', True)` references a non-existent parameter; always returns `True`
- Line 851: `'last' if only_once_each_duplicated_key else 'first'` is semantically wrong (see Section 5.3)
- Lines 818 (case_sensitive_elem): Per-column case sensitivity is parsed but never stored
- Line 814: Strict positional grouping; no elementRef-based matching for robustness
- Line 815: `i + 2 < len(elements)` silently drops incomplete groups

### Path B: `_map_component_parameters()` (component_parser.py lines 207-215)

```python
# UniqueRow mapping
elif component_type == 'tUniqueRow':
    return {
        'key_columns': config_raw.get('UNIQUE_KEY', []),        # BROKEN: table param not in config_raw
        'case_sensitive': config_raw.get('CASE_SENSITIVE', True), # WRONG: no such Talend param
        'keep': 'first' if config_raw.get('KEEP_FIRST', True) else 'last',  # WRONG: no such Talend param
        'output_duplicates': config_raw.get('OUTPUT_DUPLICATES', True),      # WRONG: no such Talend param
        'is_reject_duplicate': config_raw.get('IS_REJECT_DUPLICATE', True)   # WRONG: no such Talend param
    }
```

**This entire block should be deleted.** All 5 parameters reference non-existent Talend properties. The `UNIQUE_KEY` table parameter cannot be extracted by the flat key-value loop in `parse_base_component()`.

---

## Appendix D: Engine Class Structure

```
UniqueRow(BaseComponent)
    Constants:
        VALID_KEEP_OPTIONS = ['first', 'last', False]
        DEFAULT_KEEP = 'first'
        DEFAULT_CASE_SENSITIVE = True
        DEFAULT_OUTPUT_DUPLICATES = True
        DEFAULT_IS_REJECT_DUPLICATE = True

    Methods:
        _validate_config() -> List[str]          # Validates types; NEVER CALLED
        _process(input_data) -> Dict[str, Any]   # Main entry point; returns main+reject+named outputs
        _remove_duplicates(...) -> Dict           # Core dedup logic with pandas duplicated()
        execute(input_data) -> Dict[str, Any]     # Override: calls super().execute() + adds flow-name mapping (REDUNDANT with _process())

    Config Keys (from converter):
        key_columns: List[str]           # Columns to check for duplicates (from UNIQUE_KEY table)
        keep: str                        # 'first', 'last', or False (from ONLY_ONCE_EACH_DUPLICATED_KEY, WRONG mapping)
        case_sensitive: bool             # Global case sensitivity (should be per-column)
        output_duplicates: bool          # Whether to output duplicates (invented, always True)
        is_reject_duplicate: bool        # Whether to count duplicates as rejects (invented, always True)
        connection_format: str           # 'row' (extracted but unused)

    Output Keys:
        'main': unique_df               # First-seen rows (maps to Talend UNIQUE)
        'reject': duplicate_df           # Duplicate rows (maps to Talend DUPLICATE -- misleading name)
        {flow_name}: unique_df/dup_df   # Named outputs for engine fallback routing

    Stats:
        NB_LINE: total input rows
        NB_LINE_OK: unique rows (when is_reject_duplicate=True)
        NB_LINE_REJECT: duplicate rows (when is_reject_duplicate=True, else 0)

    Custom GlobalMap:
        {id}_NB_UNIQUES: unique row count
        {id}_NB_DUPLICATES: duplicate row count
```

---

## Appendix E: Correct `ONLY_ONCE_EACH_DUPLICATED_KEY` Implementation

```python
def _remove_duplicates_with_only_once(self, df, key_columns, temp_key_columns):
    """
    Implement ONLY_ONCE_EACH_DUPLICATED_KEY=true behavior.

    Talend behavior:
    - First occurrence of each key -> UNIQUE output
    - ONLY the first duplicate of each key -> DUPLICATE output
    - All subsequent duplicates (3rd, 4th, etc.) -> DISCARDED

    Returns:
        unique_df: First occurrence of each key group
        duplicate_df: ONLY the first duplicate of each key group (not all duplicates)
    """
    # Step 1: Identify first occurrences (unique rows) -- same as default
    first_mask = ~df.duplicated(subset=temp_key_columns, keep='first')
    unique_df = df[first_mask].copy()

    # Step 2: Get all duplicates (rows that are NOT first occurrences)
    all_duplicates = df[~first_mask].copy()

    # Step 3: Among duplicates, keep only the FIRST one per key group
    # This gives us the "second occurrence" of each key -- the first duplicate
    if not all_duplicates.empty:
        first_dup_mask = ~all_duplicates.duplicated(subset=temp_key_columns, keep='first')
        duplicate_df = all_duplicates[first_dup_mask].copy()
    else:
        duplicate_df = pd.DataFrame(columns=df.columns)

    return unique_df, duplicate_df

# Usage in _remove_duplicates():
# if only_once_each_duplicated_key:
#     return self._remove_duplicates_with_only_once(df, key_columns, temp_key_columns)
# else:
#     # Standard behavior: all duplicates go to DUPLICATE output
#     duplicates_mask = df.duplicated(subset=temp_key_columns, keep='first')
#     unique_df = df[~duplicates_mask].copy()
#     duplicate_df = df[duplicates_mask].copy()
#     return {'unique': unique_df, 'duplicate': duplicate_df}
```

---

## Appendix F: Correct Per-Column Case Sensitivity Implementation

```python
def _create_temp_columns(self, df, key_columns_config):
    """
    Create temp columns for per-column case-insensitive comparison.

    Args:
        df: Input DataFrame
        key_columns_config: List of dicts with 'column' and 'case_sensitive' keys
            e.g., [{'column': 'firstName', 'case_sensitive': True},
                   {'column': 'lastName', 'case_sensitive': False}]

    Returns:
        temp_key_columns: List of column names to use for deduplication
        temp_cols_to_drop: List of temporary column names to clean up
    """
    temp_key_columns = []
    temp_cols_to_drop = []

    for col_config in key_columns_config:
        col = col_config['column']
        case_sensitive = col_config.get('case_sensitive', True)

        if not case_sensitive and pd.api.types.is_string_dtype(df[col]):
            # Generate collision-safe temp column name using object id
            temp_col = f"__dedup_{col}_{id(df)}"
            df[temp_col] = df[col].str.lower()
            temp_key_columns.append(temp_col)
            temp_cols_to_drop.append(temp_col)
        else:
            temp_key_columns.append(col)

    return temp_key_columns, temp_cols_to_drop

# Updated parse_unique() in converter would store:
# component['config']['key_columns_config'] = [
#     {'column': 'firstName', 'case_sensitive': True},
#     {'column': 'lastName', 'case_sensitive': False}
# ]
```

---

## Appendix G: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `UNIQUE_KEY` (table: SCHEMA_COLUMN) | `key_columns` (list) | Mapped (Path A) | -- |
| `UNIQUE_KEY` (table: KEY_ATTRIBUTE) | (used to filter key_columns) | Mapped (Path A) | -- |
| `UNIQUE_KEY` (table: CASE_SENSITIVE) | `case_sensitive` (global bool) | **Partial** -- per-column data discarded | P1 |
| `ONLY_ONCE_EACH_DUPLICATED_KEY` | `keep` | **Wrong mapping** (`keep='last'`) | P1 |
| `CONNECTION_FORMAT` | `connection_format` | Mapped but unused | P3 |
| `IS_VIRTUAL_COMPONENT` | -- | **Not Mapped** | P2 |
| `BUFFER_SIZE` | -- | **Not Mapped** | P2 |
| `TEMP_DIRECTORY` | -- | **Not Mapped** | P2 |
| `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` | -- | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed (tStatCatcher rarely used) | -- |
| `LABEL` | -- | Not needed (cosmetic) | -- |
| `PROPERTY_TYPE` | -- | Not needed (always Built-In) | -- |

---

## Appendix H: Edge Case Analysis

### Edge Case 1: Empty input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows on both outputs, NB_UNIQUES=0, NB_DUPLICATES=0. No error. |
| **V1** | `_process()` checks `input_data.empty` (line 123), returns `{'main': pd.DataFrame(), 'reject': pd.DataFrame()}`. Stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: None input

| Aspect | Detail |
|--------|--------|
| **Talend** | Component requires input; None would be a design error. |
| **V1** | `_process()` checks `input_data is None` (line 123), returns empty DataFrames. Stats (0, 0, 0). |
| **Verdict** | CORRECT (graceful degradation) |

### Edge Case 3: No key columns specified

| Aspect | Detail |
|--------|--------|
| **Talend** | All columns in the schema appear in UNIQUE_KEY table; those with KEY_ATTRIBUTE=false are not keys. If no columns have KEY_ATTRIBUTE=true, component has no deduplication keys. |
| **V1** | Empty `key_columns` falls back to `list(input_data.columns)` (line 215), deduplicating on ALL columns. |
| **Verdict** | PARTIAL -- Talend would use no keys (no deduplication), v1 uses all columns. Different behavior. |

### Edge Case 4: Key column not in input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Schema mismatch would cause compile-time error in Talend Studio. |
| **V1** | Silent filtering: `[col for col in key_columns if col in input_data.columns]`. If all filtered out, returns all rows as unique. No error raised. |
| **Verdict** | GAP -- should raise error, not silently return wrong results. |

### Edge Case 5: Case-insensitive with mixed-case duplicates

| Aspect | Detail |
|--------|--------|
| **Talend** | Per-column case sensitivity. "Alice" and "ALICE" match if CASE_SENSITIVE=false for that column. |
| **V1** | Global case_sensitive=False lowercases ALL string key columns. "Alice" and "ALICE" match. |
| **Verdict** | CORRECT for single-column case. WRONG for mixed per-column case sensitivity. |

### Edge Case 6: NaN values in key columns

| Aspect | Detail |
|--------|--------|
| **Talend** | null == null is true. Two rows with null in the same key column are duplicates. |
| **V1** | pandas `duplicated()` treats NaN == NaN as True by default. Same behavior. |
| **Verdict** | CORRECT |

### Edge Case 7: NaN in case-insensitive string column

| Aspect | Detail |
|--------|--------|
| **Talend** | null.toLowerCase() would be handled; null == null still true. |
| **V1** | `df[col].str.lower()` produces NaN for NaN values. NaN == NaN in `duplicated()`. Same effective behavior. |
| **Verdict** | CORRECT (but through different code path than case-sensitive mode) |

### Edge Case 8: BigDecimal key column with trailing zeros

| Aspect | Detail |
|--------|--------|
| **Talend** | With `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL=true`, `1.00` == `1.0`. Without it, they are different. |
| **V1** | No BigDecimal normalization. `Decimal("1.00") != Decimal("1.0")` in Python. |
| **Verdict** | GAP -- BigDecimal comparison semantics differ when CHANGE_HASH flag is set. |

### Edge Case 9: ONLY_ONCE_EACH_DUPLICATED_KEY with 3+ duplicates

| Aspect | Detail |
|--------|--------|
| **Talend** | First goes to UNIQUE, second goes to DUPLICATE, 3rd+ discarded. |
| **V1** | With `keep='last'` (converter mapping): LAST occurrence goes to unique, others to duplicate. Completely wrong. |
| **Verdict** | **CRITICAL GAP** -- produces wrong output on both UNIQUE and DUPLICATE flows. |

### Edge Case 10: DUPLICATE connection not drawn (no DUPLICATE output)

| Aspect | Detail |
|--------|--------|
| **Talend** | Only UNIQUE output exists. Duplicates are silently dropped. |
| **V1** | Engine always produces both `main` and `reject` outputs. If no downstream component reads `reject`, the data is simply unused. |
| **Verdict** | CORRECT (functionally equivalent) |

### Edge Case 11: Very large dataset exceeding memory

| Aspect | Detail |
|--------|--------|
| **Talend** | With IS_VIRTUAL_COMPONENT=true, spills to disk. Without it, may OOM. |
| **V1** | No disk spill. BaseComponent may auto-switch to streaming, but streaming drops duplicate output and cannot do cross-chunk deduplication. |
| **Verdict** | GAP -- no disk-based fallback, and streaming mode loses duplicate data. |

### Edge Case 12: Output order depends on XML connection order

| Aspect | Detail |
|--------|--------|
| **Talend** | Connectors are named (UNIQUE/DUPLICATE); order in XML is irrelevant. |
| **V1** | `outputs[0]` assumed to be UNIQUE, `outputs[1]` assumed to be DUPLICATE. If XML lists DUPLICATE connection first, the mapping is reversed. |
| **Verdict** | GAP -- brittle positional assumption instead of named matching. |

### Edge Case 13: Component used with tFlowToIterate

| Aspect | Detail |
|--------|--------|
| **Talend** | Can be used inside an iteration loop. Each iteration processes independently. |
| **V1** | Works, but INFO-level logging on each iteration produces excessive output. |
| **Verdict** | PARTIAL -- functionally correct but noisy. |

### Edge Case 14: All rows are unique (no duplicates)

| Aspect | Detail |
|--------|--------|
| **Talend** | All rows go to UNIQUE output. DUPLICATE output empty. NB_UNIQUES = total, NB_DUPLICATES = 0. |
| **V1** | `duplicated(keep='first')` marks no rows as duplicate. `unique_df` = all rows, `duplicate_df` = empty. |
| **Verdict** | CORRECT |

### Edge Case 15: All rows are duplicates (same key)

| Aspect | Detail |
|--------|--------|
| **Talend** | First row goes to UNIQUE. All other rows go to DUPLICATE. NB_UNIQUES = 1, NB_DUPLICATES = N-1. |
| **V1** | `duplicated(keep='first')` marks rows 2..N as duplicates. `unique_df` = [Row1], `duplicate_df` = [Row2..N]. |
| **Verdict** | CORRECT |

---

## Appendix I: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `UniqueRow`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-UNQ-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when `global_map` is set. Should be `stat_value`. |
| BUG-UNQ-008 | **P0** (P2 in this report) | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. Also, `get_component_stat()` passes two args to single-arg `get()`. |
| STD-UNQ-001 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called by any code path. ALL components with validation logic have dead validation. Should be a standard lifecycle step in `BaseComponent.execute()`. |

These should be tracked in a cross-cutting issues report as well, as fixing them benefits every component in the v1 engine.

---

## Appendix J: Implementation Fix Guides

### Fix Guide: CONV-UNQ-001 -- Missing `tUniqueRow` dispatch

**File**: `src/converters/complex_converter/converter.py`
**Line**: After line 243 (the `tUnqRow` dispatch)

**Current code (missing dispatch)**:
```python
elif component_type == 'tUniqRow':
    component = self.component_parser.parse_unique(node, component)
elif component_type == 'tUnqRow':
    component = self.component_parser.parse_unique(node, component)
elif component_type == 'tSortRow':
```

**Fixed code**:
```python
elif component_type == 'tUniqRow':
    component = self.component_parser.parse_unique(node, component)
elif component_type == 'tUniqueRow':
    component = self.component_parser.parse_unique(node, component)
elif component_type == 'tUnqRow':
    component = self.component_parser.parse_unique(node, component)
elif component_type == 'tSortRow':
```

**Risk**: Very low. Adds a new dispatch path for the alternative Talend component name.

### Fix Guide: ENG-UNQ-001 -- Add `unique`/`duplicate` flow type handling

**File**: `src/v1/engine/engine.py`
**Line**: After line 576 (the `filter` flow type handling)

**Add these two branches**:
```python
elif flow['type'] == 'unique' and 'main' in result and result['main'] is not None:
    self.data_flows[flow['name']] = result['main']
elif flow['type'] == 'duplicate' and 'reject' in result and result['reject'] is not None:
    self.data_flows[flow['name']] = result['reject']
```

**Risk**: Low. Extends existing routing logic without changing behavior for other flow types.

---

## Appendix K: File Locations

| File | Path | Role | Lines |
|------|------|------|-------|
| Engine Component | `src/v1/engine/components/aggregate/unique_row.py` | UniqueRow class -- core deduplication logic | 290 |
| Base Component | `src/v1/engine/base_component.py` | BaseComponent ABC -- execute(), stats, streaming | ~380 |
| Engine | `src/v1/engine/engine.py` | ETLEngine orchestrator -- flow routing, component registry, execution | ~800 |
| GlobalMap | `src/v1/engine/global_map.py` | GlobalMap storage -- put/get/stats | 87 |
| Exceptions | `src/v1/engine/exceptions.py` | Custom exception hierarchy -- ComponentExecutionError, ConfigurationError | 51 |
| Converter (dispatch) | `src/converters/complex_converter/converter.py` | `_parse_component()` -- component-specific dispatch | ~500 |
| Converter (parser) | `src/converters/complex_converter/component_parser.py` | `parse_unique()` at lines 798-858; `_map_component_parameters()` at lines 207-215; `parse_base_component()` at lines 388-509 | ~1000 |
| Aggregate __init__ | `src/v1/engine/components/aggregate/__init__.py` | Package exports -- UniqueRow, AggregateRow | 6 |
| Tests (v1 engine) | -- | **None exist** -- zero test files for UniqueRow v1 engine | 0 |
| Tests (converter) | -- | **None exist** -- zero test files for parse_unique() | 0 |

---

*Report generated: 2026-03-21*
*Auditor: Claude Opus 4.6 (1M context)*
*Files analyzed: 8 source files, 0 test files, Talend official documentation*
*Total issues: 46 (4 P0, 10 P1, 21 P2, 11 P3)*
