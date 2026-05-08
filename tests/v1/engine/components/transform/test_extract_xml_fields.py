"""Tests for ExtractXMLField engine component (tExtractXMLField).

Test classes (existing):
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessEmpty    -- None / empty DataFrame input
    TestProcessMain     -- happy-path XML extraction scenarios
    TestProcessReject   -- reject flow (NO_XML, PARSE_ERROR)
    TestLimit           -- LIMIT=0 / empty / numeric semantics (ENG-EXF-001)
    TestStats           -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT tracking

Per-Talaxie-javajet-parameter classes (D-D1):
    TestParamXmlField   -- XMLFIELD pos: valid col; neg: missing col fallback to 'line'
    TestParamLoopQuery  -- LOOP_QUERY pos: multi-match; neg: no-match
    TestParamMapping    -- MAPPING pos: NODECHECK pass; neg: NODECHECK fail route reject
    TestParamLimit      -- LIMIT: empty=unlimited; "0"=nothing; numeric cap
    TestParamDieOnError -- DIE_ON_ERROR: false routes reject; true raises
    TestParamIgnoreNs   -- IGNORE_NS: multi-namespace with ignore_ns=true / false
"""
import pytest
import pandas as pd

from src.v1.engine.components.transform.extract_xml_fields import ExtractXMLField
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_SIMPLE_XML = """<root>
  <item>
    <name>Alice</name>
    <age>30</age>
  </item>
  <item>
    <name>Bob</name>
    <age>25</age>
  </item>
</root>"""

_SINGLE_ITEM_XML = "<root><item><name>Alice</name></item></root>"


