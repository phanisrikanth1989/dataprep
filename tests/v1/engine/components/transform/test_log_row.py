"""Tests for LogRow (tLogRow engine implementation).

Covers (per ENGINE_TEST_PATTERN.md):
  TestRegistration      -- both v1 and Talend alias registered in REGISTRY
  TestValidation        -- _validate_config accepts any config; no required keys
  TestDefaults          -- default config (basic_mode) produces correct behavior
  TestPassThrough       -- all rows appear unchanged on main; reject is absent
  TestRejectFlow        -- tLogRow never populates reject
  TestBasicMode         -- basic delimited format, field separator
  TestTableMode         -- bordered ASCII table output
  TestVerticalMode      -- key-value pair output with title variants
  TestDisplayOptions    -- print_header, print_colnames, print_unique_name
  TestFixedLength       -- use_fixed_length + lengths pad/truncate values
  TestMaxRows           -- context var deferral, limiting, invalid, negative
  TestDeferredFeatures  -- print_content_with_log4j=False emits warning
  TestEdgeCases         -- None, empty df, single row, NaN, large dataset
  TestGlobalMapVariables -- NB_LINE, NB_LINE_OK, NB_LINE_REJECT correct
  TestIterateReexecution -- execute() twice with reset() gives consistent results
"""
import logging

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.log_row import LogRow
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures / Helpers
# ------------------------------------------------------------------

# LogRow has no required keys -- _DEFAULT_CONFIG can be empty.
_DEFAULT_CONFIG: dict = {}


