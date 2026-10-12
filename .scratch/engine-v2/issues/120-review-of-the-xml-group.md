# 120 - Review of the XML group

Status: resolved
Type: task

## Question

What does an independent read of the six XML components and of the
fixes of ticket 114 find, and what of it is real?

## What is known

One reviewer, read-only, on a copy of the tree at `a6e99c4a`, with no
network and no helpers. It was given the code and the docs, not my view
of them. It ran its own probes: 9,000 random documents against
whole-document XPath, 700 random trees for the advanced output, 400
hostile values through both writers in 25 encodings, 640,000 mask and
name pairs.

It found seven things. Each was run again on the tree as it is now
before anything was changed.

| # | Finding | Real? |
|---|---|---|
| 1 | A context variable's value is still read as Python by the row generator, and as a number by the fixed flow input. Ticket 114 closed this for globalMap only. A file's name, handed to a child job as a context value, made a folder. | yes |
| 2 | In the XML file input and the multi-schema input a column path `../rate * qty` is worked out wholly from the element above: `NaN`, or `true`, without a word. | yes |
| 3 | A path from the root inside a function (`count(//line)`, `string(/orders/header/date)`) is not refused, and reads a tree that is being let go of: the answer changes from record to record. | yes |
| 4 | The XML readers hold the whole document when its bulk is no record that is read: 1.5 GB for a 126 MB file. The docs say memory follows the largest record. | yes |
| 5 | The XML output's read-back holds the whole tree for two or more root tags in an encoding expat does not know (GBK, Shift_JIS): 2.3 GB for 164 MB. | yes |
| 6 | A large whole number from XPath is written with a point or an exponent (`3000000000000000.0`, `3e+21`). | yes |
| 7 | `xsi:nil="1"` is not taken for nil; only `"true"` is. | yes |

Its probe also showed two failures with words nobody can use, which
its report did not list: a column that climbs above a record that is
the root (`Invalid input object: NoneType`), and the namespace axis
(`'tuple' object has no attribute 'get'`).

## Answer

All seven are real, and so are the two failures its probe showed. All
nine are fixed, each with a test that failed first. Fixed on
2026-10-12.

### 1. A context variable is data (the grave one)

- A context variable may hold what a file or another job handed over.
  The row generator ran it as Python and the fixed flow input read it
  as a number. Ticket 114 had closed that for globalMap and left it
  open for the context.
- Now such a key is left as written when the job loads, and its
  component looks the references up itself (`reads_references`, which
  was `takes_looked`). So it knows what was looked up from what was
  written.
- **Row generator.** A variable alone (`context.x`, `${context.x}`) is
  what it holds, as it is. Inside an expression it stands under a name
  of its own and the value is handed to Python under that name: text
  is text, and text that is a plain number is the number, so
  `${context.n} + 1` comes to what it does in v1. Inside quotes it is
  part of the text. Nothing a variable holds is ever compiled.
- **Fixed flow input.** A value with a variable in it is handed on as
  it is. The inline content is taken apart as it is written: what a
  variable holds makes no field and no row.
- Where this leaves v1: a variable that holds `1+1` is `1+1` and not 2,
  and `00123` keeps its zeros. Both are in the differences pages.

### 2 and 3. Column paths in the XML readers

- `../rate * qty` was taken for "climb, then a path down" and worked
  out wholly from above. Only a plain path down is taken that way now;
  anything more is worked out from the record, as written.
- A path from the root is refused wherever it stands in a column's
  path, not only at its start: inside a function, after an operator,
  in a condition. An element named `div` or `mod` is told from the
  operator of that name.

### 4 and 5. Memory

- **The readers.** What is no record that is read was held to the end
  of the document. Now, while the parser waits for its next piece,
  everything that has ended and that no kind of record reads is let go
  of. lxml asks for a piece only when it has told every record that
  ended in the last one, which was tried, so nothing is let go of
  before its row is made.
- Measured with the reviewer's own probe on its 126 MB files: 1,550 MB,
  1,548 MB, 907 MB and 1,792 MB before; 83 MB for each now, which is
  what the process holds before it reads. Speed is as it was (22 MB a
  second for the whole job).
- Its 9,000 random documents were run again against the changed reader:
  the values are the same as whole-document XPath wherever they were
  before.
- **The read-back.** An element that has ended is taken out of the tree
  at whatever depth it stands. 178 MB for a 15 MB file before, 1 MB
  now. The reviewer's own probe for this needs a file another of its
  probes writes and was not run again; that measurement stands in.
- One case stays as it is and is what the docs say: with `//*` the root
  is itself a record, and a record that is the whole document is held
  whole.

### 6, 7 and the two failures

- A number is written as XPath writes one: no exponent, and a whole one
  with no point however large.
- `xsi:nil="1"` is nil, as XML Schema has it.
- A record that is the root has nothing above it: a column that climbs
  from it is missing there, and no longer fails.
- The `namespace` axis is refused when the job loads.

### Mutation check

61 ways of breaking the fixes. 51 were caught at first. Of the ten
others:

- **Four showed code that did nothing, and it went**: a second check
  that a `${}` variable exists, a way round the tokenizer for an
  expression with no variable, a catch for a fault the reading itself
  reports, and emptying an element that is taken out of the tree anyway.
- **Six got a stronger test**: what a text names, tested as itself;
  text Python could read as something else; a variable that holds
  nothing; inline content whose reference holds its own separator;
  `mod` and `or` before a root path; `namespace::` inside quotes.

All were run again, and were caught.

**For the user's eye**

- **Finding 1 is in what was pushed.** The row generator has written a
  context variable's value into its expression and run the whole since
  it was built, as v1 does. Ticket 114 closed the same thing for
  globalMap and left the context as it was, which was my miss.
- A job that leaned on a context variable being worked out as an
  expression (`context.x` holding `1+1`) now gets the text. A number
  from the context still works in arithmetic.
