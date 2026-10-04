"""Tests for the ContextLoad utility component."""
import logging
from datetime import date

import pytest

from src.v2.components.utility.context_load import ContextLoad


# ======================================================================
# Delimited format
# ======================================================================


class TestContextLoadDelimited:
    def test_basic_properties_file(self, tmp_path):
        """Read a simple key=value properties file."""
        props = tmp_path / "config.properties"
        props.write_text("host=localhost\nport=3306\ndb=mydb\n")

        comp = ContextLoad("cl", {"path": str(props)})
        result = comp.apply({})

        assert "__context_updates__" in result
        updates = result["__context_updates__"]
        assert updates["host"] == "localhost"
        assert updates["port"] == 3306  # auto-detected as int
        assert updates["db"] == "mydb"

    def test_custom_delimiter(self, tmp_path):
        """Support custom delimiters like semicolons."""
        f = tmp_path / "config.csv"
        f.write_text("host;localhost\nport;3306\n")

        comp = ContextLoad("cl", {"path": str(f), "delimiter": ";"})
        result = comp.apply({})

        assert result["__context_updates__"]["host"] == "localhost"
        assert result["__context_updates__"]["port"] == 3306

    def test_comment_lines_skipped(self, tmp_path):
        """Lines starting with comment_char are skipped."""
        f = tmp_path / "config.properties"
        f.write_text(
            "# This is a comment\nhost=localhost\n# Another comment\nport=3306\n"
        )

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        updates = result["__context_updates__"]
        assert len(updates) == 2
        assert "# This is a comment" not in updates

    def test_empty_lines_skipped(self, tmp_path):
        """Empty lines are silently skipped."""
        f = tmp_path / "config.properties"
        f.write_text("host=localhost\n\n\nport=3306\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert len(result["__context_updates__"]) == 2

    def test_value_with_delimiter(self, tmp_path):
        """Values containing the delimiter should work (split on first occurrence)."""
        f = tmp_path / "config.properties"
        f.write_text("url=jdbc:mysql://host:3306/db\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert (
            result["__context_updates__"]["url"] == "jdbc:mysql://host:3306/db"
        )

    def test_encoding(self, tmp_path):
        """Support custom encoding."""
        f = tmp_path / "config.properties"
        f.write_text("name=caf\u00e9", encoding="latin-1")

        comp = ContextLoad("cl", {"path": str(f), "encoding": "latin-1"})
        result = comp.apply({})

        assert result["__context_updates__"]["name"] == "caf\u00e9"

    def test_stats_returned(self, tmp_path):
        """Stats should include nb_loaded count."""
        f = tmp_path / "config.properties"
        f.write_text("a=1\nb=2\nc=3\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert result["__context_load_stats__"]["nb_loaded"] == 3

    def test_whitespace_trimmed(self, tmp_path):
        """Keys and values should be trimmed of whitespace."""
        f = tmp_path / "config.properties"
        f.write_text("  host  =  localhost  \n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert result["__context_updates__"]["host"] == "localhost"


# ======================================================================
# JSON format
# ======================================================================


class TestContextLoadJSON:
    def test_basic_json(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"host": "localhost", "port": 3306, "debug": true}')

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        updates = result["__context_updates__"]
        assert updates["host"] == "localhost"
        assert updates["port"] == 3306  # native int preserved
        assert updates["debug"] is True  # native bool preserved

    def test_json_format_explicit(self, tmp_path):
        """Explicit format overrides extension-based detection."""
        f = tmp_path / "config.txt"
        f.write_text('{"host": "localhost"}')

        comp = ContextLoad("cl", {"path": str(f), "format": "json"})
        result = comp.apply({})

        assert result["__context_updates__"]["host"] == "localhost"

    def test_json_non_flat_raises(self, tmp_path):
        """Non-dict JSON should raise an error."""
        f = tmp_path / "config.json"
        f.write_text("[1, 2, 3]")

        comp = ContextLoad("cl", {"path": str(f)})
        with pytest.raises(ValueError, match="flat object"):
            comp.apply({})

    def test_json_nested_raises(self, tmp_path):
        """Nested dict values in JSON should raise an error."""
        f = tmp_path / "config.json"
        f.write_text('{"a": {"nested": true}}')

        comp = ContextLoad("cl", {"path": str(f)})
        with pytest.raises(ValueError, match="flat"):
            comp.apply({})


# ======================================================================
# YAML format
# ======================================================================


class TestContextLoadYAML:
    def test_basic_yaml(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("host: localhost\nport: 3306\ndebug: true\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        updates = result["__context_updates__"]
        assert updates["host"] == "localhost"
        assert updates["port"] == 3306
        assert updates["debug"] is True

    def test_yml_extension(self, tmp_path):
        """Both .yaml and .yml should be auto-detected."""
        f = tmp_path / "config.yml"
        f.write_text("key: value\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert result["__context_updates__"]["key"] == "value"

    def test_yaml_non_flat_raises(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("- item1\n- item2\n")

        comp = ContextLoad("cl", {"path": str(f)})
        with pytest.raises(ValueError, match="flat mapping"):
            comp.apply({})

    def test_yaml_nested_raises(self, tmp_path):
        """Nested mapping values in YAML should raise an error."""
        f = tmp_path / "config.yaml"
        f.write_text("a:\n  nested: value\n")

        comp = ContextLoad("cl", {"path": str(f)})
        with pytest.raises(ValueError, match="flat"):
            comp.apply({})


# ======================================================================
# Format auto-detection
# ======================================================================


class TestFormatAutoDetection:
    def test_json_extension(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"k": "v"}')
        comp = ContextLoad("cl", {"path": str(f)})
        assert comp._detect_format() == "json"

    def test_yaml_extension(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("k: v")
        comp = ContextLoad("cl", {"path": str(f)})
        assert comp._detect_format() == "yaml"

    def test_yml_extension(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("k: v")
        comp = ContextLoad("cl", {"path": str(f)})
        assert comp._detect_format() == "yaml"

    def test_properties_extension(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("k=v")
        comp = ContextLoad("cl", {"path": str(f)})
        assert comp._detect_format() == "delimited"

    def test_explicit_format_overrides(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text("k=v")
        comp = ContextLoad("cl", {"path": str(f), "format": "delimited"})
        assert comp._detect_format() == "delimited"


# ======================================================================
# Type casting
# ======================================================================


class TestContextLoadTypeCasting:
    def test_existing_context_var_auto_cast(self, tmp_path):
        """Values should be cast to match existing context variable types."""
        f = tmp_path / "config.properties"
        f.write_text("port=3306\nrate=0.08\n")

        comp = ContextLoad(
            "cl",
            {"path": str(f)},
            context={"port": 5432, "rate": 0.1},
        )
        result = comp.apply({})

        assert result["__context_updates__"]["port"] == 3306
        assert isinstance(result["__context_updates__"]["port"], int)
        assert result["__context_updates__"]["rate"] == 0.08
        assert isinstance(result["__context_updates__"]["rate"], float)

    def test_explicit_types_config(self, tmp_path):
        """Explicit types config should cast new variables."""
        f = tmp_path / "config.properties"
        f.write_text("batch_size=1000\nstart_date=2026-03-01\n")

        comp = ContextLoad(
            "cl",
            {
                "path": str(f),
                "types": {
                    "batch_size": {"type": "int"},
                    "start_date": {"type": "date", "format": "%Y-%m-%d"},
                },
            },
        )
        result = comp.apply({})

        assert result["__context_updates__"]["batch_size"] == 1000
        assert result["__context_updates__"]["start_date"] == date(2026, 3, 1)

    def test_auto_detect_int(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("count=42\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert result["__context_updates__"]["count"] == 42
        assert isinstance(result["__context_updates__"]["count"], int)

    def test_auto_detect_float(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("rate=3.14\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert result["__context_updates__"]["rate"] == 3.14
        assert isinstance(result["__context_updates__"]["rate"], float)

    def test_auto_detect_bool(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("enabled=true\ndisabled=false\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert result["__context_updates__"]["enabled"] is True
        assert result["__context_updates__"]["disabled"] is False

    def test_auto_detect_string_fallback(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("name=hello world\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert result["__context_updates__"]["name"] == "hello world"
        assert isinstance(result["__context_updates__"]["name"], str)

    def test_existing_bool_context_cast(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("debug=true\n")

        comp = ContextLoad(
            "cl", {"path": str(f)}, context={"debug": False}
        )
        result = comp.apply({})

        assert result["__context_updates__"]["debug"] is True

    def test_existing_date_context_cast(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("start=2026-06-15\n")

        comp = ContextLoad(
            "cl",
            {"path": str(f)},
            context={"start": date(2026, 1, 1)},
        )
        result = comp.apply({})

        assert result["__context_updates__"]["start"] == date(2026, 6, 15)


# ======================================================================
# Error handling
# ======================================================================


class TestContextLoadErrorHandling:
    def test_file_not_found_die_on_error(self, tmp_path):
        comp = ContextLoad(
            "cl", {"path": str(tmp_path / "missing.properties")}
        )
        with pytest.raises(FileNotFoundError):
            comp.apply({})

    def test_file_not_found_no_die(self, tmp_path):
        comp = ContextLoad(
            "cl",
            {
                "path": str(tmp_path / "missing.properties"),
                "die_on_error": False,
            },
        )
        result = comp.apply({})
        assert result["__context_updates__"] == {}
        assert result["__context_load_stats__"]["nb_loaded"] == 0

    def test_type_cast_error_die_on_error(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("port=not_a_number\n")

        comp = ContextLoad(
            "cl",
            {
                "path": str(f),
                "types": {"port": {"type": "int"}},
            },
        )
        with pytest.raises(ValueError, match="Failed to cast"):
            comp.apply({})

    def test_type_cast_error_no_die(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("port=not_a_number\ngood=hello\n")

        comp = ContextLoad(
            "cl",
            {
                "path": str(f),
                "die_on_error": False,
                "types": {"port": {"type": "int"}},
            },
        )
        result = comp.apply({})

        assert "port" not in result["__context_updates__"]
        assert result["__context_updates__"]["good"] == "hello"
        assert result["__context_load_stats__"]["nb_skipped"] == 1
        assert "port" in result["__context_load_stats__"]["skipped_keys"]

    def test_malformed_delimited_line_skipped(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("good=value\nbadline\nanother=ok\n")

        comp = ContextLoad("cl", {"path": str(f)})
        result = comp.apply({})

        assert len(result["__context_updates__"]) == 2
        assert "badline" not in result["__context_updates__"]


# ======================================================================
# Print operations / masking
# ======================================================================


class TestContextLoadPrintOperations:
    def test_print_operations_logs(self, tmp_path, caplog):
        f = tmp_path / "config.properties"
        f.write_text("host=localhost\n")

        comp = ContextLoad(
            "cl", {"path": str(f), "print_operations": True}
        )
        with caplog.at_level(logging.INFO):
            comp.apply({})

        assert "host = localhost" in caplog.text

    def test_password_masked(self, tmp_path, caplog):
        f = tmp_path / "config.properties"
        f.write_text("db_password=super_secret\napi_token=abc123\n")

        comp = ContextLoad(
            "cl", {"path": str(f), "print_operations": True}
        )
        with caplog.at_level(logging.INFO):
            comp.apply({})

        assert "super_secret" not in caplog.text
        assert "abc123" not in caplog.text
        assert "********" in caplog.text

    def test_sensitive_key_patterns(self, tmp_path, caplog):
        """All sensitive patterns should be masked."""
        f = tmp_path / "config.properties"
        f.write_text("my_secret=a\napi_key=b\ncredential_file=c\n")

        comp = ContextLoad(
            "cl", {"path": str(f), "print_operations": True}
        )
        with caplog.at_level(logging.INFO):
            comp.apply({})

        assert caplog.text.count("********") == 3


# ======================================================================
# Validation
# ======================================================================


class TestContextLoadValidation:
    def test_missing_path(self):
        comp = ContextLoad("cl", {})
        errors = comp.validate()
        assert any("path" in e.lower() for e in errors)

    def test_invalid_format(self):
        comp = ContextLoad("cl", {"path": "/tmp/x.txt", "format": "xml"})
        errors = comp.validate()
        assert any("format" in e.lower() for e in errors)

    def test_valid_config(self, tmp_path):
        comp = ContextLoad("cl", {"path": str(tmp_path / "x.txt")})
        errors = comp.validate()
        assert errors == []


# ======================================================================
# Context placeholder resolution
# ======================================================================


class TestContextLoadContextPlaceholder:
    def test_path_resolves_context(self, tmp_path):
        f = tmp_path / "config.properties"
        f.write_text("k=v\n")

        comp = ContextLoad(
            "cl",
            {"path": "${context.config_dir}/config.properties"},
            context={"config_dir": str(tmp_path)},
        )
        result = comp.apply({})

        assert result["__context_updates__"]["k"] == "v"


# ======================================================================
# Registry
# ======================================================================


class TestContextLoadRegistry:
    def test_registered(self):
        from src.v2.components.registry import REGISTRY

        assert REGISTRY.get("context_load") is ContextLoad
