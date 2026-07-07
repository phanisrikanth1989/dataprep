"""Code-verified config landmines for the ETL component set (from config-surfaces.md + spec)."""
from __future__ import annotations

_MAP_ALIASES = {"Map", "tMap"}

LANDMINES = [
    {"id": "die-on-error-dual-default", "component": None,
     "summary": "die_on_error defaults True in BaseComponent but False in several components' own reads -- AND the read KEY NAME is per-component: some components read it under a different key (e.g. ConvertType reads 'dieonerror', not 'die_on_error').",
     "code_anchor": "base_component.py:234 (die_on_error default True) vs file_input_delimited.py:173 (local 'die_on_error' default False) vs convert_type.py:140 (reads 'dieonerror')",
     "guidance": "Always set the die-on-error flag explicitly using the EXACT key name for that component type -- check config-reference.md for the per-type key -- and do not rely on the default (dual-default: True in base, False locally)."},
    {"id": "tmap-operator-noop", "component": "Map",
     "summary": "tMap join_key operator is parsed but read by no join path; matching is equality-only.",
     "code_anchor": "map_config.py:38,115; map_joins.py (equality merge)",
     "guidance": "Only operator '=' is honored (an inequality key is silently ignored); model a range/threshold rule as an exact join plus a post-join FilterRows/derive, never '<='."},
    {"id": "tmap-matching-mode-drops-dups", "component": "Map",
     "summary": "matching_mode default UNIQUE_MATCH silently keeps only the last duplicate lookup row, with no error or warning.",
     "code_anchor": "map_joins.py:446-463; map_config.py:46,55",
     "guidance": "For a non-unique lookup key use ALL_MATCHES + explicit duplicate handling; UNIQUE_MATCH hides dups."},
    {"id": "tmap-catch-output-reject-error-only", "component": "Map",
     "summary": "catch_output_reject captures expression ERRORS only, not filter-rejects; it cancels die_on_error propagation.",
     "code_anchor": "map_reject_routing.py:82-153; map_compiled_script.py:405",
     "guidance": "Use is_reject (or complementary output filters) for business/validation rejects; never catch_output_reject."},
    {"id": "tmap-pattern-vs-date-pattern", "component": "Map",
     "summary": "tMap output-column date formatting is driven by the column EXPRESSION, not a config key: BOTH 'pattern' and 'date_pattern' on a tMap output column are parsed but consumed by no code path.",
     "code_anchor": "map_config.py:29,149 (date_pattern parsed into a field with no consumer); map_compiled_script.py:227 (col.expression is the value driver)",
     "guidance": "Format a tMap date INSIDE the column's {{java}} expression (e.g. TalendDate.formatDate(\"yyyy-MM-dd\", ...)); a 'pattern'/'date_pattern' key on a tMap column is dead. NOTE: schema-level date_pattern IS live for File I/O, ConvertType, and SchemaComplianceCheck -- this landmine is tMap-only."},
    {"id": "tmap-requires-java-config", "component": "Map",
     "summary": "A tMap/Map job REQUIRES a top-level java_config.enabled=true; without it the tMap component crashes with \"'NoneType' object has no attribute 'compile_tmap_script'\".",
     "code_anchor": "map_component.py (unconditional self.java_bridge.compile_tmap_script call); engine.py (java bridge attached only when java_config.enabled=true)",
     "guidance": "Always include a top-level java_config.enabled=true block (with the standard routines) for any job containing a Map/tMap component, and mark tMap expressions with a {{java}} prefix so a dropped block raises the friendly bridge-missing error instead of a raw AttributeError."},
    {"id": "tmap-join-mode-values", "component": "Map",
     "summary": "tMap lookup join_mode is neither schema- nor engine-validated; only LEFT_OUTER_JOIN and INNER_JOIN are honored by the join path.",
     "code_anchor": "map_config.py:50-58 (LookupCfg.join_mode default LEFT_OUTER_JOIN); map_joins.py (join execution)",
     "guidance": "Set join_mode to exactly LEFT_OUTER_JOIN or INNER_JOIN; any other string silently degrades to the LEFT_OUTER_JOIN default. The oracle is the only backstop."},
    {"id": "tmap-matching-mode-values", "component": "Map",
     "summary": "tMap matching_mode is neither schema- nor engine-validated; the engine recognizes only UNIQUE_MATCH, FIRST_MATCH, ALL_MATCHES. ALL_ROWS is NOT a distinct mode -- it silently aliases UNIQUE_MATCH keep-last.",
     "code_anchor": "map_config.py:41-58 (MainInputCfg/LookupCfg.matching_mode default UNIQUE_MATCH); map_joins.py:455-463 (_apply_matching_mode branches only on ALL_MATCHES/FIRST_MATCH; everything else keeps last)",
     "guidance": "Use one of UNIQUE_MATCH, FIRST_MATCH, ALL_MATCHES; UNIQUE_MATCH keeps only the last duplicate lookup row (see tmap-matching-mode-drops-dups). ALL_ROWS (and any other invalid string) is not rejected -- it silently falls through to the UNIQUE_MATCH keep-last branch, giving wrong output on a duplicate-key lookup."},
    {"id": "tmap-lookup-mode-values", "component": "Map",
     "summary": "tMap lookup_mode is neither schema- nor engine-validated; the engine recognizes only LOAD_ONCE (default) and RELOAD_AT_EACH_ROW. RELOAD and CACHE_OR_RELOAD are NOT recognized and silently act as LOAD_ONCE.",
     "code_anchor": "map_joins.py:67 (only 'RELOAD_AT_EACH_ROW' triggers per-row reload); py_map.py:63,383 (same literal); map_config.py:41-58 (lookup_mode default LOAD_ONCE)",
     "guidance": "Set lookup_mode to LOAD_ONCE (default) or RELOAD_AT_EACH_ROW only. RELOAD/CACHE_OR_RELOAD are not rejected but silently degrade to LOAD_ONCE (lookup loaded once, no per-row reload) -- rely on the oracle/reference diff."},
    {"id": "tmap-lookup-mode-placement", "component": "Map",
     "summary": "tMap matching_mode/lookup_mode belong on the per-lookup entry (inputs.lookups[]), NOT inputs.main",
     "code_anchor": "map_config.py:103-104 (parsed on main, never consumed) vs map_joins.py (read off the lookup)",
     "guidance": "Put matching_mode/lookup_mode on each inputs.lookups[] entry; a value on inputs.main is silently ignored and the lookup defaults to UNIQUE_MATCH/LOAD_ONCE."},
    {"id": "sortrow-alpha-default", "component": "SortRow",
     "summary": "SortRow sort_type defaults to 'alpha' (lexicographic); numeric/date columns mis-sort as strings",
     "code_anchor": "sort_row.py:104,107 (alpha default), :108-112 (num/date coercion only)",
     "guidance": "Set sort_type to 'num' or 'date' for any non-string sort column ('10' sorts before '9', dates non-chronologically under alpha). The order-insensitive oracle will NOT catch a mis-typed sort."},
    {"id": "sortrow-external-noop", "component": "SortRow",
     "summary": "SortRow `external` (external/disk sort) is NOT implemented -- accepted but ignored; SortRow always sorts fully in memory",
     "code_anchor": "sort_row.py:87-91 (external read, then only logged and ignored)",
     "guidance": "Do not rely on `external` for large-input memory relief; there is none. Shrink the input upstream or expect full in-memory sort."},
    {"id": "reject-is-a-data-flow", "component": None,
     "summary": "Reject is a data flow (type 'reject'), not a trigger; it routes through flows[], not triggers[].",
     "code_anchor": "output_router.py:22-29",
     "guidance": "Wire rejects as flows with type 'reject', not as OnComponentError triggers."},
    {"id": "tjoin-needs-use-lookup-cols", "component": "Join",
     "summary": "A tJoin/Join adds NO lookup columns to the output unless use_lookup_cols=True AND a lookup_cols list is supplied; by default only the main-input columns pass through.",
     "code_anchor": "join.py:158-159 (use_lookup_cols default False, lookup_cols default []); join.py:231 (lookup columns kept only when both are truthy)",
     "guidance": "To add lookup columns via Join, set use_lookup_cols: true AND lookup_cols: [{output_column, lookup_column}, ...]; otherwise the join only filters/matches main rows. For column-adding lookups prefer tMap/PyMap."},
]


def landmines_for(component_type: str) -> list:
    """Return landmines whose component matches (by type/alias) or is global (None)."""
    matches = []
    for lm in LANDMINES:
        comp = lm["component"]
        if comp is None:
            matches.append(lm)
        elif comp == component_type or (component_type in _MAP_ALIASES and comp in _MAP_ALIASES):
            matches.append(lm)
    return matches
