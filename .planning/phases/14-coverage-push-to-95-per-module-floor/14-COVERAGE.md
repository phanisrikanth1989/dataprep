---
phase: 14
slug: coverage-push-to-95-per-module-floor
status: locked
measured: 2026-05-11
test_total: see acceptance gate (Phase 14 -m "not oracle" -n auto run, 0 failures)
test_failures: 0
in_scope_modules: 181
floor_percent: 95.0
floor_status: PASS
overall_percent: 98.3
---

# Phase 14 -- Final Per-Module Coverage Table

> Replaces `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md` per D-E3.
> Source of truth: `14-coverage.json` (committed alongside this file per locked Q4).
> Every in-scope module is at or above the 95% line-coverage floor; legacy `complex_converter/` is omitted (D-A1 + pyproject `[tool.coverage.run]`).

**Measured:** 2026-05-11
**Modules in scope:** 181 (Phase 13 baseline was 198 incl. `__init__.py`; `[tool.coverage.run]` omits `*/__init__.py` and the entire `complex_converter/` legacy package)
**Python:** 3.10+ / pandas 3.0.1 (CoW) / pytest 8.x / pytest-cov 7.0.0 / pytest-xdist 3.8.0
**Java:** JVM 11+ on PATH (required for `-m java` measurement per D-A3)
**Result:** ALL 181 modules at >= 95.0% line coverage; overall 98.3% (16746 / 17033 stmts)

---

## Reproducible Command (paste-runnable)

Run from the project root. Requires JVM 11+ on PATH for `-m java` tests (D-A3); Oracle live tests stay opt-in via `-m oracle` and are excluded from the gate (D-A6).

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Outputs:
- Terminal: per-module table + xdist parallelism summary
- HTML: `htmlcov/index.html` (browseable line-by-line view; gitignored)
- JSON: `coverage.json` (machine-readable; copied to `14-coverage.json` per locked Q4)
- Final line: `PASS: all 181 in-scope modules at >= 95.0% line coverage`

Notes:
- `[tool.coverage.run]` (in `pyproject.toml`) is the source of truth for in-scope modules and pragma allowlist.
- Branch coverage stays off per D-E4 / D-E2 (Phase 13 reasoning carries).
- `rm -f .coverage*` prefix is required (locked Q5) -- stale `.coverage.*` shards from interrupted xdist runs otherwise pollute the JSON report.

---

## Per-Module Coverage Table

Grouped by subsystem. Sorted by coverage % descending within each group. All in-scope modules at >= 95.0%.

### engine.components.file

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/components/file/_xml_io.py` | 24 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_copy.py` | 98 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_exist.py` | 33 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_input_json.py` | 195 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_input_msxml.py` | 124 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_input_positional.py` | 174 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_input_properties.py` | 85 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_input_raw.py` | 62 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_list.py` | 199 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_output_delimited.py` | 264 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_output_excel.py` | 294 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_properties.py` | 46 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_touch.py` | 52 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_unarchive.py` | 65 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/fixed_flow_input.py` | 113 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/set_global_var.py` | 61 | 0 | 100.0% | PASS |
| `src/v1/engine/components/file/file_output_positional.py` | 263 | 1 | 99.6% | PASS |
| `src/v1/engine/components/file/file_input_delimited.py` | 374 | 2 | 99.5% | PASS |
| `src/v1/engine/components/file/file_delete.py` | 87 | 1 | 98.9% | PASS |
| `src/v1/engine/components/file/file_output_advanced_xml.py` | 269 | 5 | 98.1% | PASS |
| `src/v1/engine/components/file/file_input_xml.py` | 139 | 3 | 97.8% | PASS |
| `src/v1/engine/components/file/file_input_excel.py` | 588 | 15 | 97.4% | PASS |
| `src/v1/engine/components/file/file_row_count.py` | 57 | 2 | 96.5% | PASS |
| `src/v1/engine/components/file/file_archive.py` | 80 | 3 | 96.2% | PASS |
| `src/v1/engine/components/file/file_input_fullrow.py` | 73 | 3 | 95.9% | PASS |
| `src/v1/engine/components/file/file_output_xml.py` | 235 | 11 | 95.3% | PASS |

