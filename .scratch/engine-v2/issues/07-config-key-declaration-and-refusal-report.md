# 07 - Config-key declaration, aliases and the refusal report

Status: resolved
Type: grilling

## Question

How does a component declare its config keys so that one declaration drives
loading, refusal, aliasing, defaults and the generated doc page? This replaces
both the free config dict and `validate()` returning strings, and it replaces
`SUPPORTED_FEATURES`, which was keyed by Talend feature names.

To settle:

- The declaration: for each key its name, type, default, kind (supported,
  ignored or refused, with the reason shown to the user), allowed values, and
  its v1 alias or translation. Where it is written and in what form.
- Defaults. When a key is omitted, is the default v1's default, so that an
  unedited v1 job config behaves as it did? What if v1's default is itself
  refused (v1's default encoding is ISO-8859-15)? What if v2's documented
  spelling had a different default (`delimiter` `,` versus `fieldseparator`
  `;`)?
- Translation: where loader-side translations of v1 forms live, and how the
  rule "components see one spelling" is enforced.
- Nested keys and lists: Map's lookups, outputs and columns; filter
  conditions.
- The refusal report: what each line says (component, key, reason, what to do
  about it), how lines are grouped, that everything is reported in one pass,
  and what the process exits with.
- Whether the report can be produced alone, as a readiness check on a v1 job
  config, without running the job.

The key-by-key tickets and the build of the loader wait on this.

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- A component declares `keys`, a tuple of `Key(name, kind, type, default,
  required, aliases, choices, reason, doc, convert, items, fields, ...)` in
  its own file (`src/v2/job/keys.py`). The one declaration drives loading,
  aliasing, defaults, refusal and the generated doc page.
- Defaults are v1's engine defaults, so an unedited v1 job config behaves as
  it did (`fieldseparator` `;`, `encoding` ISO-8859-15).
- Aliases are applied once at load; a component sees v2 names only; both
  spellings in one config are refused. Nested keys are declared with `items`
  (lists of objects) and `fields` (objects).
- The refusal report (`src/v2/job/refusal.py`) lists every problem in one
  pass, grouped by component, as `key: reason`. It is also produced alone:
  `python -m src.v2 job.json --check` (exit code 2 when anything is refused).
- Beyond the key-by-key check, the job is built against empty frames at load
  (`src/v2/engine/check.py`), so keys that do not go together and
  expressions that cannot work land in the same report.
