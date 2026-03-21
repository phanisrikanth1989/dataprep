# Audit Report: tXMLMap / XMLMap

## Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tXMLMap` |
| **V1 Engine Class** | `XMLMap` |
| **Engine File** | `src/v1/engine/components/transform/xml_map.py` |
| **Converter Parser** | `component_parser.py` -> `parse_t_xml_map()` (line ~1155) |
| **Converter Dispatch** | `converter.py` -> line ~266-267 (`elif component_type == 'tXMLMap'`) |
| **Registry Aliases (Engine)** | `XMLMap`, `tXMLMap` |
| **Converter Alias** | `tXMLMap` -> `TXMLMap` (MISMATCH - see BUG-XMP-001) |
| **Category** | Transform / XML |
| **Complexity** | Very High -- XML tree mapping, recursive parsing, XPath evaluation, namespace handling |

---

## Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 |
|-----------|-------|----|----|----|----|
| Converter Coverage | R | 1 | 3 | 3 | 2 |
| Engine Feature Parity | R | 2 | 5 | 4 | 1 |
| Code Quality | R | 3 | 3 | 5 | 3 |
| Performance & Memory | Y | 0 | 1 | 2 | 1 |
| Testing | R | 1 | 1 | 0 | 0 |

**Legend**: R = Red (critical gaps), Y = Yellow (notable gaps), G = Green (acceptable)

---

## 1. Talend Feature Baseline

### What tXMLMap Does in Talend

tXMLMap is a specialized transformation component fine-tuned to leverage the **Document** data type for processing XML data. It handles transformation scenarios that mix hierarchical data (XML) and flat data together. The Document type carries a complete user-specific XML flow. tXMLMap provides a visual Map Editor where users can:

- Define input XML tree structures (from schemas or XSD files)
- Define output XML tree structures
- Map fields between input and output trees using drag-and-drop
- Apply XPath expressions for data extraction
- Configure looping elements for repeated XML structures
- Use expression filters to conditionally route data
- Join multiple input sources (inner join and left outer join)
- Produce XML Document output or flat row output

tXMLMap is one of the most complex Talend components, combining XML parsing, tree manipulation, XPath evaluation, namespace management, and data routing into a single visual interface.

### Basic Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Input Trees | `inputTrees` (nodeData) | XML Tree Structure | One or more XML input trees defining the source data structure. The first tree is the main input; additional trees are lookups. |
| Output Trees | `outputTrees` (nodeData) | XML Tree Structure | One or more XML output trees defining the target structure. Can produce flat rows or XML Document output. |
| Looping Element | (node attribute `loop="true"`) | Node flag | The XML element on which the component iterates. Each occurrence of this element produces one output row. Critical for controlling record generation granularity. |
| Connections | `connections` (nodeData) | Source-Target Mapping | Maps input tree nodes to output tree nodes. Source expressions reference input paths; target expressions reference output column indices. |
| Schema | `metadata[@connector="FLOW"]` | Column definitions | Output schema with column names, types, nullable flags, keys, lengths, and precisions. |
| Die on Error | `DIE_ON_ERROR` | Boolean | Whether to stop job execution on processing error. Default: `true`. |

### Advanced Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Keep Order for Document | `KEEP_ORDER_FOR_DOCUMENT` | Boolean | Preserve element order in XML Document output. Default: `false`. |
| Connection Format | `CONNECTION_FORMAT` | String | Format for connection data transfer. Default: `row`. |
| Expression Filter | `expressionFilter` (outputTree attr) | Expression | Java expression to filter rows before output. Applied per output tree. |
| Activate Expression Filter | `activateExpressionFilter` (outputTree attr) | Boolean | Enable/disable the expression filter on an output tree. |
| Matching Mode (Lookup) | `matchingMode` (inputTree attr) | Enum | Lookup matching strategy: `ALL_ROWS`, `FIRST_MATCH`, `LAST_MATCH`, `ALL_MATCHES`. Default: `ALL_ROWS`. |
| Lookup Mode | `lookupMode` (inputTree attr) | Enum | When to load lookup data: `LOAD_ONCE`, `RELOAD`. Default: `LOAD_ONCE`. |
| All in One | `allInOne` (outputTree property) | Boolean | When `true`, generates a single XML document flow containing all output rows. When `false`, generates separate XML flows per record. |
| Aggregate Element | (node context menu) | Node flag | Marks an output node as an aggregate element for grouping/classifying XML output data. |

### Input Tree Structure (Talend)

In Talend, each input tree (`inputTrees`) contains:

| Attribute | Description |
|-----------|-------------|
| `name` | Tree identifier (typically the connection name, e.g., `row1`) |
| `matchingMode` | How lookup rows are matched: `ALL_ROWS`, `FIRST_MATCH`, `LAST_MATCH`, `ALL_MATCHES` |
| `lookupMode` | When lookup is loaded: `LOAD_ONCE` or `RELOAD` |
| `nodes` | Root-level tree nodes, each with `name`, `expression`, `type`, `xpath` |
| `nodes/children` | Recursive child elements with `name`, `type`, `xpath`, `nodeType`, `loop`, `main`, `outgoingConnections` |

Node types within trees:

| nodeType | Description |
|----------|-------------|
| `ELEMENT` | XML element node |
| `ATTRIBUT` | XML attribute node (note: Talend uses `ATTRIBUT`, not `ATTRIBUTE`) |
| `NAMESPACE` | XML namespace declaration node |
| (blank) | Root document node |

### Output Tree Structure (Talend)

Each output tree (`outputTrees`) contains:

| Attribute | Description |
|-----------|-------------|
| `name` | Output connection name |
| `expressionFilter` | Java expression for row filtering |
| `activateExpressionFilter` | Whether the filter is active |
| `nodes` | Output schema nodes, mapped from input via `connections` |

### Looping Element Behavior (Talend)

The looping element is the cornerstone of tXMLMap's record generation:

- Exactly one node in the input tree must have `loop="true"`
- This node defines the XML element that drives row iteration
- Each occurrence of the looping element in the XML input produces one output row
- Fields above the looping element (ancestors) produce repeated values across all rows
- Fields below the looping element (descendants) are relative to each loop iteration
- Fields in sibling branches require careful XPath construction

**Example**: For XML `<employees><employee><id>1</id><name>Alice</name></employee>...`, setting `loop="true"` on `employee` means each `<employee>` produces one row.

### XPath Expression Handling (Talend)

Talend's tXMLMap uses XPath expressions for field extraction:

| Pattern | Description | Example |
|---------|-------------|---------|
| Relative child | Access child element of loop node | `./name` |
| Relative descendant | Access any descendant | `.//address/city` |
| Absolute path | Access from document root | `/employees/metadata/version` |
| Attribute access | Access XML attributes | `./@id`, `./employee/@type` |
| Parent/ancestor | Navigate up the tree | `../department`, `./ancestor::company/name` |
| XPath functions | Built-in functions | `text()`, `position()`, `count()`, `string()`, `normalize-space()` |
| Predicates | Filter conditions | `./item[@type='active']`, `./record[position()>1]` |

### Namespace Handling (Talend)

Talend's tXMLMap handles XML namespaces:

- Default namespaces (`xmlns="..."`) are automatically managed
- Prefixed namespaces (`xmlns:abc="..."`) are preserved
- Namespace declarations can be added to output trees
- XPath expressions must be namespace-qualified when namespaces are present
- Known issue: generated code can be wrong when there is no namespace for some elements