### engine.components.transform

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/components/transform/_code_component_mixin.py` | 29 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/convert_type.py` | 109 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/denormalize.py` | 63 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/extract_delimited_fields.py` | 97 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/extract_json_fields.py` | 129 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/extract_positional_fields.py` | 104 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/extract_regex_fields.py` | 96 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/filter_columns.py` | 26 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/filter_rows.py` | 157 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/java_component.py` | 31 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/join.py` | 129 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/log_row.py` | 90 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/memorize_rows.py` | 48 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/parse_record_set.py` | 63 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/pivot_to_columns_delimited.py` | 108 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/python_component.py` | 37 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/python_dataframe_component.py` | 54 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/python_row_component.py` | 57 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/replace.py` | 98 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/replicate.py` | 29 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/row_generator.py` | 94 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/split_row.py` | 59 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/unite.py` | 22 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/unpivot_row.py` | 63 | 0 | 100.0% | PASS |
| `src/v1/engine/components/transform/aggregate_sorted_row.py` | 84 | 1 | 98.8% | PASS |
| `src/v1/engine/components/transform/sample_row.py` | 58 | 1 | 98.3% | PASS |
| `src/v1/engine/components/transform/normalize.py` | 54 | 1 | 98.1% | PASS |
| `src/v1/engine/components/transform/swift_transformer.py` | 449 | 9 | 98.0% | PASS |
| `src/v1/engine/components/transform/sort_row.py` | 49 | 1 | 98.0% | PASS |
| `src/v1/engine/components/transform/swift_block_formatter.py` | 426 | 12 | 97.2% | PASS |
| `src/v1/engine/components/transform/schema_compliance_check.py` | 121 | 4 | 96.7% | PASS |
| `src/v1/engine/components/transform/change_file_encoding.py` | 55 | 2 | 96.4% | PASS |
| `src/v1/engine/components/transform/extract_xml_fields.py` | 128 | 5 | 96.1% | PASS |
| `src/v1/engine/components/transform/map.py` | 868 | 36 | 95.9% | PASS |
| `src/v1/engine/components/transform/xml_map.py` | 417 | 18 | 95.7% | PASS |
| `src/v1/engine/components/transform/java_row_component.py` | 42 | 2 | 95.2% | PASS |

### engine.components.aggregate

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/components/aggregate/aggregate_row.py` | 199 | 0 | 100.0% | PASS |
| `src/v1/engine/components/aggregate/unique_row.py` | 69 | 0 | 100.0% | PASS |

### engine.components.control

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/components/control/send_mail.py` | 125 | 0 | 100.0% | PASS |
| `src/v1/engine/components/control/sleep.py` | 31 | 0 | 100.0% | PASS |
| `src/v1/engine/components/control/warn.py` | 54 | 1 | 98.1% | PASS |
| `src/v1/engine/components/control/die.py` | 69 | 3 | 95.7% | PASS |

### engine.components.context

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/components/context/context_load.py` | 98 | 2 | 98.0% | PASS |

### engine.components.iterate

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/components/iterate/flow_to_iterate.py` | 64 | 2 | 96.9% | PASS |

### engine.components.database

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/components/database/oracle_row.py` | 134 | 0 | 100.0% | PASS |
| `src/v1/engine/components/database/oracle_output.py` | 406 | 2 | 99.5% | PASS |
| `src/v1/engine/components/database/oracle_connection.py` | 64 | 3 | 95.3% | PASS |

### engine (core modules)

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/v1/engine/base_iterate_component.py` | 86 | 0 | 100.0% | PASS |
| `src/v1/engine/component_registry.py` | 28 | 0 | 100.0% | PASS |
| `src/v1/engine/engine.py` | 158 | 0 | 100.0% | PASS |
| `src/v1/engine/exceptions.py` | 25 | 0 | 100.0% | PASS |
| `src/v1/engine/trigger_manager.py` | 149 | 0 | 100.0% | PASS |
| `src/v1/engine/java_bridge_manager.py` | 101 | 1 | 99.0% | PASS |
| `src/v1/engine/global_map.py` | 54 | 1 | 98.1% | PASS |
| `src/v1/engine/python_routine_manager.py` | 98 | 2 | 98.0% | PASS |
| `src/v1/engine/context_manager.py` | 120 | 3 | 97.5% | PASS |
| `src/v1/engine/base_component.py` | 522 | 15 | 97.1% | PASS |
| `src/v1/engine/output_router.py` | 138 | 4 | 97.1% | PASS |
| `src/v1/engine/oracle_connection_manager.py` | 99 | 3 | 97.0% | PASS |
| `src/v1/engine/execution_plan.py` | 225 | 8 | 96.4% | PASS |
| `src/v1/engine/iterate_logging.py` | 23 | 1 | 95.7% | PASS |
| `src/v1/engine/executor.py` | 334 | 16 | 95.2% | PASS |

