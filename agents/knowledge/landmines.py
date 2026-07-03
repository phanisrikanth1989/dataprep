"""Code-verified config landmines for the recon slice (from config-surfaces.md + spec)."""
from __future__ import annotations

_MAP_ALIASES = {"Map", "tMap"}

LANDMINES = [
    {"id": "die-on-error-dual-default", "component": None,
     "summary": "die_on_error defaults True in BaseComponent but False in several components' own reads.",
     "code_anchor": "base_component.py:234 vs e.g. file_input_delimited.py:173",
     "guidance": "Always set die_on_error explicitly; do not rely on the default."},
    {"id": "tmap-operator-noop", "component": "Map",
     "summary": "tMap join_key operator is parsed but read by no join path; matching is equality-only.",
     "code_anchor": "map_config.py:38,115; map_joins.py (equality merge)",
     "guidance": "Only operator '=' is meaningful. Model tolerance as exact-join + post-join split, never operator '<='."},
    {"id": "tmap-matching-mode-drops-dups", "component": "Map",
     "summary": "matching_mode default UNIQUE_MATCH silently keeps only the last duplicate lookup row, no break.",
     "code_anchor": "map_joins.py:446-463; map_config.py:46,55",
     "guidance": "For a non-unique lookup key use ALL_MATCHES + explicit duplicate handling; UNIQUE_MATCH hides dups."},
    {"id": "tmap-catch-output-reject-error-only", "component": "Map",
     "summary": "catch_output_reject captures expression ERRORS only, not filter-rejects; it cancels die_on_error propagation.",
     "code_anchor": "map_reject_routing.py:82-153; map_compiled_script.py:405",
     "guidance": "Use is_reject (or complementary output filters) for business/tolerance breaks; never catch_output_reject."},
    {"id": "tmap-pattern-vs-date-pattern", "component": "Map",
     "summary": "tMap output column date format: dataclass reads 'date_pattern' but the converter emits 'pattern' -> date formatting silently unwired.",
     "code_anchor": "map_config.py:149 vs converter transform/map.py:251",
     "guidance": "Emit the column date format under 'pattern' (schema accepts both); do not rely on 'date_pattern'."},
    {"id": "tmap-join-mode-values", "component": "Map",
     "summary": "tMap lookup join_mode is neither schema- nor engine-validated; only LEFT_OUTER_JOIN and INNER_JOIN are honored by the join path.",
     "code_anchor": "map_config.py:50-58 (LookupCfg.join_mode default LEFT_OUTER_JOIN); map_joins.py (join execution)",
     "guidance": "Set join_mode to exactly LEFT_OUTER_JOIN or INNER_JOIN; any other string silently degrades to the LEFT_OUTER_JOIN default. The oracle is the only backstop."},
    {"id": "tmap-matching-mode-values", "component": "Map",
     "summary": "tMap matching_mode is neither schema- nor engine-validated; valid values are UNIQUE_MATCH, FIRST_MATCH, ALL_MATCHES, ALL_ROWS.",
     "code_anchor": "map_config.py:41-58 (MainInputCfg/LookupCfg.matching_mode default UNIQUE_MATCH); map_joins.py:446-463",
     "guidance": "Use one of UNIQUE_MATCH, FIRST_MATCH, ALL_MATCHES, ALL_ROWS; UNIQUE_MATCH keeps only the last duplicate lookup row (see tmap-matching-mode-drops-dups). Invalid strings are not rejected."},
    {"id": "tmap-lookup-mode-values", "component": "Map",
     "summary": "tMap lookup_mode is neither schema- nor engine-validated; valid values are LOAD_ONCE, RELOAD, CACHE_OR_RELOAD.",
     "code_anchor": "map_config.py:41-58 (MainInputCfg/LookupCfg.lookup_mode default LOAD_ONCE)",
     "guidance": "Set lookup_mode to LOAD_ONCE, RELOAD, or CACHE_OR_RELOAD; neither the schema nor the engine rejects invalid values, so rely on the oracle/reference diff."},
    {"id": "reject-is-a-data-flow", "component": None,
     "summary": "Reject is a data flow (type 'reject'), not a trigger; it routes through flows[], not triggers[].",
     "code_anchor": "output_router.py:22-29",
     "guidance": "Wire rejects as flows with type 'reject', not as OnComponentError triggers."},
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
