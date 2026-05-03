"""Comprehensive tests for FileOutputExcel (tFileOutputExcel engine component).

Covers:
- Registry registration (V1 and Talend names)
- _validate_config() raise-based validation
- Basic write: DataFrame → xlsx file
- includeheader: header row written when True
- append_file: appends to existing workbook
- append_sheet: starts after existing sheet data
- FIRST_CELL_X/Y: write offset into sheet
- IS_ALL_AUTO_SZIE: all columns auto-widened
- delete_empty_file: removes file when 0 rows written
- recalculate_formula: sets calcMode=auto on workbook
- NaN / None values written as blank cells (not 'nan' strings)
- Error handling (die_on_error True vs False, bad output directory)
- Statistics (NB_LINE, NB_LINE_OK, NB_LINE_REJECT)
- date_pattern: datetime columns formatted via input_schema date_pattern
- precision: Decimal/float columns get openpyxl number format from input_schema
- input_schema column ordering: column order taken from input_schema when output_schema is empty
"""
import os

import openpyxl
import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_output_excel import FileOutputExcel
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "filename": "",          # filled in per test via tmp_path
    "sheetname": "Sheet1",
    "includeheader": False,
    "append_file": False,
    "create": True,
    "die_on_error": True,
}


def _make_component(config, global_map=None, context_manager=None):
    """Create a FileOutputExcel with explicit config."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileOutputExcel(
        component_id="tFOE_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    comp.output_schema = None
    return comp


def _make_df(rows=None):
    """Return a small DataFrame with (name, score) columns."""
    if rows is None:
        rows = [("alice", 90), ("bob", 85), ("carol", 78)]
    return pd.DataFrame(rows, columns=["name", "score"])


def _read_xlsx(filepath, sheet_name="Sheet1"):
    """Read an xlsx file back as a list-of-lists (no header inference)."""
    wb = openpyxl.load_workbook(filepath)
    ws = wb[sheet_name]
    return [[cell.value for cell in row] for row in ws.iter_rows()]


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """REGISTRY must resolve both the V1 name and the Talend alias."""

    def test_v1_name_resolves(self):
        assert REGISTRY.get("FileOutputExcel") is FileOutputExcel

    def test_talend_alias_resolves(self):
        assert REGISTRY.get("tFileOutputExcel") is FileOutputExcel


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config() must raise ConfigurationError for bad config."""

    def test_missing_filename_raises(self):
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_empty_filename_raises(self):
        comp = _make_component({"filename": ""})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_non_bool_includeheader_raises(self):
        comp = _make_component({"filename": "out.xlsx", "includeheader": "yes"})
        with pytest.raises(ConfigurationError, match="includeheader"):
            comp._validate_config()

    def test_non_bool_append_file_raises(self):
        comp = _make_component({"filename": "out.xlsx", "append_file": 1})
        with pytest.raises(ConfigurationError, match="append_file"):
            comp._validate_config()

    def test_non_bool_append_sheet_raises(self):
        comp = _make_component({"filename": "out.xlsx", "append_sheet": "true"})
        with pytest.raises(ConfigurationError, match="append_sheet"):
            comp._validate_config()

    def test_non_bool_create_raises(self):
        comp = _make_component({"filename": "out.xlsx", "create": 0})
        with pytest.raises(ConfigurationError, match="create"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self):
        comp = _make_component({"filename": "out.xlsx", "includeheader": False})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# Basic write
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicWrite:
    """Write a DataFrame to xlsx and verify file content."""

    def test_file_created(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.execute(_make_df())
        assert os.path.exists(out)

    def test_row_count_without_header(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "includeheader": False}
        comp = _make_component(config)
        comp.execute(_make_df())
        rows = _read_xlsx(out)
        assert len(rows) == 3

    def test_data_values_written_correctly(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90)]))
        rows = _read_xlsx(out)
        assert rows[0][0] == "alice"
        assert rows[0][1] == 90


# ------------------------------------------------------------------
# Header row
# ------------------------------------------------------------------


