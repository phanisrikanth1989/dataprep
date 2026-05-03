"""Comprehensive tests for FileInputExcel (tFileInputExcel engine component).

Covers:
- Registry registration (V1 and Talend names)
- _validate_config() raise-based validation
- Talend-correct defaults (all_sheets=False, header=0, die_on_error=False)
- Basic xlsx read (with/without header skip)
- Multi-sheet read (all_sheets=True/False, sheetlist)
- header / footer / limit trimming
- CURRENT_SHEET globalMap update during sheet iteration
- Error handling (die_on_error True vs False)
- Statistics (NB_LINE, NB_LINE_OK)
- Context-var deferral (Phase 7.2-01 regression): header/first_column
  accepted at _validate_config time, resolved+re-validated at execute time.
  footer/limit checks remain strict at _validate_config time.
"""
import openpyxl
import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_input_excel import FileInputExcel
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, context_manager=None, global_map=None):
    """Create a FileInputExcel with explicit config.

    Sets both the constructor config (used by execute()) and self.config
    directly (used by isolated _validate_config() calls).
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    comp = FileInputExcel(
        component_id="tFIE_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    comp.output_schema = None
    return comp


def _make_xlsx(tmp_path, *, rows=None, sheet_name="Sheet1", suffix="input.xlsx"):
    """Write a small xlsx fixture.

    Default layout: header row + 3 data rows, columns (name, age).
    """
    p = tmp_path / suffix
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(["name", "age"])
    if rows is None:
        ws.append(["alice", 25])
        ws.append(["bob", 30])
        ws.append(["carol", 35])
    else:
        for row in rows:
            ws.append(row)
    wb.save(str(p))
    return str(p)


def _make_multi_sheet_xlsx(tmp_path):
    """Write xlsx with Sheet1 (3 data rows) and Sheet2 (2 data rows).

    Each sheet has a header row ["name", "age"].
    """
    p = tmp_path / "multi.xlsx"
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Sheet1"
    ws1.append(["name", "age"])
    ws1.append(["alice", 25])
    ws1.append(["bob", 30])
    ws1.append(["carol", 35])
    ws2 = wb.create_sheet("Sheet2")
    ws2.append(["name", "age"])
    ws2.append(["dave", 40])
    ws2.append(["eve", 45])
    wb.save(str(p))
    return str(p)


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """REGISTRY must resolve both the V1 name and the Talend alias."""

    def test_v1_name_resolves(self):
        assert REGISTRY.get("FileInputExcel") is FileInputExcel

    def test_talend_alias_resolves(self):
        assert REGISTRY.get("tFileInputExcel") is FileInputExcel


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config() must raise ConfigurationError for bad config."""

    def test_missing_filepath_raises(self):
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="filepath"):
            comp._validate_config()

    def test_empty_filepath_raises(self):
        comp = _make_component({"filepath": ""})
        with pytest.raises(ConfigurationError, match="filepath"):
            comp._validate_config()

    def test_non_string_filepath_raises(self):
        comp = _make_component({"filepath": 123})
        with pytest.raises(ConfigurationError, match="filepath"):
            comp._validate_config()

    def test_non_bool_all_sheets_raises(self):
        comp = _make_component({"filepath": "x.xlsx", "all_sheets": "yes"})
        with pytest.raises(ConfigurationError, match="all_sheets"):
            comp._validate_config()

    def test_non_bool_die_on_error_raises(self):
        comp = _make_component({"filepath": "x.xlsx", "die_on_error": 1})
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_non_list_sheetlist_raises(self):
        comp = _make_component({"filepath": "x.xlsx", "sheetlist": "Sheet1"})
        with pytest.raises(ConfigurationError, match="sheetlist"):
            comp._validate_config()

    def test_footer_bad_string_raises(self):
        """footer is validated eagerly (not deferred like header/first_column)."""
        comp = _make_component({"filepath": "x.xlsx", "footer": "abc"})
        with pytest.raises(ConfigurationError, match="footer"):
            comp._validate_config()

    def test_limit_bad_string_raises(self):
        """limit is validated eagerly."""
        comp = _make_component({"filepath": "x.xlsx", "limit": "xyz"})
        with pytest.raises(ConfigurationError, match="limit"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self):
        comp = _make_component({"filepath": "x.xlsx", "all_sheets": False, "die_on_error": False})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDefaults:
    """Verify Talend-correct defaults used when keys are absent from config."""

    def test_all_sheets_default_is_false(self, tmp_path):
        """With all_sheets not set, only the first sheet is read."""
        filepath = _make_multi_sheet_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1, "die_on_error": False})
        result = comp.execute()
        # Only Sheet1 has 3 data rows; if all_sheets defaulted True we'd get 5
        assert len(result["main"]) == 3

    def test_header_default_is_zero(self, tmp_path):
        """With header not set (default 0), no row is consumed as column header."""
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "die_on_error": False})
        result = comp.execute()
        # fixture: 1 header row + 3 data rows = 4 total rows when header=0
        assert len(result["main"]) == 4

    def test_die_on_error_default_is_false(self, tmp_path):
        """With die_on_error not set, missing file returns empty DF not exception."""
        comp = _make_component({"filepath": str(tmp_path / "nonexistent.xlsx")})
        result = comp.execute()
        df = result["main"]
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


