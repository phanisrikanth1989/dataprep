"""Tests for tFileInputXML -> FileInputXML converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_xml import (
    FileInputXMLConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputXML_1",
        component_type="tFileInputXML",
        params=params or {},
        schema=schema or {},
        position={"x": 200, "y": 300},
    )


class TestFileInputXMLConverter:
    """Tests for FileInputXMLConverter."""

    def test_basic_config_all_params(self):
        """All 17 config params are extracted correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.xml"',
            "LOOP_QUERY": '"/root/record"',
            "LIMIT": '"1000"',
            "DIE_ON_ERROR": "true",
            "ENCODING": '"ISO-8859-1"',
            "IGNORE_NS": "true",
            "IGNORE_DTD": "true",
            "GENERATION_MODE": '"SAX"',
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
            "CHECK_DATE": "true",
            "USE_SEPARATOR": "true",
            "FIELD_SEPARATOR": '"|"',
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"xml_reader"',
            "MAPPING": [],
        })
        result = FileInputXMLConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == "/data/input.xml"
        assert "filename" not in cfg
        assert cfg["loop_query"] == "/root/record"
        assert cfg["limit"] == 1000
        assert cfg["die_on_error"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["ignore_ns"] is True
        assert cfg["ignore_dtd"] is True
        assert cfg["generation_mode"] == "SAX"
        assert cfg["advanced_separator"] is True
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","
        assert cfg["check_date"] is True
        assert cfg["use_separator"] is True
        assert cfg["field_separator"] == "|"
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "xml_reader"
        assert cfg["mapping"] == []

    def test_defaults_when_params_missing(self):
        """Missing params fall back to correct Talend defaults."""
        node = _make_node(params={
            "FILENAME": '"/data/file.xml"',
            "LOOP_QUERY": '"/root/item"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == "/data/file.xml"
        assert cfg["loop_query"] == "/root/item"
        assert cfg["limit"] is None
        assert cfg["die_on_error"] is False
        assert cfg["encoding"] == "ISO-8859-15"
        assert cfg["ignore_ns"] is False
        assert cfg["ignore_dtd"] is False
        assert cfg["generation_mode"] == "Dom4j"
        assert cfg["advanced_separator"] is False
        assert cfg["thousands_separator"] == ","
        assert cfg["decimal_separator"] == "."
        assert cfg["check_date"] is False
        assert cfg["use_separator"] is False
        assert cfg["field_separator"] == ","
        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""
        assert cfg["mapping"] == []

    def test_all_config_keys_present(self):
        """Exactly 17 config keys should be present."""
        node = _make_node(params={
            "FILENAME": '"/data/file.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected = {
            "filepath", "loop_query", "mapping", "limit", "die_on_error",
            "encoding", "ignore_ns", "ignore_dtd", "generation_mode",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "check_date", "use_separator", "field_separator",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected

    def test_filepath_key_not_filename(self):
        """Config key is 'filepath' (engine reads it), NOT 'filename'."""
        node = _make_node(params={
            "FILENAME": '"/data/test.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert "filepath" in cfg
        assert cfg["filepath"] == "/data/test.xml"
        assert "filename" not in cfg

    def test_mapping_produces_engine_format(self):
        """MAPPING outputs engine-expected raw triplet format with NODECHECK."""
        node = _make_node(params={
            "FILENAME": '"/data/orders.xml"',
            "LOOP_QUERY": '"/orders/order"',
            "MAPPING": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"order_id"'},
                {"elementRef": "QUERY", "value": '"@id"'},
                {"elementRef": "NODECHECK", "value": "false"},
                {"elementRef": "SCHEMA_COLUMN", "value": '"customer"'},
                {"elementRef": "QUERY", "value": '"customer/name"'},
                {"elementRef": "NODECHECK", "value": "true"},
                {"elementRef": "SCHEMA_COLUMN", "value": '"amount"'},
                {"elementRef": "QUERY", "value": '"total/@value"'},
                {"elementRef": "NODECHECK", "value": "false"},
            ],
        })
        result = FileInputXMLConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        # 3 columns × 3 entries each = 9 entries
        assert len(mapping) == 9

        # First triplet
        assert mapping[0] == {"column": "SCHEMA_COLUMN", "xpath": "order_id"}
        assert mapping[1] == {"column": "QUERY", "xpath": "@id"}
        assert mapping[2] == {"column": "NODECHECK", "xpath": "false"}

        # Second triplet
        assert mapping[3] == {"column": "SCHEMA_COLUMN", "xpath": "customer"}
        assert mapping[4] == {"column": "QUERY", "xpath": "customer/name"}
        assert mapping[5] == {"column": "NODECHECK", "xpath": "true"}

        # Third triplet
        assert mapping[6] == {"column": "SCHEMA_COLUMN", "xpath": "amount"}
        assert mapping[7] == {"column": "QUERY", "xpath": "total/@value"}
        assert mapping[8] == {"column": "NODECHECK", "xpath": "false"}

    def test_mapping_missing_nodecheck_defaults_false(self):
        """Missing NODECHECK defaults to 'false' (mandatory for engine i+=3)."""
        node = _make_node(params={
            "FILENAME": '"/data/test.xml"',
            "LOOP_QUERY": '"/root"',
            "MAPPING": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"col1"'},
                {"elementRef": "QUERY", "value": '"path1"'},
                # No NODECHECK entry
                {"elementRef": "SCHEMA_COLUMN", "value": '"col2"'},
                {"elementRef": "QUERY", "value": '"path2"'},
            ],
        })
        result = FileInputXMLConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 6  # 2 columns × 3 entries
        assert mapping[2] == {"column": "NODECHECK", "xpath": "false"}
        assert mapping[5] == {"column": "NODECHECK", "xpath": "false"}

    def test_limit_as_int_or_none(self):
        """LIMIT: non-empty → int, empty/missing → None."""
        # With value
        node1 = _make_node(params={
            "FILENAME": '"/data/file.xml"',
            "LOOP_QUERY": '"/root"',
            "LIMIT": '"50"',
        })
        result1 = FileInputXMLConverter().convert(node1, [], {})
        assert result1.component["config"]["limit"] == 50

        # Without value
        node2 = _make_node(params={
            "FILENAME": '"/data/file.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result2 = FileInputXMLConverter().convert(node2, [], {})
        assert result2.component["config"]["limit"] is None

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={"LOOP_QUERY": '"/root"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_empty_loop_query_produces_warning(self):
        """An empty LOOP_QUERY triggers a warning."""
        node = _make_node(params={"FILENAME": '"/data/test.xml"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("LOOP_QUERY" in w for w in result.warnings)

    def test_engine_gap_warning_generation_mode(self):
        """Non-Dom4j GENERATION_MODE triggers warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
            "GENERATION_MODE": '"SAX"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("GENERATION_MODE=SAX" in w for w in result.warnings)

    def test_engine_gap_warning_advanced_separator(self):
        """ADVANCED_SEPARATOR=true triggers warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
            "ADVANCED_SEPARATOR": "true",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("ADVANCED_SEPARATOR=true" in w for w in result.warnings)

    def test_engine_gap_warning_check_date(self):
        """CHECK_DATE=true triggers warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
            "CHECK_DATE": "true",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("CHECK_DATE=true" in w for w in result.warnings)

    def test_engine_gap_warning_use_separator(self):
        """USE_SEPARATOR=true triggers warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
            "USE_SEPARATOR": "true",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("USE_SEPARATOR=true" in w for w in result.warnings)

    def test_engine_gap_warning_ignore_ns(self):
        """IGNORE_NS=true triggers warning about engine not implementing namespace stripping."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
            "IGNORE_NS": "true",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("IGNORE_NS=true" in w for w in result.warnings)

    def test_engine_gap_warning_limit(self):
        """Non-None LIMIT triggers warning about engine not implementing limits."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
            "LIMIT": '"100"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("LIMIT=100" in w for w in result.warnings)

    def test_no_engine_warnings_on_defaults(self):
        """Defaults produce no engine-gap warnings."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert len(result.warnings) == 0

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={
                "FILENAME": '"test.xml"',
                "LOOP_QUERY": '"/root"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=100),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd HH:mm:ss",
                    ),
                ]
            },
        )
        result = FileInputXMLConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 100
        assert output_schema[2]["name"] == "created"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d %H:%M:%S"

    def test_input_schema_always_empty(self):
        """FileInputXML is a source — input schema must be empty."""
        node = _make_node(params={
            "FILENAME": '"x.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.xml"',
            "LOOP_QUERY": '"/root"',
            "DIE_ON_ERROR": "false",
            "IGNORE_NS": "1",
            "IGNORE_DTD": "true",
            "ADVANCED_SEPARATOR": "false",
            "CHECK_DATE": "1",
            "USE_SEPARATOR": "true",
            "TSTATCATCHER_STATS": "true",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["die_on_error"] is False
        assert cfg["ignore_ns"] is True
        assert cfg["ignore_dtd"] is True
        assert cfg["advanced_separator"] is False
        assert cfg["check_date"] is True
        assert cfg["use_separator"] is True
        assert cfg["tstatcatcher_stats"] is True

    def test_mapping_empty_list(self):
        """MAPPING as empty list produces empty mapping."""
        node = _make_node(params={
            "FILENAME": '"test.xml"',
            "LOOP_QUERY": '"/root"',
            "MAPPING": [],
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_non_list_ignored(self):
        """If MAPPING is not a list, mapping defaults to empty."""
        node = _make_node(params={
            "FILENAME": '"test.xml"',
            "LOOP_QUERY": '"/root"',
            "MAPPING": "not_a_list",
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={
            "FILENAME": '"f.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={
            "FILENAME": '"f.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputXML'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputXML")
        assert cls is FileInputXMLConverter
