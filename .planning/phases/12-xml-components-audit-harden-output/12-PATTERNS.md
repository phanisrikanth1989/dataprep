# Phase 12: XML Components Audit, Harden & Output - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 14 (4 modified engine + 1 modified converter + 3 new engine + 1 new converter + 5 new test files; plus 3 registry/__init__ touch-ups)
**Analogs found:** 14 / 14 (every file has a strong in-repo analog)

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/v1/engine/components/file/file_input_xml.py` (MIGRATE stdlib→lxml, ~555 LOC) | engine component (source) | file-I/O / request-response | `src/v1/engine/components/file/file_input_msxml.py` | exact (same role + lxml + REJECT pattern) |
| `src/v1/engine/components/file/file_input_msxml.py` (audit + light fix) | engine component (source) | file-I/O | self (already gold pattern) — extend in place | self-analog |
| `src/v1/engine/components/transform/extract_xml_fields.py` (audit + light fix) | engine component (transform) | request-response (per-row XPath) | self — pattern is current. For NEW REJECT additions, mirror `_make_reject_row` already there | self-analog |
| `src/v1/engine/components/transform/xml_map.py` (audit + heavy fix, 738 LOC) | engine component (transform) | request-response (per-row XML doc → rows) | `src/v1/engine/components/transform/extract_xml_fields.py` (REJECT, secure parser, per-row loop) + `src/v1/engine/components/file/file_input_msxml.py` (clean lifecycle) | role-match (closest in repo; xml_map is uniquely large) |
| `src/v1/engine/components/file/file_output_xml.py` (NEW, simple/flat) | engine component (sink, streaming output) | streaming / file-I/O | `src/v1/engine/components/file/file_output_delimited.py` (streaming hook, `_streaming_write_started`, sink contract) | exact for streaming/sink shape |
| `src/v1/engine/components/file/file_output_advanced_xml.py` (NEW, hierarchical) | engine component (sink, streaming output) | streaming / file-I/O | `src/v1/engine/components/file/file_output_delimited.py` (streaming hook + globalMap write) + RESEARCH.md Pattern 2 (xmlfile nested context) | role-match for streaming, exemplar pattern from research for hierarchy |
| `src/v1/engine/components/file/_xml_io.py` (NEW shared helper) | utility | transform | `src/v1/engine/components/transform/extract_xml_fields.py:153-159` (secure parser flags) + `src/v1/engine/components/file/file_input_msxml.py:107-113` (parser construction) | role-match (no pre-existing shared helper) |
| `src/converters/talend_to_v1/components/file/file_output_xml.py` (ADD class for `tFileOutputXML`) | converter | request-response (XML node → JSON dict) | `src/converters/talend_to_v1/components/file/file_output_delimited.py` (sink converter, `_get_str/_get_bool`, framework params last) | exact |
| `src/v1/engine/engine.py` (register 2 new components if old-static-dict still used; verify decorator path) | config / registry | event-driven | existing `COMPONENT_REGISTRY` block | self |
| `src/converters/talend_to_v1/components/file/__init__.py` (no-op if file_output_xml import already present) | config | event-driven | existing file (already imports `file_output_xml`) | self |
| `src/v1/engine/components/file/__init__.py` (add 2 new exports) | config | event-driven | existing file (imports + `__all__` list pattern) | self |
| `tests/v1/engine/components/file/test_file_input_xml.py` (NEW) | test | request-response | `tests/v1/engine/components/file/test_file_input_msxml.py` (TestRegistry / TestValidateConfig / TestProcessMain / TestProcessReject / TestStats class layout) | exact |
| `tests/v1/engine/components/file/test_file_output_xml.py` (NEW) | test | streaming | `tests/v1/engine/components/file/test_file_output_delimited.py` (existing comprehensive sink test file) | role-match |
| `tests/v1/engine/components/file/test_file_output_advanced_xml.py` (NEW) | test | streaming | same as above | role-match |
| `tests/v1/engine/components/transform/test_xml_map.py` (NEW) | test | request-response | `tests/v1/engine/components/transform/test_extract_xml_fields.py` | exact |
| `tests/talend_xml_samples/Job_tFileOutputXML_*.item` (NEW fixture) | test fixture | -- | `tests/talend_xml_samples/Job_tFileOutputDelimited_0.1.item` (sink) + `Job_tFileInputXML_0.1.item` (XML node shape) | role-match (hand-author per D-D5) |
| `tests/talend_xml_samples/Job_tAdvancedFileOutputXML_*.item` (NEW fixture) | test fixture | -- | same pair | role-match |

---

## Pattern Assignments

### `src/v1/engine/components/file/file_input_xml.py` (engine component, file-I/O — MIGRATE stdlib→lxml)

**Analog:** `src/v1/engine/components/file/file_input_msxml.py` (172 LOC, already lxml + secure parser + REJECT pattern). The migration target shape is: shorter than today's 555 LOC, secure parser, `@REGISTRY.register`, REJECT flow, threshold-switched DOM/iterparse via the new `_xml_io.py` helper.

**Imports pattern** (msxml lines 25–34) — copy verbatim:
```python
import logging
import os
from typing import Any, Dict, Optional

