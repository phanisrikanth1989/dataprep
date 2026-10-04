"""
Integration tests for die_on_error behavior across components.

Tests the Talend-style die_on_error contract:
- die_on_error=true (default): crash on bad row
- die_on_error=false + no reject flow: skip bad rows silently
- die_on_error=false + reject flow: route bad rows to reject with _error_message
"""
from pathlib import Path

import polars as pl
import pytest

from v2.engine import PyETLEngine


@pytest.fixture
def data_dir(tmp_path):
    """Create test CSV files with some bad data."""
    # Good data file
    good_file = tmp_path / "good.csv"
    good_file.write_text("id,name,amount,score\n1,Alice,100,85.5\n2,Bob,200,92.3\n3,Carol,300,78.1\n")

    # Bad data file — has non-numeric values in amount and score columns
    bad_file = tmp_path / "bad.csv"
    bad_file.write_text(
        "id,name,amount,score\n"
        "1,Alice,100,85.5\n"
        "2,Bob,bad_amount,92.3\n"
        "3,Carol,300,not_a_score\n"
        "4,Dave,400,88.0\n"
    )

    return tmp_path


class TestSourceDieOnErrorDefault:
    """Default die_on_error=true should crash on schema type errors."""

    def test_bad_data_crashes_by_default(self, data_dir):
        """Schema type cast failure should crash when die_on_error is true (default)."""
        output_file = data_dir / "out.csv"
        config = {
            "name": "crash_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(data_dir / "bad.csv"),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "error"

    def test_good_data_works_by_default(self, data_dir):
        """Good data should work fine with default die_on_error."""
        output_file = data_dir / "out.csv"
        config = {
            "name": "good_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(data_dir / "good.csv"),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        df = pl.read_csv(output_file)
        assert len(df) == 3


class TestSourceDieOnErrorFalseNoReject:
    """die_on_error=false with no reject flow should skip bad rows."""

    def test_bad_rows_skipped_silently(self, data_dir):
        """Bad rows should be skipped, only good rows in output."""
        output_file = data_dir / "out.csv"
        config = {
            "name": "skip_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(data_dir / "bad.csv"),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        df = pl.read_csv(output_file)
        # Rows 1 and 4 are good, rows 2 and 3 have bad data
        assert len(df) == 2
        assert df["id"].to_list() == [1, 4]


class TestSourceDieOnErrorFalseWithReject:
    """die_on_error=false with reject flow should route bad rows."""

    def test_bad_rows_routed_to_reject(self, data_dir):
        """Bad rows should go to reject output with _error_message."""
        output_file = data_dir / "out.csv"
        reject_file = data_dir / "reject.csv"
        config = {
            "name": "reject_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(data_dir / "bad.csv"),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(output_file)}},
                {"id": "write_reject", "type": "file_output_delimited", "config": {"path": str(reject_file)}},
            ],
            "flows": [
                {"source": "read", "target": "write_main"},
                {"source": "read", "target": "write_reject", "output": "reject"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        main_df = pl.read_csv(output_file)
        assert len(main_df) == 2
        assert main_df["id"].to_list() == [1, 4]

        reject_df = pl.read_csv(reject_file)
        assert len(reject_df) == 2
        assert "_error_message" in reject_df.columns
        assert set(reject_df["id"].to_list()) == {2, 3}

    def test_reject_preserves_original_columns(self, data_dir):
        """Reject output should have all original columns plus _error_message."""
        output_file = data_dir / "out.csv"
        reject_file = data_dir / "reject.csv"
        config = {
            "name": "reject_cols_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(data_dir / "bad.csv"),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(output_file)}},
                {"id": "write_reject", "type": "file_output_delimited", "config": {"path": str(reject_file)}},
            ],
            "flows": [
                {"source": "read", "target": "write_main"},
                {"source": "read", "target": "write_reject", "output": "reject"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        reject_df = pl.read_csv(reject_file)
        assert "id" in reject_df.columns
        assert "name" in reject_df.columns
        assert "_error_message" in reject_df.columns

    def test_string_schema_means_no_type_validation(self, data_dir):
        """With all-string schema, die_on_error=false has no type cast effect."""
        output_file = data_dir / "out.csv"
        config = {
            "name": "no_schema_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(data_dir / "bad.csv"),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "string"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "string"},
                        {"name": "score", "type": "string"},
                    ],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        df = pl.read_csv(output_file)
        assert len(df) == 4  # all rows pass through

    def test_all_good_data_empty_reject(self, data_dir):
        """When all data is valid, no reject output."""
        output_file = data_dir / "out.csv"
        config = {
            "name": "all_good_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(data_dir / "good.csv"),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        df = pl.read_csv(output_file)
        assert len(df) == 3


class TestPythonRowDieOnError:
    """Test die_on_error on PythonRow component."""

    def test_default_crashes_on_row_error(self, data_dir):
        """Default die_on_error=true should crash on row processing error."""
        good_file = data_dir / "good.csv"
        output_file = data_dir / "out.csv"
        config = {
            "name": "pyrow_crash_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(good_file),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "transform", "type": "python_row", "config": {
                    "code": "return {'result': int(row['name'])}",
                    "output_columns": [{"name": "result", "type": "integer"}],
                    "pass_through": False,
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [
                {"source": "read", "target": "transform"},
                {"source": "transform", "target": "write"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "error"

    def test_die_on_error_false_skips_bad_rows(self, data_dir):
        """die_on_error=false should skip bad rows."""
        input_file = data_dir / "good.csv"
        output_file = data_dir / "out.csv"
        config = {
            "name": "pyrow_skip_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "score", "type": "float"},
                    ],
                }},
                {"id": "transform", "type": "python_row", "config": {
                    "die_on_error": False,
                    "code": "return {'parsed': int(row['name'])}",
                    "output_columns": [{"name": "parsed", "type": "integer"}],
                    "pass_through": True,
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_file)}},
            ],
            "flows": [
                {"source": "read", "target": "transform"},
                {"source": "transform", "target": "write"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        df = pl.read_csv(output_file)
        # All rows have non-numeric names (Alice, Bob, Carol), so all should be skipped
        assert len(df) == 0

    def test_die_on_error_false_routes_to_reject(self, data_dir):
        """die_on_error=false with reject flow should route bad rows."""
        # Create a file with mix of numeric and non-numeric values
        input_file = data_dir / "mixed.csv"
        input_file.write_text("val,label\n10,good\nabc,bad\n20,good\nxyz,bad\n")

        output_file = data_dir / "out.csv"
        reject_file = data_dir / "reject.csv"
        config = {
            "name": "pyrow_reject_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "schema": [
                        {"name": "val", "type": "string"},
                        {"name": "label", "type": "string"},
                    ],
                }},
                {"id": "transform", "type": "python_row", "config": {
                    "die_on_error": False,
                    "code": "return {'doubled': int(row['val']) * 2}",
                    "output_columns": [{"name": "doubled", "type": "integer"}],
                    "pass_through": True,
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(output_file)}},
                {"id": "write_reject", "type": "file_output_delimited", "config": {"path": str(reject_file)}},
            ],
            "flows": [
                {"source": "read", "target": "transform"},
                {"source": "transform", "target": "write_main"},
                {"source": "transform", "target": "write_reject", "output": "reject"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        main_df = pl.read_csv(output_file)
        assert len(main_df) == 2
        assert main_df["doubled"].to_list() == [20, 40]

        reject_df = pl.read_csv(reject_file)
        assert len(reject_df) == 2
        assert "_error_message" in reject_df.columns
        assert reject_df["val"].to_list() == ["abc", "xyz"]


class TestSourceDateDieOnError:
    """Test die_on_error with date columns."""

    def test_date_die_on_error_false_rejects_bad_dates(self, data_dir):
        """Bad date values with die_on_error=false should route to reject."""
        input_file = data_dir / "dates.csv"
        input_file.write_text(
            "id,order_date\n"
            "1,2026-03-01\n"
            "2,not_a_date\n"
            "3,2026-03-15\n"
        )
        output_file = data_dir / "out.csv"
        reject_file = data_dir / "reject.csv"
        config = {
            "name": "date_reject_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(output_file)}},
                {"id": "write_reject", "type": "file_output_delimited", "config": {"path": str(reject_file)}},
            ],
            "flows": [
                {"source": "read", "target": "write_main"},
                {"source": "read", "target": "write_reject", "output": "reject"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        main_df = pl.read_csv(output_file)
        assert len(main_df) == 2
        assert main_df["id"].to_list() == [1, 3]

        reject_df = pl.read_csv(reject_file)
        assert len(reject_df) == 1
        assert reject_df["id"][0] == 2
        assert "_error_message" in reject_df.columns

    def test_date_die_on_error_false_good_dates_typed(self, data_dir):
        """Good date values with die_on_error=false should become pl.Date."""
        input_file = data_dir / "good_dates.csv"
        input_file.write_text("id,order_date\n1,2026-03-01\n2,2026-03-02\n")
        output_file = data_dir / "out.parquet"
        config = {
            "name": "date_typed_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"},
                    ],
                }},
                {"id": "write", "type": "file_output_parquet", "config": {"path": str(output_file)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"
        df = pl.read_parquet(output_file)
        assert df["order_date"].dtype == pl.Date

    def test_date_non_iso_format_rejects_bad_dates(self, data_dir):
        """Non-ISO date format (dd/mm/yyyy) with bad values should reject properly."""
        input_file = data_dir / "dates_dmy.csv"
        input_file.write_text(
            "id,event_date\n"
            "1,01/03/2026\n"
            "2,not_a_date\n"
            "3,15/03/2026\n"
        )
        output_file = data_dir / "out.csv"
        reject_file = data_dir / "reject.csv"
        config = {
            "name": "date_dmy_reject_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "event_date", "type": "date", "date_pattern": "%d/%m/%Y"},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(output_file)}},
                {"id": "write_reject", "type": "file_output_delimited", "config": {"path": str(reject_file)}},
            ],
            "flows": [
                {"source": "read", "target": "write_main"},
                {"source": "read", "target": "write_reject", "output": "reject"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        main_df = pl.read_csv(output_file)
        assert len(main_df) == 2
        assert main_df["id"].to_list() == [1, 3]

        reject_df = pl.read_csv(reject_file)
        assert len(reject_df) == 1
        assert reject_df["id"][0] == 2
        assert "_error_message" in reject_df.columns


class TestEndToEndRejectPipeline:
    """End-to-end: Source reject + Map reject in same pipeline."""

    def test_source_and_map_reject_flows(self, data_dir):
        """Both source and map can produce reject outputs in one pipeline."""
        # Row 1: id=1, name="100", amount=50 → good at source, name casts to int at map → good
        # Row 2: id=2, name="200", amount="bad_amount" → rejected at source (bad amount)
        # Row 3: id=3, name="not_a_number", amount=75 → good at source, name fails TO_INTEGER at map → rejected at map
        # Row 4: id=4, name="400", amount=100 → good at source, name casts to int at map → good
        input_file = data_dir / "e2e.csv"
        input_file.write_text(
            "id,name,amount\n"
            "1,100,50\n"
            "2,200,bad_amount\n"
            "3,not_a_number,75\n"
            "4,400,100\n"
        )

        main_out = data_dir / "main.csv"
        source_reject_out = data_dir / "source_reject.csv"
        map_reject_out = data_dir / "map_reject.csv"

        config = {
            "name": "e2e_reject_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "die_on_error": False,
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "amount", "type": "integer"},
                    ],
                }},
                {"id": "transform", "type": "map", "config": {
                    "die_on_error": False,
                    "error_reject_output": "reject",
                    "outputs": [
                        {"name": "main", "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "name_as_int", "expression": "TO_INTEGER(name)"},
                            {"name": "amount", "expression": "amount"},
                        ]},
                        {"name": "reject", "columns": []},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(main_out)}},
                {"id": "write_source_reject", "type": "file_output_delimited", "config": {"path": str(source_reject_out)}},
                {"id": "write_map_reject", "type": "file_output_delimited", "config": {"path": str(map_reject_out)}},
            ],
            "flows": [
                {"source": "read", "target": "transform"},
                {"source": "read", "target": "write_source_reject", "output": "reject"},
                {"source": "transform", "target": "write_main"},
                {"source": "transform", "target": "write_map_reject", "output": "reject"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        # Row 2 rejected at source (bad amount)
        source_reject_df = pl.read_csv(source_reject_out)
        assert len(source_reject_df) == 1
        assert source_reject_df["id"][0] == 2
        assert "_error_message" in source_reject_df.columns

        # Row 3 rejected at map (name "not_a_number" can't cast to integer)
        map_reject_df = pl.read_csv(map_reject_out)
        assert len(map_reject_df) == 1
        assert map_reject_df["id"][0] == 3
        assert "_error_message" in map_reject_df.columns

        # Rows 1 and 4 pass through both
        main_df = pl.read_csv(main_out)
        assert len(main_df) == 2
        assert main_df["id"].to_list() == [1, 4]


class TestDatePipelineEndToEnd:
    """End-to-end: date parsing at source, sink schema validation."""

    def test_date_source_to_validated_sink(self, data_dir):
        """Full pipeline: CSV with dates -> validated sink."""
        input_file = data_dir / "orders_with_dates.csv"
        input_file.write_text(
            "id,order_date,amount\n"
            "1,2026-03-01,100\n"
            "2,2026-03-15,200\n"
            "3,2026-04-01,300\n"
        )
        output_file = data_dir / "out.parquet"
        config = {
            "name": "date_e2e",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "order_date", "type": "date", "date_pattern": "%Y-%m-%d"},
                        {"name": "amount", "type": "integer"},
                    ],
                }},
                {"id": "write", "type": "file_output_parquet", "config": {
                    "path": str(output_file),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "order_date", "type": "date"},
                        {"name": "amount", "type": "integer"},
                    ],
                }},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_parquet(output_file)
        assert df["order_date"].dtype == pl.Date
        assert len(df) == 3

    def test_sink_catches_untyped_date(self, data_dir):
        """Sink schema should catch date column that's still a string."""
        input_file = data_dir / "dates_no_schema.csv"
        input_file.write_text("id,order_date\n1,2026-03-01\n")
        output_file = data_dir / "out.csv"
        config = {
            "name": "sink_catch_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    # All-string schema — dates stay as strings
                    "schema": [
                        {"name": "id", "type": "string"},
                        {"name": "order_date", "type": "string"},
                    ],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {
                    "path": str(output_file),
                    "schema": [
                        {"name": "id", "type": "string"},
                        {"name": "order_date", "type": "date"},
                    ],
                }},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }
        result = PyETLEngine(config).execute()
        # Should fail because order_date is Utf8/String, not Date
        assert result["status"] == "error"
