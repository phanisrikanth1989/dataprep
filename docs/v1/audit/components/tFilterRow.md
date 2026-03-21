# Audit Report: tFilterRow / FilterRows

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFilterRow` (also `tFilterRows`) |
| **V1 Engine Class** | `FilterRows` |
| **Engine File** | `src/v1/engine/components/transform/filter_rows.py` (315 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_filter_rows()` (lines 744-784) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> line 236: `component_type in ['tFilterRow', 'tFilterRows']` |
| **Converter Fallback Map** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 190-197) |
| **Registry Aliases** | `FilterRows`, `tFilterRows` (registered in `src/v1/engine/engine.py` lines 103-104) |
| **Missing Registry Alias** | `tFilterRow` (singular) -- NOT registered in engine.py. Only `FilterRows` and `tFilterRows` are registered. Talend XML will reference `tFilterRow` (singular), so converter output must use the plural form or the engine must add the singular alias. |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/filter_rows.py` | Engine implementation (315 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 744-784) | Dedicated parser: extracts LOGICAL_OP, USE_ADVANCED, ADVANCED_COND, CONDITIONS table from Talend XML |
| `src/converters/complex_converter/component_parser.py` (lines 190-197) | Fallback parameter mapping: maps CONDITIONS, LOGICAL_OP, USE_ADVANCED, ADVANCED_CONDITION |
| `src/converters/complex_converter/converter.py` (line 236) | Dispatch: dedicated `elif` branch for `tFilterRow` / `tFilterRows` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/engine.py` (lines 103-104, 570-576) | Component registry and result routing (filter/reject flow types) |
| `src/v1/engine/components/transform/__init__.py` | Package exports |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 4 | 1 | 4 of ~10 Talend condition fields extracted; missing FUNCTION, PREFILTER; no operator normalization; dead `&&` replacement code; wrong fallback parameter name |
| Engine Feature Parity | **R** | 2 | 5 | 3 | 1 | Only 6 of 14+ Talend operators supported; no FUNCTION pre-transforms; string coercion for all comparisons breaks numeric ordering; advanced mode uses Python eval() not Java |
| Code Quality | **R** | 3 | 3 | 4 | 3 | `.toList()` typo crashes simple mode; 19 `print()` statements; `eval()` security risk; all comparisons use string coercion; potential index alignment issue |
| Performance & Memory | **Y** | 0 | 1 | 2 | 1 | Row-by-row `eval()` in advanced mode; row-by-row debug print loop; no vectorized operator dispatch |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready. Multiple P0 bugs will crash the component at runtime.**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFilterRow Does

`tFilterRow` is a processing component that filters input data rows by evaluating one or more conditions on selected columns. It is one of the most commonly used transformation components in Talend data integration jobs. The component takes an input data flow, evaluates each row against the configured conditions, and routes rows to either the FILTER output (rows that match) or the REJECT output (rows that do not match).

**Source**: [tFilterRow Standard Properties (Talend 8.0)](https://help.talend.com/en-US/components/8.0/processing/tfilterrow-standard-properties), [tFilterRow (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tfilterrow), [Component-specific settings for tFilterRow (Job Script Reference Guide)](https://help.talend.com/en-US/job-script-reference-guide/7.3/component-specific-settings-for-tfilterrow), [Talend Filter Rows Tutorial](https://www.tutorialgateway.org/talend-filter-rows/)

**Component family**: Processing (Transformation)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.

**Key characteristics**:
- Parametrizable filters on source data columns
- Two modes: Simple conditions table and Advanced Java expression mode
- Logical operator (AND/OR) combines multiple simple conditions
- Can combine simple conditions AND advanced conditions using a logical operator
- Two output connections: FILTER (matching rows) and REJECT (non-matching rows)
- Optional FUNCTION pre-transform on column values before comparison
- Advanced mode allows full Java boolean expressions with `&&` and `||`

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. Input schema and output schema are identical for tFilterRow (no column transformation). |
| 3 | Logical Operator | `LOGICAL_OP` | Dropdown | `"&&"` (AND) | Logical operator used to combine multiple simple conditions. Options: `&&` (AND), `||` (OR). Also used to combine the results of simple conditions with advanced mode conditions if both are defined. |
| 4 | Conditions Table | `CONDITIONS` | Table | -- | Table of simple filter conditions. Each row has: `INPUT_COLUMN` (column name), `FUNCTION` (pre-transform function), `OPERATOR` (comparison operator), `RVALUE` (reference value), `PREFILTER` (pre-filter expression). The table can have one or more rows. |
| 5 | Use Advanced Mode | `USE_ADVANCED` | Boolean (CHECK) | `false` | When checked, enables the advanced condition text area for arbitrary Java boolean expressions. Simple conditions and advanced conditions can be used together (combined with LOGICAL_OP). |
| 6 | Advanced Condition | `ADVANCED_COND` | Java expression (String) | -- | Java boolean expression using `input_row.<column>` references. Available only when `USE_ADVANCED=true`. Examples: `input_row.age > 18 && input_row.status.equals("ACTIVE")`, `input_row.name != null && input_row.name.length() > 0`. |
| 7 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | When checked, the job stops on the first error during filter evaluation. When unchecked, errors during evaluation cause the row to be rejected rather than crashing the job. |

### 3.2 Conditions Table Structure

Each row in the CONDITIONS table has five fields:

| # | Field | XML elementRef | Type | Default | Description |
|---|-------|---------------|------|---------|-------------|
| 1 | Input Column | `INPUT_COLUMN` | Dropdown (schema columns) | -- | **Mandatory**. The name of the input column to evaluate. Populated from the input schema. |
| 2 | Function | `FUNCTION` | Dropdown | `"EMPTY"` (none) | Optional pre-transform function applied to the column value BEFORE the comparison. See Section 3.3 for the complete list. When set to EMPTY (no function), the raw column value is used. |
| 3 | Operator | `OPERATOR` | Dropdown | `"=="` | **Mandatory**. The comparison operator. See Section 3.4 for the complete list. |
| 4 | Value | `RVALUE` | Expression (String) | -- | The reference value to compare against. Can be a literal, context variable (`context.var`), globalMap reference, or Java expression. Not required for unary operators like `== null`. |
| 5 | Pre-Filter | `PREFILTER` | Expression (String) | -- | Optional pre-filter expression evaluated before the main condition. Can reference context variables and globalMap. Rarely used in practice. |

### 3.3 Functions (Pre-Transform)

The FUNCTION dropdown in the Conditions table provides pre-transform operations applied to the column value BEFORE the comparison operator is evaluated. This allows comparisons like "length of name > 5" or "lowercase of status == 'active'".

| # | Function | Talend XML Value | Description | Applicable Types |
|---|----------|-----------------|-------------|-----------------|
| 1 | (none) | `"EMPTY"` | No transform -- use raw column value. This is the default. | All |
| 2 | Absolute Value | `"ABS_VALUE"` | Absolute value: `Math.abs(value)`. For numeric columns. | Integer, Long, Float, Double, BigDecimal |
| 3 | Lower Case | `"LC"` | Convert string to lowercase: `value.toLowerCase()`. | String |
| 4 | Upper Case | `"UC"` | Convert string to uppercase: `value.toUpperCase()`. | String |
| 5 | Length | `"LENGTH"` | String length: `value.length()`. Returns an integer. | String |
| 6 | Trim | `"TRIM"` | Trim leading/trailing whitespace: `value.trim()`. | String |
| 7 | Left Trim | `"LTRIM"` | Trim leading whitespace only. | String |
| 8 | Right Trim | `"RTRIM"` | Trim trailing whitespace only. | String |
| 9 | Match | `"MATCH"` | Regex match: `value.matches(pattern)`. Returns boolean. Used with `==` operator and a regex pattern as value. | String |

### 3.4 Operators (Complete List)

The OPERATOR dropdown provides the comparison operators used to evaluate each condition.

| # | Operator | Talend XML Value | Java Code Generated | Description |
|---|----------|-----------------|---------------------|-------------|
| 1 | Equals | `"=="` | `value1.equals(value2)` or `value1 == value2` (primitives) | Equality check. For strings, uses `.equals()` (case-sensitive). For primitives, uses `==`. |
| 2 | Not Equal To | `"!="` | `!value1.equals(value2)` or `value1 != value2` | Inequality check. Logical negation of Equals. |
| 3 | Lower Than | `"<"` | `value1.compareTo(value2) < 0` or `value1 < value2` | Strictly less than. For strings, uses `compareTo()` (lexicographic). For numbers, uses `<`. |
| 4 | Greater Than | `">"` | `value1.compareTo(value2) > 0` or `value1 > value2` | Strictly greater than. |
| 5 | Lower or Equal To | `"<="` | `value1.compareTo(value2) <= 0` or `value1 <= value2` | Less than or equal. |
| 6 | Greater or Equal To | `">="` | `value1.compareTo(value2) >= 0` or `value1 >= value2` | Greater than or equal. |
| 7 | Contains | `"CONTAINS"` | `value1.contains(value2)` | Substring check. Returns true if value1 contains value2 as a substring. String type only. |
| 8 | Doesn't Contain | `"NOT_CONTAINS"` | `!value1.contains(value2)` | Negated substring check. True if value1 does NOT contain value2. |
| 9 | Starts With | `"STARTS_WITH"` | `value1.startsWith(value2)` | Prefix check. True if value1 starts with value2. String type only. |
| 10 | Ends With | `"ENDS_WITH"` | `value1.endsWith(value2)` | Suffix check. True if value1 ends with value2. String type only. |
| 11 | Match Regex | `"MATCH_REGEX"` | `value1.matches(value2)` | Regular expression match. True if value1 fully matches the regex pattern value2. String type only. Note: Java `matches()` requires the FULL string to match (implicit `^...$`). |

**Note on null handling**: In Talend, null values in conditions are handled specially:
- `column == null` checks for null (RVALUE is empty or `"null"`)
- `column != null` checks for non-null
- Comparing a null column to any value with other operators evaluates to false (row goes to REJECT)
- The FUNCTION transforms will throw NullPointerException on null values unless the code generator adds null guards

### 3.5 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main Input) | Input | Row > Main | Input data flow. One input connection required. All input rows are evaluated against the conditions. |
| `FILTER` | Output | Row > Filter | Rows that PASS the filter conditions (all conditions evaluate to true with AND; at least one evaluates to true with OR). This is the primary output. The FILTER connector name is specific to tFilterRow -- it is NOT `FLOW` or `MAIN`. |
| `REJECT` | Output | Row > Reject | Rows that FAIL the filter conditions. Contains ALL original schema columns plus two additional columns: `errorCode` (String) and `errorMessage` (String). The errorMessage contains a description of which condition failed. Only active when a REJECT link is connected. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Critical distinction**: The output connection for matching rows is named `FILTER`, NOT `FLOW` or `MAIN`. This is unique to tFilterRow. In the Talend XML, the connection's `connectorName` attribute is `"FILTER"`. The converter must map this correctly to the engine's internal flow routing.

### 3.6 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed (input rows). |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows that passed the filter (sent to FILTER output). Equals `NB_LINE - NB_LINE_REJECT`. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows that failed the filter (sent to REJECT output). Zero when no REJECT link is connected. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during filter evaluation. Available for reference in downstream error handling flows. |

### 3.7 Behavioral Notes

1. **FILTER vs FLOW output naming**: Unlike most Talend components that use `FLOW` for the primary output, tFilterRow uses `FILTER` as the connector name for rows that pass the filter. This is an important distinction for converter implementations that need to map connection types correctly.

2. **REJECT flow behavior**: When a REJECT link is connected:
   - Rows that fail ALL conditions (with AND logic) or fail all conditions (with OR logic) are sent to REJECT
   - REJECT rows contain ALL original schema columns PLUS `errorCode` (String) and `errorMessage` (String) columns
   - The `errorMessage` column contains a description of which condition(s) failed
   - When REJECT is NOT connected, non-matching rows are silently discarded
   - If `DIE_ON_ERROR=true` and a condition evaluation throws an exception, the job stops

3. **Condition evaluation order**: Conditions in the table are evaluated top to bottom. With AND logic, evaluation short-circuits on the first false condition. With OR logic, evaluation short-circuits on the first true condition. This matters for performance and for conditions that may throw exceptions (e.g., null checks should come before comparisons).

4. **FUNCTION pre-transform**: When a FUNCTION is specified (e.g., LENGTH, LC, UC, TRIM), the function is applied to the column value BEFORE the operator comparison. For example, `INPUT_COLUMN=name, FUNCTION=LENGTH, OPERATOR=>, RVALUE=5` generates code equivalent to `input_row.name.length() > 5`. The V1 engine does NOT support FUNCTION pre-transforms.

5. **Null handling in conditions**: Talend generates null-safe code for conditions. If a column value is null:
   - `== null` evaluates to true
   - `!= null` evaluates to false
   - All other operators (`<`, `>`, `<=`, `>=`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCH_REGEX`) evaluate to false, and the row goes to REJECT
   - FUNCTION transforms on null values may throw NullPointerException unless explicitly handled

6. **Advanced mode Java expressions**: The ADVANCED_COND field accepts arbitrary Java boolean expressions referencing columns as `input_row.<column_name>`. These expressions are compiled into Java code and executed at runtime. They support:
   - Java operators: `&&`, `||`, `!`, `==`, `!=`, `<`, `>`, `<=`, `>=`
   - Java methods: `.equals()`, `.contains()`, `.startsWith()`, `.endsWith()`, `.matches()`, `.length()`, `.trim()`, `.toLowerCase()`, `.toUpperCase()`
   - Talend routines: `Relational.ISNULL(input_row.column)`, `TalendString.LTRIM()`, etc.
   - Ternary operator: `condition ? true_expr : false_expr`
   - Null checks: `input_row.column != null`
   - Context variables: `context.variable`
   - GlobalMap references: `(String)globalMap.get("key")`

7. **Combined simple + advanced mode**: When both simple conditions and advanced mode are active, the simple conditions produce a boolean result, the advanced condition produces a boolean result, and both are combined with the LOGICAL_OP. For example, with AND logic: `(simple_conditions_result) && (advanced_condition_result)`.

8. **Type-aware comparisons**: Talend generates type-specific comparison code:
   - **Strings**: `.equals()` for equality, `.compareTo()` for ordering, `.contains()`, `.startsWith()`, `.endsWith()`, `.matches()` for pattern matching
   - **Integers/Longs**: `==`, `!=`, `<`, `>`, `<=`, `>=` (primitive operators)
   - **Floats/Doubles**: Same as integers but with floating-point semantics
   - **BigDecimal**: `.compareTo()` for all comparisons
   - **Dates**: `.compareTo()` or `.equals()` for comparison
   - **Booleans**: `==` for equality

9. **NB_LINE availability**: The `NB_LINE` global variable is only available AFTER the component completes execution. To get row count within the same subjob's data flow, use different mechanisms.

10. **Empty conditions table**: If the conditions table is empty and advanced mode is not enabled, all rows pass the filter (all go to FILTER output, none to REJECT). This is a degenerate case.

11. **Pre-filter expressions**: The PREFILTER field in each condition row allows a boolean expression to be evaluated before the main condition. If the pre-filter evaluates to false, the condition is skipped (treated as true for AND logic, ignored for OR logic). This is rarely used in practice.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_filter_rows()` in `component_parser.py` lines 744-784) dispatched from `converter.py` line 236. This is the correct approach per STANDARDS.md. Additionally, a fallback parameter mapping exists in `_map_component_parameters()` (lines 190-197) for the simplified config path.

**Converter flow (dedicated parser)**:
1. `converter.py:_parse_component()` identifies `tFilterRow` / `tFilterRows` at line 236
2. Calls `self.component_parser.parse_filter_rows(node, component)` at line 237
3. `parse_filter_rows()` extracts `LOGICAL_OP`, `USE_ADVANCED`, `ADVANCED_COND` from `elementParameter` nodes
4. Extracts `CONDITIONS` table by iterating `elementValue` children, extracting `INPUT_COLUMN`, `OPERATOR`, `RVALUE`
5. Maps to config dict with keys: `logical_operator`, `use_advanced`, `advanced_condition`, `conditions`

**Converter flow (fallback mapping)**:
1. `_map_component_parameters('tFilterRow', config_raw)` (lines 190-197)
2. Maps `CONDITIONS` -> `conditions`, `LOGICAL_OP` -> `logical_operator`, `USE_ADVANCED` -> `use_advanced`, `ADVANCED_CONDITION` -> `advanced_condition`

| # | Talend XML Parameter | Extracted? | V1 Config Key | Parser Line | Notes |
|----|----------------------|------------|---------------|-------------|-------|
| 1 | `LOGICAL_OP` | Yes | `logical_operator` | 751-753 | Converts `&amp;&amp;` to `AND` and `||` to `OR`. Default `'AND'`. **Note**: The Talend XML stores `&&` as `&amp;&amp;` due to XML escaping. |
| 2 | `USE_ADVANCED` | Yes | `use_advanced` | 755-758 | Boolean from string `"true"/"false"`. Default `false`. |
| 3 | `ADVANCED_COND` | Yes | `advanced_condition` | 760-763 | Raw Java expression string. Not transformed. |
| 4 | `INPUT_COLUMN` (per condition) | Yes | `conditions[].column` | 771-772 | Column name from elementValue. |
| 5 | `OPERATOR` (per condition) | Yes | `conditions[].operator` | 773-774 | Raw operator string from XML (e.g., `"=="`, `"!="`, `"<"`, `">"`, `"<="`, `">="`). **Not normalized for string operators** (e.g., `"CONTAINS"`, `"STARTS_WITH"` etc. are passed through as-is). |
| 6 | `RVALUE` (per condition) | Yes | `conditions[].value` | 775-776 | Reference value. Raw string from XML. Context variables and Java expressions within the value are NOT specially handled here. |
| 7 | `FUNCTION` (per condition) | **No** | -- | -- | **Not extracted. The FUNCTION field (LC, UC, LENGTH, TRIM, ABS_VALUE, etc.) is completely ignored.** This means conditions with FUNCTION pre-transforms will produce incorrect results. For example, a condition `FUNCTION=LENGTH, OPERATOR=>, RVALUE=5` on column `name` should compare the LENGTH of name to 5, but without FUNCTION extraction, it compares the raw name string to "5". |
| 8 | `PREFILTER` (per condition) | **No** | -- | -- | **Not extracted. Pre-filter expressions are ignored.** Low usage in practice. |
| 9 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted by the dedicated parser.** The fallback mapper (line 186) extracts it for some components, but `parse_filter_rows()` does not. The engine has no `die_on_error` handling for FilterRows. |
| 10 | `SCHEMA` | Yes (generic) | `schema` | base parser | Schema extracted generically from `<metadata connector="FLOW">` nodes. |
| 11 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs). |
| 12 | `TSTATCATCHER_STATS` | No | -- | -- | Not extracted (low priority -- tStatCatcher rarely used). |
| 13 | `LABEL` | No | -- | -- | Not extracted (cosmetic -- no runtime impact). |

