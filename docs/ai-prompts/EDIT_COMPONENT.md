# AI Prompt: Safely Edit an Existing Component

*Last updated: 2026-05-11*
*Audience: AI coding assistant (Claude Code, GitHub Copilot, Cursor, etc.)*

---

## How to use this prompt

Paste the contents of the `<prompt>` block below into your AI assistant
when you need to modify an existing component -- add a feature, close a
parity gap, refactor, or address a `[STILL LIVE]` audit issue. The prompt
forces the assistant to read the project's load-bearing rules before
touching code, and to validate every change against Talend parity before
proposing it.

This prompt is for **editing components that already exist**. If you are
debugging a failure, use `docs/ai-prompts/DEBUG_JOB_FAILURE.md`. If you
are creating a brand-new component (not yet in the registry), use
`docs/ai-prompts/CREATE_COMPONENT.md`.

---

## When to use this prompt vs. just asking the assistant

| Situation | Use this prompt? |
|-----------|-------------------|
| Close a P0/P1/P2 issue from the component's audit doc | **Yes** |
| Add Talend parity for a missing feature on an existing component | **Yes** |
| Refactor a component's internals (no behavior change) | **Yes** -- the parity invariant + 95% coverage floor still apply |
| Address a `[NEW IN 15.1]` finding from Phase 15.1 reconciliation | **Yes** |
| Debug a failure happening at runtime | No -- use `DEBUG_JOB_FAILURE.md` first |
| Create a brand-new component | No -- use `CREATE_COMPONENT.md` |
| Edit converter logic only (not engine) | Partial -- skip the BaseComponent rules section, keep parity + atomic-commit rules |

---

## What this prompt enforces

1. **No edits before reading the audit doc.** The component's audit doc
   under `docs/v1/audit/components/<category>/<name>.md` is the
   authoritative record of what works, what is broken, and what is
   `[STILL LIVE]`. Editing without reading it risks reopening a closed
   bug or breaking an invariant.
2. **No edits before reading the 13 BaseComponent rules.** Phase 14
   surfaced 11+ bugs from violating these rules. They are not
   suggestions.
3. **Talend parity is non-negotiable.** Per `docs/CONTRIBUTING.md`
   Rule 9, every behavior change needs a Talend reference cited.
4. **The JSON contract is FROZEN.** Per Rule 10, you may add new
   optional config keys but never rename, remove, or change semantics of
   existing keys.
5. **Coverage gate must stay green.** Per Rule 6, the 95% per-module
   floor must hold after the edit. New code paths need new tests in the
   same commit (or the immediately following commit per Rule 4).

---

## The prompt

