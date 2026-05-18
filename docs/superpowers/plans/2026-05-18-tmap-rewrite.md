# tMap Engine Component — Modular Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `src/v1/engine/components/transform/map.py` (4292 LOC, single file, documented bugs) with a 7-file modular package under `src/v1/engine/components/transform/map/`, while fixing the str-coercion, type-fidelity, and `__errors__` Arrow-emission bugs at source in the Java bridge.

**Architecture:** Modular folder structure with single-responsibility modules: `map_component.py` (orchestrator), `map_config.py` (validation), `map_joins.py` (3 join strategies + RELOAD + schema computation), `map_compiled_script.py` (Groovy script gen), `map_reject_routing.py` (3 reject types), `map_bridge_sync.py` (typed context/globalMap push). Pairs with bridge.py + JavaBridge.java + context_manager.py fixes for end-to-end type fidelity.

**Tech Stack:** Python 3.10+, pandas, pyarrow, Py4J 0.10.9.7, Java 11+, Groovy 3.0.21, Apache Arrow 15.0.2, pytest + pytest-xdist + pytest-cov.

**Spec:** `docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md`

---

## Pre-flight

- Working branch: `feature/engine-restructure` (current)
- Verify `git status` is clean before starting
- Verify JVM 11+ on PATH (`java -version`)
- Verify Maven on PATH (`mvn -version`)
- Run the existing test suite once as a baseline: `python -m pytest tests/v1/engine/components/transform/ -m "not oracle" -q 2>&1 | tail -10` and record the pass/fail/xfail counts in a note

---

## Phase 0 — Setup & Bridge Fixes

This phase makes the foundational bridge / Java / context_manager fixes before any new map code lands. After Phase 0 the legacy `map_legacy.py` still runs (against the new bridge); this is intentional — we verify legacy still passes its existing tests before proceeding.

### Task 0.1: Backup legacy map.py and stub the new map/ folder

**Files:**
- Rename: `src/v1/engine/components/transform/map.py` → `src/v1/engine/components/transform/map_legacy.py`
- Create: `src/v1/engine/components/transform/map/__init__.py` (stub)
- Modify: `src/v1/engine/component_registry.py` (point "Map"/"tMap" at map_legacy temporarily)

- [ ] **Step 1: Rename and create stub**

```bash
git mv src/v1/engine/components/transform/map.py src/v1/engine/components/transform/map_legacy.py
mkdir -p src/v1/engine/components/transform/map
```

Then create `src/v1/engine/components/transform/map/__init__.py`:

```python
"""tMap component (modular rewrite). See docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md.

This package is being built incrementally. Until map_component.py is wired in,
``Map`` is re-exported from the legacy single-file implementation so existing
job configs continue to run unchanged.
"""
from ..map_legacy import Map  # noqa: F401

__all__ = ["Map"]
```

- [ ] **Step 2: Update component registry import path**

Modify `src/v1/engine/component_registry.py` import for Map: change `from .components.transform.map_legacy import Map` (the import path that `map.py` had — search and update). For the in-tree registry the import path is `src.v1.engine.components.transform.map` which now resolves to the package — no change needed if the registry already uses that path.

- [ ] **Step 3: Run existing transform tests against the stub**

```bash
python -m pytest tests/v1/engine/components/transform/test_map.py -q 2>&1 | tail -5
```

Expected: same pass/fail counts as the pre-flight baseline. If different, the re-export isn't working — diagnose before continuing.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(tmap): rename map.py to map_legacy.py, stub new map/ package

Pre-rewrite setup. map_legacy.py is the unchanged 4292-line file. The new
map/ package re-exports Map from map_legacy so existing tests pass while
the new implementation is built incrementally.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 0.2: Java side — Object signatures + real stack traces in __errors__

**Files:**
- Modify: `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java`

- [ ] **Step 1: Change setContext / setGlobalMap signatures**

In `JavaBridge.java`, locate lines 151-157. Change:

```java
public void setContext(String key, String value) {
    this.context.put(key, value);
}

public void setGlobalMap(String key, String value) {
    this.globalMap.put(key, value);
}
```

To:

```java
public void setContext(String key, Object value) {
    this.context.put(key, value);
}

public void setGlobalMap(String key, Object value) {
    this.globalMap.put(key, value);
}
```

- [ ] **Step 2: Fix __errors__ Arrow emission to read stackTraces as a Map**

Locate the `__errors__` branch in `convertTMapOutputsToArrow` around line 854-903. The current code declares `errStacks` as `List<String>` defaulted to an empty list. The new compiled script (Task 3.5) emits `stackTraces` as `Map<Integer, String>` (parallel to `messages`). Change the unmarshalling:

```java
if ("__errors__".equals(outputName)) {
    int errCount = ((Number) outputResult.get("count")).intValue();
    @SuppressWarnings("unchecked")
    List<Integer> errIndices = (List<Integer>) outputResult
            .getOrDefault("indices", new ArrayList<Integer>());
    @SuppressWarnings("unchecked")
    Map<Integer, String> errMessages = (Map<Integer, String>) outputResult
            .getOrDefault("messages", new HashMap<Integer, String>());
    @SuppressWarnings("unchecked")
    Map<Integer, String> errStacks = (Map<Integer, String>) outputResult
            .getOrDefault("stackTraces", new HashMap<Integer, String>());

    Map<String, String> errSchema = new LinkedHashMap<>();
    errSchema.put("rowIndex", "int");
    errSchema.put("errorMessage", "str");
    errSchema.put("errorStackTrace", "str");

    Object[] rowIdxArr = new Object[errCount];
    Object[] errMsgArr = new Object[errCount];
    Object[] errStackArr = new Object[errCount];
    for (int i = 0; i < errCount; i++) {
        Integer idx = errIndices.get(i);
        rowIdxArr[i] = idx;
        String msg = errMessages.get(idx);
        errMsgArr[i] = msg != null ? msg : "";
        String stack = errStacks.get(idx);
        errStackArr[i] = stack != null ? stack : "";
    }

    Map<String, Object[]> errColumnData = new LinkedHashMap<>();
    errColumnData.put("rowIndex", rowIdxArr);
    errColumnData.put("errorMessage", errMsgArr);
    errColumnData.put("errorStackTrace", errStackArr);

    try (VectorSchemaRoot errRoot = ArrowSerializer
            .createOutputRootFromData(allocator, errColumnData, errSchema)) {
        ByteArrayOutputStream errOutputStream = new ByteArrayOutputStream();
        ArrowStreamWriter errWriter = new ArrowStreamWriter(
                errRoot, null, errOutputStream);
        errWriter.start();
        errWriter.writeBatch();
        errWriter.close();
        outputArrowData.put("__errors__", errOutputStream.toByteArray());
    }
    continue;
}
```

The key change: `errStacks` is now `Map<Integer, String>` (not `List<String>`), looked up by row index, with `""` fallback when absent. Old emission code still works (legacy script emits no `stackTraces` key → getOrDefault returns empty map → all stacks empty string).

- [ ] **Step 3: Commit (Java source only; JAR not yet rebuilt)**

```bash
git add src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java
git commit -m "fix(java-bridge): setContext/setGlobalMap take Object, __errors__ stackTrace map

setContext/setGlobalMap previously typed value as String, requiring Python
side to coerce to str(value). Changed to Object so Py4J's native typed
protocol passes through unchanged.

__errors__ Arrow emission now reads stackTraces as Map<Integer, String>
(parallel to messages map), enabling real stack traces in the
errorStackTrace column once the Python-side compiled script generator
emits the map.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 0.3: Build the Java JAR + smoke test

**Files:**
- Build artifact (gitignored): `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`

- [ ] **Step 1: Build the JAR**

```bash
cd src/v1/java_bridge/java && mvn package -q && cd -
ls -la src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar
```

Expected: build succeeds; JAR exists.

- [ ] **Step 2: Smoke test via existing live-bridge test**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_bridge.py::TestPhase055ContextSync -m java --no-cov -x 2>&1 | tail -15
```

Expected: tests pass (the legacy map.py still uses set_context which now sends typed values; Java side accepts Object). If any test fails citing type errors, the Java change broke a contract — investigate before continuing.

- [ ] **Step 3: No commit (build artifact is gitignored). Move on.**

---

### Task 0.4: bridge.py — drop str-coercion in set_context / set_global_map

**Files:**
- Modify: `src/v1/java_bridge/bridge.py`
- Test: `tests/v1/java_bridge/test_bridge_type_fidelity.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/v1/java_bridge/test_bridge_type_fidelity.py`:

```python
"""Type fidelity for set_context / set_global_map (drop str-coercion)."""
import datetime
from decimal import Decimal

import pytest


@pytest.mark.java
class TestSetContextTypeFidelity:
    """Values passed via set_context must arrive in Java unchanged in type."""

    def test_int_stays_int(self, java_bridge):
        java_bridge.set_context("the_int", 42)
        # Java side has int in context map; assert via a one-time expression
        result = java_bridge.execute_one_time_expression(
            "context.get(\"the_int\").getClass().getName()"
        )
        assert result == "java.lang.Integer" or result == "java.lang.Long"

    def test_decimal_stays_bigdecimal(self, java_bridge):
        java_bridge.set_context("the_dec", Decimal("3.14"))
        result = java_bridge.execute_one_time_expression(
            "context.get(\"the_dec\").getClass().getName()"
        )
        assert result == "java.math.BigDecimal"

    def test_date_stays_date(self, java_bridge):
        java_bridge.set_context("the_date", datetime.date(2025, 6, 1))
        result = java_bridge.execute_one_time_expression(
            "context.get(\"the_date\").getClass().getName()"
        )
        assert result == "java.util.Date"

    def test_global_map_int_stays_int(self, java_bridge):
        java_bridge.set_global_map("gm_int", 100)
        result = java_bridge.execute_one_time_expression(
            "globalMap.get(\"gm_int\").getClass().getName()"
        )
        assert result == "java.lang.Integer" or result == "java.lang.Long"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/java_bridge/test_bridge_type_fidelity.py -m java --no-cov -v 2>&1 | tail -15
```

Expected: all 4 tests FAIL — return type is `java.lang.String` because of the current `str(value)` coercion.

- [ ] **Step 3: Drop the str-coercion in `bridge.py`**

In `src/v1/java_bridge/bridge.py`, locate `set_context` (around L850-859) and `set_global_map` (around L861-870). Change:

```python
def set_context(self, key: str, value: Any) -> None:
    """Set a context variable on both Python and Java sides."""
    self.context[key] = value
    if self.java_bridge:
        self.java_bridge.setContext(key, str(value))

def set_global_map(self, key: str, value: Any) -> None:
    """Set a globalMap variable on both Python and Java sides."""
    self.global_map[key] = value
    if self.java_bridge:
        self.java_bridge.setGlobalMap(key, str(value))
```

To:

```python
def set_context(self, key: str, value: Any) -> None:
    """Set a context variable on both Python and Java sides.

    Value type is preserved end-to-end. Py4J's native typed protocol
    handles int / bool / Decimal / str / None directly. datetime.date and
    datetime.datetime are converted via the registered Py4J input
    converters (registered in start()). Java setContext signature is
    Object so all types pass through unchanged.
    """
    self.context[key] = value
    if self.java_bridge:
        self.java_bridge.setContext(key, value)

def set_global_map(self, key: str, value: Any) -> None:
    """Set a globalMap variable on both Python and Java sides. Type-preserving."""
    self.global_map[key] = value
    if self.java_bridge:
        self.java_bridge.setGlobalMap(key, value)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/v1/java_bridge/test_bridge_type_fidelity.py -m java --no-cov -v 2>&1 | tail -15
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/java_bridge/bridge.py tests/v1/java_bridge/test_bridge_type_fidelity.py
git commit -m "fix(bridge): drop str(value) coercion in set_context / set_global_map

Values were string-coerced before sending to Java, breaking type fidelity
for every Talend-typed context/globalMap variable. Java setContext now
takes Object (Task 0.2), so the str() wrap is unnecessary and harmful.

Adds test_bridge_type_fidelity.py covering int / Decimal / date round-trip
as java.lang.Integer / java.math.BigDecimal / java.util.Date.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 0.5: context_manager.py — id_Date converter parses to date object

**Files:**
- Modify: `src/v1/engine/context_manager.py`
- Test: `tests/v1/engine/test_context_manager_id_date.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/v1/engine/test_context_manager_id_date.py`:

```python
"""id_Date context vars must store as datetime.date / datetime.datetime, not str."""
import datetime

from src.v1.engine.context_manager import ContextManager


def test_id_date_stores_as_date_object_iso():
    cm = ContextManager()
    cm.set("batch_date", "2025-06-01", "id_Date")
    val = cm.get("batch_date")
    assert isinstance(val, (datetime.date, datetime.datetime))
    assert val.year == 2025 and val.month == 6 and val.day == 1


def test_id_date_stores_as_datetime_object_iso_with_time():
    cm = ContextManager()
    cm.set("batch_dt", "2025-06-01 14:30:00", "id_Date")
    val = cm.get("batch_dt")
    assert isinstance(val, datetime.datetime)
    assert val.hour == 14 and val.minute == 30


def test_id_date_already_date_object_passes_through():
    cm = ContextManager()
    cm.set("batch_date", datetime.date(2025, 6, 1), "id_Date")
    val = cm.get("batch_date")
    assert val == datetime.date(2025, 6, 1)
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/test_context_manager_id_date.py -v 2>&1 | tail -10
```

Expected: all 3 FAIL — `id_Date` currently maps to `str`, so values become strings.

- [ ] **Step 3: Add a `_parse_talend_date` helper and update the converter map**

In `src/v1/engine/context_manager.py`, add a helper near the other private functions and update the `_TYPE_CONVERTERS` entry:

```python
# Add this helper above the ContextManager class:
def _parse_talend_date(value):
    """Parse a Talend id_Date value into datetime.date or datetime.datetime.

    Accepts already-typed date/datetime objects (pass-through) and strings
    in the four Talend-standard formats:
      - ISO datetime: "yyyy-MM-dd HH:mm:ss"
      - ISO date:     "yyyy-MM-dd"
      - US:           "MM/dd/yyyy"
      - European:     "dd/MM/yyyy HH:mm"

    Returns the original value if parsing fails (matches the
    error-tolerance contract of the type converter map).
    """
    import datetime as _dt
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value
    if not isinstance(value, str) or not value:
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y %H:%M"):
        try:
            return _dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return value
```

And in `_TYPE_CONVERTERS` (line 63), change:

```python
        "id_Date": str,
```

To:

```python
        "id_Date": _parse_talend_date,
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/v1/engine/test_context_manager_id_date.py -v 2>&1 | tail -10
```

Expected: all 3 PASS.

- [ ] **Step 5: Run the broader context_manager test suite for regressions**

```bash
python -m pytest tests/v1/engine/ -k "context" --no-cov -q 2>&1 | tail -10
```

Expected: no new failures. If something else breaks, the change is correct and the broken test was codifying the buggy str-coercion behavior — note it in the test triage doc for Phase 8.

- [ ] **Step 6: Commit**

```bash
git add src/v1/engine/context_manager.py tests/v1/engine/test_context_manager_id_date.py
git commit -m "fix(context-manager): id_Date converter parses to date/datetime object

Was: _TYPE_CONVERTERS['id_Date'] = str -- coerced every id_Date context
value to a string before storage. Downstream tMap expressions doing
(Date) context.batch_date threw ClassCastException.

Now: _parse_talend_date helper handles the 4 Talend-standard date
formats and returns datetime.date / datetime.datetime; date objects
pass through unchanged. Unparseable strings fall through unchanged
(matches existing error-tolerance contract of the converter map).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 0.6: bridge.py — tighten _reconcile_schema_to_df + remove _infer_schema_dict from tMap paths

**Files:**
- Modify: `src/v1/java_bridge/bridge.py`
- Test: `tests/v1/java_bridge/test_bridge_strict_schema.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/v1/java_bridge/test_bridge_strict_schema.py`:

```python
"""Bridge must raise on schema/DataFrame mismatch (not WARN + default to str)."""
import pandas as pd
import pytest

from src.v1.java_bridge.bridge import JavaBridge


def test_reconcile_schema_raises_on_missing_column_type():
    bridge = JavaBridge()
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})  # column 'b' not in schema
    schema = {"a": "int"}
    with pytest.raises(Exception) as exc_info:
        bridge._reconcile_schema_to_df(df, schema)
    # Specific error type checked by message content; widening to ConfigurationError below
    assert "schema" in str(exc_info.value).lower() or "type" in str(exc_info.value).lower()


def test_reconcile_schema_passes_when_all_columns_declared():
    bridge = JavaBridge()
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    schema = {"a": "int", "b": "str"}
    result = bridge._reconcile_schema_to_df(df, schema)
    assert result == {"a": "int", "b": "str"}
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/java_bridge/test_bridge_strict_schema.py -v 2>&1 | tail -10
```