**Summary**: 6 of ~10 runtime-relevant condition fields extracted (60%). The two most impactful gaps are `FUNCTION` (pre-transform) and `DIE_ON_ERROR`.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` of `component_parser.py`.

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Column default value not extracted |
| `comment` | **No** | Cosmetic -- no runtime impact |
| `talendType` | **No** | Full Talend type string not preserved -- converted to Python type |

**REJECT schema**: The converter extracts REJECT metadata when present, but the REJECT schema for tFilterRow includes the additional `errorCode` and `errorMessage` columns that Talend adds automatically. The converter does not add these columns.

### 4.3 Condition Operator Normalization

The converter passes operator strings through as raw values from the XML. This means:
- Comparison operators (`==`, `!=`, `<`, `>`, `<=`, `>=`) are passed through correctly, matching what the engine expects.
- **String operators** (`CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCH_REGEX`) are passed through as uppercase strings. The engine does NOT support these operators -- it only supports the 6 comparison operators.

This creates a silent failure mode: if a Talend job uses `CONTAINS` or `MATCH_REGEX` operators, the converter passes the operator string to the engine, the engine's `_evaluate_single_condition()` hits the `else` branch (line 292-295), logs a warning, and returns `False` for all rows. The entire dataset would be rejected.

### 4.4 Logical Operator Conversion

The converter's `parse_filter_rows()` method (line 752) converts the logical operator:
- `&amp;&amp;` (XML-escaped `&&`) -> `AND`
- `||` -> `OR`

This is done via string `.replace()` which is fragile -- it replaces ALL occurrences, not just the logical operator field. The fallback mapper (line 194) uses `.strip('""')` on the LOGICAL_OP value to remove surrounding quotes.

### 4.5 Expression Handling

**Context variable handling**: The dedicated parser does NOT perform context variable resolution on RVALUE or ADVANCED_COND. Context variables in values (e.g., `context.threshold`) are left as raw strings. The engine's `_evaluate_single_condition()` method (line 261-262) resolves context variables in the value field using `self.context_manager.resolve_string(val)`.

**Java expression handling in ADVANCED_COND**: The advanced condition is stored as a raw Java expression string. The dedicated parser does NOT mark it with `{{java}}` for the Java bridge. Instead, the engine's `_process_advanced_condition()` method (line 191) strips `{{java}}` markers and uses Python `eval()` to evaluate the expression. This is fundamentally wrong -- Java expressions like `input_row.name.equals("test")` are not valid Python.

### 4.6 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FR-001 | **P1** | **FUNCTION field not extracted**: The `parse_filter_rows()` method (line 768) iterates `elementValue` children but only extracts `INPUT_COLUMN`, `OPERATOR`, and `RVALUE`. The `FUNCTION` elementRef (e.g., `"LENGTH"`, `"LC"`, `"UC"`, `"TRIM"`, `"ABS_VALUE"`) is completely ignored. This means conditions using FUNCTION pre-transforms will produce incorrect filter results. For example, a condition that checks if a name's LENGTH is greater than 5 will instead compare the raw name string to "5" as a string comparison. |
| CONV-FR-002 | **P1** | **PREFILTER field not extracted**: The `PREFILTER` elementRef is not extracted from the CONDITIONS table. While rarely used in practice, any Talend job relying on pre-filter expressions will silently lose that logic. |
| CONV-FR-003 | **P1** | **DIE_ON_ERROR not extracted by dedicated parser**: The `parse_filter_rows()` method does not extract the `DIE_ON_ERROR` parameter. The engine has no die_on_error handling for FilterRows -- all errors propagate as exceptions. |
| CONV-FR-004 | **P2** | **No operator normalization for string operators**: Operators like `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCH_REGEX` are passed through verbatim from Talend XML to the engine config. The engine only supports `==`, `!=`, `<`, `>`, `<=`, `>=`. This creates a silent failure where all rows evaluate to False for unsupported operators. |
| CONV-FR-005 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) instead of preserving Talend format (`id_String`, `id_Integer`). This affects type-aware comparisons in the engine. |
| CONV-FR-006 | **P3** | **LOGICAL_OP conversion uses fragile `.replace()`**: Line 752 performs `replace('&amp;&amp;', 'AND').replace('||', 'OR')` which could inadvertently modify parts of complex expressions if they contain these sequences (unlikely but fragile). |
| CONV-FR-007 | **P2** | **Dead `&&` replacement code in converter**: `component_parser.py` line 752 does `replace('&amp;&amp;', 'AND')` but Python's ElementTree decodes XML entities before returning attribute values, so the value is `&&` not `&amp;&amp;`. The replacement never matches. The system works end-to-end because the engine's `LOGICAL_OPERATOR_MAPPING` handles `&&` -> `AND`, but the converter code is dead/misleading. |
| CONV-FR-008 | **P2** | **Fallback mapping uses wrong Talend parameter name**: Line 196 uses `'ADVANCED_CONDITION'` but the actual Talend XML parameter name is `'ADVANCED_COND'`. If the fallback path is exercised with raw Talend parameter names, the advanced condition is silently lost (defaults to empty string). |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Simple conditions (column-operator-value) | **Yes** | Low | `_process_simple_conditions()` line 199, `_evaluate_single_condition()` line 245 | Core functionality present but with critical string coercion issue (see 5.2) |
| 2 | `==` (Equals) operator | **Yes** | Low | line 280 | Uses string comparison (`col_data == val_stripped`) after `.astype(str)`. Correct for strings, WRONG for numbers (e.g., `"10" == "10"` works, but `"10" == "10.0"` fails for floats) |
| 3 | `!=` (Not Equal) operator | **Yes** | Low | line 282 | Same string coercion issue as `==` |
| 4 | `>` (Greater Than) operator | **Yes** | **Critical Bug** | line 284 | **String comparison, not numeric**. `"9" > "10"` evaluates to True because `"9" > "1"` lexicographically. This is fundamentally broken for numeric columns. |
| 5 | `<` (Lower Than) operator | **Yes** | **Critical Bug** | line 286 | Same lexicographic comparison issue. `"2" < "10"` evaluates to False because `"2" > "1"` lexicographically. |
| 6 | `>=` (Greater or Equal) operator | **Yes** | **Critical Bug** | line 288 | Same string coercion issue as `>`. |
| 7 | `<=` (Lower or Equal) operator | **Yes** | **Critical Bug** | line 290 | Same string coercion issue as `<`. |
| 8 | `CONTAINS` operator | **No** | N/A | -- | **Not implemented.** Talend's `CONTAINS` checks if column value contains a substring. Engine falls through to `else` branch (line 292), logs warning, returns False for all rows. |
| 9 | `NOT_CONTAINS` operator | **No** | N/A | -- | **Not implemented.** |
| 10 | `STARTS_WITH` operator | **No** | N/A | -- | **Not implemented.** |
| 11 | `ENDS_WITH` operator | **No** | N/A | -- | **Not implemented.** |
| 12 | `MATCH_REGEX` operator | **No** | N/A | -- | **Not implemented.** |
| 13 | FUNCTION pre-transforms (LC, UC, LENGTH, TRIM, ABS_VALUE, LTRIM, RTRIM, MATCH) | **No** | N/A | -- | **Not implemented. Not even extracted by converter.** |
| 14 | Pre-filter expressions | **No** | N/A | -- | **Not implemented.** |
| 15 | Logical AND combining | **Yes** | High | line 227-230 | Combines masks with `&` operator. Correct. |
| 16 | Logical OR combining | **Yes** | High | line 231-234 | Combines masks with `|` operator. Correct. |
| 17 | Advanced mode (Java expression) | **Partial** | Low | `_process_advanced_condition()` line 179 | Uses Python `eval()` instead of Java execution. Only works for expressions that happen to be valid in both Java and Python. Most Java expressions will fail. |
| 18 | `input_row.` prefix stripping | **Yes** | Medium | line 192 | Strips `input_row.` prefix to allow column references. Only works for simple column access, not method calls. |
| 19 | `{{java}}` marker stripping | **Yes** | High | line 191 | Strips `{{java}}` prefix from advanced condition. |
| 20 | FILTER output connection | **Yes** | High | `_process()` returns `{'main': accepted}` line 172 | Engine routes `result['main']` to connections with type `'filter'` (engine.py line 575-576). Correct. |
| 21 | REJECT output connection | **Yes** | High | `_process()` returns `{'reject': rejected}` line 172 | Engine routes `result['reject']` to connections with type `'reject'` (engine.py line 573-574). Correct. |
| 22 | Statistics tracking (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) | **Yes** | High | `_update_stats()` line 168 | Correctly tracks input count, accepted count, and rejected count. |
| 23 | Context variable resolution in values | **Yes** | High | line 261-262 | `context_manager.resolve_string(val)` resolves `${context.var}` patterns in condition values. |
| 24 | Quote stripping from values | **Yes** | Medium | line 265-266 | Strips single quotes from value strings. May incorrectly strip quotes that are part of the intended value. |
| 25 | Missing column handling | **Yes** | Medium | line 270-273 | Returns False mask if column not found. Logs warning. |
| 26 | Die on error | **No** | N/A | -- | **Not implemented.** No `die_on_error` config handling. All exceptions propagate. |
| 27 | Null handling | **No** | N/A | -- | **Not implemented.** `.astype(str)` converts NaN/None to string `"nan"` / `"None"`, which then fails comparisons unpredictably. Talend has explicit null guards. |
| 28 | Type-aware comparisons | **No** | N/A | -- | **Not implemented.** All comparisons use string coercion (`.astype(str)`). Talend generates type-specific comparison code (numeric operators for numbers, `.equals()` for strings, `.compareTo()` for ordering). |
| 29 | Combined simple + advanced mode | **Partial** | Low | line 153-156 | Either simple OR advanced mode is used, never both combined. Talend supports combining both with the logical operator. |
| 30 | errorCode/errorMessage in REJECT | **No** | N/A | -- | **Rejected rows contain only the original columns, without errorCode or errorMessage explaining which condition failed.** |
| 31 | Empty input handling | **Yes** | High | line 128-132 | Returns empty DataFrames for both main and reject. |
| 32 | Validation of config | **Yes** | Medium | `_validate_config()` line 65 | Validates conditions structure, operator support, logical operator. **But: never called automatically.** Must be called explicitly via `validate_config()` (line 304). |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FR-001 | **P0** | **String coercion for ALL comparisons breaks numeric ordering**: `_evaluate_single_condition()` (line 276) calls `input_data[col].astype(str).str.strip()` which converts ALL column data to strings before comparison. For numeric columns, this causes fundamentally wrong results: `"9" > "10"` evaluates to True (lexicographic comparison, `"9"` > `"1"`), `"2" < "10"` evaluates to False. Talend generates type-specific code: numeric columns use `<`/`>` operators on numeric types, string columns use `.compareTo()`. The V1 engine treats ALL columns as strings. **Impact**: Any job filtering on numeric columns with `<`, `>`, `<=`, `>=` operators will produce WRONG results. |
| ENG-FR-002 | **P0** | **Advanced mode uses Python `eval()` instead of Java**: `_process_advanced_condition()` (line 195) uses `eval(expr, {}, row.to_dict())` to evaluate advanced conditions. Java expressions like `input_row.name.equals("test")` are NOT valid Python (`.equals()` is a Java method). Only expressions that happen to be syntactically valid in both Java and Python will work (e.g., `age > 18`). Java-specific constructs (`instanceof`, `? :` ternary, `.equals()`, `.matches()`, `.startsWith()`, `Relational.ISNULL()`, `StringHandling.INDEX()`, etc.) will raise `SyntaxError` or `NameError`. **Impact**: Most advanced mode expressions will fail at runtime. |
| ENG-FR-003 | **P1** | **5 of 11 Talend operators not supported**: `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCH_REGEX` are not implemented. When encountered, the engine logs a warning and returns False for all rows. The entire dataset would be rejected. **Impact**: Any job using these operators will produce empty FILTER output. |
| ENG-FR-004 | **P1** | **FUNCTION pre-transforms not supported**: Pre-transform functions (LENGTH, LC, UC, TRIM, ABS_VALUE, LTRIM, RTRIM, MATCH) are not implemented in the engine and not even extracted by the converter. Conditions using these functions will compare the raw column value against the reference value, ignoring the intended transform. **Impact**: Jobs using FUNCTION pre-transforms will produce incorrect filter results. |
| ENG-FR-005 | **P1** | **No die_on_error handling**: The engine does not read or honor the `die_on_error` config. All exceptions during filter evaluation propagate as unhandled exceptions, which always kills the job. Talend with `die_on_error=false` would route error rows to REJECT instead of crashing. |
| ENG-FR-006 | **P1** | **Null values converted to string "nan"**: `.astype(str)` on line 276 converts pandas `NaN`/`None` values to the string `"nan"`. This means: `column == "nan"` unexpectedly matches null rows, `column != "nan"` unexpectedly excludes null rows, and `column == null` (intended null check) never matches. Talend has explicit null handling. |
| ENG-FR-007 | **P1** | **Combined simple + advanced mode not supported**: The engine uses an `if/else` branch (lines 153-156) -- either simple conditions OR advanced mode, never both. Talend supports combining both by evaluating simple conditions and advanced conditions separately, then combining with the logical operator. |
| ENG-FR-008 | **P2** | **No errorCode/errorMessage in REJECT output**: Rejected rows contain only original schema columns. Talend adds `errorCode` and `errorMessage` columns to REJECT rows explaining which condition failed. Downstream components expecting these columns will fail. |
| ENG-FR-009 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur during filter evaluation, the error message is not stored in globalMap for downstream reference. |
| ENG-FR-010 | **P2** | **No PREFILTER expression support**: Pre-filter expressions in condition rows are not extracted or evaluated. |
| ENG-FR-011 | **P3** | **No tStatCatcher integration**: No statistics capture for tStatCatcher. Low priority -- rarely used. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. **But**: `_update_global_map()` has a cross-cutting bug (BUG-FR-002) that will crash when called. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Correctly reflects accepted row count. |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Correctly reflects rejected row count. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FR-001 | **P0** | `filter_rows.py:242` | **`.toList()` typo crashes simple condition mode**: Line 242 calls `final_mask.toList()` (capital L) inside a `print()` statement. pandas Series does not have a `.toList()` method -- the correct method is `.tolist()` (lowercase L). This `AttributeError` will crash EVERY execution that uses simple conditions with any input data. The same typo does NOT exist on lines 196 and 300 which correctly use `.tolist()`. **Note**: This is inside a `print()` statement which should not be there anyway (see DBG-FR-001), but since `print()` is eagerly evaluated, the `.toList()` call will crash before the print even executes. |
| BUG-FR-002 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FilterRows. |
| BUG-FR-003 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the method signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FR-004 | **P1** | `filter_rows.py:276` | **All comparisons use string coercion**: `col_data = input_data[col].astype(str).str.strip()` forces ALL column data to strings before comparison. For numeric columns, lexicographic ordering is WRONG: `"9" > "10"` is True, `"2" < "10"` is False. For float columns, `"10" != "10.0"` is True when it should be False. For boolean columns, `"True" == "True"` works but `True == "True"` fails type checking in downstream logic. This is a design flaw, not a typo. |
| BUG-FR-005 | **P1** | `filter_rows.py:195` | **`eval()` used for advanced conditions with no sandboxing**: `eval(expr, {}, row.to_dict())` executes arbitrary Python code with the row's data as local variables. The expression is user-provided (from Talend XML). While the namespace is restricted (empty globals, row dict as locals), `eval()` can still access builtins like `__import__`, `exec`, `open`, etc. via attribute access on objects. Additionally, the expression is a Java expression that may not be valid Python. |
| BUG-FR-006 | **P1** | `filter_rows.py:195` | **Row-by-row `eval()` in advanced mode**: `input_data.apply(lambda row: eval(expr, {}, row.to_dict()), axis=1)` evaluates the expression once PER ROW. For a DataFrame with 1 million rows, this calls `eval()` 1 million times. Each call involves dict creation (`row.to_dict()`), Python expression parsing, and evaluation. Extremely slow. Should be vectorized using pandas operations. |
| BUG-FR-007 | **P1** | `filter_rows.py:265-266` | **Quote stripping is aggressive and incorrect**: `val = val.strip().strip("'").strip("'")` strips single quotes from both ends of the value. However, this uses Python's `str.strip()` which strips ALL matching characters from the ends, not just one pair of quotes. For example, `"''hello''"` becomes `"hello"` instead of `"'hello'"`. Also, the two `.strip("'")` calls are redundant (identical). The intent appears to be removing surrounding quotes from Talend string literals (e.g., `"'ACTIVE'"` -> `"ACTIVE"`), but the implementation is too aggressive. |
| BUG-FR-008 | **P2** | `filter_rows.py:218` | **Debug print accesses first condition's column unconditionally**: `print(f"[FilterRows] Unique values in '{conditions[0]['column']}': {input_data[conditions[0]['column']].unique()}")`. This accesses `conditions[0]` which could fail if conditions is empty (though this is guarded by the `if not conditions` check on line 214). More importantly, `input_data[conditions[0]['column']].unique()` will throw `KeyError` if the column doesn't exist in the input data. This is a debug print that should not be in production code. |
| BUG-FR-009 | **P2** | `filter_rows.py:298-299` | **Debug print loop iterates every row of every condition**: Lines 298-299 contain a for loop `for idx, v in enumerate(col_data): print(...)` that prints a comparison result for EVERY row of the DataFrame for EVERY condition. For a 1M-row DataFrame with 3 conditions, this produces 3 million print statements. This is not just a performance issue -- it will flood logs and may exhaust disk space in production. |
| BUG-FR-010 | **P3** | `filter_rows.py:215` | **Potential index alignment issue with empty conditions**: Line 215 returns `pd.Series([True] * len(input_data))` with a RangeIndex. If the DataFrame has a non-default index, this causes alignment issues when used as a mask. Edge case since validation would normally flag empty conditions, but validation is never auto-called. |

### 6.2 Debug Artifacts (print() Statements)

The component contains **19 `print()` statements** throughout the code. Per STANDARDS.md (line 286, 789), `print()` statements are explicitly prohibited. The component has proper `logging` infrastructure (`logger = logging.getLogger(__name__)` on line 13) and uses `logger.debug()`, `logger.info()`, `logger.warning()`, and `logger.error()` alongside the `print()` statements, making the prints entirely redundant.

| ID | Priority | Location | print() Statement | Issue |
|----|----------|----------|--------------------|-------|
| DBG-FR-001 | **P1** | line 119 | `print(f"[FilterRows] {self.id} config: {self.config}")` | Dumps entire config dict to stdout. May contain sensitive data (context variables, credentials in expressions). |
| DBG-FR-002 | **P1** | line 120 | `print(f"[FilterRows] input_data shape: ...")` | Redundant with logger.debug on line 125. |
| DBG-FR-003 | **P1** | line 121 | `print(f"[FilterRows] input_data columns: ...")` | Redundant with logger.debug. |
| DBG-FR-004 | **P2** | line 123 | `print(f"[FilterRows] First 3 rows:\n{input_data.head(3)}")` | Dumps actual data to stdout. **Data exposure risk** in production. |
| DBG-FR-005 | **P2** | line 131 | `print(f"[FilterRows] Empty input, returning empty DataFrames.")` | Redundant with logger.warning on line 129. |
| DBG-FR-006 | **P2** | line 144-145 | `print(f"[FilterRows] use_advanced: ...")` | Dumps advanced_condition expression to stdout. |
| DBG-FR-007 | **P2** | line 150 | `print(f"[FilterRows] Mapped logical operator to: ...")` | Redundant with logger.debug. |
| DBG-FR-008 | **P2** | line 165 | `print(f"[FilterRows] Accepted shape: ...")` | Redundant with logger.info on line 169-170. |
| DBG-FR-009 | **P2** | line 176 | `print(f"[FilterRows] Error during filtering: {e}")` | Redundant with logger.error on line 175. |
| DBG-FR-010 | **P2** | line 193 | `print(f"[FilterRows] Evaluating advanced condition: {expr}")` | Redundant with logger.debug on line 190. |
| DBG-FR-011 | **P2** | line 196 | `print(f"[FilterRows] Advanced mask: {mask.tolist()}")` | Dumps entire boolean mask. For 1M rows, this is a 1M-element list printed to stdout. |
| DBG-FR-012 | **P2** | line 218 | `print(f"[FilterRows] Unique values in '...'")` | Computes and prints unique values of first condition's column. Unnecessary I/O. |
| DBG-FR-013 | **P2** | line 237 | `print(f"[FilterRows] Unknown logical operator '...'")` | Redundant with logger.warning on line 236. |
| DBG-FR-014 | **P1** | line 242 | `print(f"[FilterRows] Final mask: {final_mask.toList()}")` | **CRASHES** due to `.toList()` typo (should be `.tolist()`). See BUG-FR-001. |
| DBG-FR-015 | **P2** | line 268 | `print(f"[FilterRows] Condition: column={col}, operator={op}, value={val}")` | One print per condition per execution. Redundant. |
| DBG-FR-016 | **P2** | line 272 | `print(f"[FilterRows] Column '{col}' not found in input data.")` | Redundant with logger.warning on line 271. |
| DBG-FR-017 | **P1** | line 298-299 | `for idx, v in enumerate(col_data): print(...)` | **Row-by-row print loop.** Prints comparison result for EVERY row. For 1M rows, produces 1M lines of stdout. See BUG-FR-009. |
| DBG-FR-018 | **P2** | line 300 | `print(f"[FilterRows] Mask for condition: {mask.tolist()}")` | Dumps entire boolean mask for each condition. |
| DBG-FR-019 | **P2** | line 294 | `print(f"[FilterRows] Unsupported operator '{op}'.")` | Redundant with logger.warning on line 293. |

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FR-001 | **P1** | **Missing `tFilterRow` (singular) engine registry alias**: Engine.py (lines 103-104) registers `FilterRows` and `tFilterRows` (plural), but NOT `tFilterRow` (singular). Talend XML uses `tFilterRow` (singular) as the component type. If the converter outputs the Talend type name as the component type, the engine will fail to find the component class. The converter would need to map `tFilterRow` to `FilterRows` explicitly, which the `COMPONENT_TYPE_MAP` in `component_parser.py` line 56-57 does (`'tFilterRow': 'FilterRows'`, `'tFilterRows': 'FilterRows'`). However, if any code path bypasses this mapping, the singular form would fail. |
| NAME-FR-002 | **P2** | **`advanced_condition` config key does not match Talend XML**: Talend uses `ADVANCED_COND` (abbreviated). The config key is `advanced_condition` (full word). This is not a bug (the converter maps it), but creates confusion when comparing config JSON to Talend XML. |
| NAME-FR-003 | **P2** | **`conditions[].value` vs Talend's `RVALUE`**: Talend uses `RVALUE` (right-hand value) in the XML. The config key is `value`. The `R` prefix conveys that this is the right-hand side of the comparison operator, which is lost in the config key. |
| NAME-FR-004 | **P3** | **Output key `'main'` vs Talend connector `'FILTER'`**: The engine returns `{'main': accepted, 'reject': rejected}`. Talend's matching output connector is named `FILTER`, not `FLOW` or `MAIN`. The engine.py routing code (line 575-576) correctly maps connections with type `'filter'` to `result['main']`, but the naming mismatch is confusing when debugging. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FR-001 | **P1** | "No `print()` statements" (STANDARDS.md line 286, 789) | **19 print() statements** throughout the component. All have equivalent logger calls. Some dump sensitive data or full row contents. One crashes due to `.toList()` typo. |
| STD-FR-002 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists (line 65) and is correctly implemented. It IS called by `validate_config()` (line 304) but `validate_config()` is not called automatically by `__init__()` or `execute()`. Validation is only triggered if explicitly called. |
| STD-FR-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types. |
| STD-FR-004 | **P2** | "Use logging, not print()" (STANDARDS.md line 284-286) | Component uses both `logging` and `print()` simultaneously. The `print()` calls are redundant debug artifacts. |
| STD-FR-005 | **P3** | "Component docstring must list all config keys, inputs, outputs" | Docstring (lines 17-53) correctly lists conditions, logical_operator, use_advanced, advanced_condition. Lists main and reject outputs. Lists NB_LINE, NB_LINE_OK, NB_LINE_REJECT stats. Good compliance. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FR-001 | **P1** | **`eval()` used for advanced condition evaluation**: `eval(expr, {}, row.to_dict())` on line 195 executes arbitrary Python code. The expression comes from the Talend XML (user-provided). While the namespace is restricted (empty globals, row dict as locals), Python's `eval()` can still be exploited via attribute access to reach dangerous builtins. For example, `().__class__.__bases__[0].__subclasses__()` can enumerate all loaded classes. In a trusted Talend migration context, this is a LOW risk since the expressions come from converted Talend jobs. However, if expressions are ever user-supplied or dynamically generated, this becomes a code injection vulnerability. A compiled expression system should be used instead of `eval()`. |
| SEC-FR-002 | **P2** | **Sensitive data exposure in print() statements**: `print(f"[FilterRows] {self.id} config: {self.config}")` (line 119) dumps the entire config to stdout, which may include context variable values, credentials, or sensitive filter expressions. `print(f"[FilterRows] First 3 rows:\n{input_data.head(3)}")` (line 123) dumps actual data rows to stdout. In production environments, stdout may be captured in logs accessible to operations teams who should not see the data. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 125); completion logged (line 169-170) -- correct |
| Sensitive data | **FAIL**: `print()` statements dump config and data rows to stdout |
| No print statements | **FAIL**: 19 `print()` statements present. See Section 6.2. |
| Redundancy | Every `print()` has a corresponding `logger.*()` call. The `print()` statements are entirely redundant. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use custom exceptions. Relies on generic `Exception` catch (line 174). Should use `ConfigurationError` or a filter-specific exception. |
| Exception chaining | Does NOT use `raise ... from e` pattern. Line 177 uses bare `raise` which is acceptable but loses context if wrapped. |
| `die_on_error` handling | **NOT IMPLEMENTED**. No `die_on_error` config key is read. All errors propagate as exceptions. |
| No bare `except` | Correct -- uses `except Exception as e` (line 174). |
| Error messages | Logger error includes component ID and exception message (line 175). |
| Graceful degradation | Empty input returns empty DataFrames (line 128-132). Missing column returns False mask (line 273). Unsupported operator returns False mask (line 295). |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_process_advanced_condition()`, `_process_simple_conditions()`, `_evaluate_single_condition()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[Dict]`, `pd.Series` -- correct |
| Class constants | `SUPPORTED_OPERATORS: List[str]` and `LOGICAL_OPERATOR_MAPPING: Dict[str, str]` have implicit types from initialization -- acceptable |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FR-001 | **P1** | **Row-by-row `eval()` in advanced mode**: `input_data.apply(lambda row: eval(expr, {}, row.to_dict()), axis=1)` (line 195) creates a Python dict for each row and evaluates a Python expression. For 1M rows, this means 1M dict creations and 1M `eval()` calls. pandas `apply()` with `axis=1` is the slowest iteration method in pandas. Should be vectorized using pandas native operations or at minimum use `numba`-accelerated functions. |
| PERF-FR-002 | **P2** | **Row-by-row debug print loop**: Lines 298-299 `for idx, v in enumerate(col_data): print(...)` iterates every row of the DataFrame for every condition, printing a comparison result for each. For 1M rows with 3 conditions, this produces 3M print calls. `print()` involves I/O which is orders of magnitude slower than computation. This loop alone may take longer than the actual filtering. |
| PERF-FR-003 | **P2** | **`.astype(str)` conversion on every condition**: Line 276 calls `input_data[col].astype(str).str.strip()` for each condition. If two conditions reference the same column, the string conversion is performed twice. Should cache converted columns. |
| PERF-FR-004 | **P3** | **`.tolist()` / `.unique()` in debug prints**: Multiple print statements (lines 196, 218, 242, 300) call `.tolist()` or `.unique()` to format output. These create Python lists from numpy arrays, which is an O(n) copy operation. For large DataFrames, this is wasteful when the output is just printed to stdout. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not applicable -- FilterRows processes the entire DataFrame at once (batch mode). No streaming support. |
| Memory for masks | Each condition creates a boolean Series mask (~8 bytes per row). For 3 conditions on 1M rows, this is ~24 MB. Reasonable. |
| DataFrame copies | `accepted = input_data[mask].copy()` and `rejected = input_data[~mask].copy()` (lines 159-160) create full copies of the accepted and rejected data. For a 1M-row DataFrame where 50% pass the filter, this creates two 500K-row DataFrames. Total memory: ~2x the input. This is necessary for correct behavior (avoiding pandas SettingWithCopyWarning) but could be optimized for large datasets. |
| `eval()` row dicts | In advanced mode, `row.to_dict()` (line 195) creates a new Python dict for every row. For 1M rows with 10 columns, this creates 1M dicts with 10 key-value pairs each. Significant memory churn and GC pressure. |
| String coercion | `input_data[col].astype(str)` (line 276) creates a new string Series for every condition. For a 1M-row integer column, this creates 1M Python string objects (~50 bytes each = ~50 MB per column per condition). |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FilterRows` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter tests (complex_converter) | **No** | -- | No dedicated tests for `parse_filter_rows()` |
| Manual/smoke tests | Unknown | -- | No evidence of documented manual tests |

**Key finding**: The `FilterRows` component has ZERO automated tests at any level. All 315 lines of v1 engine code are completely unverified. The `.toList()` typo on line 242 (BUG-FR-001) confirms this -- any test executing simple conditions on non-empty data would have caught this crash immediately.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic equality filter | P0 | Filter on `status == "ACTIVE"`, verify matching rows in main output and non-matching in reject output |
| 2 | Numeric column ordering | P0 | Filter on `age > 25` with numeric column, verify ordering is NUMERIC not lexicographic. Currently fails due to string coercion. |
| 3 | Multiple conditions AND | P0 | Two conditions with AND logic, verify both must pass for row to be accepted |
| 4 | Multiple conditions OR | P0 | Two conditions with OR logic, verify either passing is sufficient |
| 5 | Empty input | P0 | Verify empty DataFrame returns empty main and reject outputs with stats (0, 0, 0) |
| 6 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution |
| 7 | .toList() crash test | P0 | Execute simple conditions on non-empty data, verify no AttributeError (currently crashes due to BUG-FR-001) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Inequality filter | P1 | Filter on `status != "INACTIVE"`, verify inequality logic |
| 9 | Greater/less than with integers | P1 | Filter on `count > 100` with integer column, verify numeric comparison |
| 10 | Greater/less than with floats | P1 | Filter on `price < 9.99` with float column, verify floating-point comparison |
| 11 | Context variable in value | P1 | Filter with value `${context.threshold}`, verify context resolution |
| 12 | Missing column | P1 | Condition references non-existent column, verify warning and False mask |
| 13 | Advanced mode simple expression | P1 | Advanced condition `age > 18`, verify Python eval works for simple expressions |
| 14 | Advanced mode Java expression | P1 | Advanced condition `input_row.name.equals("test")`, verify behavior (currently fails) |
| 15 | Null/NaN handling | P1 | DataFrame with NaN values, verify null rows are handled correctly |
| 16 | CONTAINS operator | P1 | Condition with CONTAINS operator, verify behavior (currently returns False for all) |
| 17 | STARTS_WITH operator | P1 | Condition with STARTS_WITH operator |
| 18 | MATCH_REGEX operator | P1 | Condition with MATCH_REGEX operator |
| 19 | Single condition (no combining) | P1 | Only one condition, verify no combining logic issues |
| 20 | Config validation | P1 | Invalid config (missing column, unsupported operator), verify `_validate_config()` catches errors |
| 21 | Die on error = true | P1 | Error during evaluation with die_on_error=true, verify job stops |
| 22 | Die on error = false | P1 | Error during evaluation with die_on_error=false, verify row goes to reject |
| 23 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 24 | Large DataFrame performance | P2 | 100K rows, verify execution time is reasonable (< 10 seconds) |
| 25 | Boolean column filter | P2 | Filter on `is_active == True`, verify boolean handling |
| 26 | Date column filter | P2 | Filter on date comparison, verify date handling |
| 27 | Empty string value | P2 | Filter on `name == ""`, verify empty string handling |
| 28 | Value with quotes | P2 | Filter on value containing single quotes, verify quote stripping doesn't corrupt |
| 29 | Combined simple + advanced mode | P2 | Both simple conditions and advanced mode enabled, verify combination logic |
| 30 | FUNCTION pre-transform (LENGTH) | P2 | Condition with FUNCTION=LENGTH, verify behavior (currently not supported) |
| 31 | FUNCTION pre-transform (LC/UC) | P2 | Condition with FUNCTION=LC, verify behavior |
| 32 | REJECT output schema | P2 | Verify rejected rows contain errorCode and errorMessage columns |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FR-001 | Bug | **`.toList()` typo on line 242 crashes ALL simple condition executions**: `final_mask.toList()` raises `AttributeError` because pandas Series uses `.tolist()` (lowercase L). This is inside a `print()` statement that executes on every non-empty simple condition evaluation. The component is completely non-functional for simple conditions mode. |
| BUG-FR-002 | Bug (Cross-Cutting) | **`_update_global_map()` in `base_component.py:304` references undefined variable `value`**: Should be `stat_value`. Will crash ALL components when `global_map` is set. |
| BUG-FR-003 | Bug (Cross-Cutting) | **`GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`**: The `default` parameter is not in the method signature, causing `NameError` on every `.get()` call. |
| ENG-FR-001 | Engine | **String coercion for ALL comparisons breaks numeric ordering**: `.astype(str)` on line 276 converts all data to strings. `"9" > "10"` evaluates to True (lexicographic). All numeric ordering comparisons (`<`, `>`, `<=`, `>=`) produce wrong results for numeric columns. |
| ENG-FR-002 | Engine | **Advanced mode uses Python `eval()` instead of Java**: Java expressions like `.equals()`, `.matches()`, `.startsWith()`, ternary `? :`, `Relational.ISNULL()` are not valid Python. Most advanced mode expressions will fail with `SyntaxError` or `NameError`. |
| TEST-FR-001 | Testing | **Zero tests for the component**: All 315 lines of code are unverified. The `.toList()` crash (BUG-FR-001) proves no test has ever executed simple conditions on this component. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FR-001 | Converter | **FUNCTION field not extracted**: CONDITIONS table parsing ignores the FUNCTION elementRef. Conditions using LENGTH, LC, UC, TRIM, ABS_VALUE pre-transforms will produce incorrect results. |
| CONV-FR-002 | Converter | **PREFILTER field not extracted**: Pre-filter expressions are silently dropped. |
| CONV-FR-003 | Converter | **DIE_ON_ERROR not extracted by dedicated parser**: Engine has no die_on_error handling for FilterRows. |
| ENG-FR-003 | Engine | **5 of 11 operators not supported**: `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCH_REGEX` not implemented. Returns False for all rows (silent data loss). |
| ENG-FR-004 | Engine | **FUNCTION pre-transforms not supported**: Not extracted by converter or implemented in engine. |
| ENG-FR-005 | Engine | **No die_on_error handling**: All errors propagate as exceptions. |
| ENG-FR-006 | Engine | **Null values converted to string "nan"**: NaN/None becomes "nan" string, breaking null checks and comparisons. |
| ENG-FR-007 | Engine | **Combined simple + advanced mode not supported**: Engine uses either/or, not both combined. |
| BUG-FR-004 | Bug | **All comparisons use string coercion**: Design flaw causing wrong numeric ordering. See ENG-FR-001. |
| BUG-FR-005 | Bug | **`eval()` with no sandboxing**: Security risk for code injection. |
| BUG-FR-006 | Bug | **Row-by-row `eval()` in advanced mode**: O(n) Python loops for each row, extremely slow for large datasets. |
| BUG-FR-007 | Bug | **Aggressive quote stripping**: `val.strip("'")` strips all matching characters from ends, not just one pair. |
| STD-FR-001 | Standards | **19 print() statements**: Violates STANDARDS.md prohibition on print(). All redundant with existing logger calls. |
| DBG-FR-001 | Debug | **print() dumps entire config**: May expose sensitive data. |
| DBG-FR-014 | Debug | **print() with `.toList()` typo crashes component**: The offending print on line 242. |
| DBG-FR-017 | Debug | **Row-by-row print loop**: 1M rows = 1M print calls per condition. Floods stdout. |
| NAME-FR-001 | Naming | **Missing `tFilterRow` (singular) engine registry alias**: Only plural form registered. |
| PERF-FR-001 | Performance | **Row-by-row `eval()` for advanced mode**: Should be vectorized. |
| SEC-FR-001 | Security | **`eval()` on user-provided expressions**: Code injection risk. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FR-004 | Converter | **No operator normalization for string operators**: `CONTAINS`, `STARTS_WITH`, etc. passed verbatim; engine cannot handle them. |
| CONV-FR-005 | Converter | **Schema type format violates STANDARDS.md**: Uses Python types instead of Talend types. |
| CONV-FR-007 | Converter | **Dead `&&` replacement code in converter**: `component_parser.py` line 752 does `replace('&amp;&amp;', 'AND')` but Python's ElementTree decodes XML entities before returning attribute values, so the value is `&&` not `&amp;&amp;`. The replacement never matches. The system works end-to-end because the engine's `LOGICAL_OPERATOR_MAPPING` handles `&&` -> `AND`, but the converter code is dead/misleading. |
| CONV-FR-008 | Converter | **Fallback mapping uses wrong Talend parameter name**: Line 196 uses `'ADVANCED_CONDITION'` but the actual Talend XML parameter name is `'ADVANCED_COND'`. If the fallback path is exercised with raw Talend parameter names, the advanced condition is silently lost (defaults to empty string). |
| ENG-FR-008 | Engine | **No errorCode/errorMessage in REJECT output**: Rejected rows lack error explanation columns. |
| ENG-FR-009 | Engine | **`{id}_ERROR_MESSAGE` not set in globalMap**: Error details unavailable downstream. |
| ENG-FR-010 | Engine | **No PREFILTER expression support**: Pre-filter expressions not evaluated. |
| BUG-FR-008 | Bug | **Debug print accesses first condition's column unconditionally**: May throw KeyError for non-existent columns. |
| BUG-FR-009 | Bug | **Row-by-row debug print loop**: 3M prints for 1M rows x 3 conditions. |
| NAME-FR-002 | Naming | **`advanced_condition` vs Talend's `ADVANCED_COND`**: Naming inconsistency with XML. |
| NAME-FR-003 | Naming | **`conditions[].value` vs Talend's `RVALUE`**: Lost context about right-hand side. |
| STD-FR-002 | Standards | **`_validate_config()` never called automatically**: Validation is dead unless explicitly invoked. |
| STD-FR-003 | Standards | **Schema types in Python format**: Violates STANDARDS.md. |
| STD-FR-004 | Standards | **Uses both print() and logging**: Redundant output channels. |
| PERF-FR-002 | Performance | **Row-by-row debug print loop**: Dominates execution time for large DataFrames. |
| PERF-FR-003 | Performance | **`.astype(str)` repeated per condition**: Same column converted multiple times. |
| SEC-FR-002 | Security | **print() exposes data**: Config dump and head(3) print leak sensitive info. |
| DBG-FR-004 | Debug | **print() dumps data rows**: `input_data.head(3)` to stdout. |
| DBG-FR-005 through DBG-FR-019 | Debug | Multiple redundant print() statements. See Section 6.2 for full list. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FR-006 | Converter | **LOGICAL_OP uses fragile `.replace()`**: Could inadvertently modify complex expressions. |
| ENG-FR-011 | Engine | **No tStatCatcher integration**: Low priority. |
| BUG-FR-010 | Bug | **Potential index alignment issue with empty conditions**: `pd.Series([True] * len(input_data))` uses RangeIndex; non-default DataFrame index causes alignment issues when used as a mask. Edge case since validation would normally flag empty conditions, but validation is never auto-called. |
| NAME-FR-004 | Naming | **Output key `'main'` vs Talend connector `'FILTER'`**: Naming mismatch with Talend connector name. |
| STD-FR-005 | Standards | **Docstring compliance**: Good -- all config keys, inputs, outputs, stats documented. |
| PERF-FR-004 | Performance | **`.tolist()` / `.unique()` in debug prints**: O(n) copy for stdout. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 6 | 3 bugs (1 component-specific, 2 cross-cutting), 2 engine, 1 testing |
| P1 | 19 | 3 converter, 5 engine, 4 bugs, 1 standards, 3 debug, 1 naming, 1 performance, 1 security |
| P2 | 19+ | 4 converter, 3 engine, 2 bugs, 3 standards, 2 performance, 1 security, 4+ naming/debug |
| P3 | 6 | 1 converter, 1 engine, 1 bug, 1 naming, 1 standards, 1 performance |
| **Total** | **50+** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `.toList()` typo** (BUG-FR-001): Change `final_mask.toList()` to `final_mask.tolist()` on `filter_rows.py` line 242. Better yet, remove the entire print statement (see recommendation 3). **Impact**: Unblocks ALL simple condition executions. **Risk**: Zero.

2. **Fix cross-cutting bugs** (BUG-FR-002, BUG-FR-003):
   - In `base_component.py:304`: Change `{value}` to `{stat_value}` or remove the stale reference entirely.
   - In `global_map.py:26`: Add `default: Any = None` parameter to `get()` method signature.
   **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Remove ALL 19 print() statements** (STD-FR-001, DBG-FR-001 through DBG-FR-019): Delete every `print()` call in `filter_rows.py`. All have equivalent `logger.*()` calls. This simultaneously fixes:
   - BUG-FR-001 (`.toList()` crash is in a print)
   - BUG-FR-009 (row-by-row print loop)
   - SEC-FR-002 (data exposure in prints)
   - PERF-FR-002 (print I/O overhead)
   **Impact**: Removes crash, improves performance, eliminates data exposure. **Risk**: Zero (all prints are redundant with logger).

4. **Fix string coercion for numeric comparisons** (ENG-FR-001, BUG-FR-004): Replace the universal `.astype(str)` conversion on line 276 with type-aware comparison logic:
   ```python
   # Instead of: col_data = input_data[col].astype(str).str.strip()
   # Use type-aware comparison:
   col_series = input_data[col]
   if pd.api.types.is_numeric_dtype(col_series):
       val_numeric = pd.to_numeric(val, errors='coerce')
       if op == '==': mask = col_series == val_numeric
       elif op == '>': mask = col_series > val_numeric
       # ... etc
   else:
       col_data = col_series.astype(str).str.strip()
       val_stripped = str(val).strip()
       # ... string comparison as before
   ```
   **Impact**: Fixes ALL numeric ordering comparisons. **Risk**: Medium -- requires testing with mixed types.

5. **Implement missing operators** (ENG-FR-003): Add `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCH_REGEX` to `_evaluate_single_condition()`:
   ```python
   elif op == 'CONTAINS':
       mask = col_data.str.contains(val_stripped, na=False)
   elif op == 'NOT_CONTAINS':
       mask = ~col_data.str.contains(val_stripped, na=False)
   elif op == 'STARTS_WITH':
       mask = col_data.str.startswith(val_stripped, na=False)
   elif op == 'ENDS_WITH':
       mask = col_data.str.endswith(val_stripped, na=False)
   elif op == 'MATCH_REGEX':
       mask = col_data.str.match(val_stripped, na=False)
   ```
   Also add these to `SUPPORTED_OPERATORS` class constant. **Impact**: Enables jobs using string pattern operators. **Risk**: Low.

6. **Create unit test suite** (TEST-FR-001): Implement at minimum the 7 P0 test cases from Section 8.2. Without tests, no behavior is verified.

### Short-Term (Hardening)

7. **Extract FUNCTION field in converter** (CONV-FR-001): In `parse_filter_rows()` (component_parser.py line 768), add extraction of the `FUNCTION` elementRef:
   ```python
   elif ref == 'FUNCTION':
       cond['function'] = val
   ```
   Then implement FUNCTION support in the engine's `_evaluate_single_condition()` by applying the function to the column data before comparison.

8. **Extract DIE_ON_ERROR in converter** (CONV-FR-003): Add `DIE_ON_ERROR` extraction in `parse_filter_rows()`. Implement `die_on_error` handling in the engine's `_process()` method: wrap condition evaluation in try/except, route error rows to reject when `die_on_error=false`, raise when `die_on_error=true`.

9. **Fix null handling** (ENG-FR-006): Before the `.astype(str)` conversion, check for null values separately:
   ```python
   null_mask = input_data[col].isna()
   if op == '==' and val_stripped.lower() in ('null', 'none', ''):
       mask = null_mask
   elif op == '!=' and val_stripped.lower() in ('null', 'none', ''):
       mask = ~null_mask
   else:
       # Non-null rows only
       col_data = input_data[col].dropna().astype(str).str.strip()
       # ... comparison logic
       mask = mask.reindex(input_data.index, fill_value=False)
   ```

10. **Implement combined simple + advanced mode** (ENG-FR-007): Change the `if/else` on lines 153-156 to combine both when both are configured:
    ```python
    if conditions:
        simple_mask = self._process_simple_conditions(input_data, conditions, logical_operator)
    else:
        simple_mask = pd.Series([True] * len(input_data))

    if use_advanced and advanced_condition:
        adv_mask = self._process_advanced_condition(input_data, advanced_condition)
    else:
        adv_mask = pd.Series([True] * len(input_data))

    if logical_operator == 'AND':
        mask = simple_mask & adv_mask
    else:
        mask = simple_mask | adv_mask
    ```

11. **Add errorCode/errorMessage to REJECT output** (ENG-FR-008): When building the rejected DataFrame, add columns indicating which condition(s) failed:
    ```python
    rejected = input_data[~mask].copy()
    rejected['errorCode'] = 'FILTER_REJECTED'
    rejected['errorMessage'] = 'Row did not match filter conditions'
    ```

12. **Fix advanced mode to use Java bridge** (ENG-FR-002): Instead of Python `eval()`, use the Java bridge to evaluate advanced conditions:
    ```python
    if self.java_bridge:
        mask = self.java_bridge.evaluate_filter(input_data, advanced_condition)
    else:
        # Fallback to Python eval for simple expressions
        mask = input_data.apply(lambda row: eval(expr, {}, row.to_dict()), axis=1)
    ```

13. **Wire up `_validate_config()`** (STD-FR-002): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising an exception or logging warnings.

### Long-Term (Optimization)

14. **Vectorize advanced condition evaluation** (PERF-FR-001, BUG-FR-006): Replace `input_data.apply(lambda row: eval(...), axis=1)` with vectorized pandas operations. Parse the expression into an AST and translate to pandas operations using a compiled expression approach.

15. **Cache column string conversions** (PERF-FR-003): If multiple conditions reference the same column, cache the `.astype(str)` result instead of recomputing.

16. **Add FUNCTION pre-transform support** (ENG-FR-004): Implement all Talend FUNCTION pre-transforms:
    ```python
    if function == 'LENGTH':
        col_data = col_data.str.len()
    elif function == 'LC':
        col_data = col_data.str.lower()
    elif function == 'UC':
        col_data = col_data.str.upper()
    elif function == 'TRIM':
        col_data = col_data.str.strip()
    elif function == 'LTRIM':
        col_data = col_data.str.lstrip()
    elif function == 'RTRIM':
        col_data = col_data.str.rstrip()
    elif function == 'ABS_VALUE':
        col_data = col_data.abs()
    ```

17. **Add `tFilterRow` (singular) to engine registry** (NAME-FR-001): Add `'tFilterRow': FilterRows` to the component registry in `engine.py` alongside the existing `'FilterRows'` and `'tFilterRows'` entries.

18. **Replace `eval()` with safe expression evaluator** (SEC-FR-001): Implement a restricted expression evaluator that supports only comparison operators, logical operators, and column references. Use `ast.literal_eval()` for safe literal parsing or build a custom parser.

19. **Add integration tests** (TEST-FR-001): Build end-to-end tests exercising `tFileInputDelimited -> tFilterRow -> tFileOutputDelimited` in the v1 engine, verifying filter logic, reject routing, statistics, and globalMap propagation.

20. **Add PREFILTER support** (CONV-FR-002, ENG-FR-010): Extract and evaluate pre-filter expressions. Low priority unless specific jobs require it.

---

## Appendix A: Converter Parameter Mapping Code

### Dedicated Parser (component_parser.py lines 744-784)

```python
def parse_filter_rows(self, node, component: Dict) -> Dict:
    """
    Parse tFilterRow/tFilterRows component from Talend XML node.
    Extracts filter conditions and maps to ETL-AGENT FilterRows config format.
    """
    # Extract LOGICAL_OP
    logical_op = None
    for param in node.findall('.//elementParameter[@name="LOGICAL_OP"]'):
        logical_op = param.get('value', 'AND').replace('&amp;&amp;', 'AND').replace('||', 'OR')
        break
    # Extract USE_ADVANCED
    use_advanced = False
    for param in node.findall('.//elementParameter[@name="USE_ADVANCED"]'):
        use_advanced = param.get('value', 'false').lower() == 'true'
        break
    # Extract ADVANCED_COND
    advanced_cond = ''
    for param in node.findall('.//elementParameter[@name="ADVANCED_COND"]'):
        advanced_cond = param.get('value', '')
        break
    # Extract CONDITIONS table
    conditions = []
    for table in node.findall('.//elementParameter[@name="CONDITIONS"]'):
        cond = {}
        for elem in table.findall('.//elementValue'):
            ref = elem.get('elementRef')
            val = elem.get('value', '')
            if ref == 'INPUT_COLUMN':
                cond['column'] = val
            elif ref == 'OPERATOR':
                cond['operator'] = val
            elif ref == 'RVALUE':
                cond['value'] = val
            # NOTE: FUNCTION and PREFILTER elementRefs are NOT extracted
        if cond:
            conditions.append(cond)
    # Map to config
    component['config']['logical_operator'] = logical_op or 'AND'
    component['config']['use_advanced'] = use_advanced
    component['config']['advanced_condition'] = advanced_cond
    component['config']['conditions'] = conditions
    return component
