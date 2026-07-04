# Phase 15: Documentation Sweep — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 15-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 15-documentation-sweep
**Original phase ID:** Phase 16 (Documentation Sweep) — swapped to Phase 15 on 2026-05-11 because the original Phase 15 (Integration Testing & Performance) requires Talend Open Studio access and is now manager-owned as Phase 16.

---

## Pre-discussion setup

| Item | Resolution |
|------|------------|
| Phase swap 15 <-> 16 | Done — ROADMAP commit `b773997` |
| Phase 15.1 (audit reconciliation) | Added to ROADMAP this session — depends on Phase 14 + Phase 15 |
| Phase 15 SC#3 (CI doc-lint) | Dropped from ROADMAP this session — user said "not needed" |

---

## Initial doc inventory

When discussion started, I undercounted with a maxdepth-3 scan (38 files). User pushed back: "I think it would be way more than 38." A full sweep returned **124 user-facing doc files** (excluding `.planning/`, `.claude/`, `.gemini/` tooling). Breakdown that drove the discussion:

| Location | Files | Note |
|----------|------:|------|
| Root | 1 | `CLAUDE.md` only |
| `docs/` top-level | 22 | 20 .md + 2 .docx — the rot layer |
| `docs/v1/` direct | 3 | STANDARDS.md, BaseComponent-Info.md, talend_to_v1_converter_guide.md |
| `docs/v1/standards/` | 8 | ENGINE/CONVERTER/TEST patterns + AUDIT_REPORT_TEMPLATE + METHODOLOGY + MANUAL_COMPONENT_AUTHORING + NEXT_MILESTONE_GUIDE |
| `docs/v1/audit/` | 89 | 3 cross-cutting + 86 per-component |
| `tests/` | 1 | `tests/fixtures/jobs/README.md` (Phase 14 tooling readme) |

---

## Areas discussed

| Option | Description | Selected |
|--------|-------------|----------|
| A. Top-level docs/ disposition | Nuke all / triage individually / move to legacy/ / keep 2 + nuke rest | Nuke all (D-A1) |
| B. docs/v1/audit/ treatment | Archive / mark resolved per file / delete / regenerate fresh | Defer to Phase 15.1 (D-A4) — user wanted "newer 15.1 phase" |
| C. COMPONENT_REFERENCE.md depth | Generated per all 86 / priority 12 only / pointer-only / full hand-written | Registry-driven index pointing at audit/ (D-C6) — deep content owned by 15.1 |
| D. Stale-doc CI lint | Custom script + pre-commit / paste-runnable in CLAUDE.md / header-date only / skip | Skip (D-B1) — user said "not needed" |

---

## A. Top-level docs/ disposition

**User direction:** "the top level 22 to can completely nuked and we can create a fresh set of new required documents"

**Option chosen:** Nuke all 22 (20 .md + 2 .docx). No salvage. Fresh canonical doc set replaces them.

**Alternatives rejected:**
- Triage each file individually (too much per-file deliberation; the user trusts the canonical set will cover what matters)
- Move to `docs/legacy/` parking lot (preserves rot, defers the problem)
- Keep ARCHITECTURE + SETUP_DEPLOYMENT, nuke rest (existing files are stale enough that rewriting fresh is faster than fixing in place)

**Captured as:** D-A1, D-A2 (canonical names locked), D-A3 (canonical docs live at `docs/` root).

---

## B. docs/v1/audit/ treatment

**User direction:** "we will sit on this in a newer 15.1 phase. we need to go through each file, the corresponding converter and engine code to make these docs accurate and in few cases the docs themseleves had wrong or stale info. so these docs needs update but in a diff phase bro."

**Resolution:** Created Phase 15.1 (Documentation Audit Reconciliation) in ROADMAP this session. Phase 15 does NOT modify any file under `docs/v1/audit/`. Phase 15.1 owns deep reconciliation — read code, read audit doc, update audit doc to match reality.

**Alternatives rejected:**
- Archive to `docs/archive/` (loses authoritative status; the audit is still the canonical per-component truth source until 15.1 reconciles it)
- Mark "STATUS: Resolved" headers per file (cosmetic; doesn't address stale content)
- Delete (history loss; .planning/ doesn't replicate audit detail)
- Regenerate from current code (Phase 15 surface too large; that IS Phase 15.1)

**Captured as:** D-A4 (out of Phase 15 scope) + new Phase 15.1 added to ROADMAP.

---

## C. docs/v1/standards/ + 3 siblings

**User direction:** "we can rename folder if needed. we need to go through the files deeply and find any stale or wrong content and fix it. we also need to see if all 8 are needed or anything can be removed (like AUDIT_REPORT_TEMPLATE or METHODOLOGY etc)"

**Resolution:** Deep review of all 11 (8 in standards/ + STANDARDS.md, BaseComponent-Info.md, talend_to_v1_converter_guide.md). Each file cross-referenced against current code. Redundant files dropped (AUDIT_REPORT_TEMPLATE, METHODOLOGY, NEXT_MILESTONE_GUIDE all explicit candidates per user signal). Folder rename considered if surviving content no longer matches `standards/`.

**Captured as:** D-A5, D-A6, D-D1, D-D2.

---

## D. Stale-doc CI lint

**User direction:** "3. not needed."

**Resolution:** No CI / pre-commit doc-freshness lint. ROADMAP SC#3 (originally `CI lints stale docs against codebase symbols`) explicitly dropped this session. Manual review is the freshness mechanism.

**Captured as:** D-B1. Compensating control: D-C2 mandates `*Last updated: YYYY-MM-DD*` header on every new/rewritten doc.

---

## Out-of-scope confirmations (not gray areas; user explicit)

| Scope | User direction |
|-------|----------------|
| CLAUDE.md | "definitely not in scope" |
| .planning/ | "definitely not in scope" |
| .claude/ | "definitely not in scope" |
| .gemini/ | "definitely not in scope" |
| tests/fixtures/jobs/README.md | Confirmed tooling-adjacent (Phase 14 artifact, load-bearing for pipeline-test authors) — stays |

---

## Outstanding gray areas presented (rejected by user before answering)

1. **Ground truth source for TEST-06** — moot once Phase 15 ↔ 16 swapped; integration testing left this phase
2. **48 .item sample scope** — moot, same reason
3. **Diff strictness** — moot, same reason
4. **PERF-03/04 ambition** — moot, same reason

These return when the manager runs Phase 16.

---

## Deferred ideas (captured for future phases)

- **Documentation generation tooling** (Sphinx, MkDocs, Docusaurus) — defer indefinitely; plain Markdown only.
- **Auto-generated COMPONENT_REFERENCE.md** via `scripts/gen_component_reference.py` walking `COMPONENT_REGISTRY` — planner-discretion if low-cost; otherwise inline reference.
- **Repo-wide registry/abstract-method audit** — Phase 14 patched 4 known instances (PDC-001/002, FIJ-001/002, SWIFT-001/002). A systematic sweep is still owed; captured as Phase 15.2 candidate or fold into manager Phase 16 startup.
- **API reference auto-generation** from docstrings — out of scope.

---

## Phase 15 final surface area summary

- **Delete:** 22 top-level `docs/` files
- **Create:** 4 canonical docs at `docs/` root + 1 root `README.md`
- **Deep-review:** 11 files under `docs/v1/` (8 in `standards/` + 3 siblings)
- **Drop if redundant:** at least 3 candidates (AUDIT_REPORT_TEMPLATE, METHODOLOGY, NEXT_MILESTONE_GUIDE)
- **Possibly rename:** `docs/v1/standards/` folder
- **Untouched:** all 89 files in `docs/v1/audit/` (Phase 15.1 territory), CLAUDE.md, `.planning/`, `.claude/`, `.gemini/`, `tests/fixtures/jobs/README.md`

Estimated commits: ~25-30 (atomic per file per D-E1; nuke can be one batch commit; rewrites are per-file).

---
*Phase 15 discussion log — gathered 2026-05-11*
