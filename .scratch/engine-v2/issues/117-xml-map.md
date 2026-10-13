# 117 - XML map

Status: resolved
Type: task

## Question

Build XML map (`XMLMap`, `tXMLMap`), to
[XML: the decisions](110-xml-the-decisions.md): what today's config can
say rightly, and no more.

## What is known

- The converter writes the two trees of Talend's editor as they are
  (`input_trees`, `output_trees`): for an input, its columns, and for a
  column that holds a document its elements and attributes, one marked
  as the loop element; for an output, its columns with their
  expressions.
- It also writes its own reading of them, `expressions` and
  `looping_element`, which v1 runs by. For the sample in the repo, a
  map with no document at all, that reading is `"name":
  "./ancestor::name"` and a loop element `emp_id`: nothing right.
- It does not write whether a lookup keeps a row with no match
  (`innerJoin`), which outputs are reject outputs, or what the map's
  variables hold.
- Talend's syntax for a place in a document, read in Talaxie's
  `tXMLMap` skeleton at `639d5fd1f776`: `[row1.doc:/order/line/sku]`, a
  path from the root. The value is taken for the loop element at hand.

## Answer

Built on 2026-10-12: `src/v2/components/transform/xml_map.py` (41
tests in `tests/v2/components/test_xml_map.py`, 33 of them seen failing
first for want of the component).

- **v2 reads the trees themselves**, not the converter's reading of
  them.
- **A document is taken apart by the engine of extract XML field.** That
  component was reshaped around a small plan (the column, the loop
  path, the path of each column, what is handed on from the row), which
  the map fills from its trees. One engine, two ways of being told
  what to do; nothing was copied.
- **A place is turned into a path from the loop element**: what the two
  paths share goes, and a step up stands for each step of the loop
  element's path that is left. `/order/@id` with the loop element
  `/order/line` is `../@id`.
- **With no document in the tree the rows are not held**: the columns
  are handed on under other names, as a lazy plan.

### What refuses the job, and why

A lookup, because a converted job does not say whether a row with no
match is kept: run as either, half the jobs would be wrong without a
word. A second output, a filter, a document to build, an expression
that is more than a place or a column, a variable, a second document
and a second loop element, each with what to do instead.

The sample in the repo joins a lookup and is refused for it, with that
one reason.

**For the user's eye**: this is the smallest of the six, on purpose.
What makes an XML map more than an extract (lookups, building
documents, expressions over values) needs the converter to write what
it leaves out today.

## Mutation check

Forty-one ways of breaking the map and the engine it shares. Thirty-four
were caught at first. Of the seven others:

- **Two showed code that did nothing, and it went**: a mark for an
  attribute when a path's steps are held against the loop element's
  (those steps are elements), and a second look at whether a node of the
  tree is an element.
- **Five got a stronger test**: columns said by `output_schema` that are
  not the tree's; the types of the tree; a prefix nobody binds; a place
  written with prefixes on the steps it shares with the loop element
  (it would have been read from the root, and every row would have had
  the first line's value); and that rows that are dropped are not made
  ready for a reject output the map has not.

All that could be caught were run again, and were.

## How it was built

Tests first for the component as a whole. Written after their code,
with the mutation check standing in: the document handed on beside its
values, namespaces given, a column the rows lack, several loop
elements, and more flows than trees.
