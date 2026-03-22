"""Tests for tFixedFlowInput -> FixedFlowInputComponent converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.fixed_flow_input import (
    FixedFlowInputConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFixedFlowInput_1",
        component_type="tFixedFlowInput",
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


def _schema_columns():
    """Return a small reusable set of FLOW schema columns."""
    return [
        SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
        SchemaColumn(name="name", type="id_String"),
        SchemaColumn(name="city", type="id_String"),
    ]


class TestFixedFlowInputConverter:
    """Tests for FixedFlowInputConverter."""

    # ------------------------------------------------------------------
    # 1. Basic / structural tests
    # ------------------------------------------------------------------

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"NB_ROWS": "1"})
        result = FixedFlowInputConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_basic_metadata(self):
        """Component id, type, original_type, position are set correctly."""
        node = _make_node(params={"NB_ROWS": "3"})
        result = FixedFlowInputConverter().convert(node, [], {})
        comp = result.component
        assert comp["id"] == "tFixedFlowInput_1"
        assert comp["type"] == "FixedFlowInputComponent"
        assert comp["original_type"] == "tFixedFlowInput"
        assert comp["position"] == {"x": 100, "y": 200}

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_lookup(self):
        """The converter is registered under 'tFixedFlowInput'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFixedFlowInput")
        assert cls is FixedFlowInputConverter

    # ------------------------------------------------------------------
    # 2. Default / missing-param tests
    # ------------------------------------------------------------------

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node()
        result = FixedFlowInputConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["nb_rows"] == 1
        assert cfg["connection_format"] == "row"
        assert cfg["use_singlemode"] is True
        assert cfg["use_intable"] is False
        assert cfg["use_inlinecontent"] is False
        assert cfg["row_separator"] == "\n"
        assert cfg["field_separator"] == ";"
        assert cfg["inline_content"] == ""
        assert cfg["rows"] == [{}]  # 1 row, no schema cols => empty dict
        assert cfg["values_config"] == {}

    # ------------------------------------------------------------------
    # 3. Single mode tests
    # ------------------------------------------------------------------

    def test_single_mode_values_parsing(self):
        """In single mode, VALUES table is parsed into values_config and rows."""
        node = _make_node(
            params={
                "NB_ROWS": "2",
                "USE_SINGLEMODE": "true",
                "VALUES": [
                    {"elementRef": "SCHEMA_COLUMN", "value": "id"},
                    {"elementRef": "VALUE", "value": "1"},
                    {"elementRef": "SCHEMA_COLUMN", "value": "name"},
                    {"elementRef": "VALUE", "value": "Alice"},
                    {"elementRef": "SCHEMA_COLUMN", "value": "city"},
                    {"elementRef": "VALUE", "value": "Paris"},
                ],
            },
            schema={
                "FLOW": _schema_columns(),
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["values_config"] == {"id": "1", "name": "Alice", "city": "Paris"}
        assert len(cfg["rows"]) == 2
        # Each row should carry the same values
        for row in cfg["rows"]:
            assert row["id"] == "1"
            assert row["name"] == "Alice"
            assert row["city"] == "Paris"

    def test_single_mode_missing_column_in_values(self):
        """Columns not present in VALUES get None in each row."""
        node = _make_node(
            params={
                "NB_ROWS": "1",
                "USE_SINGLEMODE": "true",
                "VALUES": [
                    {"elementRef": "SCHEMA_COLUMN", "value": "id"},
                    {"elementRef": "VALUE", "value": "42"},
                ],
            },
            schema={
                "FLOW": _schema_columns(),
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        rows = result.component["config"]["rows"]

        assert len(rows) == 1
        assert rows[0]["id"] == "42"
        assert rows[0]["name"] is None
        assert rows[0]["city"] is None

    def test_single_mode_context_variable(self):
        """Context variables in VALUES are wrapped as ${context.var}."""
        node = _make_node(
            params={
                "NB_ROWS": "1",
                "USE_SINGLEMODE": "true",
                "VALUES": [
                    {"elementRef": "SCHEMA_COLUMN", "value": "name"},
                    {"elementRef": "VALUE", "value": "context.username"},
                ],
            },
            schema={
                "FLOW": [SchemaColumn(name="name", type="id_String")],
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["values_config"]["name"] == "${context.username}"
        assert cfg["rows"][0]["name"] == "${context.username}"

    def test_single_mode_java_expression(self):
        """Java expressions in VALUES are marked with {{java}} prefix."""
        node = _make_node(
            params={
                "NB_ROWS": "1",
                "USE_SINGLEMODE": "true",
                "VALUES": [
                    {"elementRef": "SCHEMA_COLUMN", "value": "id"},
                    {"elementRef": "VALUE", "value": "Integer.parseInt(row1.key)"},
                ],
            },
            schema={
                "FLOW": [SchemaColumn(name="id", type="id_Integer")],
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        val = result.component["config"]["values_config"]["id"]
        # ExpressionConverter.mark_java_expression should detect the Java call
        assert val.startswith("{{java}}")

    # ------------------------------------------------------------------
    # 4. Inline content mode tests
    # ------------------------------------------------------------------

    def test_inline_content_mode(self):
        """Inline content mode splits content by row and field separators."""
        node = _make_node(
            params={
                "NB_ROWS": "2",
                "USE_SINGLEMODE": "false",
                "USE_INLINECONTENT": "true",
                "INLINECONTENT": '"1;Alice;Paris\n2;Bob;London"',
                "ROWSEPARATOR": '"\n"',
                "FIELDSEPARATOR": '";"',
            },
            schema={
                "FLOW": _schema_columns(),
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        rows = result.component["config"]["rows"]

        assert len(rows) == 2
        assert rows[0] == {"id": "1", "name": "Alice", "city": "Paris"}
        assert rows[1] == {"id": "2", "name": "Bob", "city": "London"}

    def test_inline_content_fewer_fields_than_columns(self):
        """Columns with no matching field value get None."""
        node = _make_node(
            params={
                "NB_ROWS": "1",
                "USE_SINGLEMODE": "false",
                "USE_INLINECONTENT": "true",
                "INLINECONTENT": '"1;Alice"',
                "ROWSEPARATOR": '"\n"',
                "FIELDSEPARATOR": '";"',
            },
            schema={
                "FLOW": _schema_columns(),
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        rows = result.component["config"]["rows"]

        assert len(rows) == 1
        assert rows[0]["id"] == "1"
        assert rows[0]["name"] == "Alice"
        assert rows[0]["city"] is None

    def test_inline_content_more_rows_requested_than_available(self):
        """When nb_rows exceeds content rows, only available rows are generated."""
        node = _make_node(
            params={
                "NB_ROWS": "5",
                "USE_SINGLEMODE": "false",
                "USE_INLINECONTENT": "true",
                "INLINECONTENT": '"a;b"',
                "ROWSEPARATOR": '"\n"',
                "FIELDSEPARATOR": '";"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="col1", type="id_String"),
                    SchemaColumn(name="col2", type="id_String"),
                ],
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        rows = result.component["config"]["rows"]
        # Only 1 content row despite nb_rows=5
        assert len(rows) == 1
        assert rows[0] == {"col1": "a", "col2": "b"}

    # ------------------------------------------------------------------
    # 5. Default mode (intable) test
    # ------------------------------------------------------------------

    def test_intable_mode_generates_null_rows(self):
        """In USE_INTABLE mode (with no INTABLE data), rows have None values."""
        node = _make_node(
            params={
                "NB_ROWS": "2",
                "USE_SINGLEMODE": "false",
                "USE_INTABLE": "true",
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="x", type="id_String"),
                    SchemaColumn(name="y", type="id_Integer"),
                ],
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        rows = result.component["config"]["rows"]

        assert len(rows) == 2
        for row in rows:
            assert row == {"x": None, "y": None}

    # ------------------------------------------------------------------
    # 6. Schema output test
    # ------------------------------------------------------------------

    def test_schema_output(self):
        """Output schema is populated from FLOW metadata."""
        node = _make_node(
            params={"NB_ROWS": "1"},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=100),
                ],
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 2
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 100
        # Input schema should be empty — this is a source component
        assert result.component["schema"]["input"] == []

    # ------------------------------------------------------------------
    # 7. Quoted value stripping in VALUES
    # ------------------------------------------------------------------

    def test_values_quoted_strings_stripped(self):
        """Surrounding quotes in VALUES entries are stripped."""
        node = _make_node(
            params={
                "NB_ROWS": "1",
                "USE_SINGLEMODE": "true",
                "VALUES": [
                    {"elementRef": "SCHEMA_COLUMN", "value": '"name"'},
                    {"elementRef": "VALUE", "value": '"hello"'},
                ],
            },
            schema={
                "FLOW": [SchemaColumn(name="name", type="id_String")],
            },
        )
        result = FixedFlowInputConverter().convert(node, [], {})
        assert result.component["config"]["values_config"]["name"] == "hello"
