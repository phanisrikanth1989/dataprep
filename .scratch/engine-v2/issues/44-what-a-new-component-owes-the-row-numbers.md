# 44 - What a new component owes the row numbers

Status: resolved
Type: task
Blocked by: 40, 41, 42, 43

## Question

Write down, for whoever adds a component to v2 after this (a person or an
AI), exactly what the component has to declare and what has to be built and
tested for it, so that a failure still names its row.

Asked for by the dev on 2026-10-07: "a separate ticket which documents
exactly how a future component should be configured and what all are the
things the AI should build then."

## To build

- The rule for each kind of component, in `docs/v2/writing-a-component.md`,
  which is what a builder reads: a source, a step that keeps its rows, one
  that makes several rows of one, one that makes one row of several, one
  that hands rows to code the engine cannot see into, a file output.
- How a user marks a key column, and what a job config needs for it.
- The list of what to build and what to test, in the order to do it, with
  the two components of tickets 42 and 43 as the worked examples.
- This ticket's answer holds the same list, so that it can be handed to an
  agent as it stands.

## Answer

Written on 2026-10-07. The rules are in `docs/v2/writing-a-component.md`
(rule 9, "Row numbers", the paragraph on conversions under "Expressions",
"Tests", "Done means"). What follows is the same thing as a list to work
through, for a person or an AI handed "add component X to v2".

### How a user configures it

Nothing new. A user marks key columns with `"key": true` on the columns of
a source's schema (Talend's key flag converts to that). A new component
declares no config key for row numbers, and a job config needs no change.

### What to build, in this order

1. **Read the guide** (`docs/v2/writing-a-component.md`) and the v1
   component. Run v1 on small inputs for every case you are unsure of
   before deciding anything: v1 is the answer key.
2. **Answer-key tests first**, failing: `tests/v2/components/test_<name>.py`.
3. **The component**, one file, every key the converter writes and v1 reads
   declared as supported, ignored or refused.
4. **Decide what the component does with rows**, and do what the table in
   "Row numbers" asks for that kind:
   - a source numbers its records and implements `locate`;
   - a step that picks columns picks the hidden ones too;
   - a step that makes several rows of one lets the hidden columns repeat;
   - a step that makes one row of several keeps the first number, its key
     and the count;
   - a step that joins keeps the main input's and drops the lookup's;
   - a step that treats every column alike leaves the hidden ones out;
   - a step that hands rows to code the engine cannot see into sets
     `sees_hidden_columns = False`.
5. **If it translates expressions**, call `self.check_conversions(frame,
   scope)` for every frame they run on. The engine fails the job if you
   forget.
6. **If it can fail on a row itself**, make the check count the rows, ask
   for `*first_of(bad)`, and end the message with `self.where(found)`.
7. **Row-number tests** in `tests/v2/test_row_numbers.py`: for a source,
   the place and the key on every way it reads; for anything else, that a
   failure after it still names the source row (or, for foreign code, no
   longer does).
8. **The whole of `tests/v2`**, which is also what proves no hidden column
   reaches a file, and the coverage gate.
9. **The docs**: the component in the list of `docs/v2/README.md`, its row
   in the table of "Finding the row that failed", its differences from v1,
   and the count of components in `CLAUDE.md`.

### The two worked examples

- A source: `src/v2/components/file/file_input_json.py` (ticket 42). It
  numbers records with `with_row_index(self.row_number, offset=1)`, keeps
  each record's path while it reads, and `locate` returns "record 2
  ($.orders[1]) of in.json".
- A step that makes several rows of one:
  `src/v2/components/transform/normalize.py` (ticket 43). It does nothing
  for the numbers: it explodes one column, and Polars repeats the others,
  the hidden ones among them. Its test is
  `test_every_row_a_normalize_makes_carries_the_number_of_the_row_it_came_from`.

### What an XML input and an unpivot would need

The dev named these beside the two that were built.

- **XML input**: as the JSON input. `lxml` gives each element its line in
  the file (`sourceline`) and its path (`getpath`), so `locate` can say
  both: "record 2 (/orders/order[2], line 14) of in.xml".
- **Unpivot**: several rows of one, like normalize. Polars' `unpivot`
  keeps the columns named as its index: name the hidden columns among
  them, or they are dropped.
