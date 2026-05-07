"""Database component package. Component classes register via @REGISTRY.register
at import time (Phase 3 D-04 decorator pattern). Plans 11-03, 11-04 will append
OracleRow / OracleOutput.
"""
from .oracle_connection import OracleConnection  # noqa: F401

__all__ = ["OracleConnection"]