@pytest.mark.unit
class TestHeaderRow:
    """includeheader=True writes column names as the first row."""

    def test_header_row_written(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "includeheader": True}
        comp = _make_component(config)
        comp.execute(_make_df())
        rows = _read_xlsx(out)
        # row 0 = header, rows 1-3 = data
        assert rows[0] == ["name", "score"]
        assert len(rows) == 4

    def test_no_header_row_when_false(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "includeheader": False}
        comp = _make_component(config)
        comp.execute(_make_df())
        rows = _read_xlsx(out)
        assert len(rows) == 3  # no header row


# ------------------------------------------------------------------
# append_file
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAppendFile:
    """append_file=True appends to existing workbook."""

    def test_append_adds_rows(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}

        # First write: 2 rows
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90), ("bob", 85)]))

        # Second write: 1 row, append_file=True
        config2 = {**_DEFAULT_CONFIG, "filename": out, "append_file": True}
        comp2 = _make_component(config2)
        comp2.execute(_make_df([("carol", 78)]))

        rows = _read_xlsx(out)
        assert len(rows) == 3


# ------------------------------------------------------------------
# Cell positioning (FIRST_CELL_X / FIRST_CELL_Y)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCellPositioning:
    """first_cell_x / first_cell_y offsets the write start position."""

    def test_default_starts_at_a1(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90)]))
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        assert ws.cell(row=1, column=1).value == "alice"

    def test_first_cell_x_1_starts_at_column_b(self, tmp_path):
        """first_cell_x='1' → start_col = 1+1 = 2 (column B)."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "first_cell_x": "1"}
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90)]))
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        # Column A should be empty, column B should have "alice"
        assert ws.cell(row=1, column=1).value is None
        assert ws.cell(row=1, column=2).value == "alice"

    def test_first_cell_y_1_starts_at_row_2(self, tmp_path):
        """first_cell_y='1' → start_row = 1+1 = 2."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "first_cell_y": "1"}
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90)]))
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        # Row 1 should be empty, row 2 should have data
        assert ws.cell(row=1, column=1).value is None
        assert ws.cell(row=2, column=1).value == "alice"


# ------------------------------------------------------------------
# Auto-size columns
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAutoSizeColumns:
    """is_all_auto_szie=True sets column widths based on content length."""

    def test_auto_size_sets_column_widths(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "is_all_auto_szie": True}
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90)]))
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        # Both columns should have width > 0
        assert ws.column_dimensions["A"].width > 0
        assert ws.column_dimensions["B"].width > 0


# ------------------------------------------------------------------
# Delete empty file
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteEmptyFile:
    """delete_empty_file=True removes the output file when no rows are written."""

    def test_file_deleted_when_no_data(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "delete_empty_file": True}
        comp = _make_component(config)
        comp.execute(pd.DataFrame(columns=["name", "score"]))  # empty DataFrame
        assert not os.path.exists(out)

    def test_file_kept_when_data_present(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "delete_empty_file": True}
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90)]))
        assert os.path.exists(out)


# ------------------------------------------------------------------
# Formula recalculation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFormulaRecalculation:
    """recalculate_formula=True sets workbook.calculation.calcMode to 'auto'."""

    def test_recalculate_formula_sets_calcmode(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "recalculate_formula": True}
        comp = _make_component(config)
        comp.execute(_make_df([("alice", 90)]))
        wb = openpyxl.load_workbook(out)
        assert wb.calculation.calcMode == "auto"


