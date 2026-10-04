"""
ETL Engine v2 - Python-native Implementation

A high-performance ETL engine built with Polars for data processing.
"""

__version__ = "2.0.0"


def __getattr__(name):
    """Lazy import to avoid circular / broken imports during migration."""
    if name == "PyETLEngine":
        from .engine import PyETLEngine
        return PyETLEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ['PyETLEngine']
