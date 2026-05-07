# Phase 11: Oracle Components - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 11-oracle-components
**Areas discussed:** Connection persistence & lifecycle; Driver mode + connection types; Type mapping & transactions; tOracleRow & tOracleOutput component semantics; Architecture & test infrastructure

**User's framing:** Up-front directive — "Majorly work with three of them: tOracleConnection, tOracleRow, tOracleOutput. First research what Talend does. Then how Python in our current code can handle these. Then ask questions on the base setup." Cluster selection: all 4 selected, with explicit ask to also research the other 6 Oracle components so the base infrastructure holds for the full family.

---

## Initial gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Connection persistence & lifecycle | Manager class vs globalMap vs side-dict; driver mode; conn types in scope | ✓ |
| Type mapping & transactions | NUMBER/DATE/CLOB/XMLTYPE handling; autocommit; NLS | ✓ |
| tOracleRow & tOracleOutput component semantics | TABLE_ACTION/DATA_ACTION coverage; INSERT_OR_UPDATE strategy; USE_PREPAREDSTATEMENT; reject schema | ✓ |
| Architecture & test infrastructure | Generic BaseDb* now or later; testcontainers vs mocks; sub-phase split | ✓ |

**User's choice:** All 4 + extra directive to research remaining 6 Oracle components for base-infrastructure soundness.
**Notes:** First selection attempt was rejected with "I'd like to clarify these questions" — user wanted me to do the deep research first, then frame questions. After parallel WebFetches across all Talaxie javajets and reads of converter source + JavaBridgeManager pattern, re-presented and got selection.

---

## A1 — Where do live oracledb.Connection objects live?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated OracleConnectionManager on ETLEngine (Recommended) | Manager class analog to JavaBridgeManager; engine.oracle_manager.get(ref); globalMap retains metadata strings only | ✓ |
| Vendor-agnostic DatabaseConnectionManager | Generic manager + DbDialect ABC; pre-paves MSSql; speculative abstraction | |
| Side-dict on ETLEngine + globalMap metadata | self.db_connections dict; minimal code; no encapsulation; cleanup scattered | |

**User's choice:** Dedicated OracleConnectionManager.
**Notes:** Clean separation; no Java-bridge globalMap-sync hazard; mirrors the proven JavaBridgeManager / PythonRoutineManager pattern.

---

## A2 — Driver mode

First-pass options offered: thin only / thin+thick escape / thick only.

**User's choice:** Asked clarifying question — *"Which components need thick? Thin doesn't support certain charsets — I don't want existing DB to get affected."*

Provided detailed analysis:
- Thick is about **features** not components: SID/SERVICE_NAME/RAC work in thin; OCI8 + Wallet auto-login + Kerberos + Oracle Spatial + STRUCT/ARRAY proc args need thick.
- Thin handles all common Oracle charsets (AL32UTF8, WE8MSWIN1252, ISO-8859-15, KO16MSWIN949, ZHS16GBK, JA16SJIS, US7ASCII). Thin ignores client-side `NLS_LANG` (decodes from server-reported charset) — strictly more correct, only deviates from Talend if a job intentionally relies on `NLS_LANG`-driven re-encoding.
- Thin is read-only on client side; cannot alter DB state.

Re-asked with that context:

| Option | Description | Selected |
|--------|-------------|----------|
| Thin default + per-job thick escape (Recommended) | thick_mode flag in oracle_config; converter flags Wallet/OCI; thick init once when manager starts | ✓ |
| Thin only (defer thick) | NotImplementedError for Wallet/OCI; clean scope; lift in later phase | |
| Thick by default | Always init thick; reintroduces Oracle Instant Client deployment friction | |

**User's choice:** Thin default + thick escape.
**Notes:** User noted "the converter also needs update then" — captured as D-E1 inline scope.

---

## A3 — Connection types in active scope

| Option | Description | Selected |
|--------|-------------|----------|
| Tier 1: SID/SERVICE_NAME/RAC fully tested; OCI/WALLET raise NotImplementedError (Recommended) | Cover typical Citi production; clear deferred message; no silent failures | ✓ |
| Tier 1 + thick-mode plumbing for OCI/WALLET, not in CI | All 5 URL builders; Wallet/OCI tagged @pytest.mark.oracle_thick | |
| All 5 fully tested | Wallet/OCI fixtures in CI; high test infra cost | |

