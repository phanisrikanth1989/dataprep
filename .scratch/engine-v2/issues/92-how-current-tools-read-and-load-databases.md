# 92 - How current tools read and load databases

Status: open
Type: research

## Question

Before v2 gets the Oracle components (connection, input, output, row,
stored procedure, bulk exec, commit, rollback, close) and the two MSSQL
ones (connection, input): how do current tools read from and load into
Oracle and SQL Server from Python at the dev's sizes, manage connections
and transactions, and keep a load repeatable, and what follows for v2's
design? Findings, each with its source, in
`research/2026-10-12-databases.md`.
