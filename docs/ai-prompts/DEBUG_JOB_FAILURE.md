# AI Prompt: Debug a Failing DataPrep Job

*Last updated: 2026-05-11*
*Audience: AI coding assistant (Claude Code, GitHub Copilot, Cursor, etc.)*

---

## How to use this prompt

Paste the contents of the `<prompt>` block below into your AI assistant
together with the failing job's JSON path, the engine command that was
run, and the full traceback. The prompt forces the assistant to
investigate before editing. Do not delete or soften the HALT clauses --
they are the guardrails that stop the assistant from "fixing" a symptom
by patching the wrong component.

---

## When to use this prompt vs. just asking the assistant

| Situation | Use this prompt? |
|-----------|-------------------|
| `python src/v1/engine/engine.py job.json` raised an exception | **Yes** |
| A job produced wrong output silently (no exception) | **Yes** -- this counts as a failure |
| A test failed under `pytest` and you suspect a component bug | **Yes** -- treat the test as the reproduction step |
| You want to add a new feature | No -- use `EDIT_COMPONENT.md` or `CREATE_COMPONENT.md` |
| The error is clearly in user-supplied JSON shape (e.g., `KeyError: 'flows'`) | No -- fix the JSON; this prompt is for engine / component bugs |

---

## What this prompt enforces

1. **No edits before reproduction.** The assistant must reproduce the
   failure locally and confirm the error matches the user's report
   before doing anything else.
2. **Classify the error first.** The exception class
   (`ConfigurationError` vs. `DataValidationError` vs.
   `ComponentExecutionError` vs. plain `Exception`) determines where the
   bug lives. Skipping classification leads to fixing the wrong file.
3. **Talend parity check is mandatory if any source change is proposed.**
   Per `docs/CONTRIBUTING.md` Rule 9, every component change needs a
   Talend reference cited.
4. **No silent fallbacks.** Per `docs/CONTRIBUTING.md` Rule 3, the fix
   goes at the source of the bad data, not in a defensive downstream
   shim.

---

## The prompt

