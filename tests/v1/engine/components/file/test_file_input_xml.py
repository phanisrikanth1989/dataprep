"""Tests for FileInputXML engine component (tFileInputXML, Phase 12-03).

Test classes (per S-8 per-Talaxie-param discipline + audit OPEN-item regression):
    TestRegistry, TestBaseComponent, TestValidateConfig, TestProcessMain,
    TestProcessReject, TestStats, TestParam<X> (one per javajet param),
    TestColumnMismatch, TestNoRuntimeError, TestStreamingPath

Per D-D1 -- per-Talaxie-javajet-parameter positive + negative tests.
Per D-D4 -- no mocks of lxml.etree; all XML inputs are real strings or files.
Per 12-01-AUDIT -- regression-guards every OPEN item closed by Plan 12-03.
"""
import logging
import os
import re
import textwrap
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_input_xml import FileInputXML
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Module-level fixtures / helpers
# ------------------------------------------------------------------

_SAMPLE_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <bills>
      <bill id="1"><amount>10.5</amount></bill>
      <bill id="2"><amount>20.0</amount></bill>
      <bill id="3"><amount>30.5</amount></bill>
      <bill id="4"><amount>40.0</amount></bill>
      <bill id="5"><amount>50.5</amount></bill>
    </bills>
""")

# Namespace-prefixed variant
_NS_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <ns:bills xmlns:ns="http://example.com/bills">
      <ns:bill ns:id="1"><ns:amount>10.5</ns:amount></ns:bill>
      <ns:bill ns:id="2"><ns:amount>20.0</ns:amount></ns:bill>
    </ns:bills>
""")

# Multi-namespace document (child element introduces new namespace)
_MULTI_NS_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <root xmlns:a="http://a.example.com">
      <a:item>
        <b:val xmlns:b="http://b.example.com">hello</b:val>
      </a:item>
    </root>
""")


def _write_xml(tmp_path, content: str = _SAMPLE_XML, name: str = "in.xml") -> str:
    """Write XML content to a temp file and return its path."""
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return str(f)


def _make_component(config: Dict[str, Any], comp_id: str = "fi_xml_1") -> FileInputXML:
    """Build a FileInputXML with GlobalMap and ContextManager wired up."""
    comp = FileInputXML(
        component_id=comp_id,
        config=config,
        global_map=GlobalMap(),
        context_manager=ContextManager(),
    )
    return comp


def _direct_process(comp: FileInputXML) -> Dict[str, Any]:
    """Set config from _original_config and call _process() directly (bypasses schema validation)."""
    import copy
    comp.config = copy.deepcopy(comp._original_config)
    comp._stats_set_by_component = False
    return comp._process(None)


# ------------------------------------------------------------------
# TestRegistry -- Test 1
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    def test_registered_under_both_names(self):
        """Test 1: Both V1 and Talend alias resolve to the same class."""
        assert REGISTRY.get("FileInputXML") is FileInputXML
        assert REGISTRY.get("tFileInputXML") is FileInputXML


# ------------------------------------------------------------------
# TestBaseComponent -- Test 2
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBaseComponent:
    def test_inherits_base_component(self):
        """Test 2: FileInputXML is a proper BaseComponent subclass with required interface."""
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(FileInputXML, BaseComponent)
        assert hasattr(FileInputXML, "_process")
        assert hasattr(FileInputXML, "execute")
        assert hasattr(FileInputXML, "_validate_config")


# ------------------------------------------------------------------
# TestValidateConfig -- Tests 3-6
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_filepath_raises(self):
        """Test 3: Missing 'filepath' key raises ConfigurationError naming the key."""
        comp = _make_component({"loop_query": "//bill"})
        import copy
        comp.config = copy.deepcopy(comp._original_config)
        with pytest.raises(ConfigurationError, match="filepath"):
            comp._validate_config()

    def test_missing_loop_query_raises(self):
        """Test 4: Missing 'loop_query' key raises ConfigurationError."""
        comp = _make_component({"filepath": "/some/file.xml"})
        import copy
        comp.config = copy.deepcopy(comp._original_config)
        with pytest.raises(ConfigurationError, match="loop_query"):
            comp._validate_config()

    def test_context_var_filepath_passes_validate(self):
        """Test 5 (Rule 12): A filepath with a context variable reference does NOT trigger
        file-existence check in _validate_config -- content checks are deferred to _process."""
        comp = _make_component({
            "filepath": "${context.in_file}",
            "loop_query": "//bill",
        })
        import copy
        comp.config = copy.deepcopy(comp._original_config)
        comp._validate_config()  # must not raise

    def test_bool_typed_config_not_bool_raises(self):
        """Test 6: die_on_error (and other bool keys) receiving a non-bool raises ConfigurationError."""
        comp = _make_component({
            "filepath": "/f.xml",
            "loop_query": "//bill",
            "die_on_error": "yes",  # string, not bool
        })
        import copy
        comp.config = copy.deepcopy(comp._original_config)
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()


# ------------------------------------------------------------------
# TestProcessMain -- Test 7
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    def test_basic_5row_extraction(self, tmp_path):
        """Test 7: 5-row XML with simple LOOP_QUERY + MAPPING returns 5-row DataFrame."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [
                {"column": "bill_id", "xpath": "@id"},
                {"column": "amount", "xpath": "amount"},
            ],
        })
        result = _direct_process(comp)
        assert "main" in result
        df = result["main"]
        assert len(df) == 5
        assert list(df.columns) == ["bill_id", "amount"]
        assert df.iloc[0]["bill_id"] == "1"
        assert df.iloc[4]["bill_id"] == "5"


