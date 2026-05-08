"""Tests for FileOutputXML engine component (tFileOutputXML, Phase 12-06).

Per S-5 sink contract: main == input_data passthrough, reject == None.
Per S-6 streaming-write hook: state held across chunks, reset() closes.
Per D-D1: per-Talaxie-param positive + negative tests.
Per D-D4: no mocks of lxml.etree -- real I/O via tmp_path throughout.
Per Pitfall P-2 regression: explicit grep-based guard verifies no etree.tostring
or etree.SubElement appear in the implementation source.

Test classes:
  TestRegistry          -- @REGISTRY.register both names
  TestBaseComponent     -- subclass + lifecycle hooks
  TestValidateConfig    -- missing filename; Rule 12 deferred; bool type checks
  TestProcessMain       -- happy-path rows; sub-elements; row count
  TestMapping           -- AS_ATTRIBUTE pos; AS_ATTRIBUTE neg; mixed
  TestEncoding          -- ISO-8859-15 default; UTF-8 override
  TestRowTag            -- default 'row'; override 'record'
  TestRootTags          -- empty (no wrapper); ROOT_TAGS yields wrapper
  TestCreate            -- create=true overwrites; create=false existing file raises
  TestSplit             -- split=true with split_every; split=false single file
  TestFlushOnRow        -- flushonrow=true triggers flush after each row
  TestDeleteEmptyFile   -- empty + delete_empty_file=true -> no file; false -> empty file
  TestStreamingHook     -- first chunk opens; second reuses; reset closes
  TestNoBufferAndWrite  -- Pitfall P-2 regression grep guard
  TestSinkContract      -- main is input identity; reject is None
  TestStats             -- {id}_FILE_NAME and {id}_NB_LINE in globalMap
"""
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pandas as pd
import pytest
from lxml import etree

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_output_xml import FileOutputXML
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


_SOURCE_FILE = Path("src/v1/engine/components/file/file_output_xml.py")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config: Dict[str, Any], comp_id: str = "fo_xml_1") -> FileOutputXML:
    """Create a FileOutputXML with real GlobalMap and ContextManager.

    Also sets comp.config to match config so _process() can be called directly
    in unit tests without going through execute() lifecycle.
    """
    import copy
    comp = FileOutputXML(component_id=comp_id, config=config)
    comp.global_map = GlobalMap()
    comp.context_manager = ContextManager()
    # Pre-populate comp.config so direct _process() calls work in unit tests
    comp.config = copy.deepcopy(config)
    return comp


def _strip_comments(source: str) -> str:
    """Remove lines that begin with # (Python comment lines) from source."""
    return "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("#")
    )


def _make_df(rows=5, cols=None) -> pd.DataFrame:
    """Generate a simple DataFrame for testing."""
    if cols is None:
        cols = ["id", "name", "value"]
    data = {}
    for col in cols:
        data[col] = [f"{col}_{i}" for i in range(rows)]
    return pd.DataFrame(data)


# ------------------------------------------------------------------
# TestRegistry
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    """Both registration names resolve to FileOutputXML."""

    def test_registered_under_pascal_name(self):
        assert REGISTRY.get("FileOutputXML") is FileOutputXML

    def test_registered_under_talend_name(self):
        assert REGISTRY.get("tFileOutputXML") is FileOutputXML


# ------------------------------------------------------------------
# TestBaseComponent
# ------------------------------------------------------------------

