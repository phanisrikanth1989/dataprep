# Phase 14: Coverage Push to 95% per-module floor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 14-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 14-coverage-push-to-95-per-module-floor
**Areas discussed:** A. Module scope universe, C. Test strategy & pragma policy, D. Plan / wave structure & ordering
**Areas skipped:** B. CI gate mechanism (user pivoted mid-discussion: "no CI enforcing needed for now")

---

## Initial Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| A. Module scope universe | SWIFT (7%/7%), file_input_json (9%), file_input_raw (15%), python_dataframe (20%) — in 95% gate or excluded? | ✓ |
| B. CI gate mechanism | GitHub Actions / pre-commit / pytest --cov-fail-under per module / -m java/-m oracle handling | (user pivoted: deferred) |
| C. Test strategy & pragma policy | Mocks vs real fixtures; allowed pragma uses | ✓ |
| D. Plan / wave structure & ordering | Big-bang vs subsystem vs tier; quick-wins-first vs deep-gaps-first | ✓ |

---

## A. Module scope universe

### A1: SWIFT engine modules (~800 stmts combined)

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude (treat like complex_converter) | Mark SWIFT as N/A; PROJECT.md treated SWIFT as out-of-scope on converter side | |
| Include (full lift to 95%) | Treat them like every other engine component; ~800 stmts of new test surface | ✓ |
| Include but lower bar (e.g. 80%) | Custom per-module floor; breaks single-floor principle | |

**User's choice:** Include — full 95% lift.
**Notes:** Decisive call despite PROJECT.md "skipped" note. SWIFT modules are registered in engine and ship as production components.

### A2: file_input_json / file_input_raw / python_dataframe_component

| Option | Description | Selected |
|--------|-------------|----------|
| Include all three | Engine registers them, UI registry references them, no PROJECT.md exclusion | ✓ |
| Exclude python_dataframe_component only | python_dataframe in v2 backlog (COMP-V2-06) | |
| Exclude all three | Defer all three if user knows they're not used | |

**User's choice:** Include all three.

### A3: java_bridge_manager.py (59%, JVM lifecycle paths)

