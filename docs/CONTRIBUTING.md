# Contributing to DataPrep
*Last updated: 2026-05-11*

## Audience

This guide is for human contributors writing or modifying the DataPrep engine, the
Talend-to-V1 converter, or the test suite. Claude-driven contributors read `CLAUDE.md`
first (codebase rules, conventions, architecture) and then this file for the
human-facing process bits that `CLAUDE.md` does not cover: workflow recipes, test
commands, git etiquette, and the cross-references that pull everything together.

`CLAUDE.md` is the source of truth for codebase rules. This file REFERENCES `CLAUDE.md`
by section name -- it does not duplicate the content. When a section here says
"see CLAUDE.md X" go read CLAUDE.md X.

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
  contract (lands in plan 15-09; until then, see `docs/v1/STANDARDS.md` for the
  predecessor doc).

### Rule 6: 95% per-module line coverage floor

- Every module under `src/v1/engine/` and `src/converters/` (excluding the legacy
  `complex_converter/` tree) must clear 95.0% line coverage.
- Paste-runnable gate: see CLAUDE.md "Coverage" section for the full pytest +
  `scripts/check_per_module_coverage.py` invocation. Run it locally before pushing.
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

1. Read the authoring pattern doc: `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md`
   (lands in plan 15-09; until then `docs/v1/STANDARDS.md` is the closest standing
   guide).
2. Subclass `BaseComponent` (or `BaseIterateComponent` for iterate-style
   components -- see CLAUDE.md "Key Abstractions").
3. Decorate the class with `@REGISTRY.register("PascalCaseName", "tTalendName")`
   from `src/v1/engine/component_registry.py`. List every Talend alias the
   component should accept (see existing examples like `oracle_connection.py`).
4. Implement `_validate_config()` raising `ConfigurationError` for every required
   config key. Implement `_process()` returning `{"main": df, "reject": df_or_None,
   "stats": {...}}`.
5. Add unit tests for the component class AND a pipeline-fixture test under
   `tests/fixtures/jobs/{subsystem}/` per Rule 8.
6. Run the coverage gate (CLAUDE.md "Coverage"). New code must clear the 95% floor
   on its own module.
7. Commit atomically per Rule 4 -- one commit for the class, one for tests if
   they are large, one for the fixture JSON if it stands on its own.

### Fixing a bug

1. Reproduce the bug with a failing test FIRST. If the bug is in a
   lifecycle-sensitive module, the failing test should be a pipeline-fixture test
   per Rule 8, not a mock-only unit test.
2. Patch the root cause. Apply Rule 3 -- no downstream fallback shims. The
   producer of the bad value is where the fix lands.
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

## Tests

### Test inventory

- `tests/v1/engine/` -- engine and component unit / pipeline tests
- `tests/converters/talend_to_v1/` -- converter unit and integration tests
- `tests/integration/` -- end-to-end conversion + execution tests
- `tests/fixtures/jobs/` -- JSON job configs consumed by `run_job_fixture`
- `tests/fixtures/data/` -- input data files (CSV, Excel, JSON, XML) for pipeline tests
- `tests/fixtures/swift/` -- SWIFT MT message fixtures and YAML configs
- `tests/conftest.py` -- shared fixtures (`run_job_fixture`, `assert_ascii_logs`)

### Running tests

- Full suite (excluding the live Oracle path):
  `python -m pytest tests/ -m "not oracle" -n auto`
- Engine-only:
  `python -m pytest tests/v1/engine/ -n auto`
- Java bridge tests (requires JVM 11+ on PATH and the bridge JAR built):
  `python -m pytest tests/ -m java`
- Live Oracle tests (opt-in only; CI does not run these):
  `python -m pytest tests/ -m oracle`
- Parallel runner: pass `-n auto` to xdist for the full suite; serial for targeted
  debugging.

### Coverage

The coverage gate is documented in CLAUDE.md "Coverage" -- run the paste-runnable
command from that section to regenerate `coverage.json` and enforce the 95%
per-module floor via `scripts/check_per_module_coverage.py`. `coverage.json` and
`htmlcov/` are gitignored at the project root; per-phase acceptance artifacts
(for example, `14-coverage.json`) are committed under
`.planning/phases/{N}-{name}/` for historical reference.

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
- `docs/ARCHITECTURE.md` -- system architecture overview (landing later in
  Phase 15).
- `docs/COMPONENT_REFERENCE.md` -- registry-driven component inventory (landing
  later in Phase 15).
- `docs/DEPLOYMENT.md` -- runtime requirements and deployment notes (landing
  later in Phase 15).
- `docs/v1/patterns/` -- detailed authoring guides (post-rename location;
  landing in plan 15-09; predecessor is `docs/v1/STANDARDS.md`).
- `tests/fixtures/jobs/README.md` -- pipeline-fixture (job-config JSON) authoring
  guide, cited from Rule 8.
- `scripts/check_per_module_coverage.py` -- the 95% per-module floor gate
  enforced by Rule 6.