### converters.talend_to_v1 (core)

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/registry.py` | 18 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/converter.py` | 205 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/type_mapping.py` | 3 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/base.py` | 109 | 1 | 99.1% | PASS |
| `src/converters/talend_to_v1/expression_converter.py` | 90 | 1 | 98.9% | PASS |
| `src/converters/talend_to_v1/validator.py` | 128 | 3 | 97.7% | PASS |
| `src/converters/talend_to_v1/trigger_mapper.py` | 37 | 1 | 97.3% | PASS |
| `src/converters/talend_to_v1/xml_parser.py` | 163 | 5 | 96.9% | PASS |

### converters.talend_to_v1.components.file

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/file/file_copy.py` | 36 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_delete.py` | 25 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_exist.py` | 18 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_excel.py` | 122 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_fullrow.py` | 28 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_properties.py` | 22 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_raw.py` | 25 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_list.py` | 49 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_delimited.py` | 41 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_ebcdic.py` | 22 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_properties.py` | 20 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_row_count.py` | 21 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_touch.py` | 19 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_unarchive.py` | 30 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_excel.py` | 74 | 1 | 98.6% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_positional.py` | 70 | 1 | 98.6% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_json.py` | 62 | 1 | 98.4% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_xml.py` | 59 | 1 | 98.3% | PASS |
| `src/converters/talend_to_v1/components/file/file_archive.py` | 54 | 1 | 98.1% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_msxml.py` | 53 | 1 | 98.1% | PASS |
| `src/converters/talend_to_v1/components/file/set_global_var.py` | 47 | 1 | 97.9% | PASS |
| `src/converters/talend_to_v1/components/file/fixed_flow_input.py` | 64 | 2 | 96.9% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_delimited.py` | 94 | 3 | 96.8% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_xml.py` | 185 | 6 | 96.8% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_positional.py` | 87 | 3 | 96.6% | PASS |

### converters.talend_to_v1.components.transform

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/transform/change_file_encoding.py` | 23 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_regex_fields.py` | 22 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/filter_columns.py` | 19 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/hash_output.py` | 25 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/java_component.py` | 20 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/java_row_component.py` | 26 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/join.py` | 76 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/normalize.py` | 28 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/parse_record_set.py` | 34 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/python_component.py` | 21 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/python_row_component.py` | 21 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/replace.py` | 95 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/replicate.py` | 19 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/sample_row.py` | 19 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/swift_transformer.py` | 19 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/unite.py` | 17 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/unpivot_row.py` | 28 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_positional_fields.py` | 63 | 1 | 98.4% | PASS |
| `src/converters/talend_to_v1/components/transform/pivot_to_columns_delimited.py` | 58 | 1 | 98.3% | PASS |
| `src/converters/talend_to_v1/components/transform/log_row.py` | 54 | 1 | 98.1% | PASS |
| `src/converters/talend_to_v1/components/transform/xml_map.py` | 214 | 4 | 98.1% | PASS |
| `src/converters/talend_to_v1/components/transform/sort_row.py` | 51 | 1 | 98.0% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` | 49 | 1 | 98.0% | PASS |
| `src/converters/talend_to_v1/components/transform/split_row.py` | 42 | 1 | 97.6% | PASS |
| `src/converters/talend_to_v1/components/transform/memorize_rows.py` | 39 | 1 | 97.4% | PASS |
| `src/converters/talend_to_v1/components/transform/map.py` | 126 | 4 | 96.8% | PASS |
| `src/converters/talend_to_v1/components/transform/schema_compliance_check.py` | 92 | 3 | 96.7% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_delimited_fields.py` | 30 | 1 | 96.7% | PASS |
| `src/converters/talend_to_v1/components/transform/aggregate_sorted_row.py` | 82 | 3 | 96.3% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_json_fields.py` | 80 | 3 | 96.2% | PASS |
| `src/converters/talend_to_v1/components/transform/denormalize.py` | 51 | 2 | 96.1% | PASS |
| `src/converters/talend_to_v1/components/transform/python_dataframe_component.py` | 25 | 1 | 96.0% | PASS |
| `src/converters/talend_to_v1/components/transform/row_generator.py` | 50 | 2 | 96.0% | PASS |
| `src/converters/talend_to_v1/components/transform/convert_type.py` | 45 | 2 | 95.6% | PASS |
| `src/converters/talend_to_v1/components/transform/filter_rows.py` | 66 | 3 | 95.5% | PASS |

### converters.talend_to_v1.components.aggregate

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/aggregate/aggregate_row.py` | 116 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/aggregate/unique_row.py` | 67 | 2 | 97.0% | PASS |

### converters.talend_to_v1.components.control

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/control/die.py` | 23 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/control/loop.py` | 25 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/control/parallelize.py` | 19 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/control/postjob.py` | 16 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/control/prejob.py` | 16 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/control/sleep.py` | 15 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/control/warn.py` | 21 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/control/run_job.py` | 80 | 3 | 96.2% | PASS |
| `src/converters/talend_to_v1/components/control/send_mail.py` | 103 | 4 | 96.1% | PASS |

### converters.talend_to_v1.components.context

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/context/context_load.py` | 29 | 0 | 100.0% | PASS |

