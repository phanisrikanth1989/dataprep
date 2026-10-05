# 06 - Job file shape, key by key

Status: open
Type: grilling

## Question

The outer shape of a job config differs between v1 and v2 as found. Walk
every key outside component `config` and give each one of the five verdicts:
same in both; v2's name kept with v1's spelling as an alias; v2 adopts v1's
name; the loader translates v1's form; refused or ignored. Some v2 renames
had a purpose, so recover the purpose of each before judging it.

How to run it: bring a table of v1 key, v2 key as found, what each does and a
proposed verdict; the user confirms or changes it row by row. The starting
vocabulary is in
[v2 engine as found](../research/2026-10-05-v2-as-found.md#v1-job-configs-versus-v2-as-found).

Keys to walk:

- Job level. v1: `job_name`, `job_type`, `default_context`, `context` (grouped
  by context name), `components`, `flows`, `triggers`, `subjobs`,
  `java_config`, `_validation`, `_needs_review`. v2 as found: `name`,
  `version`, `description`, `context` (flat), `streaming`.
- Component level: `id`; `type` (v1 `FileInputDelimited` and
  `tFileInputDelimited`, v2 `file_input_delimited` plus its own extra names);
  `original_type`; `position`; `config`; `schema` beside config with `input`
  and `output` (v1) versus `schema` inside config (v2); `inputs`; `outputs`.
- Context, shape only: grouped versus flat, `{value, type}` entries.

Also settle what a job config gets when it still has `java_config.enabled:
true` or any `{{java}}` string, and whether v2-only keys such as `streaming`
survive.

Not here: flow and trigger keys ([Flows and ports](08-flows-and-ports.md),
[Subjobs, triggers and what happens after a failure](10-subjobs-triggers-and-failure.md));
schema column keys and type names
([Types, nulls and schemas](13-types-nulls-and-schemas.md)); context behaviour
([Context and globalMap](11-context-and-globalmap.md)); keys inside component
`config` (the key-by-key tickets).
