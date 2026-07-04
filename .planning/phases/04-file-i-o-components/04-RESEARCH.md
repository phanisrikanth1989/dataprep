# Phase 4: File I/O Components - Research

**Researched:** 2026-04-15
**Domain:** Engine component rewrite -- tFileInputDelimited and tFileOutputDelimited with Talend feature parity
**Confidence:** HIGH

## Summary

Phase 4 rewrites both file I/O delimited components from scratch to achieve Talend feature parity, conforming to the ENGINE_COMPONENT_PATTERN.md blueprint established in Phase 1 and using the decorator-based ComponentRegistry from Phase 3. The current implementations (574 lines input, 472 lines output) read wrong config keys, use wrong defaults, have no REJECT flow, and are missing multiple Talend features. The rewrite is straightforward because the infrastructure is solid -- BaseComponent lifecycle (validate -> snapshot -> resolve -> process -> stats), OutputRouter for REJECT flow routing, and GlobalMap for stats are all available and tested from Phases 1 and 3.

The core technical challenge is implementing per-row validation with REJECT routing in the input component. Each row must be checked for field count (CHECK_FIELDS_NUM), type conversion failures, and date pattern validity (CHECK_DATE), with failing rows routed to a reject DataFrame that includes errorCode and errorMessage columns matching Talend's behavior. The output component is simpler but adds FILE_EXIST_EXCEPTION (default true -- prevents accidental overwrites) and SPLIT/SPLIT_EVERY (multi-file output with Talend's `basename0.ext`, `basename1.ext` naming convention).

**Primary recommendation:** Read config keys directly from converter output (no mapping layer), use Talend defaults, implement row-level validation with reject routing using pandas operations for performance, and rely on Python's csv module for RFC4180 compliance when CSV_OPTION is enabled.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full rewrite from scratch for both components. Not patching existing code. Conform to ENGINE_COMPONENT_PATTERN.md blueprint.
- **D-02:** Add `@REGISTRY.register('tFileInputDelimited')` and `@REGISTRY.register('tFileOutputDelimited')` decorators per Phase 3 D-04.
- **D-03:** Focus on Talend feature parity based on audit reports and Talend _java.xml parameter definitions, not on what the current engine code happens to support.
- **D-04:** Engine reads converter config keys directly -- `fieldseparator` (not `delimiter`), `remove_empty_row` (not `remove_empty_rows`), `header_rows`, `footer_rows`, etc. No mapping layer, no dual-key support. Clean 1:1 match with converter output.
- **D-05:** Engine defaults match Talend defaults: `encoding='ISO-8859-15'`, `fieldseparator=';'`, `include_header=False`, `remove_empty_row=True`, `die_on_error=False`, `file_exist_exception=True`, `create_directory=True`.
- **D-06:** Three rejection triggers: wrong field count (CHECK_FIELDS_NUM), type conversion failure, date pattern validation (CHECK_DATE).
- **D-07:** Reject row contains all original columns plus `errorCode` (string) and `errorMessage` (string).
- **D-08:** NB_LINE_REJECT globalMap variable tracks reject count accurately.
- **D-09 through D-15:** tFileInputDelimited in-scope features (core, CSV_OPTION, TRIMSELECT, CHECK_FIELDS_NUM, CHECK_DATE, csv_row_separator, globalMap vars).
- **D-16 through D-20:** tFileOutputDelimited in-scope features (core, FILE_EXIST_EXCEPTION, SPLIT/SPLIT_EVERY, OS_LINE_SEPARATOR, globalMap vars).
- **D-21:** Deferred features (UNCOMPRESS, COMPRESS, RANDOM, DECODE, ADVANCED_SEPARATOR, SPLIT_RECORD, USESTREAM, ROW_MODE, FLUSHONROW) -- log warning if config flag set, proceed silently.
- **D-22:** Tests use `tmp_path` for programmatic file creation. Small fixture directory at `tests/v1/engine/fixtures/file/` for edge cases.
- **D-23:** All file paths constructed via `pathlib.Path` -- no hardcoded OS-specific paths.
- **D-24:** Exhaustive test coverage per requirement. Target ~80-120 tests.
- **D-25:** Include a few integration tests using real converter JSON output.
- **D-26:** Test location: `tests/v1/engine/components/file/test_file_input_delimited.py` and `test_file_output_delimited.py`.

### Claude's Discretion
- Internal method decomposition and helper design within each component
- Exact streaming threshold and chunk size (can follow BaseComponent defaults)
- How to handle single-string read mode (empty delimiter/separator edge case)
- Talend split file naming convention (determined during research -- see findings below)
- Whether CSV_OPTION implementation uses Python's csv module, pandas csv params, or a hybrid