### converters.talend_to_v1.components.iterate

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/iterate/flow_to_iterate.py` | 45 | 1 | 97.8% | PASS |
| `src/converters/talend_to_v1/components/iterate/foreach.py` | 36 | 1 | 97.2% | PASS |

### converters.talend_to_v1.components.database

| Module | Stmts | Miss | Cover | Status |
|--------|------:|-----:|------:|--------|
| `src/converters/talend_to_v1/components/database/mssql_connection.py` | 40 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/database/mssql_input.py` | 63 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_close.py` | 17 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_commit.py` | 18 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_connection.py` | 43 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_output.py` | 41 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_rollback.py` | 18 | 0 | 100.0% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_row.py` | 87 | 1 | 98.9% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_input.py` | 80 | 1 | 98.8% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_sp.py` | 71 | 1 | 98.6% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_bulk_exec.py` | 65 | 1 | 98.5% | PASS |

### Summary Row

| Scope | Stmts | Miss | Cover |
|-------|------:|-----:|------:|
| TOTAL (both cov targets, 181 in-scope modules) | 17033 | 287 | 98.3% |

_Modules summed across buckets: 181._

---

## Phase 14 Lift Result Count Summary

Coverage band distribution across all 181 in-scope modules (Phase 14 final state):

| Band | Count | Notes |
|------|------:|-------|
| 100.0% (perfect) | 100 | 55% of in-scope surface fully covered |
| 99.0% - 99.9% | 5 | within 1-2 lines of 100% |
| 98.0% - 98.9% | 23 | tight against ceiling, mostly defensive guards |
| 97.0% - 97.9% | 19 | D-C5 candidates left in source for future cleanup |
| 96.0% - 96.9% | 23 | rare defensive paths, ASCII-log-only catches |
| 95.0% - 95.9% | 11 | floor-margin modules (executor, java_row_component, map) |
| < 95.0% (FAIL) | 0 | none -- gate green |

Lift comparison vs. Phase 13 baseline:

| Subsystem | Below 95% (Phase 13) | Below 95% (Phase 14) | Modules Lifted |
|-----------|---------------------:|---------------------:|---------------:|
| engine.components.file | 16 | 0 | 16 |
| engine.components.transform | 17 | 0 | 17 |
| engine.components.aggregate | 1 | 0 | 1 |
| engine.components.control | 1 | 0 | 1 |
| engine.components.database | 2 | 0 | 2 |
| engine (core) | 7 | 0 | 7 |
| converters.talend_to_v1 (core) | 2 | 0 | 2 |
| converters.talend_to_v1.components.file | 1 | 0 | 1 |
| converters.talend_to_v1.components.transform | 2 | 0 | 2 |
| converters.talend_to_v1.components.aggregate | 1 | 0 | 1 |
| converters.talend_to_v1.components.iterate | 1 | 0 | 1 |
| converters.talend_to_v1.components.database | 1 | 0 | 1 |
| **Totals** | **52** | **0** | **52** |

(Phase 13 baseline counted 53 FAIL rows including the converter-transform `join.py` row at 94.7%; Phase 14 also closed that one via COV-CJ-001.)

---

## Notable Modules

### Deep-gap modules closed (Phase 13 baseline < 50%)

| Module | Phase 13 | Phase 14 | Plan | Notes |
|--------|---------:|---------:|------|-------|
| `src/v1/engine/components/transform/swift_transformer.py` | 7% | 98.0% | 14-07 | Synthetic SWIFT MT generator (MT103/202/940); 5 BUG-SWIFT source fixes |
| `src/v1/engine/components/transform/swift_block_formatter.py` | 7% | 97.2% | 14-07 | Same lift; 12 defensive dict-coercion branches documented |
| `src/v1/engine/components/file/file_input_json.py` | 9% | 100.0% | 14-09 | BUG-FIJ-001 (registry) + BUG-FIJ-002 (abstract method) fixed |
| `src/v1/engine/components/file/file_input_raw.py` | 15% | 100.0% | 14-09 | Real binary fixtures + JSON pipeline-job fixtures |
| `src/v1/engine/components/transform/python_dataframe_component.py` | 20% | 100.0% | 14-06 | BUG-PDC-001 (registry) + BUG-PDC-002 (abstract method) fixed |
| `src/v1/engine/components/file/file_input_excel.py` | 29% | 97.4% | 14-09 | Real .xlsx fixtures; 15 defensive guards documented |
| `src/v1/engine/java_bridge_manager.py` | 59% | 99.0% | 14-10 | @pytest.mark.java tests per D-A3; JVM lifecycle exercised |
| `src/v1/engine/components/control/send_mail.py` | 60% | 100.0% | 14-03 | smtplib boundary mocks (D-A4); BUG-MAIL-001 root-cause fix |

### Floor-margin modules (95.0% - 95.9%)

These cleared the floor with a small margin; documented as containing defensive branches that are intentional (mostly ETLError catch arms reachable only from upstream malformation) or pragma-allowlist-eligible if a future cleanup phase chooses to delete them.

- `src/v1/engine/executor.py` -- 95.2% (16 missing; iterate teardown paths)
- `src/v1/engine/components/transform/java_row_component.py` -- 95.2% (2 missing)
- `src/v1/engine/components/database/oracle_connection.py` -- 95.3% (3 missing; ORACLE_OCI/WALLET deferred branches)
- `src/v1/engine/components/file/file_output_xml.py` -- 95.3% (11 missing)
- `src/converters/talend_to_v1/components/transform/filter_rows.py` -- 95.5% (3 missing)
- `src/converters/talend_to_v1/components/transform/convert_type.py` -- 95.6% (2 missing)
- `src/v1/engine/components/control/die.py` -- 95.7% (3 missing)
- `src/v1/engine/iterate_logging.py` -- 95.7% (1 missing)
- `src/v1/engine/components/transform/xml_map.py` -- 95.7% (18 missing)
- `src/v1/engine/components/transform/map.py` -- 95.9% (36 missing; bridge-driven paths covered via Plan 14-06b @pytest.mark.java)

### Legacy modules (out of scope; omitted from coverage report)

The 4 `src/converters/complex_converter/*.py` modules (component_parser, converter, expression_converter, plus `__init__`) are explicitly N/A per D-A1 and `pyproject.toml` `[tool.coverage.run] omit`. They remain at 5-11% from Phase 13 baseline. A future cleanup phase will delete or migrate them.

---

## Pragma & Dead-Code Policy Outcomes

- **D-C3 pragma allowlist enforcement:** zero `# pragma: no cover` annotations in `src/v1/engine/` or `src/converters/talend_to_v1/` (verified via `grep -rn`). The allowlist (`__main__`, `@abstractmethod`, optional-dep `ImportError` shims) is enforced via `[tool.coverage.report] exclude_also` regexes in `pyproject.toml`, not inline pragmas.
- **D-C5 dead-code deletions during the lift** (documented in plan summaries):
  - Plan 14-02: `_build_agg_func` unknown-function silent-default fallback -> `ConfigurationError`; `_process` column-ordering safety loop
  - Plan 14-05: 5 unreachable defensive branches across `extract_positional_fields`/`extract_regex_fields`/`extract_delimited_fields`
  - Plan 14-06: 3 sets of unreachable defensive branches in `transform/join.py` (post-keep_cols merge / lookup-key drops, lk_col + '_lookup' / out_col-passthrough branches, ConfigurationError/DataValidationError re-raise)
  - Plan 14-07: duplicate `_load_lookup_files` definition in `swift_transformer.py` consolidated
  - Plan 14-08: STALE-FOD-001 `except Exception` catch-all wrapping `pd.to_datetime(errors='coerce')` in `file_output_delimited._apply_date_patterns` (pandas contracts NEVER to raise with errors='coerce')

---

## Phase 13 -> Phase 14 Migration

`13-COVERAGE-BASELINE.md` stays archived in its own phase directory for diff/audit purposes (D-E3). Future phases should refer to **this** file (`14-COVERAGE.md`) plus `14-coverage.json` as the per-module floor source of truth.

---

*Phase 14 final coverage table -- measured 2026-05-11 -- ready for closeout sign-off*