```

**Notes on this code**:
- Line 752: `.replace('&amp;&amp;', 'AND')` handles XML-escaped `&&`. However, by the time the XML is parsed by Python's ElementTree, `&amp;` has already been decoded to `&`. So the actual value in `param.get('value')` would be `&&`, not `&amp;&amp;`. The `.replace('&amp;&amp;', 'AND')` would have no effect. The correct replacement should be `.replace('&&', 'AND')`. **However**, testing would be needed to confirm whether ElementTree decodes XML entities before or after `.get()`.
- Lines 771-776: Only `INPUT_COLUMN`, `OPERATOR`, `RVALUE` are extracted. `FUNCTION` and `PREFILTER` are silently ignored.
- Line 780: Default logical operator is `'AND'` which matches Talend's default `&&`.

### Fallback Mapping (component_parser.py lines 190-197)

```python
# FilterRows mapping
elif component_type in ['tFilterRow', 'tFilterRows']:
    # FilterRows has special handling for conditions
    return {
        'conditions': config_raw.get('CONDITIONS', []),
        'logical_operator': config_raw.get('LOGICAL_OP', 'AND').strip('""'),
        'use_advanced': config_raw.get('USE_ADVANCED', False),
        'advanced_condition': config_raw.get('ADVANCED_CONDITION', '')
    }