```
<prompt>
You are debugging a failure in the DataPrep ETL engine. Your goal is to
PRODUCE A DIAGNOSIS, not a fix. Editing component source code is the
LAST step, not the first.

# Inputs the user will give you

- Path to the job JSON that failed (e.g., /tmp/orders.json)
- The exact engine command that was run
- The full traceback or wrong-output description

# Required reading before any other action

Read these in order. Do not skip any. Confirm to the user that you have
read each one before proceeding.

1. /Users/aarun/Workspace/Projects/dataprep/CLAUDE.md sections "Error
   Handling", "Architecture", "Logging".
2. /Users/aarun/Workspace/Projects/dataprep/docs/CONTRIBUTING.md Rules
   1-5 (load-bearing project rules; debug behavior must respect them).
3. /Users/aarun/Workspace/Projects/dataprep/docs/ARCHITECTURE.md
   sections "Engine Component Layer", "Data Flow", "Registry
   Discipline".
4. /Users/aarun/Workspace/Projects/dataprep/src/v1/engine/exceptions.py
   (the full exception taxonomy you will classify against).
5. The failing component's source file under
   src/v1/engine/components/<category>/<name>.py.
6. The failing component's audit doc under
   docs/v1/audit/components/<category>/<name>.md (current state of
   issues, [STILL LIVE] items, prior bug history).

If any of the files above are not present in the repo, HALT and tell the
user that the workspace is not the DataPrep repo or is at a wrong commit.

# Step 1 -- Reproduce

a. Confirm the venv is active and the Python interpreter is 3.10+:
     python --version
b. Run the exact command the user provided. Capture the traceback to a
   temp file:
     <user command> 2>&1 | tee /tmp/dataprep_repro.log
c. Diff the captured traceback against the one the user reported. If
   they do not match:
     - HALT.
     - Tell the user the local reproduction does not match. Ask whether
       the failure is environment-specific, intermittent, or whether the
       JSON they shared is different from the one they ran.
d. If the user reports wrong output (no exception), reproduce the
   wrong-output condition by examining the produced data file vs. the
   expected. Capture the diff to /tmp/dataprep_repro.log.

DO NOT MOVE TO STEP 2 UNTIL YOU CAN RELIABLY REPRODUCE THE FAILURE
LOCALLY.

# Step 2 -- Classify

From the traceback, identify the exception class and the component id
that raised. Match against this table:

| Exception class            | Where the bug usually lives                                                             |
|----------------------------|------------------------------------------------------------------------------------------|
| ConfigurationError         | Missing or malformed config key in the JSON, OR a too-strict _validate_config check     |
| DataValidationError        | Schema mismatch between flows, OR data with the wrong type, OR a null where non-nullable|
| ComponentExecutionError    | Component _process() raised. Look at the .cause attribute for the real exception.       |
| FileOperationError         | I/O. Permissions, missing path, encoding mismatch, lockfile contention.                 |
| JavaBridgeError            | The bridge JAR is missing, JVM is wrong version, or the Java/Groovy expression failed.  |
| ExpressionError            | A {{java}} marker or context resolution failed inside an expression.                    |
| SchemaError                | Output schema does not match downstream input schema.                                   |
| TriggerEvaluationError     | A RunIf condition or trigger expression failed to evaluate.                             |
| plain Exception / KeyError | This is a bug -- the engine should always raise an ETLError subclass. Treat as Rule 2 violation. |

State the classification explicitly:

  Classification: <Exception class>
  Failing component: <id> (<type>) in <category>/<name>.py
  Root location hypothesis: <one sentence>

# Step 3 -- Investigate

For each hypothesis, gather evidence BEFORE proposing a fix:

a. Read the failing component's _process() and _validate_config() in
   full. Note which lines could raise the observed exception.
b. Read the component's pipeline tests under
   tests/v1/engine/components/<category>/test_<name>.py. Identify which
   tests exercise the failing code path. If the failing path has no
   test, that is your reproduction gap.
c. Read the converter for the same component
   (src/converters/talend_to_v1/components/<category>/<name>.py) if the
   bug might be in the JSON shape produced by conversion.
d. Run the engine in debug mode to surface intermediate state:
     python -c "import logging; logging.basicConfig(level=logging.DEBUG); \\
       from src.v1.engine.engine import run_job; run_job('<job.json>')"
e. If the failure is in tMap or any Java-evaluated component, also check
   the Java bridge state -- the bridge logs go to stderr at INFO+.

State your findings. Use this format:

  Evidence collected:
  - <fact 1 with file:line reference>
  - <fact 2 with file:line reference>
  - <fact 3 with file:line reference>

  Most likely root cause: <one-sentence hypothesis>
  Confidence: <low / medium / high>
  Alternative hypotheses still on the table: <list>

# Step 4 -- Talend parity check (MANDATORY if you intend to propose a code edit)

Per docs/CONTRIBUTING.md Rule 9, every component change must be backed
by a Talend reference.

a. Identify the Talaxie javajet template for this component
   (https://github.com/Talaxie/Talaxie or the local
   tests/talend_xml_samples/ fixtures).
b. Confirm the proposed fix matches Talend behavior. If Talend has the
   bug too, the fix is "match Talend" -- not "fix it better".
c. If you cannot find Talend source for the component or the behavior
   is engine-native (Python, Swift, PythonDataFrame components), state
   that explicitly. The audit doc's "Talend Side" section is the prior
   reference.

State:

  Talend reference: <file or URL>
  Talend behavior: <one sentence>
  Proposed fix matches Talend: <yes / no / engine-native, no Talend
    equivalent>

# Step 5 -- Propose the fix (do NOT apply it yet)

Write the proposed fix as a diff. State which file changes, which lines,
and which BaseComponent rule (CONTRIBUTING.md Rules 1-10 or
MANUAL_COMPONENT_AUTHORING.md Rules 1-13) is being honored.

If your proposed fix involves a defensive shim downstream of the bad
data ("if x is None, treat as empty"), STOP. Per Rule 3, the fix lands
at the producer. Re-investigate.

If your proposed fix changes the converter JSON output shape (e.g.,
renames a config key), STOP. Per Rule 10, the JSON contract is FROZEN.
Add a new optional key; do not rename existing ones.

Present the fix as:

  File: <path>
  Lines: <range>
  Diff:
  ```
  <unified diff>
  ```
  Rule honored: <Rule N from CONTRIBUTING or Rule N from MANUAL_COMPONENT_AUTHORING>
  Talend parity: <statement from Step 4>

# Step 6 -- Confirm with the user, then apply

ASK THE USER for explicit approval before editing. The phrasing must be:

  Proposed fix above. Apply? (y/n)

If the user says yes:
a. Apply the diff.
b. Write a failing test FIRST that reproduces the bug, then re-run -- the
   test should now pass. If the test already exists in the suite,
   confirm the fix did not break it.
c. Run the full test suite filtered to the affected component:
     python -m pytest tests/v1/engine/components/<category>/test_<name>.py -v
d. Run the coverage gate locally (the command is in CLAUDE.md
   "Coverage").
e. Commit atomically per Rule 4. Format:
     fix(<phase or scope>): <one-line description> (BUG-<ticket> if exists)

   Examples (from Phase 14):
     fix(14-09): file_input_json missing _validate_config (BUG-FIJ-001)
     fix(engine): tMap row context wrong column order on RELOAD_AT_EACH_ROW

If the user says no, stop. Do not edit.

# Step 7 -- Report

Produce a short report:

  Failure reproduced: yes
  Classification: <from Step 2>
  Root cause: <one sentence>
  Fix: <one sentence; file:lines>
  Talend parity: <confirmed / engine-native>
  Tests: <added / updated / count>
  Coverage gate: <pass / fail>

# Hard rules

- NEVER edit component source before Step 6 user approval.
- NEVER add a # pragma: no cover annotation (CONTRIBUTING.md Rule 7).
- NEVER raise generic Exception / RuntimeError / ValueError from
  component code (Rule 2). Use the ETLError hierarchy.
- NEVER add an emoji or non-ASCII character to code, logs, or docs
  (Rule 1).
- NEVER use --no-verify on a commit.
- NEVER bundle unrelated changes -- one logical change per commit
  (Rule 4).
- If the proposed fix requires changing JSON config keys, HALT and tell
  the user this is breaking Rule 10. They must explicitly opt into the
  migration.
- If you cannot reproduce the failure in Step 1, HALT. Do not guess.
- If you cannot find Talend parity evidence in Step 4 and the component
  is not engine-native, HALT. The user must confirm Talend behavior
  manually.

# Tone and style

- Be terse. The user wants the diagnosis, not commentary.
- Cite file:line references for every claim.
- If you are uncertain, say so. State your confidence level explicitly.
- Do not produce a fix and a follow-up rationale on the same turn; the
  rationale lives in the commit message body or PR description.
</prompt>
```

---

## See Also

- `docs/CONTRIBUTING.md` -- the 10 load-bearing rules cited throughout the prompt
- `docs/ai-prompts/EDIT_COMPONENT.md` -- for non-debug component edits (refactors, parity gaps surfaced outside a failing run)
- `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` -- the 12+13 BaseComponent rules
- `docs/ARCHITECTURE.md` -- engine execution pipeline + exception taxonomy
- `src/v1/engine/exceptions.py` -- the exception hierarchy the classification step uses
