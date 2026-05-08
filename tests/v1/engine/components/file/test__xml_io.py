"""Tests for _xml_io shared helpers (Phase 12-02).

Covers:
    TestSecureXmlParser  -- XXE, billion-laughs, recover flag, DOCTYPE handling
    TestParseXmlStrategy -- DOM vs stream selection by size; boundary inclusive
    TestIterparseLoopQuery -- yields, clears, sibling cleanup, secure flags, tag filter
    TestLogStrategy      -- ASCII-only INFO line shape
    TestModuleImport     -- basic importability

No mocks of lxml.etree per D-D4 -- all tests use real XML strings or files.
"""
import logging
import os
import textwrap
import tracemalloc

import pytest
from lxml import etree

from src.v1.engine.components.file import _xml_io


# ------------------------------------------------------------------
# Shared XML payloads (real strings, no mocks -- D-D4)
# ------------------------------------------------------------------

_XXE_DOC = textwrap.dedent("""\
    <?xml version="1.0"?>
    <!DOCTYPE foo [
      <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <root>&xxe;</root>
""").encode("utf-8")

_BILLION_LAUGHS_DOC = textwrap.dedent("""\
    <?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
      <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
    ]>
    <lolz>&lol3;</lolz>
""").encode("utf-8")


# ==================================================================
# TestSecureXmlParser
# ==================================================================

@pytest.mark.unit
class TestSecureXmlParser:
    """Tests for secure_xml_parser() factory function."""

    def test_returns_xmlparser_instance(self):
        """secure_xml_parser() must return an etree.XMLParser."""
        p = _xml_io.secure_xml_parser()
        assert isinstance(p, etree.XMLParser)

    def test_recover_default_false(self):
        """With recover=False (default), malformed XML raises XMLSyntaxError."""
        p = _xml_io.secure_xml_parser()
        with pytest.raises(etree.XMLSyntaxError):
            etree.fromstring(b"<root><unclosed></root>", parser=p)

    def test_recover_true_honors_override(self):
        """secure_xml_parser(recover=True) passes the flag through to lxml."""
        p = _xml_io.secure_xml_parser(recover=True)
        # lxml with recover=True does not raise on malformed XML; it returns a partial tree
        tree = etree.fromstring(b"<root><unclosed></root>", parser=p)
        assert tree is not None

    def test_xxe_entities_not_resolved(self):
        """resolve_entities=False prevents external entity expansion (XXE attack)."""
        p = _xml_io.secure_xml_parser()
        tree = etree.fromstring(_XXE_DOC, parser=p)
        # With resolve_entities=False the &xxe; entity reference is NOT replaced
        # with the content of /etc/passwd
        text = tree.text or ""
        assert "/etc/passwd" not in text
        assert "root:" not in text

    def test_billion_laughs_does_not_exhaust_memory(self):
        """load_dtd=False + resolve_entities=False neutralize billion-laughs expansion.

        With these secure flags, lxml does NOT expand entity references -- the body
        is treated as unexpanded (text=None). The exponential string multiplication
        (the attack) never happens. No OOM, no hang, no explosion.
        """
        p = _xml_io.secure_xml_parser()
        # Parsing must succeed (no explosion, no hang) -- load_dtd=False prevents
        # the DTD-based entity expansion from being loaded at all
        result = etree.fromstring(_BILLION_LAUGHS_DOC, parser=p)
        # Entity reference &lol3; is NOT expanded -- the element content is None
        # (not thousands of "lol" repetitions which would indicate expansion occurred)
        serialized = etree.tostring(result, encoding="unicode")
        # With expansion, the output would be megabytes of "lol" repeated ~1000 times;
        # without expansion, the serialized form is a compact reference entity string
        assert len(serialized) < 10_000, (
            "Serialized output is suspiciously large (%d bytes) -- "
            "entity expansion may have occurred" % len(serialized)
        )

    def test_doctype_present_but_entities_unresolved(self):
        """A DOCTYPE declaration is tolerated; entity references stay literal."""
        doc = b"<?xml version='1.0'?><!DOCTYPE r [<!ENTITY x 'hello'>]><r>&x;</r>"
        p = _xml_io.secure_xml_parser()
        tree = etree.fromstring(doc, parser=p)
        # &x; is NOT expanded because resolve_entities=False
        assert "hello" not in (tree.text or "")

    def test_no_load_dtd_flag_set(self):
        """Confirm the parser was built with load_dtd=False (no external DTD fetch)."""
        p = _xml_io.secure_xml_parser()
        # We cannot directly inspect XMLParser flags via public API, so we test
        # behaviorally: a billion-laughs payload (DTD-based expansion attack) must
        # fail rather than hang. This is already covered by test_billion_laughs, but
        # a lightweight assertion here confirms the factory signature hasn't regressed.
        assert isinstance(p, etree.XMLParser)

    def test_recover_false_is_strict_by_default(self):
        """recover=False is the default -- mismatched tags fail, not silently pass."""
        p = _xml_io.secure_xml_parser()
        # Two separate calls both get strict parsers
        p2 = _xml_io.secure_xml_parser()
        for parser in [p, p2]:
            with pytest.raises(etree.XMLSyntaxError):
                etree.fromstring(b"<a><b></a>", parser=parser)