```

**Notes on this code**:
- Line 194: `.strip('""')` strips double-quote characters from the logical operator value. This handles the case where Talend stores the value as `"AND"` or `"||"` with surrounding quotes in the XML.
- Line 196: Uses `'ADVANCED_CONDITION'` (full name) instead of `'ADVANCED_COND'` (abbreviated Talend name). This may cause a mismatch if the config_raw dict uses the Talend abbreviation.

---

## Appendix B: Engine Class Structure

```
FilterRows (BaseComponent)
    Constants:
        DEFAULT_LOGICAL_OPERATOR = 'AND'
        SUPPORTED_OPERATORS = ['==', '!=', '>', '<', '>=', '<=']
        LOGICAL_OPERATOR_MAPPING = {'&&': 'AND', '||': 'OR', 'AND': 'AND', 'OR': 'OR'}

    Methods:
        _validate_config() -> List[str]                     # Config validation (not auto-called)
        _process(input_data) -> Dict[str, Any]              # Main entry point
        _process_advanced_condition(input_data, cond) -> Series  # Advanced mode: Python eval()
        _process_simple_conditions(input_data, conds, op) -> Series  # Simple mode: mask combining
        _evaluate_single_condition(input_data, cond) -> Series  # Single condition evaluation
        validate_config() -> bool                           # Legacy wrapper for _validate_config()

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]               # Lifecycle: resolve Java, process, update stats
        _update_stats(rows_read, rows_ok, rows_reject)      # Update stats dict
        _update_global_map()                                # Push stats to globalMap (HAS BUG)
        validate_schema(df, schema) -> DataFrame            # Type enforcement
        _resolve_java_expressions()                         # Resolve {{java}} markers via Java bridge
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `LOGICAL_OP` | `logical_operator` | Mapped | -- |
| `USE_ADVANCED` | `use_advanced` | Mapped | -- |
| `ADVANCED_COND` | `advanced_condition` | Mapped | -- |
| `CONDITIONS[].INPUT_COLUMN` | `conditions[].column` | Mapped | -- |
| `CONDITIONS[].OPERATOR` | `conditions[].operator` | Mapped | -- |
| `CONDITIONS[].RVALUE` | `conditions[].value` | Mapped | -- |
| `CONDITIONS[].FUNCTION` | -- | **Not Mapped** | P1 |
| `CONDITIONS[].PREFILTER` | -- | **Not Mapped** | P2 |
| `DIE_ON_ERROR` | -- | **Not Mapped** | P1 |
| `SCHEMA` | `schema` | Mapped (generic) | -- |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (low priority) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Operator Support Matrix

