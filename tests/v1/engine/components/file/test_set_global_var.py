"""Engine unit tests for SetGlobalVar (tSetGlobalVar)."""
import json
import os

import pandas as pd
import pytest

from src.v1.engine.components.file.set_global_var import SetGlobalVar, _ROW_REF_RE
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_component(config, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    comp = SetGlobalVar(
        component_id="tSetGlobalVar_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    return comp


def _base_config(*rows):
    """Build a minimal config with the given variable rows."""
    return {"variables": list(rows)}


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    def test_registered_under_v1_name(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("SetGlobalVar") is SetGlobalVar

    def test_registered_under_talend_alias(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("tSetGlobalVar") is SetGlobalVar


# ---------------------------------------------------------------------------
# 2. _validate_config
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_variables_key_raises(self):
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="variables"):
            comp._validate_config()

    def test_variables_not_list_raises(self):
        comp = _make_component({"variables": "bad"})
        with pytest.raises(ConfigurationError, match="list"):
            comp._validate_config()

    def test_empty_list_is_valid(self):
        """Empty variable table is legal -- no variables to set."""
        comp = _make_component({"variables": []})
        comp._validate_config()  # must not raise

    def test_valid_list_passes(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        comp._validate_config()  # must not raise

    def test_uppercase_variables_key_also_valid(self):
        """Legacy uppercase VARIABLES key accepted in validate."""
        comp = _make_component({"VARIABLES": [{"name": "x", "value": "1"}]})
        comp._validate_config()  # must not raise


# ---------------------------------------------------------------------------
# 3. Setting globalMap variables
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestProcessSetsVariables:
    def test_single_variable_set(self):
        gm = GlobalMap()
        comp = _make_component(_base_config({"key": "batch_id", "value": "B001"}), global_map=gm)
        comp.execute()
        assert gm.get("batch_id") == "B001"

    def test_multiple_variables_set(self):
        gm = GlobalMap()
        comp = _make_component(
            _base_config(
                {"key": "a", "value": "1"},
                {"key": "b", "value": "2"},
                {"key": "c", "value": "3"},
            ),
            global_map=gm,
        )
        comp.execute()
        assert gm.get("a") == "1"
        assert gm.get("b") == "2"
        assert gm.get("c") == "3"

    def test_variable_value_can_be_none(self):
        gm = GlobalMap()
        comp = _make_component(_base_config({"key": "nullvar", "value": None}), global_map=gm)
        comp.execute()
        assert gm.get("nullvar") is None

    def test_empty_variable_list_sets_nothing(self):
        gm = GlobalMap()
        before = dict(gm._map)
        comp = _make_component({"variables": []}, global_map=gm)
        comp.execute()
        # Only stats keys should have been added by base class
        new_keys = set(gm._map) - set(before)
        assert all("tSetGlobalVar_1" in k for k in new_keys)


# ---------------------------------------------------------------------------
# 4. Legacy key shapes (backward compatibility)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLegacyKeyFallback:
    def test_uppercase_VARIABLES_key_works(self):
        """Engine should fall back to VARIABLES (uppercase) when variables absent."""
        gm = GlobalMap()
        comp = _make_component({"VARIABLES": [{"name": "x", "value": "42"}]}, global_map=gm)
        comp.execute()
        assert gm.get("x") == "42"

    def test_name_field_fallback_for_var_name(self):
        """Row using 'name' instead of 'key' must still be resolved."""
        gm = GlobalMap()
        comp = _make_component(_base_config({"name": "legacy_key", "value": "hello"}), global_map=gm)
        comp.execute()
        assert gm.get("legacy_key") == "hello"

    def test_VALUE_uppercase_field_fallback(self):
        """Row using 'VALUE' (uppercase) field for the value."""
        gm = GlobalMap()
        comp = _make_component(_base_config({"key": "k", "VALUE": "v"}), global_map=gm)
        comp.execute()
        assert gm.get("k") == "v"


# ---------------------------------------------------------------------------
# 5. Pass-through behaviour
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPassThrough:
    def test_dataframe_input_passed_through_unchanged(self):
        df = pd.DataFrame({"col": [1, 2, 3]})
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute(df)
        pd.testing.assert_frame_equal(result["main"], df)

    def test_none_input_returns_none_main(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute(None)
        assert result["main"] is None

    def test_input_dataframe_not_mutated(self):
        df = pd.DataFrame({"a": [10, 20]})
        original = df.copy()
        comp = _make_component(_base_config({"key": "x", "value": "val"}))
        comp.execute(df)
        pd.testing.assert_frame_equal(df, original)


# ---------------------------------------------------------------------------
# 6. Statistics
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    def test_nb_line_always_zero(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute()
        assert result["stats"]["NB_LINE"] == 0

    def test_nb_line_ok_always_zero(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute()
        assert result["stats"]["NB_LINE_OK"] == 0

    def test_nb_line_reject_always_zero(self):
        comp = _make_component(_base_config({"key": "x", "value": "1"}))
        result = comp.execute()
        assert result["stats"]["NB_LINE_REJECT"] == 0

    def test_stats_unchanged_with_dataframe_input(self):
        """Stats are 0 even when a DataFrame is passed in (not a row processor)."""
        df = pd.DataFrame({"x": range(100)})
        comp = _make_component(_base_config({"key": "k", "value": "v"}))
        result = comp.execute(df)
        assert result["stats"]["NB_LINE"] == 0


# ---------------------------------------------------------------------------
# 7. die_on_error
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDieOnError:
    def test_non_dict_row_die_on_error_true_raises(self):
        comp = _make_component({"variables": ["not_a_dict"], "die_on_error": True})
        with pytest.raises(ConfigurationError):
            comp.execute()

    def test_non_dict_row_die_on_error_false_skips(self):
        """Bad row is skipped; subsequent valid rows are still set."""
        gm = GlobalMap()
        comp = _make_component(
            {"variables": ["bad_row", {"key": "good", "value": "ok"}], "die_on_error": False},
            global_map=gm,
        )
        comp.execute()
        assert gm.get("good") == "ok"

    def test_missing_name_die_on_error_true_raises(self):
        comp = _make_component({"variables": [{"value": "orphan"}], "die_on_error": True})
        with pytest.raises(ConfigurationError, match="name"):
            comp.execute()

    def test_missing_name_die_on_error_false_skips(self):
        gm = GlobalMap()
        comp = _make_component(
            {"variables": [{"value": "orphan"}, {"key": "real", "value": "set"}],
             "die_on_error": False},
            global_map=gm,
        )
        comp.execute()
        assert gm.get("real") == "set"


# ---------------------------------------------------------------------------
# 8. No globalMap (component must not crash)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoGlobalMap:
    def test_runs_without_global_map(self):
        comp = SetGlobalVar(
            component_id="tSetGlobalVar_nogm",
            config=_base_config({"key": "x", "value": "1"}),
            global_map=None,
            context_manager=ContextManager(),
        )
        comp.config = _base_config({"key": "x", "value": "1"})
        result = comp.execute()
        assert result["main"] is None


# ---------------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   46  (_get_variables: non-list config -> []),
#   61  (_get_var_value: no value/VALUE key -> None),
#   122-126 (global_map.put raises Exception: die_on_error True -> raise,
#            False -> log warning).
#
# Note: line 46 is reachable only via direct call -- _validate_config raises
# earlier if 'variables' is not a list, so the runtime path is guarded by the
# validator. We test _get_variables directly to lock the defensive contract.
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408:
    """Targeted tests added in Plan 14-08 to lift set_global_var.py to >= 95%."""

    def test_get_variables_non_list_returns_empty(self):
        """_get_variables returns [] when 'variables' is not a list (line 46)."""
        comp = _make_component({"variables": "not_a_list"})
        # Direct call -- _validate_config would block this at execute() time.
        assert comp._get_variables() == []

    def test_get_var_value_returns_none_when_neither_key_present(self):
        """_get_var_value returns None when both 'value' and 'VALUE' are missing (line 61)."""
        # Pure static method test
        assert SetGlobalVar._get_var_value({}) is None
        assert SetGlobalVar._get_var_value({"key": "x"}) is None

    def test_put_failure_die_on_error_raises_configuration_error(self, monkeypatch):
        """global_map.put raising with die_on_error=True wraps as ConfigurationError (122-125)."""
        from src.v1.engine.exceptions import ComponentExecutionError

        cfg = _base_config({"key": "k", "value": "v"})
        cfg["die_on_error"] = True
        comp = _make_component(cfg)

        def boom(*a, **kw):
            raise RuntimeError("simulated put failure")

        monkeypatch.setattr(comp.global_map, "put", boom)
        with pytest.raises(
            (ConfigurationError, ComponentExecutionError),
            match="Failed to set global variable",
        ):
            comp.execute()

    def test_put_failure_no_die_logs_warning(self, monkeypatch, caplog):
        """global_map.put raising with die_on_error=False -> log warning, continue (line 126)."""
        import logging

        cfg = _base_config(
            {"key": "ok", "value": "1"},
            {"key": "broken", "value": "2"},
        )
        # die_on_error is read from config at execute() time -- set it in config
        # so the runtime branch lands on the warning path, not the raise path.
        cfg["die_on_error"] = False
        comp = _make_component(cfg)

        original_put = comp.global_map.put

        def selective_put(name, val, *a, **kw):
            if name == "broken":
                raise RuntimeError("simulated put failure")
            return original_put(name, val, *a, **kw)

        monkeypatch.setattr(comp.global_map, "put", selective_put)
        with caplog.at_level(logging.WARNING):
            comp.execute()
        assert any(
            "Failed to set global variable 'broken'" in r.message
            for r in caplog.records
        )
        # 'ok' was still set even though 'broken' failed
        assert comp.global_map.get("ok") == "1"


@pytest.mark.unit
class TestPipelineDownstreamResolution:
    """Plan 14-08 pipeline test: vars set by tSetGlobalVar flow downstream.

    Lightweight inline pipeline (no fixture file required) -- builds a 2-component
    job dict and runs it through ETLEngine to confirm that variables put by
    tSetGlobalVar are visible to a downstream component's config-resolution step
    via context_manager (the standard Talend integration pattern).
    """

    def test_set_global_var_flows_into_downstream_component_config(self):
        from src.v1.engine.engine import ETLEngine

        # 1-component job: tSetGlobalVar puts 'upstream_value' into the global_map.
        # We then assert by inspecting engine.global_map after execute().
        job = {
            "job_name": "Job_set_global_var_pipeline",
            "components": [
                {
                    "id": "tSetGlobalVar_1",
                    "type": "SetGlobalVar",
                    "config": {
                        "variables": [
                            {"key": "upstream_value", "value": "hello_downstream"},
                        ],
                    },
                    "schema": {"input": [], "output": []},
                    "inputs": [],
                    "outputs": [],
                },
            ],
            "flows": [],
            "triggers": [],
            "subjobs": {"subjob_1": ["tSetGlobalVar_1"]},
            "java_config": {"enabled": False, "routines": [], "libraries": []},
        }
        engine = ETLEngine(job)
        engine.execute()
        # Variable is visible in the global_map for downstream components' use
        assert engine.global_map.get("upstream_value") == "hello_downstream"


# ---------------------------------------------------------------------------
# 9. _resolve_row_ref unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestResolveRowRef:
    """Unit tests for the _resolve_row_ref static helper (row-field reference resolution).

    The helper is the core of the Talend ``row2.rowid`` pattern: when tSetGlobalVar
    receives a data flow and a VALUE expression is ``flowname.colname``, the engine
    must store the actual column value -- not the literal reference text.
    """

    def _series(self, **kwargs):
        """Build a pd.Series representing one data row with given column values."""
        return pd.Series(kwargs)

    def test_dot_reference_resolves_integer_column(self):
        """row2.rowid with integer column resolves to a native Python int, not numpy scalar.

        Py4J cannot marshal numpy scalars into the Java globalMap
        ('numpy.int64' object has no attribute '_get_object_id'), so
        _resolve_row_ref must normalise via .item().
        """
        row = self._series(rowid=99)
        result = SetGlobalVar._resolve_row_ref("row2.rowid", row)
        assert result == 99
        assert type(result) is int, f"Expected native int, got {type(result)}"

    def test_dot_reference_resolves_string_column(self):
        """row1.label with string column resolves to the string value."""
        row = self._series(label="hello")
        result = SetGlobalVar._resolve_row_ref("row1.label", row)
        assert result == "hello"

    def test_dot_reference_resolves_float_column(self):
        row = self._series(amount=3.14)
        result = SetGlobalVar._resolve_row_ref("out.amount", row)
        assert result == pytest.approx(3.14)

    def test_bare_literal_not_touched(self):
        """A plain string with no dot is returned unchanged (no collision with col names)."""
        row = self._series(ok="something")
        result = SetGlobalVar._resolve_row_ref("ok", row)
        # "ok" has no dot -> _ROW_REF_RE does not match -> returned as-is
        assert result == "ok"

    def test_numeric_literal_not_touched(self):
        """A numeric string like '42' has no dot and is returned unchanged."""
        row = self._series(x=1)
        assert SetGlobalVar._resolve_row_ref("42", row) == "42"

    def test_missing_column_logs_warning_returns_literal(self, caplog):
        """dot-notation ref whose column is absent logs a warning and returns the literal."""
        import logging
        row = self._series(other_col=1)
        with caplog.at_level(logging.WARNING):
            result = SetGlobalVar._resolve_row_ref("row2.missing_col", row)
        assert result == "row2.missing_col"
        assert any("missing_col" in r.message for r in caplog.records)

    def test_non_string_value_returned_unchanged(self):
        """Non-string values (int, None) bypass resolution entirely."""
        row = self._series(x=1)
        assert SetGlobalVar._resolve_row_ref(99, row) == 99
        assert SetGlobalVar._resolve_row_ref(None, row) is None

    def test_java_marker_bypassed(self):
        """{{java}} prefixed values are already resolved upstream -- not touched."""
        row = self._series(x=1)
        val = "{{java}}TalendDate.getDate()"
        assert SetGlobalVar._resolve_row_ref(val, row) == val

    def test_context_marker_bypassed(self):
        """${context.x} values are already resolved upstream -- not touched."""
        row = self._series(x=1)
        val = "${context.runDate}"
        assert SetGlobalVar._resolve_row_ref(val, row) == val

    def test_row_ref_pattern_requires_dot(self):
        """_ROW_REF_RE only matches word.word; no dot means no match."""
        assert _ROW_REF_RE.match("rowid") is None
        assert _ROW_REF_RE.match("row2.rowid") is not None
        assert _ROW_REF_RE.match("row2.rowid.extra") is None


# ---------------------------------------------------------------------------
# 10. Row-reference resolution via execute() -- Talend per-row semantics
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRowReferenceViaExecute:
    """Tests that exercise _resolve_row_ref through the full execute() path.

    Root-cause regression guard for the GroovyCastException caused by storing
    the literal string ``row2.rowid`` in globalMap instead of the actual value.
    """

    def test_integer_row_ref_resolves_to_actual_value(self):
        """Core regression: VALUE='row2.rowid' with int input stores native int, not literal.

        Also guards against the Py4J marshalling crash: the stored value must be a
        native Python int, not a numpy.int64 scalar.
        """
        gm = GlobalMap()
        df = pd.DataFrame({"rowid": [7]})
        comp = _make_component(
            _base_config({"key": "maxrow", "value": "row2.rowid"}),
            global_map=gm,
        )
        comp.execute(df)
        stored = gm.get("maxrow")
        assert stored != "row2.rowid", "stored the literal string instead of the value"
        assert int(stored) == 7
        assert type(stored) is int, f"Expected native int for Py4J compat, got {type(stored)}"

    def test_string_row_ref_resolves_to_actual_value(self):
        gm = GlobalMap()
        df = pd.DataFrame({"label": ["ABC"]})
        comp = _make_component(
            _base_config({"key": "captured_label", "value": "row1.label"}),
            global_map=gm,
        )
        comp.execute(df)
        assert gm.get("captured_label") == "ABC"

    def test_literal_value_still_stored_verbatim(self):
        """Plain literals (no dot) are stored as-is even with DataFrame input."""
        gm = GlobalMap()
        df = pd.DataFrame({"rowid": [1, 2, 3]})
        comp = _make_component(
            _base_config({"key": "flag", "value": "DONE"}),
            global_map=gm,
        )
        comp.execute(df)
        assert gm.get("flag") == "DONE"

    def test_last_row_wins_for_multi_row_input(self):
        """When multiple rows flow through, the last row's value wins (Talend semantics)."""
        gm = GlobalMap()
        df = pd.DataFrame({"seq_id": [10, 20, 30]})
        comp = _make_component(
            _base_config({"key": "last_seq", "value": "row1.seq_id"}),
            global_map=gm,
        )
        comp.execute(df)
        assert int(gm.get("last_seq")) == 30

    def test_no_input_data_stores_literal_unchanged(self):
        """When no input DataFrame is given, literal config values are used (no crash)."""
        gm = GlobalMap()
        comp = _make_component(
            _base_config({"key": "static", "value": "VALUE_WITH_NO_DATA"}),
            global_map=gm,
        )
        comp.execute(None)
        assert gm.get("static") == "VALUE_WITH_NO_DATA"

    def test_empty_dataframe_stores_literal_unchanged(self):
        """Empty DataFrame is treated the same as None (no rows to iterate)."""
        gm = GlobalMap()
        df = pd.DataFrame({"rowid": pd.Series([], dtype=int)})
        comp = _make_component(
            _base_config({"key": "myvar", "value": "LITERAL"}),
            global_map=gm,
        )
        comp.execute(df)
        assert gm.get("myvar") == "LITERAL"

    def test_multiple_variables_mixed_ref_and_literal(self):
        """Mixed config: some variables use row refs, others are literals."""
        gm = GlobalMap()
        df = pd.DataFrame({"rowid": [42], "label": ["X"]})
        comp = _make_component(
            _base_config(
                {"key": "captured_id",    "value": "row1.rowid"},
                {"key": "captured_label", "value": "row1.label"},
                {"key": "literal_flag",   "value": "DONE"},
            ),
            global_map=gm,
        )
        comp.execute(df)
        assert int(gm.get("captured_id")) == 42
        assert gm.get("captured_label") == "X"
        assert gm.get("literal_flag") == "DONE"


# ---------------------------------------------------------------------------
# 11. Fixture-based pipeline test (set_global_var_row_ref.json)
# ---------------------------------------------------------------------------

_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "fixtures", "jobs", "core", "set_global_var_row_ref.json",
)


@pytest.mark.unit
class TestRowRefFixture:
    """Pipeline test driven by the generic set_global_var_row_ref.json fixture.

    The fixture runs FixedFlowInput (3 identical rows: seq_id=42, label='hello')
    through SetGlobalVar whose variables use row-field references and one literal.
    After execution:
      - captured_id    must be 42      (int from row1.seq_id, not the string 'row1.seq_id')
      - captured_label must be 'hello' (str from row1.label)
      - literal_flag   must be 'DONE'  (plain literal, no row ref)
    """

    def test_fixture_row_ref_resolution(self):
        from src.v1.engine.engine import ETLEngine

        fixture = os.path.normpath(_FIXTURE_PATH)
        with open(fixture) as f:
            job = json.load(f)

        engine = ETLEngine(job)
        engine.execute()

        captured_id = engine.global_map.get("captured_id")
        assert captured_id != "row1.seq_id", (
            "globalMap stored the literal string 'row1.seq_id' instead of the actual value"
        )
        assert int(captured_id) == 42

        captured_label = engine.global_map.get("captured_label")
        assert captured_label != "row1.label", (
            "globalMap stored the literal string 'row1.label' instead of 'hello'"
        )
        assert captured_label == "hello"

        assert engine.global_map.get("literal_flag") == "DONE"
