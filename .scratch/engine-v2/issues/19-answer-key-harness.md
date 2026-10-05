# 19 - Answer-key harness

Status: open
Type: task

## Question

Build the tool every component's tests stand on. Given a job config and its
input files, it runs the job on v1 and keeps the outputs as the answer key,
runs the same job on v2, and reports any difference.

Settle with the user before building:

- Answer keys produced live from v1 during the test run, or produced once
  and committed.
- Equality. Output files are compared byte for byte; decide what happens
  where neither engine promises a row order.
- Map. v1's Map needs the Java bridge, and this Mac has no JVM. Does Map's
  answer key come from v1's PyMap running the same Python expressions, from
  a machine that has the bridge, or both?
- Where the harness lives and how a test calls it. v1 is invoked read-only.

Then build it, tests first. First fixtures: delimited file in, filter rows,
sort row, delimited file out, assembled from the repo's existing fixtures.
v2 cannot load a v1 job config until the loader exists, so the v1 side and
the comparison are proven here and the v2 side is proven against the first
slice of the build.

`src/v1` is not modified.
