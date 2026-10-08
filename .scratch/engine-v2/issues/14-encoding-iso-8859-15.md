# 14 - Encoding: what to do about ISO-8859-15

Status: resolved
Type: grilling
Blocked by: 02, 05

## Question

`encoding: ISO-8859-15` is Talend's default and v1's default, and 36 of the
38 delimited file components in the fixture job configs carry it. v2 as found
accepts UTF-8 only, because that is all Polars' lazy reader takes. If the
answer is a plain refusal, almost every v1 job config is refused at its first
component. What does v2 do?

Options to weigh, with the facts from
[Polars facts: reading and writing delimited files](02-polars-facts-delimited-files.md)
and the test from [The performance bar](05-performance-bar.md):

- Refuse every encoding except UTF-8. The user converts files, or changes the
  key, before a job runs on v2.
- Accept the Latin encodings when the file's bytes are plain ASCII, where the
  encodings agree, and refuse the job when they are not.
- Transcode on the way in and on the way out, at whatever that costs.
- Anything else the facts suggest.

Covers reading and writing, and what an omitted `encoding` means given v1's
default. The verdict lands in the two delimited-file key tickets
([input](20-config-keys-delimited-file-input.md),
[output](21-config-keys-delimited-file-output.md)).

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- Transcode, both ways, paid only when needed. On read, a file in an
  encoding that agrees with ASCII is first looked through (about 10 GB/s);
  if it holds nothing but ASCII it is read in place, otherwise through a
  UTF-8 scratch copy (about 2 GB/s for ISO-8859-15), removed when the job
  ends. On write, Polars writes UTF-8 and the file is converted only when it
  holds more than ASCII.
- An omitted `encoding` means ISO-8859-15 on both sides, as in v1. Any
  encoding Python knows is accepted; an unknown one is refused at load.
- Bytes that cannot be decoded become U+FFFD (Talend's behaviour); text the
  output encoding cannot hold fails the writer and leaves the target file
  untouched.
- v1's replacement of control characters by spaces is not copied: it exists
  for the Java bridge.
- Code: `src/v2/files.py`. `V2_TEMP_DIR` says where scratch copies go.
