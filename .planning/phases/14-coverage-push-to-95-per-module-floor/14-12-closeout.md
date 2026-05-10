---
phase: 14
plan: 12
slug: closeout
type: execute
wave: 3
depends_on: [14-01, 14-02, 14-03, 14-04, 14-05, 14-06, 14-07, 14-08, 14-09, 14-10, 14-11]
files_modified:
  - .planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md       # NEW
  - .planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json     # NEW (per locked Q4)
  - .planning/phases/14-coverage-push-to-95-per-module-floor/14-VERIFICATION.md   # NEW
  - .planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md  # NEW
  - CLAUDE.md                          # update §Coverage with new gate command
  - .planning/REQUIREMENTS.md          # add TEST-11, TEST-12 with Complete status
  - .planning/ROADMAP.md               # update Phase 14 SC#2 per D-E1; flip to Complete
  - .planning/STATE.md                 # mark Phase 14 complete
autonomous: false  # final manual checkpoint to confirm gate command runs clean
requirements: [TEST-11, TEST-12]
must_haves:
  truths:
    - "Final gate command exits 0 from a clean working tree (`rm -f .coverage* && pytest ... && check_per_module_coverage.py`)"
    - "All 198 in-scope modules at >= 95% line coverage in coverage.json"
    - "No regression: every module currently >=95% (per Phase 13 baseline) is still >=95%"
    - "iterate/context modules (per locked Q2 merge) remain >=95% (no-regression check)"
    - "14-COVERAGE.md exists with final per-module table"
    - "14-coverage.json committed (per locked Q4)"
    - "CLAUDE.md §Coverage documents the locked gate command"
    - "REQUIREMENTS.md lists TEST-11 and TEST-12 with status Complete"
    - "ROADMAP.md Phase 14 reflects D-E1 amended SC#2 wording and is marked Complete"
    - "STATE.md updated"
    - "14-VERIFICATION.md and 14-PHASE-SUMMARY.md exist with retrospective + acceptance evidence"
  artifacts:
    - path: .planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md
      provides: final per-module post-lift coverage table mirroring Phase 13 baseline format
    - path: .planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json
      provides: machine-readable coverage artifact (per locked Q4)
    - path: .planning/phases/14-coverage-push-to-95-per-module-floor/14-VERIFICATION.md
      provides: acceptance evidence -- final gate run output, regression check log, all D-C3/D-C5 outcomes
    - path: .planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md
      provides: phase retrospective; lessons; final state
  key_links:
    - from: CLAUDE.md §Coverage
      to: 14-COVERAGE.md
      via: same paste-runnable command + per-module floor reference
    - from: REQUIREMENTS.md TEST-11/TEST-12
      to: 14-COVERAGE.md (delivered artifact)
      via: traceability table marks both Complete after gate green
---

<objective>
Close out Phase 14: run the final gate, generate `14-COVERAGE.md`, commit `coverage.json` (locked Q4), update CLAUDE.md / REQUIREMENTS.md / ROADMAP.md / STATE.md, write `14-VERIFICATION.md` and `14-PHASE-SUMMARY.md`. Includes the no-regression check that originally would have been Plan 14-04 (iterate / context already >= 95% -- per locked Q2 merge). Final manual checkpoint: user verifies gate command runs clean from project root before phase is closed.
</objective>

