"""Tests for SchemaComplianceCheck (tSchemaComplianceCheck engine component)."""
import pytest
import pandas as pd

from src.v1.engine.components.transform.schema_compliance_check import (
    SchemaComplianceCheck,
    _java_to_strptime,
)
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers / shared fixtures
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None):
    """Create a SchemaComplianceCheck instance with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config if config is not None else _minimal_config()
    return SchemaComplianceCheck(
        component_id="tSchemaComplianceCheck_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )


def _minimal_config(**overrides):
    """Return a minimal valid config with three columns (int/str/float)."""
    base = {
        "schema": [
            {"name": "id",    "type": "int",   "nullable": False, "length": -1, "date_pattern": ""},
            {"name": "name",  "type": "str",   "nullable": True,  "length": 20, "date_pattern": ""},
            {"name": "score", "type": "float", "nullable": True,  "length": -1, "date_pattern": ""},
        ],
        "check_all":                   True,
        "check_another":               False,
        "checkcols":                   [],
        "all_empty_are_null":          True,
        "empty_null_table":            [],
        "strict_date_check":           False,
        "check_string_by_byte_length": False,
        "charset":                     "",
    }
    base.update(overrides)
    return base


def _single_col_config(name, col_type, nullable=True, length=-1, date_pattern="", **extra):
    """Return a config with a single schema column."""
    return _minimal_config(
        schema=[{"name": name, "type": col_type, "nullable": nullable,
                 "length": length, "date_pattern": date_pattern}],
        **extra,
    )


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

class TestRegistration:
    """Component must be reachable under both V1 and Talend alias names."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("SchemaComplianceCheck") is SchemaComplianceCheck

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tSchemaComplianceCheck") is SchemaComplianceCheck


# ------------------------------------------------------------------
# TestValidation  (_validate_config rules)
# ------------------------------------------------------------------

class TestValidation:
    """_validate_config must raise ConfigurationError for structural problems."""

    def test_missing_schema_key_raises(self):
        comp = _make_component(config={"check_all": True})
        with pytest.raises(ConfigurationError, match="Missing required config key 'schema'"):
            comp.execute()

    def test_schema_not_list_raises(self):
        comp = _make_component(config={"schema": "not_a_list"})
        with pytest.raises(ConfigurationError, match="must be a list"):
            comp.execute()

    def test_schema_column_not_dict_raises(self):
        comp = _make_component(config={"schema": ["not_a_dict"]})
        with pytest.raises(ConfigurationError, match="must be a dict"):
            comp.execute()

    def test_schema_column_missing_name_raises(self):
        comp = _make_component(config={"schema": [{"type": "str"}]})
        with pytest.raises(ConfigurationError, match="missing required key 'name'"):
            comp.execute()

    def test_schema_column_missing_type_raises(self):
        comp = _make_component(config={"schema": [{"name": "x"}]})
        with pytest.raises(ConfigurationError, match="missing required key 'type'"):
            comp.execute()

    def test_valid_minimal_config_does_not_raise(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame({"id": [1], "name": ["a"], "score": [1.0]}))
        assert "main" in result


# ------------------------------------------------------------------
# TestCoreNullability
# ------------------------------------------------------------------