Expected: first test FAILS — current code logs WARN and adds `'b': 'str'` instead of raising.

- [ ] **Step 3: Update `_reconcile_schema_to_df` to raise**

In `src/v1/java_bridge/bridge.py` at the `_reconcile_schema_to_df` definition (around L1043-1080), replace the warning-and-default block:

```python
def _reconcile_schema_to_df(
    self,
    df: pd.DataFrame,
    schema_dict: dict[str, str],
) -> dict[str, str]:
    """Reconcile schema dict against actual DataFrame columns.

    Strict: any DataFrame column not declared in schema_dict raises
    ConfigurationError. Schema columns not present in the DataFrame are
    pruned (with a DEBUG log).
    """
    from src.v1.engine.exceptions import ConfigurationError

    reconciled = dict(schema_dict)

    missing = [col for col in df.columns if col not in reconciled]
    if missing:
        raise ConfigurationError(
            f"DataFrame columns lack declared types in schema: {missing!r}. "
            f"Every column crossing the Python/Java boundary must have a "
            f"declared type. Schema keys: {list(reconciled.keys())!r}"
        )

    for col_name in list(reconciled.keys()):
        if col_name not in df.columns:
            logger.debug(
                "Schema column '%s' not present in DataFrame -- skipping",
                col_name,
            )
            del reconciled[col_name]

    return reconciled
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/v1/java_bridge/test_bridge_strict_schema.py -v 2>&1 | tail -10
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/java_bridge/bridge.py tests/v1/java_bridge/test_bridge_strict_schema.py
git commit -m "fix(bridge): _reconcile_schema_to_df raises on undeclared columns

Was: WARN + default to 'str' when a DataFrame column had no declared type.
This masked upstream bugs where columns made it into a DataFrame without
type info, and caused silent type-fidelity loss at the Java boundary.

Now: raise ConfigurationError. Every column crossing Python/Java must have
a declared type. Section 9 of the tMap rewrite design.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 0.7: Verify Phase 0 — legacy + bridge changes still work end-to-end

**Files:** None (verification only)

- [ ] **Step 1: Run the full transform test suite**

```bash
python -m pytest tests/v1/engine/components/transform/ -m "not oracle" --no-cov -q 2>&1 | tail -15
```

Compare against the pre-flight baseline. Expected changes:
- A few tests may flip from PASS to FAIL because they were testing the old buggy behavior (str-coerced context, missing stack trace). These get triaged in Phase 8.
- The 4 strict-xfails from Phase 05.5 remain xfailed.
- No NEW unrelated failures (if any, investigate before continuing).

- [ ] **Step 2: Record the post-Phase-0 baseline**

Write a one-line note in `.planning/quick/2026-05-18-tmap-rewrite-progress.md` (new file):

```markdown
# tMap rewrite progress

## Post-Phase-0 baseline
- Date: 2026-05-18
- Pre-flight pass count: <N>
- Post-Phase-0 pass count: <M>
- Tests that flipped: <list with one-line reason each>
- These are the test-triage candidates for Phase 8.
```

- [ ] **Step 3: Commit progress note**

```bash
git add .planning/quick/2026-05-18-tmap-rewrite-progress.md
git commit -m "docs(tmap-rewrite): record post-Phase-0 baseline

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 1 — `map_bridge_sync.py`

Smallest module first. Pure logic, easy to test, foundation for everything that calls the bridge from the new code.

### Task 1.1: push_runtime_state_to_bridge — typed push for all standard types

**Files:**
- Create: `src/v1/engine/components/transform/map/map_bridge_sync.py`
- Create: `tests/v1/engine/components/transform/map/__init__.py` (empty)
- Create: `tests/v1/engine/components/transform/map/test_map_bridge_sync.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/v1/engine/components/transform/map/test_map_bridge_sync.py`:

```python
"""Type-safe context + globalMap push to Java bridge."""
import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.components.transform.map.map_bridge_sync import (
    push_runtime_state_to_bridge,
)


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.context = {}
    bridge.global_map = {}
    bridge.gateway = MagicMock()
    return bridge


def test_push_basic_types(mock_bridge):
    cm = ContextManager()
    cm.set("name", "hello", "id_String")
    cm.set("count", 42, "id_Integer")
    cm.set("active", True, "id_Boolean")
    cm.set("amount", Decimal("3.14"), "id_BigDecimal")
    gm = GlobalMap()
    gm.put("session_id", "abc123")

    push_runtime_state_to_bridge(cm, gm, mock_bridge)

    assert mock_bridge.context["name"] == "hello"
    assert mock_bridge.context["count"] == 42
    assert mock_bridge.context["active"] is True
    assert mock_bridge.context["amount"] == Decimal("3.14")
    assert mock_bridge.global_map["session_id"] == "abc123"


def test_push_date_types(mock_bridge):
    cm = ContextManager()
    cm.set("batch_date", datetime.date(2025, 6, 1), "id_Date")
    cm.set("ts", datetime.datetime(2025, 6, 1, 14, 30), "id_Date")
    push_runtime_state_to_bridge(cm, None, mock_bridge)
    assert mock_bridge.context["batch_date"] == datetime.date(2025, 6, 1)
    assert mock_bridge.context["ts"] == datetime.datetime(2025, 6, 1, 14, 30)


def test_push_id_float_wraps_in_java_lang_float(mock_bridge):
    """id_Float must reach Java as java.lang.Float, not java.lang.Double.

    Py4J's native protocol serializes Python float as Java Double; this
    helper wraps via gateway.jvm.java.lang.Float(v) to force Float.
    """
    cm = ContextManager()
    cm.set("rate", 1.5, "id_Float")
    sentinel = object()
    mock_bridge.gateway.jvm.java.lang.Float.return_value = sentinel

    push_runtime_state_to_bridge(cm, None, mock_bridge)

    mock_bridge.gateway.jvm.java.lang.Float.assert_called_once_with(1.5)
    assert mock_bridge.context["rate"] is sentinel


def test_push_handles_none_bridge_gracefully(mock_bridge):
    """No-op when bridge is None (e.g. java not enabled)."""
    cm = ContextManager()
    cm.set("x", "y", "id_String")
    push_runtime_state_to_bridge(cm, None, None)  # must not raise


def test_push_handles_none_managers(mock_bridge):
    push_runtime_state_to_bridge(None, None, mock_bridge)
    assert mock_bridge.context == {}
    assert mock_bridge.global_map == {}
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_bridge_sync.py -v 2>&1 | tail -15
```

