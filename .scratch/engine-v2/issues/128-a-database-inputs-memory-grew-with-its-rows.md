# 128 - A database input's memory grew with its rows

Status: resolved
Type: task

## Question

How fast are the Oracle components, and how much memory do they hold?
Tickets [Oracle input](121-oracle-input.md) and
[Oracle output](122-oracle-output.md) both say it was not measured. The
dev asked on 2026-10-12.

## What is known

Measured on 2026-10-12. One Mac (Apple M4, 10 cores, 16 GB), polars
1.44.2, python-oracledb 26.0.1, Oracle 23.26 Free in a container on the
same machine (Oracle Free takes 2 processor threads and 2 GB at the
most). Rows of eight columns: two numbers, a decimal, three texts, a
date and a timestamp; about 105 bytes a row as CSV. Each job ran as a
process of its own under the system's clock. **All of it is of this Mac,
and no word about the servers.**

"Own memory" is what the process held of its own. The pages of a file it
only reads are not in it: the system can take those back at any time.

**The input, a query to a CSV file**

| Rows | Time | Rows a second | Own memory |
|---|---|---|---|
| 1 million | 1.7 to 2.4 s | 420,000 to 580,000 | 405 MB |
| 10 million (1 GB) | 12 s | 850,000 | 937 MB |
| 30 million (3.2 GB) | 35 s | 850,000 | 1,653 MB |

- The driver alone, fetching the 10 million and doing nothing with
  them: 6.7 s.
- **Its memory grows with its rows.** The two halves were run each by
  itself to find where:
  - Fetching the rows and writing the scratch file: 156 MB, the same at
    1, 10 and 30 million rows.
  - Polars scanning the scratch file and writing the CSV: 230 MB, 1,109
    MB and 1,371 MB when it numbers the rows as it scans
    (`scan_parquet(row_index_name=...)`), and 225 MB, 501 MB and 484 MB
    when it does not.
- The engine's own pass from a file to a file, with no database: 309 MB
  at 1 million rows and 350 MB at 10 million.

**The output and the bulk load, a CSV file to a table**

| What | Rows | Time | Rows a second | Own memory |
|---|---|---|---|---|
| insert | 1 million | 2.4 to 2.7 s | 365,000 to 415,000 | 448 MB |
| insert | 10 million | 22 s | 440,000 | 768 MB |
| insert | 30 million | 78 s | 380,000 | 735 MB |
| insert into a table with a key | 1 million | 3.5 s | 285,000 | 529 MB |
| update by key | 1 million | 4.9 s | 200,000 | 546 MB |
| insert or update, half there | 1 million | 4.7 s | 210,000 | 516 MB |
| update or insert, half there | 1 million | 4.7 s | 210,000 | 569 MB |
| delete by key | 1 million | 11.1 s | 90,000 | 503 MB |
| bulk load | 10 million | 24 s | 425,000 | 546 MB |
| bulk load | 30 million | 76 s | 390,000 | 689 MB |

- The driver alone, handed the same million rows 10,000 a round trip:
  2.4 s to insert them, 11.8 s to delete them. **The output is as fast
  as the driver is**, and the delete is slow in Oracle itself.
- The ten million rows read by the input and stored again by the output
  are the rows of the table they came from, every value.
- Their memory does not grow: about 0.7 GB from 10 million rows on.

**A statement and a procedure for each row**

| What | Rows | Time | Rows a second |
|---|---|---|---|
| insert for each row | 100,000 | 0.5 s | 185,000 |
| block of PL/SQL for each row | 100,000 | 1.1 s | 90,000 |
| stored procedure for each row | 100,000 | 0.6 s | 175,000 |
| query for each row | 20,000 | 4.9 s | 4,100 |
| insert that reads its own table | 20,000 | 5.2 s | 3,800 |

- The last two cost a round trip a row. Here that is a quarter of a
  millisecond, to a database on the same machine. Over a network it is
  what the network takes.
- They hold 100 to 150 MB.

## To build

A database input writes each row's number into its scratch file, and
Polars is not asked to number the rows as it scans. The XML readers do
it that way already.

## Answer

Built on 2026-10-12, in `src/v2/components/database/reading.py`, which
the Oracle input and the SQL Server input share.

- **Each row's number is written into the scratch file**, packed as the
  step from the number before, which takes next to nothing. Polars
  scans the file as it is.
