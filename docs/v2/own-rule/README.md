# Components built to their own rule

These are built for long use and not to v1 or Talend: v1 is not their
answer key, and their tests hold them to what is written here. A converted
job config still loads as it is: the keys the converter writes are the
keys read, and where v1's engine reads another name, that name is taken
too.

What they share:

- What cannot be done fails the job and says why. Where the job config
  itself carries `die_on_error` and it is off, the job goes on with a
  warning, and why is in `<id>_ERROR_MESSAGE`.
- A file is written beside its place and put there when it is whole.
- Each counts one row (`<id>_NB_LINE`, `_OK`, `_REJECT`) unless it says
  otherwise.

| Page | What is on it |
|---|---|
| [File jobs](file-jobs.md) | File touch, File properties, Raw file input, Change file encoding, File archive |
