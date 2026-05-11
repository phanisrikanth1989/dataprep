# AI Prompt: Create a New DataPrep Component

*Last updated: 2026-05-11*
*Audience: AI coding assistant (Claude Code, GitHub Copilot, Cursor, etc.)*

---

## How to use this prompt

Paste the contents of the `<prompt>` block below into your AI assistant
when you need to add a brand-new component to the DataPrep engine. The
prompt is intentionally lighter than `EDIT_COMPONENT.md` -- creation is
contained (a new file with a fresh registry entry, no upstream callers
to break), and the source-of-truth authoring patterns already exist in
`docs/v1/patterns/`. This prompt is a thin orchestration layer that
points the assistant at the right docs and checks the right boxes.

If you are modifying an existing component instead, use
`docs/ai-prompts/EDIT_COMPONENT.md`. If you are debugging a runtime
failure, use `docs/ai-prompts/DEBUG_JOB_FAILURE.md`.

---

## When to use this prompt vs. just asking the assistant

| Situation | Use this prompt? |
|-----------|-------------------|
| Add a Talend component the engine doesn't yet implement (e.g., a non-shipped `database/` component) | **Yes** |
| Add an engine-native component with no Talend equivalent (PythonRowComponent-style) | **Yes** |
| Add a new alias to an existing component's `@REGISTRY.register` | No -- use `EDIT_COMPONENT.md`, the alias addition is a Rule-10-safe edit |
| Add a new routine (Python helper, not a component) | No -- routines live under `src/python_routines/`; this prompt is component-specific |

---

## What this prompt enforces

1. **The 8-step Talaxie-diff workflow** (audit → research → parity →
   plan → review → code → verify → close) is the canonical authoring
   methodology. Skipping the early steps causes Phase-14-style bug
   bundles (Phase 14 closed 11+ BUG-* tickets from components that
   skipped steps 1-3).
2. **Both halves are required:** an engine component class AND a
   converter component (unless explicitly engine-native). The pair must
   ship together.
3. **Both halves need tests:** unit tests for the component class AND a
   pipeline-fixture test (per CONTRIBUTING.md Rule 8).
4. **The 95% coverage gate must pass** on the new modules before merge.

---

## The prompt

