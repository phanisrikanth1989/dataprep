# 14 - Encoding: what to do about ISO-8859-15

Status: open
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