### Deferred Ideas (OUT OF SCOPE)
- UNCOMPRESS / COMPRESS -- compressed file I/O (future work)
- RANDOM / NB_RANDOM -- random line sampling (future work)
- ENABLE_DECODE / DECODE_COLS -- hex/octal decoding (future work)
- ADVANCED_SEPARATOR / THOUSANDS_SEPARATOR / DECIMAL_SEPARATOR -- numeric formatting (future work)
- SPLIT_RECORD -- multi-line field support (future work)
- USESTREAM / ROW_MODE / FLUSHONROW -- Java-specific buffer/stream concepts (future work)
</user_constraints>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.10+ engine, pandas for DataFrame operations [VERIFIED: pyproject.toml]
- **Compatibility**: Must produce identical output to Talend for same input data and job configuration
- **No breaking changes**: Converter JSON format remains compatible -- engine changes read converter output keys directly
- **Existing patterns**: Must conform to ENGINE_COMPONENT_PATTERN.md blueprint (ABC + registry + per-component)
- **Naming**: snake_case for files/functions, PascalCase for classes, `@REGISTRY.register` decorators
- **Logging**: `logger = logging.getLogger(__name__)`, no print(), no emojis/unicode
- **Error handling**: Custom exception hierarchy (ConfigurationError, FileOperationError, DataValidationError)
- **Docstrings**: Google-style with Args/Returns/Raises
- **Imports**: Relative imports within package (`from ...base_component import BaseComponent`)
- **No `requirements.txt`**: Dependencies managed via `pyproject.toml` [VERIFIED: pyproject.toml exists]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FILD-01 | Fix config key mismatch -- engine reads converter's `fieldseparator` key directly | Config key alignment table in Architecture Patterns; converter outputs verified from sample JSON |
| FILD-02 | Fix encoding default -- honor ISO-8859-15 from config | Default value mapping in Architecture Patterns; Talend _java.xml confirmed default |
| FILD-03 | Implement REJECT output flow -- capture rows failing schema validation | REJECT flow pattern with errorCode/errorMessage in Architecture Patterns; Talend source analysis |
| FILD-04 | Implement CSV mode (CSV_OPTION) with RFC4180 compliance | CSV_OPTION implementation strategy in Architecture Patterns; Python csv module analysis |
| FILD-05 | Implement per-column trim (TRIMSELECT TABLE) | TRIMSELECT pattern in Architecture Patterns; converter output format verified from sample JSON |
| FILD-06 | Implement CHECK_FIELDS_NUM -- validate row field count | REJECT flow triggers in Architecture Patterns; Talend javajet source confirms behavior |
| FILD-07 | Implement CHECK_DATE -- strict date format validation | Date validation strategy in Architecture Patterns |
| FILD-08 | Implement `{id}_FILENAME` and `{id}_ENCODING` globalMap variables | GlobalMap variables pattern in Architecture Patterns |
| FILD-09 | Implement advanced numeric separators (deferred per D-21) | Listed as deferred in User Constraints; engine should log warning |
| FOLD-01 | Fix config key mismatch -- delimiter key alignment | Same config key alignment as FILD-01 |
| FOLD-02 | Fix INCLUDEHEADER default -- engine defaults True but Talend defaults False | Default value mapping; D-05 locks Talend defaults |
| FOLD-03 | Fix encoding default -- honor ISO-8859-15 | Same as FILD-02 |
| FOLD-04 | Implement file splitting (SPLIT, SPLIT_EVERY) | Split file naming convention researched from Talend source |
| FOLD-05 | Implement FILE_EXIST_EXCEPTION -- prevent accidental overwrites | FILE_EXIST_EXCEPTION pattern in Architecture Patterns |
| FOLD-06 | Implement `{id}_FILE_NAME` globalMap variable | GlobalMap variables pattern |
| TEST-03 | Engine unit tests for file I/O components | Test pattern from ENGINE_TEST_PATTERN.md; test infrastructure verified |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.1 | DataFrame operations, CSV reading/writing | Already installed, project standard for all data transport [VERIFIED: runtime] |
| Python csv | stdlib | RFC4180 CSV parsing when CSV_OPTION=true | Handles quoted fields with embedded delimiters/newlines correctly [VERIFIED: stdlib] |
| pathlib | stdlib | Cross-platform file path construction | Mandated by D-23 for OS portability [VERIFIED: stdlib] |
| os | stdlib | File existence checks, directory creation, os.linesep | Platform-specific line endings for OS_LINE_SEPARATOR [VERIFIED: stdlib] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.0+ | Test framework with tmp_path fixture | All engine unit tests [VERIFIED: pyproject.toml] |
| datetime | stdlib | Date pattern validation for CHECK_DATE | Strict strptime validation against schema patterns |
| io | stdlib | StringIO for csv module integration | Bridge between csv reader and pandas DataFrame |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python csv module | pandas csv params only | pandas csv does not support RFC4180 embedded newlines properly when row_separator differs from default; csv module gives full RFC4180 control |
| Manual file splitting | pandas DataFrame.iloc slicing | Slicing is simpler and uses less memory than writing chunks; correct approach for SPLIT_EVERY |
| Custom date parser | pd.to_datetime with format | pd.to_datetime with format=... and errors='coerce' gives NaT for bad dates, which we can detect for REJECT routing |

**Installation:** No new packages needed -- all dependencies already available.

## Architecture Patterns

