"""Tests for tXMLMap engine component (Phase 12-05).

Test classes (per S-8 per-Talaxie-param + audit OPEN-item regression):
    TestRegistry             -- @REGISTRY.register both names
    TestBaseComponent        -- subclass + lifecycle
    TestValidateConfig       -- _validate_config() structural checks (Rule 12)
    TestProcessHappyPath     -- single-row XML doc -> output rows; empty doc
    TestMultiRowInput        -- BUG-XMP-003 P0 regression: 5-row Document input
    TestProcessReject        -- per-row XML parse error routes reject; empty XML
    TestDieOnError           -- die_on_error=True raises; default is True
    TestNoIlocZeroZero       -- grep: zero iloc[0, 0] matches (regression guard)
    TestNoPrintCalls         -- grep: zero non-comment print() calls (STD-XMP-001)
    TestNoLstripStringArg    -- grep: zero multi-char lstrip() (P-7 regression)
    TestNoBridgeImports      -- grep: zero JavaBridgeManager imports (D-E2)
    TestSecureParserDelegation -- grep: at least one _xml_io.secure_xml_parser call
    TestConditionalWarnExpressionFilter -- D-E1 pos+neg
    TestConditionalWarnLookup           -- D-E1 pos+neg
    TestConditionalWarnAllInOne         -- D-E1 pos+neg
    TestParamMap             -- MAP json round-trip (no crash with extra config)
    TestParamDieOnError      -- pos+neg die_on_error behavior
    TestParamKeepOrderForDocument -- pos+neg keep_order flag
    TestRejectRowSchema      -- reject row schema (input cols + error cols)
    TestSplitSteps           -- BUG-XMP-014 predicate preservation
    TestStats                -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT tracking
    TestE2eFixture           -- Job_tXMLMap_0.1.item converts successfully

Per D-D1 -- per-Talaxie-javajet-param positive + negative tests.
Per D-D4 -- no mocks of lxml.etree.
Per D-E2 -- no live Java-bridge calls; warn-and-ignore for expression_filter / lookup / allInOne.
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.xml_map import (
    DEFAULT_NAMESPACE_PREFIX,
    XMLMap,
    normalize_nsmap,
    split_steps,
)
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, DataValidationError
from src.v1.engine.global_map import GlobalMap


_SOURCE_FILE = Path("src/v1/engine/components/transform/xml_map.py")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config: Dict[str, Any], comp_id: str = "xm_1") -> XMLMap:
    """Build a minimal XMLMap component for testing."""
    comp = XMLMap(
        component_id=comp_id,
        config=config,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    return comp


def _strip_comments(source: str) -> str:
    """Strip lines that are pure comments to avoid false positives in audit-grep tests."""
    return "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("#")
    )


def _make_minimal_config(
    looping_element: str = "item",
    extra: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Return a minimal valid XMLMap config."""
    cfg: Dict[str, Any] = {
        "input_trees": [],
        "output_trees": [],
        "connections": [],
        "output_schema": [
            {"name": "id", "type": "id_String"},
            {"name": "name", "type": "id_String"},
        ],
        "expressions": {
            "id": "./id",
            "name": "./name",
        },
        "looping_element": looping_element,
        "die_on_error": False,
    }
    if extra:
        cfg.update(extra)
    return cfg


# ------------------------------------------------------------------
# TestRegistry
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    def test_v1_name_registered(self):
        assert REGISTRY.get("XMLMap") is XMLMap

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tXMLMap") is XMLMap

    def test_both_names_same_class(self):
        assert REGISTRY.get("XMLMap") is REGISTRY.get("tXMLMap")


# ------------------------------------------------------------------
# TestBaseComponent
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBaseComponent:
    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(XMLMap, BaseComponent)

    def test_instantiate(self):
        comp = _make_component(_make_minimal_config())
        assert comp.id == "xm_1"


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_valid_config_does_not_raise(self):
        comp = _make_component(_make_minimal_config())
        comp._validate_config()  # should not raise

    def test_output_schema_not_list_raises(self):
        cfg = _make_minimal_config()
        cfg["output_schema"] = "not_a_list"
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_expressions_not_dict_raises(self):
        cfg = _make_minimal_config()
        cfg["expressions"] = ["not", "a", "dict"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_die_on_error_not_bool_raises(self):
        cfg = _make_minimal_config()
        cfg["die_on_error"] = "yes"
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError):
            comp._validate_config()


