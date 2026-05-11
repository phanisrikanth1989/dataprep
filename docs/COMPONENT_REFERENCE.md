# DataPrep Component Reference
*Last updated: 2026-05-11*

## Overview

This document is a registry-driven inline index of every engine component currently
wired into the live REGISTRY at `src/v1/engine/component_registry.py`. Registration
happens via the `@REGISTRY.register(...)` decorator on each component class
(see `src/v1/engine/engine.py:18` for the import + `engine.py:140` for the lookup
`REGISTRY.get(comp_type)`). For each registered component the table maps:

- V1 Name (PascalCase, primary registry key)
- Talend Alias(es) (tCamelCase, alternate registry keys)
- Source file under `src/v1/engine/components/`
- Test path under `tests/v1/engine/components/` (engine-side mirror tests)
- Per-component audit doc under `docs/v1/audit/components/` (full depth lives there)
- Notes -- empty for standard rows, fix-flag for Phase 14 BUG-PDC / BUG-FIJ /
  BUG-SWIFT registration repairs

Per Phase 15 decision D-B3 this doc does NOT duplicate audit content -- it points.
Per Phase 15 decision D-C6 the inventory is registry-driven; the per-row truth is
the live decorator chain rooted at `src/v1/engine/component_registry.py`.
`src/v1/engine/engine.py:19` triggers registration via
`from . import components as _components`, which imports every component module
and fires its `@REGISTRY.register(...)` decorator at import time.

## How To Read This Doc

| Column | Meaning |
|--------|---------|
| V1 Name | PascalCase key used in JSON job configs (`"type": "FilterRows"`) |
| Talend Alias | tCamelCase alias(es) for converter-emitted configs (`"type": "tFilterRows"`) |
| Source | Engine implementation file under `src/v1/engine/components/` |
| Tests | Engine-side mirror test under `tests/v1/engine/components/` |
| Audit | Per-component audit doc -- Phase 15.1 will reconcile against current code |
| Notes | `--` for standard rows; Phase 14 BUG flags called out where relevant |

Conventions:

- ASCII only. `--` not en-dash. No emoji, no smart quotes.
- If a cited path does not exist on disk, the row does not appear (D-E2:
  verify-before-claim). The doc reflects reality, not aspiration.
- If a per-component audit doc has not been authored yet, the Audit cell reads
  `not yet authored (Phase 15.1 backlog)`.

## Component Inventory

### Aggregate

| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| AggregateRow | tAggregateRow | src/v1/engine/components/aggregate/aggregate_row.py | tests/v1/engine/components/aggregate/test_aggregate_row.py | docs/v1/audit/components/aggregate/tAggregateRow.md | -- |
| UniqueRow | tUniqRow, tUniqueRow, tUnqRow | src/v1/engine/components/aggregate/unique_row.py | tests/v1/engine/components/aggregate/test_unique_row.py | docs/v1/audit/components/aggregate/tUniqueRow.md | -- |

### Context

| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| ContextLoad | tContextLoad | src/v1/engine/components/context/context_load.py | tests/v1/engine/components/context/test_context_load.py | docs/v1/audit/components/context/tContextLoad.md | -- |
| SetGlobalVar | tSetGlobalVar | src/v1/engine/components/file/set_global_var.py | tests/v1/engine/components/file/test_set_global_var.py | docs/v1/audit/components/file/tSetGlobalVar.md | Source file lives under `file/` (historical); logically a context-mutation component |

### Control

| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| Die | tDie | src/v1/engine/components/control/die.py | tests/v1/engine/components/control/test_die.py | docs/v1/audit/components/control/tDie.md | -- |
| Warn | tWarn | src/v1/engine/components/control/warn.py | tests/v1/engine/components/control/test_warn.py | docs/v1/audit/components/control/tWarn.md | -- |
| Sleep | SleepComponent, tSleep | src/v1/engine/components/control/sleep.py | tests/v1/engine/components/control/test_sleep.py | docs/v1/audit/components/control/tSleep.md | -- |

