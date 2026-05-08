"""Tests for AdvancedFileOutputXML engine component (tAdvancedFileOutputXML, Phase 12-07).

Per S-5 sink contract: main == input_data passthrough, reject == None.
Per S-6 streaming-write hook: state held across chunks, reset() closes contexts
  from innermost to outermost.
Per D-D1: per-Talaxie-param positive + negative tests.
Per D-D4: no mocks of lxml.etree -- real I/O via tmp_path throughout.
Per Pitfall P-2 regression: explicit grep-based guard verifies no etree.tostring
  or etree.SubElement appear in the implementation source.
Per D-E1: 6 deferred sub-features each emit a logger.warning but do NOT raise.

Test classes (47 tests total; target >= 35):
  TestRegistry              -- @REGISTRY.register both names
  TestBaseComponent         -- subclass + lifecycle hooks
  TestValidateConfig        -- missing filename; Rule 12 deferred
  TestProcessMain           -- ROOT only; ROOT+LOOP; ROOT+GROUP+LOOP
  TestRootTable             -- root path; root attrs; no root -> default
  TestGroupTable            -- groupby yields per-group blocks; no group-cols -> single block
  TestLoopTable             -- loop path; per-row iteration; static value
  TestAttributes            -- attribute=true emits as XML attr on wrapper
  TestStaticElements        -- static (no-column) entries emitted as sub-elements
  TestEncoding              -- ISO-8859-15 default; UTF-8 override honored
  TestCreate                -- create=true overwrites; create=false existing file raises
  TestSplit                 -- split=true with split_every -> multiple files
  TestDeleteEmptyFile       -- empty + delete_empty_file=true -> no file
  TestStreamingHook         -- first chunk opens contexts; second reuses; reset closes
  NoBufferAndWrite          -- P-2 regression: no etree.tostring; no etree.SubElement
  TestSinkContract          -- main is input identity; reject is None
  TestStats                 -- {id}_FILE_NAME and {id}_NB_LINE in globalMap
  TestConditionalWarnDtdValid         -- warn on file_valid+dtd_valid; silent otherwise
  TestConditionalWarnXslValid         -- warn on file_valid+xsl_valid; silent otherwise
  TestConditionalWarnOutputAsXsd      -- warn on output_as_xsd=true; silent otherwise
  TestConditionalWarnAddDocumentAsNode -- warn; silent
  TestConditionalWarnAddUnmappedAttribute -- warn; silent
  TestConditionalWarnMerge            -- warn on merge=true; silent otherwise
"""
import copy
import logging
import re
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest
from lxml import etree

from src.v1.engine.base_component import BaseComponent
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_output_advanced_xml import AdvancedFileOutputXML
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


_SOURCE_FILE = Path("src/v1/engine/components/file/file_output_advanced_xml.py")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config: Dict[str, Any], comp_id: str = "adv_xml_1") -> AdvancedFileOutputXML:
    """Create an AdvancedFileOutputXML with real GlobalMap and ContextManager.

    Sets comp.config so _process() can be called directly in unit tests
    without going through execute() lifecycle.
    """
    comp = AdvancedFileOutputXML(component_id=comp_id, config=config)
    comp.global_map = GlobalMap()
    comp.context_manager = ContextManager()
    comp.config = copy.deepcopy(config)
    return comp


def _strip_comments(source: str) -> str:
    """Remove lines that begin with # (Python comment lines) from source."""
    return "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("#")
    )


def _make_df(rows: int = 5, cols=None) -> pd.DataFrame:
    """Generate a simple DataFrame for testing."""
    if cols is None:
        cols = ["id", "name", "value"]
    data = {}
    for col in cols:
        data[col] = [f"{col}_{i}" for i in range(rows)]
    return pd.DataFrame(data)


def _read_xml(path) -> etree._Element:
    """Parse an XML file to lxml element tree."""
    return etree.parse(str(path)).getroot()


