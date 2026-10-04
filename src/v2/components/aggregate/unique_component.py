"""DEPRECATED: Unique has been restructured to UniqRow at transform/uniq_row.py.

This stub remains only to avoid import errors in any code that hasn't been
updated yet. New code should import from src.v2.components.transform.uniq_row.
"""
from src.v2.components.transform.uniq_row import UniqRow as Unique  # noqa: F401

__all__ = ["Unique"]