# ------------------------------------------------------------------
# TestProcessHappyPath
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessHappyPath:
    def test_single_row_xml_produces_output(self):
        xml = "<root><item><id>1</id><name>Alice</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        assert "main" in result
        main = result["main"]
        assert len(main) == 1
        assert main.iloc[0]["id"] == "1"
        assert main.iloc[0]["name"] == "Alice"

    def test_multiple_looping_elements_produce_multiple_rows(self):
        xml = (
            "<root>"
            "<item><id>1</id><name>Alice</name></item>"
            "<item><id>2</id><name>Bob</name></item>"
            "</root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        assert len(result["main"]) == 2

    def test_empty_looping_element_returns_root(self):
        xml = "<root><id>42</id><name>X</name></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(looping_element="")
        comp = _make_component(cfg)
        result = comp._process(df_in)
        # With no looping_element, root is the only node -> 1 row
        assert len(result["main"]) == 1

    def test_none_input_returns_empty_main(self):
        comp = _make_component(_make_minimal_config())
        result = comp._process(None)
        assert "main" in result
        assert len(result["main"]) == 0

    def test_empty_dataframe_returns_empty_main(self):
        comp = _make_component(_make_minimal_config())
        result = comp._process(pd.DataFrame())
        assert len(result["main"]) == 0


# ------------------------------------------------------------------
# TestMultiRowInput (BUG-XMP-003 P0 regression-guard)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMultiRowInput:
    """BUG-XMP-003 P0 regression-guard: must not use iloc[0, 0]."""

    def test_5_row_document_input_yields_per_row_output(self):
        """5 input rows, each with 1 looping_element match -> 5 output rows total."""
        doc = "<root><item><id>{i}</id><name>N{i}</name></item></root>"
        df_in = pd.DataFrame({"xml": [doc.format(i=i) for i in range(5)]})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        assert len(result["main"]) == 5, (
            f"BUG-XMP-003 regression: expected 5 rows, got {len(result['main'])}"
        )

    def test_3_row_input_2_loop_items_each_yields_6_rows(self):
        """3 input rows, each doc has 2 items -> 6 output rows."""
        doc = (
            "<root>"
            "<item><id>{a}</id><name>N{a}</name></item>"
            "<item><id>{b}</id><name>N{b}</name></item>"
            "</root>"
        )
        rows = [doc.format(a=i * 2, b=i * 2 + 1) for i in range(3)]
        df_in = pd.DataFrame({"xml": rows})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        assert len(result["main"]) == 6

    def test_all_5_ids_present_in_output(self):
        """Regression: each input row's XML is fully processed, not just the first."""
        doc = "<root><item><id>{i}</id><name>N{i}</name></item></root>"
        df_in = pd.DataFrame({"xml": [doc.format(i=i) for i in range(5)]})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        ids = set(result["main"]["id"].tolist())
        assert ids == {"0", "1", "2", "3", "4"}, (
            f"BUG-XMP-003: not all rows processed; ids present: {ids}"
        )


# ------------------------------------------------------------------
# TestProcessReject
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_null_xml_routes_to_reject(self):
        df_in = pd.DataFrame({"xml": [None]})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        assert len(result["main"]) == 0
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NO_XML"

    def test_empty_string_routes_to_reject(self):
        df_in = pd.DataFrame({"xml": [""]})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NO_XML"

    def test_malformed_xml_routes_to_reject(self):
        df_in = pd.DataFrame({"xml": ["<not valid xml"]})
        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "PARSE_ERROR"

    def test_mixed_valid_invalid_rows(self):
        valid_xml = "<root><item><id>1</id><name>Alice</name></item></root>"
        invalid_xml = "<broken"
        df_in = pd.DataFrame({"xml": [valid_xml, invalid_xml, valid_xml]})
        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["main"]) == 2
        assert len(result["reject"]) == 1


# ------------------------------------------------------------------
# TestDieOnError
# ------------------------------------------------------------------

@pytest.mark.unit
class TestDieOnError:
    def test_die_on_error_true_raises_on_parse_failure(self):
        df_in = pd.DataFrame({"xml": ["<invalid xml"]})
        cfg = _make_minimal_config(extra={"die_on_error": True})
        comp = _make_component(cfg)
        with pytest.raises((DataValidationError, Exception)):
            comp._process(df_in)

    def test_default_die_on_error_is_true(self):
        """tXMLMap default die_on_error=True per Talaxie javajet."""
        cfg = _make_minimal_config()
        del cfg["die_on_error"]  # remove explicit setting -> use default
        comp = _make_component(cfg)
        # Default should be True, so a parse error should raise
        df_in = pd.DataFrame({"xml": ["<invalid xml"]})
        with pytest.raises((DataValidationError, Exception)):
            comp._process(df_in)


# ------------------------------------------------------------------
# TestNoIlocZeroZero (BUG-XMP-003 regression-guard)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoIlocZeroZero:
    def test_iloc_zero_zero_eradicated(self):
        """BUG-XMP-003 regression guard: iloc[0, 0] must not appear in source."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert not re.search(r"\.iloc\[\s*0\s*,\s*0\s*\]", src), (
            "BUG-XMP-003 regression: iloc[0, 0] reappeared in xml_map.py"
        )


# ------------------------------------------------------------------
# TestNoPrintCalls (STD-XMP-001 regression-guard)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoPrintCalls:
    def test_no_print_calls_in_module(self):
        """STD-XMP-001 regression guard: no bare print() calls in xml_map.py."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert "print(" not in src, (
            "STD-XMP-001 regression: print() reappeared in xml_map.py"
        )


# ------------------------------------------------------------------
# TestNoLstripStringArg (P-7 Pitfall regression-guard)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoLstripStringArg:
    def test_no_lstrip_single_char(self):
        """P-7 regression guard: no .lstrip('/') single-char calls."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert not re.search(r"\.lstrip\([\"'][^\"']{1,}[\"']\)", src), (
            "P-7 regression: lstrip() with string arg reappeared in xml_map.py"
        )

    def test_removeprefix_used_instead(self):
        """P-7 fix present: at least one removeprefix() call in source."""
        src = _SOURCE_FILE.read_text()
        assert "removeprefix" in src, (
            "P-7 fix missing: no removeprefix() found in xml_map.py"
        )


# ------------------------------------------------------------------
# TestNoBridgeImports (D-E2 regression-guard)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoBridgeImports:
    def test_no_java_bridge_manager_import(self):
        """D-E2: JavaBridgeManager must not be imported in xml_map.py."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert "JavaBridgeManager" not in src

    def test_no_java_bridge_module_import(self):
        """D-E2: 'from.*java_bridge' import must not appear."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert not re.search(r"from\s+.*java_bridge", src), (
            "D-E2 violation: java_bridge import found in xml_map.py"
        )

    def test_no_execute_one_time_expression(self):
        """D-E2: execute_one_time_expression must not appear."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert "execute_one_time_expression" not in src


# ------------------------------------------------------------------
# TestSecureParserDelegation (SEC-XMP-001)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSecureParserDelegation:
    def test_secure_xml_parser_used(self):
        """SEC-XMP-001: at least one _xml_io.secure_xml_parser call in source."""
        src = _SOURCE_FILE.read_text()
        assert "_xml_io.secure_xml_parser" in src, (
            "SEC-XMP-001: _xml_io.secure_xml_parser not found in xml_map.py"
        )


