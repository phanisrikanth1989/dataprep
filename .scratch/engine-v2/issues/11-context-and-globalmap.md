# 11 - Context and globalMap

Status: open
Type: grilling
Blocked by: 09

## Question

How do context values and globalMap entries behave in v2, given the standing
rule that context doubles as globalMap?

To settle:

- Context groups. A v1 job config holds values under a named group
  (`"Default"`) and names one with `default_context`. How a group is chosen,
  how a value is overridden at run time (v1: `--context_param KEY=VALUE`),
  and the value types.
- When a context value is read. As found, some components capture it when
  they are constructed and miss later changes, and a job that declares no
  context never sees values set during the run (findings 8 and 9).
- globalMap. Which v1 entries exist in v2 (file-list and iterate values, the
  row counts from
  [Barriers, collection and row counts](09-barriers-collection-and-row-counts.md)),
  what they are called, and how an expression spells them: v1 Python
  expressions write `globalMap.get("...")`, v2 as found writes
  `context.<component>_<KEY>`.
- Writing. Which components may set values, and whether a value set in one
  subjob is visible in the next.
- A reference to a value that does not exist. As found, an unknown
  `${context.x}` stays in a file path as literal text (finding 26). It should
  be refused; settle when it can be caught.
