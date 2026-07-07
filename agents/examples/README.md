# Example ETL requirements document

`sample_etl_requirements.docx` is a ready-to-run test document for the
multi-agent ETL pipeline builder. It is authored in the exact format
`extract_doc` requires (see `agents/templates/etl_requirements_template.md`)
and passes the conformance gate at the `verified` tier.

## The scenario

A `transactions` feed is joined against a `counterparties` reference source to
add a human-readable name:

- **R1 (join)** add `counterparty_name` from `counterparties` on
  `counterparty_code` (LEFT join, so every transaction is kept).
- **R2 (sort)** order the result by `txn_id` ascending.

The sample data is built to exercise both the matched and the unmatched case:

- `T001`/`T002` match a counterparty -> `counterparty_name` filled in.
- `T003` uses `CP999` -> **no counterparty match** -> `counterparty_name` stays
  empty, but the row is still kept.

The `Expected Output` table (`result`) is the deterministic result of those
rules and is what the harness diffs the engine output against (the oracle).
`txn_id*` is marked as the composite key.

The document also carries a `Notes / Special Handling` Heading-1 block. Its prose
is captured verbatim into `notes` and folded into the rules by the
doc-interpreter -- here it records that unmatched rows are kept with an empty
name and that `counterparty_code` is case-sensitive.

## How to use it

Extract it standalone (no Copilot needed):

```bash
python -m agents.tools.extract_doc agents/examples/sample_etl_requirements.docx --out extracted.json
# exit 0 = conformant; extracted.json holds schema + rules + sample + expected + notes + tier + derived facts
```

Or invoke the `etl-orchestrator` agent in VS Code Copilot with this `.docx` and
a `<job>` name, and let it drive the pipeline end-to-end (extract -> materialize
-> interpret -> design -> configure -> assemble -> run -> diff -> human gate).

## Regenerating it

The `.docx` is generated deterministically by
`agents/examples/gen_sample_etl_requirements.py`:

```bash
python -m agents.examples.gen_sample_etl_requirements
```

Edit the tables in that generator (not the binary `.docx`) and re-run it. Note
the **`Expected Output` rows are the test oracle**, so they must equal the
correct result of your rules or the harness will (correctly) report a mismatch.
If you add a `schema_validate` cast (e.g. `amount` -> `decimal`), remember the
engine strips trailing zeros (`"10.50"` -> `"10.5"`), so the expected values
must reflect the cast output.