# ------------------------------------------------------------------
# Basic xlsx read
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicReadXlsx:
    """Read an xlsx file and verify DataFrame shape and content."""

    def test_read_returns_dataframe(self, tmp_path):
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1})
        result = comp.execute()
        assert "main" in result
        assert isinstance(result["main"], pd.DataFrame)

    def test_read_row_count(self, tmp_path):
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1})
        result = comp.execute()
        assert len(result["main"]) == 3

    def test_read_column_names_from_header_row(self, tmp_path):
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1})
        result = comp.execute()
        assert list(result["main"].columns) == ["name", "age"]

    def test_read_first_row_values(self, tmp_path):
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1})
        result = comp.execute()
        first = result["main"].iloc[0]
        assert first["name"] == "alice"
        assert first["age"] == 25


# ------------------------------------------------------------------
# Multi-sheet behaviour
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMultiSheet:
    """all_sheets=True reads every sheet; all_sheets=False reads only first."""

    def test_all_sheets_false_reads_only_first_sheet(self, tmp_path):
        filepath = _make_multi_sheet_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1, "all_sheets": False})
        result = comp.execute()
        assert len(result["main"]) == 3  # Sheet1 only

    def test_all_sheets_true_reads_all_sheets(self, tmp_path):
        filepath = _make_multi_sheet_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1, "all_sheets": True})
        result = comp.execute()
        assert len(result["main"]) == 5  # Sheet1 (3) + Sheet2 (2)

    def test_sheetlist_restricts_sheets(self, tmp_path):
        """all_sheets=False + sheetlist=[{sheetname:Sheet2}] reads only Sheet2."""
        filepath = _make_multi_sheet_xlsx(tmp_path)
        comp = _make_component({
            "filepath": filepath,
            "header": 1,
            "all_sheets": False,
            "sheetlist": [{"sheetname": "Sheet2"}],
        })
        result = comp.execute()
        assert len(result["main"]) == 2  # Sheet2 only


# ------------------------------------------------------------------
# Header / footer / limit
# ------------------------------------------------------------------