# ------------------------------------------------------------------
# TestRegistry
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    """Both registration names resolve to AdvancedFileOutputXML."""

    def test_registered_under_pascal_name(self):
        """Test 1 (Registry): AdvancedFileOutputXML resolves in registry."""
        assert REGISTRY.get("AdvancedFileOutputXML") is AdvancedFileOutputXML

    def test_registered_under_talend_name(self):
        """Test 1b (Registry): tAdvancedFileOutputXML resolves in registry."""
        assert REGISTRY.get("tAdvancedFileOutputXML") is AdvancedFileOutputXML


# ------------------------------------------------------------------
# TestBaseComponent
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBaseComponent:
    """AdvancedFileOutputXML is a proper BaseComponent subclass."""

    def test_is_base_component_subclass(self):
        """Test 2 (BaseComponent): inherits from BaseComponent."""
        assert issubclass(AdvancedFileOutputXML, BaseComponent)

    def test_reset_method_exists(self):
        """Test 2b (BaseComponent): reset() method callable."""
        comp = _make_component({"filename": "/tmp/x.xml"})
        assert callable(comp.reset)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    """_validate_config raises on missing filename; defers content checks."""

    def test_missing_filename_raises(self):
        """Test 2 (Validate-config): missing 'filename' -> ConfigurationError."""
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_filename_with_context_var_passes(self):
        """Test 3 (Validate-config Rule 12): context variable reference is deferred."""
        comp = _make_component({"filename": "context.outputPath"})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    """Happy-path processing tests covering ROOT, ROOT+LOOP, ROOT+GROUP+LOOP."""

    def test_root_only_produces_root_element(self, tmp_path):
        """Test 4 (Process-main happy): ROOT_TABLE + data -> root wrapper with content."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "record", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=3, cols=["id"])
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert tree.tag == "data"

    def test_root_and_loop_yields_per_row_loop_elements(self, tmp_path):
        """Test 4b (Process-main): N rows -> N LOOP elements."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                     {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"}],
        })
        df = _make_df(rows=5, cols=["id"])
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert len(tree.findall(".//rec")) == 5

    def test_root_group_loop_three_levels(self, tmp_path):
        """Test 4c (Process-main): ROOT+GROUP+LOOP -> three-level nesting."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "group": [{"path": "region", "column": "region", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                     {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"}],
        })
        df = pd.DataFrame({"region": ["A", "A", "B"], "id": ["1", "2", "3"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert tree.tag == "data"
        assert len(tree.findall("region")) == 2
        assert len(tree.findall(".//rec")) == 3


# ------------------------------------------------------------------
# TestRootTable
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRootTable:
    """ROOT TABLE behavior."""

    def test_root_path_becomes_top_level_element(self, tmp_path):
        """Test 5 (ROOT_TABLE driven): ROOT.path='wrapper' -> <wrapper>...</wrapper>."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "wrapper", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "row", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=2, cols=["id"])
        comp._process(df)
        comp.reset()
        tree = _read_xml(tmp_path / "out.xml")
        assert tree.tag == "wrapper"

    def test_no_root_table_defaults_to_root_element(self, tmp_path):
        """Test 5b (ROOT_TABLE absent): falls back to <root> element."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "loop": [{"path": "row", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=2, cols=["id"])
        comp._process(df)
        comp.reset()
        tree = _read_xml(tmp_path / "out.xml")
        assert tree.tag == "root"

    def test_root_static_entry_emitted_as_child_element(self, tmp_path):
        """Test 5c (ROOT_TABLE[1:]): static sub-entries appear as child elements of root."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [
                {"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "meta", "column": "", "value": "v1", "attribute": "false", "order": "2"},
            ],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=1, cols=["id"])
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert "<meta>" in content


# ------------------------------------------------------------------
# TestGroupTable
# ------------------------------------------------------------------

