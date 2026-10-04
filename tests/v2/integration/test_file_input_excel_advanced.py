"""Integration tests for FileInputExcel advanced features."""
import pytest
import polars as pl

pytest.importorskip("openpyxl")
pytest.importorskip("xlsxwriter")

from src.v2.engine import PyETLEngine


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path


class TestExcelMultiSheetPipeline:
    """End-to-end: multi-sheet Excel -> map -> file_output."""

    def test_all_sheets_through_map_to_sink(self, data_dir):
        """Read all sheets, apply map expression, write output."""
        import xlsxwriter
        xlsx = data_dir / "multi.xlsx"
        workbook = xlsxwriter.Workbook(str(xlsx))
        ws1 = workbook.add_worksheet("Q1")
        ws1.write_row(0, 0, ["id", "amount"])
        ws1.write_row(1, 0, [1, 100])
        ws2 = workbook.add_worksheet("Q2")
        ws2.write_row(0, 0, ["id", "amount"])
        ws2.write_row(1, 0, [2, 200])
        workbook.close()

        output_file = data_dir / "out.csv"
        config = {
            "name": "excel_multi_sheet_test",
            "engine": "v2",
            "components": [
                {
                    "id": "read",
                    "type": "file_input_excel",
                    "config": {
                        "path": str(xlsx),
                        "all_sheets": True,
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "amount", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "double_amount",
                    "type": "map",
                    "config": {
                        "outputs": [{"name": "main", "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "amount", "expression": "amount * 2"},
                        ]}],
                    },
                },
                {
                    "id": "write",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "read", "target": "double_amount"},
                {"source": "double_amount", "target": "write"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        out = pl.read_csv(output_file)
        assert len(out) == 2
        assert out["amount"].to_list() == [200, 400]


class TestExcelColumnRangePipeline:
    """End-to-end: column range + footer + limit pipeline."""

    def test_column_range_with_footer_and_limit(self, data_dir):
        """Read specific columns, skip footer, apply limit."""
        xlsx = data_dir / "wide.xlsx"
        pl.DataFrame({
            "skip_me": [0, 0, 0, 0, 0],
            "id": [1, 2, 3, 4, 5],
            "name": ["a", "b", "c", "TOTAL", "NOTE"],
            "extra": [0, 0, 0, 0, 0],
        }).write_excel(xlsx)

        output_file = data_dir / "out.csv"
        config = {
            "name": "excel_col_range_test",
            "engine": "v2",
            "components": [
                {
                    "id": "read",
                    "type": "file_input_excel",
                    "config": {
                        "path": str(xlsx),
                        "first_column": 2,
                        "last_column": 3,
                        "footer_rows": 2,
                        "limit": 2,
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "name", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "write",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        out = pl.read_csv(output_file)
        assert len(out) == 2
        assert out["name"].to_list() == ["a", "b"]