### Connection Types (Talend)

| Connector | Type | Description |
|-----------|------|-------------|
| `FLOW` (Main) | Input | Primary XML data flow (Document type or flat schema) |
| `LOOKUP` | Input | Additional input flows for join/lookup operations |
| `FLOW` (Output) | Output | Transformed rows matching the output schema |
| `REJECT` | Output | Rows that failed expression evaluation or XML processing |
| `FILTER` | Output | Rows filtered by the expression filter condition |

### Join Behavior (Talend)

tXMLMap supports joining multiple input flows:

| Join Type | Description |
|-----------|-------------|
| Inner Join | Only rows matching in both main and lookup are output |
| Left Outer Join | All main rows are output; unmatched lookups produce null |

Join configuration is per-lookup-input via `matchingMode`:
- `ALL_ROWS`: No filtering, all lookup rows considered
- `FIRST_MATCH`: Stop at first matching lookup row
- `LAST_MATCH`: Use last matching lookup row
- `ALL_MATCHES`: Produce a row for each matching lookup combination (Cartesian)

### GlobalMap Variables Produced (Talend)

| Key | Type | Description |
|-----|------|-------------|
| `{id}_NB_LINE` | int | Total rows processed (output rows generated) |
| `{id}_NB_LINE_OK` | int | Rows successfully output to main flow |
| `{id}_NB_LINE_REJECT` | int | Rows sent to reject flow |

### Talend Behavioral Notes

- The Document data type is a special Talend type that carries an entire XML tree as a single field value.
- When the input is a Document field, tXMLMap parses the XML tree and applies XPath expressions against it.
- The looping element determines the granularity of output rows. Setting it on a parent element produces fewer rows with more data per row; setting it on a leaf element produces more rows.
- Expression filters are Java expressions (not XPath) evaluated per row after XML extraction. They use `row.fieldName` syntax.
- Multiple output flows can be defined, each with its own output tree and optional expression filter.
- When "All in One" mode is enabled on an output tree, all rows are aggregated into a single XML Document output.
- Reject flow captures rows where XML parsing fails, XPath evaluation errors occur, or expression filters throw exceptions.
- Namespace-unaware XPath queries against namespaced XML will silently return empty results (a common user error in Talend).

---

## 2. Converter Audit

### Parameters Extracted

| Talend Parameter | Converter Extracts? | V1 Config Key | Notes |
|------------------|---------------------|---------------|-------|
| `DIE_ON_ERROR` | Yes | `die_on_error` | Parsed with null safety |
| `KEEP_ORDER_FOR_DOCUMENT` | Yes | `keep_order` | Parsed with null safety |
| `CONNECTION_FORMAT` | Yes | `connection_format` | Default: `row` |
| `inputTrees` (nodeData) | Yes | `INPUT_TREES` | Full recursive parsing of nodes and children |
| `outputTrees` (nodeData) | Yes | `OUTPUT_TREES` | Full recursive parsing including expressionFilter |
| `connections` (nodeData) | Yes | `CONNECTIONS` | Source/target/sourceExpression extracted |
| `metadata[@connector="FLOW"]` | Yes | `output_schema` / `schema.output` | Column name, type, nullable, key, length, precision |
| `expressionFilter` | Yes | `expression_filter` | Extracted from first output tree only |
| `activateExpressionFilter` | Yes | `activate_expression_filter` | Boolean conversion |
| `looping_element` | Yes | `looping_element` | Multiple fallback strategies: children scan, elementParameter, auto-detect |
| `expressions` | Yes (derived) | `expressions` | Built from connections + input tree node map; XPath rewrite logic applied |
| `matchingMode` | Yes | (inside `INPUT_TREES`) | Per input tree |
| `lookupMode` | Yes | (inside `INPUT_TREES`) | Per input tree |

### Schema Extraction

| Attribute | Extracted? | Notes |
|-----------|-----------|-------|
| `name` | Yes | Column name from FLOW metadata |
| `type` | Yes | Talend type ID (e.g., `id_String`) |
| `nullable` | Yes | Boolean conversion |
| `key` | Yes | Boolean conversion |
| `length` | Yes | Converted to int, default `-1` |
| `precision` | Yes | Converted to int, default `-1` |
| `pattern` | No | **Date pattern not extracted from schema** |
| `comment` | No | Column comment not extracted |

### Converter: Recursive Tree Parsing Analysis

The converter implements `parse_nested_children()` (line ~1179) as a recursive function to parse the deeply-nested XML tree structure of tXMLMap's `nodeData`. This is a critical piece of logic:

**What it captures per child node**:
- `name`: Element/attribute name
- `type`: Talend type ID (default: `id_String`)
- `xpath`: XPath expression
- `nodeType`: Node type (ELEMENT, ATTRIBUT, etc.)
- `loop`: Whether this node is the looping element (boolean)
- `main`: Whether this is the main connection (boolean)
- `outgoingConnections`: Connection references
- `children`: Recursively parsed child elements

**What it misses**:
- `nullable` attribute on tree nodes
- `expression` attribute on child nodes (only captured on top-level `nodes`)
- `defaultValue` for nodes with default values
- `pattern` for date-formatted nodes
- Aggregate element flag (`aggregate` attribute)
- Namespace declaration nodes and their URIs

### Converter: Expression Building Analysis

The converter builds XPath expressions from connection mappings (lines ~1307-1355):

1. For each connection, extracts the target output column index from the path `outputTrees.0/@nodes.{idx}`
2. Traces the source path through the input tree node map
3. Builds an XPath expression from the accumulated node names
4. Handles attribute nodes by converting the last segment to `@attribute` syntax
5. Hardcodes root element removal for `CMARGINSCLM` and `root` (line 1338)

**Critical Issues in Expression Building**:
- Only handles `outputTrees.0` (first output tree) -- multi-output-tree tXMLMap jobs will lose mappings for all subsequent output trees
- Root element removal is hardcoded to specific element names (`CMARGINSCLM`, `root`) instead of dynamically detecting the document root
- The regex `outputTrees\.0/@nodes\.(\d+)` only matches flat output nodes, not nested output tree structures

### Converter: XPath Rewrite Logic Analysis

After building initial expressions, the converter applies XPath rewrite logic (lines ~1401-1449):

1. Strips leading `.` and `/` from each expression (line 1413 -- **THIS CRASHES, see BUG-XMP-001**)
2. Splits the path into segments
3. Determines if the field is "inside" or "outside" the loop element (case-insensitive name match)
4. Inside loop: rewrites to `./relative_path` (stripping everything up to and including the loop element name)
5. Outside loop: rewrites to `./ancestor::absolute_path`

### Converter: Looping Element Detection

The converter uses a multi-step fallback strategy for finding the looping element:

1. **Step 1** (line ~1361): Scan all `<children>` nodes for `loop="true"` attribute -- takes the **first** match only
2. **Step 2** (line ~1373): If still missing, check `elementParameter[@name="LOOPING_ELEMENT"]`
3. **Step 3** (line ~1389): If still missing, auto-detect by finding the deepest node in the input tree

### Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-XMP-001 | **P0** | **`lstrip('.', '/')` crashes with TypeError** (line 1413). Python's `str.lstrip()` accepts exactly one argument (a string of chars), not two. This call `xpath.strip().lstrip('.', '/')` raises `TypeError: lstrip expected at most 1 argument, got 2` at runtime. The XPath rewrite loop is dead code -- it will crash on the first expression with a non-empty value. The intended fix is `lstrip('./')` (single string argument). |
| CONV-XMP-002 | **P1** | **Registry alias mismatch**: Converter maps `tXMLMap` -> `TXMLMap` (line 98), but the engine registry only contains `XMLMap` and `tXMLMap` (engine.py lines 101-102). If the converter outputs `type: "TXMLMap"`, the engine will fail to instantiate the component with a "component not found" error. |
| CONV-XMP-003 | **P1** | **Only first output tree is mapped**: Expression building regex `outputTrees\.0/@nodes\.(\d+)` (line 1313) hardcodes index `0`. tXMLMap jobs with multiple output trees (e.g., main + reject + filter) will silently drop all expressions for non-primary outputs. |
| CONV-XMP-004 | **P1** | **Hardcoded root element names**: Root element removal at line 1338 is hardcoded to `['CMARGINSCLM', 'root']`. Any other root element name will be incorrectly included in the XPath, producing wrong paths like `./employees/employee/name` when it should be `./employee/name`. |
| CONV-XMP-005 | **P1** | **Ancestor XPath rewrite produces invalid paths**: When a field is "outside" the loop, the rewrite produces `./ancestor::full/path/to/field` (line 1441). This is not valid XPath. `./ancestor::` expects a single node name or node test, not a multi-segment path. For example, `./ancestor::employees/metadata/version` is syntactically wrong; valid forms would be `./ancestor::employees/metadata/version` only if `employees` is the ancestor axis target and `/metadata/version` is a relative continuation, which requires careful construction. |
| CONV-XMP-006 | **P2** | **Looping element auto-detect is unreliable**: The auto-detect fallback (line ~1389-1396) finds the deepest node in the input tree by path depth. However, `input_tree_nodes` values are tuples `(name, node_type, node_obj)`, not strings. The comparison `looping_element = name` assigns the tuple, not the name string. This produces a garbage looping element value. |
| CONV-XMP-007 | **P2** | **Expression filter not converted to Python**: The `expressionFilter` is extracted as a raw Java expression string (e.g., `row.status != null && row.status.equals("ACTIVE")`). The engine would need to evaluate this, but no Java-to-Python conversion is applied. The expression is stored but never usable. |
| CONV-XMP-008 | **P2** | **Pattern (date format) not extracted from schema columns**: The `pattern` attribute on schema columns (used for date formatting) is not extracted. Date-typed columns will have no formatting information. |
| CONV-XMP-009 | **P2** | **Only first looping element is used**: The children scan (line ~1361-1364) `break`s on the first `loop="true"` child found, using a flat search across all `<children>`. In complex trees with nested loops (e.g., tXMLMap with multiple looping paths), the first match may not be the correct one -- it depends on XML document order, which may not match the logical tree hierarchy. |
| CONV-XMP-010 | **P3** | **Debug print statements throughout**: The converter has ~15 `print()` statements (lines 1356, 1370, 1384, 1399, 1405, 1416, 1422, 1435, 1442, 1451, 1452). These will produce noisy output in production. Should use `logger.debug()`. |
| CONV-XMP-011 | **P3** | **`import re` inside function body**: The `import re` at line 1306 is inside the method body. While functional, it is non-standard and should be at module level per Python conventions. |

---

## 3. Engine Feature Parity Audit

### Feature Implementation Status

| Talend Feature | Implemented? | Fidelity | Notes |
|----------------|-------------|----------|-------|
| Parse XML from Document field | Yes | Medium | Reads first column of first row as XML string; does not validate Document type |
| Looping element iteration | Yes | Medium | Uses `.//{element}` XPath; cleaned up via `_clean_looping_element()` |
| XPath expression evaluation | Yes | Medium | Supports relative, absolute, descendant, ancestor paths via lxml |
| Namespace handling (default xmlns) | Yes | Medium | Default namespace remapped to `ns0` prefix |
| Namespace handling (prefixed) | Yes | Medium | Uses first prefix found in document |
| Namespace handling (xsi-only) | Yes | High | Correctly treats as unqualified |
| Namespace handling (no namespace) | Yes | High | Correctly uses empty prefix |
| Output schema column ordering | Yes | High | Ensures column order matches schema |
| Missing columns filled with empty string | Yes | High | `df[c] = ""` for missing columns |
| Statistics tracking (NB_LINE, NB_LINE_OK) | Yes | Medium | Always sets NB_LINE_REJECT = 0 |
| Expression cleaning (malformed Talend refs) | Yes | Low | Heuristic-based; many edge cases unhandled |
| Looping element cleaning | Yes | Low | Only handles 2-part paths; limited |
| Ancestor axis fallback | Yes | Low | Falls back to `//tail` from root; may return wrong nodes |
| Multi-result scoping | Yes | Low | Scopes by checking parent ancestry; heuristic approach |
| **Multiple input trees (lookup)** | **No** | **N/A** | **Only processes one input -- no lookup/join support** |
| **Multiple output trees** | **No** | **N/A** | **Only produces one "main" output** |
| **Join behavior (inner/outer)** | **No** | **N/A** | **No join implementation** |
| **Reject flow** | **No** | **N/A** | **No reject output; NB_LINE_REJECT always 0** |
| **Filter flow** | **No** | **N/A** | **No expression filter evaluation** |
| **Expression filter (Java)** | **No** | **N/A** | **expression_filter config is extracted but never consumed** |
| **Document output (All in One)** | **No** | **N/A** | **Cannot produce XML Document type output** |
| **Aggregate element** | **No** | **N/A** | **No aggregate grouping support** |
| **Multiple rows per Document** | **No** | **N/A** | **Only reads iloc[0,0]; multi-row Document input ignored** |
| **XPath predicates** | **Partial** | **Low** | **lxml supports them natively, but expression cleaning may corrupt predicate syntax** |
| **XPath functions (count, position, etc.)** | **Partial** | **Medium** | **lxml supports them, but qualify_step may incorrectly namespace-qualify function names** |
| **Die on error** | **No** | **N/A** | **Config key `die_on_error` is never read by engine** |
| **Keep order for document** | **No** | **N/A** | **Config key `keep_order` is never read by engine** |
| **Connection format** | **No** | **N/A** | **Config key `connection_format` is never read by engine** |
| **GlobalMap variable publication** | **No** | **N/A** | **Stats are tracked but never published to globalMap** |
| **Context variable resolution in expressions** | **No** | **N/A** | **No `${context.var}` resolution in XPath expressions** |

### Behavioral Differences from Talend

