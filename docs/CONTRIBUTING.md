# Contributing to DataPrep
*Last updated: 2026-05-11*

## Audience

This guide is for human contributors writing or modifying the DataPrep engine, the
Talend-to-V1 converter, or the test suite. Claude-driven contributors read `CLAUDE.md`
first (codebase rules, conventions, architecture) and then this file for the
load-bearing project rules and the cross-references that pull everything together.

`CLAUDE.md` is the source of truth for codebase rules. This file REFERENCES `CLAUDE.md`
by section name -- it does not duplicate the content. When a section here says
"see CLAUDE.md X" go read CLAUDE.md X.

This file owns: the 10 load-bearing rules + git workflow. Other workflow content lives in:
- `docs/guides/DEV_SETUP.md` -- environment setup, test commands, coverage gate invocation
- `docs/guides/QUICKSTART.md` -- run a job end-to-end in 5 minutes
- `docs/guides/AUTHORING_JOB_JSON.md` -- write job JSON by hand without a Talend source
- `docs/ai-prompts/CREATE_COMPONENT.md` -- step-by-step new-component authoring
- `docs/ai-prompts/EDIT_COMPONENT.md` -- safe edits to existing components
- `docs/ai-prompts/DEBUG_JOB_FAILURE.md` -- diagnose a failing job

## Project Rules (Load-Bearing)

These ten rules are the load-bearing rules of the project. They have been earned the
hard way -- most of them are pinned by a Phase 14 BUG or a user-memory note. Violate
them and CI, code review, or production will reject the change.

### Rule 1: ASCII-only logs and docs

- No emoji, no smart quotes, no en/em dashes anywhere in source, logs, or docs. Use
  the ASCII double-hyphen `--` for ranges and parentheticals.
- User memory: `feedback_ascii_logging`. The RHEL production servers parse these
  logs; non-ASCII bytes corrupt downstream tooling.
- Test enforcement: tests that exercise log-emitting paths use
  `tests/conftest.py::assert_ascii_logs` to fail on any non-ASCII byte in captured
  log records.

### Rule 2: Custom exception hierarchy

- Never raise generic `Exception`, `RuntimeError`, or `ValueError` from component
  code. The hierarchy lives at `src/v1/engine/exceptions.py` and is rooted at
  `ETLError`. See CLAUDE.md "Error Handling" for the full taxonomy.
- Pick the specific subclass: `ConfigurationError` for invalid config,
  `FileOperationError` for I/O failures, `ComponentExecutionError` for runtime
  failures the engine catches and tracks, etc.
- Always prefix error messages with `[{self.id}]` so log readers can correlate the
  message to the failing component.

### Rule 3: Fix source, no fallbacks

- User memory: `feedback_fix_source_no_fallbacks`. Phase 14 closed 11+ BUG-* tickets
  by patching root causes, not by adding defensive shims.
- When a downstream consumer sees bad data, fix the producer. Do not paper over the
  problem with `if x is None: x = ""` or "graceful degradation" branches.
- Defensive shims hide bugs from tests and hide the failure from the on-call. The
  engine should fail loudly on bad inputs.

### Rule 4: Atomic commits per file

- One logical change per commit. Phase 14 shipped roughly 88 commits across 12
  plans, each tightly scoped. The reviewer should be able to read the diff and the
  subject in under a minute.
- Squash-merging an unfocused branch is harder than landing five focused commits.
  When in doubt, commit smaller.

### Rule 5: BaseComponent abstract methods AND registry membership are MANDATORY

This rule is the LOAD-BEARING lesson from Phase 14. Read it twice.

- Every subclass of `BaseComponent` (`src/v1/engine/base_component.py`) MUST be
  decorated with `@REGISTRY.register("PascalCaseName", "tTalendName", ...)` from
  `src/v1/engine/component_registry.py` AND MUST implement `_validate_config()`
  raising `ConfigurationError` on missing required config keys.
- The ABC declares `_validate_config` and `_process` as `@abstractmethod`. Python
  refuses to instantiate a class that misses either; the runtime crash is loud but
  late.
- The registry is decorator-driven (`@REGISTRY.register`). A subclass that imports
  cleanly but lacks the decorator is silently dropped: at execution time the engine
  emits "Unknown component type" and moves on. The class is unreachable.
- **Why this rule is LOAD-BEARING**: Phase 14 surfaced four bug pairs of exactly
  this shape -- BUG-PDC-001/002 (python_dataframe_component), BUG-SWIFT-001..005
  (swift_transformer and swift_block_formatter), and BUG-FIJ-001/002
  (file_input_json). In each case a subclass was importable but unusable. Three
  different plans hit it independently before Plan 14-12 made it a checklist item.
