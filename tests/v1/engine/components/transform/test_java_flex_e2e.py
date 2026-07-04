"""End-to-end test for tJavaFlex: convert the real sample .item + run it.

Proves Talend-parity for the full pipeline:
    tFileInputDelimited_1 -> tJavaFlex_1 -> tFileOutputDelimited_1

The sample job (tests/talend_xml_samples/Job_tJavaFlex_0.1.item) validates each
input row in the tJavaFlex MAIN section and sets output columns:
    valid row   -> is_valid=true, name UPPERCASED, email lowercased,
                   status="HIGH_VALUE" if amount>=1000 else "NORMAL",
                   customer_id trimmed, processed_time set, error_reason null
    invalid row -> is_valid=false, status="INVALID", error_reason set
DATA_AUTO_PROPAGATE=true (V4.0) so unset same-named columns carry through.

This is a @pytest.mark.java test: it converts via the real converter pipeline
(convert_job), runs through ETLEngine with java_config.enabled=true so tJavaFlex
uses the live Java bridge, and reads the actual delimited output file.
"""
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.converters.talend_to_v1.converter import convert_job
from src.v1.engine.engine import run_job


_FIXTURE_DIR = Path("tests/talend_xml_samples")
_ITEM_NAME = "Job_tJavaFlex_0.1.item"


def _write_input_csv(path: Path) -> None:
    """Write a small input CSV matching the sample schema.

    Schema (HEADER=1): customer_id,name,email,amount,order_date

    Rows chosen to exercise the MAIN logic:
      - fully valid, NORMAL  (amount < 1000)
      - fully valid, HIGH_VALUE (amount >= 1000), needs trim/case fixes
      - invalid email
    """
    # order_date uses the input schema's declared pattern dd-MM-yyyy.
    rows = [
        "customer_id,name,email,amount,order_date",
        "C001,alice,ALICE@EXAMPLE.COM,250.0,15-01-2024",
        "  C002  ,bob smith,Bob.Smith@Example.COM,1500.0,20-02-2024",
        "C003,carol,not-an-email,300.0,10-03-2024",
    ]
    path.write_text("\n".join(rows) + "\n", encoding="ISO-8859-15")


def _read_output_rows(path: Path) -> List[Dict[str, str]]:
    """Read the tFileOutputDelimited output (comma-separated, header row)."""
    with open(path, "r", encoding="ISO-8859-15", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=","))


@pytest.mark.java
class TestE2eJavaFlex:
    """E2E: convert the sample tJavaFlex job + run it through the live bridge."""

    def test_java_flex_sample_round_trip(self, tmp_path):
        """convert_job + run_job for the sample tJavaFlex job yields Talend-parity output."""
        item_path = _FIXTURE_DIR / _ITEM_NAME
        json_path = tmp_path / f"{_ITEM_NAME}.json"
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        _write_input_csv(input_csv)

        # ---- 1. Convert the real .item to JSON ----
        convert_job(str(item_path), str(json_path))
        assert json_path.exists(), f"convert_job did not produce {json_path}"

        # ---- 2. Patch hardcoded Windows paths + enable the Java bridge ----
        with open(json_path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)

        for comp in cfg.get("components", []):
            ctype = comp.get("type")
            if ctype == "FileInputDelimited":
                comp["config"]["filepath"] = str(input_csv)
            elif ctype == "FileOutputDelimited":
                comp["config"]["filepath"] = str(output_csv)

        cfg.setdefault("java_config", {})["enabled"] = True

        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)

        # ---- 3. Run via ETLEngine (starts the live bridge from java_config) ----
        stats = run_job(str(json_path))

        assert stats is not None, "run_job returned None"
        assert stats.get("status") in ("success", "completed"), (
            f"Job failed. status={stats.get('status')}, "
            f"component_stats={stats.get('component_stats')}"
        )

        # ---- 4. Read the output file and assert Talend-parity per row ----
        assert output_csv.exists(), (
            f"tFileOutputDelimited did not write {output_csv}. "
            f"component_stats={stats.get('component_stats')}"
        )
        out_rows = _read_output_rows(output_csv)
        assert len(out_rows) == 3, f"Expected 3 output rows, got {len(out_rows)}: {out_rows}"

        by_status = {r["customer_id"]: r for r in out_rows}

        # Auto-propagate carried the input cols into the output (customer_id present).
        assert "customer_id" in out_rows[0], (
            f"Auto-propagate failed: customer_id missing from output columns: "
            f"{list(out_rows[0].keys())}"
        )

        # Valid NORMAL row: alice (amount 250 < 1000)
        alice = by_status["C001"]
        assert alice["is_valid"].lower() == "true", f"alice is_valid: {alice}"
        assert alice["name"] == "ALICE", f"name not uppercased: {alice['name']!r}"
        assert alice["email"] == "alice@example.com", (
            f"email not lowercased: {alice['email']!r}"
        )
        assert alice["status"] == "NORMAL", f"alice status: {alice['status']!r}"
        assert alice["processed_time"], "processed_time empty for valid row"
        assert alice.get("error_reason", "") in ("", "null"), (
            f"error_reason set for valid row: {alice.get('error_reason')!r}"
        )

        # Valid HIGH_VALUE row: bob (amount 1500 >= 1000), trimmed customer_id.
        bob = by_status["C002"]
        assert bob["is_valid"].lower() == "true", f"bob is_valid: {bob}"
        assert bob["status"] == "HIGH_VALUE", f"bob status: {bob['status']!r}"
        assert bob["name"] == "BOB SMITH", f"name not uppercased: {bob['name']!r}"
        assert bob["email"] == "bob.smith@example.com", (
            f"email not lowercased: {bob['email']!r}"
        )

        # Invalid row: carol (bad email).
        carol = by_status["C003"]
        assert carol["is_valid"].lower() == "false", f"carol is_valid: {carol}"
        assert carol["status"] == "INVALID", f"carol status: {carol['status']!r}"
        assert "email" in carol["error_reason"].lower(), (
            f"error_reason should mention email: {carol['error_reason']!r}"
        )
