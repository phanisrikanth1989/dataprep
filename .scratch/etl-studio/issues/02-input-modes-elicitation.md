# 02 - Input modes and requirement elicitation

Status: open
Type: grilling

## Question

How do a typed English request and an uploaded BRD both become one requirement
spec through agent<->human Q&A -- one modular pipeline, two front doors, no
duplicated downstream code copies?

To settle:

- What the elicitation loop asks, in what order, and when it stops -- what
  makes a requirement spec "complete enough" to hand to flow design.
- Whether BRD upload and typed request converge on the same artifact (the
  requirement-spec equivalent) and where the convergence point is.
- How the existing BRD-flow stages (docx purity, explode, normalize,
  interpret) map onto or merge with the typed-request path.
- What ambiguity handling looks like mid-run now that questions can reach the
  human live (today ambiguities surface only at the end).

Constraint from charting (map Notes): one modular pipeline, two front doors,
no duplicated code copies.