- See `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` for the full authoring
  contract (the 13 rules of BaseComponent subclassing).

### Rule 6: 95% per-module line coverage floor

- Every module under `src/v1/engine/` and `src/converters/` (excluding the legacy
  `complex_converter/` tree) must clear 95.0% line coverage.
- Paste-runnable gate: see CLAUDE.md "Coverage" section for the full pytest +
  `scripts/check_per_module_coverage.py` invocation. Run it locally before pushing.
  `docs/guides/DEV_SETUP.md` walks through it step-by-step.
- The gate script is `scripts/check_per_module_coverage.py`. It reads
  `coverage.json` and exits non-zero on any module below the floor.
- Source of truth for the in-scope module set and the pragma allowlist:
  `pyproject.toml` `[tool.coverage.run]` `omit` and `[tool.coverage.report]`
  `exclude_also`.
- Inline `# pragma: no cover` annotations are FORBIDDEN inside scope. Coverage
  exclusions go through the `exclude_also` regex allowlist
  (`__main__`, `@abstractmethod`, `raise NotImplementedError`) only.

### Rule 7: Dead-code policy (D-C5)

- Prefer DELETE over a `# pragma: no cover` annotation. If a branch cannot be
  reached, remove it.
- Phase 14 deleted 12+ unreachable branches across the engine and converter. The
  deletion is reversible via git; the live source stays cleaner; coverage rises
  organically; nobody has to defend a `pragma: no cover` in review.
- Exception: the `exclude_also` regex allowlist documented in CLAUDE.md "Coverage"
  covers `__main__` blocks, `@abstractmethod` stubs, and `raise NotImplementedError`
  scaffolding. Everything else: delete it.

### Rule 8: Pipeline tests for lifecycle-sensitive modules

- For modules that participate in the engine lifecycle (engine.py, base_component,
  base_iterate_component, trigger_manager, java_bridge_manager, all file I/O
  components), unit tests with mocked dependencies are not enough. Write pipeline
  tests using the `run_job_fixture` fixture from `tests/conftest.py` plus a
  job-config JSON under `tests/fixtures/jobs/{subsystem}/{behavior}.json`.
- Mock-only tests pass even when the component class is unregistered or fails
  abstract-method checks at instantiation. Pipeline tests exercise the full path:
  registry lookup, ABC check, `_validate_config`, `_process`, output schema. The
  Phase 14 BUG-PDC, BUG-SWIFT, and BUG-FIJ failures all slipped through mock-only
  test suites.
- See `tests/fixtures/jobs/README.md` for the pipeline-fixture authoring format.
- For SWIFT-specific tests, see `tests/fixtures/swift/` and the synthetic MT
  generator helpers.

### Rule 9: Talend feature parity is non-negotiable

- Any Talend job using a supported component MUST produce identical results when
  run through the Python engine. "Mostly compatible" is not compatible. This is
  pinned in CLAUDE.md "Project / Core Value".
- New features and bug fixes MUST be backed by a Talend `.item` or `_java.xml`
  reference. Cite the Talend source file (or component documentation entry) in the
  PR description so the reviewer can verify parity intent.
- If you discover divergence from Talend behavior, the default fix is "match
  Talend" -- not "improve on Talend".

### Rule 10: Converter JSON format is FROZEN

- Engine changes must not require re-conversion of existing JSONs. The roughly
  1200 production jobs have already been converted; the JSON output of the
  converter is the long-lived contract.
- Adding new optional config keys to a component is fine. Renaming, removing, or
  changing the semantics of an existing key is BREAKING.
- If you genuinely need a breaking change, raise it explicitly in the PR
  description as a migration item; do not slip it in.

## Workflow

### Authoring a new component

Use `docs/ai-prompts/CREATE_COMPONENT.md` to drive the 8-step Talaxie-diff
workflow (audit -> Talaxie research -> feature parity -> plan -> review -> code
-> verify -> close). The prompt enforces the 13 BaseComponent rules
(MANUAL_COMPONENT_AUTHORING.md) and the project rules above.

If you are working without an AI assistant, the same canonical references apply:
- `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` -- the 13 BaseComponent rules
  + long-form authoring detail
- `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` -- engine-side pattern
- `docs/v1/patterns/CONVERTER_PATTERN.md` -- converter-side pattern
- `docs/v1/patterns/ENGINE_TEST_PATTERN.md` -- test layout and fixture conventions

### Editing an existing component