### Recommended Project Structure
```
src/v1/engine/components/file/
    __init__.py               # Updated: imports trigger @REGISTRY.register
    file_input_delimited.py   # REWRITE -- ~350-450 lines estimated
    file_output_delimited.py  # REWRITE -- ~250-350 lines estimated
tests/v1/engine/components/file/
    __init__.py               # NEW
    test_file_input_delimited.py   # NEW -- ~60-70 tests
    test_file_output_delimited.py  # NEW -- ~40-50 tests
tests/v1/engine/fixtures/file/    # NEW -- small fixture directory
    __init__.py
```

### Pattern 1: Config Key Alignment (D-04)

**What:** Engine reads converter config keys directly -- no mapping layer.
**When to use:** Every config read in `_process()`.

The converter outputs these exact keys (verified from sample JSON `Job_tFileInputDelimited_0.1.json` and `Job_tFileOutputDelimited_0.1.json`). [VERIFIED: sample JSON files]

**tFileInputDelimited config keys (25 total):**
```python
# Source: tests/talend_xml_samples/converted_jsons/Job_tFileInputDelimited_0.1.json
filepath = self.config.get("filepath", "")               # str
fieldseparator = self.config.get("fieldseparator", ";")   # str, Talend default ";"
row_separator = self.config.get("row_separator", "\\n")   # str
csv_option = self.config.get("csv_option", False)         # bool
csv_row_separator = self.config.get("csv_row_separator", "\\n")  # str
escape_char = self.config.get("escape_char", '"')         # str
text_enclosure = self.config.get("text_enclosure", '"')   # str
header_rows = self.config.get("header_rows", 0)           # int
footer_rows = self.config.get("footer_rows", 0)           # int
limit = self.config.get("limit", "")                      # str (expression support)
remove_empty_row = self.config.get("remove_empty_row", True)   # bool, Talend default True
encoding = self.config.get("encoding", "ISO-8859-15")     # str, Talend default ISO-8859-15
die_on_error = self.config.get("die_on_error", False)     # bool, Talend default False
trim_all = self.config.get("trim_all", False)             # bool
trim_select = self.config.get("trim_select", [])          # list[dict] with {column, trim}
check_fields_num = self.config.get("check_fields_num", False)  # bool
check_date = self.config.get("check_date", False)         # bool
# Deferred (log warning if set):
uncompress = self.config.get("uncompress", False)
split_record = self.config.get("split_record", False)
random_flag = self.config.get("random", False)
advanced_separator = self.config.get("advanced_separator", False)
```

**tFileOutputDelimited config keys (25 total):**
```python
# Source: tests/talend_xml_samples/converted_jsons/Job_tFileOutputDelimited_0.1.json
filepath = self.config.get("filepath", "")
fieldseparator = self.config.get("fieldseparator", ";")
row_separator = self.config.get("row_separator", "\\n")
encoding = self.config.get("encoding", "ISO-8859-15")
include_header = self.config.get("include_header", False)    # Talend default False
append = self.config.get("append", False)
csv_option = self.config.get("csv_option", False)
escape_char = self.config.get("escape_char", '"')
text_enclosure = self.config.get("text_enclosure", '"')
os_line_separator = self.config.get("os_line_separator", True)
csvrowseparator = self.config.get("csvrowseparator", "LF")  # CLOSED_LIST: LF/CR/CRLF
create_directory = self.config.get("create_directory", True)
split = self.config.get("split", False)
split_every = self.config.get("split_every", "1000")         # str for expression support
delete_empty_file = self.config.get("delete_empty_file", False)
file_exist_exception = self.config.get("file_exist_exception", True)  # Talend default True
die_on_error = self.config.get("die_on_error", False)
# Deferred (log warning if set):
compress = self.config.get("compress", False)
usestream = self.config.get("usestream", False)
row_mode = self.config.get("row_mode", False)
flushonrow = self.config.get("flushonrow", False)
```

### Pattern 2: REJECT Flow Implementation (FILD-03, FILD-06, FILD-07)

**What:** Row-level validation that routes failing rows to reject output with errorCode/errorMessage.
**When to use:** When reading input file rows that may fail validation.

**Talend reject behavior (from Talend _begin.javajet source):** [VERIFIED: Talaxie GitHub javajet]
- Reject rows copy ALL original columns from the main schema
- Two additional columns appended: `errorCode` (string) and `errorMessage` (string)
- errorMessage format: `"{exception message} - Line: {line_number}"`
- There is no distinct errorCode field in the Talend javajet -- only errorMessage is populated
- NB_LINE_REJECT counter incremented for each rejected row

**Implementation approach:**
```python
# Source: Talend javajet source analysis + ENGINE_COMPONENT_PATTERN.md
def _process(self, input_data=None) -> dict:
    # Read raw lines from file
    # For each row, validate:
    #   1. Field count matches schema (if check_fields_num=True)
    #   2. Type conversion succeeds for each column
    #   3. Date pattern matches schema pattern (if check_date=True)
    # Good rows -> main DataFrame
    # Bad rows -> reject DataFrame with errorCode + errorMessage columns

    # Reject row structure:
    reject_rows = []
    # For a bad row:
    reject_row = {**original_row_dict}
    reject_row["errorCode"] = "FIELD_COUNT_MISMATCH"  # or TYPE_ERROR, DATE_FORMAT_ERROR
    reject_row["errorMessage"] = f"Field count mismatch: expected {expected}, got {actual} - Line: {line_num}"
    reject_rows.append(reject_row)

    return {
        "main": good_df,
        "reject": pd.DataFrame(reject_rows) if reject_rows else None,
    }
```

