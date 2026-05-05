"""Tests for FileInputProperties engine component (tFileInputProperties).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestPropertiesFormat -- Java .properties file parsing
    TestIniFormat        -- INI file parsing (by section, all sections)
    TestStats            -- NB_LINE / NB_LINE_OK tracking
"""
import os
import textwrap

import pytest
import pandas as pd

from src.v1.engine.components.file.file_input_properties import FileInputProperties
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_PROPERTIES_CONTENT = textwrap.dedent("""\
    # Java properties
    host=localhost
    port=5432
    name=mydb
""")

_INI_CONTENT = textwrap.dedent("""\
    [database]
    host = dbserver
    port = 3306

    [cache]
    host = cacheserver
    port = 6379
""")


def _write_file(path: str, content: str, encoding: str = "utf-8") -> None:
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = FileInputProperties(
        component_id="tFIP_1",
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
        assert REGISTRY.get("FileInputProperties") is FileInputProperties

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFileInputProperties") is FileInputProperties

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(FileInputProperties, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_filename_raises(self):
        comp = _make_component(config={})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={"filename": "/some/file.properties"})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestPropertiesFormat
# ------------------------------------------------------------------

@pytest.mark.unit
class TestPropertiesFormat:
    def test_reads_key_value_pairs(self, tmp_path):
        props_file = str(tmp_path / "db.properties")
        _write_file(props_file, _PROPERTIES_CONTENT)
        comp = _make_component(config={
            "filename": props_file,
            "file_format": "PROPERTIES_FORMAT",
        })
        _set_schema(comp, ["host", "port", "name"])
        result = comp.execute(None)
        assert len(result["main"]) == 1
        row = result["main"].iloc[0]
        assert row["host"] == "localhost"
        assert row["port"] == "5432"
        assert row["name"] == "mydb"

    def test_comments_are_ignored(self, tmp_path):
        content = "# comment\nkey=value\n! also comment"
        props_file = str(tmp_path / "test.properties")
        _write_file(props_file, content)
        comp = _make_component(config={"filename": props_file, "file_format": "PROPERTIES_FORMAT"})
        _set_schema(comp, ["key"])
        result = comp.execute(None)
        assert result["main"].iloc[0]["key"] == "value"

    def test_missing_column_returns_none(self, tmp_path):
        props_file = str(tmp_path / "db.properties")
        _write_file(props_file, "host=localhost\n")
        comp = _make_component(config={"filename": props_file, "file_format": "PROPERTIES_FORMAT"})
        _set_schema(comp, ["host", "missing_key"])
        result = comp.execute(None)
        assert result["main"].iloc[0]["missing_key"] is None

    def test_missing_file_raises(self):
        comp = _make_component(config={"filename": "/no/such.properties"})
        with pytest.raises((ComponentExecutionError, FileOperationError)):
            comp.execute(None)


# ------------------------------------------------------------------
# TestIniFormat
# ------------------------------------------------------------------

@pytest.mark.unit
class TestIniFormat:
    def test_retrive_by_section(self, tmp_path):
        ini_file = str(tmp_path / "config.ini")
        _write_file(ini_file, _INI_CONTENT)
        comp = _make_component(config={
            "filename": ini_file,
            "file_format": "INI_FORMAT",
            "retrive_mode": "RETRIVE_BY_SECTION",
            "section_name": "database",
        })
        _set_schema(comp, ["host", "port"])
        result = comp.execute(None)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["host"] == "dbserver"

    def test_retrive_all_returns_multiple_rows(self, tmp_path):
        ini_file = str(tmp_path / "config.ini")
        _write_file(ini_file, _INI_CONTENT)
        comp = _make_component(config={
            "filename": ini_file,
            "file_format": "INI_FORMAT",
            "retrive_mode": "RETRIVE_ALL",
        })
        _set_schema(comp, ["host"])
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_missing_section_returns_empty_row(self, tmp_path):
        ini_file = str(tmp_path / "config.ini")
        _write_file(ini_file, _INI_CONTENT)
        comp = _make_component(config={
            "filename": ini_file,
            "file_format": "INI_FORMAT",
            "retrive_mode": "RETRIVE_BY_SECTION",
            "section_name": "nosuchsection",
        })
        _set_schema(comp, ["host"])
        result = comp.execute(None)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["host"] is None


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_reflect_rows(self, tmp_path):
        props_file = str(tmp_path / "db.properties")
        _write_file(props_file, "host=localhost\n")
        gm = GlobalMap()
        comp = _make_component(config={"filename": props_file}, global_map=gm)
        _set_schema(comp, ["host"])
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 1
