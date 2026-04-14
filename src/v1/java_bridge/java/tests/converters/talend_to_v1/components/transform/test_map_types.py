"""Converter type fix verification tests.

Validates that tMap and tXMLMap converters produce Python type strings
(str, int, float, bool, datetime, Decimal, object) instead of raw Talend
type strings (id_String, id_Integer, id_Long, etc.) in converted JSON configs.

Also validates all converted JSONs across the test suite use valid types.
"""

import json
import re
from pathlib import Path

import pytest


_CONVERTED_JSONS_DIR = Path(__file__).resolve().parents[4] / "talend_xml_samples" / "converted_jsons"

_VALID_TYPES = {"str", "int", "float", "bool", "datetime", "Decimal", "object"}

_RAW_TALEND_TYPE_PATTERN = re.compile(r"^id_[A-Z]")


def _find_all_type_values(obj):
    """Recursively find all string values associated with 'type' keys in a nested structure."""
    type_values = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "type" and isinstance(value, str):
                type_values.append(value)
            else:
                type_values.extend(_find_all_type_values(value))
    elif isinstance(obj, list):
        for item in obj:
            type_values.extend(_find_all_type_values(item))
    return type_values


def _find_all_string_values(obj):
    """Recursively find all string values in a nested structure."""
    values = []
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, str):
                values.append(value)
            else:
                values.extend(_find_all_string_values(value))
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str):
                values.append(item)
            else:
                values.extend(_find_all_string_values(item))
    return values


# ------------------------------------------------------------------
# TestMapConverterTypes
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMapConverterTypes:
    """Verify tMap and tXMLMap converted JSONs contain no raw Talend types."""

    def test_no_raw_talend_types_in_tmap_json(self):
        json_path = _CONVERTED_JSONS_DIR / "Job_tMap_0.1.json"
        assert json_path.exists(), f"Test fixture not found: {json_path}"

        with open(json_path) as f:
            data = json.load(f)

        all_values = _find_all_string_values(data)
        raw_types = [v for v in all_values if _RAW_TALEND_TYPE_PATTERN.match(v)]
        assert raw_types == [], (
            f"Found raw Talend types in tMap JSON: {raw_types}"
        )

    def test_no_raw_talend_types_in_txmlmap_json(self):
        json_path = _CONVERTED_JSONS_DIR / "Job_tXMLMap_0.1.json"
        assert json_path.exists(), f"Test fixture not found: {json_path}"

        with open(json_path) as f:
            data = json.load(f)

        all_values = _find_all_string_values(data)
        raw_types = [v for v in all_values if _RAW_TALEND_TYPE_PATTERN.match(v)]
        assert raw_types == [], (
            f"Found raw Talend types in tXMLMap JSON: {raw_types}"
        )

    def test_map_converter_imports_convert_type(self):
        import src.converters.talend_to_v1.components.transform.map as map_module
        assert hasattr(map_module, "convert_type"), (
            "map.py does not import convert_type"
        )

    def test_xml_map_converter_imports_convert_type(self):
        import src.converters.talend_to_v1.components.transform.xml_map as xml_map_module
        assert hasattr(xml_map_module, "convert_type"), (
            "xml_map.py does not import convert_type"
        )


# ------------------------------------------------------------------
# TestSchemaTypesAcrossAllJsons
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaTypesAcrossAllJsons:
    """Validate all converted JSONs only use valid Python type strings in schemas."""

    def test_all_converted_jsons_use_valid_types(self):
        assert _CONVERTED_JSONS_DIR.exists(), (
            f"Converted JSONs directory not found: {_CONVERTED_JSONS_DIR}"
        )

        json_files = list(_CONVERTED_JSONS_DIR.glob("*.json"))
        assert len(json_files) > 0, "No JSON files found in converted_jsons directory"

        invalid_findings = []
        for json_path in sorted(json_files):
            with open(json_path) as f:
                data = json.load(f)

            type_values = _find_all_type_values(data)
            for tv in type_values:
                if tv not in _VALID_TYPES:
                    # Some "type" keys refer to component types (e.g., "Map", "FileInputDelimited")
                    # Only flag values that look like raw Talend types (id_*)
                    if _RAW_TALEND_TYPE_PATTERN.match(tv):
                        invalid_findings.append((json_path.name, tv))

        assert invalid_findings == [], (
            f"Found raw Talend type strings in converted JSONs: {invalid_findings}"
        )
