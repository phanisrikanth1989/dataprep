# tMap debug logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add observability log statements to the tMap engine component (`map_component.py`) so the next time a tMap misbehaves — like the manager's all-rows-to-`__errors__` run — the failure is visible at default log levels without enabling DEBUG.

**Architecture:** Pure additive logging. ~8 log statements at 5 surfaces (per-lookup join trace, `__errors__` surfacing, main filter, empty lookup short-circuit, script compile). No behavior change, no API change, no JSON contract change. Style matches the existing tMap `[%s]` bracket prefix + %-style format strings.

**Tech Stack:** Python 3.12, standard `logging` module, pytest `caplog` fixture.

**Spec:** `docs/superpowers/specs/2026-05-19-tmap-debug-logging-design.md`

---

## Verification gate (run after Task 4)

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

`map_component.py` is currently 97.8% covered. The new tests must keep it >= 95%.

---

## Task 1: Module setup + per-lookup join trace (§5.1)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_component.py`
- Test: `tests/v1/engine/components/transform/map/test_map_component.py` (append)

This task adds `logging` + `time` imports, the module-level `logger`, and the two INFO log statements that bracket each lookup join. Also reorders the strategy dispatch to capture a `time.perf_counter()` snapshot.

- [ ] **Step 1: Write the failing tests**

Append to `tests/v1/engine/components/transform/map/test_map_component.py`:

```python
# ===== Debug logging: per-lookup join trace =====

import logging as _logging


def _logger_name():
    return "src.v1.engine.components.transform.map.map_component"


def test_log_lookup_join_before_and_after_pair(caplog):
    """Each lookup join emits exactly two INFO records: before and after."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_1",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "row8",
                "matching_mode": "FIRST_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "join_mode": "LEFT_OUTER_JOIN",
                "join_keys": [{
                    "lookup_column": "name",
                    "expression": "{{java}}context.SOURCE",
                    "type": "str",
                }],
            }],
        },
        "outputs": [{
            "name": "out1",
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                {"name": "info", "expression": "row8.info", "type": "id_String"},
            ],
        }],
    }
    main_df = pd.DataFrame({"id": [1, 2]})
    lookup_df = pd.DataFrame({"name": ["beta"], "info": ["B"]})

    m = Map(component_id="tMap_1", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": main_df, "row8": lookup_df})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    before = [m for m in msgs if "lookup 'row8' strategy=" in m]
    after = [m for m in msgs if "lookup 'row8' joined: result_rows=" in m]
    assert len(before) == 1, f"Expected one before-join INFO record, got {before}"
    assert len(after) == 1, f"Expected one after-join INFO record, got {after}"
    # Before line carries the configured shape
    assert "[tMap_1]" in before[0]
    assert "match=FIRST_MATCH" in before[0]
    assert "join=LEFT_OUTER_JOIN" in before[0]
    assert "keys=[name <= {{java}}context.SOURCE]" in before[0]
    assert "main_rows=2" in before[0]
    assert "lookup_rows=1" in before[0]
    assert "filter_active=False" in before[0]
    # After line carries the result counts and elapsed
    assert "[tMap_1]" in after[0]
    assert "rejects=0" in after[0]
    assert "elapsed=" in after[0]


def test_log_lookup_join_strategy_value_appears(caplog):
    """The strategy enum value appears in the before-join line."""
    from src.v1.engine.components.transform.map.map_component import Map

    # Same shape as the previous test: context.SOURCE -> CONSTANT_KEY
    config = {
        "label": "tMap_strat",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "row8",
                "matching_mode": "FIRST_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "join_mode": "LEFT_OUTER_JOIN",
                "join_keys": [{
                    "lookup_column": "name",
                    "expression": "{{java}}context.SOURCE",
                    "type": "str",
                }],
            }],
        },
        "outputs": [{
            "name": "out1",
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
            ],
        }],
    }
    m = Map(component_id="tMap_strat", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({
            "row1": pd.DataFrame({"id": [1]}),
            "row8": pd.DataFrame({"name": ["beta"], "info": ["B"]}),
        })

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any("strategy=constant_key" in m for m in msgs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -k log_lookup_join -v`

