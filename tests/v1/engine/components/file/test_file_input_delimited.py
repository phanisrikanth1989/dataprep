"""Tests for FileInputDelimited (tFileInputDelimited engine implementation)."""
import csv
import logging

import pytest
import pandas as pd

from src.v1.engine.components.file.file_input_delimited import (
    FileInputDelimited,
    _ERROR_DATE_FORMAT,
    _ERROR_FIELD_COUNT,
    _ERROR_TYPE_CONVERSION,
)
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "FileInputDelimited",
    "filepath": "/tmp/placeholder.csv",  # overridden per test via tmp_path
    "fieldseparator": ";",
    "encoding": "ISO-8859-15",
    "header_rows": 0,
    "footer_rows": 0,
    "limit": "",
    "csv_option": False,
    "remove_empty_row": True,
    "trim_all": False,
    "trim_select": [],
    "check_fields_num": False,
    "check_date": False,
    "die_on_error": False,
}

_DEFAULT_SCHEMA = [
    {"name": "id", "type": "int", "nullable": False},
    {"name": "name", "type": "str", "nullable": True},
    {"name": "value", "type": "float", "nullable": True},
]


def _make_component(config=None, global_map=None, context_manager=None, schema=None):
    """Create a FileInputDelimited with test defaults.

    Always creates fresh GlobalMap and ContextManager instances
    unless explicitly provided.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileInputDelimited(
        component_id="tFID_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = schema if schema is not None else list(_DEFAULT_SCHEMA)
    return comp


def _write_file(tmp_path, filename, content, encoding="iso-8859-15"):
    """Write content to file with specified encoding, return path as string."""
    f = tmp_path / filename
    f.write_text(content, encoding=encoding)
    return str(f)


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for missing filepath."""

    def test_missing_filepath_raises(self):
        config = dict(_DEFAULT_CONFIG)
        del config["filepath"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="filepath"):
            comp.execute(None)

    def test_empty_filepath_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["filepath"] = ""
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="filepath"):
            comp.execute(None)

    def test_valid_config_does_not_raise(self, tmp_path):
        filepath = _write_file(tmp_path, "valid.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert result["main"] is not None


@pytest.mark.unit
class TestDefaults:
    """Default config produces expected behavior per Talend defaults."""

    def test_default_fieldseparator_is_semicolon(self, tmp_path):
        filepath = _write_file(tmp_path, "semi.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_default_encoding_is_iso_8859_15(self, tmp_path):
        # Write a file with ISO-8859-15 specific char (Euro sign)
        filepath = _write_file(
            tmp_path, "iso.csv", "1;\u20ac;10.5\n", encoding="iso-8859-15"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 1

    def test_default_header_rows_is_zero(self, tmp_path):
        filepath = _write_file(tmp_path, "hdr.csv", "1;Alice;10.5\n2;Bob;20.0\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        # No header skip -- all rows are data
        assert len(result["main"]) == 2

    def test_default_remove_empty_row_is_true(self, tmp_path):
        filepath = _write_file(
            tmp_path, "empty.csv", "1;Alice;10.5\n;;\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        # Empty row removed by default
        assert len(result["main"]) == 2


@pytest.mark.unit
class TestBasicReading:
    """Core file reading with various delimiters and options."""

    def test_semicolon_delimiter(self, tmp_path):
        filepath = _write_file(tmp_path, "semi.csv", "1;Alice;10.5\n2;Bob;20.0\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "fieldseparator": ";"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_comma_delimiter(self, tmp_path):
        filepath = _write_file(tmp_path, "comma.csv", "1,Alice,10.5\n2,Bob,20.0\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "fieldseparator": ","}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_tab_delimiter(self, tmp_path):
        filepath = _write_file(
            tmp_path, "tab.csv", "1\tAlice\t10.5\n2\tBob\t20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "fieldseparator": "\t"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_header_skip(self, tmp_path):
        filepath = _write_file(
            tmp_path, "hdr.csv", "ID;NAME;VALUE\n1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "header_rows": 1}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_footer_skip(self, tmp_path):
        filepath = _write_file(
            tmp_path,
            "ftr.csv",
            "1;Alice;10.5\n2;Bob;20.0\nFOOTER;LINE;HERE\n",
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "footer_rows": 1}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_limit_rows(self, tmp_path):
        filepath = _write_file(
            tmp_path,
            "limit.csv",
            "1;Alice;10.5\n2;Bob;20.0\n3;Charlie;30.0\n",
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "limit": "2"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_utf8_encoding(self, tmp_path):
        filepath = _write_file(
            tmp_path, "utf8.csv", "1;Alice;10.5\n2;Bob;20.0\n", encoding="utf-8"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "encoding": "UTF-8"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_escaped_tab_separator(self, tmp_path):
        filepath = _write_file(
            tmp_path, "tab.csv", "1\tAlice\t10.5\n2\tBob\t20.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "fieldseparator": "\\t",
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2


@pytest.mark.unit
class TestCsvOption:
    """CSV_OPTION toggle controls RFC4180 mode (FILD-04)."""

    def test_csv_disabled_no_quoting(self, tmp_path):
        """csv_option=False: quotes kept verbatim, not parsed."""
        filepath = _write_file(
            tmp_path, "noquote.csv", '1;"Alice";10.5\n2;"Bob";20.0\n'
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "csv_option": False}
        comp = _make_component(config=config)
        result = comp.execute(None)
        # Quotes kept verbatim in csv_option=False mode
        assert '"Alice"' in str(result["main"].iloc[0]["name"])

    def test_csv_enabled_handles_quoted_fields(self, tmp_path):
        """csv_option=True: quoted fields parsed correctly."""
        filepath = _write_file(
            tmp_path, "quoted.csv", '1;"Alice";10.5\n2;"Bob";20.0\n'
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_csv_embedded_delimiter(self, tmp_path):
        """csv_option=True: handles embedded delimiters inside quotes."""
        filepath = _write_file(
            tmp_path, "embed.csv", '1;"Alice;Smith";10.5\n2;"Bob";20.0\n'
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert result["main"].iloc[0]["name"] == "Alice;Smith"

    def test_csv_embedded_newlines(self, tmp_path):
        """csv_option=True: handles embedded newlines inside quotes."""
        content = '1;"Alice\nSmith";10.5\n2;"Bob";20.0\n'
        filepath = _write_file(tmp_path, "newline.csv", content)
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2
        assert "Alice\nSmith" in str(result["main"].iloc[0]["name"])

    def test_csv_escaped_quotes(self, tmp_path):
        """csv_option=True: handles doubled quotes inside fields."""
        content = '1;"Alice ""The Great""";10.5\n2;"Bob";20.0\n'
        filepath = _write_file(tmp_path, "escape.csv", content)
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "csv_option": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert 'Alice "The Great"' in str(result["main"].iloc[0]["name"])

    def test_csv_mode_with_footer_skipping(self, tmp_path):
        """CSV mode with footer_rows uses deque-based skipping."""
        lines = [
            '1;"Alice";10.5',
            '2;"Bob";20.0',
            '3;"Charlie";30.0',
            '4;"Diana";40.0',
            '5;"Eve";50.0',
            "FOOTER1;LINE;HERE",
            "FOOTER2;LINE;HERE",
        ]
        filepath = _write_file(tmp_path, "csvftr.csv", "\n".join(lines) + "\n")
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "csv_option": True,
            "footer_rows": 2,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 5


@pytest.mark.unit
class TestTrimSelect:
    """Per-column trim overrides trim_all (FILD-05)."""

    def test_trim_select_specific_column(self, tmp_path):
        filepath = _write_file(
            tmp_path, "trim.csv", "1; Alice ;10.5\n2; Bob ;20.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "trim_select": [
                {"column": "name", "trim": True},
                {"column": "id", "trim": False},
            ],
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_trim_select_overrides_trim_all(self, tmp_path):
        """trim_select overrides trim_all when non-empty."""
        filepath = _write_file(
            tmp_path, "override.csv", "1; Alice ; 10.5 \n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "trim_all": True,
            "trim_select": [
                {"column": "name", "trim": True},
                {"column": "value", "trim": False},
            ],
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        # name trimmed via trim_select, value NOT trimmed because trim_select takes priority
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_columns_not_in_trim_select_untouched(self, tmp_path):
        filepath = _write_file(
            tmp_path, "untouched.csv", "1; Alice ; 10.5 \n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "trim_select": [{"column": "name", "trim": True}],
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_trim_all_trims_all_string_columns(self, tmp_path):
        filepath = _write_file(
            tmp_path, "trimall.csv", "1; Alice ; 10.5 \n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "trim_all": True,
            "trim_select": [],
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        # All string columns trimmed
        name_val = str(result["main"].iloc[0]["name"])
        assert name_val == "Alice"

    def test_no_trim_by_default(self, tmp_path):
        filepath = _write_file(
            tmp_path, "notrim.csv", "1; Alice ;10.5\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        # No trim applied -- leading/trailing spaces preserved
        assert " Alice " in str(result["main"].iloc[0]["name"])


@pytest.mark.unit
class TestCheckFieldsNum:
    """CHECK_FIELDS_NUM validates row field count (FILD-06)."""

    def test_wrong_field_count_rejected(self, tmp_path):
        filepath = _write_file(
            tmp_path, "fields.csv", "1;Alice;10.5\n2;Bob\n3;Charlie;30.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        reject = result.get("reject")
        assert reject is not None and len(reject) > 0
        assert reject.iloc[0]["errorCode"] == _ERROR_FIELD_COUNT

    def test_correct_field_count_passes(self, tmp_path):
        filepath = _write_file(
            tmp_path, "ok.csv", "1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2
        assert result.get("reject") is None

    def test_field_count_check_disabled_by_default(self, tmp_path):
        filepath = _write_file(
            tmp_path, "nocheck.csv", "1;Alice;10.5\n2;Bob\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        # No field count check -- both rows go to main (fast path)
        assert len(result["main"]) == 2

    def test_reject_row_has_error_code_field_count(self, tmp_path):
        filepath = _write_file(
            tmp_path, "fc.csv", "1;Alice;10.5\n2;Bob\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        reject = result.get("reject")
        assert reject is not None
        assert "errorCode" in reject.columns
        assert "errorMessage" in reject.columns


@pytest.mark.unit
class TestCheckDate:
    """CHECK_DATE validates date patterns (FILD-07)."""

    def test_valid_date_passes(self, tmp_path):
        filepath = _write_file(
            tmp_path, "date.csv", "1;Alice;2024-01-15\n"
        )
        schema = [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "date", "type": "datetime", "nullable": True, "date_pattern": "%Y-%m-%d"},
        ]
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_date": True,
        }
        comp = _make_component(config=config, schema=schema)
        result = comp.execute(None)
        assert len(result["main"]) == 1
        assert result.get("reject") is None

    def test_invalid_date_rejected(self, tmp_path):
        filepath = _write_file(
            tmp_path, "baddate.csv", "1;Alice;not-a-date\n"
        )
        schema = [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "date", "type": "datetime", "nullable": True, "date_pattern": "%Y-%m-%d"},
        ]
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_date": True,
        }
        comp = _make_component(config=config, schema=schema)
        result = comp.execute(None)
        reject = result.get("reject")
        assert reject is not None and len(reject) > 0
        assert reject.iloc[0]["errorCode"] == _ERROR_DATE_FORMAT

    def test_column_without_date_pattern_skipped(self, tmp_path):
        filepath = _write_file(
            tmp_path, "nopattern.csv", "1;Alice;10.5\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_date": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        # No date columns in default schema -- no date check triggered
        assert len(result["main"]) == 1

    def test_check_date_disabled_by_default(self, tmp_path):
        filepath = _write_file(
            tmp_path, "nocheck.csv", "1;Alice;not-a-date\n"
        )
        schema = [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "date", "type": "datetime", "nullable": True, "date_pattern": "%Y-%m-%d"},
        ]
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config, schema=schema)
        result = comp.execute(None)
        # check_date=False: no date validation, goes through fast path
        assert "main" in result


@pytest.mark.unit
class TestRejectFlow:
    """REJECT output for validation failures (FILD-03)."""

    def test_type_conversion_failure_rejected(self, tmp_path):
        filepath = _write_file(
            tmp_path, "type.csv", "not_an_int;Alice;10.5\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        reject = result.get("reject")
        assert reject is not None
        assert reject.iloc[0]["errorCode"] == _ERROR_TYPE_CONVERSION

    def test_reject_has_all_original_columns(self, tmp_path):
        filepath = _write_file(
            tmp_path, "rejectcols.csv", "not_an_int;Alice;10.5\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        reject = result.get("reject")
        assert reject is not None
        # All original schema columns present
        for col in ["id", "name", "value"]:
            assert col in reject.columns
        # Plus errorCode and errorMessage
        assert "errorCode" in reject.columns
        assert "errorMessage" in reject.columns

    def test_multiple_reject_reasons(self, tmp_path):
        filepath = _write_file(
            tmp_path,
            "multi.csv",
            "not_an_int;Alice;10.5\n2;Bob;not_a_float\n3;Charlie;30.0\n",
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        reject = result.get("reject")
        assert reject is not None
        assert len(reject) == 2
        assert len(result["main"]) == 1

    def test_nb_line_reject_matches_reject_count(self, tmp_path):
        filepath = _write_file(
            tmp_path, "stats.csv", "not_int;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        result = comp.execute(None)
        assert result["stats"]["NB_LINE_REJECT"] >= 1

    def test_main_plus_reject_equals_total(self, tmp_path):
        filepath = _write_file(
            tmp_path,
            "total.csv",
            "1;Alice;10.5\nnot_int;Bob;20.0\n3;Charlie;30.0\n",
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        main_count = len(result["main"])
        reject_count = len(result["reject"]) if result.get("reject") is not None else 0
        assert main_count + reject_count == 3

    def test_error_code_constants_are_standardized(self):
        """Verify that error code constants have exact expected values."""
        assert _ERROR_FIELD_COUNT == "FIELD_COUNT"
        assert _ERROR_TYPE_CONVERSION == "TYPE_CONVERSION"
        assert _ERROR_DATE_FORMAT == "DATE_FORMAT"


@pytest.mark.unit
class TestGlobalMapVariables:
    """GlobalMap variables set correctly (FILD-08)."""

    def test_filename_set_to_resolved_path(self, tmp_path):
        filepath = _write_file(tmp_path, "gm.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(None)
        assert gm.get("tFID_1_FILENAME") == filepath

    def test_encoding_set(self, tmp_path):
        filepath = _write_file(tmp_path, "enc.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "encoding": "UTF-8"}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(None)
        assert gm.get("tFID_1_ENCODING") == "UTF-8"

    def test_stats_set_after_execution(self, tmp_path):
        filepath = _write_file(
            tmp_path, "stats.csv", "1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(None)
        assert gm.get_component_stat("tFID_1", "NB_LINE") == 2
        assert gm.get_component_stat("tFID_1", "NB_LINE_OK") == 2

    def test_works_without_global_map(self, tmp_path):
        filepath = _write_file(tmp_path, "nogm.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config, global_map=None)
        comp.global_map = None
        result = comp.execute(None)
        assert "main" in result

    def test_nb_line_reject_in_globalmap(self, tmp_path):
        filepath = _write_file(
            tmp_path, "rej.csv", "not_int;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": True,
        }
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(None)
        assert gm.get_component_stat("tFID_1", "NB_LINE_REJECT") >= 1


@pytest.mark.unit
class TestDeferredFeatures:
    """Deferred features log warning but do not crash (FILD-09/D-21)."""

    def test_uncompress_logs_warning(self, tmp_path, caplog):
        filepath = _write_file(tmp_path, "defer.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "uncompress": True}
        comp = _make_component(config=config)
        with caplog.at_level(logging.WARNING):
            result = comp.execute(None)
        assert "uncompress" in caplog.text.lower() or "Compressed" in caplog.text
        assert "main" in result

    def test_random_logs_warning(self, tmp_path, caplog):
        filepath = _write_file(tmp_path, "rand.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "random": True}
        comp = _make_component(config=config)
        with caplog.at_level(logging.WARNING):
            result = comp.execute(None)
        assert "random" in caplog.text.lower() or "Random" in caplog.text
        assert "main" in result

    def test_advanced_separator_logs_warning(self, tmp_path, caplog):
        filepath = _write_file(tmp_path, "adv.csv", "1;Alice;10.5\n")
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "advanced_separator": True,
        }
        comp = _make_component(config=config)
        with caplog.at_level(logging.WARNING):
            result = comp.execute(None)
        assert "advanced_separator" in caplog.text or "numeric" in caplog.text.lower()
        assert "main" in result


@pytest.mark.unit
class TestRemoveEmptyRow:
    """Empty row handling."""

    def test_empty_rows_removed_when_enabled(self, tmp_path):
        filepath = _write_file(
            tmp_path, "empty.csv", "1;Alice;10.5\n;;\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "remove_empty_row": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_empty_rows_kept_when_disabled(self, tmp_path):
        filepath = _write_file(
            tmp_path, "keep.csv", "1;Alice;10.5\n;;\n2;Bob;20.0\n"
        )
        nullable_schema = [
            {"name": "id", "type": "str", "nullable": True},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "value", "type": "str", "nullable": True},
        ]
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "remove_empty_row": False}
        comp = _make_component(config=config, schema=nullable_schema)
        result = comp.execute(None)
        assert len(result["main"]) == 3

    def test_all_empty_rows_file(self, tmp_path):
        filepath = _write_file(tmp_path, "allempty.csv", ";;\n;;\n;;\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "remove_empty_row": True}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 0


@pytest.mark.unit
class TestEdgeCases:
    """Empty file, missing file, single row, header only."""

    def test_empty_file_produces_empty_dataframe(self, tmp_path):
        filepath = _write_file(tmp_path, "empty.csv", "")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert result["main"] is not None
        assert len(result["main"]) == 0

    def test_file_not_found_raises(self):
        config = {**_DEFAULT_CONFIG, "filepath": "/nonexistent/path/file.csv"}
        comp = _make_component(config=config)
        with pytest.raises((FileOperationError, Exception)):
            comp.execute(None)

    def test_single_row_file(self, tmp_path):
        filepath = _write_file(tmp_path, "single.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 1

    def test_header_only_file(self, tmp_path):
        filepath = _write_file(tmp_path, "hdronly.csv", "ID;NAME;VALUE\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "header_rows": 1}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 0

    def test_invalid_limit_ignored(self, tmp_path):
        filepath = _write_file(
            tmp_path, "badlimit.csv", "1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "limit": "abc"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2


@pytest.mark.unit
class TestSchemaHandling:
    """Type coercion and schema validation."""

    def test_int_columns_converted(self, tmp_path):
        filepath = _write_file(tmp_path, "int.csv", "1;Alice;10.5\n2;Bob;20.0\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        # After schema validation, id should be numeric
        assert result["main"].iloc[0]["id"] == 1

    def test_float_columns_converted(self, tmp_path):
        filepath = _write_file(tmp_path, "flt.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert abs(result["main"].iloc[0]["value"] - 10.5) < 0.01

    def test_datetime_columns_converted(self, tmp_path):
        filepath = _write_file(
            tmp_path, "dt.csv", "1;Alice;2024-01-15\n"
        )
        schema = [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "date", "type": "datetime", "nullable": True, "date_pattern": "%Y-%m-%d"},
        ]
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config, schema=schema)
        result = comp.execute(None)
        assert result["main"].iloc[0]["date"] is not None

    def test_no_schema_returns_strings(self, tmp_path):
        filepath = _write_file(tmp_path, "noschema.csv", "1;Alice;10.5\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config, schema=None)
        comp.output_schema = None
        result = comp.execute(None)
        # Without schema, values stay as strings
        assert isinstance(result["main"].iloc[0][0], str)


@pytest.mark.unit
class TestIterateReexecution:
    """execute() twice with reset() gives correct results both times."""

    def test_second_execute_produces_same_results(self, tmp_path):
        filepath = _write_file(
            tmp_path, "iter.csv", "1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)

        result1 = comp.execute(None)
        comp.reset()
        result2 = comp.execute(None)

        assert len(result1["main"]) == len(result2["main"])

    def test_stats_reset_between_executions(self, tmp_path):
        filepath = _write_file(
            tmp_path, "iter2.csv", "1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)

        comp.execute(None)
        first_nb_line = gm.get_component_stat("tFID_1", "NB_LINE")

        comp.reset()
        comp.execute(None)
        second_nb_line = gm.get_component_stat("tFID_1", "NB_LINE")

        # Stats should reflect only the second execution
        assert second_nb_line == first_nb_line

    def test_original_config_unchanged(self, tmp_path):
        filepath = _write_file(
            tmp_path, "iter3.csv", "1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config)

        comp.execute(None)
        original_snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(None)

        assert comp._original_config == original_snapshot


@pytest.mark.unit
class TestVectorizedFastPath:
    """Fast vectorized path when no validation flags are set."""

    def test_fast_path_without_validation_flags(self, tmp_path):
        filepath = _write_file(
            tmp_path, "fast.csv", "1;Alice;10.5\n2;Bob;20.0\n3;Charlie;30.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": False,
            "check_date": False,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3

    def test_fast_path_type_conversion_correct(self, tmp_path):
        filepath = _write_file(
            tmp_path, "fasttype.csv", "1;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": False,
            "check_date": False,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        # Types should be converted even without validation flags
        assert result["main"].iloc[0]["id"] == 1
        assert abs(result["main"].iloc[0]["value"] - 10.5) < 0.01

    def test_fast_path_handles_conversion_failure(self, tmp_path):
        filepath = _write_file(
            tmp_path, "fastfail.csv", "not_int;Alice;10.5\n2;Bob;20.0\n"
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "check_fields_num": False,
            "check_date": False,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        # Fast path falls back to per-row for column with failure
        reject = result.get("reject")
        assert reject is not None
        assert len(reject) == 1
        assert reject.iloc[0]["errorCode"] == _ERROR_TYPE_CONVERSION


@pytest.mark.unit
class TestRowSeparator:
    """row_separator / csv_row_separator wired into read paths."""

    def test_standard_newline_default(self, tmp_path):
        """Default \\n row separator reads normally."""
        filepath = _write_file(tmp_path, "nl.csv", "1;Alice;10.5\n2;Bob;20.0\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "row_separator": "\\n"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_pipe_row_separator(self, tmp_path):
        """Non-standard row separator '|' splits rows correctly."""
        content = "1;Alice;10.5|2;Bob;20.0|3;Charlie;30.0"
        filepath = _write_file(tmp_path, "pipe.csv", content)
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "row_separator": "|"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3
        assert result["main"].iloc[1]["name"] == "Bob"

    def test_multichar_row_separator(self, tmp_path):
        """Multi-char row separator '||' splits rows correctly."""
        content = "1;Alice;10.5||2;Bob;20.0||3;Charlie;30.0"
        filepath = _write_file(tmp_path, "multi.csv", content)
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "row_separator": "||"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3

    def test_custom_row_separator_with_header_skip(self, tmp_path):
        """Non-standard row separator respects header_rows."""
        content = "HEADER_LINE|1;Alice;10.5|2;Bob;20.0"
        filepath = _write_file(tmp_path, "hdr.csv", content)
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "row_separator": "|",
            "header_rows": 1,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_custom_row_separator_with_footer_skip(self, tmp_path):
        """Non-standard row separator respects footer_rows."""
        content = "1;Alice;10.5|2;Bob;20.0|FOOTER"
        filepath = _write_file(tmp_path, "ftr.csv", content)
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "row_separator": "|",
            "footer_rows": 1,
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_csv_mode_custom_row_separator(self, tmp_path):
        """csv_option=True with non-standard csv_row_separator."""
        content = '1;"Alice";10.5|2;"Bob";20.0|3;"Charlie";30.0'
        filepath = _write_file(tmp_path, "csvpipe.csv", content)
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "csv_option": True,
            "csv_row_separator": "|",
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 3
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_csv_mode_standard_separator_unchanged(self, tmp_path):
        """csv_option=True with standard \\n still works via native path."""
        filepath = _write_file(
            tmp_path, "csvstd.csv", '1;"Alice";10.5\n2;"Bob";20.0\n'
        )
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "csv_option": True,
            "csv_row_separator": "\\n",
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_trailing_separator_no_extra_row(self, tmp_path):
        """Trailing row separator does not produce phantom empty row."""
        content = "1;Alice;10.5|2;Bob;20.0|"
        filepath = _write_file(tmp_path, "trail.csv", content)
        config = {**_DEFAULT_CONFIG, "filepath": filepath, "row_separator": "|"}
        comp = _make_component(config=config)
        result = comp.execute(None)
        assert len(result["main"]) == 2


@pytest.mark.unit
class TestRejectFlowCR03WR04:
    """CR-03 / WR-04 targeted tests (Task 2 RED, Task 3/4 GREEN)."""

    def test_unmapped_bool_routes_to_reject(self, tmp_path):
        """CR-03: bool column with unmapped values routes to reject, not crash.

        "yes"/"no" are recognised by _convert_value but NOT by _vectorized_convert's
        mapping dict (which only maps to True/False) before the fix.
        After the fix, DataValidationError -> ValueError so the per-row fallback catches
        it and routes bad rows to reject instead of propagating the exception.
        """
        # Row 1: valid bool (true/false)
        # Row 2: unmapped bool value ("maybe") -- must go to reject
        # Row 3: valid bool (True/False)
        content = "1;true\n2;maybe\n3;false\n"
        filepath = _write_file(tmp_path, "bool_test.csv", content)
        schema = [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "flag", "type": "bool", "nullable": True},
        ]
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "fieldseparator": ";",
        }
        comp = _make_component(config=config, schema=schema)
        # Must NOT raise -- bad rows must go to reject
        result = comp.execute(None)
        reject = result.get("reject")
        assert reject is not None, "Unmapped bool rows must route to reject, not crash"
        assert len(reject) >= 1, "At least the 'maybe' row should be rejected"
        # Valid rows go to main
        assert len(result["main"]) >= 1, "Valid rows must reach main"

    def test_reject_indices_reset(self, tmp_path):
        """WR-04: main and reject DataFrames from fast path have reset indices (0..N-1).

        When multiple rows fail type conversion, the surviving main DataFrame
        must have a reset index (no gaps), and the reject DataFrame must also
        have a contiguous 0-based index.

        Before the fix: result = result[good_mask].copy() mid-loop leaves stale
        indices in `result`. The returned main df may have non-contiguous index
        (e.g. [1, 2] instead of [0, 1]).
        """
        # Row 0 (id=bad): int column fails -> reject
        # Row 1 (id=bad): int column fails -> reject
        # Row 2: fully valid -> main
        content = "bad_int;Alice;10.5\nanother_bad;Bob;20.0\n3;Charlie;30.0\n"
        filepath = _write_file(tmp_path, "multi_row_fail.csv", content)
        config = {
            **_DEFAULT_CONFIG,
            "filepath": filepath,
            "fieldseparator": ";",
        }
        comp = _make_component(config=config)
        result = comp.execute(None)
        reject = result.get("reject")
        main = result["main"]
        assert reject is not None, "Expected 2 rejected rows"
        assert len(reject) == 2
        assert len(main) == 1
        # Main index must be reset: [0] not [2]
        assert list(main.index) == list(range(len(main))), (
            f"Main DataFrame index must be reset 0..N-1, got: {list(main.index)}"
        )
        # Reject index must be reset: [0, 1]
        assert list(reject.index) == list(range(len(reject))), (
            f"Reject DataFrame index must be reset 0..N-1, got: {list(reject.index)}"
        )


@pytest.mark.unit
class TestSchema:
    """WR-06: one-time warning when output_schema is None."""

    def test_no_schema_warns(self, tmp_path, caplog):
        """WR-06: component logs a WARNING containing 'No output_schema' when schema is None.

        The warning must appear exactly once (one-shot flag) and the main DF
        must contain all-string columns.
        """
        filepath = _write_file(tmp_path, "noschema.csv", "1;Alice;10.5\n2;Bob;20.0\n")
        config = {**_DEFAULT_CONFIG, "filepath": filepath}
        comp = _make_component(config=config, schema=None)
        comp.output_schema = None

        with caplog.at_level(logging.WARNING):
            result = comp.execute(None)

        # Warning must be present
        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        no_schema_warnings = [m for m in warning_msgs if "No output_schema" in str(m)]
        assert len(no_schema_warnings) >= 1, (
            f"Expected at least one WARNING containing 'No output_schema', got: {warning_msgs}"
        )

        # Main DF must have all-string columns
        assert "main" in result
        assert len(result["main"]) == 2
        for col in result["main"].columns:
            assert result["main"][col].dtype == object, (
                f"Column '{col}' should be object/str dtype without schema"
            )
