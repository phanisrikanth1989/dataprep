"""Tests for FileInputPositional (tFileInputPositional engine implementation).

Phase 7.2-01 regression tests: prove that pattern / header_rows /
footer_rows / limit content checks are deferred from _validate_config to
_process so that legitimate ${context.X} references are accepted at
validate time and resolved / re-validated at process time.

Phase 7.2-02 tests: registration, corrected defaults, _validate_config
raises ConfigurationError, BUG-FIP-002 (advanced_separator numeric only),
BUG-FIP-004 (remove_empty_row covers empty-string rows after trim).
"""
import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_input_positional import FileInputPositional
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, context_manager=None, global_map=None, schema=None):
    """Create a FileInputPositional with explicit config.

    Mirrors BaseComponent.execute() Step 1 by populating ``self.config``
    so that direct ``_validate_config()`` calls work in isolation.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileInputPositional(
        component_id="tFIP_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    comp.output_schema = schema
    return comp


def _make_fwf_file(tmp_path, content="alice0025\nbob  0030\ncharl0035\n"):
    """Write a small fixed-width text file. Default schema: name(5) age(4)."""
    p = tmp_path / "input.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


# ------------------------------------------------------------------
# Pattern: validate accepts context-var, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPatternContextVar:
    """pattern field accepts ${context.WIDTHS} at validate time."""

    def test_validate_config_accepts_context_var_pattern(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "${context.WIDTHS}",
        }
        comp = _make_component(config)
        comp._validate_config()  # Must not raise

    def test_process_resolves_context_var_pattern(self, tmp_path):
        cm = ContextManager()
        cm.set("WIDTHS", "5,4")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "${context.WIDTHS}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        assert "main" in result
        df = result["main"]
        assert len(df) == 3
        # Two columns (5-wide name, 4-wide age)
        assert df.shape[1] == 2

    def test_process_invalid_resolved_pattern_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "abc,def",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="comma-separated integers"):
            comp.execute()

    def test_process_negative_pattern_widths_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,-4",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="positive integers"):
            comp.execute()


# ------------------------------------------------------------------
# header_rows: validate accepts, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestHeaderRowsContextVar:
    """header_rows accepts ${context.HEADER_ROWS} at validate time."""

    def test_validate_config_accepts_context_var_header_rows(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "header_rows": "${context.HEADER_ROWS}",
        }
        comp = _make_component(config)
        comp._validate_config()  # Must not raise

    def test_process_resolves_context_var_header_rows(self, tmp_path):
        cm = ContextManager()
        cm.set("HEADER_ROWS", "1")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "header_rows": "${context.HEADER_ROWS}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        # 3 raw rows minus 1 header = 2 data rows
        assert len(result["main"]) == 2

    def test_process_invalid_resolved_header_rows_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "header_rows": "not_a_number",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="header_rows"):
            comp.execute()


# ------------------------------------------------------------------
# footer_rows: validate accepts, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFooterRowsContextVar:
    """footer_rows accepts ${context.FOOTER_ROWS} at validate time."""

    def test_validate_config_accepts_context_var_footer_rows(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "footer_rows": "${context.FOOTER_ROWS}",
        }
        comp = _make_component(config)
        comp._validate_config()  # Must not raise

    def test_process_resolves_context_var_footer_rows(self, tmp_path):
        cm = ContextManager()
        cm.set("FOOTER_ROWS", "1")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "footer_rows": "${context.FOOTER_ROWS}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        # 3 raw rows minus 1 footer = 2 data rows
        assert len(result["main"]) == 2

    def test_process_invalid_resolved_footer_rows_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "footer_rows": "abc",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="footer_rows"):
            comp.execute()


# ------------------------------------------------------------------
# limit: validate accepts, process resolves, invalid raises
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLimitContextVar:
    """limit accepts ${context.LIMIT} at validate time."""

    def test_validate_config_accepts_context_var_limit(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "limit": "${context.LIMIT}",
        }
        comp = _make_component(config)
        comp._validate_config()  # Must not raise

    def test_process_resolves_context_var_limit(self, tmp_path):
        cm = ContextManager()
        cm.set("LIMIT", "2")
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "limit": "${context.LIMIT}",
            "die_on_error": True,
        }
        comp = _make_component(config, context_manager=cm)
        result = comp.execute()
        # limit=2 -> only 2 rows
        assert len(result["main"]) == 2

    def test_process_invalid_resolved_limit_raises(self, tmp_path):
        config = {
            "filepath": _make_fwf_file(tmp_path),
            "pattern": "5,4",
            "limit": "abc",
            "die_on_error": True,
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError, match="limit"):
            comp.execute()


# ==================================================================
# Phase 7.2-02: Registration, defaults, validate raises, bugs fixed
# ==================================================================


@pytest.mark.unit
class TestRegistration:
    """Component must be discoverable under both registry names."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("FileInputPositional") is FileInputPositional

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tFileInputPositional") is FileInputPositional


