---
phase: 10-iterate-support
plan: "09"
subsystem: tests/integration
tags: [bug-fix, test-quality, silent-test-rot, gap-closure]
gap_closure: true
requirements: [TEST-04]

dependency_graph:
  requires: []
  provides: [correct-_needs_review-key-in-e2e-tests]
  affects: [tests/integration/test_iterate_e2e.py]

tech_stack:
  added: []
  patterns: [synthetic-result-injection for gate regression guard]

key_files:
  created: []
  modified:
    - tests/integration/test_iterate_e2e.py

decisions:
  - "No unittest.mock.patch needed: the new regression guard test operates directly on a synthetic dict, not a patched convert_job call. Simpler and equally effective."

metrics:
  duration: ~5 minutes
  completed: "2026-05-05T20:00:36Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 10 Plan 09: Fix `_needs_review` Key Typo in E2E Tests Summary

Fix silent test rot: two fatal-error acceptance gates in `test_iterate_e2e.py` were no-ops because they used `"needs_review"` (no leading underscore) while `converter.py:172` writes `"_needs_review"`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix wrong dict key at lines 160 and 323 | 1610602 | tests/integration/test_iterate_e2e.py |
| 2 | Prove gate fires with synthetic fatal entry | 6332192 | tests/integration/test_iterate_e2e.py |

## What Was Done

**Task 1 - Key fix:**
`TestJobTFileListConversion.test_converts_without_errors` (line 160) and `TestJobTFlowToIterateConversion.test_converts_without_errors` (line 323) both called `result.get("needs_review", [])`. Since `TalendToV1Converter.convert_file()` writes fatal items under `"_needs_review"` (with leading underscore at `converter.py:172`), the filter list was always empty and the `assert not fatal` always passed silently regardless of conversion errors.

Both occurrences replaced with `result.get("_needs_review", [])`. Verified with grep: 4 occurrences of the correct key, 0 of the wrong one.

**Task 2 - Regression guard:**
Added `test_fatal_needs_review_gate_fires` to `TestJobTFileListConversion`. The test builds a synthetic result dict containing `{"_needs_review": [{"severity": "error", "message": "synthetic fatal error"}]}` and applies the gate logic directly, then asserts the fatal list is non-empty. This proves the gate fires with the correct key and prevents silent test rot from returning.

## Deviations from Plan

None - plan executed exactly as written.

The plan mentioned `unittest.mock.patch` as a possible approach for the regression guard test, but the actual test body in the plan spec needed no patching (it applied gate logic to a synthetic dict directly). No `unittest.mock` import was required.

## Acceptance Verification

```
grep -c '"_needs_review"' tests/integration/test_iterate_e2e.py
# Result: 4 (2 fix sites + 2 in gate test)

grep -v '^#' tests/integration/test_iterate_e2e.py | grep -c '"needs_review"'
# Result: 0

pytest tests/integration/test_iterate_e2e.py -q -m "not java"
# Result: 5 passed, 1 skipped (coverage marker)
```

## Self-Check: PASSED

- [x] `tests/integration/test_iterate_e2e.py` exists and contains `"_needs_review"` at 4 sites
- [x] Commit `1610602` exists (Task 1: key fix)
- [x] Commit `6332192` exists (Task 2: gate regression guard)
- [x] `test_fatal_needs_review_gate_fires` method exists at line 167
- [x] 5 non-java tests pass, 0 fail