```
<prompt>
You are creating a new component for the DataPrep ETL engine. DataPrep
replaces Talend for ~1200 production jobs -- the new component must
either match a documented Talend component bit-for-bit, OR be an
engine-native component with its own clearly-stated contract.

This work has two halves -- the engine-side component class AND the
converter-side parser that produces JSON config for it -- plus tests for
both. All three must land together.

# Inputs the user will give you

- Component name (PascalCase for the class, e.g., FileInputAvro)
- Talend equivalent name with the t-prefix (e.g., tFileInputAvro), OR
  "engine-native" if no Talend equivalent exists
- Category (one of: aggregate, context, control, database, file,
  iterate, transform)
- A short description of what the component does

# Required reading before any other action

Read these IN ORDER. Confirm to the user that you have read each one
before writing code.

1. /Users/aarun/Workspace/Projects/dataprep/CLAUDE.md sections
   "Architecture", "Conventions", "Naming Patterns", "Error Handling",
   "Logging", "Coverage". Code style is non-negotiable.

2. /Users/aarun/Workspace/Projects/dataprep/docs/CONTRIBUTING.md Rules
   1-10. Especially Rule 5 (BaseComponent + registry dual invariant),
   Rule 8 (pipeline tests required for lifecycle-sensitive modules),
   Rule 9 (Talend parity non-negotiable), and Rule 6 (95% coverage
   floor).

3. /Users/aarun/Workspace/Projects/dataprep/docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md
   -- the 13 rules of BaseComponent subclassing AND the long-form
   sections on stats lifecycle, treat_empty_as_null, die_on_error
   reject routing, and per-chunk streaming. This is the canonical
   authoring guide. Do not duplicate its content into your reply;
   reference rule numbers.

4. /Users/aarun/Workspace/Projects/dataprep/docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md
   -- the engine-side pattern (file layout, imports, _validate_config
   contract, _process contract, helper organization).

5. /Users/aarun/Workspace/Projects/dataprep/docs/v1/patterns/CONVERTER_PATTERN.md
   -- the converter-side pattern (subclass ComponentConverter, register
   via @REGISTRY.register decorator, ComponentResult shape).

6. /Users/aarun/Workspace/Projects/dataprep/docs/v1/patterns/ENGINE_TEST_PATTERN.md
   and TEST_PATTERN.md -- the test layout and fixture conventions.

7. The closest analog component already in the repo. Find it by:
     ls src/v1/engine/components/<category>/
   Pick the most similar existing component (e.g., for a new file
   reader, start from file_input_delimited.py). Read its source, tests,
   pipeline fixture, and audit doc in full. This is your reference
   shape.

8. If the component has a Talend equivalent:
   - Talaxie javajet template
     (https://github.com/Talaxie/Talaxie/blob/master/...)
   - tests/talend_xml_samples/Job_<TalendName>_*.item if any fixture
     exists for the Talend version

# Step 1 -- The 8-step Talaxie-diff workflow

DataPrep components follow this workflow (project memory:
project_component_workflow). For new components, you execute steps 1-7;
the user owns step 8.

  Step 1: Audit -- read the existing audit doc if one exists, OR
    confirm one doesn't yet exist. (Audit docs are usually authored
    before the component; check
    docs/v1/audit/components/<category>/<name>.md.)
  Step 2: Talaxie research -- read the Talaxie javajet template.
    Catalog every Talend config parameter (every _java.xml PARAM entry)
    and every advanced setting.
  Step 3: Feature parity -- list every Talend feature, and decide which
    you will implement in v1 (full parity), which you will defer (P2/P3
    items the audit doc will record), and which are engine-native
    extensions.
  Step 4: Plan -- write a short authoring plan: component class file,
    converter file, test files, pipeline fixture. State the config keys
    you will support.
  Step 5: Review -- present the plan to the user for approval before
    writing code.
  Step 6: Code -- implement engine + converter + tests.
  Step 7: Verify -- run unit tests, pipeline fixture, coverage gate.
  Step 8: Close -- you (the assistant) hand off to the user for audit
    doc authoring and PR.

# Step 1.1 -- Output of audit phase

State explicitly:

  Component: <PascalCase name>
  Talend equivalent: <tTalendName, OR "engine-native">
  Category: <aggregate / context / control / database / file / iterate
    / transform>
  Existing audit doc: <path or "to be authored">
  Closest analog in repo: <path/to/existing_component.py>

# Step 2.1 -- Output of Talaxie research

If the component has a Talend equivalent, list its config parameters in
a table:

  | Talend PARAM name | Default | Type | What it does |
  |-------------------|---------|------|--------------|
  | FILENAME          | ""      | str  | Input file path |
  | ENCODING          | "UTF-8" | str  | File encoding   |
  | ...               | ...     | ...  | ...             |

If engine-native, write a contract instead:

  Inputs: <DataFrame shape coming in, OR "none -- generator">
  Outputs: <DataFrame shape going out>
  Side effects: <writes file? sets globalMap? raises?>

# Step 3.1 -- Feature parity verdict

Categorize every Talend feature:

  Full parity (v1): <list of feature names>
  Deferred (will be audit P2/P3 entries): <list>
  Engine-native extension (no Talend equivalent): <list>

For each deferred feature, write a one-line justification (cost vs.
value).

# Step 4 -- Authoring plan

Present the plan as four sections:

  ## Engine component
  - File: src/v1/engine/components/<category>/<snake_case_name>.py
  - Class: <PascalCaseName>(BaseComponent)
    [or (BaseIterateComponent) for iterate-style]
  - Registry decorator:
      @REGISTRY.register("PascalCaseName", "tTalendName")
  - _validate_config keys (presence-only checks):
      - <key1>: <type>
      - <key2>: <type>
  - _process steps (high-level, not code):
      1. <step>
      2. <step>
  - Helpers: <list of helper functions/methods>
  - Imports: <list>

  ## Converter
  - File: src/converters/talend_to_v1/components/<category>/<snake_case_name>.py
  - Class: <PascalCaseName>Converter(ComponentConverter)
  - Registry decorator:
      @REGISTRY.register("tTalendName")
  - Config key mappings (Talend PARAM -> JSON config key):
      - FILENAME -> filepath
      - ENCODING -> encoding
      - ...
  - Talend-to-Python type mappings: <list>
  - Schema column extraction: <how>

  ## Tests
  - Unit tests file: tests/v1/engine/components/<category>/test_<snake_case_name>.py
  - Pipeline fixture file: tests/fixtures/jobs/<category>/<snake_case_name>_<behavior>.json
    (per CONTRIBUTING.md Rule 8 -- pipeline-fixture test is REQUIRED
     for lifecycle-sensitive modules; for pure transform components
     unit tests alone are acceptable)
  - Test cases planned:
      1. <test name>
      2. <test name>
  - Coverage target: 95%+ on the new module (Rule 6)

  ## Audit doc (to be authored as a follow-up by the user)
  - File: docs/v1/audit/components/<category>/<snake_case_name>.md
  - Use existing audit docs as the template -- 11 canonical sections
  - The deferred features from Step 3.1 land as P2/P3 entries here

# Step 5 -- Ask the user for approval

Phrasing:

  Authoring plan above. Approve and proceed to implementation? (y/n)
  If you have feedback on parity decisions, scope, or planned tests,
  share now -- changes after coding are more expensive.

Do NOT write code until the user says yes.

# Step 6 -- Code

Once approved, write the files in this order:

  1. Engine component class
  2. Converter
  3. Unit tests
  4. Pipeline fixture JSON (if applicable)

For each file, write the FULL contents in one go. After each file:
  - Confirm Rule 1 (ASCII only)
  - Confirm Rule 2 (custom exceptions, [{self.id}] prefix)
  - Confirm Rule 5 (registry decorator present + ABC methods
    implemented)
  - Confirm Rule 7 (no # pragma: no cover annotations)
  - Confirm MANUAL_COMPONENT_AUTHORING Rules 1-13 (per the rule list
    in EDIT_COMPONENT.md Step 4)

Then commit the file atomically per Rule 4. Suggested commit format:

  feat(<category>): add <PascalCaseName> component (engine)
  feat(<category>): add <PascalCaseName> converter
  test(<category>): unit tests for <PascalCaseName>
  test(<category>): pipeline fixture for <PascalCaseName>

# Step 7 -- Verify

a. Run unit tests for the new component:
     python -m pytest tests/v1/engine/components/<category>/test_<snake_case_name>.py -v

b. Run pipeline fixture test (if added):
     python -m pytest tests/integration/ -k "<snake_case_name>" -v

c. Run the full coverage gate (paste-runnable command in CLAUDE.md
   "Coverage"). Confirm the new modules clear the 95% per-module
   floor.

d. If the coverage gate fails, ADD tests until it passes. Do not pragma.

# Step 8 -- Hand off to user

Produce a summary:

  Component: <PascalCaseName>
  Talend equivalent: <tName / engine-native>
  Files created:
    - src/v1/engine/components/<category>/<snake_case_name>.py
    - src/converters/talend_to_v1/components/<category>/<snake_case_name>.py
    - tests/v1/engine/components/<category>/test_<snake_case_name>.py
    - tests/fixtures/jobs/<category>/<snake_case_name>_*.json (if any)
  Commits: <hashes>
  Tests added: <count> unit + <count> pipeline
  Coverage gate: pass
  Deferred features (require audit doc P2/P3 entries): <list>

The user is responsible for:
  - Authoring the audit doc under docs/v1/audit/components/<category>/<snake_case_name>.md
  - Updating docs/COMPONENT_REFERENCE.md to include the new component
  - Adding the component to docs/v1/audit/SUMMARY_SCORECARD.md if it
    is a shipped component
  - Opening the PR

# Hard rules

- NEVER skip Step 5 (user approval before coding). Component creation
  is a multi-file change; getting parity decisions wrong wastes hours.
- NEVER ship the engine component without the converter (and vice
  versa) unless the user explicitly states the component is
  engine-native.
- NEVER ship without tests. Unit tests are mandatory; pipeline fixture
  tests are mandatory for lifecycle-sensitive components per Rule 8.
- NEVER violate the 13 BaseComponent rules (MANUAL_COMPONENT_AUTHORING).
- NEVER ship below the 95% coverage floor.
- NEVER add a feature beyond Talend parity scope without explicitly
  flagging it as engine-native and getting user sign-off.

# Tone and style

- Be terse. The user wants the plan, the diffs, and the verification
  output -- not a tutorial.
- Match the closest analog component's style exactly. Code review will
  flag stylistic deviations.
- Cite file:line references when comparing to the analog component.
- ASCII only.
</prompt>
```

---

## See Also

- `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` -- the 13 BaseComponent rules + long-form authoring detail (CANONICAL SOURCE)
- `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` -- engine-side pattern (file layout, contracts)
- `docs/v1/patterns/CONVERTER_PATTERN.md` -- converter-side pattern
- `docs/v1/patterns/ENGINE_TEST_PATTERN.md` -- test layout and fixture conventions
- `docs/CONTRIBUTING.md` -- the 10 load-bearing project rules
- `docs/ai-prompts/EDIT_COMPONENT.md` -- companion prompt for modifying existing components
- `docs/ai-prompts/DEBUG_JOB_FAILURE.md` -- companion prompt for runtime failures
- `docs/v1/audit/METHODOLOGY.md` -- the audit-side use of the same 8-step workflow (different audience)
- `tests/fixtures/jobs/README.md` -- pipeline-fixture authoring guide
