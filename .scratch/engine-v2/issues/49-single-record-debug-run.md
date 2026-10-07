# 49 - Single-record debug run

Status: claimed
Type: grilling
Blocked by: 50

## Question

For one record, or a few, show what every component of the job did with
it: what came out of each component, by which output, and where the record
stopped. What exactly is shown, for which components, in what form, and
does such a run read the whole input or the record alone?

## What the dev asked (2026-10-07)

"Single-record debug run: be able to run for a single record (or a small
set) with prints or debug enabled, so the output at each component level is
clear for that record."

Ticketed only. To be grilled with the dev before anything is built.
Blocked by ticket 50, which decides how a record is picked and what a run
for one record is; the two are best grilled together.

## What is there today

- `--log-level DEBUG` says how the job is built, not what a record looks
  like: each component's config, the columns of its outputs, the plans
  Polars is given. 659 lines for the payments scenario, none of them a
  row's values.
- A log row component in the job prints the first rows of the flow it sits
  on. It has to be put into the job, and it prints the first rows, not a
  chosen one.
- A row's number travels with the row, unseen, through every component
  that keeps its rows, and is the main input's after a join. After an
  aggregate it is the lowest number of the group; after user Python it is
  gone (the table in `docs/v2/README.md`, "Finding the row that failed").
- The engine can already hold a flow's rows in hand between two
  components: it does so before a component that needs rows (user Python,
  a context load).
- What a component turns away has a reason in some cases: a reader's and
  the schema check's rejects have `errorCode` and `errorMessage`, a filter
  names the filter the row failed, a join says "No matching lookup row"
  where its reject schema asks for a reason. A unique row gives no reason
  for a repeat.
- Talend's own tool for this is Traces Debug: the values of the row on
  every flow, row by row.

## A first shape, to react to

A sketch typed by hand; the values are invented and nothing produces this
today.

```
record txn_id=654321, line 654322 of /data/payments.csv

payments_in     file input       main: 1 row
    txn_id=654321  txn_ref=TX000000654321  amount=960081.20  currency=USD  branch_code=BR04321  (45 columns)
format_check    filter rows      main: 1 row     reject: none
no_repeats      unique row       main: 1 row     duplicates: none
branch_join     join             main: 1 row     reject: none
    added: region=EMEA
prepare         map              prepared: 1 row
    invoice_ref=INV-88213        re.search(r'INV-\d+', joined.narrative).group(0)
    amount_usd=960081.2000       round(joined.amount * joined.fx_rate, 4)
enrich          map              enriched: 1 row     high_value: 1 row     cross_border: none
    customer_name=ACME LTD       cust.customer_name      (customers.csv line 4322)
totals          aggregate row    main: 1 row     a group of this 1 row alone
enriched_out    file output      would write 1 row to /data/out/enriched.csv
high_value_out  file output      would write 1 row to /data/out/high_value.csv
cross_border_out file output     would write no row
```

And for a record that fails or is turned away, the same down to where it
stops:

```
format_check    filter rows      main: none      reject: 1 row
    errorMessage=debit_account MATCHES [A-Z]{2}[0-9]{2}[A-Z0-9]{12,30}
    the record goes no further on the main flow
```

## To settle in the grilling

1. **The whole input or the record alone.** Read only the picked record
   from its source: quick, and every row in the job then comes from that
   record, so nothing has to be followed. But a unique row, an aggregate
   and a count see one row. Or read everything and show only that record's
   rows: the true result at every step, at the price of a full run and
   more, and the record cannot be followed past an aggregate or user
   Python.
2. **What is shown at a component.** Every column each time (45 for a
   payment), or the whole row once at the source and after that only what
   a component added or changed.
3. **Maps.** Whether each output column is shown with its expression, and
   a lookup's match with the lookup row it came from (its file line or
   key). A lookup row's number is dropped at the join today.
4. **Where the record stops.** A reject output with its reason, a filter it
   did not pass, a repeat a unique row dropped, a lookup that found
   nothing, a failure: shown with as much reason as the component has.
5. **Does it write the job's files.** Ticket 50 decides this for a run of
   one record; a debug run would most likely write nothing.
6. **In what form, and where.** Text for a person on standard output, a
   JSON document for a tool, or both; and whether it is a flag
   (`--trace`), a setting in the job's JSON (ticket 47), or a level of the
   log.
7. **How many records.** One is clear, twenty are still readable, a
   thousand are not. Where the limit is and what happens at it.
8. **What a record's values may be shown to.** A printed record holds
   account numbers and names. Where such a run will be used (a developer's
   machine, production support) decides whether that is acceptable as it
   is.
9. **User Python.** The record goes in as a table of one row and what
   comes back is shown; whether anything of the code's own doing can be
   shown besides.
10. **The existing DEBUG lines.** Whether a debug run also prints the
    configs and plans, or only the record.

## Where I lean, to be argued with

- **Read the record alone.** It needs one read of the file to find the
  record (0.09 s for a million rows, measured for ticket 38; larger files
  not measured), it works past an aggregate and past user Python (every row
  in the run comes from the record, so nothing has to be followed), and the
  engine can already hold a flow's rows in hand between two components.
  What it gives up is
  said in the output where it applies: "a group of this 1 row alone".
  Reading everything and showing one record gives the true totals but
  loses the record at the first aggregate, which is where people look.
- **The whole row once, then what each component added or changed**, with
  a way to ask for every column.
- **A map's columns with their expressions.** The job's JSON has the text,
  and "why is this value what it is" is the question a debug run is for.
  The lookup row behind a match is worth having and can come second.
- **Always say where the record stopped**, with the reason the component
  has.
- **Write nothing.**
- **Text for a person first**, asked for by a flag beside the one that
  picks the record; a JSON form when a tool needs it.
- **A small limit on how many records**, refused past it with the number
  said.
- **Not the configs and plans**: `--log-level DEBUG` is there for those.

The one question to bring the dev early is 8: a printed record is customer
data in a log.