```
<prompt>
You are about to modify an existing component in the DataPrep ETL
engine. The DataPrep engine replaces Talend for ~1200 production jobs --
behavior must remain bit-identical to Talend for the same input. The
project has 10 load-bearing rules earned the hard way; violating them
gets your PR rejected and may break production.

Read everything before editing. Edits without investigation cause
regressions.

# Inputs the user will give you

- Component name (e.g., tFilterRow, FileInputDelimited)
- Goal of the edit (e.g., "add support for null-aware comparison",
  "close P1 issue FROW-04 from audit doc", "refactor to remove duplicate
  iteration")

# Required reading before any other action

Read these IN ORDER. Confirm to the user that you have read each one
before touching code. Skipping any of these has caused real bugs in
Phases 4-14.

1. /Users/aarun/Workspace/Projects/dataprep/CLAUDE.md sections
   "Architecture", "Conventions", "Error Handling", "Logging", and the
   "Coverage" command block. CLAUDE.md is the source of truth for code
   style and component contracts.

2. /Users/aarun/Workspace/Projects/dataprep/docs/CONTRIBUTING.md Rules
   1-10 -- in full. These are the load-bearing project rules. The
   relevant ones for component edits are:
   - Rule 1: ASCII-only (no emoji, no smart quotes, no em-dashes)
   - Rule 2: Custom exception hierarchy (ETLError subclasses only)
   - Rule 3: Fix source, no fallbacks (no defensive shims downstream)
   - Rule 4: Atomic commits per file
   - Rule 5: BaseComponent abstract methods AND registry membership are
     MANDATORY (the dual invariant)
   - Rule 6: 95% per-module line coverage floor
   - Rule 7: Dead-code policy -- delete unreachable branches, never
     pragma them
   - Rule 8: Pipeline tests for lifecycle-sensitive modules
   - Rule 9: Talend feature parity is non-negotiable
   - Rule 10: Converter JSON format is FROZEN

3. /Users/aarun/Workspace/Projects/dataprep/docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md
   -- the 13 rules of BaseComponent subclassing. Especially:
   - Rules 1-10 (subclass shape, registry, validate_config, process,
     execute(), config reads, globalMap, exceptions, logger, reset)
   - Rule 11: NEVER call self.validate_schema() inside _process()
   - Rule 12: _validate_config may only check key presence and
     container shape -- NEVER content
   - Rule 13: Registry Membership AND Abstract Methods (dual invariant)

4. The component's audit doc:
   docs/v1/audit/components/<category>/<name>.md
   - Read the Component Identity table
   - Read the Scorecard (P0/P1/P2/P3 issue tables)
   - Read every [STILL LIVE] issue
   - Read every [NEW IN 15.1] finding
   - Read the Resolved section -- understand what is already fixed and
     what bugs the component has had historically

5. The component's source files:
   - Engine: src/v1/engine/components/<category>/<name>.py (full file)
   - Converter: src/converters/talend_to_v1/components/<category>/<name>.py
     (only if your edit changes the JSON config shape; otherwise
     skip)

6. The component's tests:
   - Unit: tests/v1/engine/components/<category>/test_<name>.py
   - Pipeline fixture: tests/fixtures/jobs/<category>/<name>_*.json
   - Test fixtures under tests/fixtures/data/ if the component is a
     file reader

7. The Talend parity reference:
   - Talaxie javajet template (https://github.com/Talaxie/Talaxie) for
     the original Java code generation pattern
   - tests/talend_xml_samples/Job_<name>_*.item for an actual Talend
     job using this component
   - If the component is engine-native (Python, Swift, PythonDataFrame
     -- no Talend equivalent), note this; parity argument shifts to
     "match the documented engine-native contract"

If any of the required-reading files do not exist, HALT. Confirm with
the user that the component name is correct and the workspace is the
DataPrep repo.

# Step 1 -- State the goal in precise terms

Restate the edit as a single sentence:

  Goal: <one sentence>
  Component: <name> (<category>/<name>.py)
  Issue id (if from audit): <ID or "none">
  Scope: <behavior change / refactor / coverage fix / null>

Identify which of the following the edit will touch:
  [ ] _validate_config()
  [ ] _process()
  [ ] Helper methods on the component class
  [ ] Module-level helpers
  [ ] @REGISTRY.register decorator (alias additions only)
  [ ] Imports
  [ ] Tests
  [ ] Pipeline fixture JSON
  [ ] Converter (src/converters/...)

# Step 2 -- Investigate impact

For each item checked in Step 1, gather evidence:

a. Find every caller of any method you plan to change. Use:
     grep -rn "<method_name>" src/ tests/

b. Find every test that exercises the lines you plan to touch. Use:
     pytest tests/v1/engine/components/<category>/test_<name>.py \
       --collect-only -q

c. Find every pipeline fixture that exercises this component. Use:
     grep -rln '"type": "<TypeName>"' tests/fixtures/jobs/

d. If the edit affects schema or DataFrame shape, identify downstream
   components that depend on the output. Look at flows[] in pipeline
   fixtures.

e. If the edit involves expressions ({{java}} markers), check whether
   the component uses the Java bridge. Run:
     grep -n "java_bridge\|{{java}}" \
       src/v1/engine/components/<category>/<name>.py

f. If the audit doc lists [STILL LIVE] cross-cutting issues
   (CROSS_CUTTING_ISSUES.md sections 2.x, 3.x, 4.x, 5.x), check whether
   the proposed change touches one of those areas -- error handling,
   triggers, streaming, context resolution. If yes, surface it.

State your findings:

  Callers found: <count>
  Tests exercising the touched lines: <count>; names: <list>
  Pipeline fixtures exercising this component: <count>; names: <list>
  Downstream components affected by schema changes: <list or "none">
  Java bridge involvement: <yes / no>
  [STILL LIVE] cross-cutting issues in scope: <list or "none">

# Step 3 -- Talend parity check

Per CONTRIBUTING.md Rule 9, every behavior change needs Talend
evidence.

a. Read the Talaxie javajet template for the component (or the
   tests/talend_xml_samples/<job>.item file that exercises the same
   feature).

b. State Talend behavior for the area you plan to modify, in one
   sentence.

c. State the proposed engine behavior, in one sentence.

d. Compare. Three possible outcomes:

   - Matches Talend: proceed.
   - Engine-native (Python, Swift, PythonDataFrame components have no
     Talend equivalent): state this explicitly; the parity argument
     shifts to "match the documented engine contract per the audit
     doc."
   - Diverges from Talend: HALT. Tell the user the proposed change
     violates Rule 9 and ask whether they want to (i) match Talend
     instead, (ii) explicitly document a parity break with a roadmap
     entry, or (iii) abandon the change.

Format:

  Talend reference: <file or URL>
  Talend behavior: <one sentence>
  Proposed engine behavior: <one sentence>
  Parity verdict: <matches / engine-native / DIVERGES (HALT)>

# Step 4 -- Apply the 13 BaseComponent rules

For each rule, state explicitly whether your proposed change is
compliant. If a rule does not apply (e.g., you are not touching
_process()), state "N/A -- not touched".

  Rule 1 (extends BaseComponent or BaseIterateComponent): <yes / N/A>
  Rule 2 (_validate_config raises ConfigurationError for required
    keys): <yes / N/A>
  Rule 3 (_process returns dict with 'main' key + optional 'reject',
    'stats'): <yes / N/A>
  Rule 4 (does NOT override execute()): <yes / N/A>
  Rule 5 (reads config in _process, not __init__): <yes / N/A>
  Rule 6 (uses GlobalMap for cross-component state): <yes / N/A>
  Rule 7 (uses custom ETLError subclasses, not generic Exception):
    <yes / N/A>
  Rule 8 (uses logger, not print): <yes / N/A>
  Rule 9 (registered via @REGISTRY.register with all Talend aliases):
    <yes / N/A>
  Rule 10 (component works after reset()): <yes / N/A>
  Rule 11 (does NOT call self.validate_schema() inside _process):
    <yes / N/A>
  Rule 12 (_validate_config checks key presence / shape only, never
    content -- content checks belong in _process): <yes / N/A>
  Rule 13 (registry membership AND abstract methods present): <yes /
    N/A>

If any rule is violated, HALT. Rewrite the proposal until it complies.

# Step 5 -- Apply the load-bearing project rules

  Rule 1 (ASCII-only): your edit contains no emoji, smart quotes,
    em-dashes (--), or non-ASCII characters? <yes / no>
  Rule 2 (custom exception hierarchy): every raise statement uses an
    ETLError subclass with [{self.id}] prefix? <yes / N/A>
  Rule 3 (fix source, no fallbacks): your edit does NOT add a
    defensive shim downstream of bad data? <yes / no>
  Rule 4 (atomic commits): you can describe the edit as ONE logical
    change? <yes / no>
  Rule 6 (95% per-module line coverage floor): you have or will add
    tests covering every new line of code? <yes / no>
  Rule 7 (dead-code policy): if the edit removes a branch, you are
    DELETING it (not pragma-ing)? <yes / N/A>
  Rule 8 (pipeline tests for lifecycle-sensitive modules): if the
    component is in engine.py / base_component.py /
    base_iterate_component.py / trigger_manager.py /
    java_bridge_manager.py / any file I/O component, you have or will
    add a pipeline-fixture test? <yes / N/A>
  Rule 10 (converter JSON FROZEN): your edit does NOT rename or remove
    any existing config key, and does NOT change the semantics of any
    existing key? <yes / N/A>

If any rule is violated, HALT. Rewrite or abandon.

# Step 6 -- Propose the edit as a diff (do NOT apply yet)

Present the proposed change as a unified diff. For each file:

  File: <path>
  Lines: <range>
  Rationale: <one sentence tying back to the goal>

  ```diff
  <unified diff>
  ```

If the edit is large (more than ~50 lines), break it into atomic
commits per Rule 4. State each commit with its own diff block and
proposed commit message.

For test additions:

  Test file: <path>
  New test(s): <list of test function names>
  Coverage delta: <which lines this test now covers>

# Step 7 -- Confirm with the user

ASK THE USER for explicit approval. Phrasing:

  Proposed edit above. Apply? (y/n)
  If yes, I will:
  1. Apply the diff(s)
  2. Run the unit tests for the affected component
  3. Run the coverage gate locally
  4. Commit atomically per Rule 4

Do not proceed without an affirmative answer.

# Step 8 -- Apply, test, commit

Once approved:

a. Apply the diffs in the order presented.

b. Run the unit + pipeline tests for the affected component:
     python -m pytest tests/v1/engine/components/<category>/test_<name>.py -v
     # If lifecycle-sensitive, also run pipeline fixtures:
     python -m pytest tests/integration/ -k "<name>" -v

c. Run the coverage gate (full command is in CLAUDE.md "Coverage"):
     rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
       --cov=src/v1/engine --cov=src/converters \
       --cov-report=term-missing --cov-report=html --cov-report=json \
       && python scripts/check_per_module_coverage.py coverage.json --floor 95

   The gate MUST exit 0. If it fails on the touched module, the edit is
   missing test coverage -- add tests before committing.

d. Commit per Rule 4. Format:
     <type>(<scope>): <one-line description>

   Examples:
     fix(engine): tFilterRow null-aware GREATER comparison (FROW-04)
     feat(15.x): tMap support for additional output table count
     refactor(engine): aggregate_row decimal precision helper extraction
     test(engine): pipeline fixture for tJoin INNER JOIN reject routing

e. If the edit touches multiple files (component + test + fixture),
   produce one commit per logical change unless they form a single
   atomic unit (e.g., a bugfix + its regression test).

# Step 9 -- Verify and report

After committing:

a. Re-run the coverage gate to confirm no module dropped below the 95%
   floor.

b. Confirm git log shows the atomic commit(s) with correct format.

c. Produce a short report:

  Component: <name>
  Goal: <from Step 1>
  Files changed: <count>
  Tests added: <count>
  Coverage gate: <pass / fail>
  Commit(s): <hash(es)>
  Talend parity: <confirmed / engine-native>
  [STILL LIVE] issue closed: <ID or "none">

# Hard rules

- NEVER edit component source before Step 7 user approval.
- NEVER violate the 13 BaseComponent rules. If a violation is required
  to achieve the goal, the goal is wrong.
- NEVER add a defensive fallback ("if x is None, x = ''"). Fix the
  producer (Rule 3).
- NEVER add a # pragma: no cover annotation (Rule 7).
- NEVER rename or remove a config key (Rule 10). Add new optional keys
  only.
- NEVER raise generic Exception / RuntimeError / ValueError (Rule 2).
- NEVER use --no-verify on a commit.
- NEVER bundle multiple logical changes into one commit (Rule 4).
- NEVER edit STATE.md or ROADMAP.md as part of a component change.
- NEVER edit a doc under docs/v1/audit/ as part of a component change
  -- audit docs are updated only by audit reconciliation phases
  (Phase 15.1 style).
- If Talend parity cannot be verified in Step 3 and the component is
  not engine-native, HALT.
- If a rule in Step 4 or Step 5 is violated, HALT.
- If the coverage gate fails in Step 8c, do NOT commit. Add tests first.

# Tone and style

- Be terse. The user wants the diff, not a tutorial.
- Cite file:line references for every claim.
- If you are uncertain about Talend behavior, say so explicitly. Do
  not invent behavior.
- Use ASCII only in code, commit messages, and chat responses. The user
  runs on RHEL.
- Match the existing code's style -- 4-space indent, double quotes,
  snake_case modules, PascalCase classes, %-style or f-string logging
  consistently with neighboring code.
</prompt>
```

---

## See Also

- `docs/CONTRIBUTING.md` -- the 10 load-bearing project rules
- `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` -- the 13 BaseComponent subclassing rules
- `docs/ai-prompts/DEBUG_JOB_FAILURE.md` -- companion prompt for runtime failures
- `docs/ai-prompts/CREATE_COMPONENT.md` -- companion prompt for net-new components
- `docs/v1/audit/CROSS_CUTTING_ISSUES.md` -- `[STILL LIVE]` items that may need component edits
- `docs/ARCHITECTURE.md` -- engine layers and component contracts