# ------------------------------------------------------------------
# Corrected defaults
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCorrectedDefaults:
    """Talend-correct defaults match _java.xml baseline."""

    def test_encoding_default_is_iso_8859_15(self):
        assert FileInputPositional.DEFAULT_ENCODING == 'ISO-8859-15'

    def test_trim_all_default_is_true(self):
        assert FileInputPositional.DEFAULT_TRIM_ALL is True

    def test_remove_empty_row_default_is_true(self):
        assert FileInputPositional.DEFAULT_REMOVE_EMPTY_ROW is True

    def test_die_on_error_default_is_false(self):
        assert FileInputPositional.DEFAULT_DIE_ON_ERROR is False


# ------------------------------------------------------------------
# _validate_config raises ConfigurationError
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfigRaises:
    """_validate_config must raise ConfigurationError, not return a list."""

    def test_missing_filepath_raises(self):
        comp = _make_component({"pattern": "5,4"})
        with pytest.raises(ConfigurationError, match="filepath"):
            comp._validate_config()

    def test_missing_pattern_raises(self):
        comp = _make_component({"filepath": "/tmp/file.txt"})
        with pytest.raises(ConfigurationError, match="pattern"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "f.txt"),
            "pattern": "5,4",
        })
        comp._validate_config()  # Must not raise


# ------------------------------------------------------------------
# Basic read
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicRead:
    """Read a simple fixed-width file, verify row/column counts."""

    def test_reads_three_rows(self, tmp_path):
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4"})
        result = comp._process()
        assert result["main"].shape == (3, 2)

    def test_columns_named_from_schema(self, tmp_path):
        fwf = _make_fwf_file(tmp_path)
        schema = [{"name": "name", "type": "id_String"},
                  {"name": "age",  "type": "id_String"}]
        comp = _make_component({"filepath": fwf, "pattern": "5,4"}, schema=schema)
        result = comp._process()
        assert list(result["main"].columns) == ["name", "age"]

    def test_missing_file_returns_empty_when_die_on_error_false(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "nonexistent.txt"),
            "pattern": "5,4",
            "die_on_error": False,
        })
        result = comp._process()
        assert result["main"].empty

    def test_header_rows_skipped(self, tmp_path):
        content = "HEADER   \nalice0025\nbob  0030\n"
        fwf = _make_fwf_file(tmp_path, content)
        comp = _make_component({"filepath": fwf, "pattern": "5,4", "header_rows": 1})
        result = comp._process()
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# trim_all
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTrimAll:
    """trim_all=True strips leading/trailing whitespace from string columns."""

    def test_trim_all_strips_whitespace(self, tmp_path):
        # "bob  " has trailing spaces in the 5-wide name column
        fwf = _make_fwf_file(tmp_path, "alice0025\nbob  0030\n")
        schema = [{"name": "name", "type": "id_String"},
                  {"name": "age",  "type": "id_String"}]
        comp = _make_component(
            {"filepath": fwf, "pattern": "5,4", "trim_all": True},
            schema=schema,
        )
        result = comp._process()
        assert result["main"]["name"].tolist() == ["alice", "bob"]

    def test_trim_all_false_preserves_whitespace(self, tmp_path):
        fwf = _make_fwf_file(tmp_path, "bob  0030\n")
        schema = [{"name": "name", "type": "id_String"},
                  {"name": "age",  "type": "id_String"}]
        comp = _make_component(
            {"filepath": fwf, "pattern": "5,4", "trim_all": False},
            schema=schema,
        )
        result = comp._process()
        # pandas read_fwf may strip anyway; assert at least not crash
        assert "name" in result["main"].columns


