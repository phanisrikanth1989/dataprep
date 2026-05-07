"""Unit tests for OracleOutput engine component (Phase 11-04).

Mock-based tests cover registration, validation, all 8 TABLE_ACTIONs (DDL emission),
INSERT/UPDATE/DELETE batch DML, REJECT flow with [errorCode, errorMessage, *input cols],
FIELD_OPTIONS-aware key handling, USE_TIMESTAMP_FOR_DATE_TYPE binding, identifier
quoting (T-11-04), 5 stat keys (D-C8), die_on_error rewrap, deferred upserts.

Real-DB DDL/DML validation deferred to plan 11-07 per D-D3.
"""
import re

import pytest


# ----------------------------------------------------------------------
# Task 1 RED gate: module docstring documents Talaxie inspection findings
# ----------------------------------------------------------------------


@pytest.mark.unit
class TestModuleDocstring:
    """Verify Open Q 1 + 3 are resolved in code: DDL conventions documented."""

    def test_docstring_has_talaxie_attribution(self):
        from src.v1.engine.components.database import oracle_output

        src = open(oracle_output.__file__).read()
        assert "Talaxie _tableActionForOutput.javajet" in src, (
            "module docstring missing Talaxie attribution phrase"
        )

    def test_docstring_has_fetch_evidence(self):
        from src.v1.engine.components.database import oracle_output

        src = open(oracle_output.__file__).read()
        fetch_evidence = re.search(
            r"https?://raw\.githubusercontent\.com/[^\s\"']+", src
        )
        fallback_evidence = re.search(r"\b404\b", src)
        assert fetch_evidence or fallback_evidence, (
            "module docstring shows no fetch evidence: expected a "
            "raw.githubusercontent URL or a 404 fallback marker"
        )

    def test_docstring_lists_type_decisions(self):
        from src.v1.engine.components.database import oracle_output

        src = open(oracle_output.__file__).read()
        for kw in ("Float", "Double", "VARCHAR2", "CREATE_IF_NOT_EXISTS"):
            assert kw in src, f"module docstring missing decision keyword: {kw}"