@pytest.mark.unit
class TestBaseComponent:
    """FileOutputXML is a proper BaseComponent subclass."""

    def test_is_base_component_subclass(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(FileOutputXML, BaseComponent)

    def test_reset_method_exists(self):
        comp = _make_component({"filename": "/tmp/x.xml"})
        assert callable(comp.reset)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    """_validate_config raises on missing filename; defers content checks."""

    def test_missing_filename_raises(self):
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_empty_filename_raises(self):
        comp = _make_component({"filename": ""})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_filename_with_context_var_passes(self):
        """Rule 12: context variable reference deferred to _process."""
        comp = _make_component({"filename": "context.outputPath"})
        comp._validate_config()  # must not raise

    def test_invalid_bool_type_raises(self):
        """Non-bool, non-str, non-int value for bool key raises ConfigurationError."""
        comp = _make_component({"filename": "/tmp/x.xml", "split": [1, 2]})
        with pytest.raises(ConfigurationError, match="split"):
            comp._validate_config()

    def test_valid_bool_string_passes(self):
        comp = _make_component({"filename": "/tmp/x.xml", "split": "true"})
        comp._validate_config()  # must not raise

    def test_valid_bool_int_passes(self):
        comp = _make_component({"filename": "/tmp/x.xml", "flushonrow": 0})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    """Happy-path processing tests."""

    def test_5_row_output_has_5_row_elements(self, tmp_path):
        df = _make_df(rows=5, cols=["id", "name"])
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert len(tree.findall(".//row")) == 5

    def test_columns_emitted_as_sub_elements(self, tmp_path):
        df = pd.DataFrame({"id": ["1"], "name": ["Alice"]})
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        row = tree.find("row")
        assert row.find("id") is not None
        assert row.find("id").text == "1"
        assert row.find("name").text == "Alice"

    def test_row_count_matches_input(self, tmp_path):
        df = _make_df(rows=7)
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert len(tree.findall(".//row")) == 7


# ------------------------------------------------------------------
# TestMapping
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMapping:
    """AS_ATTRIBUTE mapping tests."""

    def test_as_attribute_true_emits_xml_attribute(self, tmp_path):
        df = pd.DataFrame({"id": ["42"], "name": ["Alice"]})
        mapping = [{"column": "id", "as_attribute": True}]
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "mapping": mapping,
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        row = tree.find("row")
        # 'id' should be an attribute
        assert row.get("id") == "42"
        # 'name' sub-element not in mapping, so it should appear only if mapping excludes it
        # (mapping list only has 'id', so 'name' won't be emitted)
        assert row.find("id") is None  # attribute, not sub-element

    def test_as_attribute_false_emits_sub_element(self, tmp_path):
        df = pd.DataFrame({"id": ["99"]})
        mapping = [{"column": "id", "as_attribute": False}]
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "mapping": mapping,
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        row = tree.find("row")
        assert row.find("id") is not None
        assert row.get("id") is None  # not an attribute

    def test_mixed_mapping(self, tmp_path):
        df = pd.DataFrame({"id": ["1"], "name": ["Bob"]})
        mapping = [
            {"column": "id", "as_attribute": True},
            {"column": "name", "as_attribute": False},
        ]
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "mapping": mapping,
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        row = tree.find("row")
        assert row.get("id") == "1"         # attribute
        assert row.find("name").text == "Bob"  # sub-element


# ------------------------------------------------------------------
# TestEncoding
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEncoding:
    """Encoding defaults and override."""

    def test_default_encoding_iso(self, tmp_path):
        df = pd.DataFrame({"a": ["1"]})
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        comp._process(df)
        comp.reset()
        raw = (tmp_path / "out.xml").read_bytes()
        assert b"ISO-8859-15" in raw

    def test_utf8_encoding_override(self, tmp_path):
        df = pd.DataFrame({"a": ["1"]})
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "encoding": "UTF-8",
        })
        comp._process(df)
        comp.reset()
        raw = (tmp_path / "out.xml").read_bytes()
        assert b"UTF-8" in raw


# ------------------------------------------------------------------
# TestRowTag
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRowTag:
    """ROW_TAG param controls the per-row element name."""

    def test_default_row_tag(self, tmp_path):
        df = pd.DataFrame({"a": ["1"]})
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert tree.find("row") is not None

    def test_custom_row_tag(self, tmp_path):
        df = pd.DataFrame({"a": ["1"]})
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "record"})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert tree.find("record") is not None
        assert tree.find("row") is None


# ------------------------------------------------------------------
# TestRootTags
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRootTags:
    """ROOT_TAGS wraps output in a named outer element."""

    def test_no_root_tags_uses_default_root(self, tmp_path):
        df = pd.DataFrame({"a": ["1"]})
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        # Without root_tags, component uses implicit 'root' wrapper for valid XML
        tree = etree.fromstring(content)
        assert tree.tag == "root"
        assert tree.find("row") is not None

    def test_root_tags_produces_outer_wrapper(self, tmp_path):
        df = pd.DataFrame({"a": ["1"]})
        root_tags = [{"name": "wrapper"}]
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "root_tags": root_tags,
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert tree.tag == "wrapper"
        assert tree.find("row") is not None


# ------------------------------------------------------------------
# TestCreate
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCreate:
    """CREATE flag controls overwrite vs. error on existing file."""

    def test_create_true_overwrites_existing(self, tmp_path):
        outfile = tmp_path / "out.xml"
        outfile.write_bytes(b"old content")
        df = pd.DataFrame({"a": ["1"]})
        comp = _make_component({
            "filename": str(outfile),
            "row_tag": "row",
            "create": True,
        })
        comp._process(df)
        comp.reset()
        content = outfile.read_bytes()
        assert b"old content" not in content
        assert b"<row" in content

    def test_create_false_existing_file_raises(self, tmp_path):
        outfile = tmp_path / "out.xml"
        outfile.write_bytes(b"existing")
        comp = _make_component({
            "filename": str(outfile),
            "row_tag": "row",
            "create": False,
        })
        with pytest.raises(FileOperationError, match="create=False"):
            comp._process(pd.DataFrame({"a": ["1"]}))


