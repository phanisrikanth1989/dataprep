# Config landmines (respect these)

- **die-on-error-dual-default** (GLOBAL): die_on_error defaults True in BaseComponent but False in several components' own reads.
  - guidance: Always set die_on_error explicitly; do not rely on the default.
- **tmap-operator-noop** (Map): tMap join_key operator is parsed but read by no join path; matching is equality-only.
  - guidance: Only operator '=' is meaningful. Model tolerance as exact-join + post-join split, never operator '<='.
- **tmap-matching-mode-drops-dups** (Map): matching_mode default UNIQUE_MATCH silently keeps only the last duplicate lookup row, no break.
  - guidance: For a non-unique lookup key use ALL_MATCHES + explicit duplicate handling; UNIQUE_MATCH hides dups.
- **tmap-catch-output-reject-error-only** (Map): catch_output_reject captures expression ERRORS only, not filter-rejects; it cancels die_on_error propagation.
  - guidance: Use is_reject (or complementary output filters) for business/tolerance breaks; never catch_output_reject.
- **tmap-pattern-vs-date-pattern** (Map): tMap output column date format: dataclass reads 'date_pattern' but the converter emits 'pattern' -> date formatting silently unwired.
  - guidance: Emit the column date format under 'pattern' (schema accepts both); do not rely on 'date_pattern'.
- **tmap-join-mode-values** (Map): tMap lookup join_mode is neither schema- nor engine-validated; only LEFT_OUTER_JOIN and INNER_JOIN are honored by the join path.
  - guidance: Set join_mode to exactly LEFT_OUTER_JOIN or INNER_JOIN; any other string silently degrades to the LEFT_OUTER_JOIN default. The oracle is the only backstop.
- **tmap-matching-mode-values** (Map): tMap matching_mode is neither schema- nor engine-validated; valid values are UNIQUE_MATCH, FIRST_MATCH, ALL_MATCHES, ALL_ROWS.
  - guidance: Use one of UNIQUE_MATCH, FIRST_MATCH, ALL_MATCHES, ALL_ROWS; UNIQUE_MATCH keeps only the last duplicate lookup row (see tmap-matching-mode-drops-dups). Invalid strings are not rejected.
- **tmap-lookup-mode-values** (Map): tMap lookup_mode is neither schema- nor engine-validated; valid values are LOAD_ONCE, RELOAD, CACHE_OR_RELOAD.
  - guidance: Set lookup_mode to LOAD_ONCE, RELOAD, or CACHE_OR_RELOAD; neither the schema nor the engine rejects invalid values, so rely on the oracle/reference diff.
- **reject-is-a-data-flow** (GLOBAL): Reject is a data flow (type 'reject'), not a trigger; it routes through flows[], not triggers[].
  - guidance: Wire rejects as flows with type 'reject', not as OnComponentError triggers.