**Note on errorCode:** Talend's javajet only sets errorMessage (not a separate errorCode). D-07 specifies both errorCode and errorMessage. Since this is an implementation decision locked by the user, implement both -- errorCode provides a machine-readable category (e.g., "FIELD_COUNT", "TYPE_CONVERSION", "DATE_FORMAT") and errorMessage provides the human-readable detail. [ASSUMED: errorCode values -- Talend does not define specific codes]

### Pattern 3: CSV_OPTION Toggle (FILD-04)

**What:** When `csv_option=True`, enable RFC4180 mode with text_enclosure and escape_char. When False, those params have no effect.
**When to use:** Controls whether fields can contain embedded delimiters/newlines.

**Current bug:** The old engine always applies quoting regardless of csv_option setting.

**Implementation strategy -- use Python csv module for RFC4180 reads:**
```python
# When csv_option=True:
# - Use csv.reader() with quotechar and escapechar for parsing
# - This correctly handles embedded delimiters and newlines per RFC4180
# - Use csv_row_separator instead of row_separator for line endings
# - fieldseparator MUST be single character (Talend enforces this)

# When csv_option=False:
# - Use pandas read_csv with quoting=csv.QUOTE_NONE
# - text_enclosure and escape_char have no effect
# - Multi-character delimiters and regex delimiters are allowed
```

**Recommendation:** Use a hybrid approach. For csv_option=False, use pandas `read_csv()` with `quoting=csv.QUOTE_NONE`. For csv_option=True, use Python's `csv.reader()` to handle the file reading (it handles RFC4180 correctly including embedded newlines), then construct a DataFrame from the parsed rows. This avoids fighting pandas' csv parser which does not cleanly support the csv_row_separator distinction. [ASSUMED: hybrid approach is most reliable]

### Pattern 4: TRIMSELECT Per-Column Trim (FILD-05)

**What:** Override trim_all with per-column trim settings from converter's trim_select array.
**When to use:** When trim_select has entries with `trim=True`.

```python
# Source: tests/talend_xml_samples/converted_jsons/Job_tFileInputDelimited_0.1.json
# trim_select format from converter:
# [{"column": "first_name", "trim": true}, {"column": "last_name", "trim": false}]

# Talend behavior: TRIMSELECT overrides TRIMALL
# If trim_select is non-empty, ignore trim_all and apply per-column
trim_select = self.config.get("trim_select", [])
if trim_select:
    for entry in trim_select:
        col = entry.get("column")
        if entry.get("trim", False) and col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].str.strip()
else:
    # Fall back to trim_all behavior
    if trim_all:
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].str.strip()
```

### Pattern 5: Split File Naming (FOLD-04)

**What:** Split large outputs into multiple files based on row count.
**When to use:** When `split=True` and `split_every` > 0.

**Talend split naming convention (from Talaxie javajet source):** [VERIFIED: tFileOutputDelimited_begin.javajet]
- Original filename: `data.csv`
- Split files: `data0.csv`, `data1.csv`, `data2.csv`, ...
- Pattern: `{basename_without_extension}{index}{extension}`
- **No separator** between basename and index number
- Index starts at 0

```python
# Implementation:
from pathlib import Path

def _split_filename(filepath: str, index: int) -> str:
    """Generate split filename following Talend convention.

    Examples:
        _split_filename("/data/output.csv", 0) -> "/data/output0.csv"
        _split_filename("/data/output.csv", 1) -> "/data/output1.csv"
    """
    p = Path(filepath)
    return str(p.with_name(f"{p.stem}{index}{p.suffix}"))
```

### Pattern 6: FILE_EXIST_EXCEPTION (FOLD-05)

**What:** When `file_exist_exception=True` (default) and file exists in non-append mode, raise FileOperationError.
**When to use:** Before writing output file.

```python
# Check before writing:
if file_exist_exception and not append and Path(filepath).exists():
    raise FileOperationError(
        f"[{self.id}] File already exists: '{filepath}'. "
        f"Set file_exist_exception=false or append=true to allow writing."
    )
```

### Pattern 7: OS_LINE_SEPARATOR (D-19, tFileOutputDelimited)

**What:** When `os_line_separator=True`, use `os.linesep` instead of configured row_separator.
**When to use:** Platform-appropriate line endings for output.

```python
import os

if os_line_separator:
    effective_row_separator = os.linesep
elif csv_option:
    effective_row_separator = _resolve_csv_row_separator(csvrowseparator)
else:
    effective_row_separator = _unescape_separator(row_separator)

def _resolve_csv_row_separator(csvrowseparator: str) -> str:
    """Convert CLOSED_LIST value to actual separator."""
    mapping = {"LF": "\n", "CR": "\r", "CRLF": "\r\n"}
    return mapping.get(csvrowseparator, "\n")
```

### Pattern 8: Registration and Module Init

**What:** Register components via decorator, trigger on import via `__init__.py`.