# ------------------------------------------------------------------
# TestSplit
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSplit:
    """SPLIT mode produces multiple numbered output files."""

    def test_split_true_creates_multiple_files(self, tmp_path):
        df = _make_df(rows=5, cols=["a"])
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "split": True,
            "split_every": "2",
        })
        comp._process(df)
        # 5 rows / 2 per file = 3 files: out0.xml, out1.xml, out2.xml
        files = sorted(tmp_path.glob("out*.xml"))
        assert len(files) == 3, f"Expected 3 files, got {len(files)}: {files}"

    def test_split_false_single_file(self, tmp_path):
        df = _make_df(rows=5, cols=["a"])
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "split": False,
        })
        comp._process(df)
        comp.reset()
        assert (tmp_path / "out.xml").exists()
        files = list(tmp_path.glob("*.xml"))
        assert len(files) == 1


# ------------------------------------------------------------------
# TestFlushOnRow
# ------------------------------------------------------------------

@pytest.mark.unit
class TestFlushOnRow:
    """FLUSHONROW triggers flush after each row."""

    def test_flushonrow_true_writes_and_flushes(self, tmp_path):
        df = pd.DataFrame({"a": ["1", "2", "3"]})
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "flushonrow": True,
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert len(tree.findall(".//row")) == 3


# ------------------------------------------------------------------
# TestDeleteEmptyFile
# ------------------------------------------------------------------

@pytest.mark.unit
class TestDeleteEmptyFile:
    """DELETE_EMPTY_FILE removes the output file when no rows written."""

    def test_delete_empty_file_true_no_file(self, tmp_path):
        outfile = tmp_path / "out.xml"
        df = pd.DataFrame({"a": []})
        comp = _make_component({
            "filename": str(outfile),
            "row_tag": "row",
            "delete_empty_file": True,
        })
        comp._process(df)
        assert not outfile.exists()

    def test_delete_empty_file_false_file_not_deleted(self, tmp_path):
        outfile = tmp_path / "out.xml"
        outfile.write_bytes(b"existing")
        df = pd.DataFrame({"a": []})
        comp = _make_component({
            "filename": str(outfile),
            "row_tag": "row",
            "delete_empty_file": False,
        })
        comp._process(df)
        # File should still exist (we don't delete it)
        assert outfile.exists()


# ------------------------------------------------------------------
# TestStreamingHook
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStreamingHook:
    """S-6 streaming-hook: first chunk opens, second reuses, reset closes."""

    def test_first_chunk_sets_write_started(self, tmp_path):
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        df = pd.DataFrame({"a": [1, 2]})
        comp._process(df)
        assert comp._streaming_write_started is True

    def test_second_chunk_reuses_context(self, tmp_path):
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "root_tags": [{"name": "root"}],
        })
        df1 = pd.DataFrame({"a": [1, 2]})
        df2 = pd.DataFrame({"a": [3, 4]})
        comp._process(df1)
        comp._process(df2)
        assert comp._streaming_total_written == 4
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        # Only one XML declaration
        assert content.count(b"<?xml") == 1
        # All 4 rows present
        tree = etree.fromstring(content)
        assert len(tree.findall(".//row")) == 4

    def test_reset_clears_streaming_state(self, tmp_path):
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        df = pd.DataFrame({"a": [1]})
        comp._process(df)
        comp.reset()
        assert comp._streaming_xmlfile_ctx is None
        assert comp._streaming_xmlfile_root_ctx is None
        assert comp._streaming_write_started is False
        assert comp._streaming_xf is None
        assert comp._streaming_total_written == 0

    def test_reset_allows_fresh_write(self, tmp_path):
        """After reset(), a second _process call behaves like first chunk."""
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        df1 = pd.DataFrame({"a": [1]})
        df2 = pd.DataFrame({"a": [2]})
        comp._process(df1)
        comp.reset()
        # Second write starts fresh (overwrites)
        comp._process(df2)
        assert comp._streaming_write_started is True
        assert comp._streaming_total_written == 1
        comp.reset()