`SendMailComponent` lives at `src/v1/engine/components/control/send_mail.py` and
has a test mirror at `tests/v1/engine/components/control/test_send_mail.py` but
is NOT currently decorated with `@REGISTRY.register(...)`. JSON configs using
`tSendMail` will log `Unknown component type: tSendMail` at runtime until the
decorator is added. Tracked under COMP-V2-03 in the deferred list below.

### Database

| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| OracleConnection | tOracleConnection, tDBConnection | src/v1/engine/components/database/oracle_connection.py | tests/v1/engine/components/database/test_oracle_connection.py | docs/v1/audit/components/database/tOracleConnection.md | -- |
| OracleOutput | tOracleOutput | src/v1/engine/components/database/oracle_output.py | tests/v1/engine/components/database/test_oracle_output.py | docs/v1/audit/components/database/tOracleOutput.md | -- |
| OracleRow | tOracleRow | src/v1/engine/components/database/oracle_row.py | tests/v1/engine/components/database/test_oracle_row.py | docs/v1/audit/components/database/tOracleRow.md | -- |

Other Oracle/MSSQL audit docs exist under `docs/v1/audit/components/database/`
(`tOracleClose.md`, `tOracleCommit.md`, `tOracleInput.md`, `tOracleRollback.md`,
`tOracleSP.md`, `tOracleBulkExec.md`, `tMSSqlConnection.md`, `tMSSqlInput.md`)
but their engine implementations are not yet wired -- see COMP-V2-02 in
deferred list. Oracle integration / E2E tests live at
`tests/v1/engine/components/database/integration/`.

### File

| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| FileInputDelimited | tFileInputDelimited | src/v1/engine/components/file/file_input_delimited.py | tests/v1/engine/components/file/test_file_input_delimited.py | docs/v1/audit/components/file/tFileInputDelimited.md | -- |
| FileOutputDelimited | tFileOutputDelimited | src/v1/engine/components/file/file_output_delimited.py | tests/v1/engine/components/file/test_file_output_delimited.py | docs/v1/audit/components/file/tFileOutputDelimited.md | -- |
| FileInputPositional | tFileInputPositional | src/v1/engine/components/file/file_input_positional.py | tests/v1/engine/components/file/test_file_input_positional.py | docs/v1/audit/components/file/tFileInputPositional.md | -- |
| FileOutputPositional | tFileOutputPositional | src/v1/engine/components/file/file_output_positional.py | tests/v1/engine/components/file/test_file_output_positional.py | docs/v1/audit/components/file/tFileOutputPositional.md | -- |
| FileInputFullRowComponent | tFileInputFullRow | src/v1/engine/components/file/file_input_fullrow.py | tests/v1/engine/components/file/test_file_input_fullrow.py | docs/v1/audit/components/file/tFileInputFullRow.md | -- |
| FixedFlowInputComponent | tFixedFlowInput | src/v1/engine/components/file/fixed_flow_input.py | tests/v1/engine/components/file/test_fixed_flow_input.py | docs/v1/audit/components/file/tFixedFlowInput.md | -- |
| FileArchive | FileArchiveComponent, tFileArchive | src/v1/engine/components/file/file_archive.py | tests/v1/engine/components/file/test_file_archive.py | docs/v1/audit/components/file/tFileArchive.md | -- |
| FileUnarchive | FileUnarchiveComponent, tFileUnarchive | src/v1/engine/components/file/file_unarchive.py | tests/v1/engine/components/file/test_file_unarchive.py | docs/v1/audit/components/file/tFileUnarchive.md | -- |
| FileDelete | tFileDelete | src/v1/engine/components/file/file_delete.py | tests/v1/engine/components/file/test_file_delete.py | docs/v1/audit/components/file/tFileDelete.md | -- |
| FileCopy | tFileCopy | src/v1/engine/components/file/file_copy.py | tests/v1/engine/components/file/test_file_copy.py | docs/v1/audit/components/file/tFileCopy.md | -- |
| FileTouch | tFileTouch | src/v1/engine/components/file/file_touch.py | tests/v1/engine/components/file/test_file_touch.py | docs/v1/audit/components/file/tFileTouch.md | -- |
| FileExistComponent | FileExist, tFileExist | src/v1/engine/components/file/file_exist.py | tests/v1/engine/components/file/test_file_exist.py | docs/v1/audit/components/file/tFileExist.md | -- |
| FileRowCount | tFileRowCount | src/v1/engine/components/file/file_row_count.py | tests/v1/engine/components/file/test_file_row_count.py | docs/v1/audit/components/file/tFileRowCount.md | -- |
| FileProperties | tFileProperties | src/v1/engine/components/file/file_properties.py | tests/v1/engine/components/file/test_file_properties.py | docs/v1/audit/components/file/tFileProperties.md | -- |
| FileInputProperties | tFileInputProperties | src/v1/engine/components/file/file_input_properties.py | tests/v1/engine/components/file/test_file_input_properties.py | docs/v1/audit/components/file/tFileInputProperties.md | -- |
| FileInputRaw | tFileInputRaw | src/v1/engine/components/file/file_input_raw.py | tests/v1/engine/components/file/test_file_input_raw.py | docs/v1/audit/components/file/tFileInputRaw.md | -- |
| FileInputXML | tFileInputXML | src/v1/engine/components/file/file_input_xml.py | tests/v1/engine/components/file/test_file_input_xml.py | docs/v1/audit/components/file/tFileInputXML.md | -- |
| FileInputMSXML | tFileInputMSXML | src/v1/engine/components/file/file_input_msxml.py | tests/v1/engine/components/file/test_file_input_msxml.py | docs/v1/audit/components/file/tFileInputMSXML.md | -- |
| FileInputExcel | tFileInputExcel | src/v1/engine/components/file/file_input_excel.py | tests/v1/engine/components/file/test_file_input_excel.py | docs/v1/audit/components/file/tFileInputExcel.md | -- |
| FileOutputExcel | tFileOutputExcel | src/v1/engine/components/file/file_output_excel.py | tests/v1/engine/components/file/test_file_output_excel.py | docs/v1/audit/components/file/tFileOutputExcel.md | -- |
| FileInputJSON | tFileInputJSON | src/v1/engine/components/file/file_input_json.py | tests/v1/engine/components/file/test_file_input_json.py | docs/v1/audit/components/file/tFileInputJSON.md | Registered (Phase 14 BUG-FIJ-001/002 fix) -- missing registry key + `_validate_config` repaired |
| FileList | tFileList | src/v1/engine/components/file/file_list.py | tests/v1/engine/components/file/test_file_list.py | docs/v1/audit/components/file/tFileList.md | Iterate-producing component; lives under `file/` (historical) |
| FileOutputXML | tFileOutputXML | src/v1/engine/components/file/file_output_xml.py | tests/v1/engine/components/file/test_file_output_xml.py | not yet authored (Phase 15.1 backlog) | Phase 12 new output |
| AdvancedFileOutputXML | tAdvancedFileOutputXML | src/v1/engine/components/file/file_output_advanced_xml.py | tests/v1/engine/components/file/test_file_output_advanced_xml.py | docs/v1/audit/components/file/tAdvancedFileOutputXML.md | Phase 12 new output |
| SetGlobalVar | tSetGlobalVar | src/v1/engine/components/file/set_global_var.py | tests/v1/engine/components/file/test_set_global_var.py | docs/v1/audit/components/file/tSetGlobalVar.md | Cross-listed under Context above; physical source under `file/` |

### Iterate

| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| FlowToIterate | tFlowToIterate | src/v1/engine/components/iterate/flow_to_iterate.py | tests/v1/engine/components/iterate/test_flow_to_iterate.py | docs/v1/audit/components/iterate/tFlowToIterate.md | -- |

`tForeach` has an audit doc at `docs/v1/audit/components/iterate/tForeach.md` but
no engine implementation yet -- tracked under COMP-V2-07 below.

### Transform