import pandas as pd
from lxml import etree

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError
```

**Registration pattern** (msxml line 39):
```python
@REGISTRY.register("FileInputXML", "tFileInputXML")
class FileInputXML(BaseComponent):
```
Note: today's `file_input_xml.py` does NOT use the decorator (registered via `__init__.py` import only). Plan 3 must add the decorator AND keep the `__init__.py` import to trigger registration. Confirmed pattern in msxml.

**Validate-config pattern** (msxml lines 53–73):
```python
def _validate_config(self) -> None:
    """Check key presence and container types only (Rule 12)."""
    if not self.config.get("filename"):
        raise ConfigurationError(
            f"[{self.id}] Missing required config key 'filename'"
        )
    if not self.config.get("loop_query"):
        raise ConfigurationError(
            f"[{self.id}] Missing required config key 'loop_query'"
        )
    for bool_key, default in (
        ("die_on_error", False),
        ("ignore_ns", False),
        ("ignore_dtd", False),
        ...
    ):
        val = self.config.get(bool_key, default)
        if not isinstance(val, bool):
            raise ConfigurationError(
                f"[{self.id}] Config '{bool_key}' must be a boolean"
            )
```

**Secure parser + parse pattern** (msxml lines 106–118):
```python
try:
    parser = etree.XMLParser(
        load_dtd=not ignore_dtd,
        no_network=True,
        recover=True,    # NOTE: Phase 12 RESEARCH.md P-1 says recover=False; choose per fix-source rule
        encoding=encoding,
    )
    tree = etree.parse(filepath, parser=parser)
    root = tree.getroot()
except Exception as exc:
    raise FileOperationError(
        f"[{self.id}] Failed to parse XML file {filepath!r}: {exc}"
    ) from exc
```
Plan 3 instead delegates to `from . import _xml_io` and calls `_xml_io.secure_xml_parser(recover=False)` — see `_xml_io.py` pattern below.

**REJECT-flow row-loop pattern** (msxml lines 130–154):
```python
main_rows: list = []
reject_rows: list = []
for node in nodes:
    try:
        out_row: dict = {}
        for col_name in col_names:
            children = node.findall(col_name)
            if children:
                text = children[0].text or ""
            else:
                result = node.xpath(f"./{col_name}/text()")
                text = result[0] if result else ""
            if trim_all and isinstance(text, str):
                text = text.strip()
            out_row[col_name] = text if text != "" else None
        main_rows.append(out_row)
    except Exception as exc:
        logger.warning("[%s] Node extraction failed: %s", self.id, exc)
        if die_on_error:
            raise FileOperationError(
                f"[{self.id}] Node extraction failed: {exc}"
            ) from exc
        reject_rows.append({"errorCode": "NODE_ERROR", "errorMessage": str(exc)})
```
For tFileInputXML's richer mapping (`mapping = [{column, xpath, nodecheck}]`), additionally borrow the per-mapping nodecheck loop from `extract_xml_fields.py:177–225`.

**Stats + return pattern** (msxml lines 156–172):
```python
main_df = pd.DataFrame(main_rows, columns=col_names) if main_rows else pd.DataFrame(columns=col_names)
reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()
rows_total = len(main_df) + len(reject_df)
self._update_stats(rows_total, len(main_df), len(reject_df))
logger.info("[%s] done: file=%r ok=%d reject=%d", self.id, filepath, len(main_df), len(reject_df))
return {"main": main_df, "reject": reject_df}
```

---

### `src/v1/engine/components/file/file_input_msxml.py` (audit + light fix, 172 LOC)

**Analog:** Self. File is already on lxml with secure-parser + REJECT pattern. Plan 4 work is:
- Switch `recover=True` (line 110) → `recover=False` to match P-1 fix-source policy.
- Delegate parser construction to `_xml_io.secure_xml_parser()`.
- Extend tests from 13 → ~30 per-param pos+neg.

**Pattern reference:** entire file is the pattern itself — no external analog needed. Confirm `@REGISTRY.register("FileInputMSXML", "tFileInputMSXML")` decorator (already present, line 39).

---

### `src/v1/engine/components/transform/extract_xml_fields.py` (audit + light fix, 260 LOC)

**Analog:** Self (recently hardened in Phase 7.x; gold-standard XPath-with-REJECT pattern).

**Reuse for tXMLMap fix in Plan 5** — the `_make_reject_row` helper (lines 251–260):
```python
@staticmethod
def _make_reject_row(row: pd.Series, xml_string: Any, code: str, msg: str) -> Dict[str, Any]:
    """Build a reject row dict with error detail columns."""
    reject_row = {k: row.get(k, None) for k in row.index}
    reject_row["errorXMLField"] = xml_string
    reject_row["errorCode"] = code
    reject_row["errorMessage"] = msg
    return reject_row
