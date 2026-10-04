"""Tests for tSortRow -> v2 sort_row converter.

Tests the CRITICAL SORT/ORDER semantic fix: SORT = data-type (NUM/ALPHA/DATE),
ORDER = direction (ASC/DESC). The old converter had these inverted.
"""
from __future__ import annotations

import pytest

from src.converters.talend_to_v2.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v2.components.transform.sort_row_converter import (
    SortRowConverter,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _node(params: dict | None = None) -> TalendNode:
    """Build a minimal TalendNode for tSortRow."""
    return TalendNode(
        component_id="tSortRow_1",
        component_type="tSortRow",
        params=params or {},
        schema={"FLOW": []},
    )


def _criteria(*entries: tuple[str, str, str]) -> list[dict]:
    """Build CRITERIA TABLE flat list from (COLNAME, SORT, ORDER) tuples."""
    result = []
    for colname, sort_type, order in entries:
        result.append({"elementRef": "COLNAME", "value": colname})
        result.append({"elementRef": "SORT", "value": sort_type})
        result.append({"elementRef": "ORDER", "value": order})
    return result


def _flow_conn(name: str, source: str, target: str) -> TalendConnection:
    return TalendConnection(
        name=name, source=source, target=target, connector_type="FLOW"
    )


def _convert(params: dict | None = None, connections: list | None = None) -> ComponentResult:
    """Shortcut: build node and convert."""
    return SortRowConverter().convert(_node(params), connections or [], {})


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSortRowConverter:
    """Converter unit tests for tSortRow -> v2 sort_row."""

    def test_basic_single_column_asc(self) -> None:
        """CRITERIA with one entry: COLNAME=amount, SORT=NUM, ORDER=ASC."""
        result = _convert({"CRITERIA": _criteria(("amount", "NUM", "ASC"))})
        cols = result.component["config"]["columns"]
        assert len(cols) == 1
        assert cols[0] == {"name": "amount", "order": "asc"}
        assert result.component["config"]["maintain_order"] is True
        # SORT value 'NUM' must NOT appear in config
        assert "NUM" not in str(result.component["config"])

    def test_basic_single_column_desc(self) -> None:
        """CRITERIA: COLNAME=price, SORT=ALPHA, ORDER=DESC."""
        result = _convert({"CRITERIA": _criteria(("price", "ALPHA", "DESC"))})
        cols = result.component["config"]["columns"]
        assert cols == [{"name": "price", "order": "desc"}]

    def test_multi_column_sort(self) -> None:
        """CRITERIA with 3 entries: verify correct ordering and SORT values dropped."""
        result = _convert({
            "CRITERIA": _criteria(
                ("name", "ALPHA", "ASC"),
                ("amount", "NUM", "DESC"),
                ("date", "DATE", "ASC"),
            )
        })
        cols = result.component["config"]["columns"]
        assert len(cols) == 3
        assert cols[0] == {"name": "name", "order": "asc"}
        assert cols[1] == {"name": "amount", "order": "desc"}
        assert cols[2] == {"name": "date", "order": "asc"}
        # SORT type values must be absent from config
        for sort_type in ("ALPHA", "NUM", "DATE"):
            assert sort_type not in str(result.component["config"])

    def test_sort_order_semantics_not_inverted(self) -> None:
        """CRITICAL: SORT=DESC should NOT produce descending order.

        ORDER=ASC is the direction field. The old converter read SORT
        for direction -- this test proves the fix.
        """
        result = _convert({"CRITERIA": _criteria(("col", "DESC", "ASC"))})
        cols = result.component["config"]["columns"]
        assert cols[0]["order"] == "asc"  # from ORDER field, NOT SORT

    def test_sort_type_dropped(self) -> None:
        """SORT=DATE must not appear anywhere in column config."""
        result = _convert({"CRITERIA": _criteria(("created_at", "DATE", "ASC"))})
        col = result.component["config"]["columns"][0]
        assert "sort_type" not in col
        assert "sort" not in col
        assert "DATE" not in str(col)

    def test_maintain_order_always_true(self) -> None:
        """Converter always emits maintain_order=True (Talend sort is stable)."""
        result = _convert({"CRITERIA": _criteria(("x", "NUM", "ASC"))})
        assert result.component["config"]["maintain_order"] is True

    def test_empty_criteria(self) -> None:
        """No CRITERIA param produces empty columns list."""
        result = _convert({})
        assert result.component["config"]["columns"] == []

    def test_external_sort_warning(self) -> None:
        """EXTERNAL=true triggers a grouped NOT_PLANNED warning."""
        result = _convert({
            "CRITERIA": _criteria(("x", "NUM", "ASC")),
            "EXTERNAL": '"true"',
            "TEMPFILE": '"/tmp"',
            "CREATEDIR": '"true"',
            "EXTERNAL_SORT_BUFFERSIZE": '"1000000"',
        })
        assert len(result.warnings) == 1
        assert "NOT_PLANNED" in result.warnings[0]
        assert "Polars handles large dataset sorting natively" in result.warnings[0]

    def test_tstatcatcher_warning(self) -> None:
        """TSTATCATCHER_STATS=true triggers NOT_PLANNED warning."""
        result = _convert({
            "CRITERIA": _criteria(("x", "NUM", "ASC")),
            "TSTATCATCHER_STATS": '"true"',
        })
        assert any("NOT_PLANNED" in w for w in result.warnings)
        assert any("TSTATCATCHER_STATS" in w for w in result.warnings)

    def test_label_extraction(self) -> None:
        """LABEL is extracted with quotes stripped."""
        result = _convert({
            "CRITERIA": _criteria(("x", "NUM", "ASC")),
            "LABEL": '"my sort"',
        })
        assert result.component["config"]["label"] == "my sort"

    def test_order_defaults_to_asc(self) -> None:
        """Missing ORDER field defaults to 'asc'."""
        # Build criteria manually with only COLNAME and SORT (no ORDER)
        params = {
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": "amount"},
                {"elementRef": "SORT", "value": "NUM"},
            ]
        }
        result = _convert(params)
        cols = result.component["config"]["columns"]
        # _parse_table_rows will produce one row with COLNAME and SORT keys
        # ORDER will be missing, so default "asc" applies
        assert len(cols) == 1
        assert cols[0]["order"] == "asc"

    def test_type_is_sort_row(self) -> None:
        """Component type must be 'sort_row'."""
        result = _convert({"CRITERIA": _criteria(("x", "NUM", "ASC"))})
        assert result.component["type"] == "sort_row"

    def test_flows_built(self) -> None:
        """Connections are correctly mapped to flows."""
        connections = [
            _flow_conn("row1", "tMap_1", "tSortRow_1"),
            _flow_conn("row2", "tSortRow_1", "tFileOutputDelimited_1"),
        ]
        result = SortRowConverter().convert(_node({"CRITERIA": []}), connections, {})
        assert len(result.flows) == 2
        sources = {f["source"] for f in result.flows}
        targets = {f["target"] for f in result.flows}
        assert "tMap_1" in sources
        assert "tSortRow_1" in sources
        assert "tSortRow_1" in targets
        assert "tFileOutputDelimited_1" in targets

    def test_no_needs_review(self) -> None:
        """SortRow converter should produce no needs_review entries."""
        result = _convert({"CRITERIA": _criteria(("x", "NUM", "ASC"))})
        assert result.needs_review == []

    def test_no_nulls_last_emitted(self) -> None:
        """Converter must NOT emit nulls_last -- Talend has no equivalent.

        Addresses Gemini review suggestion 2: null positioning differences
        are handled by omission, since Talend has no equivalent control.
        """
        result = _convert({
            "CRITERIA": _criteria(
                ("name", "ALPHA", "ASC"),
                ("amount", "NUM", "DESC"),
            )
        })
        config = result.component["config"]
        assert "nulls_last" not in config
        for col in config["columns"]:
            assert "nulls_last" not in col

    def test_quoted_colname_stripped(self) -> None:
        """Column names with surrounding quotes are stripped."""
        result = _convert({
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"amount"'},
                {"elementRef": "SORT", "value": '"NUM"'},
                {"elementRef": "ORDER", "value": '"DESC"'},
            ]
        })
        cols = result.component["config"]["columns"]
        assert cols[0]["name"] == "amount"
        assert cols[0]["order"] == "desc"


class TestSortRowConverterRegistry:
    """Verify converter is registered in the converter registry."""

    def test_registry_lookup(self) -> None:
        from src.converters.talend_to_v2.components.registry import REGISTRY
        # Trigger side-effect import via transform package
        import src.converters.talend_to_v2.components.transform  # noqa: F401

        assert REGISTRY.get("tSortRow") is not None