| Option | Description | Selected |
|--------|-------------|----------|
| Measure WITH `-m java` markers (require JVM in CI) | Real-bridge stance; closes Phase 02 verification debt | (Claude's call) ✓ |
| Measure default markers only; java_bridge_manager exempt | Documented exemption | |
| Default markers + add unit tests with mocked subprocess | Violates "test real bridge, not mocks" memory | |

**User's choice:** "decide the best action bro" → Claude selected option 1.
**Notes:** Aligned with project memory rule "test real bridge, not mocks" (project_test_real_bridge.md). Phase 02 verification debt naturally closes when gate runs in JVM-equipped environment.

### A4: send_mail.py (60%, SMTP send paths)

| Option | Description | Selected |
|--------|-------------|----------|
| Mock smtplib at the boundary, lift to 95% | Standard outbound-transport pattern; component-internal logic real | ✓ |
| aiosmtpd-based local SMTP server fixture | Closer to "test real" but adds dep + per-test overhead | |
| Exempt send_mail from gate | Risky for production component | |

**User's choice:** Mock smtplib at boundary.

### A5: SWIFT MT message fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| User provides scrubbed production samples | Best fixture quality; real Talend output shapes | |
| Generate synthetic per the SWIFT spec | Built from SWIFT user-handbook structure; planner-side work | ✓ |
| Use existing converter test fixtures + extend | Cheapest if fixtures exist | |

**User's choice:** Generate synthetic per SWIFT spec.

### A6: Oracle modules (oracle_output 94%, oracle_row 90%)

| Option | Description | Selected |
|--------|-------------|----------|
| Measure WITH `-m oracle` (CI requires testcontainer) | Symmetric with java_bridge_manager decision | |
| Measure default markers only; oracle modules exempt | Simpler CI; second class of exempt modules | |
| Default markers + mocked oracledb tests | Conflicts with "mocks lie" Phase 5.1/11 lesson | ✓ |

**User's choice:** "we will go with mock for oracle alone bro" → option 3.
**Notes:** User explicitly chose to deviate from the symmetric "real" stance. Reasoning preserved in CONTEXT.md D-A6: Phase 11 testcontainer suite IS the verification path; coverage path mocks at the boundary.

---

## Mid-discussion pivot

User sent: *"we have to think about multi component or project wise testing as well. no CI enforcing needed for now"*

**Two scope changes captured:**
1. **CI enforcement deferred** — Roadmap SC#2 amended to "paste-runnable gate command" (Phase 13 D-E2 pattern). Area B skipped entirely.
2. **Multi-component testing folded in** — Pipeline tests via ETLEngine.execute() with JSON job configs become a primary test mode for lifecycle/routing/globalMap-dependent modules.

These pivots reshaped Areas C and D before questions were asked.

---

## C. Test strategy & pragma policy

### C1: Multi-component testing aggression level

| Option | Description | Selected |
|--------|-------------|----------|
| Default: pipeline tests where they're the natural way | 2-5 pipeline tests per lifecycle-dependent subsystem; pure-pandas stays unit-test | ✓ |
| Aggressive: every below-95 module gets at least one pipeline test | Maximum integration coverage; ~50 pipeline tests | |
| Minimal: only where unit tests can't reach | Risks shallow coverage | |

**User's choice:** Default — pipeline tests where natural.

### C2: JSON job config style

| Option | Description | Selected |
|--------|-------------|----------|
| Inline Python dicts in test files | Fast to read; matches test_iterate_e2e.py | |
| Fixture .json files in tests/fixtures/jobs/ | Mirrors converter output; catches JSON edge cases | ✓ |
| Hybrid: inline for small, fixture for complex | Best of both; more decision overhead | |

**User's choice:** Fixture .json files.

### C3: Pragma policy

| Option | Description | Selected |
|--------|-------------|----------|
| Allow narrow set: __main__, abstract methods, ImportError fallback | Documented allowlist; anything else disallowed | ✓ |
| Strict: zero new pragmas; clean existing ones | Hardest but most honest | |
| Permissive: case-by-case in PR review | Risks inconsistency | |

**User's choice:** Narrow allowlist.

### C4: Pure-pandas transform test emphasis

| Option | Description | Selected |
|--------|-------------|----------|
| Real-shape tests + targeted edge cases | Mixed dtypes, all error branches, custom exception hierarchy, pandas 3.0 CoW | ✓ |
| Parametric matrix per component | 8-16 cases per component; mechanical + thorough | |
| Property-based testing (Hypothesis) | New dep; catches edge cases unit tests miss | |

**User's choice:** Real-shape + targeted edge cases.

---

## D. Plan / wave structure & ordering

### D1: Plan slicing strategy

| Option | Description | Selected |
|--------|-------------|----------|
| By subsystem (~12 plans total) | Each plan internally cohesive; easy to wave-parallelize | ✓ |
| By coverage tier (~5 plans) | Bigger plans; tier-aligned effort | |
| By component (~55 plans) | Maximally atomic; too much overhead | |
| Hybrid (subsystem + split big subsystems) | ~14-16 plans; more planner overhead | |

**User's choice:** By subsystem.

### D2: Plan ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Infra → quick wins → medium → deep gaps → closeout | Builds momentum; deep gaps last when patterns mature | ✓ |
| Infra → deep gaps first → medium → quick wins → closeout | Surfaces risk early | |
| Infra → by subsystem in dependency order (engine-core first) | Aligns with import graph | |

**User's choice:** Infra → quick wins → medium → deep gaps → closeout.

### D3: Regression guard

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — uniform "no module drops below 95%" | One rule for all 198 modules | ✓ |
| Yes, but lock current % as floor (stricter) | 100% must stay 100%; trivial refactor friction | |
| No — only enforce 95% on previously-FAIL modules | Risky; refactors could silently drop a 100% module | |

**User's choice:** Uniform 95% gate.

### D4: Test runtime strategy

| Option | Description | Selected |
|--------|-------------|----------|
| pytest-xdist (-n auto) + @pytest.mark.slow | Already in deps; pytest-cov 7 + xdist combine cleanly | (Claude's call) ✓ |
| Status quo: run sequentially | Simplest; test suite ~60-120s | |
| Tier the suite: fast-by-default, full opt-in | Risks "forgot to run full" drift | |

**User's choice:** "decide the best. but test coverage is priority" → Claude selected option 1.
**Notes:** Coverage stays priority — never trade real-production-path coverage for runtime savings. xdist is the optimization lever; tests >5s get the existing `slow` marker.

---

## Final readiness check

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context | Write CONTEXT.md with all decisions; advance to /gsd-plan-phase 14 | ✓ |
| Explore more gray areas | Surface 2-3 additional gray areas | |
| More questions on A/C/D | Drill deeper before moving on | |

**User's choice:** Ready for context.

---

## Claude's Discretion

- **D-A3 (java_bridge_manager gate handling):** User said "decide the best action bro" → measured WITH `-m java` markers per the "test real bridge" memory rule.
- **D-D4 (test runtime strategy):** User said "decide the best. but test coverage is priority" → pytest-xdist `-n auto` + `slow` marker, with coverage as the inviolable priority.
- **Plan / wave decomposition fine-tuning:** Planner may merge or split the ~12-plan structure (e.g., merge 14-04 into 14-09, or split 14-08 SWIFT per-component) within the "by subsystem, infra first, closeout last" envelope.
- **TEST-11 / TEST-12 wording:** Planner finalizes the requirement text; exact labels subject to user review at the planner gate.
- **Specific fixture file names + JSON job shapes:** Planner choice; convention is `tests/fixtures/jobs/{subsystem}/{behavior}.json`.
- **STALE-test cleanup if encountered:** Apply Phase 13 D-D1 pattern (delete tests for engine-implemented features, log under STALE-NN in plan summaries).

## Deferred Ideas

- CI workflow file (GitHub Actions / Jenkinsfile / pre-commit) — operational CI lands in a future phase; Phase 14 ships paste-runnable command
- aiosmtpd-based local SMTP server for send_mail integration — smtplib boundary mocks sufficient for 95% gate
- Hypothesis property-based testing — standard tests sufficient
- Real Oracle testcontainer in the gate command — Phase 11 verification debt; stays human-run
- Branch coverage — line coverage only in Phase 14
- `complex_converter` removal — legacy; not in Phase 14 scope
- TEST-05, TEST-06, PERF-02/03/04 — Phase 15 work
- Documentation sweep — Phase 16 work
- Architectural fixes surfaced during the lift — patch source per Phase 13 pattern; major refactors defer to their own phase
