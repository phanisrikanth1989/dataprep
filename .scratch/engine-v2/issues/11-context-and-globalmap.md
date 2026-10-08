# 11 - Context and globalMap

Status: resolved
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

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- Context: the group named by `default_context` (else `Default`, else the
  first) is loaded; a named group that does not exist is refused. Values are
  converted to their declared type as v1 converts them; a value that does
  not fit is refused. `--context_param KEY=VALUE` and `run_job(context=...)`
  override, typed by the declaration.
- Config values are resolved when each component is built, so a value set
  by a context load earlier in the run is seen. `${context.x}` and v1's bare
  `context.x` are both replaced; a value that is one reference keeps its
  type. An unknown `${context.x}` is refused at load when no component of
  the job sets context, and fails the reading component otherwise.
- globalMap is its own map, spelled `globalMap.get("key")` in expressions
  and RunIf conditions as in v1. v2 writes the row counts (ticket 09) and
  what components set (`<id>_FILENAME`...). Values persist across subjobs.