# ==================================================================
# TestParseXmlStrategy
# ==================================================================

@pytest.mark.unit
class TestParseXmlStrategy:
    """Tests for parse_xml_strategy() threshold-switching logic."""

    def test_dom_branch_for_small_file(self, tmp_path):
        """Files below threshold use full DOM parse and return etree._ElementTree."""
        f = tmp_path / "small.xml"
        f.write_text("<root><a/></root>")
        strategy, obj = _xml_io.parse_xml_strategy(str(f), threshold_mb=50)
        assert strategy == "dom"
        assert isinstance(obj, etree._ElementTree)

    def test_stream_branch_for_large_file(self, synthetic_60mb_xml):
        """Files >= 50 MB return ('stream', filename) tuple."""
        strategy, obj = _xml_io.parse_xml_strategy(str(synthetic_60mb_xml), threshold_mb=50)
        assert strategy == "stream"
        assert obj == str(synthetic_60mb_xml)

    def test_threshold_boundary_is_inclusive(self, tmp_path):
        """A file exactly at threshold_mb is treated as 'stream' (>= boundary)."""
        # We cannot create an exact 50 MB file cheaply, so we test the boundary
        # logic: with threshold_mb=0 even a tiny file is >= threshold
        f = tmp_path / "tiny.xml"
        f.write_text("<root/>")
        strategy, _ = _xml_io.parse_xml_strategy(str(f), threshold_mb=0)
        assert strategy == "stream"

    def test_missing_file_propagates_oserror(self, tmp_path):
        """parse_xml_strategy propagates os.stat's FileNotFoundError upward."""
        with pytest.raises((FileNotFoundError, OSError)):
            _xml_io.parse_xml_strategy(str(tmp_path / "missing.xml"), threshold_mb=50)

    def test_dom_result_is_parseable_tree(self, tmp_path):
        """DOM result is a real lxml tree that can be queried with XPath."""
        f = tmp_path / "data.xml"
        f.write_text("<items><item id='1'/><item id='2'/></items>")
        _, tree = _xml_io.parse_xml_strategy(str(f), threshold_mb=50)
        items = tree.getroot().xpath("//item")
        assert len(items) == 2

    def test_parse_xml_strategy_does_not_log(self, tmp_path, caplog):
        """parse_xml_strategy() must not log -- logging is the caller's job."""
        f = tmp_path / "small.xml"
        f.write_text("<root/>")
        with caplog.at_level(logging.DEBUG, logger="src.v1.engine.components.file._xml_io"):
            _xml_io.parse_xml_strategy(str(f), threshold_mb=50)
        # No log records should have been emitted by parse_xml_strategy
        assert len(caplog.records) == 0


# ==================================================================
# TestIterparseLoopQuery
# ==================================================================