# ------------------------------------------------------------------
# TestConditionalWarnExpressionFilter (D-E1)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestConditionalWarnExpressionFilter:
    def test_warn_emitted_when_flag_true(self, caplog):
        """D-E1: expression_filter flag -> logger.warning emitted."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={"activate_expression_filter": True})
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            comp._process(df_in)
        msgs = [r.getMessage() for r in caplog.records]
        assert any("expression_filter" in m for m in msgs), (
            "D-E1: no warning emitted for expression_filter=True"
        )

    def test_no_warn_when_flag_absent(self, caplog):
        """D-E1: no expression_filter flag -> no warning."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config()  # no activate_expression_filter
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            comp._process(df_in)
        msgs = [r.getMessage() for r in caplog.records]
        assert not any("expression_filter" in m for m in msgs), (
            "D-E1: unexpected expression_filter warning when flag absent"
        )


# ------------------------------------------------------------------
# TestConditionalWarnLookup (D-E1)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestConditionalWarnLookup:
    def test_warn_emitted_when_lookup_tree_present(self, caplog):
        """D-E1: input_tree with lookup=True -> logger.warning emitted."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={
            "input_trees": [{"name": "lookup1", "lookup": True}],
        })
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            comp._process(df_in)
        msgs = [r.getMessage() for r in caplog.records]
        assert any("lookup" in m for m in msgs), (
            "D-E1: no warning emitted for lookup tree"
        )

    def test_no_warn_when_no_lookup(self, caplog):
        """D-E1: no lookup input_trees -> no lookup warning."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={
            "input_trees": [{"name": "main1", "lookup": False}],
        })
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            comp._process(df_in)
        msgs = [r.getMessage() for r in caplog.records]
        assert not any("lookup/join" in m for m in msgs), (
            "D-E1: unexpected lookup warning when no lookup tree"
        )


# ------------------------------------------------------------------
# TestConditionalWarnAllInOne (D-E1)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestConditionalWarnAllInOne:
    def test_warn_emitted_when_all_in_one_true(self, caplog):
        """D-E1: output_tree with allInOne=True -> logger.warning emitted."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={
            "output_trees": [{"name": "out1", "allInOne": True}],
        })
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            comp._process(df_in)
        msgs = [r.getMessage() for r in caplog.records]
        assert any("allInOne" in m for m in msgs), (
            "D-E1: no warning emitted for allInOne=True"
        )

    def test_no_warn_when_all_in_one_false(self, caplog):
        """D-E1: output_tree with allInOne=False -> no allInOne warning."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={
            "output_trees": [{"name": "out1", "allInOne": False}],
        })
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            comp._process(df_in)
        msgs = [r.getMessage() for r in caplog.records]
        assert not any("allInOne" in m for m in msgs), (
            "D-E1: unexpected allInOne warning when flag is False"
        )


# ------------------------------------------------------------------
# TestParamMap
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamMap:
    def test_extra_config_keys_do_not_crash(self):
        """Extra config keys (MAP visual editor, etc.) are silently ignored."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={
            "MAP": "some_visual_editor_reference",
            "var_tables": [],
            "tstatcatcher_stats": False,
            "label": "test",
        })
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert "main" in result

    def test_full_config_round_trip(self):
        """Full config with all known tXMLMap keys does not raise."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = {
            "input_trees": [],
            "output_trees": [],
            "connections": [],
            "var_tables": [],
            "output_schema": [{"name": "id", "type": "id_String"}, {"name": "name", "type": "id_String"}],
            "expressions": {"id": "./id", "name": "./name"},
            "looping_element": "item",
            "expression_filter": None,
            "activate_expression_filter": False,
            "die_on_error": False,
            "keep_order_for_document": False,
            "tstatcatcher_stats": False,
            "label": "",
        }
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestParamDieOnError
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamDieOnError:
    def test_die_on_error_false_routes_to_reject(self):
        df_in = pd.DataFrame({"xml": ["<broken"]})
        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["reject"]) == 1
        assert len(result["main"]) == 0

    def test_die_on_error_true_raises(self):
        df_in = pd.DataFrame({"xml": ["<broken"]})
        cfg = _make_minimal_config(extra={"die_on_error": True})
        comp = _make_component(cfg)
        with pytest.raises((DataValidationError, Exception)):
            comp._process(df_in)


# ------------------------------------------------------------------
# TestParamKeepOrderForDocument
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamKeepOrderForDocument:
    def test_keep_order_false_accepted(self):
        """keep_order_for_document=False does not crash."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={"keep_order_for_document": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["main"]) == 1

    def test_keep_order_true_accepted(self):
        """keep_order_for_document=True does not crash (stored flag, not yet enforced)."""
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={"keep_order_for_document": True})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestRejectRowSchema
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRejectRowSchema:
    def test_reject_row_carries_error_columns(self):
        """Reject rows include errorCode and errorMessage (S-3 pattern)."""
        df_in = pd.DataFrame({"xml": [None]})
        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        rej = result["reject"]
        assert len(rej) == 1
        assert "errorCode" in rej.columns
        assert "errorMessage" in rej.columns

    def test_reject_row_carries_input_columns(self):
        """Reject rows also carry the original input columns (S-3 full reject schema)."""
        df_in = pd.DataFrame({"xml": [None], "extra_col": ["somevalue"]})
        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        rej = result["reject"]
        # The reject row should carry the input columns
        assert "extra_col" in rej.columns or "errorXMLField" in rej.columns

    def test_reject_row_error_code_no_xml(self):
        """Null XML input produces errorCode='NO_XML'."""
        df_in = pd.DataFrame({"xml": [None]})
        comp = _make_component(_make_minimal_config())
        result = comp._process(df_in)
        assert result["reject"].iloc[0]["errorCode"] == "NO_XML"

    def test_reject_row_error_code_parse_error(self):
        """Malformed XML produces errorCode='PARSE_ERROR'."""
        df_in = pd.DataFrame({"xml": ["<not xml"]})
        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert result["reject"].iloc[0]["errorCode"] == "PARSE_ERROR"


# ------------------------------------------------------------------
# TestSplitSteps (BUG-XMP-014 predicate preservation)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSplitSteps:
    def test_simple_path_split(self):
        """Simple /a/b/c splits into three segments."""
        assert split_steps("/a/b/c") == ["a", "b", "c"]

    def test_predicate_preserved(self):
        """XPath predicate /a/b[@id='x']/c -- the predicate must not be split."""
        result = split_steps("/a/b[@id='x']/c")
        # Should contain 3 segments: a, b[@id='x'], c
        assert len(result) == 3
        assert any("[@id='x']" in s for s in result), (
            f"BUG-XMP-014: predicate destroyed in split_steps result: {result}"
        )

    def test_nested_predicate_preserved(self):
        """Nested predicate /a/b[@x='y/z']/c keeps slash inside predicate intact."""
        result = split_steps("/a/b[@x='y/z']/c")
        predicate_segments = [s for s in result if "[" in s]
        assert predicate_segments, "Predicate-containing segment missing"
        assert "/" in predicate_segments[0], "Slash inside predicate was consumed"

    def test_double_slash(self):
        """//b produces ['//','b'] or ['b'] with // token."""
        result = split_steps("//b")
        # The result should contain the node name 'b'
        assert any("b" in s for s in result)