```

**Reuse the per-row XML parse + nodecheck pattern** (lines 138–225) when adding REJECT to xml_map.

---

### `src/v1/engine/components/transform/xml_map.py` (audit + heavy fix, 738 LOC, NO engine tests)

**Analog:** `src/v1/engine/components/transform/extract_xml_fields.py` (REJECT, secure parser, per-row loop, error codes). Use it as the rewrite-over-patch reference for the row loop and REJECT addition.

**Imports/registration pattern** to ADD (mirror extract_xml_fields lines 26–39):
```python
import logging
from typing import Any, Dict, Optional

import pandas as pd
from lxml import etree

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


@REGISTRY.register("XMLMap", "tXMLMap")
class XMLMap(BaseComponent):
```
Currently no `@REGISTRY.register` on xml_map.py. Add per Plan 5.

**Per-row loop pattern (P0 BUG-XMP-003 fix)** — replace `iloc[0,0]` with the per-row loop from extract_xml_fields lines 135–225:
```python
for _, row in input_data.iterrows():
    xml_string = row.get(src_col, None)
    try:
        is_null = pd.isna(xml_string)
    except (TypeError, ValueError):
        is_null = False
    if is_null:
        reject_rows.append(self._make_reject_row(row, xml_string, self._ERR_NO_XML, "No XML data"))
        rows_reject += 1
        continue
    # ... per-row XML parse and node loop
```

**Logger replacement (STD-XMP-001)** — replace 46 `print(...)` calls with `logger.info(...)` / `logger.warning(...)`. ASCII-only per CLAUDE.md memory rule. Pattern:
```python
# BEFORE: print(f"[XMLMap] Processing started")
# AFTER:
logger.info("[%s] Processing started", self.id)
```

**lstrip → removeprefix fix (P-7, line 281)**:
```python
# BEFORE: tail.lstrip("/")
# AFTER:
tail.removeprefix("/")
```

**Conditional needs_review for unsupported sub-features** (D-E1) — emit on the converter side (`src/converters/talend_to_v1/components/transform/xml_map.py`), engine logs a warning and treats as no-op:
```python
# Engine side — warn, do not raise:
if self.config.get("activate_expression_filter"):
    logger.warning(
        "[%s] expression_filter is not implemented in this engine; ignoring "
        "(see Phase 12 needs_review entry).",
        self.id,
    )
```

---

### `src/v1/engine/components/file/file_output_xml.py` (NEW — simple/flat sink)

**Analog:** `src/v1/engine/components/file/file_output_delimited.py` for the sink + streaming + globalMap shape. RESEARCH.md Example 3 for the actual `etree.xmlfile` write loop.

**Imports pattern** (file_output_delimited lines 42–54):
```python
import csv  # remove for XML — replace with: from lxml import etree
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)
```

**Streaming-state attribute pattern** (file_output_delimited lines 108–119):
```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # Tracks whether _process() has already written the first chunk during a
    # streaming execute() call. Used to keep the xmlfile context open across
    # chunks and to avoid re-emitting <root> on the second chunk.
    self._streaming_xmlfile_ctx = None        # active etree.xmlfile() ctx mgr
    self._streaming_xmlfile_root_ctx = None   # active xf.element(root_tag) ctx
    self._streaming_write_started: bool = False

def reset(self) -> None:
    """Reset component state for re-execution (iterate support)."""
    super().reset()
    if self._streaming_xmlfile_root_ctx is not None:
        # close root element ctx then xmlfile ctx
        ...
    self._streaming_xmlfile_ctx = None
    self._streaming_xmlfile_root_ctx = None
    self._streaming_write_started = False
```

**Bool-coerce helper pattern** (file_output_delimited lines 125–141 — `_bool` static):
```python
@staticmethod
def _bool(v: Any) -> bool:
    """Coerce a config value to bool, handling JSON string 'true'/'false'."""
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)
```

**`_process` skeleton + sink contract** (file_output_delimited lines 168–325, condensed):
```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    # 1. coerce all bool flags via self._bool(...)
    # 2. read non-bool config values
    # 3. resolve filepath via Path(...)
    # 4. create_directory parent if requested
    # 5. FILE_EXIST_EXCEPTION check
    # 6. handle empty input -> _handle_empty_input()
    # 7. open xmlfile context (or reuse held ctx if streaming)
    # 8. write rows
    # 9. set globalMap: f"{self.id}_FILE_NAME", f"{self.id}_NB_LINE"
    # 10. log "[%s] Write complete: %d rows to '%s'"
    # 11. self._streaming_write_started = True
    # 12. return {"main": input_data, "reject": None}  # PASSTHROUGH per CR-09
```

**globalMap pattern** (file_output_delimited lines 312–314):
```python
if self.global_map:
    self.global_map.put(f"{self.id}_FILE_NAME", str(resolved_path))
    self.global_map.put(f"{self.id}_NB_LINE", total_written)
