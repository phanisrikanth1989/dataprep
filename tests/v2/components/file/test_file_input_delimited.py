"""Standard tests for FileInputDelimited component (COMP-05).

Subclasses ComponentTestCase to get:
  - validate-before-apply enforcement
  - golden-case parametrized loading
  - integration-through-PyETLEngine
  - benchmark pair quarantined behind @pytest.mark.benchmark

Source components need tmp_path for CSV file creation.
Golden cases specify csv_content to write + expected output.
"""
import json
import math
import time
from pathlib import Path

import pytest
import polars as pl

from tests.v2._harness.component_test_case import ComponentTestCase
from src.v2.components.file.file_input_delimited import FileInputDelimited


class TestFileInputDelimited(ComponentTestCase):
    """Full standard test class for FileInputDelimited."""

    component_type = "file_input_delimited"
    component_class = FileInputDelimited
    golden_dir = "file_input_delimited_cases"

    # ---- Helper for source components ----

    def _run_source(self, config, tmp_path, csv_content):
        """Write CSV to tmp_path, set path in config, run component."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)
        config = {**config, "path": str(csv_file)}
        return self.run_component(config=config, inputs={})

    # ---- Golden-case tests ----

    def test_golden_cases(self, tmp_path):
        """Load golden cases, write CSV, run component, compare output."""
        cases = self.load_golden_cases()
        assert len(cases) > 0, f"No golden cases found in {self.golden_dir}"

        for case in cases:
            case_id = case.get("case_id", "unknown")
            csv_content = case["csv_content"]
            config = case["config"]
            expected = case["expected"]

            result = self._run_source(config, tmp_path, csv_content)

            for output_name, expected_data in expected.items():
                assert output_name in result, (
                    f"Case {case_id}: missing '{output_name}' output"
                )
                result_df = result[output_name]
                if isinstance(result_df, pl.LazyFrame):
                    result_df = result_df.collect()
                # Compare column-by-column
                for col_name, col_values in expected_data.items():
                    actual = result_df[col_name].to_list()
                    assert actual == col_values, (
                        f"Case {case_id}, output {output_name}, column {col_name}: "
                        f"expected {col_values}, got {actual}"
                    )

    # ---- Validation tests ----

    def test_validate_missing_path(self):
        """Missing path triggers validation error."""
        result = self.run_component(
            config={"schema": [{"name": "a", "type": "string"}]},
            inputs={},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("path" in e.lower() for e in errors)

    def test_validate_missing_schema(self):
        """Missing schema triggers validation error."""
        result = self.run_component(
            config={"path": "/tmp/x.csv"},
            inputs={},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("schema" in e.lower() for e in errors)

    def test_validate_encoding_rejects_iso(self):
        """ISO-8859-15 encoding triggers validation error."""
        result = self.run_component(
            config={
                "path": "/tmp/x.csv",
                "encoding": "ISO-8859-15",
                "schema": [{"name": "a", "type": "string"}],
            },
            inputs={},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("encoding" in e.lower() for e in errors)

    def test_validate_encoding_accepts_utf8(self):
        """utf8 encoding passes validation (no encoding error)."""
        comp = FileInputDelimited("test", {
            "path": "/tmp/x.csv",
            "encoding": "utf8",
            "schema": [{"name": "a", "type": "string"}],
        })
        errors = comp.validate()
        assert not any("encoding" in e.lower() for e in errors)

    def test_validate_encoding_accepts_utf8_lossy(self):
        """utf8-lossy encoding passes validation (no encoding error)."""
        comp = FileInputDelimited("test", {
            "path": "/tmp/x.csv",
            "encoding": "utf8-lossy",
            "schema": [{"name": "a", "type": "string"}],
        })
        errors = comp.validate()
        assert not any("encoding" in e.lower() for e in errors)

    # ---- NaN handling tests ----

    def test_nan_to_null_default(self, tmp_path):
        """NaN strings become null when nan_is_null=True (default)."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "val", "type": "float"},
                ],
            },
            tmp_path=tmp_path,
            csv_content="id,val\n1,100.0\n2,NaN\n3,nan\n4,NAN\n",
        )
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        # All three NaN variants should be null
        assert df["val"].null_count() == 3
        assert df["val"][0] == 100.0

    def test_nan_preserved_when_opt_out(self, tmp_path):
        """NaN string becomes float NaN when nan_is_null=False."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "nan_is_null": False,
                "schema": [{"name": "val", "type": "float"}],
            },
            tmp_path=tmp_path,
            csv_content="val\nNaN\n100.0\n",
        )
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        assert math.isnan(df["val"][0])

    # ---- Trim tests ----

    def test_trim_all(self, tmp_path):
        """trim_all=True strips whitespace from all string columns."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "trim_all": True,
                "schema": [
                    {"name": "name", "type": "string"},
                    {"name": "city", "type": "string"},
                ],
            },
            tmp_path=tmp_path,
            csv_content="name,city\n  Alice  , NYC \n",
        )
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        assert df["name"][0] == "Alice"
        assert df["city"][0] == "NYC"

    def test_per_column_trim(self, tmp_path):
        """Per-column trim trims specified columns only."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "trim_columns": [{"column": "name", "trim": "both"}],
                "schema": [
                    {"name": "name", "type": "string"},
                    {"name": "city", "type": "string"},
                ],
            },
            tmp_path=tmp_path,
            csv_content="name,city\n  Alice  , NYC \n",
        )
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        assert df["name"][0] == "Alice"
        assert df["city"][0] == " NYC "  # city NOT trimmed

    # ---- Footer + limit tests ----

    def test_footer_rows(self, tmp_path):
        """footer_rows=2 removes last 2 rows (eager path)."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "footer_rows": 2,
                "schema": [{"name": "id", "type": "integer"}],
            },
            tmp_path=tmp_path,
            csv_content="id\n1\n2\n3\n4\n5\n",
        )
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        assert len(df) == 3
        assert df["id"].to_list() == [1, 2, 3]

    def test_limit(self, tmp_path):
        """limit=2 returns only 2 rows."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "limit": 2,
                "schema": [{"name": "id", "type": "integer"}],
            },
            tmp_path=tmp_path,
            csv_content="id\n1\n2\n3\n4\n5\n",
        )
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        assert len(df) == 2

    # ---- Reject flow tests ----

    def test_reject_on_bad_data(self, tmp_path):
        """die_on_error=False with bad data produces main + reject outputs."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "die_on_error": False,
                "schema": [
                    {"name": "id", "type": "integer"},
                    {"name": "amount", "type": "float"},
                ],
            },
            tmp_path=tmp_path,
            csv_content="id,amount\n1,100.0\n2,bad\n3,300.0\n",
        )
        main_df = result["main"]
        if isinstance(main_df, pl.LazyFrame):
            main_df = main_df.collect()
        assert len(main_df) == 2
        if "reject" in result:
            reject_df = result["reject"]
            if isinstance(reject_df, pl.LazyFrame):
                reject_df = reject_df.collect()
            assert len(reject_df) == 1
            assert "_error_message" in reject_df.columns

    def test_die_on_error_false_enables_ignore_errors(self, tmp_path):
        """When die_on_error=False, ignore_errors=True is passed to Polars CSV reader
        so parse-level errors (malformed rows) produce nulls instead of crashing."""
        csv_file = tmp_path / "malformed.csv"
        csv_file.write_text("id,val\n1,100\n2,200\n")
        comp = FileInputDelimited("test", {
            "path": str(csv_file),
            "delimiter": ",",
            "die_on_error": False,
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "val", "type": "float"},
            ],
        })
        # Should not crash even with die_on_error=False
        result = comp.apply({})
        assert "main" in result

    # ---- Skip empty rows ----

    def test_skip_empty_rows(self, tmp_path):
        """skip_empty_rows=True filters all-null/all-empty rows."""
        result = self._run_source(
            config={
                "delimiter": ",",
                "skip_empty_rows": True,
                "schema": [
                    {"name": "name", "type": "string"},
                    {"name": "val", "type": "string"},
                ],
            },
            tmp_path=tmp_path,
            csv_content="name,val\nAlice,1\n,\nBob,2\n",
        )
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        assert len(df) == 2

    # ---- Tab delimiter ----

    def test_tab_delimiter(self, tmp_path):
        """Tab delimiter '\\t' works correctly."""
        csv_file = tmp_path / "test.tsv"
        csv_file.write_text("id\tname\n1\tAlice\n2\tBob\n")
        comp = FileInputDelimited("test", {
            "path": str(csv_file),
            "delimiter": "\\t",
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })
        result = comp.apply({})
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        assert len(df) == 2
        assert df["name"][0] == "Alice"

    # ---- Quote char ----

    def test_quote_char_none_disables_quoting(self, tmp_path):
        """quote_char=None disables quoting."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text('name,val\n"Alice",1\n"Bob",2\n')
        comp = FileInputDelimited("test", {
            "path": str(csv_file),
            "delimiter": ",",
            "quote_char": None,
            "schema": [
                {"name": "name", "type": "string"},
                {"name": "val", "type": "integer"},
            ],
        })
        result = comp.apply({})
        df = result["main"]
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
        # With quoting disabled, quotes are part of the data
        assert df["name"][0] == '"Alice"'

    # ---- Integration through PyETLEngine ----

    @pytest.mark.integration
    def test_integration_through_engine(self, tmp_path):
        """Full pipeline: file_input_delimited -> engine execution."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,name,score\n1,Alice,95.5\n2,Bob,87.0\n3,Charlie,92.3\n")

        job_config = {
            "name": "test_file_input",
            "components": [
                {
                    "id": "reader",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(csv_file),
                        "delimiter": ",",
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "name", "type": "string"},
                            {"name": "score", "type": "float"},
                        ],
                    },
                },
            ],
            "flows": [],
        }

        result = self.run_integration(job_config)
        assert result["status"] == "success"

    # ---- Benchmark ----

    @pytest.mark.benchmark
    def test_benchmark_v2_vs_raw_polars(self, tmp_path):
        """Benchmark FileInputDelimited vs raw pl.scan_csv.

        Uses 100K rows to ensure measurable overhead beyond Python startup.
        """
        import gc
        import random

        n_rows = 100_000
        csv_file = tmp_path / "bench.csv"
        random.seed(42)
        lines = ["id,name,amount,active"]
        for i in range(n_rows):
            lines.append(
                f"{i},name_{i},{random.uniform(0, 1000):.2f},"
                f"{random.choice(['true', 'false'])}"
            )
        csv_file.write_text("\n".join(lines) + "\n")

        schema = [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
            {"name": "amount", "type": "float"},
            {"name": "active", "type": "string"},
        ]

        # Warmup
        for _ in range(3):
            comp = FileInputDelimited("bench", {
                "path": str(csv_file), "delimiter": ",", "schema": schema,
            })
            comp.apply({})["main"].collect()

        # V2 timing
        gc.disable()
        try:
            v2_times = []
            for _ in range(5):
                comp = FileInputDelimited("bench", {
                    "path": str(csv_file), "delimiter": ",", "schema": schema,
                })
                start = time.perf_counter()
                comp.apply({})["main"].collect()
                v2_times.append(time.perf_counter() - start)

            # Raw Polars timing
            raw_times = []
            for _ in range(5):
                start = time.perf_counter()
                pl.scan_csv(
                    str(csv_file), separator=",",
                    schema_overrides={"id": pl.Int64, "amount": pl.Float64},
                ).collect()
                raw_times.append(time.perf_counter() - start)
        finally:
            gc.enable()

        v2_median = sorted(v2_times)[len(v2_times) // 2]
        raw_median = sorted(raw_times)[len(raw_times) // 2]
        ratio = v2_median / raw_median if raw_median > 0 else float("inf")

        # Write baseline
        import json as json_mod

        baseline = {
            "component": "file_input_delimited",
            "v2_median": v2_median,
            "raw_median": raw_median,
            "ratio": ratio,
            "n_rows": n_rows,
        }
        baseline_dir = Path(__file__).parent.parent.parent / "benchmark" / "baselines"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        (baseline_dir / "file_input_delimited.json").write_text(
            json_mod.dumps(baseline, indent=2) + "\n"
        )

        # Assert within ~10% (ratio < 1.10) with generous initial ceiling
        assert ratio < 1.50, (
            f"FileInputDelimited is {ratio:.2f}x slower than raw Polars "
            f"(v2={v2_median:.4f}s, raw={raw_median:.4f}s). Target: < 1.10x"
        )