<scope>
- Run the final gate command from a clean working tree.
- Capture per-module coverage from `coverage.json`; render as a markdown table mirroring `13-COVERAGE-BASELINE.md` format.
- Commit `coverage.json` to `.planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json` (locked Q4 deviation from researcher recommendation).
- Update CLAUDE.md §"Coverage" with the new locked gate command (the `rm -f .coverage*` prefix per locked Q5; the `-m "not oracle"`, `-n auto`, `--cov-report=json`, and `scripts/check_per_module_coverage.py` invocation).
- Update REQUIREMENTS.md: add TEST-11 and TEST-12 with final wording (per RESEARCH §phase_requirements), mark both Complete; update traceability table.
- Update ROADMAP.md Phase 14: amend SC#2 per D-E1 ("Paste-runnable gate command documented in 14-COVERAGE.md and CLAUDE.md; running the command verifies the 95% floor"); mark phase Complete; update plans-complete count.
- Update STATE.md: mark Phase 14 complete.
- Write `14-VERIFICATION.md`: the gate command, output (PASS line + module count), regression check (compare current coverage.json against `13-COVERAGE-BASELINE.md` PASS rows -- assert no regression), D-C3/D-C5 outcomes log (any pragmas added/deleted; any dead branches removed), pipeline-fixture inventory.
- Write `14-PHASE-SUMMARY.md`: retrospective per Phase 13 13-PHASE-SUMMARY.md format -- what worked, what was hard, lessons learned, final state.
- Manual checkpoint: present the gate output to the user; user types "approved" or describes issues.
</scope>