```

**Core XML-write pattern** (RESEARCH.md Example 3, ~lines 770–790; reproduce verbatim):
```python
# Inside _process(), per chunk:
if not self._streaming_write_started:
    f = open(filepath, "wb")
    self._streaming_xmlfile_ctx = etree.xmlfile(f, encoding=encoding)
    xf = self._streaming_xmlfile_ctx.__enter__()
    xf.write_declaration()
    self._streaming_xmlfile_root_ctx = xf.element(root_tag)
    self._streaming_xmlfile_root_ctx.__enter__()

xf = self._streaming_xmlfile_ctx  # already entered
for _, row in chunk_df.iterrows():
    attrs = {col: str(row[col]) for col in column_to_attr if col in row.index}
    with xf.element(row_tag, **attrs):
        for col in row.index:
            if col in column_to_attr:
                continue
            with xf.element(col):
                xf.write(str(row[col]) if row[col] is not None else "")
    xf.flush()
```

---

### `src/v1/engine/components/file/file_output_advanced_xml.py` (NEW — hierarchical sink)

**Analog:** `src/v1/engine/components/file/file_output_delimited.py` for sink/streaming shape (same as `file_output_xml.py`). RESEARCH.md Example 4 (lines 791–812) for the ROOT/GROUP/LOOP nested-context emission.

**Same imports / registration / reset / sink-contract patterns as `file_output_xml.py`.**

**Registration:**
```python
@REGISTRY.register("AdvancedFileOutputXML", "tAdvancedFileOutputXML")
class AdvancedFileOutputXML(BaseComponent):
```

**Hierarchical write pattern** (RESEARCH.md Example 4):
```python
with open(filepath, "wb") as f, etree.xmlfile(f, encoding=encoding) as xf:
    xf.write_declaration()
    with xf.element(root_table[0]["path"]):
        for group_key, group_df in df.groupby(_groupby_columns(group_table), dropna=False):
            with xf.element(group_table[0]["path"]):
                _emit_static(xf, group_table[1:])
                for _, row in group_df.iterrows():
                    with xf.element(loop_table[0]["path"]):
                        _emit_row_columns(xf, row, loop_table[1:])
                    xf.flush()
```

**Conditional needs_review** for sub-features deferred via D-E1 — emit on converter side; engine warns + ignores:
```python
for unsupported in ("dtd_valid", "xsl_valid", "output_as_xsd", "merge",
                    "add_document_as_node", "add_unmapped_attribute"):
    if self._bool(self.config.get(unsupported, False)):
        logger.warning(
            "[%s] %s is not implemented in this engine (Phase 12 needs_review).",
            self.id, unsupported,
        )
```

---

### `src/v1/engine/components/file/_xml_io.py` (NEW — shared helper utility)

**Analog:** No prior shared helper exists. Pattern is consolidated from `extract_xml_fields.py:153-159` (secure parser flags) and `file_input_msxml.py:107-113` (parser construction).

**Imports pattern:**
```python
"""Shared helpers for XML engine components.

Provides a hardened XMLParser factory (replaces deprecated defusedxml.lxml per
Phase 12 RESEARCH.md P-1) and threshold-switched DOM/iterparse helpers.
"""
import logging
import os
from typing import Iterator, Tuple

from lxml import etree

logger = logging.getLogger(__name__)
```

**Secure-parser factory** (RESEARCH.md Example 1 + extract_xml_fields:153–159 verbatim):
```python
def secure_xml_parser(*, recover: bool = False) -> etree.XMLParser:
    """Build a hardened XMLParser.

    Disables external entity expansion (XXE), DTD loading (billion-laughs),
    and network access. recover=False fails loud on malformed XML so the
    caller can route to REJECT instead of silently passing partial trees.
    """
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=recover,
    )
```

**Threshold-switched parse strategy** (RESEARCH.md Example 2):
```python
def parse_xml_strategy(filename: str, threshold_mb: int) -> Tuple[str, object]:
    """Return ('dom', tree) for small files, ('stream', filename) above threshold."""
    size_mb = os.stat(filename).st_size / (1024 * 1024)
    parser = secure_xml_parser()
    if size_mb < threshold_mb:
        return ("dom", etree.parse(filename, parser=parser))
    return ("stream", filename)


def iterparse_loop_query(filename: str, loop_tag: str) -> Iterator[etree._Element]:
    """Yield each `loop_tag` element, then clear it and prior siblings to free memory."""
    ctx = etree.iterparse(
        filename,
        events=("end",),
        tag=loop_tag,
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
    )
    for _event, element in ctx:
        yield element
        element.clear(keep_tail=True)
        while element.getprevious() is not None:
            del element.getparent()[0]
    del ctx
```

**Strategy log line** (P-4 mitigation — must be present and ASCII-only):
```python
def log_strategy(component_id: str, strategy: str, size_mb: float, threshold_mb: int) -> None:
    logger.info(
        "[%s] XML strategy=%s size=%.2fMB threshold=%dMB",
        component_id, strategy, size_mb, threshold_mb,
    )
