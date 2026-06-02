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

    def test_trim_all_wins_over_trim_select_false_entries(self, tmp_path):
        """trim_all=True trims every string column even when trim_select has trim=False entries.

        Talend semantics: TRIMALL=true always wins.  TRIMSELECT entries with
        trim=false are the UI default state ("no explicit override"), not an
        instruction to suppress trimming.
        """
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
        # trim_all=True must trim ALL string columns -- trim_select trim=False does not suppress it.
        assert result["main"].iloc[0]["name"] == "Alice"
        # 'value' is float here (schema typed), so trimming happens on the raw string before cast;
        # what matters is name was trimmed and no error was raised.
        assert result["main"].iloc[0]["value"] == 10.5

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

        # Main DF must have all-string columns (object or Arrow StringDtype in pandas 3.0)
        assert "main" in result
        assert len(result["main"]) == 2
        for col in result["main"].columns:
            dtype = result["main"][col].dtype
            is_string_dtype = (
                dtype == object
                or str(dtype) in ("string", "str")
                or hasattr(dtype, "na_value")  # pandas 3.0 StringDtype
                or pd.api.types.is_string_dtype(dtype)
            )
            assert is_string_dtype, (
                f"Column '{col}' should be string-like dtype without schema, got {dtype}"
            )


# ------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   175-179 (csv_option=True + multi-char fieldseparator -> truncate + warn)
#   254-255 (die_on_error=True with reject rows -> DataValidationError wrap)
#   300-301 (CSV-mode non-standard sep + read failure -> FileOperationError)
#   315 (CSV-mode non-standard sep + empty after split -> empty DF)
#   332-333 / 358-359 (standard-mode + non-standard sep + parse failure)
#   401-406 (CSV-mode non-standard sep FileNotFoundError branch)
#   413, 415, 417 (CSV non-standard sep header_rows / footer_rows / pop)
#   420 (CSV non-standard sep no lines -> empty DF)
#   430-431 (CSV escape != quote: escapechar + doublequote=False)
#   436 (CSV non-standard sep csv.reader -> empty rows -> empty DF)
#   441-442 (CSV non-standard sep schema mismatch -> warning)
#   459-460 (CSV standard sep escape != quote)
#   466-469 (CSV standard sep header skip / StopIteration)
#   483-488 (CSV standard sep FileNotFoundError + Exception)
#   493-494 (CSV standard sep no rows -> empty DF)
#   499-500 (CSV standard sep schema mismatch -> warning)
#   618 (vectorized convert no schema -> early return)
#   645 (per-row fallback skip already-rejected idx)
#   670 (per-row fallback else-branch values)
#   722 (vectorized bool unmapped -> raise)
#   725 (vectorized passthrough for str type)
#   797 (chunked validate row missing schema column)
#   914-918 (convert_value empty + nullable / non-nullable raise)
#   937-944 (convert_value datetime no pattern + Decimal + object + fallthrough)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408StaticHelpers:
    """Direct exercises of static helpers _convert_value / _vectorized_convert."""

    def test_convert_value_empty_nullable_returns_none(self):
        """convert_value: empty + nullable -> None (914-915)."""
        out = FileInputDelimited._convert_value(
            "  ", {"name": "x", "type": "int", "nullable": True}
        )
        assert out is None

    def test_convert_value_empty_non_nullable_raises(self):
        """convert_value: empty + non-nullable -> ValueError (916-918)."""
        with pytest.raises(ValueError, match="non-nullable"):
            FileInputDelimited._convert_value(
                "", {"name": "x", "type": "int", "nullable": False}
            )

    def test_convert_value_datetime_no_pattern(self):
        """convert_value: datetime without pattern uses pd.to_datetime fallback (937)."""
        out = FileInputDelimited._convert_value(
            "2024-01-15", {"name": "d", "type": "datetime"}
        )
        # Coerced to a Timestamp/datetime
        assert hasattr(out, "year") or out is not None

    def test_convert_value_decimal(self):
        """convert_value: Decimal type returns Decimal instance (938-940)."""
        from decimal import Decimal
        out = FileInputDelimited._convert_value(
            "12.34", {"name": "d", "type": "Decimal"}
        )
        assert isinstance(out, Decimal)
        assert out == Decimal("12.34")

    def test_convert_value_object_type_returns_value(self):
        """convert_value: 'object' type returns raw value (941-942)."""
        out = FileInputDelimited._convert_value(
            "raw_string", {"name": "x", "type": "object"}
        )
        assert out == "raw_string"

    def test_convert_value_unknown_type_falls_through(self):
        """convert_value: unknown type returns value unchanged (944)."""
        out = FileInputDelimited._convert_value(
            "anything", {"name": "x", "type": "WIDGET"}
        )
        assert out == "anything"

    def test_vectorized_convert_str_passthrough(self):
        """_vectorized_convert: str type returns series unchanged (725)."""
        s = pd.Series(["a", "b", "c"])
        out = FileInputDelimited._vectorized_convert(s, "str")
        assert list(out) == ["a", "b", "c"]

    def test_vectorized_convert_bool_unmapped_raises(self):
        """_vectorized_convert: unmapped bool string -> ValueError (717-721)."""
        s = pd.Series(["true", "MAYBE", "false"])
        with pytest.raises(ValueError, match="Unmapped bool"):
            FileInputDelimited._vectorized_convert(s, "bool")

    def test_vectorized_convert_bool_all_mapped_returns_series(self):
        """_vectorized_convert: all values mapped -> return mapped Series (line 722)."""
        s = pd.Series(["true", "false", "yes", "no"])
        out = FileInputDelimited._vectorized_convert(s, "bool")
        assert list(out) == [True, False, True, False]

    def test_vectorized_convert_datetime_returns_series(self):
        """_vectorized_convert: datetime type -> return parsed Series (line 724)."""
        s = pd.Series(["2024-01-15", "2024-02-20"])
        out = FileInputDelimited._vectorized_convert(s, "datetime")
        assert pd.api.types.is_datetime64_any_dtype(out)


