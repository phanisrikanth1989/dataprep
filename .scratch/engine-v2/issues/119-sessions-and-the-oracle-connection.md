# 119 - Sessions, and the Oracle connection, commit, rollback and close

Status: resolved
Type: task

## Question

Build what every database component stands on, and the four that only
open and end things: Oracle connection (`OracleConnection`,
`tOracleConnection`, `tDBConnection`), commit, rollback and close. To
[Databases: the decisions](118-databases-the-decisions.md).

## What is known

- A component does its work on a session and never ends a transaction.
  The engine does, when the subjob has succeeded or failed.
- The engine acts at build (an action), in the pass (the plan), and when
  the pass has succeeded (`ready`, then `place`). A database is touched
  at build and after the pass, never in it: no driver is called from one
  of Polars' threads. So the lock the decisions name is not needed, and
  is not built.
- An action is a subjob of its own. A commit that a trigger sets off
  acts when its turn comes. One that stands in a flow, as the sample
  `Job_tOracleRow_0.1.json` has it, is built with the plan.
- A converted job carries the connection block on six components
  (research 4.2), and `connection` on the three that end things.
- No Oracle is there when the coverage gate runs.

## To build

1. `src/v2/sessions.py`: what a session is to the engine (run a
   statement, commit, roll back, mark a place and go back to it, close,
   say whether work is pending), and the sessions of a run: the shared
   ones by the id of their connection component, and the ones a
   component opened for its subjob.
2. The engine tells the sessions when a subjob has succeeded (commit,
   before any file is moved), when it has failed (take the work back),
   and when the job ends (work still pending fails the job).
3. `src/v2/oracle.py`: a session over python-oracledb, and how a
   connection block becomes what the driver is given.
4. The four components, in `src/v2/components/database/`.
5. At load: `connection` has to name a connection component of the job.

## How it is tested

Three ways, each for what it can show:

- **A real database with no server** stands behind the same seam in the
  gate's tests: SQLite, from Python's own library. Commits, rollbacks,
  places gone back to, and what a second session sees are real there.
- **What is Oracle's alone and needs no database** (the connection
  block, the words of a failure) is tested as what it is: text.
- **A real Oracle in a container**, marked `oracle` and not in the
  gate, runs the components as a job does.

## Answer

Built on 2026-10-12.

- `src/v2/sessions.py`: a session as the engine sees it, and the
  sessions of a run. The engine's part is three lines: a subjob that
  has succeeded, one that has failed, the end of the job.
- `src/v2/oracle.py`: the connection block, what is wrong with one, what
  the driver is given, and a session over python-oracledb.
- `src/v2/components/database/`: Oracle connection, commit, rollback and
  close.
- The loader refuses a `connection` that names no connection component
  of the job, and lists the ones the job has.
- `oracle_config` at the top of a job is read: `thick_mode`, `lib_dir`.
- Docs: `docs/v2/own-rule/databases.md`.

### What was decided on the way

- **No lock.** The decisions named one for each session. Nothing calls
  a driver from a second thread, so there is nothing for it to guard.
- **A commit in a flow draws every row through.** It first looked at one
  row only, to see whether any came. Then a flow that ends in a commit
  never read its second row, and a bad value there went unseen. Every
  row is counted now, as the flow would have them.
- **A rollback and a close of a session that is not open are no
  fault**; a commit of one is. Nothing can be lost by the first two.
- **A close says "roll back" before it closes.** python-oracledb loses
  pending work on a close and Talend's driver stores it: what a close
  does is said, and left to no driver.
- **A statement that stores by itself is seen.** What the engine noted
  as waiting is checked against what the database says waits, so a
  close after a `TRUNCATE` does not fail on work that is stored.
- **An empty port is 1521**, as an empty number is its default
  everywhere in v2.
- **`properties` refuses the job when it holds anything.** No JDBC
  parameter has a meaning here yet; one that a real job carries gets a
  key of its own when it is met.

### How it was tested

- 37 tests of the sessions and 12 of the engine with them, on SQLite.
  32 and 12 of them were seen failing first for want of the code; the
  five others came with the mutation check.
- 47 tests of the four components, on SQLite: 43 seen failing first. One
  passed before its component was there (it looked for the component's
  name in a refusal, and "no such type" has it too); it now holds the
  whole refusal.
- 58 tests of the Oracle module. **Not seen failing first**: they were
  written before the module and first run after it. The mutation check
  stands in.
- 18 tests against a real Oracle (marked `oracle`): the session, the
  connect strings, a wrong password, a statement that stores by itself,
  and the four components in jobs. They pass on a database that was
  running and on a container the tests start themselves.

### Mutation check

103 ways of breaking it. 91 were caught at first. Of the twelve others:

- **Two showed code that did nothing, and it went**: a second look at
  whether a port is `true`, and a split of `properties` at `;`.
- **One was the tool's**: the break did not parse.
- **Nine got a stronger test**: a commit in the middle of a subjob,
  what a rollback leaves waiting, a rollback that closes, the rollback
  a close and the end of a job say, a dead session's work, a host of
  blanks, a long connect string, and a component that opens a session
  of its own.

All were run again, and were caught.

**For the user's eye**

- Thick mode (`oracle_config.thick_mode`) is built and was not tried:
  no Oracle client is on this machine.
- v1's own tests of its Oracle output fail here, 71 of them with the
  new driver and 80 without any: not from this work, and not touched.
- v1's `oracle` extra pins `oracledb<4` and v2 needs 26.0.1: the two do
  not go into one environment.