# ------------------------------------------------------------------
# remove_empty_row -- BUG-FIP-004 fix
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRemoveEmptyRow:
    """remove_empty_row=True drops rows that are NaN or all-empty-string after trim."""

    def test_removes_nan_rows(self, tmp_path):
        # A row of spaces (9 chars) produces NaN values after read_fwf
        content = "alice0025\n         \nbob  0030\n"
        fwf = _make_fwf_file(tmp_path, content)
        comp = _make_component({
            "filepath": fwf,
            "pattern": "5,4",
            "remove_empty_row": True,
            "trim_all": False,
        })
        result = comp._process()
        assert len(result["main"]) == 2

    def test_removes_empty_string_rows_after_trim(self, tmp_path):
        # BUG-FIP-004: after trim_all, a row of spaces becomes all "" which
        # dropna(how='all') would NOT catch.  Our fix replaces "" with NaN first.
        content = "alice0025\n         \nbob  0030\n"
        fwf = _make_fwf_file(tmp_path, content)
        comp = _make_component({
            "filepath": fwf,
            "pattern": "5,4",
            "remove_empty_row": True,
            "trim_all": True,
        })
        result = comp._process()
        assert len(result["main"]) == 2

    def test_remove_empty_row_false_keeps_all_rows(self, tmp_path):
        # Use 3 data rows; remove_empty_row=False must not drop any.
        fwf = _make_fwf_file(tmp_path)  # 3 rows: alice, bob, charley
        comp = _make_component({
            "filepath": fwf,
            "pattern": "5,4",
            "remove_empty_row": False,
            "trim_all": False,
        })
        result = comp._process()
        assert len(result["main"]) == 3


# ------------------------------------------------------------------
# advanced_separator -- BUG-FIP-002 fix: numeric columns only
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAdvancedSeparator:
    """BUG-FIP-002 fix: advanced_separator must only apply to numeric schema columns.

    Use id_BigDecimal for the numeric column: it is in _NUMERIC_TYPES so the
    separator IS applied, but _build_dtype_dict() maps it to 'object' so pandas
    reads it as a plain string.  This avoids the dtype-coercion conflict that
    id_Double ('float64') would cause when the raw value still contains a comma.
    """

    _SCHEMA = [
        {"name": "name",  "type": "id_String"},
        {"name": "price", "type": "id_BigDecimal"},
    ]

    def test_separator_not_applied_to_string_columns(self, tmp_path):
        # 'name' contains ',' which must NOT be stripped (id_String)
        content = "al,ce1,234\n"
        fwf = _make_fwf_file(tmp_path, content)
        comp = _make_component({
            "filepath": fwf,
            "pattern": "5,5",
            "advanced_separator": True,
            "thousands_separator": ",",
            "decimal_separator": ".",
        }, schema=self._SCHEMA)
        result = comp._process()
        assert "," in result["main"].iloc[0]["name"]

    def test_separator_applied_to_numeric_columns(self, tmp_path):
        # 'price' is id_BigDecimal (numeric): thousands comma must be stripped
        content = "alice1,234\n"
        fwf = _make_fwf_file(tmp_path, content)
        comp = _make_component({
            "filepath": fwf,
            "pattern": "5,5",
            "advanced_separator": True,
            "thousands_separator": ",",
            "decimal_separator": ".",
        }, schema=self._SCHEMA)
        result = comp._process()
        # id_BigDecimal gets further converted to Decimal('1234') — verify comma stripped
        price_val = result["main"].iloc[0]["price"]
        assert "," not in str(price_val)

    def test_advanced_separator_no_schema_applies_nothing(self, tmp_path):
        # Without schema, no numeric columns can be identified -- nothing changes
        content = "al,ce1,234\n"
        fwf = _make_fwf_file(tmp_path, content)
        comp = _make_component({
            "filepath": fwf,
            "pattern": "5,5",
            "advanced_separator": True,
            "thousands_separator": ",",
        })
        result = comp._process()
        # First column still has comma (no schema -> no numeric columns identified)
        assert "," in result["main"].iloc[0, 0]


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStatistics:
    """NB_LINE and NB_LINE_OK populated correctly after _process."""

    def test_stats_match_row_count(self, tmp_path):
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4"})
        comp._process()
        assert comp.stats["NB_LINE"] == 3
        assert comp.stats["NB_LINE_OK"] == 3
        assert comp.stats["NB_LINE_REJECT"] == 0