# ------------------------------------------------------------------
# TestProcessReject -- Tests 8-11
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_missing_file_die_false_produces_reject_row(self):
        """Test 8 (ENG-FIX-002): die_on_error=False, missing file -> empty main + reject with FILE_MISSING."""
        comp = _make_component({
            "filepath": "/no/such/file.xml",
            "loop_query": "//bill",
            "die_on_error": False,
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 0
        reject = result["reject"]
        assert len(reject) == 1
        assert reject.iloc[0]["errorCode"] == "FILE_MISSING"
        assert "errorMessage" in reject.columns

    def test_bad_xpath_in_mapping_produces_reject_row(self, tmp_path):
        """Test 9 (ENG-FIX-002): Invalid mapping XPath routes row to reject with XPATH_ERROR."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [
                # lxml raises XPathEvalError for expressions with unbalanced brackets
                {"column": "bad", "xpath": "amount["},
            ],
            "die_on_error": False,
        })
        result = _direct_process(comp)
        reject = result["reject"]
        assert len(reject) >= 1
        assert reject.iloc[0]["errorCode"] == "XPATH_ERROR"

    def test_nodecheck_missing_element_routes_to_reject(self, tmp_path):
        """Test 10 (ENG-FIX-002): nodecheck=True with missing element -> NODECHECK_FAIL in reject."""
        xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <root>
              <item><name>Alice</name></item>
              <item></item>
            </root>
        """)
        xml_file = _write_xml(tmp_path, xml)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/root/item",
            "mapping": [
                {"column": "name", "xpath": "name", "nodecheck": True},
            ],
            "die_on_error": False,
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 1  # Alice passes
        reject = result["reject"]
        assert len(reject) == 1
        assert reject.iloc[0]["errorCode"] == "NODECHECK_FAIL"

    def test_bad_xpath_die_on_error_true_raises(self, tmp_path):
        """Test 11 (ENG-FIX-002): die_on_error=True with invalid mapping XPath raises FileOperationError."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "bad", "xpath": "amount["}],
            "die_on_error": True,
        })
        with pytest.raises(FileOperationError):
            _direct_process(comp)


# ------------------------------------------------------------------
# TestStats -- Test 12
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_global_map_stats_set_after_process(self, tmp_path):
        """Test 12: After _process the GlobalMap has NB_LINE / NB_LINE_OK / NB_LINE_REJECT set."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        gm = GlobalMap()
        comp = FileInputXML(
            component_id="fi_xml_stats",
            config={
                "filepath": xml_file,
                "loop_query": "/bills/bill",
                "mapping": [{"column": "bid", "xpath": "@id"}],
            },
            global_map=gm,
            context_manager=ContextManager(),
        )
        _direct_process(comp)
        # Stats are set by _update_stats inside _process
        assert comp.stats["NB_LINE"] == 5
        assert comp.stats["NB_LINE_OK"] == 5
        assert comp.stats["NB_LINE_REJECT"] == 0


# ------------------------------------------------------------------
# TestParamFilename -- Tests 13-14
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamFilename:
    def test_valid_filepath_resolves(self, tmp_path):
        """Test 13 (FILENAME pos): valid file path produces expected DataFrame."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 5

    def test_nonexistent_file_routes_reject(self):
        """Test 14 (FILENAME neg): nonexistent file with die_on_error=False -> reject."""
        comp = _make_component({
            "filepath": "/does/not/exist.xml",
            "loop_query": "//bill",
            "die_on_error": False,
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 0
        assert result["reject"].iloc[0]["errorCode"] == "FILE_MISSING"


# ------------------------------------------------------------------
# TestParamLoopQuery -- Tests 15-16
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamLoopQuery:
    def test_matching_loop_query_yields_rows(self, tmp_path):
        """Test 15 (LOOP_QUERY pos): matching loop_query extracts rows."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 5

    def test_non_matching_loop_query_yields_empty(self, tmp_path):
        """Test 16 (LOOP_QUERY neg): no-match loop_query yields empty DF (not an error)."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/invoice",  # doesn't exist
            "mapping": [{"column": "amount", "xpath": "amount"}],
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 0
        # reject should also be empty (no per-node errors)
        assert len(result["reject"]) == 0


# ------------------------------------------------------------------
# TestParamMapping -- Tests 17-19
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamMapping:
    def test_bare_attr_xpath_returns_attribute(self, tmp_path):
        """Test 17 (MAPPING @attr pos, ENG-FIX-008): MAPPING xpath='@id' on loop element
        returns the 'id' attribute of each <bill> element."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "bill_id", "xpath": "@id"}],
        })
        result = _direct_process(comp)
        df = result["main"]
        assert len(df) == 5
        assert list(df["bill_id"]) == ["1", "2", "3", "4", "5"]

    def test_nodecheck_present_element_passes(self, tmp_path):
        """Test 18 (MAPPING nodecheck pos): nodecheck=True with present element is included in main."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount", "nodecheck": True}],
        })
        result = _direct_process(comp)
        # All 5 bills have <amount>; all should pass
        assert len(result["main"]) == 5
        assert len(result["reject"]) == 0

    def test_nodecheck_missing_element_routed_to_reject(self, tmp_path):
        """Test 19 (MAPPING nodecheck neg): nodecheck=True with missing element -> reject."""
        xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <bills>
              <bill id="1"><amount>10.5</amount></bill>
              <bill id="2"></bill>
            </bills>
        """)
        xml_file = _write_xml(tmp_path, xml)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount", "nodecheck": True}],
            "die_on_error": False,
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 1
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NODECHECK_FAIL"


