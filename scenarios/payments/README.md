# The payments scenario

One Talend-shaped job, the end-of-day payments run, timed on the v1 engine
and on the v2 engine with the same input files. It answers one question: how
long does a job of this kind take on each, and do they write the same thing?

## The job

One job of 24 components in three stages. Each stage is started by a
trigger, as in a Talend job.

| Stage | What it does | Starts when |
|---|---|---|
| 1. Settings | Reads a small settings file (business date, high-value limit) into the context | The job starts |
| 2. Validate and enrich | Checks, de-duplicates, joins, enriches, sorts and totals the payments; writes six files | Stage 1 finished without error (`OnSubjobOk`) |
| 3. Reject report | Reads the two reject files back, puts them together and counts rejects per currency | The format check turned something away (`RunIf` on its reject count) |

Stage 2, step by step:

1. Four file inputs: payments (45 columns), branches, customers, purpose codes.
2. Filter rows: both account numbers must look like an IBAN and the currency
   must be three capitals (three regular expressions), and the amount must be
   above zero. Rows that fail go to `format_rejects.csv`.
3. Unique row: a transaction reference seen before is dropped.
4. Join: inner join to the branches. Payments of an unknown branch go to
   `unknown_branch.csv`.
5. Map (prepare): keeps the columns the job goes on with and works out three
   by regular expression: the invoice reference pulled out of the narrative,
   the narrative with its runs of blanks made one, and the purpose code
   pulled out of the remittance text. It also works out the amount in USD.
6. Map (enrich): looks up the customer (only customers that are ACTIVE) and
   the purpose code, and has three outputs, each with its own condition: all
   enriched rows, high-value payments (the limit comes from the settings
   file), and cross-border payments.
7. Sort row: enriched rows by value date, then amount descending.
8. Aggregate row: count, sum, average and largest amount per value date,
   currency and region.
9. Six file outputs: `enriched.csv`, `high_value.csv`, `cross_border.csv`,
   `summary.csv`, `format_rejects.csv`, `unknown_branch.csv`.

Stage 3 writes `reject_report.csv`.

## Three variants

| Variant | Job file | Engine |
|---|---|---|
| `v1-java` | The map is a tMap with Java expressions, as the converter writes a Talend job | v1, through the Java bridge |
| `v1-pymap` | The map is a PyMap with Python expressions | v1 |
| `v2` | The same file as `v1-pymap` | v2 |

The job is written once, in `jobs.py`, and spelled two ways. The two
spellings differ only in the expressions of the two maps. Each run writes
the job file it used next to its outputs (`job_python.json`,
`job_java.json`), so it can be read or run by hand.

No Talend job exists for this pipeline: the Java job file is written by hand
in the shape the converter produces.

## The data

`data.py` makes the files from the row count alone, so the same count gives
the same files on any machine. About 470 bytes a payment.

- Payments: ids, dates, amounts, currencies, account numbers, BICs,
  countries, branch and customer ids, status codes, free texts and flags.
- 5,000 branches, 200,000 customers (one in ten not ACTIVE), 300 purpose
  codes.
- Of every hundred payments, two fail the format check, one names an unknown
  branch and one repeats a reference. About 2.5% are high value and 22%
  cross-border.

## How it is measured

- Each run is a process of its own. What is timed is that process from its
  start to its exit: starting Python (and Java for `v1-java`), loading the
  job, reading, transforming and writing.
- The most memory the engine's process held is recorded. For `v1-java` that
  leaves out the Java process beside it.
- The time of each stage comes from the line each engine logs when it starts
  a subjob. v1 also reports the time of each component; that is kept in
  `results.json`.
- v2 is run three times at each size and the middle run is reported.
- A v1 run that passes the cap (20 minutes) is stopped and reported as
  stopped.
- After the runs, every output file is compared between v2 and each v1
  variant by its SHA-256.

## Running it

From the repository's root:

```bash
python -m scenarios.payments.run --rows 1000000
python -m scenarios.payments.run --rows 1000000,2000000,5000000 --work /data/payments
python -m scenarios.payments.run --rows 50000000 --work /data/payments --variants v2
```

It needs Python 3.12 or later with pandas and polars, and for `v1-java` a
JDK on the PATH and the built bridge JAR. The work folder holds the data,
each variant's outputs, `results.json` and `results.md`. Nothing in it
belongs in the repository.

A v1 run needs memory in step with the row count, and disk for its outputs:
about 0.5 GB of input and 0.3 GB of output per million payments,
for each variant.

## What building it found

- **v1's tMap reads a lookup filter another way than Talend writes it.**
  Talend writes the filter of a lookup on the lookup's own row
  (`"ACTIVE".equals(cust.status)`). v1 hands the filter the lookup's rows
  under the main flow's name. Written Talend's way, the filter matches
  nothing, no customer is found for any payment, and the job still ends in
  success. The Java job file here spells the filter the way v1 reads it
  (`prepared.status`), so that v1 does the right work and can be timed.
- **v1's PyMap takes only a plain column as a lookup key.** A key worked out
  by an expression fails the component. That is why the purpose code is
  pulled out in a first map and looked up in a second; v2 and v1's tMap
  would take the expression as the key.
- **v2 ran the job as first written.** Nothing in v2 had to change.

## Not in it yet

A lookup by regular expressions kept in a file (a table of pattern and
category) is the next enhancement:
`.scratch/engine-v2/issues/30-pattern-lookup-from-a-file.md`.

## Results

Not filled in yet: the full timing run has not been done. First numbers,
taken while building, on an Apple M4 with 10 cores and 16 GB of memory:

| Rows | Variant | Time | Memory | Same files as v2 |
|---|---|---|---|---|
| 100,000 | v2 | 0.5 s | 0.6 GB | - |
| 100,000 | v1-java | 34.4 s | 1.7 GB | yes |
| 100,000 | v1-pymap | 105.8 s | 1.1 GB | yes |
| 1,000,000 | v2 | 1.9 s | 2.0 GB | - |
| 2,000,000 | v2 | 3.8 s | 3.5 GB | - |
| 5,000,000 | v2 | 12.2 s | 5.4 GB | - |

The v1 runs at 100,000 rows were single runs; the v2 times are the middle of
three.