Expected: FAIL — no INFO log records appear because the production code doesn't emit them yet. Specifically the `assert len(before) == 1` will fail with `Expected one before-join INFO record, got []`.

- [ ] **Step 3: Add module-level setup to `map_component.py`**

Find the existing import block at the top of `src/v1/engine/components/transform/map/map_component.py`:

```python
from __future__ import annotations

import copy
from typing import Any, Optional

import pandas as pd

from src.v1.engine.base_component import BaseComponent, ExecutionMode
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError

from .map_config import MapConfig, parse_config, validate_config, has_any_java_marker
```

Replace with:

```python
from __future__ import annotations

import copy
import logging
import time
from typing import Any, Optional

import pandas as pd

from src.v1.engine.base_component import BaseComponent, ExecutionMode
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError

from .map_config import MapConfig, parse_config, validate_config, has_any_java_marker


logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Add the before-join and after-join INFO logs**

In `Map._process`, find the strategy dispatch block currently at lines 117-160. The block looks like (paraphrased):

```python
            strategy = classify_join_strategy(
                lk,
                main_name=cfg.main.name,
                prior_lookup_names=[n for n, _ in consumed_lookups],
            )
            # ... lookup filter pre-application block ...
            if strategy == JoinStrategy.SIMPLE:
                joined_df, rejects = join_simple_equality(joined_df, lookup_df, lk)
            elif strategy == JoinStrategy.CONSTANT_KEY:
                # ...
            # ... other strategies ...
            if rejects is not None and not rejects.empty:
                inner_join_reject_dfs[lk.name] = rejects
            consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))
```

Insert the **before-join INFO log + start timer** immediately AFTER the lookup-filter pre-application block (around current line 132, immediately before `if strategy == JoinStrategy.SIMPLE`):

```python
            logger.info(
                "[%s] lookup '%s' strategy=%s match=%s join=%s keys=[%s] "
                "main_rows=%d lookup_rows=%d filter_active=%s",
                self.id, lk.name, strategy.value, lk.matching_mode,
                lk.join_mode,
                ", ".join(
                    f"{jk.lookup_column} <= {jk.expression}"
                    for jk in lk.join_keys
                ),
                len(joined_df), len(lookup_df), lk.activate_filter,
            )
            start = time.perf_counter()