```python
# file_input_delimited.py
from ...component_registry import REGISTRY

@REGISTRY.register("FileInputDelimited", "tFileInputDelimited")
class FileInputDelimited(BaseComponent):
    ...

# file_output_delimited.py
@REGISTRY.register("FileOutputDelimited", "tFileOutputDelimited")
class FileOutputDelimited(BaseComponent):
    ...
```

The existing `__init__.py` already imports both classes. Since we are rewriting in-place, the imports continue to work. Just ensure the class names remain `FileInputDelimited` and `FileOutputDelimited`. [VERIFIED: src/v1/engine/components/file/__init__.py]

### Pattern 9: Deferred Feature Warning (D-21)

**What:** Log warning for config flags that are set but not yet implemented.

```python
# At the start of _process(), after reading config:
_DEFERRED_FLAGS = {
    "uncompress": "Compressed file reading",
    "split_record": "Multi-line field support",
    "random": "Random line sampling",
    "advanced_separator": "Advanced numeric separators",
    "enable_decode": "Hex/octal number decoding",
}
for flag, description in _DEFERRED_FLAGS.items():
    if self.config.get(flag, False):
        logger.warning(
            f"[{self.id}] {description} ('{flag}') is not yet implemented. "
            f"Config flag will be ignored."
        )
```

### Anti-Patterns to Avoid
- **Reading config in `__init__`**: Values are stale on re-execute, context vars not resolved [VERIFIED: ENGINE_COMPONENT_PATTERN.md Rule 5]
- **Overriding `execute()`**: Breaks lifecycle (stats, config immutability, expression resolution) [VERIFIED: ENGINE_COMPONENT_PATTERN.md Rule 4]
- **Using `print()`**: Must use logger [VERIFIED: ENGINE_COMPONENT_PATTERN.md Rule 8]
- **Storing processing state on `self`**: Leaks between iterate re-executions [VERIFIED: ENGINE_COMPONENT_PATTERN.md Rule 10]
- **Using `_update_stats()` manually when result dict has main/reject**: `_update_stats_from_result()` in BaseComponent handles this automatically from the returned dict [VERIFIED: base_component.py lines 455-475]
- **Dual-key support**: Never read both `delimiter` and `fieldseparator` -- only `fieldseparator` per D-04
- **Calling `validate_schema` on ALL rows then routing rejects**: validate_schema raises on non-nullable violations -- can't use it for reject routing. Implement custom per-row validation in `_process()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RFC4180 CSV parsing | Custom quoted field parser | Python `csv.reader()` | RFC4180 embedded newlines, escaped quotes, edge cases are deceptively complex |
| Cross-platform paths | String concatenation with `/` or `\\` | `pathlib.Path` | OS portability mandated by D-23 |
| File encoding detection | Charset sniffing | Trust config `encoding` value | Talend specifies encoding explicitly; detection is unreliable |
| Delimiter escaping | Manual escape handling | pandas `sep` parameter + `csv.QUOTE_NONE` | pandas handles regex delimiters, tab shortcuts correctly |
| Date pattern validation | Custom regex date parser | `datetime.strptime(value, pattern)` | Python's strptime handles all standard date patterns |
| Stats tracking (NB_LINE etc.) | Manual counter management | BaseComponent's `_update_stats_from_result()` auto-extracts from `main`/`reject` return dict | Less code, can't get wrong |

**Key insight:** The biggest "don't hand-roll" is the REJECT flow routing infrastructure -- BaseComponent + OutputRouter already handle routing the reject DataFrame to downstream reject-connected components. The component just needs to return `{"main": good_df, "reject": bad_df}` and the infrastructure takes care of the rest.

## Common Pitfalls

### Pitfall 1: pandas read_csv Ignores csv_option Toggle
**What goes wrong:** pandas' `read_csv()` always interprets `quotechar` if provided, even when Talend's CSV_OPTION is False.
**Why it happens:** There's no "disable quoting" mode in pandas that matches Talend's behavior where text_enclosure exists in config but has no effect.
**How to avoid:** When `csv_option=False`, explicitly pass `quoting=csv.QUOTE_NONE` to `read_csv()`. When `csv_option=True`, pass `quotechar` and either `doublequote=True` or `escapechar`.
**Warning signs:** Fields with quote characters getting silently mangled in non-CSV mode.

### Pitfall 2: Footer Skip Forces Python Engine in pandas
**What goes wrong:** `skipfooter` parameter in `pd.read_csv()` only works with `engine='python'`, which is significantly slower than the C engine.
**Why it happens:** The C engine doesn't support footer skipping.
**How to avoid:** Accept this tradeoff for footer > 0 files. Log it at DEBUG level. For files without footers, use the C engine for performance.
**Warning signs:** Slow reads on large files with footer_rows > 0.

### Pitfall 3: validate_schema Raises Instead of Rejecting
**What goes wrong:** `BaseComponent.validate_schema()` raises `DataValidationError` when a non-nullable column has NULL. This kills the entire component instead of routing bad rows to reject.
**Why it happens:** validate_schema was designed for post-processing validation, not per-row reject routing.
**How to avoid:** Do NOT use `validate_schema()` for row-level reject routing. Implement custom per-row validation in `_process()` that catches type/date/field-count issues and routes to reject. Only use `validate_schema()` on the final good rows DataFrame for final type coercion.
**Warning signs:** Component crashes instead of producing reject output.