| V1 Name | Talend Alias | Source | Tests | Audit | Notes |
|---------|--------------|--------|-------|-------|-------|
| Map | tMap | src/v1/engine/components/transform/map.py | tests/v1/engine/components/transform/test_map.py | docs/v1/audit/components/transform/tMap.md | -- |
| XMLMap | tXMLMap | src/v1/engine/components/transform/xml_map.py | tests/v1/engine/components/transform/test_xml_map.py | docs/v1/audit/components/transform/tXMLMap.md | -- |
| FilterRows | FilterRow, tFilterRow, tFilterRows | src/v1/engine/components/transform/filter_rows.py | tests/v1/engine/components/transform/test_filter_rows.py | docs/v1/audit/components/transform/tFilterRow.md | -- |
| FilterColumns | tFilterColumns | src/v1/engine/components/transform/filter_columns.py | tests/v1/engine/components/transform/test_filter_columns.py | docs/v1/audit/components/transform/tFilterColumns.md | -- |
| SortRow | tSortRow | src/v1/engine/components/transform/sort_row.py | tests/v1/engine/components/transform/test_sort_row.py | docs/v1/audit/components/transform/tSortRow.md | -- |
| RowGenerator | tRowGenerator | src/v1/engine/components/transform/row_generator.py | tests/v1/engine/components/transform/test_row_generator.py | docs/v1/audit/components/transform/tRowGenerator.md | -- |
| AggregateSortedRow | tAggregateSortedRow | src/v1/engine/components/transform/aggregate_sorted_row.py | tests/v1/engine/components/transform/test_aggregate_sorted_row.py | docs/v1/audit/components/transform/tAggregateSortedRow.md | Logically aggregate; physically under transform/ |
| Denormalize | tDenormalize | src/v1/engine/components/transform/denormalize.py | tests/v1/engine/components/transform/test_denormalize.py | docs/v1/audit/components/transform/tDenormalize.md | -- |
| Normalize | tNormalize | src/v1/engine/components/transform/normalize.py | tests/v1/engine/components/transform/test_normalize.py | docs/v1/audit/components/transform/tNormalize.md | -- |
| Replicate | tReplicate | src/v1/engine/components/transform/replicate.py | tests/v1/engine/components/transform/test_replicate.py | docs/v1/audit/components/transform/tReplicate.md | -- |
| ExtractDelimitedFields | tExtractDelimitedFields | src/v1/engine/components/transform/extract_delimited_fields.py | tests/v1/engine/components/transform/test_extract_delimited_fields.py | docs/v1/audit/components/transform/tExtractDelimitedFields.md | -- |
| ExtractJSONFields | tExtractJSONFields | src/v1/engine/components/transform/extract_json_fields.py | tests/v1/engine/components/transform/test_extract_json_fields.py | docs/v1/audit/components/transform/tExtractJSONFields.md | -- |
| ExtractPositionalFields | tExtractPositionalFields | src/v1/engine/components/transform/extract_positional_fields.py | tests/v1/engine/components/transform/test_extract_positional_fields.py | docs/v1/audit/components/transform/tExtractPositionalFields.md | -- |
| ExtractRegexFields | tExtractRegexFields | src/v1/engine/components/transform/extract_regex_fields.py | tests/v1/engine/components/transform/test_extract_regex_fields.py | docs/v1/audit/components/transform/tExtractRegexFields.md | -- |
| ExtractXMLField | tExtractXMLField | src/v1/engine/components/transform/extract_xml_fields.py | tests/v1/engine/components/transform/test_extract_xml_fields.py | docs/v1/audit/components/transform/tExtractXMLField.md | -- |
| ConvertType | tConvertType | src/v1/engine/components/transform/convert_type.py | tests/v1/engine/components/transform/test_convert_type.py | docs/v1/audit/components/transform/tConvertType.md | -- |
| ChangeFileEncoding | tChangeFileEncoding | src/v1/engine/components/transform/change_file_encoding.py | tests/v1/engine/components/transform/test_change_file_encoding.py | docs/v1/audit/components/transform/tChangeFileEncoding.md | -- |
| ParseRecordSet | tParseRecordSet | src/v1/engine/components/transform/parse_record_set.py | tests/v1/engine/components/transform/test_parse_record_set.py | docs/v1/audit/components/transform/tParseRecordSet.md | -- |
| MemorizeRows | tMemorizeRows | src/v1/engine/components/transform/memorize_rows.py | tests/v1/engine/components/transform/test_memorize_rows.py | docs/v1/audit/components/transform/tMemorizeRows.md | -- |
| SampleRow | tSampleRow | src/v1/engine/components/transform/sample_row.py | tests/v1/engine/components/transform/test_sample_row.py | docs/v1/audit/components/transform/tSampleRow.md | -- |
| SplitRow | tSplitRow | src/v1/engine/components/transform/split_row.py | tests/v1/engine/components/transform/test_split_row.py | docs/v1/audit/components/transform/tSplitRow.md | -- |
| Replace | tReplace | src/v1/engine/components/transform/replace.py | tests/v1/engine/components/transform/test_replace.py | docs/v1/audit/components/transform/tReplace.md | -- |
| JavaRowComponent | tJavaRow | src/v1/engine/components/transform/java_row_component.py | tests/v1/engine/components/transform/test_java_row_component.py | docs/v1/audit/components/transform/tJavaRow.md | -- |
| JavaComponent | tJava | src/v1/engine/components/transform/java_component.py | tests/v1/engine/components/transform/test_java_component.py | docs/v1/audit/components/transform/tJava.md | -- |
| PythonRowComponent | tPythonRow | src/v1/engine/components/transform/python_row_component.py | tests/v1/engine/components/transform/test_python_row_component.py | docs/v1/audit/components/transform/PythonRowComponent.md | -- |
| PythonDataFrameComponent | tPythonDataFrame | src/v1/engine/components/transform/python_dataframe_component.py | tests/v1/engine/components/transform/test_python_dataframe_component.py | docs/v1/audit/components/transform/PythonDataFrameComponent.md | Registered (Phase 14 BUG-PDC-001/002 fix) -- missing registry key + `_validate_config` repaired |
| PythonComponent | tPython, tPythonComponent | src/v1/engine/components/transform/python_component.py | tests/v1/engine/components/transform/test_python_component.py | docs/v1/audit/components/transform/PythonComponent.md | -- |
| LogRow | tLogRow | src/v1/engine/components/transform/log_row.py | tests/v1/engine/components/transform/test_log_row.py | docs/v1/audit/components/transform/tLogRow.md | -- |
| SwiftBlockFormatter | tSwiftBlockFormatter | src/v1/engine/components/transform/swift_block_formatter.py | tests/v1/engine/components/transform/test_swift_block_formatter.py | docs/v1/audit/components/transform/SwiftBlockFormatter.md | Registered (Phase 14 BUG-SWIFT-001..005 fix) -- registry + `_validate_config` + 3 behavior bugs repaired |
| SwiftTransformer | tSwiftDataTransformer | src/v1/engine/components/transform/swift_transformer.py | tests/v1/engine/components/transform/test_swift_transformer.py | docs/v1/audit/components/transform/SwiftTransformer.md | Registered (Phase 14 BUG-SWIFT-001..005 fix) -- registry + `_validate_config` + 3 behavior bugs repaired |
| Join | tJoin | src/v1/engine/components/transform/join.py | tests/v1/engine/components/transform/test_join.py | docs/v1/audit/components/transform/tJoin.md | -- |
| PivotToColumnsDelimited | tPivotToColumnsDelimited | src/v1/engine/components/transform/pivot_to_columns_delimited.py | tests/v1/engine/components/transform/test_pivot_to_columns_delimited.py | docs/v1/audit/components/transform/tPivotToColumnsDelimited.md | -- |
| SchemaComplianceCheck | tSchemaComplianceCheck | src/v1/engine/components/transform/schema_compliance_check.py | tests/v1/engine/components/transform/test_schema_compliance_check.py | docs/v1/audit/components/transform/tSchemaComplianceCheck.md | -- |
| Unite | tUnite | src/v1/engine/components/transform/unite.py | tests/v1/engine/components/transform/test_unite.py | docs/v1/audit/components/transform/tUnite.md | -- |
| UnpivotRow | tUnpivotRow | src/v1/engine/components/transform/unpivot_row.py | tests/v1/engine/components/transform/test_unpivot_row.py | docs/v1/audit/components/transform/tUnpivotRow.md | -- |

