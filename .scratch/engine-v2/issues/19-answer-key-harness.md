# 19 - Answer-key harness

Status: resolved
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

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

Built: `tests/v2/answer_key`. A test hands over a job config and input
files; v1 and v2 each run it in a fresh folder; what is compared is whether
the job finished, which files it wrote and their bytes. Nothing is stored.
A job whose v1 form needs Java carries a v2 rewrite (`v2_job=`) and is
skipped where the bridge is not available. Component tests add a guard that
both engines really finished, since two failures compare as equal.
