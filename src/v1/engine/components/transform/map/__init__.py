"""tMap component (modular rewrite).

See ``docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md`` for the
design. The legacy ``map_legacy.py`` module was removed in Phase 11
(closeout); Phase 10's diff harness confirmed bit-for-bit parity on all
testable fixtures.
"""
from .map_component import Map  # noqa: F401

__all__ = ["Map"]