Use `docs/ai-prompts/EDIT_COMPONENT.md`. The prompt enforces Talend parity
checks, the 13 BaseComponent rules, and Rule 10 (JSON FROZEN).

### Fixing a bug

Use `docs/ai-prompts/DEBUG_JOB_FAILURE.md`. The prompt enforces reproduction +
classification before any code edit. Manual version:

1. Reproduce the bug with a failing test FIRST. If the bug is in a
   lifecycle-sensitive module, the failing test should be a pipeline-fixture test
   per Rule 8, not a mock-only unit test.
2. Patch the root cause. Apply Rule 3 -- no downstream fallback shims.
3. Run the full test suite and the coverage gate to verify no regressions and no
   coverage drift on neighboring modules.
4. Commit atomically: one commit for the failing test (so the bisect log is clean),
   one for the fix. Reference the BUG-* ticket id in the commit body when one
   exists.

### Modifying conventions

The conventions live in `CLAUDE.md` (sections "Naming Patterns", "Code Style",
"Import Organization", "Comments", "Function Design", "Module Design"). This file
references them; it does not own them. CLAUDE.md edits are a separate concern
from a feature PR -- do not bundle a CLAUDE.md change into a feature branch.
Raise convention changes as their own PR with an explicit rationale.

## Style

Conventions live in CLAUDE.md "Conventions" (covering "Naming Patterns",
"Code Style", "Import Organization", "Comments", "Function Design", and
"Module Design"). Highlights for quick reference:

- `snake_case.py` for module names, `PascalCase` for classes, `_` prefix for
  private methods and module-level helpers, `UPPER_SNAKE_CASE` for constants.
- 4-space indent, double-quoted strings preferred, type hints on public function
  signatures, no automated formatter is wired up so be consistent with neighboring
  code.
- One logger per module: `logger = logging.getLogger(__name__)` at module top.
- Custom exceptions only -- see Rule 2 above.
- ASCII-only -- see Rule 1 above and CLAUDE.md "Logging".

## Git Workflow

### Branch naming

- `feature/<short-name>` -- new components, new features
- `fix/<short-name>` -- bug fixes
- `docs/<short-name>` -- documentation-only changes
- `chore/<short-name>` -- tooling, infra, repo hygiene

### Commit messages

Format: `type(scope): short description`

- `type` is one of `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
- `scope` is the phase id when working a planned phase (e.g., `15-04`) or the
  subsystem (`engine`, `converter`, `tests`, `docs`).
- Subject line stays under roughly 72 characters. Wrap the body at 72.
- Use the body to explain the "why" and to cite BUG-* ids or phase plan
  references when applicable.

Examples drawn from Phase 14:

- `docs(14-12): complete closeout plan -- Phase 14 verified Complete`
- `feat(14-07): SWIFT synthetic MT generator + 5 BUG-SWIFT root-cause fixes`
- `fix(14-09): file_input_json missing _validate_config (BUG-FIJ-001)`

### PR process

TBD by the project manager. This section stays minimal until the team formalizes
a PR template under `.github/PULL_REQUEST_TEMPLATE.md`. For now, push the branch,
open the PR, link the phase plan or BUG ticket in the description, and request a
review.

## See Also

- `CLAUDE.md` -- codebase and Claude-specific instructions; section anchors
  ("Error Handling", "Logging", "Coverage", "Conventions", "Architecture") are
  referenced throughout this file.
- `docs/ARCHITECTURE.md` -- system architecture overview
- `docs/COMPONENT_REFERENCE.md` -- registry-driven component inventory
- `docs/DEPLOYMENT.md` -- runtime requirements and production deployment notes
- `docs/guides/DEV_SETUP.md` -- local dev environment, test commands, coverage gate
- `docs/guides/QUICKSTART.md` -- end-to-end 5-minute walkthrough
- `docs/guides/AUTHORING_JOB_JSON.md` -- hand-write job JSON without a Talend source
- `docs/ai-prompts/CREATE_COMPONENT.md` -- AI prompt for new components
- `docs/ai-prompts/EDIT_COMPONENT.md` -- AI prompt for safe component edits
- `docs/ai-prompts/DEBUG_JOB_FAILURE.md` -- AI prompt for diagnosing failures
- `docs/v1/patterns/` -- detailed authoring guides (MANUAL_COMPONENT_AUTHORING,
  ENGINE_COMPONENT_PATTERN, CONVERTER_PATTERN, ENGINE_TEST_PATTERN)
- `tests/fixtures/jobs/README.md` -- pipeline-fixture authoring guide cited from Rule 8
- `scripts/check_per_module_coverage.py` -- the 95% per-module floor gate
  enforced by Rule 6