| ID | Priority | Difference |
|----|----------|------------|
| ENG-XMP-001 | **P0** | **No lookup/join support**: Talend's tXMLMap can join multiple input flows (main + lookups) with inner/outer join semantics. The engine processes only a single input DataFrame. Jobs using tXMLMap with lookup connections will silently lose the lookup data, producing incorrect output. |
| ENG-XMP-002 | **P0** | **Only first row, first column is processed**: The engine reads `input_data.iloc[0, 0]` (line 506), meaning it only processes the XML from the very first cell of the first column. If the input has multiple rows (each containing a different XML Document), only the first is processed. In Talend, tXMLMap processes each incoming row's Document field. |
| ENG-XMP-003 | **P1** | **No reject flow**: Talend produces reject rows for XML parsing failures, XPath errors, and expression filter rejections. The engine returns empty string for all errors (line 643) and hardcodes `NB_LINE_REJECT = 0` (line 708). Data quality pipelines relying on reject capture will miss all errors. |
| ENG-XMP-004 | **P1** | **No expression filter support**: The converter extracts `expression_filter` and `activate_expression_filter`, but the engine never reads these config keys. Rows that should be filtered/routed are always output. |
| ENG-XMP-005 | **P1** | **No Document output mode**: Talend's tXMLMap can produce XML Document output (useful for building XML from flat data). The engine only produces flat DataFrames. Jobs that chain tXMLMap -> tFileOutputXML via Document type will break. |
| ENG-XMP-006 | **P1** | **Die on error ignored**: The converter extracts `die_on_error`, but the engine never checks it. All XML parsing errors are silently swallowed (line 516-518), returning an empty DataFrame instead of raising an exception. |
| ENG-XMP-007 | **P1** | **GlobalMap variables not published**: Although `_update_stats()` is called, the stats are never written to `self.global_map`. Downstream components referencing `globalMap.get("tXMLMap_1_NB_LINE")` will get null. |
| ENG-XMP-008 | **P2** | **Namespace prefix selection is fragile**: When multiple named prefixes exist (e.g., `xmlns:ns1="..." xmlns:ns2="..."`), the engine uses `next(iter(nsmap.keys()))` (line 539), which picks the first prefix in iteration order. This is non-deterministic in Python < 3.7 and may pick the wrong prefix even in 3.7+ (depends on XML attribute order, which is not guaranteed). |
| ENG-XMP-009 | **P2** | **No multi-namespace support**: Only one namespace prefix is used for qualifying all XPath steps. XML documents with elements in different namespaces (e.g., SOAP envelopes with `soap:Envelope` and `app:Data`) cannot be correctly queried. |
| ENG-XMP-010 | **P2** | **Aggregate element not supported**: The "aggregate element" feature in Talend groups output rows into classified XML structures. Not implemented. |
| ENG-XMP-011 | **P2** | **No "All in One" mode**: The engine cannot aggregate all output rows into a single XML Document flow. |
| ENG-XMP-012 | **P3** | **Context variable resolution missing**: XPath expressions or file paths containing `${context.varName}` or `(String)globalMap.get("key")` are not resolved. |

---

## 4. Code Quality Audit

### Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-XMP-001 | **P0** | `component_parser.py` line 1413 | **`lstrip('.', '/')` raises TypeError at runtime.** Python's `str.lstrip()` accepts exactly one argument. The call `xpath.strip().lstrip('.', '/')` will crash with `TypeError: lstrip expected at most 1 argument, got 2` whenever the XPath rewrite loop is entered (i.e., whenever any expression has a non-empty value). This means the entire XPath normalization logic in the converter is dead code that crashes on first use. The entire tXMLMap converter pipeline will fail for any job with mapped columns. Fix: change to `lstrip('./')`. |
| BUG-XMP-002 | **P0** | `component_parser.py` line 98 vs `engine.py` lines 101-102 | **Registry alias mismatch.** The converter maps `tXMLMap` -> `TXMLMap`, but the engine registry only has `XMLMap` and `tXMLMap`. The converted JSON will contain `"type": "TXMLMap"`, which the engine cannot find, causing a "component type not registered" error. The engine will fail to instantiate the component. Fix: either change the converter alias to `XMLMap` or add `TXMLMap` to the engine registry. |
| BUG-XMP-003 | **P0** | `xml_map.py` line 506 | **Only first row is processed.** `xml_string = str(input_data.iloc[0, 0] or "")` reads only the first cell of the input DataFrame. If the upstream component produces multiple rows (each with its own XML Document in the first column), only the first row's XML is parsed. All other rows are silently discarded. In Talend, each incoming row is processed independently. This is a data loss bug for multi-row Document inputs. |
| BUG-XMP-004 | **P1** | `xml_map.py` line 498 | **`self.id` overwritten from config inside `_process()`.** Line 498 does `self.id = config.get("id", self.DEFAULT_COMPONENT_ID)`. The `self.id` was already set by `BaseComponent.__init__()` to `component_id`. Overwriting it inside `_process()` means the component ID changes mid-execution if the config has a different `id` value, which can cause confusing log messages and statistics misattribution. |
| BUG-XMP-005 | **P1** | `xml_map.py` line 526 | **`None in nsmap` check is redundant after normalization.** `normalize_nsmap()` (line 38-41) already removes `None` keys and remaps them to `ns0`. So the check at line 526 `if None in nsmap:` will never be `True`. The code path for Case 1 is dead code. The prefix selection always falls through to Case 3 or Case 4. |
| BUG-XMP-006 | **P1** | `xml_map.py` lines 647-665 | **Ancestor fallback produces incorrect results for multi-valued XPath.** When an ancestor XPath returns empty, the fallback rewrites `./ancestor::X/Y/Z` to `//Y/Z` from root (lines 652-653). The `//` search returns ALL matching nodes anywhere in the document, not just the ancestor. For XML with repeated structures, this can return nodes from unrelated branches, silently producing wrong data. |
| BUG-XMP-007 | **P1** | `component_parser.py` lines 1389-1396 | **Auto-detect looping element assigns a tuple, not a string.** `input_tree_nodes` values are tuples of `(name, node_type, node_obj)`. At line 1396, `looping_element = name` assigns the entire tuple to `looping_element` because the loop variable `name` shadows the outer scope and references the tuple from `input_tree_nodes.items()`. Specifically, the loop is `for path, name in input_tree_nodes.items():` where `name` is a tuple `(name_str, node_type, node_obj)`. This produces a garbage looping element like `('employee', 'ELEMENT', {...})`. |
| BUG-XMP-008 | **P2** | `xml_map.py` line 177 | **Double-prefix removal pattern is fragile.** `qexpr.replace(f"{ns_prefix}:{ns_prefix}:", f"{ns_prefix}:")` only handles exact double-prefix. Triple-prefix (from nested qualify calls) or other malformations are not caught. |
| BUG-XMP-009 | **P2** | `xml_map.py` line 670-673 | **Scoping logic checks wrong ancestry direction.** The scoping filter `parent in r.iterancestors()` checks if the loop node's parent is an ancestor of the result node. This means it keeps result nodes that are descendants of the loop's parent -- but this is the *opposite* of what scoping should do. It should keep results that are in the same subtree as the current loop node, not results that share the same grandparent. For deeply nested XML, this returns too many results. |
| BUG-XMP-010 | **P2** | `xml_map.py` lines 406-412 | **`_clean_expression` colon-slash heuristic is over-aggressive.** Any expression containing both `:` and `/` (including valid namespace-qualified XPaths like `ns:element/child`) will be transformed to `./{last_segment}`. This means `ns1:employees/ns1:employee/ns1:name` becomes `./name`, losing the full path. Valid XPath with namespaces is silently corrupted. |
| BUG-XMP-011 | **P2** | `xml_map.py` lines 415-421 | **`_clean_expression` dot heuristic mishandles XPath with predicates.** Any expression with a `.` that does not start with `./` is treated as `row.field` notation. But XPath expressions like `employee[position()=1]` contain `.` (in `position`) and would be mishandled. Although unlikely due to the ordering of conditionals, the logic is brittle. |

### Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-XMP-001 | **P2** | Config key `INPUT_TREES` uses UPPER_CASE while other keys use `snake_case` (e.g., `die_on_error`, `keep_order`). Inconsistent with project naming conventions. Same for `OUTPUT_TREES` and `CONNECTIONS`. |
| NAME-XMP-002 | **P2** | Converter alias `TXMLMap` does not match engine alias `XMLMap`. The `T` prefix convention is used nowhere else in the codebase (other components use `tMap`->`Map`, `tFilterRows`->`FilterRows`). |
| NAME-XMP-003 | **P3** | Constants `AXES` and `DEFAULT_NAMESPACE_PREFIX` are defined at module level but `DEFAULT_LOOPING_ELEMENT` (line 21) is defined but never used. Dead constant. |

