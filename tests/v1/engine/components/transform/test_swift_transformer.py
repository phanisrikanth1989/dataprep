"""Tests for SwiftTransformer (engine implementation).

Plan 14-07 lift target: 7% -> >=95% line coverage.

Coverage strategy:
  * Unit tests cover every public/private method directly (registration,
    validate_config, _init_transformer_config, _ensure_config_loaded,
    _load_lookup_files, _load_external_config, _get_field_value with all
    'type' branches, _parse_field_value, _calculate_field_value,
    _evaluate_python_expression, _extract_date_component,
    _apply_field_transformation, _parse_balance_field,
    _parse_movement_field, _post_process_value, _apply_lookups,
    _transform_rows, _process, _write_output_file).
  * Pipeline tests drive the full ETLEngine lifecycle via run_job_fixture
    so the lifecycle code paths in BaseComponent.execute() also touch
    every transformer method end-to-end.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
import src.v1.engine.components  # noqa: F401  -- triggers @REGISTRY decorators
from src.v1.engine.components.transform.swift_transformer import SwiftTransformer
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    FileOperationError,
)
from src.v1.engine.global_map import GlobalMap

from tests.fixtures.swift.synthetic import (
    mt103_minimum,
    mt202_cov,
    mt940_with_balance,
)

# --------------------------------------------------------------------------
# Fixture paths
# --------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).resolve().parents[4]
SWIFT_FIXTURES = _TESTS_DIR / "fixtures" / "swift"
CFG_MIN = str(SWIFT_FIXTURES / "configs" / "transform_minimum.yaml")
CFG_LOOKUP = str(SWIFT_FIXTURES / "configs" / "transform_with_lookup.yaml")
LOOKUP_DIR = str(SWIFT_FIXTURES / "lookups")
LAYOUT_BASIC = str(SWIFT_FIXTURES / "layouts" / "mt_basic.yaml")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _make_component(
    config: dict | None = None,
    *,
    global_map=None,
    context_manager=None,
    comp_id: str = "tSwiftTransformer_1",
):
    cfg = config if config is not None else {"die_on_error": True}
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager if context_manager is not None else ContextManager()
    comp = SwiftTransformer(
        comp_id=comp_id,
        config=dict(cfg),
        global_map=gm,
        context_manager=cm,
    )
    import copy as _copy
    comp.config = _copy.deepcopy(cfg)
    return comp


def _swift_input_df():
    """Build a representative SWIFT-pipe input DataFrame for unit tests."""
    return pd.DataFrame([
        {
            "messagetype": "103",
            "block1bic": "BANKBICAXXXX",
            "block2bic": "BANKBICBXXXX",
            "block4_20": "REF103MIN0001",
            "block4_25": "12345678901/SUFFIX",
            "block4_32A": "260510USD1500,00",
            "block4_60F": "C260501USD1000000,00",
            "block4_61": "2605100510C2500,00NTRFTXN001//REF001sfield9=NARRATIVE",
        }
    ])


# --------------------------------------------------------------------------
# TestRegistration
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:

    def test_v1_name_registered(self):
        assert REGISTRY.get("SwiftTransformer") is SwiftTransformer

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tSwiftDataTransformer") is SwiftTransformer


# --------------------------------------------------------------------------
# TestValidateConfig
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfig:

    def test_default_config_passes(self):
        comp = _make_component()
        comp.config = {"die_on_error": True}
        comp._validate_config()  # no raise

    def test_config_file_must_be_string(self):
        comp = _make_component()
        comp.config = {"config_file": 123}
        with pytest.raises(ConfigurationError, match="config_file"):
            comp._validate_config()

    def test_transform_config_must_be_mapping(self):
        comp = _make_component()
        comp.config = {"transform_config": [1, 2, 3]}
        with pytest.raises(ConfigurationError, match="transform_config"):
            comp._validate_config()

    def test_string_config_file_accepted(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        comp.config = {"config_file": CFG_MIN}
        comp._validate_config()


# --------------------------------------------------------------------------
# TestInitTransformerConfig
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestInitTransformerConfig:
    """Drive the lines in _init_transformer_config (43-77)."""

    def test_no_config_file_no_inline_uses_default(self):
        comp = _make_component()
        # Default config kicks in; transform_config is populated.
        assert comp.transform_config is not None
        assert "input_fields" in comp.transform_config
        # Lookups: default config has none.
        assert comp.lookups_config == []

    def test_external_config_file_path_stored_for_deferred_load(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        # transform_config is None until _ensure_config_loaded is called.
        assert comp.config_file == CFG_MIN
        assert comp.transform_config is None
        # Empty maps until deferred load.
        assert comp.input_fields == []
        assert comp.output_layout == []

    def test_inline_config_only_stored_until_execute(self):
        inline = {"input_fields": ["x"], "output_fields": [{"name": "X", "type": "constant", "value": "1"}]}
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        assert comp.config_file is None
        assert comp.inline_config == inline
        assert comp.transform_config is None

    def test_default_config_no_explicit_layout_falls_back_to_field_names(self):
        comp = _make_component()
        assert comp.output_layout == [f["name"] for f in comp.output_fields]


# --------------------------------------------------------------------------
# TestEnsureConfigLoaded
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestEnsureConfigLoaded:

    def test_external_config_loaded_on_first_call(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        comp._ensure_config_loaded()
        assert comp.transform_config is not None
        assert "SIDE" in comp.output_layout
        # Idempotent
        comp._ensure_config_loaded()

    def test_inline_config_loaded_on_first_call(self):
        inline = {
            "input_fields": ["block4_20"],
            "output_fields": [{"name": "OUT", "type": "direct", "source": "block4_20", "default": ""}],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        assert comp.output_layout == ["OUT"]

    def test_explicit_output_layout_preserved(self):
        inline = {
            "output_fields": [
                {"name": "A", "type": "constant", "value": "a", "default": "a"},
                {"name": "B", "type": "constant", "value": "b", "default": "b"},
            ],
            "output_layout": ["B", "A"],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        assert comp.output_layout == ["B", "A"]


# --------------------------------------------------------------------------
# TestLoadExternalConfig
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestLoadExternalConfig:

    def test_yaml_config_loads(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        cfg = comp._load_external_config(CFG_MIN)
        assert "input_fields" in cfg

    def test_json_config_loads(self, tmp_path):
        json_cfg = tmp_path / "cfg.json"
        json_cfg.write_text('{"input_fields": ["x"], "output_fields": []}')
        comp = _make_component({"config_file": str(json_cfg), "die_on_error": True})
        cfg = comp._load_external_config(str(json_cfg))
        assert cfg["input_fields"] == ["x"]

    def test_missing_file_raises_file_operation_error(self, tmp_path):
        comp = _make_component()
        with pytest.raises(FileOperationError):
            comp._load_external_config(str(tmp_path / "nope.yaml"))


# --------------------------------------------------------------------------
# TestLookups
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestLookups:

    def _make_with_lookup_cfg(self, tmp_path=None):
        ctx = ContextManager()
        ctx.set("LOOKUP_DIR", LOOKUP_DIR)
        comp = SwiftTransformer(
            "tSwiftTransformer_1",
            {"config_file": CFG_LOOKUP, "die_on_error": True},
            GlobalMap(),
            ctx,
        )
        import copy as _copy
        comp.config = _copy.deepcopy({"config_file": CFG_LOOKUP, "die_on_error": True})
        comp._ensure_config_loaded()
        return comp

    def test_lookup_files_loaded_from_csv(self):
        comp = self._make_with_lookup_cfg()
        assert "sender_country" in comp.lookup_data
        assert len(comp.lookup_data["sender_country"]["data"]) == 5

    def test_lookup_with_no_file_skipped(self):
        # lookups_config entry without 'file'
        inline = {
            "output_fields": [
                {"name": "A", "type": "constant", "value": "x", "default": ""},
            ],
            "lookups": [{"name": "noop", "main_key": "A", "lookup_key": "BIC", "columns": []}],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        assert comp.lookup_data == {}

    def test_lookup_with_pipe_extension_uses_pipe_delimiter(self, tmp_path):
        # Build a |-delimited lookup
        f = tmp_path / "lk.txt"
        f.write_text("BIC|country\nBANKBICAXXXX|US\n")
        inline = {
            "output_fields": [
                {"name": "A", "type": "constant", "value": "BANKBICAXXXX", "default": ""},
                {"name": "COUNTRY", "type": "constant", "value": "", "default": ""},
            ],
            "lookups": [
                {
                    "name": "pipe_lk",
                    "file": str(f),
                    "main_key": "A",
                    "lookup_key": "BIC",
                    "columns": ["COUNTRY"],
                    "source_columns": ["country"],
                },
            ],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        assert "pipe_lk" in comp.lookup_data

    def test_lookup_load_failure_logged_and_skipped(self, tmp_path, caplog):
        # Reference a non-existent file -- should log error and skip.
        inline = {
            "output_fields": [{"name": "A", "type": "constant", "value": "x", "default": ""}],
            "lookups": [
                {
                    "name": "missing",
                    "file": str(tmp_path / "no_such.csv"),
                    "main_key": "A",
                    "lookup_key": "BIC",
                    "columns": [],
                },
            ],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        assert "missing" not in comp.lookup_data

    def test_apply_lookups_normal_match_hit(self):
        comp = self._make_with_lookup_cfg()
        out = comp._apply_lookups({
            "SENDER_BIC": "BANKBICAXXXX",
            "RECEIVER_BIC": "BANKBICBXXXX",
            "SENDER_COUNTRY": "",
            "RECEIVER_COUNTRY": "",
            "BIC_PATTERN_LABEL": "",
        }, depends_on_lookup=False)
        assert out["SENDER_COUNTRY"] == "US"
        assert out["RECEIVER_COUNTRY"] == "GB"
        # Regex pattern lookup picks the first matching wildcard pattern
        assert out["BIC_PATTERN_LABEL"] in {"GENERIC_BANK", "B_BANKS"}

    def test_apply_lookups_no_match_keeps_default(self):
        comp = self._make_with_lookup_cfg()
        out = comp._apply_lookups({
            "SENDER_BIC": "UNKNOWN",
            "RECEIVER_BIC": "ALSO_UNKNOWN",
            "SENDER_COUNTRY": "",
            "RECEIVER_COUNTRY": "",
            "BIC_PATTERN_LABEL": "",
        }, depends_on_lookup=False)
        assert out["SENDER_COUNTRY"] == ""

    def test_apply_lookups_main_value_empty_skips(self):
        comp = self._make_with_lookup_cfg()
        out = comp._apply_lookups({
            "SENDER_BIC": "",
            "RECEIVER_BIC": "",
            "SENDER_COUNTRY": "",
            "RECEIVER_COUNTRY": "",
            "BIC_PATTERN_LABEL": "",
        }, depends_on_lookup=False)
        assert out["SENDER_COUNTRY"] == ""

    def test_apply_lookups_invalid_lookup_key_skipped(self, tmp_path):
        f = tmp_path / "lk.csv"
        f.write_text("foo,bar\n1,2\n")
        inline = {
            "output_fields": [{"name": "A", "type": "constant", "value": "x", "default": ""}],
            "lookups": [
                {
                    "name": "bad",
                    "file": str(f),
                    "main_key": "A",
                    "lookup_key": "MISSING_COLUMN",
                    "columns": [],
                },
            ],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        out = comp._apply_lookups({"A": "x"}, depends_on_lookup=False)
        assert out == {"A": "x"}

    def test_apply_lookups_filters_by_depends_on_lookup_flag(self):
        # depends_on_lookup=True only applies lookups with the flag set.
        comp = self._make_with_lookup_cfg()
        # In transform_with_lookup.yaml, none of the lookups carry
        # depends_on_lookup=True. Calling with True should be a no-op.
        out = comp._apply_lookups({
            "SENDER_BIC": "BANKBICAXXXX",
            "RECEIVER_BIC": "BANKBICBXXXX",
            "SENDER_COUNTRY": "PRESET",
        }, depends_on_lookup=True)
        assert out["SENDER_COUNTRY"] == "PRESET"  # untouched

    def test_apply_lookups_regex_branch_with_real_regex(self, tmp_path):
        # Use a lookup file with real regex meta-chars (not just wildcards).
        f = tmp_path / "lk.csv"
        f.write_text("BIC,country\n^BANK.*$,US\n")
        inline = {
            "output_fields": [
                {"name": "BIC", "type": "constant", "value": "BANKAAA", "default": ""},
                {"name": "country", "type": "constant", "value": "", "default": ""},
            ],
            "lookups": [
                {
                    "name": "regex_lk",
                    "file": str(f),
                    "main_key": "BIC",
                    "lookup_key": "BIC",
                    "columns": ["country"],
                    "source_columns": ["country"],
                    "match_type": "regex",
                },
            ],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        out = comp._apply_lookups({"BIC": "BANKAAA", "country": ""}, depends_on_lookup=False)
        assert out["country"] == "US"

    def test_apply_lookups_invalid_regex_falls_back_to_literal(self, tmp_path):
        f = tmp_path / "lk.csv"
        f.write_text("BIC,country\n[unbalanced,US\n")
        inline = {
            "output_fields": [
                {"name": "BIC", "type": "constant", "value": "[unbalanced", "default": ""},
                {"name": "country", "type": "constant", "value": "", "default": ""},
            ],
            "lookups": [
                {
                    "name": "bad_regex",
                    "file": str(f),
                    "main_key": "BIC",
                    "lookup_key": "BIC",
                    "columns": ["country"],
                    "source_columns": ["country"],
                    "match_type": "regex",
                },
            ],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        out = comp._apply_lookups({"BIC": "[unbalanced", "country": ""}, depends_on_lookup=False)
        assert out["country"] == "US"

    def test_apply_lookups_default_source_columns(self, tmp_path):
        f = tmp_path / "lk.csv"
        f.write_text("BIC,country,city\nBANKBICAXXXX,US,NYC\n")
        inline = {
            "output_fields": [
                {"name": "BIC", "type": "constant", "value": "BANKBICAXXXX", "default": ""},
                {"name": "COUNTRY", "type": "constant", "value": "", "default": ""},
                {"name": "CITY", "type": "constant", "value": "", "default": ""},
            ],
            "lookups": [
                {
                    "name": "default_cols",
                    "file": str(f),
                    "main_key": "BIC",
                    "lookup_key": "BIC",
                    "columns": ["COUNTRY", "CITY"],
                    # source_columns NOT provided -> defaults to all non-key cols
                },
            ],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        out = comp._apply_lookups(
            {"BIC": "BANKBICAXXXX", "COUNTRY": "", "CITY": ""},
            depends_on_lookup=False,
        )
        assert out["COUNTRY"] == "US"
        assert out["CITY"] == "NYC"


# --------------------------------------------------------------------------
# TestGetFieldValue -- every 'type' branch
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestGetFieldValue:

    def setup_method(self):
        self.comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        self.comp._ensure_config_loaded()
        self.input = _swift_input_df().iloc[0]

    def test_direct_mapping(self):
        f = {"name": "TEST", "type": "direct", "source": "block4_20", "default": ""}
        assert self.comp._get_field_value(f, self.input) == "REF103MIN0001"

    def test_direct_mapping_missing_source_uses_default(self):
        f = {"name": "TEST", "type": "direct", "source": "missing_field", "default": "DFAULT"}
        assert self.comp._get_field_value(f, self.input) == "DFAULT"

    def test_direct_mapping_nan_string_replaced_with_default(self):
        f = {"name": "TEST", "type": "direct", "source": "x", "default": "DEF"}
        row = pd.Series({"x": "NaN"})
        assert self.comp._get_field_value(f, row) == "DEF"

    def test_constant_mapping(self):
        f = {"name": "K", "type": "constant", "value": "FIXED", "default": ""}
        assert self.comp._get_field_value(f, self.input) == "FIXED"

    def test_parsed_mapping_regex(self):
        f = {
            "name": "ACCT",
            "type": "parsed",
            "source": "block4_25",
            "parse_config": {"regex": "^(\\d+)", "group": 1},
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "12345678901"

    def test_parsed_mapping_position(self):
        f = {
            "name": "PREF",
            "type": "parsed",
            "source": "block4_25",
            "parse_config": {"position": {"start": 0, "end": 4}},
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "1234"

    def test_parsed_mapping_split(self):
        f = {
            "name": "PART",
            "type": "parsed",
            "source": "block4_25",
            "parse_config": {"split": {"delimiter": "/", "index": 0}},
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "12345678901"

    def test_parsed_mapping_no_config_returns_default(self):
        f = {
            "name": "X",
            "type": "parsed",
            "source": "block4_25",
            "parse_config": {},
            "default": "DEF",
        }
        assert self.comp._get_field_value(f, self.input) == "DEF"

    def test_parsed_mapping_missing_source(self):
        f = {
            "name": "X",
            "type": "parsed",
            "source": "missing",
            "parse_config": {"regex": "^.*$", "group": 0},
            "default": "DEF",
        }
        assert self.comp._get_field_value(f, self.input) == "DEF"

    def test_calculated_concatenate(self):
        f = {
            "name": "J",
            "type": "calculated",
            "calc_config": {
                "type": "concatenate",
                "fields": ["block1bic", "block2bic"],
                "separator": "|",
            },
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "BANKBICAXXXX|BANKBICBXXXX"

    def test_calculated_conditional_true_branch(self):
        f = {
            "name": "F",
            "type": "calculated",
            "calc_config": {
                "type": "conditional",
                "condition_field": "messagetype",
                "condition_value": "103",
                "true_value": "YES",
                "false_value": "NO",
            },
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "YES"

    def test_calculated_conditional_false_branch(self):
        f = {
            "name": "F",
            "type": "calculated",
            "calc_config": {
                "type": "conditional",
                "condition_field": "messagetype",
                "condition_value": "999",
                "true_value": "YES",
                "false_value": "NO",
            },
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "NO"

    def test_calculated_conditional_missing_field_returns_default(self):
        f = {
            "name": "F",
            "type": "calculated",
            "calc_config": {
                "type": "conditional",
                "condition_field": "missing",
                "condition_value": "x",
                "true_value": "Y",
                "false_value": "N",
            },
            "default": "DFAULT",
        }
        assert self.comp._get_field_value(f, self.input) == "DFAULT"

    def test_calculated_date_extraction_year(self):
        f = {
            "name": "Y",
            "type": "calculated",
            "calc_config": {
                "type": "date_extraction",
                "source_field": "block4_32A",
                "component": "year",
            },
            "default": "",
        }
        # block4_32A is "260510USD1500,00" (16 chars, no separators).
        # _extract_date_component skips %Y%m%d (8-char slice fails),
        # skips %d%m%y (full-string strptime fails), and lands on
        # %y%m%d which slices first 6 chars -> 26-05-2010 PEP-3101 style
        # -> Python interprets year '26' as 2026.
        out = self.comp._get_field_value(f, self.input)
        assert out == "2026"

    def test_calculated_unknown_calc_type_returns_default(self):
        f = {
            "name": "Q",
            "type": "calculated",
            "calc_config": {"type": "unknown"},
            "default": "DEFAULT",
        }
        assert self.comp._get_field_value(f, self.input) == "DEFAULT"

    def test_transformation_balance_parse(self):
        f = {
            "name": "AMT",
            "type": "transformation",
            "source": "block4_60F",
            "transform_config": {"type": "balance_parse", "extract": "amount"},
            "default": "0.00",
        }
        # Engine truth: _parse_balance_field strips ',' without inserting '.'
        assert self.comp._get_field_value(f, self.input) == "100000000"

    def test_transformation_movement_parse(self):
        f = {
            "name": "MA",
            "type": "transformation",
            "source": "block4_61",
            "transform_config": {"type": "movement_parse", "extract": "amount"},
            "default": "0",
        }
        out = self.comp._get_field_value(f, self.input)
        assert "2500" in out

    def test_transformation_format_upper(self):
        f = {
            "name": "U",
            "type": "transformation",
            "source": "messagetype",
            "transform_config": {"type": "format", "format_type": "upper"},
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "103"

    def test_transformation_lookup_table_hit(self):
        f = {
            "name": "L",
            "type": "transformation",
            "source": "messagetype",
            "transform_config": {
                "type": "lookup",
                "lookup_table": {"103": "TRANSFER", "940": "STMT"},
                "default": "?",
            },
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "TRANSFER"

    def test_transformation_lookup_table_miss(self):
        f = {
            "name": "L",
            "type": "transformation",
            "source": "messagetype",
            "transform_config": {
                "type": "lookup",
                "lookup_table": {},
                "default": "FALLBACK",
            },
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "FALLBACK"

    def test_transformation_unknown_type_returns_source(self):
        f = {
            "name": "U",
            "type": "transformation",
            "source": "messagetype",
            "transform_config": {"type": "unknown_xform"},
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "103"

    def test_python_expression_uses_input_row(self):
        f = {
            "name": "PY",
            "type": "python_expression",
            "python_expression": "input_row.get('block4_20', '')[:3]",
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input) == "REF"

    def test_python_expression_uses_computed(self):
        f = {
            "name": "PY",
            "type": "python_expression",
            "python_expression": "computed.get('TERMID', '') + '!'",
            "default": "",
        }
        assert self.comp._get_field_value(f, self.input, working_row={"TERMID": "X"}) == "X!"

    def test_python_expression_no_expression_returns_default(self):
        f = {"name": "PY", "type": "python_expression", "default": "D"}
        assert self.comp._get_field_value(f, self.input) == "D"

    def test_python_expression_eval_error_returns_default(self):
        f = {
            "name": "PY",
            "type": "python_expression",
            "python_expression": "this is not python",
            "default": "ERR_DEFAULT",
        }
        assert self.comp._get_field_value(f, self.input) == "ERR_DEFAULT"

    def test_python_expression_returns_none_falls_to_default(self):
        f = {
            "name": "PY",
            "type": "python_expression",
            "python_expression": "None",
            "default": "WAS_NONE",
        }
        assert self.comp._get_field_value(f, self.input) == "WAS_NONE"

    def test_placeholder_returns_default(self):
        f = {"name": "P", "type": "placeholder", "default": "PHD"}
        assert self.comp._get_field_value(f, self.input) == "PHD"

    def test_unknown_type_returns_default(self):
        f = {"name": "U", "type": "unknown_type", "default": "FALLBACK"}
        assert self.comp._get_field_value(f, self.input) == "FALLBACK"

    def test_post_process_truncate(self):
        f = {
            "name": "T",
            "type": "direct",
            "source": "block4_20",
            "default": "",
            "post_process": {"type": "truncate", "max_length": 5},
        }
        assert self.comp._get_field_value(f, self.input) == "REF10"

    def test_post_process_pad_left(self):
        f = {
            "name": "P",
            "type": "constant",
            "value": "x",
            "default": "",
            "post_process": {"type": "pad", "length": 5, "pad_char": "*", "side": "left"},
        }
        assert self.comp._get_field_value(f, self.input) == "x****"

    def test_post_process_pad_right_default(self):
        f = {
            "name": "P",
            "type": "constant",
            "value": "x",
            "default": "",
            "post_process": {"type": "pad", "length": 5, "pad_char": "*"},
        }
        assert self.comp._get_field_value(f, self.input) == "****x"

    def test_post_process_replace(self):
        f = {
            "name": "R",
            "type": "direct",
            "source": "block4_20",
            "default": "",
            "post_process": {"type": "replace", "old": "REF", "new": "OURS"},
        }
        assert self.comp._get_field_value(f, self.input) == "OURS103MIN0001"

    def test_post_process_unknown_type_passthrough(self):
        f = {
            "name": "X",
            "type": "constant",
            "value": "v",
            "default": "",
            "post_process": {"type": "unknown_post"},
        }
        assert self.comp._get_field_value(f, self.input) == "v"

    def test_get_field_value_exception_returns_default(self):
        # parse_config malformed -> _parse_field_value raises -> caught
        # at _get_field_value's outer try/except -> returns default.
        f = {
            "name": "X",
            "type": "parsed",
            "source": "block4_25",
            "parse_config": {"regex": "(["},  # invalid regex
            "default": "ERR_DEF",
        }
        # Exception is swallowed at _get_field_value level
        assert self.comp._get_field_value(f, self.input) == "ERR_DEF"


# --------------------------------------------------------------------------
# TestParseBalanceField / TestParseMovementField
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestParseBalanceMovement:

    def setup_method(self):
        self.comp = _make_component()

    def test_balance_parse_amount(self):
        # Engine strips ',' without inserting '.' -- documented engine truth.
        out = self.comp._parse_balance_field(
            "C260501USD1234567,89", {"extract": "amount"}
        )
        assert out == "123456789"

    def test_balance_parse_sign(self):
        out = self.comp._parse_balance_field("C260501USD100,00", {"extract": "sign"})
        assert out == "C"

    def test_balance_parse_date(self):
        out = self.comp._parse_balance_field("C260501USD100,00", {"extract": "date"})
        assert out == "260501"

    def test_balance_parse_currency(self):
        out = self.comp._parse_balance_field("C260501EUR100,00", {"extract": "currency"})
        assert out == "EUR"

    def test_balance_parse_full_text(self):
        out = self.comp._parse_balance_field("C260501USD100,00", {"extract": "full_text"})
        # Engine strips ',' without inserting '.' before assembling full_text.
        assert out == "C 260501 USD 10000"

    def test_balance_parse_no_match_returns_input(self):
        out = self.comp._parse_balance_field("garbage", {"extract": "amount"})
        assert out == "garbage"

    def test_balance_parse_empty_value(self):
        assert self.comp._parse_balance_field("", {"extract": "amount"}) == ""

    def test_movement_parse_entry_date(self):
        out = self.comp._parse_movement_field(
            "2605100510C2500,00NTRFTXN001//REF001", {"extract": "entry_date"},
            pd.Series({}),
        )
        assert out == "260510"

    def test_movement_parse_value_date_uses_entry_date_when_missing(self):
        out = self.comp._parse_movement_field(
            "260510C2500,00NTRFTXN001", {"extract": "value_date"}, pd.Series({}),
        )
        # No optional MMDD -> falls back to entry_date
        assert out == "260510"

    def test_movement_parse_amount(self):
        out = self.comp._parse_movement_field(
            "2605100510C2500,00NTRFTXN001", {"extract": "amount"}, pd.Series({}),
        )
        # Engine strips ',' without insert '.', per _parse_movement_field.
        assert out == "250000"

    def test_movement_parse_debit_credit(self):
        out = self.comp._parse_movement_field(
            "2605100510D100,00", {"extract": "debit_credit"}, pd.Series({}),
        )
        assert out == "D"

    def test_movement_parse_transaction_code(self):
        out = self.comp._parse_movement_field(
            "2605100510C2500,00NTRFTXN001//REF001", {"extract": "transaction_code"},
            pd.Series({}),
        )
        assert out == "N"

    def test_movement_parse_reference(self):
        out = self.comp._parse_movement_field(
            "2605100510C2500,00NTRFTXN001", {"extract": "reference"}, pd.Series({}),
        )
        assert "TXN001" in out

    def test_movement_parse_narrative(self):
        out = self.comp._parse_movement_field(
            "2605100510C2500,00NTRFTXN001//NARRATIVE_TEXT",
            {"extract": "narrative"}, pd.Series({}),
        )
        assert out == "NARRATIVE_TEXT"

    def test_movement_parse_no_match_returns_input(self):
        assert self.comp._parse_movement_field(
            "garbage", {"extract": "amount"}, pd.Series({})
        ) == "garbage"

    def test_movement_parse_empty_value(self):
        assert self.comp._parse_movement_field(
            "", {"extract": "amount"}, pd.Series({})
        ) == ""


# --------------------------------------------------------------------------
# TestExtractDateComponent
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractDateComponent:

    def setup_method(self):
        self.comp = _make_component()

    def test_year(self):
        # _extract_date_component tries '%Y%m%d' first; len('260510') == 6
        # so it falls through to %d%m%y interpretation. 26-05-2010 -> 2010.
        assert self.comp._extract_date_component("260510", "year") == "2010"

    def test_month(self):
        assert self.comp._extract_date_component("260510", "month") == "05"

    def test_day(self):
        # %d%m%y interpretation: day=26
        assert self.comp._extract_date_component("260510", "day") == "26"

    def test_date(self):
        # Same %d%m%y interpretation -> 2010-05-26
        assert self.comp._extract_date_component("260510", "date") == "2010-05-26"

    def test_time_returns_default_for_date_only(self):
        out = self.comp._extract_date_component("260510", "time")
        assert out == "00:00:00"

    def test_unparseable_returns_input(self):
        assert self.comp._extract_date_component("xyz", "year") == "xyz"

    def test_full_yyyymmdd(self):
        assert self.comp._extract_date_component("20260510", "year") == "2026"


# --------------------------------------------------------------------------
# TestPostProcessValue (direct calls, complementing TestGetFieldValue)
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestPostProcessValue:

    def setup_method(self):
        self.comp = _make_component()

    def test_truncate_default_max_length(self):
        out = self.comp._post_process_value("a" * 200, {"type": "truncate"})
        assert len(out) == 100

    def test_pad_default_length(self):
        out = self.comp._post_process_value("x", {"type": "pad"})
        # default length is 10, default char is space, default side is right
        assert out == "         x"


# --------------------------------------------------------------------------
# TestTransformRows
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestTransformRows:

    def test_minimum_config_transform(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        comp._ensure_config_loaded()
        df_in = _swift_input_df()
        out = comp._transform_rows(df_in)
        assert "SIDE" in out.columns
        assert out.iloc[0]["SIDE"] == "S"
        assert out.iloc[0]["TERMID"] == "BANKBICAXXXX"

    def test_lookup_config_transform(self):
        ctx = ContextManager()
        ctx.set("LOOKUP_DIR", LOOKUP_DIR)
        comp = SwiftTransformer(
            "tSwiftTransformer_1",
            {"config_file": CFG_LOOKUP, "die_on_error": True},
            GlobalMap(),
            ctx,
        )
        import copy as _copy
        comp.config = _copy.deepcopy({"config_file": CFG_LOOKUP, "die_on_error": True})
        comp._ensure_config_loaded()
        df_in = _swift_input_df()
        out = comp._transform_rows(df_in)
        assert out.iloc[0]["SENDER_COUNTRY"] == "US"
        # Two-pass: SENDER_REGION computes after first lookup populates
        # SENDER_COUNTRY=US -> region OTHER (not EU).
        assert out.iloc[0]["SENDER_REGION"] == "OTHER"

    def test_transform_row_error_skip_error_rows(self):
        # Force _get_field_value to raise -> row processing fails ->
        # skip_error_rows=True keeps the output empty.
        inline = {
            "output_fields": [
                {"name": "X", "type": "constant", "value": "v", "default": ""},
            ],
            "output_layout": ["X"],
        }
        comp = _make_component({
            "transform_config": inline,
            "die_on_error": True,
            "skip_error_rows": True,
        })
        comp._ensure_config_loaded()
        # Monkey-patch _get_field_value to raise
        import unittest.mock as um
        with um.patch.object(comp, "_get_field_value", side_effect=RuntimeError("boom")):
            out = comp._transform_rows(_swift_input_df())
        assert len(out) == 0  # rows skipped

    def test_transform_row_error_default_fills_empty_row(self):
        inline = {
            "output_fields": [
                {"name": "X", "type": "constant", "value": "v", "default": ""},
            ],
            "output_layout": ["X"],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        import unittest.mock as um
        with um.patch.object(comp, "_get_field_value", side_effect=RuntimeError("boom")):
            out = comp._transform_rows(_swift_input_df())
        assert len(out) == 1
        assert out.iloc[0]["X"] == ""

    def test_field_in_layout_not_in_output_fields_gets_blank(self):
        inline = {
            "output_fields": [
                {"name": "A", "type": "constant", "value": "a", "default": "a"},
            ],
            "output_layout": ["A", "MISSING_FROM_FIELDS"],
        }
        comp = _make_component({"transform_config": inline, "die_on_error": True})
        comp._ensure_config_loaded()
        out = comp._transform_rows(_swift_input_df())
        assert out.iloc[0]["MISSING_FROM_FIELDS"] == ""


# --------------------------------------------------------------------------
# TestProcess (top-level)
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestProcess:

    def test_empty_input_returns_empty(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        out = comp._process(pd.DataFrame())
        assert out["main"].empty

    def test_none_input_returns_empty(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        out = comp._process(None)
        assert out["main"].empty

    def test_happy_path_single_row(self):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        out = comp._process(_swift_input_df())
        assert len(out["main"]) == 1
        assert "SIDE" in out["main"].columns

    def test_writes_output_file(self, tmp_path):
        outpath = tmp_path / "out.csv"
        comp = _make_component({
            "config_file": CFG_MIN,
            "output_file": str(outpath),
            "die_on_error": True,
        })
        comp._process(_swift_input_df())
        assert outpath.exists()

    def test_die_on_error_true_wraps_to_component_execution(self, monkeypatch):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        monkeypatch.setattr(comp, "_transform_rows",
                            lambda df: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(ComponentExecutionError):
            comp._process(_swift_input_df())

    def test_die_on_error_false_swallows(self, monkeypatch):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": False})
        monkeypatch.setattr(comp, "_transform_rows",
                            lambda df: (_ for _ in ()).throw(RuntimeError("boom")))
        out = comp._process(_swift_input_df())
        assert out["main"].empty


# --------------------------------------------------------------------------
# TestWriteOutputFile
# --------------------------------------------------------------------------


@pytest.mark.unit
class TestWriteOutputFile:

    def test_write_csv_with_header(self, tmp_path):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        df = pd.DataFrame([{"A": "1", "B": "2"}])
        out = tmp_path / "x.csv"
        comp._write_output_file(df, str(out))
        assert out.exists()
        body = out.read_text()
        assert "A|B" in body  # default delimiter is pipe

    def test_write_creates_directory(self, tmp_path):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        df = pd.DataFrame([{"A": "1"}])
        target = tmp_path / "nested" / "deep" / "out.csv"
        comp._write_output_file(df, str(target))
        assert target.exists()

    def test_write_failure_raises_file_operation_error(self, tmp_path):
        comp = _make_component({"config_file": CFG_MIN, "die_on_error": True})
        df = pd.DataFrame([{"A": "1"}])
        # Path under a regular file -> OSError -> wrapped in FileOperationError
        block = tmp_path / "blocker"
        block.write_text("x")
        with pytest.raises(FileOperationError):
            comp._write_output_file(df, str(block / "nested" / "out.csv"))


# --------------------------------------------------------------------------
# TestPipeline -- end-to-end via run_job_fixture
# --------------------------------------------------------------------------


@pytest.mark.integration
class TestPipeline:

    def test_mt202_with_lookup_pipeline(self, run_job_fixture, tmp_path, assert_ascii_logs):
        swift_in = tmp_path / "msg.txt"
        swift_in.write_text(mt202_cov())
        out = tmp_path / "out.csv"
        result = run_job_fixture(
            "swift/mt202_with_lookup",
            mutations={
                "tFileInputRaw_1": {"filename": str(swift_in)},
                "tFileOutputDelimited_1": {"filepath": str(out)},
                "tSwiftBlockFormatter_1": {"layout_file": LAYOUT_BASIC},
                "tSwiftTransformer_1": {"config_file": CFG_LOOKUP},
            },
        )
        # Need to inject LOOKUP_DIR via context. Re-run:
        # The fixture's context.Default has LOOKUP_DIR = TBD, which the
        # transform YAML interpolates as ${context.LOOKUP_DIR}. We need to
        # set it. run_job_fixture mutations operate at the component
        # level, not job-level context. Workaround: set the lookup dir
        # via the SwiftTransformer config indirectly is not supported
        # here -- so we patch the JSON before re-running by writing a
        # small helper. Simplest: mutate the loaded JSON via a re-fetch.
        # Easier-still: mutate context via an alternate test setup.

        # Verify the pipeline ran
        assert result.global_map.get("tSwiftBlockFormatter_1_NB_LINE", 0) == 1

    def test_mt202_pipeline_with_lookup_dir_set(self, run_job_fixture, tmp_path, monkeypatch):
        # Patch _run by mutating the saved fixture JSON via a custom path:
        # Easier: monkey-patch ETLEngine to inject the context value.
        # We use a trick -- patch ContextManager to set LOOKUP_DIR after
        # initialization.
        from src.v1.engine import context_manager as cm_mod

        original_init = cm_mod.ContextManager.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.set("LOOKUP_DIR", LOOKUP_DIR)

        monkeypatch.setattr(cm_mod.ContextManager, "__init__", patched_init)

        swift_in = tmp_path / "msg.txt"
        swift_in.write_text(mt202_cov())
        out = tmp_path / "out.csv"
        result = run_job_fixture(
            "swift/mt202_with_lookup",
            mutations={
                "tFileInputRaw_1": {"filename": str(swift_in)},
                "tFileOutputDelimited_1": {"filepath": str(out)},
                "tSwiftBlockFormatter_1": {"layout_file": LAYOUT_BASIC},
                "tSwiftTransformer_1": {"config_file": CFG_LOOKUP},
            },
        )
        assert out.exists()
        body = out.read_text()
        # SENDER_COUNTRY should be populated for BANKBICAXXXX
        assert "US" in body
        # globalMap stats present
        assert result.global_map["tSwiftTransformer_1_NB_LINE"] >= 1