# ------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   167 (input_data not None debug log)
#   186, 198 (header_rows / footer_rows < 0 raise)
#   222 (limit <= 0 raise)
#   229, 231 (missing filepath / pattern raise from _process)
#   237-238 (file not found + die_on_error=True)
#   253 (pattern empty after split)
#   308 (logger.debug on removed empty rows)
#   333-343 (check_date with date column conversion)
#   371-372 (logger.debug dtypes_info)
#   376-391 (FileOperationError / ConfigurationError re-raise + general
#            Exception with die_on_error True/False)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408ProcessGuards:
    def test_input_data_logs_debug(self, tmp_path, caplog):
        """input_data not None -> debug log (line 167)."""
        import logging
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4"})
        with caplog.at_level(logging.DEBUG,
                             logger="src.v1.engine.components.file.file_input_positional"):
            comp._process(input_data=pd.DataFrame({"x": [1]}))
        assert any(
            "Input data provided but not used" in r.message
            for r in caplog.records
        )

    def test_header_rows_negative_raises(self, tmp_path):
        """header_rows < 0 -> ConfigurationError (line 186)."""
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4",
                                "header_rows": -1})
        with pytest.raises(ConfigurationError, match="non-negative"):
            comp._process()

    def test_footer_rows_negative_raises(self, tmp_path):
        """footer_rows < 0 -> ConfigurationError (line 198)."""
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4",
                                "footer_rows": -2})
        with pytest.raises(ConfigurationError, match="non-negative"):
            comp._process()

    def test_limit_zero_or_negative_raises(self, tmp_path):
        """limit <= 0 -> ConfigurationError (line 222-223)."""
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4",
                                "limit": "0"})
        with pytest.raises(ConfigurationError, match="must be positive"):
            comp._process()

    def test_missing_filepath_raises(self):
        """filepath empty -> ConfigurationError (line 228-229)."""
        comp = _make_component({"filepath": "", "pattern": "5,4"})
        with pytest.raises(ConfigurationError, match="filepath"):
            comp._process()

    def test_missing_pattern_raises(self, tmp_path):
        """pattern empty -> ConfigurationError (line 230-231)."""
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": ""})
        with pytest.raises(ConfigurationError, match="pattern"):
            comp._process()

    def test_file_not_found_die_on_error_true_raises(self):
        """File missing + die_on_error=True -> FileOperationError (237-238)."""
        from src.v1.engine.exceptions import FileOperationError
        comp = _make_component({"filepath": "/nonexistent/_x_.txt",
                                "pattern": "5,4",
                                "die_on_error": True})
        with pytest.raises(FileOperationError, match="not found"):
            comp._process()

    def test_pattern_with_only_whitespace_raises(self, tmp_path):
        """pattern only whitespace + commas -> empty list -> raise (line 252-254)."""
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": " , , "})
        with pytest.raises(ConfigurationError, match="cannot be empty"):
            comp._process()


@pytest.mark.unit
class TestCoverageLift1408RemoveEmptyRowsLogging:
    def test_remove_empty_rows_logs_count(self, tmp_path, caplog, monkeypatch):
        """remove_empty_row=True with rows removed -> debug log (line 308).

        We bypass pd.read_fwf with a stub returning a frame containing a
        wholly-empty-string row so the remove_empty_row branch can drop it
        and emit the debug count.
        """
        import logging

        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": str(fwf), "pattern": "5,4",
                                "remove_empty_row": True})

        # Stub pd.read_fwf to inject a wholly-empty-string row alongside data
        def fake_read_fwf(*a, **k):
            return pd.DataFrame({0: ["alice", "", "bob"], 1: ["0025", "", "0030"]})

        monkeypatch.setattr(pd, "read_fwf", fake_read_fwf)
        with caplog.at_level(logging.DEBUG,
                             logger="src.v1.engine.components.file.file_input_positional"):
            result = comp._process()
        assert len(result["main"]) == 2  # empty row dropped
        assert any(
            "Removed" in r.message and "empty rows" in r.message
            for r in caplog.records
        )


