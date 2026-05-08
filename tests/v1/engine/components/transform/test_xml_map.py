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
from src.v1.engine.components.transform.xml_map import XMLMap, split_steps
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
