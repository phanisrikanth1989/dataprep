"""Tests for tOracleOutput -> OracleOutput converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_output import (
    OracleOutputConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tOracleOutput_1",
        component_type="tOracleOutput",
        params=params or {},
        schema=schema or {},
        position={"x": 480, "y": 240},
    )


def _full_params():
    """Return a complete set of typical tOracleOutput parameters."""
    return {
        "HOST": '"db.example.com"',
        "PORT": '"1521"',
        "DBNAME": '"ORCL"',
        "USER": '"scott"',
        "PASSWORD": '"tiger"',
        "TABLE": '"employees"',
        "DATA_ACTION": '"INSERT"',
        "CONNECTION": '"tOracleConnection_1"',
        "USE_EXISTING_CONNECTION": "true",
    }


def _sample_schema():
    """Return a FLOW schema with typical columns."""
    return {
        "FLOW": [
            SchemaColumn(name="emp_id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="emp_name", type="id_String", nullable=True, length=200),
            SchemaColumn(
                name="hire_date",
                type="id_Date",
                date_pattern="yyyy-MM-dd",
            ),
        ]
    }


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestOracleOutputRegistration:
    def test_registered_in_registry(self):
        from src.converters.talend_to_v1.components.registry import REGISTRY
        assert REGISTRY.get("tOracleOutput") is OracleOutputConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestOracleOutputBasicConversion:
    def test_basic_config_extracted(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params=_full_params())
        result = OracleOutputConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "OracleOutput"
        assert comp["original_type"] == "tOracleOutput"
        assert comp["id"] == "tOracleOutput_1"
        assert comp["position"] == {"x": 480, "y": 240}

        cfg = comp["config"]
        assert cfg["HOST"] == "db.example.com"
        assert cfg["PORT"] == 1521
        assert cfg["DBNAME"] == "ORCL"
        assert cfg["USER"] == "scott"
        assert cfg["PASSWORD"] == "tiger"
        assert cfg["TABLE"] == "employees"
        assert cfg["DATA_ACTION"] == "INSERT"
        assert cfg["CONNECTION"] == "tOracleConnection_1"
        assert cfg["USE_EXISTING_CONNECTION"] is True

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params=_full_params())
        result = OracleOutputConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params=_full_params())
        result = OracleOutputConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position",
                         "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_no_warnings_when_all_required_present(self):
        """No warnings when HOST, DBNAME, and TABLE are provided."""
        node = _make_node(params=_full_params())
        result = OracleOutputConverter().convert(node, [], {})
        assert result.warnings == []
        assert result.needs_review == []


# --------------------------------------------------------------------- #
#  Defaults / missing parameters
# --------------------------------------------------------------------- #

class TestOracleOutputDefaults:
    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={})
        result = OracleOutputConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["HOST"] == ""
        assert cfg["PORT"] == 1521
        assert cfg["DBNAME"] == ""
        assert cfg["USER"] == ""
        assert cfg["PASSWORD"] == ""
        assert cfg["TABLE"] == ""
        assert cfg["DATA_ACTION"] == ""
        assert cfg["CONNECTION"] == ""
        assert cfg["USE_EXISTING_CONNECTION"] is False

    def test_use_existing_connection_false(self):
        """USE_EXISTING_CONNECTION='false' is correctly parsed as bool."""
        node = _make_node(params={"USE_EXISTING_CONNECTION": "false"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["USE_EXISTING_CONNECTION"] is False

    def test_port_as_raw_integer(self):
        """PORT param given as a raw integer is handled correctly."""
        params = _full_params()
        params["PORT"] = 1522
        node = _make_node(params=params)
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["PORT"] == 1522


# --------------------------------------------------------------------- #
#  Warnings / validation
# --------------------------------------------------------------------- #

class TestOracleOutputWarnings:
    def test_missing_host_produces_warning(self):
        """An empty HOST triggers a warning."""
        params = _full_params()
        del params["HOST"]
        node = _make_node(params=params)
        result = OracleOutputConverter().convert(node, [], {})
        assert any("HOST" in w for w in result.warnings)

    def test_missing_dbname_produces_warning(self):
        """An empty DBNAME triggers a warning."""
        params = _full_params()
        del params["DBNAME"]
        node = _make_node(params=params)
        result = OracleOutputConverter().convert(node, [], {})
        assert any("DBNAME" in w for w in result.warnings)

    def test_missing_table_produces_warning(self):
        """An empty TABLE triggers a warning."""
        params = _full_params()
        del params["TABLE"]
        node = _make_node(params=params)
        result = OracleOutputConverter().convert(node, [], {})
        assert any("TABLE" in w for w in result.warnings)

    def test_multiple_missing_fields_produce_all_warnings(self):
        """Multiple missing required fields produce multiple warnings."""
        node = _make_node(params={})
        result = OracleOutputConverter().convert(node, [], {})
        warning_text = " ".join(result.warnings)
        assert "HOST" in warning_text
        assert "DBNAME" in warning_text
        assert "TABLE" in warning_text


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestOracleOutputSchema:
    def test_input_schema_parsed(self):
        """Schema columns are parsed into the input schema for an output component."""
        node = _make_node(params=_full_params(), schema=_sample_schema())
        result = OracleOutputConverter().convert(node, [], {})
        input_schema = result.component["schema"]["input"]

        assert len(input_schema) == 3
        assert input_schema[0]["name"] == "emp_id"
        assert input_schema[0]["key"] is True
        assert input_schema[0]["nullable"] is False
        assert input_schema[1]["name"] == "emp_name"
        assert input_schema[1]["length"] == 200
        assert input_schema[2]["name"] == "hire_date"
        assert input_schema[2]["date_pattern"] == "%Y-%m-%d"

    def test_output_schema_always_empty(self):
        """OracleOutput is a sink — output schema must be empty."""
        node = _make_node(params=_full_params(), schema=_sample_schema())
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []

    def test_empty_schema(self):
        """When no schema is defined, both input and output are empty lists."""
        node = _make_node(params=_full_params(), schema={})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}