```

---

### `src/converters/talend_to_v1/components/file/file_output_xml.py` (ADD `tFileOutputXML` simple-converter class)

**Analog:** `src/converters/talend_to_v1/components/file/file_output_delimited.py` (sink converter, full param-extraction pattern, 113 LOC).

**Existing file already contains** `AdvancedFileOutputXmlConverter` (lines 104–193). Plan 6 ADDS a second class in the same file for simple `tFileOutputXML`. Keep `_parse_xml_table` shared at module scope (already there).

**Module-level imports** (existing, lines 43–47):
```python
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
```

**Registration + class pattern** (mirror `FileOutputDelimitedConverter` lines 45–113 verbatim, with tFileOutputXML param table from RESEARCH.md lines 526–548):
```python
@REGISTRY.register("tFileOutputXML")
class FileOutputXMLConverter(ComponentConverter):
    """Convert Talend tFileOutputXML (simple/flat) to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["filename"] = self._get_str(node, "FILENAME", "")
        config["input_is_document"] = self._get_bool(node, "INPUT_IS_DOCUMENT", False)
        config["document_col"] = self._get_str(node, "DOCUMENT_COL", "")
        config["row_tag"] = self._get_str(node, "ROW_TAG", "row")
        config["root_tags"] = _parse_xml_table(node.params.get("ROOT_TAGS", []))
        config["mapping"] = _parse_mapping_table(node.params.get("MAPPING", []))  # AS_ATTRIBUTE + SCHEMA_COLUMN_NAME
        config["use_dynamic_grouping"] = self._get_bool(node, "USE_DYNAMIC_GROUPING", False)
        config["group_by"] = _parse_groupby_table(node.params.get("GROUP_BY", []))
        config["flushonrow"] = self._get_bool(node, "FLUSHONROW", False)
        config["flushonrow_num"] = self._get_str(node, "FLUSHONROW_NUM", "1")
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")  # NOT UTF-8
        config["split"] = self._get_bool(node, "SPLIT", False)
        config["split_every"] = self._get_str(node, "SPLIT_EVERY", "1000")
        config["create"] = self._get_bool(node, "CREATE", True)
        config["trim"] = self._get_bool(node, "TRIM", False)
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["delete_empty_file"] = self._get_bool(node, "DELETE_EMPTYFILE", False)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema (sink: input populated, output empty) ----
        schema = {"input": self._parse_schema(node), "output": []}

        # ---- 4. Build component ----
        component = self._build_component_dict(
            node=node,
            type_name="FileOutputXML",   # engine class name
            config=config,
            schema=schema,
        )

        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
```

**MAPPING / ROOT_TAGS / GROUP_BY parsing helpers** — model on `_parse_xml_table` already in this file (lines 61–101). Add two siblings at module scope:
```python
def _parse_mapping_table(raw: Any) -> List[Dict[str, Any]]:
    """Parse MAPPING TABLE: [{column, as_attribute}]."""
    # mirror _parse_xml_table; recognize SCHEMA_COLUMN_NAME, AS_ATTRIBUTE


def _parse_groupby_table(raw: Any) -> List[Dict[str, Any]]:
    """Parse GROUP_BY TABLE: [{column, label}]."""
    # mirror _parse_xml_table; recognize COLUMN, LABEL
```

---

### `src/v1/engine/engine.py` (registration touch-up — verify only, may be no-op)

**Analog:** existing `COMPONENT_REGISTRY` patterns (search for the static-dict block).

The two NEW components register via `@REGISTRY.register("FileOutputXML", "tFileOutputXML")` and `@REGISTRY.register("AdvancedFileOutputXML", "tAdvancedFileOutputXML")` decorators in their modules — Plan 6 should NOT need to touch `engine.py` if the import side-effect chain (`engine.py:19 from . import components`) reaches the new module. The new modules MUST be added to `src/v1/engine/components/file/__init__.py` so the import chain reaches them.

**Verification step:** Plan 6 add an integration test that calls `from src.v1.engine.component_registry import REGISTRY; assert REGISTRY.get("tFileOutputXML") is FileOutputXML`.

---

### `src/v1/engine/components/file/__init__.py` (add 2 new exports)

**Analog:** existing `__init__.py` (file lines 1–54) — already established import + `__all__` pattern.

**Add lines** (before `set_global_var` import, alphabetical-ish order is loose; current file groups by category):
```python
from .file_output_xml import FileOutputXML
from .file_output_advanced_xml import AdvancedFileOutputXML
```
And in `__all__`:
```python
'FileOutputXML',
'AdvancedFileOutputXML',
```

---

### `src/converters/talend_to_v1/components/file/__init__.py` (no-op)

Already imports `file_output_xml` (line 21 of existing file). Adding a second class to that same module requires no `__init__.py` change.

---

### `tests/v1/engine/components/file/test_file_input_xml.py` (NEW)

**Analog:** `tests/v1/engine/components/file/test_file_input_msxml.py` — exact match. Copy the test class layout (TestRegistry, TestValidateConfig, TestProcessMain, TestProcessReject, TestStats), the `_SAMPLE_XML` constant + `_write_xml` helper, the `_make_component` factory, and the `pytest.mark.unit` marker.

**Imports + helper pattern** (test_file_input_msxml.py lines 1–63, copy verbatim with renames):
```python
"""Tests for FileInputXML engine component (tFileInputXML).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessMain     -- happy-path XML file reading
    TestProcessReject   -- missing file, bad XPath
    TestStats           -- NB_LINE / NB_LINE_OK tracking
    TestParam<X>        -- per-param pos+neg per D-D1 (one class per javajet param)
    TestStreamingPath   -- threshold-switched iterparse (synthetic ~60MB fixture)