## Out-of-Scope Components

The following are intentionally NOT in the live REGISTRY today.
Source of truth: `.planning/REQUIREMENTS.md` lines 245-251.

- **COMP-V2-01** -- the long tail of ~74 engine components needing production-quality hardening
- **COMP-V2-02** -- additional MSSQL / Oracle components (`tMSSqlConnection`, `tMSSqlInput`, `tOracleClose`, `tOracleCommit`, `tOracleInput`, `tOracleRollback`, `tOracleSP`, `tOracleBulkExec`) -- audit docs exist under `docs/v1/audit/components/database/`, engine wiring deferred
- **COMP-V2-03** -- additional control components (`tSendMail` source present but undecorated, `tLoop`, `tParallelize`, `tRunJob`, `tPrejob`, `tPostjob`)
- **COMP-V2-04** -- remaining file components beyond the inventory above (e.g. `tFileOutputEBCDIC` -- audit at `docs/v1/audit/components/file/tFileOutputEBCDIC.md`)
- **COMP-V2-05** -- remaining transform components without engine implementations (e.g. `tHashOutput` -- audit at `docs/v1/audit/components/transform/tHashOutput.md`)
- **COMP-V2-06** -- Python / Swift component hardening (Phase 14 closed the registration + `_validate_config` portion; remaining V2 line covers feature-parity work)
- **COMP-V2-07** -- additional iterate / aggregate components (`tForeach` audit exists; engine impl deferred)

