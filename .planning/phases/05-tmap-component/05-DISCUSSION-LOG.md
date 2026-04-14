# Phase 5: tMap Component - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 05-tmap-component
**Areas discussed:** Rewrite approach, Expression & join architecture, Multi-input/output routing, Feature scope boundary, Cross-table join handling, Research depth

---

## Rewrite Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Full rewrite | Rewrite from scratch conforming to ENGINE_COMPONENT_PATTERN.md. Preserve hybrid pandas+Java architecture and compile-once pattern. | Y |
| Targeted surgical fix | Keep existing code, fix MAP-01 through MAP-08 in place. Faster but doesn't address structural issues. | |
| Hybrid rewrite | Rewrite structural shell, transplant working join/expression logic with fixes. | |

**User's choice:** Full rewrite -- consistent with Phase 4 approach. User confirmed immediately.
**Notes:** User noted BaseComponent lifecycle had changed since audit. Led to detailed review of Phase 1's rewritten BaseComponent.

---

## BaseComponent Lifecycle Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Override hooks (not execute()) | Override _resolve_expressions(), _update_stats_from_result(), _select_mode(). Don't override execute(). | Y |
| Override execute() too | tMap gets full control of execute(). Still calls _validate_config() etc manually. | |

**User's choice:** Asked Claude for recommendation. Claude recommended override hooks because: (1) MAP-04's whole point is to stop bypassing lifecycle, (2) hooks are the intended extension mechanism, (3) config immutability and iterate support for free, (4) future-proof against lifecycle additions.
**Notes:** None

---

## Join Semantics (Null Keys, UNIQUE_MATCH, Reject Routing)

**User's choice:** All behavioral questions answered by Talend parity principle -- not gray areas, locked decisions.
**Notes:** User said "we are trying to create talend level similarity as much as possible. so the behaviour should be similar to talend bro." All join semantics follow Talend behavior exactly.

Locked directly:
- Null keys: never match (SQL/Talend semantics)
- UNIQUE_MATCH: first-row wins (keep='first')
- rejectInnerJoin: distinct from generic reject, tracked per-lookup

---

## Chunking Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Same 50K chunk pattern | Always chunk preprocessing, consistent with post-processing. | |
| Configurable threshold | Only chunk if DataFrame exceeds threshold. Small datasets go through in one call. | Y |
| You decide | Claude picks during implementation. | |

**User's choice:** Configurable threshold
**Notes:** User raised chunking in preprocessing as a new concern: "we need to allow chunking in preprocessing also similar to post processing bro."

---

## Feature Scope Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Defer MAP-05 (catch output reject) | Rare in production, can add later. | |
| Defer MAP-06 (auto type conversion) | Converter removed param, needs converter change. | |
| Defer MAP-08 (RELOAD_AT_EACH_ROW) | High complexity, rare pattern. | |
| Keep all MAP-01 to MAP-08 | No scope reduction. | Y |

**User's choice:** Keep all MAP-01 to MAP-08.
**Notes:** User initially said "we will try to reduce the talend feature parity" but chose to keep full scope when presented with options.

---

## Cross-Table Join Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Research + smart routing | Classify joins by type, route to different strategies. Research Talend behavior first. | Y |
| Always cartesian + filter | Simple but risks OOM on large datasets. | |
| Defer cross-table to v2 | Only support equality joins. May block production jobs. | |

**User's choice:** Research + smart routing
**Notes:** User raised this concern: "i want to redesign the cartesian product aspect if possible. for example, i have source file and lookup file, in talend's tMap, i can add a regex match filter function and things will work. the current tMap code can't handle it."

---

## Research Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Deep research | All 10 topics including production .item scan and Talend javajet analysis. | Y |
| Focused research | Top 5 issues only, skip production scan. | |
| Minimal research | Only cross-table join strategy and thread safety fix. | |

**User's choice:** Deep research
**Notes:** User said "I would say we need to have the plan researcher find all edge cases like this and close in a performance and memory efficient way as much as possible." User also identified Talaxie GitHub repo as key source: "one of talaxie github repo was extensively used to capture the requirements for converter code."

---

## Talaxie GitHub Source

**User surfaced:** The Talaxie/tdi-studio-se GitHub repository contains `.javajet` code generation templates for tMap that show the exact Talend execution logic. Added as primary canonical reference for research phase.

---

## Claude's Discretion

- Internal method decomposition and helper design
- Exact preprocessing chunk threshold value
- Smart join classifier structure
- Column prefixing strategy
- Compiled script generation details
- Test count target

## Deferred Ideas

- MAP-V2-02: Disk-based lookup caching -- v2
- MAP-V2-03: Parallel lookup loading -- v2
- MAP-V2-04: Fuzzy matching (Levenshtein/Jaccard) -- v2
- MAP-V2-05: BigDecimal hash/equals -- v2
- activateGlobalMap on tables -- low priority
- persistent lookup support -- low priority
- ALL_ROWS keyless cross-join -- P3
