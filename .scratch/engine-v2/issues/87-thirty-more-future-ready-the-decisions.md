# 87 - Thirty more components, future-ready: the decisions

Status: resolved
Type: grilling

## Question

On 2026-10-12 the user asked for v1's file-job, loop and job-control, XML
and database components on v2 (30), and left out the special (send mail,
SWIFT), code (tJava*, Python*) and other-transform ones (memorize rows,
pagination, parse record set). What are they built to?

## Answer

The user's words, in order:

- "In these components we don't need v1 parity. Instead we should focus
  on long-term usage and ensuring the performance and other things are
  not compromised. You can do a bit of research on how this is to be
  implemented in modern etl pipelines. No need to just mimic talend or v1
  for these components dude. These are niche. Let's make them
  future-ready."
- Of the eight design questions put to them: "You make the decisions
  dude."
- "ultrathink and do things bro. don't just rush through please."
- "ensure research and future readiness for these components are also
  prioritised. Not only talend parity. talend maynot be the advanced etl
  tool present there."

Decided by the agent, for all thirty:

- **Research comes first, for each group.** Before a group is designed,
  how current tools do the same job is looked up in primary sources
  (their documentation and source), written down with its sources in a
  research ticket, and what is taken from it is tried here before it is
  relied on. Talend's own source is read too, for one purpose: so that a
  converted job still means something (its column names, its globalMap
  entries). It is not the model.
- **v1 is not the answer key here.** The tests hold v2 to what its
  documentation says, by the bytes, folders and tables a run leaves. (The
  44 earlier components keep v1 as their answer key.)
- **A converted job config still loads unchanged**: the keys the
  converter writes are the keys read, and the names v1's engine reads
  instead are taken too. (For most of the file jobs v1's engine reads
  other names than the converter writes: the converter's own
  `needs_review` notes say so.)
- **What every one of them has to be**, since the dev's files run to 30
  to 100 GB and the jobs run unattended on RHEL servers:
  - memory that does not grow with the size of what is handled (a file,
    an archive, a table, a document is gone through in pieces);
  - all or nothing: a file is written beside its place and put there
    when it is whole; rows are committed when the subjob has succeeded;
  - safe by default: nothing is read or written through a link out of
    the folder named, nothing an archive names lands outside the folder
    it is unpacked to, an XML document cannot make the engine read
    another file or the network, a value never becomes part of an SQL
    statement's text where it can be bound, and a password is never
    logged;
  - the same input gives the same output (order is fixed, not what the
    file system or the database happens to give);
  - it says what it did: in the log, in globalMap and in the summary;
  - what cannot be done fails the job and says why. Where the job config
    itself carries `die_on_error` and it is off, the job goes on with a
    warning and `<id>_ERROR_MESSAGE` in globalMap.
- **Order**: file jobs, then loops and job control (the engine learns to
  run a subjob once for each item), then XML, then database.
- **Discipline as before**: a ticket, tests seen failing first, a
  mutation check, a documentation entry and a commit for each component;
  an independent review for each group.

What each group is built to is decided in its own research and design
tickets, not here.
