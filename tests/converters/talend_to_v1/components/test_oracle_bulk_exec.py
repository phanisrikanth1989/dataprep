"""Tests for tOracleBulkExec -> OracleBulkExec converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_bulk_exec import (
    OracleBulkExecConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tOracleBulkExec_1",
        component_type="tOracleBulkExec",
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
    )


def _full_params():
    """Return a complete set of typical tOracleBulkExec parameters."""
    return {
        "HOST": '"db.example.com"',
        "PORT": '"1521"',
        "DBNAME": '"ORCL"',
        "USER": '"bulk_user"',
        "PASS": '"s3cret"',
        "DATA": '"/tmp/data.csv"',
        "TABLE": '"staging_table"',
        "CLT_FILE": '"/opt/oracle/sqlldr"',
        "DIE_ON_ERROR": "true",
    }


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestOracleBulkExecRegistration:
    def test_registered_in_registry(self):
        from src.converters.talend_to_v1.components.registry import REGISTRY
        assert REGISTRY.get("tOracleBulkExec") is OracleBulkExecConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestOracleBulkExecBasicConversion:
    def test_basic_config_extracted(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params=_full_params())
        result = OracleBulkExecConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "OracleBulkExec"
        assert comp["original_type"] == "tOracleBulkExec"
        assert comp["id"] == "tOracleBulkExec_1"
        assert comp["position"] == {"x": 320, "y": 160}

        cfg = comp["config"]
        assert cfg["HOST"] == "db.example.com"
        assert cfg["PORT"] == 1521
        assert cfg["DBNAME"] == "ORCL"
        assert cfg["USER"] == "bulk_user"
        assert cfg["PASS"] == "s3cret"
        assert cfg["DATA"] == "/tmp/data.csv"
        assert cfg["TABLE"] == "staging_table"
        assert cfg["CLT_FILE"] == "/opt/oracle/sqlldr"
        assert cfg["DIE_ON_ERROR"] is True

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params=_full_params())
        result = OracleBulkExecConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params=_full_params())
        result = OracleBulkExecConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position",
                         "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_no_warnings_when_all_required_present(self):
        """No warnings when HOST, DBNAME, and TABLE are provided."""
        node = _make_node(params=_full_params())
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.warnings == []
        assert result.needs_review == []


# --------------------------------------------------------------------- #
#  Defaults / missing parameters
# --------------------------------------------------------------------- #

class TestOracleBulkExecDefaults:
    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={})
        result = OracleBulkExecConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["HOST"] == ""
        assert cfg["PORT"] == 1521
        assert cfg["DBNAME"] == ""
        assert cfg["USER"] == ""
        assert cfg["PASS"] == ""
        assert cfg["DATA"] == ""
        assert cfg["TABLE"] == ""
        assert cfg["CLT_FILE"] == ""
        assert cfg["DIE_ON_ERROR"] is False

    def test_die_on_error_false(self):
        """DIE_ON_ERROR='false' is correctly parsed as bool False."""
        node = _make_node(params={"DIE_ON_ERROR": "false"})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["DIE_ON_ERROR"] is False

    def test_port_as_raw_integer(self):
        """PORT param given as a raw integer is handled correctly."""
        params = _full_params()
        params["PORT"] = 1522
        node = _make_node(params=params)
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["PORT"] == 1522


# --------------------------------------------------------------------- #
#  Warnings / validation
# --------------------------------------------------------------------- #

class TestOracleBulkExecWarnings:
    def test_missing_host_produces_warning(self):
        """An empty HOST triggers a warning."""
        params = _full_params()
        del params["HOST"]
        node = _make_node(params=params)
        result = OracleBulkExecConverter().convert(node, [], {})
        assert any("HOST" in w for w in result.warnings)

    def test_missing_dbname_produces_warning(self):
        """An empty DBNAME triggers a warning."""
        params = _full_params()
        del params["DBNAME"]
        node = _make_node(params=params)
        result = OracleBulkExecConverter().convert(node, [], {})
        assert any("DBNAME" in w for w in result.warnings)

    def test_missing_table_produces_warning(self):
        """An empty TABLE triggers a warning."""
        params = _full_params()
        del params["TABLE"]
        node = _make_node(params=params)
        result = OracleBulkExecConverter().convert(node, [], {})
        assert any("TABLE" in w for w in result.warnings)

    def test_multiple_missing_fields_produce_all_warnings(self):
        """Multiple missing required fields produce multiple warnings."""
        node = _make_node(params={})
        result = OracleBulkExecConverter().convert(node, [], {})
        warning_text = " ".join(result.warnings)
        assert "HOST" in warning_text
        assert "DBNAME" in warning_text
        assert "TABLE" in warning_text


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestOracleBulkExecSchema:
    def test_schema_always_empty(self):
        """OracleBulkExec is a utility — both input and output schemas are empty."""
        node = _make_node(params=_full_params())
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}

    def test_schema_empty_even_with_no_params(self):
        """Schema stays empty regardless of parameter presence."""
        node = _make_node(params={})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []
