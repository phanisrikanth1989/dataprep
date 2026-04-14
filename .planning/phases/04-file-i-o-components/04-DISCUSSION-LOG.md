# Phase 4: File I/O Components - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 04-file-i-o-components
**Areas discussed:** Rewrite scope, REJECT flow behavior, Config key strategy, Test approach

---

## Rewrite Scope

### Feature Deferral

| Option | Description | Selected |
|--------|-------------|----------|
| UNCOMPRESS (input) | Compressed file reading. Rare in production jobs. | Deferred |
| COMPRESS (output) | ZIP-compressed output writing. | Deferred |
| RANDOM sampling | Random line extraction. Specialized use case. | Deferred |
| ENABLE_DECODE | Hex/octal number decoding. Very niche. | Deferred |
| THOUSANDS/DECIMAL_SEPARATOR | Numeric formatting separators. | Deferred |

**User's choice:** All five deferred to future work (not "v2" — just future work).
**Notes:** User clarified not to use "v2" label. Also deferred SPLIT_RECORD from tFileInputDelimited.

### Java-Specific Concepts

| Option | Description | Selected |
|--------|-------------|----------|
| Defer all three | USESTREAM, ROW_MODE, FLUSHONROW — Java buffer/stream concepts | ✓ |
| Keep FLUSHONROW | Implement flush-on-row-count for output | |

**User's choice:** Defer all three — no Python equivalent needed.

---

## REJECT Flow Behavior

### Rejection Triggers

| Option | Description | Selected |
|--------|-------------|----------|
| Wrong field count | CHECK_FIELDS_NUM: row has wrong number of fields | ✓ |
| Type conversion failure | Field can't convert to schema type | ✓ |
| Date pattern validation | CHECK_DATE: dates must match schema pattern | ✓ |

**User's choice:** All three triggers implemented.
**Notes:** User confirmed all three are in scope.

### Reject Row Content

| Option | Description | Selected |
|--------|-------------|----------|
| Original row + error columns | Talend behavior: all original columns + errorCode + errorMessage | ✓ |
| Error columns only | Just errorCode + errorMessage | |

**User's choice:** Original row + error columns (Talend behavior).

---

## Config Key Strategy

### Key Alignment

| Option | Description | Selected |
|--------|-------------|----------|
| Engine reads converter keys | Engine reads fieldseparator, remove_empty_row, etc. directly. No mapping layer. | ✓ |
| Mapping layer | Engine accepts both old and new keys via mapping dict. | |

**User's choice:** Engine reads converter keys directly. Clean 1:1 match.

### Defaults

| Option | Description | Selected |
|--------|-------------|----------|
| Match Talend defaults | ISO-8859-15, ';', include_header=False | ✓ |
| Keep Python defaults | UTF-8, ',', include_header=True | |

**User's choice:** Match Talend defaults for correctness.

---

## Test Approach

### Fixture Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| tmp_path + small fixture dir | Programmatic creation for most tests, pre-built fixtures for complex cases | ✓ |
| All programmatic | Every test creates own files, no stored fixtures | |

**User's choice:** tmp_path + small fixture dir at tests/v1/engine/fixtures/file/.
**Notes:** User asked about cross-OS path handling — confirmed all paths use pathlib.Path, no hardcoded OS-specific paths. User asked about "multi-byte encoding" and "RFC4180 edge cases" — clarified these are simple concepts (ISO-8859-15 special chars and CSV quoted fields with embedded delimiters).

### Coverage Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Exhaustive per requirement | ~80-120 tests, dedicated test class per requirement | ✓ |
| Happy path + critical edges | ~40-60 tests, lighter coverage | |

**User's choice:** Exhaustive per requirement.

### Integration Tests

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to Phase 12 | Keep Phase 4 focused on unit tests | |
| Add a few now | 2-3 integration tests with real converter output | ✓ |

**User's choice:** Add a few integration tests now for early confidence.

---

## Claude's Discretion

- Internal method decomposition within each component
- Streaming threshold and chunk size
- Single-string read mode handling
- Talend split file naming convention (research determines)
- CSV_OPTION implementation approach

## Deferred Ideas

- UNCOMPRESS, COMPRESS, RANDOM, ENABLE_DECODE, ADVANCED_SEPARATOR — future work
- SPLIT_RECORD — future work
- USESTREAM, ROW_MODE, FLUSHONROW — future work (Java-specific)

---

*Log generated: 2026-04-15*
