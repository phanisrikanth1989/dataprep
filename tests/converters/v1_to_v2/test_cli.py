"""Tests for the V1-to-V2 CLI entry point."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def v1_config(tmp_path):
    """Write a minimal V1 config to a temp file."""
    cfg = {
        "job_name": "cli_test",
        "components": [
            {
                "id": "read",
                "type": "tFileInputDelimited",
                "config": {"filepath": "/data/in.csv"},
            }
        ],
        "flows": [],
    }
    p = tmp_path / "v1.json"
    p.write_text(json.dumps(cfg))
    return p


class TestCLI:
    def test_converts_file(self, v1_config, tmp_path):
        out = tmp_path / "v2.json"
        result = subprocess.run(
            [sys.executable, "-m", "src.converters.v1_to_v2", str(v1_config), str(out)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        v2 = json.loads(out.read_text())
        assert v2["name"] == "cli_test"
        assert v2["version"] == "2.0"

    def test_stdout_when_no_output(self, v1_config):
        result = subprocess.run(
            [sys.executable, "-m", "src.converters.v1_to_v2", str(v1_config)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        v2 = json.loads(result.stdout)
        assert v2["name"] == "cli_test"

    def test_missing_input_file(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "-m", "src.converters.v1_to_v2", "/nonexistent.json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_strip_metadata_flag(self, v1_config, tmp_path):
        out = tmp_path / "v2.json"
        result = subprocess.run(
            [
                sys.executable, "-m", "src.converters.v1_to_v2",
                str(v1_config), str(out), "--strip-metadata",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        v2 = json.loads(out.read_text())
        assert "_conversion_metadata" not in v2
