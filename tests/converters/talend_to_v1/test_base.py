import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentConverter,
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)


def _make_node(params=None, schema=None, component_id="test_1",
               component_type="tTest"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 0, "y": 0},
        raw_xml=ET.Element("node"),
    )


class TestGetStr:
    def test_strips_quotes(self):
        node = _make_node(params={"NAME": '"hello"'})
        assert ComponentConverter._get_str(node, "NAME") == "hello"

    def test_no_quotes(self):
        node = _make_node(params={"NAME": "hello"})
        assert ComponentConverter._get_str(node, "NAME") == "hello"

    def test_default(self):
        node = _make_node()
        assert ComponentConverter._get_str(node, "MISSING", "default") == "default"

    def test_empty_string(self):
        node = _make_node(params={"NAME": ""})
        assert ComponentConverter._get_str(node, "NAME") == ""

    def test_single_char_quotes(self):
        node = _make_node(params={"NAME": '"'})
        assert ComponentConverter._get_str(node, "NAME") == '"'


class TestGetBool:
    def test_true_string(self):
        node = _make_node(params={"FLAG": "true"})
        assert ComponentConverter._get_bool(node, "FLAG") is True

    def test_false_string(self):
        node = _make_node(params={"FLAG": "false"})
        assert ComponentConverter._get_bool(node, "FLAG") is False

    def test_bool_value(self):
        node = _make_node(params={"FLAG": True})
        assert ComponentConverter._get_bool(node, "FLAG") is True

    def test_default(self):
        node = _make_node()
        assert ComponentConverter._get_bool(node, "MISSING") is False

    def test_default_true(self):
        node = _make_node()
        assert ComponentConverter._get_bool(node, "MISSING", True) is True

    def test_string_one(self):
        node = _make_node(params={"FLAG": "1"})
        assert ComponentConverter._get_bool(node, "FLAG") is True

    def test_string_zero(self):
        node = _make_node(params={"FLAG": "0"})
        assert ComponentConverter._get_bool(node, "FLAG") is False


class TestGetInt:
    def test_string_number(self):
        node = _make_node(params={"COUNT": "42"})
        assert ComponentConverter._get_int(node, "COUNT") == 42

    def test_int_value(self):
        node = _make_node(params={"COUNT": 42})
        assert ComponentConverter._get_int(node, "COUNT") == 42

    def test_quoted_number(self):
        node = _make_node(params={"COUNT": '"42"'})
        assert ComponentConverter._get_int(node, "COUNT") == 42

    def test_non_numeric(self):
        node = _make_node(params={"COUNT": "abc"})
        assert ComponentConverter._get_int(node, "COUNT", 0) == 0

    def test_default(self):
        node = _make_node()
        assert ComponentConverter._get_int(node, "MISSING", 5) == 5

    def test_negative(self):
        node = _make_node(params={"COUNT": "-3"})
        assert ComponentConverter._get_int(node, "COUNT") == -3


class TestGetParam:
    def test_returns_value(self):
        node = _make_node(params={"KEY": [1, 2, 3]})
        assert ComponentConverter._get_param(node, "KEY") == [1, 2, 3]

    def test_returns_default(self):
        node = _make_node()
        assert ComponentConverter._get_param(node, "MISSING", "fallback") == "fallback"


class TestParseSchema:
    def test_flow_schema(self):
        node = _make_node(schema={
            "FLOW": [
                SchemaColumn(name="id", type="id_Integer", key=True),
                SchemaColumn(name="name", type="id_String"),
            ]
        })
        result = ComponentConverter._parse_schema(node, "FLOW")
        assert len(result) == 2
        assert result[0]["name"] == "id"
        assert result[0]["type"] == "int"
        assert result[0]["key"] is True
        assert result[1]["name"] == "name"
        assert result[1]["type"] == "str"

    def test_empty_schema(self):
        node = _make_node()
        result = ComponentConverter._parse_schema(node, "FLOW")
        assert result == []

    def test_includes_length_precision(self):
        node = _make_node(schema={
            "FLOW": [
                SchemaColumn(name="amount", type="id_BigDecimal", length=19, precision=2),
            ]
        })
        result = ComponentConverter._parse_schema(node)
        assert result[0]["length"] == 19
        assert result[0]["precision"] == 2

    def test_excludes_negative_length(self):
        node = _make_node(schema={
            "FLOW": [SchemaColumn(name="x", type="id_String")]
        })
        result = ComponentConverter._parse_schema(node)
        assert "length" not in result[0]

    def test_date_pattern_conversion(self):
        node = _make_node(schema={
            "FLOW": [
                SchemaColumn(name="dt", type="id_Date", date_pattern="yyyy-MM-dd"),
            ]
        })
        result = ComponentConverter._parse_schema(node)
        assert result[0]["date_pattern"] == "%Y-%m-%d"


class TestDatePattern:
    def test_basic_date(self):
        assert ComponentConverter._convert_date_pattern("yyyy-MM-dd") == "%Y-%m-%d"

    def test_datetime(self):
        assert ComponentConverter._convert_date_pattern("dd/MM/yyyy HH:mm:ss") == "%d/%m/%Y %H:%M:%S"

    def test_short_year(self):
        assert ComponentConverter._convert_date_pattern("yy-MM-dd") == "%y-%m-%d"

    def test_12hour(self):
        assert ComponentConverter._convert_date_pattern("hh:mm a") == "%I:%M %p"

    def test_milliseconds(self):
        assert ComponentConverter._convert_date_pattern("HH:mm:ss.SSS") == "%H:%M:%S.%f"

    def test_empty(self):
        assert ComponentConverter._convert_date_pattern("") == ""


class TestBuildComponentDict:
    def test_structure(self):
        node = _make_node(component_id="comp_1", component_type="tFoo")
        result = ComponentConverter._build_component_dict(
            node=node,
            type_name="Foo",
            config={"key": "val"},
            schema={"input": [], "output": []},
        )
        assert result["id"] == "comp_1"
        assert result["type"] == "Foo"
        assert result["original_type"] == "tFoo"
        assert result["position"] == {"x": 0, "y": 0}
        assert result["config"] == {"key": "val"}
        assert result["schema"] == {"input": [], "output": []}
        assert result["inputs"] == []
        assert result["outputs"] == []


class TestConnectionHelpers:
    def test_incoming(self):
        node = _make_node(component_id="B")
        conns = [
            TalendConnection(name="r1", source="A", target="B", connector_type="FLOW"),
            TalendConnection(name="r2", source="B", target="C", connector_type="FLOW"),
        ]
        result = ComponentConverter._incoming(node, conns)
        assert len(result) == 1
        assert result[0].source == "A"

    def test_outgoing(self):
        node = _make_node(component_id="B")
        conns = [
            TalendConnection(name="r1", source="A", target="B", connector_type="FLOW"),
            TalendConnection(name="r2", source="B", target="C", connector_type="FLOW"),
        ]
        result = ComponentConverter._outgoing(node, conns)
        assert len(result) == 1
        assert result[0].target == "C"

    def test_no_connections(self):
        node = _make_node(component_id="X")
        assert ComponentConverter._incoming(node, []) == []
        assert ComponentConverter._outgoing(node, []) == []