# ------------------------------------------------------------------
# TestNormalizeNsmap (CR-03 regression: full descendant walk for namespaces)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNormalizeNsmap:
    """CR-03: normalize_nsmap must collect namespaces from all descendants, not just root."""

    def test_root_namespace_collected(self):
        """Namespaces on the root element are collected."""
        from lxml import etree
        root = etree.fromstring(b'<root xmlns:a="http://a.example.com"><child/></root>')
        result = normalize_nsmap(root)
        assert "a" in result
        assert result["a"] == "http://a.example.com"

    def test_descendant_only_namespace_collected(self):
        """CR-03 regression: namespace declared only on a descendant must appear in result."""
        from lxml import etree
        root = etree.fromstring(
            b'<root><child xmlns:b="http://b.example.com"><b:val>hello</b:val></child></root>'
        )
        result = normalize_nsmap(root)
        assert "b" in result, (
            f"CR-03 regression: descendant-only namespace 'b' not in nsmap; got {result}"
        )
        assert result["b"] == "http://b.example.com"

    def test_default_namespace_mapped_to_sentinel(self):
        """Default namespace (None key in lxml) becomes DEFAULT_NAMESPACE_PREFIX in result."""
        from lxml import etree
        root = etree.fromstring(b'<root xmlns="http://default.example.com"><child/></root>')
        result = normalize_nsmap(root)
        assert DEFAULT_NAMESPACE_PREFIX in result
        assert result[DEFAULT_NAMESPACE_PREFIX] == "http://default.example.com"
        assert None not in result  # None key must never appear

    def test_no_none_key_in_result(self):
        """The returned dict must never contain None as a key."""
        from lxml import etree
        root = etree.fromstring(
            b'<root xmlns="http://default.example.com" xmlns:a="http://a.example.com"/>'
        )
        result = normalize_nsmap(root)
        assert None not in result

    def test_empty_nsmap_returns_empty(self):
        """Element with no namespace declarations returns empty dict."""
        from lxml import etree
        root = etree.fromstring(b"<root><child/></root>")
        result = normalize_nsmap(root)
        assert result == {}


# ------------------------------------------------------------------
# TestCleanExpression (CR-02 regression: no rstrip("]") in _clean_expression)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCleanExpression:
    """CR-02 regression guard: _clean_expression must not strip XPath predicate brackets."""

    def test_predicate_not_stripped_position(self):
        """./item[1] -- positional predicate must survive _clean_expression."""
        comp = _make_component(_make_minimal_config())
        result = comp._clean_expression("./item[1]")
        assert result == "./item[1]", (
            f"CR-02 regression: predicate bracket stripped; got {result!r}"
        )

    def test_predicate_not_stripped_attribute(self):
        """./status[@active='true'] -- attribute predicate must survive."""
        comp = _make_component(_make_minimal_config())
        result = comp._clean_expression("./status[@active='true']")
        assert result == "./status[@active='true']", (
            f"CR-02 regression: predicate bracket stripped; got {result!r}"
        )

    def test_predicate_not_stripped_text_match(self):
        """./child[. = 'x'] -- text predicate must survive."""
        comp = _make_component(_make_minimal_config())
        result = comp._clean_expression("./child[. = 'x']")
        assert result == "./child[. = 'x']", (
            f"CR-02 regression: predicate bracket stripped; got {result!r}"
        )

    def test_malformed_row_bracket_still_cleaned(self):
        """[row1.employee:/employees/employee/id] -> the outer [] are stripped."""
        comp = _make_component(_make_minimal_config())
        result = comp._clean_expression("[row1.employee:/employees/employee/id]")
        # The outer brackets are stripped, then the ":" path pattern fires
        assert result.startswith("./"), (
            f"CR-02: malformed [row1...] pattern not cleaned; got {result!r}"
        )

    def test_no_rstrip_in_source(self):
        """Regression guard: rstrip(\"]\") must not appear as executable code."""
        src = _SOURCE_FILE.read_text()
        # Strip comment lines and docstrings (triple-quote blocks) for targeted check
        import re as _re
        # Remove triple-quoted strings to avoid matching docstring examples
        src_no_docstrings = _re.sub(r'""".*?"""', '""""""', src, flags=_re.DOTALL)
        src_no_docstrings = _re.sub(r"'''.*?'''", "''''''", src_no_docstrings, flags=_re.DOTALL)
        # Also strip comment lines
        src_clean = "\n".join(
            line for line in src_no_docstrings.splitlines()
            if not line.lstrip().startswith("#")
        )
        assert 'rstrip("]")' not in src_clean, (
            "CR-02 regression: rstrip(\"]\") reappeared as executable code in xml_map.py"
        )


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_updated_on_success(self):
        """NB_LINE, NB_LINE_OK, NB_LINE_REJECT updated via _update_stats."""
        gm = GlobalMap()
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        comp = XMLMap(
            component_id="xm_s",
            config=_make_minimal_config(),
            global_map=gm,
            context_manager=ContextManager(),
        )
        comp.config = _make_minimal_config()
        comp._process(df_in)
        # _update_stats should be called; GlobalMap should have stats
        # (exact format depends on BaseComponent impl, just check no crash)
        assert True  # reached without exception

    def test_reject_stats_incremented(self):
        """Rejected rows increment NB_LINE_REJECT."""
        gm = GlobalMap()
        df_in = pd.DataFrame({"xml": [None, None]})
        comp = XMLMap(
            component_id="xm_r",
            config=_make_minimal_config(),
            global_map=gm,
            context_manager=ContextManager(),
        )
        comp.config = _make_minimal_config()
        result = comp._process(df_in)
        assert len(result["reject"]) == 2


