# Golden Phase-A recon job

A synthesized, code-verified Phase-A reconciliation job: two delimited sources
joined on an exact key, partitioned into a **matched** file and a one-sided
**break/reject** file. Used by `tests/agents/tools/test_golden_phase_a_e2e.py`
to prove the parity harness (`agents/tools/run_and_validate.py`) PASSES on a
correct engine run and FAILS on a mutated expectation.

## Topology

```
in_main (main.csv)   --row1-->  tmap (INNER_JOIN on cc)  --matched-->  out_matched (matched.csv)
in_lookup (lookup.csv) --row2-->                          --reject-->   out_reject  (reject.csv)
```

- `in_main` / `in_lookup`: `FileInputDelimited`, `;`-separated, one header row.
- `tmap`: `Map` (tMap). Main input `row1`, lookup `row2`, INNER_JOIN on `cc`
  (`UNIQUE_MATCH`). Two outputs:
  - `matched` (`is_reject=false`, `inner_join_reject=false`): columns `cc, amt, name`.
  - `reject` (`inner_join_reject=true`): columns `cc, amt` -- the main rows with
    no lookup match (the one-sided break).
- `out_matched` / `out_reject`: `FileOutputDelimited`, `;`-separated,
  `include_header=true`, `file_exist_exception=false`.

All expression evaluation runs through the **real Java bridge**
(`java_config.enabled=true`), so the e2e test is marked `@pytest.mark.java`.

## Data

`main.csv` (`cc;amt`): `US;10`, `UK;20`, `FR;30`, `DE;40`.
`lookup.csv` (`cc;name`): `US;United States`, `UK;United Kingdom`.

So `US` and `UK` match; `FR` and `DE` are one-sided breaks. Main and lookup share
**only** the key column `cc` (non-key columns `amt` vs `name` never collide).

## Break mechanism (design note)

The one-sided break output uses `inner_join_reject=true` -- the tMap "catch
lookup inner-join reject" flag, cribbed from
`tests/fixtures/jobs/transform/05_4/inner_reject.json`. That is the mechanism
that routes unmatched main rows (`FR`, `DE`) to the reject output under
`INNER_JOIN`. (`is_reject=true` is a different tMap feature -- it catches rows
dropped by a main output's own filter/type-conversion, not join misses -- and
would leave the reject output empty here.)

## Determinism

No dates, no random, no clock-dependent expressions. Column `amt` is declared
`str` so there is no int/float serialization ambiguity. Output is compared
key-wise on `cc` (see `manifest.json`), so row order is irrelevant.

## Provenance of `*_expected.csv`

`matched_expected.csv` and `reject_expected.csv` were **engine-captured** (run
once through `run_job_capture` over the live bridge, then frozen byte-for-byte
from the produced files) and **cross-verified** against the independent
`agents.tools.reference_matcher.match_phase_a(main, lookup, keys=["cc"])`
oracle-of-oracle on commit `eb8bcde`:

- engine matched `cc` = reference matched `cc` = `{US, UK}`
- engine reject `cc`  = reference break  `cc` = `{FR, DE}`
- reference stats: `n_matched=2, n_break_no_match=2, n_break_multi=0`

Engine output and reference matcher agree with **zero** disagreement. To
regenerate after an intentional change, re-run the capture, confirm the
reference matcher still agrees, and re-freeze.