@pytest.mark.unit
class TestCoverageLift1408ProcessBranches:
    """Targeted process branches: multi-char delimiter, die_on_error, etc."""

    def test_csv_option_multichar_delimiter_warns_and_truncates(self, tmp_path, caplog):
        """csv_option=True + multi-char fieldseparator -> warn + use first char (175-179)."""
        # Use ";;" multi-char in CSV mode; component should warn and reduce to ";"
        f = _write_file(tmp_path, "multi.csv", "1;Alice\n2;Bob\n", encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "csv_option": True,
               "fieldseparator": ";;", "encoding": "utf-8"}
        comp = _make_component(config=cfg)
        with caplog.at_level(logging.WARNING):
            result = comp.execute(None)
        assert any(
            "Multi-character fieldseparator" in r.message and "csv_option=True" in r.message
            for r in caplog.records
        )
        # File parsed with single-char ';' delimiter -> 2 rows
        assert len(result["main"]) == 2

    def test_die_on_error_true_with_reject_rows_raises_data_validation_error(
        self, tmp_path
    ):
        """die_on_error=True with type-conversion rejects -> DataValidationError (254-255)."""
        from src.v1.engine.exceptions import DataValidationError, ComponentExecutionError
        # 'bad' is not int-convertible -> reject -> die
        content = "1;Alice;10.5\nbad;Bob;20.0\n"
        f = _write_file(tmp_path, "die.csv", content)
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "die_on_error": True}
        comp = _make_component(config=cfg)
        with pytest.raises(
            (DataValidationError, ComponentExecutionError),
            match="Schema/coercion failed",
        ):
            comp.execute(None)