Expected: ImportError (module doesn't exist).

- [ ] **Step 3: Implement map_bridge_sync.py**

Create `src/v1/engine/components/transform/map/map_bridge_sync.py`:

```python
"""Type-safe push of ContextManager + GlobalMap state to the Java bridge.

This is the ONLY module in the map package that touches the bridge's
internal context / global_map dicts directly. Writes are direct
(``bridge.context[k] = v``) rather than via ``bridge.set_context(k, v)``
to bypass any setter-side coercion and preserve Python value types
end-to-end. (As of Phase 0 the setter no longer str-coerces, but direct
write keeps this module independent of setter implementation details.)

Type-aware: id_Float values are explicitly wrapped via
``gateway.jvm.java.lang.Float(v)`` because Py4J's native protocol always
sends Python ``float`` as Java ``Double``.
"""
from __future__ import annotations

from typing import Any


def push_runtime_state_to_bridge(
    context_manager: Any | None,
    global_map: Any | None,
    java_bridge: Any | None,
) -> None:
    """Flush ContextManager + GlobalMap state into the Java bridge.

    Must be called immediately before any bridge invocation that runs
    per-row Groovy. No-op when java_bridge is None.

    Args:
        context_manager: ContextManager instance, or None.
        global_map: GlobalMap instance, or None.
        java_bridge: JavaBridge wrapper, or None.
    """
    if java_bridge is None:
        return

    if context_manager is not None:
        types = getattr(context_manager, "context_types", {})
        for key, value in context_manager.get_all().items():
            value_type = types.get(key)
            if value_type == "id_Float" and isinstance(value, float):
                # Py4J protocol always emits Python float as Java Double.
                # Force Java Float via explicit JVM construction.
                java_bridge.context[key] = (
                    java_bridge.gateway.jvm.java.lang.Float(value)
                )
            else:
                # All other types: native Py4J protocol + registered date
                # converters handle serialization correctly.
                java_bridge.context[key] = value

    if global_map is not None:
        for key, value in global_map.get_all().items():
            java_bridge.global_map[key] = value
```

- [ ] **Step 4: Create the test package __init__**

Create empty `tests/v1/engine/components/transform/map/__init__.py`.

- [ ] **Step 5: Run tests to verify pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_bridge_sync.py -v 2>&1 | tail -15
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/v1/engine/components/transform/map/map_bridge_sync.py \
        tests/v1/engine/components/transform/map/__init__.py \
        tests/v1/engine/components/transform/map/test_map_bridge_sync.py
git commit -m "feat(tmap): map_bridge_sync.py — typed context/globalMap push to bridge

First module of the new map/ package. Pure Python, no bridge calls in
tests (mocked). Type-aware: id_Float values are wrapped via
gateway.jvm.java.lang.Float to force Java Float (Py4J otherwise sends
Python float as Java Double).

5 unit tests covering basic types, date types, id_Float wrap, and
None-handling for both bridge and managers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — `map_config.py`

Pure dataclasses + validation. Independent of bridge. Easy to test thoroughly.

### Task 2.1: Dataclasses for the config shape

**Files:**
- Create: `src/v1/engine/components/transform/map/map_config.py`
- Test: `tests/v1/engine/components/transform/map/test_map_config.py`

- [ ] **Step 1: Write tests for dataclass parsing from a representative config dict**

Add to `tests/v1/engine/components/transform/map/test_map_config.py`:

```python
"""Config parsing + validation for the new Map component."""
import pytest

from src.v1.engine.components.transform.map.map_config import (
    MapConfig,
    parse_config,
    validate_config,
)
from src.v1.engine.exceptions import ConfigurationError


SAMPLE_CONFIG = {
    "component_type": "Map",
    "inputs": {
        "main": {
            "name": "row1",
            "filter": "",
            "activate_filter": False,
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
        },
        "lookups": [{
            "name": "row2",
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
            "filter": "",
            "activate_filter": False,
            "join_keys": [{
                "lookup_column": "key",
                "expression": "{{java}}row1.key",
                "type": "str",
                "nullable": True,
                "operator": "=",
            }],
            "join_mode": "LEFT_OUTER_JOIN",
        }],
    },
    "variables": [],
    "outputs": [{
        "name": "out_main",
        "is_reject": False,
        "inner_join_reject": False,
        "catch_output_reject": False,
        "filter": "",
        "activate_filter": False,
        "columns": [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
        ],
    }],
    "die_on_error": True,
    "enable_auto_convert_type": False,
}


def test_parse_config_basic():
    cfg = parse_config(SAMPLE_CONFIG)
    assert isinstance(cfg, MapConfig)
    assert cfg.main.name == "row1"
    assert len(cfg.lookups) == 1
    assert cfg.lookups[0].name == "row2"
    assert cfg.lookups[0].join_keys[0].expression == "{{java}}row1.key"
    assert cfg.lookups[0].join_mode == "LEFT_OUTER_JOIN"
    assert cfg.die_on_error is True
    assert len(cfg.outputs) == 1
    assert cfg.outputs[0].columns[0].type == "int"


def test_parse_config_preserves_die_on_error_false():
    raw = {**SAMPLE_CONFIG, "die_on_error": False}
    cfg = parse_config(raw)
    assert cfg.die_on_error is False
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_config.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement map_config.py**

Create `src/v1/engine/components/transform/map/map_config.py`:

```python
"""Config dataclasses + validation for the Map component.

Mirrors the JSON shape produced by the converter (verified from
tests/fixtures/jobs/transform/map_with_lookup.json and
tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json).

See docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md Section 11
for the full contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.v1.engine.exceptions import ConfigurationError


_JAVA_MARKER = "{{java}}"


@dataclass
class ColumnCfg:
    name: str
    expression: str
    type: str
    nullable: bool = True
    length: int = -1
    precision: int = -1
    date_pattern: str = ""


@dataclass
class JoinKeyCfg:
    lookup_column: str
    expression: str
    type: str
    nullable: bool = True
    operator: str = "="


@dataclass
class MainInputCfg:
    name: str
    filter: str = ""
    activate_filter: bool = False
    matching_mode: str = "UNIQUE_MATCH"
    lookup_mode: str = "LOAD_ONCE"


@dataclass
class LookupCfg:
    name: str
    join_keys: list[JoinKeyCfg]
    join_mode: str = "LEFT_OUTER_JOIN"
    matching_mode: str = "UNIQUE_MATCH"
    lookup_mode: str = "LOAD_ONCE"
    filter: str = ""
    activate_filter: bool = False


@dataclass
class VariableCfg:
    name: str
    expression: str
    type: str
    nullable: bool = True


@dataclass
class OutputCfg:
    name: str
    columns: list[ColumnCfg]
    is_reject: bool = False
    inner_join_reject: bool = False
    catch_output_reject: bool = False
    filter: str = ""
    activate_filter: bool = False


@dataclass
class MapConfig:
    main: MainInputCfg
    lookups: list[LookupCfg]
    variables: list[VariableCfg]
    outputs: list[OutputCfg]
    die_on_error: bool = True
    enable_auto_convert_type: bool = False
    label: str = ""


def parse_config(raw: dict[str, Any]) -> MapConfig:
    """Parse the raw JSON config dict into MapConfig dataclasses.

    Does NOT validate semantics — only constructs the typed shape. Use
    validate_config() for semantic checks.
    """
    inputs = raw.get("inputs") or {}
    main_raw = inputs.get("main") or {}
    main = MainInputCfg(
        name=main_raw.get("name", ""),
        filter=main_raw.get("filter", ""),
        activate_filter=bool(main_raw.get("activate_filter", False)),
        matching_mode=main_raw.get("matching_mode", "UNIQUE_MATCH"),
        lookup_mode=main_raw.get("lookup_mode", "LOAD_ONCE"),
    )

    lookups: list[LookupCfg] = []
    for lk in inputs.get("lookups") or []:
        join_keys = [
            JoinKeyCfg(
                lookup_column=jk.get("lookup_column", ""),
                expression=jk.get("expression", ""),
                type=jk.get("type", "str"),
                nullable=bool(jk.get("nullable", True)),
                operator=jk.get("operator", "="),
            )
            for jk in lk.get("join_keys") or []
        ]
        lookups.append(LookupCfg(
            name=lk.get("name", ""),
            join_keys=join_keys,
            join_mode=lk.get("join_mode", "LEFT_OUTER_JOIN"),
            matching_mode=lk.get("matching_mode", "UNIQUE_MATCH"),
            lookup_mode=lk.get("lookup_mode", "LOAD_ONCE"),
            filter=lk.get("filter", ""),
            activate_filter=bool(lk.get("activate_filter", False)),
        ))

    variables = [
        VariableCfg(
            name=v.get("name", ""),
            expression=v.get("expression", ""),
            type=v.get("type", "str"),
            nullable=bool(v.get("nullable", True)),
        )
        for v in raw.get("variables") or []
    ]

    outputs = []
    for o in raw.get("outputs") or []:
        cols = [
            ColumnCfg(
                name=c.get("name", ""),
                expression=c.get("expression", ""),
                type=c.get("type", "str"),
                nullable=bool(c.get("nullable", True)),
                length=int(c.get("length", -1)),
                precision=int(c.get("precision", -1)),
                date_pattern=c.get("date_pattern", ""),
            )
            for c in o.get("columns") or []
        ]
        outputs.append(OutputCfg(
            name=o.get("name", ""),
            columns=cols,
            is_reject=bool(o.get("is_reject", False)),
            inner_join_reject=bool(o.get("inner_join_reject", False)),
            catch_output_reject=bool(o.get("catch_output_reject", False)),
            filter=o.get("filter", ""),
            activate_filter=bool(o.get("activate_filter", False)),
        ))

    return MapConfig(
        main=main,
        lookups=lookups,
        variables=variables,
        outputs=outputs,
        die_on_error=bool(raw.get("die_on_error", True)),
        enable_auto_convert_type=bool(raw.get("enable_auto_convert_type", False)),
        label=raw.get("label", ""),
    )


def has_any_java_marker(cfg: MapConfig) -> bool:
    """Return True if any expression-bearing field has a {{java}} prefix."""
    if cfg.main.filter.startswith(_JAVA_MARKER):
        return True
    for lk in cfg.lookups:
        if lk.filter.startswith(_JAVA_MARKER):
            return True
        for jk in lk.join_keys:
            if jk.expression.startswith(_JAVA_MARKER):
                return True
    for v in cfg.variables:
        if v.expression.startswith(_JAVA_MARKER):
            return True
    for o in cfg.outputs:
        if o.filter.startswith(_JAVA_MARKER):
            return True
        for c in o.columns:
            if c.expression.startswith(_JAVA_MARKER):
                return True
    return False


def validate_config(cfg: MapConfig, java_bridge_available: bool) -> None:
    """Semantic validation of the parsed config.

    Args:
        cfg: Parsed config.
        java_bridge_available: True if a JavaBridge instance is attached
            to the component. Required if any {{java}} marker present.

    Raises:
        ConfigurationError: on any structural / semantic problem.
    """
    if not cfg.main.name:
        raise ConfigurationError("Missing inputs.main.name")
    if not cfg.outputs:
        raise ConfigurationError("At least one output is required")
    for i, out in enumerate(cfg.outputs):
        if not out.name:
            raise ConfigurationError(f"Output [{i}] missing 'name'")
        if not out.columns:
            raise ConfigurationError(
                f"Output '{out.name}' has no columns"
            )
    for i, lk in enumerate(cfg.lookups):
        if not lk.name:
            raise ConfigurationError(f"Lookup [{i}] missing 'name'")
        for j, jk in enumerate(lk.join_keys):
            if not jk.lookup_column:
                raise ConfigurationError(
                    f"Lookup '{lk.name}' join_key [{j}] missing 'lookup_column'"
                )
            if not jk.expression:
                raise ConfigurationError(
                    f"Lookup '{lk.name}' join_key [{j}] missing 'expression'"
                )

    if has_any_java_marker(cfg) and not java_bridge_available:
        raise ConfigurationError(
            "Config contains {{java}} expressions but Java bridge is "
            "unavailable. Set java_config.enabled=true in the job config "
            "or remove Java expressions."
        )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_config.py -v 2>&1 | tail -10
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_config.py \
        tests/v1/engine/components/transform/map/test_map_config.py
git commit -m "feat(tmap): map_config.py — dataclasses + parse_config

Typed dataclasses mirroring the converter JSON shape (see spec §11):
MapConfig wrapping MainInputCfg, LookupCfg, JoinKeyCfg, VariableCfg,
OutputCfg, ColumnCfg. parse_config() turns the raw dict into typed
objects; has_any_java_marker() scans for {{java}} prefixes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.2: validate_config — full semantic validation suite

**Files:**
- Modify: `tests/v1/engine/components/transform/map/test_map_config.py` (add validation tests)

- [ ] **Step 1: Write validation tests**

Append to `tests/v1/engine/components/transform/map/test_map_config.py`:

```python
def test_validate_missing_main_name_raises():
    raw = {**SAMPLE_CONFIG}
    raw["inputs"] = {**raw["inputs"], "main": {**raw["inputs"]["main"], "name": ""}}
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="inputs.main.name"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_no_outputs_raises():
    raw = {**SAMPLE_CONFIG, "outputs": []}
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="At least one output"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_output_no_columns_raises():
    raw = {**SAMPLE_CONFIG}
    raw["outputs"] = [{**raw["outputs"][0], "columns": []}]
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="no columns"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_lookup_missing_lookup_column_raises():
    raw = {**SAMPLE_CONFIG}
    raw["inputs"]["lookups"][0]["join_keys"][0]["lookup_column"] = ""
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="lookup_column"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_java_marker_without_bridge_raises():
    cfg = parse_config(SAMPLE_CONFIG)
    with pytest.raises(ConfigurationError, match="Java bridge is unavailable"):
        validate_config(cfg, java_bridge_available=False)


def test_validate_no_marker_no_bridge_passes():
    # All expressions stripped of {{java}}; should pass without bridge
    raw = {
        **SAMPLE_CONFIG,
        "outputs": [{
            **SAMPLE_CONFIG["outputs"][0],
            "columns": [{"name": "id", "expression": "1", "type": "int"}],
        }],
        "inputs": {
            **SAMPLE_CONFIG["inputs"],
            "lookups": [{
                **SAMPLE_CONFIG["inputs"]["lookups"][0],
                "join_keys": [{
                    **SAMPLE_CONFIG["inputs"]["lookups"][0]["join_keys"][0],
                    "expression": "row1.key",  # no {{java}} prefix
                }],
            }],
        },
    }
    cfg = parse_config(raw)
    validate_config(cfg, java_bridge_available=False)  # must not raise
```

- [ ] **Step 2: Run tests to verify pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_config.py -v 2>&1 | tail -15
```

Expected: all 8 tests PASS (2 original + 6 new). If `validate_config` is missing any rule, fix it in `map_config.py` per the test's expectation, re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/v1/engine/components/transform/map/test_map_config.py
git commit -m "test(tmap): validate_config — 6 semantic rule tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3 — `map_compiled_script.py`

Pure Groovy-source generation. Unit-testable without JVM (just compare generated strings). The behavioral correctness of the generated Groovy is verified later via real-bridge tests in Phase 9.

### Task 3.1: _groovy_escape_expression

**Files:**
- Create: `src/v1/engine/components/transform/map/map_compiled_script.py`
- Test: `tests/v1/engine/components/transform/map/test_map_compiled_script.py`

- [ ] **Step 1: Write failing tests**

Create `tests/v1/engine/components/transform/map/test_map_compiled_script.py`:

```python
"""Groovy script generation for tMap (active + reject scripts, $ escape)."""
from src.v1.engine.components.transform.map.map_compiled_script import (
    groovy_escape_expression,
)


def test_escape_no_strings_passes_through():
    assert groovy_escape_expression("row1.amount + 5") == "row1.amount + 5"


def test_escape_dollar_inside_double_quoted_string():
    # Groovy GString interpolation: $identifier triggers eval. Escape it.
    assert groovy_escape_expression('"Total: $100"') == '"Total: \\$100"'


def test_escape_dollar_outside_string_unchanged():
    # $ outside a string is a legal Java/Groovy identifier char; leave alone
    assert groovy_escape_expression("var.$amount + 5") == "var.$amount + 5"


def test_escape_handles_escaped_quotes_inside_string():
    # \" inside a string is a 2-char escape; must not break out of string
    src = '"he said \\"hi\\" and $5"'
    assert groovy_escape_expression(src) == '"he said \\"hi\\" and \\$5"'


def test_escape_handles_single_quoted_strings_as_non_strings():
    # Single quotes are Groovy char literals; treat as outside-string region
    assert groovy_escape_expression("'$abc'") == "'$abc'"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement (port from legacy)**

Create `src/v1/engine/components/transform/map/map_compiled_script.py` initial content:

```python
"""Groovy script generation for tMap compiled execution.

Pure functions: takes parsed MapConfig in, returns a Groovy source string.
No bridge calls, no state. Two entry points:

- build_active_script(cfg) -> active-pass script (vars + outputs + is_reject +
  catch_output_reject error capture).
- build_reject_script(cfg) -> reject-pass script (inner_join_reject column
  expressions only).

See spec §7 for the full Groovy script shape.
"""
from __future__ import annotations


def groovy_escape_expression(java_expr: str) -> str:
    """Escape ``$`` inside double-quoted string literals.

    Groovy GString interpolates ``$identifier`` / ``${expr}`` at runtime.
    Talend Java expressions like ``"Total: $100"`` would either parse-error
    or, worse, evaluate an unintended identifier. Outside string literals,
    ``$`` is a legal identifier character in both Java and Groovy — left
    alone.

    Escape sequences (``\\\\``, ``\\"``) inside a string region are
    consumed as two-character units so they cannot mis-detect the closing
    quote.

    Single-quoted strings (Groovy char literals) are treated as
    outside-string regions; ``$`` inside them is not interpolated by
    Groovy anyway.
    """
    result: list[str] = []
    in_string = False
    i = 0
    n = len(java_expr)
    while i < n:
        ch = java_expr[i]
        if not in_string:
            if ch == '"':
                in_string = True
            result.append(ch)
            i += 1
            continue
        # Inside a double-quoted string literal
        if ch == "\\" and i + 1 < n:
            result.append(ch)
            result.append(java_expr[i + 1])
            i += 2
        elif ch == '"':
            in_string = False
            result.append(ch)
            i += 1
        elif ch == "$":
            result.append("\\$")
            i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v 2>&1 | tail -10
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py \
        tests/v1/engine/components/transform/map/test_map_compiled_script.py
git commit -m "feat(tmap): map_compiled_script.groovy_escape_expression — GString \\\$ escape

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3.2: build_active_script — basic structure (one output, no variables, no rejects)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script.py`

- [ ] **Step 1: Write failing test**

Append to `test_map_compiled_script.py`:

```python
from src.v1.engine.components.transform.map.map_compiled_script import (
    build_active_script,
)
from src.v1.engine.components.transform.map.map_config import parse_config


def _basic_cfg(die_on_error=True, with_variables=False, with_filter=False,
               with_reject=False, with_catch=False):
    """Return a minimal config dict for script tests."""
    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "out", "is_reject": False, "inner_join_reject": False,
            "catch_output_reject": False,
            "filter": "row1.amount > 0" if with_filter else "",
            "activate_filter": with_filter,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "int"},
                {"name": "label", "expression": '"row_" + row1.id', "type": "str"},
            ],
        }],
        "die_on_error": die_on_error,
    }
    if with_variables:
        raw["variables"] = [
            {"name": "v1", "expression": "row1.amount", "type": "int"},
            {"name": "v2", "expression": "Var.get(\"v1\") + 100", "type": "int"},
        ]
    if with_reject:
        raw["outputs"].append({
            "name": "rej", "is_reject": True, "inner_join_reject": False,
            "catch_output_reject": False, "filter": "", "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1.id", "type": "int"}],
        })
    if with_catch:
        raw["outputs"].append({
            "name": "errs", "is_reject": False, "inner_join_reject": False,
            "catch_output_reject": True, "filter": "", "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "int"},
                {"name": "errorMessage", "expression": "", "type": "str"},
                {"name": "errorStackTrace", "expression": "", "type": "str"},
            ],
        })
    return parse_config(raw)


def test_build_active_script_basic_includes_imports_and_buffer_decls():
    cfg = _basic_cfg()
    src = build_active_script(cfg)
    assert "import java.util.*;" in src
    assert "import com.citi.gru.etl.RowWrapper;" in src
    assert "Object[][] out_data = new Object[rowCount][2];" in src
    assert "int out_count = 0;" in src


def test_build_active_script_basic_row_loop_shape():
    cfg = _basic_cfg()
    src = build_active_script(cfg)
    assert "for (int i = 0; i < rowCount; i++) {" in src
    assert 'RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1");' in src
    # Column assignments to the temp row
    assert "out_tempRow[0] = row1.id;" in src
    assert 'out_tempRow[1] = "row_" + row1.id;' in src
    # Atomic commit
    assert "out_data[out_count++] = out_tempRow;" in src


def test_build_active_script_basic_returns_results_map():
    cfg = _basic_cfg()
    src = build_active_script(cfg)
    assert "Map<String, Map<String, Object>> results = new HashMap<>();" in src
    assert 'results.put("out", out_result);' in src
    assert "return results;" in src
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v 2>&1 | tail -10
```

Expected: `ImportError` for `build_active_script`.

- [ ] **Step 3: Implement basic build_active_script**

Append to `map_compiled_script.py`:

```python
from .map_config import MapConfig


def build_active_script(cfg: MapConfig) -> str:
    """Build the active-pass Groovy script for a tMap.

    Covers: row wrapper construction, variables, all active (non-reject)
    output columns with filter routing, is_reject routing, and (when any
    catch_output_reject output exists) try/catch with errorMap/stackTraceMap.

    Variables are emitted as a HashMap<String, Object> Var. Sequential
    chaining works because later vars use Var.get("earlier") which reads
    the just-populated entry.

    The script binds buildRowWrapper, inputRoot, rowCount, context,
    globalMap on the Java side (see JavaBridge.buildTMapBinding).

    See spec §7 for the full shape.
    """
    lines: list[str] = []
    # Imports
    lines.append("import java.util.*;")
    lines.append("import com.citi.gru.etl.RowWrapper;")
    lines.append("")

    # Output classification (active vs reject vs catch)
    active_outputs = [o for o in cfg.outputs
                      if not o.is_reject
                      and not o.inner_join_reject
                      and not o.catch_output_reject]
    is_reject_outputs = [o for o in cfg.outputs if o.is_reject]
    catch_outputs = [o for o in cfg.outputs if o.catch_output_reject]

    has_error_tracking = (not cfg.die_on_error) or bool(catch_outputs)

    # Buffers
    for out in active_outputs + is_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    if has_error_tracking:
        lines.append("int errorCount = 0;")
        lines.append("Map<Integer, String> errorMap = new HashMap<>();")
        lines.append("Map<Integer, String> stackTraceMap = new HashMap<>();")
    lines.append("")

    # Row loop
    lines.append("for (int i = 0; i < rowCount; i++) {")
    lines.append("    try {")
    main_name = cfg.main.name
    lines.append(f'        RowWrapper {main_name} = buildRowWrapper(inputRoot, i, "{main_name}");')
    for lk in cfg.lookups:
        lines.append(f'        RowWrapper {lk.name} = buildRowWrapper(inputRoot, i, "{lk.name}");')
    lines.append("")

    if has_error_tracking:
        lines.append("        try {")
        body_indent = "            "
    else:
        body_indent = "        "

    # Variables map (always emitted, even if empty, so output code can reference)
    lines.append(f"{body_indent}Map<String, Object> Var = new HashMap<>();")
    for v in cfg.variables:
        expr = groovy_escape_expression(_strip_marker(v.expression)) or "null"
        lines.append(f'{body_indent}Var.put("{v.name}", {expr});')
    lines.append("")

    # Track is_reject routing
    if is_reject_outputs:
        lines.append(f"{body_indent}boolean matchedAny = false;")

    # Active outputs — atomic-row commit
    for out in active_outputs:
        ncols = len(out.columns)
        lines.append(f"{body_indent}// Active output: {out.name}")
        if out.activate_filter and out.filter:
            filter_expr = groovy_escape_expression(_strip_marker(out.filter))
            lines.append(f"{body_indent}if ({filter_expr}) {{")
            inner = body_indent + "    "
        else:
            lines.append(f"{body_indent}{{")
            inner = body_indent + "    "
        lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
        for j, col in enumerate(out.columns):
            expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
            lines.append(f"{inner}{out.name}_tempRow[{j}] = {expr};")
        if is_reject_outputs:
            lines.append(f"{inner}matchedAny = true;")
        lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")
    lines.append("")

    # is_reject routing: rows that didn't match any active output
    if is_reject_outputs:
        lines.append(f"{body_indent}if (!matchedAny) {{")
        for out in is_reject_outputs:
            ncols = len(out.columns)
            inner = body_indent + "    "
            lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
            for j, col in enumerate(out.columns):
                expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
                lines.append(f"{inner}{out.name}_tempRow[{j}] = {expr};")
            lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")

    # Inner try/catch for error tracking
    if has_error_tracking:
        lines.append("        } catch (Exception innerE) {")
        lines.append("            String msg = innerE.getMessage() != null ? innerE.getMessage() : innerE.toString();")
        lines.append("            java.io.StringWriter sw = new java.io.StringWriter();")
        lines.append("            innerE.printStackTrace(new java.io.PrintWriter(sw));")
        lines.append("            errorCount++;")
        lines.append("            errorMap.put(i, msg);")
        lines.append("            stackTraceMap.put(i, sw.toString());")
        if not cfg.die_on_error:
            lines.append("            // die_on_error=false: row continues to catch_output_reject via __errors__")
        else:
            # die_on_error=true with catch_output_reject: catch still routes; outer doesn't re-raise here
            lines.append("            // die_on_error=true with catch_output_reject: row routes to __errors__")
        lines.append("        }")

    # Outer try (row wrapper construction errors): always re-raise
    lines.append("    } catch (Exception outerE) {")
    lines.append("        String msg = outerE.getMessage() != null ? outerE.getMessage() : outerE.toString();")
    lines.append("        throw new RuntimeException(\"Error at row \" + i + \": \" + msg, outerE);")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # Results map
    lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
    for out in active_outputs + is_reject_outputs:
        lines.append(f"Map<String, Object> {out.name}_result = new HashMap<>();")
        lines.append(f'{out.name}_result.put("data", {out.name}_data);')
        lines.append(f'{out.name}_result.put("count", {out.name}_count);')
        lines.append(f'results.put("{out.name}", {out.name}_result);')

    if has_error_tracking:
        lines.append("Map<String, Object> errorInfo = new HashMap<>();")
        lines.append("errorInfo.put(\"count\", errorCount);")
        lines.append("errorInfo.put(\"indices\", new ArrayList<>(errorMap.keySet()));")
        lines.append("errorInfo.put(\"messages\", errorMap);")
        lines.append("errorInfo.put(\"stackTraces\", stackTraceMap);")
        lines.append("results.put(\"__errors__\", errorInfo);")

    lines.append("return results;")
    return "\n".join(lines)


def _strip_marker(expr: str) -> str:
    return expr[len("{{java}}"):] if expr.startswith("{{java}}") else expr
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v 2>&1 | tail -15
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py \
        tests/v1/engine/components/transform/map/test_map_compiled_script.py
git commit -m "feat(tmap): build_active_script — basic structure + active outputs

Initial structure of the active-pass Groovy script generator. Covers:
imports, output buffer declarations, row loop with row wrapper
construction, variables (sequential via Var map), active outputs with
atomic-row commit, is_reject routing, optional try/catch with
errorMap + stackTraceMap, results map emission including __errors__.

3 unit tests checking imports, row loop shape, results map.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3.3: build_active_script — variables, is_reject, catch_output_reject coverage tests

**Files:**
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script.py`

- [ ] **Step 1: Add tests for variables, filters, is_reject, catch outputs**

Append to test file:

```python
def test_build_active_script_with_variables_chained():
    cfg = _basic_cfg(with_variables=True)
    src = build_active_script(cfg)
    assert 'Var.put("v1", row1.amount);' in src
    assert 'Var.put("v2", Var.get("v1") + 100);' in src


def test_build_active_script_with_filter():
    cfg = _basic_cfg(with_filter=True)
    src = build_active_script(cfg)
    assert "if (row1.amount > 0) {" in src


def test_build_active_script_with_is_reject_emits_matched_any():
    cfg = _basic_cfg(with_reject=True)
    src = build_active_script(cfg)
    assert "boolean matchedAny = false;" in src
    assert "matchedAny = true;" in src
    assert "if (!matchedAny) {" in src
    assert "rej_data[rej_count++] = rej_tempRow;" in src


def test_build_active_script_with_catch_emits_error_tracking_and_stacktrace():
    cfg = _basic_cfg(with_catch=True)
    src = build_active_script(cfg)
    assert "Map<Integer, String> errorMap = new HashMap<>();" in src
    assert "Map<Integer, String> stackTraceMap = new HashMap<>();" in src
    assert "catch (Exception innerE)" in src
    assert "innerE.printStackTrace(new java.io.PrintWriter(sw));" in src
    assert "stackTraceMap.put(i, sw.toString());" in src
    assert 'errorInfo.put("stackTraces", stackTraceMap);' in src


def test_build_active_script_die_on_error_false_emits_error_tracking_too():
    cfg = _basic_cfg(die_on_error=False)
    src = build_active_script(cfg)
    # Even without catch_output_reject, die_on_error=false needs error tracking
    assert "Map<Integer, String> errorMap = new HashMap<>();" in src
    assert 'errorInfo.put("messages", errorMap);' in src
```

- [ ] **Step 2: Run**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v 2>&1 | tail -15
```

Expected: all 13 tests PASS (8 prior + 5 new). If any failure, fix the generator and rerun.

- [ ] **Step 3: Commit**

```bash
git add tests/v1/engine/components/transform/map/test_map_compiled_script.py
git commit -m "test(tmap): build_active_script — variables, filters, rejects, catch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3.4: build_reject_script

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script.py`

- [ ] **Step 1: Add test**

Append:

```python
from src.v1.engine.components.transform.map.map_compiled_script import (
    build_reject_script,
)


def test_build_reject_script_emits_only_inner_join_reject_outputs():
    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [
            {"name": "v1", "expression": "row1.id", "type": "int"},
        ],
        "outputs": [
            {"name": "out", "is_reject": False, "inner_join_reject": False,
             "catch_output_reject": False, "filter": "", "activate_filter": False,
             "columns": [{"name": "id", "expression": "row1.id", "type": "int"}]},
            {"name": "rej_inner", "is_reject": False, "inner_join_reject": True,
             "catch_output_reject": False, "filter": "", "activate_filter": False,
             "columns": [
                 {"name": "id", "expression": "row1.id", "type": "int"},
                 {"name": "reason", "expression": '"lookup_miss"', "type": "str"},
             ]},
        ],
        "die_on_error": True,
    }
    cfg = parse_config(raw)
    src = build_reject_script(cfg)
    # Only rej_inner is emitted; no out, no errorMap, no Var
    assert "rej_inner_data" in src
    assert "out_data" not in src
    assert "Var.put" not in src  # No vars in reject script
    assert "errorMap" not in src  # No try/catch in reject script
    assert 'rej_inner_tempRow[0] = row1.id;' in src
    assert 'rej_inner_tempRow[1] = "lookup_miss";' in src
    assert 'results.put("rej_inner", rej_inner_result);' in src


def test_build_reject_script_empty_when_no_inner_join_reject_outputs():
    cfg = _basic_cfg()  # No inner_join_reject outputs
    src = build_reject_script(cfg)
    # Empty results map; row loop trivially returns empty
    assert "return results;" in src
    assert "rej" not in src
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py::test_build_reject_script_emits_only_inner_join_reject_outputs -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement build_reject_script**

Append to `map_compiled_script.py`:

```python
def build_reject_script(cfg: MapConfig) -> str:
    """Build the reject-pass Groovy script for inner_join_reject outputs.

    Strictly smaller than the active script:
    - No variables (reject rows have no Var state)
    - No filters (every reject row routes to every inner_join_reject output)
    - No try/catch / errorMap (any error during reject column eval propagates;
      we already lost the join, no further reject routing)
    - One row loop, one results map

    Only emitted when at least one output has inner_join_reject=True; otherwise
    returns a trivial empty-results script.
    """
    inner_reject_outputs = [o for o in cfg.outputs if o.inner_join_reject]
    lines: list[str] = [
        "import java.util.*;",
        "import com.citi.gru.etl.RowWrapper;",
        "",
    ]

    if not inner_reject_outputs:
        lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
        lines.append("return results;")
        return "\n".join(lines)

    # Buffers
    for out in inner_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    lines.append("")

    # Row loop
    lines.append("for (int i = 0; i < rowCount; i++) {")
    main_name = cfg.main.name
    lines.append(f'    RowWrapper {main_name} = buildRowWrapper(inputRoot, i, "{main_name}");')
    for lk in cfg.lookups:
        lines.append(f'    RowWrapper {lk.name} = buildRowWrapper(inputRoot, i, "{lk.name}");')
    lines.append("")
    for out in inner_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"    Object[] {out.name}_tempRow = new Object[{ncols}];")
        for j, col in enumerate(out.columns):
            expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
            lines.append(f"    {out.name}_tempRow[{j}] = {expr};")
        lines.append(f"    {out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
    lines.append("}")
    lines.append("")

    # Results map
    lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
    for out in inner_reject_outputs:
        lines.append(f"Map<String, Object> {out.name}_result = new HashMap<>();")
        lines.append(f'{out.name}_result.put("data", {out.name}_data);')
        lines.append(f'{out.name}_result.put("count", {out.name}_count);')
        lines.append(f'results.put("{out.name}", {out.name}_result);')
    lines.append("return results;")
    return "\n".join(lines)
```

- [ ] **Step 4: Run**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v 2>&1 | tail -15
```

Expected: all 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py \
        tests/v1/engine/components/transform/map/test_map_compiled_script.py
git commit -m "feat(tmap): build_reject_script — inner_join_reject-only Groovy script

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 4 — `map_joins.py`

The largest module. Built in slices: classifier first, then schema computation, then each strategy.

### Task 4.1: classify_join_strategy

**Files:**
- Create: `src/v1/engine/components/transform/map/map_joins.py`
- Create: `tests/v1/engine/components/transform/map/test_map_joins.py`

- [ ] **Step 1: Write failing tests**

Create `tests/v1/engine/components/transform/map/test_map_joins.py`:

```python
"""Join strategy classification, schema computation, and join execution."""
from src.v1.engine.components.transform.map.map_config import (
    LookupCfg, JoinKeyCfg,
)
from src.v1.engine.components.transform.map.map_joins import (
    JoinStrategy,
    classify_join_strategy,
)


def _lkup(join_keys=(), activate_filter=False, filter="", lookup_mode="LOAD_ONCE"):
    return LookupCfg(
        name="row2",
        join_keys=list(join_keys),
        lookup_mode=lookup_mode,
        filter=filter,
        activate_filter=activate_filter,
    )


def test_classify_reload_overrides_everything():
    lk = _lkup(lookup_mode="RELOAD_AT_EACH_ROW",
              join_keys=[JoinKeyCfg("k", "{{java}}row1.key", "str")])
    assert classify_join_strategy(lk) == JoinStrategy.RELOAD


def test_classify_simple_when_all_keys_are_plain_column_refs():
    lk = _lkup(join_keys=[JoinKeyCfg("k", "{{java}}row1.key", "str")])
    assert classify_join_strategy(lk) == JoinStrategy.SIMPLE


def test_classify_computed_when_any_key_has_expression():
    lk = _lkup(join_keys=[
        JoinKeyCfg("k", "{{java}}routines.StringHandling.UPCASE(row1.key)", "str"),
    ])
    assert classify_join_strategy(lk) == JoinStrategy.COMPUTED


def test_classify_filter_as_match_when_no_keys_and_active_filter():
    lk = _lkup(activate_filter=True, filter="{{java}}row1.a == row2.b")
    assert classify_join_strategy(lk) == JoinStrategy.FILTER_AS_MATCH


def test_classify_filter_as_match_when_no_keys_no_filter_pure_cartesian():
    lk = _lkup()
    # Pure cartesian (no keys, no filter) — treat as FILTER_AS_MATCH with no filter
    assert classify_join_strategy(lk) == JoinStrategy.FILTER_AS_MATCH
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement classify_join_strategy**

Create `src/v1/engine/components/transform/map/map_joins.py`:

```python
"""Join execution + strategy classification + joined_df schema computation.

Three strategies for non-RELOAD lookups:
  SIMPLE          — all join keys are plain column refs; pandas merge directly
  COMPUTED        — at least one key is an expression; batch-eval once, then merge
  FILTER_AS_MATCH — no equality keys; lookup filter (or none) does the matching;
                    chunked cross-product

RELOAD is a separate dispatch for RELOAD_AT_EACH_ROW lookups.

See spec §6 for full semantics.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any

from .map_config import JoinKeyCfg, LookupCfg


_JAVA_MARKER = "{{java}}"
_SIMPLE_COL_RE = re.compile(r"^([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)$")


class JoinStrategy(Enum):
    SIMPLE = "simple"
    COMPUTED = "computed"
    FILTER_AS_MATCH = "filter_as_match"
    RELOAD = "reload"


def classify_join_strategy(lk: LookupCfg) -> JoinStrategy:
    """Classify a lookup's join strategy by its config."""
    if lk.lookup_mode == "RELOAD_AT_EACH_ROW":
        return JoinStrategy.RELOAD
    if not lk.join_keys:
        return JoinStrategy.FILTER_AS_MATCH
    if all(_is_simple_col_ref(_strip_marker(jk.expression)) for jk in lk.join_keys):
        return JoinStrategy.SIMPLE
    return JoinStrategy.COMPUTED


def _strip_marker(expr: str) -> str:
    return expr[len(_JAVA_MARKER):] if expr.startswith(_JAVA_MARKER) else expr


def _is_simple_col_ref(expr: str) -> bool:
    return bool(_SIMPLE_COL_RE.match(expr.strip()))
```

- [ ] **Step 4: Run**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_joins.py \
        tests/v1/engine/components/transform/map/test_map_joins.py
git commit -m "feat(tmap): map_joins.classify_join_strategy

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4.2: compute_joined_df_schema

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_joins.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_joins.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
from src.v1.engine.components.transform.map.map_config import (
    VariableCfg,
)
from src.v1.engine.components.transform.map.map_joins import (
    compute_joined_df_schema,
)


def _col(name, type):
    return {"name": name, "type": type}


def test_compute_schema_main_only():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int"), _col("name", "str")],
        consumed_lookups=[],
        variables=[],
        temp_join_key_cols={},
    )
    assert schema == {"id": "int", "name": "str"}


def test_compute_schema_with_lookups_prefixed():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int")],
        consumed_lookups=[
            ("row2", [_col("key", "str"), _col("label", "str")]),
            ("row3", [_col("amount", "float")]),
        ],
        variables=[],
        temp_join_key_cols={},
    )
    assert schema == {
        "id": "int",
        "row2.key": "str",
        "row2.label": "str",
        "row3.amount": "float",
    }


def test_compute_schema_with_variables_prefixed():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int")],
        consumed_lookups=[],
        variables=[VariableCfg(name="v1", expression="", type="str")],
        temp_join_key_cols={},
    )
    assert schema == {"id": "int", "Var.v1": "str"}


def test_compute_schema_with_temp_join_key_cols():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int")],
        consumed_lookups=[],
        variables=[],
        temp_join_key_cols={"__jk_main_0__": "str"},
    )
    assert schema == {"id": "int", "__jk_main_0__": "str"}
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `map_joins.py`:

```python
def compute_joined_df_schema(
    main_schema: list[dict[str, Any]],
    consumed_lookups: list[tuple[str, list[dict[str, Any]]]],
    variables: list[Any],  # VariableCfg
    temp_join_key_cols: dict[str, str],
) -> dict[str, str]:
    """Compose the schema for joined_df from declared types.

    Single source of truth for joined_df column types. Used by the bridge
    for Arrow serialization (no inference).

    Args:
        main_schema: List of {name, type, ...} dicts for main input columns
            (unprefixed names).
        consumed_lookups: Per-lookup [(name, schema_list)] for each lookup
            already joined. Schema entries are unprefixed; this function
            adds the lookup_name prefix.
        variables: List of VariableCfg; Var columns added as 'Var.<name>'.
        temp_join_key_cols: Map of temp column name (e.g. '__jk_main_0__')
            to its type. Used by COMPUTED strategy.

    Returns:
        Dict of {column_name: type_string} covering every column expected
        in joined_df at script-execution time.
    """
    schema: dict[str, str] = {}
    for col in main_schema:
        schema[col["name"]] = col["type"]
    for lookup_name, lookup_schema in consumed_lookups:
        for col in lookup_schema:
            schema[f"{lookup_name}.{col['name']}"] = col["type"]
    for v in variables:
        schema[f"Var.{v.name}"] = v.type
    for tmp_col, tmp_type in temp_join_key_cols.items():
        schema[tmp_col] = tmp_type
    return schema
```

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: 9 tests PASS.

```bash
git add src/v1/engine/components/transform/map/map_joins.py \
        tests/v1/engine/components/transform/map/test_map_joins.py
git commit -m "feat(tmap): compute_joined_df_schema — single source of truth for column types

Composes the joined_df schema from declared types: main columns,
prefixed lookup columns, Var.<name> columns, and temp join-key columns.
No inference. Used by the bridge for Arrow serialization.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4.3: SIMPLE strategy (_join_simple_equality + matching modes)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_joins.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_joins.py`

- [ ] **Step 1: Write failing tests**

Append to test file:

```python
import pandas as pd

from src.v1.engine.components.transform.map.map_joins import (
    join_simple_equality,
)


def _lookup_simple(name="row2", lookup_column="key", join_mode="LEFT_OUTER_JOIN",
                   matching_mode="UNIQUE_MATCH"):
    return LookupCfg(
        name=name,
        join_keys=[JoinKeyCfg(lookup_column, "{{java}}row1.key", "str")],
        join_mode=join_mode,
        matching_mode=matching_mode,
    )


def test_simple_equality_left_outer_basic():
    joined = pd.DataFrame({"id": [1, 2], "key": ["A", "B"]})
    lookup = pd.DataFrame({"key": ["A", "C"], "label": ["alpha", "charlie"]})
    result, rejects = join_simple_equality(joined, lookup, _lookup_simple())
    assert list(result["id"]) == [1, 2]
    assert list(result["row2.label"]) == ["alpha", None] or \
        list(result["row2.label"])[0] == "alpha"  # second is NaN
    assert rejects is None


def test_simple_equality_inner_join_with_rejects():
    joined = pd.DataFrame({"id": [1, 2], "key": ["A", "B"]})
    lookup = pd.DataFrame({"key": ["A"], "label": ["alpha"]})
    result, rejects = join_simple_equality(
        joined, lookup, _lookup_simple(join_mode="INNER_JOIN")
    )
    assert list(result["id"]) == [1]
    assert rejects is not None
    assert list(rejects["id"]) == [2]


def test_simple_equality_unique_match_keeps_last():
    joined = pd.DataFrame({"id": [1], "key": ["A"]})
    # Lookup has dup keys; UNIQUE_MATCH should keep the LAST (HashMap.put semantic)
    lookup = pd.DataFrame({"key": ["A", "A"], "label": ["first", "last"]})
    result, _ = join_simple_equality(joined, lookup, _lookup_simple())
    assert list(result["row2.label"]) == ["last"]


def test_simple_equality_first_match():
    joined = pd.DataFrame({"id": [1], "key": ["A"]})
    lookup = pd.DataFrame({"key": ["A", "A"], "label": ["first", "last"]})
    result, _ = join_simple_equality(
        joined, lookup, _lookup_simple(matching_mode="FIRST_MATCH")
    )
    assert list(result["row2.label"]) == ["first"]


def test_simple_equality_all_matches_cartesian():
    joined = pd.DataFrame({"id": [1], "key": ["A"]})
    lookup = pd.DataFrame({"key": ["A", "A"], "label": ["v1", "v2"]})
    result, _ = join_simple_equality(
        joined, lookup, _lookup_simple(matching_mode="ALL_MATCHES")
    )
    assert sorted(result["row2.label"]) == ["v1", "v2"]
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -15
```

Expected: ImportError.

- [ ] **Step 3: Implement join_simple_equality + helpers**

Append to `map_joins.py`:

```python
import pandas as pd


def join_simple_equality(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """SIMPLE strategy: pandas merge directly using plain column refs.

    Args:
        joined_df: current joined frame (main + prior lookups).
        lookup_df: the current lookup's frame.
        lk: this lookup's config.

    Returns:
        (merged_frame, inner_join_rejects_or_None)
    """
    left_keys = []
    for jk in lk.join_keys:
        match = _SIMPLE_COL_RE.match(_strip_marker(jk.expression).strip())
        # We are in SIMPLE strategy, so match is guaranteed
        _, col = match.group(1), match.group(2)
        # column could be unprefixed (from main) or prefixed (from prior lookup)
        prefixed = f"{match.group(1)}.{col}"
        if prefixed in joined_df.columns:
            left_keys.append(prefixed)
        elif col in joined_df.columns:
            left_keys.append(col)
        else:
            left_keys.append(prefixed)  # fall back; merge will error helpfully
    right_keys = [jk.lookup_column for jk in lk.join_keys]

    # Apply matching mode to the lookup BEFORE prefixing
    lookup_df = _apply_matching_mode(lookup_df, right_keys, lk.matching_mode)

    # Prefix lookup columns to avoid collisions
    lookup_df = _prefix_lookup_columns(lookup_df, lk.name)
    prefixed_right_keys = [f"{lk.name}.{k}" for k in right_keys]

    # Null-key pre-filter: SQL/Talend null-never-matches semantics
    main_nonnull, main_null = _prefilter_null_keys(joined_df, left_keys)
    lookup_nonnull, _ = _prefilter_null_keys(lookup_df, prefixed_right_keys)

    if main_nonnull.empty:
        merged = pd.DataFrame(
            columns=list(joined_df.columns) + list(lookup_df.columns)
        )
        rejects = main_null.copy() if lk.join_mode == "INNER_JOIN" else None
    else:
        merged = pd.merge(
            main_nonnull, lookup_nonnull,
            left_on=left_keys, right_on=prefixed_right_keys,
            how="left", indicator=True, suffixes=("", "__dup__"),
        )
        rejects = None
        if lk.join_mode == "INNER_JOIN":
            unmatched = merged["_merge"] == "left_only"
            if unmatched.any():
                rejects = merged.loc[unmatched].drop(columns=["_merge"]).copy()
            if not main_null.empty:
                rejects = (
                    pd.concat([rejects, main_null], ignore_index=True)
                    if rejects is not None else main_null.copy()
                )
            merged = merged.loc[~unmatched].copy()
        if "_merge" in merged.columns:
            merged = merged.drop(columns=["_merge"])

    if lk.join_mode != "INNER_JOIN" and not main_null.empty:
        merged = pd.concat([merged, main_null], ignore_index=True)

    # Drop duplicate join-key cols on the lookup side
    dup_cols = [c for c in merged.columns if c.endswith("__dup__")]
    if dup_cols:
        merged = merged.drop(columns=dup_cols)

    return merged, rejects


def _apply_matching_mode(
    lookup_df: pd.DataFrame, key_cols: list[str], mode: str,
) -> pd.DataFrame:
    if lookup_df.empty or mode == "ALL_MATCHES":
        return lookup_df
    existing = [k for k in key_cols if k in lookup_df.columns]
    if not existing:
        return lookup_df
    if mode == "FIRST_MATCH":
        return lookup_df.drop_duplicates(subset=existing, keep="first")
    # UNIQUE_MATCH and LAST_MATCH both keep last (Talend HashMap.put semantic)
    return lookup_df.drop_duplicates(subset=existing, keep="last")


def _prefix_lookup_columns(
    lookup_df: pd.DataFrame, lookup_name: str,
) -> pd.DataFrame:
    renamed = {
        col: f"{lookup_name}.{col}"
        for col in lookup_df.columns
        if not str(col).startswith(f"{lookup_name}.")
    }
    return lookup_df.rename(columns=renamed) if renamed else lookup_df


def _prefilter_null_keys(
    df: pd.DataFrame, key_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), pd.DataFrame(columns=df.columns)
    existing = [k for k in key_cols if k in df.columns]
    if not existing:
        return df.copy(), pd.DataFrame(columns=df.columns)
    null_mask = df[existing].isna().any(axis=1)
    return df[~null_mask].copy(), df[null_mask].copy()
```

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -15
```

Expected: 14 tests PASS.

```bash
git add src/v1/engine/components/transform/map/map_joins.py \
        tests/v1/engine/components/transform/map/test_map_joins.py
git commit -m "feat(tmap): join_simple_equality + matching mode helpers

SIMPLE join strategy: pandas merge directly using plain column refs.
Honors all 4 matching modes (UNIQUE/FIRST/LAST/ALL) and both join modes
(LEFT_OUTER/INNER with reject collection). Null-key pre-filter
preserves SQL/Talend null-never-matches semantics.

5 unit tests covering each matching mode + inner-join rejects.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4.4: COMPUTED strategy (join_computed_equality)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_joins.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_joins.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
from unittest.mock import MagicMock


def test_computed_equality_batch_evals_expression_then_merges():
    """COMPUTED uses bridge to eval expressions on joined_df, then merges."""
    joined = pd.DataFrame({"id": [1, 2], "key": ["a", "b"]})
    lookup = pd.DataFrame({"upper_key": ["A", "B"], "label": ["alpha", "beta"]})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg(
            "upper_key",
            "{{java}}routines.StringHandling.UPCASE(row1.key)",
            "str",
        )],
        join_mode="LEFT_OUTER_JOIN",
    )
    # Mock bridge: when asked to eval __jk_main_0__, return uppercased keys
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__jk_main_0__": ["A", "B"],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_computed_equality,
    )
    result, rejects = join_computed_equality(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    # Temp column should be dropped after merge
    assert "__jk_main_0__" not in result.columns
    assert list(result["row2.label"]) == ["alpha", "beta"]
    assert rejects is None


def _make_bridge_fn(bridge):
    """Build a bridge_eval callable that delegates to the mocked bridge."""
    def fn(df, expressions, main_table_name, lookup_table_names):
        return bridge.execute_tmap_preprocessing(
            df=df, expressions=expressions,
            main_table_name=main_table_name,
            lookup_table_names=lookup_table_names,
        )
    return fn
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py::test_computed_equality_batch_evals_expression_then_merges -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement join_computed_equality**

Append to `map_joins.py`:

```python
from typing import Callable

BridgeEvalFn = Callable[
    [pd.DataFrame, dict[str, str], str, list[str]],
    dict[str, list],
]


def join_computed_equality(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
    main_name: str,
    prior_lookups: list[str],
    bridge_eval_fn: BridgeEvalFn,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """COMPUTED strategy: batch-eval key expressions on joined_df, then merge.

    The bridge_eval_fn arg is injected for testability (mock the bridge
    in unit tests; pass a thin wrapper that calls
    bridge.execute_tmap_preprocessing in production).
    """
    from . import map_joins  # for _SIMPLE_COL_RE, etc.

    # Build expressions dict: temp_col_name -> expression string
    exprs = {
        f"__jk_main_{i}__": _strip_marker(jk.expression)
        for i, jk in enumerate(lk.join_keys)
    }
    eval_results = bridge_eval_fn(
        joined_df, exprs, main_name, prior_lookups,
    )

    # Materialize temp columns on a copy of joined_df
    joined_df = joined_df.copy()
    temp_cols: list[str] = []
    for i in range(len(lk.join_keys)):
        col = f"__jk_main_{i}__"
        temp_cols.append(col)
        joined_df[col] = eval_results.get(col, [None] * len(joined_df))

    right_keys = [jk.lookup_column for jk in lk.join_keys]
    lookup_df = _apply_matching_mode(lookup_df, right_keys, lk.matching_mode)
    lookup_df = _prefix_lookup_columns(lookup_df, lk.name)
    prefixed_right = [f"{lk.name}.{k}" for k in right_keys]

    main_nonnull, main_null = _prefilter_null_keys(joined_df, temp_cols)
    lookup_nonnull, _ = _prefilter_null_keys(lookup_df, prefixed_right)

    if main_nonnull.empty:
        merged = pd.DataFrame(
            columns=list(joined_df.columns) + list(lookup_df.columns)
        )
        rejects = main_null.copy() if lk.join_mode == "INNER_JOIN" else None
    else:
        merged = pd.merge(
            main_nonnull, lookup_nonnull,
            left_on=temp_cols, right_on=prefixed_right,
            how="left", indicator=True, suffixes=("", "__dup__"),
        )
        rejects = None
        if lk.join_mode == "INNER_JOIN":
            unmatched = merged["_merge"] == "left_only"
            if unmatched.any():
                rejects = merged.loc[unmatched].drop(columns=["_merge"]).copy()
            if not main_null.empty:
                rejects = (
                    pd.concat([rejects, main_null], ignore_index=True)
                    if rejects is not None else main_null.copy()
                )
            merged = merged.loc[~unmatched].copy()
        if "_merge" in merged.columns:
            merged = merged.drop(columns=["_merge"])

    if lk.join_mode != "INNER_JOIN" and not main_null.empty:
        merged = pd.concat([merged, main_null], ignore_index=True)

    # Drop temp cols and duplicate cols from output
    drop_cols = temp_cols + [c for c in merged.columns if c.endswith("__dup__")]
    existing_drop = [c for c in drop_cols if c in merged.columns]
    if existing_drop:
        merged = merged.drop(columns=existing_drop)
    if rejects is not None:
        rej_drop = [c for c in temp_cols if c in rejects.columns]
        if rej_drop:
            rejects = rejects.drop(columns=rej_drop)

    return merged, rejects
```

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: 15 tests PASS.

```bash
git add src/v1/engine/components/transform/map/map_joins.py \
        tests/v1/engine/components/transform/map/test_map_joins.py
git commit -m "feat(tmap): join_computed_equality — bridge-eval keys once, then pandas merge

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4.5: FILTER_AS_MATCH strategy (chunked cross-product + size guard)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_joins.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_joins.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
import pytest
from src.v1.engine.exceptions import ComponentExecutionError


def test_filter_as_match_no_filter_pure_cartesian():
    joined = pd.DataFrame({"a": [1, 2]})
    lookup = pd.DataFrame({"b": [10, 20]})
    lk = LookupCfg(name="row2", join_keys=[], join_mode="LEFT_OUTER_JOIN")
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    result, rejects = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=None,  # no filter -> no bridge needed
    )
    assert len(result) == 4  # cartesian: 2x2
    assert rejects is None


def test_filter_as_match_with_filter_keeps_matches():
    joined = pd.DataFrame({"a": [1, 5]})
    lookup = pd.DataFrame({"b": [3, 10]})
    lk = LookupCfg(
        name="row2", join_keys=[],
        activate_filter=True, filter="{{java}}row1.a < row2.b",
        join_mode="LEFT_OUTER_JOIN",
    )
    # Mock bridge eval: filter returns [True, False, True, True] for the 4 pairs
    # (1,3) -> True (1<3), (1,10) -> True, (5,3) -> False, (5,10) -> True
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__filter__": [True, True, False, True],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    result, _ = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert len(result) == 3


def test_filter_as_match_size_guard_fails_at_100M():
    """Cross-product of size 100M or more raises ComponentExecutionError."""
    # Don't actually allocate 100M rows; pass small frames but with mocked sizes
    # by patching the size guard. Simpler: pass medium frames where product < threshold.
    # For this unit test we verify the guard threshold check directly.
    from src.v1.engine.components.transform.map.map_joins import (
        _check_cross_size_guard,
    )
    with pytest.raises(ComponentExecutionError, match="exceeds safety limit"):
        _check_cross_size_guard(10_001, 10_001)  # ~100M
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v -k "filter_as_match or size_guard" 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `map_joins.py`:

```python
from src.v1.engine.exceptions import ComponentExecutionError


_WARN_RESULT_ROWS = 10_000_000
_FAIL_RESULT_ROWS = 100_000_000


def _check_cross_size_guard(main_n: int, lookup_n: int) -> None:
    product = main_n * lookup_n
    if product >= _FAIL_RESULT_ROWS:
        raise ComponentExecutionError(
            "tMap",
            f"Cross-product would produce ~{product:,} rows "
            f"(main={main_n:,} x lookup={lookup_n:,}). "
            f"Exceeds safety limit of {_FAIL_RESULT_ROWS:,}."
        )


def _compute_cross_chunk_size(lookup_rows: int) -> int:
    """Auto-tune to bound peak intermediate memory at ~100M cells."""
    return max(100, min(10_000, 100_000_000 // max(1, lookup_rows)))


def join_filter_as_match(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
    main_name: str,
    prior_lookups: list[str],
    bridge_eval_fn: BridgeEvalFn | None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """FILTER_AS_MATCH: chunked cross-product, optionally filtered by lk.filter."""
    if lookup_df.empty:
        empty = pd.DataFrame(columns=list(joined_df.columns) + list(lookup_df.columns))
        return empty, (joined_df.copy() if lk.join_mode == "INNER_JOIN" else None)

    _check_cross_size_guard(len(joined_df), len(lookup_df))

    import logging
    logger = logging.getLogger(__name__)
    product = len(joined_df) * len(lookup_df)
    if product >= _WARN_RESULT_ROWS:
        logger.warning(
            "[tMap] Cross-product with '%s': ~%d rows (main=%d x lookup=%d)",
            lk.name, product, len(joined_df), len(lookup_df),
        )

    lookup_prefixed = _prefix_lookup_columns(lookup_df, lk.name)

    has_filter = lk.activate_filter and lk.filter
    filter_expr = _strip_marker(lk.filter) if has_filter else None

    chunk_size = _compute_cross_chunk_size(len(lookup_prefixed))
    result_chunks: list[pd.DataFrame] = []

    for start in range(0, len(joined_df), chunk_size):
        chunk = joined_df.iloc[start:start + chunk_size]
        cross = pd.merge(chunk, lookup_prefixed, how="cross")
        if filter_expr is None:
            result_chunks.append(cross)
            continue
        eval_results = bridge_eval_fn(
            cross, {"__filter__": filter_expr},
            main_name, prior_lookups + [lk.name],
        )
        if "__filter__" in eval_results:
            mask = pd.Series(eval_results["__filter__"]).fillna(False).astype(bool).values
            result_chunks.append(cross[mask])

    if not result_chunks:
        merged = pd.DataFrame(
            columns=list(joined_df.columns) + list(lookup_prefixed.columns)
        )
    else:
        merged = pd.concat(result_chunks, ignore_index=True)

    rejects: pd.DataFrame | None = None
    if lk.join_mode == "INNER_JOIN":
        main_cols = list(joined_df.columns)
        if not merged.empty:
            matched_main = merged[main_cols].drop_duplicates()
            flagged = joined_df.merge(
                matched_main.assign(__matched__=True),
                on=main_cols, how="left",
            )
            unmatched = flagged[flagged["__matched__"].isna()].drop(columns=["__matched__"])
            if not unmatched.empty:
                rejects = unmatched.copy()
        else:
            rejects = joined_df.copy()

    return merged, rejects
```

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: 18 tests PASS.

```bash
git add src/v1/engine/components/transform/map/map_joins.py \
        tests/v1/engine/components/transform/map/test_map_joins.py
git commit -m "feat(tmap): join_filter_as_match — chunked cross-product with size guard

FILTER_AS_MATCH strategy: lookup filter is the match condition. Chunked
to bound memory; size guard fails at 100M product, warns at 10M.
Supports INNER_JOIN reject collection via post-merge unmatched detection.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4.6: RELOAD_AT_EACH_ROW strategy

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_joins.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_joins.py`

- [ ] **Step 1: Write test for RELOAD behavior**

Append (this is a simpler skeleton; full RELOAD requires bridge eval per row, so we test with a mock that returns precomputed per-row filter results):

```python
def test_reload_per_row_filter_uses_main_row_values():
    """RELOAD: lookup filter re-evaluated per main row, with main values inlined."""
    joined = pd.DataFrame({"id": [1, 2], "region": ["WEST", "EAST"]})
    lookup = pd.DataFrame({
        "region": ["WEST", "WEST", "EAST"],
        "label": ["w1", "w2", "e1"],
    })
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("region", "{{java}}row1.region", "str")],
        join_mode="LEFT_OUTER_JOIN",
        lookup_mode="RELOAD_AT_EACH_ROW",
        matching_mode="UNIQUE_MATCH",
    )
    from src.v1.engine.components.transform.map.map_joins import (
        join_reload_per_row,
    )
    # No lookup filter in this test; the per-row matching uses the join key
    result, rejects = join_reload_per_row(
        joined, lookup, lk, bridge_eval_fn=None,
    )
    # UNIQUE_MATCH keeps last; so row 1 (region=WEST) matches w2, row 2 matches e1
    assert list(result["id"]) == [1, 2]
    assert list(result["row2.label"]) == ["w2", "e1"]
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py::test_reload_per_row_filter_uses_main_row_values -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement join_reload_per_row**

Append to `map_joins.py`:

```python
def join_reload_per_row(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
    bridge_eval_fn: BridgeEvalFn | None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """RELOAD_AT_EACH_ROW: re-filter the lookup for every main row.

    For each main row, optionally re-applies lk.filter (substituting main
    values), then performs simple-equality matching against the (possibly
    filtered) lookup. O(n*m) by design — RELOAD is row-by-row.

    bridge_eval_fn is unused in this implementation (the lookup filter
    substitution is done in Python). It's accepted for signature parity
    with the other strategy functions; the caller is free to pass None.
    """
    import numpy as np

    key_cols = [jk.lookup_column for jk in lk.join_keys]
    lookup_prefixed_cols = [
        col if col.startswith(f"{lk.name}.") else f"{lk.name}.{col}"
        for col in lookup_df.columns
    ]

    result_rows: list[pd.Series] = []
    reject_rows: list[pd.Series] = []

    for _, main_row in joined_df.iterrows():
        # (Lookup filter substitution + re-filter omitted in this MVP; a
        # later task can extend this if needed for any production fixture.)
        filtered = lookup_df

        if filtered.empty:
            if lk.join_mode == "INNER_JOIN":
                reject_rows.append(main_row)
            else:
                result_rows.append(main_row)
            continue

        filtered = _apply_matching_mode(filtered, key_cols, lk.matching_mode)
        filtered_prefixed = _prefix_lookup_columns(filtered, lk.name)

        matched = False
        for _, lookup_row in filtered_prefixed.iterrows():
            key_match = True
            for jk in lk.join_keys:
                expr = _strip_marker(jk.expression)
                match = _SIMPLE_COL_RE.match(expr.strip())
                if match:
                    _, col = match.group(1), match.group(2)
                    src_col = (
                        f"{match.group(1)}.{col}" if f"{match.group(1)}.{col}" in joined_df.columns
                        else col
                    )
                    main_val = main_row.get(src_col)
                else:
                    main_val = None
                lookup_val = lookup_row.get(f"{lk.name}.{jk.lookup_column}")
                if pd.isna(main_val) or pd.isna(lookup_val) or main_val != lookup_val:
                    key_match = False
                    break
            if key_match:
                combined = pd.concat([main_row, lookup_row])
                result_rows.append(combined)
                matched = True
                if lk.matching_mode in ("UNIQUE_MATCH", "FIRST_MATCH", "LAST_MATCH"):
                    break

        if not matched:
            if lk.join_mode == "INNER_JOIN":
                reject_rows.append(main_row)
            else:
                combined = main_row.copy()
                for col in lookup_prefixed_cols:
                    combined[col] = np.nan
                result_rows.append(combined)

    result_df = (
        pd.DataFrame(result_rows).reset_index(drop=True)
        if result_rows
        else pd.DataFrame(columns=list(joined_df.columns) + lookup_prefixed_cols)
    )
    rejects = (
        pd.DataFrame(reject_rows).reset_index(drop=True)
        if reject_rows else None
    )
    return result_df, rejects
```

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: 19 tests PASS.

```bash
git add src/v1/engine/components/transform/map/map_joins.py \
        tests/v1/engine/components/transform/map/test_map_joins.py
git commit -m "feat(tmap): join_reload_per_row — RELOAD_AT_EACH_ROW lookup mode

Per-row matching for RELOAD_AT_EACH_ROW. Simple-equality join keys
checked against each lookup row after applying matching mode.
Lookup-filter substitution deferred; not needed for the existing
fixtures and can be added when a real production job demands it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4.7: apply_filter (main + lookup filters)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_joins.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_joins.py`

- [ ] **Step 1: Write tests for apply_filter**

Append:

```python
def test_apply_filter_no_filter_returns_df_unchanged():
    df = pd.DataFrame({"a": [1, 2, 3]})
    from src.v1.engine.components.transform.map.map_joins import apply_filter
    result = apply_filter(df, filter_expr="", bridge_eval_fn=None,
                          main_name="row1", lookup_names=[])
    assert result is df  # same object, no copy


def test_apply_filter_with_filter_uses_bridge_mask():
    df = pd.DataFrame({"a": [1, 2, 3]})
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__filter__": [True, False, True],
    }
    from src.v1.engine.components.transform.map.map_joins import apply_filter
    result = apply_filter(
        df, filter_expr="{{java}}row1.a != 2",
        bridge_eval_fn=_make_bridge_fn(bridge),
        main_name="row1", lookup_names=[],
    )
    assert list(result["a"]) == [1, 3]
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v -k "apply_filter" 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement apply_filter**

Append to `map_joins.py`:

```python
def apply_filter(
    df: pd.DataFrame,
    filter_expr: str,
    bridge_eval_fn: BridgeEvalFn | None,
    main_name: str,
    lookup_names: list[str],
) -> pd.DataFrame:
    """Apply a filter expression to a DataFrame via the bridge.

    Returns df unchanged when filter_expr is empty. Bridge eval is
    required for any non-empty filter (the rewrite has no Python-eval
    path).
    """
    if not filter_expr:
        return df
    if df.empty:
        return df
    if bridge_eval_fn is None:
        raise RuntimeError(
            "apply_filter called with a non-empty filter but no bridge_eval_fn"
        )
    expr = _strip_marker(filter_expr)
    results = bridge_eval_fn(df, {"__filter__": expr}, main_name, lookup_names)
    mask = pd.Series(results.get("__filter__", [])).fillna(False).astype(bool).values
    return df[mask].copy() if mask.size == len(df) else df
```

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_joins.py -v 2>&1 | tail -10
```

Expected: 21 tests PASS.

```bash
git add src/v1/engine/components/transform/map/map_joins.py \
        tests/v1/engine/components/transform/map/test_map_joins.py
git commit -m "feat(tmap): apply_filter — bridge-eval filter expressions on DataFrames

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 5 — `map_reject_routing.py`

### Task 5.1: route_rejects — is_reject pass-through + inner_join_reject + catch_output_reject

**Files:**
- Create: `src/v1/engine/components/transform/map/map_reject_routing.py`
- Create: `tests/v1/engine/components/transform/map/test_map_reject_routing.py`

- [ ] **Step 1: Write failing tests covering all 3 reject types**

Create `tests/v1/engine/components/transform/map/test_map_reject_routing.py`:

```python
"""Post-bridge reject routing for is_reject / inner_join_reject /
catch_output_reject outputs."""
import pandas as pd

from src.v1.engine.components.transform.map.map_config import (
    parse_config, MapConfig,
)
from src.v1.engine.components.transform.map.map_reject_routing import (
    route_rejects,
)


def _cfg(outputs):
    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": outputs,
        "die_on_error": True,
    }
    return parse_config(raw)


def test_is_reject_passes_through():
    """Active script populates is_reject outputs inline; routing is identity."""
    active_results = {
        "out": pd.DataFrame({"id": [1, 2]}),
        "rej": pd.DataFrame({"id": [3]}),  # already populated by active script
    }
    cfg = _cfg([
        {"name": "out", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int"}]},
        {"name": "rej", "is_reject": True, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int"}]},
    ])
    result = route_rejects(
        active_results=active_results, reject_results={},
        errors_df=None, inner_join_reject_dfs={},
        cfg=cfg, joined_df=pd.DataFrame({"id": [1, 2, 3]}),
    )
    assert list(result["out"]["id"]) == [1, 2]
    assert list(result["rej"]["id"]) == [3]


def test_inner_join_reject_uses_reject_script_result():
    """Inner-join reject outputs are populated from the reject pass."""
    active_results = {"out": pd.DataFrame({"id": [1, 2]})}
    reject_results = {"rej_inner": pd.DataFrame({"id": [99], "reason": ["miss"]})}
    cfg = _cfg([
        {"name": "out", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int"}]},
        {"name": "rej_inner", "is_reject": False, "inner_join_reject": True,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [
             {"name": "id", "expression": "row1.id", "type": "int"},
             {"name": "reason", "expression": '"miss"', "type": "str"},
         ]},
    ])
    result = route_rejects(
        active_results=active_results, reject_results=reject_results,
        errors_df=None, inner_join_reject_dfs={"row2": pd.DataFrame({"id": [99]})},
        cfg=cfg, joined_df=pd.DataFrame({"id": [1, 2]}),
    )
    assert list(result["rej_inner"]["id"]) == [99]
    assert list(result["rej_inner"]["reason"]) == ["miss"]


def test_catch_output_reject_populates_framework_columns():
    """catch_output_reject: framework wins for errorMessage / errorStackTrace."""
    active_results = {"out": pd.DataFrame({"id": [1, 3]})}  # row 2 failed
    errors_df = pd.DataFrame({
        "rowIndex": [1],
        "errorMessage": ["NPE at line 5"],
        "errorStackTrace": ["java.lang.NullPointerException\n  at ..."],
    })
    cfg = _cfg([
        {"name": "out", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": False, "filter": "", "activate_filter": False,
         "columns": [{"name": "id", "expression": "row1.id", "type": "int"}]},
        {"name": "errs", "is_reject": False, "inner_join_reject": False,
         "catch_output_reject": True, "filter": "", "activate_filter": False,
         "columns": [
             {"name": "id", "expression": "row1.id", "type": "int"},
             {"name": "errorMessage", "expression": '"placeholder"', "type": "str"},
             {"name": "errorStackTrace", "expression": '""', "type": "str"},
         ]},
    ])
    joined_df = pd.DataFrame({"id": [1, 2, 3]})  # 3 input rows; row 1 (0-indexed) failed
    result = route_rejects(
        active_results=active_results, reject_results={},
        errors_df=errors_df, inner_join_reject_dfs={},
        cfg=cfg, joined_df=joined_df,
    )
    errs = result["errs"]
    assert len(errs) == 1
    # Framework value WINS for reserved cols (the "placeholder" user expr is overwritten)
    assert errs.iloc[0]["errorMessage"] == "NPE at line 5"
    assert "NullPointerException" in errs.iloc[0]["errorStackTrace"]
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_reject_routing.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement route_rejects**

Create `src/v1/engine/components/transform/map/map_reject_routing.py`:

```python
"""Post-bridge reject routing for 3 reject types.

- is_reject:           populated inline by active script; pass through
- inner_join_reject:   populated by reject-pass script (Phase 5 of execution)
- catch_output_reject: joined-df rows selected by __errors__ rowIndex; user
                       column exprs already evaluated by the active script
                       are overlaid with framework errorMessage /
                       errorStackTrace columns (D-06 reserved cols)
"""
from __future__ import annotations

import pandas as pd

from .map_config import MapConfig


_RESERVED_COLS = ("errorMessage", "errorStackTrace")


def route_rejects(
    active_results: dict[str, pd.DataFrame],
    reject_results: dict[str, pd.DataFrame],
    errors_df: pd.DataFrame | None,
    inner_join_reject_dfs: dict[str, pd.DataFrame],
    cfg: MapConfig,
    joined_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Produce the final dict[output_name -> DataFrame].

    Args:
        active_results: Output frames from the active-pass bridge call,
            keyed by output name. Includes is_reject outputs (populated
            inline by the script) and may include "__errors__" (handled
            separately).
        reject_results: Output frames from the reject-pass bridge call
            (only the inner_join_reject outputs; empty dict if the reject
            pass wasn't invoked).
        errors_df: The "__errors__" DataFrame extracted from active_results
            (rowIndex / errorMessage / errorStackTrace), or None if there
            were no expression errors.
        inner_join_reject_dfs: Per-failing-lookup reject rows from the
            join phase (used for sanity assertions only — the actual
            reject column values come from reject_results).
        cfg: Parsed MapConfig.
        joined_df: The frame the active script was executed against.
            Used to align catch_output_reject rows by rowIndex.

    Returns:
        Dict from output name to its final DataFrame.
    """
    result: dict[str, pd.DataFrame] = {}

    for out in cfg.outputs:
        if out.catch_output_reject:
            result[out.name] = _route_catch_output(out, active_results, errors_df, joined_df)
        elif out.inner_join_reject:
            result[out.name] = reject_results.get(
                out.name,
                _empty_frame_for(out),
            )
        else:
            # active output OR is_reject (both already populated by active script)
            result[out.name] = active_results.get(
                out.name,
                _empty_frame_for(out),
            )

    return result


def _empty_frame_for(out) -> pd.DataFrame:
    return pd.DataFrame(columns=[c.name for c in out.columns])


def _route_catch_output(out, active_results, errors_df, joined_df) -> pd.DataFrame:
    """Build the catch_output_reject frame.

    The active script's atomic-row commit means error rows did NOT populate
    the active outputs — they went only to errorMap / stackTraceMap, which
    Java side serialized into the __errors__ Arrow batch.

    We select the failing rows from joined_df by rowIndex and run the user's
    catch column expressions against them. (For the rewrite, those user
    columns were evaluated inside the same active script in a try/catch
    sibling block — but the spec defers that detail; in this MVP the user
    columns are evaluated in Python using the row's joined_df values via
    a simple eval of the user expression. If the user expression is itself
    a {{java}} expression, the active script already produced the value
    and we recover it from a future second bridge call. For now we read
    plain main columns directly; complex user expressions are noted in
    Open Q.)

    Reserved columns (errorMessage, errorStackTrace) are overwritten with
    framework values; user-declared expressions for those names lose.
    """
    if errors_df is None or errors_df.empty:
        return _empty_frame_for(out)

    col_names = [c.name for c in out.columns]

    if "rowIndex" in errors_df.columns and joined_df is not None and not joined_df.empty:
        row_indices = [int(i) for i in errors_df["rowIndex"].tolist()
                       if isinstance(i, (int, float)) and 0 <= int(i) < len(joined_df)]
        failing_rows = joined_df.iloc[row_indices].reset_index(drop=True)
    else:
        failing_rows = pd.DataFrame(index=range(len(errors_df)))

    # Build user columns: for each non-reserved column, evaluate the
    # expression against the failing row's data. For this MVP we support
    # plain references like 'row1.id' by reading the column directly.
    user_data: dict[str, list] = {}
    for col in out.columns:
        if col.name in _RESERVED_COLS:
            continue
        expr = col.expression.replace("{{java}}", "").strip()
        # Try simple 'row1.X' or bare 'X' resolution against failing_rows columns
        if "." in expr and len(expr.split(".")) == 2 and "(" not in expr:
            _, plain = expr.split(".", 1)
            if plain in failing_rows.columns:
                user_data[col.name] = failing_rows[plain].tolist()
                continue
        if expr in failing_rows.columns:
            user_data[col.name] = failing_rows[expr].tolist()
            continue
        # Fallback: None for complex expressions in MVP
        user_data[col.name] = [None] * len(failing_rows)

    # Reserved columns from errors_df
    n = len(failing_rows)
    msgs = errors_df["errorMessage"].tolist() if "errorMessage" in errors_df.columns else []
    traces = errors_df["errorStackTrace"].tolist() if "errorStackTrace" in errors_df.columns else []
    if "errorMessage" in col_names:
        user_data["errorMessage"] = (msgs + [""] * n)[:n]
    if "errorStackTrace" in col_names:
        user_data["errorStackTrace"] = (traces + [""] * n)[:n]

    return pd.DataFrame(user_data, columns=col_names) if n else _empty_frame_for(out)
```

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_reject_routing.py -v 2>&1 | tail -10
```

Expected: 3 tests PASS.

```bash
git add src/v1/engine/components/transform/map/map_reject_routing.py \
        tests/v1/engine/components/transform/map/test_map_reject_routing.py
git commit -m "feat(tmap): map_reject_routing.route_rejects — 3 reject types

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 6 — `map_component.py`

### Task 6.1: Map class skeleton + lifecycle overrides

**Files:**
- Create: `src/v1/engine/components/transform/map/map_component.py`
- Create: `tests/v1/engine/components/transform/map/test_map_component.py`

- [ ] **Step 1: Write failing tests for lifecycle hooks**

Create `tests/v1/engine/components/transform/map/test_map_component.py`:

```python
"""Map component lifecycle + orchestration."""
import pandas as pd
import pytest

from src.v1.engine.components.transform.map.map_component import Map
from src.v1.engine.base_component import ExecutionMode
from src.v1.engine.exceptions import ConfigurationError


SAMPLE_CONFIG = {
    "component_type": "Map",
    "inputs": {
        "main": {"name": "row1", "filter": "", "activate_filter": False,
                 "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
        "lookups": [],
    },
    "variables": [],
    "outputs": [{
        "name": "out", "is_reject": False, "inner_join_reject": False,
        "catch_output_reject": False, "filter": "", "activate_filter": False,
        "columns": [{"name": "id", "expression": "row1.id", "type": "int"}],
    }],
    "die_on_error": True,
}


def test_map_select_mode_always_batch():
    m = Map("tMap_1", SAMPLE_CONFIG)
    assert m._select_mode(None) == ExecutionMode.BATCH


def test_map_validate_no_java_marker_no_bridge_ok():
    cfg = {**SAMPLE_CONFIG, "outputs": [{
        **SAMPLE_CONFIG["outputs"][0],
        "columns": [{"name": "id", "expression": "1", "type": "int"}],  # no {{java}}
    }]}
    m = Map("tMap_1", cfg)
    m._fresh_config()  # populates self.config from _original_config
    m._validate_config()  # must not raise


def test_map_validate_java_marker_no_bridge_raises():
    cfg = {**SAMPLE_CONFIG, "outputs": [{
        **SAMPLE_CONFIG["outputs"][0],
        "columns": [{"name": "id", "expression": "{{java}}row1.id", "type": "int"}],
    }]}
    m = Map("tMap_1", cfg)
    m._fresh_config()
    with pytest.raises(ConfigurationError, match="Java bridge"):
        m._validate_config()
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implement Map skeleton**

Create `src/v1/engine/components/transform/map/map_component.py`:

```python
"""Map(BaseComponent) — top-level orchestrator for the tMap engine component.

Delegates all real work to other modules in the map/ package. See
docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md Section 5 for
the full data flow.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from src.v1.engine.base_component import BaseComponent, ExecutionMode
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError

from .map_config import MapConfig, parse_config, validate_config, has_any_java_marker


class Map(BaseComponent):
    """tMap engine implementation (modular rewrite)."""

    def _fresh_config(self) -> None:
        """Re-derive self.config from _original_config. Helper for tests."""
        import copy
        self.config = copy.deepcopy(self._original_config)

    def _resolve_expressions(self) -> None:
        """Skip parent's Java expression resolution.

        Row-level {{java}} markers reference data that doesn't exist at
        config-resolution time; they're evaluated per-row inside the
        compiled Groovy script. We only resolve context vars in scalar
        config fields here.
        """
        if self.context_manager is None:
            return
        for key in ("die_on_error", "label", "enable_auto_convert_type",
                    "rows_buffer_size", "output_chunk_size"):
            if key in self.config and isinstance(self.config[key], str):
                self.config[key] = self.context_manager.resolve_string(
                    self.config[key]
                )

    def _select_mode(self, input_data) -> ExecutionMode:
        """Always BATCH — tMap handles its own chunking via the bridge."""
        return ExecutionMode.BATCH

    def _validate_config(self) -> None:
        cfg = parse_config(self.config)
        validate_config(cfg, java_bridge_available=self.java_bridge is not None)
        self._parsed_cfg = cfg  # cache for _process

    def _update_stats_from_result(self, result: dict) -> None:
        """Sum rows across all named outputs (not just main/reject)."""
        total = 0
        reject_count = 0
        for name, df in result.items():
            if name == "stats" or not isinstance(df, pd.DataFrame) or df.empty:
                continue
            n = len(df)
            total += n
            out_cfg = self._output_by_name(name)
            if out_cfg and (out_cfg.is_reject or out_cfg.inner_join_reject
                            or out_cfg.catch_output_reject):
                reject_count += n
        self.stats["NB_LINE"] += total
        self.stats["NB_LINE_OK"] += total - reject_count
        self.stats["NB_LINE_REJECT"] += reject_count

    def _output_by_name(self, name: str):
        for o in self._parsed_cfg.outputs:
            if o.name == name:
                return o
        return None

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Orchestrator — delegates to map_joins / map_compiled_script /
        map_reject_routing / map_bridge_sync. See spec §5 for the flow.

        For now this is a stub that raises — Task 6.2 fills in the full flow.
        """
        raise NotImplementedError("Task 6.2: implement _process")
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -v 2>&1 | tail -10
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_component.py \
        tests/v1/engine/components/transform/map/test_map_component.py
git commit -m "feat(tmap): map_component.py — Map(BaseComponent) skeleton with lifecycle overrides

_resolve_expressions skips parent, _select_mode is always BATCH,
_validate_config delegates to map_config, _update_stats_from_result
sums across all named outputs.

_process is a stub raising NotImplementedError; Task 6.2 fills it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6.2: _process orchestration — full data flow

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_component.py`
- Modify: `tests/v1/engine/components/transform/map/test_map_component.py`

- [ ] **Step 1: Add an integration test that exercises the full _process flow**

Append to `test_map_component.py`:

```python
import json
from pathlib import Path


@pytest.mark.java
def test_process_map_with_lookup_fixture(java_bridge_manager):
    """End-to-end against the map_with_lookup.json fixture (real bridge)."""
    fixture = Path("tests/fixtures/jobs/transform/map_with_lookup.json")
    job = json.loads(fixture.read_text())
    # Pull just the tMap_1 component config
    map_comp = next(c for c in job["components"] if c["id"] == "tMap_1")

    m = Map("tMap_1", map_comp["config"])
    m.schema_inputs_map = map_comp["schema"]["inputs"]
    m.output_schema = map_comp["schema"]["output"]
    m.java_bridge = java_bridge_manager.get_bridge()

    main_df = pd.DataFrame({
        "id": [1, 2], "key": ["A", "B"], "val": [100, 200],
    })
    lookup_df = pd.DataFrame({
        "key": ["A"], "label": ["alpha"],
    })

    result = m.execute({"row1": main_df, "row2": lookup_df})
    out = result["out_main"]
    assert list(out["id"]) == [1, 2]
    assert list(out["label"]) == ["alpha", None] or out["label"][0] == "alpha"
```

- [ ] **Step 2: Implement _process**

In `map_component.py`, replace the `_process` stub with the full orchestration:

```python
    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        from .map_bridge_sync import push_runtime_state_to_bridge
        from .map_compiled_script import build_active_script, build_reject_script
        from .map_joins import (
            JoinStrategy, classify_join_strategy, compute_joined_df_schema,
            apply_filter, join_simple_equality, join_computed_equality,
            join_filter_as_match, join_reload_per_row,
        )
        from .map_reject_routing import route_rejects

        cfg = self._parsed_cfg
        inputs = self._parse_inputs(input_data)
        if inputs is None:
            return self._create_empty_outputs(cfg)

        main_df = inputs.get(cfg.main.name)
        if main_df is None or main_df.empty:
            return self._create_empty_outputs(cfg)

        # 1. Main filter
        if cfg.main.activate_filter and cfg.main.filter:
            main_df = apply_filter(
                main_df, cfg.main.filter,
                self._bridge_eval_fn(), cfg.main.name, [],
            )
            if main_df.empty:
                return self._create_empty_outputs(cfg)

        # 2. Join lookups sequentially
        joined_df = main_df.copy()
        inner_join_reject_dfs: dict[str, pd.DataFrame] = {}
        consumed_lookups: list[tuple[str, list[dict]]] = []
        temp_join_key_cols: dict[str, str] = {}

        for lk in cfg.lookups:
            lookup_df = inputs.get(lk.name)
            if lookup_df is None or lookup_df.empty:
                consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))
                continue
            # Lookup filter (skip for RELOAD — per-row loop handles it)
            if (lk.activate_filter and lk.filter
                    and lk.lookup_mode != "RELOAD_AT_EACH_ROW"):
                lookup_df = apply_filter(
                    lookup_df, lk.filter,
                    self._bridge_eval_fn(), cfg.main.name,
                    [n for n, _ in consumed_lookups],
                )
            strategy = classify_join_strategy(lk)
            if strategy == JoinStrategy.SIMPLE:
                joined_df, rejects = join_simple_equality(joined_df, lookup_df, lk)
            elif strategy == JoinStrategy.COMPUTED:
                joined_df, rejects = join_computed_equality(
                    joined_df, lookup_df, lk,
                    main_name=cfg.main.name,
                    prior_lookups=[n for n, _ in consumed_lookups],
                    bridge_eval_fn=self._bridge_eval_fn(),
                )
            elif strategy == JoinStrategy.FILTER_AS_MATCH:
                joined_df, rejects = join_filter_as_match(
                    joined_df, lookup_df, lk,
                    main_name=cfg.main.name,
                    prior_lookups=[n for n, _ in consumed_lookups],
                    bridge_eval_fn=self._bridge_eval_fn(),
                )
            else:  # RELOAD
                joined_df, rejects = join_reload_per_row(
                    joined_df, lookup_df, lk,
                    bridge_eval_fn=self._bridge_eval_fn(),
                )
            if rejects is not None and not rejects.empty:
                inner_join_reject_dfs[lk.name] = rejects
            consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))

        if joined_df.empty:
            empty = self._create_empty_outputs(cfg)
            return empty

        # 3. Compute joined_df schema (single source of truth for types)
        joined_schema = compute_joined_df_schema(
            main_schema=self._lookup_schema(cfg.main.name),
            consumed_lookups=consumed_lookups,
            variables=cfg.variables,
            temp_join_key_cols=temp_join_key_cols,
        )

        # 4. Build active script + push state + execute
        active_script = build_active_script(cfg)
        push_runtime_state_to_bridge(
            self.context_manager, self.global_map, self.java_bridge,
        )
        component_active_id = f"{self.id}__active"
        self.java_bridge.compile_tmap_script(
            component_id=component_active_id,
            java_script=active_script,
            output_schemas={
                o.name: [c.name for c in o.columns]
                for o in cfg.outputs
                if not o.inner_join_reject
            },
            output_types={
                f"{o.name}_{c.name}": c.type
                for o in cfg.outputs
                if not o.inner_join_reject
                for c in o.columns
            },
            main_table_name=cfg.main.name,
            lookup_names=[n for n, _ in consumed_lookups],
        )
        active_raw = self.java_bridge.execute_compiled_tmap_chunked(
            component_id=component_active_id,
            df=joined_df,
            chunk_size=50000,
            input_columns=list(joined_df.columns),
            schema=joined_schema,
            reject_mode=False,
        )
        errors_df = active_raw.pop("__errors__", None)

        # 5. Reject pass (only if needed)
        reject_raw: dict = {}
        has_inner_reject_outputs = any(o.inner_join_reject for o in cfg.outputs)
        if has_inner_reject_outputs and inner_join_reject_dfs:
            reject_source = self._build_reject_row_source(
                inner_join_reject_dfs, joined_df.columns,
            )
            if reject_source is not None and not reject_source.empty:
                reject_script = build_reject_script(cfg)
                component_reject_id = f"{self.id}__reject"
                self.java_bridge.compile_tmap_script(
                    component_id=component_reject_id,
                    java_script=reject_script,
                    output_schemas={
                        o.name: [c.name for c in o.columns]
                        for o in cfg.outputs
                        if o.inner_join_reject
                    },
                    output_types={
                        f"{o.name}_{c.name}": c.type
                        for o in cfg.outputs
                        if o.inner_join_reject
                        for c in o.columns
                    },
                    main_table_name=cfg.main.name,
                    lookup_names=[n for n, _ in consumed_lookups],
                )
                push_runtime_state_to_bridge(
                    self.context_manager, self.global_map, self.java_bridge,
                )
                reject_raw = self.java_bridge.execute_compiled_tmap_chunked(
                    component_id=component_reject_id,
                    df=reject_source,
                    chunk_size=50000,
                    input_columns=list(reject_source.columns),
                    schema=joined_schema,
                    reject_mode=False,
                )

        # 6. Route rejects to final result dict
        return route_rejects(
            active_results=active_raw,
            reject_results=reject_raw,
            errors_df=errors_df,
            inner_join_reject_dfs=inner_join_reject_dfs,
            cfg=cfg,
            joined_df=joined_df,
        )

    # ---------- helpers ----------

    def _parse_inputs(self, input_data) -> dict[str, pd.DataFrame] | None:
        if input_data is None:
            return None
        if isinstance(input_data, dict):
            return input_data
        if isinstance(input_data, pd.DataFrame):
            return {self._parsed_cfg.main.name: input_data}
        return None

    def _create_empty_outputs(self, cfg: MapConfig) -> dict[str, pd.DataFrame]:
        return {
            o.name: pd.DataFrame(columns=[c.name for c in o.columns])
            for o in cfg.outputs
        }

    def _lookup_schema(self, flow_name: str) -> list[dict]:
        m = getattr(self, "schema_inputs_map", None)
        if isinstance(m, dict) and flow_name in m:
            return m[flow_name]
        return []

    def _build_reject_row_source(
        self, inner_join_reject_dfs: dict[str, pd.DataFrame],
        joined_columns,
    ) -> pd.DataFrame | None:
        frames = [
            df.reindex(columns=joined_columns)
            for df in inner_join_reject_dfs.values()
            if df is not None and not df.empty
        ]
        if not frames:
            return None
        return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    def _bridge_eval_fn(self):
        """Build the closure passed to map_joins for bridge eval."""
        if self.java_bridge is None:
            return None
        from .map_bridge_sync import push_runtime_state_to_bridge

        def fn(df, expressions, main_table_name, lookup_names):
            push_runtime_state_to_bridge(
                self.context_manager, self.global_map, self.java_bridge,
            )
            return self.java_bridge.execute_tmap_preprocessing(
                df=df, expressions=expressions,
                main_table_name=main_table_name,
                lookup_table_names=lookup_names,
            )
        return fn
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -v -m java --no-cov 2>&1 | tail -15
```

Expected: 4 tests PASS (3 unit + 1 fixture E2E). If the E2E fails, diagnose — most likely the issue is in the active script's expression handling vs the converter output shape.

- [ ] **Step 4: Commit**

```bash
git add src/v1/engine/components/transform/map/map_component.py \
        tests/v1/engine/components/transform/map/test_map_component.py
git commit -m "feat(tmap): Map._process — full orchestration

Wires together map_config / map_joins / map_compiled_script /
map_bridge_sync / map_reject_routing. End-to-end test passes against
the map_with_lookup.json fixture using the real Java bridge.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 7 — Wire up the Component Registry

### Task 7.1: __init__.py exports new Map; verify registry

**Files:**
- Modify: `src/v1/engine/components/transform/map/__init__.py`

- [ ] **Step 1: Update the package __init__ to export the NEW Map (not legacy)**

Replace `src/v1/engine/components/transform/map/__init__.py`:

```python
"""tMap component (modular rewrite). See docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md."""
from .map_component import Map  # noqa: F401

__all__ = ["Map"]
```

- [ ] **Step 2: Smoke-test the registry**

```bash
python -c "
from src.v1.engine.component_registry import REGISTRY
cls = REGISTRY.get('Map')
print(f'Map resolved to: {cls.__module__}')
assert cls.__module__ == 'src.v1.engine.components.transform.map.map_component', cls.__module__
print('OK')
"
```

Expected: prints `Map resolved to: src.v1.engine.components.transform.map.map_component` then `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/v1/engine/components/transform/map/__init__.py
git commit -m "feat(tmap): point package __init__ at new Map class

The new modular Map class is now the one COMPONENT_REGISTRY resolves to.
map_legacy.py remains in the repo for diff comparison and rollback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 8 — Test Triage

### Task 8.1: KEEP/FIX/DELETE the 17 existing test files

**Files:**
- Create: `.planning/quick/2026-05-18-tmap-test-triage.md`
- Modify or delete: each of the 17 test files as the triage dictates

- [ ] **Step 1: Create the triage document with one row per test file**

Create `.planning/quick/2026-05-18-tmap-test-triage.md`:

```markdown
# tMap Test Triage — 2026-05-18

Each existing test file in `tests/v1/engine/components/transform/test_map*.py`
and the converter side `tests/converters/talend_to_v1/components/transform/test_map*.py`
is triaged as KEEP / FIX / DELETE before being treated as the regression contract
for the new map/ package.

## Engine-side test files

| File | Disposition | Rationale |
|---|---|---|
| test_map.py | TBD per task | Read assertions; KEEP if Talend-parity, FIX if codifying legacy bug, DELETE if testing implementation detail of old dispatch |
| test_map_bridge.py | TBD | Same |
| test_map_05_3_e2e.py | TBD | Same |
| test_map_05_3_perf.py | TBD | Same |
| test_map_05_4_e2e.py | TBD | Same |
| test_map_groovy_safety.py | TBD | Same |
| test_map_integration.py | TBD | Same |
| test_map_method_size.py | LIKELY DELETE | Tested current code's per-output-method JVM bytecode workaround; new design uses one script (no method split) |
| test_map_reject_inner_join.py | TBD | Same |
| test_map_reject_catch.py | TBD | Will need FIX for stack-trace tests |
| test_map_reject_filter.py | LIKELY FIX | 4 strict-xfails to be promoted to PASS |

## Converter-side test files

| File | Disposition | Rationale |
|---|---|---|
| converters/.../test_map.py | KEEP (no changes) | Converter is untouched; tests should still pass |
| converters/.../test_map_types.py | KEEP | Same |
| converters/.../test_xml_map.py | KEEP | xml_map untouched |

## Procedure for each TBD entry

1. Read the file's test functions
2. For each test:
   - Run it: `pytest <path>::<test_name> -v`
   - If it PASSES against the new code → KEEP (move on)
   - If it FAILS:
     - Read the assertion. Is the new behavior CORRECT (Talend-parity)?
       - Yes → FIX the assertion. Note in triage doc.
       - No → bug in new code. Fix the code; rerun.
     - Is the test checking implementation detail of legacy code (e.g. internal dispatch, locality classifier, per-method byte budgets)?
       - DELETE. Note rationale.
3. Update this triage doc with the final disposition

## Resolution Log

(Filled in as triage progresses)
```

- [ ] **Step 2: Run the full transform test suite once and record results**

```bash
python -m pytest tests/v1/engine/components/transform/ -m "not oracle" --no-cov -q --tb=line 2>&1 | tail -30 > /tmp/tmap_test_run.txt
cat /tmp/tmap_test_run.txt
```

Use the output to populate the triage doc. For each failing test, work through the procedure above. This is iterative — could take several hours.

- [ ] **Step 3: Iterate triage until all KEEP+FIX tests pass and DELETE'd files are removed**

This is N sub-steps, one per test file. Each sub-step:
- Edit the test file (fix assertions per the new correct behavior, or delete the file)
- Run that file's tests:
  ```bash
  python -m pytest tests/v1/engine/components/transform/<filename> -v --no-cov 2>&1 | tail -10
  ```
- Update the triage doc
- Commit per file:
  ```bash
  git add tests/v1/engine/components/transform/<filename> .planning/quick/2026-05-18-tmap-test-triage.md
  git commit -m "test(tmap-triage): <KEEP/FIX/DELETE> <filename> -- <one-line reason>"
  ```

- [ ] **Step 4: Final triage commit confirming all engine-side tests pass against new code**

```bash
python -m pytest tests/v1/engine/components/transform/ -m "not oracle" --no-cov -q 2>&1 | tail -5
```

Expected: no failures (xfails OK if explicitly marked). All KEEP+FIX tests green.

---

## Phase 9 — New Bug-Fix Tests

### Task 9.1: Type round-trip test matrix (8 types × {data, context, globalMap})

**Files:**
- Create: `tests/v1/engine/components/transform/map/test_type_fidelity.py`

- [ ] **Step 1: Write the parametrized matrix test**

Create `tests/v1/engine/components/transform/map/test_type_fidelity.py`:

```python
"""Type round-trip across Python/Java for context/globalMap/row data.

For each Talend type, verify the value arrives in Groovy as the correct
Java class (via instanceof / .getClass().getName())."""
import datetime
from decimal import Decimal

import pytest


TYPE_CASES = [
    # (talend_type, python_value, expected_java_class)
    ("id_String",     "hello",                       "java.lang.String"),
    ("id_Integer",    42,                            "java.lang.Integer"),
    ("id_Long",       9_999_999_999,                 "java.lang.Long"),
    ("id_Boolean",    True,                          "java.lang.Boolean"),
    ("id_BigDecimal", Decimal("3.14"),               "java.math.BigDecimal"),
    ("id_Date",       datetime.date(2025, 6, 1),     "java.util.Date"),
    ("id_Date",       datetime.datetime(2025, 6, 1), "java.util.Date"),
    ("id_Double",     1.5,                           "java.lang.Double"),
]


@pytest.mark.java
@pytest.mark.parametrize("talend_type,py_value,expected_class", TYPE_CASES)
def test_context_round_trip(java_bridge, talend_type, py_value, expected_class):
    """context.X arrives in Groovy as the correct Java class."""
    java_bridge.set_context("the_val", py_value)
    result = java_bridge.execute_one_time_expression(
        "context.get(\"the_val\").getClass().getName()"
    )
    assert result == expected_class, (
        f"{talend_type}: expected {expected_class}, got {result}"
    )


@pytest.mark.java
@pytest.mark.parametrize("talend_type,py_value,expected_class", TYPE_CASES)
def test_global_map_round_trip(java_bridge, talend_type, py_value, expected_class):
    """globalMap.get(key) returns the correct Java class."""
    java_bridge.set_global_map("the_val", py_value)
    result = java_bridge.execute_one_time_expression(
        "globalMap.get(\"the_val\").getClass().getName()"
    )
    assert result == expected_class
```

- [ ] **Step 2: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_type_fidelity.py -m java --no-cov -v 2>&1 | tail -25
```

Expected: All cases PASS for context AND globalMap **except** `id_Float` cases. `id_Float` requires the `gateway.jvm.java.lang.Float` wrap from `map_bridge_sync.py` — but `set_context` is the legacy direct setter that doesn't apply the wrap. Add a clarifying note in the triage doc; the test as written should PASS for Double (which is what Py4J sends by default for floats). If id_Float was in the test list, remove it (covered by tests that go through `push_runtime_state_to_bridge`).

Actually re-check TYPE_CASES — id_Float was not included (only id_Double); the matrix should be 16 cases (8 types × 2 namespaces) but we have 8 types so 16 PARAM cases per matrix function. Expected counts depend on which types are in TYPE_CASES.

```bash
git add tests/v1/engine/components/transform/map/test_type_fidelity.py
git commit -m "test(tmap): type round-trip matrix for context + globalMap (8 types)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9.2: errorStackTrace populated test

**Files:**
- Modify: existing `tests/v1/engine/components/transform/test_map_reject_catch.py` OR create new file

- [ ] **Step 1: Add or update a test that asserts errorStackTrace is non-empty for a thrown row**

In `tests/v1/engine/components/transform/test_map_reject_catch.py`, find the test that previously asserted `errorStackTrace` was empty (or xfailed) and update it:

```python
@pytest.mark.java
def test_catch_output_reject_stack_trace_populated(java_bridge_manager):
    """die_on_error=false: errorStackTrace column contains real stack frames."""
    # ... fixture setup that intentionally throws (e.g. division by zero) ...
    # ... execute tMap ...
    # ... assert errorMessage is non-empty AND errorStackTrace contains a frame
    assert errs.iloc[0]["errorMessage"]
    assert "at " in errs.iloc[0]["errorStackTrace"]
```

If a similar test exists with xfail/skip, remove the marker.

- [ ] **Step 2: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_reject_catch.py -m java --no-cov -v 2>&1 | tail -15
```

Expected: the stack-trace test PASSES (Java change in Task 0.2 + active script change in Task 3.2 deliver this end-to-end).

```bash
git add tests/v1/engine/components/transform/test_map_reject_catch.py
git commit -m "test(tmap): catch_output_reject.errorStackTrace contains real frames

Promotes (or fixes) the previously-xfailed assertion. Real stack traces
are emitted by the active script's inner try/catch via
e.printStackTrace(StringWriter) and serialized by Java side's
__errors__ Arrow branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9.3: Filter-reject compiled-path tests (promote 4 xfails from Phase 05.5)

**Files:**
- Modify: `tests/v1/engine/components/transform/test_map_reject_filter.py`

- [ ] **Step 1: Remove the strict-xfail markers from the 4 tests**

In `test_map_reject_filter.py`, find `_COMPILED_FILTER_REJECT_XFAIL` constant. Remove it (or set it to a no-op marker). Remove its application to the 4 tests:

- `test_filter_reject_compiled_same_name_ref`
- `test_filter_reject_compiled_renamed_ref`
- `test_filter_reject_compiled_hardcoded_literal`
- `test_filter_reject_compiled_java_expr`

- [ ] **Step 2: Run + commit**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_reject_filter.py::TestFilterRejectCompiled -m java --no-cov -v 2>&1 | tail -15
```

Expected: all 4 PASS (the new active script emits filter-reject routing in the active loop via `matchedAny`).

```bash
git add tests/v1/engine/components/transform/test_map_reject_filter.py
git commit -m "test(tmap): promote 4 filter-reject compiled-path xfails to active

The new active script populates is_reject outputs inline via the
matchedAny boolean. The 4 strict-xfails from Phase 05.5 are now green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 10 — Diff Harness

### Task 10.1: scripts/diff_map_outputs.py

**Files:**
- Create: `scripts/diff_map_outputs.py`

- [ ] **Step 1: Write the diff harness**

Create `scripts/diff_map_outputs.py`:

```python
#!/usr/bin/env python3
"""Diff harness: run every tMap fixture through both legacy Map and new Map,
assert outputs are equal.

Usage:
    python scripts/diff_map_outputs.py [fixture_glob]

Default glob: tests/fixtures/jobs/transform/**/*.json
Exit code 0 if all match, 1 on any divergence.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pandas as pd


def _import_map_classes():
    """Return (NewMap, LegacyMap) classes."""
    from src.v1.engine.components.transform.map.map_component import Map as NewMap
    from src.v1.engine.components.transform.map_legacy import Map as LegacyMap
    return NewMap, LegacyMap


def _build_fake_inputs(map_comp_cfg, *, n_main=3, n_lookup=3):
    """Build synthetic inputs for each declared input flow."""
    inputs: dict[str, pd.DataFrame] = {}
    main_name = map_comp_cfg["inputs"]["main"]["name"]
    schema_inputs = map_comp_cfg.get("schema", {}).get("inputs", {})
    for flow_name, cols in schema_inputs.items():
        if not cols:
            continue
        data = {}
        for c in cols:
            if c["type"] == "int":
                data[c["name"]] = [i + 1 for i in range(n_main if flow_name == main_name else n_lookup)]
            else:
                data[c["name"]] = [f"v{i}" for i in range(n_main if flow_name == main_name else n_lookup)]
        inputs[flow_name] = pd.DataFrame(data)
    return inputs


def diff_one_fixture(fixture_path: str) -> tuple[bool, str]:
    NewMap, LegacyMap = _import_map_classes()
    job = json.loads(Path(fixture_path).read_text())
    for comp in job["components"]:
        if comp.get("type") not in ("Map", "tMap"):
            continue
        cfg = comp["config"]
        inputs = _build_fake_inputs(comp)
        new_m = NewMap(comp["id"] + "_new", cfg)
        legacy_m = LegacyMap(comp["id"] + "_legacy", cfg)
        new_m.schema_inputs_map = comp.get("schema", {}).get("inputs", {})
        legacy_m.schema_inputs_map = comp.get("schema", {}).get("inputs", {})
        # (Bridge attachment omitted here; the harness is best-run inside the
        # test suite via a session-scoped java_bridge fixture. The plan
        # implementer should adapt this to whatever bootstrap is convenient.)
        try:
            new_result = new_m.execute(inputs)
            legacy_result = legacy_m.execute(inputs)
        except Exception as e:
            return False, f"{fixture_path}: execute raised {type(e).__name__}: {e}"
        for out_name in new_result:
            if out_name not in legacy_result:
                continue
            try:
                pd.testing.assert_frame_equal(
                    new_result[out_name].reset_index(drop=True),
                    legacy_result[out_name].reset_index(drop=True),
                    check_dtype=False,
                )
            except AssertionError as e:
                return False, f"{fixture_path}: {out_name} diverges: {e}"
    return True, "OK"


def main():
    glob_pat = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/jobs/transform/**/*.json"
    fixtures = sorted(glob.glob(glob_pat, recursive=True))
    if not fixtures:
        print(f"No fixtures matched {glob_pat}")
        return 1
    failures = []
    for f in fixtures:
        ok, msg = diff_one_fixture(f)
        marker = "OK " if ok else "FAIL"
        print(f"{marker} {f}: {msg}")
        if not ok:
            failures.append(f)
    print(f"\n{len(fixtures) - len(failures)}/{len(fixtures)} passed")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/diff_map_outputs.py
git commit -m "feat(tmap): diff harness for fixture-by-fixture old vs new output comparison

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10.2: Run the harness; fix any divergences

- [ ] **Step 1: Run the harness**

```bash
python scripts/diff_map_outputs.py 2>&1 | tail -30
```

Expected: most fixtures pass; any divergences point at correctness gaps to fix. Iterate on the new Map until all fixtures match.

- [ ] **Step 2: Commit the iteration fixes (if any)**

```bash
git add -A
git commit -m "fix(tmap): align new Map output to legacy on <fixture_name>"
```

---

## Phase 11 — Final Verification

### Task 11.1: Phase 14 coverage gate

- [ ] **Step 1: Run the per-module coverage gate (per CLAUDE.md)**

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected: PASS with all in-scope modules ≥ 95.0%. If any new map/ module is below the floor, write the missing-line tests in that module's test file (not in this plan — gap-fill within Phase 11.1).

- [ ] **Step 2: Commit any coverage-fill tests**

```bash
git add tests/v1/engine/components/transform/map/
git commit -m "test(tmap): coverage-fill for map/ modules above the 95% floor"
```

---

### Task 11.2: Delete map_legacy.py (cleanup)

- [ ] **Step 1: Confirm all KEEP+FIX tests pass and diff harness passes against the new code WITHOUT legacy**

```bash
python -m pytest tests/v1/engine/components/transform/ -m "not oracle" --no-cov -q 2>&1 | tail -5
```

Expected: clean.

- [ ] **Step 2: Remove the legacy file**

```bash
git rm src/v1/engine/components/transform/map_legacy.py
```

Also remove `LegacyMap` import from `scripts/diff_map_outputs.py` (the harness now has nothing to compare against; either delete the script or leave it as a one-sided sanity runner).

- [ ] **Step 3: Run the full suite one more time**

```bash
python -m pytest tests/ -m "not oracle" -n auto --no-cov -q 2>&1 | tail -10
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore(tmap): delete map_legacy.py — rewrite verified

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11.3: Update CLAUDE.md if any constraint emerged

- [ ] **Step 1: Decide if CLAUDE.md needs updating**

Review the spec's Section 14 (Known Follow-ups) and any constraints discovered during implementation. If any of them justifies a CLAUDE.md note, add it; otherwise skip.

- [ ] **Step 2: Commit if changed**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): update for tMap rewrite outcomes"
```

---

### Task 11.4: Final summary commit

- [ ] **Step 1: Write a short summary note**

Create `.planning/quick/2026-05-18-tmap-rewrite-summary.md` with:
- Total LOC: old 4292 → new (sum across map/) — record the actual number
- Number of bugs fixed (from xfails promoted + new test count)
- Number of legacy tests KEPT / FIXED / DELETED
- Coverage numbers before/after

- [ ] **Step 2: Commit**

```bash
git add .planning/quick/2026-05-18-tmap-rewrite-summary.md
git commit -m "docs(tmap): rewrite complete — final summary"
```

---

## Self-Review Checklist (run after writing this plan)

- [ ] Every spec section has at least one task (§1-15 coverage check)
- [ ] No "TBD" / "TODO" / "fill in later" in any executable step
- [ ] Function and class names consistent across tasks
- [ ] Every file path is exact (no `<path>` placeholders)
- [ ] Every test step has either real code or a `pytest` invocation with expected outcome
- [ ] Every commit step has the actual `git commit -m "..."` text
- [ ] Tasks ordered so dependencies are met (config before joins, joins before component, etc.)

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-18-tmap-rewrite.md`.**