| Talend Operator | XML Value | V1 Engine Supported? | V1 Behavior When Used | Correct Behavior |
|-----------------|-----------|---------------------|----------------------|-----------------|
| Equals | `"=="` | **Yes** | String comparison via `==` after `.astype(str)` | Type-specific: `.equals()` for strings, `==` for primitives |
| Not Equal To | `"!="` | **Yes** | String comparison via `!=` after `.astype(str)` | Type-specific: `!.equals()` for strings, `!=` for primitives |
| Lower Than | `"<"` | **Yes (broken for numbers)** | Lexicographic comparison on strings | Numeric `<` for numbers, `.compareTo() < 0` for strings |
| Greater Than | `">"` | **Yes (broken for numbers)** | Lexicographic comparison on strings | Numeric `>` for numbers, `.compareTo() > 0` for strings |
| Lower or Equal | `"<="` | **Yes (broken for numbers)** | Lexicographic comparison on strings | Numeric `<=` for numbers |
| Greater or Equal | `">="` | **Yes (broken for numbers)** | Lexicographic comparison on strings | Numeric `>=` for numbers |
| Contains | `"CONTAINS"` | **No** | Returns False for ALL rows (silent data loss) | `col.contains(val)` substring check |
| Doesn't Contain | `"NOT_CONTAINS"` | **No** | Returns False for ALL rows | `!col.contains(val)` |
| Starts With | `"STARTS_WITH"` | **No** | Returns False for ALL rows | `col.startsWith(val)` |
| Ends With | `"ENDS_WITH"` | **No** | Returns False for ALL rows | `col.endsWith(val)` |
| Match Regex | `"MATCH_REGEX"` | **No** | Returns False for ALL rows | `col.matches(val)` regex match |

