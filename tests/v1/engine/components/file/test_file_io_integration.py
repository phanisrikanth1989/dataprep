"""Integration tests for file I/O components using real converter JSON configs.

These tests verify that the rewritten components work correctly with actual
converter output -- the JSON configs produced by the Talend-to-V1 converter.
This is early confidence testing (D-25), not full Phase 12 integration scope.
"""
import json
from pathlib import Path

import pytest
import pandas as pd

from src.v1.engine.components.file.file_input_delimited import FileInputDelimited
from src.v1.engine.components.file.file_output_delimited import FileOutputDelimited
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.component_registry import REGISTRY


# ------------------------------------------------------------------
# Paths to converter JSON configs
# ------------------------------------------------------------------

_CONVERTED_JSONS_DIR = Path(__file__).resolve().parents[4] / (
    "talend_xml_samples" / Path("converted_jsons")
)

_INPUT_JSON = _CONVERTED_JSONS_DIR / "Job_tFileInputDelimited_0.1.json"
_OUTPUT_JSON = _CONVERTED_JSONS_DIR / "Job_tFileOutputDelimited_0.1.json"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _load_job_config(json_path):
    """Load a converter JSON job config."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_component(job_config, component_id):
    """Extract a component dict from a job config by ID."""
    for comp in job_config["components"]:
        if comp["id"] == component_id:
            return comp
    raise ValueError(f"Component {component_id} not found in job config")


def _make_input_component(config, schema_output, tmp_filepath, global_map=None):
    """Create a FileInputDelimited from converter config, overriding filepath."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = dict(config)
    cfg["filepath"] = str(tmp_filepath)
    comp = FileInputDelimited(
        component_id="tFileInputDelimited_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = schema_output
    return comp


def _make_output_component(config, schema_input, tmp_filepath, global_map=None):
    """Create a FileOutputDelimited from converter config, overriding filepath."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = dict(config)
    cfg["filepath"] = str(tmp_filepath)
    cfg["file_exist_exception"] = False  # allow writes in tests
    comp = FileOutputDelimited(
        component_id="tFileOutputDelimited_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = schema_input
    return comp


# ------------------------------------------------------------------
# Integration tests
# ------------------------------------------------------------------


@pytest.mark.integration
class TestRegistryFileComponents:
    """After importing the file package, REGISTRY contains both components."""

    def test_registry_has_file_input_delimited(self):
        assert REGISTRY.get("FileInputDelimited") is FileInputDelimited
        assert REGISTRY.get("tFileInputDelimited") is FileInputDelimited

    def test_registry_has_file_output_delimited(self):
        assert REGISTRY.get("FileOutputDelimited") is FileOutputDelimited
        assert REGISTRY.get("tFileOutputDelimited") is FileOutputDelimited


@pytest.mark.integration
class TestInputFromConverterJson:
    """FileInputDelimited works with real converter JSON config."""

    def test_input_from_converter_json_config(self, tmp_path):
        """Load tFileInputDelimited config from converter JSON, execute it."""
        job_config = _load_job_config(_INPUT_JSON)
        comp_dict = _extract_component(job_config, "tFileInputDelimited_1")
        config = comp_dict["config"]
        schema_output = comp_dict["schema"]["output"]

        # Create test input file matching the 7-column schema
        # Schema: id(int), first_name(str), last_name(str), email(str),
        #         department(str), salary(int), hire_date(datetime)
        input_file = tmp_path / "employees.csv"
        lines = [
            "id;first_name;last_name;email;department;salary;hire_date",
            "1;Alice;Smith;alice@example.com;Engineering;95000;2020-01-15",
            "2;Bob;Jones;bob@example.com;Marketing;72000;2019-06-01",
            "3;Carol;White;carol@example.com;Engineering;88000;2021-03-20",
        ]
        input_file.write_text("\n".join(lines) + "\n", encoding="UTF-8")

        comp = _make_input_component(config, schema_output, input_file)
        result = comp.execute(None)

        assert "main" in result
        df = result["main"]
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert len(df.columns) == 7
        expected_cols = [
            "id", "first_name", "last_name", "email",
            "department", "salary", "hire_date",
        ]
        assert list(df.columns) == expected_cols


@pytest.mark.integration
class TestOutputFromConverterJson:
    """FileOutputDelimited works with real converter JSON config."""

    def test_output_from_converter_json_config(self, tmp_path):
        """Load tFileOutputDelimited config from converter JSON, execute it."""
        job_config = _load_job_config(_OUTPUT_JSON)
        comp_dict = _extract_component(job_config, "tFileOutputDelimited_1")
        config = comp_dict["config"]
        schema_input = comp_dict["schema"]["input"]

        output_file = tmp_path / "output_employees.csv"

        # Create test DataFrame matching the 6-column input schema
        test_data = pd.DataFrame([
            {"id": 1, "first_name": "Alice", "last_name": "Smith",
             "email": "alice@example.com", "department": "Engineering",
             "salary": 95000},
            {"id": 2, "first_name": "Bob", "last_name": "Jones",
             "email": "bob@example.com", "department": "Marketing",
             "salary": 72000},
        ])

        comp = _make_output_component(config, schema_input, output_file)
        result = comp.execute(test_data)

        assert output_file.exists()
        content = output_file.read_text(encoding="UTF-8")
        lines = [line for line in content.strip().split("\n") if line]

        # Converter config has include_header=true and fieldseparator="|"
        assert "|" in lines[0], "Pipe delimiter expected from converter config"
        # First line should be header since include_header=true
        assert "id" in lines[0]
        assert "first_name" in lines[0]
        # Data rows follow
        assert len(lines) == 3  # 1 header + 2 data rows


@pytest.mark.integration
class TestPipelineInputToOutput:
    """Round-trip: read file -> FileInputDelimited -> FileOutputDelimited -> verify."""

    def test_pipeline_input_to_output(self, tmp_path):
        """Read a file, pipe through output, verify round-trip data integrity."""
        # Setup: create source file
        source_file = tmp_path / "source.csv"
        lines = [
            "10;Alice;Smith",
            "20;Bob;Jones",
            "30;Carol;White",
        ]
        source_file.write_text("\n".join(lines) + "\n", encoding="ISO-8859-15")

        schema = [
            {"name": "id", "type": "str", "nullable": False},
            {"name": "first_name", "type": "str", "nullable": True},
            {"name": "last_name", "type": "str", "nullable": True},
        ]

        # Step 1: Read with FileInputDelimited
        input_config = {
            "component_type": "FileInputDelimited",
            "filepath": str(source_file),
            "fieldseparator": ";",
            "encoding": "ISO-8859-15",
            "header_rows": 0,
            "footer_rows": 0,
            "csv_option": False,
            "remove_empty_row": True,
            "check_fields_num": False,
            "check_date": False,
            "die_on_error": False,
        }
        input_comp = FileInputDelimited(
            component_id="tFID_1",
            config=input_config,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        input_comp.output_schema = schema
        read_result = input_comp.execute(None)
        read_df = read_result["main"]
        assert len(read_df) == 3

        # Step 2: Write with FileOutputDelimited
        dest_file = tmp_path / "destination.csv"
        output_config = {
            "component_type": "FileOutputDelimited",
            "filepath": str(dest_file),
            "fieldseparator": ";",
            "encoding": "ISO-8859-15",
            "include_header": False,
            "append": False,
            "csv_option": False,
            "os_line_separator": False,
            "row_separator": "\\n",
            "create_directory": True,
            "file_exist_exception": False,
            "die_on_error": False,
        }
        output_comp = FileOutputDelimited(
            component_id="tFOD_1",
            config=output_config,
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        output_comp.execute(read_df)

        # Step 3: Read back and verify
        roundtrip_comp = FileInputDelimited(
            component_id="tFID_2",
            config={**input_config, "filepath": str(dest_file)},
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        roundtrip_comp.output_schema = schema
        roundtrip_result = roundtrip_comp.execute(None)
        roundtrip_df = roundtrip_result["main"]

        assert len(roundtrip_df) == 3
        assert list(roundtrip_df.columns) == ["id", "first_name", "last_name"]
        assert list(roundtrip_df["first_name"]) == ["Alice", "Bob", "Carol"]


@pytest.mark.integration
class TestConverterConfigKeyCompatibility:
    """Converter JSON config keys match what engine components actually read."""

    def test_converter_config_keys_no_mapping_needed(self):
        """Config keys in converter JSON match engine expectations directly."""
        input_job = _load_job_config(_INPUT_JSON)
        input_comp = _extract_component(input_job, "tFileInputDelimited_1")
        input_config = input_comp["config"]

        # Engine reads 'fieldseparator', not 'delimiter'
        assert "fieldseparator" in input_config
        assert "delimiter" not in input_config

        # Engine reads 'filepath', not 'file_path'
        assert "filepath" in input_config
        assert "file_path" not in input_config

        output_job = _load_job_config(_OUTPUT_JSON)
        output_comp = _extract_component(output_job, "tFileOutputDelimited_1")
        output_config = output_comp["config"]

        # Engine reads 'fieldseparator', not 'delimiter'
        assert "fieldseparator" in output_config
        assert "delimiter" not in output_config

        # Engine reads 'include_header', not 'include_headers'
        assert "include_header" in output_config
        assert "include_headers" not in output_config

        # Engine reads 'filepath', not 'file_path'
        assert "filepath" in output_config
        assert "file_path" not in output_config


@pytest.mark.integration
class TestEncodingRoundTrip:
    """Encoding preservation through read/write cycle."""

    def test_encoding_round_trip_iso_8859_15(self, tmp_path):
        """Write ISO-8859-15 encoded data, read it back, verify characters."""
        # ISO-8859-15 includes Euro sign and accented characters
        source_file = tmp_path / "encoded.csv"
        # Characters valid in ISO-8859-15: accented chars
        content = "1;caf\u00e9;r\u00e9sum\u00e9\n2;na\u00efve;\u00e0 la carte\n"
        source_file.write_text(content, encoding="ISO-8859-15")

        schema = [
            {"name": "id", "type": "str", "nullable": False},
            {"name": "word1", "type": "str", "nullable": True},
            {"name": "word2", "type": "str", "nullable": True},
        ]

        input_comp = FileInputDelimited(
            component_id="tFID_1",
            config={
                "filepath": str(source_file),
                "fieldseparator": ";",
                "encoding": "ISO-8859-15",
                "header_rows": 0,
                "footer_rows": 0,
                "csv_option": False,
                "remove_empty_row": True,
                "check_fields_num": False,
                "check_date": False,
                "die_on_error": False,
            },
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        input_comp.output_schema = schema
        result = input_comp.execute(None)
        df = result["main"]

        assert df.iloc[0]["word1"] == "caf\u00e9"
        assert df.iloc[0]["word2"] == "r\u00e9sum\u00e9"
        assert df.iloc[1]["word1"] == "na\u00efve"
        assert df.iloc[1]["word2"] == "\u00e0 la carte"


@pytest.mark.integration
class TestOutputEmptyInputHeaderOnly:
    """Empty input with include_header=true produces header-only file."""

    def test_output_empty_input_header_only_integration(self, tmp_path):
        """Load converter config with include_header=true, empty DataFrame."""
        job_config = _load_job_config(_OUTPUT_JSON)
        comp_dict = _extract_component(job_config, "tFileOutputDelimited_1")
        config = comp_dict["config"]
        schema_input = comp_dict["schema"]["input"]

        output_file = tmp_path / "header_only.csv"

        # Create empty DataFrame with correct columns
        columns = [col["name"] for col in schema_input]
        empty_df = pd.DataFrame(columns=columns)

        comp = _make_output_component(config, schema_input, output_file)
        comp.execute(empty_df)

        assert output_file.exists()
        content = output_file.read_text(encoding="UTF-8")
        non_empty_lines = [line for line in content.split("\n") if line.strip()]

        # Should contain exactly 1 line: the header
        assert len(non_empty_lines) == 1
        # Header should use pipe delimiter from converter config
        header_parts = non_empty_lines[0].split("|")
        assert len(header_parts) == 6
        assert header_parts[0] == "id"
        assert header_parts[1] == "first_name"