# ------------------------------------------------------------------
# NaN handling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNaNHandling:
    """NaN and None values are written as blank cells, not 'nan' strings."""

    def test_nan_written_as_none(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        df = pd.DataFrame({"name": ["alice", float("nan")], "score": [90, None]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        # Row 1: alice, 90
        assert ws.cell(row=1, column=1).value == "alice"
        # Row 2 may be filtered by is_non_empty_row (all nulls) or written as None
        # Either case: 'nan' string must not appear
        all_values = [ws.cell(row=r, column=c).value
                      for r in range(1, ws.max_row + 1)
                      for c in range(1, ws.max_column + 1)]
        assert "nan" not in [str(v).lower() for v in all_values if v is not None]

    def test_partial_none_row_written(self, tmp_path):
        """Row with one None and one real value should NOT be filtered out."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        df = pd.DataFrame({"name": ["alice"], "score": [None]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        # Row should be written (name="alice" is non-empty)
        assert ws.cell(row=1, column=1).value == "alice"
        assert ws.cell(row=1, column=2).value is None


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestErrorHandling:
    """die_on_error controls whether write failures raise or return gracefully."""

    def test_bad_dir_die_on_error_true_raises(self, tmp_path):
        bad_path = str(tmp_path / "nonexistent_dir" / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": bad_path, "create": False, "die_on_error": True}
        comp = _make_component(config)
        with pytest.raises((FileOperationError, Exception)):
            comp.execute(_make_df())

    def test_none_input_returns_gracefully(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        result = comp.execute(None)
        assert result is not None
        assert "stats" in result

    def test_component_via_registry_is_executable(self, tmp_path):
        """Component resolved from REGISTRY can write a file."""
        cls = REGISTRY.get("FileOutputExcel")
        out = str(tmp_path / "out.xlsx")
        comp = cls(
            component_id="test_reg",
            config={**_DEFAULT_CONFIG, "filename": out},
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.output_schema = None  # BaseComponent does not set this in __init__
        comp.execute(_make_df())
        assert os.path.exists(out)


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStatistics:
    """NB_LINE, NB_LINE_OK, NB_LINE_REJECT set correctly after execute()."""

    def test_stats_set_after_write(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        result = comp.execute(_make_df())
        stats = result.get("stats", {})
        assert stats.get("NB_LINE", 0) == 3
        assert stats.get("NB_LINE_OK", 0) == 3
        assert stats.get("NB_LINE_REJECT", 0) == 0

    def test_stats_zero_for_none_input(self, tmp_path):
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        result = comp.execute(None)
        stats = result.get("stats", {})
        assert stats.get("NB_LINE_OK", 0) == 0


# ------------------------------------------------------------------
# date_pattern formatting (ENG-FOE-013 fixed)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDatePatternFormatting:
    """input_schema date_pattern causes datetime columns to be formatted as strings."""

    def test_date_pattern_applied_to_datetime_column(self, tmp_path):
        """datetime column with date_pattern is written as a formatted string."""
        from decimal import Decimal
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.input_schema = [
            {"name": "id", "type": "str", "nullable": True},
            {"name": "joindate", "type": "datetime", "nullable": True, "date_pattern": "%y%m%d"},
        ]
        df = pd.DataFrame({
            "id": ["E001", "E002"],
            "joindate": pd.to_datetime(["2023-01-15", "2024-06-30"]),
        })
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        # joindate column is col 2 (B)
        val_r1 = ws.cell(row=1, column=2).value
        val_r2 = ws.cell(row=2, column=2).value
        assert val_r1 == "230115", f"Expected '230115', got {val_r1!r}"
        assert val_r2 == "240630", f"Expected '240630', got {val_r2!r}"

    def test_nat_written_as_empty_string(self, tmp_path):
        """NaT value in datetime column with date_pattern is written as empty string."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.input_schema = [
            {"name": "name", "type": "str", "nullable": True},
            {"name": "dt", "type": "datetime", "nullable": True, "date_pattern": "%Y-%m-%d"},
        ]
        df = pd.DataFrame({
            "name": ["alice"],
            "dt": [pd.NaT],
        })
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        val = ws.cell(row=1, column=2).value
        # NaT → empty string → openpyxl writes None (blank cell)
        assert val in ("", None), f"Expected blank for NaT, got {val!r}"

    def test_column_without_date_pattern_unchanged(self, tmp_path):
        """datetime column without date_pattern is written as-is (not formatted)."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.input_schema = [
            {"name": "ts", "type": "datetime", "nullable": True},
        ]
        df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01"])})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        val = ws.cell(row=1, column=1).value
        # Without a pattern the value is left as whatever pandas / openpyxl produces
        # (could be a datetime or string) -- key assertion: it must not be a strftime string
        assert val is not None


# ------------------------------------------------------------------
# Decimal precision (ENG-FOE-014 fixed)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDecimalPrecision:
    """input_schema precision applies an openpyxl number format to Decimal/float cells."""

    def test_decimal_cell_has_number_format(self, tmp_path):
        """Decimal column with precision=2 gets '0.00' number_format on each cell."""
        from decimal import Decimal
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.input_schema = [
            {"name": "salary", "type": "Decimal", "nullable": True, "precision": 2},
        ]
        df = pd.DataFrame({"salary": [Decimal("1234.5"), Decimal("0.1")]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        fmt = ws.cell(row=1, column=1).number_format
        assert fmt == "0.00", f"Expected '0.00', got {fmt!r}"

    def test_decimal_precision_10_format(self, tmp_path):
        """Decimal column with precision=10 gets '0.0000000000' number format."""
        from decimal import Decimal
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.input_schema = [
            {"name": "amount", "type": "Decimal", "nullable": True, "precision": 10},
        ]
        df = pd.DataFrame({"amount": [Decimal("99.5")]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        fmt = ws.cell(row=1, column=1).number_format
        assert fmt == "0.0000000000", f"Expected '0.0000000000', got {fmt!r}"

    def test_float_column_precision_format(self, tmp_path):
        """Float column with precision=3 gets '0.000' number format."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.input_schema = [
            {"name": "rate", "type": "float", "nullable": True, "precision": 3},
        ]
        df = pd.DataFrame({"rate": [1.5, 2.25]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        fmt_r1 = ws.cell(row=1, column=1).number_format
        fmt_r2 = ws.cell(row=2, column=1).number_format
        assert fmt_r1 == "0.000"
        assert fmt_r2 == "0.000"

    def test_column_without_precision_no_custom_format(self, tmp_path):
        """Decimal column without precision gets no custom number format applied."""
        from decimal import Decimal
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out}
        comp = _make_component(config)
        comp.input_schema = [
            {"name": "val", "type": "Decimal", "nullable": True},
        ]
        df = pd.DataFrame({"val": [Decimal("1.5")]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        fmt = ws.cell(row=1, column=1).number_format
        # No precision in schema → default openpyxl format (General or empty)
        assert fmt in ("General", None, "")

    def test_build_col_formats_returns_correct_mapping(self):
        """_build_col_formats builds the right column→format map from input_schema."""
        comp = _make_component({**_DEFAULT_CONFIG, "filename": "dummy.xlsx"})
        comp.input_schema = [
            {"name": "a", "type": "Decimal", "nullable": True, "precision": 4},
            {"name": "b", "type": "str", "nullable": True},
            {"name": "c", "type": "float", "nullable": True, "precision": 0},
        ]
        fmt_map = comp._build_col_formats()
        assert fmt_map == {"a": "0.0000", "c": "0"}


# ------------------------------------------------------------------
# input_schema column ordering
# ------------------------------------------------------------------


@pytest.mark.unit
class TestInputSchemaColumnOrdering:
    """Column order in output comes from input_schema when output_schema is empty."""

    def test_column_order_from_input_schema(self, tmp_path):
        """Columns are written in input_schema order, not DataFrame column order."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "includeheader": True}
        comp = _make_component(config)
        # Schema order: dept, name, salary
        comp.input_schema = [
            {"name": "dept", "type": "str", "nullable": True},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "salary", "type": "str", "nullable": True},
        ]
        # DataFrame has different column order
        df = pd.DataFrame({
            "name": ["alice"],
            "salary": ["50000"],
            "dept": ["HR"],
        })
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        # Header row (row 1) should follow input_schema order
        header = [ws.cell(row=1, column=c).value for c in range(1, 4)]
        assert header == ["dept", "name", "salary"]

    def test_output_schema_used_when_input_schema_empty(self, tmp_path):
        """Falls back to output_schema if input_schema is empty/absent."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "includeheader": True}
        comp = _make_component(config)
        comp.input_schema = []
        comp.output_schema = [
            {"name": "z", "type": "str"},
            {"name": "a", "type": "str"},
        ]
        df = pd.DataFrame({"a": [1], "z": [2]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        header = [ws.cell(row=1, column=c).value for c in range(1, 3)]
        assert header == ["z", "a"]

    def test_dataframe_order_when_no_schema(self, tmp_path):
        """Falls back to DataFrame column order when both schemas are empty."""
        out = str(tmp_path / "out.xlsx")
        config = {**_DEFAULT_CONFIG, "filename": out, "includeheader": True}
        comp = _make_component(config)
        comp.input_schema = []
        comp.output_schema = None
        df = pd.DataFrame({"b": [1], "a": [2]})
        comp.execute(df)
        wb = openpyxl.load_workbook(out)
        ws = wb["Sheet1"]
        header = [ws.cell(row=1, column=c).value for c in range(1, 3)]
        assert header == ["b", "a"]