### Pitfall 4: pandas 3.0 CoW and Arrow StringDtype
**What goes wrong:** pandas 3.0.1 is installed (runtime verified). Copy-on-Write is the default. String columns may use Arrow StringDtype internally, which behaves differently from object dtype for some operations.
**Why it happens:** pandas 3.0 defaults to CoW mode and may infer Arrow-backed string types.
**How to avoid:** When building DataFrames from parsed rows, explicitly specify `dtype=object` for string columns. Use `.copy()` where needed. The validate_schema pandas 3.0 bug (from project memory) is a known issue to be fixed in Phase 4 if encountered. [CITED: project memory - validate_schema pandas 3.0 bug]
**Warning signs:** Type errors on `.str.strip()`, unexpected dtype comparisons failing.

### Pitfall 5: Row Separator Unescaping
**What goes wrong:** Converter stores row_separator as escaped strings like `"\\n"` (literal backslash-n) in JSON, not as the actual newline character `"\n"`.
**Why it happens:** JSON serialization escapes special characters.
**How to avoid:** Implement a separator unescape helper that converts `"\\n"` -> `"\n"`, `"\\r\\n"` -> `"\r\n"`, `"\\t"` -> `"\t"`.
**Warning signs:** Files with literal `\n` in output instead of actual newlines.

### Pitfall 6: Empty DataFrame vs None
**What goes wrong:** Components may return empty DataFrame (`pd.DataFrame()`) or None for main/reject. BaseComponent handles both in `_update_stats_from_result()`.
**Why it happens:** Different edge cases produce different empty results.
**How to avoid:** Return `None` for reject when there are no rejected rows (not an empty DataFrame). Return an empty DataFrame for main when there is no data (matching current convention). [VERIFIED: base_component.py _update_stats_from_result checks both None and empty]

### Pitfall 7: Split File Index Starts at 0
**What goes wrong:** Split files get wrong naming if index starts at 1.
**Why it happens:** Assumption about index base.
**How to avoid:** Index starts at 0 per Talend convention: `output0.csv`, `output1.csv`. [VERIFIED: Talaxie tFileOutputDelimited_begin.javajet]

## Code Examples

### FileInputDelimited Module Header
```python
# Source: ENGINE_COMPONENT_PATTERN.md + converter output analysis
"""Engine component for FileInputDelimited (tFileInputDelimited).

Reads a character-delimited flat file and outputs rows as a DataFrame.
Supports CSV mode (RFC4180), per-column trim, field count validation,
date pattern validation, and REJECT flow routing for invalid rows.

Config keys consumed (25 total):
  filepath           (str, default "")         -- input file path
  fieldseparator     (str, default ";")        -- field delimiter
  row_separator      (str, default "\\n")      -- row delimiter
  csv_option         (bool, default False)     -- enable RFC4180 CSV mode
  csv_row_separator  (str, default "\\n")      -- row separator for CSV mode
  escape_char        (str, default '"')        -- escape character (CSV mode)
  text_enclosure     (str, default '"')        -- text enclosure (CSV mode)
  header_rows        (int, default 0)          -- header rows to skip
  footer_rows        (int, default 0)          -- footer rows to skip
  limit              (str, default "")         -- max rows to read
  remove_empty_row   (bool, default True)      -- remove empty rows
  encoding           (str, default "ISO-8859-15") -- file encoding
  die_on_error       (bool, default False)     -- halt on error
  trim_all           (bool, default False)     -- trim all string columns
  trim_select        (list, default [])        -- per-column trim settings
  check_fields_num   (bool, default False)     -- validate field count
  check_date         (bool, default False)     -- validate date patterns
  uncompress         (bool, default False)     -- DEFERRED: compressed reading
  split_record       (bool, default False)     -- DEFERRED: multi-line fields
  random             (bool, default False)     -- DEFERRED: random sampling
  advanced_separator (bool, default False)     -- DEFERRED: numeric formatting
  enable_decode      (bool, default False)     -- DEFERRED: hex/octal decode
  tstatcatcher_stats (bool, default False)     -- framework: stats collection
  label              (str, default "")         -- framework: component label
"""
```

### GlobalMap Variables Setting Pattern
```python
# Source: ENGINE_COMPONENT_PATTERN.md GlobalMap Variables Pattern
# Set BEFORE file reading (per Talend behavior):
if self.global_map:
    self.global_map.put(f"{self.id}_FILENAME", str(resolved_filepath))
    self.global_map.put(f"{self.id}_ENCODING", encoding)

# NB_LINE, NB_LINE_OK, NB_LINE_REJECT set AUTOMATICALLY by BaseComponent
# via _update_stats_from_result() and _update_global_map() -- do not set manually

# tFileOutputDelimited additionally sets:
if self.global_map:
    self.global_map.put(f"{self.id}_FILE_NAME", str(resolved_filepath))
```