class TestCoreNullability:
    """Non-nullable columns must reject null/empty values."""

    def test_null_in_non_nullable_column_rejected(self):
        comp = _make_component(config=_minimal_config())
        df = pd.DataFrame({"id": [1, None, 3], "name": ["a", "b", "c"], "score": [1.0, 2.0, 3.0]})
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert len(result["reject"]) == 1
        assert "cannot be null" in result["reject"]["errorMessage"].iloc[0]
        assert "id" in result["reject"]["errorMessage"].iloc[0]

    def test_null_in_nullable_column_passes(self):
        comp = _make_component(config=_minimal_config())
        df = pd.DataFrame({"id": [1, 2], "name": [None, "b"], "score": [None, 2.0]})
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["reject"].empty

    def test_empty_string_treated_as_null_when_all_empty_are_null_true(self):
        comp = _make_component(config=_minimal_config(all_empty_are_null=True))
        # "" in non-nullable int col -> treated as null -> rejected
        df = pd.DataFrame({"id": ["", 2], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "cannot be null" in result["reject"]["errorMessage"].iloc[0]

    def test_whitespace_only_string_treated_as_null(self):
        comp = _make_component(config=_minimal_config(all_empty_are_null=True))
        df = pd.DataFrame({"id": ["   ", 2], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1


# ------------------------------------------------------------------
# TestCoreAllEmptyAreNull
# ------------------------------------------------------------------

class TestCoreAllEmptyAreNull:
    """all_empty_are_null=False must NOT treat "" as null."""

    def test_all_empty_are_null_false_passes_empty_to_type_check(self):
        # all_empty_are_null=False: "" is NOT null, so "" in int col -> type error, not null error
        cfg = _minimal_config(all_empty_are_null=False)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"id": ["", 2], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "invalid type" in result["reject"]["errorMessage"].iloc[0]

    def test_per_column_override_false_ignored_when_global_true(self):
        # When all_empty_are_null=True the global flag wins; per-column False entries
        # from empty_null_table are ignored (matches Talend UI: table is show="false"
        # while ALL_EMPTY_ARE_NULL is checked).
        cfg = _minimal_config(
            all_empty_are_null=True,
            empty_null_table=[{"column": "id", "empty_is_null": False}],
        )
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"id": ["", 2], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        # Global flag still applies -> "" treated as null -> non-nullable -> rejected
        assert len(result["reject"]) == 1
        assert "cannot be null" in result["reject"]["errorMessage"].iloc[0]

    def test_talend_default_empty_null_table_all_false_does_not_cancel_global_flag(self):
        """Regression: Talend emits EMPTY_NULL_TABLE for every schema column with
        EMPTY_NULL=false as a default scaffold.  When ALL_EMPTY_ARE_NULL=true that
        table must be ignored; otherwise every empty-string would bypass null checks."""
        # Simulate what the converter produces for a real Talend job
        talend_scaffold = [
            {"column": "id",   "empty_is_null": False},
            {"column": "name", "empty_is_null": False},
        ]
        cfg = _minimal_config(
            all_empty_are_null=True,
            empty_null_table=talend_scaffold,
            # name must be non-nullable so empty "" triggers the check
            schema=[
                {"name": "id",    "type": "int", "nullable": False, "length": -1, "date_pattern": ""},
                {"name": "name",  "type": "str", "nullable": False, "length": -1, "date_pattern": ""},
                {"name": "score", "type": "float", "nullable": True, "length": -1, "date_pattern": ""},
            ],
        )
        comp = _make_component(config=cfg)
        # Row 0: name is empty -> non-nullable -> must be rejected
        df = pd.DataFrame({"id": [1, 2], "name": ["", "Bob"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1, (
            "Empty name should be rejected when all_empty_are_null=True, "
            "even when empty_null_table has empty_is_null=False for 'name'"
        )
        assert "name:cannot be null" in result["reject"]["errorMessage"].iloc[0]

    def test_per_column_empty_null_override_true_overrides_global_false(self):
        # Global all_empty_are_null=False but column 'id' overrides to True
        cfg = _minimal_config(
            all_empty_are_null=False,
            empty_null_table=[{"column": "id", "empty_is_null": True}],
        )
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"id": ["", 2], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        # "" in non-nullable id: override says empty_is_null=True -> treated as null -> null error
        assert len(result["reject"]) == 1
        assert "cannot be null" in result["reject"]["errorMessage"].iloc[0]


# ------------------------------------------------------------------
# TestCoreTypeCheck
# ------------------------------------------------------------------

class TestCoreTypeCheck:
    """Type coercion checks for int, float, Decimal, bool."""

    def test_non_coercible_string_in_int_col_rejected(self):
        comp = _make_component(config=_minimal_config())
        df = pd.DataFrame({"id": ["abc", 2], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "id:invalid type" in result["reject"]["errorMessage"].iloc[0]

    def test_numeric_string_passes_int_check(self):
        comp = _make_component(config=_minimal_config())
        df = pd.DataFrame({"id": ["42", 2], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["reject"].empty

    def test_float_type_check_rejects_non_numeric(self):
        cfg = _single_col_config("val", "float", nullable=False)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"val": ["not_a_float", "3.14", "1"]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "invalid type" in result["reject"]["errorMessage"].iloc[0]

    def test_decimal_type_check_rejects_non_numeric(self):
        cfg = _single_col_config("val", "Decimal", nullable=True)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"val": ["xyz", "123.45", None]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1

    def test_bool_type_valid_values_all_pass(self):
        cfg = _single_col_config("flag", "bool", nullable=False)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"flag": ["true", "false", "1", "0", True, False]})
        result = comp.execute(df)
        assert result["reject"].empty

    def test_bool_type_invalid_value_rejected(self):
        cfg = _single_col_config("flag", "bool", nullable=False)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"flag": ["maybe", "true"]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "flag:invalid type" in result["reject"]["errorMessage"].iloc[0]

    def test_str_type_always_passes_type_check(self):
        cfg = _single_col_config("tag", "str", nullable=True)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"tag": ["hello", "123", "True", None]})
        result = comp.execute(df)
        assert result["reject"].empty


# ------------------------------------------------------------------
# TestCoreLengthCheck
# ------------------------------------------------------------------

class TestCoreLengthCheck:
    """String length constraints (character and byte modes)."""

    def test_str_exceeding_max_length_rejected(self):
        cfg = _single_col_config("name", "str", nullable=True, length=5)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"name": ["Hi", "TooLongString", "OK"]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "name:exceed max length" in result["reject"]["errorMessage"].iloc[0]

    def test_str_at_exact_max_length_passes(self):
        cfg = _single_col_config("name", "str", nullable=True, length=5)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"name": ["Hello", "Hi"]})
        result = comp.execute(df)
        assert result["reject"].empty

    def test_no_length_check_when_length_is_minus_one(self):
        cfg = _single_col_config("name", "str", nullable=True, length=-1)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"name": ["A" * 10_000]})
        result = comp.execute(df)
        assert result["reject"].empty

    def test_byte_length_check_rejects_multibyte_chars(self):
        cfg = _single_col_config(
            "name", "str", nullable=True, length=3,
            check_string_by_byte_length=True, charset="utf-8",
        )
        comp = _make_component(config=cfg)
        # "café" is 5 bytes in UTF-8 (é = 2 bytes) -> exceeds limit of 3
        df = pd.DataFrame({"name": ["Hi", "café"]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1

    def test_length_check_not_applied_to_null_values(self):
        cfg = _single_col_config("name", "str", nullable=True, length=3)
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"name": [None, "HiThere"]})
        result = comp.execute(df)
        # None passes (nullable=True); "HiThere" exceeds 3 chars
        assert len(result["reject"]) == 1
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestCoreDateCheck
# ------------------------------------------------------------------

class TestCoreDateCheck:
    """Date pattern enforcement when strict_date_check=True."""

    def test_strict_date_check_invalid_date_rejected(self):
        cfg = _single_col_config(
            "dob", "datetime", nullable=True, date_pattern="yyyy-MM-dd",
            strict_date_check=True,
        )
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"dob": ["2024-01-15", "not-a-date", "2023-12-31"]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "dob:invalid date format" in result["reject"]["errorMessage"].iloc[0]

    def test_strict_date_check_all_valid_passes(self):
        cfg = _single_col_config(
            "dob", "datetime", nullable=True, date_pattern="yyyy-MM-dd",
            strict_date_check=True,
        )
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"dob": ["2024-01-15", "2023-12-31"]})
        result = comp.execute(df)
        assert result["reject"].empty

    def test_no_date_check_when_strict_date_check_false(self):
        cfg = _single_col_config(
            "dob", "datetime", nullable=True, date_pattern="yyyy-MM-dd",
            strict_date_check=False,
        )
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"dob": ["not-a-date", "2024-01-15"]})
        result = comp.execute(df)
        assert result["reject"].empty

    def test_no_date_check_without_date_pattern(self):
        cfg = _single_col_config(
            "dob", "datetime", nullable=True, date_pattern="",
            strict_date_check=True,
        )
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"dob": ["not-a-date"]})
        result = comp.execute(df)
        # No date_pattern -> no date format check even with strict_date_check=True
        assert result["reject"].empty