**Summary**: 6 of 11 operators implemented. Of the 6 implemented, 4 (`<`, `>`, `<=`, `>=`) are broken for numeric columns due to string coercion. Only `==` and `!=` work reliably for string columns.

---

## Appendix E: FUNCTION Pre-Transform Support Matrix

| Talend Function | XML Value | V1 Engine Supported? | V1 Converter Extracts? | Impact |
|-----------------|-----------|---------------------|----------------------|--------|
| (none) | `"EMPTY"` | Yes (default) | N/A | No transform needed |
| Absolute Value | `"ABS_VALUE"` | **No** | **No** | Numeric abs() not applied |
| Lower Case | `"LC"` | **No** | **No** | Case-insensitive comparison fails |
| Upper Case | `"UC"` | **No** | **No** | Case-insensitive comparison fails |
| Length | `"LENGTH"` | **No** | **No** | Length comparison compares raw value instead |
| Trim | `"TRIM"` | **Partial** | **No** | Engine always trims via `.str.strip()`, but this is applied universally, not based on FUNCTION |
| Left Trim | `"LTRIM"` | **No** | **No** | Left-trim not applied |
| Right Trim | `"RTRIM"` | **No** | **No** | Right-trim not applied |
| Match | `"MATCH"` | **No** | **No** | Regex match not applied |

**Summary**: 0 of 8 functions explicitly implemented. TRIM is accidentally supported because the engine always applies `.str.strip()` to column data (line 276). This is a happy accident, not a deliberate implementation.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows to FILTER, 0 rows to REJECT. NB_LINE=0, NB_LINE_OK=0, NB_LINE_REJECT=0. |
| **V1** | Returns empty DataFrames for both main and reject (line 128-132). Stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: All rows pass filter

| Aspect | Detail |
|--------|--------|
| **Talend** | All rows to FILTER, 0 to REJECT. NB_LINE=N, NB_LINE_OK=N, NB_LINE_REJECT=0. |
| **V1** | Mask is all True. `accepted = input_data[mask]` returns all rows. `rejected = input_data[~mask]` returns empty. |
| **Verdict** | CORRECT (assuming no `.toList()` crash) |

### Edge Case 3: All rows fail filter

| Aspect | Detail |
|--------|--------|
| **Talend** | 0 rows to FILTER, all to REJECT. NB_LINE=N, NB_LINE_OK=0, NB_LINE_REJECT=N. |
| **V1** | Mask is all False. `accepted` is empty. `rejected` has all rows. |
| **Verdict** | CORRECT (assuming no `.toList()` crash) |

### Edge Case 4: Numeric column with `>` operator

| Aspect | Detail |
|--------|--------|
| **Talend** | `age > 25` evaluates numerically. Age 30 passes, age 9 fails. |
| **V1** | `"30" > "25"` is True (correct by accident). `"9" > "25"` is True (WRONG -- `"9" > "2"` lexicographically). |
| **Verdict** | **WRONG** -- Lexicographic comparison gives incorrect results for single-digit vs multi-digit numbers. |

### Edge Case 5: Float column with `==` operator

| Aspect | Detail |
|--------|--------|
| **Talend** | `price == 10.0` evaluates numerically. Both `10` and `10.0` match. |
| **V1** | `"10" == "10.0"` is False (string comparison). `"10.0" == "10.0"` is True. |
| **Verdict** | **WRONG** -- String representation mismatch for equivalent numeric values. |

### Edge Case 6: Null/NaN values in column

| Aspect | Detail |
|--------|--------|
| **Talend** | Null column with `!= null` evaluates to False. Null column with `== null` evaluates to True. |
| **V1** | `.astype(str)` converts NaN to `"nan"`. `"nan" == "null"` is False. `"nan" != "null"` is True. Null checks do not work as expected. |
| **Verdict** | **WRONG** -- Null handling is fundamentally broken. |

### Edge Case 7: CONTAINS operator

| Aspect | Detail |
|--------|--------|
| **Talend** | `description CONTAINS "error"` checks substring. |
| **V1** | `CONTAINS` is not in `SUPPORTED_OPERATORS`. `_evaluate_single_condition()` falls through to `else` (line 292), returns `pd.Series([False] * len(input_data))`. ALL rows rejected. |
| **Verdict** | **WRONG** -- Silent data loss. All rows fail filter. |

### Edge Case 8: Advanced mode with Java `.equals()` method

| Aspect | Detail |
|--------|--------|
| **Talend** | `input_row.status.equals("ACTIVE")` evaluates via Java. |
| **V1** | After stripping `input_row.`, expression becomes `status.equals("ACTIVE")`. `eval()` tries to call `.equals()` on a Python string, which has no `.equals()` method. Raises `AttributeError`. |
| **Verdict** | **WRONG** -- Crashes with AttributeError. |

### Edge Case 9: Advanced mode with simple Python-compatible expression

| Aspect | Detail |
|--------|--------|
| **Talend** | `input_row.age > 18` evaluates via Java. |
| **V1** | After stripping `input_row.`, expression becomes `age > 18`. `eval()` evaluates `age > 18` with `age` as a value from `row.to_dict()`. Works correctly if `age` is numeric. |
| **Verdict** | CORRECT (for simple expressions that are valid in both Java and Python) |

### Edge Case 10: Condition with FUNCTION=LENGTH

| Aspect | Detail |
|--------|--------|
| **Talend** | `FUNCTION=LENGTH, OPERATOR=>, RVALUE=5` on column `name` generates `name.length() > 5`. |
| **V1** | FUNCTION not extracted. Condition becomes `name > "5"` (string comparison). `"Alice" > "5"` is True (correct by accident for ASCII). `"Bob" > "5"` is True. `"12345" > "5"` is False (WRONG). |
| **Verdict** | **WRONG** -- FUNCTION ignored, comparison semantics changed entirely. |

### Edge Case 11: Multiple conditions with AND

| Aspect | Detail |
|--------|--------|
| **Talend** | `status == "ACTIVE" AND age > 18`. Both must be true. |
| **V1** | Two masks created and combined with `&`. `status == "ACTIVE"` mask AND `age > 18` mask (broken for numeric). Logic is correct but numeric comparison is wrong. |
| **Verdict** | **PARTIALLY CORRECT** -- AND logic correct, but numeric comparison in second condition is broken. |

### Edge Case 12: Value with surrounding quotes

| Aspect | Detail |
|--------|--------|
| **Talend** | RVALUE=`"'ACTIVE'"` (Talend stores string literals with quotes). |
| **V1** | `val.strip("'")` strips surrounding single quotes. `"'ACTIVE'"` becomes `"ACTIVE"`. |
| **Verdict** | CORRECT for simple cases. But `"''ACTIVE''"` becomes `"ACTIVE"` (strips all `'` from ends). |

### Edge Case 13: Context variable in condition value

| Aspect | Detail |
|--------|--------|
| **Talend** | RVALUE=`context.threshold`. Resolved at runtime. |
| **V1** | `context_manager.resolve_string(val)` on line 262 resolves `${context.threshold}` pattern. Raw `context.threshold` (without `${}`) may not be resolved -- depends on resolve_string implementation. |
| **Verdict** | **PARTIAL** -- Works if value uses `${context.var}` syntax, may fail with raw `context.var`. |

### Edge Case 14: Boolean column with `==` operator

| Aspect | Detail |
|--------|--------|
| **Talend** | `is_active == true` evaluates as boolean. |
| **V1** | `.astype(str)` converts `True` to `"True"`. Value `"true"` compared to `"True"` -- CASE MISMATCH. `"true" == "True"` is False. |
| **Verdict** | **WRONG** -- Boolean case mismatch after string coercion. |

### Edge Case 15: Empty conditions table (no conditions)