- **The scratch file has groups of 10,000 rows, whatever a round trip
  brings.** A batch of more rows is cut; batches of fewer are put
  together.

**The input, a query to a CSV file, before and now**

| Rows | Time | Own memory before | Own memory now |
|---|---|---|---|
| 1 million | 1.8 s | 405 MB | 316 MB |
| 10 million (1 GB) | 12 s | 937 MB | 428 MB |
| 30 million (3.2 GB) | 38 s | 1,653 MB | 615 MB |
| 100 million (10.7 GB) | 151 s | not measured | 655 MB |
| 10 million, a thousand rows a round trip | 24 s before, 16.5 s now | 280 MB | 407 MB |

### What it was

- Polars reads the groups of a Parquet file ahead of what writes the
  rows out, and holds what it has read. How much is by the group: the
  same thirty million rows, in the same time, held 1.5 GB with 50,000
  rows a group, 0.9 GB with 20,000, 0.6 GB with 10,000 and 0.4 GB with
  5,000.
- A group was a round trip's rows: 50,000 by default. With Talend's own
  cursor size it was a thousand, which held little and wrote slowly: a
  file of ten thousand groups for ten million rows.
- Numbering the rows as it scans made Polars hold about twice as much
  again, measured on the pass by itself.
- The engine's own counting of the rows an output is handed is not it:
  the pass was run with and without, and held the same.

### What was decided

- **10,000 rows a group.** 5,000 held a little less (0.4 GB against 0.6
  GB at thirty million rows), and a file of a thousand million rows
  would have 200,000 groups of it. Fewer rows a group buys little more
  and costs what a file of very many groups costs.
- **The numbers are packed as steps** (Parquet's `DELTA_BINARY_PACKED`).
  Plain, they added a quarter to the file. Polars reads them back
  right: held by a test across twelve groups, and tried with column
  names that hold dots and blanks.
- The size of a round trip stays the job's to say. Only the file's
  layout is the engine's.
- The output and the bulk load were left as they are: they hold 0.7 GB
  at thirty million rows, and do not grow.

### Slips

- **The Oracle components had been built and reviewed without one
  measurement of their speed or memory.** Two tickets said so in a line
  each, and I did not say it to the dev. It took the dev asking.
- **My first reading was wrong twice.** First I took the numbering of
  rows for the whole cause; the real job held as much with it gone.
  Then I took the engine's row counter for it; the pass held the same
  without. The third, the size of a group, is the one the real job
  bore out.
- **[SQL Server connection and input](126-sql-server-connection-and-input.md)
  says the growth of the whole job "is the engine's pass, as for any
  reader". It is not.** A file read and written by the same pass holds
  0.35 GB at ten million rows. It was the scratch file's layout, and
  both inputs had it.
- The 30-million-row figures taken while the machine was busy swing by
  a factor of two in time. The memory figures were steadier; where two
  runs differ, both are in the tables.

### How it was tested

17 tests more, in `tests/v2/components/test_oracle_input.py`.

- 4 seen failing first: the number in the file, and three of the four
  layouts.
- 13 hold what must stay, or came after the code: the grouping by
  itself (ten cases), a row far into a result named by its number, a
  query of no rows, and a layout that passed by chance.
- Gate: 8,413 passed, 105 modules at 95% or more. Real Oracle: 73
  passed. Real SQL Server: 62 passed.

### Mutation check

18 ways of breaking it. Of the first 17, 14 were caught. The three
that were not each got a stronger test: the plan Polars runs is read
for any numbering of rows, a full group is handed on before more rows
are asked for, and the size of a group is held by a file of twelve
groups. They are caught now, and so is the one added with them.

### Not done

- The SQL Server input was not measured again. It shares this code.
- Nothing was measured beyond a hundred million rows, or on RHEL, or
  against an Oracle that is no Oracle Free on the same machine.
- The XML readers keep their scratch files as Arrow files. They were
  not measured here.

**For the user's eye**

- **The Oracle components are as fast as the driver is.** Reading:
  840,000 rows a second into a CSV file. Storing: 440,000 rows a
  second. On this Mac; a real server and a real network will differ.
- **A query of a hundred million rows, a 10.7 GB file, took two and a
  half minutes and 0.7 GB of memory.** Before this ticket the same job
  held 1.7 GB at thirty million rows.
- A job converted from Talend with "use cursor" and a thousand rows
  reads about 40% slower than one without. It is the round trips.
- A query for each row costs a round trip a row.