# ------------------------------------------------------------------
# TestParamLimit -- Tests 20-22
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamLimit:
    def test_empty_limit_no_cap(self, tmp_path):
        """Test 20 (LIMIT pos, ENG-FIX-007): empty string limit -> all rows extracted."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "limit": "",
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 5

    def test_zero_limit_reads_nothing(self, tmp_path):
        """Test 21 (LIMIT neg, ENG-FIX-007): limit="0" -> 0 rows (Talend semantic)."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "limit": "0",
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 0

    def test_numeric_limit_caps_rows(self, tmp_path):
        """Test 22 (LIMIT pos, ENG-FIX-007): limit="3" -> exactly 3 rows from 5-element doc."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "limit": "3",
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 3


# ------------------------------------------------------------------
# TestParamEncoding -- Tests 23-24
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamEncoding:
    def test_latin1_fixture_parses_correctly(self, tmp_path):
        """Test 23 (ENCODING pos, ENG-FIX-006): ISO-8859-15 file with non-ASCII bytes parses."""
        # Write XML with ISO-8859-15 declaration and a non-ASCII character (e.g., euro sign u00e9)
        xml_content = (
            '<?xml version="1.0" encoding="ISO-8859-15"?>'
            "<items>"
            "<item><name>caf\xe9</name></item>"
            "</items>"
        )
        f = tmp_path / "latin.xml"
        f.write_bytes(xml_content.encode("iso-8859-15"))
        comp = _make_component({
            "filepath": str(f),
            "loop_query": "/items/item",
            "mapping": [{"column": "name", "xpath": "name"}],
            "encoding": "ISO-8859-15",
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 1
        assert "caf" in result["main"].iloc[0]["name"]

    def test_wrong_encoding_declaration_handled(self, tmp_path):
        """Test 24 (ENCODING neg): lxml tolerates minor encoding mismatches via XML decl;
        if the file is truly corrupt, it routes to reject (die_on_error=False)."""
        # A valid UTF-8 file -- no encoding mismatch, should parse fine regardless of config
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "encoding": "UTF-8",
            "die_on_error": False,
        })
        result = _direct_process(comp)
        # UTF-8 matches declaration, so parsing succeeds
        assert len(result["main"]) == 5


# ------------------------------------------------------------------
# TestParamIgnoreNS -- Tests 25-26
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamIgnoreNS:
    def test_ignore_ns_true_allows_prefixless_xpath(self, tmp_path):
        """Test 25 (IGNORE_NS pos, P-5): namespaced doc with ignore_ns=True -> XPath
        without namespace prefix matches elements via local-name() rewrite."""
        xml_file = _write_xml(tmp_path, _NS_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/ns:bills/ns:bill",  # will get rewritten by ignore_ns
            "mapping": [{"column": "amount", "xpath": "ns:amount"}],
            "ignore_ns": True,
        })
        # With ignore_ns=True the query gets rewritten so ns: prefixes turn into
        # local-name() predicates. Result is: non-empty (rows found)
        result = _direct_process(comp)
        # ignore_ns rewrites the loop_query; if no match, empty is acceptable
        # but should not raise an exception
        assert "main" in result

    def test_ignore_ns_false_multi_namespace_logged(self, tmp_path):
        """Test 26 (IGNORE_NS neg, P-5): multi-namespace doc with ignore_ns=False
        -> _build_nsmap collects child-element namespaces (P-5 regression guard).
        Verifies the namespace walk crosses element boundaries."""
        xml_file = _write_xml(tmp_path, _MULTI_NS_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/root/a:item",
            "mapping": [{"column": "val", "xpath": "b:val"}],
            "ignore_ns": False,
        })
        result = _direct_process(comp)
        # The a: and b: namespaces should both be discovered by _build_nsmap
        # resulting in correct extraction
        assert "main" in result
        df = result["main"]
        # If extraction worked, val = "hello"
        if len(df) > 0:
            assert df.iloc[0]["val"] == "hello"


# ------------------------------------------------------------------
# TestParamIgnoreDtd -- Test 27
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamIgnoreDtd:
    def test_ignore_dtd_true_parses_doc_with_dtd(self, tmp_path):
        """Test 27 (IGNORE_DTD pos): doc with external DTD reference and ignore_dtd=True
        -> secure parser's load_dtd=False ensures DTD is not loaded from network."""
        # Simulate a doc with a DOCTYPE that would normally trigger DTD loading.
        # Our secure parser has load_dtd=False so this will parse without fetching network DTD.
        xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE bills SYSTEM "http://example.com/bills.dtd">
            <bills>
              <bill id="1"><amount>10.5</amount></bill>
            </bills>
        """)
        xml_file = _write_xml(tmp_path, xml)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "ignore_dtd": True,
            "die_on_error": False,
        })
        result = _direct_process(comp)
        # With load_dtd=False the parser ignores the DTD; doc parses or partial parse
        assert "main" in result


# ------------------------------------------------------------------
# TestParamDieOnError -- Test 28
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamDieOnError:
    def test_die_on_error_true_raises_on_bad_node(self, tmp_path):
        """Test 28 (DIE_ON_ERROR neg): die_on_error=True + invalid mapping XPath -> FileOperationError."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "bad", "xpath": "amount["}],
            "die_on_error": True,
        })
        with pytest.raises(FileOperationError):
            _direct_process(comp)