```

Then insert the **after-join INFO log** immediately AFTER the strategy dispatch finishes (immediately before the `if rejects is not None and not rejects.empty:` line, currently around line 155-156):

```python
            elapsed = time.perf_counter() - start
            logger.info(
                "[%s] lookup '%s' joined: result_rows=%d rejects=%d elapsed=%.3fs",
                self.id, lk.name, len(joined_df),
                0 if rejects is None else len(rejects),
                elapsed,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -k log_lookup_join -v`

Expected: 2/2 PASS.

Also run the full map suite to catch regressions:

Run: `python -m pytest tests/v1/engine/components/transform/map/ -v`

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/v1/engine/components/transform/map/map_component.py \
        tests/v1/engine/components/transform/map/test_map_component.py
git commit -m "$(cat <<'EOF'
feat(tmap): per-lookup join trace logs (Task 1)

Map._process now emits two INFO log records per lookup join: one
before the strategy dispatch with the lookup name, strategy, match
mode, join mode, key list, and input row counts; one after with
result row counts, reject count, and elapsed time. Adds module-level
logging + time imports and the module logger.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Peripheral observability logs (§5.3 + §5.4 + §5.5)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_component.py`
- Test: `tests/v1/engine/components/transform/map/test_map_component.py` (append)

This task adds the three other INFO log surfaces: main filter row-count change, empty/missing lookup short-circuit, and script compile (active + reject).

- [ ] **Step 1: Write the failing tests**

Append to `tests/v1/engine/components/transform/map/test_map_component.py`:

```python
# ===== Debug logging: peripheral observability =====


def test_log_lookup_skipped_when_lookup_df_none(caplog):
    """Missing lookup input -> INFO record with 'no input data'."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_skip",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "row8",
                "matching_mode": "FIRST_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "join_mode": "LEFT_OUTER_JOIN",
                "join_keys": [{
                    "lookup_column": "name",
                    "expression": "{{java}}context.SOURCE",
                    "type": "str",
                }],
            }],
        },
        "outputs": [{
            "name": "out1",
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
            ],
        }],
    }
    m = Map(component_id="tMap_skip", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        # Note: row8 is NOT in the inputs dict at all -> lookup_df is None
        m._process({"row1": pd.DataFrame({"id": [1]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_skip] lookup 'row8' skipped: no input data" in msg
        for msg in msgs
    )


def test_log_lookup_skipped_when_lookup_df_empty(caplog):
    """Empty lookup DataFrame -> INFO record with 'empty frame'."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_empty",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "row8",
                "matching_mode": "FIRST_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "join_mode": "LEFT_OUTER_JOIN",
                "join_keys": [{
                    "lookup_column": "name",
                    "expression": "{{java}}context.SOURCE",
                    "type": "str",
                }],
            }],
        },
        "outputs": [{
            "name": "out1",
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
            ],
        }],
    }
    m = Map(component_id="tMap_empty", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({
            "row1": pd.DataFrame({"id": [1]}),
            # Empty frame with the right columns
            "row8": pd.DataFrame({"name": [], "info": []}),
        })

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_empty] lookup 'row8' skipped: empty frame" in msg
        for msg in msgs
    )


def test_log_main_filter_drops_rows(caplog):
    """Main filter that drops rows logs a before/after INFO record."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_mainfilter",
        "die_on_error": False,
        "inputs": {
            "main": {
                "name": "row1",
                "activate_filter": True,
                "filter": "{{java}}row1.id > 1",
            },
            "lookups": [],
        },
        "outputs": [{
            "name": "out1",
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
            ],
        }],
    }

    # Stub bridge: filter eval returns boolean mask via batch eval
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None
    bridge.execute_compiled_tmap_chunked.side_effect = (
        lambda **kwargs: {"out1": kwargs["df"].copy().assign(id=kwargs["df"]["id"])}
    )
    # apply_filter calls execute_tmap_preprocessing with {"__filter__": expr}
    # returning {"__filter__": [bool, bool, ...]}. We drop rows where id <= 1.
    def fake_preprocess(df, expressions, main_table_name, lookup_table_names):
        return {"__filter__": [bool(v > 1) for v in df["id"].tolist()]}
    bridge.execute_tmap_preprocessing.side_effect = fake_preprocess

    m = Map(component_id="tMap_mainfilter", config=config)
    m._fresh_config()
    m.java_bridge = bridge
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [1, 2, 3]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_mainfilter] main filter: 3 -> 2 rows" in msg
        for msg in msgs
    )


def test_log_compile_active_script(caplog):
    """Active script compile logs INFO with the output count."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_compile",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [],
        },
        "outputs": [
            {
                "name": "out1",
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
            {
                "name": "out2",
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
        ],
    }
    m = Map(component_id="tMap_compile", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [1]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_compile] compiling active script (2 outputs)" in msg
        for msg in msgs
    )


def test_log_compile_reject_script(caplog):
    """Reject script compile logs INFO when inner_join_reject path is taken.

    The reject pass only runs when (a) at least one output has
    inner_join_reject=True AND (b) inner_join_reject_dfs is non-empty
    (which requires an INNER_JOIN lookup to produce rejects). We use a
    CONSTANT_KEY lookup with INNER_JOIN + a context value that doesn't
    match any lookup row to force every main row into rejects.
    """
    from src.v1.engine.components.transform.map.map_component import Map
    from src.v1.engine.context_manager import ContextManager
    from src.v1.engine.global_map import GlobalMap

    config = {
        "label": "tMap_rej_compile",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "row8",
                "matching_mode": "FIRST_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "join_mode": "INNER_JOIN",
                "join_keys": [{
                    "lookup_column": "name",
                    "expression": "{{java}}context.SOURCE",
                    "type": "str",
                }],
            }],
        },
        "outputs": [
            {
                "name": "out1",
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
            {
                "name": "rej",
                "inner_join_reject": True,
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
        ],
    }

    ctx = ContextManager()
    ctx.set("SOURCE", "no_such_name")  # Will cause INNER_JOIN to reject all

    m = Map(
        component_id="tMap_rej_compile", config=config,
        global_map=GlobalMap(), context_manager=ctx,
    )
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({
            "row1": pd.DataFrame({"id": [1, 2]}),
            "row8": pd.DataFrame({"name": ["alpha"], "info": ["A"]}),
        })

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_rej_compile] compiling reject script (1 outputs)" in msg
        for msg in msgs
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -k "log_lookup_skipped or log_main_filter or log_compile" -v`

Expected: 5/5 FAIL — the production code doesn't emit these logs yet.

- [ ] **Step 3: Add the main filter INFO log**

In `Map._process`, find the main filter block (currently lines 97-104):

OLD:

```python
        # 1. Main filter
        if cfg.main.activate_filter and cfg.main.filter:
            main_df = apply_filter(
                main_df, cfg.main.filter,
                self._bridge_eval_fn(), cfg.main.name, [],
            )
            if main_df.empty:
                return self._create_empty_outputs(cfg)
```

NEW:

```python
        # 1. Main filter
        if cfg.main.activate_filter and cfg.main.filter:
            before_count = len(main_df)
            main_df = apply_filter(
                main_df, cfg.main.filter,
                self._bridge_eval_fn(), cfg.main.name, [],
            )
            logger.info(
                "[%s] main filter: %d -> %d rows (filter=%s)",
                self.id, before_count, len(main_df), cfg.main.filter,
            )
            if main_df.empty:
                return self._create_empty_outputs(cfg)
```

- [ ] **Step 4: Add the empty/missing lookup INFO log**

In `Map._process`, find the per-lookup loop's empty-lookup short-circuit (currently around lines 113-116):

OLD:

```python
        for lk in cfg.lookups:
            lookup_df = inputs.get(lk.name)
            if lookup_df is None or lookup_df.empty:
                consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))
                continue
```

NEW:

```python
        for lk in cfg.lookups:
            lookup_df = inputs.get(lk.name)
            if lookup_df is None or lookup_df.empty:
                logger.info(
                    "[%s] lookup '%s' skipped: %s",
                    self.id, lk.name,
                    "no input data" if lookup_df is None else "empty frame",
                )
                consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))
                continue
```

- [ ] **Step 5: Add the active and reject script compile INFO logs**

In `Map._process`, find the **active script compile** call (currently around line 187). Insert the INFO log immediately before the `self.java_bridge.compile_tmap_script(...)` call:

The current block (paraphrased):
```python
        active_script = build_active_script(cfg)
        push_runtime_state_to_bridge(
            self.context_manager, self.global_map, self.java_bridge,
        )
        component_active_id = f"{self.id}__active"
        self.java_bridge.compile_tmap_script(
            component_id=component_active_id,
            java_script=active_script,
            ...
        )
```

becomes:

```python
        active_script = build_active_script(cfg)
        push_runtime_state_to_bridge(
            self.context_manager, self.global_map, self.java_bridge,
        )
        component_active_id = f"{self.id}__active"
        logger.info(
            "[%s] compiling active script (%d outputs)",
            self.id, sum(1 for o in cfg.outputs if not o.inner_join_reject),
        )
        self.java_bridge.compile_tmap_script(
            component_id=component_active_id,
            java_script=active_script,
            ...
        )
```

Then find the **reject script compile** call (currently around line 224, inside the `if has_inner_reject_outputs and inner_join_reject_dfs:` branch):

```python
                reject_script = build_reject_script(cfg)
                component_reject_id = f"{self.id}__reject"
                self.java_bridge.compile_tmap_script(
                    component_id=component_reject_id,
                    java_script=reject_script,
                    ...
                )
```

becomes:

```python
                reject_script = build_reject_script(cfg)
                component_reject_id = f"{self.id}__reject"
                logger.info(
                    "[%s] compiling reject script (%d outputs)",
                    self.id, sum(1 for o in cfg.outputs if o.inner_join_reject),
                )
                self.java_bridge.compile_tmap_script(
                    component_id=component_reject_id,
                    java_script=reject_script,
                    ...
                )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -k "log_lookup_skipped or log_main_filter or log_compile" -v`

Expected: 5/5 PASS.

Also re-run Task 1's tests + full map suite to ensure no regressions:

Run: `python -m pytest tests/v1/engine/components/transform/map/ -v`

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/v1/engine/components/transform/map/map_component.py \
        tests/v1/engine/components/transform/map/test_map_component.py
git commit -m "$(cat <<'EOF'
feat(tmap): main filter + empty lookup + script compile logs (Task 2)

Three peripheral observability surfaces added at INFO:
  - main filter row-count change (before -> after with filter expr)
  - empty/missing lookup short-circuit ("no input data" / "empty frame")
  - active and reject script compile (output counts)

All use the established [%s] bracket prefix + %-style format pattern.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `__errors__` surfacing (§5.2)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_component.py`
- Test: `tests/v1/engine/components/transform/map/test_map_component.py` (append)

This is the most important surface — it's what would have shown the manager the manager why the production run failed. Three log statements (WARN summary + first 3 messages; INFO routing decision; DEBUG full stack traces), all gated on `err_count > 0`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/v1/engine/components/transform/map/test_map_component.py`:

```python
# ===== Debug logging: __errors__ surfacing =====


def _make_errors_bridge(err_count, messages, stack_traces=None, total_rows=2):
    """Stub bridge whose active execute returns a populated __errors__ dict."""
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None
    stack_traces = stack_traces or {}

    def fake_chunked(component_id, df, chunk_size, input_columns,
                    schema, reject_mode):
        return {
            "out1": pd.DataFrame({"id": list(range(total_rows))}),
            "__errors__": {
                "count": err_count,
                "indices": list(messages.keys()),
                "messages": messages,
                "stackTraces": stack_traces,
            },
        }
    bridge.execute_compiled_tmap_chunked.side_effect = fake_chunked
    bridge.execute_batch_one_time_expressions.return_value = {}
    return bridge


def _base_errors_config(label="tMap_err", with_catch_output=False):
    outputs = [{
        "name": "out1",
        "columns": [
            {"name": "id", "expression": "row1.id", "type": "id_Integer"},
        ],
    }]
    if with_catch_output:
        outputs.append({
            "name": "rej",
            "catch_output_reject": True,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
            ],
        })
    return {
        "label": label,
        "die_on_error": False,
        "inputs": {"main": {"name": "row1"}, "lookups": []},
        "outputs": outputs,
    }


def test_log_errors_warning_when_active_script_captures_errors(caplog):
    """__errors__ count > 0 -> WARNING with count, percent, and first 3 messages."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err1")
    messages = {0: "msg0", 1: "msg1", 2: "msg2", 3: "msg3"}

    m = Map(component_id="tMap_err1", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(
        err_count=4, messages=messages, total_rows=4,
    )
    m._validate_config()

    with caplog.at_level(_logging.WARNING, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0, 1, 2, 3]})})

    warn_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.WARNING
    ]
    assert len(warn_msgs) == 1, f"Expected 1 WARN record, got {warn_msgs}"
    m_text = warn_msgs[0]
    assert "[tMap_err1]" in m_text
    assert "captured 4/4 rows in __errors__" in m_text
    assert "(100.0%)" in m_text
    assert "first 3:" in m_text
    assert "row 0: msg0" in m_text
    assert "row 1: msg1" in m_text
    assert "row 2: msg2" in m_text
    # row 3 must NOT appear -- only first 3 shown
    assert "row 3:" not in m_text


def test_log_errors_routing_with_catch_output(caplog):
    """When catch_output_reject is configured, INFO routing line names it."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err2", with_catch_output=True)
    messages = {0: "msg0"}

    m = Map(component_id="tMap_err2", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(
        err_count=1, messages=messages, total_rows=1,
    )
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0]})})

    info_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.INFO
    ]
    assert any(
        "[tMap_err2] __errors__ rows routed to catch_output_reject output(s): rej"
        in msg for msg in info_msgs
    )


def test_log_errors_routing_without_catch_output(caplog):
    """When no catch_output_reject is configured, INFO routing line says discarded."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err3", with_catch_output=False)
    messages = {0: "msg0"}

    m = Map(component_id="tMap_err3", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(
        err_count=1, messages=messages, total_rows=1,
    )
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0]})})

    info_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.INFO
    ]
    assert any(
        "[tMap_err3] __errors__ rows discarded "
        "(no catch_output_reject output configured)" in msg
        for msg in info_msgs
    )


def test_log_errors_debug_stack_traces(caplog):
    """At DEBUG level, full stack trace for first 3 rows is logged."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err4")
    messages = {0: "msg0", 1: "msg1", 2: "msg2", 3: "msg3"}
    stack_traces = {
        0: "stack-row-0\n  at Script1.run(Script1.groovy:42)",
        1: "stack-row-1",
        2: "stack-row-2",
        3: "stack-row-3",
    }

    m = Map(component_id="tMap_err4", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(
        err_count=4, messages=messages, stack_traces=stack_traces, total_rows=4,
    )
    m._validate_config()

    with caplog.at_level(_logging.DEBUG, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0, 1, 2, 3]})})

    debug_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.DEBUG
    ]
    # Exactly 3 debug stackTrace records, one per first-3 index
    stack_msgs = [m for m in debug_msgs if "stackTrace for row" in m]
    assert len(stack_msgs) == 3
    assert any("stackTrace for row 0:" in m and "stack-row-0" in m for m in stack_msgs)
    assert any("stackTrace for row 1:" in m and "stack-row-1" in m for m in stack_msgs)
    assert any("stackTrace for row 2:" in m and "stack-row-2" in m for m in stack_msgs)
    assert all("stackTrace for row 3:" not in m for m in stack_msgs)


def test_no_error_log_when_errors_count_zero(caplog):
    """When __errors__ is absent OR count=0, no WARN/INFO/DEBUG error log fires."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err5")
    # Stub bridge whose response has NO __errors__ key at all
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None
    bridge.execute_compiled_tmap_chunked.side_effect = (
        lambda **kw: {"out1": pd.DataFrame({"id": [0]})}
    )
    bridge.execute_batch_one_time_expressions.return_value = {}

    m = Map(component_id="tMap_err5", config=config)
    m._fresh_config()
    m.java_bridge = bridge
    m._validate_config()

    with caplog.at_level(_logging.DEBUG, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    # No __errors__-specific logs
    assert not any("__errors__" in m for m in msgs)
    assert not any("stackTrace for row" in m for m in msgs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -k "log_errors or no_error_log" -v`

Expected: 5/5 FAIL — production code doesn't emit any `__errors__` log records yet.

- [ ] **Step 3: Add the `__errors__` surfacing block**

In `Map._process`, find the line where `errors_df` is popped (currently around line 201):

```python
        errors_df = active_raw.pop("__errors__", None)
```

Immediately AFTER this line, insert the surfacing block:

```python
        if errors_df is not None:
            err_count = int(errors_df.get("count", 0))
            if err_count > 0:
                total_rows = len(joined_df)
                messages = errors_df.get("messages") or {}
                stack_traces = errors_df.get("stackTraces") or {}
                sorted_indices = sorted(messages.keys())[:3]
                samples = " | ".join(
                    f"row {idx}: {messages[idx]}" for idx in sorted_indices
                )
                pct = (100.0 * err_count / total_rows) if total_rows else 0.0
                logger.warning(
                    "[%s] active script captured %d/%d rows in __errors__ "
                    "(%.1f%%) -- first 3: %s",
                    self.id, err_count, total_rows, pct, samples,
                )
                catch_outputs = [
                    o.name for o in cfg.outputs if o.catch_output_reject
                ]
                if catch_outputs:
                    logger.info(
                        "[%s] __errors__ rows routed to catch_output_reject "
                        "output(s): %s",
                        self.id, ", ".join(catch_outputs),
                    )
                else:
                    logger.info(
                        "[%s] __errors__ rows discarded "
                        "(no catch_output_reject output configured)",
                        self.id,
                    )
                for idx in sorted_indices:
                    logger.debug(
                        "[%s] stackTrace for row %d:\n%s",
                        self.id, idx, stack_traces.get(idx, "<no stack>"),
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v1/engine/components/transform/map/test_map_component.py -k "log_errors or no_error_log" -v`

Expected: 5/5 PASS.

Re-run all logging tests + full map suite:

Run: `python -m pytest tests/v1/engine/components/transform/map/ -v`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_component.py \
        tests/v1/engine/components/transform/map/test_map_component.py
git commit -m "$(cat <<'EOF'
feat(tmap): __errors__ surfacing logs (Task 3)

After the active script execution, when __errors__ count > 0:
  - WARNING with count, percent, and the first 3 error messages inline
  - INFO with the routing decision (catch_output_reject vs. discarded)
  - DEBUG with full stack traces for the first 3 error indices

When count is 0 or __errors__ is absent, no log records fire.

Closes the visibility gap that hid the manager's all-rows-to-errors
production run.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Verification + coverage gate

**Files:** None (verification only)

- [ ] **Step 1: Run the full map test suite**

```bash
python -m pytest tests/v1/engine/components/transform/map/ -v
```

Expected: all PASS (Task 1's 2 tests + Task 2's 5 tests + Task 3's 5 tests = 12 new tests, plus the existing suite).

- [ ] **Step 2: Run the per-module coverage gate**

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected: exit 0 with `PASS: all 181 in-scope modules at >= 95.0% line coverage`. Note: 5 pre-existing failures (xml_map x2, py_map, file_input_xml, file_output_delimited) are unrelated to this work.

If `map_component.py` drops below 95%:
- Look at the missing-lines report for `map_component.py`
- The new code adds ~30 lines; most should be hit by the 11 tests above
- Add a targeted test for any uncovered branch (e.g. the `<no stack>` fallback if `stackTraces` doesn't have an entry for a message-bearing index)

- [ ] **Step 3: Smoke-test by running an existing live-bridge integration test with INFO logging enabled**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_integration.py::test_constant_key_context_source_end_to_end -v -m java --log-cli-level=INFO 2>&1 | grep -E "tMap|lookup|__errors__|compiling|main filter" | head -20
```

Expected output should include the new INFO log lines from a real bridge run, similar to:

```
INFO     src.v1.engine.components.transform.map.map_component:map_component.py:N [tMap_1] lookup 'row8' strategy=constant_key match=FIRST_MATCH ...
INFO     src.v1.engine.components.transform.map.map_component:map_component.py:N [tMap_1] lookup 'row8' joined: result_rows=3 rejects=0 elapsed=...
INFO     src.v1.engine.components.transform.map.map_component:map_component.py:N [tMap_1] compiling active script (1 outputs)
```

This confirms the logs work end-to-end with the live JVM bridge, not just the mock-bridge unit tests.

If no log lines appear, ensure `--log-cli-level=INFO` is in effect (pytest may suppress logging at default settings).

- [ ] **Step 4: No commit needed for Task 4** — this is verification only. If a coverage-fill test was needed, it lands in its own commit at the end of Step 2.

---

## Done criteria

After Task 4 verification:
- [ ] Three commits land on `feature/engine-restructure` (Task 1, Task 2, Task 3)
- [ ] `python -m pytest tests/v1/engine/components/transform/map/ -v` is all green
- [ ] Coverage gate exits 0
- [ ] Live-bridge smoke test (Step 3 above) shows the new INFO log lines
- [ ] No production code outside `map_component.py` touched
- [ ] No converter / bridge / Java / JSON-contract changes