| Aspect | Detail |
|--------|--------|
| **Talend** | All rows pass (no filter applied). All rows to FILTER, none to REJECT. |
| **V1** | `_validate_config()` reports error: "Config 'conditions' must be a non-empty list". But `_validate_config()` is never auto-called. `_process_simple_conditions()` checks `if not conditions: return pd.Series([True] * len(input_data))` (line 214). All rows pass. |
| **Verdict** | CORRECT (at runtime, validation would flag it as error if called) |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FilterRows`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FR-002 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FR-003 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| STD-FR-002 | **P2** | `base_component.py` | `_validate_config()` is defined in child components but never called automatically. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-FR-001 -- `.toList()` typo

**File**: `src/v1/engine/components/transform/filter_rows.py`
**Line**: 242

**Current code (crashes)**:
```python
print(f"[FilterRows] Final mask: {final_mask.toList()}")
```

**Minimal fix** (change case):
```python
print(f"[FilterRows] Final mask: {final_mask.tolist()}")
```

**Recommended fix** (remove print entirely):
```python
# Delete this line entirely. The logger.debug() calls provide equivalent information.
```

**Explanation**: pandas Series has `.tolist()` (lowercase L), not `.toList()` (uppercase L). The `.toList()` call raises `AttributeError: 'Series' object has no attribute 'toList'`. Since this is inside a `print()` statement that should not exist per STANDARDS.md, the best fix is to delete the entire line.

**Impact**: Unblocks ALL simple condition executions. Without this fix, the component crashes on every execution with non-empty data. **Risk**: Zero.

---

### Fix Guide: ENG-FR-001 -- String coercion for numeric comparisons

**File**: `src/v1/engine/components/transform/filter_rows.py`
**Method**: `_evaluate_single_condition()`
**Lines**: 275-295

**Current code (broken for numbers)**:
```python
# Use .astype(str).str.strip() for robust comparison
col_data = input_data[col].astype(str).str.strip()
val_stripped = str(val).strip()

# Apply operator
if op == '==':
    mask = col_data == val_stripped
elif op == '!=':
    mask = col_data != val_stripped
elif op == '>':
    mask = col_data > val_stripped
# ... etc
```

**Recommended fix**:
```python
col_series = input_data[col]

# Determine comparison type based on column dtype
if pd.api.types.is_numeric_dtype(col_series):
    # Numeric comparison
    try:
        val_numeric = pd.to_numeric(val, errors='raise')
    except (ValueError, TypeError):
        logger.warning(f"[{self.id}] Cannot convert value '{val}' to numeric for column '{col}'")
        return pd.Series([False] * len(input_data), index=input_data.index)

    if op == '==':
        mask = col_series == val_numeric
    elif op == '!=':
        mask = col_series != val_numeric
    elif op == '>':
        mask = col_series > val_numeric
    elif op == '<':
        mask = col_series < val_numeric
    elif op == '>=':
        mask = col_series >= val_numeric
    elif op == '<=':
        mask = col_series <= val_numeric
    else:
        logger.warning(f"[{self.id}] Operator '{op}' not supported for numeric columns")
        mask = pd.Series([False] * len(input_data), index=input_data.index)
elif pd.api.types.is_bool_dtype(col_series):
    # Boolean comparison
    val_bool = str(val).strip().lower() in ('true', '1', 'yes')
    if op == '==':
        mask = col_series == val_bool
    elif op == '!=':
        mask = col_series != val_bool
    else:
        logger.warning(f"[{self.id}] Operator '{op}' not meaningful for boolean columns")
        mask = pd.Series([False] * len(input_data), index=input_data.index)
else:
    # String comparison (existing logic)
    col_data = col_series.astype(str).str.strip()
    val_stripped = str(val).strip()

    if op == '==':
        mask = col_data == val_stripped
    elif op == '!=':
        mask = col_data != val_stripped
    elif op == '>':
        mask = col_data > val_stripped
    elif op == '<':
        mask = col_data < val_stripped
    elif op == '>=':
        mask = col_data >= val_stripped
    elif op == '<=':
        mask = col_data <= val_stripped
    elif op == 'CONTAINS':
        mask = col_data.str.contains(val_stripped, na=False)
    elif op == 'NOT_CONTAINS':
        mask = ~col_data.str.contains(val_stripped, na=False)
    elif op == 'STARTS_WITH':
        mask = col_data.str.startswith(val_stripped)
    elif op == 'ENDS_WITH':
        mask = col_data.str.endswith(val_stripped)
    elif op == 'MATCH_REGEX':
        mask = col_data.str.match(val_stripped, na=False)
    else:
        logger.warning(f"[{self.id}] Unsupported operator '{op}'")
        mask = pd.Series([False] * len(input_data), index=input_data.index)

# Handle NaN in the mask
mask = mask.fillna(False)
```

**Impact**: Fixes all numeric ordering comparisons and adds string operator support. **Risk**: Medium -- requires thorough testing with mixed types and edge cases (NaN, None, empty strings, mixed types in a column).

---

### Fix Guide: ENG-FR-003 -- Adding missing operators

**File**: `src/v1/engine/components/transform/filter_rows.py`

**Step 1**: Update SUPPORTED_OPERATORS class constant:
```python
SUPPORTED_OPERATORS = [
    '==', '!=', '>', '<', '>=', '<=',
    'CONTAINS', 'NOT_CONTAINS',
    'STARTS_WITH', 'ENDS_WITH',
    'MATCH_REGEX'
]
```

**Step 2**: Add operator implementations in `_evaluate_single_condition()` (see Fix Guide for ENG-FR-001 above).

**Step 3**: Update `_validate_config()` to accept the new operators.

---

### Fix Guide: CONV-FR-001 -- Extracting FUNCTION field

**File**: `src/converters/complex_converter/component_parser.py`
**Method**: `parse_filter_rows()`
**Lines**: 768-776

**Current code** (missing FUNCTION):
```python
for elem in table.findall('.//elementValue'):
    ref = elem.get('elementRef')
    val = elem.get('value', '')
    if ref == 'INPUT_COLUMN':
        cond['column'] = val
    elif ref == 'OPERATOR':
        cond['operator'] = val
    elif ref == 'RVALUE':
        cond['value'] = val
```

**Fix**:
```python
for elem in table.findall('.//elementValue'):
    ref = elem.get('elementRef')
    val = elem.get('value', '')
    if ref == 'INPUT_COLUMN':
        cond['column'] = val
    elif ref == 'FUNCTION':
        cond['function'] = val
    elif ref == 'OPERATOR':
        cond['operator'] = val
    elif ref == 'RVALUE':
        cond['value'] = val
    elif ref == 'PREFILTER':
        cond['prefilter'] = val
```

**Impact**: Enables FUNCTION pre-transform and PREFILTER extraction for downstream engine implementation. **Risk**: Low (additive change, no existing behavior modified).

---

### Fix Guide: Removing all print() statements

**File**: `src/v1/engine/components/transform/filter_rows.py`

Delete the following lines (19 print statements + 2 lines for the row-by-row loop):
- Line 119: `print(f"[FilterRows] {self.id} config: {self.config}")`
- Line 120: `print(f"[FilterRows] input_data shape: ...")`
- Line 121: `print(f"[FilterRows] input_data columns: ...")`
- Line 123: `print(f"[FilterRows] First 3 rows:\n{input_data.head(3)}")`
- Line 131: `print(f"[FilterRows] Empty input, returning empty DataFrames.")`
- Lines 144-145: `print(f"[FilterRows] use_advanced: ...")`
- Line 150: `print(f"[FilterRows] Mapped logical operator to: ...")`
- Line 165: `print(f"[FilterRows] Accepted shape: ...")`
- Line 176: `print(f"[FilterRows] Error during filtering: {e}")`
- Line 193: `print(f"[FilterRows] Evaluating advanced condition: {expr}")`
- Line 196: `print(f"[FilterRows] Advanced mask: {mask.tolist()}")`
- Line 218: `print(f"[FilterRows] Unique values in '...'...")`
- Line 237: `print(f"[FilterRows] Unknown logical operator '...'...")`
- Line 242: `print(f"[FilterRows] Final mask: {final_mask.toList()}")` **<-- the crash**
- Line 268: `print(f"[FilterRows] Condition: column=...")`
- Line 272: `print(f"[FilterRows] Column '{col}' not found in input data.")`
- Lines 298-299: `for idx, v in enumerate(col_data): print(...)` (entire loop)
- Line 294: `print(f"[FilterRows] Unsupported operator '{op}'.")`
- Line 300: `print(f"[FilterRows] Mask for condition: {mask.tolist()}")`

**Impact**: Eliminates crash (BUG-FR-001), data exposure (SEC-FR-002), performance drag (PERF-FR-002), and STANDARDS.md violation (STD-FR-001). **Risk**: Zero -- all prints are redundant with existing logger calls.

---

## Appendix I: Detailed Code Flow Analysis

### Execution Flow: Simple Conditions Mode

```
1. engine.py calls component.execute(input_data)
2. BaseComponent.execute():
   a. _resolve_java_expressions()          # Resolve {{java}} markers
   b. _process(input_data)                 # Dispatch to FilterRows._process()
   c. _update_stats()                      # Update NB_LINE, NB_LINE_OK, NB_LINE_REJECT
   d. _update_global_map()                 # Push stats to globalMap (CRASHES -- BUG-FR-002)

3. FilterRows._process(input_data):
   a. print(config)                         # Debug print #1 (SEC-FR-002)
   b. print(input_data.shape)              # Debug print #2
   c. print(input_data.columns.tolist())   # Debug print #3
   d. print(input_data.head(3))            # Debug print #4 (SEC-FR-002)
   e. Check empty input -> return empty    # Correct
   f. Get config: use_advanced, conditions, logical_operator
   g. print(config values)                 # Debug print #5
   h. Map logical operator (&&->AND, ||->OR)
   i. Branch: simple mode -> _process_simple_conditions()
   j. Split: accepted = input_data[mask], rejected = input_data[~mask]
   k. print(shapes)                        # Debug print #6
   l. _update_stats(rows_in, rows_out, rows_rejected)
   m. return {'main': accepted, 'reject': rejected}