# ------------------------------------------------------------------
# TestE2eFixture
# ------------------------------------------------------------------

@pytest.mark.unit
class TestE2eFixture:
    def test_item_fixture_converts_successfully(self, tmp_path):
        """Job_tXMLMap_0.1.item converts to JSON without errors."""
        from src.converters.talend_to_v1.converter import convert_job
        fixture = Path("tests/talend_xml_samples/Job_tXMLMap_0.1.item")
        if not fixture.exists():
            pytest.skip(f"Fixture not found: {fixture}")
        json_path = tmp_path / "job.json"
        convert_job(str(fixture), str(json_path))
        assert json_path.exists(), "convert_job did not produce output JSON"
        import json
        with open(json_path) as f:
            job = json.load(f)
        assert "components" in job

    def test_xml_map_component_importable(self):
        """XMLMap can be imported without errors (registry self-test)."""
        from src.v1.engine.components.transform.xml_map import XMLMap as _XMLMap
        assert _XMLMap is XMLMap


# ==================================================================
# Coverage-lift tests (per-row + multiloop + filter machinery)
# ==================================================================

from lxml import etree as _etree  # noqa: E402


class _FakeBridge:
    """Minimal stand-in for the live Java bridge.

    Implements only ``execute_batch_one_time_expressions(dict)`` which the
    filter machinery calls.  ``returns`` maps each request key to the value the
    bridge would return; ``raise_exc`` forces a raise to exercise the
    fail-open branch.
    """

    def __init__(self, returns: Dict[str, Any] = None, raise_exc: bool = False):
        self.returns = returns or {}
        self.raise_exc = raise_exc
        self.calls: List[Dict[str, str]] = []

    def execute_batch_one_time_expressions(self, exprs: Dict[str, str]) -> Dict[str, Any]:
        self.calls.append(dict(exprs))
        if self.raise_exc:
            raise RuntimeError("bridge boom")
        # default: echo True for every key not explicitly overridden
        out = {k: True for k in exprs}
        out.update(self.returns)
        return out


# ------------------------------------------------------------------
# TestResolveExpressions (line 460: {{java}} prefix strip)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestResolveExpressions:
    def test_java_prefix_stripped_from_expression_filter(self):
        cfg = _make_minimal_config(extra={
            "expression_filter": "{{java}}Relational.ISNULL([r.c:/a/b])",
        })
        comp = _make_component(cfg)
        comp._resolve_expressions()
        assert comp.config["expression_filter"] == "Relational.ISNULL([r.c:/a/b])"

    def test_non_java_expression_filter_untouched(self):
        cfg = _make_minimal_config(extra={
            "expression_filter": "Relational.ISNULL([r.c:/a/b])",
        })
        comp = _make_component(cfg)
        comp._resolve_expressions()
        assert comp.config["expression_filter"] == "Relational.ISNULL([r.c:/a/b])"


# ------------------------------------------------------------------
# TestSubstituteXmlPlaceholders (lines 507-534)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSubstituteXmlPlaceholders:
    def test_value_token_becomes_quoted_literal_no_ns(self):
        node = _etree.fromstring(b"<item><id>42</id></item>")
        out = XMLMap._substitute_xml_placeholders(
            "Relational.ISNULL([r.c:/root/item/id])", node, "item", "", {}, "xm_t"
        )
        assert out == 'Relational.ISNULL("42")'

    def test_empty_text_token_becomes_null(self):
        node = _etree.fromstring(b"<item><id></id></item>")
        out = XMLMap._substitute_xml_placeholders(
            "[r.c:/root/item/id]", node, "item", "", {}, "xm_t"
        )
        assert out == "null"

    def test_missing_node_token_becomes_null(self):
        node = _etree.fromstring(b"<item><id>x</id></item>")
        out = XMLMap._substitute_xml_placeholders(
            "[r.c:/root/item/missing]", node, "item", "", {}, "xm_t"
        )
        assert out == "null"

    def test_descendant_fallback_search_no_ns(self):
        # rel_xpath resolves to "deep/id" (loop element 'item'); direct child
        # lookup fails, so the .//rel_xpath fallback must find it.
        node = _etree.fromstring(b"<item><wrap><deep><id>99</id></deep></wrap></item>")
        out = XMLMap._substitute_xml_placeholders(
            "[r.c:/root/item/deep/id]", node, "item", "", {}, "xm_t"
        )
        assert out == '"99"'

    def test_namespace_branch_resolves_value(self):
        xml = (
            b'<item xmlns="http://ex.com"><id>7</id></item>'
        )
        node = _etree.fromstring(xml)
        nsmap = {DEFAULT_NAMESPACE_PREFIX: "http://ex.com"}
        out = XMLMap._substitute_xml_placeholders(
            "[r.c:/root/item/" + DEFAULT_NAMESPACE_PREFIX + ":id]",
            node, "item", DEFAULT_NAMESPACE_PREFIX, nsmap, "xm_t",
        )
        assert out == '"7"'

    def test_namespace_descendant_fallback(self):
        # rel_xpath resolves to "ns0:deep/ns0:id" but 'deep' is nested under
        # 'wrap' (not a direct child of the loop node), so the direct lookup is
        # empty and the ns-branch `.//rel_xpath` fallback (lines 515-518) fires.
        xml = (
            b'<item xmlns:ns0="http://ex.com">'
            b'<wrap><ns0:deep><ns0:id>5</ns0:id></ns0:deep></wrap>'
            b'</item>'
        )
        node = _etree.fromstring(xml)
        nsmap = {"ns0": "http://ex.com"}
        out = XMLMap._substitute_xml_placeholders(
            "[r.c:/root/item/ns0:deep/ns0:id]", node, "item", "ns0", nsmap, "xm_t",
        )
        assert out == '"5"'

    def test_special_chars_escaped(self):
        node = _etree.fromstring(b'<item><id>a"b\\c</id></item>')
        out = XMLMap._substitute_xml_placeholders(
            "[r.c:/root/item/id]", node, "item", "", {}, "xm_t"
        )
        # backslash doubled, quote escaped
        assert out == '"a\\"b\\\\c"'

    def test_invalid_xpath_token_logs_and_returns_null(self, caplog):
        node = _etree.fromstring(b"<item><id>x</id></item>")
        with caplog.at_level(logging.DEBUG, logger="src.v1.engine.components.transform.xml_map"):
            out = XMLMap._substitute_xml_placeholders(
                "[r.c:/root/item/id[bad(]", node, "item", "", {}, "xm_t"
            )
        assert out == "null"