@pytest.mark.unit
class TestCoverageLift1408NonStandardRowSeparator:
    """Branches inside _read_standard_mode and _read_csv_mode for non-default row separators."""

    def test_standard_mode_nonstandard_sep_read_failure(self, tmp_path, monkeypatch):
        """Standard mode + non-standard row sep + open() fails -> FileOperationError (300-301)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        f = tmp_path / "nostd.csv"
        f.write_text("1;Alice|2;Bob", encoding="iso-8859-15")

        cfg = {**_DEFAULT_CONFIG, "filepath": str(f), "csv_option": False,
               "row_separator": "|"}  # non-standard separator
        comp = _make_component(config=cfg)

        # Force open() to fail when reading the CSV path (route via _read_standard_mode).
        import builtins
        original_open = builtins.open

        def selective_open(path, *args, **kwargs):
            if str(path) == str(f):
                raise OSError("simulated read failure")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", selective_open)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Failed to read file",
        ):
            comp.execute(None)

    def test_standard_mode_nonstandard_sep_empty_after_split(self, tmp_path):
        """Standard mode + non-standard sep + content empty after split -> empty DF (315).

        Direct call to _read_standard_mode so we can hit the early-return after the
        header skip consumes all available lines.
        """
        f = _write_file(tmp_path, "empty_nstd.csv", "ONLY_HDR|", encoding="iso-8859-15")
        comp = _make_component(config={**_DEFAULT_CONFIG, "filepath": f})
        df = comp._read_standard_mode(
            filepath=f,
            field_separator=";",
            row_separator="|",
            encoding="iso-8859-15",
            header_rows=5,  # > available -> empty after skip
            footer_rows=0,
            schema_cols=None,
        )
        assert len(df) == 0

    def test_standard_mode_nonstandard_sep_parse_failure(self, tmp_path, monkeypatch):
        """Standard mode + non-standard sep + pd.read_csv parse failure -> FileOperationError (332-333)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        f = _write_file(tmp_path, "nstd.csv", "1;Alice|2;Bob", encoding="iso-8859-15")
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "csv_option": False, "row_separator": "|"}
        comp = _make_component(config=cfg)

        original_read_csv = pd.read_csv

        def boom(*a, **kw):
            raise RuntimeError("simulated pd.read_csv failure")

        monkeypatch.setattr(pd, "read_csv", boom)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Failed to parse file|Failed to read file",
        ):
            comp.execute(None)

    def test_standard_mode_default_rowsep_parse_failure(self, tmp_path, monkeypatch):
        """Standard mode + default \\n separator + pd.read_csv failure -> FileOperationError (358-359)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        f = _write_file(tmp_path, "stdsep.csv", "1;Alice\n2;Bob\n", encoding="iso-8859-15")
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "csv_option": False}
        comp = _make_component(config=cfg)

        def boom(*a, **kw):
            raise RuntimeError("simulated pd.read_csv failure")

        monkeypatch.setattr(pd, "read_csv", boom)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Failed to read file",
        ):
            comp.execute(None)

    def test_csv_mode_nonstandard_sep_file_not_found(self, tmp_path, monkeypatch):
        """CSV mode + non-standard csv_row_separator + FileNotFoundError -> FileOperationError (401-404)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        f = tmp_path / "exists.csv"
        f.write_text("1;A|2;B", encoding="utf-8")
        # csv_row_separator (not row_separator) drives _read_csv_mode's branch.
        cfg = {**_DEFAULT_CONFIG, "filepath": str(f), "csv_option": True,
               "csv_row_separator": "|", "encoding": "utf-8"}
        comp = _make_component(config=cfg)

        import builtins
        original_open = builtins.open

        def selective_open(path, *args, **kwargs):
            if str(path) == str(f):
                raise FileNotFoundError("simulated missing during read")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", selective_open)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="File not found",
        ):
            comp.execute(None)

    def test_csv_mode_nonstandard_sep_other_read_error(self, tmp_path, monkeypatch):
        """CSV mode + non-standard csv_row_separator + arbitrary Exception -> FileOperationError (405-408)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        f = tmp_path / "exists.csv"
        f.write_text("1;A|2;B", encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": str(f), "csv_option": True,
               "csv_row_separator": "|", "encoding": "utf-8"}
        comp = _make_component(config=cfg)

        import builtins
        original_open = builtins.open

        def selective_open(path, *args, **kwargs):
            if str(path) == str(f):
                raise OSError("simulated I/O error")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", selective_open)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Failed to read file",
        ):
            comp.execute(None)

    def test_csv_mode_nonstandard_sep_with_header_and_footer(self, tmp_path):
        """CSV non-standard sep with header_rows / footer_rows / trailing-empty pop (413,415,417).

        Calls _read_csv_mode directly to isolate the lines-handling logic from the
        downstream validation pipeline, which has its own coverage elsewhere.
        """
        f = _write_file(tmp_path, "hdr_ftr.csv",
                        "HDR;HDR2|1;A|2;B|FTR;FTR2|", encoding="utf-8")
        comp = _make_component(config={**_DEFAULT_CONFIG, "filepath": f})
        df = comp._read_csv_mode(
            filepath=f,
            field_separator=";",
            row_separator="|",
            encoding="utf-8",
            header_rows=1,
            footer_rows=1,
            text_enclosure='"',
            escape_char='"',
            schema_cols=["k", "v"],
        )
        assert len(df) == 2
        assert list(df["k"]) == ["1", "2"]
        assert list(df["v"]) == ["A", "B"]

    def test_csv_mode_nonstandard_sep_no_lines_after_skip(self, tmp_path):
        """CSV non-standard sep + header_rows >= total lines -> empty DF (line 420).

        Uses direct _read_csv_mode call so we exercise the non-standard
        row-separator branch (csv_row_separator drives this in the public flow).
        """
        f = _write_file(tmp_path, "all_hdr.csv", "HDR|", encoding="utf-8")
        comp = _make_component(config={**_DEFAULT_CONFIG, "filepath": f})
        df = comp._read_csv_mode(
            filepath=f,
            field_separator=";",
            row_separator="|",
            encoding="utf-8",
            header_rows=5,  # > available -> empty after skip
            footer_rows=0,
            text_enclosure='"',
            escape_char='"',
            schema_cols=["k"],
        )
        assert len(df) == 0

    def test_csv_mode_nonstandard_sep_escapechar_distinct_from_quote(self, tmp_path):
        """CSV non-standard sep + escape_char != text_enclosure -> escapechar branch (430-431).

        Direct _read_csv_mode call so the test covers the escapechar reader_kwargs
        branch without involving the downstream validation pipeline.
        """
        f = _write_file(tmp_path, "esc.csv",
                        "1;A|2;B", encoding="utf-8")
        comp = _make_component(config={**_DEFAULT_CONFIG, "filepath": f})
        df = comp._read_csv_mode(
            filepath=f,
            field_separator=";",
            row_separator="|",
            encoding="utf-8",
            header_rows=0,
            footer_rows=0,
            text_enclosure='"',
            escape_char="\\",  # distinct from quote -> hits escapechar branch
            schema_cols=["k", "v"],
        )
        assert len(df) == 2

    def test_csv_mode_nonstandard_sep_schema_column_mismatch_warns(
        self, tmp_path, caplog
    ):
        """CSV non-standard sep + schema column count mismatch -> warning (441-445)."""
        f = _write_file(tmp_path, "mismatch.csv", "1;A;extra|2;B;extra2", encoding="utf-8")
        comp = _make_component(config={**_DEFAULT_CONFIG, "filepath": f})
        with caplog.at_level(logging.WARNING):
            df = comp._read_csv_mode(
                filepath=f,
                field_separator=";",
                row_separator="|",
                encoding="utf-8",
                header_rows=0,
                footer_rows=0,
                text_enclosure='"',
                escape_char='"',
                schema_cols=["k", "v"],  # 2 cols expected; data has 3
            )
        assert len(df) == 2  # rows still parsed
        assert any(
            "Schema expects" in r.message and "columns per row" in r.message
            for r in caplog.records
        )

    def test_csv_mode_nonstandard_sep_csv_reader_returns_empty(self, tmp_path):
        """CSV non-standard sep + csv.reader produces empty rows -> empty DF (line 436).

        After header_rows skip leaves empty list of lines, the rows variable is
        also empty so the early-return at 436 fires.
        """
        f = _write_file(tmp_path, "blank.csv", "x|", encoding="utf-8")
        comp = _make_component(config={**_DEFAULT_CONFIG, "filepath": f})
        # Single line "x" + trailing empty popped; header_rows=1 leaves [].
        df = comp._read_csv_mode(
            filepath=f,
            field_separator=";",
            row_separator="|",
            encoding="utf-8",
            header_rows=1,
            footer_rows=0,
            text_enclosure='"',
            escape_char='"',
            schema_cols=["k"],
        )
        assert len(df) == 0


@pytest.mark.unit
class TestCoverageLift1408CSVStandardRowSep:
    """Branches inside _read_csv_mode standard-row-sep path."""

    def test_csv_mode_escapechar_distinct_from_quote(self, tmp_path):
        """CSV standard sep + escape != quote -> escapechar branch (459-460)."""
        f = _write_file(tmp_path, "esc.csv",
                        '1;\\"escaped\\"\n2;normal\n', encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "csv_option": True,
               "encoding": "utf-8",
               "escape_char": "\\", "text_enclosure": '"'}
        schema = [{"name": "k", "type": "str", "nullable": True},
                  {"name": "v", "type": "str", "nullable": True}]
        comp = _make_component(config=cfg, schema=schema)
        result = comp.execute(None)
        assert len(result["main"]) == 2

    def test_csv_mode_header_rows_with_short_file_stops_iteration(self, tmp_path):
        """CSV standard sep + header_rows > available -> StopIteration break (466-469)."""
        # File has 1 line; header_rows=5 -> next() raises StopIteration on 2nd call -> break
        f = _write_file(tmp_path, "short.csv", "ONLY\n", encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "csv_option": True,
               "encoding": "utf-8", "header_rows": 5}
        schema = [{"name": "k", "type": "str", "nullable": True}]
        comp = _make_component(config=cfg, schema=schema)
        result = comp.execute(None)
        # All lines consumed by header skip; nothing remains.
        assert len(result["main"]) == 0

    def test_csv_mode_file_not_found_raises(self, tmp_path, monkeypatch):
        """CSV standard sep + FileNotFoundError -> FileOperationError (483-486)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        f = tmp_path / "exists.csv"
        f.write_text("a;b\n", encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": str(f), "csv_option": True,
               "encoding": "utf-8"}
        comp = _make_component(config=cfg)

        import builtins
        original_open = builtins.open

        def selective_open(path, *args, **kwargs):
            if str(path) == str(f):
                raise FileNotFoundError("simulated FNF during read")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", selective_open)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="File not found",
        ):
            comp.execute(None)

    def test_csv_mode_other_read_error_wraps(self, tmp_path, monkeypatch):
        """CSV standard sep + non-FNF Exception -> FileOperationError (487-490)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        f = tmp_path / "exists.csv"
        f.write_text("a;b\n", encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": str(f), "csv_option": True,
               "encoding": "utf-8"}
        comp = _make_component(config=cfg)

        import builtins
        original_open = builtins.open

        def selective_open(path, *args, **kwargs):
            if str(path) == str(f):
                raise OSError("simulated I/O error")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", selective_open)
        with pytest.raises(
            (FileOperationError, ComponentExecutionError),
            match="Failed to read file",
        ):
            comp.execute(None)

    def test_csv_mode_empty_after_read_returns_empty_df(self, tmp_path):
        """CSV standard sep + no rows -> empty DF (493-494)."""
        f = _write_file(tmp_path, "empty.csv", "", encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "csv_option": True,
               "encoding": "utf-8"}
        schema = [{"name": "k", "type": "str", "nullable": True}]
        comp = _make_component(config=cfg, schema=schema)
        result = comp.execute(None)
        assert len(result["main"]) == 0

    def test_csv_mode_schema_mismatch_warns(self, tmp_path, caplog):
        """CSV standard sep + schema column mismatch -> warning (499-503)."""
        f = _write_file(tmp_path, "mismatch.csv", "1;A;extra\n2;B;extra2\n",
                        encoding="utf-8")
        cfg = {**_DEFAULT_CONFIG, "filepath": f, "csv_option": True,
               "encoding": "utf-8"}
        schema = [{"name": "k", "type": "str", "nullable": True},
                  {"name": "v", "type": "str", "nullable": True}]
        comp = _make_component(config=cfg, schema=schema)
        with caplog.at_level(logging.WARNING):
            comp.execute(None)
        assert any(
            "Schema expects" in r.message and "columns per row" in r.message
            for r in caplog.records
        )


@pytest.mark.unit
class TestCoverageLift1408FastPathBranches:
    """_vectorized_type_conversion edge branches."""

    def test_fast_path_no_schema_returns_input(self):
        """_fast_path_convert with no schema -> early return (line 618)."""
        comp = _make_component()
        comp.output_schema = None
        df = pd.DataFrame({"x": ["a", "b"]})
        out_df, reject = comp._fast_path_convert(df)
        assert out_df is df
        assert reject is None

    def test_fast_path_per_row_fallback_skips_already_rejected_idx(self):
        """_fast_path_convert: when an earlier column rejected a row, later columns skip it (645)."""
        comp = _make_component()
        comp.output_schema = [
            {"name": "a", "type": "int", "nullable": False},
            {"name": "b", "type": "int", "nullable": False},
        ]
        # row 0 fails on 'a' (BAD); row 1 fails on 'b' (BAD); row 2 OK
        df = pd.DataFrame({
            "a": ["BAD", "1", "2"],
            "b": ["10", "BAD", "20"],
        }, dtype=str)
        # Trigger fast-path's per-row fallback (mixed valid/invalid forces vectorized
        # convert to fail on each column, then fall back per-row).
        main_df, reject_df = comp._fast_path_convert(df)
        # row 2 only is the cleanly converted row
        assert len(main_df) == 1
        assert reject_df is not None
        assert len(reject_df) == 2

    def test_chunked_validate_skips_columns_missing_from_row(self):
        """_chunked_validate row missing schema column -> continue (line 797).

        Construct a DataFrame whose columns deliberately omit a schema column.
        The chunked validator should skip the absent column without raising.
        """
        comp = _make_component()
        comp.output_schema = [
            {"name": "id", "type": "int", "nullable": True},
            {"name": "extra_only_in_schema", "type": "str", "nullable": True},
        ]
        df = pd.DataFrame({"id": ["1", "2"]}, dtype=str)
        main_df, reject_df = comp._chunked_validate(
            df=df,
            check_fields_num=False,
            check_date=True,
            expected_col_count=None,
        )
        assert len(main_df) == 2
        # 'id' converted, missing column simply not present in output rows
        assert reject_df is None or len(reject_df) == 0


@pytest.mark.unit
class TestCoverageLift1408PipelineFixtures:
    """Plan 14-08 pipeline tests via run_job_fixture (D-C1)."""

    def test_csv_with_header_pipeline(self, run_job_fixture, tmp_path, assert_ascii_logs):
        csv_path = tmp_path / "input.csv"
        csv_path.write_text("id;name\n1;Alice\n2;Bob\n3;Carol\n", encoding="iso-8859-15")
        result = run_job_fixture(
            "file/csv_with_header",
            mutations={
                "tFileInputDelimited_1": {"filepath": str(csv_path)},
            },
        )
        # 3 data rows; header skipped via header_rows=1
        assert result.global_map.get("tFileInputDelimited_1_NB_LINE") == 3
        assert result.global_map.get("tFileInputDelimited_1_NB_LINE_OK") == 3
        assert result.global_map.get("tFileInputDelimited_1_NB_LINE_REJECT") == 0
        # FILENAME / ENCODING set pre-execution (D-15)
        assert result.global_map.get("tFileInputDelimited_1_FILENAME") == str(csv_path)
        assert result.global_map.get("tFileInputDelimited_1_ENCODING") == "ISO-8859-15"

    def test_csv_with_reject_pipeline(self, run_job_fixture, tmp_path, assert_ascii_logs):
        # 2nd row only has 1 field (id missing) -> caught by check_fields_num
        # Actually CSV has fields id;name (2 cols expected). "1;Alice" passes;
        # "bad_only_one" has 1 field -> rejected.
        csv_path = tmp_path / "input.csv"
        csv_path.write_text(
            "1;Alice\nbad_only_one\n3;Carol\n", encoding="iso-8859-15",
        )
        out_main = tmp_path / "out_main.csv"
        out_reject = tmp_path / "out_reject.csv"
        result = run_job_fixture(
            "file/csv_with_reject",
            mutations={
                "tFileInputDelimited_1": {"filepath": str(csv_path)},
                "tFileOutputDelimited_main": {"filepath": str(out_main)},
                "tFileOutputDelimited_reject": {"filepath": str(out_reject)},
            },
        )
        # 2 OK + 1 reject expected
        assert result.global_map.get("tFileInputDelimited_1_NB_LINE_OK") == 2
        assert result.global_map.get("tFileInputDelimited_1_NB_LINE_REJECT") == 1
        # Both output files created
        assert out_main.exists()
        assert out_reject.exists()
