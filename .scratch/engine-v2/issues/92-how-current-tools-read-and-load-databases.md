# 92 - How current tools read and load databases

Status: resolved
Type: research

## Question

Before v2 gets the Oracle components (connection, input, output, row,
stored procedure, bulk exec, commit, rollback, close) and the two MSSQL
ones (connection, input): how do current tools read from and load into
Oracle and SQL Server from Python at the dev's sizes, manage connections
and transactions, and keep a load repeatable, and what follows for v2's
design? Findings, each with its source, in
`research/2026-10-12-databases.md`.

## Answer

Researched on 2026-10-12; the note has ten findings that the design
turns on, twelve decisions each with its options, and the keys a
converted job carries. Decided in
[Databases: the decisions](118-databases-the-decisions.md).

The research ran nothing against a database. What it could only read
about was tried afterwards against a real Oracle, and is in ticket 118
under "What the real database said". Two things the pages do not say
came out of that: the driver changes a number without a word when asked
for a decimal too wide, and it brings the interpreter down when a time
limit is set on a session the database has closed.
