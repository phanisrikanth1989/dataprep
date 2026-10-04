"""
Feature support declarations for v2 components.

Provides the types and helpers that every v2 component uses to declare
which Talend features it supports, partially supports, or explicitly
excludes.  The declarations power:

- ``talend_to_v2`` converter warnings (unsupported features at convert time)
- Registry-completeness tests (every registered component must declare)
- Auto-generated v2-native documentation feature tables
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

__all__ = ["Support", "FeatureSupport", "get_supported_features"]


class Support(str, Enum):
    """Level of support for a Talend feature in a v2 component."""

    FULL = "full"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_PLANNED = "not_planned"


@dataclass(frozen=True)
class FeatureSupport:
    """Declaration of how a v2 component handles a specific Talend feature."""

    support: Support
    note: str = ""


def get_supported_features(cls) -> Dict[str, FeatureSupport]:
    """Return the SUPPORTED_FEATURES dict declared on a component class.

    Self-contained lookup -- returns cls.SUPPORTED_FEATURES directly
    with no parent/MRO merging.  Each component's declared dict is
    authoritative for itself.
    """
    return getattr(cls, "SUPPORTED_FEATURES", {})