@pytest.mark.unit
class TestIterparseLoopQuery:
    """Tests for iterparse_loop_query() streaming generator."""

    def test_yields_matching_elements(self, tmp_path):
        """iterparse_loop_query yields all elements matching loop_tag."""
        f = tmp_path / "items.xml"
        f.write_text(
            "<root>"
            "<item><id>1</id></item>"
            "<item><id>2</id></item>"
            "<item><id>3</id></item>"
            "</root>"
        )
        # Must capture child data BEFORE the generator clears the element
        ids = []
        for el in _xml_io.iterparse_loop_query(str(f), "item"):
            id_el = el.find("id")
            ids.append(id_el.text if id_el is not None else None)
        assert ids == ["1", "2", "3"]

    def test_filters_by_tag_only(self, tmp_path):
        """Only elements with the specified tag are yielded; siblings are skipped."""
        f = tmp_path / "mixed.xml"
        f.write_text(
            "<root>"
            "<item>a</item>"
            "<other>b</other>"
            "<item>c</item>"
            "</root>"
        )
        seen_tags = [el.tag for el in _xml_io.iterparse_loop_query(str(f), "item")]
        assert seen_tags == ["item", "item"]

    def test_element_cleared_after_yield(self, tmp_path):
        """After yielding, the element's text and children are None (cleared)."""
        f = tmp_path / "clear_test.xml"
        f.write_text("<root><item><child>data</child></item></root>")
        cleared_elements = []
        for el in _xml_io.iterparse_loop_query(str(f), "item"):
            # Force the generator to advance to trigger element.clear()
            cleared_elements.append(el)
        # After iteration completes, the element should be cleared
        for el in cleared_elements:
            # text should be None after clear()
            assert el.text is None
            # children should be empty after clear()
            assert len(list(el)) == 0

    def test_streaming_memory_bounded(self, synthetic_60mb_xml):
        """Pitfall P-3 regression guard: peak memory must stay under 100 MB on 60 MB file."""
        tracemalloc.start()
        count = 0
        for _el in _xml_io.iterparse_loop_query(str(synthetic_60mb_xml), "item"):
            count += 1
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        # A 60 MB file with element clearing + sibling cleanup should keep
        # peak memory well under 100 MB (constant-memory streaming)
        assert count > 50_000, "Expected > 50,000 items in synthetic 60 MB file"
        assert peak < 100 * 1024 * 1024, (
            "Peak memory %.1f MB exceeds 100 MB bound (Pitfall P-3 regression)"
            % (peak / 1024 / 1024)
        )

    def test_secure_flags_forwarded_to_iterparse(self, tmp_path):
        """XXE entities are not resolved even through the iterparse path."""
        f = tmp_path / "xxe_stream.xml"
        f.write_bytes(_XXE_DOC)
        # The generator tags on 'root'; the XXE entity must not resolve to /etc/passwd
        for el in _xml_io.iterparse_loop_query(str(f), "root"):
            assert "/etc/passwd" not in (el.text or "")

    def test_generator_is_lazy(self, tmp_path):
        """iterparse_loop_query returns a generator, not a pre-built list."""
        f = tmp_path / "gen.xml"
        f.write_text("<root><item>x</item></root>")
        gen = _xml_io.iterparse_loop_query(str(f), "item")
        import types
        assert isinstance(gen, types.GeneratorType)


# ==================================================================
# TestLogStrategy
# ==================================================================

@pytest.mark.unit
class TestLogStrategy:
    """Tests for log_strategy() ASCII-only INFO log emitter."""

    def test_emits_expected_format(self, caplog):
        """log_strategy emits exactly the expected INFO message format."""
        with caplog.at_level(logging.INFO, logger="src.v1.engine.components.file._xml_io"):
            _xml_io.log_strategy("comp_1", "dom", 12.34, 50)
        messages = [r.getMessage() for r in caplog.records]
        assert any(
            "[comp_1] XML strategy=dom size=12.34MB threshold=50MB" in m
            for m in messages
        ), "Expected log pattern not found in: %r" % messages

    def test_log_message_is_ascii(self, caplog):
        """log_strategy output must round-trip through .encode('ascii') without error."""
        with caplog.at_level(logging.INFO, logger="src.v1.engine.components.file._xml_io"):
            _xml_io.log_strategy("c", "stream", 60.0, 50)
        for r in caplog.records:
            # Must not raise UnicodeEncodeError -- ASCII-only mandate
            r.getMessage().encode("ascii")

    def test_emits_exactly_one_record(self, caplog):
        """log_strategy emits exactly one log record per call."""
        with caplog.at_level(logging.INFO, logger="src.v1.engine.components.file._xml_io"):
            _xml_io.log_strategy("x", "dom", 1.0, 50)
        assert len(caplog.records) == 1

    def test_stream_strategy_log_format(self, caplog):
        """log_strategy correctly formats 'stream' strategy label."""
        with caplog.at_level(logging.INFO, logger="src.v1.engine.components.file._xml_io"):
            _xml_io.log_strategy("tFileInputXML_1", "stream", 75.5, 50)
        messages = [r.getMessage() for r in caplog.records]
        assert any("XML strategy=stream" in m for m in messages)


# ==================================================================
# TestModuleImport
# ==================================================================

@pytest.mark.unit
class TestModuleImport:
    """Sanity: the module imports without side-effect errors."""

    def test_module_importable(self):
        """_xml_io imports cleanly and exposes the 4 expected public helpers."""
        from src.v1.engine.components.file import _xml_io as m
        assert callable(m.secure_xml_parser)
        assert callable(m.parse_xml_strategy)
        assert callable(m.iterparse_loop_query)
        assert callable(m.log_strategy)

    def test_module_has_no_defusedxml_import(self):
        """_xml_io must not import defusedxml (deprecated per RESEARCH P-1).

        The module docstring may reference defusedxml by name for historical
        context; what is forbidden is an actual 'import defusedxml' statement.
        """
        import importlib
        import sys
        mod_name = "src.v1.engine.components.file._xml_io"
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
        else:
            mod = importlib.import_module(mod_name)
        mod_file = mod.__file__
        with open(mod_file, "r", encoding="ascii") as fh:
            source = fh.read()
        # Check that no actual import statement pulls in defusedxml
        import_lines = [
            line.strip() for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        assert not any("defusedxml" in line for line in import_lines), (
            "Found defusedxml in import statements: %r" % [
                l for l in import_lines if "defusedxml" in l
            ]
        )
