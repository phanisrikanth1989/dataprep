"""Standard tests for FileOutputDelimited component (COMP-06).

Subclasses ComponentTestCase to get:
  - validate-before-apply enforcement
  - golden-case parametrized loading
  - integration-through-PyETLEngine
  - benchmark pair quarantined behind @pytest.mark.benchmark

Sink components need tmp_path for output file creation.
Golden cases specify input_data to build a DataFrame + expected_output_contains.
"""
import json
import time
from pathlib import Path

import pytest
import polars as pl

from tests.v2._harness.component_test_case import ComponentTestCase
from src.v2.components.file.file_output_delimited import FileOutputDelimited

# Safe error-type lookup for golden-case fixtures (avoids eval()).
_ERROR_TYPES = {
    "FileExistsError": FileExistsError,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "OSError": OSError,
}


class TestFileOutputDelimited(ComponentTestCase):
    """Full standard test class for FileOutputDelimited."""

    component_type = "file_output_delimited"
    component_class = FileOutputDelimited
    golden_dir = "file_output_delimited_cases"

    # ---- Sink-specific helper ----

    def _run_sink(self, config, input_df, tmp_path):
        """Run sink component: resolve __TMP__ placeholder, consume data, return output path.

        Parameters
        ----------
        config : dict
            Component configuration. ``path`` may contain ``__TMP__`` placeholder.
        input_df : pl.DataFrame
            Input data to write.
        tmp_path : pathlib.Path
            Pytest tmp_path fixture.

        Returns
        -------
        pathlib.Path
            The resolved output file path.
        """
        # Resolve __TMP__ placeholder
        path_str = config.get("path", str(tmp_path / "output.csv"))
        path_str = path_str.replace("__TMP__", str(tmp_path))
        config = {**config, "path": path_str}

        comp = FileOutputDelimited(
            component_id="test_sink",
            config=config,
        )

        # Validate before consume
        errors = comp.validate()
        assert not errors, f"Validation failed: {errors}"

        comp.consume({"main": input_df.lazy()})
        return Path(path_str)

    # ---- Validation tests (7) ----

    def test_validate_missing_path(self):
        """Missing path triggers validation error."""
        result = self.run_component(
            config={},
            inputs={"main": pl.DataFrame({"a": [1]}).lazy()},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("path" in e.lower() for e in errors)

    def test_validate_invalid_quote_char(self):
        """Multi-character quote_char triggers validation error."""
        result = self.run_component(
            config={"path": "/tmp/x.csv", "quote_char": "abc"},
            inputs={"main": pl.DataFrame({"a": [1]}).lazy()},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("quote_char" in e for e in errors)

    def test_validate_invalid_quote_style(self):
        """Invalid quote_style triggers validation error."""
        result = self.run_component(
            config={"path": "/tmp/x.csv", "quote_style": "foo"},
            inputs={"main": pl.DataFrame({"a": [1]}).lazy()},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("quote_style" in e for e in errors)

    def test_validate_append_and_error_conflict(self):
        """Both append=True and error_if_exists=True triggers validation error."""
        result = self.run_component(
            config={"path": "/tmp/x.csv", "append": True, "error_if_exists": True},
            inputs={"main": pl.DataFrame({"a": [1]}).lazy()},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("append" in e.lower() and "error_if_exists" in e.lower() for e in errors)

    def test_validate_empty_line_terminator(self):
        """Empty string line_terminator triggers validation error."""
        result = self.run_component(
            config={"path": "/tmp/x.csv", "line_terminator": ""},
            inputs={"main": pl.DataFrame({"a": [1]}).lazy()},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("line_terminator" in e for e in errors)

    def test_validate_multi_char_delimiter(self):
        """Multi-character delimiter triggers validation error."""
        result = self.run_component(
            config={"path": "/tmp/x.csv", "delimiter": ";;"},
            inputs={"main": pl.DataFrame({"a": [1]}).lazy()},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("delimiter" in e for e in errors)

    def test_validate_append_path_is_directory(self, tmp_path):
        """append=True with path pointing to existing directory triggers validation error."""
        dir_path = tmp_path / "mydir"
        dir_path.mkdir()
        result = self.run_component(
            config={"path": str(dir_path), "append": True},
            inputs={"main": pl.DataFrame({"a": [1]}).lazy()},
            expect_validation_errors=True,
        )
        errors = result["_validation_errors"]
        assert any("directory" in e.lower() for e in errors)

    # ---- Write behavior tests (9) ----

    def test_basic_write(self, tmp_path):
        """Basic write produces CSV with header and correct rows."""
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "amount": [100.5, 200.0, 300.75],
        })
        out = self._run_sink({"path": str(tmp_path / "output.csv")}, df, tmp_path)

        content = out.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "id,name,amount"
        assert lines[1] == "1,Alice,100.5"
        assert lines[2] == "2,Bob,200.0"
        assert lines[3] == "3,Charlie,300.75"

    def test_no_header(self, tmp_path):
        """has_header=False suppresses header row."""
        df = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        out = self._run_sink(
            {"path": str(tmp_path / "output.csv"), "has_header": False},
            df, tmp_path,
        )

        content = out.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "1,Alice"
        assert lines[1] == "2,Bob"

    def test_tab_delimiter(self, tmp_path):
        """Tab delimiter produces TSV output."""
        df = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        out = self._run_sink(
            {"path": str(tmp_path / "output.tsv"), "delimiter": "\\t"},
            df, tmp_path,
        )

        content = out.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "id\tname"
        assert lines[1] == "1\tAlice"

    def test_null_value(self, tmp_path):
        """null_value config controls null string representation."""
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", None, "Charlie"],
        })
        out = self._run_sink(
            {"path": str(tmp_path / "output.csv"), "null_value": "NULL"},
            df, tmp_path,
        )

        content = out.read_text()
        assert "NULL" in content
        lines = content.strip().split("\n")
        assert lines[2] == "2,NULL"

    def test_append_mode(self, tmp_path):
        """Append mode appends to existing file without duplicate header."""
        out_path = tmp_path / "output.csv"
        # Write initial data
        df1 = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        self._run_sink({"path": str(out_path)}, df1, tmp_path)

        # Append more data
        df2 = pl.DataFrame({"id": [3, 4], "name": ["Charlie", "Dave"]})
        self._run_sink({"path": str(out_path), "append": True}, df2, tmp_path)

        content = out_path.read_text()
        lines = content.strip().split("\n")
        # Should have 1 header + 4 data rows
        assert lines[0] == "id,name"
        assert len(lines) == 5
        # Header should appear only once
        assert content.count("id,name") == 1

    def test_delete_empty_file_skips(self, tmp_path):
        """delete_empty_file=True with 0-row DataFrame does not create file."""
        out_path = tmp_path / "output.csv"
        df = pl.DataFrame({"id": pl.Series([], dtype=pl.Int64)})
        self._run_sink(
            {"path": str(out_path), "delete_empty_file": True},
            df, tmp_path,
        )
        assert not out_path.exists()

    def test_error_if_exists_raises(self, tmp_path):
        """error_if_exists=True raises FileExistsError on existing file."""
        out_path = tmp_path / "output.csv"
        out_path.write_text("existing content")

        df = pl.DataFrame({"id": [1], "name": ["Alice"]})
        with pytest.raises(FileExistsError):
            self._run_sink(
                {"path": str(out_path), "error_if_exists": True},
                df, tmp_path,
            )

    def test_schema_column_selection(self, tmp_path):
        """Schema selects subset and reorders columns."""
        df = pl.DataFrame({
            "id": [1, 2],
            "name": ["Alice", "Bob"],
            "city": ["NYC", "LA"],
            "age": [30, 25],
        })
        out = self._run_sink(
            {
                "path": str(tmp_path / "output.csv"),
                "schema": [{"name": "city"}, {"name": "name"}],
            },
            df, tmp_path,
        )

        content = out.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "city,name"
        assert lines[1] == "NYC,Alice"
        assert lines[2] == "LA,Bob"

    def test_quote_style_always(self, tmp_path):
        """quote_style='always' wraps all values in quotes."""
        df = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        out = self._run_sink(
            {
                "path": str(tmp_path / "output.csv"),
                "quote_style": "always",
                "quote_char": '"',
            },
            df, tmp_path,
        )

        content = out.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == '"id","name"'
        assert lines[1] == '"1","Alice"'
        assert lines[2] == '"2","Bob"'

    # ---- Golden-case tests ----

    def test_golden_cases(self, tmp_path):
        """Load golden cases and verify sink output matches expectations."""
        cases = self.load_golden_cases()
        assert len(cases) > 0, f"No golden cases found in {self.golden_dir}"

        for case in cases:
            case_id = case.get("case_id", "unknown")
            config = case["config"].copy()

            # Resolve __TMP__ in path
            path_str = config.get("path", str(tmp_path / f"{case_id}_output.csv"))
            path_str = path_str.replace("__TMP__", str(tmp_path))
            config["path"] = path_str
            out_path = Path(path_str)

            # Write pre-existing content if specified
            if "pre_existing_content" in case:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(case["pre_existing_content"])

            # Build input DataFrame
            input_data = case.get("input_data", {})
            if input_data:
                df = pl.DataFrame(input_data)
            else:
                # Empty DataFrame for delete_empty_file test
                df = pl.DataFrame({"_empty": pl.Series([], dtype=pl.Int64)}).drop("_empty")

            # Handle expected error cases
            if "expect_error" in case:
                error_type = case["expect_error"]
                comp = FileOutputDelimited("test_sink", config)
                errors = comp.validate()
                assert not errors, f"Case {case_id}: unexpected validation errors: {errors}"
                error_cls = _ERROR_TYPES[error_type]
                with pytest.raises(error_cls):
                    comp.consume({"main": df.lazy()})
                continue

            # Handle expect_no_file cases
            if case.get("expect_no_file"):
                comp = FileOutputDelimited("test_sink", config)
                errors = comp.validate()
                assert not errors, f"Case {case_id}: unexpected validation errors: {errors}"
                comp.consume({"main": df.lazy()})
                assert not out_path.exists(), (
                    f"Case {case_id}: file should not exist but does"
                )
                continue

            # Normal write case
            comp = FileOutputDelimited("test_sink", config)
            errors = comp.validate()
            assert not errors, f"Case {case_id}: unexpected validation errors: {errors}"
            comp.consume({"main": df.lazy()})

            assert out_path.exists(), f"Case {case_id}: output file not created"
            content = out_path.read_text()

            # Verify expected_output_contains
            for expected_line in case.get("expected_output_contains", []):
                assert expected_line in content, (
                    f"Case {case_id}: expected '{expected_line}' in output, "
                    f"got:\n{content}"
                )

            # Verify expected_header_count if specified
            if "expected_header_count" in case:
                header_line = case["expected_output_contains"][0]
                actual_count = content.count(header_line)
                assert actual_count == case["expected_header_count"], (
                    f"Case {case_id}: expected header '{header_line}' to appear "
                    f"{case['expected_header_count']} time(s), got {actual_count}"
                )

            # Clean up for next case
            if out_path.exists():
                out_path.unlink()

    # ---- Integration test ----

    @pytest.mark.integration
    def test_integration_through_engine(self, tmp_path):
        """Full pipeline: file_input_delimited -> file_output_delimited."""
        input_file = tmp_path / "input.csv"
        input_file.write_text("id,name,score\n1,Alice,95.5\n2,Bob,87.0\n3,Charlie,92.3\n")
        output_file = tmp_path / "output.csv"

        job_config = {
            "name": "test_input_to_output",
            "components": [
                {
                    "id": "reader",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "delimiter": ",",
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "name", "type": "string"},
                            {"name": "score", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "writer",
                    "type": "file_output_delimited",
                    "config": {
                        "path": str(output_file),
                        "delimiter": ",",
                    },
                },
            ],
            "flows": [
                {"source": "reader", "target": "writer"},
            ],
        }

        result = self.run_integration(job_config)
        assert result["status"] == "success"

        # Verify output file was created with correct content
        assert output_file.exists()
        content = output_file.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "id,name,score"
        assert len(lines) == 4  # header + 3 data rows

    # ---- Benchmark ----

    @pytest.mark.benchmark
    def test_benchmark_write(self, tmp_path):
        """Benchmark FileOutputDelimited vs raw Polars write_csv.

        Uses 100K rows with mixed types including columns that contain
        embedded delimiters and quote characters to measure real quoting
        overhead (not just passthrough).
        """
        import gc
        import random

        n_rows = 100_000
        random.seed(42)

        # Build diverse benchmark DataFrame with quoting-stress columns
        ids = list(range(1, n_rows + 1))
        names = [f"name_{i}" for i in range(n_rows)]
        amounts = [random.uniform(0, 10000) for _ in range(n_rows)]
        dates = [f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n_rows)]

        # Embedded delimiters: strings that contain commas
        delim_patterns = [
            "value A, part B",
            "item 1, item 2, item 3",
            "first, second",
            "alpha, beta, gamma",
            "city, state",
        ]
        descriptions_with_delimiters = [
            delim_patterns[i % len(delim_patterns)] for i in range(n_rows)
        ]

        # Embedded quotes: strings that contain double-quote characters
        quote_patterns = [
            'She said "hello"',
            'The "best" option',
            'Called "foo" bar',
            'A "test" value',
            'Known as "xyz"',
        ]
        notes_with_quotes = [
            quote_patterns[i % len(quote_patterns)] for i in range(n_rows)
        ]

        df = pl.DataFrame({
            "id": ids,
            "name": names,
            "amount": amounts,
            "date": dates,
            "description_with_delimiters": descriptions_with_delimiters,
            "notes_with_quotes": notes_with_quotes,
        })

        config = {
            "path": str(tmp_path / "bench_output.csv"),
            "quote_style": "necessary",
        }

        # Warmup (fewer for I/O-bound write)
        for i in range(2):
            out_path = tmp_path / f"warmup_{i}.csv"
            comp = FileOutputDelimited("bench", {**config, "path": str(out_path)})
            comp.consume({"main": df.lazy()})

        # V2 timing
        gc.disable()
        try:
            v2_times = []
            for i in range(5):
                out_path = tmp_path / f"v2_run_{i}.csv"
                comp = FileOutputDelimited("bench", {**config, "path": str(out_path)})
                start = time.perf_counter()
                comp.consume({"main": df.lazy()})
                v2_times.append(time.perf_counter() - start)

            # Raw Polars timing
            raw_times = []
            for i in range(5):
                out_path = tmp_path / f"raw_run_{i}.csv"
                start = time.perf_counter()
                df.write_csv(out_path)
                raw_times.append(time.perf_counter() - start)
        finally:
            gc.enable()

        v2_median = sorted(v2_times)[len(v2_times) // 2]
        raw_median = sorted(raw_times)[len(raw_times) // 2]
        ratio = v2_median / raw_median if raw_median > 0 else float("inf")

        # Get Polars version
        polars_version = pl.__version__

        # Write baseline JSON
        baseline = {
            "component": "file_output_delimited",
            "v2_median": v2_median,
            "raw_median": raw_median,
            "ratio": ratio,
            "rows": n_rows,
            "columns": 6,
            "polars_version": polars_version,
            "ceiling": 1.50,
            "note": (
                "v2 vs raw Polars write_csv, 100K rows mixed types "
                "incl. embedded delimiters and quotes"
            ),
        }
        baseline_dir = Path(__file__).parent.parent.parent / "benchmark" / "baselines"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        (baseline_dir / "file_output_delimited.json").write_text(
            json.dumps(baseline, indent=2) + "\n"
        )

        # Assert within ceiling (1.50x generous for write overhead)
        assert ratio < 1.50, (
            f"FileOutputDelimited is {ratio:.2f}x slower than raw Polars "
            f"(v2={v2_median:.4f}s, raw={raw_median:.4f}s). Target: < 1.50x"
        )