<out_of_scope>
- Any new test additions (subsystem plans 14-02..14-11 own that).
- Operational CI workflow file (D-E1 -- explicitly out of scope for Phase 14).
- Migration of `13-COVERAGE-BASELINE.md` -- it stays archived in its own phase dir per D-E3.
- `htmlcov/` directory commit (gitignored).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-E1, D-E2, D-E3, D-E4 (locked); locked Q2 merge; locked Q4 (commit coverage.json); locked Q5 (rm -f .coverage* prefix)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Coverage Tooling Configuration (gate command), §Closeout
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md` (table format reference)
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-VERIFICATION.md` (verification format reference)
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-PHASE-SUMMARY.md` (retrospective format reference)
- `.planning/REQUIREMENTS.md` (TEST-11, TEST-12 add)
- `.planning/ROADMAP.md` Phase 14 (SC#2 amend)
- `.planning/STATE.md`
- `CLAUDE.md` §Coverage (update target)
- `scripts/check_per_module_coverage.py` (Plan 14-01 deliverable)
</canonical_refs>

<waves>

## Wave 1 -- Final measurement

### Task 14-12-001 -- Run the final gate command from a clean working tree

- **Type:** infra (measure)
- **Description:** From project root:
    ```bash
    rm -f .coverage* coverage.json && python -m pytest tests/ \
      -m "not oracle" \
      -n auto \
      --cov=src/v1/engine \
      --cov=src/converters \
      --cov-report=term-missing \
      --cov-report=html \
      --cov-report=json -q
    python scripts/check_per_module_coverage.py coverage.json --floor 95
    ```
    Capture full stdout/stderr to a log file under `tests/_artifacts/14-final-gate-run.log` (ephemeral; NOT committed). Move the produced `coverage.json` (project root) to `.planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json` (the committed location per locked Q4).
- **Files:** `.planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json`
- **Verification:** the gate script itself; expected `exit 0` with `PASS: all <N> in-scope modules at >= 95.0% line coverage`.
- **Expected outcome:** PASS line printed; `14-coverage.json` ready to commit.
- **Notes:** If FAIL, do NOT proceed to closeout -- return to the failing subsystem's plan and close the gap. Closeout requires green from a clean run.

### Task 14-12-002 -- No-regression check (incl. iterate/context per locked Q2 merge)

- **Type:** infra (verify)
- **Description:** Programmatically diff `14-coverage.json` against the Phase 13 baseline.
    ```python
    # ad-hoc inline -- not committed
    import json
    cur = json.load(open('.planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json'))
    # Phase 13 PASS modules (from 13-COVERAGE-BASELINE.md): assert each is still >= 95% in cur
    pass_modules = [<list of paths from baseline PASS rows>]
    for p in pass_modules:
        pct = cur['files'][p]['summary']['percent_covered']
        assert pct >= 95, f'REGRESSION: {p} dropped to {pct}%'
    print('no regressions')
    ```
    Also explicitly assert iterate/context modules (`flow_to_iterate.py`, `iterate/__init__.py`, `context/context_load.py`, `context/__init__.py`) are >= 95% (the 14-04 merge per locked Q2).
- **Files:** none persisted (the assertion is captured in 14-VERIFICATION.md).
- **Verification:** the inline script.
- **Expected outcome:** `no regressions` printed; if any module regressed, do NOT proceed -- find the regression cause and fix in the responsible plan.

## Wave 2 -- Documentation artifacts

### Task 14-12-003 -- Generate 14-COVERAGE.md (per-module post-lift table)

- **Type:** docs
- **Description:** Build `14-COVERAGE.md` mirroring the structure of `13-COVERAGE-BASELINE.md`: front-matter (`phase: 14`, `slug: coverage-push-to-95-per-module-floor`, `status: locked`, `measured: 2026-MM-DD`, `test_total: <N>`, `test_failures: 0`), reproducible command, per-subsystem tables sorted by coverage descending, summary row, "Phase 14 Lift Result Count Summary", "Notable Modules" section. Source data: `14-coverage.json`.
- **Files:** `.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md`
- **Verification:** `python -c "import yaml, re; t=open('.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md').read(); fm=re.search(r'---(.*?)---', t, re.S).group(1); d=yaml.safe_load(fm); assert d['phase']==14 and d['status']=='locked'; print('ok')"`
- **Expected:** `ok`.
- **Notes:** Replace the Phase 14 Floor column ("PASS/FAIL") with "Status" -- expected ALL "PASS". `complex_converter` legacy section retained for historical context (still N/A).

### Task 14-12-004 -- Update CLAUDE.md §Coverage

- **Type:** docs
- **Description:** Replace the existing CLAUDE.md "Coverage" section with the new locked gate command (per locked Q4/Q5):
    ```bash
    rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
      --cov=src/v1/engine \
      --cov=src/converters \
      --cov-report=term-missing \
      --cov-report=html \
      --cov-report=json \
      && python scripts/check_per_module_coverage.py coverage.json --floor 95
    ```
    Documentation:
    - Note: requires JVM 11+ on PATH (`-m java` tests measured per D-A3).
    - Note: Oracle live tests opt-in via `-m oracle` (excluded from gate per D-A6).
    - Note: `[tool.coverage.run]` and `[tool.coverage.report]` in `pyproject.toml` are the source of truth for in-scope modules and pragma allowlist.
    - Reference `14-COVERAGE.md` for the per-module post-lift table (replaces Phase 13 baseline).
- **Files:** `CLAUDE.md`
- **Verification:** `grep -A 20 "## Coverage" CLAUDE.md | grep "rm -f .coverage" && grep "check_per_module_coverage" CLAUDE.md && echo ok`
- **Expected:** `ok`.

### Task 14-12-005 -- Update REQUIREMENTS.md (TEST-11, TEST-12) and ROADMAP.md (Phase 14 SC#2 + Complete)

- **Type:** docs
- **Description:**
    - REQUIREMENTS.md: under `### Testing`, append:
        ```
        - [x] **TEST-11**: Per-module line coverage of `src/v1/engine/` and `src/converters/` lifted to and verified at >=95% for every in-scope module (excluding `src/converters/complex_converter/` legacy modules); regression guard prevents any module from dropping below 95%; tests added are real-behavior (no `# pragma: no cover` outside the documented narrow allowlist of `__main__`, `@abstractmethod`, `ImportError` shims).
        - [x] **TEST-12**: Paste-runnable coverage gate command documented in CLAUDE.md and `14-COVERAGE.md`; per-module floor enforcement script (`scripts/check_per_module_coverage.py`) parses `coverage.json` and exits non-zero if any in-scope module is below 95%; final `14-COVERAGE.md` shows post-lift per-module numbers replacing `13-COVERAGE-BASELINE.md`.
        ```
        Update Traceability table: TEST-11 / Phase 14 / Complete; TEST-12 / Phase 14 / Complete. Update Coverage counts (v1 requirements: 127 total -> 127, +2). Bump "Last updated" footer date.
    - ROADMAP.md Phase 14:
        - Replace SC#2 wording per D-E1: "Paste-runnable gate command documented in `14-COVERAGE.md` and CLAUDE.md; running the command verifies the 95% floor."
        - Update **Requirements:** line: `TEST-11, TEST-12`.
        - Mark `[x]` in the phase header.
        - Add `**Plans:** 12/12 plans complete` and a list of all 12 plans `[x] 14-NN-*.md -- ...`.
        - Add `**Completed**: 2026-MM-DD | **SUMMARY**: 14-PHASE-SUMMARY.md`.
        - Update the Progress table: `14. Coverage Push to 95% per-module floor | 12/12 | Complete | 2026-MM-DD`.
- **Files:** `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`
- **Verification:**
    ```bash
    grep -E "TEST-11|TEST-12" .planning/REQUIREMENTS.md | head && grep "Phase 14" .planning/ROADMAP.md | head && echo ok
    ```
- **Expected:** Both modules referenced; phase header updated.

### Task 14-12-006 -- Update STATE.md

- **Type:** docs
- **Description:** Append a Phase 14 entry: phase number 14, slug, status `complete`, completed-on date, plans 12/12, key artifacts (`14-COVERAGE.md`, `14-VERIFICATION.md`, `14-PHASE-SUMMARY.md`, `scripts/check_per_module_coverage.py`, `tests/conftest.py` root, `tests/fixtures/jobs/` + `tests/fixtures/swift/` + `tests/fixtures/data/`), key decisions (D-A1..A6, D-C1..C5, D-D1..D4, D-E1..E4 + locked Q2/Q3/Q4/Q5 deviations).
- **Files:** `.planning/STATE.md`
- **Verification:** `grep "Phase 14" .planning/STATE.md && echo ok`
- **Expected:** `ok`.

### Task 14-12-007 -- Write 14-VERIFICATION.md

- **Type:** docs
- **Description:** Per the Phase 13 13-VERIFICATION.md format. Sections:
    - Front-matter (`phase: 14`, `status: locked`, `measured: 2026-MM-DD`).
    - Acceptance Criteria check (TEST-11 evidence: per-module >=95%; TEST-12 evidence: paste-runnable command; SC#1..SC#4 from ROADMAP).
    - Final gate command + full stdout output (the PASS line; first 30 lines of pytest summary).
    - Regression check log (Task 14-12-002 output -- "no regressions").
    - D-C3 pragma audit (`grep -rn "pragma: no cover" src/ ...` -- expected: only D-C3 allowlisted).
    - D-C5 dead-code deletions log (any subsystem plan that surfaced one).
    - Bug-fix log (any `BUG-*` commits that surfaced during the lift -- typically very few given test-only phase).
    - STALE deletions log (typically zero in Phase 14).
    - Pipeline-fixture inventory (count of fixtures under `tests/fixtures/jobs/`).
    - SWIFT generator inventory (`tests/fixtures/swift/synthetic.py` exposed names).
    - Manager / contributor notes -- `coverage.json` is committed per phase per locked Q4; future operational CI phase will re-emit.
- **Files:** `.planning/phases/14-coverage-push-to-95-per-module-floor/14-VERIFICATION.md`
- **Verification:** structural inspection.
- **Expected:** All acceptance evidence captured.

### Task 14-12-008 -- Write 14-PHASE-SUMMARY.md

- **Type:** docs
- **Description:** Per the Phase 13 13-PHASE-SUMMARY.md format. Sections:
    - Front-matter.
    - Phase outcome summary.
    - Plans executed (table mapping 14-01..14-12 to outcome + commit count).
    - What worked (D-C1 pipeline-test infra reuse; existing test patterns scaling up cleanly; SWIFT synth generator reusable for Phase 15).
    - What was hard (SWIFT MT branch coverage iteration; java_bridge_manager port-retry seeding; locked Q4 coverage.json size in repo).
    - Lessons learned (D-A3 vs D-A6 asymmetry was the right call; pipeline tests pay back for lifecycle modules; pragma allowlist is enforceable via grep without a custom plugin).
    - Final state of REQUIREMENTS.md / ROADMAP.md / STATE.md.
    - Handoff notes for Phase 15 (TEST-05/TEST-06 builds on this phase's pipeline-test infra).
- **Files:** `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md`
- **Verification:** structural inspection.
- **Expected:** Phase retrospective complete.

## Wave 3 -- Final manual checkpoint

### Task 14-12-009 -- Final gate-run + manual checkpoint

- **Type:** checkpoint:human-verify
- **What built:** All Phase 14 deliverables -- 14-COVERAGE.md, 14-coverage.json, 14-VERIFICATION.md, 14-PHASE-SUMMARY.md, CLAUDE.md update, REQUIREMENTS.md / ROADMAP.md / STATE.md updates, the per-module floor script.
- **How to verify:**
    1. From project root: `rm -f .coverage* coverage.json && python -m pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html --cov-report=json -q && python scripts/check_per_module_coverage.py coverage.json --floor 95`
    2. Confirm exit 0 with `PASS: all <N> in-scope modules at >= 95.0% line coverage`.
    3. Browse `htmlcov/index.html` (gitignored) to spot-check at least 3 modules; confirm green for each.
    4. Confirm `14-COVERAGE.md` table matches `coverage.json` per-module numbers.
    5. Confirm `CLAUDE.md` §Coverage shows the locked gate command.
    6. Confirm `.planning/REQUIREMENTS.md` shows TEST-11 / TEST-12 as `[x]` and traceability table updated.
    7. Confirm `.planning/ROADMAP.md` Phase 14 marked `[x]` with the D-E1 amended SC#2 wording.
- **Resume signal:** Type "approved" or describe issues.

</waves>

<verification_gate>

Plan 14-12 is GREEN when:
1. Final gate command exits 0 from a clean working tree.
2. All 198 in-scope modules at >= 95% line coverage in `14-coverage.json`.
3. No-regression check passes (every Phase 13 PASS module still >= 95%, including iterate/context per locked Q2 merge).
4. `14-COVERAGE.md`, `14-coverage.json`, `14-VERIFICATION.md`, `14-PHASE-SUMMARY.md` exist.
5. CLAUDE.md §Coverage updated with locked gate command.
6. REQUIREMENTS.md TEST-11 + TEST-12 present and `[x]`; traceability table updated.
7. ROADMAP.md Phase 14 marked Complete with D-E1 amended SC#2.
8. STATE.md Phase 14 entry added.
9. Manual checkpoint approved.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(14-12): INFRA-CLOSE-001 commit final coverage.json (per locked Q4)` | `.planning/phases/14-coverage-push-to-95-per-module-floor/14-coverage.json` |
| 2 | `docs(14-12): DOC-COV-001 add 14-COVERAGE.md final per-module table` | `.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md` |
| 3 | `docs(14-12): DOC-CLAUDE-001 update CLAUDE.md Coverage section with locked gate command (rm -f prefix + check_per_module_coverage)` | `CLAUDE.md` |
| 4 | `docs(14-12): DOC-REQ-001 add TEST-11/TEST-12 (Complete) to REQUIREMENTS.md` | `.planning/REQUIREMENTS.md` |
| 5 | `docs(14-12): DOC-ROAD-001 update ROADMAP Phase 14 SC#2 (D-E1) and mark Complete` | `.planning/ROADMAP.md` |
| 6 | `docs(14-12): DOC-STATE-001 mark Phase 14 complete in STATE.md` | `.planning/STATE.md` |
| 7 | `docs(14-12): DOC-VER-001 add 14-VERIFICATION.md acceptance evidence` | `.planning/phases/14-coverage-push-to-95-per-module-floor/14-VERIFICATION.md` |
| 8 | `docs(14-12): DOC-SUMMARY-001 add 14-PHASE-SUMMARY.md retrospective` | `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md` |

(Total: 8 commits; final commit landed only after manual checkpoint approves.)

</commit_map>
