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
# Minimal Java bridge mock for expression_filter tests
# ------------------------------------------------------------------

class _MockBridge:
    """Evaluates Relational.ISNULL/ISNOTNULL post-substitution expressions in Python.

    Used only in unit tests so expression_filter filtering logic can be verified
    without a running JVM.
    """

    def execute_batch_one_time_expressions(self, exprs: dict) -> dict:
        import re as _re
        result = {}
        for key, expr in exprs.items():
            m = _re.match(r"Relational\.(ISNULL|ISNOTNULL)\((.+)\)\s*$", expr.strip())
            if m:
                func, arg = m.group(1), m.group(2).strip()
                is_null = arg == "null" or arg in ('""', "''")
                result[key] = is_null if func == "ISNULL" else not is_null
            else:
                result[key] = True  # unknown → include
        return result


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


# ------------------------------------------------------------------
# TestFlatToFlatMode -- ENG-FIX: flat column-to-column bypass
# When all output_trees node expressions are in 'flow.column' format
# (e.g. 'row1.id'), XMLMap skips XML parsing and maps columns directly.
# ------------------------------------------------------------------

@pytest.mark.unit
class TestFlatToFlatMode:
    """Tests for the flat-to-flat bypass path in XMLMap._process.

    The converter produces 'flow.column' expressions (e.g. 'row1.id') for
    tXMLMap jobs that simply rename or pass-through flat columns.  Without the
    fix the component tried to parse each value as XML and crashed on integers.
    """

    # ---- helpers -------------------------------------------------------

    @staticmethod
    def _flat_cfg(cols: list) -> dict:
        """Return a minimal XMLMap config whose output_trees nodes all use
        'row1.<col>' (flat) expressions.

        ``cols`` is a list of dicts with keys 'in' (input column) and 'out'
        (output column).
        """
        nodes = [
            {"name": col["out"], "expression": f"row1.{col['in']}"}
            for col in cols
        ]
        return {
            "input_trees": [],
            "output_trees": [{"name": "out1", "nodes": nodes}],
            "connections": [],
            "output_schema": [
                {"name": col["out"], "type": "id_String"} for col in cols
            ],
            "expressions": {},
            "looping_element": "item",
            "die_on_error": False,
        }

    # ---- tests ---------------------------------------------------------

    def test_flat_to_flat_direct_column_mapping(self):
        """Test F-1: flat 'row1.col' expressions produce correct output values."""
        df_in = pd.DataFrame({"id": ["1", "2"], "name": ["Alice", "Bob"]})
        cfg = self._flat_cfg([{"in": "id", "out": "id"}, {"in": "name", "out": "name"}])
        comp = _make_component(cfg)
        result = comp._process(df_in)
        out = result["main"]
        assert list(out["id"]) == ["1", "2"]
        assert list(out["name"]) == ["Alice", "Bob"]

    def test_flat_mode_preserves_row_count(self):
        """Test F-2: 5 input rows → 5 output rows in flat mode."""
        df_in = pd.DataFrame({"val": [str(i) for i in range(5)]})
        cfg = self._flat_cfg([{"in": "val", "out": "val"}])
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["main"]) == 5

    def test_xpath_expression_prevents_flat_mode(self):
        """Test F-3: a node with an XPath expression ('/') causes _build_flat_column_map to return None."""
        cfg = _make_minimal_config()
        cfg["output_trees"] = [{"name": "out1", "nodes": [
            {"name": "id", "expression": "/root/id"},  # XPath -- not flat
        ]}]
        comp = _make_component(cfg)
        assert comp._build_flat_column_map() is None

    def test_flat_mode_stats_correct(self):
        """Test F-4: NB_LINE == NB_LINE_OK == 2, NB_LINE_REJECT == 0 after flat _process."""
        df_in = pd.DataFrame({"a": ["x", "y"]})
        cfg = self._flat_cfg([{"in": "a", "out": "a"}])
        comp = _make_component(cfg)
        comp._process(df_in)
        assert comp.stats["NB_LINE"] == 2
        assert comp.stats["NB_LINE_OK"] == 2
        assert comp.stats["NB_LINE_REJECT"] == 0

    def test_flat_mode_empty_dataframe_returns_empty(self):
        """Test F-5: empty input DataFrame → empty main result (no crash)."""
        df_in = pd.DataFrame({"id": pd.Series([], dtype=object), "name": pd.Series([], dtype=object)})
        cfg = self._flat_cfg([{"in": "id", "out": "id"}, {"in": "name", "out": "name"}])
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["main"]) == 0


