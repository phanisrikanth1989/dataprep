"""Tests for tOracleInput -> OracleInput converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_input import (
    OracleInputConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tOracleInput_1",
        component_type="tOracleInput",
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
    )


class TestOracleInputConverter:
    """Tests for OracleInputConverter."""

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "HOST": '"db.example.com"',
            "PORT": '"1521"',
            "DBNAME": '"ORCL"',
            "USER": '"scott"',
            "PASSWORD": '"tiger"',
            "QUERY": '"SELECT * FROM employees"',
        })
        result = OracleInputConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "OracleInput"
        assert comp["original_type"] == "tOracleInput"
        assert comp["id"] == "tOracleInput_1"
        assert comp["position"] == {"x": 320, "y": 160}

        cfg = comp["config"]
        assert cfg["host"] == "db.example.com"
        assert cfg["port"] == 1521
        assert cfg["dbname"] == "ORCL"
        assert cfg["user"] == "scott"
        assert cfg["password"] == "tiger"
        assert cfg["query"] == "SELECT * FROM employees"

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={})
        result = OracleInputConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["host"] == ""
        assert cfg["port"] == 1521
        assert cfg["dbname"] == ""
        assert cfg["user"] == ""
        assert cfg["password"] == ""
        assert cfg["query"] == ""

    def test_missing_host_produces_warning(self):
        """An empty HOST triggers a warning."""
        node = _make_node(params={
            "PORT": '"1521"',
            "DBNAME": '"ORCL"',
            "QUERY": '"SELECT 1 FROM dual"',
        })
        result = OracleInputConverter().convert(node, [], {})
        assert any("HOST" in w for w in result.warnings)

    def test_missing_dbname_produces_warning(self):
        """An empty DBNAME triggers a warning."""
        node = _make_node(params={
            "HOST": '"localhost"',
            "QUERY": '"SELECT 1 FROM dual"',
        })
        result = OracleInputConverter().convert(node, [], {})
        assert any("DBNAME" in w for w in result.warnings)

    def test_missing_query_produces_warning(self):
        """An empty QUERY triggers a warning."""
        node = _make_node(params={
            "HOST": '"localhost"',
            "DBNAME": '"ORCL"',
        })
        result = OracleInputConverter().convert(node, [], {})
        assert any("QUERY" in w for w in result.warnings)

    def test_no_warnings_when_all_required_present(self):
        """No warnings when all mandatory fields are provided."""
        node = _make_node(params={
            "HOST": '"localhost"',
            "PORT": '"1521"',
            "DBNAME": '"ORCL"',
            "USER": '"admin"',
            "PASSWORD": '"secret"',
            "QUERY": '"SELECT id FROM t"',
        })
        result = OracleInputConverter().convert(node, [], {})
        assert result.warnings == []

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={
                "HOST": '"localhost"',
                "DBNAME": '"ORCL"',
                "QUERY": '"SELECT * FROM emp"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="emp_id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="emp_name", type="id_String", key=False, length=200),
                    SchemaColumn(
                        name="hire_date",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd",
                    ),
                ]
            },
        )
        result = OracleInputConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "emp_id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "emp_name"
        assert output_schema[1]["length"] == 200
        assert output_schema[2]["name"] == "hire_date"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d"

    def test_input_schema_always_empty(self):
        """OracleInput is a source — input schema must be empty."""
        node = _make_node(params={
            "HOST": '"localhost"',
            "DBNAME": '"ORCL"',
            "QUERY": '"SELECT 1 FROM dual"',
        })
        result = OracleInputConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_port_as_raw_integer(self):
        """PORT param given as a raw integer is handled correctly."""
        node = _make_node(params={
            "HOST": '"localhost"',
            "PORT": 1522,
            "DBNAME": '"ORCL"',
            "QUERY": '"SELECT 1 FROM dual"',
        })
        result = OracleInputConverter().convert(node, [], {})
        assert result.component["config"]["port"] == 1522

    def test_port_default_when_missing(self):
        """PORT defaults to 1521 when not supplied."""
        node = _make_node(params={
            "HOST": '"localhost"',
            "DBNAME": '"ORCL"',
            "QUERY": '"SELECT 1 FROM dual"',
        })
        result = OracleInputConverter().convert(node, [], {})
        assert result.component["config"]["port"] == 1521

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'})
        result = OracleInputConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'})
        result = OracleInputConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_registry_lookup(self):
        """The converter is registered under 'tOracleInput'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tOracleInput")
        assert cls is OracleInputConverter