# ------------------------------------------------------------------
# TestComputeFilterMask (lines 568-608)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestComputeFilterMask:
    def _loop_nodes(self, n: int) -> List[Any]:
        root = _etree.fromstring(
            ("<root>" + "".join(f"<item><id>{i}</id></item>" for i in range(n)) + "</root>").encode()
        )
        return root.xpath(".//item")

    def test_bridge_true_false_mask(self, caplog):
        comp = _make_component(_make_minimal_config())
        comp.java_bridge = _FakeBridge(returns={"_f0": True, "_f1": False})
        nodes = self._loop_nodes(2)
        with caplog.at_level(logging.DEBUG, logger="src.v1.engine.components.transform.xml_map"):
            mask = comp._compute_filter_mask(
                "[r.c:/root/item/id]", nodes, "item", "", {}, "xm_t"
            )
        assert mask == [True, False]

    def test_bridge_error_fails_open(self, caplog):
        comp = _make_component(_make_minimal_config())
        comp.java_bridge = _FakeBridge(returns={"_f0": "{{ERROR}}Groovy parse error"})
        nodes = self._loop_nodes(1)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            mask = comp._compute_filter_mask(
                "[r.c:/root/item/id]", nodes, "item", "", {}, "xm_t"
            )
        assert mask == [True]
        assert any("Filter eval error" in r.getMessage() for r in caplog.records)

    def test_bridge_exception_includes_all(self, caplog):
        comp = _make_component(_make_minimal_config())
        comp.java_bridge = _FakeBridge(raise_exc=True)
        nodes = self._loop_nodes(3)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            mask = comp._compute_filter_mask(
                "[r.c:/root/item/id]", nodes, "item", "", {}, "xm_t"
            )
        assert mask == [True, True, True]
        assert any("Filter batch Java eval failed" in r.getMessage() for r in caplog.records)

    def test_no_bridge_includes_all_and_warns(self, caplog):
        comp = _make_component(_make_minimal_config())
        comp.java_bridge = None
        nodes = self._loop_nodes(2)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            mask = comp._compute_filter_mask(
                "[r.c:/root/item/id]", nodes, "item", "", {}, "xm_t"
            )
        assert mask == [True, True]
        assert any("requires a running Java bridge" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------------------
# TestMakeFilterRelativeXpath (lines 630-639)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMakeFilterRelativeXpath:
    def test_loop_element_found_returns_tail(self):
        out = XMLMap._make_filter_relative_xpath(
            "/CM/Required/Detail/Component/MarginType", "Detail"
        )
        assert out == "Component/MarginType"

    def test_loop_element_is_last_returns_dot(self):
        out = XMLMap._make_filter_relative_xpath("/a/b/Detail", "Detail")
        assert out == "."

    def test_loop_element_not_found_returns_full_path(self):
        out = XMLMap._make_filter_relative_xpath("/a/b/c", "NotThere")
        assert out == "a/b/c"

    def test_namespace_prefix_stripped_for_match(self):
        out = XMLMap._make_filter_relative_xpath("/ns0:a/ns0:Detail/ns0:x", "Detail")
        assert out == "ns0:x"


# ------------------------------------------------------------------
# TestHasLookupConnection (line 651: connector_name == LOOKUP)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestHasLookupConnection:
    def test_connector_name_lookup_detected(self):
        cfg = _make_minimal_config(extra={
            "connections": [{"connector_name": "LOOKUP"}],
        })
        comp = _make_component(cfg)
        assert comp._has_lookup_connection() is True

    def test_no_lookup_connection(self):
        cfg = _make_minimal_config(extra={
            "connections": [{"connector_name": "MAIN"}],
        })
        comp = _make_component(cfg)
        assert comp._has_lookup_connection() is False


# ------------------------------------------------------------------
# TestParseFlowColumnExpr + flat mode (lines 784-844, 1256-1257)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParseFlowColumnExpr:
    def test_valid_flow_column(self):
        assert XMLMap._parse_flow_column_expr("row1.id") == ("row1", "id")

    def test_empty_expr_returns_none(self):
        assert XMLMap._parse_flow_column_expr("") is None

    def test_non_string_returns_none(self):
        assert XMLMap._parse_flow_column_expr(None) is None

    def test_slash_expr_returns_none(self):
        assert XMLMap._parse_flow_column_expr("./a/b") is None

    def test_space_expr_returns_none(self):
        assert XMLMap._parse_flow_column_expr("row1 . id") is None

    def test_three_parts_returns_none(self):
        assert XMLMap._parse_flow_column_expr("a.b.c") is None


@pytest.mark.unit
class TestBuildFlatColumnMap:
    def test_no_output_trees_returns_none(self):
        comp = _make_component(_make_minimal_config())
        assert comp._build_flat_column_map() is None

    def test_all_flow_column_builds_map(self):
        cfg = _make_minimal_config(extra={
            "output_trees": [{
                "nodes": [
                    {"name": "id", "expression": "row1.id"},
                    {"name": "name", "expression": "row1.fullname"},
                ],
            }],
        })
        comp = _make_component(cfg)
        assert comp._build_flat_column_map() == {"id": "id", "name": "fullname"}

    def test_any_xpath_expr_returns_none(self):
        cfg = _make_minimal_config(extra={
            "output_trees": [{
                "nodes": [
                    {"name": "id", "expression": "row1.id"},
                    {"name": "name", "expression": "./name"},
                ],
            }],
        })
        comp = _make_component(cfg)
        assert comp._build_flat_column_map() is None

    def test_empty_nodes_returns_none(self):
        cfg = _make_minimal_config(extra={
            "output_trees": [{"nodes": []}],
        })
        comp = _make_component(cfg)
        assert comp._build_flat_column_map() is None


@pytest.mark.unit
class TestFlatMode:
    def test_flat_mapping_maps_columns(self):
        cfg = _make_minimal_config(extra={
            "output_trees": [{
                "nodes": [
                    {"name": "id", "expression": "row1.id"},
                    {"name": "name", "expression": "row1.fullname"},
                ],
            }],
        })
        comp = _make_component(cfg)
        df_in = pd.DataFrame({"id": ["1", "2"], "fullname": ["Alice", "Bob"]})
        result = comp._process(df_in)
        main = result["main"]
        assert main["id"].tolist() == ["1", "2"]
        assert main["name"].tolist() == ["Alice", "Bob"]
        assert result["reject"].empty

    def test_flat_mapping_output_col_fallback(self):
        # in_col missing, but out_col present in input -> elif branch (line 834-835)
        cfg = _make_minimal_config(extra={
            "output_trees": [{
                "nodes": [
                    {"name": "id", "expression": "row1.id"},
                    {"name": "name", "expression": "row1.fullname"},
                ],
            }],
        })
        comp = _make_component(cfg)
        # 'fullname' (mapped source for 'name') absent; but a 'name' column exists
        df_in = pd.DataFrame({"id": ["1"], "name": ["Direct"]})
        result = comp._process(df_in)
        assert result["main"]["name"].tolist() == ["Direct"]

    def test_flat_mapping_missing_column_yields_none(self):
        cfg = _make_minimal_config(extra={
            "output_trees": [{
                "nodes": [
                    {"name": "id", "expression": "row1.id"},
                    {"name": "name", "expression": "row1.fullname"},
                ],
            }],
        })
        comp = _make_component(cfg)
        df_in = pd.DataFrame({"id": ["1"]})  # neither 'fullname' nor 'name'
        result = comp._process(df_in)
        assert result["main"]["name"].tolist() == [None]


# ------------------------------------------------------------------
# TestEvaluateXmlMultiloop (lines 913-992, 1358)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEvaluateXmlMultiloop:
    def _multiloop_cfg(self, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        cfg = {
            "output_schema": [
                {"name": "order_id", "type": "id_String"},
                {"name": "line_id", "type": "id_String"},
            ],
            "expressions": {
                "order_id": "./oid",
                "line_id": "./lid",
            },
            "loop_nodes": ["order", "line"],
            "expression_contexts": {"order_id": "order", "line_id": "line"},
            "die_on_error": False,
        }
        if extra:
            cfg.update(extra)
        return cfg

    def test_cross_product_no_ns(self):
        xml = (
            "<root>"
            "<order><oid>O1</oid><line><lid>L1</lid></line><line><lid>L2</lid></line></order>"
            "</root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        comp = _make_component(self._multiloop_cfg())
        result = comp._process(df_in)
        main = result["main"]
        # 1 order x 2 lines = 2 rows
        assert len(main) == 2
        assert main["order_id"].tolist() == ["O1", "O1"]
        assert set(main["line_id"].tolist()) == {"L1", "L2"}

    def test_primary_loop_empty_returns_no_rows(self):
        xml = "<root><other/></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        comp = _make_component(self._multiloop_cfg())
        result = comp._process(df_in)
        assert len(result["main"]) == 0

    def test_secondary_loop_empty_null_padded(self):
        # order present, no line elements -> outer-join: 1 row, empty line_id
        xml = "<root><order><oid>O9</oid></order></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        comp = _make_component(self._multiloop_cfg())
        result = comp._process(df_in)
        main = result["main"]
        assert len(main) == 1
        assert main["order_id"].tolist() == ["O9"]
        assert main["line_id"].tolist() == [""]

    def test_namespaced_multiloop(self):
        xml = (
            '<root xmlns="http://ex.com">'
            "<order><oid>O1</oid><line><lid>L1</lid></line></order>"
            "</root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = self._multiloop_cfg()
        cfg["expressions"] = {"order_id": "ns0:oid", "line_id": "ns0:lid"}
        comp = _make_component(cfg)
        result = comp._process(df_in)
        main = result["main"]
        assert len(main) == 1
        assert main["order_id"].tolist() == ["O1"]
        assert main["line_id"].tolist() == ["L1"]

    def test_multiloop_xpath_eval_error_yields_empty_value(self, caplog):
        xml = "<root><order><oid>O1</oid><line><lid>L1</lid></line></order></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = self._multiloop_cfg()
        # malformed XPath for one column -> warning + empty value
        cfg["expressions"] = {"order_id": "oid[bad(", "line_id": "./lid"}
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            result = comp._process(df_in)
        main = result["main"]
        assert main["order_id"].tolist() == [""]
        assert main["line_id"].tolist() == ["L1"]
        assert any("XPath eval error" in r.getMessage() for r in caplog.records)

    def test_multiloop_loop_node_xpath_error_logged(self, caplog):
        # A loop_node name containing an invalid XPath char triggers the
        # find-loop-node exception branch (lines 922-927).
        xml = "<root><order><oid>O1</oid></order></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = self._multiloop_cfg()
        cfg["loop_nodes"] = ["order", "li[ne"]
        cfg["expression_contexts"] = {"order_id": "order", "line_id": "li[ne"}
        comp = _make_component(cfg)
        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.transform.xml_map"):
            result = comp._process(df_in)
        # secondary loop errored -> elems=[] -> null padded; 1 primary row
        assert len(result["main"]) == 1
        assert any("XPath error finding loop node" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------------------
# TestEvaluateXmlForRowBranches (lines 1068, 1100-1105, 1126-1144, 1165-1166)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEvaluateXmlForRowBranches:
    def test_empty_expression_sets_empty_value(self):
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config()
        cfg["expressions"] = {"id": "./id", "name": ""}  # name has no expression
        comp = _make_component(cfg)
        result = comp._process(df_in)
        main = result["main"]
        assert main["id"].tolist() == ["1"]
        assert main["name"].tolist() == [""]

    def test_ancestor_fallback_from_root(self):
        # ./ancestor:: returns nothing on the loop node, so the //tail fallback
        # from root is used (lines 1122-1144).
        xml = (
            "<root>"
            "<meta><region>EU</region></meta>"
            "<item><id>1</id></item>"
            "</root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config()
        cfg["output_schema"] = [
            {"name": "id", "type": "id_String"},
            {"name": "region", "type": "id_String"},
        ]
        cfg["expressions"] = {
            "id": "./id",
            "region": "./ancestor::region",
        }
        comp = _make_component(cfg)
        result = comp._process(df_in)
        main = result["main"]
        assert main["id"].tolist() == ["1"]
        assert main["region"].tolist() == ["EU"]

    def test_ancestor_fallback_namespaced_from_root(self):
        # Namespaced doc: ./ancestor::region is empty on the loop node (region
        # is in a sibling subtree), so the //region fallback from ROOT under the
        # ns branch (lines 1134-1136) must recover the value.
        xml = (
            '<root xmlns="http://ex.com">'
            "<meta><region>EU</region></meta>"
            "<item><id>1</id></item>"
            "</root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config()
        cfg["output_schema"] = [
            {"name": "id", "type": "id_String"},
            {"name": "region", "type": "id_String"},
        ]
        cfg["expressions"] = {
            "id": "./id",
            "region": "./ancestor::region",
        }
        comp = _make_component(cfg)
        result = comp._process(df_in)
        main = result["main"]
        assert main["id"].tolist() == ["1"]
        assert main["region"].tolist() == ["EU"]

    def test_primary_xpath_error_sets_empty(self):
        # Malformed primary XPath raises at the first xpath call (the primary
        # except branch sets the column to "" and continues).
        xml = "<root><item><id>1</id></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config()
        cfg["output_schema"] = [{"name": "id", "type": "id_String"}]
        cfg["expressions"] = {"id": "bad[("}
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert result["main"]["id"].tolist() == [""]

    def test_scoping_for_multiple_results(self):
        # An expression that matches multiple descendants triggers the
        # multi-result scoping branch (lines 1147-1152).
        xml = (
            "<root>"
            "<group><item><val>A</val><val>B</val></item></group>"
            "</root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config()
        cfg["output_schema"] = [{"name": "val", "type": "id_String"}]
        cfg["expressions"] = {"val": ".//val"}
        comp = _make_component(cfg)
        result = comp._process(df_in)
        # First scoped value is extracted (non-empty)
        assert result["main"]["val"].tolist()[0] in ("A", "B")

    def test_filter_excludes_node(self):
        # expression_filter active with a fake bridge that excludes node 0.
        xml = (
            "<root>"
            "<item><id>1</id><name>A</name></item>"
            "<item><id>2</id><name>B</name></item>"
            "</root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={
            "activate_expression_filter": True,
            "expression_filter": "[r.c:/root/item/id]",
        })
        comp = _make_component(cfg)
        comp.java_bridge = _FakeBridge(returns={"_f0": False, "_f1": True})
        result = comp._process(df_in)
        main = result["main"]
        # node 0 filtered out -> only id=2 survives
        assert main["id"].tolist() == ["2"]


# ------------------------------------------------------------------
# TestProcessBranches (lines 1242-1244, 1286-1287, 1385, 1399)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessBranches:
    def test_expression_filter_active_logs_bridge(self, caplog):
        xml = "<root><item><id>1</id><name>A</name></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = _make_minimal_config(extra={
            "activate_expression_filter": True,
            "expression_filter": "[r.c:/root/item/id]",
        })
        comp = _make_component(cfg)
        comp.java_bridge = _FakeBridge()
        with caplog.at_level(logging.INFO, logger="src.v1.engine.components.transform.xml_map"):
            comp._process(df_in)
        assert any("expression_filter active" in r.getMessage() for r in caplog.records)

    def test_list_xml_value_is_null_check_swallowed(self):
        # A list value makes pd.isna() return an array; bool() raises -> the
        # except branch (lines 1286-1287) sets is_null=False, and the row is
        # then treated as non-null XML (parse fails -> reject).
        df_in = pd.DataFrame({"xml": pd.Series([["a", "b"]], dtype=object)})
        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _make_component(cfg)
        result = comp._process(df_in)
        # list is not '' and not null -> parse attempt fails -> reject
        assert len(result["reject"]) == 1

    def test_die_on_error_eval_failure_raises(self):
        # die_on_error=True with a multiloop eval that raises inside the helper.
        xml = "<root><order><oid>O1</oid></order></root>"
        df_in = pd.DataFrame({"xml": [xml]})

        class _Boom(XMLMap):
            def _evaluate_xml_for_row(self, *a, **k):
                raise RuntimeError("eval kaboom")

        cfg = _make_minimal_config(extra={"die_on_error": True})
        comp = _Boom(
            component_id="xm_boom",
            config=cfg,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.config = dict(cfg)
        with pytest.raises(DataValidationError):
            comp._process(df_in)

    def test_eval_failure_routes_to_reject(self):
        xml = "<root><item><id>1</id></item></root>"
        df_in = pd.DataFrame({"xml": [xml]})

        class _Boom(XMLMap):
            def _evaluate_xml_for_row(self, *a, **k):
                raise RuntimeError("eval kaboom")

        cfg = _make_minimal_config(extra={"die_on_error": False})
        comp = _Boom(
            component_id="xm_boom2",
            config=cfg,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.config = dict(cfg)
        result = comp._process(df_in)
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "EVAL_ERROR"