@pytest.mark.unit
class TestGroupTable:
    """GROUP TABLE behavior."""

    def test_groupby_yields_per_region_block(self, tmp_path):
        """Test 7 (GROUP_TABLE): N regions -> N <group> blocks."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "group": [{"path": "region", "column": "region", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                     {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"}],
        })
        df = pd.DataFrame({
            "region": ["A", "A", "B", "B"],
            "id": [1, 2, 3, 4],
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert content.count("<region>") == 2
        assert content.count("<rec>") == 4

    def test_no_group_cols_emits_single_group_block(self, tmp_path):
        """Test 7b (GROUP_TABLE no cols): group_table with no column -> single group wrapper."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "group": [{"path": "batch", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = pd.DataFrame({"id": [1, 2, 3]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert content.count("<batch>") == 1
        assert content.count("<rec>") == 3

    def test_no_group_table_emits_rows_under_root(self, tmp_path):
        """Test 7c (no GROUP_TABLE): rows emitted directly under ROOT."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "items", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "item", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = pd.DataFrame({"id": ["a", "b"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert content.count("<item>") == 2


# ------------------------------------------------------------------
# TestLoopTable
# ------------------------------------------------------------------

@pytest.mark.unit
class TestLoopTable:
    """LOOP TABLE behavior."""

    def test_loop_path_names_the_row_element(self, tmp_path):
        """Test 6 (LOOP_TABLE per-row): LOOP.path='record' -> <record>...</record> per row."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "record", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = pd.DataFrame({"id": ["x", "y", "z"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert content.count("<record>") == 3

    def test_column_value_emitted_as_text(self, tmp_path):
        """Test 10 (Column value): TABLE entry with column='id' emits row[id] as text."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [
                {"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"},
            ],
        })
        df = pd.DataFrame({"id": ["abc123"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert "abc123" in content

    def test_static_value_entry_emitted_verbatim(self, tmp_path):
        """Test 9 (Static value): TABLE entry with value='X' emits literal 'X' text."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [
                {"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "status", "column": "", "value": "ACTIVE", "attribute": "false", "order": "2"},
            ],
        })
        df = pd.DataFrame({"id": ["1"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert "ACTIVE" in content


# ------------------------------------------------------------------
# TestAttributes
# ------------------------------------------------------------------

@pytest.mark.unit
class TestAttributes:
    """Attribute flag: attribute=true emits as XML attribute on the loop element."""

    def test_attribute_true_emits_as_xml_attribute(self, tmp_path):
        """Test 8 (Attribute via TABLE row.attribute=true): emits as attr, not child element."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [
                {"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "id", "column": "id", "value": "", "attribute": "true", "order": "2"},
            ],
        })
        df = pd.DataFrame({"id": ["val99"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        # Should be an XML attribute: id="val99" on <rec>, not a child <id>val99</id>
        assert 'id="val99"' in content
        assert "<id>val99</id>" not in content

    def test_attribute_false_emits_as_child_element(self, tmp_path):
        """Test 8b: attribute=false -> child element, not XML attribute."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [
                {"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "name", "column": "name", "value": "", "attribute": "false", "order": "2"},
            ],
        })
        df = pd.DataFrame({"name": ["Alice"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert "<name>Alice</name>" in content
        assert 'name="Alice"' not in content

    def test_mixed_attr_and_element(self, tmp_path):
        """Test 8c: mixed -- some entries as attrs, some as elements."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [
                {"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "id", "column": "id", "value": "", "attribute": "true", "order": "2"},
                {"path": "name", "column": "name", "value": "", "attribute": "false", "order": "3"},
            ],
        })
        df = pd.DataFrame({"id": ["42"], "name": ["Bob"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert 'id="42"' in content
        assert "<name>Bob</name>" in content


# ------------------------------------------------------------------
# TestStaticElements
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStaticElements:
    """Static entries (no column, value-only) emit as child elements."""

    def test_root_static_child_present(self, tmp_path):
        """ROOT TABLE[1:] static entry appears as a child of root element."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [
                {"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "version", "column": "", "value": "2.0", "attribute": "false", "order": "2"},
            ],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = pd.DataFrame({"id": ["x"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert "<version>2.0</version>" in content

    def test_column_driven_entry_not_treated_as_static(self, tmp_path):
        """Column-driven entries are not emitted in _emit_static_entries."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [
                {"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"},
                # Column-driven: should NOT be emitted as a root static child
                {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"},
            ],
            "loop": [
                {"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"},
            ],
        })
        df = pd.DataFrame({"id": ["x"]})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        # Column-driven root static entry is skipped; only loop entries carry the value
        tree = _read_xml(tmp_path / "out.xml")
        direct_id_children = tree.findall("id")
        assert len(direct_id_children) == 0  # not emitted as direct root child


# ------------------------------------------------------------------
# TestEncoding
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEncoding:
    """Encoding config."""

    def test_iso_8859_15_is_default(self, tmp_path):
        """Test 11 (Encoding ISO-8859-15 default): declaration says ISO-8859-15."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=1, cols=["id"])
        comp._process(df)
        comp.reset()
        raw = (tmp_path / "out.xml").read_bytes()
        assert b"ISO-8859-15" in raw

    def test_utf8_override_honored(self, tmp_path):
        """Test 12 (Encoding override UTF-8 honored): declaration says UTF-8."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "encoding": "UTF-8",
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=1, cols=["id"])
        comp._process(df)
        comp.reset()
        raw = (tmp_path / "out.xml").read_bytes()
        assert b"UTF-8" in raw


# ------------------------------------------------------------------
# TestCreate
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCreate:
    """CREATE config flag."""

    def test_create_true_overwrites_existing(self, tmp_path):
        """Test 13 (CREATE=true overwrites): second run replaces first output."""
        outfile = tmp_path / "out.xml"
        outfile.write_bytes(b"<old/>")
        comp = _make_component({
            "filename": str(outfile),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "create": True,
        })
        df = _make_df(rows=1, cols=["id"])
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_text()
        assert "<old/>" not in content

    def test_create_false_existing_file_raises(self, tmp_path):
        """Test 13 (CREATE=false existing-file -> FileOperationError)."""
        outfile = tmp_path / "out.xml"
        outfile.write_bytes(b"<existing/>")
        comp = _make_component({
            "filename": str(outfile),
            "create": False,
        })
        with pytest.raises(FileOperationError, match="create=False"):
            comp._process(_make_df(rows=1, cols=["id"]))


# ------------------------------------------------------------------
# TestSplit
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSplit:
    """SPLIT config."""

    def test_split_every_creates_multiple_files(self, tmp_path):
        """Test 14 (SPLIT_EVERY): 2500 rows + split_every=1000 -> 3 files (0,1,2)."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                     {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"}],
            "split": True,
            "split_every": "1000",
        })
        df = pd.DataFrame({"id": list(range(2500))})
        comp._process(df)
        files = list(tmp_path.glob("out*.xml"))
        assert len(files) == 3

    def test_no_split_single_file(self, tmp_path):
        """Test 14b (split=false): single output file."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "split": False,
        })
        df = _make_df(rows=10, cols=["id"])
        comp._process(df)
        comp.reset()
        files = list(tmp_path.glob("*.xml"))
        assert len(files) == 1


# ------------------------------------------------------------------
# TestDeleteEmptyFile
# ------------------------------------------------------------------

@pytest.mark.unit
class TestDeleteEmptyFile:
    """DELETE_EMPTYFILE behavior."""

    def test_empty_input_with_flag_true_no_file(self, tmp_path):
        """Test 15 (DELETE_EMPTYFILE pos): empty input + flag=true -> no file created."""
        outfile = tmp_path / "out.xml"
        outfile.write_bytes(b"<existing/>")  # existing file should be deleted
        comp = _make_component({
            "filename": str(outfile),
            "delete_empty_file": True,
        })
        comp._process(pd.DataFrame())
        assert not outfile.exists()

    def test_empty_input_with_flag_false_file_remains(self, tmp_path):
        """Test 15b (DELETE_EMPTYFILE neg): flag=false -> file remains as-is."""
        outfile = tmp_path / "out.xml"
        outfile.write_bytes(b"<existing/>")
        comp = _make_component({
            "filename": str(outfile),
            "delete_empty_file": False,
        })
        comp._process(pd.DataFrame())
        assert outfile.exists()


# ------------------------------------------------------------------
# TestStreamingHook
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStreamingHook:
    """S-6 streaming-write hook: contexts held across chunks."""

    def test_first_chunk_opens_context(self, tmp_path):
        """Test 16 (StreamingHook first chunk): after first call, _streaming_write_started=True."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=3, cols=["id"])
        comp._process(df)
        assert comp._streaming_write_started is True
        assert comp._streaming_xf is not None
        assert comp._streaming_root_ctx is not None
        comp.reset()

    def test_second_chunk_reuses_context(self, tmp_path):
        """Test 17 (StreamingHook second chunk): state held across two _process() calls."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"},
                     {"path": "id", "column": "id", "value": "", "attribute": "false", "order": "2"}],
        })
        df1 = _make_df(rows=2, cols=["id"])
        df2 = _make_df(rows=3, cols=["id"])
        comp._process(df1)
        xf_after_first = comp._streaming_xf
        comp._process(df2)
        xf_after_second = comp._streaming_xf
        assert xf_after_first is xf_after_second  # same context object
        comp.reset()
        # Total row count = 5
        content = (tmp_path / "out.xml").read_text()
        assert content.count("<rec>") == 5

    def test_reset_closes_contexts_inner_to_outer(self, tmp_path):
        """Test 18 (StreamingHook reset()): reset closes; subsequent reads valid XML."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=2, cols=["id"])
        comp._process(df)
        comp.reset()
        # After reset, state is cleared
        assert comp._streaming_write_started is False
        assert comp._streaming_xf is None
        assert comp._streaming_root_ctx is None
        # Output file should be valid, parseable XML
        content = (tmp_path / "out.xml").read_bytes()
        etree.fromstring(content)  # should not raise


# ------------------------------------------------------------------
# P-2 regression guard
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoBufferAndWrite:
    """Pitfall P-2 regression: implementation must not buffer the full tree.

    etree.tostring() and etree.SubElement() are the telltale signs of the
    buffer-then-write antipattern. Neither must appear in the source file.
    """

    def test_no_etree_tostring_in_source(self):
        """Test 19 (Pitfall P-2): no etree.tostring( in the implementation."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert not re.search(r"etree\.tostring\(", src)

    def test_no_etree_subelement_in_source(self):
        """Test 19b (Pitfall P-2): no etree.SubElement( in the implementation."""
        src = _strip_comments(_SOURCE_FILE.read_text())
        assert "etree.SubElement(" not in src


# ------------------------------------------------------------------
# TestSinkContract
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSinkContract:
    """S-5 sink contract: passthrough main; reject is None."""

    def test_main_is_input_identity(self, tmp_path):
        """Test 20 (Sink contract S-5): main is the exact input DataFrame passed in."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=3, cols=["id"])
        result = comp._process(df)
        comp.reset()
        assert result["main"] is df

    def test_reject_is_none(self, tmp_path):
        """Test 20b (Sink contract S-5): reject is always None."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
        })
        df = _make_df(rows=2, cols=["id"])
        result = comp._process(df)
        comp.reset()
        assert result["reject"] is None


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    """GlobalMap puts: {id}_FILE_NAME and {id}_NB_LINE after _process()."""

    def test_globalmap_puts_file_name_and_nb_line(self, tmp_path):
        """Test 21 (globalMap puts): both keys set after processing."""
        comp_id = "adv_out"
        comp = _make_component(
            {
                "filename": str(tmp_path / "out.xml"),
                "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            },
            comp_id=comp_id,
        )
        df = _make_df(rows=4, cols=["id"])
        comp._process(df)
        comp.reset()
        assert comp.global_map.get(f"{comp_id}_FILE_NAME") == str(tmp_path / "out.xml")
        assert comp.global_map.get(f"{comp_id}_NB_LINE") == 4


# ------------------------------------------------------------------
# D-E1 Conditional Warn-and-Ignore Tests
# ------------------------------------------------------------------

@pytest.mark.unit
class TestConditionalWarnDtdValid:
    """Test 26-27 (D-E1 DTD_VALID): logger.warning emitted when file_valid+dtd_valid=true."""

    def test_warn_emitted_when_file_valid_and_dtd_valid_true(self, tmp_path, caplog):
        """Test 26: file_valid=true AND dtd_valid=true -> WARNING emitted."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "file_valid": True,
            "dtd_valid": True,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert any("DTD" in r.getMessage() for r in caplog.records)

    def test_no_warn_when_file_valid_false(self, tmp_path, caplog):
        """Test 27: file_valid=False -> no DTD WARNING."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "file_valid": False,
            "dtd_valid": True,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert not any("DTD" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
class TestConditionalWarnXslValid:
    """Test 28-29 (D-E1 XSL_VALID): logger.warning emitted when file_valid+xsl_valid=true."""

    def test_warn_emitted_when_file_valid_and_xsl_valid_true(self, tmp_path, caplog):
        """Test 28: file_valid=true AND xsl_valid=true -> WARNING emitted."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "file_valid": True,
            "xsl_valid": True,
            "dtd_valid": False,  # isolate XSL path
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert any("XSL" in r.getMessage() for r in caplog.records)

    def test_no_warn_when_file_valid_false(self, tmp_path, caplog):
        """Test 29: file_valid=False -> no XSL WARNING."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "file_valid": False,
            "xsl_valid": True,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert not any("XSL" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
class TestConditionalWarnOutputAsXsd:
    """Test 30-31 (D-E1 OUTPUT_AS_XSD): logger.warning emitted when true."""

    def test_warn_emitted_when_output_as_xsd_true(self, tmp_path, caplog):
        """Test 30: output_as_xsd=True -> WARNING emitted."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "output_as_xsd": True,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert any("OUTPUT_AS_XSD" in r.getMessage() for r in caplog.records)

    def test_no_warn_when_output_as_xsd_false(self, tmp_path, caplog):
        """Test 31: output_as_xsd=False -> no WARNING."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "output_as_xsd": False,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert not any("OUTPUT_AS_XSD" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
class TestConditionalWarnAddDocumentAsNode:
    """Test 32-33 (D-E1 ADD_DOCUMENT_AS_NODE): logger.warning emitted when true."""

    def test_warn_emitted_when_add_document_as_node_true(self, tmp_path, caplog):
        """Test 32: add_document_as_node=True -> WARNING emitted."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "add_document_as_node": True,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert any("ADD_DOCUMENT_AS_NODE" in r.getMessage() for r in caplog.records)

    def test_no_warn_when_add_document_as_node_false(self, tmp_path, caplog):
        """Test 33: add_document_as_node=False -> no WARNING."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "add_document_as_node": False,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert not any("ADD_DOCUMENT_AS_NODE" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
class TestConditionalWarnAddUnmappedAttribute:
    """Test 34-35 (D-E1 ADD_UNMAPPED_ATTRIBUTE): logger.warning emitted when true."""

    def test_warn_emitted_when_add_unmapped_attribute_true(self, tmp_path, caplog):
        """Test 34: add_unmapped_attribute=True -> WARNING emitted."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "add_unmapped_attribute": True,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert any("ADD_UNMAPPED_ATTRIBUTE" in r.getMessage() for r in caplog.records)

    def test_no_warn_when_add_unmapped_attribute_false(self, tmp_path, caplog):
        """Test 35: add_unmapped_attribute=False -> no WARNING."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "add_unmapped_attribute": False,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert not any("ADD_UNMAPPED_ATTRIBUTE" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
class TestConditionalWarnMerge:
    """Test 36-37 (D-E1 MERGE): logger.warning emitted when merge=true."""

    def test_warn_emitted_when_merge_true(self, tmp_path, caplog):
        """Test 36: merge=True -> WARNING emitted."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "merge": True,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert any("MERGE" in r.getMessage() for r in caplog.records)

    def test_no_warn_when_merge_false(self, tmp_path, caplog):
        """Test 37: merge=False -> no MERGE WARNING."""
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "root": [{"path": "data", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "loop": [{"path": "rec", "column": "", "value": "", "attribute": "false", "order": "1"}],
            "merge": False,
        })
        df = _make_df(rows=1, cols=["id"])
        with caplog.at_level(logging.WARNING):
            comp._process(df)
        comp.reset()
        assert not any("MERGE" in r.getMessage() for r in caplog.records)