"""
import os
import tempfile
import textwrap

import pytest
import pandas as pd

from src.v1.engine.components.file.file_input_xml import FileInputXML
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, FileOperationError
from src.v1.engine.global_map import GlobalMap

_SAMPLE_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <bills>
      <bill><line><id>1</id><amount>10.5</amount></line></bill>
      <bill><line><id>2</id><amount>20.0</amount></line></bill>
    </bills>
""")
```

**Per-parameter pos+neg test class pattern** (RESEARCH.md Example 5):
```python
class TestParamLimit:
    """Per D-D1: positive + negative tests for the LIMIT parameter."""

    def test_limit_unlimited_when_empty_string(self): ...
    def test_limit_zero_reads_nothing(self): ...
    def test_limit_exceeds_available(self): ...
```

---

### `tests/v1/engine/components/file/test_file_output_xml.py` (NEW)

**Analog:** `tests/v1/engine/components/file/test_file_output_delimited.py` — sink test layout. Copy class structure (TestRegistry, TestValidateConfig, TestProcessMain, TestSplit, TestStreamingHook, TestStats, plus per-param classes per D-D1).

**Streaming-hook test pattern** (mirrors how test_file_output_delimited tests `_streaming_write_started`):
```python
class TestStreamingHook:
    def test_first_chunk_opens_file(self, tmp_path):
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        comp._process(_make_chunk_df(rows=10))
        assert comp._streaming_write_started is True

    def test_second_chunk_appends(self, tmp_path):
        ...

    def test_reset_closes_xmlfile_ctx(self, tmp_path):
        ...
```

---

### `tests/v1/engine/components/file/test_file_output_advanced_xml.py` (NEW)

Same analog and structure as `test_file_output_xml.py`. Add a class for ROOT/GROUP/LOOP TABLE-driven hierarchical emission and a test that fails if the implementation buffers the full tree (P-2 — assert `etree.xmlfile` is in the call graph).

---

### `tests/v1/engine/components/transform/test_xml_map.py` (NEW)

**Analog:** `tests/v1/engine/components/transform/test_extract_xml_fields.py` — exact transform test layout. ~35–50 tests target per RESEARCH.md.

**Critical test for P-6 (BUG-XMP-003 iloc[0,0] regression guard):**
```python
class TestMultiRowInput:
    def test_5_row_document_input_yields_per_row_output(self):
        """Regression guard for BUG-XMP-003 — must NOT use iloc[0,0]."""
        df_in = pd.DataFrame({"xml": [doc1, doc2, doc3, doc4, doc5]})
        result = comp._process(df_in)
        # 5 input rows, each Document has N looping_element matches → 5 × N output rows
        assert len(result["main"]) == 5 * EXPECTED_PER_DOC
```

---

### `tests/talend_xml_samples/Job_tFileOutputXML_*.item` (NEW hand-authored fixture)

**Analog:** `tests/talend_xml_samples/Job_tFileInputXML_0.1.item` (XML structure for an XML-related component) AND `tests/talend_xml_samples/Job_tFileOutputDelimited_0.1.item` (sink shape with FILENAME, MAPPING, framework params).

**Pattern:** Hand-author minimal `.item` with `<node componentName="tFileOutputXML">` + the 18 javajet parameters from RESEARCH.md lines 526–548 + a minimal schema. Validate by running `convert_job(<fixture>) -> ETLEngine.run_job()` end-to-end.

Recommended fixture variants (per RESEARCH.md sampling rate):
- `Job_tFileOutputXML_0.1.item` — flat-with-attributes
- (optional second fixture) `Job_tFileOutputXML_0.2.item` — with-namespace if Plan 6 chooses to cover it

---

### `tests/talend_xml_samples/Job_tAdvancedFileOutputXML_*.item` (NEW hand-authored fixture)

**Analog:** same as above. Hand-author the ROOT/GROUP/LOOP TABLE structure (33 params) per RESEARCH.md lines 558–578.

---

## Shared Patterns

### S-1. ASCII-only logging
**Source:** CLAUDE.md memory rule + `feedback_ascii_logging.md`
**Apply to:** ALL new/modified XML engine components, especially `xml_map.py` (replacing 46 `print()` calls)
```python
# Module-level
logger = logging.getLogger(__name__)