### Standards Compliance

| ID | Priority | Issue |
|----|----------|-------|
| STD-XMP-001 | **P1** | **Massive print() pollution**: The engine file `xml_map.py` contains **28 print() statements** (lines 501-502, 508, 514, 517, 523-524, 530, 534-536, 541, 546, 550-551, 563, 570-571, 576-577, 591, 600-601, 605, 613-615, 627-631, 638, 643, 655, 664, 682-683, 691-692, 696, 713-715). The project STANDARDS.md explicitly states: "No `print()` statements" (checklist item). All should be replaced with `logger.debug()` or `logger.info()`. |
| STD-XMP-002 | **P1** | **print() in converter**: The converter's `parse_t_xml_map()` method contains **15 print() statements** (lines 1356, 1370, 1384, 1399, 1405, 1416, 1422, 1435, 1442, 1451, 1452). Same STANDARDS.md violation. |
| STD-XMP-003 | **P2** | **Typo in debug message**: Line 213 has `"Parent Vaue"` instead of `"Parent Value"`. |
| STD-XMP-004 | **P2** | **`_validate_config()` does not validate all config keys**: The method validates `output_schema`, `expressions`, and `looping_element` but ignores `die_on_error`, `keep_order`, `connection_format`, `expression_filter`, `INPUT_TREES`, `OUTPUT_TREES`, `CONNECTIONS`. STANDARDS.md requires validation of all config parameters. |
| STD-XMP-005 | **P2** | **Inconsistent method naming**: `validate_config()` (public, line 719) wraps `_validate_config()` (private, line 341). The public method is redundant and breaks the convention of having only `_validate_config()` as the standard validation interface per BaseComponent. |
| STD-XMP-006 | **P3** | **No type hints on helper functions at module level**: `normalize_nsmap()`, `split_steps()`, `qualify_step()`, `qualify_xpath()`, `choose_context()`, `extract_value()`, and `_broaden_ancestor_if_empty()` are all module-level functions without full return type annotations (some have them, but `extract_value` and `_broaden_ancestor_if_empty` do not). |

### Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-XMP-001 | **P1** | **28 `print()` statements in engine file**: See STD-XMP-001 above. These produce massive console output in production, potentially impacting performance for large XML documents with many loop nodes (each node triggers 6+ print calls per expression evaluation). For a document with 10,000 loop nodes and 10 output columns, this is ~160,000 print() calls. |
| DBG-XMP-002 | **P1** | **15 `print()` statements in converter**: See STD-XMP-002 above. |
| DBG-XMP-003 | **P2** | **`[TRACE]` and `[DEBUG]` prefix in print statements**: These mimic logging levels but bypass the logging framework entirely. Cannot be filtered, redirected, or disabled via logging configuration. |
| DBG-XMP-004 | **P2** | **Full parent chain logged per loop node** (line 615): `[p.tag for p in loop_node.iterancestors()]` iterates all ancestors and prints their tags. For deeply nested XML (e.g., SOAP envelopes with 10+ levels), this produces long noisy output per row. |
| DBG-XMP-005 | **P3** | **Sample result truncation in trace** (line 638): `[str(r)[:50] for r in ...]` truncates to 50 chars. For debugging namespace issues, this may cut off the crucial namespace URI portion of element tags. |

### Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-XMP-001 | **P2** | **No XML bomb protection**: `ET.fromstring()` (line 512) is called with the default lxml parser, which is vulnerable to XML entity expansion attacks (billion laughs attack). If the XML input comes from an untrusted source, a malicious document could cause memory exhaustion. Mitigation: use `lxml.etree.XMLParser(resolve_entities=False, huge_tree=False)` or `defusedxml`. |
| SEC-XMP-002 | **P3** | **XPath injection risk**: XPath expressions from config are used directly in `ctx.xpath(expr_q, ...)` (line 635). If config is constructed from untrusted user input, XPath injection could extract unintended data. Low risk since config typically comes from Talend job export, but noted for defense-in-depth. |

---

## 5. Performance & Memory Audit

| ID | Priority | Issue |
|----|----------|-------|
| PERF-XMP-001 | **P1** | **O(N*M) print() calls for large XML**: For each of N loop nodes and M output columns, the engine executes 6+ print() calls (lines 613-615, 627-631, 638). For a document with 10,000 loop nodes and 10 output columns, this is ~160,000 synchronous print() calls with `flush=True`, which forces a system call per print. This can be the dominant cost for medium-sized XML documents. |
| PERF-XMP-002 | **P2** | **Full ancestor chain iteration per loop node** (line 615): `[p.tag for p in loop_node.iterancestors()]` traverses the full ancestor chain for every loop node purely for debug output. For a flat list of 10,000 sibling nodes under a root, this is O(10,000 * tree_depth) just for print statements. |
| PERF-XMP-003 | **P2** | **Redundant XPath evaluation in ancestor fallback**: When the initial XPath returns empty for ancestor expressions (lines 647-665), the fallback re-evaluates a broadened XPath from the root. This doubles the XPath evaluation cost for every ancestor-axis expression that misses. Additionally, `_broaden_ancestor_if_empty()` (line 255) performs yet another fallback attempt, creating a triple-evaluation pattern. |
| PERF-XMP-004 | **P3** | **No XML caching between rows**: The engine parses XML from scratch for each input row (if multi-row support is added). Since only one row is processed currently, this is not an active issue, but will become one if BUG-XMP-003 is fixed. Parsed XML trees should be cached. |

---

## 6. Testing Audit

| ID | Priority | Issue |
|----|----------|-------|
| TEST-XMP-001 | **P0** | **Zero unit tests exist for XMLMap engine component.** No test file found for `xml_map.py` in the test suite. This is a complex component with XPath evaluation, namespace handling, and multiple fallback mechanisms -- all untested. |
| TEST-XMP-002 | **P1** | **Zero unit tests for `parse_t_xml_map()` converter method.** The converter's recursive tree parsing, expression building, looping element detection, and XPath rewrite logic are all untested. The `lstrip` crash bug (BUG-XMP-001) would have been caught by even basic smoke testing. |

### Recommended Test Cases

#### Engine Tests (xml_map.py)