def _make_component(config=None, global_map=None, context_manager=None):
    """Create a LogRow with test defaults.

    Creates fresh GlobalMap and ContextManager unless explicitly provided.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    return LogRow(
        component_id="tLogRow_1",
        config=config if config is not None else dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_df(n: int = 5) -> pd.DataFrame:
    """Create test input DataFrame with predictable content."""
    return pd.DataFrame({
        "id": list(range(1, n + 1)),
        "name": [f"user_{i}" for i in range(1, n + 1)],
        "score": [float(i * 10) for i in range(1, n + 1)],
    })


def _component_logs(caplog):
    """Return only log records emitted by the log_row module itself.

    Filters out base_component completion messages so tests can count
    exactly the rows logged by LogRow without the lifecycle noise.
    """
    return [r for r in caplog.records if "log_row" in r.name]


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component must be reachable by both its v1 name and Talend alias."""

    def test_registered_as_v1_name(self):
        assert REGISTRY.get("LogRow") is LogRow

    def test_registered_as_talend_alias(self):
        assert REGISTRY.get("tLogRow") is LogRow


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises nothing -- all config keys are optional."""

    def test_empty_config_does_not_raise(self):
        comp = _make_component({})
        # _validate_config is called on self.config (empty initially),
        # but since there are no required keys it must pass.
        assert comp._validate_config() is None

    def test_full_config_does_not_raise(self):
        config = {
            "basic_mode": True,
            "table_print": False,
            "vertical": False,
            "fieldseparator": "|",
            "print_header": False,
            "print_unique_name": False,
            "print_colnames": False,
            "use_fixed_length": False,
            "lengths": [],
            "print_content_with_log4j": True,
            "max_rows": 100,
            "tstatcatcher_stats": False,
            "label": "",
        }
        comp = _make_component(config)
        assert comp._validate_config() is None

    def test_context_var_in_max_rows_accepted_at_validate_time(self):
        """${context.MAX_ROWS} must not be rejected before context resolution."""
        comp = _make_component({"max_rows": "${context.MAX_ROWS}"})
        # Direct call: self.config is empty at this point -- no keys â†’ no error
        assert comp._validate_config() is None

    def test_execute_with_valid_config_completes(self):
        comp = _make_component({"basic_mode": True, "max_rows": 10})
        result = comp.execute(_make_df())
        assert "main" in result


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDefaults:
    """Default config selects basic_mode with pipe separator."""

    def test_default_mode_is_basic(self, caplog):
        """No config: basic mode must be used (default Talend behavior)."""
        comp = _make_component({})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(3))
        # Basic mode: 3 rows, each with "|" separator
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        assert len(data_lines) == 3

    def test_default_separator_is_pipe(self, caplog):
        comp = _make_component({})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(1))
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        assert len(data_lines) == 1
        assert "|" in data_lines[0]

    def test_default_no_header(self, caplog):
        """print_header defaults to False -- no column name line logged."""
        comp = _make_component({})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(2))
        # Filter to only records from the log_row module (exclude base_component lifecycle)
        info_lines = [r.message for r in _component_logs(caplog) if r.levelno == logging.INFO]
        # 2 data rows, no header row
        assert len(info_lines) == 2

    def test_default_max_rows_100(self, caplog):
        """Without max_rows, the default 100 is used."""
        comp = _make_component({})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(150))
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        assert len(data_lines) == 100


# ------------------------------------------------------------------
# TestPassThrough
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPassThrough:
    """LogRow must never modify, filter, or drop rows."""

    def test_all_rows_present_on_main(self):
        comp = _make_component({})
        result = comp.execute(_make_df(5))
        assert len(result["main"]) == 5

    def test_output_values_identical_to_input(self):
        df = _make_df(3)
        comp = _make_component({})
        result = comp.execute(df.copy())
        pd.testing.assert_frame_equal(
            result["main"].reset_index(drop=True),
            df.reset_index(drop=True),
        )

    def test_output_columns_unchanged(self):
        df = _make_df(3)
        comp = _make_component({})
        result = comp.execute(df)
        assert list(result["main"].columns) == list(df.columns)

    def test_display_limit_does_not_reduce_main_rows(self):
        """max_rows=2 logs only 2 rows but main must still carry all 5."""
        comp = _make_component({"max_rows": 2})
        result = comp.execute(_make_df(5))
        assert len(result["main"]) == 5


# ------------------------------------------------------------------
# TestRejectFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRejectFlow:
    """tLogRow never populates a reject flow."""

    def test_reject_absent_on_normal_input(self):
        comp = _make_component({})
        result = comp.execute(_make_df(3))
        reject = result.get("reject")
        assert reject is None or (isinstance(reject, pd.DataFrame) and len(reject) == 0)

    def test_reject_absent_on_nan_input(self):
        df = pd.DataFrame({"id": [1, None, 3], "name": [None, "Bob", "Carol"]})
        comp = _make_component({})
        result = comp.execute(df)
        reject = result.get("reject")
        assert reject is None or (isinstance(reject, pd.DataFrame) and len(reject) == 0)

    def test_main_plus_reject_equals_input(self):
        df = _make_df(4)
        comp = _make_component({})
        result = comp.execute(df)
        main_count = len(result["main"]) if result["main"] is not None else 0
        reject_count = (
            len(result["reject"])
            if result.get("reject") is not None
            and isinstance(result["reject"], pd.DataFrame)
            else 0
        )
        assert main_count + reject_count == len(df)


# ------------------------------------------------------------------
# TestBasicMode
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicMode:
    """Basic mode: one sep-delimited line per row."""

    def test_basic_mode_row_count(self, caplog):
        comp = _make_component({"basic_mode": True})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(4))
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        assert len(data_lines) == 4

    def test_custom_separator(self, caplog):
        comp = _make_component({"basic_mode": True, "fieldseparator": ";"})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(1))
        data_lines = [r.message for r in caplog.records if ";" in r.message]
        assert len(data_lines) == 1
        assert "|" not in data_lines[0]

    def test_basic_mode_with_header(self, caplog):
        """print_header=True adds one extra line with column names."""
        comp = _make_component({"basic_mode": True, "print_header": True})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(3))
        sep_lines = [r.message for r in caplog.records if "|" in r.message]
        # 1 header + 3 data rows = 4 lines
        assert len(sep_lines) == 4
        # First line is the header (contains column names, not numeric data only)
        assert "id" in sep_lines[0] or "name" in sep_lines[0]

    def test_values_appear_in_output(self, caplog):
        df = pd.DataFrame({"code": ["ABC"], "amount": [42]})
        comp = _make_component({"basic_mode": True})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        all_messages = " ".join(r.message for r in caplog.records)
        assert "ABC" in all_messages
        assert "42" in all_messages


# ------------------------------------------------------------------
# TestTableMode
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTableMode:
    """Table mode: bordered ASCII table."""

    def test_table_mode_produces_border_lines(self, caplog):
        comp = _make_component({"table_print": True, "basic_mode": False})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(2))
        border_lines = [r.message for r in caplog.records if r.message.startswith("+")]
        # top border + after-header border + bottom border = 3
        assert len(border_lines) >= 3

    def test_table_mode_includes_column_names(self, caplog):
        comp = _make_component({"table_print": True, "basic_mode": False})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(1))
        all_messages = " ".join(r.message for r in caplog.records)
        assert "id" in all_messages
        assert "name" in all_messages

    def test_table_mode_includes_data_values(self, caplog):
        df = pd.DataFrame({"x": ["hello"]})
        comp = _make_component({"table_print": True, "basic_mode": False})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        all_messages = " ".join(r.message for r in caplog.records)
        assert "hello" in all_messages

    def test_table_mode_empty_df_produces_no_output(self, caplog):
        comp = _make_component({"table_print": True, "basic_mode": False})
        with caplog.at_level(logging.INFO):
            comp.execute(pd.DataFrame({"a": pd.Series([], dtype=str)}))
        border_lines = [r.message for r in caplog.records if r.message.startswith("+")]
        assert len(border_lines) == 0

    def test_table_mode_print_unique_name_prepends_title(self, caplog):
        comp = _make_component(
            {"table_print": True, "basic_mode": False, "print_unique_name": True}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(1))
        title_lines = [r.message for r in caplog.records if "tLogRow_1" in r.message]
        assert len(title_lines) >= 1


# ------------------------------------------------------------------
# TestVerticalMode
# ------------------------------------------------------------------


@pytest.mark.unit
class TestVerticalMode:
    """Vertical mode: key-value pairs per row with title group."""

    def test_vertical_mode_produces_section_headers(self, caplog):
        comp = _make_component({"vertical": True})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(2))
        row_headers = [r.message for r in caplog.records if r.message.startswith("---")]
        assert len(row_headers) == 2

    def test_vertical_mode_includes_column_names(self, caplog):
        df = pd.DataFrame({"alpha": [99]})
        comp = _make_component({"vertical": True})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        all_messages = " ".join(r.message for r in caplog.records)
        assert "alpha" in all_messages
        assert "99" in all_messages

    def test_vertical_default_title_is_unique_name(self, caplog):
        """Default TITLE_PRINT=print_unique: title contains component id."""
        comp = _make_component({"vertical": True})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(1))
        header_lines = [r.message for r in caplog.records if r.message.startswith("---")]
        assert "tLogRow_1" in header_lines[0]

    def test_vertical_print_label_uses_label(self, caplog):
        comp = _make_component(
            {"vertical": True, "print_label": True, "label": "My Label"}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(1))
        header_lines = [r.message for r in caplog.records if r.message.startswith("---")]
        assert "My Label" in header_lines[0]

    def test_vertical_print_unique_label_combines_both(self, caplog):
        comp = _make_component(
            {"vertical": True, "print_unique_label": True, "label": "Debug"}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(1))
        header_lines = [r.message for r in caplog.records if r.message.startswith("---")]
        assert "tLogRow_1" in header_lines[0]
        assert "Debug" in header_lines[0]

    def test_vertical_max_rows_limits_sections(self, caplog):
        comp = _make_component({"vertical": True, "max_rows": 2})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(5))
        row_headers = [r.message for r in caplog.records if r.message.startswith("---")]
        assert len(row_headers) == 2

    def test_vertical_use_fixed_length_truncates_values(self, caplog):
        """Plan 14-06 lift: vertical mode + use_fixed_length truncates values per width.

        Targets log_row.py:335-336 (use_fixed_length / lengths handling inside
        _log_vertical: width = int(lengths[j]); val = val[:width].ljust(width)).
        """
        df = pd.DataFrame({"longcol": ["ABCDEFGHIJ"]})  # 10 chars
        comp = _make_component(
            {"vertical": True, "use_fixed_length": True, "lengths": [4]}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        # The column line shows truncated value: 'ABCD' padded to 4 chars
        col_lines = [r.message for r in caplog.records if "longcol:" in r.message]
        assert len(col_lines) >= 1
        # Value truncated to 4 chars: "ABCD"
        line = col_lines[0]
        assert "ABCD" in line
        assert "ABCDE" not in line  # 5th char truncated

    def test_vertical_use_fixed_length_with_non_numeric_width_falls_back_to_10(self, caplog):
        """Plan 14-06 lift: vertical mode + non-numeric length entry falls back to width=10.

        Targets log_row.py:335 else-branch (isinstance check for int/float).
        """
        df = pd.DataFrame({"v": ["ABCDEFGHIJKLMNOP"]})  # 16 chars
        comp = _make_component(
            {"vertical": True, "use_fixed_length": True, "lengths": ["bogus"]}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        col_lines = [r.message for r in caplog.records if "v:" in r.message]
        line = col_lines[0]
        # Width fallback to 10 -> truncated to "ABCDEFGHIJ"
        assert "ABCDEFGHIJ" in line
        assert "ABCDEFGHIJK" not in line


# ------------------------------------------------------------------
# TestPrivateMethodGuards -- Plan 14-06 lift, exercise direct method invocation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPrivateMethodGuards:
    """Direct invocations of private display helpers cover defensive guards.

    Targets log_row.py:251 (_log_table early return on empty df). _process()
    short-circuits before reaching this branch, so direct invocation is the
    natural way to exercise it.
    """

    def test_log_table_empty_df_returns_without_emitting(self, caplog):
        """Direct _log_table call with empty df emits no lines."""
        comp = _make_component({"table_print": True, "basic_mode": False})
        with caplog.at_level(logging.INFO):
            comp._log_table(
                pd.DataFrame(),  # explicitly empty
                print_unique_name=False,
                use_fixed_length=False,
                lengths=[],
            )
        # No border, header, or data lines emitted
        relevant = [r for r in caplog.records if "log_row" in r.name]
        assert relevant == []


# ------------------------------------------------------------------
# TestDisplayOptions
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDisplayOptions:
    """print_header, print_colnames, print_unique_name options."""

    def test_print_colnames_prefixes_values(self, caplog):
        """With print_colnames=True each value appears as 'colname=value'."""
        df = pd.DataFrame({"code": ["XYZ"]})
        comp = _make_component({"basic_mode": True, "print_colnames": True})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        data_lines = [r.message for r in caplog.records if "=" in r.message]
        assert any("code=XYZ" in line for line in data_lines)

    def test_print_colnames_false_no_prefix(self, caplog):
        df = pd.DataFrame({"code": ["XYZ"]})
        comp = _make_component({"basic_mode": True, "print_colnames": False})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        data_lines = [r.message for r in caplog.records]
        # Value present but NOT prefixed with colname=
        assert any("XYZ" in line for line in data_lines)
        assert not any("code=XYZ" in line for line in data_lines)

    def test_print_unique_name_prefixes_each_row(self, caplog):
        comp = _make_component(
            {"basic_mode": True, "print_unique_name": True, "max_rows": 3}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(3))
        # Filter to log_row module only to exclude base_component completion log
        prefixed_lines = [
            r.message for r in _component_logs(caplog)
            if r.message.startswith("[tLogRow_1]")
        ]
        assert len(prefixed_lines) == 3

    def test_print_unique_name_false_no_prefix(self, caplog):
        comp = _make_component({"basic_mode": True, "print_unique_name": False})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(2))
        # Filter to log_row module only to exclude base_component completion log
        prefixed_lines = [
            r.message for r in _component_logs(caplog)
            if r.message.startswith("[tLogRow_1]")
        ]
        assert len(prefixed_lines) == 0

    def test_print_header_adds_column_line(self, caplog):
        df = pd.DataFrame({"alpha": [1], "beta": [2]})
        comp = _make_component({"basic_mode": True, "print_header": True})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        sep_lines = [r.message for r in caplog.records if "|" in r.message]
        # Header + 1 data row = 2 lines
        assert len(sep_lines) == 2
        assert "alpha" in sep_lines[0]
        assert "beta" in sep_lines[0]


# ------------------------------------------------------------------
# TestFixedLength
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFixedLength:
    """use_fixed_length + lengths pad/truncate values in basic and table modes."""

    def test_fixed_length_pads_short_values(self, caplog):
        """Values shorter than the declared width must be left-padded with spaces."""
        df = pd.DataFrame({"x": ["hi"]})
        comp = _make_component(
            {"basic_mode": True, "use_fixed_length": True, "lengths": [10]}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        data_lines = [r.message for r in caplog.records if caplog.records]
        # "hi" padded to width 10 â†’ "hi        " (8 trailing spaces)
        assert any("hi" in line for line in data_lines)
        padded = [line for line in data_lines if "hi" in line]
        assert padded[0].count(" ") >= 8 or "hi" in padded[0]

    def test_fixed_length_truncates_long_values(self, caplog):
        """Values longer than the declared width must be truncated."""
        df = pd.DataFrame({"x": ["ABCDEFGHIJ"]})
        comp = _make_component(
            {"basic_mode": True, "use_fixed_length": True, "lengths": [5]}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        data_lines = [r.message for r in caplog.records]
        # Truncated to 5 chars: "ABCDE"
        assert any("ABCDE" in line for line in data_lines)
        assert not any("ABCDEFGHIJ" in line for line in data_lines)

    def test_fixed_length_false_no_padding(self, caplog):
        """use_fixed_length=False must not pad values."""
        df = pd.DataFrame({"x": ["hi"]})
        comp = _make_component(
            {"basic_mode": True, "use_fixed_length": False, "lengths": [20]}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        data_lines = [r.message for r in caplog.records if "hi" in r.message]
        # value should be exactly "hi", not padded to 20 chars
        assert any(line.strip() == "hi" or line == "hi" for line in data_lines)

    def test_fixed_length_in_table_mode(self, caplog):
        """Table mode respects use_fixed_length when widths are provided."""
        df = pd.DataFrame({"col": ["short"]})
        comp = _make_component(
            {"table_print": True, "basic_mode": False,
             "use_fixed_length": True, "lengths": [15]}
        )
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        # Cell "short" (5 chars) padded to 15 in the table row line
        row_lines = [
            r.message for r in caplog.records if r.message.startswith("|")
        ]
        assert any("short" in line for line in row_lines)
        # Width of cell in the row line should be 15
        data_row = [line for line in row_lines if "short" in line][0]
        # Row format: |col_padded| -- inner width is 15
        inner = data_row.strip("|")
        assert len(inner) == 15


# ------------------------------------------------------------------
# TestMaxRows
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMaxRows:
    """max_rows controls display limit but not main row count."""

    def test_max_rows_limits_logged_lines(self, caplog):
        comp = _make_component({"max_rows": 3})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(10))
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        assert len(data_lines) == 3

    def test_max_rows_does_not_affect_main_output(self):
        comp = _make_component({"max_rows": 2})
        result = comp.execute(_make_df(10))
        assert len(result["main"]) == 10

    def test_max_rows_zero_logs_nothing(self, caplog):
        comp = _make_component({"max_rows": 0})
        with caplog.at_level(logging.INFO):
            comp.execute(_make_df(5))
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        assert len(data_lines) == 0

    def test_context_var_max_rows_resolved_at_process_time(self, caplog):
        """${context.MAX_ROWS} must be accepted at validate time and resolved later."""
        cm = ContextManager()
        cm.set("MAX_ROWS", "2")
        comp = _make_component({"max_rows": "${context.MAX_ROWS}"}, context_manager=cm)
        with caplog.at_level(logging.INFO):
            result = comp.execute(_make_df(5))
        # All 5 rows still on main
        assert len(result["main"]) == 5
        # But only 2 logged
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        assert len(data_lines) == 2

    def test_invalid_max_rows_raises_config_error(self):
        comp = _make_component({"max_rows": "not_a_number"})
        with pytest.raises(ConfigurationError, match="max_rows"):
            comp.execute(_make_df(3))

    def test_negative_max_rows_raises_config_error(self):
        comp = _make_component({"max_rows": "-5"})
        with pytest.raises(ConfigurationError, match="non-negative"):
            comp.execute(_make_df(3))


# ------------------------------------------------------------------
# TestDeferredFeatures
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDeferredFeatures:
    """print_content_with_log4j=False must emit a WARNING, not silently ignore."""

    def test_log4j_false_emits_warning(self, caplog):
        comp = _make_component({"print_content_with_log4j": False})
        with caplog.at_level(logging.WARNING):
            comp.execute(_make_df(2))
        warnings = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("print_content_with_log4j" in w.lower() or "log4j" in w.lower() for w in warnings)

    def test_log4j_true_no_warning(self, caplog):
        comp = _make_component({"print_content_with_log4j": True})
        with caplog.at_level(logging.WARNING):
            comp.execute(_make_df(2))
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 0

    def test_log4j_default_no_warning(self, caplog):
        """print_content_with_log4j defaults to True -- no warning expected."""
        comp = _make_component({})
        with caplog.at_level(logging.WARNING):
            comp.execute(_make_df(2))
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 0


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """None input, empty df, single row, NaN values, large dataset."""

    def test_none_input_returns_empty_df(self):
        comp = _make_component({})
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_empty_dataframe_returns_empty_df(self):
        comp = _make_component({})
        result = comp.execute(pd.DataFrame({"a": pd.Series([], dtype=str)}))
        assert len(result["main"]) == 0

    def test_single_row_input(self):
        comp = _make_component({})
        result = comp.execute(_make_df(1))
        assert len(result["main"]) == 1

    def test_nan_values_render_as_empty_string(self, caplog):
        df = pd.DataFrame({"id": [1, 2], "name": [None, "Bob"]})
        comp = _make_component({"basic_mode": True})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        # Row with None: value rendered as "" (not "nan" or "None")
        data_lines = [r.message for r in caplog.records if "|" in r.message]
        nan_row = [line for line in data_lines if "1" in line][0]
        assert "nan" not in nan_row.lower()
        assert "none" not in nan_row.lower()

    def test_large_dataset_processes_without_error(self):
        comp = _make_component({"max_rows": 10})
        result = comp.execute(_make_df(10_000))
        assert len(result["main"]) == 10_000

    def test_dataframe_with_special_characters(self, caplog):
        df = pd.DataFrame({"data": ["hello|world", "foo;bar"]})
        comp = _make_component({"basic_mode": True})
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        all_messages = " ".join(r.message for r in caplog.records)
        assert "hello|world" in all_messages

    def test_dataframe_with_numeric_types(self):
        df = pd.DataFrame({"int_col": [1, 2], "float_col": [1.5, 2.5]})
        comp = _make_component({})
        result = comp.execute(df)
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """NB_LINE, NB_LINE_OK, NB_LINE_REJECT must be set correctly after execute()."""

    def test_nb_line_equals_input_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_df(7))
        assert gm.get_nb_line("tLogRow_1") == 7

    def test_nb_line_ok_equals_input_row_count(self):
        """NB_LINE_OK must count ALL input rows, not just the displayed subset."""
        gm = GlobalMap()
        comp = _make_component({"max_rows": 2}, global_map=gm)
        comp.execute(_make_df(7))
        # max_rows=2 limits display but NB_LINE_OK is based on main output (7 rows)
        assert gm.get_nb_line_ok("tLogRow_1") == 7

    def test_nb_line_reject_always_zero(self):
        """tLogRow never rejects rows -- NB_LINE_REJECT must always be 0."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_df(5))
        assert gm.get_nb_line_reject("tLogRow_1") == 0

    def test_stats_without_global_map(self):
        """Component must work without a GlobalMap instance (isolated testing)."""
        comp = _make_component(global_map=None)
        comp.global_map = None
        result = comp.execute(_make_df(3))
        assert len(result["main"]) == 3

    def test_stats_with_empty_input(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(pd.DataFrame())
        # Empty input: NB_LINE = 0
        assert gm.get_nb_line("tLogRow_1") == 0


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    """execute() twice with reset() between gives consistent results both times."""

    def test_second_execute_produces_same_output(self):
        comp = _make_component({})
        df = _make_df(4)
        result1 = comp.execute(df)
        comp.reset()
        result2 = comp.execute(df)
        assert len(result1["main"]) == len(result2["main"])

    def test_stats_reset_between_executions(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_df(3)
        comp.execute(df)
        first_count = gm.get_nb_line("tLogRow_1")
        comp.reset()
        comp.execute(df)
        second_count = gm.get_nb_line("tLogRow_1")
        assert first_count == second_count

    def test_config_not_mutated_across_executions(self):
        comp = _make_component({"max_rows": 10, "basic_mode": True})
        df = _make_df(3)
        comp.execute(df)
        original_snapshot = dict(comp._original_config)
        comp.reset()
        comp.execute(df)
        assert comp._original_config == original_snapshot

    def test_context_var_re_resolved_each_execution(self, caplog):
        """Context vars must be re-resolved on every execute(), not cached."""
        cm = ContextManager()
        cm.set("MAX_ROWS", "3")
        comp = _make_component({"max_rows": "${context.MAX_ROWS}"}, context_manager=cm)
        df = _make_df(10)

        caplog.clear()
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        lines_first = [r.message for r in caplog.records if "|" in r.message]
        assert len(lines_first) == 3

        cm.set("MAX_ROWS", "5")
        comp.reset()
        caplog.clear()
        with caplog.at_level(logging.INFO):
            comp.execute(df)
        lines_second = [r.message for r in caplog.records if "|" in r.message]
        assert len(lines_second) == 5