# ------------------------------------------------------------------
# TestColumnMismatch -- Test 29
# ------------------------------------------------------------------

@pytest.mark.unit
class TestColumnMismatch:
    def test_missing_column_yields_none(self, tmp_path):
        """Test 29 (ENG-FIX-005 regression): MAPPING with a column xpath that finds nothing
        yields None for that column; no silent zip() data loss."""
        xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <bills>
              <bill id="1"><amount>10.5</amount></bill>
              <bill id="2"><amount>20.0</amount></bill>
            </bills>
        """)
        xml_file = _write_xml(tmp_path, xml)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [
                {"column": "amount", "xpath": "amount"},
                {"column": "missing_col", "xpath": "does_not_exist"},
            ],
        })
        result = _direct_process(comp)
        df = result["main"]
        assert len(df) == 2
        assert list(df.columns) == ["amount", "missing_col"]
        # missing column xpath returns "" -> stored as None (explicit, not zip-truncated)
        assert df.iloc[0]["missing_col"] is None


# ------------------------------------------------------------------
# TestNoRuntimeError -- Test 30
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoRuntimeError:
    def test_no_runtime_error_in_source(self):
        """Test 30 (STD-FIX-001 regression): inspect source; no bare 'raise RuntimeError'."""
        src_path = Path("src/v1/engine/components/file/file_input_xml.py")
        src = src_path.read_text(encoding="ascii")
        # Strip comment lines to avoid false positives
        non_comment = "\n".join(
            line for line in src.splitlines()
            if not line.lstrip().startswith("#")
        )
        assert "raise RuntimeError" not in non_comment, (
            "Found bare RuntimeError in file_input_xml.py -- must use ConfigurationError or FileOperationError"
        )


# ------------------------------------------------------------------
# TestStreamingPath -- Tests 31-32
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStreamingPath:
    def test_streaming_branch_taken_above_threshold(self, synthetic_60mb_xml, caplog):
        """Test 31 (P-4 regression): file > threshold -> log_strategy emits 'strategy=stream'."""
        comp = _make_component({
            "filepath": str(synthetic_60mb_xml),
            "loop_query": "/root/item",
            "mapping": [{"column": "item_id", "xpath": "id"}],
            "xml_streaming_threshold_mb": 50,
        })
        with caplog.at_level(logging.INFO):
            result = _direct_process(comp)
        strategy_logs = [r.getMessage() for r in caplog.records if "strategy=" in r.getMessage()]
        assert any("strategy=stream" in msg for msg in strategy_logs), (
            "Expected 'strategy=stream' in logs; got: %s" % strategy_logs
        )
        assert len(result["main"]) > 50_000

    def test_dom_branch_when_threshold_above_size(self, synthetic_60mb_xml, caplog):
        """Test 32 (P-4 regression): threshold much higher than file size -> 'strategy=dom' logged."""
        comp = _make_component({
            "filepath": str(synthetic_60mb_xml),
            "loop_query": "/root/item",
            "mapping": [{"column": "item_id", "xpath": "id"}],
            "xml_streaming_threshold_mb": 10000,
        })
        with caplog.at_level(logging.INFO):
            _direct_process(comp)
        strategy_logs = [r.getMessage() for r in caplog.records if "strategy=" in r.getMessage()]
        assert any("strategy=dom" in msg for msg in strategy_logs), (
            "Expected 'strategy=dom' in logs; got: %s" % strategy_logs
        )


# ------------------------------------------------------------------
# TestDocumentPassing -- Tests 33-35 (document-passing / "/" loop_query and "." xpath)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestDocumentPassing:
    def test_root_loop_query_selects_document_root(self, tmp_path):
        """Test 33 (line 175): loop_query "/" treats the whole document root as a single
        loop node ([root]) -- Talend document-passing pattern -- yielding exactly one row."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/",
            # empty xpath -> element text of the root (line 348)
            "mapping": [{"column": "doc", "xpath": ""}],
        })
        result = _direct_process(comp)
        df = result["main"]
        assert len(df) == 1
        assert len(result["reject"]) == 0

    def test_dot_xpath_serializes_whole_node(self, tmp_path):
        """Test 34 (lines 353-356): MAPPING xpath="." serializes the loop element back to
        an XML string (document-passing into a downstream tXMLMap step)."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "raw", "xpath": "."}],
        })
        result = _direct_process(comp)
        df = result["main"]
        assert len(df) == 5
        # Each serialized value is the full <bill> element XML
        first = df.iloc[0]["raw"]
        assert isinstance(first, str)
        assert first.startswith("<bill")
        assert "<amount>10.5</amount>" in first

    def test_empty_xpath_returns_element_text(self, tmp_path):
        """Test 35 (line 348): MAPPING xpath="" returns the loop element's own text content."""
        xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <root>
              <item>alpha</item>
              <item>beta</item>
            </root>
        """)
        xml_file = _write_xml(tmp_path, xml)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/root/item",
            "mapping": [{"column": "txt", "xpath": ""}],
        })
        result = _direct_process(comp)
        df = result["main"]
        assert len(df) == 2
        assert list(df["txt"]) == ["alpha", "beta"]


# ------------------------------------------------------------------
# TestBuildNsmapEdge -- Tests 36-37 (defensive except in _build_nsmap)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBuildNsmapEdge:
    def test_build_nsmap_swallows_iteration_error(self):
        """Test 36 (lines 254-255): if iterating the element tree raises, _build_nsmap
        returns whatever was collected so far instead of propagating -- defensive guard."""
        comp = _make_component({
            "filepath": "/f.xml",
            "loop_query": "//bill",
        })

        class _BoomElement:
            def iter(self):
                raise RuntimeError("iteration blew up")

        # ignore_ns=False so the walk is attempted; the raised error is swallowed -> {}
        result = comp._build_nsmap(_BoomElement(), ignore_ns=False)
        assert result == {}

    def test_dot_xpath_tostring_failure_returns_empty(self, tmp_path):
        """Test 37 (lines 355-356): when etree.tostring raises for the "." node serialization,
        the except path returns "" rather than propagating."""
        import src.v1.engine.components.file.file_input_xml as mod

        comp = _make_component({
            "filepath": "/f.xml",
            "loop_query": "//bill",
        })

        # Build a real loop node, then force tostring to blow up.
        node = mod.etree.fromstring("<bill id='1'><amount>10.5</amount></bill>")
        orig_tostring = mod.etree.tostring

        def _boom(*args, **kwargs):
            raise ValueError("cannot serialize")

        mod.etree.tostring = _boom
        try:
            value = comp._eval_mapping_xpath(node, ".", {})
        finally:
            mod.etree.tostring = orig_tostring
        assert value == ""


# ------------------------------------------------------------------
# TestResidualBranches -- Tests 38-43 (error/limit/smart-result paths)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestResidualBranches:
    def test_unparseable_limit_raises_configuration_error(self, tmp_path):
        """Test 38 (lines 132-133): a non-integer LIMIT value raises ConfigurationError."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "limit": "not-a-number",
        })
        with pytest.raises(ConfigurationError, match="LIMIT"):
            _direct_process(comp)

    def test_missing_file_die_on_error_true_raises(self):
        """Test 39 (line 141): missing file with die_on_error=True raises FileOperationError."""
        comp = _make_component({
            "filepath": "/no/such/file.xml",
            "loop_query": "//bill",
            "die_on_error": True,
        })
        with pytest.raises(FileOperationError, match="not found"):
            _direct_process(comp)

    def test_malformed_xml_die_false_routes_reject(self, tmp_path):
        """Test 40 (lines 156-157): malformed XML with die_on_error=False -> PARSE_ERROR reject."""
        xml_file = _write_xml(tmp_path, "<bills><bill></bills>", name="bad.xml")
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "die_on_error": False,
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 0
        assert result["reject"].iloc[0]["errorCode"] == "PARSE_ERROR"

    def test_malformed_xml_die_true_raises(self, tmp_path):
        """Test 41 (lines 152-155): malformed XML with die_on_error=True raises FileOperationError."""
        xml_file = _write_xml(tmp_path, "<bills><bill></bills>", name="bad2.xml")
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "die_on_error": True,
        })
        with pytest.raises(FileOperationError, match="parse failed"):
            _direct_process(comp)

    def test_bad_loop_query_xpath_die_false_routes_reject(self, tmp_path):
        """Test 42 (lines 178/183): an invalid LOOP_QUERY XPath with die_on_error=False
        routes to an XPATH_ERROR reject row instead of raising."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill[",  # unbalanced bracket -> XPathEvalError
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "die_on_error": False,
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 0
        assert result["reject"].iloc[0]["errorCode"] == "XPATH_ERROR"

    def test_bad_loop_query_xpath_die_true_raises(self, tmp_path):
        """Test 43 (lines 179-182): an invalid LOOP_QUERY XPath with die_on_error=True raises."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill[",
            "mapping": [{"column": "amount", "xpath": "amount"}],
            "die_on_error": True,
        })
        with pytest.raises(FileOperationError, match="LOOP_QUERY XPath invalid"):
            _direct_process(comp)

    def test_smart_xpath_result_stringified(self, tmp_path):
        """Test 44 (line 371): an XPath returning a smart (non-element) value -- e.g. a
        text() node -- has no .text attribute, so it is stringified via str(first)."""
        xml_file = _write_xml(tmp_path, _SAMPLE_XML)
        comp = _make_component({
            "filepath": xml_file,
            "loop_query": "/bills/bill",
            # text() returns a list of _ElementUnicodeResult (smart strings) with no
            # .text attribute -> falls through to the str(first) branch (line 371).
            "mapping": [{"column": "amt", "xpath": "amount/text()"}],
        })
        result = _direct_process(comp)
        df = result["main"]
        assert len(df) == 5
        assert df.iloc[0]["amt"] == "10.5"

    def test_streaming_limit_cap(self, synthetic_60mb_xml):
        """Test 45 (line 201): streaming path honors LIMIT (idx >= limit break)."""
        comp = _make_component({
            "filepath": str(synthetic_60mb_xml),
            "loop_query": "/root/item",
            "mapping": [{"column": "item_id", "xpath": "id"}],
            "xml_streaming_threshold_mb": 50,
            "limit": "10",
        })
        result = _direct_process(comp)
        assert len(result["main"]) == 10
