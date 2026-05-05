# Phase 10 Deferred Items

## Pre-existing Test Failures (Out of Scope for Phase 10-01)

The following test failures were observed during Phase 10-01 execution and confirmed
as pre-existing (present before any Phase 10-01 code changes).

| Test | File | Status | Notes |
|------|------|--------|-------|
| TestStatistics::test_stats_set_after_write | tests/v1/engine/components/file/test_file_output_excel.py | Pre-existing | Excel component bug |
| TestManualTable::test_string_to_int_cast | tests/v1/engine/components/transform/test_convert_type.py | Pre-existing | ConvertType bug |
| TestFullPipeline::test_read_join_write_pipeline | tests/v1/engine/test_full_pipeline.py | Pre-existing | Integration test issue |
| TestFullPipeline::test_inner_join_with_reject | tests/v1/engine/test_full_pipeline.py | Pre-existing | Integration test issue |
| TestCaseSensitivity::test_case_insensitive_dict_deduplicates | tests/v1/engine/components/aggregate/test_unique_row.py | Pre-existing | UniqueRow case-sensitivity bug |
| Multiple TestCellPositioning / TestAutoSize etc. | tests/v1/engine/components/file/test_file_output_excel.py | Pre-existing | Excel component tests (17 total) |

All confirmed by running tests on the f5f22ca baseline commit before any Phase 10-01 changes.