### Date Validation (CHECK_DATE)
```python
# Source: Python datetime.strptime docs
from datetime import datetime

def _validate_date(value: str, pattern: str) -> bool:
    """Check if value matches date pattern exactly.

    Args:
        value: String value to validate.
        pattern: Python strftime pattern (e.g., '%Y-%m-%d').

    Returns:
        True if value matches pattern, False otherwise.
    """
    if not value or not pattern:
        return True  # Skip validation if no value or no pattern
    try:
        datetime.strptime(str(value).strip(), pattern)
        return True
    except (ValueError, TypeError):
        return False
```

### Row Separator Unescaping
```python
def _unescape_separator(sep: str) -> str:
    """Convert escaped separator strings to actual characters.

    Converter stores separators as escaped strings in JSON
    (e.g., "\\n" for newline). This converts them back.
    """
    replacements = {
        "\\n": "\n",
        "\\r\\n": "\r\n",
        "\\r": "\r",
        "\\t": "\t",
    }
    return replacements.get(sep, sep)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Engine reads `delimiter` config key | Engine reads `fieldseparator` directly | Phase 4 (this phase) | Perfect alignment with converter output |
| Engine default UTF-8, comma delimiter | Engine defaults ISO-8859-15, semicolon | Phase 4 (this phase) | Matches Talend behavior for jobs using defaults |
| No REJECT flow in file input | Reject rows routed via return dict | Phase 4 (this phase) | Rows failing validation don't get silently dropped |
| Manual COMPONENT_REGISTRY dict | @REGISTRY.register decorator | Phase 3 | Auto-registration on import |
| Config mutation during execute | Deepcopy from _original_config per execute | Phase 1 | Safe iterate re-execution |

**Deprecated/outdated:**
- `self.config.get('delimiter')` -- NEVER use in new code, old key
- `self.config.get('remove_empty_rows')` (plural) -- converter uses `remove_empty_row` (singular)
- `_update_stats()` manual calls -- use return dict with main/reject for automatic stats
- `_validate_config` returning List[str] -- must return None and raise ConfigurationError

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | errorCode values should be machine-readable strings like "FIELD_COUNT", "TYPE_CONVERSION", "DATE_FORMAT" | REJECT Flow Implementation | Low -- errorCode is an added convenience; Talend only has errorMessage. Can adjust format later. |
| A2 | Hybrid csv.reader + pandas approach is most reliable for CSV_OPTION | CSV_OPTION Toggle | Medium -- if csv.reader has performance issues on very large files, may need to fall back to pandas-only approach. Testing will verify. |
| A3 | pandas 3.0 CoW won't cause issues for the rewrite if we use explicit dtypes | Common Pitfalls | Medium -- if Arrow StringDtype causes unexpected behavior, may need targeted workarounds. |

## Open Questions

1. **Single-string read mode behavior**
   - What we know: Old engine reads entire file as single string when both delimiter and row_separator are empty. This is used for XML/document files.
   - What's unclear: Whether any production Talend jobs use this mode with tFileInputDelimited (unlikely -- XML files use tFileInputXML).
   - Recommendation: Keep the mode but fix the bug (use `[file_content]` not `file_content` in DataFrame constructor). Low priority -- handle as edge case in `_process()`.

2. **Streaming mode for file input with REJECT**
   - What we know: BaseComponent's `_execute_streaming` chunks input DataFrames. But FileInputDelimited is a source component (no input DataFrame) -- it reads from file.
   - What's unclear: How to handle streaming with per-row reject validation.
   - Recommendation: FileInputDelimited should handle its own streaming internally (chunked file reading), not rely on BaseComponent streaming. The current approach of checking file size and switching modes can be preserved but with correct REJECT handling per chunk.

3. **validate_schema interaction with REJECT**
   - What we know: validate_schema raises DataValidationError on non-nullable violations. Per-row validation for REJECT must not crash the component.
   - What's unclear: Whether validate_schema should be called at all after per-row validation.
   - Recommendation: Call validate_schema on the GOOD rows only (after rejecting bad ones) for final type coercion. Skip the non-nullable check since per-row validation already handled it.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ [VERIFIED: pyproject.toml] |
| Config file | pyproject.toml `[tool.pytest.ini_options]` [VERIFIED] |
| Quick run command | `python -m pytest tests/v1/engine/components/file/ -x -q` |
| Full suite command | `python -m pytest tests/v1/engine/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FILD-01 | Config key `fieldseparator` read correctly | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestDefaults -x` | Wave 0 |
| FILD-02 | Encoding default ISO-8859-15 honored | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestEncoding -x` | Wave 0 |
| FILD-03 | REJECT flow for validation failures | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestRejectFlow -x` | Wave 0 |
| FILD-04 | CSV_OPTION with RFC4180 | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestCsvOption -x` | Wave 0 |
| FILD-05 | TRIMSELECT per-column trim | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestTrimSelect -x` | Wave 0 |
| FILD-06 | CHECK_FIELDS_NUM validation | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestCheckFieldsNum -x` | Wave 0 |
| FILD-07 | CHECK_DATE date validation | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestCheckDate -x` | Wave 0 |
| FILD-08 | globalMap FILENAME and ENCODING | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestGlobalMapVariables -x` | Wave 0 |
| FILD-09 | ADVANCED_SEPARATOR (deferred) | unit | `pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestDeferredFeatures -x` | Wave 0 |
| FOLD-01 | Config key `fieldseparator` read correctly | unit | `pytest tests/v1/engine/components/file/test_file_output_delimited.py::TestDefaults -x` | Wave 0 |
| FOLD-02 | INCLUDEHEADER default False | unit | `pytest tests/v1/engine/components/file/test_file_output_delimited.py::TestDefaults -x` | Wave 0 |
| FOLD-03 | Encoding default ISO-8859-15 | unit | `pytest tests/v1/engine/components/file/test_file_output_delimited.py::TestEncoding -x` | Wave 0 |
| FOLD-04 | SPLIT/SPLIT_EVERY file splitting | unit | `pytest tests/v1/engine/components/file/test_file_output_delimited.py::TestSplitOutput -x` | Wave 0 |
| FOLD-05 | FILE_EXIST_EXCEPTION check | unit | `pytest tests/v1/engine/components/file/test_file_output_delimited.py::TestFileExistException -x` | Wave 0 |
| FOLD-06 | globalMap FILE_NAME variable | unit | `pytest tests/v1/engine/components/file/test_file_output_delimited.py::TestGlobalMapVariables -x` | Wave 0 |
| TEST-03 | Engine unit tests for file components | unit | `pytest tests/v1/engine/components/file/ -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/v1/engine/components/file/ -x -q`
- **Per wave merge:** `python -m pytest tests/v1/engine/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/v1/engine/components/__init__.py` -- package init
- [ ] `tests/v1/engine/components/file/__init__.py` -- package init
- [ ] `tests/v1/engine/components/file/test_file_input_delimited.py` -- covers FILD-01 through FILD-09
- [ ] `tests/v1/engine/components/file/test_file_output_delimited.py` -- covers FOLD-01 through FOLD-06

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A -- batch ETL system |
| V3 Session Management | no | N/A -- no sessions |
| V4 Access Control | no | N/A -- file paths from trusted config |
| V5 Input Validation | yes | Schema validation via REJECT flow; field count validation; date format validation |
| V6 Cryptography | no | N/A -- no encryption |