**User's choice:** Tier 1, NotImplementedError for the other two.

---

## A4 — Connection lifecycle semantics

First-pass options: Talend-parity / all-live-until-job-end / component-owned.

**User's choice:** Asked clarifying question — *"How does Talend do it and what is the closest we can achieve?"*

Provided code-level breakdown of Talend's pattern:
- **Ad-hoc**: open at component begin → setAutoCommit(false) if COMMIT_EVERY > 0 → execute → final commit of trailing batch → close. Per-component lifecycle.
- **Shared**: tOracleConnection puts conn in globalMap → persists → tOracleClose explicitly closes (or JVM finalizer GC at process exit if missing close component — non-deterministic leak).
- **Uncommitted at close**: Oracle JDBC default rolls back. oracledb matches.

The **single deviation** from Talend in our engine: deterministic safety-net cleanup in `engine._cleanup()` (vs Talend's JVM-GC-driven close). This is *strictly more correct* — same observable end state, no resource leak window.

Locked in option (a) Talend-parity with safety-net documented as D-A4.

**Notes:** User followed up with directive: "Ensure to close connections or clean up connections in engine using the corresponding connection manager, similar to how Java bridge closes." Confirmed via `grep` that `engine._cleanup()` calls `java_bridge_manager.stop()` from success path / exception path / `__del__`. Phase 11 adds `oracle_manager.stop()` at the same site. Locked as D-A4b.

---

## B1 — Type mapping policy

| Option | Description | Selected |
|--------|-------------|----------|
| Schema-driven (Talend-parity, Recommended) | Coerce per engine schema column type via existing _coerce_column_type; oracledb.defaults.fetch_lobs=False; honor USE_TIMESTAMP_FOR_DATE_TYPE; XMLTYPE→str for tOracleRow | ✓ |
| oracledb defaults, no schema-driven coercion | NUMBER may be float (lossy), DATE is plain datetime not pd.Timestamp; breaks parity | |
| Convert everything to string | Loses type info; catastrophic for precision and date arithmetic | |

**User's choice:** Schema-driven (Talend-parity).
**Notes:** Engine already has `Decimal` schema type with precision-aware coercion (`base_component.py:1067-1069`). This decision reuses that infrastructure exactly.

---

## B2 — Batching strategy when REJECT flow is wired

| Option | Description | Selected |
|--------|-------------|----------|
| executemany(batcherrors=True) always (Recommended) | Single code path; cursor.getbatcherrors() drives reject DataFrame; 5-50x faster than per-row; identical semantics | ✓ |
| Strict Talend mirror: per-row when REJECT, executemany otherwise | Two code paths; byte-for-byte Talend execution; 5-50x slower for REJECT-wired jobs | |
| executemany unconditionally; on first error switch to per-row | Complicates state; partial-batch already committed; worse than option 2 | |

**User's choice:** executemany(batcherrors=True) always.
**Notes:** oracledb's batcherrors mode preserves identical row-level error info as Talend's per-row pattern, just at the protocol level.

---

## C1 — tOracleOutput TABLE_ACTION + DATA_ACTION scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full Talend coverage, all 8 × 5 (Recommended for parity) | All TABLE_ACTIONs + DATA_ACTIONs; CREATE emits DDL from schema column types; bounded effort | ✓ |
| Pragmatic subset (NONE/TRUNCATE/CREATE_IF_NOT_EXISTS × INSERT/UPDATE/INSERT_OR_UPDATE/DELETE) | Common Citi patterns; rare actions raise NotImplementedError | |
| Minimal (NONE/TRUNCATE × INSERT) | Just enough to load existing tables; production-blocking for incremental loads | |

**User's choice:** Full coverage.
**Notes:** Project memory "identical to Talend" preference; full coverage avoids future production-blocking errors.

---

## C2 — INSERT_OR_UPDATE / UPDATE_OR_INSERT strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Talend's 2-statement pattern, batched (Recommended) | SELECT pk_cols WHERE pk IN (batch_keys), partition matched/unmatched, executemany UPDATE + executemany INSERT; ~10x faster than per-row, splits NB_LINE_INSERTED/UPDATED correctly | ✓ |
| Use Oracle MERGE | Single MERGE per batch; aggregate rowcount loses INSERTED/UPDATED split; small parity edge cases (no-op MATCHED rows) | |
| Strict per-row mirror of Talend (slowest) | Byte-for-byte mirror; 3x slower than batched 2-stmt; only for regulatory audit | |

**User's choice:** Batched 2-statement pattern.

---

## C3 / C4 / C5 — tOracleRow advanced features

| Option | Description | Selected |
|--------|-------------|----------|
| Ship USE_PREPAREDSTATEMENT (full 16-type coverage), defer PROPAGATE_RECORD_SET (Recommended) | Full PARAMETER_TYPE table; PROPAGATE_RECORD_SET → ConfigurationError; USE_NB_LINE → set globalMap from cursor.rowcount; DDL → 0 with WARNING | ✓ |
| USE_PREPAREDSTATEMENT subset only, defer rest | 8 common types; rare types (Bytes/Time/Short/Byte/BigInteger) raise ConfigurationError | |
| Ship everything including PROPAGATE_RECORD_SET | Materialize cursor as DataFrame in single-cell value; awkward UX | |

**User's choice:** Full USE_PREPAREDSTATEMENT, defer PROPAGATE_RECORD_SET.

---

## D1 — Architecture abstraction scope

| Option | Description | Selected |
|--------|-------------|----------|
| Oracle-specific now; refactor when MSSql phase comes (Recommended) | Phase scope boundary; no speculative abstraction; existing 2 MSSql converters stay engine-unimplemented | ✓ |
| Build BaseDb* abstractions now | Pre-pave MSSql; refactor risk when MSSql semantics differ | |

**User's choice:** Oracle-specific now.
**Notes:** Project memory "Phase scope boundaries — don't do global sweeps" + "don't design for hypothetical needs" both reinforce this.

---

## D2 — Real-DB test infrastructure

| Option | Description | Selected |
|--------|-------------|----------|
| testcontainers + gvenzl/oracle-free (Recommended) | @pytest.mark.oracle gated by `pytest -m oracle`; CI runs in Docker job; mandatory per-component real-DB test | |
| Mocks-only with manual integration verification | Violates "Test real bridge, not mocks" memory; Phase 5.1 lesson warns this gives false confidence | |
| Hybrid: mock-default unit tests, optional Docker fixture | Mocks default; @pytest.mark.oracle opt-in; rot risk if no one runs it | ✓ |

**User's choice:** Hybrid.
**Notes:** Mitigation added (D-D3): `gsd-verify-work` for Phase 11 must require `pytest -m oracle` at least once before phase verified. Captures Phase 5.1 lesson without forcing CI Docker today.

---

## Wrap-up confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Looks good — write CONTEXT.md | All decisions locked, deferred items captured, sub-phase split reasonable | ✓ |
| One more concern to surface | Pause for additional discussion | |
| Adjust the sub-phase split | 7-plan tentative split needs revision | |

**User's choice:** Looks good — write CONTEXT.md.

---

## Claude's Discretion

- Internal class structure of `OracleConnectionManager` (private helpers, method decomposition)
- Stats dict shape for per-component execution stats
- SQL-emitter helper organization for tOracleOutput TABLE_ACTIONs (one method each vs dispatch table)
- Test fixture location for testcontainers (conftest.py vs new tests/oracle_fixture.py)
- Reject DataFrame buffer strategy (in-memory list vs concat-on-finalize)
- Public `engine.oracle_manager` attribute vs private with getter
- Exact log message wording for thick-mode init
- DDL string formatting style (uppercase keywords, line breaks, indentation)

## Deferred Ideas

- ORACLE_OCI / ORACLE_WALLET runtime support (thick mode + Instant Client) — needs_review pointer, NotImplementedError until lifted
- Other 6 Oracle engine components (Input, SP, BulkExec, Commit, Rollback, Close) — manager API supports them; each lands in own phase
- tOracleRow PROPAGATE_RECORD_SET — DataFrame-semantics mismatch
- tOracleInput IS_CONVERT_XMLTYPE / CONVERT_XMLTYPE table
- BaseDbConnection / BaseDbInput / BaseDbOutput abstractions (when MSSql phase brings 2nd vendor impl)
- Default-CI Docker fixtures (when ops can host Docker in CI)
- Streaming-mode for very large tOracleOutput inputs
- MSSql engine components (separate future phase)