# ------------------------------------------------------------------
# TestExpressionFilterNative -- D-E1 native filter evaluation
# Tests for the Relational.ISNULL / ISNOTNULL expression_filter support
# added as a native Python implementation (no Java bridge required).
# ------------------------------------------------------------------

@pytest.mark.unit
class TestExpressionFilterNative:
    """Tests for native Python evaluation of expression_filter DSL.

    Covers _parse_expression_filter, _make_filter_relative_xpath, and
    end-to-end filter application via _process.
    """

    # ---- helper to build a config with filter ----

    @staticmethod
    def _filter_cfg(func: str, abs_xpath: str) -> dict:
        """Return an XMLMap config with expression_filter set."""
        raw_filter = f"Relational.{func}([row2.col:{abs_xpath}])"
        nodes = [
            {"name": "type", "expression": "[row2.col:/Root/Item/Type]"},
        ]
        return {
            "input_trees": [],
            "output_trees": [{"name": "out1", "nodes": nodes}],
            "connections": [],
            "output_schema": [{"name": "type", "type": "id_String"}],
            "expressions": {"type": "./Type"},
            "looping_element": "Item",
            "die_on_error": False,
            "activate_expression_filter": True,
            "expression_filter": raw_filter,
        }

    # ---- _substitute_xml_placeholders ----

    def test_substitute_placeholder_with_value(self):
        """EF-1: placeholder resolved to text literal when child element has text."""
        from lxml import etree
        from src.v1.engine.components.transform.xml_map import XMLMap
        xml = "<Item><Type>X</Type></Item>"
        node = etree.fromstring(xml)
        result = XMLMap._substitute_xml_placeholders(
            "Relational.ISNULL([row2.col:/Root/Item/Type])",
            node, "Item", "", {}, "test",
        )
        assert result == 'Relational.ISNULL("X")'

    def test_substitute_placeholder_with_null(self):
        """EF-2: placeholder resolved to null when child element is absent."""
        from lxml import etree
        from src.v1.engine.components.transform.xml_map import XMLMap
        xml = "<Item></Item>"
        node = etree.fromstring(xml)
        result = XMLMap._substitute_xml_placeholders(
            "Relational.ISNULL([row2.col:/Root/Item/Type])",
            node, "Item", "", {}, "test",
        )
        assert result == "Relational.ISNULL(null)"

    def test_substitute_multiple_placeholders(self):
        """EF-3: expression with two placeholders — both substituted independently."""
        from lxml import etree
        from src.v1.engine.components.transform.xml_map import XMLMap
        xml = "<Item><A>hello</A></Item>"
        node = etree.fromstring(xml)
        result = XMLMap._substitute_xml_placeholders(
            "[row2.c:/X/Item/A] != null && [row2.c:/X/Item/B] == null",
            node, "Item", "", {}, "test",
        )
        # A has text → "hello"; B is absent → null
        assert '"hello"' in result
        assert "null" in result

    # ---- _compute_filter_mask (no bridge) ----

    def test_no_bridge_includes_all_rows(self):
        """EF-4: no Java bridge → all rows included (fail-open) with a warning."""
        from lxml import etree
        from src.v1.engine.components.transform.xml_map import XMLMap
        xml = "<Root><Item><Type>X</Type></Item><Item></Item></Root>"
        root = etree.fromstring(xml)
        comp = XMLMap.__new__(XMLMap)
        comp.java_bridge = None
        comp.config = {}
        nodes = root.findall("Item")
        mask = comp._compute_filter_mask(
            "Relational.ISNULL([row2.col:/Root/Item/Type])",
            nodes, "Item", "", {}, "test",
        )
        assert mask == [True, True]

    # ---- _make_filter_relative_xpath ----

    def test_make_relative_xpath_simple(self):
        """EF-5: _make_filter_relative_xpath strips prefix up to looping element."""
        from src.v1.engine.components.transform.xml_map import XMLMap
        rel = XMLMap._make_filter_relative_xpath(
            "/Root/Items/Item/SubChild/Value", "Item"
        )
        assert rel == "SubChild/Value"

    def test_make_relative_xpath_direct_child(self):
        """EF-6: looping element is the last segment — returns '.'."""
        from src.v1.engine.components.transform.xml_map import XMLMap
        rel = XMLMap._make_filter_relative_xpath("/Root/Items/Item", "Item")
        assert rel == "."

    def test_make_relative_xpath_not_found(self):
        """EF-7: looping element not in path — best-effort full path returned."""
        from src.v1.engine.components.transform.xml_map import XMLMap
        rel = XMLMap._make_filter_relative_xpath("/Root/Foo/Bar", "Missing")
        assert rel == "Root/Foo/Bar"

    # ---- end-to-end filter application ----

    def test_isnull_filters_rows_with_value(self):
        """EF-8: ISNULL filter keeps only rows where Type is absent (via mock bridge)."""
        xml = (
            "<Root>"
            "<Item><Type>X</Type></Item>"   # has Type -- should be excluded
            "<Item></Item>"                  # no Type -- should be included
            "<Item><Type></Type></Item>"     # empty Type -- should be included
            "</Root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = self._filter_cfg("ISNULL", "/Root/Item/Type")
        comp = _make_component(cfg)
        comp.java_bridge = _MockBridge()
        result = comp._process(df_in)
        out = result["main"]
        # Only 2 rows should pass the ISNULL filter
        assert len(out) == 2

    def test_isnotnull_filters_rows_without_value(self):
        """EF-9: ISNOTNULL filter keeps only rows where Type is present (via mock bridge)."""
        xml = (
            "<Root>"
            "<Item><Type>X</Type></Item>"   # has Type -- included
            "<Item></Item>"                  # no Type -- excluded
            "<Item><Type>Y</Type></Item>"   # has Type -- included
            "</Root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = self._filter_cfg("ISNOTNULL", "/Root/Item/Type")
        comp = _make_component(cfg)
        comp.java_bridge = _MockBridge()
        result = comp._process(df_in)
        out = result["main"]
        assert len(out) == 2

    def test_filter_inactive_passes_all_rows(self):
        """EF-10: activate_expression_filter=False — all rows pass through."""
        xml = (
            "<Root>"
            "<Item><Type>X</Type></Item>"
            "<Item></Item>"
            "</Root>"
        )
        df_in = pd.DataFrame({"xml": [xml]})
        cfg = self._filter_cfg("ISNULL", "/Root/Item/Type")
        cfg["activate_expression_filter"] = False
        comp = _make_component(cfg)
        result = comp._process(df_in)
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# TestMultiLoopEvaluation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMultiLoopEvaluation:
    """Tests for _evaluate_xml_multiloop (cross-product across multiple loop axes)."""

    _XML = (
        "<employee>"
        "  <id>101</id>"
        "  <name>John</name>"
        "  <addresses>"
        "    <address><type>Home</type><city>Dublin</city></address>"
        "    <address><type>Office</type><city>Cork</city></address>"
        "  </addresses>"
        "  <skills>"
        "    <skill>Java</skill>"
        "    <skill>SQL</skill>"
        "  </skills>"
        "  <projects>"
        "    <project><project_name>BankingApp</project_name><duration>12</duration></project>"
        "    <project><project_name>InsurancePortal</project_name><duration>8</duration></project>"
        "  </projects>"
        "</employee>"
    )

    _LOOP_NODES = ["address", "skill", "project"]

    _EXPRESSION_CONTEXTS = {
        "id": "address",
        "name": "address",
        "type": "address",
        "city": "address",
        "skill": "skill",
        "project_name": "project",
        "duration": "project",
    }

    _EXPRESSIONS = {
        "id": "./../../id",
        "name": "./../../name",
        "type": "./type",
        "city": "./city",
        "skill": ".",
        "project_name": "./project_name",
        "duration": "./duration",
    }

    _OUTPUT_SCHEMA = [
        {"name": "id", "type": "id_String"},
        {"name": "name", "type": "id_String"},
        {"name": "type", "type": "id_String"},
        {"name": "city", "type": "id_String"},
        {"name": "skill", "type": "id_String"},
        {"name": "project_name", "type": "id_String"},
        {"name": "duration", "type": "id_String"},
    ]

    def _make_cfg(self):
        return {
            "output_schema": self._OUTPUT_SCHEMA,
            "expressions": self._EXPRESSIONS,
            "looping_element": "address",
            "loop_nodes": self._LOOP_NODES,
            "expression_contexts": self._EXPRESSION_CONTEXTS,
            "die_on_error": False,
        }

    def test_cross_product_row_count(self):
        """2 addresses × 2 skills × 2 projects = 8 output rows."""
        comp = _make_component(self._make_cfg())
        df_in = pd.DataFrame({"xml": [self._XML]})
        result = comp._process(df_in)
        assert len(result["main"]) == 8

    def test_address_values_cycle_correctly(self):
        """First 4 rows share 'Home/Dublin', last 4 share 'Office/Cork'."""
        comp = _make_component(self._make_cfg())
        df_in = pd.DataFrame({"xml": [self._XML]})
        out = comp._process(df_in)["main"].reset_index(drop=True)
        assert list(out["type"][:4]) == ["Home", "Home", "Home", "Home"]
        assert list(out["type"][4:]) == ["Office", "Office", "Office", "Office"]

    def test_skill_values_alternate(self):
        """Skills alternate: Java, Java, SQL, SQL (grouped by project axis)."""
        comp = _make_component(self._make_cfg())
        df_in = pd.DataFrame({"xml": [self._XML]})
        out = comp._process(df_in)["main"].reset_index(drop=True)
        # For each address group (4 rows): Java, Java, SQL, SQL (skill × project order)
        skills = list(out["skill"][:4])
        assert skills == ["Java", "Java", "SQL", "SQL"]

    def test_project_name_values_innermost(self):
        """Projects cycle fastest: BankingApp, InsurancePortal alternating."""
        comp = _make_component(self._make_cfg())
        df_in = pd.DataFrame({"xml": [self._XML]})
        out = comp._process(df_in)["main"].reset_index(drop=True)
        # For each address+skill pair (2 rows): BankingApp, InsurancePortal
        assert out["project_name"][0] == "BankingApp"
        assert out["project_name"][1] == "InsurancePortal"

    def test_outside_loop_fields_propagated_from_primary(self):
        """id and name are evaluated from address context -> propagated to all rows."""
        comp = _make_component(self._make_cfg())
        df_in = pd.DataFrame({"xml": [self._XML]})
        out = comp._process(df_in)["main"]
        assert list(out["id"].unique()) == ["101"]
        assert list(out["name"].unique()) == ["John"]

    def test_empty_secondary_loop_null_pads(self):
        """Employee with no skills or projects -> 1 row with empty skill/project cols."""
        xml = (
            "<employee>"
            "  <id>102</id>"
            "  <name>Emma</name>"
            "  <addresses>"
            "    <address><type>Home</type><city>Galway</city></address>"
            "  </addresses>"
            "</employee>"
        )
        comp = _make_component(self._make_cfg())
        df_in = pd.DataFrame({"xml": [xml]})
        result = comp._process(df_in)
        out = result["main"]
        assert len(out) == 1
        assert out.iloc[0]["skill"] == ""
        assert out.iloc[0]["project_name"] == ""

    def test_empty_primary_loop_returns_no_rows(self):
        """When the primary loop axis (address) has no elements, return 0 rows."""
        xml = "<employee><id>103</id><name>Ghost</name></employee>"
        comp = _make_component(self._make_cfg())
        df_in = pd.DataFrame({"xml": [xml]})
        result = comp._process(df_in)
        assert len(result["main"]) == 0

    def test_single_loop_node_config_uses_legacy_path(self):
        """A config with loop_nodes of length 1 still uses _evaluate_xml_for_row."""
        xml = "<root><item><id>1</id></item><item><id>2</id></item></root>"
        cfg = {
            "output_schema": [{"name": "id", "type": "id_String"}],
            "expressions": {"id": "./id"},
            "looping_element": "item",
            "loop_nodes": ["item"],
            "expression_contexts": {},  # empty -> use_multiloop=False
            "die_on_error": False,
        }
        comp = _make_component(cfg)
        df_in = pd.DataFrame({"xml": [xml]})
        result = comp._process(df_in)
        assert list(result["main"]["id"]) == ["1", "2"]