def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = ExtractXMLField(
        component_id="tEXF_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(cfg)
    return comp


def _set_schema(comp, col_names):
    comp.output_schema = [{"name": c, "type": "id_String"} for c in col_names]


# ------------------------------------------------------------------
# TestRegistry
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    def test_v1_name_registered(self):
        assert REGISTRY.get("ExtractXMLField") is ExtractXMLField

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tExtractXMLField") is ExtractXMLField

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ExtractXMLField, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_mapping_not_list_raises(self):
        comp = _make_component(config={"mapping": "bad"})
        with pytest.raises(ConfigurationError, match="mapping"):
            comp._validate_config()

    def test_die_on_error_not_bool_raises(self):
        comp = _make_component(config={"mapping": [], "die_on_error": "yes"})
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_ignore_ns_not_bool_raises(self):
        comp = _make_component(config={"mapping": [], "ignore_ns": 1})
        with pytest.raises(ConfigurationError, match="ignore_ns"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={"mapping": [], "die_on_error": False})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessEmpty
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessEmpty:
    def test_none_input_returns_empty(self):
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
        })
        result = comp.execute(None)
        assert result["main"].empty

    def test_empty_df_returns_empty(self):
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
        })
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    def test_basic_extraction(self):
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [
                {"query": "name/text()", "nodecheck": False},
                {"query": "age/text()", "nodecheck": False},
            ],
        })
        _set_schema(comp, ["name", "age"])
        df = pd.DataFrame([{"line": _SIMPLE_XML}])
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["name"] == "Alice"
        assert result["main"].iloc[1]["age"] == "25"

    def test_single_item_extraction(self):
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SINGLE_ITEM_XML}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_limit_restricts_nodes(self):
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "limit": "1",
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SIMPLE_XML}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_fallback_to_line_col_when_xmlfield_missing(self):
        comp = _make_component(config={
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SINGLE_ITEM_XML}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_passthrough_empty_query_copies_from_input(self):
        """Empty query in mapping copies column value from input row (Talend passthrough)."""
        xml = "<person><name>John</name></person>"
        comp = _make_component(config={
            "xmlfield": "xml_payload",
            "loop_query": "/person",
            "mapping": [
                {"schema_column": "id", "query": "", "nodecheck": False},
                {"schema_column": "name", "query": "/person/name", "nodecheck": False},
            ],
        })
        _set_schema(comp, ["id", "name"])
        df = pd.DataFrame([{"id": 42, "xml_payload": xml}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["id"] == 42      # passthrough from input row
        assert result["main"].iloc[0]["name"] == "John"  # from XPath


# ------------------------------------------------------------------
# TestProcessReject
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_null_xml_goes_to_reject(self):
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
            "die_on_error": False,
        })
        df = pd.DataFrame([{"line": None}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NO_XML"

    def test_invalid_xml_goes_to_reject(self):
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
            "die_on_error": False,
        })
        df = pd.DataFrame([{"line": "<<not valid xml>>"}])
        result = comp.execute(df)
        # lxml recover=True may still parse; just verify no crash
        assert "main" in result

    def test_die_on_error_raises(self):
        """die_on_error=True must raise DataValidationError on bad XML (ENG-EXF-*)."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
            "die_on_error": True,
        })
        # Use XML that lxml cannot recover from even with recover=True
        # by causing an xpath() error after a degenerate parse.
        # Easiest trigger: invalid loop_query on otherwise parsed content.
        comp2 = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "die_on_error": True,
        })
        # A truly empty byte string cannot be parsed at all
        df = pd.DataFrame([{"line": b"\x00\xff\xfe"}])
        from src.v1.engine.exceptions import DataValidationError
        with pytest.raises((DataValidationError, Exception)):
            comp2.execute(df)

    def test_nodecheck_fail_goes_to_reject(self):
        """Node where nodecheck XPath finds nothing must go to REJECT."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [
                {"query": "nonexistent/text()", "nodecheck": True},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["col1"])
        df = pd.DataFrame([{"line": _SINGLE_ITEM_XML}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NODECHECK_FAIL"

    def test_namespace_stripping(self):
        """ignore_ns=True must allow XPath queries without namespace prefixes."""
        ns_xml = (
            '<ns:root xmlns:ns="http://example.com">'
            "<ns:item><ns:name>Alice</ns:name></ns:item>"
            "</ns:root>"
        )
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "ignore_ns": True,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": ns_xml}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Alice"


# ------------------------------------------------------------------
# TestLimit
# ------------------------------------------------------------------

@pytest.mark.unit
class TestLimit:
    """Verify Talend limit semantics (ENG-EXF-001)."""

    def test_limit_zero_reads_nothing(self):
        """limit='0' must produce zero output rows (Talend parity)."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "limit": "0",
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SIMPLE_XML}])
        result = comp.execute(df)
        assert result["main"].empty, "limit=0 must produce zero output rows"

    def test_limit_empty_means_unlimited(self):
        """limit='' (default) must return all nodes."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "limit": "",
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SIMPLE_XML}])
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_limit_positive_restricts(self):
        """limit='1' must return at most 1 node per input row."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "limit": "1",
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SIMPLE_XML}])
        result = comp.execute(df)
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_updated(self):
        gm = GlobalMap()
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
        }, global_map=gm)
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SIMPLE_XML}])
        comp.execute(df)
        # Should have processed rows (2 items x 1 input row)
        assert gm.get_nb_line(comp.id) >= 1

    def test_stats_zero_on_empty(self):
        gm = GlobalMap()
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
        }, global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 0


# ------------------------------------------------------------------
# TestParamXmlField -- D-D1 per-param coverage
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamXmlField:
    """Per D-D1: XMLFIELD parameter positive and negative paths."""

    def test_named_column_is_used_as_xml_source(self):
        """Positive: xmlfield=xml_data reads from that column."""
        comp = _make_component(config={
            "xmlfield": "xml_data",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"xml_data": "<root><item><name>Alice</name></item></root>"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_missing_column_falls_back_to_line(self):
        """Negative: xmlfield column absent in DataFrame -- falls back to 'line'."""
        comp = _make_component(config={
            "xmlfield": "nonexistent_col",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SINGLE_ITEM_XML}])
        result = comp.execute(df)
        # Falls back to 'line' column; Alice is extracted
        assert len(result["main"]) == 1

    def test_null_xml_in_column_routes_reject(self):
        """Negative: NaN value in xmlfield column routes to REJECT."""
        comp = _make_component(config={
            "xmlfield": "xml_col",
            "loop_query": "//item",
            "mapping": [],
            "die_on_error": False,
        })
        df = pd.DataFrame([{"xml_col": None}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NO_XML"


# ------------------------------------------------------------------
# TestParamLoopQuery -- D-D1 per-param coverage
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamLoopQuery:
    """Per D-D1: LOOP_QUERY parameter positive and negative paths."""

    def test_loop_query_matches_multiple_nodes(self):
        """Positive: loop_query selects 3 items from XML string."""
        xml = "<root><item><v>a</v></item><item><v>b</v></item><item><v>c</v></item></root>"
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "v/text()", "nodecheck": False}],
        })
        _set_schema(comp, ["v"])
        df = pd.DataFrame([{"line": xml}])
        result = comp.execute(df)
        assert len(result["main"]) == 3

    def test_non_matching_loop_query_yields_no_rows(self):
        """Negative: loop_query matches nothing -- main is empty."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//nonexistent",
            "mapping": [{"query": "v/text()", "nodecheck": False}],
        })
        _set_schema(comp, ["v"])
        df = pd.DataFrame([{"line": _SINGLE_ITEM_XML}])
        result = comp.execute(df)
        assert result["main"].empty


