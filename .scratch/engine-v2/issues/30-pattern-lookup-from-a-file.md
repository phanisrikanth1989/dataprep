# 30 - Pattern lookup from a file

Status: needs-triage
Type: grilling

## Question

A job wants to classify each row by a table of regular expressions kept in a
lookup file: some thirty rows of pattern and category, and each row of the
main flow takes the category of the first pattern its text matches. How
should v2 offer that?

Parked by the dev on 2026-10-06 as the next enhancement, while the payments
scenario (`scenarios/payments`) was being planned. The scenario runs without
it.

## What is known

- v2 takes a pattern that is written in the job config, in a filter rows
  `MATCHES` test or in a map expression (`re.search`, `re.match`,
  `re.fullmatch`, `re.sub`).
- v2 refuses a pattern that comes from a column: "the pattern must be a
  constant, not a value that changes per row". Tried on a map with a lookup
  of patterns, no join key, and `re.search(row2.pattern, row1.text)` as the
  output filter.
- Talend and v1 have no join on a pattern either. There it is a tMap with no
  join key, which puts every main row beside every pattern, and a filter; or
  Java code.
- The dev's reading of the need: the patterns stay in a file, not in the job
  config.

## To decide

- Where it lives: a new matching mode on a map lookup, a config key of its
  own, or a component.
- What "first" means when several patterns match: the file's order, or a
  priority column.
- How it stays fast: the lookup file is small, so its patterns could be read
  when the plan is built and tried one after another in a single pass over
  the main rows, never as rows multiplied by patterns.
- What v1 is the answer key for it, since v1 has no such lookup.
