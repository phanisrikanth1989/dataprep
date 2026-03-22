"""Tests for the OracleSPConverter (tOracleSP -> OracleSP)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_sp import OracleSPConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="oracle_sp_1",
               component_type="tOracleSP"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 400},
        raw_xml=ET.Element("node"),
    )


class TestOracleSPConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tOracleSP") is OracleSPConverter


class TestOracleSPConverterBasic:
    def test_basic_conversion(self):
        node = _make_node(params={
            "HOST": '"db-host.example.com"',
            "PORT": '"1521"',
            "DBNAME": '"ORCL"',
            "USER": '"scott"',
            "PASSWORD": '"tiger"',
            "PROCEDURE": '"pkg_etl.run_load"',
            "DIE_ON_ERROR": "true",
        })
        result = OracleSPConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "oracle_sp_1"
        assert comp["type"] == "OracleSP"
        assert comp["original_type"] == "tOracleSP"
        assert comp["position"] == {"x": 300, "y": 400}
        assert comp["config"]["HOST"] == "db-host.example.com"
        assert comp["config"]["PORT"] == 1521
        assert comp["config"]["DBNAME"] == "ORCL"
        assert comp["config"]["USER"] == "scott"
        assert comp["config"]["PASSWORD"] == "tiger"
        assert comp["config"]["PROCEDURE"] == "pkg_etl.run_load"
        assert comp["config"]["DIE_ON_ERROR"] is True
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_die_on_error_false(self):
        node = _make_node(params={
            "HOST": '"localhost"',
            "PORT": '"1521"',
            "DBNAME": '"testdb"',
            "USER": '"admin"',
            "PASSWORD": '"pass"',
            "PROCEDURE": '"my_proc"',
            "DIE_ON_ERROR": "false",
        })
        result = OracleSPConverter().convert(node, [], {})

        assert result.component["config"]["DIE_ON_ERROR"] is False

    def test_port_as_integer(self):
        node = _make_node(params={
            "HOST": '"host"',
            "PORT": '"1522"',
            "DBNAME": '"db"',
            "USER": '"u"',
            "PASSWORD": '"p"',
            "PROCEDURE": '"proc"',
        })
        result = OracleSPConverter().convert(node, [], {})

        assert result.component["config"]["PORT"] == 1522
        assert isinstance(result.component["config"]["PORT"], int)


class TestOracleSPConverterDefaults:
    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = OracleSPConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["HOST"] == ""
        assert cfg["PORT"] == 1521
        assert cfg["DBNAME"] == ""
        assert cfg["USER"] == ""
        assert cfg["PASSWORD"] == ""
        assert cfg["PROCEDURE"] == ""
        assert cfg["DIE_ON_ERROR"] is False

    def test_port_default_when_missing(self):
        node = _make_node(params={
            "HOST": '"host"',
            "DBNAME": '"db"',
            "USER": '"u"',
            "PASSWORD": '"p"',
            "PROCEDURE": '"proc"',
        })
        result = OracleSPConverter().convert(node, [], {})

        assert result.component["config"]["PORT"] == 1521


class TestOracleSPConverterWarnings:
    def test_no_warnings_when_all_params_provided(self):
        node = _make_node(params={
            "HOST": '"host"',
            "PORT": '"1521"',
            "DBNAME": '"db"',
            "USER": '"user"',
            "PASSWORD": '"pass"',
            "PROCEDURE": '"proc"',
            "DIE_ON_ERROR": "true",
        })
        result = OracleSPConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_warnings_for_missing_required_params(self):
        node = _make_node(params={})
        result = OracleSPConverter().convert(node, [], {})

        warning_text = " ".join(result.warnings)
        assert "HOST" in warning_text
        assert "DBNAME" in warning_text
        assert "USER" in warning_text
        assert "PROCEDURE" in warning_text
        assert len(result.warnings) == 4

    def test_warning_only_for_host(self):
        node = _make_node(params={
            "DBNAME": '"db"',
            "USER": '"u"',
            "PROCEDURE": '"proc"',
        })
        result = OracleSPConverter().convert(node, [], {})

        assert len(result.warnings) == 1
        assert "HOST" in result.warnings[0]


class TestOracleSPConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """OracleSP is a utility component -- no data flow schema."""
        node = _make_node(params={
            "HOST": '"h"',
            "DBNAME": '"d"',
            "USER": '"u"',
            "PROCEDURE": '"p"',
        })
        result = OracleSPConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestOracleSPConverterEdgeCases:
    def test_port_non_numeric_falls_back_to_default(self):
        node = _make_node(params={
            "HOST": '"host"',
            "PORT": '"abc"',
            "DBNAME": '"db"',
            "USER": '"u"',
            "PASSWORD": '"p"',
            "PROCEDURE": '"proc"',
        })
        result = OracleSPConverter().convert(node, [], {})

        assert result.component["config"]["PORT"] == 1521

    def test_custom_component_id(self):
        node = _make_node(
            params={
                "HOST": '"h"',
                "DBNAME": '"d"',
                "USER": '"u"',
                "PROCEDURE": '"p"',
            },
            component_id="custom_sp_99",
        )
        result = OracleSPConverter().convert(node, [], {})

        assert result.component["id"] == "custom_sp_99"

    def test_boolean_true_as_python_bool(self):
        node = _make_node(params={
            "HOST": '"h"',
            "DBNAME": '"d"',
            "USER": '"u"',
            "PROCEDURE": '"p"',
            "DIE_ON_ERROR": True,
        })
        result = OracleSPConverter().convert(node, [], {})

        assert result.component["config"]["DIE_ON_ERROR"] is True