## How To Regenerate This Reference

**Option A (Phase 15 -- current).** Manual maintenance at component-add time.
The contributor adds the component class, decorates it with
`@REGISTRY.register("PascalName", "tTalendName")`, implements `_validate_config()`
on the new subclass (Phase 14 systemic discipline), wires the import into the
appropriate sub-package `__init__.py`, and adds a row to the appropriate H3 table
above. Contributing rules live in `docs/CONTRIBUTING.md` Rule 5 (registry +
abstract-method discipline).

**Option B (deferred follow-up).** A small helper at
`scripts/gen_component_reference.py` could walk
`REGISTRY.list_types()` (or the underlying `_components` map) and emit this
table directly. The generator is implementable in ~50-100 lines of stdlib and
is captured in `.planning/phases/15-documentation-sweep/15-CONTEXT.md` Deferred
Ideas. It is NOT in Phase 15 scope per planner D.3 resolution. A future
quick-task or Phase 15.1 follow-up may ship it.

Phase 15 deliberately ships inline tables -- per D-B2 the phase forbids
documentation tooling, and an inline table is the minimum-footprint choice.
If the registry shape stabilises and table maintenance gets noisy, file a
quick-task to add the generator.

## See Also

- `docs/ARCHITECTURE.md` -- system overview (engine + converter + Java bridge layout)
- `docs/CONTRIBUTING.md` -- authoring conventions, registry + abstract-method discipline (Phase 14 Rule 5), ASCII-only, atomic commits
- `docs/v1/audit/components/` -- per-component audit depth; Phase 15.1 reconciles each audit doc against current code
- `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` -- BaseComponent lifecycle and `_process()` contract
- `docs/v1/patterns/ENGINE_TEST_PATTERN.md` -- `run_job_fixture`, `assert_ascii_logs`, pipeline-fixture authoring
- `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` -- end-to-end walkthrough for adding a new component
- `.planning/REQUIREMENTS.md` -- COMP-V2-* deferred component list (source for `Out-of-Scope Components` above)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` -- Phase 14 BUG-PDC / BUG-FIJ / BUG-SWIFT fix commits and the systemic registry+abstract-method discipline that emerged from them
