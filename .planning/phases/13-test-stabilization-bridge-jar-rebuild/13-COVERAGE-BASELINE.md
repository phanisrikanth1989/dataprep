---
phase: 13
slug: test-stabilization-bridge-jar-rebuild
status: locked
measured: 2026-05-10
test_total: 6832
test_failures: 0
---

# Phase 13 -- Coverage Baseline

> Per-module line coverage measured against the green test suite at HEAD `5649b6f`.
> This is the FLOOR for Phase 14's 95% per-module gate.

**Measured:** 2026-05-10
**Test count at measurement:** 6832 passed, 26 skipped, 1 xfailed, 0 failed
**Python:** 3.10+ / pandas 3.0.1 (CoW) / pytest-cov 7.0.0

## Reproducible Command

Run from the project root:

```bash
python -m pytest tests/ \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  -q
```

Outputs:
- Terminal: per-module table (this file's data source)
- HTML: `htmlcov/index.html` (browseable line-by-line view; gitignored)

Note: do NOT add `--cov-branch` -- Phase 14's 95% gate is line coverage only.

---

## Per-Module Coverage Table

Grouped by subsystem. Sorted by coverage % descending within each group.
Phase 14 Floor column: PASS = already at or above 95%, FAIL = below 95% (Phase 14 lift target).

### engine.components.file

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/components/file/_xml_io.py` | 24 | 0 | 100% | PASS |
| `src/v1/engine/components/file/file_exist.py` | 33 | 0 | 100% | PASS |
| `src/v1/engine/components/file/__init__.py` | 28 | 0 | 100% | PASS |
| `src/v1/engine/components/file/file_delete.py` | 87 | 1 | 99% | PASS |
| `src/v1/engine/components/file/file_input_xml.py` | 139 | 3 | 98% | PASS |
| `src/v1/engine/components/file/file_output_advanced_xml.py` | 269 | 5 | 98% | PASS |
| `src/v1/engine/components/file/file_archive.py` | 80 | 3 | 96% | PASS |
| `src/v1/engine/components/file/file_row_count.py` | 57 | 2 | 96% | PASS |
| `src/v1/engine/components/file/file_input_fullrow.py` | 73 | 3 | 96% | PASS |
| `src/v1/engine/components/file/file_output_xml.py` | 235 | 11 | 95% | PASS |
| `src/v1/engine/components/file/file_list.py` | 199 | 11 | 94% | FAIL |
| `src/v1/engine/components/file/file_unarchive.py` | 65 | 5 | 92% | FAIL |
| `src/v1/engine/components/file/file_properties.py` | 46 | 4 | 91% | FAIL |
| `src/v1/engine/components/file/file_copy.py` | 98 | 8 | 92% | FAIL |
| `src/v1/engine/components/file/file_input_properties.py` | 85 | 10 | 88% | FAIL |
| `src/v1/engine/components/file/fixed_flow_input.py` | 113 | 14 | 88% | FAIL |
| `src/v1/engine/components/file/set_global_var.py` | 61 | 7 | 89% | FAIL |
| `src/v1/engine/components/file/file_input_delimited.py` | 374 | 53 | 86% | FAIL |
| `src/v1/engine/components/file/file_output_delimited.py` | 265 | 46 | 83% | FAIL |
| `src/v1/engine/components/file/file_output_positional.py` | 263 | 44 | 83% | FAIL |
| `src/v1/engine/components/file/file_input_positional.py` | 174 | 33 | 81% | FAIL |
| `src/v1/engine/components/file/file_touch.py` | 52 | 9 | 83% | FAIL |
| `src/v1/engine/components/file/file_output_excel.py` | 294 | 91 | 69% | FAIL |
| `src/v1/engine/components/file/file_input_excel.py` | 588 | 419 | 29% | FAIL |
| `src/v1/engine/components/file/file_input_json.py` | 172 | 156 | 9% | FAIL |
| `src/v1/engine/components/file/file_input_raw.py` | 60 | 51 | 15% | FAIL |

### engine.components.transform

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/components/transform/__init__.py` | 37 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/_code_component_mixin.py` | 29 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/denormalize.py` | 63 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/filter_columns.py` | 26 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/java_component.py` | 31 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/memorize_rows.py` | 48 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/replicate.py` | 29 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/split_row.py` | 59 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/unite.py` | 22 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/unpivot_row.py` | 63 | 0 | 100% | PASS |
| `src/v1/engine/components/transform/aggregate_sorted_row.py` | 84 | 1 | 99% | PASS |
| `src/v1/engine/components/transform/normalize.py` | 54 | 1 | 98% | PASS |
| `src/v1/engine/components/transform/sample_row.py` | 58 | 1 | 98% | PASS |
| `src/v1/engine/components/transform/sort_row.py` | 49 | 1 | 98% | PASS |
| `src/v1/engine/components/transform/log_row.py` | 90 | 3 | 97% | PASS |
| `src/v1/engine/components/transform/schema_compliance_check.py` | 121 | 4 | 97% | PASS |
| `src/v1/engine/components/transform/xml_map.py` | 417 | 18 | 96% | PASS |
| `src/v1/engine/components/transform/extract_xml_fields.py` | 128 | 5 | 96% | PASS |
| `src/v1/engine/components/transform/change_file_encoding.py` | 55 | 2 | 96% | PASS |
| `src/v1/engine/components/transform/java_row_component.py` | 42 | 2 | 95% | PASS |
| `src/v1/engine/components/transform/replace.py` | 98 | 6 | 94% | FAIL |
| `src/v1/engine/components/transform/python_row_component.py` | 57 | 4 | 93% | FAIL |
| `src/v1/engine/components/transform/pivot_to_columns_delimited.py` | 108 | 10 | 91% | FAIL |
| `src/v1/engine/components/transform/parse_record_set.py` | 63 | 7 | 89% | FAIL |
| `src/v1/engine/components/transform/row_generator.py` | 94 | 15 | 84% | FAIL |
| `src/v1/engine/components/transform/python_component.py` | 37 | 6 | 84% | FAIL |
| `src/v1/engine/components/transform/extract_positional_fields.py` | 107 | 14 | 87% | FAIL |
| `src/v1/engine/components/transform/extract_regex_fields.py` | 102 | 14 | 86% | FAIL |
| `src/v1/engine/components/transform/convert_type.py` | 109 | 15 | 86% | FAIL |
| `src/v1/engine/components/transform/extract_json_fields.py` | 129 | 18 | 86% | FAIL |
| `src/v1/engine/components/transform/extract_delimited_fields.py` | 103 | 18 | 83% | FAIL |
| `src/v1/engine/components/transform/filter_rows.py` | 157 | 32 | 80% | FAIL |
| `src/v1/engine/components/transform/map.py` | 868 | 198 | 77% | FAIL |
| `src/v1/engine/components/transform/join.py` | 146 | 45 | 69% | FAIL |
| `src/v1/engine/components/transform/python_dataframe_component.py` | 46 | 37 | 20% | FAIL |
| `src/v1/engine/components/transform/swift_transformer.py` | 441 | 409 | 7% | FAIL |
| `src/v1/engine/components/transform/swift_block_formatter.py` | 410 | 382 | 7% | FAIL |

### engine.components.aggregate

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/components/aggregate/__init__.py` | 3 | 0 | 100% | PASS |
| `src/v1/engine/components/aggregate/unique_row.py` | 69 | 0 | 100% | PASS |
| `src/v1/engine/components/aggregate/aggregate_row.py` | 203 | 43 | 79% | FAIL |

### engine.components.control

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/components/control/__init__.py` | 5 | 0 | 100% | PASS |
| `src/v1/engine/components/control/sleep.py` | 31 | 0 | 100% | PASS |
| `src/v1/engine/components/control/warn.py` | 54 | 1 | 98% | PASS |
| `src/v1/engine/components/control/die.py` | 69 | 3 | 96% | PASS |
| `src/v1/engine/components/control/send_mail.py` | 123 | 49 | 60% | FAIL |

### engine.components.context

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/components/context/__init__.py` | 2 | 0 | 100% | PASS |
| `src/v1/engine/components/context/context_load.py` | 98 | 2 | 98% | PASS |

### engine.components.iterate

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/components/iterate/__init__.py` | 2 | 0 | 100% | PASS |
| `src/v1/engine/components/iterate/flow_to_iterate.py` | 64 | 2 | 97% | PASS |

### engine.components.database

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/components/database/__init__.py` | 4 | 0 | 100% | PASS |
| `src/v1/engine/components/database/oracle_connection.py` | 64 | 3 | 95% | PASS |
| `src/v1/engine/components/database/oracle_output.py` | 408 | 26 | 94% | FAIL |
| `src/v1/engine/components/database/oracle_row.py` | 134 | 13 | 90% | FAIL |

### engine (core modules)

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/v1/engine/__init__.py` | 3 | 0 | 100% | PASS |
| `src/v1/engine/components/__init__.py` | 6 | 0 | 100% | PASS |
| `src/v1/engine/component_registry.py` | 28 | 0 | 100% | PASS |
| `src/v1/engine/exceptions.py` | 25 | 0 | 100% | PASS |
| `src/v1/engine/context_manager.py` | 120 | 3 | 98% | PASS |
| `src/v1/engine/global_map.py` | 54 | 1 | 98% | PASS |
| `src/v1/engine/output_router.py` | 138 | 4 | 97% | PASS |
| `src/v1/engine/oracle_connection_manager.py` | 99 | 3 | 97% | PASS |
| `src/v1/engine/execution_plan.py` | 225 | 8 | 96% | PASS |
| `src/v1/engine/iterate_logging.py` | 23 | 1 | 96% | PASS |
| `src/v1/engine/trigger_manager.py` | 149 | 13 | 91% | FAIL |
| `src/v1/engine/executor.py` | 334 | 30 | 91% | FAIL |
| `src/v1/engine/base_iterate_component.py` | 93 | 11 | 88% | FAIL |
| `src/v1/engine/base_component.py` | 526 | 69 | 87% | FAIL |
| `src/v1/engine/python_routine_manager.py` | 98 | 18 | 82% | FAIL |
| `src/v1/engine/engine.py` | 175 | 33 | 81% | FAIL |
| `src/v1/engine/java_bridge_manager.py` | 101 | 41 | 59% | FAIL |

### converters.talend_to_v1 (core)

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/__init__.py` | 2 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/type_mapping.py` | 3 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/__init__.py` | 1 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/validator.py` | 128 | 3 | 98% | PASS |
| `src/converters/talend_to_v1/xml_parser.py` | 163 | 5 | 97% | PASS |
| `src/converters/talend_to_v1/trigger_mapper.py` | 37 | 1 | 97% | PASS |
| `src/converters/talend_to_v1/components/base.py` | 111 | 1 | 99% | PASS |
| `src/converters/talend_to_v1/components/registry.py` | 18 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/converter.py` | 214 | 13 | 94% | FAIL |
| `src/converters/talend_to_v1/expression_converter.py` | 90 | 20 | 78% | FAIL |

### converters.talend_to_v1.components.file

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/components/file/__init__.py` | 25 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_copy.py` | 36 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_delete.py` | 25 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_exist.py` | 18 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_fullrow.py` | 28 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_properties.py` | 22 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_raw.py` | 25 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_list.py` | 49 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_delimited.py` | 41 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_ebcdic.py` | 22 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_properties.py` | 20 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_row_count.py` | 21 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_touch.py` | 19 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_unarchive.py` | 30 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_excel.py` | 74 | 1 | 99% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_positional.py` | 70 | 1 | 99% | PASS |
| `src/converters/talend_to_v1/components/file/file_output_xml.py` | 185 | 6 | 97% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_delimited.py` | 94 | 3 | 97% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_positional.py` | 87 | 3 | 97% | PASS |
| `src/converters/talend_to_v1/components/file/set_global_var.py` | 47 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_json.py` | 62 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_msxml.py` | 53 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_xml.py` | 59 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/file/file_archive.py` | 54 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/file/fixed_flow_input.py` | 64 | 2 | 97% | PASS |
| `src/converters/talend_to_v1/components/file/file_input_excel.py` | 122 | 7 | 94% | FAIL |

### converters.talend_to_v1.components.transform

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/components/transform/__init__.py` | 35 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/change_file_encoding.py` | 23 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/filter_columns.py` | 19 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/hash_output.py` | 25 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/java_component.py` | 20 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/java_row_component.py` | 26 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/normalize.py` | 28 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/parse_record_set.py` | 34 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/python_component.py` | 21 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/python_dataframe_component.py` | 25 | 1 | 96% | PASS |
| `src/converters/talend_to_v1/components/transform/python_row_component.py` | 21 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/replicate.py` | 19 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/sample_row.py` | 19 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/split_row.py` | 42 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/transform/swift_transformer.py` | 19 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/unite.py` | 17 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/unpivot_row.py` | 28 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/sort_row.py` | 51 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/transform/log_row.py` | 54 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/transform/memorize_rows.py` | 39 | 1 | 97% | PASS |
| `src/converters/talend_to_v1/components/transform/map.py` | 126 | 4 | 97% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_delimited_fields.py` | 30 | 1 | 97% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_positional_fields.py` | 63 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_regex_fields.py` | 22 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_xml_fields.py` | 49 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/transform/schema_compliance_check.py` | 92 | 3 | 97% | PASS |
| `src/converters/talend_to_v1/components/transform/pivot_to_columns_delimited.py` | 58 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/transform/row_generator.py` | 50 | 2 | 96% | PASS |
| `src/converters/talend_to_v1/components/transform/extract_json_fields.py` | 80 | 3 | 96% | PASS |
| `src/converters/talend_to_v1/components/transform/denormalize.py` | 51 | 2 | 96% | PASS |
| `src/converters/talend_to_v1/components/transform/aggregate_sorted_row.py` | 82 | 3 | 96% | PASS |
| `src/converters/talend_to_v1/components/transform/convert_type.py` | 45 | 2 | 96% | PASS |
| `src/converters/talend_to_v1/components/transform/filter_rows.py` | 66 | 3 | 95% | PASS |
| `src/converters/talend_to_v1/components/transform/join.py` | 76 | 4 | 95% | PASS |
| `src/converters/talend_to_v1/components/transform/replace.py` | 95 | 6 | 94% | FAIL |
| `src/converters/talend_to_v1/components/transform/xml_map.py` | 214 | 15 | 93% | FAIL |

### converters.talend_to_v1.components.aggregate

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/components/aggregate/__init__.py` | 2 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/aggregate/unique_row.py` | 67 | 2 | 97% | PASS |
| `src/converters/talend_to_v1/components/aggregate/aggregate_row.py` | 116 | 11 | 91% | FAIL |

### converters.talend_to_v1.components.control

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/components/control/__init__.py` | 10 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/die.py` | 23 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/loop.py` | 25 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/parallelize.py` | 19 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/postjob.py` | 16 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/prejob.py` | 16 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/sleep.py` | 15 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/warn.py` | 21 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/control/run_job.py` | 80 | 3 | 96% | PASS |
| `src/converters/talend_to_v1/components/control/send_mail.py` | 103 | 4 | 96% | PASS |

### converters.talend_to_v1.components.context

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/components/context/__init__.py` | 1 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/context/context_load.py` | 29 | 0 | 100% | PASS |

### converters.talend_to_v1.components.iterate

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/components/iterate/__init__.py` | 1 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/iterate/flow_to_iterate.py` | 45 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/iterate/foreach.py` | 36 | 2 | 94% | FAIL |

### converters.talend_to_v1.components.database

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/talend_to_v1/components/database/__init__.py` | 11 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_close.py` | 17 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_commit.py` | 18 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_connection.py` | 43 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_output.py` | 41 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_rollback.py` | 18 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_bulk_exec.py` | 65 | 1 | 98% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_input.py` | 80 | 1 | 99% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_row.py` | 87 | 1 | 99% | PASS |
| `src/converters/talend_to_v1/components/database/oracle_sp.py` | 71 | 1 | 99% | PASS |
| `src/converters/talend_to_v1/components/database/mssql_connection.py` | 40 | 0 | 100% | PASS |
| `src/converters/talend_to_v1/components/database/mssql_input.py` | 63 | 12 | 81% | FAIL |

### converters.complex_converter (legacy -- not a Phase 14 target)

| Module | Stmts | Miss | Cover | Phase 14 Floor (95%) |
|--------|------:|-----:|------:|---------------------:|
| `src/converters/complex_converter/__init__.py` | 2 | 0 | 100% | N/A (legacy) |
| `src/converters/complex_converter/component_parser.py` | 1673 | 1593 | 5% | N/A (legacy) |
| `src/converters/complex_converter/converter.py` | 430 | 404 | 6% | N/A (legacy) |
| `src/converters/complex_converter/expression_converter.py` | 94 | 84 | 11% | N/A (legacy) |

Note: `complex_converter` is a superseded implementation (see ARCHITECTURE.md). Its low coverage is expected and NOT a Phase 14 lift target. Phase 14 enforces the 95% floor only for `talend_to_v1` and `v1/engine`.

---

## Summary Row

| Scope | Stmts | Miss | Cover |
|-------|------:|-----:|------:|
| TOTAL (both cov targets) | 19429 | 4881 | 75% |

---

## Notes for Phase 14

- Phase 14 uses these numbers as the FLOOR for the 95% per-module gate.
- **Modules at or above 95% (PASS):** must not regress below 95% in Phase 14.
- **Modules below 95% (FAIL):** are Phase 14 lift targets.
- The `htmlcov/` directory is gitignored (generated output); only this table is tracked.

### Phase 14 Lift Target Count Summary

| Subsystem | Total Modules | At/Above 95% | Below 95% |
|-----------|-------------:|-------------:|----------:|
| engine.components.file | 26 | 10 | 16 |
| engine.components.transform | 37 | 20 | 17 |
| engine.components.aggregate | 3 | 2 | 1 |
| engine.components.control | 5 | 4 | 1 |
| engine.components.context | 2 | 2 | 0 |
| engine.components.iterate | 2 | 2 | 0 |
| engine.components.database | 4 | 1 | 3 |
| engine (core) | 17 | 10 | 7 |
| converters.talend_to_v1 (core) | 10 | 8 | 2 |
| converters.talend_to_v1.components.file | 26 | 25 | 1 |
| converters.talend_to_v1.components.transform | 36 | 34 | 2 |
| converters.talend_to_v1.components.aggregate | 3 | 2 | 1 |
| converters.talend_to_v1.components.control | 10 | 10 | 0 |
| converters.talend_to_v1.components.context | 2 | 2 | 0 |
| converters.talend_to_v1.components.iterate | 3 | 2 | 1 |
| converters.talend_to_v1.components.database | 12 | 11 | 1 |
| **Totals (excl. complex_converter)** | **198** | **145** | **53** |

### Notable Low-Coverage Modules (below 50% -- Phase 14 high-priority)

| Module | Cover | Note |
|--------|------:|-------|
| `src/v1/engine/components/transform/swift_transformer.py` | 7% | SWIFT processing -- no tests exist yet |
| `src/v1/engine/components/transform/swift_block_formatter.py` | 7% | SWIFT block formatting -- no tests exist yet |
| `src/v1/engine/components/file/file_input_json.py` | 9% | JSON input -- minimal test coverage |
| `src/v1/engine/components/transform/python_dataframe_component.py` | 20% | DataFrame component -- integration-only paths untested |
| `src/v1/engine/components/file/file_input_excel.py` | 29% | Excel input -- complex format-branching paths untested |
| `src/v1/engine/components/file/file_input_raw.py` | 15% | Raw file input -- mostly untested |
| `src/v1/engine/components/control/send_mail.py` | 60% | Send mail -- SMTP live paths untested |
| `src/v1/engine/java_bridge_manager.py` | 59% | Bridge manager -- JVM lifecycle paths (skipped without JVM) |
| `src/converters/complex_converter/component_parser.py` | 5% | Legacy (N/A for Phase 14) |
| `src/converters/complex_converter/converter.py` | 6% | Legacy (N/A for Phase 14) |
