# 89 - The v2 README taken apart

Status: resolved
Type: task

## Question

`docs/v2/README.md` is 1,495 lines and thirty more components are about
to be written into it. The user, on 2026-10-12: "in a separate ticket,
decompose readme.md if it feels too huge." (The README at the root of the
repo is 43 lines; the v2 one is meant.) Into what, so that a reader finds
one thing without reading the rest, and nothing is lost?

## Answer

Done on 2026-10-12. A page is for one thing a reader comes to do:

| Page | Lines | What is on it |
|---|---|---|
| `README.md` | 82 | what v2 is, where to read what, and every component with the page it is written up on |
| `running-a-job.md` | 211 | the command line, run settings, from a service, what the log says |
| `looking-into-a-job.md` | 187 | finding the row that failed, running for a few rows, the trace |
| `from-v1-to-v2.md` | 78 | taking a v1 job config to v2, expressions, routines |
| `how-a-job-runs.md` | 46 | how a job runs, types and missing values |
| `differences-from-v1/` | 16 to 324 | one page for each family: the engine and values, sources and outputs, rows, extracting fields, job control, file jobs |
| `own-rule/` | 21 each | the components v1 is no answer key for: the rule, and a page for each family (file jobs so far) |

- The text was moved as it is, by a script, and checked: every line of
  the old page is on a new page as often as before, but for the lines
  rewritten on purpose. Those are the old opening (now the start page),
  the list of components under "Taking a v1 job config to v2" (now the
  table on the start page, which that step points to), the two sentences
  that opened "Differences from v1", and three pointers to another
  section, which are links now.
- A component's entry is a heading now (it was a line in bold), so a link
  can lead to it.
- Replicate had no entry; it has one (no difference from v1 known).
- Grouped by family and not one page a component: many entries lean on a
  neighbour ("as for extract delimited fields above"), and a page of five
  lines is no easier to find than a heading.
- Three tests keep it so (`tests/v2/unit/test_docs.py`, seen failing
  before the split): every registered component has a row in the README's
  table that leads to a heading that is there; every link between the
  pages leads somewhere; no page is longer than 600 lines.
- `writing-a-component.md` says where a component is written up, and that
  v1 is no answer key for the components under `own-rule/`.
- The pages generated from the code (`docs/v2/components/`, not kept in
  the repo) are as they were.