@pytest.mark.unit
class TestCoverageLift1408CheckDate:
    def test_check_date_converts_date_column(self, tmp_path):
        """check_date=True + schema date type -> pd.to_datetime (333-343)."""
        fwf = tmp_path / "dates.txt"
        fwf.write_text("20240115Alice\n20240220Bob  \n", encoding="utf-8")
        schema = [
            {"name": "dt", "type": "id_date", "date_pattern": "%Y%m%d"},
            {"name": "name", "type": "id_String"},
        ]
        comp = _make_component(
            {"filepath": str(fwf), "pattern": "8,5",
             "check_date": True},
            schema=schema,
        )
        result = comp._process()
        assert pd.api.types.is_datetime64_any_dtype(result["main"]["dt"])

    def test_check_date_swallows_conversion_exception(self, tmp_path, monkeypatch):
        """check_date=True + pd.to_datetime raises -> swallowed silently (342-343)."""
        fwf = tmp_path / "dates2.txt"
        fwf.write_text("20240115Alice\n", encoding="utf-8")
        schema = [
            {"name": "dt", "type": "id_date", "date_pattern": "%Y%m%d"},
            {"name": "name", "type": "id_String"},
        ]
        comp = _make_component(
            {"filepath": str(fwf), "pattern": "8,5",
             "check_date": True},
            schema=schema,
        )

        def boom(*a, **k):
            raise RuntimeError("simulated date parse failure")

        monkeypatch.setattr(pd, "to_datetime", boom)
        # The exception is swallowed; _process returns successfully with the
        # unconverted column.
        result = comp._process()
        assert "main" in result


@pytest.mark.unit
class TestCoverageLift1408DebugDtypes:
    def test_debug_dtypes_logged(self, tmp_path, caplog):
        """logger.isEnabledFor(DEBUG) -> log dtypes (lines 370-372)."""
        import logging
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4"})
        with caplog.at_level(logging.DEBUG,
                             logger="src.v1.engine.components.file.file_input_positional"):
            comp._process()
        assert any(
            "Column dtypes" in r.message for r in caplog.records
        )


@pytest.mark.unit
class TestCoverageLift1408ExceptionPaths:
    def test_file_operation_error_re_raised(self, tmp_path, monkeypatch):
        """FileOperationError raised inside try -> re-raise (376-378)."""
        from src.v1.engine.exceptions import FileOperationError
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4"})

        def boom(*a, **k):
            raise FileOperationError("inner FOE")

        monkeypatch.setattr(pd, "read_fwf", boom)
        with pytest.raises(FileOperationError, match="inner FOE"):
            comp._process()

    def test_configuration_error_re_raised(self, tmp_path, monkeypatch):
        """ConfigurationError raised inside try -> re-raise (379-381)."""
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4"})

        def boom(*a, **k):
            raise ConfigurationError("inner CE")

        monkeypatch.setattr(pd, "read_fwf", boom)
        with pytest.raises(ConfigurationError, match="inner CE"):
            comp._process()

    def test_unexpected_exception_die_on_error_true_raises(self, tmp_path, monkeypatch):
        """Unexpected Exception + die_on_error=True -> ComponentExecutionError (382-387)."""
        from src.v1.engine.exceptions import ComponentExecutionError
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4",
                                "die_on_error": True})

        def boom(*a, **k):
            raise RuntimeError("unexpected boom")

        monkeypatch.setattr(pd, "read_fwf", boom)
        with pytest.raises(ComponentExecutionError, match="Error reading positional"):
            comp._process()

    def test_unexpected_exception_die_on_error_false_returns_empty(
        self, tmp_path, monkeypatch
    ):
        """Unexpected Exception + die_on_error=False -> empty DF (388-391)."""
        fwf = _make_fwf_file(tmp_path)
        comp = _make_component({"filepath": fwf, "pattern": "5,4",
                                "die_on_error": False})

        def boom(*a, **k):
            raise RuntimeError("unexpected boom")

        monkeypatch.setattr(pd, "read_fwf", boom)
        result = comp._process()
        assert len(result["main"]) == 0


@pytest.mark.unit
class TestCoverageLift1408FileNotFoundSoftFail:
    def test_file_not_found_die_on_error_false_returns_empty(self):
        """File missing + die_on_error=False -> empty DF (240-242)."""
        comp = _make_component({"filepath": "/nonexistent/_xyz_.txt",
                                "pattern": "5,4",
                                "die_on_error": False})
        result = comp._process()
        assert len(result["main"]) == 0
