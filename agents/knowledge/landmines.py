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
