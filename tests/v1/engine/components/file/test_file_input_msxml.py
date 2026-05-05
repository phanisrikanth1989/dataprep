"""Tests for FileInputMSXML engine component (tFileInputMSXML).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessMain     -- happy-path XML file reading
    TestProcessReject   -- missing file, bad XPath
    TestStats           -- NB_LINE / NB_LINE_OK tracking
"""
import os
import tempfile
import textwrap

import pytest
import pandas as pd

from src.v1.engine.components.file.file_input_msxml import FileInputMSXML
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_SAMPLE_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <people>
      <person>
        <name>Alice</name>
        <age>30</age>
      </person>
      <person>
        <name>Bob</name>
        <age>25</age>
      </person>
    </people>
""")


def _write_xml(path: str, content: str, encoding: str = "utf-8") -> None:
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = FileInputMSXML(
        component_id="tFIMSXML_1",
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
        assert REGISTRY.get("FileInputMSXML") is FileInputMSXML

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFileInputMSXML") is FileInputMSXML

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(FileInputMSXML, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_filename_raises(self):
        comp = _make_component(config={"root_loop_query": "//person"})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_missing_root_loop_query_raises(self):
        comp = _make_component(config={"filename": "/some/file.xml"})
        with pytest.raises(ConfigurationError, match="root_loop_query"):
            comp._validate_config()

    def test_die_on_error_not_bool_raises(self):
        comp = _make_component(config={
            "filename": "/f.xml",
            "root_loop_query": "//p",
            "die_on_error": "true",
        })
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={"filename": "/f.xml", "root_loop_query": "//p"})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessMain
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessMain:
    def test_basic_extraction(self, tmp_path):
        xml_file = str(tmp_path / "people.xml")
        _write_xml(xml_file, _SAMPLE_XML)
        comp = _make_component(config={
            "filename": xml_file,
            "root_loop_query": "//person",
            "encoding": "UTF-8",
            "trim_all": True,
        })
        _set_schema(comp, ["name", "age"])
        result = comp.execute(None)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["name"] == "Alice"
        assert result["main"].iloc[1]["age"] == "25"

    def test_trim_all_strips_whitespace(self, tmp_path):
        xml_content = "<r><item><col> hello </col></item></r>"
        xml_file = str(tmp_path / "t.xml")
        _write_xml(xml_file, xml_content)
        comp = _make_component(config={
            "filename": xml_file,
            "root_loop_query": "//item",
            "trim_all": True,
        })
        _set_schema(comp, ["col"])
        result = comp.execute(None)
        assert result["main"].iloc[0]["col"] == "hello"

    def test_columns_in_schema_order(self, tmp_path):
        xml_file = str(tmp_path / "people.xml")
        _write_xml(xml_file, _SAMPLE_XML)
        comp = _make_component(config={
            "filename": xml_file,
            "root_loop_query": "//person",
        })
        _set_schema(comp, ["name", "age"])
        result = comp.execute(None)
        assert list(result["main"].columns) == ["name", "age"]


# ------------------------------------------------------------------
# TestProcessReject
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_missing_file_raises(self):
        comp = _make_component(config={
            "filename": "/no/such/file.xml",
            "root_loop_query": "//item",
        })
        with pytest.raises((ComponentExecutionError, FileOperationError)):
            comp.execute(None)

    def test_empty_filename_raises_on_process(self):
        comp = _make_component(config={"filename": "", "root_loop_query": "//item"})
        with pytest.raises((ComponentExecutionError, FileOperationError, ConfigurationError)):
            comp.execute(None)


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_reflect_rows(self, tmp_path):
        xml_file = str(tmp_path / "people.xml")
        _write_xml(xml_file, _SAMPLE_XML)
        gm = GlobalMap()
        comp = _make_component(config={
            "filename": xml_file,
            "root_loop_query": "//person",
        }, global_map=gm)
        _set_schema(comp, ["name", "age"])
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 2