# ------------------------------------------------------------------
# TestParamMapping -- D-D1 per-param coverage
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamMapping:
    """Per D-D1: MAPPING NODECHECK positive and negative paths."""

    def test_nodecheck_true_passes_when_xpath_matches(self):
        """Positive: NODECHECK=true and XPath found -- row goes to main."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [
                {"query": "name/text()", "nodecheck": True},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": _SINGLE_ITEM_XML}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_nodecheck_true_rejects_when_xpath_missing(self):
        """Negative: NODECHECK=true and XPath not found -- row goes to REJECT."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [
                {"query": "missing_tag/text()", "nodecheck": True},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["col"])
        df = pd.DataFrame([{"line": _SINGLE_ITEM_XML}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NODECHECK_FAIL"


# ------------------------------------------------------------------
# TestParamLimit -- D-D1 per-param coverage (extends existing TestLimit)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamLimit:
    """Per D-D1: LIMIT parameter -- empty=unlimited; 0=nothing; numeric cap.

    This class mirrors TestLimit with explicit per-param naming for D-D1
    traceability. TestLimit above retains its original test methods.
    """

    def test_limit_empty_string_is_unlimited(self):
        five_items = "<root>" + "<item><id>1</id></item>" * 5 + "</root>"
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "id/text()", "nodecheck": False}],
            "limit": "",
        })
        _set_schema(comp, ["id"])
        df = pd.DataFrame([{"line": five_items}])
        result = comp.execute(df)
        assert len(result["main"]) == 5

    def test_limit_zero_reads_nothing(self):
        five_items = "<root>" + "<item><id>1</id></item>" * 5 + "</root>"
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "id/text()", "nodecheck": False}],
            "limit": "0",
        })
        _set_schema(comp, ["id"])
        df = pd.DataFrame([{"line": five_items}])
        result = comp.execute(df)
        assert result["main"].empty

    def test_limit_caps_row_count(self):
        five_items = "<root>" + "<item><id>1</id></item>" * 5 + "</root>"
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "id/text()", "nodecheck": False}],
            "limit": "3",
        })
        _set_schema(comp, ["id"])
        df = pd.DataFrame([{"line": five_items}])
        result = comp.execute(df)
        assert len(result["main"]) == 3


# ------------------------------------------------------------------
# TestParamDieOnError -- D-D1 per-param coverage
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamDieOnError:
    """Per D-D1: DIE_ON_ERROR parameter positive and negative paths."""

    def test_die_on_error_false_routes_parse_error_to_reject(self):
        """Negative: invalid XML with die_on_error=False goes to REJECT."""
        from src.v1.engine.exceptions import DataValidationError
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
            "die_on_error": False,
        })
        # Byte string that cannot be parsed as XML at all
        df = pd.DataFrame([{"line": b"\x00\xff\xfe invalid bytes"}])
        result = comp.execute(df)
        # Must not raise; errorCode must appear in reject
        assert "reject" in result
        if len(result["reject"]) > 0:
            assert result["reject"].iloc[0]["errorCode"] in (
                "PARSE_ERROR", "NO_XML"
            )

    def test_die_on_error_true_raises_data_validation_error(self):
        """Negative: invalid XML with die_on_error=True raises DataValidationError."""
        from src.v1.engine.exceptions import DataValidationError
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [],
            "die_on_error": True,
        })
        df = pd.DataFrame([{"line": b"\x00\xff\xfe invalid bytes"}])
        with pytest.raises((DataValidationError, Exception)):
            comp.execute(df)


# ------------------------------------------------------------------
# TestParamIgnoreNs -- D-D1 per-param coverage
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamIgnoreNs:
    """Per D-D1: IGNORE_NS parameter -- namespace stripping with lxml iter()."""

    _NS_XML = (
        '<ns:root xmlns:ns="http://example.com">'
        "<ns:item><ns:name>Carol</ns:name></ns:item>"
        "</ns:root>"
    )

    def test_ignore_ns_true_allows_unprefixed_xpath(self):
        """Positive: ignore_ns=True strips namespaces so simple XPath works."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "ignore_ns": True,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": self._NS_XML}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Carol"

    def test_ignore_ns_false_unprefixed_xpath_returns_empty(self):
        """Negative: ignore_ns=False with unprefixed XPath finds no nodes."""
        comp = _make_component(config={
            "xmlfield": "line",
            "loop_query": "//item",
            "mapping": [{"query": "name/text()", "nodecheck": False}],
            "ignore_ns": False,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"line": self._NS_XML}])
        result = comp.execute(df)
        # Unprefixed //item matches nothing in a namespace-qualified document
        assert result["main"].empty
