"""tMap component (modular rewrite). See docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md.

This package is being built incrementally. Until map_component.py is wired in,
``Map`` is re-exported from the legacy single-file implementation so existing
job configs continue to run unchanged.
"""
from ..map_legacy import Map  # noqa: F401
# Re-export private symbols so existing tests that import directly from this
# package path continue to resolve (transparent re-export from the legacy file).
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