| Test | Priority | Description |
|------|----------|-------------|
| Basic XML extraction | P0 | Parse simple XML with looping element, verify correct row count and field values |
| Namespace handling (default xmlns) | P0 | Parse XML with `xmlns="..."`, verify namespace-qualified XPath works |
| Namespace handling (prefixed) | P0 | Parse XML with `xmlns:ns="..."`, verify prefix-qualified XPath works |
| No namespace XML | P0 | Parse plain XML without namespaces, verify unqualified XPath works |
| Empty input handling | P0 | Pass None, empty DataFrame, verify graceful empty return |
| Invalid XML handling | P0 | Pass malformed XML string, verify no crash and empty return |
| Looping element produces correct row count | P0 | Verify each occurrence of loop element produces exactly one row |
| Multiple loop nodes with ancestor access | P1 | Verify ancestor-axis expressions return correct values per loop node |
| Attribute extraction (@attr) | P1 | Verify `@attribute` XPath syntax extracts attribute values |
| XPath text() function | P1 | Verify `text()` returns element text content |
| Relative path extraction (./) | P1 | Verify `./child/grandchild` resolves relative to loop node |
| Absolute path extraction (/) | P1 | Verify `/root/element` resolves from document root |
| Descendant path (//) | P1 | Verify `//element` searches all descendants |
| Missing column in expressions | P1 | Column in schema but not in expressions, verify empty string |
| Expression cleaning: bracket removal | P1 | Verify `[row1.employee:/employees/employee/id]` cleans correctly |
| Expression cleaning: dot notation | P1 | Verify `row1.field_name` becomes `./field_name` |
| Looping element cleaning: root prefix | P1 | Verify `employees/employee` with root=`employees` becomes `employee` |
| Multi-namespace XML | P2 | Parse XML with multiple namespace prefixes, verify correct extraction |
| Large XML (10K+ nodes) | P2 | Verify performance and correctness with large documents |
| XPath returning multiple results | P2 | Verify first result is used when multiple nodes match |
| xsi-only namespace | P2 | Parse XML with only `xmlns:xsi="..."`, verify no namespace qualification |
| Ancestor fallback correctness | P2 | Verify fallback `//` search returns correct ancestor data |
| Output column ordering | P2 | Verify DataFrame columns match schema order exactly |
| Statistics tracking | P2 | Verify NB_LINE and NB_LINE_OK are set correctly |

#### Converter Tests (parse_t_xml_map)

| Test | Priority | Description |
|------|----------|-------------|
| Basic tree parsing | P0 | Parse simple tXMLMap nodeData, verify input/output trees correct |
| Recursive children parsing | P0 | Parse nested children 3+ levels deep, verify all captured |
| Connection mapping to expressions | P0 | Verify connections produce correct XPath expressions |
| Looping element from loop attribute | P0 | Verify `loop="true"` child is detected correctly |
| Output schema extraction | P0 | Verify FLOW metadata columns are correctly extracted |
| Attribute node handling | P1 | Verify `nodeType="ATTRIBUT"` produces `@attribute` XPath |
| Expression filter extraction | P1 | Verify `expressionFilter` and `activateExpressionFilter` are captured |
| lstrip fix verification | P1 | After fixing BUG-XMP-001, verify XPath stripping works correctly |
| Multiple input trees | P2 | Verify matchingMode and lookupMode are captured per tree |
| Empty nodeData | P2 | Verify graceful handling when nodeData is missing |

---

## 7. Issues Summary

### All Issues by Priority

#### P0 -- Critical (6 issues)

| ID | Category | Summary |
|----|----------|---------|
| BUG-XMP-001 | Converter Bug | `lstrip('.', '/')` crashes with TypeError -- XPath rewrite is completely broken |
| BUG-XMP-002 | Converter Bug | Registry alias mismatch: converter outputs `TXMLMap`, engine expects `XMLMap` -- component cannot be instantiated |
| BUG-XMP-003 | Engine Bug | Only first row processed -- multi-row Document input silently loses all rows after the first |
| CONV-XMP-001 | Converter Bug | Same as BUG-XMP-001 (lstrip crash) |
| ENG-XMP-001 | Feature Gap | No lookup/join support -- tXMLMap jobs with lookup connections produce incorrect output |
| TEST-XMP-001 | Testing | Zero unit tests for XMLMap engine component |

#### P1 -- Major (14 issues)

| ID | Category | Summary |
|----|----------|---------|
| BUG-XMP-004 | Engine Bug | `self.id` overwritten from config inside `_process()` |
| BUG-XMP-005 | Engine Bug | Dead code: `None in nsmap` check after normalization removes None keys |
| BUG-XMP-006 | Engine Bug | Ancestor fallback `//tail` produces incorrect results from wrong document branches |
| BUG-XMP-007 | Converter Bug | Auto-detect looping element assigns tuple instead of string |
| CONV-XMP-002 | Converter | Registry alias mismatch (`TXMLMap` vs `XMLMap`) |
| CONV-XMP-003 | Converter | Only first output tree is mapped -- multi-output jobs lose expressions |
| CONV-XMP-004 | Converter | Hardcoded root element names (`CMARGINSCLM`, `root`) |
| CONV-XMP-005 | Converter | Ancestor XPath rewrite produces invalid multi-segment `./ancestor::a/b/c` paths |
| ENG-XMP-002 | Feature Gap | Only first row, first column is processed (iloc[0,0]) |
| ENG-XMP-003 | Feature Gap | No reject flow -- all errors silently produce empty strings |
| ENG-XMP-004 | Feature Gap | No expression filter support -- config extracted but never consumed |
| ENG-XMP-005 | Feature Gap | No Document output mode |
| ENG-XMP-006 | Feature Gap | Die on error config ignored -- errors always silently swallowed |
| ENG-XMP-007 | Feature Gap | GlobalMap variables not published |
| STD-XMP-001 | Standards | 28 print() statements in engine file (STANDARDS.md violation) |
| STD-XMP-002 | Standards | 15 print() statements in converter (STANDARDS.md violation) |
| PERF-XMP-001 | Performance | O(N*M) flush=True print() calls dominate processing time |
| TEST-XMP-002 | Testing | Zero unit tests for converter's parse_t_xml_map() method |

#### P2 -- Moderate (16 issues)

| ID | Category | Summary |
|----|----------|---------|
| BUG-XMP-008 | Engine Bug | Double-prefix removal pattern is fragile -- misses triple-prefix |
| BUG-XMP-009 | Engine Bug | Scoping logic checks wrong ancestry direction for multi-result filtering |
| BUG-XMP-010 | Engine Bug | Expression cleaning colon-slash heuristic corrupts namespace-qualified XPath |
| BUG-XMP-011 | Engine Bug | Expression cleaning dot heuristic may mishandle XPath with predicates |
| CONV-XMP-006 | Converter | Auto-detect looping element picks deepest node unreliably (tuple assignment) |
| CONV-XMP-007 | Converter | Expression filter stored as raw Java -- no Python conversion |
| CONV-XMP-008 | Converter | Date pattern not extracted from schema columns |
| CONV-XMP-009 | Converter | Only first `loop="true"` child found -- may pick wrong loop in complex trees |
| ENG-XMP-008 | Feature Gap | Namespace prefix selection is fragile with multiple named prefixes |
| ENG-XMP-009 | Feature Gap | No multi-namespace support -- single prefix for all XPath steps |
| ENG-XMP-010 | Feature Gap | Aggregate element not supported |
| ENG-XMP-011 | Feature Gap | No "All in One" mode for XML Document aggregation |
| NAME-XMP-001 | Naming | UPPER_CASE config keys (INPUT_TREES, OUTPUT_TREES, CONNECTIONS) inconsistent with snake_case |
| NAME-XMP-002 | Naming | Converter alias `TXMLMap` inconsistent with engine alias `XMLMap` |
| SEC-XMP-001 | Security | No XML bomb protection (entity expansion attack via lxml defaults) |
| STD-XMP-003 | Standards | Typo "Parent Vaue" -> "Parent Value" (line 213) |
| STD-XMP-004 | Standards | `_validate_config()` does not validate all config keys |
| STD-XMP-005 | Standards | Redundant public `validate_config()` wrapping private `_validate_config()` |
| PERF-XMP-002 | Performance | Full ancestor chain iteration per loop node for debug output |
| PERF-XMP-003 | Performance | Redundant triple-evaluation for ancestor XPath fallback |
| DBG-XMP-003 | Debug | `[TRACE]`/`[DEBUG]` prefixes bypass logging framework |
| DBG-XMP-004 | Debug | Full parent chain logged per loop node -- noisy for deep XML |

#### P3 -- Low (8 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-XMP-010 | Converter | 15 debug print statements in converter method |
| CONV-XMP-011 | Converter | `import re` inside method body instead of module level |
| ENG-XMP-012 | Feature Gap | Context variable resolution missing in expressions |
| NAME-XMP-003 | Naming | `DEFAULT_LOOPING_ELEMENT` constant defined but never used |
| STD-XMP-006 | Standards | Missing return type annotations on module-level helper functions |
| SEC-XMP-002 | Security | XPath injection risk from untrusted config |
| PERF-XMP-004 | Performance | No XML caching between rows (latent, not active) |
| DBG-XMP-005 | Debug | Sample result truncation to 50 chars may hide namespace info |

---

## 8. Architecture Assessment

### Data Flow Analysis

```
Talend Job (.item XML)
       |
       v
  [Converter: parse_t_xml_map()]
       |
       | Parses: inputTrees, outputTrees, connections, metadata
       | Builds: expressions dict, looping_element, output_schema
       | BUG: lstrip crash (P0), alias mismatch (P0)
       |
       v
  [Converted JSON Config]
       |
       | Contains: type="TXMLMap" (WRONG), expressions, looping_element,
       |           output_schema, INPUT_TREES, OUTPUT_TREES, etc.
       |
       v
  [Engine Registry Lookup]
       |
       | FAILS: "TXMLMap" not in registry (P0)
       | Would need: "XMLMap" or "tXMLMap"
       |
       v
  [XMLMap._process()]
       |
       | 1. Read XML from iloc[0,0] (only first row)
       | 2. Parse XML with lxml
       | 3. Normalize namespace map
       | 4. Clean expressions (heuristic, lossy)
       | 5. Clean looping element
       | 6. Build loop XPath, find loop nodes
       | 7. For each loop node:
       |    a. For each output column:
       |       - Qualify XPath with namespace
       |       - Choose context (root vs loop node)
       |       - Evaluate XPath
       |       - Apply ancestor fallback if empty
       |       - Apply multi-result scoping
       |       - Extract value
       |    b. Append row
       | 8. Build DataFrame, reorder columns
       | 9. Update stats (not published to globalMap)
       |
       v
  [Output DataFrame]
       |
       | Single "main" output only
       | No reject, no filter, no Document output
```

### Dependency Chain Risks

1. **Converter -> Engine handoff is broken** (BUG-XMP-001 + BUG-XMP-002): Even if the converter crash is fixed, the alias mismatch prevents engine instantiation. Both bugs must be fixed simultaneously.

2. **Expression pipeline is multi-stage and lossy**:
   - Converter builds XPath from connection paths (may miss nodes)
   - Converter rewrites XPath based on loop position (crashes)
   - Engine cleans expressions again with heuristics (may corrupt valid XPath)
   - Engine qualifies with namespace (may double-prefix)
   - Net result: an expression may be transformed 4 times, each stage potentially introducing errors

3. **Namespace handling is single-prefix**: The architecture assumes one namespace prefix fits all. This breaks for multi-namespace documents (SOAP, XBRL, SVG+MathML, etc.).

---

## 9. Comparison with Related Components

### XMLMap vs Map (tMap)

| Aspect | XMLMap | Map |
|--------|--------|-----|
| Input type | XML Document (single cell) | Flat DataFrame rows |
| Expression language | XPath | Python/Java expressions |
| Lookup support | Not implemented | Implemented (inner/left join) |
| Reject flow | Not implemented | Implemented |
| Expression filter | Not implemented | Implemented |
| Multi-row processing | Only first row | All rows |
| Namespace handling | Complex, fragile | N/A |
| GlobalMap publication | Not implemented | Implemented |

### XMLMap vs FileInputXML (tFileInputXML)

| Aspect | XMLMap | FileInputXML |
|--------|--------|--------------|
| Input source | DataFrame cell | File path |
| Purpose | Transform XML-in-flow | Read XML file |
| Loop XPath | Configured per component | `LOOP_QUERY` parameter |
| Mapping XPath | Expression dict | `MAPPING` entries |
| Namespace handling | Auto-detect + qualify | `IGNORE_NS` flag |

---

## 10. Recommendations

### Immediate (Before Production) -- Sprint 1

These issues **must** be resolved before any tXMLMap job can run:

1. **Fix BUG-XMP-001**: Change `lstrip('.', '/')` to `lstrip('./')` on line 1413 of `component_parser.py`. This is a one-character fix that unblocks the entire converter pipeline.

2. **Fix BUG-XMP-002**: Change the converter alias from `'tXMLMap': 'TXMLMap'` to `'tXMLMap': 'XMLMap'` on line 98 of `component_parser.py`, OR add `'TXMLMap': XMLMap` to the engine registry in `engine.py`.

3. **Fix BUG-XMP-003**: Replace `xml_string = str(input_data.iloc[0, 0] or "")` with a loop that processes each row in the input DataFrame. Accumulate results across all rows.

4. **Remove all print() statements**: Replace all 28 print() calls in `xml_map.py` and all 15 in `parse_t_xml_map()` with appropriate `logger.debug()` or `logger.info()` calls. This is both a standards violation and a performance concern.

5. **Create basic unit tests**: At minimum, test:
   - Simple XML extraction with looping element
   - Namespace handling (default, prefixed, none)
   - Empty/null input handling
   - Converter tree parsing roundtrip

### Short-Term (Hardening) -- Sprint 2

6. **Fix BUG-XMP-005**: Remove the dead `None in nsmap` check and correct the namespace prefix selection logic.

7. **Fix BUG-XMP-006**: Replace the ancestor fallback with a correct XPath that respects document structure (use `ancestor-or-self::` with proper context instead of `//` from root).

8. **Fix BUG-XMP-007**: Change line 1396 from `looping_element = name` to `looping_element = name[0]` (extract the string from the tuple).

9. **Fix CONV-XMP-004**: Replace hardcoded root names with dynamic detection using the actual XML root element from the input tree's first node.

10. **Fix CONV-XMP-005**: Generate valid ancestor XPath by separating the ancestor axis target from the continuation path (e.g., `./ancestor::parentElement/child` instead of `./ancestor::parent/child/grandchild`).

11. **Implement die_on_error**: Read the `die_on_error` config key and either raise an exception or return empty DataFrame accordingly.

12. **Implement GlobalMap publication**: After `_update_stats()`, write stats to `self.global_map` using the `{component_id}_NB_LINE` key pattern.

13. **Add XML bomb protection**: Use `lxml.etree.XMLParser(resolve_entities=False)` or `defusedxml.lxml`.

### Medium-Term (Feature Parity) -- Sprint 3-4

14. **Implement reject flow**: Create a reject output for XML parsing errors, XPath evaluation failures, and expression filter rejections. Include `errorCode` and `errorMessage` columns.

15. **Implement expression filter**: Convert Java expression filters to Python (or evaluate via the Java bridge) and apply them to filter/route output rows.

16. **Implement lookup/join**: Support multiple input DataFrames with inner join and left outer join semantics, matching Talend's `matchingMode` options.

17. **Implement Document output mode**: Support producing XML Document type output for downstream tFileOutputXML consumption.

18. **Implement multi-namespace support**: Support multiple namespace prefixes in XPath qualification, not just a single prefix.

19. **Fix expression cleaning**: Replace heuristic-based `_clean_expression()` with a proper parser that understands Talend's expression syntax, distinguishing between `row.field` references and valid XPath expressions.

### Long-Term (Optimization) -- Sprint 5+

20. **Implement "All in One" mode**: Aggregate all output rows into a single XML Document.

21. **Implement aggregate element**: Support the aggregate grouping feature for classified XML output.

22. **Add XML caching**: Cache parsed XML trees for multi-row processing to avoid re-parsing.

23. **Support multiple output trees**: Extend the converter and engine to handle multi-output-tree configurations.

24. **Implement context variable resolution**: Resolve `${context.varName}` and `globalMap.get()` references in XPath expressions.

---

## Appendix A: File Reference

| File | Path | Purpose |
|------|------|---------|
| Engine component | `src/v1/engine/components/transform/xml_map.py` | XMLMap class and XPath helper functions |
| Converter parser | `src/converters/complex_converter/component_parser.py` | `parse_t_xml_map()` method (line ~1155) |
| Converter dispatch | `src/converters/complex_converter/converter.py` | Dispatch to `parse_t_xml_map()` (line ~266) |
| Engine registry | `src/v1/engine/engine.py` | `XMLMap` and `tXMLMap` registration (lines 101-102) |
| Transform __init__ | `src/v1/engine/components/transform/__init__.py` | `XMLMap` export (line 28) |
| Base component | `src/v1/engine/base_component.py` | `BaseComponent` ABC with stats tracking |
| Project standards | `docs/v1/STANDARDS.md` | Logging, naming, and code structure standards |

---

## Appendix B: Talend Reference Links

- [tXMLMap -- Docs for ESB 7.x -- Talend Skill](https://talendskill.com/talend-for-esb-docs/docs-7-x/txmlmap-talend-open-studio-for-esb-document-7-x/)
- [tXMLMap operation -- Talend Studio Help](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-10/txmlmap-operation)
- [Configuring the input flow -- Talend Components Help](https://help.qlik.com/talend/en-US/components/8.0/txmlmap/txmlmap-tfileinputxml-tlogrow-tlogrow-configuring-input-flow-standard-component)
- [Configuring tXMLMap with multiple loops -- Talend Components Help](https://help.qlik.com/talend/en-US/components/8.0/txmlmap/txmlmap-tfileinputxml-tlogrow-tfileoutputxml-configuring-txmlmap-with-multiple-loops-standard-component)
- [Aggregating the output data -- Talend Studio Help](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-12/aggregating-output-data)
- [tXMLMap Standard properties -- Talend Components Help](https://help.talend.com/r/en-US/7.3/txmlmap/txmlmap-standard-properties)
- [Looping Multiple Tags in tXMLMAP -- Perficient](https://blogs.perficient.com/2021/05/24/looping-multiple-tags-in-txmlmap-component-using-talend/)
- [Looping Simple XML Tags using tXMLMap -- Perficient](https://blogs.perficient.com/2021/05/17/looping-simple-xml-tags-using-txmlmap-in-talend/)
- [Using tXMLMap to read XML -- O'Reilly](https://www.oreilly.com/library/view/talend-open-studio/9781782167266/ch09s02.html)
- [Using tXMLMap to create an XML document -- O'Reilly](https://www.oreilly.com/library/view/talend-open-studio/9781782167266/ch09s03.html)
- [Using a globalMap variable in a map -- Talend Help](https://help.talend.com/en-US/data-mapper-functions-reference-guide/7.3/using-globalmap-variable-in-map)

---

## Appendix C: Code Snippets for Critical Bugs

### BUG-XMP-001: lstrip TypeError (P0)

File: `src/converters/complex_converter/component_parser.py`, line 1413

```python
# CURRENT (crashes):
xpath = xpath.strip().lstrip('.', '/')
# TypeError: lstrip expected at most 1 argument, got 2

# FIX:
xpath = xpath.strip().lstrip('./')
```

### BUG-XMP-002: Registry Alias Mismatch (P0)

File: `src/converters/complex_converter/component_parser.py`, line 98

```python
# CURRENT (wrong alias):
'tXMLMap': 'TXMLMap',

# FIX (match engine registry):
'tXMLMap': 'XMLMap',
```

Engine registry (`src/v1/engine/engine.py`, lines 101-102) expects:
```python
'XMLMap': XMLMap,
'tXMLMap': XMLMap,
```

### BUG-XMP-003: Only First Row Processed (P0)

File: `src/v1/engine/components/transform/xml_map.py`, line 506

```python
# CURRENT (only first row):
xml_col = input_data.columns[0]
xml_string = str(input_data.iloc[0, 0] or "")

# FIX (process all rows):
xml_col = input_data.columns[0]
all_rows = []
for row_idx in range(len(input_data)):
    xml_string = str(input_data.iloc[row_idx, 0] or "")
    # ... process each XML and accumulate rows ...
all_rows.extend(rows)
```

### BUG-XMP-005: Dead Code After Normalization

File: `src/v1/engine/components/transform/xml_map.py`, lines 526-529

```python
# normalize_nsmap() already removes None keys (line 38-41):
def normalize_nsmap(root):
    nsmap = dict(root.nsmap or {})
    if None in nsmap:
        nsmap[DEFAULT_NAMESPACE_PREFIX] = nsmap.pop(None)  # Removes None
    nsmap = {k: v for k, v in nsmap.items() if k is not None}  # Double-removes None
    return nsmap

# Therefore this check in _process() is dead code:
if None in nsmap:  # <-- NEVER TRUE after normalize_nsmap()
    ns_prefix = DEFAULT_NAMESPACE_PREFIX
```

The ns0 prefix IS set correctly by `normalize_nsmap()`, but the detection logic in `_process()` is checking the wrong condition. The prefix is set as a key `"ns0"` in nsmap, not detected via the `None in nsmap` branch. The correct check should be:

```python
if DEFAULT_NAMESPACE_PREFIX in nsmap:
    ns_prefix = DEFAULT_NAMESPACE_PREFIX
```

---

## Appendix D: Issue Count Summary

| Category | P0 | P1 | P2 | P3 | Total |
|----------|----|----|----|----|-------|
| Converter Bugs | 2 | 4 | 4 | 2 | 12 |
| Engine Bugs | 1 | 3 | 4 | 0 | 8 |
| Feature Gaps | 1 | 6 | 4 | 1 | 12 |
| Standards | 0 | 2 | 3 | 1 | 6 |
| Performance | 0 | 1 | 2 | 1 | 4 |
| Testing | 1 | 1 | 0 | 0 | 2 |
| Naming | 0 | 0 | 2 | 1 | 3 |
| Security | 0 | 0 | 1 | 1 | 2 |
| Debug | 0 | 0 | 2 | 1 | 3 |
| **Total** | **5** | **17** | **22** | **8** | **52** |

**Overall Assessment: NOT PRODUCTION READY**

The tXMLMap/XMLMap component has **5 P0 critical issues** that prevent it from functioning at all:
- The converter crashes on every tXMLMap job (lstrip bug)
- The registry alias mismatch prevents engine instantiation
- Only the first row of multi-row input is processed

Even after P0 fixes, the component lacks fundamental Talend features (lookup/join, reject flow, expression filter, Document output) that are commonly used in production tXMLMap jobs. Significant development effort is required before this component can be considered production-ready.