# In _process:
logger.info("[%s] done: file=%r ok=%d reject=%d", self.id, filepath, ok, rej)
```
No emojis, no unicode arrows, no checkmarks. Existing repo files use either `%`-style or f-strings; both are acceptable. Prefer `%`-style with `logger` (deferred formatting) for performance.

### S-2. Custom exception hierarchy
**Source:** `src/v1/engine/exceptions.py` (lines 1–60)
**Apply to:** ALL 6 in-scope XML engine components — never raise bare `RuntimeError`/`ValueError`.

| Situation | Exception |
|---|---|
| Missing required config key (`filename`, `loop_query`, etc.) | `ConfigurationError` |
| Bool-typed config received non-bool | `ConfigurationError` |
| File missing / parse failed / write failed | `FileOperationError` |
| Per-row XML parse failed (NOT `die_on_error`) → REJECT | (no exception — reject row) |
| Per-row XML parse failed AND `die_on_error=True` | `DataValidationError` |
| Bad XPath at config-time | `FileOperationError` (msxml line 122–125) or `DataValidationError` (extract_xml_fields style) |

Existing `file_input_xml.py` raises bare `RuntimeError` per audit STD-FIX-001 — fix in Plan 3.

### S-3. REJECT-row schema
**Source:** `src/v1/engine/components/file/file_input_msxml.py:154` and `src/v1/engine/components/transform/extract_xml_fields.py:251–260`
**Apply to:** All input components and xml_map (currently has NO reject — P1 fix).

```python
# Minimal (from msxml)
{"errorCode": "NODE_ERROR", "errorMessage": str(exc)}

# Per-row (from extract_xml_fields _make_reject_row)
{
    **row.to_dict(),                # carry-through input columns
    "errorXMLField": xml_string,
    "errorCode": "PARSE_ERROR",     # or NO_XML / NODECHECK_FAIL
    "errorMessage": str(exc),
}
```
Error-code constants live as class attributes:
```python
_ERR_NO_XML = "NO_XML"
_ERR_NODECHECK = "NODECHECK_FAIL"
_ERR_PARSE = "PARSE_ERROR"
```

### S-4. Secure XML parser (replaces deprecated `defusedxml.lxml`)
**Source:** `src/v1/engine/components/transform/extract_xml_fields.py:153-159` and `src/v1/engine/components/file/file_input_msxml.py:107-113`; centralized in NEW `src/v1/engine/components/file/_xml_io.py:secure_xml_parser()`
**Apply to:** All 6 in-scope components AT EVERY input boundary
```python
# Caller pattern after _xml_io exists:
from . import _xml_io

parser = _xml_io.secure_xml_parser(recover=False)
tree = etree.parse(filepath, parser=parser)
# OR for streaming:
yield from _xml_io.iterparse_loop_query(filepath, loop_tag)
```

**Anti-pattern (forbidden):** `from defusedxml.lxml import ...` — Phase 12 RESEARCH.md P-1 confirms upstream deprecation.

### S-5. Sink-component contract (passthrough + globalMap)
**Source:** `src/v1/engine/components/file/file_output_delimited.py:233-325` (CR-09 / ENG-CR-06)
**Apply to:** Both new output components (`file_output_xml.py`, `file_output_advanced_xml.py`)
```python
# 1. NEVER mutate input_data; build df_out = input_data.copy() if formatting needed
# 2. Write df_out to disk (xmlfile context)
# 3. globalMap puts:
self.global_map.put(f"{self.id}_FILE_NAME", str(resolved_path))
self.global_map.put(f"{self.id}_NB_LINE", total_written)
# 4. Return ORIGINAL input_data as 'main' (passthrough), reject=None
return {"main": input_data, "reject": None}
```

### S-6. Streaming-write state hook
**Source:** `src/v1/engine/components/file/file_output_delimited.py:108-119` (commit `bb5b97f`)
**Apply to:** Both new output components.

For XML specifically the held state is the `etree.xmlfile()` context manager (which CANNOT be re-opened across chunks because it would re-emit the XML declaration and root element). The pattern:
```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._streaming_xmlfile_ctx = None       # held across chunks
    self._streaming_xmlfile_root_ctx = None  # held across chunks
    self._streaming_write_started = False

def reset(self) -> None:
    super().reset()
    if self._streaming_xmlfile_root_ctx is not None:
        self._streaming_xmlfile_root_ctx.__exit__(None, None, None)
    if self._streaming_xmlfile_ctx is not None:
        self._streaming_xmlfile_ctx.__exit__(None, None, None)
    self._streaming_xmlfile_ctx = None
    self._streaming_xmlfile_root_ctx = None
    self._streaming_write_started = False
