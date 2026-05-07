# Phase 11 Deferred Items

## Pre-existing engine test failures (out of scope for plan 11-01)

Discovered during plan 11-01 regression check. NOT caused by Oracle work
(verified by stashing 11-01 changes and re-running the same suite).

27 pre-existing failures in `pytest tests/v1/engine/ --ignore=tests/v1/engine/components/database --ignore=tests/v1/engine/test_oracle_connection_manager.py`:

- tests/v1/engine/components/aggregate/test_unique_row.py::TestCaseSensitivity::test_case_insensitive_dict_deduplicates
- tests/v1/engine/components/file/test_file_output_excel.py (8 failures, openpyxl-related)
- tests/v1/engine/components/transform/test_convert_type.py::TestManualTable::test_string_to_int_cast
- tests/v1/engine/components/transform/test_java_component.py (2 failures, java bridge)
- tests/v1/engine/test_bridge_integration.py (2 failures, java bridge)
- tests/v1/engine/test_code_components_engine_smoke.py (1 failure, java bridge)
- (~13 other unrelated failures in same suite)

These are out of scope per `SCOPE BOUNDARY` in the deviation rules. Each is
unrelated to Oracle work and existed at the base commit
`4552719 docs(11): widen Oracle identifier regex...`.

Plan 11-01 added 43 new Oracle-manager tests; all 43 pass.
