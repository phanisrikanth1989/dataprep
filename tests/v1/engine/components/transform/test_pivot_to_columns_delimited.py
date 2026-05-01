"""Tests for PivotToColumnsDelimited (tPivotToColumnsDelimited) engine component.

Covers:
- Component registration (V1 alias, Talend alias, BaseComponent inheritance)
- _validate_config() raises ConfigurationError on missing/invalid structural keys
- Pivot operation correctness for all aggregation functions
- File output: separator, lineterminator, encoding, create=False, parent dirs
- Separator handling: escape sequences, context variable deferral
- Edge cases: None input, empty DF, delete_emptyfile behaviour
- GlobalMap variables: NB_LINE, NB_LINE_OK, NB_LINE_OUT
- Re-execution: config immutability across multiple execute() calls
"""
import os

import pandas as pd
import pytest

from src.v1.engine.base_component import BaseComponent
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.pivot_to_columns_delimited import (
    PivotToColumnsDelimited,
    _unescape_separator,
)
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_component(config, global_map=None, context_manager=None):
    """Construct a PivotToColumnsDelimited with the given config."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    return PivotToColumnsDelimited(
        component_id="tPivot_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )


def _sample_df():
    """4-row DataFrame: region x category pivot, amount values."""
    return pd.DataFrame({
        "region": ["N", "N", "S", "S"],
        "category": ["A", "B", "A", "B"],
        "amount": [10, 20, 30, 40],
    })


def _base_config(tmp_path, **overrides):
    """Minimal valid config using D-38 config key names."""
    cfg = {
        "pivot_column": "category",
        "aggregation_column": "amount",
        "aggregation_function": "sum",
        "groupbys": ["region"],
        "filename": str(tmp_path / "out.csv"),
        "create": True,
        "fieldseparator": ";",
        "rowseparator": "\\n",
        "encoding": "ISO-8859-15",
        "advanced_separator": False,
        "thousands_separator": ",",
        "decimal_separator": ".",
        "csv_option": False,
        "escape_char": '"',
        "text_enclosure": '"',
        "delete_emptyfile": False,
        "tstatcatcher_stats": False,
        "label": "",
    }
    cfg.update(overrides)
    return cfg


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component is registered under both V1 and Talend aliases."""

    def test_registered_under_v1_name(self):
        assert REGISTRY.get("PivotToColumnsDelimited") is PivotToColumnsDelimited

    def test_registered_under_talend_name(self):
        assert REGISTRY.get("tPivotToColumnsDelimited") is PivotToColumnsDelimited

    def test_instance_is_base_component(self, tmp_path):
        comp = _make_component(_base_config(tmp_path))
        assert isinstance(comp, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config() raises ConfigurationError on missing/invalid keys."""

    def test_missing_pivot_column_raises(self, tmp_path):
        cfg = _base_config(tmp_path)
        del cfg["pivot_column"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="pivot_column"):
            comp.execute(pd.DataFrame())

    def test_missing_aggregation_column_raises(self, tmp_path):
        cfg = _base_config(tmp_path)
        del cfg["aggregation_column"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="aggregation_column"):
            comp.execute(pd.DataFrame())

    def test_missing_groupbys_raises(self, tmp_path):
        cfg = _base_config(tmp_path)
        del cfg["groupbys"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="groupbys"):
            comp.execute(pd.DataFrame())

    def test_groupbys_not_list_raises(self, tmp_path):
        cfg = _base_config(tmp_path, groupbys="region")
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="groupbys"):
            comp.execute(pd.DataFrame())

    def test_missing_filename_raises(self, tmp_path):
        cfg = _base_config(tmp_path)
        del cfg["filename"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="filename"):
            comp.execute(pd.DataFrame())

    def test_empty_groupbys_list_passes_validate_deferred_to_process(self, tmp_path):
        """Empty list is structurally valid; emptiness check lives in _process."""
        cfg = _base_config(tmp_path, groupbys=[])
        comp = _make_component(cfg)
        # Set config directly so _validate_config() can see it (bypasses execute lifecycle)
        comp.config = dict(cfg)
        # Must NOT raise -- deferred per Rule 12
        comp._validate_config()


# ------------------------------------------------------------------
# TestPivotOperation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPivotOperation:
    """Pivot semantics: groupby -> pivot -> aggregate."""

    def test_basic_sum_pivot(self, tmp_path):
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg)
        result = comp.execute(_sample_df())
        df = result["main"]
        # Two regions -> 2 rows; 2 pivot values + 1 groupby = 3 cols
        assert len(df) == 2
        assert set(df.columns) == {"region", "A", "B"}

    def test_sum_values_correct(self, tmp_path):
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg)
        result = comp.execute(_sample_df())
        df = result["main"].set_index("region")
        assert df.loc["N", "A"] == 10
        assert df.loc["N", "B"] == 20
        assert df.loc["S", "A"] == 30
        assert df.loc["S", "B"] == 40

    def test_count_aggregation(self, tmp_path):
        cfg = _base_config(tmp_path, aggregation_function="count", create=False)
        comp = _make_component(cfg)
        result = comp.execute(_sample_df())
        df = result["main"].set_index("region")
        # Each region has exactly 1 row per category
        assert df.loc["N", "A"] == 1
        assert df.loc["S", "B"] == 1

    def test_min_aggregation(self, tmp_path):
        df_in = pd.DataFrame({
            "region": ["N", "N", "N"],
            "category": ["A", "A", "B"],
            "amount": [5, 10, 20],
        })
        cfg = _base_config(tmp_path, aggregation_function="min", create=False)
        comp = _make_component(cfg)
        result = comp.execute(df_in)
        assert result["main"].set_index("region").loc["N", "A"] == 5

    def test_max_aggregation(self, tmp_path):
        df_in = pd.DataFrame({
            "region": ["N", "N", "N"],
            "category": ["A", "A", "B"],
            "amount": [5, 10, 20],
        })
        cfg = _base_config(tmp_path, aggregation_function="max", create=False)
        comp = _make_component(cfg)
        result = comp.execute(df_in)
        assert result["main"].set_index("region").loc["N", "A"] == 10

    def test_multiple_groupbys(self, tmp_path):
        df_in = pd.DataFrame({
            "region": ["N", "N", "S", "S"],
            "year": [2023, 2023, 2023, 2023],
            "category": ["A", "B", "A", "B"],
            "amount": [1, 2, 3, 4],
        })
        cfg = _base_config(tmp_path, groupbys=["region", "year"], create=False)
        comp = _make_component(cfg)
        result = comp.execute(df_in)
        df = result["main"]
        assert "region" in df.columns
        assert "year" in df.columns
        assert "A" in df.columns
        assert "B" in df.columns

    def test_sparse_pivot_nan_replaced_with_empty_string(self, tmp_path):
        """Pivot cells with no data are filled with empty string, not NaN."""
        df_in = pd.DataFrame({
            "region": ["N", "S"],
            "category": ["A", "B"],  # N has no B, S has no A
            "amount": [10, 20],
        })
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg)
        result = comp.execute(df_in)
        df = result["main"].set_index("region")
        # Sparse cells should be empty string, not NaN
        assert df.loc["N", "B"] == ""
        assert df.loc["S", "A"] == ""

    def test_invalid_aggregation_function_raises(self, tmp_path):
        cfg = _base_config(tmp_path, aggregation_function="average")
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="aggregation_function"):
            comp.execute(_sample_df())

    def test_reject_is_none(self, tmp_path):
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg)
        result = comp.execute(_sample_df())
        assert result.get("reject") is None

    def test_pivot_column_order_matches_first_appearance(self, tmp_path):
        """Pivot value columns appear in first-seen input order, not alphabetical.

        Regression test: pd.pivot_table() sorts alphabetically (Feb, Jan, Mar).
        Talend preserves first-appearance order (Jan, Feb, Mar).
        """
        df_in = pd.DataFrame({
            "employee_id": [101, 101, 101, 102, 102, 102],
            "month":       ["Jan", "Feb", "Mar", "Jan", "Feb", "Mar"],
            "amount":      [1000, 1200, 900, 800, 950, 1100],
        })
        cfg = _base_config(
            tmp_path,
            pivot_column="month",
            aggregation_column="amount",
            groupbys=["employee_id"],
            create=False,
        )
        comp = _make_component(cfg)
        result = comp.execute(df_in)
        df = result["main"]
        value_cols = [c for c in df.columns if c != "employee_id"]
        assert value_cols == ["Jan", "Feb", "Mar"], (
            f"Expected ['Jan', 'Feb', 'Mar'] but got {value_cols}"
        )


# ------------------------------------------------------------------
# TestFileOutput
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFileOutput:
    """File write semantics: path, separator, lineterminator, encoding, create flag."""

    def test_file_created_at_filename(self, tmp_path):
        out = tmp_path / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out))
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        assert out.exists()

    def test_custom_fieldseparator_written(self, tmp_path):
        out = tmp_path / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out), fieldseparator="|")
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        content = out.read_text(encoding="ISO-8859-15")
        # Header row should use pipe separator
        assert "|" in content.splitlines()[0]

    def test_create_false_does_not_write_file(self, tmp_path):
        out = tmp_path / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out), create=False)
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        assert not out.exists()

    def test_parent_directory_created_automatically(self, tmp_path):
        out = tmp_path / "nested" / "deep" / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out))
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        assert out.exists()

    def test_encoding_applied(self, tmp_path):
        out = tmp_path / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out), encoding="utf-8")
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        # File must be readable as UTF-8
        content = out.read_text(encoding="utf-8")
        assert "region" in content


# ------------------------------------------------------------------
# TestSeparatorHandling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSeparatorHandling:
    """Separator escape-sequence decoding and validation."""

    def test_tab_separator_decoded(self, tmp_path):
        out = tmp_path / "pivot.tsv"
        cfg = _base_config(tmp_path, filename=str(out), fieldseparator="\\t")
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        content = out.read_text(encoding="ISO-8859-15")
        assert "\t" in content.splitlines()[0]

    def test_context_var_fieldseparator_accepted_at_validate(self, tmp_path):
        """${context.SEP} is structurally a string; deferral prevents false error."""
        cfg = _base_config(tmp_path, fieldseparator="${context.SEP}")
        comp = _make_component(cfg)
        # Set config directly so _validate_config() can see it (bypasses execute lifecycle)
        comp.config = dict(cfg)
        # _validate_config must not raise for a context-var string
        comp._validate_config()

    def test_multi_char_fieldseparator_raises_in_process(self, tmp_path):
        cfg = _base_config(tmp_path, fieldseparator="||")
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="single character"):
            comp.execute(_sample_df())

    def test_default_fieldseparator_is_semicolon(self, tmp_path):
        """Matches Talend/converter default ';'."""
        out = tmp_path / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out))
        del cfg["fieldseparator"]
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        content = out.read_text(encoding="ISO-8859-15")
        assert ";" in content.splitlines()[0]


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """None input, empty DataFrame, delete_emptyfile behaviour."""

    def test_none_input_returns_empty_main(self, tmp_path):
        cfg = _base_config(tmp_path)
        comp = _make_component(cfg)
        result = comp.execute(None)
        assert result["main"].empty

    def test_empty_df_input_returns_empty_main(self, tmp_path):
        cfg = _base_config(tmp_path)
        comp = _make_component(cfg)
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty

    def test_empty_groupbys_list_raises_in_process(self, tmp_path):
        """Non-empty input but empty groupbys triggers content error in _process."""
        cfg = _base_config(tmp_path, groupbys=[])
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError, match="groupbys"):
            comp.execute(_sample_df())

    def test_delete_emptyfile_true_empty_input_no_file(self, tmp_path):
        """When input is empty and delete_emptyfile=True, no file is written."""
        out = tmp_path / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out), delete_emptyfile=True)
        comp = _make_component(cfg)
        comp.execute(pd.DataFrame())
        assert not out.exists()

    def test_delete_emptyfile_false_with_data_writes_file(self, tmp_path):
        out = tmp_path / "pivot.csv"
        cfg = _base_config(tmp_path, filename=str(out), delete_emptyfile=False)
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        assert out.exists()


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """GlobalMap statistics written by the component."""

    def test_nb_line_equals_input_row_count(self, tmp_path):
        gm = GlobalMap()
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg, global_map=gm)
        comp.execute(_sample_df())
        assert gm.get_component_stat("tPivot_1", "NB_LINE") == 4

    def test_nb_line_ok_equals_output_row_count(self, tmp_path):
        gm = GlobalMap()
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg, global_map=gm)
        comp.execute(_sample_df())
        assert gm.get_component_stat("tPivot_1", "NB_LINE_OK") == 2

    def test_nb_line_out_equals_output_row_count(self, tmp_path):
        gm = GlobalMap()
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg, global_map=gm)
        comp.execute(_sample_df())
        assert gm.get_component_stat("tPivot_1", "NB_LINE_OUT") == 2

    def test_nb_line_reject_is_zero(self, tmp_path):
        gm = GlobalMap()
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg, global_map=gm)
        comp.execute(_sample_df())
        assert gm.get_component_stat("tPivot_1", "NB_LINE_REJECT") == 0

    def test_stats_on_empty_input(self, tmp_path):
        gm = GlobalMap()
        cfg = _base_config(tmp_path)
        comp = _make_component(cfg, global_map=gm)
        comp.execute(pd.DataFrame())
        assert gm.get_component_stat("tPivot_1", "NB_LINE") == 0
        assert gm.get_component_stat("tPivot_1", "NB_LINE_OUT") == 0


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    """Component can be re-executed multiple times without config mutation."""

    def test_config_unchanged_after_execute(self, tmp_path):
        cfg = _base_config(tmp_path, create=False)
        original_keys = set(cfg.keys())
        comp = _make_component(cfg)
        comp.execute(_sample_df())
        comp.execute(_sample_df())
        assert set(comp.config.keys()) == original_keys

    def test_reexecution_produces_same_result(self, tmp_path):
        cfg = _base_config(tmp_path, create=False)
        comp = _make_component(cfg)
        r1 = comp.execute(_sample_df())
        r2 = comp.execute(_sample_df())
        pd.testing.assert_frame_equal(
            r1["main"].reset_index(drop=True),
            r2["main"].reset_index(drop=True),
        )


# ------------------------------------------------------------------
# TestUnescapeSeparator (module-level helper)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestUnescapeSeparator:
    """_unescape_separator decodes escape sequences safely."""

    def test_newline(self):
        assert _unescape_separator("\\n") == "\n"

    def test_tab(self):
        assert _unescape_separator("\\t") == "\t"

    def test_carriage_return(self):
        assert _unescape_separator("\\r") == "\r"

    def test_crlf(self):
        assert _unescape_separator("\\r\\n") == "\r\n"

    def test_plain_char_unchanged(self):
        assert _unescape_separator(";") == ";"

    def test_pipe_unchanged(self):
        assert _unescape_separator("|") == "|"

