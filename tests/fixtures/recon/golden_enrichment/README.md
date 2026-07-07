# Golden enrichment job

A synthesized, engine-captured **enrichment** job: a driving source is joined
to a reference lookup on an exact key, ALL source rows are kept, and the lookup
columns are ADDED to each source row (unmatched rows get null lookup columns --
no reject/break output). Used by
`tests/agents/tools/test_golden_enrichment_e2e.py` to prove the parity harness
(`agents/tools/run_and_validate.py`) PASSES on a correct engine run and FAILS on
a mutated expectation.

## Topology

```
in_source (source.csv) --row1--> tmap (LEFT_OUTER_JOIN on cc) --enriched--> conv (ConvertType) --> sort (SortRow) --> out_enriched (enriched.csv)
in_lookup (lookup.csv) --row2-->
```

- `in_source` / `in_lookup`: `FileInputDelimited`, `;`-separated, one header row.
- `tmap`: `Map` (tMap). Main input `row1`, lookup `row2`, **LEFT_OUTER_JOIN** on
  `cc`. ONE output `enriched` (`is_reject=false`, `inner_join_reject=false`):
  columns `cc, amt` from the source plus `name` from the lookup. Because the join
  is LEFT_OUTER, every source row survives; a source row with no lookup match
  carries a null `name`. There is NO reject output.
- `conv`: `ConvertType`. MANUALTABLE entry `amt -> amt` with no explicit numeric
  target type, which triggers tConvertType's default numeric conversion
  (`pd.to_numeric`): the string `amt` is cast to numeric, so `"10.50"` is emitted
  as the normalized `"10.5"`.
- `sort`: `SortRow`. Sorts by `cc` ascending (alpha), so the output order is
  independent of the input order.
- `out_enriched`: `FileOutputDelimited`, `;`-separated, `include_header=true`,
  `file_exist_exception=false`.

All expression evaluation runs through the **real Java bridge**
(`java_config.enabled=true`), so the e2e test is marked `@pytest.mark.java`.

## Data

`source.csv` (`cc;amt`): `US;10.50`, `UK;20.50`, `FR;30.00`, `DE;40.00`.
`lookup.csv` (`cc;name`): `US;United States`, `UK;United Kingdom`.

So `US` and `UK` are enriched with a `name`; `FR` and `DE` have no lookup match
and keep a null (empty) `name` -- but they are STILL PRESENT in the output (this
is enrichment, not reconciliation: no row is dropped or routed to a break).

## Determinism

No dates, no random, no clock-dependent expressions. The only numeric conversion
is `amt` (string -> numeric via ConvertType), whose values are exactly
representable. Output is compared key-wise on `cc` (see `manifest.json`), so row
order is irrelevant to the harness; `sort` still makes the file itself
deterministic.

## Provenance of `enriched_expected.csv`

`enriched_expected.csv` was **engine-captured** -- run once through
`run_job_capture` over the live Java bridge, then frozen byte-for-byte from the
produced file. It is NOT hand-authored. Eyeball-verified: all four source rows
present; `US`/`UK` enriched with their `name`, `FR`/`DE` with an empty `name`;
`amt` cast to normalized numeric text (`"10.50"` -> `"10.5"`); rows sorted by
`cc` ascending (`DE, FR, UK, US`). To regenerate after an intentional change,
re-run the capture and re-freeze.
