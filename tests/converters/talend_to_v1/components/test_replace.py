"""Tests for tReplace -> Replace converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.replace import (
    ReplaceConverter,
)


def _make_node(params=None, schema=None, component_type="tReplace"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


def _subst_entries(
    input_column,
    search_pattern,
    replace_string,
    whole_word="false",
    case_sensitive="false",
    use_glob="false",
    comment="",
):
    """Helper to build the 7 flat elementRef/value dicts for one substitution."""
    return [
        {"elementRef": "INPUT_COLUMN", "value": input_column},
        {"elementRef": "SEARCH_PATTERN", "value": search_pattern},
        {"elementRef": "REPLACE_STRING", "value": replace_string},
        {"elementRef": "WHOLE_WORD", "value": whole_word},
        {"elementRef": "CASE_SENSITIVE", "value": case_sensitive},
        {"elementRef": "USE_GLOB", "value": use_glob},
        {"elementRef": "COMMENT", "value": comment},
    ]


class TestReplaceConverter:
    """Tests for ReplaceConverter."""

    def test_basic_config(self):
        """Config params and a single substitution are extracted correctly."""
        node = _make_node(params={
            "SIMPLE_MODE": "true",
            "ADVANCED_MODE": "false",
            "STRICT_MATCH": "true",
            "CONNECTION_FORMAT": "row",
            "SUBSTITUTIONS": _subst_entries(
                "name", '"foo"', '"bar"', "false", "true", "false", "swap foo",
            ),
        })
        result = ReplaceConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "Replace"
        assert comp["original_type"] == "tReplace"
        assert comp["id"] == "tReplace_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["simple_mode"] is True
        assert cfg["advanced_mode"] is False
        assert cfg["strict_match"] is True
        assert cfg["connection_format"] == "row"

        assert len(cfg["substitutions"]) == 1
        sub = cfg["substitutions"][0]
        assert sub["input_column"] == "name"
        assert sub["search_pattern"] == "foo"
        assert sub["replace_string"] == "bar"
        assert sub["whole_word"] is False
        assert sub["case_sensitive"] is True
        assert sub["use_glob"] is False
        assert sub["comment"] == "swap foo"

    def test_multiple_substitutions(self):
        """Multiple substitution rows are parsed and columns are deduped."""
        entries = (
            _subst_entries("city", '"NYC"', '"New York"')
            + _subst_entries("city", '"LA"', '"Los Angeles"')
            + _subst_entries("state", '"CA"', '"California"')
        )
        node = _make_node(params={"SUBSTITUTIONS": entries})
        result = ReplaceConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert len(cfg["substitutions"]) == 3
        assert cfg["substitutions"][0]["input_column"] == "city"
        assert cfg["substitutions"][1]["search_pattern"] == "LA"
        assert cfg["substitutions"][2]["replace_string"] == "California"

        # Unique columns, sorted
        assert cfg["columns"] == ["city", "state"]

    def test_html_entity_quote_stripping(self):
        """&quot; wrappers are stripped from SEARCH_PATTERN and REPLACE_STRING."""
        node = _make_node(params={
            "SUBSTITUTIONS": _subst_entries(
                "desc",
                "&quot;old value&quot;",
                "&quot;new value&quot;",
            ),
        })
        result = ReplaceConverter().convert(node, [], {})
        sub = result.component["config"]["substitutions"][0]

        assert sub["search_pattern"] == "old value"
        assert sub["replace_string"] == "new value"

    def test_defaults_when_params_missing(self):
        """Missing params fall back to defaults and a warning is emitted."""
        node = _make_node(params={})
        result = ReplaceConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["simple_mode"] is True
        assert cfg["advanced_mode"] is False
        assert cfg["strict_match"] is True
        assert cfg["connection_format"] == "row"
        assert cfg["substitutions"] == []
        assert cfg["columns"] == []

        assert any("no effect" in w.lower() for w in result.warnings)

    def test_boolean_flags_in_substitution(self):
        """whole_word, case_sensitive, use_glob are parsed as booleans."""
        node = _make_node(params={
            "SUBSTITUTIONS": _subst_entries(
                "col_a", '"x"', '"y"', "true", "true", "true", "all flags on",
            ),
        })
        result = ReplaceConverter().convert(node, [], {})
        sub = result.component["config"]["substitutions"][0]

        assert sub["whole_word"] is True
        assert sub["case_sensitive"] is True
        assert sub["use_glob"] is True

    def test_schema_passthrough(self):
        """Replace passes through schema: input and output match."""
        node = _make_node(
            params={
                "SUBSTITUTIONS": _subst_entries("id", '"a"', '"b"'),
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=100),
                ],
            },
        )
        result = ReplaceConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "name"
        assert schema["output"][1]["length"] == 100

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = ReplaceConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = ReplaceConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_registration(self):
        """The converter is registered under 'tReplace'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tReplace")
        assert cls is ReplaceConverter

    def test_incomplete_group_ignored(self):
        """A partial substitution group (fewer than 7 entries) is dropped."""
        partial = [
            {"elementRef": "INPUT_COLUMN", "value": "col"},
            {"elementRef": "SEARCH_PATTERN", "value": '"x"'},
            # only 2 entries -- incomplete group
        ]
        node = _make_node(params={"SUBSTITUTIONS": partial})
        result = ReplaceConverter().convert(node, [], {})

        assert result.component["config"]["substitutions"] == []
        assert any("no effect" in w.lower() for w in result.warnings)

    def test_advanced_mode_settings(self):
        """Advanced mode flags are captured correctly."""
        node = _make_node(params={
            "SIMPLE_MODE": "false",
            "ADVANCED_MODE": "true",
            "STRICT_MATCH": "false",
            "CONNECTION_FORMAT": "table",
            "SUBSTITUTIONS": _subst_entries("col", '"a"', '"b"'),
        })
        result = ReplaceConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["simple_mode"] is False
        assert cfg["advanced_mode"] is True
        assert cfg["strict_match"] is False
        assert cfg["connection_format"] == "table"