```

### S-7. Decorator-based registration
**Source:** `src/v1/engine/components/file/file_input_msxml.py:39` and `src/v1/engine/components/transform/extract_xml_fields.py:39`
**Apply to:** Add to `file_input_xml.py` (Plan 3) and `xml_map.py` (Plan 5); use on both new output components.
```python
@REGISTRY.register("FileInputXML", "tFileInputXML")
class FileInputXML(BaseComponent):
    ...
```
Both V1 PascalCase name and Talend `t`-prefix alias must be present, per the established pattern.

### S-8. Per-parameter pos+neg test discipline (D-D1)
**Source:** RESEARCH.md Example 5 lines 814–846; existing test class layout in `tests/v1/engine/components/file/test_file_input_msxml.py` lines 70–80
**Apply to:** All 5 new/extended test files. Each Talaxie javajet parameter gets a `class TestParam<NAME>` with at least one positive and one negative test.

### S-9. Hand-authored `.item` fixture pattern
**Source:** Existing `tests/talend_xml_samples/Job_tFileInputXML_0.1.item` (XML node shape) + `Job_tFileOutputDelimited_0.1.item` (sink-component shape)
**Apply to:** 3 new fixtures (Job_tFileInputMSXML_0.1.item, Job_tFileOutputXML_0.1.item, Job_tAdvancedFileOutputXML_0.1.item)
**Validation:** every new fixture must be runnable through `convert_job(fixture) -> ETLEngine.run_job()`.

### S-10. `_get_str` / `_get_bool` converter helper pattern
**Source:** `src/converters/talend_to_v1/components/file/file_output_delimited.py:60-89`; provided by `ComponentConverter` ABC
**Apply to:** New `FileOutputXMLConverter` in `src/converters/talend_to_v1/components/file/file_output_xml.py`
**Pattern:** every parameter extraction goes through `self._get_str(node, "PARAM_NAME", default)` or `self._get_bool(node, "PARAM_NAME", default)` — never `node.params.get(...)` directly except for TABLE params which need a custom parser (`_parse_xml_table`, etc.).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| (none) | -- | -- | Every Phase 12 file has a strong in-repo analog (lxml-based input components for input fixes, file_output_delimited for output streaming, msxml for tests). The hierarchical XML emission in `file_output_advanced_xml.py` is the only mildly novel pattern, and RESEARCH.md provides verified Example 4 from lxml 6.0 docs to anchor it. |

---

## Project Conventions (carry-through reminders for the planner)

These are global rules; PATTERNS.md flags them so each plan honors them without re-deriving from CLAUDE.md.

1. **Snake_case modules** — `file_input_xml.py`, `file_output_advanced_xml.py`, `_xml_io.py` (leading underscore = private/shared module).
2. **PascalCase classes ending in component name** — `FileInputXML`, `FileOutputXML`, `AdvancedFileOutputXML`.
3. **ASCII-only logging** (S-1) — no emojis, unicode arrows, checkmarks.
4. **Custom exceptions only** (S-2) — never `RuntimeError`/`ValueError`. The `xml_map.py:46` print()-fest must die in Plan 5.
5. **`from __future__ import annotations` is OPTIONAL on engine modules** — present on converter modules (`file_output_xml.py`-converter does NOT have it; project pattern is per-file). Engine files generally do NOT use it (msxml does not). Plan 3/5 should match neighbouring style: do NOT add `from __future__ import annotations` to engine modules unless other files in the same package use it.
6. **Component registration** — converter via `@REGISTRY.register("tComponentName")`; engine via `@REGISTRY.register("ComponentName", "tComponentName")` (both names). Trigger via `__init__.py` import.
7. **Tests live in mirrored paths** — `tests/v1/engine/components/{file,transform}/test_*.py` and `tests/converters/talend_to_v1/components/{file,transform}/test_*.py`.
8. **Fixtures in `tests/talend_xml_samples/`** — naming `Job_<TalendName>_0.1.item`.
9. **Encoding default is `ISO-8859-15`, NOT UTF-8** — javajet contract for tFileInputXML, tFileInputMSXML, tFileOutputXML, tAdvancedFileOutputXML. Carry through both converter and engine.
10. **`Rule 12` validate-config split** — `_validate_config` does presence/type checks ONLY; content/file-existence checks deferred to `_process` (after context resolution). Pattern from msxml lines 53–73.

---

## Metadata

**Analog search scope:**
- `src/v1/engine/components/file/` (all sibling components)
- `src/v1/engine/components/transform/` (all sibling components)
- `src/v1/engine/base_component.py`, `component_registry.py`, `exceptions.py`
- `src/converters/talend_to_v1/components/file/` (all sibling converters)
- `tests/v1/engine/components/file/`, `tests/v1/engine/components/transform/`
- `tests/talend_xml_samples/`

**Files scanned:** 12 source files + 4 test files + 3 fixture-paths + 4 supporting modules = 23 reads (within budget; one read per file, no re-reads).

**Pattern extraction date:** 2026-05-08

## PATTERN MAPPING COMPLETE
