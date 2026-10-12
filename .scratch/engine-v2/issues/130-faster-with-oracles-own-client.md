# 130 - Faster with Oracle's own client, and a fraction of a second that was lost

Status: resolved
Type: task

## Question

With Oracle's own client (thick mode) the Oracle components worked
([Oracle's own client (thick mode), tried](129-oracles-own-client-tried.md))
and were slow: about twice as long for a bulk read and a bulk insert,
and over twenty times as long for a block of PL/SQL run for each row.
The dev asked on 2026-10-13 what can be done about it, by research and
by trial. This ticket is the trial. The research is its own ticket.

## What was measured

In a container of Oracle Linux 8 with Python 3.12, python-oracledb
26.0.1 and Instant Client 23.26, against Oracle 23 Free, with rows of
eight columns. Each job ran as a process of its own, with the client
and without it turn by turn. All of it is of one Mac.

**Reading ten million rows, by how many rows a round trip brings**

| Rows a round trip | With the client | Without |
|---|---|---|
| 500 | 15.6 s, 0.9 GB | 13.8 s |
| 1,000 | 14.9 s, 0.9 GB | 13.3 s |
| 2,000 | 14.0 s, 0.9 GB | 12.1 s |
| 5,000 | 17.6 s, 1.0 GB | 12.5 s |
| 10,000 | 21.4 s, 1.0 GB | 13.2 s |
| 50,000 (what v2 asked for) | 22.1 s, 1.5 GB | 12.3 s |

**The driver by itself, a million rows inserted**

| | Rows handed over as | Time | Memory |
|---|---|---|---|
| without the client | an Arrow table | 1.75 s | 0.4 GB |
| without the client | tuples | 2.4 to 3.1 s | 0.4 GB |
| with the client | an Arrow table, 10,000 a round trip | 4.1 s | 2.2 GB |
| with the client | an Arrow table, 2,000 a round trip | 3.5 s | 1.1 GB |
| with the client | tuples | 2.6 s | 0.4 GB |

**The driver by itself, a block of PL/SQL for each of 100,000 rows**

| | Rows handed over as | Time |
|---|---|---|
| without the client | an Arrow table | 0.9 s |
| with the client | an Arrow table | 17.6 s |
| with the client | tuples | 0.7 s |

- A procedure with a value that comes out, 100,000 calls: 0.1 s without
  the client, 2.8 s with it, whatever the size of a round trip. The
  client makes a round trip of each such call.

**Why an Arrow table is so dear with the client**, found by the
research
([How Oracle is made fast from Python](131-how-oracle-is-made-fast-from-python.md))
and then tried: Polars hands a text over as Arrow's `large_string`, and
the driver binds that as a LONG. With the client that is 64 KiB for
every value, and for a block of PL/SQL a temporary LOB for every value.

| With the client, rows handed over as | A million rows inserted | A block for 100,000 rows |
|---|---|---|
| an Arrow table, text as `large_string` | 3.6 to 4.5 s, 2.2 GB | 27.8 s |
| an Arrow table, text as plain `string` | 3.6 to 3.9 s, 0.57 GB | 0.87 s |
| tuples | 2.5 s, 0.40 GB | 0.68 s |

Without the client the two kinds of text cost the same.

**The session data unit**, also from the research and then tried. The
driver by itself, ten million rows fetched:

| | The unit asked for | The unit the two sides settled on | Time |
|---|---|---|---|
| without the client | nothing (the driver's own) | 8 KB | 5.3 s |
| without the client | 64 KB or 2 MB | 64 KB (what the database allows) | 4.5 to 4.7 s |
| with the client | either | cannot be asked | 5.9 to 6.2 s, no gain |

## What was found besides

**A moment lost its fraction of a second, with the client and without
it.** A driver takes a moment that is handed to it as a plain value for
a date, and a date has no fraction of a second. v2 handed values over
that way in two places, both in what is pushed:

- **A stored procedure handed 13:14:15.123456 got 13:14:15.**
- **A query run for each row that compared a moment of the row found
  no row.** (An insert, an update or a block for each row went as an
  Arrow table, which says what its columns are.)

Handing rows to the client as tuples would have added a third.

**The driver has a direct path load** (`direct_path_load`), tried here:

- A million rows in 0.9 s, about twice as fast as the insert.
- Only without the client.
- **It stores by itself**: another session sees the rows at once, and a
  rollback does not take them back. It refuses to run with work waiting
  on the session.
- **A key that is there twice goes in**, and the table's index is left
  unusable.
- So it is no way of the output's or the bulk load's as they are: they
  store nothing unless the whole subjob succeeded. Not built.

## Answer

Built on 2026-10-13.

- `src/v2/oracle.py`: **with the client, rows are handed over as
  tuples**, for an insert, an update, a delete and a block alike.
- **Wherever rows go as plain values, the driver is told what each
  column is**, as an Arrow table says it of itself: a moment, a day, a
  float, a number, a true or false. For the client's tuples, for a
  query run for each row in either mode, and for a moment that goes
  into a procedure.
- **A session of the client reads 2,000 rows a round trip** when the
  job does not say (`src/v2/sessions.py`, `reading.py`). Without the
  client it stays 50,000.
- **Every session asks for the largest session data unit.** A connect
  string that names its own keeps it.
- `tests/v2/oracle/thick/Dockerfile`: the container the tests were run
  in with the client, so that it can be done again.

**The same jobs, with the client, before and now** (10 million rows
where it says so):

| What | Before | Now | Without the client |
|---|---|---|---|
| read to a CSV file, 10M | 22 s, 1.5 GB | 13.9 s, 0.9 GB | 12.8 s |
| insert, 10M | 47 to 50 s, 2.4 GB | 35 to 40 s, 1.6 GB | 20 to 29 s |
| insert, 1M | 5.0 to 6.6 s, 2.2 GB | 3.9 s, 0.7 GB | 2.2 s |
| a block for each of 100,000 rows | 28 to 31 s | 1.2 s | 1.1 s |
| a procedure, a value coming out, 100,000 calls | 3.8 s | 4.1 s | 0.6 s |

With the database demanding Native Network Encryption (AES256, SHA256
checksums): 15.8 s to read, 35 s to insert the ten million, 6.8 s for
the procedure.

### What was decided

- **Tuples only with the client.** Without it an Arrow table is the
  faster by a third, and stays.
- **2,000 rows a round trip with the client.** 1,000 to 2,000 read
  fastest here. Over a slow network more rows a round trip would pay,
  and the job can say so (`use_cursor`, `cursor_size`).
- **Every kind is said, and not only a moment's.** A float goes as the
  database's own float and a number as a number, as from an Arrow
  table: a row is bound the same way whichever way it travels.
- For a procedure only a moment that goes in is said. Its other values
  are bound as they always were.
- **Tuples, and not an Arrow table with plain strings.** The second
  mends the memory and the block, and an insert stays a second a
  million rows slower than with tuples.
- The size of a round trip for an insert stays 10,000: with tuples it
  made no difference.

### Slips

- **Two faults in pushed code were found only because the way rows
  travel was changed for speed.** No test had handed a procedure a
  moment with a fraction of a second, or compared one in a query for
  each row.
- My measuring script printed the driver's whole complaint once for
  every job when the database demanded the encryption and the script
  itself looked at it without the client. Noise, and no finding.

### How it was tested

19 tests more (two of them for the session data unit, where thirteen
that were there had to say it too and were seen failing first).

- 8 against the stand-in driver, all seen failing first: rows as
  tuples, each kind said, the block's rows, the round trip of each
  mode, the query's values in both modes, the moment into a procedure.
- 5 of the components on SQLite, 2 seen failing first (the round trip
  the session asks for). The others hold what must stay, or came after
  the code.
- 4 against the real database. Two were run against the code as it was
  pushed and fail there: the procedure, and the query for each row.
  One that was there already (every kind of value into a table) failed
  in thick mode while the rows went as tuples with nothing said.
- The whole real suite: 78 passed with the client, 78 without.
- Mutation: 25 ways of breaking it, all caught at first.

### Not done

- A procedure with a value that comes out stays a round trip a call
  with the client. One block that takes all the rows as arrays would
  mend it, and would have to rewrite the call.
- An insert with the client stays about half as long again as without.
- The direct path load (above).
- TLS without the client was not tried: the scratch database's image
  has no tool to make a certificate with.

**For the user's eye**

- **Two faults were in what is pushed, without the client too**: a
  stored procedure and a query run for each row lost the fraction of a
  second of a moment. Fixed here.
- **With Oracle's client v2 now reads as fast as without it**, runs a
  block for each row as fast, and inserts in about half as long again.
  It holds the same memory.
- **Stored procedures with OUT values are slow with the client**: 25,000
  calls a second here, against 170,000.
- Native Network Encryption itself costs about a tenth.
