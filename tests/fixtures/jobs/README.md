# Pipeline-Test Fixture Jobs

This directory holds JSON job-config fixtures consumed by Phase 14 pipeline tests
through the `run_job_fixture` helper in `tests/conftest.py`. Each fixture is a
small (1-3 component) JSON job that mirrors the converter output shape and is
loaded, optionally mutated, and executed via `ETLEngine.execute()` in unit tests.

## JSON Shape

Fixtures mirror the `talend_to_v1` converter output:

```json
{
  "job": { "name": "<fixture_name>", "version": "0.1" },
  "components": [
    {
      "id": "tFileInputDelimited_1",
      "type": "FileInputDelimited",
      "config": {
        "filepath": "TBD_via_mutations",
        "field_separator": ";",
        "header": 0,
        "schema": [
          {"name": "id", "type": "string"},
          {"name": "name", "type": "string"}
        ]
      }
    }
  ],
  "flows": [],
  "triggers": [],
  "subjobs": [],
  "context": {}
}
```

The required top-level keys are `job`, `components`, `flows`, `triggers`,
`subjobs`, `context`. Most simple fixtures will have empty `flows` / `triggers` /
`subjobs` lists -- pipeline tests for multi-component jobs populate these per the
Phase 13 / Phase 14 converter output schema.

## Naming Convention

```
tests/fixtures/jobs/<subsystem>/<behavior>.json
```

- `<subsystem>`: lowercase snake_case directory matching the lift subsystem --
  `file`, `transform`, `core`, `swift` (more may be added by later plans).
- `<behavior>`: lowercase snake_case slug describing the scenario the fixture
  exercises -- e.g. `csv_with_header`, `tab_delimited_no_header`,
  `mt103_basic_block4`.

Examples:

```
tests/fixtures/jobs/file/csv_with_header.json
tests/fixtures/jobs/file/excel_multi_sheet.json
tests/fixtures/jobs/transform/tmap_inner_join.json
tests/fixtures/jobs/swift/mt103_basic.json
tests/fixtures/jobs/core/run_with_oracle_disabled.json
```

## How Pipeline Tests Use Fixtures

Tests call the `run_job_fixture` callable from the root `tests/conftest.py` and
pass a `mutations` dict to inject runtime paths and per-test overrides into the
fixture without dirtying the on-disk JSON. The fixture file is copied to the
test's `tmp_path`, mutations are applied to the copy, and `ETLEngine` runs the
mutated copy. The original JSON in `tests/fixtures/jobs/` is never modified.

```python
def test_csv_with_header_reads_three_rows(run_job_fixture, tmp_path):
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("id;name\n1;Alice\n2;Bob\n3;Carol\n", encoding="utf-8")
    out_path = tmp_path / "output.csv"

    result = run_job_fixture(
        "file/csv_with_header",
        mutations={
            "tFileInputDelimited_1": {"filepath": str(csv_path)},
            "tFileOutputDelimited_1": {"filepath": str(out_path)},
        },
    )

    assert result.global_map["tFileInputDelimited_1_NB_LINE"] == 3
```

## Fixture Authoring Guidelines

1. **Keep fixtures small.** 1-3 components is the target. Larger fixtures hide
   intent and slow tests.
2. **Use placeholder paths.** Any filesystem path that the test must control
   (`filepath`, `directory`, etc.) should be set to the literal sentinel
   `"TBD_via_mutations"` in the JSON. Tests inject the real path via
   `mutations`.
3. **No production data.** Fixtures must be synthetic. SWIFT fixtures use the
   synthetic generator under `tests/fixtures/swift/` (Plan 14-08).
4. **ASCII-only.** No emojis, no smart quotes, no unicode field values unless
   the test exists specifically to exercise non-ASCII handling -- in which case
   declare the encoding explicitly in `config`.
5. **Realistic dtypes.** Schemas should mix `string`, `integer`, `decimal`,
   `date` types where the test exercises pandas 3.0 / CoW behavior (Phase 14
   D-C4).

## Regenerating From a Real .item

If you have a Talend `.item` job that already exercises the behavior you need,
generate a starter JSON via the converter and trim it down:

```bash
python -m src.converters.talend_to_v1.converter \
    tests/talend_xml_samples/Job_<name>.item \
    tests/fixtures/jobs/<subsystem>/<behavior>.json
```

Then manually:

- Strip components unrelated to the behavior under test.
- Replace concrete paths with `"TBD_via_mutations"` placeholders.
- Trim schema columns to the minimum the test needs.
- Verify the fixture loads and runs through `ETLEngine` before committing.

## Subsystem Coverage

| Directory | Plans That Use It |
|-----------|-------------------|
| `file/` | Plan 14-09 (file quick wins / medium gaps), Plan 14-10 (Excel / JSON / raw deep gaps) |
| `transform/` | Plan 14-06, Plan 14-07 (tMap, join, python_dataframe_component) |
| `core/` | Plan 14-11 (engine core: executor, base_component, base_iterate_component, trigger_manager, engine.py, java_bridge_manager) |
| `swift/` | Plan 14-08 (swift_transformer, swift_block_formatter -- consumes the synthetic MT generator) |

Future plans may add subsystem directories (e.g. `database/`, `aggregate/`)
following the same conventions.