### Known Threat Patterns for File I/O

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal in filepath config | Tampering | File paths come from converter-generated JSON configs (trusted input); no user-facing API. Path validation deferred to production hardening. |
| CSV formula injection | Information Disclosure | Fields starting with =, +, -, @ could be formulas in Excel. No built-in protection needed -- this is a data pipeline, not a user-facing tool. |
| Encoding mismatch data loss | Tampering | Engine defaults to ISO-8859-15 matching Talend; explicit encoding in config prevents mismatch. |
| Large file memory exhaustion | Denial of Service | Streaming mode auto-activates for files > 3GB via BaseComponent threshold. |

## Sources

### Primary (HIGH confidence)
- `src/v1/engine/base_component.py` -- BaseComponent lifecycle, stats, schema validation [VERIFIED: direct code read]
- `src/v1/engine/component_registry.py` -- @REGISTRY.register pattern [VERIFIED: direct code read]
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- Component blueprint [VERIFIED: direct code read]
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` -- Test pattern [VERIFIED: direct code read]
- `docs/v1/audit/components/file/tFileInputDelimited.md` -- 33 params, 21 issues [VERIFIED: direct code read]
- `docs/v1/audit/components/file/tFileOutputDelimited.md` -- 27 params, 14 issues [VERIFIED: direct code read]
- `src/converters/talend_to_v1/components/file/file_input_delimited.py` -- Converter config keys [VERIFIED: direct code read]
- `src/converters/talend_to_v1/components/file/file_output_delimited.py` -- Converter config keys [VERIFIED: direct code read]
- `tests/talend_xml_samples/converted_jsons/Job_tFileInputDelimited_0.1.json` -- Sample converter output [VERIFIED: direct read]
- `tests/talend_xml_samples/converted_jsons/Job_tFileOutputDelimited_0.1.json` -- Sample converter output [VERIFIED: direct read]

### Secondary (MEDIUM confidence)
- [Talend tFileOutputDelimited Standard Properties (8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileoutputdelimited-standard-properties) -- Parameter defaults and descriptions
- [Talend tFileInputDelimited Standard Properties (8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-standard-properties) -- Parameter defaults and descriptions
- [Talaxie tFileOutputDelimited_begin.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileOutputDelimited/tFileOutputDelimited_begin.javajet) -- Split file naming convention: `{stem}{index}{suffix}`
- [Talaxie tFileInputDelimited_begin.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputDelimited/tFileInputDelimited_begin.javajet) -- Reject row structure: original columns + errorMessage

### Tertiary (LOW confidence)
- None -- all claims verified against source code or official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, verified versions
- Architecture: HIGH -- patterns derived from existing codebase (ENGINE_COMPONENT_PATTERN.md, BaseComponent source)
- Config keys: HIGH -- verified against converter source code and sample JSON output
- Talend behavior: HIGH -- verified against Talend official docs and Talaxie javajet source
- Split naming: MEDIUM -- verified from javajet but not tested with running Talend instance
- REJECT errorCode values: LOW (ASSUMED) -- Talend only sets errorMessage, errorCode is our addition per D-07
- Pitfalls: HIGH -- derived from current code bugs documented in audit reports

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable -- infrastructure and Talend behavior don't change rapidly)