# ------------------------------------------------------------------
# TestCoreCheckAnother
# ------------------------------------------------------------------

class TestCoreCheckAnother:
    """check_another=True restricts validation to the checkcols list."""

    def test_check_another_skips_unlisted_columns(self):
        cfg = _minimal_config(
            check_another=True,
            checkcols=[
                {"column": "name", "selected_type": "str",
                 "date_pattern": "", "nullable": False, "max_length": False},
            ],
            schema=[
                {"name": "id",   "type": "int", "nullable": False, "length": -1, "date_pattern": ""},
                {"name": "name", "type": "str", "nullable": True,  "length": -1, "date_pattern": ""},
            ],
        )
        comp = _make_component(config=cfg)
        # id=None would violate nullability, but id is NOT in checkcols -> not checked
        # name=None violates checkcols nullable=False override -> rejected
        df = pd.DataFrame({"id": [None, 1], "name": [None, "Bob"]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        assert "name:cannot be null" in result["reject"]["errorMessage"].iloc[0]
        assert len(result["main"]) == 1

    def test_check_all_true_checks_all_columns(self):
        cfg = _minimal_config(
            check_all=True,
            check_another=False,
        )
        comp = _make_component(config=cfg)
        # Both id and name would violate -> both failures in the same row
        df = pd.DataFrame({"id": [None], "name": ["a"], "score": [1.0]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1


# ------------------------------------------------------------------
# TestRejectOutput
# ------------------------------------------------------------------

class TestRejectOutput:
    """Structural guarantees on the reject output."""

    def test_reject_rows_have_error_code_and_message(self):
        comp = _make_component(config=_minimal_config())
        df = pd.DataFrame({"id": [None], "name": ["a"], "score": [1.0]})
        result = comp.execute(df)
        reject = result["reject"]
        assert "errorCode"    in reject.columns
        assert "errorMessage" in reject.columns
        assert reject["errorCode"].iloc[0] == 8

    def test_multiple_violations_semicolon_delimited(self):
        cfg = _minimal_config(schema=[
            {"name": "id",   "type": "int", "nullable": False, "length": -1, "date_pattern": ""},
            {"name": "name", "type": "str", "nullable": False, "length": 3,  "date_pattern": ""},
        ])
        comp = _make_component(config=cfg)
        # id=None (null viol) + name="TooLong" (length viol) — both in the same row
        df = pd.DataFrame({"id": [None], "name": ["TooLong"]})
        result = comp.execute(df)
        assert len(result["reject"]) == 1
        msg = result["reject"]["errorMessage"].iloc[0]
        assert ";" in msg

    def test_reject_contains_original_column_values(self):
        comp = _make_component(config=_minimal_config())
        df = pd.DataFrame({"id": [None], "name": ["Alice"], "score": [5.0]})
        result = comp.execute(df)
        assert result["reject"]["name"].iloc[0] == "Alice"

    def test_valid_rows_preserved_unchanged(self):
        comp = _make_component(config=_minimal_config())
        df = pd.DataFrame({"id": [42], "name": ["Alice"], "score": [9.5]})
        result = comp.execute(df)
        assert result["main"]["id"].iloc[0] == 42
        assert result["main"]["name"].iloc[0] == "Alice"
        assert result["main"]["score"].iloc[0] == 9.5


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------

class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_none_input_returns_empty_dfs(self):
        comp = _make_component()
        result = comp.execute(None)
        assert result["main"].empty
        assert result["reject"].empty

    def test_empty_dataframe_returns_empty_dfs(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty
        assert result["reject"].empty

    def test_column_absent_from_input_skipped_gracefully(self):
        # Schema declares 'missing_col' but input doesn't have it — no error raised
        cfg = _minimal_config(schema=[
            {"name": "id",          "type": "int", "nullable": False, "length": -1, "date_pattern": ""},
            {"name": "missing_col", "type": "str", "nullable": False, "length": -1, "date_pattern": ""},
        ])
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"id": [1, 2]})
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["reject"].empty

    def test_all_rows_valid_produces_empty_reject(self):
        comp = _make_component()
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"], "score": [1.0, 2.0, 3.0]})
        result = comp.execute(df)
        assert len(result["main"]) == 3
        assert result["reject"].empty

    def test_all_rows_rejected_produces_empty_main(self):
        comp = _make_component()
        df = pd.DataFrame({"id": [None, None], "name": ["a", "b"], "score": [1.0, 2.0]})
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 2

    def test_stats_tracked_in_global_map(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = pd.DataFrame({"id": [1, None, 3], "name": ["a", "b", "c"], "score": [1.0, 2.0, 3.0]})
        comp.execute(df)
        assert gm.get_nb_line(comp.id)        == 3
        assert gm.get_nb_line_ok(comp.id)     == 2
        assert gm.get_nb_line_reject(comp.id) == 1

    def test_schema_with_zero_columns_passes_all_rows(self):
        cfg = _minimal_config(schema=[])
        comp = _make_component(config=cfg)
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["reject"].empty


# ------------------------------------------------------------------
# TestJavaToStrptime  (module-level helper)
# ------------------------------------------------------------------

class TestJavaToStrptime:
    """_java_to_strptime must convert common Java date tokens."""

    def test_yyyy_mm_dd(self):
        assert _java_to_strptime("yyyy-MM-dd") == "%Y-%m-%d"

    def test_with_time(self):
        result = _java_to_strptime("yyyy-MM-dd HH:mm:ss")
        assert result == "%Y-%m-%d %H:%M:%S"

    def test_two_digit_year(self):
        assert _java_to_strptime("yy/MM/dd") == "%y/%m/%d"