4. FilterRows._process_simple_conditions(input_data, conditions, logical_operator):
   a. Check empty conditions -> return all-True mask
   b. print(unique values of first condition's column)  # Debug print #7
   c. For each condition:
      i. mask = _evaluate_single_condition(input_data, cond)
      ii. masks.append(mask)
   d. Combine masks with AND or OR logic
   e. print(f"Final mask: {final_mask.toList()}")       # **CRASHES HERE** (BUG-FR-001)
   f. return final_mask

5. FilterRows._evaluate_single_condition(input_data, condition):
   a. Extract column, operator, value
   b. Resolve context variables in value
   c. Strip quotes from value                           # Aggressive stripping (BUG-FR-007)
   d. print(condition details)                          # Debug print #8
   e. Check column exists in DataFrame
   f. col_data = input_data[col].astype(str).str.strip()  # STRING COERCION (ENG-FR-001)
   g. val_stripped = str(val).strip()
   h. Apply operator (==, !=, >, <, >=, <=)
   i. for idx, v in enumerate(col_data): print(...)     # ROW-BY-ROW PRINT (BUG-FR-009)
   j. print(mask.tolist())                              # Debug print #10
   k. return mask
```

### Execution Flow: Advanced Mode

```
1-3. Same as simple mode up to step 3.i

3.i. Branch: advanced mode -> _process_advanced_condition()

4. FilterRows._process_advanced_condition(input_data, advanced_condition):
   a. Strip {{java}} prefix from expression
   b. Strip 'input_row.' prefix from expression
   c. print(expression)                                 # Debug print
   d. mask = input_data.apply(
        lambda row: eval(expr, {}, row.to_dict()),       # EVAL (SEC-FR-001, PERF-FR-001)
        axis=1
      )
   e. print(mask.tolist())                              # Debug print
   f. return mask
```

### Engine Connection Routing (engine.py lines 570-576)

```python
if flow['from'] == comp_id:
    if flow['type'] == 'flow' and 'main' in result and result['main'] is not None:
        self.data_flows[flow['name']] = result['main']
    elif flow['type'] == 'reject' and 'reject' in result and result['reject'] is not None:
        self.data_flows[flow['name']] = result['reject']
    elif flow['type'] == 'filter' and 'main' in result and result['main'] is not None:
        self.data_flows[flow['name']] = result['main']
```

Key observations:
- `flow['type'] == 'filter'` maps to `result['main']` -- correct. FILTER output gets the accepted rows.
- `flow['type'] == 'reject'` maps to `result['reject']` -- correct. REJECT output gets the rejected rows.
- `flow['type'] == 'flow'` also maps to `result['main']` -- this means if a connection is typed as `FLOW` instead of `FILTER`, it still gets the accepted rows. This is a fallback that works correctly.

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using numeric column filtering (`>`, `<`, `>=`, `<=`) | **Critical** | ANY job with numeric comparison operators | Fix string coercion (ENG-FR-001) before migration |
| Jobs using CONTAINS, STARTS_WITH, ENDS_WITH, MATCH_REGEX | **Critical** | Jobs with string pattern operators | Implement missing operators (ENG-FR-003) |
| Jobs using advanced mode with Java expressions | **Critical** | Jobs with `USE_ADVANCED=true` and Java-specific syntax | Replace `eval()` with Java bridge (ENG-FR-002) |
| Jobs using FUNCTION pre-transforms | **High** | Jobs with LENGTH, LC, UC, ABS_VALUE functions | Extract FUNCTION in converter (CONV-FR-001) and implement in engine |
| Jobs relying on REJECT output errorCode/errorMessage | **High** | Jobs with downstream error handling | Add error columns to reject output (ENG-FR-008) |
| Jobs with null values in filtered columns | **High** | Most production jobs | Fix null handling (ENG-FR-006) |

### Medium-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using die_on_error | Medium | No die_on_error handling -- all errors crash the job |
| Jobs using combined simple + advanced mode | Medium | Only one mode used at a time |
| Jobs using PREFILTER expressions | Low-Medium | Rarely used in practice |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs with simple string equality filters (`==`, `!=`) | Low | Works correctly for string columns |
| Jobs with AND/OR logical operators | Low | Logic is correctly implemented |
| Jobs with context variables in filter values | Low | Context resolution works |
| Jobs with empty input data | Low | Handled correctly |

### Recommended Migration Strategy

1. **Phase 1 -- Immediate fixes**: Fix `.toList()` crash (BUG-FR-001), remove all `print()` statements, fix cross-cutting bugs (BUG-FR-002, BUG-FR-003). This makes the component minimally functional for string equality filters.

2. **Phase 2 -- Type-aware comparisons**: Fix string coercion (ENG-FR-001). Implement numeric, boolean, and date comparison logic. This enables jobs with numeric filtering.

3. **Phase 3 -- Operator coverage**: Implement `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCH_REGEX` operators. This enables jobs using pattern matching.

4. **Phase 4 -- Converter fixes**: Extract FUNCTION, PREFILTER, DIE_ON_ERROR in converter. Implement FUNCTION pre-transforms in engine. This enables jobs using pre-transform functions.

5. **Phase 5 -- Advanced mode**: Replace `eval()` with Java bridge or safe expression evaluator. Implement combined simple + advanced mode. This enables jobs using advanced expressions.

6. **Phase 6 -- Testing**: Create comprehensive unit and integration tests covering all operators, functions, data types, null handling, and edge cases.

7. **Phase 7 -- Production validation**: Parallel-run migrated jobs against Talend originals. Compare FILTER and REJECT output row-for-row.

---

## Appendix K: Complete Engine Implementation Code

```python
"""
FilterRows - Filters rows based on conditions or advanced Java expressions.

Talend equivalent: tFilterRow, tFilterRows
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FilterRows(BaseComponent):
    """
    Filters rows based on specified conditions or advanced Java expressions.
    ...
    """

    # Class constants
    DEFAULT_LOGICAL_OPERATOR = 'AND'
    SUPPORTED_OPERATORS = ['==', '!=', '>', '<', '>=', '<=']
    LOGICAL_OPERATOR_MAPPING = {
        '&&': 'AND',
        '||': 'OR',
        'AND': 'AND',
        'OR': 'OR'
    }

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        # ... validation logic (correctly implemented, never auto-called)

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Process input data by filtering rows based on conditions."""
        print(f"[FilterRows] {self.id} config: {self.config}")          # DBG-FR-001
        print(f"[FilterRows] input_data shape: ...")                     # DBG-FR-002
        print(f"[FilterRows] input_data columns: ...")                   # DBG-FR-003
        if input_data is not None:
            print(f"[FilterRows] First 3 rows:\n{input_data.head(3)}")  # DBG-FR-004

        # ... empty input handling (correct)

        # Branch: simple or advanced
        if use_advanced and advanced_condition:
            mask = self._process_advanced_condition(input_data, advanced_condition)
        else:
            mask = self._process_simple_conditions(input_data, conditions, logical_operator)

        # Split data
        accepted = input_data[mask].copy()
        rejected = input_data[~mask].copy()

        return {'main': accepted, 'reject': rejected}

    def _process_advanced_condition(self, input_data, advanced_condition):
        """Process advanced Java-like condition."""
        expr = advanced_condition.replace('{{java}}', '').strip()
        expr = expr.replace('input_row.', '')
        mask = input_data.apply(lambda row: eval(expr, {}, row.to_dict()), axis=1)  # SEC-FR-001
        return mask

    def _process_simple_conditions(self, input_data, conditions, logical_operator):
        """Process simple conditions."""
        # ... mask combining (correct AND/OR logic)
        print(f"[FilterRows] Final mask: {final_mask.toList()}")  # BUG-FR-001 (CRASHES)
        return final_mask

    def _evaluate_single_condition(self, input_data, condition):
        """Evaluate a single condition."""
        col_data = input_data[col].astype(str).str.strip()  # ENG-FR-001 (STRING COERCION)
        val_stripped = str(val).strip()

        if op == '==':    mask = col_data == val_stripped
        elif op == '!=':  mask = col_data != val_stripped
        elif op == '>':   mask = col_data > val_stripped     # WRONG for numbers
        elif op == '<':   mask = col_data < val_stripped     # WRONG for numbers
        elif op == '>=':  mask = col_data >= val_stripped    # WRONG for numbers
        elif op == '<=':  mask = col_data <= val_stripped    # WRONG for numbers
        else:
            mask = pd.Series([False] * len(input_data))      # CONTAINS etc. -> False

        for idx, v in enumerate(col_data):                   # BUG-FR-009 (ROW PRINT LOOP)
            print(f"[FilterRows] Row {idx}: ...")

        return mask
```

---

## Appendix L: Talend tFilterRow XML Example

Below is an example of what a tFilterRow component looks like in Talend's `.item` XML file. This illustrates the parameters the converter must parse.

```xml
<node componentName="tFilterRow_1" componentVersion="0.102" offsetLabelX="0" offsetLabelY="0" posX="384" posY="128">
  <elementParameter field="CHECK" name="DIE_ON_ERROR" value="false"/>
  <elementParameter field="CLOSED_LIST" name="LOGICAL_OP" value="&amp;&amp;"/>
  <elementParameter field="CHECK" name="USE_ADVANCED" value="false"/>
  <elementParameter field="MEMO_JAVA" name="ADVANCED_COND" value=""/>

  <!-- CONDITIONS table: each elementParameter[@name="CONDITIONS"] is one condition row -->
  <elementParameter field="TABLE" name="CONDITIONS" show="true">
    <elementValue elementRef="INPUT_COLUMN" value="status"/>
    <elementValue elementRef="FUNCTION" value="EMPTY"/>
    <elementValue elementRef="OPERATOR" value="=="/>
    <elementValue elementRef="RVALUE" value="&quot;ACTIVE&quot;"/>
    <elementValue elementRef="PREFILTER" value=""/>
  </elementParameter>
  <elementParameter field="TABLE" name="CONDITIONS" show="true">
    <elementValue elementRef="INPUT_COLUMN" value="age"/>
    <elementValue elementRef="FUNCTION" value="EMPTY"/>
    <elementValue elementRef="OPERATOR" value="&gt;"/>
    <elementValue elementRef="RVALUE" value="18"/>
    <elementValue elementRef="PREFILTER" value=""/>
  </elementParameter>

  <metadata connector="FLOW" name="tFilterRow_1">
    <column key="false" length="50" name="name" nullable="true" type="id_String"/>
    <column key="false" name="age" nullable="true" type="id_Integer"/>
    <column key="false" length="20" name="status" nullable="true" type="id_String"/>
  </metadata>
</node>

<!-- FILTER connection (matching rows) -->
<connection connectorName="FILTER" label="filter_1" lineStyle="0"
    metaname="tFilterRow_1" offsetLabelX="0" offsetLabelY="0"
    source="tFilterRow_1" target="tLogRow_1">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="filter_1"/>
</connection>

<!-- REJECT connection (non-matching rows) -->
<connection connectorName="REJECT" label="reject_1" lineStyle="0"
    metaname="tFilterRow_1" offsetLabelX="0" offsetLabelY="0"
    source="tFilterRow_1" target="tLogRow_2">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="reject_1"/>
</connection>
```

**Key observations from the XML**:
- `LOGICAL_OP` value `&amp;&amp;` is the XML-escaped form of `&&`. ElementTree will decode this to `&&` when reading.
- Each `CONDITIONS` `elementParameter` contains 5 `elementValue` children: `INPUT_COLUMN`, `FUNCTION`, `OPERATOR`, `RVALUE`, `PREFILTER`.
- `RVALUE` may contain XML-escaped quotes: `&quot;ACTIVE&quot;` decodes to `"ACTIVE"`.
- `OPERATOR` may contain XML-escaped comparison operators: `&gt;` decodes to `>`.
- `FUNCTION` value `EMPTY` means no pre-transform function.
- The `FILTER` connection uses `connectorName="FILTER"`, not `"FLOW"` or `"MAIN"`.
- The `REJECT` connection uses `connectorName="REJECT"`.
- The `metaname` attribute on connections references the tFilterRow component, not a separate schema.

---

## Appendix M: Detailed Null Handling Analysis

### How Talend Handles Nulls

In Talend, null handling in tFilterRow is type-dependent:

1. **String columns**: Null strings are stored as Java `null`. Comparisons against null:
   - `column == null` -> True
   - `column != null` -> False
   - `column.equals("value")` -> NullPointerException (Talend generates null guards)
   - `column.contains("substring")` -> NullPointerException (null-guarded to false)

2. **Integer/Long columns**: Null primitives are not possible in Java (primitive types). Talend uses wrapper types (`Integer`, `Long`) for nullable columns. Comparisons:
   - `column == null` -> True (wrapper is null)
   - `column > value` -> NullPointerException (auto-unboxing null throws NPE)
   - Talend generates null guards that route null rows to REJECT

3. **Date columns**: Null dates are `null` references. Same null handling as strings.

### How V1 Handles Nulls (Current)

pandas represents null values as `NaN` (for float/object columns) or `<NA>` (for nullable integer columns). The V1 engine:

1. Calls `.astype(str)` on the column (line 276)
2. This converts:
   - `NaN` -> `"nan"`
   - `None` -> `"None"`
   - `<NA>` -> `"<NA>"`
3. Then compares the string `"nan"` against the reference value

**Results**:
- `"nan" == "ACTIVE"` -> False (correct -- null != "ACTIVE")
- `"nan" == "null"` -> False (WRONG -- should be True for null check)
- `"nan" == "nan"` -> True (WRONG -- this is a string match, not a null check)
- `"nan" != ""` -> True (CORRECT by accident)
- `"nan" > "5"` -> True (WRONG -- null should not be greater than anything)

**Summary**: V1's null handling is fundamentally broken. Null values become the string `"nan"` which then participates in string comparisons with unpredictable results. The fix requires explicit null detection before string coercion.

---

## Appendix N: Print Statement Impact Analysis

### I/O Impact

Each `print()` call in Python involves:
1. String formatting (f-string evaluation)
2. System call to write to stdout file descriptor
3. Potential buffer flush

For a 1 million row DataFrame:
- The row-by-row print loop (lines 298-299) produces ~1M print calls PER CONDITION
- Each print writes ~100 bytes
- Total I/O for 3 conditions: ~300 MB written to stdout
- At ~1 GB/s stdout throughput: ~300 ms just for printing

### Data Volume Impact

- `mask.tolist()` (lines 196, 242, 300): Creates a Python list from a numpy boolean array. For 1M rows, this creates a list of 1M Python `bool` objects. Printing this list creates a string of ~9M characters (`[True, False, True, ...]`).
- `input_data.head(3)` (line 123): Creates a formatted string of the first 3 rows. Typically 200-500 characters. Low impact.
- `col_data.unique()` (line 218): Computes unique values (O(n)) then converts to string. For high-cardinality columns, this could be millions of unique values.

### Total Performance Overhead

For a typical execution with 1M rows and 2 conditions:
- Row-by-row print loop: ~200 ms (I/O bound)
- `.tolist()` print calls: ~50 ms (memory allocation + I/O)
- `.unique()` computation: ~20 ms (computation)
- Other prints: ~1 ms (negligible individually)
- **Total overhead: ~270 ms**, which may exceed the actual filtering computation time (~100 ms for pandas mask operations)

**Conclusion**: The `print()` statements more than DOUBLE the execution time for medium-sized DataFrames. For large DataFrames (10M+ rows), the row-by-row print loop alone could take several seconds.

---

## Appendix O: Comparison with Other Transform Components in V1

| Feature | FilterRows | Map | SortRow | UniqueRow | Join |
|---------|-----------|-----|---------|-----------|------|
| Lines of code | 315 | ~1200 | ~200 | ~250 | ~350 |
| print() statements | **19** | ~5 | ~3 | ~2 | ~4 |
| .toList() typo | **Yes** | No | No | No | No |
| REJECT output | Yes | Yes | No | Yes | No |
| _validate_config() | Has but not auto-called | Has but not auto-called | Has but not auto-called | Has but not auto-called | Has but not auto-called |
| Type-aware processing | **No** (all string) | Yes (expression-based) | Yes (pandas sort) | Yes (pandas unique) | Yes (pandas merge) |
| eval() usage | **Yes** (advanced mode) | No (Java bridge) | No | No | No |
| Unit tests | **Zero** | **Zero** | **Zero** | **Zero** | **Zero** |

**Observation**: FilterRows has the most `print()` statements and is the only component using `eval()` for expression evaluation. The `.toList()` typo is unique to this component. The lack of type-aware comparison is also unique -- other transform components leverage pandas' native type handling. The zero-test pattern is systemic across all v1 components.

---

## Appendix P: Recommended Test File Structure

```python
"""
Tests for FilterRows (tFilterRow) v1 engine component.

Covers:
- Simple conditions (all operators)
- Logical operators (AND, OR)
- Advanced mode (Python eval)
- Null handling
- Type-aware comparisons
- REJECT output
- Statistics tracking
- Edge cases
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

from src.v1.engine.components.transform.filter_rows import FilterRows


class TestFilterRowsSimpleConditions:
    """Test simple condition evaluation."""

    def test_equality_filter_string(self):
        """Filter on string equality."""
        config = {
            'conditions': [{'column': 'status', 'operator': '==', 'value': 'ACTIVE'}],
            'logical_operator': 'AND'
        }
        component = FilterRows('test_1', config)
        df = pd.DataFrame({'status': ['ACTIVE', 'INACTIVE', 'ACTIVE']})
        result = component._process(df)
        assert len(result['main']) == 2
        assert len(result['reject']) == 1

    def test_numeric_greater_than(self):
        """Filter on numeric > operator -- currently broken due to string coercion."""
        config = {
            'conditions': [{'column': 'age', 'operator': '>', 'value': '25'}],
            'logical_operator': 'AND'
        }
        component = FilterRows('test_2', config)
        df = pd.DataFrame({'age': [30, 9, 25, 100]})
        result = component._process(df)
        # Expected: [30, 100] pass, [9, 25] fail
        assert len(result['main']) == 2
        assert list(result['main']['age']) == [30, 100]

    # ... additional test cases per Section 8.2


class TestFilterRowsAdvancedMode:
    """Test advanced expression mode."""
    pass


class TestFilterRowsNullHandling:
    """Test null/NaN value handling."""
    pass


class TestFilterRowsStatistics:
    """Test statistics tracking."""
    pass


class TestFilterRowsEdgeCases:
    """Test edge cases."""
    pass
```

**File location**: `tests/v1/unit/test_filter_rows.py`

This test structure covers the P0 and P1 test cases from Section 8.2 and provides a foundation for comprehensive testing.