# ------------------------------------------------------------------
# TestNoBufferAndWrite
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoBufferAndWrite:
    """Pitfall P-2 regression: NEVER use etree.tostring or etree.SubElement."""

    def test_no_etree_tostring_in_source(self):
        """etree.tostring (buffer-and-write smell) must not appear in implementation."""
        src = _strip_comments(_SOURCE_FILE.read_text(encoding="ascii"))
        assert not re.search(r"etree\.tostring\(", src), (
            "Pitfall P-2 regression: etree.tostring reappeared (buffer-and-write pattern)"
        )

    def test_no_etree_subelement_in_source(self):
        """etree.SubElement (buffer-and-write smell) must not appear in implementation."""
        src = _strip_comments(_SOURCE_FILE.read_text(encoding="ascii"))
        assert "etree.SubElement(" not in src, (
            "Pitfall P-2 regression: etree.SubElement reappeared (buffer-and-write pattern)"
        )


# ------------------------------------------------------------------
# TestSinkContract
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSinkContract:
    """S-5: main is passthrough identity, reject is None."""

    def test_main_is_input_identity(self, tmp_path):
        df_in = pd.DataFrame({"a": [1, 2, 3]})
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        result = comp._process(df_in)
        comp.reset()
        assert result["main"] is df_in  # object identity passthrough (S-5)

    def test_reject_is_none(self, tmp_path):
        df_in = pd.DataFrame({"a": [1]})
        comp = _make_component({"filename": str(tmp_path / "out.xml"), "row_tag": "row"})
        result = comp._process(df_in)
        comp.reset()
        assert result["reject"] is None


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    """GlobalMap puts {id}_FILE_NAME and {id}_NB_LINE."""

    def test_globalmap_file_name_and_nb_line(self, tmp_path):
        outfile = tmp_path / "out.xml"
        df = _make_df(rows=5, cols=["a"])
        comp = _make_component({"filename": str(outfile), "row_tag": "row"})
        comp._process(df)
        comp.reset()
        assert comp.global_map.get("fo_xml_1_FILE_NAME") == str(outfile)
        assert comp.global_map.get("fo_xml_1_NB_LINE") == 5

    def test_globalmap_accumulates_across_chunks(self, tmp_path):
        outfile = tmp_path / "out.xml"
        comp = _make_component({
            "filename": str(outfile),
            "row_tag": "row",
            "root_tags": [{"name": "root"}],
        })
        comp._process(_make_df(rows=3, cols=["a"]))
        comp._process(_make_df(rows=4, cols=["a"]))
        comp.reset()
        assert comp.global_map.get("fo_xml_1_NB_LINE") == 7


# ------------------------------------------------------------------
# TestInputIsDocument
# ------------------------------------------------------------------

@pytest.mark.unit
class TestInputIsDocument:
    """INPUT_IS_DOCUMENT mode emits per-row XML doc strings."""

    def test_input_is_document_passthrough(self, tmp_path):
        doc1 = "<item><id>1</id></item>"
        doc2 = "<item><id>2</id></item>"
        df = pd.DataFrame({"doc": [doc1, doc2]})
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "input_is_document": True,
            "document_col": "doc",
            "root_tags": [{"name": "root"}],
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        items = tree.findall(".//item")
        assert len(items) == 2
        assert items[0].find("id").text == "1"

    def test_input_is_document_false_uses_row_tag(self, tmp_path):
        df = pd.DataFrame({"a": ["1"]})
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "myrow",
            "input_is_document": False,
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        assert b"<myrow" in content

    def test_trim_strips_whitespace_in_doc_mode(self, tmp_path):
        doc = "  <item><id>1</id></item>  "
        df = pd.DataFrame({"doc": [doc]})
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "input_is_document": True,
            "document_col": "doc",
            "trim": True,
            "root_tags": [{"name": "root"}],
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert tree.find(".//item") is not None


# ------------------------------------------------------------------
# TestParamRootTagsMultiple
# ------------------------------------------------------------------

@pytest.mark.unit
class TestParamRootTagsMultiple:
    """ROOT_TAGS with a name key wraps rows in the named element."""

    def test_root_tags_name_key(self, tmp_path):
        df = pd.DataFrame({"a": ["1", "2"]})
        comp = _make_component({
            "filename": str(tmp_path / "out.xml"),
            "row_tag": "row",
            "root_tags": [{"name": "data"}],
        })
        comp._process(df)
        comp.reset()
        content = (tmp_path / "out.xml").read_bytes()
        tree = etree.fromstring(content)
        assert tree.tag == "data"
        assert len(tree.findall("row")) == 2