@pytest.mark.unit
class TestHeaderFooterLimit:
    """header/footer/limit trim the reading window correctly."""

    def test_header_1_skips_first_row(self, tmp_path):
        """header=1: row 1 becomes column names, 3 data rows remain."""
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1})
        result = comp.execute()
        assert len(result["main"]) == 3

    def test_header_0_no_skip(self, tmp_path):
        """header=0 (default): no header consumed, all 4 rows are data."""
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 0})
        result = comp.execute()
        assert len(result["main"]) == 4

    def test_footer_1_skips_last_row(self, tmp_path):
        """footer=1 with header=1: 3 data rows minus 1 footer = 2 rows."""
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1, "footer": 1})
        result = comp.execute()
        assert len(result["main"]) == 2

    def test_limit_restricts_rows(self, tmp_path):
        """limit=2 with header=1: at most 2 data rows."""
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1, "limit": 2})
        result = comp.execute()
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# CURRENT_SHEET globalMap update
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCurrentSheetGlobalMap:
    """CURRENT_SHEET is written to globalMap for each sheet read."""

    def test_single_sheet_sets_current_sheet(self, tmp_path):
        gm = GlobalMap()
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1}, global_map=gm)
        comp.execute()
        assert gm.get("tFIE_1_CURRENT_SHEET") == "Sheet1"

    def test_multi_sheet_last_value_reflects_last_sheet(self, tmp_path):
        """After reading both sheets, CURRENT_SHEET reflects the last sheet processed."""
        gm = GlobalMap()
        filepath = _make_multi_sheet_xlsx(tmp_path)
        comp = _make_component(
            {"filepath": filepath, "header": 1, "all_sheets": True},
            global_map=gm,
        )
        comp.execute()
        # Last sheet iterated is Sheet2
        assert gm.get("tFIE_1_CURRENT_SHEET") == "Sheet2"


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestErrorHandling:
    """die_on_error controls whether bad files raise or return empty."""

    def test_missing_file_die_on_error_true_raises(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "missing.xlsx"),
            "die_on_error": True,
        })
        with pytest.raises((FileOperationError, ConfigurationError, Exception)):
            comp.execute()

    def test_missing_file_die_on_error_false_returns_empty(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "missing.xlsx"),
            "die_on_error": False,
        })
        result = comp.execute()
        df = result["main"]
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_component_via_registry_is_executable(self, tmp_path):
        """Component resolved from REGISTRY can be instantiated and executed."""
        cls = REGISTRY.get("FileInputExcel")
        filepath = _make_xlsx(tmp_path)
        comp = cls(
            component_id="test_reg",
            config={"filepath": filepath, "header": 1},
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        comp.output_schema = None  # BaseComponent does not set this in __init__
        result = comp.execute()
        assert len(result["main"]) == 3


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStatistics:
    """NB_LINE and NB_LINE_OK are set correctly after execute()."""

    def test_stats_set_after_successful_read(self, tmp_path):
        filepath = _make_xlsx(tmp_path)
        comp = _make_component({"filepath": filepath, "header": 1})
        result = comp.execute()
        stats = result.get("stats", {})
        assert stats.get("NB_LINE", 0) == 3
        assert stats.get("NB_LINE_OK", 0) == 3
        assert stats.get("NB_LINE_REJECT", 0) == 0

    def test_stats_zero_on_empty_result(self, tmp_path):
        comp = _make_component({
            "filepath": str(tmp_path / "missing.xlsx"),
            "die_on_error": False,
        })
        result = comp.execute()
        stats = result.get("stats", {})
        assert stats.get("NB_LINE_OK", 0) == 0


# ------------------------------------------------------------------
# Context-var deferral (Phase 7.2-01 regression)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextVarDeferral:
    """header / first_column context vars deferred from _validate_config to _process.

    footer and limit checks are NOT deferred -- they remain eager at
    _validate_config time per Phase 7.2 CONTEXT.md decision A.
    """

    # ---- header ----

    def test_validate_accepts_context_var_header(self, tmp_path):
        """${context.HEADER} must not cause ConfigurationError at validate time."""
        comp = _make_component({
            "filepath": _make_xlsx(tmp_path),
            "header": "${context.HEADER}",
        })
        comp._validate_config()  # Must not raise

    def test_execute_resolves_context_var_header(self, tmp_path):
        cm = ContextManager()
        cm.set("HEADER", "1")
        filepath = _make_xlsx(tmp_path)
        comp = _make_component(
            {"filepath": filepath, "header": "${context.HEADER}"},
            context_manager=cm,
        )
        result = comp.execute()
        # header=1 → 3 data rows
        assert len(result["main"]) == 3

    def test_execute_invalid_resolved_header_raises(self, tmp_path):
        comp = _make_component({
            "filepath": _make_xlsx(tmp_path),
            "header": "abc",
            "die_on_error": True,
        })
        with pytest.raises(ConfigurationError, match="header"):
            comp.execute()

    def test_execute_negative_header_raises(self, tmp_path):
        comp = _make_component({
            "filepath": _make_xlsx(tmp_path),
            "header": -1,
            "die_on_error": True,
        })
        with pytest.raises(ConfigurationError):
            comp.execute()

    # ---- first_column ----

    def test_validate_accepts_context_var_first_column(self, tmp_path):
        """${context.FIRST_COL} must not raise at validate time."""
        comp = _make_component({
            "filepath": _make_xlsx(tmp_path),
            "first_column": "${context.FIRST_COL}",
        })
        comp._validate_config()  # Must not raise

    def test_execute_resolves_context_var_first_column(self, tmp_path):
        cm = ContextManager()
        cm.set("FIRST_COL", "1")
        filepath = _make_xlsx(tmp_path)
        comp = _make_component(
            {"filepath": filepath, "first_column": "${context.FIRST_COL}", "header": 1},
            context_manager=cm,
        )
        result = comp.execute()
        assert len(result["main"]) == 3

    def test_execute_zero_first_column_raises(self, tmp_path):
        """first_column=0 is invalid (1-based; minimum is 1)."""
        comp = _make_component({
            "filepath": _make_xlsx(tmp_path),
            "first_column": "0",
            "die_on_error": True,
        })
        with pytest.raises(ConfigurationError, match="first_column"):
            comp.execute()

    # ---- footer / limit remain strict ----

    def test_footer_bad_string_raises_at_validate_time(self, tmp_path):
        comp = _make_component({
            "filepath": _make_xlsx(tmp_path),
            "footer": "abc",
        })
        with pytest.raises(ConfigurationError, match="footer"):
            comp._validate_config()

    def test_limit_bad_string_raises_at_validate_time(self, tmp_path):
        comp = _make_component({
            "filepath": _make_xlsx(tmp_path),
            "limit": "xyz",
        })
        with pytest.raises(ConfigurationError, match="limit"):
            comp._validate_config()
