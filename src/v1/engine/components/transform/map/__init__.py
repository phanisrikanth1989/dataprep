"""tMap component (modular rewrite). See docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md.

The Map class now comes from the modular map_component.py. The legacy
map_legacy.py module remains in the repo: (a) some existing tests still
import private symbols from this package's path, and they continue to
resolve to legacy via the explicit re-exports below; (b) the diff harness
in Phase 10 can import the legacy class as `LegacyMap` for side-by-side
comparison. After Phase 11 closeout, map_legacy.py is removed.
"""
from .map_component import Map  # noqa: F401

# Re-export private symbols still consumed by legacy-era tests via the
# `from src.v1.engine.components.transform.map import _X` path. These
# resolve to the LEGACY definitions in map_legacy.py; they exercise the
# legacy code path until Phase 8 triage decides KEEP / FIX / DELETE per
# test.
from ..map_legacy import (  # noqa: F401
    _WARN_RESULT_ROWS,
    _FAIL_RESULT_ROWS,
    _LOCALITY_CONTEXT,
    _LOCALITY_MAIN_SIDE,
    _LOCALITY_LOOKUP_SIDE,
    _LOCALITY_TWO_SIDED,
    _VarBag,
    _NullRow,
    _infer_arrow_schema_dict,
)

__all__ = ["Map"]
